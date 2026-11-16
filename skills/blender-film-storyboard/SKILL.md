---
name: blender-film-storyboard
description: 'Rules for a blender-film-factory film whose input is a script with storyboard pictures. Use for every film created with --input storyboard, when bringing the storyboard pages in, reading and numbering the panels, tying panels to script lines and shots, deciding what of a panel must be matched (framing, staging, camera arrows) and what may differ, and comparing the film with the panels. Pair it with blender-film-session, blender-film-commit-always and the skill of the output.'
---

# Storyboard input: a script with pictures

The script says what happens; the storyboard says **how it is framed**. Each panel is a shot or a moment of a shot
that someone already decided. The film follows the script for content and the panels for framing. Everything in
the blender-film-session skill applies; this skill covers the pictures.

## Bring the pictures in and read them

- `python3 <BFF_ROOT>/blender-film-factory/tools/storyboard.py <BFF_ROOT>/films/<slug> <pictures or a folder>`
  copies them to `storyboard/page_<NN>.<ext>` in order and writes `storyboard/storyboard.json` and
  `storyboard/sheet.jpg`. Commit them with the brief.
- **Open every page with your image tool**, one by one; the sheet is only a map. A page holds one panel or many.
- Storyboards are drawings, often rough: stick figures, arrows, notes in the margin. Read them as a crew does:
  - **the frame** is the panel's border: what is inside is in shot, and where it sits in the border is where it sits
    on screen;
  - **arrows inside the frame** are movement of people or things; **arrows on or outside the border**, or a frame
    drawn inside a frame, are camera moves (an arrow along the border: pan or truck; a smaller frame with arrows to
    or from the border: push in or pull out; a tall or wide panel: tilt or pan across it);
  - **several panels of one set-up** are moments of one shot, in order;
  - **written notes** (a shot size, a lens, a sound, a line of dialogue) are part of the panel.

## Number the panels in the breakdown

`Docs/Breakdown.md` gets, besides what every film's breakdown has, a **panel table** in reading order: panel number
(`P1`, `P2`, ...; you number them, page by page, left to right, top to bottom), the page it is on and where, what
the drawing shows (who, where in the frame, facing which way, how large), the camera move its arrows give, any
written note word for word, and the script lines it belongs to. Then:

- **Every panel is tied to script lines, and every beat of the script to a panel or to none.** A beat with no panel
  is yours to frame. A panel that fits no line is listed under "What the input leaves open" with what you do with
  it (most often: it is a moment inside a neighbouring beat).
- **Where a panel and the script disagree** (the script says night, the panel shows a sun; the script has two
  people, the panel three), the script wins for what happens and the panel for how it is framed. Write each
  disagreement down with your choice.
- Panels that are moments of one shot are grouped: the shot list has one shot for them.

## What a panel fixes, and what it leaves open

| Matched from the panel | Yours to decide |
|---|---|
| shot size and angle (how large the subject is in the frame, seen from above, below or level) | exact lens and camera distance that give that frame |
| where each person and main thing sits in the frame, and which way it faces | everything the drawing does not show: surfaces, small props, the far background |
| the camera move its arrows give, and its direction | how far and how fast, from the time the beat takes |
| the order of the panels | shots for beats that have no panel |
| screen direction from panel to panel | the look (final output): palette, light, materials, unless a note gives them |

## Matching a shot to its panel

One shot's camera per step, after the blockout of what that shot sees:

1. Place the camera so that the frame agrees with the panel: the subject as large in the frame as drawn, at the
   same place in the frame, the horizon as high (the horizon sits at the camera's own height: a low horizon is a
   low camera). Choose the lens from how much of the place the panel shows around the subject.
2. Open the step's picture **and the panel's page again**, and compare positions in the frame: the top of the
   subject's head, its feet or base, the main verticals, what is cut by the border. Say in your note what agrees and
   what does not. Move the camera, then the lens, until it agrees; then key the move the arrows give.
3. A shot with several panels is checked at each: the frame at the start agrees with the first panel, the frame at
   the end with the last.

The shot list's entry carries the panels of the shot: `"panels": ["P3", "P4"]`.

## At the end

- Each critique round holds every shot against its panel, by the left column of the table above; each mismatch is
  a `critique.issue`.
- `Docs/Report.md` has a table: per shot, its panels and script lines, and for size, angle, placement in the frame
  and camera move whether it matches the panel, with one line on every difference that stayed and why.
