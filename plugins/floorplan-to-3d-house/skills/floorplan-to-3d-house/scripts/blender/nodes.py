"""Shader-node helpers shared by the Blender passes (imported, never exec'd)."""
import bpy

UVM = {  # tile size in metres used when the GLB UVs were baked (uv * size = metres)
    'Wall_Limestone_Cladding': (2.0, 1.6), 'Wood_Slats': (0.6, 2.0), 'Door_Garage_WoodSlats': (0.6, 2.0), 'Door_Front_DarkWood': (0.6, 2.0),
    'Roof_Tile_DarkGrey': (1.32, 1.36), 'Floor_Oak': (2.2, 2.2), 'Floor_Porcelain': (1.2, 2.4), 'Floor_Limestone': (1.2, 2.4),
    'Terrace_Paving': (1.2, 2.4), 'Retaining_Wall_Stone': (2.0, 1.6),
}

def new_tree(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return nt, bsdf

def N(nt, kind, x=0, y=0, **props):
    n = nt.nodes.new(kind); n.location = (x, y)
    for k, v in props.items():
        if k in n.inputs: n.inputs[k].default_value = v
        else: setattr(n, k, v)
    return n

def L(nt, a, b): nt.links.new(a, b)

def coords(nt, name, mode):
    """vector in metres: 'obj' -> object coords; 'uv' -> UV scaled back to metres"""
    tc = N(nt, 'ShaderNodeTexCoord', -1200, 0)
    if mode == 'obj': return tc.outputs['Object']
    sx, sy = UVM.get(name, (1, 1))
    vm = N(nt, 'ShaderNodeVectorMath', -1000, 0, operation='MULTIPLY')
    vm.inputs[1].default_value = (sx, sy, 1)
    L(nt, tc.outputs['UV'], vm.inputs[0])
    return vm.outputs['Vector']

def noise(nt, vec, scale, detail=4, rough=0.55, x=-700, y=0):
    n = N(nt, 'ShaderNodeTexNoise', x, y); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail; n.inputs['Roughness'].default_value = rough
    L(nt, vec, n.inputs['Vector']); return n

def ramp_mix(nt, fac, c1, c2, x=-300, y=0):
    m = N(nt, 'ShaderNodeMix', x, y, data_type='RGBA'); m.inputs[6].default_value = (*c1, 1); m.inputs[7].default_value = (*c2, 1)
    L(nt, fac, m.inputs[0]); return m.outputs[2]

def bump(nt, bsdf, height, strength, dist=0.01, x=300, y=-300, normal_in=None, invert=False):
    b = N(nt, 'ShaderNodeBump', x, y); b.inputs['Strength'].default_value = strength; b.inputs['Distance'].default_value = dist; b.invert = invert
    L(nt, height, b.inputs['Height'])
    if normal_in is not None: L(nt, normal_in, b.inputs['Normal'])
    L(nt, b.outputs['Normal'], bsdf.inputs['Normal']); return b

def brick(nt, vec, w, h, c1, c2, mortar, msize, offset=0.5, x=-500, y=200):
    b = N(nt, 'ShaderNodeTexBrick', x, y); b.offset = offset; b.offset_frequency = 2 if offset != 0.5 else 2
    b.inputs['Color1'].default_value = (*c1, 1); b.inputs['Color2'].default_value = (*c2, 1); b.inputs['Mortar'].default_value = (*mortar, 1)
    b.inputs['Scale'].default_value = 1.0; b.inputs['Mortar Size'].default_value = msize; b.inputs['Mortar Smooth'].default_value = 0.15
    b.inputs['Brick Width'].default_value = w; b.inputs['Row Height'].default_value = h; b.inputs['Bias'].default_value = 0.0
    L(nt, vec, b.inputs['Vector']); return b

def mul_color(nt, col, fac_node, lo, hi, x=200, y=200):
    mr = N(nt, 'ShaderNodeMapRange', x - 150, y - 150); mr.inputs['To Min'].default_value = lo; mr.inputs['To Max'].default_value = hi
    L(nt, fac_node, mr.inputs['Value'])
    m = N(nt, 'ShaderNodeMix', x, y, data_type='RGBA', blend_type='MULTIPLY'); m.inputs[0].default_value = 1.0
    L(nt, col, m.inputs[6]); L(nt, mr.outputs['Result'], m.inputs[7]); return m.outputs[2]

def mat_named(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)
