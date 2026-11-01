"""Material-painted ground texture from the site plan: grass, limestone slabs, calçada, road, floors."""
import sys, json, math
import numpy as np, cv2
import pdfplumber
from PIL import Image, ImageDraw

src, sitejson, out, dbg = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
K = 25.4 / 72 * 200 / 1000
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
rd.line([T((float(np.polyval(co, y)), float(y))) for y in yline], fill=255, width=int(5.0 * PXM))
road = arr(road) & ~boundary & ~ceder
print('road dashes', len(cl))

garage_pt = [(408, 402), (500, 402), (500, 488), (408, 488)]
garage = blank(); ImageDraw.Draw(garage).polygon([T(p) for p in garage_pt], fill=255); garage = arr(garage)

interior = house & ~lajeta & ~garage
calcada = boundary & ~grass & ~lajeta & ~house & ~ceder

# ---------- materials ----------
def solid(c): return np.ones((TH, TW, 3), np.float32) * np.array(c, np.float32)
def tint(img, n): return img * (1 + n[..., None])

# rural surroundings: dry meadow / soil
meadow = solid((150, 146, 98))
soil = solid((158, 134, 102))
mm = np.clip(fbm(11) * 0.9 + 0.15, 0, 1)[..., None] * 0.7
outside = meadow * (1 - mm) + soil * mm
outside = tint(outside, fbm(21, ((3, .08), (.4, .06), (.08, .07))))

# lawn
lawn = solid((96, 122, 66))
lawn = tint(lawn, fbm(31, ((8, .06), (2.5, .05), (.5, .05), (.07, .09))))
stripe = (np.sin(np.arange(TW) / (2.2 * PXM) * math.pi)[None, :] * 0.035).astype(np.float32)
lawn = tint(lawn, np.broadcast_to(stripe, (TH, TW)).copy())

# limestone slabs (lajetas): per-cell tint using the drawn joints
stone = solid((216, 208, 189))
cells_src = ((lajeta > 0) & (lajeta_lines == 0)).astype(np.uint8)
n, lab = cv2.connectedComponents(cells_src, connectivity=4)
cell_t = (rng.random(n).astype(np.float32) - 0.5) * 0.10
stone = tint(stone, cell_t[lab] + fbm(41, ((0.3, .03), (0.05, .04))))
stone[lajeta_lines > 0] *= 0.72

# calçada (small limestone setts) for paths and parking
cs = int(0.09 * PXM) or 1
sg = rng.random((TH // cs + 1, TW // cs + 1)).astype(np.float32)
sett = np.kron(sg, np.ones((cs, cs), np.float32))[:TH, :TW]
calc = solid((205, 199, 184))
calc = tint(calc, (sett - 0.5) * 0.16 + fbm(51, ((2, .05),)))
jx = (np.arange(TW) % cs == 0)[None, :]; jy = (np.arange(TH) % cs == 0)[:, None]
calc[np.broadcast_to(jx | jy, (TH, TW))] *= 0.8

# public sidewalk to be ceded: light concrete pavers 0.4 x 0.2
pav = solid((184, 182, 176))
pav = tint(pav, fbm(61, ((1, .04), (0.1, .05))))
px_, py_ = int(0.4 * PXM), int(0.2 * PXM)
yy, xx = np.mgrid[0:TH, 0:TW]
off = ((yy // py_) % 2) * (px_ // 2)
pav[(((xx + off) % px_) == 0) | ((yy % py_) == 0)] *= 0.82

# asphalt
asph = solid((84, 84, 86))
asph = tint(asph, fbm(71, ((4, .06), (0.3, .05), (0.03, .12))))

# interior oak planks
plank_w, plank_l = int(0.19 * PXM), int(1.8 * PXM)
row = yy // plank_w
offs = (rng.random(row.max() + 2) * plank_l).astype(np.int32)[row]
pid = row * 1000 + (xx + offs) // plank_l
ptint = (rng.random(int(pid.max()) + 1).astype(np.float32) - 0.5) * 0.14
oak = solid((186, 150, 108))
grain = noise(0.6, 0.04, 81) + cv2.resize(rng.random((TH // 3, TW // 40)).astype(np.float32) - .5, (TW, TH)) * 0.06
oak = tint(oak, ptint[pid] + grain)
oak[(yy % plank_w == 0) | (((xx + offs) % plank_l) == 0)] *= 0.78

conc = tint(solid((172, 170, 164)), fbm(91, ((2, .05), (0.2, .04))))

# ---------- composite ----------
def soft(m, k=3):
    return cv2.GaussianBlur((m > 0).astype(np.float32), (k, k), 0)[..., None]
img = outside
for mat, m in ((asph, road), (pav, ceder), (calc, calcada), (lawn, grass & boundary), (stone, lajeta), (oak, interior), (conc, garage & house)):
    a = soft(m)
    img = img * (1 - a) + mat * a

# grass edge darkening along paving
edge = cv2.GaussianBlur(((grass & boundary) > 0).astype(np.float32), (0, 0), 0.08 * PXM)
img *= (0.9 + 0.1 * np.clip(edge * 2, 0, 1))[..., None] * (grass[..., None] > 0) + (grass[..., None] == 0)

# road centre dashes in white
im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
d = ImageDraw.Draw(im)
for x, y, o in cl:
    d.line([T(p) for p in o.pts], fill=(232, 230, 222), width=max(2, int(0.12 * PXM)))

# furniture/linework inside the house only (thin, ink on floor); skip long dimension runs and ticks
hm = house > 0
for o in objs:
    if type(o).__name__ == 'LTChar' or not hasattr(o, 'pts') or not getattr(o, 'stroke', False): continue
    if rgb(o.stroking_color) != (0.0, 0.0, 0.0) or o.fill: continue
    pts = [T(p) for p in o.pts]
    if not all(0 <= x < TW and 0 <= y < TH and hm[int(y), int(x)] for x, y in pts): continue
    if len(pts) == 2:
        L = math.dist(pts[0], pts[1]) / PXM
        dx, dy = abs(pts[0][0] - pts[1][0]), abs(pts[0][1] - pts[1][1])
        if L > 2.2 and (dx < 1 or dy < 1): continue           # dimension lines
        if L < 0.45 and abs(dx - dy) < 0.3 * max(dx, dy, 1e-6): continue   # 45° dimension ticks
    d.line(pts, fill=(88, 74, 60), width=2)

# fade outer border into meadow
a = np.array(im).astype(np.float32)
f = 110
yy1 = np.minimum(np.arange(TH), np.arange(TH)[::-1])[:, None]; xx1 = np.minimum(np.arange(TW), np.arange(TW)[::-1])[None, :]
t = np.clip(np.minimum(yy1, xx1) / f, 0, 1); t = t * t * (3 - 2 * t)
edgecol = np.array((152, 144, 100), np.float32)
a = a * t[..., None] + edgecol * (1 - t[..., None])
Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(out, quality=86, optimize=True)
Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((1600, int(1600 * TH / TW)), Image.LANCZOS).save(dbg)
print('done', TW, TH, 'px/m', round(PXM, 1), 'cells', n)
