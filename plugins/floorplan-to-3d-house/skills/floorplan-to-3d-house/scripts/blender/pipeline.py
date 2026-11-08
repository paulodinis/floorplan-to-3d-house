"""One launcher for the whole Blender video job: one MCP call, then poll one small JSON.

From the Blender MCP (live session) or any Python:
    import subprocess, sys, bpy
    subprocess.Popen([sys.executable, r"<scripts>/blender/pipeline.py", "<mode>", r"<dir>/params.json", bpy.app.binary_path],
                     creationflags=0x00000008 | 0x08000000, close_fds=True)        # Windows: detached, no window
or from a shell:  python pipeline.py <mode> <params.json> [<blender executable>]

modes
  build  import the GLB and run every pass (run_all.py) -> <blend>
  test   build, then render PARAMS["test_frames"] (default: 8 frames spread over the video, plus the door frames)
         at 50 % / 48 samples, time them, and write one contact sheet tests/sheet.jpg (look at this one image)
  final  build, start encode.py (waits for the frames, writes the MP4), render every frame
  check  print status.json (no Blender)
status: <dir>/pipeline_status.json  {mode, stage, ok, error, build: run_all result, test: {frame: s}, s_per_frame_est,
        frames_done, frames_total, eta_h, mp4}. Logs: <dir>/pipeline_<stage>.log. Read the status, not the logs.
"""
import json, os, sys, subprocess, time, glob, traceback

NOWIN = 0x08000000 if os.name == 'nt' else 0


def main():
    mode, params = sys.argv[1], sys.argv[2]
    P = json.load(open(params, encoding='utf-8')); D = P['dir']; SD = P.get('scripts_dir') or os.path.dirname(os.path.abspath(__file__))
    B = sys.argv[3] if len(sys.argv) > 3 else P.get('blender', 'blender')
    if os.path.basename(B).lower().startswith('blender-launcher'): B = os.path.join(os.path.dirname(B), 'blender.exe')
    stp = os.path.join(D, 'pipeline_status.json')
    st = json.load(open(stp)) if os.path.exists(stp) and mode == 'check' else dict(mode=mode, stage='start', ok=None, started=time.strftime('%Y-%m-%d %H:%M'))
    def save(**kw):
        st.update(kw); json.dump(st, open(stp, 'w'), indent=1)
    if mode == 'check':
        fr = len(glob.glob(os.path.join(D, 'frames', 'f_*.png'))); st['frames_done'] = fr
        print(json.dumps(st, indent=1)); return
    blend = os.path.join(D, P.get('blend', 'scene.blend'))
    try:
        save(stage='build')
        drv = os.path.join(D, '_pipeline_build.py')
        open(drv, 'w').write(
            "import json, runpy\n"
            f"P = json.load(open(r'{params}', encoding='utf-8'))\n"
            f"r = runpy.run_path(r'{os.path.join(SD, 'run_all.py')}', init_globals={{'PARAMS': P}})['result']\n"
            f"json.dump(r, open(r'{os.path.join(D, '_build_result.json')}', 'w'), indent=1)\n")
        subprocess.run([B, '-b', '--python', drv], stdout=open(os.path.join(D, 'pipeline_build.log'), 'w'), stderr=subprocess.STDOUT, creationflags=NOWIN)
        br = os.path.join(D, '_build_result.json')
        if not os.path.exists(br): raise RuntimeError('build failed: see pipeline_build.log')
        build = json.load(open(br)); os.remove(br); save(build=build)
        if mode == 'build': save(stage='done', ok=True); return
        if mode == 'test':
            n = P.get('frames_out', 375)
            fr = P.get('test_frames') or sorted(set([1 + i * (n - 1) // 7 for i in range(8)] + [min(n, d['frame'] + 40) for d in P.get('doors', [])][:6]))
            save(stage='test', test_frames=fr)
            drv = os.path.join(D, '_pipeline_test.py')
            open(drv, 'w').write(TEST.replace('__D__', D).replace('__FR__', json.dumps(fr)))
            subprocess.run([B, '-b', blend, '--python', drv], stdout=open(os.path.join(D, 'pipeline_test.log'), 'w'), stderr=subprocess.STDOUT, creationflags=NOWIN)
            tt = json.load(open(os.path.join(D, 'tests', 'times.json')))
            med = sorted(tt.values())[len(tt) // 2]
            res = P.get('res', [1600, 900]); smp = P.get('samples', 24)
            est = med * 4 * smp / 48 * 1.05                       # 50 % -> 100 % = 4x pixels; 48 -> final samples
            save(stage='done', ok=True, test=tt, sheet=os.path.join(D, 'tests', 'sheet.jpg'), s_per_frame_est=round(est, 1),
                 eta_h=round(est * n / 3600, 1), note='estimate from 50 % test frames; replaced by the measured time once the final render starts')
            return
        if mode == 'final':
            n = P.get('frames_out', 375); os.makedirs(os.path.join(D, 'frames'), exist_ok=True)
            env = dict(os.environ, CS_DIR=D, CS_TOTAL=str(n), CS_RES='%dx%d' % tuple(P.get('res', [1600, 900])), CS_OUT=P.get('video_name', 'video_'))
            subprocess.Popen([B, '-b', '--factory-startup', '--python', os.path.join(SD, 'encode.py')], env=env,
                             stdout=open(os.path.join(D, 'pipeline_encode.log'), 'w'), stderr=subprocess.STDOUT, creationflags=NOWIN)
            save(stage='render', frames_total=n)
            t0 = time.time()
            p = subprocess.Popen([B, '-b', blend, '-a'], stdout=open(os.path.join(D, 'pipeline_render.log'), 'w'), stderr=subprocess.STDOUT, creationflags=NOWIN)
            while p.poll() is None:
                time.sleep(60)
                done = len(glob.glob(os.path.join(D, 'frames', 'f_*.png')))
                if done:
                    spf = (time.time() - t0) / done
                    save(frames_done=done, s_per_frame=round(spf, 1), eta_h=round(spf * (n - done) / 3600, 1))
            for _ in range(120):                                       # wait for the encoder (up to 2 h)
                mp4 = glob.glob(os.path.join(D, env['CS_OUT'] + '*.mp4'))
                if mp4 and os.path.exists(os.path.join(D, env['CS_OUT'] + 'DONE.txt')):
                    save(stage='done', ok=True, mp4=mp4[0]); return
                time.sleep(60)
            save(stage='encode', ok=False, error='frames rendered, MP4 not written: see pipeline_encode.log')
    except BaseException:
        save(ok=False, error=traceback.format_exc()[-1500:])


TEST = r'''import bpy, os, json, time, numpy as np
D = r"__D__"; FR = __FR__
s = bpy.context.scene; s.render.resolution_percentage = 50; s.cycles.samples = 48
T = os.path.join(D, "tests"); os.makedirs(T, exist_ok=True); times = {}
for f in FR:
    t = time.time(); s.frame_set(f); s.render.filepath = os.path.join(T, "t_%04d.png" % f)
    bpy.ops.render.render(write_still=True); times[f] = round(time.time() - t, 1)
json.dump(times, open(os.path.join(T, "times.json"), "w"), indent=1)
# contact sheet: 4 columns of 480 px, frame number burnt in as a red bar length (no fonts in Blender Python)
tiles = []
for f in FR:
    im = bpy.data.images.load(os.path.join(T, "t_%04d.png" % f)); w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    sy, sx = max(1, h // 270), max(1, w // 480); a = a[::sy, ::sx][:270, :480]
    tile = np.zeros((270, 480, 4), np.float32); tile[:a.shape[0], :a.shape[1]] = a; tile[..., 3] = 1
    tile[:6, : max(4, int(480 * f / max(FR)))] = (1, 0, 0, 1)        # progress bar = position in the video
    tiles.append(tile); bpy.data.images.remove(im)
cols = 4; rows = (len(tiles) + cols - 1) // cols
sheet = np.zeros((rows * 270, cols * 480, 4), np.float32); sheet[..., 3] = 1
for i, t in enumerate(tiles): sheet[(i // cols) * 270:(i // cols + 1) * 270, (i % cols) * 480:(i % cols + 1) * 480] = t
img = bpy.data.images.new("sheet", cols * 480, rows * 270); img.pixels = sheet[::-1].ravel()
img.filepath_raw = os.path.join(T, "sheet.jpg"); img.file_format = "JPEG"; img.save()
json.dump(FR, open(os.path.join(T, "sheet_frames.json"), "w"))
'''

if __name__ == '__main__':
    main()
