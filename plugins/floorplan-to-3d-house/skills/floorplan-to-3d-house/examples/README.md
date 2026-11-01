# Example project

An **invented** plot (synthetic survey, not a real place) with a 3-bedroom single-storey house on two levels (bedrooms at 32.00, living at 30.80), a garage and a workshop. 285 m² in total.

- `project.json`: project settings (texts, language, location, north, limits, views).
- `site.json`: synthetic survey (boundary, spot heights, trees, ground window), in the format `extract3d.py` writes.
- `layout.json`: the design in the schema of `references/layout-schema.md`.
- `layout_generator_example.py`: how that layout was authored in Python. Copy it as a starting point.
- `tex/`: ground masks for this site (road and markings drawn synthetically, finishes from the layout).

Expected QA result: 0 errors, 1 warning (stair 2R+G = 66.4 cm, just above the comfort band).
