---
name: drone-video
description: >
  This skill should be used when the user asks to "make a drone video of the house", "render the Blender video",
  "make a 15 / 30 / 60 / 90 second video", "add a walkthrough inside the house", "make the camera go …", "use my recorded path",
  "I recorded the drone path", "re-render the video" or types /drone-video
  for a project whose 2D plan was already approved in floorplan-to-3d-house and whose GLB exists.
metadata:
  version: "1.12.0"
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
   - **Length / path:** "15 s: 360° orbit (Recommended)" / "60 s: orbit + every space" (≥ 45 s; ~15 spaces fit in 60 s, more need 90 s) / "Record it myself in the 3D page" (the length is the recording's) / "My own path (describe it)". A 30 s slower orbit, or any other length, comes through the free answer. If the user already sent a recording (`camera_recording_*.json`, or JSON with `"kind": "fp3d-camera-recording"`), skip this question.
   - **Resolution**, each with the time for the chosen length on an RTX 4060 (1600×900 measured, others scaled by pixels): "1600×900 (Recommended)" ~31 s/frame · "1920×1080" ~45 s/frame · "1280×720 (faster)" ~20 s/frame. Times = frames × s/frame; say they are corrected after the test frames.
2. **Camera path.**
   - Automatic: `python3 <FT>/scripts/cloud/camera_path.py site3d/layout.json <s> export/camera.json --site site3d/site.json --preview export/camera_path.png --lang <lang>` (options `--skip`, `--order`, `--radius`, `--height`, `--cw`).
   - **Recorded in the 3D page** (1.12.0): the page's navigation section has **● Record path** (or the `R` key). The user flies (Drone: it goes through everything but walls, so through doors, windows, furniture and roofs) or walks (Walk) while it records; the view switches to the video framing (16 mm lens, 16:9 frame) so what they see is what Blender renders. **▶ Play** replays it as the video will move: smoothed, with pauses cut. **Download** saves `camera_recording_<date>.json`; **Copy** puts the same JSON on the clipboard. Tell the user exactly this, in their language, with the page link (republish the page first if it was built before 1.12.0: no Record button). Get the file:
     - downloaded: ask where it is (usually Downloads), then `device_stage_files` it if that folder is connected (else `device_request_folder_access` for that folder), or ask them to attach it;
     - pasted in the chat: write it to `export/recording.json` unchanged.
     Then `export/path.json` = `{"fps": 25, "steps": [{"do": "track", "file": "recording.json", "label": "<what they did>"}]}` and run `camera_script.py` as below. It **always smooths the recording before the render** and **cuts pauses**: a still camera for more than 1.5 s is cut down to 0.4 s, still time at the start and end to 0.2 s; then Gaussian smoothing of the position (0.35 s) and of the look direction (0.5 s), with an ease at both ends. `camera.json` gets `lens_mm: 16` and `track_cuts` (tell the user how many pauses were cut and the final length). Options on the step: `"smooth"` / `"smooth_look"` (raise to 0.6 / 0.9 for a shaky keyboard flight), `"still_max"`, `"still_keep"`, `"cut_stills": false`, `"speed"` (0.5 = twice as long and calmer), `"trim": [from_s, to_s]`, `"lens"`. Several recordings, or a recording plus scripted steps (`orbit`, `aerial`, `hold` …), go in one `steps` list. A fast drone (> 6 m/s, `Shift`) reads badly: suggest `"speed": 0.5`.
   - The user's own shot list ("start low facing the door, rise, orbit, go into the suite, pivot 45° right…"): translate it into `export/path.json` steps and run `python3 <FT>/scripts/cloud/camera_script.py site3d/layout.json export/path.json export/camera.json --site site3d/site.json --preview export/camera_path.png --lang <lang>`. Steps: `start`, `orbit_in`, `orbit`, `to_door`, `move` (`to`, `via`), `forward`, `pivot`, `turn_to`, `spin`, `stairs`, `rise`, `strafe`, `aerial`, `hold`; points are `{"room"}`, `{"door"}`, `{"xz"}`, `{"stair"}` (full list in the script's docstring). Doors on the path open by themselves; `checks` lists glass crossed, walls crossed and eyes too close to a wall: fix those or tell the user.
3. **Path approval (mandatory stop).** Send the preview PNG with what it can't do (rooms left out, glass crossed; for a recording also walls crossed and the speed). Ask: "Approve the video path?" — "Yes" / "Change it (describe)". Repeat until "Yes".
4. **params.json** (the reference lists the keys): site window and spots, `camera_keys` / `frames_src` / `frames_out` / `doors` (and `lens_mm` when present: 16 for a recorded path) from `export/camera.json`, `res`, `samples` 24, `sun` (lat from project.json, else 40 and say so), room lights, `video_name`, `blend`, `scripts_dir`. Put it with the GLB on the PC.
5. **Test** (one MCP call): launch `pipeline.py test <params.json> <blender>` detached; poll `pipeline_status.json` (text) every ~2 min. It builds the scene, renders 8 frames + the frame after each door at 50 %, and writes **one contact sheet** `tests/sheet.jpg` and `s_per_frame_est`. Stage and read only the sheet. Also read `build.steps` → `doors.py` → `missing` / `suspicious` (a door that will not open fully).
6. **Fix and re-test** only what the sheet shows (closed doors, blank walls, camera inside a column or roof). Re-test just the frames involved (`"test_frames"` in params.json).
7. **Launch** (one MCP call): `pipeline.py final …` detached. It rebuilds, starts `encode.py`, renders and keeps `frames_done`, measured `s_per_frame` and `eta_h` in the status file. Tell the user the finish time and to keep the PC awake; schedule a check (`send_later`) at the ETA instead of polling.
8. **Deliver.** At the check: read the status; when `mp4` is set, look at one contact sheet of 4 frames, send the MP4 path, name what is still weak (box furniture, narrow rooms that show mostly walls).
