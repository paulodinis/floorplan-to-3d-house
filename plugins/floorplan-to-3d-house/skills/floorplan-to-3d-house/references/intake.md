# Intake question bank (Step 0)

Use AskUserQuestion: at most 4 questions per call and 2–4 options each; "Other" is always added automatically. Put the recommended option first and mark it "(Recommended)". Ask only what changes the result. Translate the questions into the user's language.

## Call 1: scope (always)
1. **Faithful or redesign?**
   - "Faithful to the drawing (Recommended when the design is final)": model what is drawn.
   - "Redesign on this plot": keep the plot, road and slope; propose a new house.
2. **Storeys**
   - "Single storey"
   - "Single storey, split levels following the slope (Recommended on sloping plots)"
   - "Two storeys": supported (see multi-storey.md); ask the floor-to-floor height if the drawing lacks sections (default 2.95 m).
   - "Three or more storeys": the schema allows it, but only two are tested; say so.
3. **Photos (optional)**: "Can you share 1–2 photos? They make the result much closer to what you imagine."
   - "Style references (houses I like)"
   - "Photos of the plot / street"
   - "Both"
   - "No photos"
4. **Location (optional)**: "Address or GPS point of the plot? Used only for the sun and lighting, the climate and vegetation, and to check north. It won't appear on the published page unless you ask."
   - "I'll send it"
   - "Region only (e.g. central Portugal)"
   - "Skip"

## Call 2: redesign only
- **Programme:** bedrooms, en-suite, office, garage (cars), workshop / storage, covered terrace.
- **Floor-area cap:** "≤ 200 m²", "≤ 250 m²", "≤ 300 m²", or a number from the local plan.
- **Slope:** split levels (Recommended) / one platform with retaining walls / a basement garage.
- **Must-keep items:** existing trees, walls, access position.

## Approval gate (Step 5): one call, two or three questions
- **Approve the 2D plan?**
  - "Approved, go to 3D"
  - "Approved with small changes (describe in Other)"
  - "Change and show again"
- **Blender video?** Only ask this if Blender + the MCP add-on is available, and never when the user already chose the model only ("só a maqueta", "just the 3D model", "no video"); then the gate is the approval question alone, and no length, resolution or time question follows.
  - "No"
  - "15 s (Recommended)": 360° orbit of the house
  - "30 s": slower 360° orbit
  - "60 s: 360° + inside": orbit, then the front door opens and the camera goes to the doorway of every space
  - Quote time = frames × measured s/frame. The reference GPU (RTX 4060) does 1600×900 at 24 samples in about 25–31 s per frame.
- **Video resolution?** Ask together with the length, only if a video was requested. Show the estimated time for the chosen length in each option (table in `references/blender-pipeline.md`), for example for 15 s:
  - "1600×900 (Recommended)": ~31 s/frame, ~3 h 15
  - "1920×1080 (Full HD)": ~45 s/frame, ~4 h 40
  - "1280×720 (faster)": ~20 s/frame, ~2 h 05
  - Say the times are estimates for an RTX 4060 and get corrected after a measured test frame.

## Handling answers
- **Style photos:** extract a palette with style-guide.md and confirm it in one line. Don't ask the style question.
- **Site photos:**
  - compare trees, walls and the road side with site.json;
  - list the differences;
  - never move surveyed geometry because of a photo without asking.
- **GPS:**
  - write `location.lat` / `location.lon` in project.json;
  - `show_address_on_page` stays false unless the user says otherwise;
  - don't web-search the address unless the user asks.
- **No reply (unattended):** take the recommended options, say so at the top of the summary, and stop at the approval gate.
