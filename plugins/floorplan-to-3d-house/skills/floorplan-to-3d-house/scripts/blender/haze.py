"""Distance haze (mist pass in the compositor) + smaller, denser far canopies, so the countryside reads as distant trees, not green balls.
Blender 5.x: the compositor is a node group (scene.compositing_node_group) with a Group Output; Mix/Map Range are the shared shader nodes."""
import bpy
P = globals().get("PARAMS") or {}
s = bpy.context.scene
info = {}
s.view_layers[0].use_pass_mist = True
w = s.world; w.mist_settings.start = P.get("haze_start", 45.0); w.mist_settings.depth = P.get("haze_depth", 260.0); w.mist_settings.falloff = 'QUADRATIC'
ng = bpy.data.node_groups.get('Haze') or bpy.data.node_groups.new('Haze', 'CompositorNodeTree')
for n in list(ng.nodes): ng.nodes.remove(n)
if not ng.interface.items_tree: ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
rl = ng.nodes.new('CompositorNodeRLayers'); rl.scene = s
mr = ng.nodes.new('ShaderNodeMapRange'); mr.inputs['To Max'].default_value = P.get("haze_max", 0.55)
mix = ng.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs[7].default_value = tuple(P.get("haze_color", [0.60, 0.66, 0.74])) + (1,)
out = ng.nodes.new('NodeGroupOutput')
ng.links.new(rl.outputs['Image'], mix.inputs[6]); ng.links.new(rl.outputs['Mist'], mr.inputs['Value'])
ng.links.new(mr.outputs['Result'], mix.inputs[0]); ng.links.new(mix.outputs[2], out.inputs[0])
s.compositing_node_group = ng; s.render.use_compositing = True
info['haze'] = 'ok'
far = bpy.data.node_groups.get("Scatter_far3")
if far:
    for n in far.nodes:
        if n.bl_idname == "FunctionNodeRandomValue" and n.data_type == "FLOAT":
            for sk in n.inputs:
                if sk.name == "Min" and sk.enabled and sk.type == "VALUE": sk.default_value = 3.0
                if sk.name == "Max" and sk.enabled and sk.type == "VALUE": sk.default_value = 7.0
        if n.bl_idname == "GeometryNodeDistributePointsOnFaces": n.inputs["Density"].default_value = 0.009
    info['far'] = 'ok'
bpy.ops.wm.save_mainfile()
result = info
