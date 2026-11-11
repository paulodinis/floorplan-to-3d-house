# Inputs: PDF / DXF → site.json (Steps 1–3 in detail)

##  1. Workspace and inputs
Run `bash <skill>/scripts/setup_workspace.sh` in a new project work dir; it copies the textures and reports missing dependencies. ezdxf (DXF read/write): `python3 -m pip install ezdxf==1.4.5`; where PyPI is blocked, point `EZDXF_SRC` at the `src` folder of an ezdxf 1.4.5 source tree (default `./ezdxf-src/src`). Write `project.json` from `examples/project.json`: name, `lang`, location, `north_deg`, `plan_scale`, `area_limit`, `setback_min`, notes and views.
- **PDF:** `pdfinfo`, `pdfimages -list` (vector? raster scans need tracing; say so), `pdffonts`. Render at 110 dpi to look at it. Read the scale from the title block. `K = 25.4/72 × scale / 1000` converts PDF points to metres.
- **DXF:** skip the conversion. Check `$INSUNITS` and the coordinate magnitude (mm? national grid? subtract an origin near the house). List layers, explode blocks, render a preview, map the layers to plot/walls/roof/spot heights/trees/road. If the mapping isn't obvious, ask with a layer list and a thumbnail.
- **DWG:** can't be read here. Ask for a DXF export.
- **Validate the scale** against a known number, such as the plot area in the title block. If it doesn't match, stop and resolve it.

##  2. DXF from PDF (PDF input only)
`python3 scripts/cloud/pdf2dxf.py in.pdf out.dxf <scale>` writes metres, layers by colour and editable text. Verify by rendering the DXF next to the PDF. Tell the user:
- layers are by colour, not the architect's layers;
- dimensions are not associative;
- the architect has the original DWG.

##  3. Site → `site3d/site.json`
Extract the plot boundary, existing walls, the eave line, spot heights (`dd.ddd` texts, position = the decimal point), trees, the road and ceded strips. North comes from the needle or the survey text angle.
- PDF: adapt `extract3d.py`. Its colour constants come from one drawing; confirm them on each new drawing. Then run `masks.py` for the ground masks.
- DXF: write the equivalent from the layers and save it as `scripts/cloud/extract3d_dxf.py` for reuse.

Scene axes: x east, z south (sheet axes), y up, y = 0 at the main finished floor level.

