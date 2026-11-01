"""Ground material masks for the v2 site layout (same texture window as v1)."""
import json, numpy as np, cv2
from PIL import Image, ImageDraw
site = json.load(open('site3d/site.json')); L = json.load(open('site3d/layout.json'))
G = site['ground']; TW = 4096
TH = int(round(TW * (G['z1'] - G['z0']) / (G['x1'] - G['x0'])))
sx = TW / (G['x1'] - G['x0'])
T = lambda x, z: ((x - G['x0']) * sx, (z - G['z0']) * sx)
def poly_mask(polys):
    im = Image.new('L', (TW, TH), 0); d = ImageDraw.Draw(im)
    for p in polys: d.polygon([T(*q) for q in p], fill=255)
    return np.array(im) > 0
old1 = np.array(Image.open('site3d/tex/mask1.png').convert('RGB')); old3 = np.array(Image.open('site3d/tex/mask3.png').convert('RGB'))
assert old1.shape[:2] == (TH, TW), old1.shape
road = old1[..., 2] > 127; mark = old3[..., 1] > 127
plot = poly_mask([L['plot']]); ceded = poly_mask([L['ceded']])
houses = poly_mask([[[b['rect'][0], b['rect'][1]], [b['rect'][2], b['rect'][1]], [b['rect'][2], b['rect'][3]], [b['rect'][0], b['rect'][3]]] for b in L['blocks'].values()])
z = {k: poly_mask(v) & plot for k, v in L['zones'].items()}
floors_terr = poly_mask([f['poly'] for f in L['floors'] if f['mat'] == 'terrace'])
gravel = z['gravel']; beds = z['beds'] & ~gravel; drive = z['drive'] & ~beds; stone = (z['stone'] | floors_terr) & plot
lawn = plot & ~gravel & ~beds & ~drive & ~stone & ~houses
sm = lambda m, k=5: cv2.GaussianBlur(m.astype(np.float32), (k, k), 0)
def save(name, chans):
    Image.fromarray((np.stack(chans, -1) * 255).astype(np.uint8), 'RGB').save('site3d/tex/' + name, optimize=True)
save('v2_mask1.png', (sm(lawn), sm(drive), sm(road & ~plot)))
save('v2_mask2.png', (sm(stone), sm(gravel), sm(beds)))
save('v2_mask3.png', (sm(ceded & ~road), sm(mark & road, 3), np.zeros((TH, TW), np.float32)))
print('masks', TW, TH, 'lawn px', int(lawn.sum()))
