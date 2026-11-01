"""triangle soup (three.js, Y-up, metres) -> 3D DXF (Z-up, metres), one MESH per material layer."""
import sys, json
sys.path.insert(0, sys.argv[3])
import ezdxf
from ezdxf import colors

data = json.load(open(sys.argv[1]))
doc = ezdxf.new('R2010', setup=True)
doc.units = ezdxf.units.M
doc.header['$INSUNITS'] = 6
msp = doc.modelspace()
FFL = 32.0

def conv(x, y, z):            # three (x east, y up, z south) -> DXF (x east, y north, z up), absolute level
    return (round(x, 3), round(-z, 3), round(y + FFL, 3))

for name, m in data['materials'].items():
    rgb = tuple(int(m['color'][i:i + 2], 16) for i in (1, 3, 5))
    lay = doc.layers.add(name); lay.rgb = rgb
    t = m['tris']
    verts, idx, faces = [], {}, []
    for k in range(0, len(t), 9):
        f = []
        for j in range(3):
            v = conv(t[k + j * 3], t[k + j * 3 + 1], t[k + j * 3 + 2])
            if v not in idx:
                idx[v] = len(verts); verts.append(v)
            f.append(idx[v])
        if len(set(f)) == 3:
            faces.append(f)
    mesh = msp.add_mesh(dxfattribs={'layer': name, 'color': 256})
    with mesh.edit_data() as md:
        md.vertices = verts
        md.faces = faces
    print(f'{name}: {len(faces)} faces')

lay = doc.layers.add('Plot_Limit'); lay.rgb = (220, 0, 0)
msp.add_polyline3d([conv(*p) for p in data['boundary']], close=True, dxfattribs={'layer': 'Plot_Limit'})
doc.saveas(sys.argv[2])
print('saved', sys.argv[2])
