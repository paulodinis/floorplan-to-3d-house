"""Elevations (4 façades) and a section through the stair, from layout.json — PNG per view + one DXF.

Usage (from the project work dir):
    PROJECT_JSON=project.json python3 elevations.py export/elevations [--storey all]
Writes elev_<side>.png (front, back, left, right as seen on the sheet), section_stair.png, elevations.png (sheet) and
elevations.dxf (views side by side, layers ELEV-*, SECT-*, ANNO). Orthographic, painter's algorithm, 1 px = 1/PX m.
Labels use the true bearing of each façade (north_deg = true north clockwise from sheet-up).
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else 'export/elevations'
os.makedirs(OUT, exist_ok=True)
L = json.load(open('site3d/layout.json', encoding='utf-8'))
site = json.load(open('site3d/site.json', encoding='utf-8'))
P = json.load(open(os.environ['PROJECT_JSON'], encoding='utf-8')) if os.environ.get('PROJECT_JSON') else {}
lang = P.get('lang', 'en')
TX = {'en': dict(facade='Façade facing {card} (bearing {b:.0f}°)', section='Section through the stair', ground='finished ground', natural='natural ground',
                 eave='eave', ridge='ridge', title='Elevations and section — indicative', cards=('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')),
      'pt-PT': dict(facade='Alçado virado a {card} (rumo {b:.0f}°)', section='Corte pela escada', ground='terreno final', natural='terreno natural',
                    eave='beirado', ridge='cumeeira', title='Alçados e corte — proposta indicativa', cards=('N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'))}
TX = TX.get(lang, TX['en'])
FFL = site['meta']['ffl']
NORTH = P.get('north_deg', L.get('meta', {}).get('north_deg', site['meta'].get('north_deg', 0.0)))
PITCH = math.radians(L.get('meta', {}).get('pitch', 16))
GR = L.get('grading', {})
SPOTS = site.get('spots', [])
fmt = lambda v: f'{v:.2f}'.replace('.', ',' if lang == 'pt-PT' else '.')

# ---------------- ground ----------------
def idw(x, z):
    sw = sh = 0.0
    for s in SPOTS:
        w = 1 / ((x - s['x']) ** 2 + (z - s['z']) ** 2 + 4) ** 1.3; sw += w; sh += w * s['h']
    return sh / sw if sw else FFL


def inside(x, z, poly):
    ins = False
    for i in range(len(poly)):
        (xi, zi), (xj, zj) = poly[i], poly[i - 1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi: ins = not ins
    return ins


def designed(x, z):
    if not GR or not inside(x, z, L['plot']): return idw(x, z)
    if x < GR['x_w1']:
        h = GR['upper'] - max(0, z - GR.get('upper_slope_from_z', 1e9)) * GR.get('upper_slope', 0)
    elif x < GR['x_w2']: h = GR['lower']
    elif x < GR['x_w3']: h = GR['t1']
    else: h = GR['t2']
    return h


# ---------------- geometry → 3D primitives ----------------
storey_filter = sys.argv[sys.argv.index('--storey') + 1] if '--storey' in sys.argv else 'all'
keep = (lambda o: True) if storey_filter == 'all' else (lambda o: str(o.get('storey', 0)) == storey_filter)
boxes = []   # (x0, x1, y0, y1, z0, z1, kind, ops-info)
walls = [w for w in L['walls'] if keep(w)]
for w in walls:
    (ax, az), (bx, bz) = w['a'], w['b']; t = w['t']
    if abs(az - bz) < 1e-6:   # along x
        boxes.append(dict(x0=min(ax, bx), x1=max(ax, bx), z0=az - t / 2, z1=az + t / 2, y0=w['y0'], y1=w['y0'] + w['h'], kind='stone' if w['mat'] == 'stone' else 'wall', ext=t >= 0.2, w=w, axis='x'))
    else:
        boxes.append(dict(x0=ax - t / 2, x1=ax + t / 2, z0=min(az, bz), z1=max(az, bz), y0=w['y0'], y1=w['y0'] + w['h'], kind='stone' if w['mat'] == 'stone' else 'wall', ext=t >= 0.2, w=w, axis='z'))
for c in L.get('columns', []):
    s = c['s'] / 2; boxes.append(dict(x0=c['x'] - s, x1=c['x'] + s, z0=c['z'] - s, z1=c['z'] + s, y0=c['y0'], y1=c['y0'] + c['h'], kind='stone', ext=True))
for sl in L.get('slats', []):
    boxes.append(dict(x0=sl['x0'], x1=sl['x1'], z0=sl['z0'], z1=sl['z1'], y0=sl['y0'], y1=sl['y1'], kind='timber', ext=True))

for r in L.get('railings', []):                       # balustrades (glass) and the edge of upper balconies / terraces
    if not keep(r): continue
    (ax, az), (bx, bz) = r['a'], r['b']
    boxes.append(dict(x0=min(ax, bx) - 0.02, x1=max(ax, bx) + 0.02, z0=min(az, bz) - 0.02, z1=max(az, bz) + 0.02, y0=r['y'], y1=r['y'] + r.get('h', 1.0), kind='glass', ext=True))
for fl in L.get('floors', []):
    if keep(fl) and fl.get('storey', 0) >= 1 and fl.get('mat') == 'terrace':
        xs_ = [p[0] for p in fl['poly']]; zs_ = [p[1] for p in fl['poly']]
        boxes.append(dict(x0=min(xs_), x1=max(xs_), z0=min(zs_), z1=max(zs_), y0=fl['y'] - 0.35, y1=fl['y'], kind='slab', ext=True))


def roof_faces(rect, Y):
    x0, z0, x1, z1 = rect; tn = math.tan(PITCH)
    if (x1 - x0) >= (z1 - z0):
        h = (z1 - z0) / 2 * tn; zc = (z0 + z1) / 2; r1 = (x0 + (z1 - z0) / 2, Y + h, zc); r2 = (x1 - (z1 - z0) / 2, Y + h, zc)
        return [[(x0, Y, z1), (x1, Y, z1), r2, r1], [(x1, Y, z0), (x0, Y, z0), r1, r2], [(x0, Y, z0), (x0, Y, z1), r1], [(x1, Y, z1), (x1, Y, z0), r2]], Y + h
    h = (x1 - x0) / 2 * tn; xc = (x0 + x1) / 2; r1 = (xc, Y + h, z0 + (x1 - x0) / 2); r2 = (xc, Y + h, z1 - (x1 - x0) / 2)
    return [[(x1, Y, z0), (x1, Y, z1), r2, r1], [(x0, Y, z1), (x0, Y, z0), r1, r2], [(x0, Y, z0), (x1, Y, z0), r1], [(x1, Y, z1), (x0, Y, z1), r2]], Y + h


roofs = []
for rf in L.get('roofs', []):
    if storey_filter != 'all' and str(rf.get('storey', 0)) != storey_filter: continue
    fs, ridge = roof_faces(rf['rect'], rf['eave']); roofs.append((rf, fs, ridge))


def roof_h(x, z):   # union of hip roofs: height of the highest surface over (x, z), or None
    best = None
    for rf, fs, ridge in roofs:
        x0, z0, x1, z1 = rf['rect']
        if x0 <= x <= x1 and z0 <= z <= z1:
            h = rf['eave'] + math.tan(PITCH) * min(x - x0, x1 - x, z - z0, z1 - z)
            best = h if best is None else max(best, h)
    return best


# ---------------- views ----------------
def bearing(dx, dz):   # true bearing of a scene direction (x east-ish, z south-ish on the sheet)
    sheet = math.degrees(math.atan2(dx, -dz)) % 360    # 0 = sheet-up
    return (sheet - NORTH) % 360


def cardinal(b): return TX['cards'][int(((b + 22.5) % 360) // 45)]


VIEWS = {  # name: (outward normal dx, dz, u(x, z), depth(x, z) larger = farther)
    'front': ((0, 1), lambda x, z: x, lambda x, z: -z),
    'back': ((0, -1), lambda x, z: -x, lambda x, z: z),
    'right': ((1, 0), lambda x, z: -z, lambda x, z: -x),
    'left': ((-1, 0), lambda x, z: z, lambda x, z: x),
}
PX = 40          # px per metre
COL = dict(wall=(246, 244, 238), stone=(222, 210, 186), timber=(176, 124, 78), roof=(74, 80, 90), roof2=(96, 102, 112), glass=(150, 190, 220),
           door=(120, 84, 56), garage=(170, 120, 76), open=(60, 60, 60), slab=(200, 200, 196), ground=(232, 236, 222), line=(30, 30, 30), cut=(20, 20, 20))
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
f = lambda sz: ImageFont.truetype(FONT, sz)
dxf_items = []   # (layer, polyline points in metres (u, y), closed, view offset index)


def project_box(b, U, Dp):
    pts = [(b['x0'], b['z0']), (b['x1'], b['z0']), (b['x1'], b['z1']), (b['x0'], b['z1'])]
    us = [U(x, z) for x, z in pts]; ds = [Dp(x, z) for x, z in pts]
    return min(us), max(us), min(ds)


def render_view(name):
    (nx, nz), U, Dp = VIEWS[name]
    polys = []
    for b in boxes:
        u0, u1, d = project_box(b, U, Dp)
        polys.append((d, b['kind'], [(u0, b['y0']), (u1, b['y0']), (u1, b['y1']), (u0, b['y1'])]))
        w = b.get('w')
        if w and ((b['axis'] == 'x' and nz != 0) or (b['axis'] == 'z' and nx != 0)):      # wall parallel to the view plane: openings
            (ax, az), (bx, bz) = w['a'], w['b']; Lw = math.hypot(bx - ax, bz - az); ux, uz = (bx - ax) / Lw, (bz - az) / Lw
            for o in w.get('ops', []):
                kind = o['kind']; sill = o.get('sill', 0.0); head = o.get('head', 2.4)
                pa = (ax + ux * o['o'], az + uz * o['o']); pb = (ax + ux * (o['o'] + o['w']), az + uz * (o['o'] + o['w']))
                ua, ub = sorted((U(*pa), U(*pb)))
                c = 'glass' if kind in ('window', 'slide', 'door_glass') else 'garage' if kind == 'garage' else 'open' if kind == 'open' else 'door'
                polys.append((d - 0.001, c, [(ua, w['y0'] + sill), (ub, w['y0'] + sill), (ub, w['y0'] + head), (ua, w['y0'] + head)]))
    for rf, fs, ridge in roofs:
        for k, face in enumerate(fs):
            d = sum(Dp(p[0], p[2]) for p in face) / len(face)
            n = 'roof' if k < 2 else 'roof2'
            polys.append((d - 0.002, n, [(U(p[0], p[2]), p[1]) for p in face]))
    polys.sort(key=lambda t: -t[0])
    us = [p[0] for _, _, poly in polys for p in poly]; ys = [p[1] for _, _, poly in polys for p in poly]
    umin, umax = min(us) - 4, max(us) + 4
    # ground profile along the front plane of the house (1 m in front of the nearest face)
    dnear = min(t[0] for t in polys) - 1.0
    prof, nat = [], []
    for i in range(int((umax - umin) * 4) + 1):
        u = umin + i * 0.25
        if name == 'front': x, z = u, -dnear
        elif name == 'back': x, z = -u, dnear
        elif name == 'right': x, z = -dnear, -u
        else: x, z = dnear, u
        prof.append((u, designed(x, z) - FFL)); nat.append((u, idw(x, z) - FFL))
    ymin = min(min(p[1] for p in prof), min(ys)) - 1.5; ymax = max(ys) + 1.5
    W, H = int((umax - umin) * PX), int((ymax - ymin) * PX) + 70
    im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    Q = lambda u, y: ((u - umin) * PX, (ymax - y) * PX)
    for dep, kind, poly in polys:
        d.polygon([Q(*p) for p in poly], fill=COL[kind], outline=COL['line'] if kind not in ('roof', 'roof2') else (40, 44, 50))
        layer = {'glass': 'ELEV-OPEN', 'door': 'ELEV-OPEN', 'garage': 'ELEV-OPEN', 'open': 'ELEV-OPEN', 'roof': 'ELEV-ROOF', 'roof2': 'ELEV-ROOF'}.get(kind, 'ELEV-WALL')
        dxf_items.append((name, layer, poly, True))
    gp = [Q(*p) for p in prof]
    d.polygon(gp + [Q(prof[-1][0], ymin), Q(prof[0][0], ymin)], fill=COL['ground'])
    d.line(gp, fill=(60, 90, 40), width=3)
    for i in range(0, len(nat) - 1, 2): d.line([Q(*nat[i]), Q(*nat[i + 1])], fill=(140, 120, 90), width=1)
    dxf_items.append((name, 'ELEV-GROUND', prof, False))
    annotate(d, name, Q, umax, (nx, nz), W, H)
    return im


def annotate(d, name, Q, umax, n, W, H):
    lv = sorted({b['level'] for b in L['blocks'].values() if 'level' in b}, reverse=True)
    eaves = sorted({rf['eave'] for rf, _, _ in roofs}, reverse=True); ridges = sorted({round(r, 2) for _, _, r in roofs}, reverse=True)
    marks = [(v - FFL, '▽ ' + fmt(v)) for v in lv] + [(e, f"{TX['eave']} {fmt(e + FFL)}") for e in eaves[:2]] + [(r, f"{TX['ridge']} {fmt(r + FFL)}") for r in ridges[:1]]
    last = -1e9
    for y, txt in sorted(marks, key=lambda m: m[0]):          # bottom-up, labels pushed apart by at least 18 px
        x, yy = Q(umax - 3.6, y); ty = min(yy, last - 18) if last > -1e9 else yy; last = ty
        d.line([(x - 8, yy), (x + 8, yy)], fill=(190, 0, 120), width=2); d.text((x + 12, ty), txt, fill=(190, 0, 120), font=f(15), anchor='lm')
    if name.startswith('sect'):
        title = TX['section']
    else:
        b = bearing(*n); title = TX['facade'].format(card=cardinal(b), b=b)
    d.text((16, H - 40), title, fill=(0, 0, 0), font=f(22))
    sx = W - 16 - 5 * PX
    for k in range(5): d.rectangle([sx + k * PX, H - 30, sx + (k + 1) * PX, H - 22], fill=(20, 20, 20) if k % 2 == 0 else (255, 255, 255), outline=(20, 20, 20))
    d.text((sx, H - 34), '0', fill=(0, 0, 0), font=f(12), anchor='ms'); d.text((sx + 5 * PX, H - 34), '5 m', fill=(0, 0, 0), font=f(12), anchor='ms')


def render_section():
    st = L.get('stairs', [])
    if not st: return None
    s0 = st[0]; zc = (s0['z0'] + s0['z1']) / 2
    U = lambda x, z: x; Dp = lambda x, z: -z
    cut, beyond = [], []
    for b in boxes:
        if b['z0'] <= zc <= b['z1'] and b.get('axis') != 'x':     # walls (and columns) crossing the plane: cut
            gaps = []
            w = b.get('w')
            if w:
                (ax, az), (bx, bz) = w['a'], w['b']; z_lo = min(az, bz)
                for o in w.get('ops', []):
                    za, zb = sorted((az + (o['o'] if bz > az else -o['o']), az + ((o['o'] + o['w']) if bz > az else -(o['o'] + o['w']))))
                    if za <= zc <= zb: gaps.append((w['y0'] + o.get('sill', 0), w['y0'] + o.get('head', 2.4)))
            ys = [b['y0']] + [g for gp in sorted(gaps) for g in gp] + [b['y1']]
            for i in range(0, len(ys) - 1, 2):
                if ys[i + 1] - ys[i] > 0.01: cut.append([(b['x0'], ys[i]), (b['x1'], ys[i]), (b['x1'], ys[i + 1]), (b['x0'], ys[i + 1])])
        elif b['z1'] < zc and b.get('axis') == 'x':                # walls behind the plane, seen in elevation
            beyond.append((-b['z1'], b))
    for fl in L.get('floors', []):
        if not keep(fl): continue
        xs = []
        poly = fl['poly']
        for i in range(len(poly)):
            (x1, z1), (x2, z2) = poly[i - 1], poly[i]
            if (z1 - zc) * (z2 - zc) < 0 or z1 == zc: xs.append(x1 + (x2 - x1) * (zc - z1) / (z2 - z1) if z2 != z1 else x1)
        xs.sort()
        hx = []                                               # stair voids / double-height holes crossed by the cut
        for h in fl.get('holes', []):
            for i in range(len(h)):
                (x1, z1), (x2, z2) = h[i - 1], h[i]
                if (z1 - zc) * (z2 - zc) < 0: hx.append(x1 + (x2 - x1) * (zc - z1) / (z2 - z1))
        hx.sort(); voids = list(zip(hx[0::2], hx[1::2]))
        for i in range(0, len(xs) - 1, 2):
            segs = [(xs[i], xs[i + 1])]
            for va, vb in voids:
                segs = [p for a_, b_ in segs for p in ((a_, min(b_, va)), (max(a_, vb), b_)) if p[1] - p[0] > 0.01]
            for a_, b_ in segs:
                cut.append([(a_, fl['y'] - 0.35), (b_, fl['y'] - 0.35), (b_, fl['y']), (a_, fl['y'])])
    for sx in st:
        if sx['z0'] <= zc <= sx['z1']:
            rise = (sx['ytop'] - sx['ybot']) / sx['n']; run = (sx['x1'] - sx['x0']) / sx['n']
            for i in range(1, sx['n'] + 1):
                cut.append([(sx['x0'] + (i - 1) * run, sx['ybot'] - 0.05), (sx['x0'] + i * run, sx['ybot'] - 0.05), (sx['x0'] + i * run, sx['ytop'] - i * rise), (sx['x0'] + (i - 1) * run, sx['ytop'] - i * rise)])
    xs_all = [p[0] for c in cut for p in c] + [b['x0'] for _, b in beyond] + [b['x1'] for _, b in beyond]
    umin, umax = min(xs_all) - 4, max(xs_all) + 4
    rline = [(x / 4, roof_h(x / 4, zc)) for x in range(int(umin * 4), int(umax * 4) + 1)]
    prof = [(u / 4, designed(u / 4, zc) - FFL) for u in range(int(umin * 4), int(umax * 4) + 1)]
    ys = [p[1] for c in cut for p in c] + [h for _, h in rline if h is not None]
    ymin = min(min(p[1] for p in prof), min(ys)) - 1.5; ymax = max(ys) + 1.5
    W, H = int((umax - umin) * PX), int((ymax - ymin) * PX) + 70
    im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    Q = lambda u, y: ((u - umin) * PX, (ymax - y) * PX)
    gp = [Q(*p) for p in prof]
    d.polygon(gp + [Q(prof[-1][0], ymin), Q(prof[0][0], ymin)], fill=COL['ground']); d.line(gp, fill=(60, 90, 40), width=3)
    for dep, b in sorted(beyond, key=lambda t: -t[0]):
        d.polygon([Q(b['x0'], b['y0']), Q(b['x1'], b['y0']), Q(b['x1'], b['y1']), Q(b['x0'], b['y1'])], fill=(250, 250, 248), outline=(170, 170, 170))
        w = b['w']; (ax, az), (bx, bz) = w['a'], w['b']; sgn = 1 if bx >= ax else -1
        for o in w.get('ops', []):
            u0, u1 = sorted((ax + sgn * o['o'], ax + sgn * (o['o'] + o['w'])))
            d.rectangle([Q(u0, w['y0'] + o.get('head', 2.4)), Q(u1, w['y0'] + o.get('sill', 0))], outline=(150, 170, 190))
    seg = []
    for x, h in rline:
        if h is None:
            if len(seg) > 1: d.line([Q(*p) for p in seg], fill=COL['cut'], width=8); dxf_items.append(('section', 'SECT-ROOF', seg, False))
            seg = []
        else: seg.append((x, h))
    if len(seg) > 1: d.line([Q(*p) for p in seg], fill=COL['cut'], width=8); dxf_items.append(('section', 'SECT-ROOF', seg, False))
    for c in cut:
        d.polygon([Q(*p) for p in c], fill=COL['cut']); dxf_items.append(('section', 'SECT-CUT', c, True))
    dxf_items.append(('section', 'ELEV-GROUND', prof, False))
    annotate(d, 'section', Q, umax, (0, 1), W, H)
    return im


views = {}
for nm in ('front', 'back', 'right', 'left'):
    views[nm] = render_view(nm); views[nm].save(os.path.join(OUT, f'elev_{nm}.png'))
sec = render_section()
if sec: views['section'] = sec; sec.save(os.path.join(OUT, 'section_stair.png'))
# sheet
order = [k for k in ('front', 'back', 'right', 'left', 'section') if k in views]
cw = max(v.width for v in views.values())
rows = [order[i:i + 2] for i in range(0, len(order), 2)]
Wt = cw * 2 + 60; Ht = sum(max(views[k].height for k in r) + 30 for r in rows) + 80
sheet = Image.new('RGB', (Wt, Ht), (255, 255, 255)); ds = ImageDraw.Draw(sheet)
ds.text((30, 24), TX['title'], fill=(0, 0, 0), font=f(30))
y = 80
for r in rows:
    for i, k in enumerate(r): sheet.paste(views[k], (20 + i * (cw + 20), y))
    y += max(views[k].height for k in r) + 30
sheet.save(os.path.join(OUT, 'elevations.png'))
# DXF
try:
    sys.path.insert(0, os.environ.get('EZDXF_SRC', 'ezdxf-src/src')); import ezdxf
    doc = ezdxf.new('R2010', setup=True); doc.units = ezdxf.units.M; msp = doc.modelspace()
    for lay, rgb in (('ELEV-WALL', (60, 60, 60)), ('ELEV-OPEN', (0, 120, 200)), ('ELEV-ROOF', (90, 90, 90)), ('ELEV-GROUND', (60, 120, 40)), ('SECT-CUT', (0, 0, 0)), ('SECT-ROOF', (0, 0, 0)), ('ANNO', (190, 0, 120))):
        doc.layers.add(lay).rgb = rgb
    off = {k: (i % 2 * 60.0, -(i // 2) * 25.0) for i, k in enumerate(order)}
    for view, lay, pts, closed in dxf_items:
        ox, oy = off.get(view, (0, 0))
        msp.add_lwpolyline([(ox + u, oy + y) for u, y in pts], close=closed, dxfattribs={'layer': lay})
    for k, (ox, oy) in off.items():
        msp.add_text(k, height=0.6, dxfattribs={'layer': 'ANNO'}).set_placement((ox, oy - 3))
    doc.saveas(os.path.join(OUT, 'elevations.dxf'))
    print('dxf ok')
except Exception as e:
    print('dxf skipped:', e)
print('views', {k: v.size for k, v in views.items()})
