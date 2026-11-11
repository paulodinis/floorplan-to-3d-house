"""Soften the procedural furniture (floorplan-to-3d-house, optional pass).

Rounded edges (Bevel modifier, angle-limited) on every furniture / car mesh, puffier cushions, pillows and duvets,
and a fine fabric weave + wrinkles (bump only, no extra geometry) on upholstery. Runs after materials.py.
PARAMS["soften"] = {"edge": 0.012, "soft": 0.035, "car": 0.06} overrides the radii (metres).
"""
import bpy, math
P = globals().get("PARAMS") or {}
S = {"edge": 0.012, "soft": 0.035, "car": 0.06, **(P.get("soften") or {})}
SOFT = ("Furn_Fabric_Linen", "Furn_White", "Furn_Rug")             # cushions, mattresses, pillows, duvets, sanitaryware
HARD = ("Furn_Wood_Oak", "Furn_Wardrobe", "Furn_Kitchen", "Furn_Stone_Top", "Furn_Dark", "Furn_Chair", "Car_Taillight")
done = []


def mat_of(o):
    return o.data.materials[0].name.split('.')[0] if o.type == 'MESH' and o.data.materials else ''


def bevel(o, w, seg):
    if any(m.type == 'BEVEL' for m in o.modifiers): return
    b = o.modifiers.new('Soften', 'BEVEL'); b.width = w; b.segments = seg; b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(40); b.use_clamp_overlap = True; b.harden_normals = False
    o.data.shade_smooth() if hasattr(o.data, 'shade_smooth') else None
    done.append((o.name, w))


def fabric_bump(m, scale, strength):
    if not m or not m.use_nodes or m.get('soft_bump'): return
    nt = m.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not b: return
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale
    nz.inputs['Detail'].default_value = 6.0; wv = nt.nodes.new('ShaderNodeTexNoise'); wv.inputs['Scale'].default_value = scale * 12
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'ADD'
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = strength; bp.inputs['Distance'].default_value = 0.01
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(tc.outputs['Object'], wv.inputs['Vector'])
    nt.links.new(nz.outputs['Fac'], mx.inputs[0]); nt.links.new(wv.outputs['Fac'], mx.inputs[1]); nt.links.new(mx.outputs[0], bp.inputs['Height'])
    if b.inputs['Normal'].is_linked:
        nt.links.new(b.inputs['Normal'].links[0].from_socket, bp.inputs['Normal'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    for k in ('Sheen Weight', 'Sheen'):
        if k in b.inputs: b.inputs[k].default_value = 0.6; break
    m['soft_bump'] = 1


for o in list(bpy.data.objects):
    mn = mat_of(o)
    if not mn: continue
    if mn == 'Car_Paint': bevel(o, S["car"], 5)
    elif mn in SOFT: bevel(o, S["soft"], 4)
    elif mn in HARD: bevel(o, S["edge"], 2)
for m in bpy.data.materials:
    base = m.name.split('.')[0]
    if base in ('Furn_Fabric_Linen', 'Furn_Rug'): fabric_bump(m, 6.0, 0.25)
    elif base == 'Furn_White': fabric_bump(m, 3.0, 0.06)        # soft folds on pillows / duvet; barely visible on ceramics
result = dict(softened=len(done), objects=[d[0] for d in done][:12])
