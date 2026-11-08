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
         corridor_min=0.90, bedroom_min_area=9.0, bedroom_min_side=2.40, wc_min_area=2.5, landing_min=0.90,
         headroom_min=2.0, guard_h=1.0, upper_sill_min=0.9)
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

# 7) storeys: headroom over stairs, guards at voids / upper terraces, low glazing on upper floors
def in_poly(x, z, poly):
    ins = False
    for i in range(len(poly)):
        (xi, zi), (xj, zj) = poly[i], poly[i - 1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi: ins = not ins
    return ins


def solid_at(x, z, f):
    return in_poly(x, z, f['poly']) and not any(in_poly(x, z, h) for h in f.get('holes', []))


FLOORS = L.get('floors', [])
for k, st in enumerate(L.get('stairs', [])):
    n = st['n']; rise = (st['ytop'] - st['ybot']) / n; run = (st['x1'] - st['x0']) / n; worst = None
    for i in range(1, n + 1):
        x, top = st['x0'] + (i - 0.5) * run, st['ytop'] - i * rise
        for zc in (st['z0'] + 0.1, (st['z0'] + st['z1']) / 2, st['z1'] - 0.1):
            for f in FLOORS:
                under = f['y'] - 0.35
                if under > top + 0.05 and solid_at(x, zc, f):
                    worst = under - top if worst is None else min(worst, under - top)
    if worst is not None:
        (ERR if worst < Q['headroom_min'] else OK).append(f'Stair {k}: headroom {worst:.2f} m under the slab above (min {Q["headroom_min"]})' + (': enlarge the void or move the stair' if worst < Q['headroom_min'] else ''))


def guarded(x, z, y, walls=True):
    for r in L.get('railings', []):
        if abs(r['y'] - y) < 0.3 and r.get('h', 1.0) >= Q['guard_h'] - 1e-6:
            u, f = seg_proj((x, z), r['a'], r['b'])
            if -0.02 <= u <= 1.02 and math.dist((x, z), f) < 0.3: return True
    for w in (L['walls'] if walls else []):
        if w['y0'] <= y + 0.1 and w['y0'] + w['h'] >= y + Q['guard_h']:
            u, f = seg_proj((x, z), w['a'], w['b'])
            if -0.02 <= u <= 1.02 and math.dist((x, z), f) < w['t'] / 2 + 0.3: return True
    for st in L.get('stairs', []):                    # arrival edge of a stair that tops out on this floor
        if abs(st['ytop'] - y) < 0.05 and st['z0'] - 0.05 <= z <= st['z1'] + 0.05 and abs(x - st['x0']) < 0.3: return True
    return False


def edge_check(poly, y, what):
    bad = 0.0
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]; Ln = math.dist(a, b); m = max(1, int(Ln / 0.25))
        for j in range(m):
            t = (j + 0.5) / m; x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            if not guarded(x, z, y): bad += Ln / m
    (WARN if bad > 0.3 else OK).append(f'{what}: ' + (f'{bad:.1f} m of edge without a {Q["guard_h"]:.1f} m guard (add "railings")' if bad > 0.3 else 'edges guarded'))


for f in FLOORS:
    for h in f.get('holes', []):
        edge_check(h, f['y'], f'Void in floor "{f.get("name", "")}" at y {f["y"]:+.2f}')
    if f.get('storey', 0) >= 1 and f.get('mat') == 'terrace':
        edge_check(f['poly'], f['y'], f'Upper terrace "{f.get("name", "")}"')
for w in L['walls']:
    if w.get('storey', 0) < 1: continue
    (ax, az), (bx, bz) = w['a'], w['b']; Ln = math.dist(w['a'], w['b']) or 1; ux, uz = (bx - ax) / Ln, (bz - az) / Ln
    for o in w.get('ops', []):
        cx, cz = ax + ux * (o['o'] + o['w'] / 2), az + uz * (o['o'] + o['w'] / 2)
        both = all(any(abs(f['y'] - w['y0']) < 0.05 and solid_at(cx + s * -uz * 0.6, cz + s * ux * 0.6, f) for f in FLOORS) for s in (1, -1))
        if both: continue                               # opens onto a floor (balcony / terrace) on both sides
        low = o['kind'] in ('slide', 'door_glass', 'door', 'front', 'open') or (o['kind'] == 'window' and o.get('sill', 0) < Q['upper_sill_min'])
        if low and not any(guarded(cx + sx * -uz * 0.2, cz + sx * ux * 0.2, w['y0'], walls=False) for sx in (1, -1)):   # a railing in front or behind
            WARN.append(f'Upper-floor {o["kind"]} {o["w"]:.2f} m in wall {w.get("tag") or w["a"]}: sill {o.get("sill", 0):.2f} m, no balcony floor or railing (needs ≥ {Q["upper_sill_min"]} m sill or a guard)')

# furniture: nothing in a door swing, in front of a low window / sliding door / front door, or blocking an opening
def _block_at(x, z):
    for b in L.get('blocks', {}).values():
        x0, z0, x1, z1 = b['rect']
        if x0 - 0.05 <= x <= x1 + 0.05 and z0 - 0.05 <= z <= z1 + 0.05: return b
_zones = []
for w in L['walls']:
    (ax, az), (bx, bz) = w['a'], w['b']; Lw = math.dist(w['a'], w['b'])
    if Lw < 1e-6: continue
    ux, uz = (bx - ax) / Lw, (bz - az) / Lw; nx, nz = -uz, ux; t = w.get('t', 0.2)
    for o in w.get('ops', []):
        s0, e0, k = o['o'], o['o'] + o['w'], o['kind']; mid = s0 + o['w'] / 2
        sides = [sg for sg in (1, -1) if (lambda b: b and not any(k in b['name'].lower() for k in ('alpendre', 'porch', 'terrace', 'terraço')))(_block_at(ax + ux * mid + nx * sg * 0.6, az + uz * mid + nz * sg * 0.6))]
        if k == 'door': depth, use, what = o['w'], [1 if 1 in sides or not sides else -1], 'in a door swing'
        elif k in ('window', 'slide', 'door_glass', 'front'):
            if o.get('sill', 0) >= 1.4: continue
            depth, use, what = (1.1, sides or [1], 'in the front-door swing') if k == 'front' else (0.5, sides or [1], 'in front of a ' + ('window' if k == 'window' else 'glazed door'))
        elif k == 'open': depth, use, what = 0.6, [1, -1], 'in an opening'
        else: continue
        for sg in use:
            pts = [(ax + ux * u + nx * sg * v, az + uz * u + nz * sg * v) for u in (s0, e0) for v in (t / 2, t / 2 + depth)]
            _zones.append(((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)), w.get('y0', 0), k, o, what))
_bad = 0
for fu in L.get('furniture', []):
    if fu.get('mat') == 'rug' or fu.get('h', 0) < 0.06: continue
    fb = fu['b']
    for (r, y0, k, o, what) in _zones:
        if abs(fu.get('y0', 0) - y0) > 0.35: continue
        if not (fb[0] < r[2] - 0.02 and r[0] < fb[2] - 0.02 and fb[1] < r[3] - 0.02 and r[1] < fb[3] - 0.02): continue
        if k == 'window' and fu.get('h', 0) <= o.get('sill', 0) - 0.1 and any(n in fu.get('name', '').lower() for n in ('bancada', 'counter', 'máquinas', 'sink')): continue
        _bad += 1; WARN.append(f'Furniture "{fu.get("name") or fu.get("mat")}" {fu["b"]} is {what} ({o["kind"]} {o["w"]} m)')
if L.get('furniture') and not _bad: OK.append('Furniture: clear of door swings and low windows')

lines = [f'# Layout QA — {P.get("name", "")}', '', f'{len(ERR)} error(s), {len(WARN)} warning(s), {len(OK)} check(s) passed.',
         '', '_Generic good-practice thresholds, not a building-code check._', '']
for title, items in (('Errors', ERR), ('Warnings', WARN), ('Passed', OK)):
    if items: lines += [f'## {title}'] + [f'- {x}' for x in items] + ['']
report = '\n'.join(lines)
print(report)
if md_out: open(md_out, 'w', encoding='utf-8').write(report)
sys.exit(1 if ERR else 0)
