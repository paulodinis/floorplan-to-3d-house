# Two or more storeys (v1.1)

## What is supported
- Any element can carry `"storey": k` (0 = ground, the default): walls, floors, rooms, blocks, roofs, stairs, slats, columns, furniture, railings.
- **Floors with voids:** `floors[].holes: [polygon]` cuts stair voids and double-height spaces out of a slab. The 3D page, walk mode, QA and the section all respect them.
- **Railings / balustrades:** `railings: [{a, b, y, h = 1.0, storey}]` (glass + handrail). They block walking and count as guards in the QA.
- **Balconies:** a `terrace` floor on storey ≥ 1 plus railings on its free edges; posts as `columns`.
- **3D page:** a *Storey* selector appears when there is more than one storey (cut-away: shows storeys up to k; the roof only with the top storey). `window.__storey("0")` in tests. Walk mode climbs stairs between storeys.
- **2D plans per storey:** `storey_filter.py` + `plan2d.py` (`LAYOUT_JSON`) + `plan2d_simple.py`. On the upper plan the stair arrow reads "down".
- **QA:** headroom over the stair (≥ 2.0 m under the slab above), guards at voids and on upper terraces, low glazing on upper floors without a balcony or railing (sill ≥ 0.9 m).
- **Elevations and section:** `elevations.py` draws all storeys, balconies and railings; the section cuts the slab at the void. `--storey k` draws one storey.
- **Sun report:** works per room on every storey (windows matched to rooms by level).

## How to model it (see `examples/two-storey/`)
1. One block per storey with the same rect (or the upper one smaller / cantilevered), `level` = that storey's FFL, `storey` = k. The areas table sums all storeys.
2. Ground-floor exterior walls go from `y0 = 0` to the next floor (`h` = floor-to-floor); upper walls start at `y0 = floor-to-floor`, `storey: 1`, up to the eaves.
3. The upper slab: `{"poly": exterior-wall centrelines, "y": H, "holes": [void], "storey": 1}`. Stop it at the wall centrelines, not the outer face, or its edge flickers through the façade. Size the void from the headroom rule: treads closer than 2.0 m to the slab underside must be under the void.
4. Stairs: straight runs along x, `storey` = the storey they start from, top at `x0`. Leave ≥ 0.9 m of floor in front of the top step. U-shaped stairs = two runs plus a landing floor.
5. Roofs only on the top storey (`storey` = top), eave = upper FFL - main FFL + wall height.
6. Rooms with `level` = their storey's FFL and `storey`.

## Workflow differences
- Step 4: run the plan pair once per storey:
  ```
  python3 storey_filter.py site3d/layout.json 1 site3d/layout_s1.json --label "First floor"
  LAYOUT_JSON=site3d/layout_s1.json python3 plan2d.py export/plan_s1.dxf /tmp/x.png
  python3 plan2d_simple.py site3d/layout_s1.json site3d/site.json export/plan_s1_v<n>.png export/plan_s1.dxf site3d/tex/mask1.png
  ```
- Step 5: send every storey plan; the approval covers all of them.
- Step 6: add a walk route that climbs the stair (`NAV_ROUTE=route.json node navtest.js`) and screenshots per storey (`"actions": ["js:window.__storey(\"0\")"]`).

## Still not supported (roadmap)
- Stairs along z, L/U stairs as one object, spiral stairs.
- Flat roofs and roof terraces (model a terrace floor + railings and no roof over it; the roof generator is hip-only).
- Stacked-wall check (upper walls bearing on lower walls or beams), escape-route length.
- Multi-page PDFs (one sheet per floor) aligned automatically.
- Blender: interior camera path per storey and dollhouse cut-away.
