import bpy, bmesh, math, os
from mathutils import Vector
P = globals().get("PARAMS") or {}
D = P["dir"]
SD = P.get("scripts_dir", os.path.join(D, "scripts"))
ns = {'HELPERS_ONLY': True}
exec(open(os.path.join(SD, "materials.py"), encoding="utf-8").read(), ns)
new_tree, N, L, ramp_mix, noise, bump, mul_color = ns['new_tree'], ns['N'], ns['L'], ns['ramp_mix'], ns['noise'], ns['bump'], ns['mul_color']
G = P['window']                          # detailed ground window {x0, x1, z0, z1} = site.json 'ground'
info = {}

# 1) skirt along the edge of the fine ground window, hides cracks against the coarse apron
def on_window(co, eps=0.02):
    x, z = co.x, -co.y
    inside = G['x0'] - eps <= x <= G['x1'] + eps and G['z0'] - eps <= z <= G['z1'] + eps
    edge = min(abs(x - G['x0']), abs(x - G['x1']), abs(z - G['z0']), abs(z - G['z1'])) < eps
    return inside and edge
for nm in ('Site_Ground__Ground_Meadow', 'Site_Ground__Ground_Asphalt', 'Site_Ground__Ground_Sidewalk', 'Site_Ground__Road_Marking'):
    ob = bpy.data.objects.get(nm)
    if not ob: continue
    bm = bmesh.new(); bm.from_mesh(ob.data)
    edges = [e for e in bm.edges if e.is_boundary and on_window(e.verts[0].co) and on_window(e.verts[1].co)]
    if edges:
        r = bmesh.ops.extrude_edge_only(bm, edges=edges)
        nv = [g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)]
        for v in nv: v.co.z -= 0.8
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    info[nm] = len(edges)

# 2) darker, greener countryside (pine/eucalyptus mosaic, central Portugal reference) instead of sand
mat = bpy.data.materials['Ground_Meadow']; nt, b = new_tree(mat)
tc = N(nt, 'ShaderNodeTexCoord', -1300, 0); v = tc.outputs['Object']
n0 = noise(nt, v, 0.010, 5, 0.62, y=600); n1 = noise(nt, v, 0.05, 6, 0.6, y=300); n2 = noise(nt, v, 0.4, 6, 0.6, y=0); n3 = noise(nt, v, 160, 4, 0.6, y=-300)
dry = ramp_mix(nt, n1.outputs['Fac'], (0.15, 0.12, 0.055), (0.095, 0.085, 0.04), x=-450, y=400)
m1 = N(nt, 'ShaderNodeMix', -150, 300, data_type='RGBA'); m1.inputs[7].default_value = (0.028, 0.045, 0.016, 1)
mr = N(nt, 'ShaderNodeMapRange', -350, 150); mr.inputs['From Min'].default_value = 0.47; mr.inputs['From Max'].default_value = 0.58
L(nt, n0.outputs['Fac'], mr.inputs['Value']); L(nt, mr.outputs['Result'], m1.inputs[0]); L(nt, dry, m1.inputs[6])
m2 = N(nt, 'ShaderNodeMix', 50, 150, data_type='RGBA'); m2.inputs[7].default_value = (0.11, 0.08, 0.05, 1)
mr2 = N(nt, 'ShaderNodeMapRange', -150, 0); mr2.inputs['From Min'].default_value = 0.62; mr2.inputs['From Max'].default_value = 0.72
L(nt, n2.outputs['Fac'], mr2.inputs['Value']); L(nt, mr2.outputs['Result'], m2.inputs[0]); L(nt, m1.outputs[2], m2.inputs[6])
col = mul_color(nt, m2.outputs[2], n3.outputs['Fac'], 0.7, 1.2, x=300, y=150)
L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.97
bump(nt, b, n3.outputs['Fac'], 0.8, 0.04)
# far bushes: denser and taller, reading as tree clumps
far = bpy.data.objects['Far_Ground']; md = far.modifiers.get('Scatter')
if md and md.node_group:
    for n in md.node_group.nodes:
        if n.bl_idname == 'GeometryNodeDistributePointsOnFaces': n.inputs['Density'].default_value = 0.012
        if n.bl_idname == 'FunctionNodeRandomValue' and n.data_type == 'FLOAT':
            for s in n.inputs:
                if s.name == 'Min' and s.enabled and s.type == 'VALUE': s.default_value = 4.0
                if s.name == 'Max' and s.enabled and s.type == 'VALUE': s.default_value = 11.0

# 3) olive trees: open, silvery crowns (no solid core, sparser leaves)
core = bpy.data.materials['Olive_Foliage']; nt, b = new_tree(core)
for n in list(nt.nodes):
    if n.type == 'BSDF_PRINCIPLED': nt.nodes.remove(n)
tr = N(nt, 'ShaderNodeBsdfTransparent', 600, 0)
L(nt, tr.outputs[0], [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0].inputs['Surface'])
for nm in ('Olive_Trees__Olive_Foliage', 'Olive_Trees__Olive_Foliage.001', 'Olive_Trees__Olive_Foliage.002'):
    ob = bpy.data.objects.get(nm); md = ob.modifiers.get('Scatter') if ob else None
    if md and md.node_group:
        for n in md.node_group.nodes:
            if n.bl_idname == 'GeometryNodeDistributePointsOnFaces': n.inputs['Density'].default_value = 170
            if n.bl_idname == 'FunctionNodeRandomValue' and n.data_type == 'FLOAT':
                for s in n.inputs:
                    if s.name == 'Min' and s.enabled and s.type == 'VALUE': s.default_value = 1.0
                    if s.name == 'Max' and s.enabled and s.type == 'VALUE': s.default_value = 2.2
leaf = bpy.data.materials['Olive_Leaf']
for n in leaf.node_tree.nodes:
    if n.bl_idname == 'ShaderNodeMix':
        n.inputs[6].default_value = (0.11, 0.13, 0.075, 1); n.inputs[7].default_value = (0.22, 0.24, 0.17, 1)

# 4) drop the outdoor furniture blocks (alpendre / bedroom terrace) — they read as fake boxes outdoors
zones = [tuple(z) for z in P.get('outdoor_zones', [(3.4, 3.6, 13.0, 7.4), (-11.0, 4.4, -0.2, 6.4)])]
removed = 0
for ob in [o for o in bpy.data.objects if o.name.startswith('Furniture__')]:
    bm = bmesh.new(); bm.from_mesh(ob.data)
    kill = [vv for vv in bm.verts if any(x0 <= vv.co.x <= x1 and z0 <= -vv.co.y <= z1 for x0, z0, x1, z1 in zones)]
    removed += len(kill)
    bmesh.ops.delete(bm, geom=kill, context='VERTS'); bm.to_mesh(ob.data); bm.free()
info['furniture_verts_removed'] = removed
bpy.ops.wm.save_mainfile()
result = info
