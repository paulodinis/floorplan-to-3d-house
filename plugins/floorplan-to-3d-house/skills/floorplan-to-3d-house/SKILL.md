---
name: floorplan-to-3d-house
description: >
  This skill should be used when the user shares a house site plan or floor plan (PDF or DXF) and asks to
  "make a 3D model of my house", "convert this plan to DXF", "redesign this house on my plot",
  "show me the house in 3D", "walk through the house", "export the plan to GLB" or "make a drone video of the house",
  or types /floorplan-to-3d-house. Runs the full workflow: DXF, simplified 2D plan for approval, interactive 3D page,
  GLB/3D-DXF exports and reference renders, elevations and section, a sun & daylight report, opens the model in Blender, optional Blender video.
  Supports two-storey houses and style presets from reference photos.
metadata:
  version: "1.7.0"
---

# Floor plan → 2D plan (approval) → 3D model → Blender → video

Turn an architect's plan of a house (site plan or floor plan) into an interactive 3D model, files for other tools, and optionally a photoreal drone video.

**Language.** Reply in the user's language and regional variant (European Portuguese for PT-PT). Project files follow `lang` in project.json (`en`, `pt-PT`; others via `scripts/web/i18n.json`). Skill files stay in English.

**Tone.** Label confidence: [Certain], [Likely] or [Assumption]. Keep what was measured from the drawing apart from what was assumed or designed.

## The flow and its stops
Intake → inputs → **2D plan → stop: approve?** → 3D page + exports → **stop: open in Blender?** (once per session) → video only if asked: **stop: approve the path** → test frames → launch.
Every change, at any point, goes back to a new 2D plan `v<n+1>` and its stop. Never treat silence as approval. If nobody is there, deliver what is done, say what is pending and stop.

## Ground rules
1. **Indicative only.** Every deliverable says "indicative proposal — not for construction or permit". Zoning, building code and structure are for the user's architect or engineer; the QA is good practice, not compliance.
2. **Privacy.** An address, GPS point or site photos identify a home: ask before using them, keep them out of anything published (`show_address_on_page` false), store them only in the project folder.
3. **Honesty about gaps.** Missing heights, north arrow or scale: ask, or state the assumption.
4. **Ambiguous change requests: ask with the readings as options** before drawing ("same height" = floor level or eave? "attach" = shared wall or link?). One question with 2–3 concrete options costs less than a wrong plan version.
5. **Keep the work files.** After every plan version, pack the work dir (`scripts/cloud/pack_work.py pack . export/work_v<n>.zip`) and put it next to the deliverables on the user's PC (`<Project>/v<n>/`). A new session starts by unpacking the latest `work_v<n>.zip`, never by rebuilding from a published page or a PDF.
6. **Cheap checks.** Read small images: `plan_v<n>.check.png` (not the full plan), one contact sheet for renders or test frames, text reports (`qa.md`, `sun_report.md`, pipeline/status JSON) instead of logs. Send the full images to the user; don't look at them again yourself.

## Files
Paths are relative to this skill's base directory. `validate-plan` and `drone-video` reuse these scripts.
- `scripts/setup_workspace.sh`: workspace setup (textures, ezdxf, three.js r160 test files).
- `scripts/cloud/`: `pdf2dxf.py`, `extract3d.py`, `masks.py`, `masks2.py` (inputs); `validate_layout.py`, `plan2d.py`, `plan2d_simple.py`, `storey_filter.py` (plan + QA); `build_page.py`, `export.js`, `tris2dxf.py`, `elevations.py`, `sun_report.py`, `style_from_colors.py` (3D + exports); `camera_path.py`, `camera_script.py` (video paths); `pack_work.py`; `shot2.js`, `navtest.js` (debugging); `gaps.py`, `tex.py`.
- `scripts/web/`: the 3D page engine. `scripts/blender/`: `pipeline.py` (build / test / final in one call), `run_all.py` + passes, `doors.py`, `open_in_blender.py`, `encode.py`.
- `styles/`: presets. `examples/`: a complete one-storey and a two-storey project.
- `references/`: `intake.md`, `inputs.md` (Steps 1–3), `plan-and-grid.md` (Step 4), `exports.md` (Steps 6–7, pitfalls), `blender-pipeline.md` (Blender, video), `layout-schema.md`, `style-guide.md`, `multi-storey.md`, `qa-checklist.md`.

## Step 0. Intake
One AskUserQuestion (up to 4 questions, only what changes the result; wording in `references/intake.md`): faithful or redesign (programme, area cap, slope), storeys, optional style/site photos, optional location (with consent). Style photos pick a preset (`references/style-guide.md`); without photos use `portuguese-contemporary` and say so.
If the user already has a project from this skill, skip the intake: unpack the latest `work_v<n>.zip` and go to the step they ask for.

## Steps 1–3. Inputs → `site3d/site.json`
Set up the workspace, write `project.json`, read the PDF or DXF, check the scale against a known number (plot area), make the DXF (PDF input only) and extract the site: boundary, walls, eave, spot heights, trees, road, ceded strips, north. DWG: ask for a DXF. Details: `references/inputs.md`.

## Step 4. Layout + 2D plan
Write `site3d/layout.json` (`references/layout-schema.md`); redesigns respect the plot, setbacks, area cap and slope. Then `validate_layout.py`, `plan2d.py` (DXF) and `plan2d_simple.py` (approval PNG with setbacks, levels, furniture, reference grid). During change rounds only the PNG is needed (`-` instead of the DXF). Two storeys: one plan per storey. Commands, grid cells and furniture checks: `references/plan-and-grid.md`.

## Step 5. Approval gate (mandatory stop)
Send the PNG (and DXF once approved). Tell the user they can point at places by grid cell ("C4"). Summary, short: programme and areas; measured vs assumed; QA errors/warnings; 2–4 debatable points.
One AskUserQuestion: **"Continue to 3D?"** — "Yes" / "Change the plan (describe; grid cells welcome)" / "Stop here". Ask about the video only later, and only if the user wants one (Step 8). On a change: update the layout, `v<n+1>`, PNG, ask again.

## Steps 6–7. 3D page, exports
Masks, `build_page.py`, publish the page with the Artifact tool (same link on republish). Then one `export.js … all` session (GLB + 5 renders, which double as the visual check), `tris2dxf.py`, and for the approved version the elevations and sun report. Zip: GLB, 3D DXF, plan DXF + PNG, renders, elevations, sun report, QA, `PROMPT.txt` (English + user's language), `README.txt` (units, axes, measured vs proposed, credits). Pack `work_v<n>.zip`. Details: `references/exports.md`.

## Step 7b. Open in Blender (stop, once per session)
Ask: **"Open the 3D model in Blender on your computer?"** — "Yes (Recommended)" / "I don't have Blender" / "Not now". If computer use is available, check the install first (`computer_resolve_access(["Blender"])`) and say what was found; still ask. "I don't have Blender" skips this and the video (the GLB opens in any glTF viewer; Blender is free). After "Yes", open later versions without asking.
Open it with `scripts/blender/open_in_blender.py` through the Blender MCP when connected (fallbacks and MCP troubleshooting: `references/blender-pipeline.md`). Read `<name>_blender_open.json`; tell the user where the `.blend` is.

## Step 8. Video (only if the user asks)
Use the `drone-video` skill. It covers length and resolution, the automatic tour (`camera_path.py`) or the user's own shot list (`camera_script.py`), the path approval stop, test frames and the launch through `pipeline.py`.

## Closing summary (fixed block, ≤ 6 lines)
- **Done:** one line.
- **Files:** where (folder on the PC, page link).
- **Measured vs assumed:** one line.
- **To validate with a professional:** 2–3 items (zoning, setbacks, structure, heights).
- **Next:** the one question or option that remains, if any.
