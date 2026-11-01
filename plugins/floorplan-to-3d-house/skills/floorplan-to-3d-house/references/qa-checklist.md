# QA checklist

Automated by `scripts/cloud/validate_layout.py project.json --md export/qa.md`, with thresholds overridable in `project.json.qa`. These are good-practice defaults, **not a building-code check**.

| Check | Default | Severity |
|---|---|---|
| Total floor area vs `area_limit` | +0.5 % tolerance | error |
| Setback, nearest corner → each plot edge | `setback_min` = 3.0 m | error |
| Stair riser | ≤ 18 cm | error |
| Stair going | ≥ 27 cm | error |
| Stair 2R+G | 60–66 cm | warning |
| Stair width | ≥ 0.90 m | error |
| Level floor before the top step | ≥ 0.90 m | warning |
| Door / front door / garage door widths | 0.70 / 0.90 / 2.40 m | error |
| Bedroom area / narrowest side | 9 m² / 2.40 m | error / warning |
| WC area | ≥ 2.5 m² | error |
| Corridor / hall width | ≥ 0.90 m | error |
| Tree inside or against a building | n/a | error |
| Headroom over each tread under the slab above | ≥ 2.0 m (`headroom_min`) | error |
| Guard along void edges and upper terraces (railing or wall ≥ `guard_h`) | 1.0 m | warning |
| Upper-floor glazing / doors with sill < `upper_sill_min` and no balcony or railing | 0.9 m | warning |

## Manual checks before showing anything
- [ ] Scale validated against a known dimension or area.
- [ ] North confirmed (needle, survey text angle or the user).
- [ ] Walk test (`navtest.js`) passes; every room reachable; no furniture blocking a passage (< 0.8 m).
- [ ] Terrain doesn't poke through any slab (inspect the interior cut-away and lower rooms).
- [ ] Stairs show treads (screenshot from the bottom).
- [ ] Two storeys: walk route climbs the stair; each storey shown with the selector; one plan per storey.
- [ ] Doors on the camera path open in the Blender video.
- [ ] Renders and PNGs looked at with Read before sending.
- [ ] Address / GPS not visible on the published page unless the user asked.
