import bpy, math, os
from mathutils import Vector

P = globals().get("PARAMS") or {}
D = P.get("dir", "")                     # materials pass; helpers live in nodes.py
SD = P.get("scripts_dir", os.path.join(D, "scripts"))
import sys
if SD not in sys.path: sys.path.insert(0, SD)   # sibling modules: nodes.py, scatter.py
from nodes import UVM, new_tree, N, L, coords, noise, ramp_mix, bump, brick, mul_color, mat_named


def build(name):
    mat = mat_named(name); nt, b = new_tree(mat)
    if name in ('Wall_White_Render',):
        v = coords(nt, name, 'obj'); n1 = noise(nt, v, 4, 6, 0.6, y=200); n2 = noise(nt, v, 90, 8, 0.7, y=-200)
        col = mul_color(nt, ramp_mix(nt, n1.outputs['Fac'], (0.78, 0.76, 0.72), (0.84, 0.82, 0.78)), n2.outputs['Fac'], 0.96, 1.03)
        L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.92
        bump(nt, b, n2.outputs['Fac'], 0.22, 0.003)
    elif name == 'Wall_Interior_White':
        b.inputs['Base Color'].default_value = (0.82, 0.81, 0.78, 1); b.inputs['Roughness'].default_value = 0.8
    elif name in ('Wall_Limestone_Cladding', 'Retaining_Wall_Stone'):
        v = coords(nt, name, 'uv'); br = brick(nt, v, 0.52, 0.23, (0.66, 0.58, 0.46), (0.79, 0.72, 0.59), (0.50, 0.46, 0.40), 0.008, offset=0.37)
        br.inputs['Bias'].default_value = 0.1
        nv = coords(nt, name, 'obj'); n1 = noise(nt, nv, 3.0, 5, 0.6, y=-150); n2 = noise(nt, nv, 45, 8, 0.75, y=-400)
        col = mul_color(nt, br.outputs['Color'], n1.outputs['Fac'], 0.85, 1.12)
        L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.88
        h = N(nt, 'ShaderNodeMath', 100, -300, operation='MULTIPLY_ADD'); L(nt, n2.outputs['Fac'], h.inputs[0]); h.inputs[1].default_value = 0.35; L(nt, br.outputs['Fac'], h.inputs[2])
        m = N(nt, 'ShaderNodeMath', 0, -450, operation='SUBTRACT'); m.inputs[0].default_value = 1.0; L(nt, br.outputs['Fac'], m.inputs[1])
        L(nt, m.outputs[0], h.inputs[2]); bump(nt, b, h.outputs[0], 0.7, 0.008)
    elif name in ('Roof_Tile_DarkGrey', 'Roof_Ridge'):
        v = coords(nt, name, 'uv') if name == 'Roof_Tile_DarkGrey' else coords(nt, name, 'obj')
        br = brick(nt, v, 0.30, 0.24, (0.032, 0.034, 0.037), (0.055, 0.057, 0.062), (0.008, 0.008, 0.009), 0.004)
        sep = N(nt, 'ShaderNodeSeparateXYZ', -700, -300); L(nt, v, sep.inputs[0])
        dv = N(nt, 'ShaderNodeMath', -500, -300, operation='DIVIDE'); L(nt, sep.outputs['Y'], dv.inputs[0]); dv.inputs[1].default_value = 0.24
        fr = N(nt, 'ShaderNodeMath', -350, -300, operation='FRACT'); L(nt, dv.outputs[0], fr.inputs[0])
        nn = noise(nt, coords(nt, name, 'obj'), 60, 6, 0.6, y=-550)
        h = N(nt, 'ShaderNodeMath', -150, -350, operation='MULTIPLY_ADD'); L(nt, nn.outputs['Fac'], h.inputs[0]); h.inputs[1].default_value = 0.08; L(nt, fr.outputs[0], h.inputs[2])
        h2 = N(nt, 'ShaderNodeMath', 0, -350, operation='SUBTRACT'); L(nt, h.outputs[0], h2.inputs[0]); L(nt, br.outputs['Fac'], h2.inputs[1])
        L(nt, br.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.42
        if 'Coat Weight' in b.inputs: b.inputs['Coat Weight'].default_value = 0.15
        bump(nt, b, h2.outputs[0], 0.55, 0.012)
    elif name in ('Wood_Slats', 'Door_Garage_WoodSlats', 'Door_Front_DarkWood'):
        v = coords(nt, name, 'uv'); sep = N(nt, 'ShaderNodeSeparateXYZ', -900, -300); L(nt, v, sep.inputs[0])
        pitch = 0.075 if name != 'Door_Front_DarkWood' else 0.16
        dv = N(nt, 'ShaderNodeMath', -750, -300, operation='DIVIDE'); L(nt, sep.outputs['X'], dv.inputs[0]); dv.inputs[1].default_value = pitch
        fr = N(nt, 'ShaderNodeMath', -600, -300, operation='FRACT'); L(nt, dv.outputs[0], fr.inputs[0])
        fl = N(nt, 'ShaderNodeMath', -600, -450, operation='FLOOR'); L(nt, dv.outputs[0], fl.inputs[0])
        wn = N(nt, 'ShaderNodeTexWhiteNoise', -450, -450, noise_dimensions='1D'); L(nt, fl.outputs[0], wn.inputs['W'])
        gap = N(nt, 'ShaderNodeMath', -450, -300, operation='LESS_THAN'); L(nt, fr.outputs[0], gap.inputs[0]); gap.inputs[1].default_value = 0.84 if name != 'Door_Front_DarkWood' else 0.985
        wave = N(nt, 'ShaderNodeTexWave', -700, 200, wave_type='BANDS', bands_direction='X'); wave.inputs['Scale'].default_value = 2.5; wave.inputs['Distortion'].default_value = 6; wave.inputs['Detail'].default_value = 4
        # grain runs along the slat (v): rotate so bands vary across x
        L(nt, v, wave.inputs['Vector'])
        dark = name == 'Door_Front_DarkWood'
        c1, c2 = ((0.10, 0.055, 0.03), (0.16, 0.09, 0.05)) if dark else ((0.30, 0.16, 0.075), (0.46, 0.27, 0.13))
        col = ramp_mix(nt, wave.outputs['Fac'], c1, c2, x=-300, y=200)
        col = mul_color(nt, col, wn.outputs['Value'], 0.8, 1.15, x=0, y=200)
        m = N(nt, 'ShaderNodeMix', 300, 200, data_type='RGBA'); m.inputs[6].default_value = (0.02, 0.015, 0.01, 1); L(nt, gap.outputs[0], m.inputs[0]); L(nt, col, m.inputs[7])
        L(nt, m.outputs[2], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.5 if dark else 0.62
        bump(nt, b, gap.outputs[0], 0.8, 0.01)
    elif name == 'Floor_Oak':
        v = coords(nt, name, 'uv'); br = brick(nt, v, 1.6, 0.19, (0.50, 0.33, 0.18), (0.60, 0.42, 0.24), (0.25, 0.16, 0.09), 0.0025)
        br.inputs['Bias'].default_value = 0.0
        wave = N(nt, 'ShaderNodeTexWave', -700, -200, wave_type='BANDS', bands_direction='Y'); wave.inputs['Scale'].default_value = 3; wave.inputs['Distortion'].default_value = 8; wave.inputs['Detail'].default_value = 3
        L(nt, v, wave.inputs['Vector'])
        col = mul_color(nt, br.outputs['Color'], wave.outputs['Fac'], 0.85, 1.08)
        L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.32; bump(nt, b, br.outputs['Fac'], 0.25, 0.003, invert=True)
    elif name in ('Floor_Porcelain', 'Floor_Limestone', 'Terrace_Paving', 'Ground_Stone_Paving'):
        v = coords(nt, name, 'uv' if name != 'Ground_Stone_Paving' else 'obj')
        br = brick(nt, v, 1.2, 0.6, (0.72, 0.68, 0.61), (0.79, 0.75, 0.68), (0.55, 0.52, 0.47), 0.003)
        n1 = noise(nt, coords(nt, name, 'obj'), 6, 6, 0.6, y=-200)
        col = mul_color(nt, br.outputs['Color'], n1.outputs['Fac'], 0.92, 1.06)
        L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.35 if name == 'Floor_Porcelain' else 0.7
        bump(nt, b, br.outputs['Fac'], 0.3, 0.004, invert=True)
    elif name in ('Floor_Concrete', 'Plinth_Grey'):
        v = coords(nt, name, 'obj'); n1 = noise(nt, v, 1.5, 8, 0.65)
        c = (0.42, 0.41, 0.39) if name == 'Floor_Concrete' else (0.30, 0.29, 0.27)
        L(nt, ramp_mix(nt, n1.outputs['Fac'], tuple(x * 0.85 for x in c), c), b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.8
    elif name == 'Glass':
        b.inputs['Base Color'].default_value = (0.92, 0.96, 0.96, 1); b.inputs['Roughness'].default_value = 0.0; b.inputs['IOR'].default_value = 1.5
        b.inputs['Transmission Weight'].default_value = 1.0
    elif name == 'Window_Frame_Anthracite':
        b.inputs['Base Color'].default_value = (0.03, 0.032, 0.035, 1); b.inputs['Metallic'].default_value = 0.6; b.inputs['Roughness'].default_value = 0.35
    elif name in ('Eave_Soffit_White', 'Door_Interior_White'):
        b.inputs['Base Color'].default_value = (0.83, 0.82, 0.79, 1); b.inputs['Roughness'].default_value = 0.6
    elif name == 'Ground_Lawn':
        v = coords(nt, name, 'obj'); n1 = noise(nt, v, 0.35, 6, 0.6, y=200); n2 = noise(nt, v, 300, 4, 0.6, y=-200)
        col = ramp_mix(nt, n1.outputs['Fac'], (0.035, 0.075, 0.015), (0.075, 0.13, 0.03))
        L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.9; bump(nt, b, n2.outputs['Fac'], 0.6, 0.01)
    elif name == 'Ground_Meadow':
        v = coords(nt, name, 'obj'); n1 = noise(nt, v, 0.08, 6, 0.6, y=300); n2 = noise(nt, v, 0.6, 6, 0.6, y=0); n3 = noise(nt, v, 200, 4, 0.6, y=-300)
        c = ramp_mix(nt, n1.outputs['Fac'], (0.20, 0.17, 0.08), (0.10, 0.12, 0.04), x=-350, y=300)
        m = N(nt, 'ShaderNodeMix', 0, 100, data_type='RGBA'); m.inputs[7].default_value = (0.17, 0.12, 0.075, 1)
        ss = N(nt, 'ShaderNodeMapRange', -200, 0); ss.inputs['From Min'].default_value = 0.55; ss.inputs['From Max'].default_value = 0.7
        L(nt, n2.outputs['Fac'], ss.inputs['Value']); L(nt, ss.outputs['Result'], m.inputs[0]); L(nt, c, m.inputs[6])
        L(nt, m.outputs[2], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.95; bump(nt, b, n3.outputs['Fac'], 0.5, 0.02)
    elif name in ('Ground_Driveway_Pavers', 'Ground_Sidewalk'):
        v = coords(nt, name, 'obj')
        if name == 'Ground_Driveway_Pavers': br = brick(nt, v, 0.2, 0.1, (0.27, 0.265, 0.25), (0.34, 0.33, 0.31), (0.16, 0.155, 0.15), 0.004)
        else: br = brick(nt, v, 0.11, 0.11, (0.42, 0.41, 0.39), (0.55, 0.54, 0.51), (0.25, 0.24, 0.22), 0.008)
        n1 = noise(nt, v, 2, 6, 0.6, y=-200)
        L(nt, mul_color(nt, br.outputs['Color'], n1.outputs['Fac'], 0.85, 1.1), b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.85
        bump(nt, b, br.outputs['Fac'], 0.5, 0.006, invert=True)
    elif name == 'Ground_White_Gravel':
        v = coords(nt, name, 'obj'); vo = N(nt, 'ShaderNodeTexVoronoi', -600, 0); vo.inputs['Scale'].default_value = 55; L(nt, v, vo.inputs['Vector'])
        col = ramp_mix(nt, vo.outputs['Color'], (0.55, 0.54, 0.51), (0.82, 0.81, 0.78))
        L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.85
        inv = N(nt, 'ShaderNodeMath', -300, -300, operation='SUBTRACT'); inv.inputs[0].default_value = 1; L(nt, vo.outputs['Distance'], inv.inputs[1])
        bump(nt, b, inv.outputs[0], 1.0, 0.01)
    elif name == 'Ground_Planting_Bed':
        v = coords(nt, name, 'obj'); n1 = noise(nt, v, 25, 6, 0.6)
        L(nt, ramp_mix(nt, n1.outputs['Fac'], (0.035, 0.026, 0.018), (0.07, 0.05, 0.035)), b.inputs['Base Color']); b.inputs['Roughness'].default_value = 1.0
        bump(nt, b, n1.outputs['Fac'], 0.8, 0.02)
    elif name == 'Ground_Asphalt':
        v = coords(nt, name, 'obj'); n1 = noise(nt, v, 400, 3, 0.7); n2 = noise(nt, v, 0.7, 4, 0.6, y=-250)
        c = ramp_mix(nt, n1.outputs['Fac'], (0.035, 0.035, 0.038), (0.075, 0.075, 0.078))
        L(nt, mul_color(nt, c, n2.outputs['Fac'], 0.85, 1.1), b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.85
        bump(nt, b, n1.outputs['Fac'], 0.3, 0.005)
    elif name == 'Road_Marking':
        b.inputs['Base Color'].default_value = (0.75, 0.74, 0.70, 1); b.inputs['Roughness'].default_value = 0.6
    elif name == 'Hedge':
        v = coords(nt, name, 'obj'); vo = N(nt, 'ShaderNodeTexVoronoi', -600, 0); vo.inputs['Scale'].default_value = 28; L(nt, v, vo.inputs['Vector'])
        n1 = noise(nt, v, 2, 5, 0.6, y=-250)
        col = ramp_mix(nt, vo.outputs['Color'], (0.015, 0.04, 0.01), (0.05, 0.10, 0.025))
        L(nt, mul_color(nt, col, n1.outputs['Fac'], 0.7, 1.2), b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.75
        bump(nt, b, vo.outputs['Distance'], 1.0, 0.05)
    elif name == 'Garden_Light':
        b.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1)
        b.inputs['Emission Color'].default_value = (1.0, 0.72, 0.42, 1); b.inputs['Emission Strength'].default_value = 12
    elif name == 'Olive_Bark':
        v = coords(nt, name, 'obj'); n1 = noise(nt, v, 18, 8, 0.7)
        L(nt, ramp_mix(nt, n1.outputs['Fac'], (0.10, 0.085, 0.07), (0.25, 0.22, 0.18)), b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.95
        bump(nt, b, n1.outputs['Fac'], 1.0, 0.03)
    elif name.startswith('Olive_Foliage'):
        b.inputs['Base Color'].default_value = (0.09, 0.11, 0.06, 1); b.inputs['Roughness'].default_value = 0.8
    else:
        return False
    return True

if not globals().get('HELPERS_ONLY'):
    done = [m.name for m in list(bpy.data.materials) if build(m.name)]
    # leaf + grass materials used by the scatter step
    for nm, base, base2, sss in (('Olive_Leaf', (0.20, 0.24, 0.14), (0.36, 0.40, 0.29), 0.0), ('Grass_Blade', (0.05, 0.12, 0.02), (0.13, 0.20, 0.05), 0.0),
                                 ('Lavender', (0.20, 0.13, 0.38), (0.30, 0.22, 0.50), 0.0), ('Shrub_Leaf', (0.06, 0.12, 0.04), (0.12, 0.19, 0.07), 0.0)):
        mat = mat_named(nm); nt, b = new_tree(mat)
        oi = N(nt, 'ShaderNodeObjectInfo', -700, 0)
        col = ramp_mix(nt, oi.outputs['Random'], base, base2)
        L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.55
        if 'Subsurface Weight' in b.inputs:
            b.inputs['Subsurface Weight'].default_value = 0.15
        if nm in ('Olive_Leaf', 'Grass_Blade', 'Shrub_Leaf') and 'Transmission Weight' in b.inputs:
            pass
        mat.use_backface_culling = False
    result = dict(done=done)

