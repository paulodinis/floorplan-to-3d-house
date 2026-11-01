import bpy, bmesh, os
P = globals().get("PARAMS") or {}
D = P["dir"]
SD = P.get("scripts_dir", os.path.join(D, "scripts"))
ns = {'HELPERS_ONLY': True}
exec(open(os.path.join(SD, "materials.py"), encoding="utf-8").read(), ns)
new_tree, N, L, ramp_mix, noise, bump, mul_color = ns['new_tree'], ns['N'], ns['L'], ns['ramp_mix'], ns['noise'], ns['bump'], ns['mul_color']
# 1) base ground under everything fills the wedges left where the lane leaves the surveyed window
if 'Base_Ground' not in bpy.data.objects:
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=4000)
    for v in bm.verts: v.co.z = -5.5
    me = bpy.data.meshes.new('Base_Ground'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('Base_Ground', me); me.materials.append(bpy.data.materials['Ground_Meadow'])
    bpy.data.collections['Lights_Camera'].objects.link(ob)
# 2) far shrubs -> soft tree canopies (smooth, subdivided, darker with leafy bump)
sh = bpy.data.objects['A_Shrub']
for p in sh.data.polygons: p.use_smooth = True
if not sh.modifiers.get('Subsurf'):
    m = sh.modifiers.new('Subsurf', 'SUBSURF'); m.levels = 2; m.render_levels = 2
if not sh.modifiers.get('Displace'):
    tex = bpy.data.textures.get('ShrubNoise') or bpy.data.textures.new('ShrubNoise', 'CLOUDS'); tex.noise_scale = 0.35
    d = sh.modifiers.new('Displace', 'DISPLACE'); d.texture = tex; d.strength = 0.18; d.mid_level = 0.5
mat = bpy.data.materials['Shrub_Leaf']; nt, b = new_tree(mat)
tc = N(nt, 'ShaderNodeTexCoord', -1200, 0); oi = N(nt, 'ShaderNodeObjectInfo', -1200, -300)
vo = N(nt, 'ShaderNodeTexVoronoi', -800, 0); vo.inputs['Scale'].default_value = 9; L(nt, tc.outputs['Object'], vo.inputs['Vector'])
base = ramp_mix(nt, oi.outputs['Random'], (0.018, 0.04, 0.012), (0.05, 0.085, 0.028), x=-500, y=200)
col = mul_color(nt, base, vo.outputs['Distance'], 1.25, 0.55, x=-100, y=200)
L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.8
bump(nt, b, vo.outputs['Distance'], 0.9, 0.08)
bpy.ops.wm.save_mainfile()
result = 'ok'
