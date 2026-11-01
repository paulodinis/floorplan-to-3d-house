"""Material-painted ground texture from the site plan: grass, limestone slabs, calçada, road, floors."""
import sys, json, math
import numpy as np, cv2
import pdfplumber
from PIL import Image, ImageDraw

src, sitejson, out, dbg = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
import os
SCALE = float(os.environ.get('PLAN_SCALE', '200'))   # drawing scale 1:SCALE
K = 25.4 / 72 * SCALE / 1000
OX, OY = 500.0, 320.0
RX0, RY0, RX1, RY1 = 72.0, 16.0, 1008.0, 812.0
TW = 4096
TH = int(round(TW * (RY1 - RY0) / (RX1 - RX0)))
PXM = TW / ((RX1 - RX0) * K)            # pixels per metre (~62)
site = json.load(open(sitejson))
pg = pdfplumber.open(src).pages[0]
objs = pg.layout._objs
rng = np.random.default_rng(7)
sx = TW / (RX1 - RX0)

def T(p): return ((p[0] - RX0) * sx, (RY1 - p[1]) * sx)
def Tm(xz): return T((xz[0] / K + OX, OY - xz[1] / K))
def rgb(c):
    c = tuple(c or (0, 0, 0))
    if len(c) == 1: c = c * 3
    return tuple(round(v, 2) for v in c[:3])
def blank(): return Image.new('L', (TW, TH), 0)
def arr(im): return np.array(im)

def lines_mask(pred, width=2):
    im = blank(); d = ImageDraw.Draw(im)
    for o in objs:
        if type(o).__name__ == 'LTChar' or not hasattr(o, 'pts'): continue
        if getattr(o, 'stroke', False) and pred(o):
            d.line([T(p) for p in o.pts], fill=255, width=width)
    return arr(im)

def close(m, k):
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, ker)

def noise(scale_m, amp=1.0, seed=0):
    """smooth value noise, feature size ~scale_m metres, range ~[-1,1]"""
    r = np.random.default_rng(seed)
    gw, gh = max(2, int(TW / (scale_m * PXM)) + 2), max(2, int(TH / (scale_m * PXM)) + 2)
    g = r.random((gh, gw)).astype(np.float32) * 2 - 1
    return cv2.resize(g, (TW, TH), interpolation=cv2.INTER_CUBIC) * amp

def fbm(seed, octaves=((6, .5), (2, .3), (.6, .15), (.15, .08))):
    return sum(noise(s, a, seed + i) for i, (s, a) in enumerate(octaves))

# ---------- masks ----------
boundary = blank(); ImageDraw.Draw(boundary).polygon([Tm(p) for p in site['boundary']], fill=255); boundary = arr(boundary)
house = blank(); ImageDraw.Draw(house).polygon([Tm(p) for p in site['roof']], fill=255); house = arr(house)

grass = lines_mask(lambda o: rgb(o.stroking_color) == (0.36, 0.72, 0.0) and not o.fill, 6)
grass = close(grass, 19); grass = close(grass, 19)

# covered terraces (alpendres) + eave strips paved in limestone slabs, read off the plan (pt)
lj_rects = [(413, 332, 481, 381), (553, 332, 680, 376), (547, 472, 680, 488), (413, 141, 428, 332)]
lj = blank(); ljd = ImageDraw.Draw(lj)
for x0, y0, x1, y1 in lj_rects:
    ljd.rectangle([T((x0, y1)), T((x1, y0))], fill=255)
lajeta = arr(lj)
yy0, xx0 = np.mgrid[0:TH, 0:TW]
sl = int(0.6 * PXM)
lajeta_lines = ((((xx0 % sl) == 0) | ((yy0 % sl) == 0)) & (lajeta > 0)).astype(np.uint8) * 255

ceder = lines_mask(lambda o: rgb(o.stroking_color) == (0.43, 0.54, 0.87) and o.x1 < 1000, 3)
ceder = close(ceder, int(0.9 * PXM))
ceder[:, int((300 - RX0) * sx):] = 0

# road: band around the dashed centre line west of the plot
cl = []
for o in objs:
    if type(o).__name__ == 'LTLine' and rgb(o.stroking_color) == (0.0, 0.0, 0.0) and 150 < o.x0 < 260 and o.x1 < 260:
        L = math.dist(o.pts[0], o.pts[-1])
        if 2.0 < L < 9 and abs(o.pts[0][0] - o.pts[-1][0]) < 2.5:
            cl.append(((o.pts[0][0] + o.pts[-1][0]) / 2, (o.pts[0][1] + o.pts[-1][1]) / 2, o))
cl.sort(key=lambda t: t[1])
ys = np.array([c[1] for c in cl]); xs = np.array([c[0] for c in cl])
keep = np.ones(len(cl), bool)
for _ in range(4):
    co = np.polyfit(ys[keep], xs[keep], 3)
    res = np.abs(np.polyval(co, ys) - xs)
    keep = res < max(3.0, np.median(res[keep]) * 3)
cl = [c for c, k in zip(cl, keep) if k]
road = blank(); rd = ImageDraw.Draw(road)
yline = np.linspace(RY0 - 20, RY1 + 20, 300)
cpts = np.array([T((float(np.polyval(co, y)), float(y))) for y in yline])
tang = np.gradient(cpts, axis=0); tang /= np.linalg.norm(tang, axis=1, keepdims=True)
nrm = np.stack([-tang[:, 1], tang[:, 0]], 1) * (2.5 * PXM)
poly = [tuple(p) for p in (cpts + nrm)] + [tuple(p) for p in (cpts - nrm)[::-1]]
rd.polygon(poly, fill=255)
road = arr(road) & ~boundary & ~ceder
print('road dashes', len(cl))

garage_pt = [(408, 402), (500, 402), (500, 488), (408, 488)]
garage = blank(); ImageDraw.Draw(garage).polygon([T(p) for p in garage_pt], fill=255); garage = arr(garage)

interior = house & ~lajeta & ~garage
calcada = boundary & ~grass & ~lajeta & ~house & ~ceder


# ---------- material masks for the shader ----------
def sm(m, k=5):
    return cv2.GaussianBlur((m > 0).astype(np.float32), (k, k), 0)
lawn_m = sm(grass & boundary)
mk = Image.new('L', (TW, TH), 0); md = ImageDraw.Draw(mk)
for x, y, o in cl:
    md.line([T(p) for p in o.pts], fill=255, width=max(2, int(0.12 * PXM)))
mark = sm(arr(mk), 3)
z = np.zeros_like(lawn_m)
for name, chans in (('mask1', (lawn_m, sm(calcada), sm(road))), ('mask2', (sm(lajeta), sm(interior), sm(garage & house))), ('mask3', (sm(ceder), mark, z))):
    Image.fromarray((np.stack(chans, -1) * 255).astype(np.uint8), 'RGB').save(out + '/' + name + '.png', optimize=True)
print('masks saved', TW, TH)
