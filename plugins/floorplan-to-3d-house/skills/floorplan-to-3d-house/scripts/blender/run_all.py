"""House-style Blender pipeline (see references/blender-pipeline.md). In Blender:  import runpy; runpy.run_path(r"<scripts>/blender/run_all.py", init_globals={"PARAMS": {...}})["result"]
PARAMS keys: dir (project folder on the PC, holds <name>.glb), glb (file name), scripts_dir (this folder),
window {x0,x1,z0,z1} (detailed ground window, scene metres), spots [[x,z,h],...], ffl (abs level of y=0),
camera_keys [[frame,[x,y,z],[tx,ty,tz]],...] (scene coords: x east, y up, z south), frames_src, frames_out,
res [w,h], samples, sun {lat, dec, hour, north_deg}, room_lights [[x,y,z],...], outdoor_zones [[x0,z0,x1,z1],...], render (bool)."""
import bpy, os, json, struct, runpy, sys
P = globals().get("PARAMS") or {}
D = P["dir"]; SD = P.get("scripts_dir", os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(D, "scripts"))
P["scripts_dir"] = SD
if SD not in sys.path: sys.path.insert(0, SD)
log = []
# 1) GLB -> Blender (drop KHR_materials_volume: Blender 5.2 importer crashes on a null attenuation distance)
src = os.path.join(D, P.get("glb", "modelo.glb")); b = open(src, "rb").read()
jl = struct.unpack("<I", b[12:16])[0]; j = json.loads(b[20:20 + jl]); rest = b[20 + jl:]
for m in j.get("materials", []):
    ext = m.get("extensions", {}); ext.pop("KHR_materials_volume", None)
    if not ext and "extensions" in m: m.pop("extensions")
j["extensionsUsed"] = [e for e in j.get("extensionsUsed", []) if e != "KHR_materials_volume"]
nj = json.dumps(j, separators=(",", ":")).encode(); nj += b" " * ((4 - len(nj) % 4) % 4)
fixed = os.path.join(D, "_fixed.glb")
with open(fixed, "wb") as f:
    f.write(struct.pack("<4sII", b"glTF", 2, 20 + len(nj) + len(rest))); f.write(struct.pack("<I4s", len(nj), b"JSON")); f.write(nj); f.write(rest)
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.gltf(filepath=fixed, import_shading='NORMALS')
# 2) join meshes per (top group, material), drop empties, apply transforms
def top(o):
    while o.parent: o = o.parent
    return o.name
groups = {}
for o in list(bpy.data.objects):
    if o.type == 'MESH':
        groups.setdefault((top(o), o.data.materials[0].name if o.data.materials else 'none'), []).append(o)
for o in bpy.data.objects:
    if o.type == 'MESH' and o.parent:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
for (g, mat), objs in groups.items():
    objs = [o for o in objs if o.name in bpy.data.objects]
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs, object=objs[0]):
            bpy.ops.object.join()
    objs[0].name = f"{g}__{mat}"
for o in list(bpy.data.objects):
    if o.type == 'EMPTY': bpy.data.objects.remove(o)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
with bpy.context.temp_override(selected_editable_objects=meshes, selected_objects=meshes, active_object=meshes[0], object=meshes[0]):
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
blend = os.path.join(D, P.get("blend", "cena.blend"))
bpy.ops.wm.save_as_mainfile(filepath=blend)
# 3) style passes, same order as the reference project
def run(name):
    ns = runpy.run_path(os.path.join(SD, name), init_globals={"PARAMS": P}, run_name="__pass__")
    log.append((name, ns.get("result")))
for name in ("materials.py", "setup.py", "tweaks.py", "tweaks2.py"):
    run(name)
if "Far_Ground" in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects["Far_Ground"])
for name in ("tweaks4.py", "terrain.py", "style.py", "haze.py", "final.py"):
    if name == "final.py" and not P.get("render", False):
        pr = dict(P); pr["render"] = False
        try: runpy.run_path(os.path.join(SD, name), init_globals={"PARAMS": pr}, run_name="__pass__")
        except SystemExit: pass
        log.append((name, "settings only")); continue
    run(name)
bpy.ops.wm.save_mainfile()
result = dict(blend=blend, steps=[str(x)[:120] for x in log])
