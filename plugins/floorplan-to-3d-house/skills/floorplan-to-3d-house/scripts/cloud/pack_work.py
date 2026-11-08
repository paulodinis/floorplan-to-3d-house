"""Pack (or unpack) a project version's work files, so the next session starts from them instead of rebuilding.

pack:    python3 pack_work.py pack <work dir> <out.zip>      -> project.json, site3d/*.json, site3d/tex masks,
         export/plan_v*.png/.dxf/.grid.json, export/camera*.json, export/qa.md (no GLB, renders or textures)
unpack:  python3 pack_work.py unpack <work.zip> <work dir>
Keep one zip per version next to the deliverables on the user's PC: <Project>/v<n>/work_v<n>.zip.
"""
import sys, os, zipfile, glob
mode, a, b = sys.argv[1:4]
KEEP = ['project.json', 'site3d/*.json', 'site3d/tex/mask*.png', 'site3d/tex/v2_mask*.png', 'export/plan*.png', 'export/plan*.dxf',
        'export/plan*.grid.json', 'export/camera*.json', 'export/qa.md', '*.json']
if mode == 'pack':
    n = 0
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        seen = set()
        for pat in KEEP:
            for f in glob.glob(os.path.join(a, pat)):
                r = os.path.relpath(f, a)
                if r in seen or os.path.getsize(f) > 30e6: continue
                seen.add(r); z.write(f, r); n += 1
    print('packed', n, 'files ->', b, round(os.path.getsize(b) / 1e6, 2), 'MB')
elif mode == 'unpack':
    os.makedirs(b, exist_ok=True); zipfile.ZipFile(a).extractall(b); print('unpacked ->', b)
else:
    sys.exit(__doc__)
