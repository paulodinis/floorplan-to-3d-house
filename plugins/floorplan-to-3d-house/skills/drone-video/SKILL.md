---
name: drone-video
description: >
  This skill should be used when the user asks to "make a drone video of the house", "render the Blender video",
  "make a 15 / 30 / 60 second video", "add a walkthrough inside the house", "re-render the video" or types /drone-video
  for a project whose 2D plan was already approved in floorplan-to-3d-house and whose GLB exists.
metadata:
  version: "1.5.3"
---

# Blender drone / walkthrough video for an approved house model

Reuse the sibling skill `floorplan-to-3d-house`. Below, `<FT>` is its base directory: the parent of this skill's base directory, then `floorplan-to-3d-house`. Follow `<FT>/references/blender-pipeline.md` for the details.

Reply in the user's language. Label confidence as [Certain], [Likely] or [Assumption].

## Preconditions (check, don't assume)
- **Approved plan.** The 2D plan was approved and the GLB exported (`export/<name>.glb`). If not, run `floorplan-to-3d-house` up to Step 7 first. Never skip its approval gate.
- **Blender reachable.** A computer is linked to this session and Blender tools are available: Blender MCP add-on installed, server started. If they're missing, say that one integration isn't connected and how to start it (Blender → MCP add-on → Start Server). Then stop at a written plan: camera path + time estimate.
- **Project folder on the user's machine.** Example: `<Videos>/<Project>/`, with a copy of `<FT>/scripts/blender/`.

## Steps
1. **Ask once (AskUserQuestion), if not already given.** Only when the user asked for a video; if they chose the model only, don't run this skill and don't ask:
   - length: 15 s (Recommended) or 30 s: a 360° orbit of the house / 60 s: the 360° orbit, then the front door opens and the camera visits the doorway of every space; plus a custom length;
   - resolution, always these three options, each labelled with its estimated time for the chosen length (if the length is not known yet, ask it first or put the 15/30/60 s times in the option description):
     - "1600×900 (Recommended)": ~31 s/frame (measured), 15 s ≈ 3 h 15 · 30 s ≈ 6 h 30 · 60 s ≈ 12 h 55;
     - "1920×1080 (Full HD)": ~45 s/frame, 15 s ≈ 4 h 40 · 30 s ≈ 9 h 25 · 60 s ≈ 18 h 45;
     - "1280×720 (faster)": ~20 s/frame, 15 s ≈ 2 h 05 · 30 s ≈ 4 h 10 · 60 s ≈ 8 h 20.
   - State that the times are estimates for an RTX 4060 (1600×900 measured, the others scaled by pixel count) and will be corrected after the test frames (step 7). Other GPUs: scale in proportion.
   - Set `res` in params.json from the answer.
2. **Transfer the GLB.** Split it if it is over the device transfer cap: `split -b 15000000`. Join the parts on the machine.
3. **Write params.json:**
   - from `site3d/site.json`: `window` = ground, `spots` = [x, z, h];
   - `camera_keys`, `frames_src`, `frames_out` and `doors` from `camera_path.py` (step 4);
   - `sun.lat` from `project.json.location.lat` (else 40, and say so);
   - `north_deg`, the room lights converted [x, z, y] → [x, y, z], the outdoor zones;
   - `res`, `samples` 24, haze defaults.
4. **Camera path.** Camera path (every video): `python3 scripts/cloud/camera_path.py site3d/layout.json <seconds> export/camera.json --site site3d/site.json --preview export/camera_path.png`, then merge `camera_keys`, `frames_src`, `frames_out` and `doors` from `export/camera.json` into `params.json`. Don't hand-place keys.
   - **Every length is a full 360° orbit** around the house, starting and ending on the front-door side (radius = house + 10 m, height ≥ 10 m and above the tree crowns).
   - **60 s (any length ≥ 45 s): orbit, then the house from inside.** The camera comes down to the front door, the door opens, and it walks every storey (climbing the straight stairs) to the doorway of **every space** (each door on the way opens toward the room; glass sliding doors are looked through, not opened), pausing to look in. Open-plan rooms with no wall between them are linked too.
   - Read `tour` and `not_visited` in the output and tell the user which spaces are left out and why: rooms reached only from outside (a detached garage) or through a stair the script cannot follow (stairs along z, L/U or spiral stairs).
   - **Path approval (mandatory stop, before any Blender work).** Run it with `--preview export/camera_path.png --lang <project lang>`, look at the PNG, send it, and ask one AskUserQuestion: "Approve the video path?" — "Yes, launch the video" / "Change the path (describe it)". The PNG shows the orbit (radius, height, start, direction) and, per storey, the walk on the same 2 m grid as the approval plan, with the stops numbered and listed with their cells. Turn the answer into options and run again:
     - "skip 5 and 7" → `--skip "<room of stop 5>,<room of stop 7>"` (stop numbers come from `stops` in the last output);
     - "living room first", "bedrooms before the kitchen" → `--order "<room>,<room>"`;
     - "orbit closer / further / higher / lower", "the other way round" → `--radius <m>` (default house + 10 m), `--height <m>` (default ≥ 10 m), `--cw`;
     - a place given by grid cell ("start the walk at C11", "also look into K13") → find the room at that cell in the plan and use `--order` or `--skip`; say so in one line when a wish can't be expressed with these options.
     Show the new PNG and ask again. Repeat until "Yes"; never treat silence as yes. Only then build the scene, render test frames and launch.
   - If it stops with "house too large" (about 15 spaces fit in 60 s), offer 90 s.
   - Keep low cameras off saw-toothed mesh edges such as the asphalt boundary.
5. **Build the scene in a background Blender process**, not inside one MCP call: a driver script that joins the GLB, loads PARAMS and runs `run_all.py`.
6. **Test frames:**
   - 50 %, 48 samples, 5–6 frames at the keys;
   - copy them back and look at them;
   - fix closed doors, obstructions, blank walls, missing stair treads.
7. **Measure seconds per frame** from the render log. Quote the total = frames × s/frame, plus about 10 %. Tell the user to keep the PC awake.
8. **Launch** `blender -b <blend> -o <dir>/frames/f_ -a` and the `encode.py` watcher (`CS_DIR`, `CS_TOTAL`, `CS_OUT`). Schedule a check if the host supports it; otherwise tell the user when to come back.
9. **Deliver.** Look at 3–4 final frames, then send the MP4. Name what is still weak: for example box furniture in interiors, or light fixtures rendered as spheres.
