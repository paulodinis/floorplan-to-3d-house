"""Two-storey example (same invented site as ../): ground floor living + upper floor with 3 bedrooms and a balcony.
Shows the v1.1 two-storey schema: "storey" on every element, a floor with "holes" (stair void), "railings", per-storey
blocks and rooms. Reads site3d/site.json, writes site3d/layout.json. Run it from a work dir set up like the example.
Scene coordinates: x east, z south, y up, y = 0 at the ground-floor finished level (32.00)."""
import json

site = json.load(open('site3d/site.json'))
FFL0, H0 = 32.00, 2.95            # ground floor level and floor-to-floor height
FFL1 = FFL0 + H0                  # 34.95
y0, y1 = 0.0, H0
CUT = -14.73

def clip(poly, c, keep_ge=True):
    out, n = [], len(poly)
    for i in range(n):
        P, Q = poly[i], poly[(i + 1) % n]
        inP = (P[0] >= c) if keep_ge else (P[0] < c); inQ = (Q[0] >= c) if keep_ge else (Q[0] < c)
        if inP: out.append(list(P))
        if inP != inQ:
            t = (c - P[0]) / (Q[0] - P[0]); out.append([c, P[1] + t * (Q[1] - P[1])])
    return out
def area(p): return 0.5 * abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p))))
plot, ceded = clip(site['boundary'], CUT, True), clip(site['boundary'], CUT, False)
R = lambda x0, z0, x1, z1: [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]

# ---------------- volumes (gross, one block per storey) ----------------
FP = [-9.8, -5.0, 1.3, 3.0]
blocks = {'G0': dict(name='Ground floor', rect=FP, level=FFL0, storey=0), 'G1': dict(name='First floor', rect=FP, level=FFL1, storey=1)}
for b in blocks.values():
    x0, z0, x1, z1 = b['rect']; b['area'] = round((x1 - x0) * (z1 - z0), 2)

# ---------------- walls ----------------
walls = []
def W(a, b, t, y, h, mat='render', ops=(), tag='', storey=0):
    walls.append(dict(a=a, b=b, t=t, y0=y, h=h, mat=mat, ops=list(ops), tag=tag, storey=storey))
def op(o, w, kind, sill=0.0, head=2.4): return dict(o=round(o, 3), w=round(w, 3), kind=kind, sill=sill, head=head)
T, ti, HI = 0.30, 0.12, 2.60
xw, xe, zn, zs = -9.65, 1.15, -4.85, 2.85
# ground floor exterior (up to the first-floor slab)
W([xw - .15, zs], [xe + .15, zs], T, y0, H0, ops=[op(0.8, 3.0, 'slide'), op(5.0, 3.0, 'slide'), op(8.6, 1.4, 'window', 1.05, 2.2)], tag='G south')
W([xw - .15, zn], [xe + .15, zn], T, y0, H0, ops=[op(1.0, 0.8, 'window', 1.5, 2.1), op(3.4, 0.6, 'window', 1.6, 2.1)], tag='G north')
W([xw, zn], [xw, zs], T, y0, H0, 'stone', ops=[op(1.6, 1.1, 'front', 0, 2.4), op(5.0, 1.6, 'window', 0.9, 2.3)], tag='G west (entrance)')
W([xe, zn], [xe, zs], T, y0, H0, ops=[op(5.2, 1.6, 'window', 1.05, 2.2)], tag='G east')
# ground floor interior
W([-6.85, -4.7], [-6.85, -1.6], ti, y0, HI, 'render_in', [op(2.0, 0.9, 'door', 0, 2.1)], tag='hall | WC + corridor')
W([-5.05, -4.7], [-5.05, -2.95], ti, y0, HI, 'render_in', tag='WC | stair')
W([-6.85, -2.95], [-5.05, -2.95], ti, y0, HI, 'render_in', [op(0.4, 0.7, 'door', 0, 2.1)], tag='WC south')
W([-5.05, -3.65], [-0.24, -3.65], ti, y0, HI, 'render_in', tag='stair | corridor')
W([xw, -1.55], [xe, -1.55], ti, y0, HI, 'render_in', [op(1.0, 0.9, 'door', 0, 2.1), op(5.0, 1.6, 'open', 0, 2.4)], tag='corridor | living')
# first floor exterior (to the eaves)
HU = 2.75
W([xw - .15, zs], [xe + .15, zs], T, y1, HU, ops=[op(1.0, 2.2, 'slide', 0, 2.3), op(5.6, 1.4, 'window', 0.9, 2.2), op(8.8, 1.4, 'window', 0.9, 2.2)], tag='F south', storey=1)
W([xw - .15, zn], [xe + .15, zn], T, y1, HU, ops=[op(1.0, 0.8, 'window', 1.5, 2.1), op(6.0, 1.6, 'window', 0.9, 2.2)], tag='F north', storey=1)
W([xw, zn], [xw, zs], T, y1, HU, ops=[op(5.2, 1.4, 'window', 0.9, 2.2)], tag='F west', storey=1)
W([xe, zn], [xe, zs], T, y1, HU, ops=[op(5.5, 1.0, 'window', 0.9, 2.2)], tag='F east', storey=1)
# first floor interior
W([-6.85, -4.7], [-6.85, -2.35], ti, y1, HI, 'render_in', [op(1.2, 0.8, 'door', 0, 2.1)], tag='bath | landing', storey=1)
W([xw, -2.35], [xe, -2.35], ti, y1, HI, 'render_in', [op(3.1, 0.8, 'door', 0, 2.1), op(5.5, 0.8, 'door', 0, 2.1), op(8.9, 0.8, 'door', 0, 2.1)], tag='landing | bedrooms', storey=1)
W([-5.24, -2.35], [-5.24, 2.7], ti, y1, HI, 'render_in', tag='bed 1 | bed 2', storey=1)
W([-1.94, -2.35], [-1.94, 2.7], ti, y1, HI, 'render_in', tag='bed 2 | bed 3', storey=1)
W([-1.24, -4.7], [-1.24, -3.62], ti, y1, HI, 'render_in', tag='linen | void', storey=1)
W([-1.24, -3.62], [xe, -3.62], ti, y1, HI, 'render_in', [op(0.5, 0.8, 'door', 0, 2.1)], tag='linen south', storey=1)

# ---------------- stair, void, railings, balcony ----------------
stairs = [dict(x0=-5.0, x1=-0.24, z0=-4.7, z1=-3.7, ytop=y1, ybot=y0, n=17, storey=0)]   # 17 x 17.4 cm, going 28 cm
VOID = R(-5.0, -4.7, -1.3, -3.65)
railings = [dict(a=[-5.0, -3.65], b=[-1.3, -3.65], y=y1, h=1.0, storey=1),                  # void, landing side
            dict(a=[-9.8, 3.0], b=[-9.8, 4.4], y=y1, h=1.0, storey=1), dict(a=[-9.8, 4.4], b=[-5.3, 4.4], y=y1, h=1.0, storey=1),
            dict(a=[-5.3, 4.4], b=[-5.3, 3.0], y=y1, h=1.0, storey=1)]                     # balcony
columns = [dict(x=x, z=4.25, y0=y0, h=y1 - 0.35, s=0.25) for x in (-9.65, -5.45)]

floors = [
    dict(poly=R(*FP), y=y0, mat='oak', name='ground floor'),
    dict(poly=R(-9.65, -4.85, -6.85, -1.55), y=y0 + 0.004, mat='stone_floor', name='hall'),
    dict(poly=R(-6.85, -4.7, -5.05, -2.95), y=y0 + 0.004, mat='porcelain', name='WC'),
    dict(poly=R(xw, zn, xe, zs), y=y1, mat='oak', name='first floor', holes=[VOID], storey=1),   # to the wall centrelines: no z-fighting with the façade
    dict(poly=R(-9.65, -4.85, -6.85, -2.35), y=y1 + 0.004, mat='porcelain', name='bathroom', storey=1),
    dict(poly=R(-9.8, 3.0, -5.3, 4.4), y=y1 - 0.03, mat='terrace', name='balcony', storey=1),
    dict(poly=R(-9.8, 3.0, 1.3, 6.0), y=y0 - 0.03, mat='terrace', name='south terrace'),
]

# ---------------- roofs ----------------
OV = 0.6
roofs = [dict(rect=[FP[0] - OV, FP[1] - OV, FP[2] + OV, FP[3] + OV], eave=y1 + HU, name='house', storey=1)]
PITCH = 22

# ---------------- rooms ----------------
def room(n, p, lv, s=0): return dict(name=n, poly=p, level=lv, area=round(area(p), 2), storey=s)
rooms = [
    room('Entrance hall', R(-9.5, -4.7, -6.91, -1.61), FFL0), room('WC', R(-6.79, -4.7, -5.11, -3.01), FFL0),
    room('Stair', R(-5.0, -4.7, -0.24, -3.71), FFL0),
    room('Corridor', [[-6.79, -2.89], [-5.0, -2.89], [-5.0, -3.59], [-0.24, -3.59], [-0.24, -4.7], [1.0, -4.7], [1.0, -1.61], [-6.79, -1.61]], FFL0),
    room('Living / dining / kitchen', R(-9.5, -1.49, 1.0, 2.7), FFL0),
    room('Bathroom', R(-9.5, -4.7, -6.91, -2.41), FFL1, 1),
    room('Landing', [[-6.79, -4.7], [-5.0, -4.7], [-5.0, -3.56], [1.0, -3.56], [1.0, -2.41], [-6.79, -2.41]], FFL1, 1),
    room('Linen closet', R(-1.18, -4.7, 1.0, -3.68), FFL1, 1),
    room('Bedroom 1', R(-9.5, -2.29, -5.3, 2.7), FFL1, 1), room('Bedroom 2', R(-5.18, -2.29, -2.0, 2.7), FFL1, 1),
    room('Bedroom 3', R(-1.88, -2.29, 1.0, 2.7), FFL1, 1), room('Balcony', R(-9.8, 3.0, -5.3, 4.4), FFL1, 1),
]

# ---------------- site works (same invented site as the single-storey example) ----------------
grading = dict(upper=31.80, lower=30.65, t1=29.55, t2=28.45, x_w1=3.4, x_w2=15.0, x_w3=22.5, upper_slope_from_z=6.5, upper_slope=0.08)
retaining = [dict(x=3.4, name='W1'), dict(x=15.0, name='W2'), dict(x=22.5, name='W3')]
garden_steps = [dict(x=3.4, z0=8.6, z1=10.2), dict(x=15.0, z0=3.0, z1=4.6), dict(x=22.5, z0=3.0, z1=4.6)]
gate, ped_gate = dict(z0=-15.1, z1=-10.9), dict(z0=-3.8, z1=-2.2)
zones = {'drive': [R(CUT, -15.1, -6.0, -10.9)],
         'stone': [R(CUT, -3.8, -9.8, -2.2), R(-9.8, 3.0, 1.3, 6.0), R(-12.4, -10.9, -11.2, -2.4)],
         'gravel': [R(-11.0, -9.2, 3.4, -5.0), R(-12.2, -2.4, -9.8, 3.0)],
         'beds': [R(-14.5, -10.6, -12.6, -3.9), R(-10.6, -8.8, -7.2, -6.0)]}
trees = [(-14.0, -16.4, 2.4), (25.0, -17.0, 2.2), (13.0, 15.2, 1.9), (-6.0, -7.6, 1.4), (-12.5, 9.0, 2.0), (-5.5, 10.0, 2.2),
         (8.5, 12.0, 2.3), (12.0, -10.0, 2.0), (19.0, -12.0, 2.4), (18.5, 10.5, 2.3), (26.5, -6.0, 2.4), (6.0, -16.5, 2.0)]

furniture = []
def F(x0, z0, x1, z1, y, h, mat, name='', s=0): furniture.append(dict(b=[x0, z0, x1, z1], y0=y, h=h, mat=mat, name=name, storey=s))
F(-2.4, -1.4, 0.9, -0.8, y0, 0.9, 'kitchen', 'kitchen counter'); F(-0.2, -1.4, 0.9, -0.8, y0, 2.3, 'kitchen', 'tall units')
F(-2.2, 0.2, -0.2, 1.2, y0, 0.75, 'wood', 'dining table'); F(-8.9, -0.6, -6.2, 0.2, y0, 0.8, 'fabric', 'sofa')
F(-8.4, 0.6, -7.2, 1.4, y0, 0.4, 'wood', 'coffee table'); F(-9.0, 0.4, -6.4, 2.2, y0, 0.01, 'rug', 'rug')
F(-8.9, -1.2, -7.8, -0.75, y1, 0.48, 'wood', 'bedside', 1)
F(-8.6, -2.2, -6.8, -0.1, y1, 0.48, 'fabric', 'bed 1', 1); F(-4.3, -1.4, -2.7, 0.6, y1, 0.48, 'fabric', 'bed 2', 1)
F(-1.4, -1.4, 0.0, 0.6, y1, 0.48, 'fabric', 'bed 3', 1); F(-5.15, 0.6, -4.55, 2.6, y1, 2.2, 'wardrobe', 'wardrobe', 1)
F(-9.4, -4.6, -8.0, -4.1, y1, 0.85, 'white', 'vanity', 1); F(-9.6, 3.2, -8.9, 4.2, y1, 0.35, 'white', 'lounger', 1)
room_lights = [[-8.2, -3.0, 2.3], [-6.0, -3.8, 2.3], [-3.0, -2.3, 2.3], [-5.0, 0.6, 2.3], [-1.0, 0.6, 2.3],
               [-8.2, -3.5, y1 + 2.3], [-3.5, -3.0, y1 + 2.3], [-7.4, 0.2, y1 + 2.3], [-3.6, 0.2, y1 + 2.3], [-0.4, 0.2, y1 + 2.3]]

layout = dict(
    meta=dict(ffl_ground=FFL0, ffl_first=FFL1, area_total=round(sum(b['area'] for b in blocks.values()), 2), plot_area=round(area(plot), 1),
              ceded_area=round(area(ceded), 1), cut_x=CUT, pitch=PITCH, north_deg=8.0, area_limit=285, setback_min=3.0, retaining_cuts=[],
              title='Simplified 2D plan — for approval before 3D'),
    plot=plot, ceded=ceded, blocks=blocks, walls=walls, columns=columns, roofs=roofs, floors=floors, stairs=stairs, railings=railings,
    rooms=rooms, grading=grading, retaining=retaining, garden_steps=garden_steps, gate=gate, ped_gate=ped_gate,
    zones=zones, trees=[dict(x=x, z=z, r=r) for x, z, r in trees], furniture=furniture, slats=[], room_lights=room_lights)
json.dump(layout, open('site3d/layout.json', 'w'), indent=0)
print('total', layout['meta']['area_total'], 'plot', layout['meta']['plot_area'])
for r in rooms: print(f"  [{r['storey']}] {r['name']:<26} {r['area']:6.2f} m2")
