"""2D plan (DXF + PNG preview) from layout.json."""
import sys, json, math
import os
sys.path.insert(0, os.environ.get('EZDXF_SRC', 'ezdxf-src/src'))
import ezdxf
from ezdxf.enums import TextEntityAlignment
from PIL import Image, ImageDraw, ImageFont
L = json.load(open('site3d/layout.json')); site = json.load(open('site3d/site.json'))
OUT_DXF, OUT_PNG = sys.argv[1], sys.argv[2]
P = lambda x, z: (x, -z)       # scene -> DXF plan (y north)

doc = ezdxf.new('R2010', setup=True); doc.units = ezdxf.units.M
msp = doc.modelspace()
def layer(n, rgb, lw=25):
    if n not in doc.layers: l = doc.layers.add(n); l.rgb = rgb; l.dxf.lineweight = lw
    return n
layer('A-WALL', (40, 40, 40), 50); layer('A-WALL-INT', (80, 80, 80), 25); layer('A-GLAZ', (0, 120, 200), 18)
layer('A-DOOR', (150, 90, 30), 18); layer('A-ROOF', (120, 120, 120), 13); layer('A-ROOM', (0, 0, 0), 13)
layer('L-PLOT', (220, 0, 0), 35); layer('L-CEDED', (110, 138, 221), 18); layer('L-RETAIN', (130, 110, 80), 35)
layer('L-ZONE', (90, 150, 60), 13); layer('L-TREE', (60, 120, 40), 13); layer('A-FURN', (170, 170, 170), 9); layer('A-LEVEL', (200, 0, 120), 13)

def wall_parts(w):
    (ax, az), (bx, bz) = w['a'], w['b']; t = w['t']
    L_ = math.hypot(bx - ax, bz - az); ux, uz = (bx - ax) / L_, (bz - az) / L_; nx, nz = -uz, ux
    cuts = sorted([(o['o'], o['o'] + o['w'], o) for o in w['ops'] if w['y0'] < 2.0 or True])
    spans, cur = [], 0.0
    for s, e, o in cuts:
        if s > cur: spans.append((cur, s))
        cur = max(cur, e)
    if cur < L_: spans.append((cur, L_))
    rect = lambda s, e: [(ax + ux * s + nx * t / 2, az + uz * s + nz * t / 2), (ax + ux * e + nx * t / 2, az + uz * e + nz * t / 2),
                         (ax + ux * e - nx * t / 2, az + uz * e - nz * t / 2), (ax + ux * s - nx * t / 2, az + uz * s - nz * t / 2)]
    return [rect(s, e) for s, e in spans], [(rect(s, e), o, (ux, uz), (nx, nz), (ax + ux * s, az + uz * s)) for s, e, o in cuts]

png_items = []
for w in L['walls']:
    if w.get('y0', 0) > 1.5 or w.get('tag', '').startswith('C east above'): continue   # walls standing on a lower roof
    solid, ops = wall_parts(w)
    lay = 'A-WALL' if w['t'] > 0.2 else 'A-WALL-INT'
    for r in solid:
        pl = msp.add_lwpolyline([P(*p) for p in r], close=True, dxfattribs={'layer': lay})
        h = msp.add_hatch(color=7 if lay == 'A-WALL' else 8, dxfattribs={'layer': lay}); h.paths.add_polyline_path([P(*p) for p in r], is_closed=True)
        png_items.append(('wall' if lay == 'A-WALL' else 'wallin', r))
    for r, o, u, n, start in ops:
        k = o['kind']
        if k in ('window', 'slide', 'door_glass', 'open'):
            if k == 'open': continue
            a, b, c, d = r
            m1 = ((a[0] + d[0]) / 2, (a[1] + d[1]) / 2); m2 = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
            msp.add_lwpolyline([P(*p) for p in r], close=True, dxfattribs={'layer': 'A-GLAZ'})
            msp.add_line(P(*m1), P(*m2), dxfattribs={'layer': 'A-GLAZ'})
            png_items.append(('glass', r))
        else:
            # door leaf + swing
            a, b, c, d = r
            hx, hz = a; wdt = o['w']
            leaf_end = (hx + n[0] * wdt, hz + n[1] * wdt)
            msp.add_line(P(*a), P(*leaf_end), dxfattribs={'layer': 'A-DOOR'})
            ang0 = math.degrees(math.atan2(-(b[1] - a[1]), b[0] - a[0])); ang1 = math.degrees(math.atan2(-(leaf_end[1] - a[1]), leaf_end[0] - a[0]))
            msp.add_arc(P(*a), wdt, min(ang0, ang1), max(ang0, ang1) if abs(ang1 - ang0) <= 180 else min(ang0, ang1) + 90, dxfattribs={'layer': 'A-DOOR'})
            png_items.append(('door', r))
for c in L['columns']:
    s = c['s'] / 2; r = [(c['x'] - s, c['z'] - s), (c['x'] + s, c['z'] - s), (c['x'] + s, c['z'] + s), (c['x'] - s, c['z'] + s)]
    msp.add_lwpolyline([P(*p) for p in r], close=True, dxfattribs={'layer': 'A-WALL'}); png_items.append(('wall', r))
for rf in L['roofs']:
    x0, z0, x1, z1 = rf['rect']
    msp.add_lwpolyline([P(x0, z0), P(x1, z0), P(x1, z1), P(x0, z1)], close=True, dxfattribs={'layer': 'A-ROOF', 'linetype': 'DASHED'})
for st in L['stairs']:
    for i in range(st['n'] + 1):
        x = st['x0'] + (st['x1'] - st['x0']) * i / st['n']
        msp.add_line(P(x, st['z0']), P(x, st['z1']), dxfattribs={'layer': 'A-WALL-INT'})
for f in L['furniture']:
    x0, z0, x1, z1 = f['b']
    msp.add_lwpolyline([P(x0, z0), P(x1, z0), P(x1, z1), P(x0, z1)], close=True, dxfattribs={'layer': 'A-FURN'})
for rm in L['rooms']:
    xs = [p[0] for p in rm['poly']]; zs = [p[1] for p in rm['poly']]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    t = msp.add_text(rm['name'], height=0.28, dxfattribs={'layer': 'A-ROOM'}); t.set_placement(P(cx, cz - 0.1), align=TextEntityAlignment.BOTTOM_CENTER)
    t = msp.add_text(f"{rm['area']:.2f} m²".replace('.', ','), height=0.22, dxfattribs={'layer': 'A-ROOM'}); t.set_placement(P(cx, cz + 0.15), align=TextEntityAlignment.TOP_CENTER)
    png_items.append(('label', (cx, cz, rm['name'], rm['area'])))
for b in L['blocks'].values():
    if 'level' not in b: continue
    x0, z0, x1, z1 = b['rect']
    t = msp.add_text('▽ %+.2f' % b['level'], height=0.3, dxfattribs={'layer': 'A-LEVEL'}); t.set_placement(P(x0 + 0.3, z1 - 0.4))
msp.add_lwpolyline([P(*p) for p in L['plot']], close=True, dxfattribs={'layer': 'L-PLOT', 'linetype': 'DASHED'})
msp.add_lwpolyline([P(*p) for p in L['ceded']], close=True, dxfattribs={'layer': 'L-CEDED'})
for z_, col in (('drive', 'L-ZONE'), ('stone', 'L-ZONE'), ('gravel', 'L-ZONE')):
    for poly in L['zones'][z_]:
        msp.add_lwpolyline([P(*p) for p in poly], close=True, dxfattribs={'layer': col})
for t_ in L['trees']:
    msp.add_circle(P(t_['x'], t_['z']), t_['r'], dxfattribs={'layer': 'L-TREE'})
# retaining walls clipped to plot (scan z for inside)
def inside(x, z, poly):
    ins = False
    for i in range(len(poly)):
        (xi, zi), (xj, zj) = poly[i], poly[i - 1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi: ins = not ins
    return ins
ret_segs = []
house_cut = {}
for cx, a, b in L.get('meta', {}).get('retaining_cuts', []): house_cut.setdefault(cx, []).append((a, b))
for rw in L['retaining']:
    x = rw['x']; zs = [z / 10 for z in range(-300, 200) if inside(x, z / 10, L['plot'])]
    if not zs: continue
    z0, z1 = min(zs), max(zs); segs = [(z0, z1)]
    for a, b in house_cut.get(x, []): segs = [s for seg in segs for s in ((seg[0], min(seg[1], a)), (max(seg[0], b), seg[1])) if s[1] - s[0] > 0.1]
    for a, b in segs:
        msp.add_lwpolyline([P(x - .15, a), P(x + .15, a), P(x + .15, b), P(x - .15, b)], close=True, dxfattribs={'layer': 'L-RETAIN'})
        ret_segs.append((x, a, b))
txt = 'Total %.2f m2 (' % sum(b['area'] for b in L['blocks'].values()) + ' · '.join('%s %.2f' % (b['name'], b['area']) for b in L['blocks'].values()) + ')'
t = msp.add_text(txt, height=0.45, dxfattribs={'layer': 'A-ROOM'})
t.set_placement(P(-14.0, 20.0))
doc.saveas(OUT_DXF)

# ---------- PNG preview ----------
X0, X1, Z0, Z1, S = -24, 33, -29, 20, 28
if len(sys.argv) > 3 and sys.argv[3] == 'ground':
    G = site['ground']; X0, X1, Z0, Z1 = G['x0'], G['x1'], G['z0'], G['z1']; S = 4096 / (X1 - X0)
im = Image.new('RGB', (int((X1 - X0) * S), int((Z1 - Z0) * S)), (250, 249, 245)); d = ImageDraw.Draw(im)
Q = lambda x, z: ((x - X0) * S, (z - Z0) * S)
col = {'drive': (205, 205, 200), 'stone': (226, 220, 205), 'gravel': (238, 236, 230), 'beds': (150, 140, 110)}
d.polygon([Q(*p) for p in L['plot']], fill=(214, 228, 196))
d.polygon([Q(*p) for p in L['ceded']], fill=(200, 200, 205))
for k in ('drive', 'stone', 'gravel', 'beds'):
    for poly in L['zones'][k]: d.polygon([Q(*p) for p in poly], fill=col[k])
for b in L['blocks'].values():
    x0, z0, x1, z1 = b['rect']; d.rectangle([Q(x0, z0), Q(x1, z1)], fill=(255, 255, 255) if b['name'] != 'Alpendre' else (232, 226, 210))
for f in L['furniture']:
    x0, z0, x1, z1 = f['b']; d.rectangle([Q(x0, z0), Q(x1, z1)], outline=(170, 170, 170))
for kind, r in png_items:
    if kind in ('wall', 'wallin'): d.polygon([Q(*p) for p in r], fill=(40, 40, 40) if kind == 'wall' else (90, 90, 90))
    elif kind == 'glass': d.polygon([Q(*p) for p in r], fill=(120, 180, 230))
    elif kind == 'door': d.polygon([Q(*p) for p in r], fill=(200, 150, 90))
for x, a, b in ret_segs: d.rectangle([Q(x - .15, a), Q(x + .15, b)], fill=(140, 110, 70))
for st in L['stairs']:
    for i in range(st['n'] + 1):
        x = st['x0'] + (st['x1'] - st['x0']) * i / st['n']
        d.line([Q(x, st['z0']), Q(x, st['z1'])], fill=(90, 90, 90), width=2)
    ym = (st['z0'] + st['z1']) / 2
    d.line([Q(st['x0'] + 0.2, ym), Q(st['x1'] - 0.2, ym)], fill=(200, 0, 0), width=2)
for rf in L['roofs']:
    x0, z0, x1, z1 = rf['rect']; d.rectangle([Q(x0, z0), Q(x1, z1)], outline=(150, 150, 150))
d.line([Q(*p) for p in L['plot'] + [L['plot'][0]]], fill=(220, 0, 0), width=3)
for t_ in L['trees']:
    d.ellipse([Q(t_['x'] - t_['r'], t_['z'] - t_['r']), Q(t_['x'] + t_['r'], t_['z'] + t_['r'])], outline=(60, 120, 40), width=2)
try: fnt = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', max(13, int(S * 0.3)))
except Exception: fnt = None
for kind, r in png_items:
    if kind == 'label':
        cx, cz, n, a = r; x, y = Q(cx, cz); d.text((x, y), f'{n}\n{a:.1f} m²', fill=(0, 0, 0), anchor='mm', font=fnt, align='center')
im = im.convert('RGB'); im.save(OUT_PNG, quality=85) if OUT_PNG.endswith('.jpg') else im.save(OUT_PNG); print('ok', im.size)
