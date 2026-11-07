"""Open the doors on the camera path (PARAMS['doors'], written by scripts/cloud/camera_path.py).
The GLB joins all leaves of one material into one mesh (House__Door_Interior_White, House__Door_Front_DarkWood),
so the leaves are split into loose parts first; each door on the path gets its pivot on the hinge and swings
95 deg toward `toward` over ~1 s, starting at `frame`. The front-door handle (a small frame-material box on the
leaf) is moved onto the leaf so it swings with it."""
import bpy, bmesh, math
from mathutils import Vector, Matrix
P = globals().get("PARAMS") or {}
DOORS = P.get('doors') or []
S2B = lambda x, y, z: Vector((x, -z, y))                 # scene (x east, y up, z south) -> Blender (Z up)
SWING = math.radians(95); DUR = 25
log = []

def _sub_object(ob, keep, name):
    """new object holding only the vertices in `keep` (indices) of ob, same materials / UVs / transform"""
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context='VERTS')
    me = ob.data.copy(); me.name = name; bm.to_mesh(me); bm.free()
    no = bpy.data.objects.new(name, me); no.matrix_world = ob.matrix_world.copy()
    for col in ob.users_collection: col.objects.link(no)
    return no

def _remove_verts(ob, idx):
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in idx], context='VERTS'); bm.to_mesh(ob.data); bm.free()

def split_loose(ob):
    """loose parts of a mesh -> separate objects (no edit-mode operators: works in background Blender)"""
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    seen, comps = set(), []
    for v in bm.verts:
        if v.index in seen: continue
        stack, comp = [v], set()
        while stack:
            u = stack.pop()
            if u.index in comp: continue
            comp.add(u.index)
            stack += [e.other_vert(u) for e in u.link_edges if e.other_vert(u).index not in comp]
        seen |= comp; comps.append(comp)
    bm.free()
    if len(comps) <= 1: return [ob]
    parts = [_sub_object(ob, comp, f'{ob.name}.{i:03d}') for i, comp in enumerate(comps)]
    me = ob.data; bpy.data.objects.remove(ob)
    if me.users == 0: bpy.data.meshes.remove(me)
    return parts

def bbox(o):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    return Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))), Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))

def set_origin(o, p):
    o.data.transform(Matrix.Translation(-(o.matrix_world.inverted() @ p)))
    o.matrix_world = Matrix.Translation(p) @ o.matrix_world

if DOORS:
    leaves = []
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and ('Door_Interior' in o.name or 'Door_Front' in o.name)]:
        leaves += split_loose(o)
    frames = [o for o in bpy.data.objects if o.type == 'MESH' and 'Frame' in o.name and o.name.startswith('House')]
    used = set()
    for d in DOORS:
        c = S2B(d['x'], d.get('y0', 0.0) + 1.0, d['z'])
        best = None
        for o in leaves:
            if o.name in used: continue
            lo, hi = bbox(o); m = (lo + hi) / 2
            if hi.z - lo.z < 1.5: continue
            dd = math.hypot(m.x - c.x, m.y - c.y)
            if dd < 0.8 and (best is None or dd < best[0]): best = (dd, o, lo, hi)
        if not best: log.append(('no leaf', d['kind'], round(d['x'], 2), round(d['z'], 2))); continue
        _, o, lo, hi = best; used.add(o.name)
        along_x = (hi.x - lo.x) >= (hi.y - lo.y)
        hinge = Vector((lo.x, (lo.y + hi.y) / 2, lo.z)) if along_x else Vector(((lo.x + hi.x) / 2, lo.y, lo.z))
        set_origin(o, hinge)                             # pivot on the hinge first, then attach the handle
        if d['kind'] == 'front':                         # handle box: a small frame-material part on the leaf
            for fo in frames:
                mw = fo.matrix_world
                sel = {v.index for v in fo.data.vertices if lo.x - 0.15 <= (mw @ v.co).x <= hi.x + 0.15 and lo.y - 0.15 <= (mw @ v.co).y <= hi.y + 0.15
                       and lo.z + 0.4 <= (mw @ v.co).z <= lo.z + 1.8}
                if sel and len(sel) <= 16:
                    h = _sub_object(fo, sel, 'Front_Door_Handle'); _remove_verts(fo, sel)
                    hm = h.matrix_world.copy(); h.parent = o; h.matrix_world = hm
        tw = S2B(d['toward'][0], 0, d['toward'][1])
        mid = (lo + hi) / 2
        def swung(sign):
            r = Matrix.Rotation(sign * SWING, 4, 'Z'); q = r @ (mid - hinge) + hinge
            return (q.x - c.x) * (tw.x - c.x) + (q.y - c.y) * (tw.y - c.y)
        sign = 1 if swung(1) > swung(-1) else -1
        o.rotation_mode = 'XYZ'; o.animation_data_clear()
        f = int(d['frame'])
        o.rotation_euler.z = 0.0; o.keyframe_insert('rotation_euler', index=2, frame=f)
        o.rotation_euler.z = sign * SWING; o.keyframe_insert('rotation_euler', index=2, frame=f + DUR)
        log.append(('open', d['kind'], o.name, f))
result = dict(doors=len(DOORS), opened=sum(1 for l in log if l[0] == 'open'), missing=[l for l in log if l[0] != 'open'])
