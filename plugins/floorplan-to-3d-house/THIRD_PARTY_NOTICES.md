# Third-party notices

| Component | Use | License |
|---|---|---|
| three.js r160 (mrdoob/three.js) | 3D engine, loaded from jsDelivr; local test copies fetched by `setup_workspace.sh`, not bundled | MIT |
| ezdxf (mozman/ezdxf) | DXF read/write, fetched by `setup_workspace.sh`, not bundled | MIT |
| pdfplumber / pdfminer.six | PDF vector extraction (pip) | MIT |
| Playwright + Chromium | headless tests, GLB export, renders | Apache-2.0 / BSD-style |
| Blender | optional video pipeline (user-installed) | GPL (the scripts here only call its Python API) |
| `scripts/web/tex/sky.jpg` | Poly Haven "Quarry 01" HDRI, 1024×512, encoded as sRGB JPEG at 1/4 radiance (sun disc re-injected analytically in `engine.js`) | CC0 |
| `scripts/web/tex/grass.jpg` | Poly Haven `leafy_grass` (diffuse 1k), hue/saturation adjusted greener | CC0 |
| `scripts/web/tex/gravel.jpg` | Poly Haven `gravel_floor` (diffuse 1k), desaturated and brightened | CC0 |
| `scripts/web/tex/oak.jpg` | Poly Haven `oak_wood_planks` (diffuse 1k) | CC0 |
| `scripts/web/tex/setts.jpg` | Poly Haven `cobblestone_floor_04` (diffuse, resized to 512) | CC0 |
| `scripts/web/tex/soil.jpg` | Poly Haven `forest_ground_04` (diffuse, resized to 512) | CC0 |

Stone, timber slats, roof tiles, render and paving are generated procedurally (`scripts/cloud/tex.py`, `scripts/blender/materials.py`).
