"""Design QA for layout.json, run before showing the 2D plan and again before the 3D build.

Usage (from the project work dir):  python3 validate_layout.py project.json [site3d/layout.json] [--md report.md]
Exit code 1 if any ERROR. Thresholds are generic good practice, NOT a building-code check: override them in
project.json "qa" and always tell the user that local rules (zoning plan, building code) decide.
"""
import json, math, sys

argv = sys.argv[1:]
flag_vals = {argv[i + 1] for i, a in enumerate(argv[:-1]) if a == '--md'}
args = [a for a in argv if not a.startswith('--') and a not in flag_vals]
P = json.load(open(args[0], encoding='utf-8'))
L = json.load(open(args[1] if len(args) > 1 else 'site3d/layout.json', encoding='utf-8'))
md_out = sys.argv[sys.argv.index('--md') + 1] if '--md' in sys.argv else None
Q = dict(setback_min=P.get('setback_min', 3.0), area_limit=P.get('area_limit'), riser_max=0.18, going_min=0.27,
         blondel=(0.60, 0.66), stair_width_min=0.90, door_min=0.70, front_door_min=0.90, garage_door_min=2.40,
         corridor_min=0.90, bedroom_min_area=9.0, bedroom_min_side=2.40, wc_min_area=2.5, landing_min=0.90)
Q.update(P.get('qa', {}))
ERR, WARN, OK = [], [], []


def seg_proj(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]; l2 = dx * dx + dz * dz
    u = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2
    return u, (a[0] + u * dx, a[1] + u * dz)


def area(poly):
    return 0.5 * abs(sum(poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1] for i in range(len(poly))))


def bbox(poly):
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    return min(xs), min(zs), max(xs), max(zs)


# 1) floor area
tot = sum(b['area'] for b in L['blocks'].values())
if Q['area_limit']:
    (ERR if tot > Q['area_limit'] * 1.005 else OK).append(f'Total floor area {tot:.2f} m² vs limit {Q["area_limit"]} m²')
else:
    OK.append(f'Total floor area {tot:.2f} m² (no limit set)')

# 2) setbacks: nearest building corner to each plot edge
plot = L['plot']
corners = [(x, z) for b in L['blocks'].values() for x, z in ((b['rect'][0], b['rect'][1]), (b['rect'][2], b['rect'][1]), (b['rect'][2], b['rect'][3]), (b['rect'][0], b['rect'][3]))]
for i in range(len(plot)):
    a, b = plot[i - 1], plot[i]
    if math.dist(a, b) < 3: continue
    best = None
    for c in corners:
        u, f = seg_proj(c, a, b)
        if 0.05 < u < 0.95:
            d = math.dist(c, f)
            if best is None or d < best[0]: best = (d, c)
    if best and best[0] < 25:
        (ERR if best[0] < Q['setback_min'] else OK).append(f'Setback {best[0]:.2f} m from corner {best[1]} to plot edge {i} (min {Q["setback_min"]} m)')

# 3) stairs: riser, going, Blondel (2R + G), width, arrival space at the top
for k, st in enumerate(L.get('stairs', [])):
    n = st['n']; rise = abs(st['ytop'] - st['ybot']) / n; run = abs(st['x1'] - st['x0']) / n; w = abs(st['z1'] - st['z0'])
    bl = 2 * rise + run
    (ERR if rise > Q['riser_max'] + 0.01 else OK).append(f'Stair {k}: riser {rise * 100:.1f} cm (max {Q["riser_max"] * 100:.0f})')
    (ERR if run < Q['going_min'] else OK).append(f'Stair {k}: going {run * 100:.1f} cm (min {Q["going_min"] * 100:.0f})')
    (WARN if not Q['blondel'][0] <= bl <= Q['blondel'][1] else OK).append(f'Stair {k}: 2R+G = {bl * 100:.1f} cm (comfort {Q["blondel"][0] * 100:.0f}-{Q["blondel"][1] * 100:.0f})')
    (ERR if w < Q['stair_width_min'] else OK).append(f'Stair {k}: width {w:.2f} m (min {Q["stair_width_min"]})')
    top_x = st['x0'] if st['ytop'] >= st['ybot'] else st['x1']
    land = [f for f in L.get('floors', []) if abs(f['y'] - max(st['ytop'], st['ybot'])) < 0.05
            and bbox(f['poly'])[0] <= top_x - Q['landing_min'] and bbox(f['poly'])[2] >= top_x - 0.01
            and bbox(f['poly'])[1] <= st['z0'] + 0.01 and bbox(f['poly'])[3] >= st['z1'] - 0.01]
    (OK if land else WARN).append(f'Stair {k}: level floor of at least {Q["landing_min"]} m in front of the top step ' + ('found' if land else 'NOT found (check walls at the top)'))

# 4) openings
for w in L['walls']:
    for o in w.get('ops', []):
        k = o['kind']; mn = {'door': Q['door_min'], 'front': Q['front_door_min'], 'garage': Q['garage_door_min']}.get(k)
        if mn and o['w'] < mn - 1e-6:
            ERR.append(f'{k} opening {o["w"]:.2f} m < {mn} m in wall {w.get("tag") or w["a"]}')

# 5) rooms: area / narrowest side by type (names in EN or PT)
def kind(name):
    n = name.lower()
    if any(t in n for t in ('closet', 'roupeiro')): return 'closet'
    if any(t in n for t in ('wc', 'i.s', 'bath', 'banho')): return 'wc'
    if any(t in n for t in ('corr', 'hall', 'landing', 'patamar')): return 'corridor'
    if any(t in n for t in ('bed', 'quarto', 'suite')): return 'bedroom'
    return 'other'
for r in L.get('rooms', []):
    x0, z0, x1, z1 = bbox(r['poly']); side = min(x1 - x0, z1 - z0); a = r.get('area') or area(r['poly']); kd = kind(r['name'])
    if kd == 'bedroom':
        (ERR if a < Q['bedroom_min_area'] else OK).append(f'{r["name"]}: {a:.1f} m² (min {Q["bedroom_min_area"]})')
        if side < Q['bedroom_min_side']: WARN.append(f'{r["name"]}: narrowest side {side:.2f} m (< {Q["bedroom_min_side"]})')
    elif kd == 'wc' and a < Q['wc_min_area']:
        ERR.append(f'{r["name"]}: {a:.1f} m² (min {Q["wc_min_area"]})')
    elif kd == 'corridor' and side < Q['corridor_min']:
        ERR.append(f'{r["name"]}: width {side:.2f} m (min {Q["corridor_min"]})')

# 6) trees inside buildings
for t in L.get('trees', []):
    for b in L['blocks'].values():
        x0, z0, x1, z1 = b['rect']
        if x0 - 0.5 < t['x'] < x1 + 0.5 and z0 - 0.5 < t['z'] < z1 + 0.5:
            ERR.append(f'Tree at ({t["x"]}, {t["z"]}) stands in/against "{b["name"]}": move or mark as removed')

lines = [f'# Layout QA — {P.get("name", "")}', '', f'{len(ERR)} error(s), {len(WARN)} warning(s), {len(OK)} check(s) passed.',
         '', '_Generic good-practice thresholds, not a building-code check._', '']
for title, items in (('Errors', ERR), ('Warnings', WARN), ('Passed', OK)):
    if items: lines += [f'## {title}'] + [f'- {x}' for x in items] + ['']
report = '\n'.join(lines)
print(report)
if md_out: open(md_out, 'w', encoding='utf-8').write(report)
sys.exit(1 if ERR else 0)
