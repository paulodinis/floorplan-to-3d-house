"""Run with: blender -b --factory-startup --python encode.py  — waits for all frames, then writes the MP4."""
import bpy, os, time, glob
D = os.environ["CS_DIR"]
FR = os.path.join(D, "frames")
TOTAL = int(os.environ.get("CS_TOTAL", "375"))
OUT = os.environ.get("CS_OUT", "drone_")
while len(glob.glob(os.path.join(FR, "f_*.png"))) < TOTAL:
    time.sleep(30)
time.sleep(10)
files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(FR, "f_*.png")))[:TOTAL]
sc = bpy.context.scene
RES = [int(x) for x in os.environ.get('CS_RES', '1600x900').split('x')]
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
sc.render.fps = 25
sc.sequence_editor_create()
seq = sc.sequence_editor
strips = seq.strips if hasattr(seq, 'strips') else seq.sequences
st = strips.new_image(name="frames", filepath=os.path.join(FR, files[0]), channel=1, frame_start=1)
for f in files[1:]: st.elements.append(f)
sc.frame_start, sc.frame_end = 1, len(files)
sc.view_settings.view_transform = 'Standard'
r = sc.render
if hasattr(r.image_settings, 'media_type'):
    r.image_settings.media_type = 'VIDEO'
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format = 'MPEG4'; r.ffmpeg.codec = 'H264'
try: r.ffmpeg.constant_rate_factor = 'HIGH'
except Exception: pass
r.ffmpeg.ffmpeg_preset = 'GOOD'
r.filepath = os.path.join(D, OUT)
bpy.ops.render.render(animation=True)
open(os.path.join(D, OUT + "DONE.txt"), "w").write("ok")
