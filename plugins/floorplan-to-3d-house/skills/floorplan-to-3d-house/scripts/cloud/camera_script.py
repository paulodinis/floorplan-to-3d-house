"""Scripted camera path: the user's own shot list, in plain steps, turned into Blender camera keys.

usage: python3 camera_script.py layout.json script.json out.json [--site site.json] [--preview path.png] [--lang pt-PT]
out.json has the same keys as camera_path.py (camera_keys, frames_src, frames_out, doors, stops) plus `checks`
(eye closer than 0.2 m to a wall, walls crossed without an opening, glass crossed). Merge it into params.json the same way.

script.json:
  {"seconds": 90, "fps": 25, "steps": [ {"do": ..., "t": <relative duration>, "label": "..."}, ... ]}
Durations are relative: they are scaled so the steps fill `seconds`. Points ("to", "look", "via" items) are
  {"room": "<name>"}        room centroid ({"room": ..., "toward": "<other room>", "frac": 0.5} = part way from the
                            door into that room toward its centroid)
  {"door": "<room>"}        centre of the opening between the camera's current room and <room>
  {"xz": [x, z]}            scene metres (x east, z south)
  {"stair": "top"|"bottom"}  0.6 m before the first / after the last tread of the (first) stair
Steps (heading in degrees: 0 = east, 90 = south; "pivot" > 0 turns right):
  start      {"at": "front_door", "dist": 4, "eye": 1.2}   outside the front door, facing it
  orbit_in   rise and back off to the orbit start, the whole house in view
  orbit      {"deg": 360, "radius": m?, "height": m?, "cw": false}
  to_door    {"door": "front"}  come down to 1.2 m outside the front door (it opens as the camera goes through)
  move       {"to": point, "via": [points]}  walk at eye height, looking ahead; doors on the way open; wall
             crossings between adjacent rooms are routed through their opening automatically
  forward    {"m": 1.5}        straight ahead along the current heading
  pivot      {"deg": +45}      turn on the spot (+ right, - left)
  turn_to    {"look": point}   turn on the spot toward a point
  spin       {"deg": 360, "radius": 0.5}  small circle while turning, to show a whole room
  stairs     walk the stair down or up (the end the camera is nearest is the start)
  rise       {"up": 1.0, "back": 3.0, "look": point}  go up and back off, looking at a point
  strafe     {"to": point, "via": [points], "look": point}  walk sideways, eyes on a point
  aerial     {"height": 40}    pull up and away until the whole house is seen from above
  hold       stay
"""
import json, math, sys, argparse
ap = argparse.ArgumentParser()
ap.add_argument('layout'); ap.add_argument('script'); ap.add_argument('out')
ap.add_argument('--site'); ap.add_argument('--preview'); ap.add_argument('--lang', default='en')
A = ap.parse_args()
L = json.load(open(A.layout, encoding='utf-8')); SC = json.load(open(A.script, encoding='utf-8'))
FPS = int(SC.get('fps', 25)); SEC = float(SC.get('seconds', 60)); F = int(round(SEC * FPS))
EYE, LOOKD = 1.6, 0.25                    # eye above the floor; look slightly down (m per m)

# ---------- geometry ----------
def inside(p, poly):
    x, z = p; c = False
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i - 1], poly[i]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1: c = not c
    return c
def area(poly): return abs(sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))) / 2
def centroid(poly):
    a = cx = cz = 0.0
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i - 1], poly[i]; k = x0 * z1 - x1 * z0; a += k; cx += (x0 + x1) * k; cz += (z0 + z1) * k
    return (cx / (3 * a), cz / (3 * a)) if abs(a) > 1e-9 else poly[0]
def seg_d(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]; l2 = dx * dx + dz * dz or 1e-9
    u = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dz)
def cross(p, q, a, b):
    """parameter u on p->q where it crosses segment a-b, or None"""
    r = (q[0] - p[0], q[1] - p[1]); s = (b[0] - a[0], b[1] - a[1]); den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12: return None
    u = ((a[0] - p[0]) * s[1] - (a[1] - p[1]) * s[0]) / den; v = ((a[0] - p[0]) * r[1] - (a[1] - p[1]) * r[0]) / den
    return u if 0 <= u <= 1 and 0 <= v <= 1 else None
def lerp(a, b, u): return tuple(a[i] + (b[i] - a[i]) * u for i in range(len(a)))
def ease(u): return u * u * (3 - 2 * u)
rooms = L['rooms']; floors = L.get('floors', []); stairs = L.get('stairs', [])
def room_at(p):
    c = [r for r in rooms if inside(p, r['poly'])]
    return min(c, key=lambda r: area(r['poly'])) if c else None
def room_named(n):
    r = next((r for r in rooms if r['name'].lower() == n.lower()), None) or next((r for r in rooms if n.lower() in r['name'].lower()), None)
    if not r: sys.exit(f'room not found: {n!r} (rooms: {", ".join(r["name"] for r in rooms)})')
    return r
def floor_y(p):
    for s in stairs:
        z0, z1 = sorted((s['z0'], s['z1']))
        if min(s['x0'], s['x1']) <= p[0] <= max(s['x0'], s['x1']) and z0 <= p[1] <= z1:
            return s['ytop'] + (s['ybot'] - s['ytop']) * (p[0] - s['x0']) / (s['x1'] - s['x0'])
    c = [f for f in floors if inside(p, f['poly'])]
    return min(c, key=lambda f: area(f['poly']))['y'] if c else None

# openings: centre, along-wall unit vector, normal, half width, kind, rooms on each side
OPS, WALLS = [], []
for w in L['walls']:
    (ax, az), (bx, bz) = w['a'], w['b']; lw = math.hypot(bx - ax, bz - az)
    if lw < 1e-6 or w.get('y0', 0) > 1.0: continue
    d = ((bx - ax) / lw, (bz - az) / lw); n = (-d[1], d[0]); t = w.get('t', 0.2)
    cuts = sorted((o['o'], o['o'] + o['w'], o) for o in w.get('ops', []))
    cur = 0.0
    for s, e, o in cuts:
        if s > cur: WALLS.append(((ax + d[0] * cur, az + d[1] * cur), (ax + d[0] * s, az + d[1] * s), t))
        cur = max(cur, e)
        c = (ax + d[0] * (s + e) / 2, az + d[1] * (s + e) / 2); off = t / 2 + 0.45
        r1, r2 = room_at((c[0] + n[0] * off, c[1] + n[1] * off)), room_at((c[0] - n[0] * off, c[1] - n[1] * off))
        OPS.append(dict(c=c, a=(ax + d[0] * s, az + d[1] * s), b=(ax + d[0] * e, az + d[1] * e), n=n, t=t, w=o['w'], kind=o['kind'],
                        y0=w.get('y0', 0.0), r=(r1, r2), sill=o.get('sill', 0)))
    if cur < lw: WALLS.append(((ax + d[0] * cur, az + d[1] * cur), (bx, bz), t))
# rooms sharing a boundary with no wall on it (open plan: hall <-> corridor) get a virtual opening
def _walled(m): return any(seg_d(m, a_, b_) < t_ / 2 + 0.06 for a_, b_, t_ in WALLS) and not any(seg_d(m, o['a'], o['b']) < 0.1 for o in OPS)
for i, ra in enumerate(rooms):
    for rb in rooms[i + 1:]:
        if any({id(ra), id(rb)} == {id(o['r'][0]), id(o['r'][1])} for o in OPS): continue
        best = None
        for j in range(len(ra['poly'])):
            a0, a1 = ra['poly'][j - 1], ra['poly'][j]; la = math.dist(a0, a1)
            if la < 0.3: continue
            dd = ((a1[0] - a0[0]) / la, (a1[1] - a0[1]) / la); nrm = (-dd[1], dd[0])
            for k in range(len(rb['poly'])):
                b0, b1 = rb['poly'][k - 1], rb['poly'][k]
                o0 = (b0[0] - a0[0]) * nrm[0] + (b0[1] - a0[1]) * nrm[1]; o1 = (b1[0] - a0[0]) * nrm[0] + (b1[1] - a0[1]) * nrm[1]
                if abs(o0 - o1) > 0.02 or abs(o0) > 0.35: continue
                u0, u1 = sorted(((b0[0] - a0[0]) * dd[0] + (b0[1] - a0[1]) * dd[1], (b1[0] - a0[0]) * dd[0] + (b1[1] - a0[1]) * dd[1]))
                lo, hi = max(0.0, u0), min(la, u1)
                if hi - lo < 0.8: continue
                um = (lo + hi) / 2; m = (a0[0] + dd[0] * um + nrm[0] * o0 / 2, a0[1] + dd[1] * um + nrm[1] * o0 / 2)
                if _walled(m): continue
                if best is None or hi - lo > best[1]:
                    best = (m, hi - lo, nrm, abs(o0), (a0[0] + dd[0] * lo + nrm[0] * o0 / 2, a0[1] + dd[1] * lo + nrm[1] * o0 / 2), (a0[0] + dd[0] * hi + nrm[0] * o0 / 2, a0[1] + dd[1] * hi + nrm[1] * o0 / 2))
        if best:
            m, wd, n_, gap, pa, pb = best
            r1 = room_at((m[0] + n_[0] * (gap / 2 + 0.4), m[1] + n_[1] * (gap / 2 + 0.4))); r2 = room_at((m[0] - n_[0] * (gap / 2 + 0.4), m[1] - n_[1] * (gap / 2 + 0.4)))
            if {id(r1), id(r2)} == {id(ra), id(rb)}:
                OPS.append(dict(c=m, a=pa, b=pb, n=n_, t=gap, w=wd, kind='open', y0=floor_y(m) or 0.0, r=(r1, r2), sill=0))
FRONT = next((o for o in OPS if o['kind'] == 'front'), None) or next((o for o in OPS if o['kind'] == 'door' and None in o['r']), None)
def op_between(ra, rb):
    c = [o for o in OPS if o['kind'] in ('door', 'front', 'open') and {id(ra), id(rb)} == {id(o['r'][0]), id(o['r'][1])}]
    return c[0] if c else None
def side(op, room, k):
    s = 1 if op['r'][0] is room else -1
    return (op['c'][0] + op['n'][0] * s * (op['t'] / 2 + k), op['c'][1] + op['n'][1] * s * (op['t'] / 2 + k))

# ---------- site / orbit ----------
rects = [b['rect'] for b in L.get('blocks', {}).values()]
X0, Z0, X1, Z1 = min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)
HC = ((X0 + X1) / 2, (Z0 + Z1) / 2); HR = math.hypot(X1 - X0, Z1 - Z0) / 2
ground_top = 0.0
if A.site:
    S = json.load(open(A.site, encoding='utf-8')); ffl = S.get('meta', {}).get('ffl')
    if ffl is not None and S.get('spots'): ground_top = max(0.0, max(sp['h'] - ffl for sp in S['spots']))

# ---------- state machine ----------
segs, labels, checks, doors = [], [], [], []     # segs: (dur, eye(u), target(u)); doors: (seg index, u, op, toward)
st = dict(p=None, y=None, h=0.0)                 # position (x, z), eye y, heading deg
def eye_y(p, extra=0.0):
    fy = floor_y(p)
    return (fy if fy is not None else (st['y'] - EYE if st['y'] is not None else 0.0)) + EYE + extra
def look_at(e, h, d=3.0):
    r = math.radians(h); return (e[0] + math.cos(r) * d, e[1] - LOOKD * d, e[2] + math.sin(r) * d)
def heading(a, b): return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
def turn(h0, h1):                                # shortest signed turn
    return h0 + ((h1 - h0 + 180) % 360 - 180)
def pt(spec):
    if 'xz' in spec: return tuple(spec['xz'])
    if 'room' in spec:
        r = room_named(spec['room']); c = centroid(r['poly'])
        if 'toward' in spec or 'frac' in spec:
            src = room_at(st['p']) if 'toward' not in spec else room_named(spec['toward'])
            op = op_between(src, r) if src else None
            if op:
                a = side(op, r, 0.3); return lerp(a, c, spec.get('frac', 0.5))
        return c
    if 'door' in spec:
        if spec['door'] == 'front': return FRONT['c']
        cur = room_at(st['p']); op = op_between(cur, room_named(spec['door'])) if cur else None
        if not op: sys.exit(f'no door between {cur and cur["name"]!r} and {spec["door"]!r}')
        return op['c']
    if 'stair' in spec:
        s = stairs[0]; zc = (s['z0'] + s['z1']) / 2; dr = 1 if s['x1'] > s['x0'] else -1
        return (s['x0'] - dr * 0.6, zc) if spec['stair'] == 'top' else (s['x1'] + dr * 0.6, zc)
    sys.exit(f'bad point {spec}')
def route(a, b):
    """a -> b through the openings: adjacent rooms via their opening, others via the shortest chain of rooms (BFS)"""
    ra, rb = room_at(a), room_at(b)
    if ra is rb or ra is None or rb is None: return [a, b]
    prev, todo = {id(ra): None}, [ra]
    while todo and id(rb) not in prev:
        r = todo.pop(0)
        for o in OPS:
            if o['kind'] not in ('door', 'front', 'open') or r not in o['r']: continue
            q = o['r'][1] if o['r'][0] is r else o['r'][0]
            if q is None or id(q) in prev: continue
            prev[id(q)] = (r, o); todo.append(q)
    if id(rb) not in prev: return [a, b]
    chain, r = [], rb
    while prev[id(r)]: pr, o = prev[id(r)]; chain.append((pr, o, r)); r = pr
    pts = [a]
    for pr, o, r in reversed(chain): pts += [side(o, pr, 0.5), side(o, r, 0.5)]
    return pts + [b]
def add_move(points, dur, look_fixed=None, keep_heading=False):
    pts = [points[0]]
    for q in points[1:]: pts += route(pts[-1], q)[1:]
    if len(pts) > 2 and math.dist(pts[-2], pts[-1]) < 0.3: pts.pop(-2)        # door-side stub right at the target
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]; tot = sum(lens) or 1e-9
    h0 = st['h']
    def at(u):
        s = ease(u) * tot
        for i, l in enumerate(lens):
            if s <= l or i == len(lens) - 1:
                v = s / l if l else 0; return lerp(pts[i], pts[i + 1], min(1, v)), i
            s -= l
    def eye(u): p, _ = at(u); return (p[0], eye_y(p), p[1])
    def tgt(u):
        e = eye(u)
        if look_fixed: return look_fixed
        if keep_heading: return look_at(e, h0)
        p, i = at(min(1.0, u + 0.08)); q, _ = at(min(1.0, u + 0.2))
        hd = heading(p, q) if math.dist(p, q) > 0.05 else heading(pts[i], pts[i + 1])
        hd = turn(h0, hd) if u < 0.15 else hd
        hh = h0 + (hd - h0) * min(1, u / 0.15) if u < 0.15 else hd
        return look_at(e, hh)
    segs.append((dur, eye, tgt))
    # doors and walls crossed
    acc = 0.0
    for i in range(len(pts) - 1):
        for op in OPS:
            v = cross(pts[i], pts[i + 1], op['a'], op['b'])
            if v is None: continue
            u_t = (acc + v * lens[i]) / tot
            if op['kind'] in ('door', 'front'):
                dst = room_at(pts[i + 1]) or room_at(lerp(pts[i], pts[i + 1], min(1, v + 0.3)))
                tow = side(op, dst, 2.0) if dst in op['r'] else pts[i + 1]
                doors.append((len(segs) - 1, u_t, op, tow))
            elif op['kind'] in ('slide', 'door_glass', 'window'):
                checks.append(f"step {len(labels)}: passes through glass ({op['kind']} {op['w']} m at x {op['c'][0]:.1f}, z {op['c'][1]:.1f})")
        for (wa, wb, t) in WALLS:
            if cross(pts[i], pts[i + 1], wa, wb) is not None and min(seg_d(pts[i], wa, wb), seg_d(pts[i + 1], wa, wb)) > 0.01:
                checks.append(f"step {len(labels)}: crosses a wall near x {(wa[0] + wb[0]) / 2:.1f}, z {(wa[1] + wb[1]) / 2:.1f}")
        acc += lens[i]
    st['p'] = pts[-1]; st['y'] = eye_y(pts[-1])
    if not look_fixed and not keep_heading and len(pts) > 1:              # heading of the last real leg (skip tiny door-side stubs)
        j = next((i for i in range(len(pts) - 1, 0, -1) if math.dist(pts[i - 1], pts[i]) > 0.3), len(pts) - 1)
        st['h'] = heading(pts[j - 1], pts[j])

steps = SC['steps']; TT = sum(s.get('t', 1.0) for s in steps); K = SEC / TT
ORB = dict(r=None, h=None, a0=None)
for s in steps:
    do, dur = s['do'], s.get('t', 1.0) * K
    labels.append((len(segs), s.get('label', do)))
    if do == 'start':
        op = FRONT; out = 1 if op['r'][0] is None else -1
        p = (op['c'][0] + op['n'][0] * out * s.get('dist', 4.0), op['c'][1] + op['n'][1] * out * s.get('dist', 4.0))
        fy = floor_y(side(op, op['r'][1] if out == 1 else op['r'][0], 0.5)) or 0.0
        e = (p[0], fy + s.get('eye', 1.2), p[1]); tg = (op['c'][0], fy + 1.1, op['c'][1])
        segs.append((dur, lambda u, e=e: e, lambda u, tg=tg: tg))
        st.update(p=p, y=e[1], h=heading(p, op['c']))
    elif do in ('orbit_in', 'orbit'):
        if ORB['r'] is None:
            ORB['r'] = s.get('radius') or HR + 10.0; ORB['h'] = s.get('height') or max(10.0, ground_top + 8.0)
            ORB['a0'] = math.degrees(math.atan2(st['p'][1] - HC[1], st['p'][0] - HC[0]))
        R_, H_, a0 = ORB['r'], ORB['h'], ORB['a0']
        T = (HC[0], 0.0, HC[1])
        def opt(a): r = math.radians(a); return (HC[0] + R_ * math.cos(r), H_, HC[1] + R_ * math.sin(r))
        if do == 'orbit_in':
            e0 = (st['p'][0], st['y'], st['p'][1]); t0 = look_at(e0, st['h'])
            segs.append((dur, lambda u, e0=e0: lerp(e0, opt(a0), ease(u)), lambda u, t0=t0: lerp(t0, T, ease(u))))
        else:
            deg = s.get('deg', 360) * (-1 if s.get('cw') else 1); a1 = ORB.get('a', a0)
            segs.append((dur, lambda u, a1=a1, deg=deg: opt(a1 + deg * u), lambda u: T)); ORB['a'] = a1 + deg
        a_now = ORB.get('a', a0); e = opt(a_now); st.update(p=(e[0], e[2]), y=e[1], h=heading((e[0], e[2]), HC))
    elif do == 'to_door':
        op = FRONT; out = 1 if op['r'][0] is None else -1
        p = (op['c'][0] + op['n'][0] * out * 1.2, op['c'][1] + op['n'][1] * out * 1.2)
        fy = floor_y(side(op, op['r'][1] if out == 1 else op['r'][0], 0.5)) or 0.0
        e0 = (st['p'][0], st['y'], st['p'][1]); t0 = look_at(e0, st['h']) if ORB['r'] is None else (HC[0], 0.0, HC[1])
        e1 = (p[0], fy + EYE, p[1]); t1 = (op['c'][0] - op['n'][0] * out * 2.0, fy + 1.3, op['c'][1] - op['n'][1] * out * 2.0)
        segs.append((dur, lambda u, e0=e0, e1=e1: lerp(e0, e1, ease(u)), lambda u, t0=t0, t1=t1: lerp(t0, t1, ease(u))))
        st.update(p=p, y=e1[1], h=heading(p, op['c']))
    elif do == 'move':
        add_move([st['p']] + [pt(v) for v in s.get('via', [])] + [pt(s['to'])], dur)
    elif do == 'forward':
        r = math.radians(st['h']); q = (st['p'][0] + math.cos(r) * s.get('m', 1.0), st['p'][1] + math.sin(r) * s.get('m', 1.0))
        add_move([st['p'], q], dur, keep_heading=True)
    elif do in ('pivot', 'turn_to'):
        h0 = st['h']; h1 = h0 + s['deg'] if do == 'pivot' else turn(h0, heading(st['p'], pt(s['look'])))
        e = (st['p'][0], st['y'], st['p'][1])
        segs.append((dur, lambda u, e=e: e, lambda u, e=e, h0=h0, h1=h1: look_at(e, h0 + (h1 - h0) * ease(u)))); st['h'] = h1
    elif do == 'spin':
        rad, deg, h0 = s.get('radius', 0.5), s.get('deg', 360), st['h']
        c = (st['p'][0] - math.cos(math.radians(h0)) * rad, st['p'][1] - math.sin(math.radians(h0)) * rad)
        def ep(u, c=c, h0=h0, deg=deg, rad=rad):
            a = math.radians(h0 + deg * u); p = (c[0] + math.cos(a) * rad, c[1] + math.sin(a) * rad); return (p[0], eye_y(p), p[1])
        segs.append((dur, ep, lambda u, ep=ep, h0=h0, deg=deg: look_at(ep(u), h0 + deg * u)))
        st['h'] = h0 + deg; e = ep(1.0); st['p'] = (e[0], e[2])
    elif do == 'stairs':
        s0 = stairs[0]; zc = (s0['z0'] + s0['z1']) / 2; dr = 1 if s0['x1'] > s0['x0'] else -1
        top, bot = (s0['x0'] - dr * 0.6, zc), (s0['x1'] + dr * 0.6, zc)
        a, b = (top, bot) if math.dist(st['p'], top) < math.dist(st['p'], bot) else (bot, top)
        if math.dist(st['p'], a) > 0.05: add_move([st['p'], a], dur * 0.25); dur *= 0.75
        add_move([a, b], dur)
    elif do == 'rise':
        lk = pt(s['look']) if 'look' in s else None
        r = math.radians(st['h']); e0 = (st['p'][0], st['y'], st['p'][1])
        back = s.get('back', 3.0); up = s.get('up', 1.0)
        p1 = (st['p'][0] - math.cos(r) * back, st['p'][1] - math.sin(r) * back) if lk is None else \
             (lambda d: (st['p'][0] - d[0] * back, st['p'][1] - d[1] * back))(
                 (lambda dx, dz: (dx / (math.hypot(dx, dz) or 1), dz / (math.hypot(dx, dz) or 1)))(lk[0] - st['p'][0], lk[1] - st['p'][1]))
        e1 = (p1[0], st['y'] + up, p1[1]); t0 = look_at(e0, st['h'])
        t1 = (lk[0], (floor_y(lk) if floor_y(lk) is not None else st['y'] - EYE) + 0.8, lk[1]) if lk else look_at(e1, st['h'])
        segs.append((dur, lambda u, e0=e0, e1=e1: lerp(e0, e1, ease(u)), lambda u, t0=t0, t1=t1: lerp(t0, t1, ease(u))))
        st.update(p=p1, y=e1[1], h=heading(p1, lk) if lk else st['h'])
    elif do == 'strafe':
        lk = pt(s['look']); pts = [st['p']] + [pt(v) for v in s.get('via', [])] + [pt(s['to'])]
        y0 = st['y']; ly = (floor_y(lk) if floor_y(lk) is not None else y0 - EYE) + 0.8
        lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]; tot = sum(lens) or 1e-9
        def ep(u, pts=pts, lens=lens, tot=tot, y0=y0):
            d = ease(u) * tot
            for i, l in enumerate(lens):
                if d <= l or i == len(lens) - 1:
                    q = lerp(pts[i], pts[i + 1], min(1, d / l if l else 0)); return (q[0], y0, q[1])
                d -= l
        t_prev = look_at((st['p'][0], y0, st['p'][1]), st['h'])
        segs.append((dur, ep, lambda u, t_prev=t_prev, lk=lk, ly=ly: lerp(t_prev, (lk[0], ly, lk[1]), min(1, ease(u) * 2.5))))
        st.update(p=pts[-1], h=heading(pts[-1], lk))
    elif do == 'aerial':
        e0 = (st['p'][0], st['y'], st['p'][1]); t0 = look_at(e0, st['h'])
        hgt = s.get('height', max(30.0, HR * 2.2)); dx, dz = st['p'][0] - HC[0], st['p'][1] - HC[1]; dd = math.hypot(dx, dz) or 1
        e1 = (HC[0] + dx / dd * hgt * 0.45, hgt, HC[1] + dz / dd * hgt * 0.45); t1 = (HC[0], 0.0, HC[1])
        segs.append((dur, lambda u, e0=e0, e1=e1: lerp(e0, e1, ease(u)), lambda u, t0=t0, t1=t1: lerp(t0, t1, ease(u))))
        st.update(p=(e1[0], e1[2]), y=e1[1])
    elif do == 'hold':
        e = (st['p'][0], st['y'], st['p'][1]); tg = look_at(e, st['h'])
        segs.append((dur, lambda u, e=e: e, lambda u, tg=tg: tg))
    else:
        sys.exit(f'unknown step {do!r}')

# ---------- sample ----------
starts, t = [], 0.0
for d_, _, _ in segs: starts.append(t); t += d_
def sample(tt):
    for i, (d_, ef, tf) in enumerate(segs):
        if tt <= starts[i] + d_ + 1e-9 or i == len(segs) - 1:
            u = 0 if d_ == 0 else max(0.0, min(1.0, (tt - starts[i]) / d_)); return ef(u), tf(u)
keys = []
for f in list(range(1, F + 1, 3)) + ([F] if (F - 1) % 3 else []):
    e, g = sample((f - 1) / FPS); keys.append([f, [round(v, 3) for v in e], [round(v, 3) for v in g]])
# eye too close to a wall (not while passing through an opening)
for f, e, _ in keys[::2]:
    p = (e[0], e[2])
    if floor_y(p) is None: continue
    dmin = min((seg_d(p, a, b) - t / 2 for a, b, t in WALLS), default=9)
    near_op = any(seg_d(p, o['a'], o['b']) < 0.7 for o in OPS)
    if dmin < 0.2 and not near_op: checks.append(f'frame {f}: eye {dmin:.2f} m from a wall at x {p[0]:.1f}, z {p[1]:.1f}')
DOORS, seen = [], set()
for si, u, op, tow in doors:
    if id(op) in seen: continue
    seen.add(id(op)); fr = max(1, int(round((starts[si] + segs[si][0] * u - 1.2) * FPS)))
    DOORS.append(dict(x=round(op['c'][0], 3), z=round(op['c'][1], 3), y0=op['y0'], w=op['w'], kind=op['kind'], frame=fr, toward=[round(v, 3) for v in tow]))
STOPS = []
for si, lab in labels:
    if si >= len(segs): continue
    e, _ = sample(starts[si] + segs[si][0]); STOPS.append(dict(n=len(STOPS) + 1, label=lab, frame=int(starts[si] * FPS) + 1, pos=[round(e[0], 2), round(e[2], 2)]))   # marker where the step ends
out = dict(camera_keys=keys, frames_src=F, frames_out=F, doors=DOORS, stops=STOPS, checks=checks, mode='script', seconds=SEC)
json.dump(out, open(A.out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(json.dumps(dict(frames=F, keys=len(keys), doors=len(DOORS), stops=[f"{s['n']} {s['label']} ({s['frame'] / FPS:.1f} s)" for s in STOPS], checks=checks), ensure_ascii=False))

# ---------- preview ----------
if A.preview:
    from PIL import Image, ImageDraw, ImageFont
    FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    fnt = lambda s: ImageFont.truetype(FONT, s)
    W2, H2 = 1700, 1000; im = Image.new('RGB', (W2, H2), 'white'); d = ImageDraw.Draw(im)
    def panel(x0, y0, w, h, bx):
        X0_, Z0_, X1_, Z1_ = bx; s = min(w / (X1_ - X0_), h / (Z1_ - Z0_))
        return lambda x, z: (x0 + (x - X0_) * s, y0 + (z - Z0_) * s)
    xs = [k[1][0] for k in keys]; zs = [k[1][2] for k in keys]; plot = L.get('plot', [])
    bxA = (min(xs + [p[0] for p in plot]) - 2, min(zs + [p[1] for p in plot]) - 2, max(xs + [p[0] for p in plot]) + 2, max(zs + [p[1] for p in plot]) + 2)
    bxB = (X0 - 4, Z0 - 4, X1 + 4, Z1 + 4)
    for bx, (x0, y0, w, h) in ((bxA, (10, 50, 640, 640)), (bxB, (670, 50, 1020, 640))):
        sub = Image.new('RGB', (w, h), 'white'); d = ImageDraw.Draw(sub); Q = panel(0, 0, w, h, bx)
        if plot: d.polygon([Q(*p) for p in plot], fill=(244, 247, 238), outline=(200, 40, 40))
        for a, b, t in WALLS: d.line([Q(*a), Q(*b)], fill=(30, 30, 30), width=3 if t > 0.2 else 1)
        for o in OPS:
            if o['kind'] in ('slide', 'door_glass', 'window'): d.line([Q(*o['a']), Q(*o['b'])], fill=(30, 110, 190), width=2)
        d.line([Q(k[1][0], k[1][2]) for k in keys], fill=(21, 101, 192), width=2)
        for k in keys[::8]:
            e, g = k[1], k[2]; dx, dz = g[0] - e[0], g[2] - e[2]; n = math.hypot(dx, dz) or 1
            d.line([Q(e[0], e[2]), Q(e[0] + dx / n * 0.7, e[2] + dz / n * 0.7)], fill=(230, 81, 0), width=1)
        for s_ in STOPS:
            x, y = Q(*s_['pos']); d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=(46, 125, 50)); d.text((x, y), str(s_['n']), fill='white', font=fnt(12), anchor='mm')
        for dr in DOORS:
            x, y = Q(dr['x'], dr['z']); d.rectangle([x - 4, y - 4, x + 4, y + 4], fill=(230, 120, 0))
        d.rectangle([0, 0, w - 1, h - 1], outline=(200, 200, 200)); im.paste(sub, (x0, y0))
    d = ImageDraw.Draw(im)
    pt_ = A.lang.startswith('pt')
    d.text((10, 12), (f'Percurso por guião — {SEC:.0f} s · {F} imagens' if pt_ else f'Scripted path — {SEC:.0f} s · {F} frames'), fill='black', font=fnt(22))
    y = 705
    for s_ in STOPS:
        d.text((10 + (s_['n'] - 1) // 12 * 560, y + ((s_['n'] - 1) % 12) * 22), f"{s_['n']}  {s_['label']}  ({s_['frame'] / FPS:.1f} s)", fill='black', font=fnt(15))
    if checks:
        d.text((1130, 705), ('Avisos:' if pt_ else 'Checks:'), fill=(200, 0, 0), font=fnt(15))
        for i, c in enumerate(checks[:12]): d.text((1130, 727 + i * 20), c[:70], fill=(200, 0, 0), font=fnt(12))
    im.save(A.preview)
