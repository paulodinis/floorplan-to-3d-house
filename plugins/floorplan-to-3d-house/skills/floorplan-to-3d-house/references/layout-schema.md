# layout.json schema (v2)

Units are metres. Scene axes: **x east, z south** (sheet axes), **y up**, with y = 0 at the main finished floor level (`site.meta.ffl`, absolute). Rects are `[x0, z0, x1, z1]`; polygons are `[[x, z], ...]`.

| Key | Shape | Notes |
|---|---|---|
| `meta` | `{ffl_*, area_total, area_habitacao, plot_area, ceded_area, cut_x, pitch, retaining_cuts}` | `pitch` is the roof pitch in degrees. `retaining_cuts: [[x, z0, z1]]` gives the stretches where a house wall replaces a terrace retaining wall. |
| `plot`, `ceded` | polygon | Final plot and the strip ceded to the public domain. |
| `blocks` | `{id: {name, rect, level, area}}` | Gross volumes. They drive the areas table, the setbacks, terrain clamping and walk floors. `level` is absolute. |
| `walls` | `[{a, b, t, y0, h, mat, ops, tag}]` | Axis-aligned centrelines. `t` is the thickness (0.30 exterior, 0.12 interior). `mat`: `render`, `render_in` or `stone`. `y0` can be below 0 for walls standing on a lower floor. |
| `walls[].ops` | `[{o, w, kind, sill, head}]` | Distance `o` from `a`, width `w`. `kind`: `window`, `slide`, `door_glass`, `front`, `door`, `garage`, `open`. `sill`/`head` are relative to the wall's `y0`. |
| `columns` | `[{x, z, y0, h, s}]` | Square columns. |
| `roofs` | `[{rect, eave, name}]` | Hipped roof over the union of rectangles that share an eave height. Lower roofs can slide under higher eaves; valleys come out on their own. |
| `floors` | `[{poly, y, mat, name}]` | Slabs (0.35 thick). `mat`: `oak`, `stone_floor`, `porcelain`, `concrete` or `terrace`. |
| `stairs` | `[{x0, x1, z0, z1, ytop, ybot, n}]` | Straight run **along x**, top at `x0`, `n` risers, one block per tread. Leave ≥ 0.9 m of level floor before the top step. |
| `rooms` | `[{name, poly, level, area}]` | Labels and areas on the 2D plan. Names steer the QA type checks (EN or PT keywords). |
| `grading` | `{upper, lower, t1, t2, x_w1, x_w2, x_w3, upper_slope_from_z, upper_slope}` | Designed ground: terraces stepping **along x** at `x_w*`. |
| `retaining` | `[{x, name}]` | Stone retaining walls on the x-lines, clipped to the plot. |
| `garden_steps` | `[{x, z0, z1}]` | Outdoor steps across a retaining wall. |
| `gate`, `ped_gate` | `{z0, z1}` | Gaps in the boundary wall on the road side (west). |
| `zones` | `{drive, stone, gravel, beds: [polygon]}` | Ground finishes; later layers win. |
| `trees` | `[{x, z, r}]` | Olive-type trees; `r` is the crown radius. |
| `furniture` | `[{b: rect, y0, h, mat, name}]` | Boxes. Names containing sofa, rug, coffee table or lounger get special treatment. |
| `slats` | `[{x0, x1, z0, z1, y0, y1}]` | Timber slat panels on façades. |
| `room_lights` | `[[x, z, y]]` | Interior lights. |
| `railings` | `[{a, b, y, h, storey}]` | Glass balustrades (`h` default 1.0) on void edges and balconies. Count as guards in the QA and block walk mode. |
| `*.storey` | integer | Any wall, floor, room, block, roof, stair, slat, column, furniture item or railing; 0 = ground (default). Drives the storey selector, per-storey plans and the QA. |
| `floors[].holes` | `[polygon]` | Voids cut out of a slab (stair void, double height). |

## Known geometric assumptions (roadmap)
- The road / main access is on the **west** side (`cut_x`, gates on the west line). Other orientations: rotate the scene so the road is west, or generalise `cut_x`.
- Terraces and retaining walls run along x; stairs run along x.
- Stairs run along x (top at `x0`). Two storeys are supported (see multi-storey.md); the roof generator is hip-only.
