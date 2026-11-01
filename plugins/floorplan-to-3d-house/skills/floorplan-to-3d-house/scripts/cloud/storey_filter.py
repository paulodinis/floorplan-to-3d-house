"""Write the layout of ONE storey, for per-storey 2D plans (plan2d.py / plan2d_simple.py / elevations-free checks).

Usage:  python3 storey_filter.py site3d/layout.json <storey> site3d/layout_s<storey>.json [--label "First floor"]
Keeps walls, floors, rooms, furniture, slats, columns, railings, blocks and roofs whose "storey" (default 0) matches;
stairs are kept on the storey they start from AND on the storey they arrive at (drawn on both plans). Site data
(plot, grading, zones, trees, retaining...) is kept so setbacks and the site context still show.
Then:  LAYOUT_JSON=site3d/layout_s1.json python3 plan2d.py export/plan_s1.dxf /tmp/x.png
       python3 plan2d_simple.py site3d/layout_s1.json site3d/site.json export/plan_s1_v<n>.png export/plan_s1.dxf
"""
import json, sys

src, k, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
label = sys.argv[sys.argv.index('--label') + 1] if '--label' in sys.argv else None
L = json.load(open(src, encoding='utf-8'))
mine = lambda o: int(o.get('storey', 0)) == k
for key in ('walls', 'floors', 'rooms', 'furniture', 'slats', 'columns', 'railings', 'roofs'):
    if key in L: L[key] = [o for o in L[key] if mine(o)]
L['blocks'] = {n: b for n, b in L['blocks'].items() if mine(b)}
ys = {round(f['y'], 2) for f in L.get('floors', [])}
L['stairs'] = [st for st in L.get('stairs', []) if mine(st) or round(st['ytop'], 2) in ys]
if k > 0:   # upper storeys: no garden furniture / lights at ground level
    L['room_lights'] = [p for p in L.get('room_lights', []) if p[2] > min(ys or {0}) - 0.5]
L.setdefault('meta', {})['storey'] = k
L['meta']['storey_y'] = min((f['y'] for f in L.get('floors', []) if f.get('mat') != 'terrace'), default=0.0)   # plans skip walls starting > 1.5 m above it
if label: L['meta']['storey_label'] = label
json.dump(L, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
print(f'storey {k}: {len(L["walls"])} walls, {len(L.get("floors", []))} floors, {len(L.get("rooms", []))} rooms, {len(L["stairs"])} stairs, {len(L["blocks"])} blocks -> {out}')
