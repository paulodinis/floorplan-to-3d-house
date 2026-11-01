import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix, Euler

P = globals().get("PARAMS") or {}
D = P["dir"]
SD = P.get("scripts_dir", os.path.join(D, "scripts"))
S2B = lambda x, y, z: Vector((x, -z, y))           # three.js scene coords -> Blender (Z up, +Y north-ish)
scene = bpy.context.scene
rnd = random.Random(7)

def coll(name, hide=False):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name); scene.collection.children.link(c)
    c.hide_render = hide; c.hide_viewport = hide
    return c
assets = coll('Assets', hide=True)
lights_c = coll('Lights_Camera')

def mesh_obj(name, verts, faces, mat, collection):
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry(); me.from_pydata(verts, [], faces); me.update()
    me.materials.clear(); me.materials.append(bpy.data.materials[mat])
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if ob.name not in collection.objects: collection.objects.link(ob)
    return ob

# ---------- scatter assets ----------
def grass_clump():
    V, F = [], []
    for i in range(12):
        a = rnd.uniform(0, 2 * math.pi); r = rnd.uniform(0, 0.035); h = rnd.uniform(0.05, 0.11); w = rnd.uniform(0.004, 0.007)
        lean = rnd.uniform(-0.35, 0.35); la = rnd.uniform(0, 2 * math.pi)
        bx, by = r * math.cos(a), r * math.sin(a); ox, oy = -math.sin(a) * w, math.cos(a) * w
        tip = (bx + math.cos(la) * lean * h, by + math.sin(la) * lean * h, h)
        k = len(V); V += [(bx - ox, by - oy, 0), (bx + ox, by + oy, 0), tip]; F.append((k, k + 1, k + 2))
    return V, F
def leaf_cluster(n=7, L_=0.075, W=0.016):
    V, F = [], []
    for i in range(n):
        e = Euler((rnd.uniform(-1.2, 1.2), rnd.uniform(-1.2, 1.2), rnd.uniform(0, 6.28))); m = e.to_matrix()
        base = Vector((rnd.uniform(-.03, .03), rnd.uniform(-.03, .03), rnd.uniform(-.03, .03)))
        pts = [Vector((0, 0, 0)), Vector((W / 2, L_ * 0.45, 0)), Vector((0, L_, 0)), Vector((-W / 2, L_ * 0.45, 0))]
        k = len(V); V += [tuple(base + m @ p) for p in pts]; F.append((k, k + 1, k + 2, k + 3))
    return V, F
def bush(r=0.32, seg=8):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
    for v in bm.verts: v.co *= 1 + rnd.uniform(-0.15, 0.15); v.co.z = max(v.co.z * 0.8, -0.05)
    me = bpy.data.meshes.new('tmp'); bm.to_mesh(me); bm.free()
    V = [tuple(v.co) for v in me.vertices]; F = [tuple(p.vertices) for p in me.polygons]; bpy.data.meshes.remove(me)
    return V, F
grass_ob = mesh_obj('A_GrassClump', *grass_clump(), 'Grass_Blade', assets)
leaf_ob = mesh_obj('A_OliveLeaves', *leaf_cluster(), 'Olive_Leaf', assets)
hedge_leaf_ob = mesh_obj('A_HedgeLeaves', *leaf_cluster(6, 0.05, 0.03), 'Shrub_Leaf', assets)
lav_ob = mesh_obj('A_Lavender', *bush(0.28), 'Lavender', assets)
shrub_ob = mesh_obj('A_Shrub', *bush(0.38), 'Shrub_Leaf', assets)

# ---------- geometry-nodes scatter (one small group per use, constants baked in) ----------
def scatter_group(gname, inst_ob, density, smin, smax, tilt, seed, keep=True):
    ng = bpy.data.node_groups.get(gname)
    if ng: bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(gname, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n = ng.nodes; l = ng.links
    def sock(coll, name, typ):
        c = [x for x in coll if x.name == name and x.enabled]
        c = [x for x in c if x.type == typ] or c
        return c[0]
    gi = n.new('NodeGroupInput'); go = n.new('NodeGroupOutput')
    dist = n.new('GeometryNodeDistributePointsOnFaces'); dist.distribute_method = 'RANDOM'
    dist.inputs['Density'].default_value = density; dist.inputs['Seed'].default_value = seed
    oi = n.new('GeometryNodeObjectInfo'); oi.transform_space = 'ORIGINAL'; oi.inputs['Object'].default_value = inst_ob
    inst = n.new('GeometryNodeInstanceOnPoints')
    rs = n.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
    sock(rs.inputs, 'Min', 'VALUE').default_value = smin; sock(rs.inputs, 'Max', 'VALUE').default_value = smax; rs.inputs['Seed'].default_value = seed + 1
    rr = n.new('FunctionNodeRandomValue'); rr.data_type = 'FLOAT_VECTOR'
    sock(rr.inputs, 'Min', 'VECTOR').default_value = (-tilt, -tilt, 0); sock(rr.inputs, 'Max', 'VECTOR').default_value = (tilt, tilt, 6.2832); rr.inputs['Seed'].default_value = seed + 2
    join = n.new('GeometryNodeJoinGeometry')
    l.new(gi.outputs[0], dist.inputs['Mesh'])
    l.new(dist.outputs['Points'], inst.inputs['Points'])
    l.new(oi.outputs['Geometry'], inst.inputs['Instance'])
    l.new(sock(rr.outputs, 'Value', 'VECTOR'), inst.inputs['Rotation'])
    l.new(sock(rs.outputs, 'Value', 'VALUE'), inst.inputs['Scale'])
    if keep: l.new(gi.outputs[0], join.inputs[0])
    l.new(inst.outputs['Instances'], join.inputs[0])
    l.new(join.outputs[0], go.inputs[0])
    return ng
def add_scatter(obname, inst, density, smin, smax, tilt, seed, keep=True, label='Scatter'):
    ob = bpy.data.objects.get(obname)
    if not ob: return 0
    ng = scatter_group(f'Scatter_{label}_{obname}', inst, density, smin, smax, tilt, seed, keep)
    md = ob.modifiers.get(label) or ob.modifiers.new(label, 'NODES'); md.node_group = ng
    md.show_viewport = False          # render-only, keeps the viewport responsive
    return 1
added = 0
added += add_scatter('Site_Ground__Ground_Lawn', grass_ob, 500, 0.8, 1.5, 0.25, 1)
for i, nm in enumerate(['Olive_Trees__Olive_Foliage', 'Olive_Trees__Olive_Foliage.001', 'Olive_Trees__Olive_Foliage.002']):
    added += add_scatter(nm, leaf_ob, 260, 0.8, 1.6, 3.14, 10 + i)
added += add_scatter('Site_Works__Hedge', hedge_leaf_ob, 450, 0.9, 1.6, 3.14, 20)
added += add_scatter('Site_Ground__Ground_Planting_Bed', lav_ob, 2.2, 0.7, 1.2, 0.1, 30)
added += add_scatter('Site_Ground__Ground_Planting_Bed', shrub_ob, 1.2, 0.6, 1.1, 0.1, 31, label='Scatter2')
# olive crowns: darker inner core
for nm in ['Olive_Trees__Olive_Foliage', 'Olive_Trees__Olive_Foliage.001', 'Olive_Trees__Olive_Foliage.002']:
    ob = bpy.data.objects.get(nm)
    if ob: ob.data.materials[0] = bpy.data.materials['Olive_Foliage']

# ---------- sun position: 21 June, 18:45 solar time, 40°N; true north 13° east of sheet-up ----------
SUN = P.get('sun', {})
lat, dec, hour = math.radians(SUN.get('lat', 40)), math.radians(SUN.get('dec', 23.44)), SUN.get('hour', 18.75)
H = math.radians(15 * (hour - 12))
sin_alt = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(H)
alt = math.asin(sin_alt)
az = math.atan2(math.sin(H), math.cos(H) * math.sin(lat) - math.tan(dec) * math.cos(lat)) + math.pi    # clockwise from north
nr = math.radians(SUN.get('north_deg', 13.1))
north = Vector((math.sin(nr), math.cos(nr), 0)); east = Vector((math.cos(nr), -math.sin(nr), 0))
sun_dir = (north * math.cos(az) + east * math.sin(az)) * math.cos(alt) + Vector((0, 0, math.sin(alt)))
sun_dir.normalize()
for o in list(bpy.data.objects):
    if o.type == 'LIGHT': bpy.data.objects.remove(o)
sun_data = bpy.data.lights.new('Sun', 'SUN'); sun_data.energy = 4.0; sun_data.color = (1.0, 0.80, 0.60); sun_data.angle = math.radians(0.6)
sun = bpy.data.objects.new('Sun', sun_data); lights_c.objects.link(sun)
sun.rotation_euler = (-sun_dir).to_track_quat('-Z', 'Y').to_euler()

# ---------- world: physical sky ----------
world = scene.world or bpy.data.worlds.new('World'); scene.world = world; world.use_nodes = True
wt = world.node_tree
for n in list(wt.nodes): wt.nodes.remove(n)
sky = wt.nodes.new('ShaderNodeTexSky'); bg = wt.nodes.new('ShaderNodeBackground'); wo = wt.nodes.new('ShaderNodeOutputWorld')
types = [i.identifier for i in sky.bl_rna.properties['sky_type'].enum_items]
pick = next((t for t in ('MULTIPLE_SCATTERING', 'NISHITA', 'SINGLE_SCATTERING', 'HOSEK_WILKIE') if t in types), types[0])
sky.sky_type = pick
if hasattr(sky, 'sun_elevation'):
    sky.sun_elevation = alt
    # Blender's sky: sun_rotation is measured around Z from +Y toward -X? derive from the vector instead
    sky.sun_rotation = math.atan2(-sun_dir.x, sun_dir.y) % (2 * math.pi)
    for k, v in (('sun_disc', True), ('sun_size', math.radians(0.6)), ('sun_intensity', 0.6), ('altitude', 10.0), ('air_density', 1.0), ('dust_density', 2.5), ('ozone_density', 1.0)):
        if hasattr(sky, k):
            try: setattr(sky, k, v)
            except Exception: pass
if hasattr(sky, 'sun_direction'): sky.sun_direction = sun_dir
bg.inputs['Strength'].default_value = 0.35
wt.links.new(sky.outputs['Color'], bg.inputs['Color']); wt.links.new(bg.outputs['Background'], wo.inputs['Surface'])

# ---------- interior lights (warm, on at dusk) ----------
rooms = P.get('room_lights') or [(-8.7, 2.3, 2.1), (-5.2, 2.3, 2.1), (-2.0, 2.3, 2.1), (-2.5, 2.3, -2.5), (-9.7, 2.3, -2.5), (0.7, 2.3, -2.0), (5.5, 1.1, -1.0), (8.0, 1.1, 1.0), (11.0, 1.1, 1.2), (6.0, 1.3, 5.5), (10.5, 1.3, 5.5)]
for i, (x, y, z) in enumerate(rooms):
    ld = bpy.data.lights.new(f'Room_{i}', 'POINT'); ld.energy = 70 if y > 2 else 90; ld.color = (1.0, 0.72, 0.45); ld.shadow_soft_size = 0.15
    lo = bpy.data.objects.new(f'Room_{i}', ld); lo.location = S2B(x, y, z); lights_c.objects.link(lo)

# ---------- render settings ----------
scene.render.engine = 'CYCLES'
cp = bpy.context.preferences.addons['cycles'].preferences
cp.compute_device_type = 'OPTIX'; cp.get_devices()
for d in cp.devices: d.use = (d.type == 'OPTIX')
cy = scene.cycles
cy.device = 'GPU'; cy.samples = 128; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.025
cy.use_denoising = True
try: cy.denoiser = 'OPTIX'
except Exception: pass
cy.max_bounces = 8; cy.transparent_max_bounces = 16; cy.caustics_reflective = False; cy.caustics_refractive = False
cy.sample_clamp_indirect = 8.0
scene.render.use_persistent_data = True
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1920, 1080, 100
scene.render.fps = 25; scene.frame_start = 1; scene.frame_end = P.get('frames_src', 450)
vs = scene.view_settings
try:
    vs.view_transform = 'AgX'
    vs.look = 'AgX - Medium High Contrast'
except Exception:
    try: vs.look = 'Medium High Contrast'
    except Exception: pass
vs.exposure = 0.3
scene.render.film_transparent = False

# ---------- drone camera ----------
for o in list(bpy.data.objects):
    if o.type == 'CAMERA': bpy.data.objects.remove(o)
cam_d = bpy.data.cameras.new('DroneCam'); cam_d.lens = 22; cam_d.sensor_width = 36; cam_d.clip_end = 1500
cam = bpy.data.objects.new('DroneCam', cam_d); lights_c.objects.link(cam); scene.camera = cam
tgt = bpy.data.objects.get('DroneTarget') or bpy.data.objects.new('DroneTarget', None);
if tgt.name not in lights_c.objects: lights_c.objects.link(tgt)
c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
keys = [tuple([k[0], tuple(k[1]), tuple(k[2])]) for k in P['camera_keys']] if P.get('camera_keys') else [  # frame, camera (scene coords x, y, z), target
    (1,   (38, 26, 32),   (4, -1, 2)),
    (110, (25, 10, 19),   (7, -0.6, 4)),
    (210, (12, 1.1, 8.6), (8, 0.2, 3.5)),
    (300, (-1.0, 2.0, 9.0), (-6, 0.9, 3)),
    (380, (-16, 8, 2),    (-5, 0.2, -5)),
    (450, (-20, 3.2, -10), (-3, 1.0, -6)),
]
cam.animation_data_clear(); tgt.animation_data_clear()
for f, p, t in keys:
    cam.location = S2B(*p); cam.keyframe_insert('location', frame=f)
    tgt.location = S2B(*t); tgt.keyframe_insert('location', frame=f)
for ob in (cam, tgt):
    ad = ob.animation_data
    if ad and ad.action:
        fcs = []
        try: fcs = list(ad.action.fcurves)
        except Exception:
            for layer in ad.action.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags: fcs += list(cb.fcurves)
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
scene.frame_set(210)
bpy.ops.wm.save_mainfile()
result = dict(sky=pick, sky_types=types, sun_alt_deg=round(math.degrees(alt), 1), sun_az_deg=round(math.degrees(az), 1), scatter=added,
              sun_dir=[round(v, 3) for v in sun_dir])
