---
name: blender-film-reference
description: 'Rules for a blender-film-factory film whose input is a video: a reference clip that the film recreates in Blender, as a previs or as a finished picture. Use for every film created with --input video, when preparing the clip (cuts, frames, sheets), writing the shot-by-shot breakdown, deciding what must match the reference and what may differ, timing the film to the clip, and comparing the result with it. Pair it with blender-film-session, blender-film-commit-always and the skill of the output mode.'
---

# Video input: recreate a reference clip

The input is a short clip. The film recreates **what happens in it and how it is shot**: the same shots in the same
order with the same lengths, the same staging and blocking, the same camera position, lens feel and move in each
shot, the same events at the same times. It is made from nothing but the clip: every model, material and motion is
built in this session. Everything in the blender-film-session skill applies; this skill covers the steps that come
before the first scene step and the checks that come after.

## The clip

- Only a clip the brief gives you, with where it is from and its licence written in `Brief.md` (public domain,
  CC0, or one the person owns or has cleared). You do not go looking for clips.
- You cannot watch a video; you read pictures. So the clip is turned into frames and sheets:
  `python3 <BFF_ROOT>/blender-film-factory/tools/reference.py <BFF_ROOT>/films/<slug> <clip> --source "<where from, licence>"`
  copies it to `reference/`, finds the cuts, and writes `reference/reference.json` (duration, frame rate, size,
  cuts, a shot table), `reference/frames/` (frames of each shot, named by shot and time) and `reference/sheets/`
  (`overview.jpg`, then one sheet per shot). Commit them (`reference.breakdown` row once the breakdown is written).
- **Read every sheet.** The cut detection is a first guess: a whip pan or a flash is taken for a cut, a dissolve
  or a cut between similar pictures is missed. Correct the shot table in `reference.json` by hand and say so in the
  breakdown; run the tool again with `--cut 0.2` (finds more) or `--cut 0.4` (finds fewer) or `--fps 8` (more
  frames of each shot) when the sheets do not show enough.
- A clip longer than the film's format allows: recreate the stretch the brief names, or the first stretch that is
  one complete event, and write in the breakdown which seconds are used.

## The breakdown: `reference/Breakdown.md`

Written before the treatment, from the sheets, and committed. It is what you saw, not what you plan.

1. **The whole**: one paragraph. Where, when, who and what, what happens from first frame to last, the mood, the
   palette, the kind of light.
2. **Cast and things**: every person, animal, vehicle and prop that matters, with a neutral name used from here on
   (`Rider`, `Dog`, `Gate`), what it looks like, its size against something known, its colour.
3. **The place**: a plan of each location in words and numbers: ground, walls, openings, the main masses, with
   estimated sizes in metres (a door is 2 m, a person 1.7 m, a car 4.5 m long: measure everything against those),
   and where north is on your plan. Name where the camera stands in each shot on that plan.
4. **Shot table**, one row per shot: number; start and end in seconds and the length; shot size; camera angle and
   height; lens feel (wide, normal, long: how strongly the background is compressed, how fast it shifts when the
   camera moves); camera move (static, pan, tilt, dolly, truck, pedestal, orbit, crane, zoom, handheld) with its
   direction and how far; the subject; what happens, as events with their time in the shot (`0.8 s the rider
   turns his head left`); where things enter and leave the frame; light direction (where the shadows fall).
5. **What cannot be known**: what the frames do not show (what is behind the camera, exact distances, a motion
   too fast for the frame spacing), and the choice you make for each.

Describe what is in the frames; do not name real people, brands, titles or places even when you recognise them
(the film must not carry them either: no likeness, no logo, no lettering copied from the clip).

## Timing: the film follows the clip

- The film runs at 24 fps unless the brief says otherwise. Each shot's length in frames = its length in the clip in
  seconds x 24, rounded; the total may differ from the clip by a frame or two, a shot by no more than two frames.
  The treatment's shot list carries both: clip seconds and film frames.
- Events keep their time: an event at 0.8 s of a shot is at frame `first_frame + round(0.8 * 24)`, within three
  frames.
- The format in `film.json` follows the clip: pass `--width/--height` at creation for the clip's aspect ratio
  (1920 wide for final, 1280 wide for previs; the height from the clip's ratio, made even), and
  `--min-seconds/--max-seconds/--min-shots` around the clip's length and shot count.

## What must match, what may differ

| Must match | May differ |
|---|---|
| number, order and length of shots; the cut points | faces and exact likeness (and must differ for real people) |
| shot size, angle and camera height of every shot | exact textures and patterns |
| the camera move of every shot: kind, direction, rough extent | small props that do not matter to the event |
| who and what is in frame, where on screen, facing which way | the exact number of background things |
| what moves, where to, and when (the events) | weather detail, lettering, logos (left out) |
| screen direction across cuts (left stays left) | |
| final output: the palette, the light direction and its hardness, the time of day | |

A previs output matches the left column except the last row, with mannequins and blocks (blender-film-previs
skill). A final output matches all of it with built models and materials (blender-film-final skill).

## Matching a shot

One shot's camera per step, after the blockout of what that shot sees:

1. Put the camera on your plan where the breakdown says, at the height the horizon line in the frame gives (the
   horizon sits at the camera's eye height: things taller than the camera cross it).
2. Choose the lens from how much of the place is in frame at that distance: 24-35 mm when the walls run away, 50 mm
   when it looks as the eye sees, 85 mm and above when the background is flat and large.
3. Render the shot's first, middle and last frame next to the reference frames of the same times and compare
   **positions on screen**: where the subject's head is in the frame, how tall it stands in the frame, where the
   ground line and the main verticals are. Move the camera, then the lens, until they agree; then key the move.
   A side-by-side look:
   `python3 .../tools/render.py <film> --frames <a>,<b>,<c> --sheet 3 --out match_s<k>` and open it beside
   `reference/sheets/shot<k>.jpg`.
4. Then the blocking of that shot: one move per step, timed from the shot table.

## Comparing at the end

- The critique rounds compare every shot with its reference sheet, row by row of the "must match" column, and each
  mismatch is a `critique.issue`.
- `Docs/Report.md` has a table: per shot, clip seconds, film frames, and for size, angle, move and events whether
  they match, with one line on every known difference and why it stayed.
- `tools/release.py` writes `out/comparison.mp4`: the reference on the left, the film on the right. Make a sheet of
  it at a few times and look: this is what a reviewer will open first.
