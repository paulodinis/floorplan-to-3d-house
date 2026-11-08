# floorplan-to-3d-house: a Claude plugin

Turn a house **site plan or floor plan** (vector PDF or DXF) into:

1. a clean **DXF** of the drawing (metric, editable text);
2. a **simplified 2D plan for approval**, with dimensioned setbacks, levels, north, scale bar and area table;
3. an **interactive 3D model page**:
   - Orbit / Walk / Drone navigation, preset views and layers;
   - sun study by date and hour;
   - areas panel;
4. **exports**: GLB (glTF), a 3D DXF (one layer per material) and five reference renders, plus a prompt pack for AI image and video tools;
5. **elevations and a section** (PNG sheet + DXF) and a **sun & daylight report**: direct-sun hours per room and ground sun maps for the equinox and both solstices;
6. the model **opened in Blender** on your machine, if you say yes when asked (it checks that Blender is installed), saved as a `.blend` ready to explore or edit;
7. optionally, a **photoreal drone video** rendered on your own machine with Blender (Cycles), including a walkthrough with doors opening.

It works as a conversation: Claude asks a few questions, shows the 2D plan, waits for your **approval**, and only then builds the 3D and the video.

> Indicative proposals only, not for construction or permit applications. Local zoning, building codes and structure are for your architect or engineer.

## What you need
- Claude with code execution (Claude.ai / Claude desktop with Cowork, or Claude Code).
- Network access to GitHub (the setup script fetches ezdxf and three.js r160). Python 3 with pdfplumber, numpy, opencv-python and pillow; Node with Playwright and Chromium for tests and exports.
- Optional, for the video:
  - Blender 4.2+ (tested on 5.2) with the Blender MCP add-on;
  - a GPU;
  - a computer linked to Claude (Claude desktop app).

## What's inside
| Skill | Use it for |
|---|---|
| `/floorplan-to-3d-house` | The full workflow: intake → DXF → 2D plan for approval → 3D page → exports → model opened in Blender → optional video. It also triggers on its own when you share a plan. |
| `/validate-plan` | Re-run the design QA (setbacks, stairs, doors, room sizes, area cap, furniture clear of doors and windows) and regenerate the 2D approval plan for an existing project. |
| `/drone-video` | Make or redo the Blender drone / walkthrough video for an approved project: 15 / 30 / 60 s automatic tours, or your own shot list in words ("start at the door, rise, orbit, go into the suite, pivot 45° right…"). Doors open on the way. |

Scripts, web engine, CC0 textures, Blender passes, references and an invented example project live in `skills/floorplan-to-3d-house/`.

Each plan version's work files are packed into `work_v<n>.zip` next to the deliverables, so a later session (or a change request) continues from them instead of rebuilding the project.

## Install
- **Claude desktop (Cowork):** open `floorplan-to-3d-house.plugin` in a chat and press the install button, or add it from the plugins menu.
- **Claude Code:** publish this folder in a GitHub repo together with a marketplace file (below). Then run:
  - `/plugin install floorplan-to-3d-house --marketplace paulodinis/floorplan-to-3d-house`
  - Older versions: `/plugin marketplace add paulodinis/floorplan-to-3d-house`, then `/plugin install floorplan-to-3d-house@paulodinis`.
- **Claude.ai (web), skill only:** zip `skills/floorplan-to-3d-house/` and upload it under Settings → Capabilities → Skills. You get the main workflow; the two shortcut skills are plugin-only.

### Marketplace file (for a GitHub repo)
Put the plugin in `plugins/floorplan-to-3d-house/` and add `.claude-plugin/marketplace.json` at the repo root:
```json
{
  "name": "paulodinis",
  "owner": { "name": "Paulo Silva" },
  "plugins": [
    { "name": "floorplan-to-3d-house", "source": "./plugins/floorplan-to-3d-house",
      "description": "House plan (PDF/DXF) → 2D approval plan → 3D model → GLB/DXF → Blender video", "version": "1.6.0" }
  ]
}
```

### Blender (for the video only)
The plugin does not bundle a Blender server, because Blender runs on your own computer.
1. Install Blender 4.2+ (tested on 5.2) and the Blender MCP add-on.
2. Start its server.
3. Link your computer to Claude in the desktop app.

The `drone-video` skill checks that the Blender tools are available before doing anything.

## Try it
- "Here is the site plan of my plot (PDF). Make a 3D model of the house."
- "Redesign this house: 3 bedrooms + office, max 250 m², two levels following the slope. Here are two photos of houses I like."
- "Use this DXF from my architect and make a 60-second drone video with a walk through the house."

Claude will ask:
- faithful or redesign;
- number of storeys (one, split levels or two);
- 1–2 optional photos (style references and/or the site);
- an optional address or GPS point. It is used only for the sun, the climate and vegetation, and to check north. It is never put on the published page unless you ask.

## Outputs (typical)
| File | What |
|---|---|
| `plan.dxf`, `plan_vN.png` | 2D drawing and approval plan |
| 3D page (Claude artifact) | interactive model, private until you share it |
| `<name>.glb`, `<name>_3d.dxf` | 3D model for Blender, SketchUp, D5, Twinmotion, Lumion, CAD |
| `render_*.png`, `PROMPT.txt` | references for AI image/video tools |
| `qa.md` | layout checks: setbacks, stairs, doors, room sizes, area cap, headroom and guards |
| `elevations.png`, `elevations.dxf` | four elevations + section through the stair |
| `sun_report.md`, `sun_ground.png` | direct-sun hours per room, ground sun maps |
| `*.mp4` | Blender drone video (optional) |

## Try the example
`<skill>` = `skills/floorplan-to-3d-house` inside this plugin.
```bash
mkdir work && cd work
bash <skill>/scripts/setup_workspace.sh
cp <skill>/examples/{site.json,layout.json} site3d/ && cp <skill>/examples/tex/* site3d/tex/
python3 <skill>/scripts/cloud/validate_layout.py <skill>/examples/project.json
PROJECT_JSON=<skill>/examples/project.json python3 <skill>/scripts/cloud/plan2d.py export/plan.dxf /tmp/x.png
PROJECT_JSON=<skill>/examples/project.json python3 <skill>/scripts/cloud/plan2d_simple.py site3d/layout.json site3d/site.json export/plan_v1.png export/plan.dxf site3d/tex/mask1.png
python3 <skill>/scripts/cloud/build_page.py <skill>/examples/project.json   # -> site3d/page.html
node <skill>/scripts/cloud/navtest.js                                       # walk-collision test
```
The example is an **invented** plot (synthetic survey) with a 3-bedroom single-storey house on two levels, a garage and a workshop. Expected QA: 0 errors, 1 warning.

`examples/two-storey/` uses the same site with a two-storey house (stair void, glass balustrade, balcony): run `python3 <skill>/examples/two-storey/layout_generator_two_storey.py` in a work dir that holds `site3d/site.json`, then use its `project.json`. Expected QA: 0 errors, 0 warnings.

## Limitations (honest list)
- **Storeys:** one storey with split levels, or two storeys (voids, railings, balconies, storey selector, per-storey plans). Three or more are untested. Stairs are straight runs along x, and roofs are hip-only; see `references/multi-storey.md`.
- **Drawings:**
  - vector PDFs work best; scanned images need tracing;
  - DWG must be exported to DXF first.
- **Site geometry:**
  - `extract3d.py` was tuned on one architect's colour conventions; Claude adapts it to each drawing, so check the result;
  - the road is assumed on the west side;
  - terraces and stairs run along x.
- **Interior:** furniture is simple boxes, fine for proportions but not for interior photography.
- **Video:** render time is real; a 60 s video at 1600×900 is roughly 12–13 h on an RTX 4060.

## Privacy
Addresses, GPS points and site photos identify a home. The skill asks before using them. It keeps the address out of the generated page code, and keeps everything in your project folder. The published 3D page is private until you share it.

## Roadmap
See `CHANGELOG.md` and `references/multi-storey.md`.
- L/U stairs and stairs along z; flat roofs and roof terraces.
- IFC export.
- Free road orientation.
- Blender camera paths per storey and a dollhouse cut-away.

Contributions welcome.

## License
MIT; see `LICENSE`. All bundled textures are CC0 (Poly Haven). Third-party components keep their own licences; see `THIRD_PARTY_NOTICES.md`.
