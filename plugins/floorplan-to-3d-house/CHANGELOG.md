# Changelog

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
