import bpy, bmesh, math, os, random
from mathutils import Vector
P = globals().get("PARAMS") or {}
D = P["dir"]
SD = P.get("scripts_dir", os.path.join(D, "scripts"))
S2B = lambda x, y, z: Vector((x, -z, y))
ns = {'HELPERS_ONLY': True}
exec(open(os.path.join(SD, "materials.py"), encoding="utf-8").read(), ns)
new_tree, N, L, ramp_mix, noise, bump, mul_color = ns['new_tree'], ns['N'], ns['L'], ns['ramp_mix'], ns['noise'], ns['bump'], ns['mul_color']

# 1) close the 6 cm step between the fine ground window and the coarse apron (low sun made it cast a line)
G = P['window']                          # detailed ground window {x0, x1, z0, z1} = site.json 'ground'
me = bpy.data.objects['Site_Ground__Ground_Meadow'].data
moved = 0
for v in me.vertices:
    x, z = v.co.x, -v.co.y
    if not (G['x0'] + 0.01 < x < G['x1'] - 0.01 and G['z0'] + 0.01 < z < G['z1'] - 0.01):
        v.co.z += 0.06; moved += 1
me.update()

# 2) far ground to the horizon, same meadow look
if 'Far_Ground' not in bpy.data.objects:
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=60, y_segments=60, size=1500)
    kill = [f for f in bm.faces if abs(f.calc_center_median().x) < 110 and abs(f.calc_center_median().y) < 110]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    for vv in bm.verts: vv.co.z = -4.2
    fme = bpy.data.meshes.new('Far_Ground'); bm.to_mesh(fme); bm.free()
    fg = bpy.data.objects.new('Far_Ground', fme); fg.data.materials.append(bpy.data.materials['Ground_Meadow'])
    bpy.data.collections['Lights_Camera'].objects.link(fg)

# 3) meadow: more variety (golden dry grass, green patches, bare soil) at several scales
mat = bpy.data.materials['Ground_Meadow']; nt, b = new_tree(mat)
tc = N(nt, 'ShaderNodeTexCoord', -1200, 0); v = tc.outputs['Object']
n0 = noise(nt, v, 0.012, 4, 0.6, y=500); n1 = noise(nt, v, 0.06, 6, 0.6, y=300); n2 = noise(nt, v, 0.5, 6, 0.6, y=0); n3 = noise(nt, v, 220, 4, 0.6, y=-300)
c_dry = ramp_mix(nt, n1.outputs['Fac'], (0.24, 0.19, 0.09), (0.15, 0.13, 0.06), x=-400, y=400)
c_green = (0.06, 0.08, 0.03)
m1 = N(nt, 'ShaderNodeMix', -150, 300, data_type='RGBA'); m1.inputs[7].default_value = (*c_green, 1)
mr = N(nt, 'ShaderNodeMapRange', -350, 150); mr.inputs['From Min'].default_value = 0.5; mr.inputs['From Max'].default_value = 0.62
L(nt, n0.outputs['Fac'], mr.inputs['Value']); L(nt, mr.outputs['Result'], m1.inputs[0]); L(nt, c_dry, m1.inputs[6])
m2 = N(nt, 'ShaderNodeMix', 50, 150, data_type='RGBA'); m2.inputs[7].default_value = (0.16, 0.11, 0.07, 1)
mr2 = N(nt, 'ShaderNodeMapRange', -150, 0); mr2.inputs['From Min'].default_value = 0.6; mr2.inputs['From Max'].default_value = 0.72
L(nt, n2.outputs['Fac'], mr2.inputs['Value']); L(nt, mr2.outputs['Result'], m2.inputs[0]); L(nt, m1.outputs[2], m2.inputs[6])
col = mul_color(nt, m2.outputs[2], n3.outputs['Fac'], 0.8, 1.15, x=300, y=150)
L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.97
bump(nt, b, n3.outputs['Fac'], 0.6, 0.03)

# 4) roof darker, less sheen (charcoal flat tiles as in the reference)
rb = [n for n in bpy.data.materials['Roof_Tile_DarkGrey'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
rb.inputs['Roughness'].default_value = 0.6
if 'Coat Weight' in rb.inputs: rb.inputs['Coat Weight'].default_value = 0.0
if 'Specular IOR Level' in rb.inputs: rb.inputs['Specular IOR Level'].default_value = 0.35

# 5) furniture: real colours and textures instead of flat white boxes
def simple(name, base, rough, noise_scale=None, bump_s=0.0, metal=0.0):
    m = bpy.data.materials.get(name)
    if not m: return
    nt, b = new_tree(m)
    if noise_scale:
        tc = N(nt, 'ShaderNodeTexCoord', -1200, 0); nn = noise(nt, tc.outputs['Object'], noise_scale, 6, 0.6)
        L(nt, ramp_mix(nt, nn.outputs['Fac'], tuple(c * 0.85 for c in base), base), b.inputs['Base Color'])
        if bump_s: bump(nt, b, nn.outputs['Fac'], bump_s, 0.004)
    else:
        b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
simple('Furn_Fabric_Linen', (0.52, 0.47, 0.40), 0.95, 180, 0.3)
simple('Furn_Rug', (0.33, 0.29, 0.23), 1.0, 120, 0.5)
simple('Furn_White', (0.80, 0.79, 0.76), 0.35)
simple('Furn_Kitchen', (0.045, 0.045, 0.048), 0.4)
simple('Furn_Dark', (0.03, 0.03, 0.03), 0.45)
simple('Furn_Stone_Top', (0.72, 0.70, 0.66), 0.2, 8)
simple('Furn_Wardrobe', (0.55, 0.45, 0.34), 0.5, 30)
simple('Furn_Chair', (0.28, 0.18, 0.10), 0.55, 40)
m = bpy.data.materials.get('Furn_Wood_Oak')
if m:
    nt, b = new_tree(m)
    tc = N(nt, 'ShaderNodeTexCoord', -1200, 0)
    w = N(nt, 'ShaderNodeTexWave', -700, 0, wave_type='BANDS', bands_direction='X'); w.inputs['Scale'].default_value = 6; w.inputs['Distortion'].default_value = 8
    L(nt, tc.outputs['Object'], w.inputs['Vector'])
    L(nt, ramp_mix(nt, w.outputs['Fac'], (0.36, 0.22, 0.11), (0.50, 0.33, 0.18)), b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.45

# 6) warmer golden-hour sun
sun = bpy.data.objects['Sun']; sun.data.color = (1.0, 0.70, 0.45); sun.data.energy = 5.0

# 7) a few scattered shrubs/trees in the surrounding meadow for depth (instances, cheap)
far = bpy.data.objects['Far_Ground']
setup_ns = {}
src = open(os.path.join(SD, "setup.py"), encoding="utf-8").read()
fn_src = src[src.index('def scatter_group('):src.index('def add_scatter(')]
exec("import bpy\n" + fn_src, setup_ns)
bush = bpy.data.objects['A_Shrub']
md = far.modifiers.get('Scatter') or far.modifiers.new('Scatter', 'NODES')
md.node_group = setup_ns['scatter_group']('Scatter_far', bush, 0.004, 3.0, 7.0, 0.1, 77, True); md.show_viewport = False

bpy.ops.wm.save_mainfile()
result = dict(moved=moved)
