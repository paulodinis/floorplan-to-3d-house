# Blender drone video (Blender 4.2+ / 5.x, Cycles)

Requirements:
- Blender with the official Blender MCP add-on (Server started) on the user's machine;
- a GPU (OptiX / CUDA / HIP / Metal);
- the project folder on that machine.

1. **GLB transfer:** device file transfers may be capped (~30 MB). Split the file (`split -b 15000000`), copy the parts and join them in Blender Python.
2. **params.json:**
   - `dir`, `glb`, `blend`, `scripts_dir` (the skill's `scripts/blender` copied to the PC);
   - `window` (detailed ground window), `spots`, `ffl`;
   - `camera_keys: [[frame, [x, y, z], [tx, ty, tz]]]` in scene coordinates;
   - `frames_src` / `frames_out`, `res`, `samples`;
   - `sun {lat, dec, hour, north_deg}`;
   - `room_lights [[x, y, z]]`, `outdoor_zones`;
   - optional `haze_start`, `haze_depth`, `haze_max`, `haze_color`.
3. **Build in the background.** MCP calls time out at about 60 s:
   `blender -b --python run_<project>.py`, where the driver joins the GLB, loads params and runs `run_all.py`. The passes are:
   - import (the KHR_materials_volume extension is stripped);
   - join by material;
   - materials;
   - scatter (grass, olive leaves, hedges, lavender);
   - physical sky + sun;
   - interior lights;
   - surrounding terrain from the spot heights;
   - style (`style.py`: only when `params.json` has `"restyle"`, see style-guide.md);
   - haze;
   - final settings.
4. **Camera path:**
   - test canopy clearance numerically: horizontal distance to each tree > crown radius + 0.5 m whenever the camera is below the canopy top;
   - keep low cameras off saw-toothed mesh edges such as the asphalt boundary;
   - in walkthroughs:
     - open the doors on the path (`rotation_mode='XYZ'`, origin moved to the hinge);
     - keep the eye 1.5–1.7 m above the floor;
     - keep clear of door heads (opening head ~2.1–2.4 m above that floor).
5. **Test frames:**
   - 50 % resolution, 48 samples, 5–6 frames at the keys;
   - copy them back and look at them;
   - fix framing, obstructions and missing parts.
6. **Measure:** read `Time:` in the log and quote frames × s/frame. Examples (RTX 4060, 1600×900, 24 samples, haze): 15 s ≈ 3 h 15, 60 s ≈ 12 h 45.
7. **Final:**
   - render in a subprocess: `blender -b <blend> -o <dir>/frames/f_ -a`;
   - start the watcher: `CS_DIR=<dir> CS_TOTAL=<frames> CS_OUT=<name>_ blender -b --factory-startup --python encode.py`, which writes the MP4 (H.264) and `<name>_DONE.txt`;
   - schedule a check, if the host supports it;
   - tell the user to keep the PC awake.
