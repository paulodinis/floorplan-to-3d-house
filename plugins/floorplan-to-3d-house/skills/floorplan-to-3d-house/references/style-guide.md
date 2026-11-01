# Style: from photos to materials

The look lives in two palettes:
- **3D page:** the `M = { ... }` material table in `scripts/web/engine.js`, plus the textures in `scripts/web/tex/` and the procedural ones in `scripts/cloud/tex.py`.
- **Blender:** `scripts/blender/materials.py`. The node setups are keyed by the GLB material names: Roof_*, Wall_Render, Stone_Cladding, Timber_Slats, Window_Frame, Glass, Paving_*, Ground_*.

Change colours and parameters there. Keep the material names, because the GLB → Blender mapping depends on them.

## Reading a style photo (fill this table, show it to the user in one line)
| Element | Look for | Parameter |
|---|---|---|
| Roof | hipped / gable / flat; pitch; tile type and colour | `meta.pitch`, roof colour |
| Walls | render colour and texture; stone type, course pattern, tint | Wall_Render colour, Stone tint and scale |
| Accents | timber slats or cladding; tone | Timber colour, slat spacing |
| Openings | frame colour (anthracite, white, wood); sill heights; full-height glazing | Window_Frame colour; ops `sill`/`head` |
| Eaves | depth, soffit colour | roof `rect` overhang, soffit colour |
| Ground | paving (pavers, large slabs, gravel); planting (lawn, lavender, olives) | zones and Paving_* colours |
| Light | time of day in the photo | `sun.hour` in Blender params, slider default |

## Bundled preset: "Portuguese contemporary" (default when no photos)
- **Roof:** low hipped roof (16°), dark charcoal flat tiles, wide white eaves.
- **Walls:**
  - sand-finish white render;
  - warm limestone in irregular courses;
  - stone-clad terrace columns.
- **Timber and openings:**
  - warm vertical timber slats on the garage door and flanking the entrance;
  - dark wood front door;
  - anthracite frames with floor-to-ceiling glazing.
- **Outside:** grey pavers at the drive, large pale slabs on the terraces, white gravel with lavender, lawn, hedges, a low stone wall with gate pillars, multi-trunk olives.
- **Light:** 21 June around 18:45 solar time, warm low sun, interiors and bollards lit.

Roadmap: move palettes into `style.json` presets (for example contemporary-white, rural-stone, nordic-timber), read by both engine.js and materials.py.
