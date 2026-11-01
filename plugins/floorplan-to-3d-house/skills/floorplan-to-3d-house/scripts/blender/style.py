"""Restyle an existing GLB in Blender without re-exporting it from the page.

Normally NOT needed: export.js exports the GLB from the styled page, so the project's style is already baked into the
GLB colours. Use this only when the GLB was exported with the default look (or to try another preset on the video):
set PARAMS["restyle"] to a style object (the content of styles/<name>.json). Without it the pass does nothing.
tint: RGB multipliers per material key (1 = default look); roof_tile 'terracotta' recolours the roof keeping its pattern."""
import bpy
P = globals().get("PARAMS") or {}
ST = P.get("restyle") or {}
NAMES = {'render': 'Wall_White_Render', 'render_in': 'Wall_Interior_White', 'stone': 'Wall_Limestone_Cladding', 'slats': 'Wood_Slats', 'soffit': 'Eave_Soffit_White',
         'roof': 'Roof_Tile_DarkGrey', 'ridge': 'Roof_Ridge', 'frame': 'Window_Frame_Anthracite', 'front': 'Door_Front_DarkWood', 'garage': 'Door_Garage_WoodSlats',
         'terrace': 'Terrace_Paving', 'oak': 'Floor_Oak', 'retain': 'Retaining_Wall_Stone', 'plinth': 'Plinth_Grey'}
done = []


def bsdf(m):
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m and m.use_nodes else None


def multiply(m, rgb, mode='MULTIPLY', fac=1.0):
    b = bsdf(m)
    if not b: return False
    sock = b.inputs['Base Color']; nt = m.node_tree
    if sock.is_linked:
        src = sock.links[0].from_socket
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = mode; mx.inputs[0].default_value = fac
        mx.inputs[7].default_value = (*rgb, 1); nt.links.new(src, mx.inputs[6]); nt.links.new(mx.outputs[2], sock)
    else:
        c = sock.default_value; sock.default_value = (c[0] * rgb[0], c[1] * rgb[1], c[2] * rgb[2], c[3]) if mode == 'MULTIPLY' else (*rgb, 1)
    return True


for key, t in (ST.get('tint') or {}).items():
    m = bpy.data.materials.get(NAMES.get(key, key))
    if m and isinstance(t, list) and multiply(m, t): done.append(key)
if ST.get('roof_tile') == 'terracotta':
    m = bpy.data.materials.get(NAMES['roof'])
    if m and multiply(m, (0.62, 0.22, 0.12), mode='COLOR') and multiply(m, (3.2, 3.2, 3.2)): done.append('roof:terracotta')
    r = bpy.data.materials.get(NAMES['ridge'])
    if r and bsdf(r): bsdf(r).inputs['Base Color'].default_value = (0.36, 0.1, 0.05, 1)
if done: bpy.ops.wm.save_mainfile()
result = dict(styled=done)
