---
name: drone-video
description: >
  This skill should be used when the user asks to "make a drone video of the house", "render the Blender video",
  "make a 15 / 30 / 60 / 90 second video", "add a walkthrough inside the house", "make the camera go …", "re-render the video" or types /drone-video
  for a project whose 2D plan was already approved in floorplan-to-3d-house and whose GLB exists.
metadata:
  version: "1.8.4"
---

# Blender drone / walkthrough video for an approved house model

Reuse the sibling skill `floorplan-to-3d-house`. `<FT>` is its base directory: the parent of this skill's base directory, then `floorplan-to-3d-house`. Details: `<FT>/references/blender-pipeline.md`.

Reply in the user's language. Label confidence as [Certain], [Likely] or [Assumption].

## Preconditions (check, don't assume)
- **Approved plan and GLB** (`export/<name>.glb`). If not, run `floorplan-to-3d-house` first; never skip its approval gate.
- **Work files.** Unpack the latest `work_v<n>.zip` from the project folder on the PC if the work dir isn't there.
- **Blender MCP connected.** Use `execute_blender_code` in the live session to launch `pipeline.py` (detached); everything heavy runs in background Blender processes. If the MCP is down, see "Blender MCP" in the reference (Windows: Smart App Control). Only fall back to computer use if the user agrees: it costs screenshots.
- **Project folder on the PC**, e.g. `<Videos>/<Project>/v<n>/`, with the GLB.

## Steps
1. **Ask once (one AskUserQuestion, two questions), unless already given:**
   - **Length / path:** "15 s: 360° orbit (Recommended)" / "30 s: slower orbit" / "60 s: orbit + every space" (≥ 45 s; ~15 spaces fit in 60 s, more need 90 s) / "My own path (describe it)".
   - **Resolution**, each with the time for the chosen length on an RTX 4060 (1600×900 measured, others scaled by pixels): "1600×900 (Recommended)" ~31 s/frame · "1920×1080" ~45 s/frame · "1280×720 (faster)" ~20 s/frame. Times = frames × s/frame; say they are corrected after the test frames.
2. **Camera path.**
   - Automatic: `python3 <FT>/scripts/cloud/camera_path.py site3d/layout.json <s> export/camera.json --site site3d/site.json --preview export/camera_path.png --lang <lang>` (options `--skip`, `--order`, `--radius`, `--height`, `--cw`).
   - The user's own shot list ("start low facing the door, rise, orbit, go into the suite, pivot 45° right…"): translate it into `export/path.json` steps and run `python3 <FT>/scripts/cloud/camera_script.py site3d/layout.json export/path.json export/camera.json --site site3d/site.json --preview export/camera_path.png --lang <lang>`. Steps: `start`, `orbit_in`, `orbit`, `to_door`, `move` (`to`, `via`), `forward`, `pivot`, `turn_to`, `spin`, `stairs`, `rise`, `strafe`, `aerial`, `hold`; points are `{"room"}`, `{"door"}`, `{"xz"}`, `{"stair"}` (full list in the script's docstring). Doors on the path open by themselves; `checks` lists glass crossed, walls crossed and eyes too close to a wall: fix those or tell the user.
3. **Path approval (mandatory stop).** Send the preview PNG with what it can't do (rooms left out, glass crossed). Ask: "Approve the video path?" — "Yes" / "Change it (describe)". Repeat until "Yes".
4. **params.json** (the reference lists the keys): site window and spots, `camera_keys` / `frames_src` / `frames_out` / `doors` from `export/camera.json`, `res`, `samples` 24, `sun` (lat from project.json, else 40 and say so), room lights, `video_name`, `blend`, `scripts_dir`. Put it with the GLB on the PC.
5. **Test** (one MCP call): launch `pipeline.py test <params.json> <blender>` detached; poll `pipeline_status.json` (text) every ~2 min. It builds the scene, renders 8 frames + the frame after each door at 50 %, and writes **one contact sheet** `tests/sheet.jpg` and `s_per_frame_est`. Stage and read only the sheet. Also read `build.steps` → `doors.py` → `missing` / `suspicious` (a door that will not open fully).
6. **Fix and re-test** only what the sheet shows (closed doors, blank walls, camera inside a column or roof). Re-test just the frames involved (`"test_frames"` in params.json).
7. **Launch** (one MCP call): `pipeline.py final …` detached. It rebuilds, starts `encode.py`, renders and keeps `frames_done`, measured `s_per_frame` and `eta_h` in the status file. Tell the user the finish time and to keep the PC awake; schedule a check (`send_later`) at the ETA instead of polling.
8. **Deliver.** At the check: read the status; when `mp4` is set, look at one contact sheet of 4 frames, send the MP4 path, name what is still weak (box furniture, narrow rooms that show mostly walls).
