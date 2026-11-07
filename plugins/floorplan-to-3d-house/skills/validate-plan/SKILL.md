---
name: validate-plan
description: >
  This skill should be used when the user asks to "check my house layout", "validate the plan",
  "run the design QA", "check setbacks / stairs / room sizes", "regenerate the 2D plan" or types /validate-plan
  on a project made with floorplan-to-3d-house (a work dir with site3d/layout.json and project.json).
metadata:
  version: "1.3.0"
---

# Validate a house layout and regenerate the 2D approval plan

Reuse the scripts of the sibling skill `floorplan-to-3d-house`, in its `scripts/cloud/` folder. Below, `<FT>` is that skill's base directory: the parent of this skill's base directory, then `floorplan-to-3d-house`.

Reply in the user's language. Label confidence as [Certain], [Likely] or [Assumption]. Present the checks as good practice, never as building-code compliance.

## Steps
1. **Locate the project work dir.** It holds `site3d/site.json`, `site3d/layout.json` and `project.json`.
   - If there is none, say this skill works on a project created by `floorplan-to-3d-house`, and offer to start one.
   - If only the layout exists, write a minimal `project.json` from `<FT>/examples/project.json`. Ask for `area_limit` and `setback_min` if unknown, or state the defaults: no cap, 3.0 m.
2. **Run the QA:** `python3 <FT>/scripts/cloud/validate_layout.py project.json --md export/qa.md`. Exit code 1 means errors.
3. **Regenerate the plan DXF:** `PROJECT_JSON=project.json python3 <FT>/scripts/cloud/plan2d.py export/plan.dxf /tmp/x.png`. If ezdxf is missing, run `bash <FT>/scripts/setup_workspace.sh` first.
4. **Regenerate the approval PNG and add setbacks and north to the DXF:** `PROJECT_JSON=project.json python3 <FT>/scripts/cloud/plan2d_simple.py site3d/layout.json site3d/site.json export/plan_vN.png export/plan.dxf site3d/tex/mask1.png`. Increment N from the last plan in `export/`.
   - **Two storeys** (elements with `"storey"`): one plan per storey. First `python3 <FT>/scripts/cloud/storey_filter.py site3d/layout.json <k> site3d/layout_s<k>.json --label "<storey name>"`, then steps 3–4 with `LAYOUT_JSON=site3d/layout_s<k>.json` for plan2d.py, `site3d/layout_s<k>.json` as the layout argument of plan2d_simple.py, and `plan_s<k>` file names.
5. **Look at the PNG with Read** before sending it. Check:
   - overlapping labels;
   - door swings into walls;
   - orange setbacks (below the minimum).
6. **Deliver** the PNG, the DXF and `qa.md`. Summarise in 3–6 lines:
   - errors first, each phrased as a decision for the user (move, accept, ask the architect);
   - then warnings;
   - then one line with the totals: floor area vs cap, smallest setback.
7. **Thresholds:** they can be changed in `project.json` under `"qa"` (see `<FT>/references/qa-checklist.md`). Change them only when the user gives a local rule; say so in the summary.

Do not edit the layout in this skill unless the user asks. For design changes, go back to `floorplan-to-3d-house` Step 4 and its approval gate.
