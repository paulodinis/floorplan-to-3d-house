# Changelog

## 1.5.3 (2026-11-08)
- **Fix `doors.py`: doors on the camera path did not open.** The GLB writes flat-shaded boxes with split vertices, so splitting by edges cut each leaf into 6–12 separate faces and only one face swung. Loose parts are now grouped by shared edges *or* coincident vertex positions. Checked in a render: the front door of a test house opens fully.
- The threshold stops and hinge-side choice from 1.5.2 are confirmed in renders.

## 1.5.2 (2026-11-08)
- **Blender MCP on Windows:** when Smart App Control blocks the `uvx`-built `blender-mcp.exe` ("Connection closed"), run the server with the signed Python (`py -c "from blender_mcp.server import main; main()"`) in `claude_desktop_config.json`. Documented in Step 7b and `references/blender-pipeline.md`.
- `camera_path.py`: each stop now steps onto the threshold (`CAM_THRESHOLD`, 0.25 m into the room; 0 = previous behaviour). From 0.8 m back, narrow doorways showed only jambs and walls. *Not yet checked in a render.*
- `doors.py`: picks the hinge side that keeps the open leaf out of the camera's view when it looks into the room. *Not yet checked in a render.*

## 1.5.1 (2026-11-08)
- **Step 7b asks before launching Blender:** "Open the 3D model in Blender on your computer?", with the options "Yes" / "I don't have Blender" / "Not now". When computer use is available it checks the install first and shows the result (e.g. "Blender 5.2 found"), but it still asks. "I don't have Blender" skips Step 7b and the video, and points to the GLB and to blender.org. The question is asked once per session.

## 1.5.0 (2026-11-08)
- **New Step 7b: open the finished 3D in Blender.**
  - Right after the exports, the skill opens the model in Blender on the user's PC, without asking; it is not the video and needs no approval.
  - It runs through the Blender MCP when connected. Otherwise it types into an open Blender's Python console with computer use, or writes a `.bat`/`.command` launcher.
- New `scripts/blender/open_in_blender.py`:
  - strips `KHR_materials_volume`, clears the scene and imports the GLB;
  - looks through the aerial camera in Material Preview and saves `<name>.blend` next to the GLB;
  - starts the MCP add-on server, either BlenderMCP or the "MCP" extension (`blmcp.server_start`);
  - writes `<name>_blender_open.json`.
  - Tested on Blender 5.2 (Windows) with a 30 MB GLB of 4,230 objects.
- Troubleshooting note: if the add-on server is running and the Blender MCP still reports "Connection closed", Windows Smart App Control may be blocking `uvx`/`blender-mcp.exe` on the client side.

## 1.4.0 (2026-11-07)
- **Every video is a 360° orbit of the house**, starting and ending on the front-door side, above the tree crowns.
- **60 s video = orbit + the house from inside:** the camera comes down to the front door, the door opens, and it walks every storey (climbing straight stairs) to the doorway of every space, looking in; each door on the way opens toward the room, glass sliding doors are looked through. Open-plan rooms with no wall between them are linked.
- New `scripts/cloud/camera_path.py`: builds `camera_keys`, `frames_src`/`frames_out`, `doors`, the tour order and the spaces left out (with reasons) from `layout.json`; `--preview` draws the path over the plan. Tested on both examples (15 of 17 spaces on one storey: the detached garage and workshop are reached only from outside; 12 of 12 on two storeys).
- **Path approval before rendering:** `camera_path.py --preview` draws the orbit and, per storey, the walk on the approval plan's 2 m grid with numbered stops; the skill shows it and asks to approve or change the path (`--skip`, `--order`, `--radius`, `--height`, `--cw`) before any Blender work.
- New Blender pass `scripts/blender/doors.py` (run by `run_all.py`): splits the merged door leaves without edit-mode operators, puts each pivot on its hinge and keys a 95° swing toward the next room; the front-door handle swings with its leaf.

## 1.3.0 (2026-11-07)
- **Reference grid on the approval plan:** `plan2d_simple.py` draws a light lettered grid (columns A, B, C… west → east; rows 1, 2, 3… top → bottom; labels on all four sides) so the user can say where things go ("pool in K14", "garage from C3 to G5"). 2 m squares by default, `PLAN_GRID_STEP` / `PLAN_GRID=0` to override. Writes `<png>.grid.json` (cell → scene x/z) and an `A-GRID` layer in the DXF; the skill explains how to turn a cell into metres and confirm it.
- **Model only = no video questions:** when the user chooses only the 3D model (in the request, the intake or an earlier answer), the approval gate asks the approval question alone and the skill never asks the video length, resolution or render time; Step 8 and `drone-video` are skipped unless the user raises the video again.
- **Packaging (plugin review): no more `exec()` in the Blender pipeline.**
  - shader-node helpers moved from `materials.py` to `scripts/blender/nodes.py`, and `scatter_group` from `setup.py` to `scripts/blender/scatter.py`; the passes `import` them instead of exec'ing `materials.py` or slices of `setup.py`;
  - `run_all.py` runs each pass file with `runpy.run_path(..., init_globals={"PARAMS": P})`; entry point is now `runpy.run_path(r"<scripts>/blender/run_all.py", init_globals={"PARAMS": {...}})["result"]`.

## 1.2.0 (2026-11-06)
- Video resolution question: 1920×1080, 1600×900 (recommended) or 1280×720, each with its estimated render time for 15 / 30 / 60 s (RTX 4060 reference; 1600×900 measured, the others scaled by pixel count). Asked in the approval gate and in `/drone-video`; the estimate is replaced by the measured test-frame time before launching.

## 1.1.2 (2026-11-03)
- **Packaging (plugin review):**
  - the sky is now `scripts/web/tex/sky.jpg` (79 KB, sRGB at 1/4 radiance) instead of a 2 MB base64 `sky.txt`; `engine.js` decodes it back to linear half-float for the environment map and no longer needs `RGBELoader`;
  - author is now "Paulo Silva" in `plugin.json`, matching the marketplace owner;
  - `setup_workspace.sh` pins ezdxf to `v1.4.5` instead of cloning `master`.

## 1.1.1 (2026-11-02)
- **Fix (Blender pipeline):** `tweaks.py`, `tweaks2.py`, `tweaks4.py` and `terrain.py` imported the `materials.py` helpers (`HELPERS_ONLY`) without passing `PARAMS`, so `materials.py` failed with `KeyError: 'dir'` and `run_all.py` stopped after the first pass. The helpers namespace now carries `PARAMS`, and `materials.py` no longer requires `dir` when imported as helpers.

## 1.1.0 (2026-11-01)
- **Elevations & section:** `elevations.py` draws the four elevations (titled by true bearing, with level / eave / ridge marks, finished and natural ground) and a section through the stair. Output: PNG per view, one sheet and a layered DXF.
- **Style presets:**
  - `styles/` holds `portuguese-contemporary`, `white-minimal`, `rural-stone` (terracotta roof) and `nordic-timber`;
  - `project.json "style"` takes a preset name or an inline object;
  - `style_from_colors.py` turns colours sampled from style photos into a preset;
  - the GLB carries the style into Blender; an optional `restyle` pass handles older GLBs.
- **Sun & daylight report:** `sun_report.py` computes direct-sun hours per room through its exterior glazing on 21 Mar / 21 Jun / 21 Dec, with occlusion by walls, roofs, the designed ground and trees. It writes ground sun-hour maps and flags rooms with little winter sun or long summer sun on west glazing.
- **Two storeys:**
  - schema: `storey` on any element, `floors[].holes` for stair voids, `railings` and balconies;
  - 3D page: storey selector (cut-away), walk mode across storeys, glass balustrades;
  - per-storey plans: `storey_filter.py`, with a "down" arrow on upper plans;
  - QA: headroom over the stair, guards at voids and upper terraces, low glazing upstairs;
  - new example: `examples/two-storey/`.
- **Tests:**
  - `navtest.js` takes a route file (`NAV_ROUTE`);
  - `shot2.js` accepts `js:` actions;
  - page loads tolerate slow machines.
- New icon and GitHub banner (designed in Canva; flat SVG versions kept in `assets/`).

## 1.0.0 (2026-11-01): first community release
- Packaged as a Claude plugin with three skills: `floorplan-to-3d-house` (full workflow), `validate-plan` (QA + 2D plan) and `drone-video` (Blender video).
- Self-contained package: scripts, web engine, CC0 textures (Poly Haven), Blender passes, and an invented reference example (synthetic site).
- `project.json` drives:
  - name and texts;
  - UI language (`en`, `pt-PT`);
  - latitude, north, area cap, setbacks;
  - camera views, walk start, garden lights and level labels.
- Intake: optional 1–2 photos (style / site) and optional address or GPS, with privacy defaults (address never embedded in the page).
- Mandatory 2D approval gate before any 3D work; the video question moved there.
- `validate_layout.py`: area cap, setbacks, stair riser/going/2R+G/width/top landing, door widths, room sizes, corridors, trees vs buildings.
- `plan2d_simple.py`: localised approval plan with setbacks below the minimum flagged.
- Engine fixes:
  - stair treads render as steps;
  - terrain stays under slabs (rooms below garden level, under stairs).
- Blender:
  - distance haze (mist-pass compositor) and smaller, denser far trees;
  - doors opening on walkthrough paths;
  - idempotent `final.py`;
  - render time measured, not guessed.
