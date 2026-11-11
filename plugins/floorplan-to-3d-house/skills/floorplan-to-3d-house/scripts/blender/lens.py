"""Animate the drone camera's focal length (optional pass): PARAMS["lens_keys"] = [[frame, mm], ...].
Use a wider lens indoors (e.g. 16 mm) so small rooms show more than one wall; smooth (Bezier) between keys."""
import bpy
P = globals().get("PARAMS") or {}
keys = P.get("lens_keys") or []
cams = [o for o in bpy.data.objects if o.type == 'CAMERA']
cam = bpy.context.scene.camera or (cams[0] if cams else None)
n = 0
if cam and keys:
    for f, mm in keys:
        cam.data.lens = float(mm); cam.data.keyframe_insert('lens', frame=int(f)); n += 1
result = dict(camera=cam.name if cam else None, keys=n)
