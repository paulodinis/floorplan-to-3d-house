import bpy, bmesh, math, os
P = globals().get("PARAMS") or {}
D = P["dir"]
SD = P.get("scripts_dir", os.path.join(D, "scripts"))
import sys
if SD not in sys.path: sys.path.insert(0, SD)   # sibling modules: nodes.py, scatter.py
from nodes import new_tree, N, L, ramp_mix, noise, bump, mul_color
from scatter import scatter_group
SPOTS = P['spots']                       # [[x, z, abs_height], ...] from site.json spot heights
def idw(x, z):
    sw = sh = 0.0
    for sx, sz, h in SPOTS:
        w = 1 / ((x - sx) ** 2 + (z - sz) ** 2 + 4) ** 1.3; sw += w; sh += w * h
    return sh / sw
G = P['window']                          # detailed ground window {x0, x1, z0, z1} = site.json 'ground'
eps = 0.03
def inside(co): return G['x0'] - eps <= co.x <= G['x1'] + eps and G['z0'] - eps <= -co.y <= G['z1'] + eps
# 1) strip everything outside the surveyed window from the ground meshes (undo the earlier extensions)
for nm in ('Site_Ground__Ground_Meadow', 'Site_Ground__Ground_Asphalt', 'Site_Ground__Road_Marking', 'Site_Ground__Ground_Sidewalk'):
    ob = bpy.data.objects.get(nm)
    if not ob: continue
    for md in list(ob.modifiers):
        if md.name == 'ScatterFar': ob.modifiers.remove(md)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    kill = [f for f in bm.faces if abs(f.normal.z) < 0.3 or any(not inside(v.co) for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(ob.data); bm.free(); ob.data.update(); ob.location.z = 0.0
for nm in ('Base_Ground',):
    if nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm])
# 2) surrounding terrain from the survey (same interpolation as the model), 700 m square, hole under the window
if 'Terrain_Surround' in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects['Terrain_Surround'])
bm = bmesh.new()
step, half = 4.0, 350
n = int(2 * half / step)
cx, cz = (G['x0'] + G['x1']) / 2, (G['z0'] + G['z1']) / 2
verts = []
for j in range(n + 1):
    row = []
    for i in range(n + 1):
        x = cx - half + i * step; z = cz - half + j * step
        h = idw(x, z) - P.get('ffl', 32.0)
        # gentle long-wave relief far away so the horizon is not a flat plane
        h += 2.5 * math.sin(x * 0.011) * math.cos(z * 0.009) * min(1.0, max(0.0, (math.hypot(x - cx, z - cz) - 80) / 120))
        row.append(bm.verts.new((x, -z, h - 0.06)))
    verts.append(row)
for j in range(n):
    for i in range(n):
        q = [verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]]
        xs = [v.co.x for v in q]; zs = [-v.co.y for v in q]
        if min(xs) > G['x0'] + 0.5 and max(xs) < G['x1'] - 0.5 and min(zs) > G['z0'] + 0.5 and max(zs) < G['z1'] - 0.5:
            continue                                   # fully under the detailed window
        bm.faces.new(q)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
me = bpy.data.meshes.new('Terrain_Surround'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
ob = bpy.data.objects.new('Terrain_Surround', me); me.materials.append(bpy.data.materials['Ground_Meadow'])
bpy.data.collections['Lights_Camera'].objects.link(ob)
# lane continues straight north and south beyond the window, following the terrain
road = bpy.data.objects['Site_Ground__Ground_Asphalt']
bm = bmesh.new(); bm.from_mesh(road.data)
for side, sign in ((G['z0'], -1), (G['z1'], 1)):
    edges = [e for e in bm.edges if e.is_boundary and all(abs(-v.co.y - side) < 0.05 for v in e.verts)]
    for k in range(30):
        r = bmesh.ops.extrude_edge_only(bm, edges=edges)
        nv = [g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)]
        edges = [g for g in r['geom'] if isinstance(g, bmesh.types.BMEdge) and all(v in nv for v in g.verts)]
        for v in nv:
            v.co.y -= sign * 10.0
            v.co.z = idw(v.co.x, -v.co.y) - P.get('ffl', 32.0) + 0.02
bm.to_mesh(road.data); bm.free(); road.data.update()
# 3) far canopies only beyond 70 m, on the new terrain
ng = scatter_group('Scatter_far3', bpy.data.objects['A_Shrub'], 0.006, 5.0, 12.0, 0.1, 77, True)
dist = [x for x in ng.nodes if x.bl_idname == 'GeometryNodeDistributePointsOnFaces'][0]
pos = ng.nodes.new('GeometryNodeInputPosition'); vm = ng.nodes.new('ShaderNodeVectorMath'); vm.operation = 'LENGTH'
cmp = ng.nodes.new('FunctionNodeCompare'); cmp.data_type = 'FLOAT'; cmp.operation = 'GREATER_THAN'; cmp.inputs[1].default_value = 70.0
ng.links.new(pos.outputs[0], vm.inputs[0]); ng.links.new(vm.outputs['Value'], cmp.inputs[0]); ng.links.new(cmp.outputs[0], dist.inputs['Selection'])
md = ob.modifiers.new('ScatterFar', 'NODES'); md.node_group = ng; md.show_viewport = False
# 4) greener countryside tones
mat = bpy.data.materials['Ground_Meadow']; nt, b = new_tree(mat)
tc = N(nt, 'ShaderNodeTexCoord', -1300, 0); v = tc.outputs['Object']
n0 = noise(nt, v, 0.012, 5, 0.62, y=600); n1 = noise(nt, v, 0.08, 6, 0.6, y=300); n2 = noise(nt, v, 0.9, 8, 0.65, y=0); n3 = noise(nt, v, 120, 4, 0.6, y=-300)
dry = ramp_mix(nt, n1.outputs['Fac'], (0.070, 0.062, 0.028), (0.042, 0.050, 0.020), x=-450, y=400)
m1 = N(nt, 'ShaderNodeMix', -150, 300, data_type='RGBA'); m1.inputs[7].default_value = (0.020, 0.034, 0.011, 1)
mr = N(nt, 'ShaderNodeMapRange', -350, 150); mr.inputs['From Min'].default_value = 0.44; mr.inputs['From Max'].default_value = 0.55
L(nt, n0.outputs['Fac'], mr.inputs['Value']); L(nt, mr.outputs['Result'], m1.inputs[0]); L(nt, dry, m1.inputs[6])
col = mul_color(nt, m1.outputs[2], n2.outputs['Fac'], 0.55, 1.45, x=100, y=150)
col = mul_color(nt, col, n3.outputs['Fac'], 0.8, 1.15, x=350, y=150)
L(nt, col, b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.97
bump(nt, b, n3.outputs['Fac'], 0.8, 0.05)
# 5) olive leaves a little darker, silvery underside feel kept by the random mix
for x in bpy.data.materials['Olive_Leaf'].node_tree.nodes:
    if x.bl_idname == 'ShaderNodeMix': x.inputs[6].default_value = (0.075, 0.095, 0.052, 1); x.inputs[7].default_value = (0.17, 0.19, 0.13, 1)
# 6) faster, still clean: fewer bounces, denoised low sample count
cy = bpy.context.scene.cycles
cy.max_bounces = 5; cy.diffuse_bounces = 2; cy.glossy_bounces = 2; cy.transmission_bounces = 4; cy.volume_bounces = 0; cy.transparent_max_bounces = 8
cy.samples = 32; cy.adaptive_threshold = 0.04
try: cy.use_fast_gi = False
except Exception: pass
bpy.ops.wm.save_mainfile()
result = dict(terrain_faces=len(me.polygons))
