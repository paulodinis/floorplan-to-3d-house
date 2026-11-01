"""Find openings (gaps) in the wall poché and classify them."""
import sys, json, numpy as np
from PIL import Image, ImageDraw
S = sys.argv[1]
site = json.load(open(S + '/site3d/site.json'))
SCALE = float(str(site['meta'].get('scale', '1:200')).split(':')[-1]); K = 25.4 / 72 * SCALE / 1000; OX, OY = site['meta']['origin_pt']
R = 0.05                                  # metres per pixel
xs = [p[0] for w in site['walls'] for p in w]; zs = [p[1] for w in site['walls'] for p in w]
X0, Z0 = min(xs) - 2, min(zs) - 2; W = int((max(xs) + 2 - X0) / R); H = int((max(zs) + 2 - Z0) / R)
P = lambda x, z: ((x - X0) / R, (z - Z0) / R)
im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
for w in site['walls']: d.polygon([P(*p) for p in w], fill=255)
wall = np.array(im) > 0
pt2m = lambda x, y: ((x - OX) * K, -(y - OY) * K)
roof = [tuple(p) for p in site['roof']]
lj_pt = [(413, 332, 481, 381), (553, 332, 680, 376), (547, 472, 680, 488), (413, 141, 428, 332)]
lj = [(*pt2m(a, d_), *pt2m(c, b)) for a, b, c, d_ in lj_pt]   # x0,z0,x1,z1
garage = (*pt2m(408, 488), *pt2m(500, 402))
porch = (*pt2m(386, 488), *pt2m(408, 407))
def inpoly(x, z, poly):
    ins = False
    for i in range(len(poly)):
        (xi, zi), (xj, zj) = poly[i], poly[i - 1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi: ins = not ins
    return ins
inrect = lambda x, z, r: r[0] <= x <= r[2] and r[1] <= z <= r[3]
def zone(x, z):
    if not inpoly(x, z, roof): return 'out'
    if any(inrect(x, z, r) for r in lj): return 'terrace'
    if inrect(x, z, garage): return 'garage'
    if inrect(x, z, porch): return 'porch'
    return 'in'

def runs(a):
    """list of (start, end) of True runs"""
    out, s = [], None
    for i, v in enumerate(a):
        if v and s is None: s = i
        if not v and s is not None: out.append((s, i)); s = None
    if s is not None: out.append((s, len(a)))
    return out
MAXT = int(0.55 / R)
found = {}
for axis in (0, 1):                       # 0: scan rows (gaps in horizontal walls), 1: scan columns
    A = wall if axis == 0 else wall.T
    for r in range(A.shape[0]):
        rr = runs(A[r])
        for (s1, e1), (s2, e2) in zip(rr, rr[1:]):
            gap = (s2 - e1) * R
            if not (0.6 <= gap <= 6.5): continue
            # perpendicular thickness of the wall at both gap ends
            def band(c):
                col = A[:, c]; lo = r; hi = r
                while lo > 0 and col[lo - 1]: lo -= 1
                while hi < len(col) - 1 and col[hi + 1]: hi += 1
                return lo, hi
            b1, b2 = band(e1 - 1), band(s2)
            t1, t2 = b1[1] - b1[0] + 1, b2[1] - b2[0] + 1
            if t1 > MAXT or t2 > MAXT: continue
            lo, hi = max(b1[0], b2[0]), min(b1[1], b2[1])
            if hi - lo + 1 < 2: continue
            key = (axis, e1, s2, lo, hi)
            found[key] = True
gaps = []
for (axis, a, b, lo, hi) in found:
    if axis == 0:   # wall runs along x
        x0, x1 = X0 + a * R, X0 + b * R; z0, z1 = Z0 + lo * R, Z0 + (hi + 1) * R
        mx, mz = (x0 + x1) / 2, (z0 + z1) / 2; n = (0, 1)
    else:
        z0, z1 = Z0 + a * R, Z0 + b * R; x0, x1 = X0 + lo * R, X0 + (hi + 1) * R
        mx, mz = (x0 + x1) / 2, (z0 + z1) / 2; n = (1, 0)
    t = max(x1 - x0, z1 - z0) if False else (z1 - z0 if axis == 0 else x1 - x0)
    za, zb = zone(mx - n[0] * (t / 2 + 0.4), mz - n[1] * (t / 2 + 0.4)), zone(mx + n[0] * (t / 2 + 0.4), mz + n[1] * (t / 2 + 0.4))
    sides = {za, zb}
    if 'garage' in sides and sides & {'out', 'terrace'}: kind = 'garage_door'
    elif 'in' in sides and sides & {'out', 'terrace'}: kind = 'glass'
    elif 'garage' in sides and 'in' in sides: kind = 'door'
    elif 'porch' in sides and 'in' in sides: kind = 'front_door'
    else: kind = 'interior'
    gaps.append({'x0': round(x0, 3), 'x1': round(x1, 3), 'z0': round(z0, 3), 'z1': round(z1, 3), 'axis': 'x' if axis == 0 else 'z', 'kind': kind, 'sides': sorted(sides)})
# drop duplicates/overlaps: keep the widest per (axis, overlapping band)
gaps.sort(key=lambda g: -((g['x1'] - g['x0']) * (g['z1'] - g['z0'])))
keep = []
for g in gaps:
    if any(k['axis'] == g['axis'] and not (g['x1'] <= k['x0'] or g['x0'] >= k['x1'] or g['z1'] <= k['z0'] or g['z0'] >= k['z1']) for k in keep): continue
    keep.append(g)
# glazing where a room meets a covered terrace with no wall drawn
def wall_near(x, z, rad=0.22):
    cx, cz = int((x - X0) / R), int((z - Z0) / R); k = int(rad / R)
    return wall[max(0, cz - k):cz + k + 1, max(0, cx - k):cx + k + 1].any()
def in_gap(x, z):
    return any(g['x0'] - 0.3 <= x <= g['x1'] + 0.3 and g['z0'] - 0.3 <= z <= g['z1'] + 0.3 for g in keep)
for (rx0, rz0, rx1, rz1) in lj:
    for (ax, a0, a1, fixed, outward) in (('x', rx0, rx1, rz0, -1), ('x', rx0, rx1, rz1, 1), ('z', rz0, rz1, rx0, -1), ('z', rz0, rz1, rx1, 1)):
        run = []
        def flush():
            if len(run) * 0.05 >= 0.6:
                a, b = run[0], run[-1]
                if ax == 'x': keep.append({'x0': round(a, 3), 'x1': round(b, 3), 'z0': round(fixed - 0.04, 3), 'z1': round(fixed + 0.04, 3), 'axis': 'x', 'kind': 'glass_free', 'sides': ['in', 'terrace']})
                else: keep.append({'x0': round(fixed - 0.04, 3), 'x1': round(fixed + 0.04, 3), 'z0': round(a, 3), 'z1': round(b, 3), 'axis': 'z', 'kind': 'glass_free', 'sides': ['in', 'terrace']})
            run.clear()
        t = a0
        while t <= a1:
            x, z = (t, fixed) if ax == 'x' else (fixed, t)
            px, pz = (x, z + outward * 0.35) if ax == 'x' else (x + outward * 0.35, z)
            deep = all(not wall_near(*(((x, z + outward * dd) if ax == 'x' else (x + outward * dd, z))), 0.06) for dd in (0.5, 0.75, 1.0, 1.25))
            ok = inpoly(x, z, roof) and zone(px, pz) == 'in' and deep and not wall_near(x, z) and not in_gap(x, z)
            if ok: run.append(t)
            elif run: flush()
            t += 0.05
        if run: flush()
from collections import Counter
print(Counter(g['kind'] for g in keep))
for g in keep: print(g)
# garage door on the open west face of the garage (no wall drawn there)
gx = pt2m(408, 0)[0]
keep.append({'x0': round(gx - 0.15, 3), 'x1': round(gx + 0.15, 3), 'z0': round(pt2m(0, 481)[1], 3), 'z1': round(pt2m(0, 414)[1], 3), 'axis': 'z', 'kind': 'garage_door', 'sides': ['garage', 'out']})
json.dump(keep, open(S + '/site3d/gaps.json', 'w'))
# debug image
dbg = Image.new('RGB', (W * 2, H * 2), 'white'); dd = ImageDraw.Draw(dbg)
Q = lambda x, z: ((x - X0) / R * 2, (z - Z0) / R * 2)
dd.polygon([Q(*p) for p in roof], outline=(0, 0, 0))
for r in lj: dd.rectangle([Q(r[0], r[1]), Q(r[2], r[3])], fill=(230, 225, 200))
for w in site['walls']: dd.polygon([Q(*p) for p in w], fill=(120, 120, 120))
col = {'glass_free': (0, 220, 120), 'front_door': (120, 60, 0), 'glass': (0, 150, 255), 'garage_door': (255, 120, 0), 'door': (160, 0, 160), 'interior': (255, 0, 0)}
for g in keep: dd.rectangle([Q(g['x0'], g['z0']), Q(g['x1'], g['z1'])], fill=col[g['kind']])
dbg.save(S + '/gaps.png'); print(dbg.size)
