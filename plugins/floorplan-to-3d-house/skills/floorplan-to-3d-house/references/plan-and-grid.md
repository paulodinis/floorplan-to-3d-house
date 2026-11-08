# Layout, QA and the 2D approval plan (Step 4 in detail)

## Layout + simplified 2D plan
Author `site3d/layout.json` following `references/layout-schema.md`. `examples/layout_generator_example.py` shows the Python way.
- **Faithful mode:** wall poché → rectangles. Openings come from `gaps.py`, classified by what is on each side.
- **Redesign:**
  - respect the plot, ceded strips, setbacks and the area cap;
  - follow the slope with split levels;
  - existing trees: keep them, or list them as removed or transplanted.

Run, in order:
1. `python3 scripts/cloud/validate_layout.py project.json --md export/qa.md`. Fix the errors, or present each one as a decision for the user.
2. `python3 scripts/cloud/plan2d.py export/plan.dxf /tmp/x.png` writes the DXF with layers A-WALL, A-GLAZ, A-DOOR, A-ROOM…
3. `python3 scripts/cloud/plan2d_simple.py site3d/layout.json site3d/site.json export/plan_v<n>.png export/plan.dxf site3d/tex/mask1.png` writes the approval PNG and adds setback dimensions, north and the reference grid (layer `A-GRID`) to the DXF. It also writes `export/plan_v<n>.grid.json`.

Two storeys: run steps 2–3 once per storey after `python3 scripts/cloud/storey_filter.py site3d/layout.json <k> site3d/layout_s<k>.json --label "<name>"` (`LAYOUT_JSON=site3d/layout_s<k>.json` for plan2d.py). See `references/multi-storey.md`.

`plan2d_simple.py` also writes `export/plan_v<n>.check.png`, a ~1000 px crop of the buildings. **Read that one, not the full PNG**, to check labels, door swings, furniture and setbacks; send the full PNG to the user.

Furniture is drawn on the plan (light boxes; `PLAN_FURNITURE=0` hides it) and `validate_layout.py` warns when a piece sits in a door swing, in front of a low window or glazed door, or in an opening. Kitchen counters and laundry machines under a window sill are allowed. Optional `plan_cars: [[x0, z0, x1, z1]]` in the layout draws car outlines in garages (plan only).

**Reference grid.** The plan carries a light grid: letters = columns (west → east), numbers = rows (top → bottom of the sheet), labelled on all four sides. Squares are 2 m by default; `PLAN_GRID_STEP=<m>` changes it, `PLAN_GRID=0` turns it off. Past column Z the letters go on AA, AB… When the user places something by cell ("a piscina em K14", "sofá no canto nordeste de J9", "garagem de C3 a G5"):
- read `plan_v<n>.grid.json`: cell `<L><n>` spans x ∈ [x0 + i·step, x0 + (i+1)·step], z ∈ [z0 + (n−1)·step, z0 + n·step] (i = column index from 0, scene x east, z south);
- a cell alone = its centre; a corner word = that corner of the cell, on the sheet (top = row 1 side); a range = the rectangle from the first cell to the last;
- confirm in one line with the metres it resolves to and what it touches (wall, setback, tree), then apply it to `layout.json`.

