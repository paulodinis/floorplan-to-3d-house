# 3D page, exports and AI pack (Steps 6–7 in detail)

## Step 6. 3D page
1. `python3 scripts/cloud/masks2.py`, then `plan2d.py ... ground` → `site3d/tex/plan_v2.jpg`.
2. `python3 scripts/cloud/build_page.py project.json` → `site3d/publish.html` (and `page.html` for tests).
3. Test with the Step 7 renders: they load the page once and give the five views (aerial, street, garden, interior, plan) at the same time as the GLB. Don't take separate screenshots for checking.
   - Debugging only: `node scripts/cloud/shot2.js '[{"actions":["#v-street"],"out":"tmp/s.png"}]'` (actions are CSS selectors or `js:<code>`), about 3 min per page load.
   - Walk mode: `NAV_ROUTE=route.json node scripts/cloud/navtest.js` (text output, no images) when the layout changed doors, stairs or walls on the walking path.
   - Chromium flags: `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`.
4. Publish `site3d/publish.html` and every file in `site3d/tex/` with the Artifact tool. It must be a full `<!DOCTYPE html>` document. `.hdr` is not served, so the sky ships as `sky.jpg` (sRGB at 1/4 of its HDR radiance; `engine.js` restores the range). Republish to the same link.

## Step 7. Exports and AI pack
Elevations and the sun report go with the version approved for 3D (or when asked), not with every plan revision. Present the sun report from `sun_report.md` (text); don't read `sun_ground.png` unless the user asks about it.

1. `python3 scripts/cloud/build_page.py project.json --export`.
2. `MODEL_NAME=<name> node scripts/cloud/export.js x export all`: **one browser session** → GLB + `tris.json` + 5 renders at 1920×1080. Run it in the background and do steps 4–6 meanwhile. To check the renders, make one contact sheet (PIL, 5 × 384 px) and read that, not five full images.
4. `python3 scripts/cloud/tris2dxf.py export/tris.json export/<name>_3d.dxf <ezdxf/src>` writes one layer per material, Z = real level.
5. `PROJECT_JSON=project.json python3 scripts/cloud/elevations.py export/elevations` → four elevations (titled by true bearing), a section through the stair, `elevations.png` and `elevations.dxf`. Look at the sheet once, at reduced size.
6. **Sun & daylight** (needs `location.lat`; ask for it, or use the region's latitude and say so): `PROJECT_JSON=project.json python3 scripts/cloud/sun_report.py export/sun` → `sun_report.md` (direct-sun hours per room through its exterior glazing on 21 Mar / 21 Jun / 21 Dec, solar time) and `sun_ground.png`. Present the 2–3 points it flags (rooms with < 2 h in winter, west glazing with long summer sun) and its limits: clear sky, neighbours not modelled, not an energy or daylight-factor calculation.

Zip:
- the GLB, the 3D DXF, the plan DXF + PNG;
- the renders;
- `PROMPT.txt`, in English plus the user's language: style prompt, negative prompt, per-view hints, video prompt;
- `README.txt`: units and axes, measured vs proposed, credits;
- the QA report, the elevations sheet + DXF and the sun report.

Explain that AI video tools don't take GLB and don't keep dimensions. Use the renders or the video as references.


## Known pitfalls (all steps)
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
