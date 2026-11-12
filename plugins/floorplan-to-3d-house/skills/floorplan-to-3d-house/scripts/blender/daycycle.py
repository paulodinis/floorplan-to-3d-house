"""Sun position and an optional day cycle (floorplan-to-3d-house, optional pass; run after setup.py).

1. Re-aims the sky texture's sun to match the Sun lamp. Blender's sky `sun_rotation` is measured from +Y toward +X
   (rotation 90 deg = sun toward +X); setup.py up to 1.8.0 used the mirrored angle, so the sky glow and the sun
   disc sat on the wrong side of the shadows.
2. PARAMS["sun_anim"] = {"f0": frame, "f1": frame, "hour0": 10, "hour1": 22} animates the solar time between two
   frames (lamp direction and strength, sky sun, background strength); before f0 the hour is hour0, after f1 hour1.
   Uses PARAMS["sun"] = {lat, dec, north_deg}.
"""
import bpy, math
from mathutils import Vector
P = globals().get("PARAMS") or {}
SUN = P.get("sun", {}); A = P.get("sun_anim") or {}
lat, dec, nr = math.radians(SUN.get('lat', 40)), math.radians(SUN.get('dec', 23.44)), math.radians(SUN.get('north_deg', 13.1))
north = Vector((math.sin(nr), math.cos(nr), 0)); east = Vector((math.cos(nr), -math.sin(nr), 0))


def sun_at(hour):
    H = math.radians(15 * (hour - 12))
    s_alt = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(H)
    alt = math.asin(max(-1, min(1, s_alt)))
    az = math.atan2(math.sin(H), math.cos(H) * math.sin(lat) - math.tan(dec) * math.cos(lat)) + math.pi
    d = (north * math.cos(az) + east * math.sin(az)) * math.cos(alt) + Vector((0, 0, math.sin(alt)))
    return d.normalized(), alt


sc = bpy.context.scene
lamp = bpy.data.objects.get('Sun')
w = sc.world; nt = w.node_tree if w and w.use_nodes else None
sky = next((n for n in nt.nodes if n.type == 'TEX_SKY'), None) if nt else None
bg = next((n for n in nt.nodes if n.type == 'BACKGROUND'), None) if nt else None
E0 = lamp.data.energy if lamp else 4.0
B0 = bg.inputs[1].default_value if bg else 1.0
SI0 = getattr(sky, 'sun_intensity', 1.0) if sky else 1.0
EX0 = sc.view_settings.exposure


QPREV = None
RPREV = None


def apply(hour, frame=None):
    d, alt = sun_at(hour)
    day = max(0.0, min(1.0, (math.sin(alt) + 0.05) / 0.25))         # 0 at night, 1 with the sun > ~11 deg
    if lamp:
        global QPREV
        dl = d.copy()
        if day < 1:                                                    # night: the lamp becomes a soft moon, high in the sky
            m = Vector((d.x, d.y, 0)).normalized() * math.cos(math.radians(35)) + Vector((0, 0, math.sin(math.radians(35))))
            dl = (d * day + m * (1 - day)).normalized()
        lamp.rotation_mode = 'QUATERNION'; q = (-dl).to_track_quat('-Z', 'Y')
        if QPREV is not None and q.dot(QPREV) < 0: q.negate()
        QPREV = q.copy(); lamp.rotation_quaternion = q; lamp.data.energy = E0 * day + 0.6 * (1 - day)
        warm = 1 - max(0.0, min(1.0, math.sin(alt) / 0.35)); c = (1.0, 0.92 - 0.25 * warm, 0.82 - 0.45 * warm); lamp.data.color = tuple(c[i] * day + (0.55, 0.66, 1.0)[i] * (1 - day) for i in range(3))
        if frame is not None:
            lamp.keyframe_insert('rotation_quaternion', frame=frame); lamp.data.keyframe_insert('energy', frame=frame); lamp.data.keyframe_insert('color', frame=frame)
    if sky:
        if hasattr(sky, 'sun_elevation'):
            global RPREV
            rot = math.atan2(d.x, d.y)                                     # +Y = 0, +X = 90 deg
            if RPREV is not None:                                          # keep it continuous (no 360 -> 0 jump between keys)
                while rot - RPREV > math.pi: rot -= 2 * math.pi
                while rot - RPREV < -math.pi: rot += 2 * math.pi
            RPREV = rot; sky.sun_elevation = alt; sky.sun_rotation = rot
            if hasattr(sky, 'sun_intensity'): sky.sun_intensity = SI0 * day
        if hasattr(sky, 'sun_direction'): sky.sun_direction = d
        if frame is not None:
            for k in ('sun_elevation', 'sun_rotation', 'sun_intensity', 'sun_direction'):
                if hasattr(sky, k):
                    try: sky.keyframe_insert(k, frame=frame)
                    except Exception: pass
    hi = max(0.0, min(1.0, (math.sin(alt) - 0.3) / 0.55))              # high sun: pull exposure down (no washed-out walls)
    vs = sc.view_settings; vs.exposure = EX0 - 1.5 * hi + 3.0 * (1 - day)   # night: lift it so lit windows and the garden read
    if frame is not None: vs.keyframe_insert('exposure', frame=frame)
    if bg:
        bg.inputs[1].default_value = B0 * (0.06 + 0.94 * day)
        if frame is not None: bg.inputs[1].keyframe_insert('default_value', frame=frame)
    return round(math.degrees(alt), 1)


keys = 0
if A.get('f0') is not None:
    f0, f1 = int(A['f0']), int(A['f1']); h0, h1 = float(A.get('hour0', SUN.get('hour', 10))), float(A.get('hour1', 22))
    apply(h0, 1); apply(h0, f0); keys = 2
    n = max(2, (f1 - f0) // 12)
    for i in range(1, n + 1):
        f = f0 + (f1 - f0) * i // n; apply(h0 + (h1 - h0) * i / n, f); keys += 1
    apply(h1, max(f1 + 1, sc.frame_end))
    result = dict(fixed_rotation=True, keys=keys, alt_start=apply(h0), hour=(h0, h1))
    apply(h0, None)
else:
    result = dict(fixed_rotation=True, alt=apply(float(SUN.get('hour', 18.75))))
