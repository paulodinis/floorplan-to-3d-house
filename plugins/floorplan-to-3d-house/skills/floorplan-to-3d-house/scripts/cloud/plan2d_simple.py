"""Simplified 2D plan for approval (readable PNG + setback dimensions and north added to the DXF).
Uso: python3 plan2d_simple.py <layout.json> <site.json> <out.png> [planta.dxf a completar] [mask1.png com estrada no canal B]
Mostra: paredes, vãos (portas com arco, janelas, portões), divisões e áreas, escadas com sentido de subida,
plot boundary, ceded strip, road, dimensioned setbacks, levels, north, scale bar and area table.
Language: PROJECT_JSON=project.json ("lang": en | pt-PT)."""
import sys, json, math, os
from PIL import Image, ImageDraw, ImageFont

L = json.load(open(sys.argv[1])); site = json.load(open(sys.argv[2])); OUT = sys.argv[3]
DXF = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] not in ('', '-') else None
MASK = sys.argv[5] if len(sys.argv) > 5 else None
meta = dict(L.get('meta', {}))
if os.environ.get('PROJECT_JSON'):                      # project.json values win: north_deg, area_limit, setback_min, plan_title
    _p = json.load(open(os.environ['PROJECT_JSON'], encoding='utf-8'))
    for k in ('north_deg', 'area_limit', 'setback_min'):
        if _p.get(k) is not None: meta[k] = _p[k]
    if _p.get('plan_title'): meta['title'] = _p['plan_title']
_lang = (_p.get('lang') if os.environ.get('PROJECT_JSON') else None) or 'en'
TX = {'en': dict(up='up', down='down', road='ROAD', ceded='ceded strip', title='Simplified 2D plan — for approval before 3D', cols=('Volume', 'Level', 'Area (m²)'), total='Total', limit='limit',
                 legend=('exterior wall', 'interior wall', 'window / glazing', 'door (swing) / garage door (dashed)', 'plot boundary', 'setback to boundary', 'setback below minimum', '▽ floor level', 'ceded to public domain'),
                 plot='Plot', disclaimer='Indicative proposal — not for construction or permit', dec='.',
                 grid='Reference grid: {step} m squares — say a cell, e.g. "C4"'),
      'pt-PT': dict(up='sobe', down='desce', road='ESTRADA', ceded='cedência', title='Plano 2D simplificado — para aprovação antes do 3D', cols=('Volume', 'Nível', 'Área (m²)'), total='Total', limit='limite',
                 legend=('parede exterior', 'parede interior', 'janela / envidraçado', 'porta (arco) / portão (tracejado)', 'limite do terreno', 'afastamento ao limite', 'afastamento abaixo do mínimo', '▽ cota do pavimento', 'cedência ao domínio público'),
                 plot='Terreno', disclaimer='Proposta indicativa — sem valor de projeto', dec=',',
                 grid='Grelha de referência: quadrados de {step} m — indica uma célula, ex.: "C4"')}[_lang if _lang in ('en', 'pt-PT') else 'en']
north = meta.get('north_deg', site.get('meta', {}).get('north_deg', 0.0))
fmt = lambda v, n=2: f'{v:.{n}f}'.replace('.', TX['dec'])

# ---------- geometry helpers ----------
def wall_parts(w):
    (ax, az), (bx, bz) = w['a'], w['b']; t = w['t']
    Lw = math.hypot(bx - ax, bz - az); ux, uz = (bx - ax) / Lw, (bz - az) / Lw; nx, nz = -uz, ux
    cuts = sorted((o['o'], o['o'] + o['w'], o) for o in w.get('ops', []))
    spans, cur = [], 0.0
    for s, e, o in cuts:
        if s > cur: spans.append((cur, s))
        cur = max(cur, e)
    if cur < Lw: spans.append((cur, Lw))
    pt = lambda s, k: (ax + ux * s + nx * t / 2 * k, az + uz * s + nz * t / 2 * k)
    rect = lambda s, e: [pt(s, 1), pt(e, 1), pt(e, -1), pt(s, -1)]
    return [rect(s, e) for s, e in spans], [(s, e, o, (ax, az), (ux, uz), (nx, nz), t) for s, e, o in cuts]

def seg_dist(p, a, b):
    ax, az = a; bx, bz = b; px, pz = p
    dx, dz = bx - ax, bz - az; l2 = dx * dx + dz * dz
    u = ((px - ax) * dx + (pz - az) * dz) / l2
    return u, (ax + u * dx, az + u * dz)

def inside(x, z, poly):
    ins = False
    for i in range(len(poly)):
        (xi, zi), (xj, zj) = poly[i], poly[i - 1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi: ins = not ins
    return ins

def block_at(x, z):
    for b in L['blocks'].values():
        x0, z0, x1, z1 = b['rect']
        if x0 - 0.05 <= x <= x1 + 0.05 and z0 - 0.05 <= z <= z1 + 0.05: return b
    return None

# ---------- canvas ----------
plot = L['plot']
xs = [p[0] for p in plot]; zs = [p[1] for p in plot]
X0, X1, Z0, Z1 = min(xs) - 5, max(xs) + 5, min(zs) - 5, max(zs) + 5
S = 2400 / (X1 - X0)
TABLE_H = 330
W, H = int((X1 - X0) * S), int((Z1 - Z0) * S) + TABLE_H
im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
Q = lambda x, z: ((x - X0) * S, (z - Z0) * S)
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
f = lambda sz, b=False: ImageFont.truetype(FONTB if b else FONT, sz)
F_ROOM, F_AREA, F_SMALL, F_DIM, F_TITLE = f(19, True), f(17), f(15), f(17, True), f(26, True)

def dashed(pts, fill, width, dash=14, gap=9):
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]; Ls = math.hypot(x1 - x0, y1 - y0); k = 0.0
        while k < Ls:
            e = min(k + dash, Ls)
            d.line([(x0 + (x1 - x0) * k / Ls, y0 + (y1 - y0) * k / Ls), (x0 + (x1 - x0) * e / Ls, y0 + (y1 - y0) * e / Ls)], fill=fill, width=width)
            k = e + gap

def hatch(poly, fill, step=12):
    m = Image.new('L', im.size, 0); ImageDraw.Draw(m).polygon([Q(*p) for p in poly], fill=255)
    lines = Image.new('L', im.size, 0); dl = ImageDraw.Draw(lines)
    for k in range(-H, W, step): dl.line([(k, H), (k + H, 0)], fill=255, width=2)
    from PIL import ImageChops
    im.paste(fill, (0, 0), ImageChops.multiply(m, lines))

# road (from the site's material mask, blue channel) and ceded strip
if MASK and os.path.exists(MASK):
    G = site['ground']; mk = Image.open(MASK).convert('RGB').split()[2]
    sx = mk.width / (G['x1'] - G['x0'])
    crop = mk.crop((int((X0 - G['x0']) * sx), int((Z0 - G['z0']) * sx), int((X1 - G['x0']) * sx), int((Z1 - G['z0']) * sx)))
    crop = crop.resize((W, H - TABLE_H)).point(lambda v: 255 if v > 127 else 0)
    im.paste((222, 222, 222), (0, 0, W, H - TABLE_H), crop)
d.polygon([Q(*p) for p in plot], fill=(244, 248, 238))
if L.get('ceded'):
    d.polygon([Q(*p) for p in L['ceded']], fill=(236, 238, 246)); hatch(L['ceded'], (150, 160, 200))

# retaining walls / terraces (under the house)
for rw in L.get('retaining', []):
    x = rw['x']; zz = [z / 10 for z in range(int(Z0 * 10), int(Z1 * 10)) if inside(x, z / 10, plot)]
    if zz: d.rectangle([Q(x - .15, min(zz)), Q(x + .15, max(zz))], fill=(165, 140, 105))

# trees (thin, they matter for what gets moved)
for t in L.get('trees', []):
    d.ellipse([Q(t['x'] - t['r'], t['z'] - t['r']), Q(t['x'] + t['r'], t['z'] + t['r'])], outline=(120, 160, 100), width=2)

# blocks
for b in L['blocks'].values():
    x0, z0, x1, z1 = b['rect']
    open_ = any(k in b['name'].lower() for k in ('alpendre', 'terraço', 'telheiro'))
    d.rectangle([Q(x0, z0), Q(x1, z1)], fill=(246, 240, 226) if open_ else (255, 255, 255))
    if open_: dashed([Q(x0, z0), Q(x1, z0), Q(x1, z1), Q(x0, z1), Q(x0, z0)], (150, 130, 100), 2)

# walls + openings
doors = []
for w in L['walls']:
    if w.get('tag', '').startswith('C east above') or w.get('y0', 0) > L.get('meta', {}).get('storey_y', 0) + 1.5: continue
    solid, ops = wall_parts(w)
    col = (25, 25, 25) if w['t'] > 0.2 else (70, 70, 70)
    for r in solid: d.polygon([Q(*p) for p in r], fill=col)
    for s, e, o, A, U, N, t in ops:
        k = o['kind']; P_ = lambda u, v: Q(A[0] + U[0] * u + N[0] * v, A[1] + U[1] * u + N[1] * v)
        if k in ('window', 'slide', 'door_glass'):
            d.polygon([P_(s, t / 2), P_(e, t / 2), P_(e, -t / 2), P_(s, -t / 2)], fill=(255, 255, 255), outline=(30, 110, 190))
            d.line([P_(s, 0), P_(e, 0)], fill=(30, 110, 190), width=2)
        elif k == 'garage':
            dashed([P_(s, 0), P_(e, 0)], (150, 90, 30), 3, 10, 6)
        elif k in ('door', 'front'):
            doors.append((s, e, o, A, U, N, t))
# door leaves + swing arcs (side chosen towards the larger free side: the room side)
for s, e, o, A, U, N, t in doors:
    wdt = e - s
    for sg in (1, -1):
        mx, mz = A[0] + U[0] * (s + wdt / 2) + N[0] * sg * 0.6, A[1] + U[1] * (s + wdt / 2) + N[1] * sg * 0.6
        if block_at(mx, mz) and not any(k in (block_at(mx, mz)['name'].lower()) for k in ('alpendre',)): break
    hinge = (A[0] + U[0] * s + N[0] * sg * t / 2, A[1] + U[1] * s + N[1] * sg * t / 2)
    leaf = (hinge[0] + N[0] * sg * wdt, hinge[1] + N[1] * sg * wdt)
    d.line([Q(*hinge), Q(*leaf)], fill=(150, 90, 30), width=3)
    a0 = math.degrees(math.atan2(N[1] * sg, N[0] * sg)); a1 = math.degrees(math.atan2(U[1], U[0]))
    lo, hi = sorted((a0, a1))
    if hi - lo > 180: lo, hi = hi, lo + 360
    cx, cy = Q(*hinge); r = wdt * S
    d.arc([cx - r, cy - r, cx + r, cy + r], lo, hi, fill=(150, 90, 30), width=2)
for c in L.get('columns', []):
    s_ = c['s'] / 2; d.rectangle([Q(c['x'] - s_, c['z'] - s_), Q(c['x'] + s_, c['z'] + s_)], fill=(25, 25, 25))

# stairs with "sobe" arrow towards the higher block
for st in L.get('stairs', []):
    for i in range(st['n'] + 1):
        x = st['x0'] + (st['x1'] - st['x0']) * i / st['n']; d.line([Q(x, st['z0']), Q(x, st['z1'])], fill=(80, 80, 80), width=2)
    zm = (st['z0'] + st['z1']) / 2
    sgn = 1 if st['x1'] >= st['x0'] else -1                      # schema: the top of the run is at x0
    down = int(st.get('storey', 0)) != int(meta.get('storey', st.get('storey', 0)))   # upper plan of a two-storey house
    xa, xb = (st['x0'] + 0.15 * sgn, st['x1'] - 0.15 * sgn) if down else (st['x1'] - 0.15 * sgn, st['x0'] + 0.15 * sgn)
    d.line([Q(xa, zm), Q(xb, zm)], fill=(200, 0, 0), width=3)
    hx, hy = Q(xb, zm); dx = 1 if xb > xa else -1
    d.polygon([(hx, hy), (hx - dx * 14, hy - 8), (hx - dx * 14, hy + 8)], fill=(200, 0, 0))
    if down: d.text(Q(st['x0'] - 0.25 * sgn, zm), TX['down'], fill=(200, 0, 0), font=F_SMALL, anchor='rm' if sgn > 0 else 'lm')   # at the top step
    else: d.text(Q((xa + xb) / 2, max(st['z0'], st['z1']) + 0.3), TX['up'], fill=(200, 0, 0), font=F_SMALL, anchor='mm')
# railings / balustrades (two-storey: void edges, balconies)
for r in L.get('railings', []):
    d.line([Q(*r['a']), Q(*r['b'])], fill=(90, 90, 90), width=4); d.line([Q(*r['a']), Q(*r['b'])], fill=(235, 235, 235), width=1)

# plot outline
pp = [Q(*p) for p in plot + [plot[0]]]; dashed(pp, (210, 0, 0), 4, 22, 8)

# room labels: centroid, kept off the stairs, font shrunk / wrapped to fit the room width
stair_boxes = [(min(st['x0'], st['x1']), min(st['z0'], st['z1']), max(st['x0'], st['x1']), max(st['z0'], st['z1'])) for st in L.get('stairs', [])]
def fit(text, wpx, sizes=range(19, 11, -1)):
    for sz in sizes:
        if d.textlength(text, font=f(sz, True)) <= wpx: return [text], sz
    for sep in (' / ', ' '):
        if sep in text:
            i = text.index(sep) if sep == ' / ' else text.rfind(' ', 0, len(text) // 2 + 4)
            parts = [text[:i + (len(sep) if sep == ' / ' else 0)].strip(), text[i + len(sep):].strip()]
            for sz in list(sizes) + [11, 10]:
                if max(d.textlength(t, font=f(sz, True)) for t in parts) <= wpx: return parts, sz
    return [text], 10
for rm in L['rooms']:
    poly = rm['poly']; a = cx = cz = 0.0
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i - 1], poly[i]; c = x0 * z1 - x1 * z0; a += c; cx += (x0 + x1) * c; cz += (z0 + z1) * c
    if abs(a) < 1e-6: continue
    cx, cz = cx / (3 * a), cz / (3 * a)
    pxs = [q[0] for q in poly]; pzs = [q[1] for q in poly]
    if any(min(pxs) >= sx0 - 0.2 and max(pxs) <= sx1 + 0.2 and min(pzs) >= sz0 - 0.2 and max(pzs) <= sz1 + 0.2 for sx0, sz0, sx1, sz1 in stair_boxes):
        continue                                   # the room is just the stair: the treads + 'sobe' say it
    rx0, rx1 = min(p[0] for p in poly), max(p[0] for p in poly); boxed = False
    for sx0, sz0, sx1, sz1 in stair_boxes:
        if sx0 - 0.3 <= cx <= sx1 + 0.3 and sz0 - 0.3 <= cz <= sz1 + 0.3:
            left, right = sx0 - rx0, rx1 - sx1
            if max(left, right) > 2.0: rx0, rx1 = (rx0, sx0) if left >= right else (sx1, rx1); cx = (rx0 + rx1) / 2
            else: boxed = True; cz = sz0 + 0.75
    lines, sz = fit(rm['name'], (rx1 - rx0) * S - 10)
    x, y = Q(cx, cz); lh = sz + 3; y0 = y - lh * len(lines) / 2 - 2
    if boxed:
        wbox = max(d.textlength(t, font=f(sz, True)) for t in lines) / 2 + 8
        d.rounded_rectangle([x - wbox, y0 - 4, x + wbox, y0 + (len(lines) + 1) * lh + 4], 6, fill=(255, 255, 255), outline=(160, 160, 160))
    for k, t in enumerate(lines): d.text((x, y0 + k * lh), t, fill=(0, 0, 0), font=f(sz, True), anchor='mt')
    d.text((x, y0 + len(lines) * lh + 1), f"{fmt(rm['area'])} m²", fill=(60, 60, 60), font=f(min(17, sz), False), anchor='mt')

# levels per block
for b in L['blocks'].values():
    if 'level' not in b: continue
    x0, z0, x1, z1 = b['rect']
    if any(bx0 - 0.3 <= x0 and x1 <= bx1 + 0.3 for bx0, bz0, bx1, bz1 in stair_boxes) and any(bz0 - 0.5 <= z0 and z1 <= bz1 + 0.5 for bx0, bz0, bx1, bz1 in stair_boxes):
        continue                                       # the stair box: the 'sobe' arrow already says it
    x, y = Q(x0 + 0.25, z1 - 0.3)
    d.text((x, y), f"▽ {fmt(b['level'])}", fill=(190, 0, 120), font=F_SMALL, anchor='ls')

# setbacks: for each plot edge, nearest built corner, perpendicular dimension
corners = [(x, z) for b in L['blocks'].values() for x, z in ((b['rect'][0], b['rect'][1]), (b['rect'][2], b['rect'][1]), (b['rect'][2], b['rect'][3]), (b['rect'][0], b['rect'][3]))]
setbacks = []
for i in range(len(plot)):
    a, b = plot[i - 1], plot[i]
    if math.dist(a, b) < 3: continue
    best = None
    for c in corners:
        u, foot = seg_dist(c, a, b)
        if 0.05 < u < 0.95:
            dd = math.dist(c, foot)
            if best is None or dd < best[0]: best = (dd, c, foot)
    if best and best[0] < 25: setbacks.append(best)
MIN_SB = meta.get('setback_min', 3.0)
for dd, c, foot in setbacks:
    p0, p1 = Q(*c), Q(*foot); sbc = (0, 90, 170) if dd >= MIN_SB else (220, 60, 0)
    d.line([p0, p1], fill=sbc, width=2 if dd >= MIN_SB else 4)
    for p in (p0, p1): d.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=sbc)
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    tx = f'{fmt(dd)} m' + ('' if dd >= MIN_SB else ' < ' + fmt(MIN_SB, 0)); bb = d.textbbox((mx, my), tx, font=F_DIM, anchor='mm')
    d.rectangle([bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2], fill=(255, 255, 255)); d.text((mx, my), tx, fill=sbc, font=F_DIM, anchor='mm')

# road / ceded labels
if L.get('ceded'):
    cx = sum(p[0] for p in L['ceded']) / len(L['ceded']); cz = sum(p[1] for p in L['ceded']) / len(L['ceded'])
    d.text(Q(cx - 2.2, cz), TX['road'], fill=(110, 110, 110), font=F_ROOM, anchor='mm')
    d.text(Q(cx, cz + 3), TX['ceded'], fill=(110, 120, 170), font=F_SMALL, anchor='mm')

# north arrow + scale bar
nx_, ny_ = W - 90, 110; a = math.radians(north); vx, vy = math.sin(a), -math.cos(a)
tip = (nx_ + vx * 55, ny_ + vy * 55); tail = (nx_ - vx * 45, ny_ - vy * 45); px_, py_ = -vy, vx
d.polygon([tip, (tail[0] + px_ * 16, tail[1] + py_ * 16), (nx_, ny_), (tail[0] - px_ * 16, tail[1] - py_ * 16)], fill=(20, 20, 20))
d.text((tip[0] + vx * 22, tip[1] + vy * 22), 'N', fill=(20, 20, 20), font=F_TITLE, anchor='mm')
sx0, sy0 = 60, H - TABLE_H - 40
for k in range(4):
    d.rectangle([sx0 + k * 5 * S, sy0, sx0 + (k + 1) * 5 * S, sy0 + 12], fill=(20, 20, 20) if k % 2 == 0 else (255, 255, 255), outline=(20, 20, 20))
for k in range(5): d.text((sx0 + k * 5 * S, sy0 - 6), f'{k * 5}', fill=(20, 20, 20), font=F_SMALL, anchor='ms')
d.text((sx0 + 20 * S + 12, sy0 + 6), 'm', fill=(20, 20, 20), font=F_SMALL, anchor='lm')

# title + area table
y = H - TABLE_H + 18
d.line([(0, H - TABLE_H), (W, H - TABLE_H)], fill=(180, 180, 180), width=2)
d.text((40, y), meta.get('title', TX['title']) + (' — ' + meta['storey_label'] if meta.get('storey_label') else ''), fill=(0, 0, 0), font=F_TITLE)
y += 46
cols = (40, 560, 760)
for i, h in enumerate(TX['cols']): d.text((cols[i], y), h, fill=(90, 90, 90), font=F_ROOM)
y += 30
for b in L['blocks'].values():
    d.text((cols[0], y), b['name'], fill=(0, 0, 0), font=F_AREA)
    if 'level' in b: d.text((cols[1], y), fmt(b['level']), fill=(0, 0, 0), font=F_AREA)
    d.text((cols[2], y), fmt(b['area']), fill=(0, 0, 0), font=F_AREA); y += 24
tot = sum(b['area'] for b in L['blocks'].values())
d.line([(cols[0], y + 2), (cols[2] + 120, y + 2)], fill=(0, 0, 0), width=1); y += 8
d.text((cols[0], y), TX['total'], fill=(0, 0, 0), font=F_ROOM); d.text((cols[2], y), fmt(tot), fill=(0, 0, 0), font=F_ROOM)
if 'area_limit' in meta: d.text((cols[2] + 110, y), f"({TX['limit']} {fmt(meta['area_limit'], 0)})", fill=(120, 120, 120), font=F_AREA)
lx = 1150; ly = H - TABLE_H + 70
legend = list(zip([(25, 25, 25), (70, 70, 70), (30, 110, 190), (150, 90, 30), (210, 0, 0), (0, 90, 170), (220, 60, 0), (190, 0, 120), (150, 160, 200)], TX['legend']))
for i, (c, t) in enumerate(legend):
    yy = ly + i * 28; d.rectangle([lx, yy, lx + 26, yy + 16], fill=c); d.text((lx + 38, yy + 8), t, fill=(0, 0, 0), font=F_AREA, anchor='lm')
if meta.get('plot_area'):
    d.text((lx + 560, ly), f"{TX['plot']}: {fmt(meta['plot_area'], 0)} m²", fill=(0, 0, 0), font=F_AREA)
d.text((lx + 560, ly + 28), TX['disclaimer'], fill=(120, 120, 120), font=F_AREA)
# ---------- reference grid: letters = columns (west→east), numbers = rows (top→bottom of the sheet) ----------
# lets the user point at a place ("sofa in C4", "move the garage to F2-G3"); OUT.grid.json maps cells back to scene x/z
GRID = None
if os.environ.get('PLAN_GRID', '1') != '0':
    gx0, gz0, gx1, gz1 = min(xs), min(zs), max(xs), max(zs)
    step = float(os.environ.get('PLAN_GRID_STEP', '2') or 2)          # 2 m squares by default; PLAN_GRID_STEP=<m> to change
    ncol, nrow = math.ceil((gx1 - gx0) / step - 1e-6), math.ceil((gz1 - gz0) / step - 1e-6)
    col_name = lambda i: (col_name(i // 26 - 1) if i >= 26 else '') + chr(65 + i % 26)
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ov); gc = (40, 110, 200, 85)
    ex, ez = gx0 + ncol * step, gz0 + nrow * step
    for i in range(ncol + 1): do.line([Q(gx0 + i * step, gz0), Q(gx0 + i * step, ez)], fill=gc, width=1)
    for j in range(nrow + 1): do.line([Q(gx0, gz0 + j * step), Q(ex, gz0 + j * step)], fill=gc, width=1)
    im.paste(Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB').crop((0, 0, W, H - TABLE_H)), (0, 0))
    d = ImageDraw.Draw(im); F_GRID = f(max(13, min(20, int(step * S * 0.45))), True); lc = (30, 90, 170)
    for i in range(ncol):
        cx_, _ = Q(gx0 + (i + 0.5) * step, gz0)
        d.text((cx_, Q(0, gz0)[1] - 8), col_name(i), fill=lc, font=F_GRID, anchor='md', stroke_width=4, stroke_fill=(255, 255, 255))
        d.text((cx_, Q(0, ez)[1] + 8), col_name(i), fill=lc, font=F_GRID, anchor='mt', stroke_width=4, stroke_fill=(255, 255, 255))
    for j in range(nrow):
        _, cy_ = Q(gx0, gz0 + (j + 0.5) * step)
        d.text((Q(gx0, 0)[0] - 10, cy_), str(j + 1), fill=lc, font=F_GRID, anchor='rm', stroke_width=4, stroke_fill=(255, 255, 255))
        d.text((Q(ex, 0)[0] + 10, cy_), str(j + 1), fill=lc, font=F_GRID, anchor='lm', stroke_width=4, stroke_fill=(255, 255, 255))
    d.text((lx + 560, ly + 56), TX['grid'].format(step=fmt(step, 0 if step == int(step) else 1)), fill=lc, font=F_AREA)
    GRID = dict(x0=gx0, z0=gz0, step=step, cols=ncol, rows=nrow, col_labels=[col_name(i) for i in range(ncol)],
                note='cell <L><n>: x in [x0+i*step, x0+(i+1)*step], z in [z0+(n-1)*step, z0+n*step]; i = column index from 0; scene x east, z south')
    json.dump(GRID, open(os.path.splitext(OUT)[0] + '.grid.json', 'w'), indent=1)
im.save(OUT); print('png', im.size, 'setbacks', [round(s[0], 2) for s in setbacks], 'below_min', [round(s[0], 2) for s in setbacks if s[0] < MIN_SB])

# ---------- add setbacks + north to the plan DXF ----------
if DXF:
    sys.path.insert(0, os.environ.get('EZDXF_SRC', 'ezdxf-src/src')); import ezdxf
    doc = ezdxf.readfile(DXF); msp = doc.modelspace()
    if 'A-DIM-AFAST' not in doc.layers: doc.layers.add('A-DIM-AFAST').rgb = (0, 90, 170)
    for dd, c, foot in setbacks:
        msp.add_aligned_dim(p1=(c[0], -c[1]), p2=(foot[0], -foot[1]), distance=0.0, dxfattribs={'layer': 'A-DIM-AFAST'}).render()
    if 'A-NORTH' not in doc.layers: doc.layers.add('A-NORTH')
    cx, cy = max(xs) + 2, -min(zs) - 2
    msp.add_line((cx, cy), (cx + 3 * vx, cy - 3 * vy), dxfattribs={'layer': 'A-NORTH'})
    msp.add_text('N', height=0.8, dxfattribs={'layer': 'A-NORTH'}).set_placement((cx + 3.6 * vx, cy - 3.6 * vy))
    if GRID:
        if 'A-GRID' not in doc.layers: doc.layers.add('A-GRID').rgb = (120, 160, 220)
        g = GRID; st = g['step']; ex, ez = g['x0'] + g['cols'] * st, g['z0'] + g['rows'] * st; th = max(0.3, st * 0.25)
        for i in range(g['cols'] + 1): msp.add_line((g['x0'] + i * st, -g['z0']), (g['x0'] + i * st, -ez), dxfattribs={'layer': 'A-GRID'})
        for j in range(g['rows'] + 1): msp.add_line((g['x0'], -(g['z0'] + j * st)), (ex, -(g['z0'] + j * st)), dxfattribs={'layer': 'A-GRID'})
        for i, lab in enumerate(g['col_labels']):
            msp.add_text(lab, height=th, dxfattribs={'layer': 'A-GRID'}).set_placement((g['x0'] + (i + 0.5) * st, -g['z0'] + th), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
        for j in range(g['rows']):
            msp.add_text(str(j + 1), height=th, dxfattribs={'layer': 'A-GRID'}).set_placement((g['x0'] - th, -(g['z0'] + (j + 0.5) * st)), align=ezdxf.enums.TextEntityAlignment.MIDDLE_RIGHT)
    doc.saveas(DXF); print('dxf ok')
