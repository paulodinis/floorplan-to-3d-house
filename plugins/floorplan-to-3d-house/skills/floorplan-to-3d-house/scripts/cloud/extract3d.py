"""Extract 3D-relevant geometry + ground texture from the site plan PDF."""
import sys, json, math, re
import numpy as np, cv2
import pdfplumber
from PIL import Image, ImageDraw

src, outdir = sys.argv[1], sys.argv[2]
import os
SCALE = float(os.environ.get('PLAN_SCALE', '200'))   # drawing scale 1:SCALE
K = 25.4 / 72 * SCALE / 1000            # pt -> m at 1:200
OX, OY = 500.0, 320.0                 # scene origin (pt), roughly house centre
RX0, RY0, RX1, RY1 = 72.0, 16.0, 1008.0, 812.0   # ground texture window (pt, bottom-up)
TW = 4096
TH = int(round(TW * (RY1 - RY0) / (RX1 - RX0)))
SS = 2                                 # supersample
pg = pdfplumber.open(src).pages[0]
objs = pg.layout._objs

def M(x, y):  # pt -> scene metres (x east, z south)
    return [round((x - OX) * K, 3), round(-(y - OY) * K, 3)]

def rgb(c):
    c = tuple(c or (0, 0, 0))
    if len(c) == 1: c = c * 3
    return tuple(round(v, 2) for v in c[:3])

def rings(o):
    res, cur = [], []
    for op in o.original_path or []:
        if op[0] == 'm':
            if len(cur) > 2: res.append(cur)
            cur = [op[1]]
        elif op[0] == 'l': cur.append(op[1])
        elif op[0] == 'c': cur.append(op[3])
    if len(cur) > 2: res.append(cur)
    return res

# ---------- walls (grey poché fills) ----------
walls = []
for o in objs:
    if getattr(o, 'fill', False) and rgb(o.non_stroking_color) == (0.6, 0.6, 0.6):
        for r in rings(o):
            walls.append([M(*p) for p in r])

# ---------- roof outline (dashed eaves line read off the plan) ----------
roof_pt = [(334, 141), (428, 141), (428, 332), (680, 332), (680, 488), (386, 488), (386, 407), (334, 407)]
# snap to nearest wall/dash coordinates measured precisely
roof = [M(*p) for p in roof_pt]

# ---------- plot boundary: chain red dashes ----------
red = [o for o in objs if getattr(o, 'stroke', False) and rgb(o.stroking_color) == (1.0, 0.0, 0.0) and o.x1 < 1000]
segs = []
for o in red:
    if type(o).__name__ != 'LTCurve' or len(o.pts) < 4: continue
    c = o.pts[:4]
    e = [(math.dist(c[i], c[(i + 1) % 4]), i) for i in range(4)]
    e.sort()
    i1, i2 = e[0][1], e[1][1]
    mid = lambda i: ((c[i][0] + c[(i + 1) % 4][0]) / 2, (c[i][1] + c[(i + 1) % 4][1]) / 2)
    segs.append((mid(i1), mid(i2)))
used = [False] * len(segs)
chain = list(segs[0]); used[0] = True
for _ in range(len(segs) - 1):
    end = chain[-1]; best = None
    for i, (a, b) in enumerate(segs):
        if used[i]: continue
        for p, q in ((a, b), (b, a)):
            d = math.dist(end, p)
            if best is None or d < best[0]: best = (d, i, p, q)
    if best is None or best[0] > 25: break
    used[best[1]] = True; chain += [best[2], best[3]]
# simplify
pts = np.array(chain, dtype=np.float32).reshape(-1, 1, 2)
simp = cv2.approxPolyDP(pts, 0.6, True).reshape(-1, 2)
boundary = [M(float(x), float(y)) for x, y in simp]
area = 0.5 * abs(sum(boundary[i][0] * boundary[i - 1][1] - boundary[i - 1][0] * boundary[i][1] for i in range(len(boundary))))
print('boundary pts', len(boundary), 'area m2', round(area, 1), 'dashes used', sum(used), '/', len(segs))

# ---------- spot heights ----------
chars = [o for o in objs if type(o).__name__ == 'LTChar']
runs, cur = [], []
for c in chars:
    if cur and (c.matrix[:4] != cur[-1].matrix[:4] or math.dist(c.matrix[4:], cur[-1].matrix[4:]) > 5):
        runs.append(cur); cur = []
    cur.append(c)
runs.append(cur)
spots = []
for r in runs:
    s = ''.join(c.get_text() for c in r).strip()
    if re.fullmatch(r'\d\d\.\d{3}', s) and r[0].x0 < 1000:
        h = float(s)
        if not (26 < h < 33.0):   # drop neighbour-structure tops (34-36 m) and the 68.069 typo
            continue
        dot = [c for c in r if c.get_text() == '.'][0]
        x, z = M((dot.x0 + dot.x1) / 2, (dot.y0 + dot.y1) / 2)
        spots.append({'x': x, 'z': z, 'h': h, 'label': s})
print('spots', len(spots))

# ---------- trees (symbol centres read off the plan) ----------
trees_pt = [(291.0, 533.0, 11), (345.3, 535.0, 11), (345.3, 503.3, 11), (912.7, 459.6, 13), (156.8, 278.4, 13), (310.9, 484.7, 15)]
trees = [{'x': M(x, y)[0], 'z': M(x, y)[1], 'r': round(r * K, 2)} for x, y, r in trees_pt]

# ---------- ground texture ----------
W, H = TW * SS, TH * SS
sx = W / (RX1 - RX0)
def T(p): return ((p[0] - RX0) * sx, (RY1 - p[1]) * sx)

BG = (226, 221, 208)       # bare ground / gravel
GRASS = (150, 178, 102)
img = Image.new('RGB', (W, H), BG)
d = ImageDraw.Draw(img)

# garden mask from the green dot hatch, closed into solid regions
mask = Image.new('L', (W, H), 0); md = ImageDraw.Draw(mask)
for o in objs:
    if type(o).__name__ == 'LTLine' and rgb(o.stroking_color) == (0.36, 0.72, 0.0):
        md.line([T(p) for p in o.pts], fill=255, width=int(3 * SS))
m = np.array(mask)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9 * SS, 9 * SS))
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
m = cv2.GaussianBlur(m, (5, 5), 0)
grass = Image.new('RGB', (W, H), GRASS)
img.paste(grass, (0, 0), Image.fromarray(m))
# subtle grass speckle
noise = (np.random.default_rng(1).random((H // 4, W // 4)) * 18 - 9).astype(np.int16)
noise = cv2.resize(noise.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
arr = np.array(img).astype(np.int16)
arr += (noise[..., None] * (m[..., None] / 255.0)).astype(np.int16)
img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(img)

def col(c, alpha_to_bg=0.0):
    c = tuple(int(v * 255) for v in c)
    return c

for o in objs:
    tn = type(o).__name__
    if tn == 'LTChar' or not hasattr(o, 'original_path'): continue
    if o.x1 < RX0 or o.x0 > RX1 or o.y1 < RY0 or o.y0 > RY1: continue
    sc, fc = rgb(o.stroking_color), rgb(o.non_stroking_color)
    if sc == (0.36, 0.72, 0.0) and not o.fill: continue          # hatch already turned into grass
    if o.fill:
        if fc == (1.0, 1.0, 1.0): continue
        f = {(0.6, 0.6, 0.6): (120, 120, 118)}.get(fc, tuple(int(v * 255) for v in fc))
        for r in rings(o):
            d.polygon([T(p) for p in r], fill=f)
    if o.stroke:
        w = max(1, int(round((o.linewidth or 0.1) * sx * 0.8)))
        c = tuple(int(v * 255) for v in sc)
        if sc == (0.0, 0.0, 0.0):
            c = (70, 66, 60)
        for r in [list(o.pts)] if tn == 'LTLine' else ([p for p in rings(o)] or [list(o.pts)]):
            if len(r) >= 2: d.line([T(p) for p in r], fill=c, width=w)

img = img.resize((TW, TH), Image.LANCZOS)
img.save(f'{outdir}/ground.jpg', quality=84, optimize=True)

data = {
    'meta': {'scale': '1:%g' % SCALE, 'ffl': 32.00, 'origin_pt': [OX, OY]},
    'ground': {'x0': M(RX0, RY0)[0], 'x1': M(RX1, RY0)[0], 'z0': M(RX0, RY1)[1], 'z1': M(RX0, RY0)[1]},
    'walls': walls, 'roof': roof, 'boundary': boundary, 'spots': spots, 'trees': trees,
}
json.dump(data, open(f'{outdir}/site.json', 'w'))
print('walls', len(walls), 'texture', TW, TH)
