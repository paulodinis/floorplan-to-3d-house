"""Camera path for the Blender video, computed from layout.json (scene coords: x east, y up, z south).

Every video: a full 360° orbit around the house, starting and ending on the front-door side.
60 s (or any length >= 45 s): orbit, then down to the front door, the door opens, and the camera walks
every storey (climbing the stairs), stopping at the doorway of every space reachable through doors / openings (opening
each door on the way), looking into it.

usage: python3 camera_path.py layout.json SECONDS out.json [--site site.json] [--preview path.png] [--lang pt-PT]
       [--skip "Bedroom 3,WC"] [--order "Living / dining / kitchen,Office"] [--radius 18] [--height 14] [--cw]
out.json: camera_keys, frames_src = frames_out, doors (for scripts/blender/doors.py), stops (numbered, with grid cell),
not_visited, timing. Merge camera_keys, frames_src, frames_out and doors into params.json.
The preview shows the orbit and, per storey, the walk on the same 2 m reference grid as the approval plan
(PLAN_GRID_STEP to change it) with the stops numbered, so the user can redirect it before rendering:
--skip  rooms not to stop at (still walked through when they lead on); stop numbers map to `stops`
--order rooms to visit first, in this order, where the layout allows it
--radius / --height / --cw  orbit distance from the house centre (m), camera height (m), clockwise
"""
import json, math, sys, argparse

ap = argparse.ArgumentParser()
ap.add_argument('layout'); ap.add_argument('seconds', type=float); ap.add_argument('out')
ap.add_argument('--site'); ap.add_argument('--preview'); ap.add_argument('--fps', type=int, default=25)
ap.add_argument('--interior-from', type=float, default=45.0, help='lengths >= this get the interior tour')
ap.add_argument('--skip', default=''); ap.add_argument('--order', default='')
ap.add_argument('--radius', type=float); ap.add_argument('--height', type=float); ap.add_argument('--cw', action='store_true')
ap.add_argument('--lang', default='en')
A = ap.parse_args()
SKIP = {x.strip().lower() for x in A.skip.split(',') if x.strip()}
ORDER = [x.strip().lower() for x in A.order.split(',') if x.strip()]
rank = lambda r: ORDER.index(r['name'].lower()) if r and r['name'].lower() in ORDER else len(ORDER)
L = json.load(open(A.layout, encoding='utf-8'))
FPS, SEC = A.fps, A.seconds
F = int(round(SEC * FPS))
EYE, LOOK, CLEAR = 1.6, 1.3, 0.25          # eye height, look height, wall clearance (m)
WALK, DWELL, DOOR_T = 1.2, 1.2, 1.0         # m/s, s at each doorway, s for a door to swing

# ---------- geometry ----------
def inside(p, poly):
    x, z = p; c = False
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i - 1], poly[i]
        if (z0 > z) != (z1 > z) and x < x0 + (z - z0) * (x1 - x0) / (z1 - z0): c = not c
    return c
def seg_d(p, a, b):
    ax, az = a; bx, bz = b; dx, dz = bx - ax, bz - az; L2 = dx * dx + dz * dz or 1e-9
    u = max(0, min(1, ((p[0] - ax) * dx + (p[1] - az) * dz) / L2)); return math.hypot(p[0] - ax - u * dx, p[1] - az - u * dz)
def edge_d(p, poly): return min(seg_d(p, poly[i - 1], poly[i]) for i in range(len(poly)))
def area(poly): return abs(sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))) / 2
def centroid(poly):
    a = cx = cz = 0.0
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i - 1], poly[i]; c = x0 * z1 - x1 * z0; a += c; cx += (x0 + x1) * c; cz += (z0 + z1) * c
    return (cx / (3 * a), cz / (3 * a)) if abs(a) > 1e-9 else tuple(poly[0])
def lerp(a, b, u): return tuple(a[i] + (b[i] - a[i]) * u for i in range(len(a)))
def dist(a, b): return math.dist(a, b)

st_of = lambda e: e.get('storey', 0)
rooms = list(L['rooms'])
floors = list(L.get('floors', []))
stairs = list(L.get('stairs', []))
NST = 1 + max([st_of(r) for r in rooms] + [0])

def room_at(p, sto=0):
    c = [r for r in rooms if st_of(r) == sto and inside(p, r['poly'])]
    return min(c, key=lambda r: area(r['poly'])) if c else None
def floor_y(p, sto=0):
    for s in stairs:                                    # stairs run along x, top at x0 (engine convention)
        if st_of(s) not in (sto, sto - 1): continue
        x0, x1 = s['x0'], s['x1']; z0, z1 = sorted((s['z0'], s['z1']))
        if min(x0, x1) <= p[0] <= max(x0, x1) and z0 <= p[1] <= z1:
            u = (p[0] - x0) / (x1 - x0); return s['ytop'] + (s['ybot'] - s['ytop']) * u
    c = [f for f in floors if st_of(f) == sto and inside(p, f['poly']) and not any(inside(p, h) for h in f.get('holes', []))]
    return min(c, key=lambda f: area(f['poly']))['y'] if c else (0.0 if sto == 0 else max([f['y'] for f in floors if st_of(f) == sto] + [0.0]))

def seg_ok(a, b, poly):
    n = max(2, int(dist(a, b) / 0.1))
    for i in range(1, n):
        q = lerp(a, b, i / n)
        if not inside(q, poly) or edge_d(q, poly) < CLEAR: return False
    return True
def route(a, b, poly):
    """polyline a -> b inside a room polygon: direct, else through one or two inset vertices / the centroid"""
    if seg_ok(a, b, poly): return [a, b]
    cands = [centroid(poly)]
    cx, cz = cands[0]
    for v in poly:                                       # vertices pulled 0.6 m toward the inside
        for k in (0.6, 1.0):
            dx, dz = cx - v[0], cz - v[1]; d = math.hypot(dx, dz) or 1
            q = (v[0] + dx / d * k, v[1] + dz / d * k)
            if inside(q, poly) and edge_d(q, poly) >= CLEAR: cands.append(q)
    best = None
    for w in cands:
        if seg_ok(a, w, poly) and seg_ok(w, b, poly):
            l = dist(a, w) + dist(w, b)
            if best is None or l < best[0]: best = (l, [a, w, b])
    if best: return best[1]
    for w in cands:
        for v in cands:
            if w != v and seg_ok(a, w, poly) and seg_ok(w, v, poly) and seg_ok(v, b, poly):
                l = dist(a, w) + dist(w, v) + dist(v, b)
                if best is None or l < best[0]: best = (l, [a, w, v, b])
    return best[1] if best else [a, b]

# ---------- openings and the room graph ----------
OPEN_KINDS = ('door', 'front', 'open', 'slide', 'door_glass')
LOOK_ONLY = ('slide', 'door_glass')          # glass: look through it, never walk through
ops = []
for w in L['walls']:
    sto = st_of(w)
    (ax, az), (bx, bz) = w['a'], w['b']; Lw = math.hypot(bx - ax, bz - az)
    if Lw < 1e-6: continue
    d = ((bx - ax) / Lw, (bz - az) / Lw); n = (-d[1], d[0]); t = w.get('t', 0.2)
    for o in w.get('ops', []):
        if o['kind'] not in OPEN_KINDS: continue
        c = (ax + d[0] * (o['o'] + o['w'] / 2), az + d[1] * (o['o'] + o['w'] / 2))
        off = t / 2 + 0.45
        p1, p2 = (c[0] + n[0] * off, c[1] + n[1] * off), (c[0] - n[0] * off, c[1] - n[1] * off)
        r1, r2 = room_at(p1, sto), room_at(p2, sto)
        if r1 is r2: continue
        ops.append(dict(c=c, n=n, t=t, kind=o['kind'], w=o['w'], y0=w.get('y0', 0.0), sides={id(r1) if r1 else None: (r1, 1), id(r2) if r2 else None: (r2, -1)}, r=(r1, r2)))
# rooms that share a boundary with no wall on it (open plan: hall <-> corridor) get a virtual opening
def walled(m, sto): return any(st_of(w) == sto and seg_d(m, w['a'], w['b']) < w.get('t', 0.2) / 2 + 0.06 for w in L['walls'])
for i, ra in enumerate(rooms):
    for rb in rooms[i + 1:]:
        if st_of(ra) != st_of(rb): continue
        if any(ra in op['r'] and rb in op['r'] for op in ops): continue
        best = None
        for j in range(len(ra['poly'])):
            a0, a1 = ra['poly'][j - 1], ra['poly'][j]; la = dist(a0, a1)
            if la < 0.3: continue
            d = ((a1[0] - a0[0]) / la, (a1[1] - a0[1]) / la)
            nrm = (-d[1], d[0])
            for k in range(len(rb['poly'])):
                b0, b1 = rb['poly'][k - 1], rb['poly'][k]
                o0 = (b0[0] - a0[0]) * nrm[0] + (b0[1] - a0[1]) * nrm[1]; o1 = (b1[0] - a0[0]) * nrm[0] + (b1[1] - a0[1]) * nrm[1]
                if abs(o0 - o1) > 0.02 or abs(o0) > 0.35: continue          # parallel, at most a wall thickness apart
                u0, u1 = sorted(((b0[0] - a0[0]) * d[0] + (b0[1] - a0[1]) * d[1], (b1[0] - a0[0]) * d[0] + (b1[1] - a0[1]) * d[1]))
                lo, hi = max(0.0, u0), min(la, u1)
                if hi - lo < 0.8: continue
                um = (lo + hi) / 2; m = (a0[0] + d[0] * um + nrm[0] * o0 / 2, a0[1] + d[1] * um + nrm[1] * o0 / 2)
                if walled(m, st_of(ra)): continue
                if best is None or hi - lo > best[1]: best = (m, hi - lo, nrm, abs(o0))
        if best:
            m, wd, n, gap = best
            r1, r2 = room_at((m[0] + n[0] * (gap / 2 + 0.4), m[1] + n[1] * (gap / 2 + 0.4)), st_of(ra)), room_at((m[0] - n[0] * (gap / 2 + 0.4), m[1] - n[1] * (gap / 2 + 0.4)), st_of(ra))
            if {id(r1), id(r2)} == {id(ra), id(rb)}:
                ops.append(dict(c=m, n=n, t=gap, kind='open', w=wd, y0=floor_y(m, st_of(ra)), sides={id(r1): (r1, 1), id(r2): (r2, -1)}, r=(r1, r2)))
# stairs: a passage from the room at the bottom end (storey k) to the room past the top end (storey k+1)
for stp in stairs:
    k = st_of(stp); x0, x1 = stp['x0'], stp['x1']; zc = (stp['z0'] + stp['z1']) / 2; dr = 1 if x1 > x0 else -1
    bot, top = (x1 + dr * 0.7, zc), (x0 - dr * 0.7, zc)
    lo_r = room_at(bot, k) or room_at((x1 - dr * 0.3, zc), k); hi_r = room_at(top, k + 1)
    if lo_r and hi_r and lo_r is not hi_r:
        ops.append(dict(c=((x0 + x1) / 2, zc), n=(dr, 0), t=0, kind='stair', w=abs(stp['z1'] - stp['z0']), y0=stp['ybot'],
                        sides={id(lo_r): (lo_r, 1), id(hi_r): (hi_r, -1)}, r=(lo_r, hi_r),
                        pts={id(lo_r): bot, id(hi_r): top}, via=[(x1 - dr * 0.2, zc), (x0 + dr * 0.2, zc)]))
def side_pt(op, room, k):
    """point k m from the opening's centre, on room's side (room None = outside)"""
    if 'pts' in op: return op['pts'][id(room)]
    s = op['sides'][id(room) if room else None][1]; t = op['t'] / 2 + k
    return (op['c'][0] + op['n'][0] * s * t, op['c'][1] + op['n'][1] * s * t)
def other(op, room): return op['r'][1] if op['r'][0] is room else op['r'][0]
nbrs = {id(r): [op for op in ops if r in op['r']] for r in rooms}

front = next((op for op in ops if op['kind'] == 'front' and None in op['r']), None) or next((op for op in ops if op['kind'] in ('door', 'open') and None in op['r']), None)
if front is None: sys.exit('no front door (kind "front") between a room and the outside on storey 0')
entry = other(front, None)

# ---------- interior tour (depth-first, nearest opening first) ----------
EV = []                     # events: ('move', [pts]) | ('dwell', pos, look_room) | ('door', op, toward_room)
visited = {id(entry)}; tour = [entry['name']]
def has_unvisited(room, came):
    return any(op is not came and other(op, room) is not None and id(other(op, room)) not in visited for op in nbrs[id(room)])
def walkable(op): return op['kind'] not in LOOK_ONLY
def branch_rank(op, room):
    """best --order rank among the unvisited rooms reachable through op (so 'living first' also pulls the stair before it)"""
    start = other(op, room); best, seen, todo = rank(start), {id(room), id(start)}, [start] if walkable(op) else []
    while todo:
        r = todo.pop()
        for o in nbrs[id(r)]:
            q = other(o, r)
            if q is None or id(q) in seen or id(q) in visited or not walkable(o): continue
            seen.add(id(q)); best = min(best, rank(q)); todo.append(q)
    return best
def visit(room, pos, came):
    while True:
        cand = [op for op in nbrs[id(room)] if op is not came and other(op, room) is not None and id(other(op, room)) not in visited]
        if not cand: return pos
        # dead ends first, then rooms that lead on, the stair last (its branch is the one not walked back)
        op = min(cand, key=lambda o: (branch_rank(o, room), not walkable(o), o['kind'] == 'stair' and not ORDER, walkable(o) and has_unvisited(other(o, room), o), dist(pos, side_pt(o, room, 0.8))))
        nxt = other(op, room); appr = side_pt(op, room, 0.8)
        EV.append(('move', [(q, st_of(room)) for q in route(pos, appr, room['poly'])]))
        if op['kind'] in ('door', 'front'): EV.append(('door', op, nxt))
        visited.add(id(nxt))
        if nxt['name'].lower() not in SKIP:
            tour.append(nxt['name']); EV.append(('dwell', (appr, st_of(room)), nxt))
        if walkable(op) and has_unvisited(nxt, op):
            inn = side_pt(op, nxt, 0.8)
            via = op.get('via', [])
            if via and op['r'][0] is not room: via = via[::-1]
            cross = [(appr, st_of(room))] + [(v, min(st_of(room), st_of(nxt))) for v in via] + [(inn, st_of(nxt))]
            EV.append(('move', cross))
            back = visit(nxt, inn, op)
            EV.append(('move', [(q, st_of(nxt)) for q in route(back, inn, nxt['poly'])] + cross[::-1][1:]))
        pos = appr

# ---------- orbit ----------
rects = [b['rect'] for b in L.get('blocks', {}).values()] or [[min(p[0] for r in rooms for p in r['poly']), min(p[1] for r in rooms for p in r['poly']),
                                                               max(p[0] for r in rooms for p in r['poly']), max(p[1] for r in rooms for p in r['poly'])]]
X0, Z0 = min(r[0] for r in rects), min(r[1] for r in rects); X1, Z1 = max(r[2] for r in rects), max(r[3] for r in rects)
C = ((X0 + X1) / 2, (Z0 + Z1) / 2); R = math.hypot(X1 - X0, Z1 - Z0) / 2
RAD = A.radius or R + 10.0
ground_top = 0.0
if A.site:
    site = json.load(open(A.site, encoding='utf-8')); ffl = site.get('meta', {}).get('ffl', L.get('meta', {}).get('ffl_upper'))
    if ffl is not None and site.get('spots'):
        ground_top = max(0.0, max((sp['h'] if isinstance(sp, dict) else sp[2]) - ffl for sp in site['spots']))
H = max(10.0, ground_top + 8.0) if A.height is None else A.height
for tr in L.get('trees', []):                           # keep above crowns near the circle (crown top ~ ground + 6.5 m)
    if A.height is None and abs(math.hypot(tr['x'] - C[0], tr['z'] - C[1]) - RAD) < tr.get('r', 2) + 1.0: H = max(H, ground_top + 6.5 + 2.0)
out_far = side_pt(front, None, 4.0); out_near = side_pt(front, None, 1.0)
a0 = math.atan2(out_far[1] - C[1], out_far[0] - C[0])
def orbit_pt(u): a = a0 + (-1 if A.cw else 1) * 2 * math.pi * u; return (C[0] + RAD * math.cos(a), H, C[1] + RAD * math.sin(a))
TGT = (C[0], 1.5 + 1.5 * (NST - 1), C[1])

# ---------- timeline ----------
samples = []                # (t seconds, cam xyz, tgt xyz)
STOPS = []
doors = []
def P3(p, look=False, y=None, sto=0): return (p[0], (floor_y(p, sto) if y is None else y) + (LOOK if look else EYE), p[1])
interior = SEC >= A.interior_from
if interior:
    visit(entry, side_pt(front, entry, 0.8), front)
    while EV and EV[-1][0] == 'move': EV.pop()          # the tour ends at the last doorway: no walking back
    # durations at nominal speed
    def ev_time(e, sp, dw):
        if e[0] == 'move': return sum(dist(e[1][i][0], e[1][i + 1][0]) for i in range(len(e[1]) - 1)) / sp
        return dw if e[0] == 'dwell' else DOOR_T * 0.25
    T_APP = 4.0 + 1.0 + DOOR_T + dist(out_near, side_pt(front, entry, 0.8)) / WALK      # descend, step in, front door, enter
    Ti = sum(ev_time(e, WALK, DWELL) for e in EV)
    To = SEC - T_APP - Ti; k = 1.0
    if To < 15: k = max(0.6, (SEC - T_APP - 15) / Ti)           # faster at most to 2 m/s, ~0.7 s per doorway
    elif To > 30: k = min(1.3, (SEC - T_APP - 30) / Ti)
    sp, dw = WALK / k, DWELL * k
    Ti = sum(ev_time(e, sp, dw) for e in EV); To = SEC - T_APP - Ti
    if To < 12: sys.exit(f'house too large for {SEC:.0f} s: the interior needs {Ti:.0f} s at {sp:.1f} m/s; use a longer video (e.g. 90 s)')
else:
    To = SEC
# orbit samples
n = max(24, int(To * 1.6))
for i in range(n + 1):
    u = i / n; samples.append((To * u, orbit_pt(u), TGT))
t = To
if interior:
    # descend to the front door, step in, door opens, step through
    t_dn = 4.0
    p_far, p_near = P3(out_far, y=floor_y(side_pt(front, entry, 0.8))), P3(out_near, y=floor_y(side_pt(front, entry, 0.8)))
    door_c = P3(front['c'], look=True, y=floor_y(side_pt(front, entry, 0.8)))
    for i in range(1, 6):
        u = i / 5; samples.append((t + t_dn * u, lerp(orbit_pt(1.0), p_far, u), lerp(TGT, door_c, u)))
    t += t_dn
    samples.append((t + 1.0, p_near, door_c)); t += 1.0
    doors.append(dict(x=front['c'][0], z=front['c'][1], y0=front['y0'], w=front['w'], kind='front', frame=int(round(t * FPS)), toward=list(side_pt(front, entry, 2.0))))
    t += DOOR_T; samples.append((t, p_near, P3(centroid(entry['poly']), look=True)))
    pin = side_pt(front, entry, 0.8)
    t += dist(out_near, pin) / sp; samples.append((t, P3(pin), P3(centroid(entry['poly']), look=True)))
    for e in EV:
        if e[0] == 'move':
            pts = e[1]
            for i in range(len(pts) - 1):
                (a, sa), (b, sb) = pts[i], pts[i + 1]; dl = dist(a, b)
                if dl < 1e-3: continue
                m = max(1, int(dl / 0.5))
                for j in range(1, m + 1):
                    u = j / m; q = lerp(a, b, u); sq = sa if u < 0.5 else sb
                    # look 2.5 m ahead along this leg (or at its end)
                    ahead = lerp(a, b, min(1.0, u + 2.5 / dl)) if dl > 0 else b
                    if dist(q, ahead) < 0.4: ahead = (b[0] + (b[0] - a[0]) / dl, b[1] + (b[1] - a[1]) / dl)
                    samples.append((t + dl / sp * u, P3(q, sto=sq), P3(ahead, look=True, sto=sb)))
                t += dl / sp
        elif e[0] == 'door':
            op, to = e[1], e[2]
            doors.append(dict(x=op['c'][0], z=op['c'][1], y0=op['y0'], w=op['w'], kind=op['kind'], frame=max(1, int(round((t - 1.2) * FPS))), toward=list(side_pt(op, to, 2.0))))
            t += DOOR_T * 0.25; samples.append((t, samples[-1][1], samples[-1][2]))
        else:
            (pos, ps), rm = e[1], e[2]; tg = P3(centroid(rm['poly']), look=True, sto=st_of(rm))
            STOPS.append(dict(n=len(STOPS) + 1, room=rm['name'], storey=ps, pos=pos, frame=1 + int(round((t + dw * 0.4) / SEC * (F - 1)))))
            samples.append((t + dw * 0.4, P3(pos, sto=ps), tg)); t += dw; samples.append((t, P3(pos, sto=ps), tg))
# frames
keys, last = [], -1
for ts, cpos, tpos in samples:
    f = 1 + int(round(ts / SEC * (F - 1)))
    f = min(F, max(f, last + 1)); last = f
    keys.append([f, [round(v, 3) for v in cpos], [round(v, 3) for v in tpos]])
keys[-1][0] = F
import os
GX0, GZ0 = min(p[0] for p in L['plot']), min(p[1] for p in L['plot'])        # same origin and step as plan2d_simple.py
GSTEP = float(os.environ.get('PLAN_GRID_STEP', '2') or 2)
col_name = lambda i: (col_name(i // 26 - 1) if i >= 26 else '') + chr(65 + i % 26)
cell = lambda p: f"{col_name(max(0, int((p[0] - GX0) // GSTEP)))}{max(0, int((p[1] - GZ0) // GSTEP)) + 1}"
res = dict(camera_keys=keys, frames_src=F, frames_out=F, doors=doors,
           stops=[dict(n=x['n'], room=x['room'], storey=x['storey'], cell=cell(x['pos']), frame=x['frame']) for x in STOPS],
           front_door_cell=cell(front['c']), not_visited=[r['name'] for r in rooms if id(r) not in visited] if interior else [],
           timing=dict(seconds=SEC, orbit_s=round(To, 1), walk_m_s=round(sp, 2) if interior else None, doorway_s=round(dw, 2) if interior else None, interior_s=round(SEC - To, 1) if interior else 0, orbit_radius_m=round(RAD, 1), orbit_height_m=round(H, 1)))
json.dump(res, open(A.out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in res.items() if k not in ('camera_keys', 'doors', 'stops')}, ensure_ascii=False), 'stops', [f"{x['n']} {x['room']} ({x['cell']})" for x in res['stops']], 'keys', len(keys), 'doors', len(doors))

# ---------- preview: orbit (left) + the walk per storey on the reference grid (right) ----------
if A.preview:
    from PIL import Image, ImageDraw, ImageFont
    def font(sz, b=False):
        try: return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % ('-Bold' if b else ''), sz)
        except OSError: return ImageFont.load_default()
    TX = {'en': dict(orbit='360° orbit', rad='radius', h='height', start='start / end', cw='clockwise', ccw='anticlockwise', storey='Storey',
                     stops='Stops', skipped='Not visited', front='front door', hint='To change the path, say e.g.: "skip 5 and 7" · "living room first" · "orbit closer / higher" · "the other way round"',
                     title='Video path — %d s'),
          'pt-PT': dict(orbit='Órbita 360°', rad='raio', h='altura', start='início / fim', cw='sentido horário', ccw='sentido anti-horário', storey='Piso',
                        stops='Paragens', skipped='Não visitados', front='porta de entrada', hint='Para alterar o percurso, diz por ex.: "salta a 5 e a 7" · "a sala primeiro" · "órbita mais perto / mais alta" · "ao contrário"',
                        title='Percurso do vídeo — %d s')}[A.lang if A.lang in ('en', 'pt-PT') else 'en']
    BLUE, ORANGE, GREEN, GRID = (30, 100, 210), (225, 120, 0), (0, 150, 70), (170, 195, 230)
    PW = 760; storeys = sorted({st_of(r) for r in rooms}) if interior else []
    IW = 0 if not interior else max(700, 820 * len(storeys))
    W, PH, LH = PW + IW, 760, 230
    im = Image.new('RGB', (W, PH + LH), 'white'); d = ImageDraw.Draw(im)
    # --- orbit panel
    xs = [p[0] for p in L['plot']] + [C[0] - RAD, C[0] + RAD]; zs = [p[1] for p in L['plot']] + [C[1] - RAD, C[1] + RAD]
    ox0, oz0 = min(xs) - 3, min(zs) - 3; so = (PW - 40) / max(max(xs) - min(xs) + 6, max(zs) - min(zs) + 6)
    Qo = lambda x, z: (20 + (x - ox0) * so, 50 + (z - oz0) * so)
    d.polygon([Qo(*p) for p in L['plot']], fill=(244, 248, 238), outline=(210, 0, 0))
    for r in rects: d.rectangle([Qo(r[0], r[1]), Qo(r[2], r[3])], fill=(90, 90, 90))
    for tr in L.get('trees', []): x, y = Qo(tr['x'], tr['z']); rr = tr.get('r', 2) * so; d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(60, 140, 60))
    orb = [Qo(*(lambda q: (q[0], q[2]))(orbit_pt(i / 72))) for i in range(73)]; d.line(orb, fill=BLUE, width=4)
    sx, sy = orb[0]; d.ellipse([sx - 9, sy - 9, sx + 9, sy + 9], fill=BLUE)
    ax_, ay_ = orb[3]; d.polygon([(ax_, ay_), (orb[1][0] + (orb[1][1] - ay_) * 0.5, orb[1][1] - (orb[1][0] - ax_) * 0.5), (orb[1][0] - (orb[1][1] - ay_) * 0.5, orb[1][1] + (orb[1][0] - ax_) * 0.5)], fill=BLUE)
    d.text((sx + 14, sy), TX['start'], fill=BLUE, font=font(18, True), anchor='lm')
    fx, fy = Qo(*front['c']); d.ellipse([fx - 7, fy - 7, fx + 7, fy + 7], fill=ORANGE)
    d.text((20, 14), f"{TX['orbit']} · {TX['rad']} {RAD:.0f} m · {TX['h']} {H:.0f} m · {To:.0f} s · {TX['cw'] if A.cw else TX['ccw']}", fill=(0, 0, 0), font=font(20, True))
    # --- one panel per storey, on the plan's reference grid
    for si, k in enumerate(storeys):
        pw = IW // len(storeys); px0 = PW + si * pw
        rk = [r for r in rooms if st_of(r) == k]
        rv = [r for r in rk if id(r) in visited] or rk                      # zoom on the spaces the walk reaches
        bx0 = min(p[0] for r in rv for p in r['poly']) - 1.5; bx1 = max(p[0] for r in rv for p in r['poly']) + 1.5
        bz0 = min(p[1] for r in rv for p in r['poly']) - 1.5; bz1 = max(p[1] for r in rv for p in r['poly']) + 1.5
        i0, i1 = int((bx0 - GX0) // GSTEP), int((bx1 - GX0) // GSTEP) + 1; j0, j1 = int((bz0 - GZ0) // GSTEP), int((bz1 - GZ0) // GSTEP) + 1
        gx0, gx1, gz0, gz1 = GX0 + i0 * GSTEP, GX0 + i1 * GSTEP, GZ0 + j0 * GSTEP, GZ0 + j1 * GSTEP
        sp_ = min((pw - 90) / (gx1 - gx0), (PH - 110) / (gz1 - gz0))
        pan = Image.new('RGB', (pw, PH), 'white'); dp = ImageDraw.Draw(pan)
        Qp = lambda x, z: (55 + (x - gx0) * sp_, 75 + (z - gz0) * sp_)
        for r in rk: dp.polygon([Qp(*p) for p in r['poly']], fill=(240, 240, 240) if id(r) in visited else (255, 225, 225))
        for w in L['walls']:
            if st_of(w) == k: dp.line([Qp(*w['a']), Qp(*w['b'])], fill=(20, 20, 20), width=max(2, int(w.get('t', 0.2) * sp_)))
        for i in range(i1 - i0 + 1): dp.line([Qp(gx0 + i * GSTEP, gz0), Qp(gx0 + i * GSTEP, gz1)], fill=GRID, width=1)
        for j in range(j1 - j0 + 1): dp.line([Qp(gx0, gz0 + j * GSTEP), Qp(gx1, gz0 + j * GSTEP)], fill=GRID, width=1)
        for i in range(i1 - i0): dp.text((Qp(gx0 + (i + 0.5) * GSTEP, gz0)[0], 62), col_name(i0 + i), fill=BLUE, font=font(16, True), anchor='md')
        for j in range(j1 - j0): dp.text((48, Qp(gx0, gz0 + (j + 0.5) * GSTEP)[1]), str(j0 + j + 1), fill=BLUE, font=font(16, True), anchor='rm')
        for r in rk: dp.text(Qp(*centroid(r['poly'])), r['name'], fill=(110, 110, 110), font=font(13), anchor='mm')
        # the walk on this storey (keys whose eye height belongs to it), front door, doors, stops
        fy_k = {kk: floor_y(centroid(next(r for r in rooms if st_of(r) == kk)['poly']), kk) for kk in storeys}
        def key_storey(y): return min(storeys, key=lambda kk: abs(y - EYE - fy_k[kk]) if y - EYE >= fy_k[kk] - 0.6 else 99)
        walk = [k_ for k_ in keys if k_[0] > int(round(To * FPS)) and k_[1][1] < H - 2]
        seg = []
        for k_ in walk:
            if key_storey(k_[1][1]) == k: seg.append(Qp(k_[1][0], k_[1][2]))
            else:
                if len(seg) > 1: dp.line(seg, fill=BLUE, width=3)
                seg = []
        if len(seg) > 1: dp.line(seg, fill=BLUE, width=3)
        for dr in doors:
            if key_storey(dr['y0'] + EYE) == k: x, y = Qp(dr['x'], dr['z']); dp.ellipse([x - 6, y - 6, x + 6, y + 6], fill=ORANGE)
        if k == storeys[0]: x, y = Qp(*front['c']); dp.text((max(x, 60), y - 12), TX['front'], fill=ORANGE, font=font(14, True), anchor='mb', stroke_width=3, stroke_fill='white')
        placed = []
        for st in STOPS:
            if st['storey'] == k:
                x, y = Qp(*st['pos'])
                while any(math.hypot(x - a, y - b) < 27 for a, b in placed): y -= 27     # keep numbers readable
                placed.append((x, y)); dp.ellipse([x - 13, y - 13, x + 13, y + 13], fill=GREEN); dp.text((x, y), str(st['n']), fill='white', font=font(15, True), anchor='mm')
        dp.text((10, 12), f"{TX['storey']} {k}", fill=(0, 0, 0), font=font(20, True))
        im.paste(pan, (px0, 0)); d.line([(px0, 0), (px0, PH)], fill=(200, 200, 200), width=2)
    # --- legend
    y = PH + 12; d.line([(0, PH), (W, PH)], fill=(180, 180, 180), width=2)
    d.text((20, y), TX['title'] % SEC, fill=(0, 0, 0), font=font(24, True)); y += 40
    if interior:
        items = [f"{x['n']} {x['room']} ({cell(x['pos'])})" for x in STOPS]; line = TX['stops'] + ': '
        for it in items:
            if d.textlength(line + it + ' · ', font=font(17)) > W - 40: d.text((20, y), line, fill=(0, 0, 0), font=font(17)); y += 26; line = ''
            line += it + ' · '
        d.text((20, y), line.rstrip(' ·'), fill=(0, 0, 0), font=font(17)); y += 30
        nv = [r['name'] for r in rooms if id(r) not in visited]
        if nv: d.text((20, y), TX['skipped'] + ': ' + ', '.join(nv), fill=(190, 60, 60), font=font(17)); y += 30
    d.text((20, y), TX['hint'], fill=BLUE, font=font(17))
    im.crop((0, 0, W, min(PH + LH, y + 40))).save(A.preview)
