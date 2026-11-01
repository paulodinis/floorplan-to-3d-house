"""Sun & daylight report: direct-sun hours per room (through its exterior glazing) and ground sun-hour maps.

Usage (from the project work dir):
    PROJECT_JSON=project.json python3 sun_report.py export/sun [--step 10] [--grid 1.0]
Writes sun_report.md, sun_ground.png (3 panels: March equinox, June and December solstices) and sun_rooms.json.

Model (state it to the user, it is indicative):
- Sun position from latitude (project.json location.lat) in local SOLAR time, clear sky, no refraction.
- True north = north_deg clockwise from sheet-up.
- Obstacles: every wall (openings ignored = conservative), columns, slats (as solid), roofs as 0.25 m slabs under the
  hip surfaces, the designed ground (grading) and tree crowns as solid ellipsoids. Neighbouring buildings are NOT
  modelled unless added as walls/blocks.
- A room "has sun" at an instant when at least half of the sample points of one of its exterior windows see the sun.
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'export/sun'
arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
STEP_MIN, GRID = arg('--step', 10.0), arg('--grid', 1.0)
os.makedirs(OUT, exist_ok=True)
L = json.load(open('site3d/layout.json', encoding='utf-8'))
site = json.load(open('site3d/site.json', encoding='utf-8'))
P = json.load(open(os.environ['PROJECT_JSON'], encoding='utf-8')) if os.environ.get('PROJECT_JSON') else {}
lang = P.get('lang', 'en')
LAT = P.get('location', {}).get('lat', 40.0)
NORTH = P.get('north_deg', L.get('meta', {}).get('north_deg', site['meta'].get('north_deg', 0.0)))
FFL = site['meta']['ffl']
PITCH = math.radians(L.get('meta', {}).get('pitch', 16))
GR, SPOTS = L.get('grading', {}), site.get('spots', [])
TX = {'en': dict(title='Sun & daylight — indicative', dates=('March equinox (21 Mar)', 'June solstice (21 Jun)', 'December solstice (21 Dec)'),
                 short=('21 Mar', '21 Jun', '21 Dec'), room='Room', facing='Glazing faces', h='h of direct sun', first='Sun from–to (21 Dec)',
                 none='no exterior glazing', never='no direct sun', hours='hours of direct sun on the ground', house='house',
                 intro='Hours of direct sun through each room\'s exterior windows (solar time, clear sky). Latitude {lat:.1f}°, true north {n:.0f}° clockwise from sheet-up.',
                 model='Model: walls (openings ignored), roofs, columns, slats, designed ground and tree crowns block the sun; neighbours are not modelled. Indicative only — not an energy or daylight-factor calculation.',
                 tips='Points to discuss', low='{r}: under 2 h of direct sun on 21 Dec', high='{r}: over 7 h of direct sun on 21 Jun through {f} glazing — check shading/overheating',
                 cards=('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')),
      'pt-PT': dict(title='Sol e luz natural — indicativo', dates=('Equinócio de março (21 mar)', 'Solstício de junho (21 jun)', 'Solstício de dezembro (21 dez)'),
                    short=('21 mar', '21 jun', '21 dez'), room='Divisão', facing='Envidraçados virados a', h='h de sol direto', first='Sol das–às (21 dez)',
                    none='sem envidraçados exteriores', never='sem sol direto', hours='horas de sol direto no terreno', house='casa',
                    intro='Horas de sol direto pelas janelas exteriores de cada divisão (hora solar, céu limpo). Latitude {lat:.1f}°, norte verdadeiro a {n:.0f}° no sentido horário a partir do topo da folha.',
                    model='Modelo: paredes (vãos ignorados), coberturas, pilares, ripados, terreno modelado e copas das árvores bloqueiam o sol; vizinhos não modelados. Apenas indicativo — não é um cálculo energético nem de fator de luz do dia.',
                    tips='Pontos a discutir', low='{r}: menos de 2 h de sol direto a 21 dez', high='{r}: mais de 7 h de sol direto a 21 jun pelos envidraçados a {f} — verificar sombreamento/sobreaquecimento',
                    cards=('N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'))}
TX = TX.get(lang, TX['en'])
fmt = lambda v, d=1: f'{v:.{d}f}'.replace('.', ',' if lang == 'pt-PT' else '.')
GLAZED = {'window', 'slide', 'door_glass'}
OUTDOOR = ('terrace', 'porch', 'alpendre', 'varanda', 'terraço', 'patio', 'pátio', 'deck', 'balcony')

# ---------------- sun ----------------
def sun_dir(doy, solar_h):
    """Unit vector towards the sun in scene axes (x, y, z) or None below 1° altitude."""
    dec = math.radians(23.44) * math.sin(2 * math.pi * (284 + doy) / 365)
    H, phi = math.radians(15 * (solar_h - 12)), math.radians(LAT)
    alt = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H))
    if alt < math.radians(1): return None
    az_s = math.atan2(math.sin(H), math.cos(H) * math.sin(phi) - math.tan(dec) * math.cos(phi))   # from south, west +
    sheet = math.radians(math.degrees(az_s) + 180 + NORTH)                                        # bearing on the sheet
    c = math.cos(alt)
    return np.array([c * math.sin(sheet), math.sin(alt), -c * math.cos(sheet)])


def card(dx, dz):
    true = (math.degrees(math.atan2(dx, -dz)) - NORTH) % 360
    return TX['cards'][int((true + 22.5) // 45) % 8]


# ---------------- obstacles ----------------
B = []   # boxes x0 x1 y0 y1 z0 z1
for w in L['walls']:
    (ax, az), (bx, bz) = w['a'], w['b']; t = w['t']
    if abs(az - bz) < 1e-6: B.append((min(ax, bx), max(ax, bx), w['y0'], w['y0'] + w['h'], az - t / 2, az + t / 2))
    else: B.append((ax - t / 2, ax + t / 2, w['y0'], w['y0'] + w['h'], min(az, bz), max(az, bz)))
for c in L.get('columns', []):
    s = c['s'] / 2; B.append((c['x'] - s, c['x'] + s, c['y0'], c['y0'] + c['h'], c['z'] - s, c['z'] + s))
for s in L.get('slats', []):
    B.append((s['x0'], s['x1'], s['y0'], s['y1'], s['z0'], s['z1']))
B = np.array(B, dtype=float).reshape(-1, 6)
R = np.array([(*rf['rect'], rf['eave']) for rf in L.get('roofs', [])], dtype=float).reshape(-1, 5)


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
    if x < GR['x_w1']: return GR['upper'] - max(0, z - GR.get('upper_slope_from_z', 1e9)) * GR.get('upper_slope', 0)
    if x < GR['x_w2']: return GR['lower']
    if x < GR['x_w3']: return GR['t1']
    return GR['t2']


px = [p[0] for p in L['plot']]; pz = [p[1] for p in L['plot']]
GX0, GX1, GZ0, GZ1 = min(px) - 40, max(px) + 40, min(pz) - 40, max(pz) + 40
GS = 1.0
gxs, gzs = np.arange(GX0, GX1 + GS, GS), np.arange(GZ0, GZ1 + GS, GS)
GH = np.array([[designed(x, z) - FFL for x in gxs] for z in gzs])            # ground y (scene) on a 1 m lattice
# the ground under the buildings is the slab: carve it down so it never blocks rays leaving the façades
for b in L['blocks'].values():
    x0, z0, x1, z1 = b['rect']; lv = b.get('level', FFL) - FFL
    ix = (gxs >= x0 - 0.5) & (gxs <= x1 + 0.5); iz = (gzs >= z0 - 0.5) & (gzs <= z1 + 0.5)
    GH[np.ix_(iz, ix)] = np.minimum(GH[np.ix_(iz, ix)], lv - 0.05)
T = []
for t in L.get('trees', []):
    H = 2.2 + t['r'] * 0.9; T.append((t['x'], designed(t['x'], t['z']) - FFL + H, t['z'], t['r']))
T = np.array(T, dtype=float).reshape(-1, 4)
YMAX = max([b[3] for b in B] + [r[4] + math.tan(PITCH) * min(r[2] - r[0], r[3] - r[1]) / 2 for r in R] + [t[1] + t[3] for t in T] + [float(GH.max())]) + 0.2


def blocked(O, d, maxdist=60.0, step=0.3):
    """O: (N,3) ray origins, d: sun direction. Returns bool (N,) True where something blocks the sun."""
    N = len(O); hit = np.zeros(N, bool); alive = np.ones(N, bool)
    for s in np.arange(step, maxdist, step):
        idx = np.nonzero(alive)[0]
        if not len(idx): break
        p = O[idx] + s * d; x, y, z = p[:, 0], p[:, 1], p[:, 2]
        h = np.zeros(len(idx), bool)
        if len(B):
            h |= ((x[:, None] >= B[:, 0]) & (x[:, None] <= B[:, 1]) & (y[:, None] >= B[:, 2]) & (y[:, None] <= B[:, 3])
                  & (z[:, None] >= B[:, 4]) & (z[:, None] <= B[:, 5])).any(1)
        if len(R):
            inr = (x[:, None] >= R[:, 0]) & (x[:, None] <= R[:, 2]) & (z[:, None] >= R[:, 1]) & (z[:, None] <= R[:, 3])
            dist = np.minimum.reduce([x[:, None] - R[:, 0], R[:, 2] - x[:, None], z[:, None] - R[:, 1], R[:, 3] - z[:, None]])
            top = R[:, 4] + math.tan(PITCH) * dist
            h |= (inr & (y[:, None] <= top) & (y[:, None] >= R[:, 4] - 0.25)).any(1)
        if len(T):
            e = ((x[:, None] - T[:, 0]) ** 2 + (z[:, None] - T[:, 2]) ** 2) / T[:, 3] ** 2 + (y[:, None] - T[:, 1]) ** 2 / (0.75 * T[:, 3]) ** 2
            h |= (e <= 1).any(1)
        ix = np.clip(((x - GX0) / GS).round().astype(int), 0, len(gxs) - 1); iz = np.clip(((z - GZ0) / GS).round().astype(int), 0, len(gzs) - 1)
        h |= y < GH[iz, ix]
        hit[idx[h]] = True
        alive[idx[h | (y > YMAX)]] = False
    return hit


# ---------------- windows → rooms ----------------
def room_at(x, z, y):
    best = None
    for r in L.get('rooms', []):
        if inside(x, z, r['poly']):
            dy = abs(r.get('level', FFL) - FFL - y)
            if best is None or dy < best[0]: best = (dy, r)
    return best[1] if best and best[0] < 2.0 else None


def is_out(r):
    return r is None or any(k in r['name'].lower() for k in OUTDOOR)


WIN = []   # dict(room, pts (k,3), normal, face)
for w in L['walls']:
    (ax, az), (bx, bz) = w['a'], w['b']; L_ = math.dist(w['a'], w['b'])
    if L_ < 1e-6: continue
    ux, uz = (bx - ax) / L_, (bz - az) / L_; nx, nz = -uz, ux
    for o in w.get('ops', []):
        if o['kind'] not in GLAZED: continue
        cx, cz = ax + ux * (o['o'] + o['w'] / 2), az + uz * (o['o'] + o['w'] / 2)
        sill = w['y0'] + o.get('sill', 0.0 if o['kind'] != 'window' else 0.9); head = w['y0'] + o.get('head', 2.1)
        ra, rb = room_at(cx + nx * 0.6, cz + nz * 0.6, w['y0']), room_at(cx - nx * 0.6, cz - nz * 0.6, w['y0'])
        if is_out(ra) == is_out(rb): continue                         # interior glazing, or both sides outdoors
        room, sgn = (rb, 1) if is_out(ra) else (ra, -1)
        n = (nx * sgn, nz * sgn); off = w['t'] / 2 + 0.06
        pts = [(cx + ux * f * o['w'] + n[0] * off, sill + (head - sill) * g, cz + uz * f * o['w'] + n[1] * off)
               for f in (-0.35, 0, 0.35) for g in (0.25, 0.75)]
        WIN.append(dict(room=room['name'], pts=np.array(pts), n=np.array([n[0], 0, n[1]]), face=card(*n), w=o['w']))

DATES = ((80, TX['dates'][0]), (172, TX['dates'][1]), (355, TX['dates'][2]))
times = np.arange(4.0, 20.0 + 1e-9, STEP_MIN / 60)
rooms = {r['name']: dict(hours=[0.0, 0.0, 0.0], first=None, last=None, faces=set()) for r in L.get('rooms', []) if not is_out(r)}
for wn in WIN: rooms[wn['room']]['faces'].add(wn['face'])
allpts = np.concatenate([wn['pts'] for wn in WIN]) if WIN else np.zeros((0, 3))
own = np.repeat(np.arange(len(WIN)), 6)

# ground grid over the plot
xs = np.arange(min(px), max(px) + 1e-9, GRID); zs = np.arange(min(pz), max(pz) + 1e-9, GRID)
GP = [(x, z) for z in zs for x in xs if inside(x, z, L['plot'])]
gy = []
for x, z in GP:
    ix = int(round((x - GX0) / GS)); iz = int(round((z - GZ0) / GS)); gy.append(GH[iz, ix] + 0.05)
GPA = np.array([(x, y, z) for (x, z), y in zip(GP, gy)]) if GP else np.zeros((0, 3))
under = np.array([any(b['rect'][0] <= x <= b['rect'][2] and b['rect'][1] <= z <= b['rect'][3] for b in L['blocks'].values()) for x, z in GP], bool)
ground = np.zeros((3, len(GPA)))

for di, (doy, _) in enumerate(DATES):
    for t in times:
        d = sun_dir(doy, t)
        if d is None: continue
        dt = STEP_MIN / 60
        if len(allpts):
            facing = np.array([float(np.dot(wn['n'], d)) > 0.02 for wn in WIN])
            sel = facing[own]
            lit = np.zeros(len(allpts), bool)
            if sel.any(): lit[sel] = ~blocked(allpts[sel], d)
            frac = np.bincount(own, weights=lit, minlength=len(WIN)) / 6
            got = set()
            for k, wn in enumerate(WIN):
                if frac[k] >= 0.5: got.add(wn['room'])
            for r in got:
                rooms[r]['hours'][di] += dt
                if di == 2:
                    rooms[r]['first'] = t if rooms[r]['first'] is None else rooms[r]['first']; rooms[r]['last'] = t
        if len(GPA):
            m = ~under
            g = np.zeros(len(GPA), bool); g[m] = ~blocked(GPA[m], d, maxdist=50, step=0.4)
            ground[di] += g * dt
    print('done', DATES[di][1], flush=True)

# ---------------- outputs ----------------
hm = lambda h: f'{int(h):02d}:{int(round((h % 1) * 60)) % 60:02d}'
lines = [f'# {TX["title"]} — {P.get("name", "")}', '', TX['intro'].format(lat=LAT, n=NORTH), '', TX['model'], '',
         f'| {TX["room"]} | {TX["facing"]} | {TX["short"][0]} | {TX["short"][1]} | {TX["short"][2]} | {TX["first"]} |', '|---|---|---|---|---|---|']
tips = []
for name, r in rooms.items():
    if not r['faces']:
        lines.append(f'| {name} | {TX["none"]} | – | – | – | – |'); continue
    fr = f'{hm(r["first"])}–{hm(r["last"] + STEP_MIN / 60)}' if r['first'] is not None else TX['never']
    faces = ', '.join(sorted(r['faces'], key=TX['cards'].index))
    lines.append(f'| {name} | {faces} | {fmt(r["hours"][0])} h | {fmt(r["hours"][1])} h | {fmt(r["hours"][2])} h | {fr} |')
    win_i, sum_i = (2, 1) if LAT >= 0 else (1, 2)                 # winter / summer solstice for this hemisphere
    if r['hours'][win_i] < 2: tips.append(TX['low'].replace('21 Dec', TX['short'][win_i]).replace('21 dez', TX['short'][win_i]).format(r=name))
    if r['hours'][sum_i] > 7 and r['faces'] & set(TX['cards'][5:8]):
        tips.append(TX['high'].replace('21 Jun', TX['short'][sum_i]).replace('21 jun', TX['short'][sum_i]).format(r=name, f=faces))
if tips: lines += ['', f'## {TX["tips"]}'] + [f'- {t}' for t in tips]
lines += ['', '![](sun_ground.png)', '']
open(os.path.join(OUT, 'sun_report.md'), 'w', encoding='utf-8').write('\n'.join(lines))
json.dump({k: dict(hours=v['hours'], faces=sorted(v['faces']), dec_first=v['first'], dec_last=v['last']) for k, v in rooms.items()},
          open(os.path.join(OUT, 'sun_rooms.json'), 'w'), indent=1)

# ground maps: 3 panels
PXM = 6; W = int((max(px) - min(px)) * PXM) + 40; H = int((max(pz) - min(pz)) * PXM) + 70
try:
    F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15); FS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
except OSError:
    F = FS = ImageFont.load_default()
sheet = Image.new('RGB', (W * 3, H + 40), 'white'); dr = ImageDraw.Draw(sheet)
vmax = max(1.0, float(ground.max()))


def ramp(v):   # dark blue (0 h) → yellow (max)
    t = max(0.0, min(1.0, v / vmax)); stops = [(0, (40, 52, 110)), (0.35, (70, 120, 170)), (0.7, (230, 190, 90)), (1, (255, 236, 150))]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b: f = (t - a) / (b - a); return tuple(int(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))
    return stops[-1][1]


for di in range(3):
    ox = di * W + 20; oy = 40
    tx = lambda x: ox + (x - min(px)) * PXM; tz = lambda z: oy + (z - min(pz)) * PXM
    for k, (x, z) in enumerate(GP):
        c = (210, 210, 210) if under[k] else ramp(ground[di, k])
        dr.rectangle([tx(x - GRID / 2), tz(z - GRID / 2), tx(x + GRID / 2), tz(z + GRID / 2)], fill=c)
    dr.polygon([(tx(x), tz(z)) for x, z in L['plot']], outline=(30, 30, 30))
    for b in L['blocks'].values():
        x0, z0, x1, z1 = b['rect']; dr.rectangle([tx(x0), tz(z0), tx(x1), tz(z1)], outline=(20, 20, 20), width=2)
    for t in L.get('trees', []):
        dr.ellipse([tx(t['x'] - t['r']), tz(t['z'] - t['r']), tx(t['x'] + t['r']), tz(t['z'] + t['r'])], outline=(40, 110, 50), width=2)
    dr.text((ox, 10), DATES[di][1], fill='black', font=F)
    a = math.radians(NORTH); cx, cy = ox + W - 70, oy + 25
    dr.line([cx, cy, cx + 18 * math.sin(a), cy - 18 * math.cos(a)], fill='black', width=2); dr.text((cx + 22 * math.sin(a) - 4, cy - 30 * math.cos(a) - 7), 'N', fill='black', font=FS)
for i in range(200):
    dr.line([20 + i, H + 18, 20 + i, H + 30], fill=ramp(vmax * i / 199))
dr.text((230, H + 15), f'0 – {fmt(vmax)} {TX["hours"]}  ·  {TX["house"]} = grey  ·  lat {fmt(LAT)}°', fill='black', font=FS)
sheet.save(os.path.join(OUT, 'sun_ground.png'))
print('\n'.join(lines))
