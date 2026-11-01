# Changelog

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
