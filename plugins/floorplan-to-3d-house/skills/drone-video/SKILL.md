---
name: drone-video
description: >
  This skill should be used when the user asks to "make a drone video of the house", "render the Blender video",
  "make a 15 / 30 / 60 second video", "add a walkthrough inside the house", "re-render the video" or types /drone-video
  for a project whose 2D plan was already approved in floorplan-to-3d-house and whose GLB exists.
metadata:
  version: "1.1.1"
---

# Blender drone / walkthrough video for an approved house model

Reuse the sibling skill `floorplan-to-3d-house`. Below, `<FT>` is its base directory: the parent of this skill's base directory, then `floorplan-to-3d-house`. Follow `<FT>/references/blender-pipeline.md` for the details.

Reply in the user's language. Label confidence as [Certain], [Likely] or [Assumption].

## Preconditions (check, don't assume)
- **Approved plan.** The 2D plan was approved and the GLB exported (`export/<name>.glb`). If not, run `floorplan-to-3d-house` up to Step 7 first. Never skip its approval gate.
- **Blender reachable.** A computer is linked to this session and Blender tools are available: Blender MCP add-on installed, server started. If they're missing, say that one integration isn't connected and how to start it (Blender → MCP add-on → Start Server). Then stop at a written plan: camera path + time estimate.
- **Project folder on the user's machine.** Example: `<Videos>/<Project>/`, with a copy of `<FT>/scripts/blender/`.

## Steps
1. **Ask once (AskUserQuestion), if not already given:**
   - length: 15 s (Recommended) / 30 s / 60 s with an interior pass, plus a custom length;
   - resolution: 1600×900 (Recommended) / 1280×720 (about half the time) / 1920×1080.
2. **Transfer the GLB.** Split it if it is over the device transfer cap: `split -b 15000000`. Join the parts on the machine.
3. **Write params.json:**
   - from `site3d/site.json`: `window` = ground, `spots` = [x, z, h];
   - camera keys (scene coordinates);
   - `sun.lat` from `project.json.location.lat` (else 40, and say so);
   - `north_deg`, the room lights converted [x, z, y] → [x, y, z], the outdoor zones;
   - `frames_src` / `frames_out`, `res`, `samples` 24, haze defaults.
4. **Plan the camera path.**
   - Exterior: 6–8 keys.
   - 60 s: add an interior pass through the front door → corridor → stair → living → terrace.
   - Check canopy clearance numerically. In walkthroughs, open the doors on the path: move the origin to the hinge, `rotation_mode='XYZ'`, key 90–95°.
   - Keep low cameras off saw-toothed mesh edges such as the asphalt boundary.
5. **Build the scene in a background Blender process**, not inside one MCP call: a driver script that joins the GLB, loads PARAMS and runs `run_all.py`.
6. **Test frames:**
   - 50 %, 48 samples, 5–6 frames at the keys;
   - copy them back and look at them;
   - fix closed doors, obstructions, blank walls, missing stair treads.
7. **Measure seconds per frame** from the render log. Quote the total = frames × s/frame, plus about 10 %. Tell the user to keep the PC awake.
8. **Launch** `blender -b <blend> -o <dir>/frames/f_ -a` and the `encode.py` watcher (`CS_DIR`, `CS_TOTAL`, `CS_OUT`). Schedule a check if the host supports it; otherwise tell the user when to come back.
9. **Deliver.** Look at 3–4 final frames, then send the MP4. Name what is still weak: for example box furniture in interiors, or light fixtures rendered as spheres.
