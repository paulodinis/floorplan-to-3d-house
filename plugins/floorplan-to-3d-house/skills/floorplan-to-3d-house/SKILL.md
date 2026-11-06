---
name: floorplan-to-3d-house
description: >
  This skill should be used when the user shares a house site plan or floor plan (PDF or DXF) and asks to
  "make a 3D model of my house", "convert this plan to DXF", "redesign this house on my plot",
  "show me the house in 3D", "walk through the house", "export the plan to GLB" or "make a drone video of the house",
  or types /floorplan-to-3d-house. Runs the full workflow: DXF, simplified 2D plan for approval, interactive 3D page,
  GLB/3D-DXF exports and reference renders, elevations and section, a sun & daylight report, optional Blender video.
  Supports two-storey houses and style presets from reference photos.
metadata:
  version: "1.2.0"
---

# Floor plan → DXF → 2D plan (approval) → 3D model → video

Turn an architect's plan of a house (site plan or floor plan) into an interactive 3D model, files for other tools, and optionally a photoreal drone video.

**Language.** Reply in the user's language and regional variant, for example European Portuguese if they write PT-PT. Write project files in that language too, using `lang` in project.json: `en` and `pt-PT` ship; add others in `scripts/web/i18n.json`. Skill files stay in English.

**Tone.** Label confidence: [Certain], [Likely] or [Assumption]. Always separate what was measured from the drawing from what was assumed or designed.

## Ground rules (always)
1. **Indicative only.** Every deliverable says "indicative proposal — not for construction or permit". Local zoning, building code and structure are for the user's architect or engineer. Never present the QA checks as code compliance.
2. **2D approval gate.** The order is: simplified 2D plan → explicit user approval → anything 3D. If nobody is there to approve, deliver the 2D plan, say what is pending and stop. Silence is not approval.
3. **Privacy.** An address, GPS point or site photos identify a home.
   - Ask before using them.
   - Keep them out of anything published unless the user asks: `show_address_on_page` is false by default, and `build_page.py` never puts the address in the page code.
   - Don't store them beyond the project folder.
4. **Honesty about gaps.** If the drawing lacks heights, a north arrow or a scale, say so. Ask, or state the assumption.

## Files in this skill
Paths below are relative to this skill's base directory (shown when the skill loads). The sibling skills `validate-plan` and `drone-video` reuse these scripts.
- `scripts/setup_workspace.sh`: one-time workspace setup. It copies the textures and fetches ezdxf and the three.js r160 test files.
- `scripts/cloud/`:
  - `pdf2dxf.py`: PDF → DXF
  - `extract3d.py`: PDF → site.json, a reference implementation tuned on one drawing; adapt its colour constants to each new drawing
  - `masks.py`: ground masks from the PDF
  - `masks2.py`: ground masks from the layout
  - `plan2d.py`: plan DXF
  - `plan2d_simple.py`: plan PNG for approval, with setbacks, levels, north and area table
  - `storey_filter.py`: one storey's layout, for per-storey plans
  - `elevations.py`: 4 elevations + a section through the stair (PNG sheet + DXF)
  - `sun_report.py`: direct-sun hours per room and ground sun maps (equinox, both solstices)
  - `style_from_colors.py`: colours sampled from style photos → style preset
  - `validate_layout.py`: design QA
  - `build_page.py`: builds the 3D page
  - `navtest.js`: walk-collision test
  - `shot2.js`: screenshots
  - `export.js`: GLB export and renders
  - `tris2dxf.py`: 3D DXF
  - `gaps.py`: openings detection, faithful mode
  - `tex.py`: procedural textures
- `scripts/web/`: `template.html`, `engine.js` (three.js r160, Orbit/Walk/Drone navigation, sun study), `export_glb.js`, `i18n.json`, `tex/`.
- `scripts/blender/`: the Blender 4.2+/5.x pipeline (`run_all.py` + passes, `style.py`, `haze.py`, `final.py`, `encode.py`).
- `styles/`: style presets (`portuguese-contemporary`, `white-minimal`, `rural-stone`, `nordic-timber`).
- `examples/`: a complete reference project with `project.json`, `site.json`, `layout.json`, masks and `layout_generator_example.py`. Run it once to see the expected outputs. `examples/two-storey/` is the same site with a two-storey house (stair void, railings, balcony).
- `references/`: read these when the step needs them.
  - `intake.md`: question bank
  - `layout-schema.md`
  - `style-guide.md`: photos → materials
  - `multi-storey.md`
  - `blender-pipeline.md`
  - `qa-checklist.md`

## Step 0. Intake
Use AskUserQuestion: up to 4 questions per call, only what changes the result. Exact wording and options are in `references/intake.md`.
1. **Faithful or redesign?** If redesign, ask for the programme (bedrooms, office, garage…), a floor-area cap, and how to handle the slope; two levels is a good default.
2. **Storeys.** One / one with split levels / two.
   - Two storeys are supported: `storey` on each element, slab voids, railings, balconies, a storey selector, one plan per storey (`references/multi-storey.md`).
   - Three or more: the schema allows it but only two are tested; say so.
3. **Photos (optional, 1–2).** Reference images of the style they want, and/or photos of the site: street view of the plot, existing trees, neighbours, boundary walls. Style photos drive the materials (`references/style-guide.md`). Site photos validate trees, walls, terrain and the road.
4. **Location (optional).** Address or GPS point, with consent.
   - Latitude drives the sun study and the video lighting.
   - The region guides vegetation and typical materials.
   - The location can confirm north and the road side, but north still comes from the drawing.
   - The address never goes on the page unless the user asks.

Don't ask about style when style photos were given: pick the nearest preset in `styles/`, or derive one with `style_from_colors.py`, and set `"style"` in project.json (`references/style-guide.md`). Without photos, use `portuguese-contemporary`, and say so; offer the other presets in one line.

## Step 1. Workspace and inputs
Run `bash <skill>/scripts/setup_workspace.sh` in a new project work dir. Write `project.json` from `examples/project.json`: name, `lang`, location, `north_deg`, `plan_scale`, `area_limit`, `setback_min`, notes and views.
- **PDF:** `pdfinfo`, `pdfimages -list` (vector? raster scans need tracing; say so), `pdffonts`. Render at 110 dpi to look at it. Read the scale from the title block. `K = 25.4/72 × scale / 1000` converts PDF points to metres.
- **DXF:** skip the conversion. Check `$INSUNITS` and the coordinate magnitude (mm? national grid? subtract an origin near the house). List layers, explode blocks, render a preview, map the layers to plot/walls/roof/spot heights/trees/road. If the mapping isn't obvious, ask with a layer list and a thumbnail.
- **DWG:** can't be read here. Ask for a DXF export.
- **Validate the scale** against a known number, such as the plot area in the title block. If it doesn't match, stop and resolve it.

## Step 2. DXF from PDF (PDF input only)
`python3 scripts/cloud/pdf2dxf.py in.pdf out.dxf <scale>` writes metres, layers by colour and editable text. Verify by rendering the DXF next to the PDF. Tell the user:
- layers are by colour, not the architect's layers;
- dimensions are not associative;
- the architect has the original DWG.

## Step 3. Site → `site3d/site.json`
Extract the plot boundary, existing walls, the eave line, spot heights (`dd.ddd` texts, position = the decimal point), trees, the road and ceded strips. North comes from the needle or the survey text angle.
- PDF: adapt `extract3d.py`. Its colour constants come from one drawing; confirm them on each new drawing. Then run `masks.py` for the ground masks.
- DXF: write the equivalent from the layers and save it as `scripts/cloud/extract3d_dxf.py` for reuse.

Scene axes: x east, z south (sheet axes), y up, y = 0 at the main finished floor level.

## Step 4. Layout + simplified 2D plan
Author `site3d/layout.json` following `references/layout-schema.md`. `examples/layout_generator_example.py` shows the Python way.
- **Faithful mode:** wall poché → rectangles. Openings come from `gaps.py`, classified by what is on each side.
- **Redesign:**
  - respect the plot, ceded strips, setbacks and the area cap;
  - follow the slope with split levels;
  - existing trees: keep them, or list them as removed or transplanted.

Run, in order:
1. `python3 scripts/cloud/validate_layout.py project.json --md export/qa.md`. Fix the errors, or present each one as a decision for the user.
2. `python3 scripts/cloud/plan2d.py export/plan.dxf /tmp/x.png` writes the DXF with layers A-WALL, A-GLAZ, A-DOOR, A-ROOM…
3. `python3 scripts/cloud/plan2d_simple.py site3d/layout.json site3d/site.json export/plan_v<n>.png export/plan.dxf site3d/tex/mask1.png` writes the approval PNG and adds setback dimensions and north to the DXF.

Two storeys: run steps 2–3 once per storey after `python3 scripts/cloud/storey_filter.py site3d/layout.json <k> site3d/layout_s<k>.json --label "<name>"` (`LAYOUT_JSON=site3d/layout_s<k>.json` for plan2d.py). See `references/multi-storey.md`.

Look at the PNG with Read before showing it: labels, door swings, setbacks.

## Step 5. Approval gate (mandatory stop)
Send the PNG and DXF. Summarise:
- programme and areas;
- measured vs assumed;
- the QA errors and warnings;
- 2–4 debatable points, such as tight passages, area near the cap, trees affected or setbacks below the minimum.

Then ask one AskUserQuestion with two questions, plus a third when a video is wanted or likely:
- **Approve the 2D plan?** "Approved, go to 3D" / "Approved with small changes (describe)" / "Change and show again".
- **Blender video at the end?**
  - No / 10 s / 15 s (recommended) / 30 s / 60 s, plus a custom length.
  - Only offer it if Blender with the MCP add-on is available on the user's machine.
  - The time estimate comes from a measured test frame (Step 8). Before measuring, give a range.
- **Video resolution?** (if a video may be wanted) Three options, each with the estimated time for the length: 1920×1080 (~45 s/frame), 1600×900 (recommended, ~31 s/frame measured) and 1280×720 (~20 s/frame), RTX 4060 reference. Table in `references/blender-pipeline.md`. If the answer to the video question is "No", ignore it.

On "Change": update the layout, bump `v<n>`, rerun QA and repeat. Never take a closed question as approval.

## Step 6. 3D page
1. `python3 scripts/cloud/masks2.py`, then `plan2d.py ... ground` → `site3d/tex/plan_v2.jpg`.
2. `python3 scripts/cloud/build_page.py project.json` → `site3d/publish.html` (and `page.html` for tests).
3. Test:
   - `NAV_ROUTE=route.json node scripts/cloud/navtest.js` walks a route of `[x, z, "label"]` waypoints (gate → door → corridor → stair → rooms → terrace → garden; up the stair on two storeys). Without `NAV_ROUTE` it runs the example's route.
   - `node scripts/cloud/shot2.js '[{"actions":["#v-street"],"out":"tmp/s.png"}]'`. Actions are CSS selectors to click, or `js:<code>` (for example `js:window.__storey("0")`).
   - Chromium flags: `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`, about 3 min per shot.
4. Publish `site3d/publish.html` and every file in `site3d/tex/` with the Artifact tool. It must be a full `<!DOCTYPE html>` document. `.hdr` is not served, so the sky ships as `sky.jpg` (sRGB at 1/4 of its HDR radiance; `engine.js` restores the range). Republish to the same link.

## Step 7. Exports and AI pack
1. `python3 scripts/cloud/build_page.py project.json --export`.
2. `MODEL_NAME=<name> node scripts/cloud/export.js x export glb` → GLB + `tris.json`.
3. `... renders` → 5 views at 1920×1080.
4. `python3 scripts/cloud/tris2dxf.py export/tris.json export/<name>_3d.dxf <ezdxf/src>` writes one layer per material, Z = real level.
5. `PROJECT_JSON=project.json python3 scripts/cloud/elevations.py export/elevations` → four elevations (titled by true bearing), a section through the stair, `elevations.png` and `elevations.dxf`. Look at the sheet before sending.
6. **Sun & daylight** (needs `location.lat`; ask for it, or use the region's latitude and say so): `PROJECT_JSON=project.json python3 scripts/cloud/sun_report.py export/sun` → `sun_report.md` (direct-sun hours per room through its exterior glazing on 21 Mar / 21 Jun / 21 Dec, solar time) and `sun_ground.png`. Present the 2–3 points it flags (rooms with < 2 h in winter, west glazing with long summer sun) and its limits: clear sky, neighbours not modelled, not an energy or daylight-factor calculation.

Zip:
- the GLB, the 3D DXF, the plan DXF + PNG;
- the renders;
- `PROMPT.txt`, in English plus the user's language: style prompt, negative prompt, per-view hints, video prompt;
- `README.txt`: units and axes, measured vs proposed, credits;
- the QA report, the elevations sheet + DXF and the sun report.

Explain that AI video tools don't take GLB and don't keep dimensions. Use the renders or the video as references.

## Step 8. Blender video (optional, only if the user asked)
See `references/blender-pipeline.md`.
1. Write `params.json`: dir, glb, camera keys, sun, haze, frames, resolution.
2. Run `run_all.py` in a background Blender process, not inside the MCP call; it takes longer than the MCP timeout.
3. Plan the camera path:
   - 6–8 keys;
   - check canopy clearance;
   - for walkthroughs, open the doors on the path; glTF objects use quaternions, so set `rotation_mode='XYZ'` before keying.
4. Render 5–6 test frames at 50 %, look at them, fix what's wrong.
5. **Measure** seconds per frame, then quote frames × s/frame.
6. Launch the final render plus the `encode.py` watcher. Schedule a check, if the host supports it, and deliver the MP4.
7. Tell the user to keep the PC awake.

## Closing summary
- What was done.
- Where the files are.
- Measured vs inferred.
- What to validate with a professional: local plan and ratios, setbacks, structure of retaining walls, heights.

## Known pitfalls
- **Shell:** never use `pkill -f <pattern>` in a command that contains the pattern; it kills its own shell.
- **Masks:** RGB, never RGBA.
- **Terrain:** it must stay under slabs inside buildings; `engine.js` `underSlab()` handles it, including stairs.
- **Stair mesh:** one block per tread. Stacking full-length blocks hides the steps.
- **Blender 5.x:**
  - glTF import breaks on `KHR_materials_volume`; `run_all.py` strips it.
  - The compositor is `scene.compositing_node_group` with a Group Output node.
  - Set `media_type='VIDEO'` before choosing FFMPEG.
  - `read_homefile(use_empty=True)` instead of the factory reset.
- **Asphalt:** the asphalt mesh edge is saw-toothed (raster origin). Keep low cameras off that edge, or rebuild the road polygon.
- **Engine geometry:** `engine.js` assumes stairs run along x (top at `x0`) and that terraces and retaining walls are x-lines. Roofs are hip-only. See the roadmap in `references/multi-storey.md` and `references/layout-schema.md`.
- **Comments in one-line edits:** when patching a Python line, never append a `# comment` before a `;`-joined statement: the statement becomes part of the comment.
- **Style:** the GLB carries the page's style. Don't also run the Blender `restyle` pass on it, or the tint applies twice.
