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

## Style presets (`styles/*.json`)
Set `"style"` in project.json to a preset name, or to an inline object with the same shape. `build_page.py` resolves it into the page (`PROJ.style_data`); the GLB exported from that page carries the colours, so the Blender video inherits them.

| Preset | Look |
|---|---|
| `portuguese-contemporary` | the default above (no tint) |
| `white-minimal` | brilliant white render, pale stone, white frames, light timber, pale grey roof |
| `rural-stone` | terracotta tiles, warm rubble stone, cream render, brown timber frames and doors |
| `nordic-timber` | dark grey render, dark timber, cool stone, near-black frames |

Shape:
```json
{"name": "Rural stone", "description": "...", "roof_tile": "terracotta",
 "pitch_hint": 28, "tint": {"stone": [0.86, 0.8, 0.7], "frame": [2.7, 1.8, 1.15]}}
```
- `tint`: RGB multipliers on the default material colours (1 = unchanged, > 1 lightens). Keys: render, render_in, stone, slats, garage, front, frame, soffit, roof, ridge, terrace, plinth, retain, oak.
- `roof_tile`: `flat_dark` (default) or `terracotta`.
- `pitch_hint`: advisory only. The real pitch is `layout.meta.pitch`; propose it to the user, don't change it silently.

### From style photos to a preset
1. Fill the table above from the photos and pick the nearest preset.
2. When the colours differ, sample them from the photo (render, stone, timber, frames, roof) and run:
   `python3 scripts/cloud/style_from_colors.py site3d/style.json --name "Client style" --roof terracotta --set render=#f1ede4 stone=#bfae93 slats=#8a5a36 frame=#ffffff`
3. Put the resulting object inline in project.json `"style"` and rebuild the page. Check a screenshot of the street view before showing it.
4. Tell the user in one line which preset or colours were used and that the colours are approximate (screen, sun and textures change them).

### Blender
Normally nothing to do: the GLB already carries the style. To restyle an existing GLB for the video without re-exporting, put the style object in `params.json` as `"restyle"`; the `style.py` pass (run by `run_all.py` before the haze) multiplies the Base Color of the matching materials.
