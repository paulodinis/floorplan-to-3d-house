# Two or more storeys: status and roadmap

**Today:**
- Supported: one storey plus split levels, with any number of `level` values, slabs at different `y`, and straight stairs between them.
- Not supported: floors stacked on top of each other with a real ceiling slab, stair voids, balconies, or per-floor plans and views.

## Interim approach (works now, tell the user it is approximate)
1. Model the upper floor as extra `walls` with `y0 = upper_ffl - main_ffl`, `floors` at that `y`, and `rooms` with `level = upper_ffl`.
2. Put the roofs only on the top level. Add a flat "slab" floor at the upper level to close the ground floor; cut a rectangle out of it for the stair void.
3. Draw the stairs as straight runs along x. U-shaped stairs = two runs plus a landing floor.
4. The 2D approval plan shows the ground floor. Make a second plan by temporarily filtering the layout to the upper walls, floors and rooms; this is a manual step.
5. Walk mode works if each stair's `ytop`/`ybot` matches the slabs.

## Proposed roadmap (for contributors)
1. **Schema:**
   - `levels: [{id, name, ffl, height, slab_t}]`;
   - every wall, floor, room, opening and furniture item gets `level`, and `y` comes from it;
   - `voids: [{level, poly}]` for stair and double-height openings.
2. **Stairs:**
   - `{type: straight|L|U, origin, dir, width, risers, landings[]}`;
   - automatic void in the slab above;
   - QA checks for headroom ≥ 2.0 m under the slab and Blondel 2R+G 60–66 cm.
3. **2D:**
   - one approval plan per level (`plan2d_simple.py --level`);
   - a schematic section through the stair;
   - area table per level (gross / net);
   - stacked-wall check (upper walls bearing on lower walls or beams).
4. **3D page:**
   - level selector that shows up to level N (cut-away of the floors above);
   - Walk mode across levels;
   - balconies and roof terraces with 1.10 m guard rails;
   - flat-roof support.
5. **QA:**
   - guard rails;
   - window sill heights on upper floors (≥ 0.9 m or a guard);
   - stair clear width;
   - escape route length (good practice, not code).
6. **Inputs:**
   - multi-page PDFs (one sheet per floor) aligned on common references (grid, stair, façade corner);
   - elevations and sections to read storey heights and the roof profile.
7. **Blender:** an interior camera path per level and a vertical cut for "dollhouse" shots.
