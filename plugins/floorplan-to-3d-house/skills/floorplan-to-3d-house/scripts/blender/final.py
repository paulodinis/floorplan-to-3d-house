import bpy, os
P = globals().get("PARAMS") or {}
D = P["dir"]
SD = P.get("scripts_dir", os.path.join(D, "scripts"))
def principled(name):
    m = bpy.data.materials[name]
    return m, [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
# greener countryside (less red), canopies less pastel
m, b = principled('Ground_Meadow')
for n in ([] if m.get('cs_final_tuned') else m.node_tree.nodes):   # only once: re-running final.py must not darken the meadow again
    if n.bl_idname == 'ShaderNodeMix' and n.data_type == 'RGBA' and n.blend_type == 'MIX':
        for i in (6, 7):
            if not n.inputs[i].is_linked:
                r, g, bl, a = n.inputs[i].default_value; n.inputs[i].default_value = (r * 0.62, g * 0.95, bl * 0.8, a)
m['cs_final_tuned'] = 1
if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = 0.25
for nm in ('Shrub_Leaf', 'Olive_Leaf', 'Hedge'):
    m, b = principled(nm)
    if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = 0.25
    b.inputs['Roughness'].default_value = 0.85
s = bpy.context.scene
RES = P.get('res', [1600, 900])
s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = RES[0], RES[1], 100
s.cycles.samples = P.get('samples', 24); s.cycles.adaptive_threshold = 0.05
s.render.frame_map_old, s.render.frame_map_new = P.get('frames_src', 450), P.get('frames_out', 375)
s.frame_start, s.frame_end = 1, P.get('frames_out', 375)
s.render.use_persistent_data = True
s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGB'
s.render.filepath = os.path.join(D, "frames", "f_")
os.makedirs(os.path.join(D, "frames"), exist_ok=True)
bpy.ops.wm.save_mainfile()
import subprocess
if not P.get('render', True):
    raise SystemExit
log = open(os.path.join(D, "render_log.txt"), "w")
p = subprocess.Popen([bpy.app.binary_path, "-b", os.path.join(D, P.get("blend", "cena.blend")), "-a"], stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
result = dict(pid=p.pid)
