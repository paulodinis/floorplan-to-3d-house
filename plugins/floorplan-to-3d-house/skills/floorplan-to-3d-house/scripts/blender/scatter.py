"""Geometry-nodes scatter group shared by setup.py, tweaks.py and terrain.py."""
import bpy

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
