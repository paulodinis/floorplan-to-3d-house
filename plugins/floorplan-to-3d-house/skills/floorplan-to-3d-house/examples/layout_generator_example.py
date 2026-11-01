"""Example layout generator (reference project): authoring layout.json in plain Python.
Copy it, keep the helpers (W/op/R/F), and replace the volumes, walls, rooms and site works with your design.
Reads site3d/site.json, writes site3d/layout.json.
Scene coordinates in metres: x east, z south (sheet axes), y up with y=0 at the upper finished floor level."""
import json, math

site = json.load(open('site3d/site.json'))
FFL_U, FFL_L, FFL_G = 32.00, 30.80, 31.80
yU, yL, yG = 0.0, FFL_L - 32.0, FFL_G - 32.0
CUT = -14.73                      # west line of the final plot after the 65 m² cession

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
plot = clip(site['boundary'], CUT, True)
ceded = clip(site['boundary'], CUT, False)
R = lambda x0, z0, x1, z1: [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]

# ---------------- volumes (gross) ----------------
blocks = {
    'U': dict(name='Entrance and bedrooms', rect=[-9.8, -5.0, 1.3, 4.4], level=FFL_U),
    'C': dict(name='Stair', rect=[1.3, -1.67, 3.4, 0.53], level=FFL_U),
    'D': dict(name='Pantry', rect=[1.3, -4.0, 3.4, -1.67], level=FFL_L),
    'V': dict(name='Laundry', rect=[1.3, 0.53, 3.4, 3.6], level=FFL_L),
    'L': dict(name='Living / kitchen', rect=[3.4, -4.0, 13.0, 3.6], level=FFL_L),
    'G': dict(name='Garage', rect=[-8.5, -16.0, -3.0, -10.0], level=FFL_G),
    'O': dict(name='Workshop / storage', rect=[-3.0, -16.0, 2.5, -10.0], level=FFL_G),
    'A': dict(name='Covered terrace', rect=[3.4, 3.6, 13.0, 6.3], level=FFL_L),
}
for k, b in blocks.items():
    x0, z0, x1, z1 = b['rect']; b['area'] = round((x1 - x0) * (z1 - z0), 2)
area_total = round(sum(b['area'] for b in blocks.values()), 2)
area_hab = round(sum(blocks[k]['area'] for k in 'UCDVL'), 2)
area_garage_oficina = round(blocks['G']['area'] + blocks['O']['area'], 2)

# ---------------- walls ----------------
# wall: a,b (centreline, axis aligned), t, y0, h, mat, ops: [{o (from a), w, sill, head, kind}]
walls = []
def W(a, b, t, y0, h, mat='render', ops=(), tag=''):
    walls.append(dict(a=a, b=b, t=t, y0=y0, h=h, mat=mat, ops=list(ops), tag=tag))
def op(o, w, kind, sill=0.0, head=2.4): return dict(o=round(o, 3), w=round(w, 3), kind=kind, sill=sill, head=head)
T, ti = 0.30, 0.12
HU = 3.0                     # wall height up to the eaves
# --- U (bedrooms) exterior, centrelines 0.15 in from the gross outline
xw, xe, zn, zs = -9.65, 1.15, -4.85, 4.25
W([xw - .15, zs], [xe + .15, zs], T, yU, HU, ops=[op(0.6, 2.6, 'slide'), op(5.2, 0.9, 'window', 1.5, 2.1), op(8.1, 2.2, 'slide')], tag='U south')
W([xw - .15, zn], [xe + .15, zn], T, yU, HU, ops=[op(3.3, 1.6, 'window', 0.9, 2.3), op(7.0, 1.6, 'window', 0.9, 2.3), op(9.4, 0.8, 'window', 1.5, 2.1)], tag='U north')
W([xw, zn], [xw, zs], T, yU, HU, 'stone', ops=[op(1.3, 1.1, 'front', 0, 2.4), op(6.05, 2.0, 'window', 0.9, 2.3)], tag='U west (entrance, facing the road)')
W([xe, zn], [xe, zs], T, yU, HU, ops=[op(3.48, 1.6, 'open', 0, 2.4)], tag='U east (stair arrival)')
W([xe, -4.0], [xe, -1.52], T, yL, -yL, tag='U east below floor (pantry side)')
W([xe, 0.38], [xe, 3.6], T, yL, -yL, tag='U east below floor (laundry side)')
# --- U interior: hall (NW) + q3 + office + WC on the north band; corridor; suite (closet + WC) + closet q2 + q2 on the south band
W([-7.34, -4.70], [-7.34, -1.24], ti, yU, 2.7, 'render_in')                                          # hall | quarto 3
W([-3.74, -4.70], [-3.74, -1.24], ti, yU, 2.7, 'render_in')                                          # quarto 3 | escritório
W([-0.86, -4.70], [-0.86, -1.24], ti, yU, 2.7, 'render_in')                                          # escritório | I.S.
W([-7.28, -1.18], [0.10, -1.18], ti, yU, 2.7, 'render_in', [op(0.3, 0.8, 'door', 0, 2.1), op(3.9, 0.8, 'door', 0, 2.1), op(6.65, 0.7, 'door', 0, 2.1)])
W([0.10, -1.24], [0.10, -1.43], ti, yU, 2.7, 'render_in'); W([0.10, -1.43], [1.0, -1.43], ti, yU, 2.7, 'render_in')   # arrival strip (north jog)
W([-9.50, 0.04], [0.10, 0.04], ti, yU, 2.7, 'render_in', [op(1.1, 0.9, 'door', 0, 2.1), op(4.9, 0.7, 'door', 0, 2.1), op(7.9, 0.8, 'door', 0, 2.1)])
W([0.10, 0.10], [0.10, 0.29], ti, yU, 2.7, 'render_in'); W([0.10, 0.29], [1.0, 0.29], ti, yU, 2.7, 'render_in')       # arrival strip (south jog)
W([-6.24, 0.10], [-6.24, 4.10], ti, yU, 2.7, 'render_in', [op(0.4, 0.8, 'door', 0, 2.1)])            # suite | closet suite (full depth)
W([-4.92, 0.10], [-4.92, 4.10], ti, yU, 2.7, 'render_in')                                            # closet suite | I.S. suite
W([-3.30, 0.10], [-3.30, 4.10], ti, yU, 2.7, 'render_in')                                            # I.S. suite | closet q2
W([-1.98, 0.10], [-1.98, 4.10], ti, yU, 2.7, 'render_in', [op(0.4, 0.8, 'door', 0, 2.1)])            # closet q2 (full depth) | quarto 2
# --- C (stair only, 1.6 m clear), D (pantry, lower level), V (laundry, upper level); walls from the lower floor up
W([1.15, -1.52], [3.55, -1.52], T, yL, HU - yL, tag='C north | pantry')
W([1.15, 0.38], [3.55, 0.38], T, yL, HU - yL, tag='C south | laundry')
W([1.15, -3.85], [3.55, -3.85], T, yL, 3.0, 'stone', tag='pantry north (living-room height)')
W([1.15, 3.45], [3.55, 3.45], T, yL, 3.0, ops=[op(0.5, 1.2, 'window', 1.6, 2.6)], tag='laundry south (living-room height)')
# --- L (living, lower level)
HL = 3.0
W([3.55, -3.85], [13.15, -3.85], T, yL, HL, ops=[op(1.0, 4.2, 'window', 1.05, 2.3), op(6.8, 2.0, 'window', 0.9, 2.3)], tag='L north (kitchen window + one window in the NE corner)')
W([3.40, 3.45], [13.15, 3.45], T, yL, HL, ops=[op(0.6, 2.6, 'slide', 0, 2.5), op(3.6, 2.6, 'slide', 0, 2.5)], tag='L south (SE corner solid: TV wall)')
W([12.85, -4.0], [12.85, 3.6], T, yL, HL, 'stone', [op(2.9, 3.4, 'slide', 0, 2.5)], tag='L east')
W([3.55, -4.0], [3.55, 3.6], T, yL, HL, ops=[op(1.0, 0.8, 'door', 0, 2.1), op(2.63, 1.6, 'open', 0, 2.4), op(5.2, 0.8, 'door', 0, 2.1)], tag='L west (pantry door from the kitchen, stair opening, laundry door from the living room)')
W([3.55, -1.67], [3.55, 0.53], T, yL + HL, yU + HU - (yL + HL), tag='C east above L roof')
# --- garage (stone)
HG = 2.8
W([-8.5, -15.85], [-3.0, -15.85], T, yG, HG, 'stone')
W([-8.5, -10.15], [-3.0, -10.15], T, yG, HG, 'stone', [op(4.0, 0.9, 'door', 0, 2.1)], tag='garage south (door to the garden)')
W([-8.35, -16.0], [-8.35, -10.0], T, yG, HG, 'stone', [op(0.75, 4.5, 'garage', 0, 2.3)], tag='garage west (door facing the road)')
W([-3.0, -16.0], [-3.0, -10.0], ti + 0.08, yG, HG, 'render_in', [op(4.5, 0.9, 'door', 0, 2.1)], tag='garage | workshop')
W([-3.0, -15.85], [2.5, -15.85], T, yG, HG, 'stone')
W([-3.0, -10.15], [2.5, -10.15], T, yG, HG, 'stone', [op(1.0, 1.6, 'window', 1.5, 2.2), op(3.6, 0.9, 'door', 0, 2.1)], tag='workshop south')
W([2.35, -16.0], [2.35, -10.0], T, yG, HG, 'stone', [op(2.2, 1.6, 'window', 1.5, 2.2)], tag='workshop east')

# ---------------- columns, roofs ----------------
columns = [dict(x=x, z=6.12, y0=yL, h=HL, s=0.32) for x in (3.58, 8.2, 12.82)]
OV = 0.8
roofs = [
    dict(rect=[-9.8 - OV, -5.0 - OV, 1.3 + OV, 4.4 + OV], eave=yU + HU, name='U'),
    dict(rect=[1.3, -1.67 - 0.4, 3.4, 0.53 + 0.4], eave=yU + HU, name='C (stair)'),
    dict(rect=[1.3, -4.0 - OV, 13.0 + OV, 6.3 + 0.5], eave=yL + HL, name='L + pantry + laundry'),
    dict(rect=[-8.5 - 0.6, -16.0 - 0.6, 2.5 + 0.6, -10.0 + 0.6], eave=yG + HG, name='G'),
]
PITCH = 16

# ---------------- floors (top of slab) ----------------
floors = [
    dict(poly=R(-9.8, -5.0, 1.3, 4.4), y=yU, mat='oak', name='U'),
    dict(poly=R(-9.65, -4.85, -7.34, 0.04), y=yU + 0.004, mat='stone_floor', name='hall de entrada'),
    dict(poly=R(0.1, -1.37, 1.3, 0.23), y=yU + 0.004, mat='stone_floor', name='topo da escada'),
    dict(poly=R(3.4, -4.0, 13.0, 3.6), y=yL, mat='oak', name='L'),
    dict(poly=R(1.3, -4.0, 3.4, -1.67), y=yL, mat='porcelain', name='despensa'),
    dict(poly=R(1.3, 0.53, 3.4, 3.6), y=yL, mat='porcelain', name='lavandaria'),
    dict(poly=R(-4.92, 0.10, -3.30, 4.1), y=yU + 0.004, mat='porcelain', name='WC suite'),
    dict(poly=R(-0.80, -4.7, 1.0, -1.49), y=yU + 0.004, mat='porcelain', name='WC'),
    dict(poly=R(-8.5, -16.0, -3.0, -10.0), y=yG, mat='concrete', name='garage'),
    dict(poly=R(-3.0, -16.0, 2.5, -10.0), y=yG, mat='concrete', name='oficina'),
    dict(poly=R(3.4, 3.6, 13.0, 6.3), y=yL, mat='terrace', name='alpendre'),
    dict(poly=R(-9.8, 4.4, 1.3, 6.4), y=yU - 0.03, mat='terrace', name='terraço quartos'),
    dict(poly=R(13.0, -4.0, 15.0, 6.3), y=yL - 0.03, mat='terrace', name='terraço nascente'),
]
stairs = [dict(x0=1.3, x1=3.55, z0=-1.37, z1=0.23, ytop=yU, ybot=yL, n=7)]

# ---------------- rooms (labels + areas, interior) ----------------
rooms = [
    ('Entrance hall', R(-9.5, -4.7, -7.4, -1.24), FFL_U), ('Bedroom 3', R(-7.28, -4.7, -3.80, -1.24), FFL_U),
    ('Office', R(-3.68, -4.7, -0.92, -1.24), FFL_U), ('WC', [[-0.8, -4.7], [1.0, -4.7], [1.0, -1.49], [0.16, -1.49], [0.16, -1.24], [-0.8, -1.24]], FFL_U),
    ('Corridor', [[-9.5, -1.12], [0.1, -1.12], [0.1, -1.37], [1.0, -1.37], [1.0, 0.23], [0.1, 0.23], [0.1, -0.02], [-9.5, -0.02]], FFL_U),
    ('Main bedroom', R(-9.5, 0.1, -6.3, 4.1), FFL_U), ('Main closet', R(-6.18, 0.1, -4.98, 4.1), FFL_U), ('Bathroom', R(-4.86, 0.1, -3.36, 4.1), FFL_U),
    ('Closet B2', R(-3.24, 0.1, -2.04, 4.1), FFL_U),
    ('Bedroom 2', [[-1.92, 0.1], [0.04, 0.1], [0.04, 0.35], [1.0, 0.35], [1.0, 4.1], [-1.92, 4.1]], FFL_U),
    ('Laundry', R(1.3, 0.53, 3.4, 3.3), FFL_L),
    ('Pantry', R(1.3, -3.7, 3.4, -1.67), FFL_L),
    ('Stair', R(1.3, -1.37, 3.4, 0.23), FFL_U),
    ('Living / dining / kitchen', R(3.7, -3.7, 12.7, 3.3), FFL_L),
    ('Garage', R(-8.2, -15.7, -3.06, -10.3), FFL_G), ('Workshop / storage', R(-2.94, -15.7, 2.2, -10.3), FFL_G),
    ('Covered terrace', R(3.4, 3.6, 13.0, 6.3), FFL_L),
]
rooms = [dict(name=n, poly=p, level=l, area=round(area(p), 2)) for n, p, l in rooms]

# ---------------- site works ----------------
# designed ground levels (absolute) by zone
grading = dict(upper=31.80, lower=30.65, t1=29.55, t2=28.45, x_w1=3.4, x_w2=15.0, x_w3=22.5, upper_slope_from_z=6.5, upper_slope=0.08)
retaining = [  # vertical stone retaining walls (x line), z ranges filled at build time from the plot polygon
    dict(x=3.4, name='W1'), dict(x=15.0, name='W2'), dict(x=22.5, name='W3')]
garden_steps = [dict(x=3.4, z0=8.6, z1=10.2), dict(x=15.0, z0=3.0, z1=4.6), dict(x=22.5, z0=3.0, z1=4.6), dict(x=3.4, z0=-7.6, z1=-6.0)]
gate = dict(z0=-15.1, z1=-10.9)         # vehicle gate on the west line, in line with the garage door
ped_gate = dict(z0=-3.8, z1=-2.2)       # pedestrian gate in line with the front door (1.1 m clear between pillars)

zones = {   # ground finishes (polygons), later layers win
    'drive':  [R(CUT, -15.1, -8.5, -10.9)],
    'stone':  [R(CUT, -3.8, -9.8, -2.2), R(-12.4, -10.9, -11.2, -2.4), R(-9.8, 4.4, 1.3, 6.4), R(13.0, -4.0, 15.0, 6.3),
               R(3.4, 6.3, 6.2, 9.0), R(-1.6, 6.4, -0.2, 10.4), R(-4.6, -10.0, -3.4, -5.0), R(-3.0, -10.0, 2.5, -9.2)],
    'gravel': [R(-11.0, -9.2, 3.4, -5.0), R(3.4, -6.4, 13.0, -4.0), R(-12.2, -2.4, -9.8, 4.4), R(1.3, -5.0, 3.4, -4.0), R(1.3, 3.6, 3.4, 4.4)],
    'beds':   [R(-14.5, -10.6, -12.6, -3.9), R(0.0, -7.6, 3.2, -6.2), R(-10.6, -8.8, -7.2, -6.0)],
}
trees = [  # olive trees (x, z, crown radius)
    (-14.0, -16.4, 2.4),                                                  # existing tree kept by the gate
    (25.0, -17.0, 2.2), (13.0, 15.2, 1.9),                                # two existing olives transplanted from the new driveway
    (2.9, -6.7, 1.5), (-6.0, -7.4, 1.4), (-12.5, 9.0, 2.0), (-5.5, 10.0, 2.2), (8.5, 12.0, 2.3), (12.0, -10.0, 2.0),
    (19.0, -12.0, 2.4), (18.5, 10.5, 2.3), (26.5, -6.0, 2.4), (27.0, 11.0, 2.2), (6.0, -16.5, 2.0),
]

furniture = []
def F(x0, z0, x1, z1, y0, h, mat, name=''): furniture.append(dict(b=[x0, z0, x1, z1], y0=y0, h=h, mat=mat, name=name))
y = yU
F(-8.7, 0.18, -7.1, 2.3, y, 0.48, 'fabric', 'cama suite'); F(-8.7, 0.18, -7.1, 0.45, y, 1.0, 'wood', 'cabeceira')
F(-9.35, 0.2, -8.85, 0.6, y, 0.5, 'wood'); F(-6.95, 0.2, -6.45, 0.6, y, 0.5, 'wood'); F(-9.1, 2.5, -6.7, 3.6, y, 0.01, 'rug')
F(-5.58, 0.1, -4.98, 4.1, y, 2.3, 'wardrobe', 'roupeiro closet suite'); F(-4.86, 3.5, -3.36, 4.05, y, 0.85, 'white', 'bancada I.S. suite')
F(-3.24, 0.1, -2.64, 4.1, y, 2.3, 'wardrobe', 'roupeiro closet q2'); F(-1.0, 1.6, 1.0, 3.2, y, 0.48, 'fabric', 'cama q2')
F(-6.24, -4.6, -4.84, -2.6, y, 0.48, 'fabric', 'cama q3'); F(-7.28, -4.6, -6.68, -2.3, y, 2.3, 'wardrobe')
F(-3.5, -4.7, -1.7, -4.05, y, 0.75, 'wood', 'secretária'); F(-1.4, -4.7, -0.92, -2.6, y, 2.0, 'wood', 'estante')
F(-0.8, -4.7, 0.3, -4.2, y, 0.85, 'white', 'bancada I.S.'); F(-8.0, -4.7, -7.4, -3.4, y, 2.3, 'wardrobe', 'roupeiro hall')
F(1.45, 2.7, 3.35, 3.3, yL, 0.9, 'white', 'máquinas + bancada lavandaria'); F(1.45, 0.7, 1.85, 2.5, yL, 2.2, 'wardrobe', 'armário lavandaria')
F(1.45, -3.7, 3.35, -3.3, yL, 2.2, 'wood', 'prateleiras despensa'); F(1.45, -3.3, 1.85, -1.85, yL, 2.2, 'wood', 'prateleiras despensa')
y = yL
F(4.6, -3.7, 9.08, -3.08, y, 0.9, 'kitchen', 'bancada cozinha'); F(7.9, -3.7, 9.08, -3.08, y, 2.3, 'kitchen', 'colunas')
F(5.0, -2.3, 7.8, -1.3, y, 0.92, 'stone_top', 'ilha'); F(5.0, 0.6, 7.4, 1.6, y, 0.75, 'wood', 'mesa jantar')
F(9.6, -0.9, 12.4, -0.1, y, 0.8, 'fabric', 'sofá'); F(11.6, -0.1, 12.4, 1.5, y, 0.8, 'fabric', 'sofá chaise')
F(10.0, 0.4, 11.1, 1.3, y, 0.4, 'wood', 'mesa centro'); F(9.6, 0.1, 11.9, 2.3, y, 0.01, 'rug')
F(10.0, 2.9, 12.4, 3.3, y, 0.55, 'dark', 'móvel TV (parede sul)')
F(4.4, 4.6, 6.8, 5.6, y, 0.75, 'wood', 'mesa exterior'); F(9.5, 3.7, 12.2, 4.5, y, 0.75, 'fabric', 'sofá exterior')
F(10.3, 4.75, 11.4, 5.3, y, 0.38, 'wood')
F(-8.4, 4.8, -7.7, 6.2, yU, 0.35, 'white', 'espreguiçadeira'); F(-7.2, 4.8, -6.5, 6.2, yU, 0.35, 'white')
chairs = [(x, z) for x in (5.3, 6.2, 7.1) for z in (0.25, 1.95)] + [(x, z) for x in (4.7, 5.6, 6.5) for z in (4.25, 5.85)] + [(5.4, -0.95), (6.2, -0.95), (7.0, -0.95)]
for x, z in chairs:
    F(x - .22, z - .22, x + .22, z + .22, yL, 0.45, 'chair')
# sanitary (toilet, vanity, shower glass) as small boxes
for (x, z, yy) in ((-4.1, 2.6, yU), (0.7, -3.0, yU)):
    F(x - .2, z - .35, x + .2, z + .05, yy, 0.42, 'white', 'sanita')

slats = [dict(x0=-9.92, x1=-9.8, z0=-4.25, z1=-3.62, y0=yU, y1=yU + HU), dict(x0=-9.92, x1=-9.8, z0=-2.38, z1=-1.75, y0=yU, y1=yU + HU)]
room_lights = [[-8.4, -2.6, 2.3], [-5.5, -3.0, 2.3], [-2.3, -3.0, 2.3], [-5.0, -0.6, 2.3], [-7.9, 2.1, 2.3], [-0.5, 2.4, 2.3], [-4.1, 2.0, 2.3], [0.6, -0.57, 2.3], [0.1, -3.0, 2.3], [2.3, 2.0, 1.1], [2.3, -2.8, 1.1], [5.5, -1.0, 1.1], [8.0, 1.0, 1.1], [11.0, 1.2, 1.1], [6.0, 5.0, 1.3], [10.5, 5.0, 1.3]]

layout = dict(
    meta=dict(ffl_upper=FFL_U, ffl_lower=FFL_L, ffl_garage=FFL_G, area_total=area_total, area_habitacao=area_hab, area_garagem_oficina=area_garage_oficina,
              plot_area=round(area(plot), 1), ceded_area=round(area(ceded), 1), cut_x=CUT, pitch=PITCH, north_deg=8.0, area_limit=285, setback_min=3.0, retaining_cuts=[[3.4, -4.0, 7.4]],
              title='Simplified 2D plan — for approval before 3D'),
    plot=plot, ceded=ceded, blocks=blocks, walls=walls, columns=columns, roofs=roofs, floors=floors, stairs=stairs,
    rooms=rooms, grading=grading, retaining=retaining, garden_steps=garden_steps, gate=gate, ped_gate=ped_gate,
    zones=zones, trees=[dict(x=x, z=z, r=r) for x, z, r in trees], furniture=furniture, slats=slats, room_lights=room_lights)
json.dump(layout, open('site3d/layout.json', 'w'), indent=0)
print('total', area_total, 'dwelling', area_hab, 'plot', layout['meta']['plot_area'], 'ceded', layout['meta']['ceded_area'])
for k, b in blocks.items(): print(k, b['name'], b['area'])
for r in rooms: print(f"  {r['name']:<26} {r['area']:6.2f} m2")
