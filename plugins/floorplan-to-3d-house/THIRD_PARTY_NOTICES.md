# Third-party notices

| Component | Use | License |
|---|---|---|
| three.js r187 (mrdoob/three.js) | 3D engine (WebGPU renderer with WebGL 2 fallback, TSL post-processing), loaded from jsDelivr by the 3D page. For the local Playwright tests and GLB export `scripts/web/three/` bundles `build/three.core.js`, `build/three.webgpu.js` and `build/three.tsl.js` (whitespace-minified with esbuild so each file stays under 1 MiB; same exports and code) and these addons unmodified under `jsm/`: `OrbitControls`, `GLTFExporter`, `GLTFLoader`, `BufferGeometryUtils`, `SkeletonUtils`, `RoundedBoxGeometry`, `SSGINode`, `GTAONode`, `TRAANode`, `TAAUtils`. Licence: `scripts/web/three/LICENSE` | MIT |
| ezdxf (mozman/ezdxf) | DXF read/write, installed by the user (`pip install ezdxf==1.4.5`), not bundled | MIT |
| pdfplumber / pdfminer.six | PDF vector extraction (pip) | MIT |
| Playwright + Chromium | headless tests, GLB export, renders | Apache-2.0 / BSD-style |
| Blender | optional video pipeline (user-installed) | GPL (the scripts here only call its Python API) |
| `scripts/web/tex/sky.jpg` | Poly Haven "Quarry 01" HDRI, 1024×512, encoded as sRGB JPEG at 1/4 radiance (sun disc re-injected analytically in `engine.js`) | CC0 |
| `scripts/web/tex/grass.jpg` | Poly Haven `leafy_grass` (diffuse 1k), hue/saturation adjusted greener | CC0 |
| `scripts/web/tex/gravel.jpg` | Poly Haven `gravel_floor` (diffuse 1k), desaturated and brightened | CC0 |
| `scripts/web/tex/oak.jpg` | Poly Haven `oak_wood_planks` (diffuse 1k) | CC0 |
| `scripts/web/tex/setts.jpg` | Poly Haven `cobblestone_floor_04` (diffuse, resized to 512) | CC0 |
| `scripts/web/tex/soil.jpg` | Poly Haven `forest_ground_04` (diffuse, resized to 512) | CC0 |
| `scripts/web/models/*.glb.json` | Poly Haven models `modern_coffee_table_01`, `throw_pillows_01`, `potted_plant_04`, `modern_ceiling_lamp_01`, `wicker_basket_01`, `jug_01` (glTF 1k, textures reduced to 512 px JPEG in Blender, stored as base64 GLB because the artifact host serves no `.glb`). `wicker_basket_01` is decimated to ~4.9k triangles with 256 px textures; `throw_pillows_01` is recoloured at load time | CC0 |

Stone, timber slats, roof tiles, render and paving are generated procedurally, and so are the olive trees, the cars and the soft upholstery (`scripts/cloud/tex.py`, `scripts/blender/materials.py`).
