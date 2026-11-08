"""Open the finished 3D model (GLB) in Blender for the user to explore, after the 3D step.

Launch from a terminal / .bat (Blender UI opens with the model):
    blender --python open_in_blender.py -- <model.glb> [<model.blend>]
Or from the Blender MCP:
    import runpy; runpy.run_path(r"<dir>/open_in_blender.py", init_globals={"ARGS": [r"<model.glb>", r"<model.blend>"]})

What it does: drops KHR_materials_volume (the Blender 5.x glTF importer crashes on a null attenuation
distance), clears the default scene, imports the GLB, makes the aerial camera active, switches every 3D view
to Material Preview and frames the house, saves <model>.blend next to the GLB and, if the BlenderMCP add-on
is installed, starts its server so the video step can drive Blender."""
import bpy, os, sys, json, struct

args = globals().get("ARGS") or (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
if not args: raise SystemExit("usage: blender --python open_in_blender.py -- <model.glb> [<model.blend>]")
GLB = os.path.abspath(args[0])
BLEND = os.path.abspath(args[1]) if len(args) > 1 else os.path.splitext(GLB)[0] + ".blend"


def strip_volume(src, dst):
    b = open(src, "rb").read()
    jl = struct.unpack("<I", b[12:16])[0]; j = json.loads(b[20:20 + jl]); rest = b[20 + jl:]
    for m in j.get("materials", []):
        ext = m.get("extensions", {}); ext.pop("KHR_materials_volume", None)
        if not ext and "extensions" in m: m.pop("extensions")
    for k in ("extensionsUsed", "extensionsRequired"):
        if k in j: j[k] = [e for e in j[k] if e != "KHR_materials_volume"]
    nj = json.dumps(j, separators=(",", ":")).encode(); nj += b" " * ((4 - len(nj) % 4) % 4)
    with open(dst, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 20 + len(nj) + len(rest)))
        f.write(struct.pack("<I4s", len(nj), b"JSON")); f.write(nj); f.write(rest)


fixed = os.path.join(os.path.dirname(GLB), "_fixed.glb")
strip_volume(GLB, fixed)
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)      # keep the UI, drop the default cube/light/camera
bpy.ops.import_scene.gltf(filepath=fixed)
sc = bpy.context.scene
cams = [o for o in sc.objects if o.type == 'CAMERA']
cam = next((c for c in cams if 'aerial' in c.name.lower()), cams[0] if cams else None)
if cam: sc.camera = cam
for o in sc.objects: o.select_set(False)                                         # nothing selected: the house reads in its materials
log = {"glb": GLB, "objects": len(sc.objects), "camera": cam.name if cam else None}


def ui():
    """Runs once the window exists: Material Preview, frame everything, save, start the MCP server."""
    wm = bpy.context.window_manager
    if not wm.windows: return 0.5
    win = wm.windows[0]
    for area in win.screen.areas:
        if area.type != 'VIEW_3D': continue
        for sp in area.spaces:
            if sp.type == 'VIEW_3D': sp.shading.type = 'MATERIAL'; sp.clip_end = 2000
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region:
            with bpy.context.temp_override(window=win, area=area, region=region):
                try:                                                                 # look through the aerial camera (frames the house, not the whole terrain)
                    if sc.camera: bpy.ops.view3d.view_camera()
                    else: bpy.ops.view3d.view_all(center=False)
                except Exception as e: log["view"] = str(e)
    try: bpy.ops.wm.save_as_mainfile(filepath=BLEND); log["blend"] = BLEND
    except Exception as e: log["save"] = str(e)
    # MCP add-on server, whichever add-on is installed: BlenderMCP (blendermcp.start_server) or the "MCP" extension (blmcp.server_start)
    start = [(ns, op) for ns in dir(bpy.ops) if 'mcp' in ns.lower() for op in dir(getattr(bpy.ops, ns)) if 'start' in op.lower()]
    if start:
        ns, op = start[0]
        try: getattr(getattr(bpy.ops, ns), op)(); log["mcp"] = f"started ({ns}.{op})"
        except Exception as e: log["mcp"] = "already running" if "already running" in str(e).lower() else f"{ns}.{op} failed: " + str(e)[:80]
    else: log["mcp"] = "no MCP add-on enabled"
    with open(os.path.splitext(BLEND)[0] + "_blender_open.json", "w") as f: json.dump(log, f, indent=1)
    print("open_in_blender:", log)
    return None


if bpy.app.background: print("open_in_blender (background):", log)
else: bpy.app.timers.register(ui, first_interval=1.0)
result = log
