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

## Approval gate (Step 5): one question
- **Continue to 3D?** "Yes" / "Change the plan (describe; grid cells welcome)" / "Stop here".
- Video length and resolution are not asked here: `drone-video` asks them, once, when the user wants a video. "Open in Blender?" is asked after the 3D (Step 7b), once per session.
- A request with two readings ("same height", "attach", "centre the entrance"): ask with the readings as options before drawing.

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
