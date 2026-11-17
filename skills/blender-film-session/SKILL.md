---
name: blender-film-session
description: 'Rules for a session that makes one short film in Blender 5.2 from a script (or a script with a storyboard) for blender-film-factory (repo <BFF_ROOT>/films/<slug>). Use at the start of every film session and whenever deciding about reading the script, the breakdown and treatment, the build order, what goes in a step, the step tool and its pictures, shot cameras and markers, the shot list, animation, naming, recording, the deliverables, or what to tell the person. Pair it with blender-film-commit-always, with blender-film-greybox or blender-film-final for the output, and with blender-film-storyboard when the input has storyboard pictures.'
---

# Film session (Blender)

Build the supplied script into a complete Blender film, headlessly in code. Develop it in small,
visible increments. Save every script, render each change, inspect the image, and commit before moving on.
The deliverables are the film, its source files, and a complete, replayable build history.

Work continuously through the stages below. Make one object, shot, material family, animation beat or fix
per step. Save partial work and failed attempts too; correct them in a new step. Commit the brief, plans,
review notes and final outputs separately. Do not combine a whole scene into one script or one commit.

| Input | Output |
|---|---|
| `script`: a written script | `greybox`: a grey-box video (mannequins and blocks: staging, motion, camera, cuts) |
| `storyboard`: a script with storyboard pictures | `final`: a fully rendered film, which also delivers its grey-box video on the way |

`<BFF_ROOT>` = the machine root (`machine/README.md`). "The person" is whoever started you.

**Only the blender-film-factory skills (owner's rule).** Use blender-film-commit-always, blender-film-session,
blender-film-greybox, blender-film-final and blender-film-storyboard and no other skill: never install, enable or
invoke a personal, project, plugin, marketplace or agent built-in skill, even when the agent offers one, nor another
factory's skills. Do what they do not cover by hand under these rules.

## Start

1. Read `AGENTS.md`, `docs/film-format.md`, `docs/shot-facts.md`, the skill of your output (blender-film-greybox or
   blender-film-final), and blender-film-storyboard for a storyboard input.
2. **Your first tool call names your film folder's full path** (the recording hooks file a session under the film
   whose path its first such call names). Create the film with it:
   `python3 <BFF_ROOT>/blender-film-factory/templates/new-film.py --slug <slug> --path <BFF_ROOT>/films/<slug> --title "<Title>" --description "<one line>" --input <script|storyboard> --output <greybox|final>`
   with `<BFF_ROOT>` written out as the absolute path, never `$BFF_ROOT` or `~` (in Git Bash on Windows, each
   Windows path in single quotes). A format the brief gives goes in with
   `--width --height --min-seconds --max-seconds --min-shots`.
3. **Brief**: put the script into `Brief.md`, every line as given, and commit it (`brief.write` row). A storyboard:
   bring the pictures in with `tools/storyboard.py` and open every page (blender-film-storyboard skill).
4. **Breakdown**: `Docs/Breakdown.md`, written from the input and committed before the treatment
   (`breakdown.write` row). "Reading the script" below.
5. **Treatment**: `Docs/Treatment.md`, written and committed before the first step (`treatment.write` row): the
   look, **the object list** (every object by name: what it is, how big, where it stands), the shot list as a table
   (frames, seconds, size and angle, camera move, what happens, which script lines), and why each cut is where it
   is. Keep its status section current. An object or a shot added later is added to the treatment first.

## Reading the script

The script is the brief: the film shows **what the script says, in its order, and nothing that contradicts it**.

- **Break it into beats**: one beat per action or line of dialogue that the camera must show. The breakdown lists
  the cast and things (a neutral object name for each, used from here on: `Rider`, `Gate`), the places (a plan in
  words and metres), the beats in order with their script lines, and what the script leaves open with the choice
  you make for each (a distance, a time of day, a camera the script does not give).
- **Time the beats**: a script page is about a minute. An action takes the time the action takes (a walk covers
  1.3 m per second; someone needs a second to turn and look). A line of dialogue takes its words at about 2.5 words
  per second plus half a second, and a pause the script writes ("beat", "a moment") is one second. The film has no
  recorded voices: a speaking character is shown speaking (grey box: a small gesture and the shot held for the
  line; final: as the output skill says), and the line stays in the shot list's description.
- **Shots come from the script first.** A shot or move the script names (`CLOSE ON`, `WIDE`, `PAN TO`, `POV`) is
  that shot. Where it names none, you choose: a new shot when the place, the time or the centre of attention
  changes; the size by what must be read (a face for a reaction, the whole body for a walk, the room for where
  people stand); screen direction kept across cuts (who is on the left stays on the left).
- **A script longer than the film's format**: film the stretch the brief names, or the first complete scene, and
  write in the breakdown which lines are in.
- Nothing from the real world is carried into the film: no real person's likeness, no brand, logo or lettering.

## Blender runs headless only

Never open the Blender window and never take over the screen. Every scene change is a Python script run by the step
tool; every look at the scene is a rendered picture you open with your image tool.

## The step: one visible change, one picture, one commit

**This is the core rule.** The scene changes only like this:

```
python3 <BFF_ROOT>/blender-film-factory/tools/step.py <BFF_ROOT>/films/<slug> "<what changes on screen>" build/<NNN>_<name>.py \
    --op <op> --target <object or shot> --reason "<brief action purpose or visible issue>" [--frame <n>]
```

1. **Give a short progress update** naming the visible change about to be made.
   Example: `The chest is still a plain box. Next I will add three rows of drawer fronts visible in shot 3.`
   After inspecting a fix, report whether the rendered issue is resolved. Describe the work as it happens.
2. **Write the step script with your file tool**, never with a heredoc, `sed -i` or a Python rewrite (a file
   tool's call is recorded with the exact text). `build/<NNN>_<name>.py`, numbered in the order written, starting
   with a comment that says what the step does, then
   `import bpy, sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kit`.
3. **Run it with the step tool.** `--frame` picks the frame of the picture: one inside the shot the change shows in.
   The first step runs with `--new` and calls `kit.start_film(...)`.
4. **Open the picture and judge it** (`steps/<NNNN>-<name>/preview.png`) before the next step. Black, empty,
   clipped, floating, sunk, the wrong way round: that is the next step's job, before anything new.
5. The tool has committed. Go to 1.

Rules for every step:

- **Never batch** several objects, several shots or several fixes into one step, and never split one change into
  empty steps to make the history longer. A step is one thing a viewer could point at.
- **A step that came out wrong stays**: fix it in the next step, whose name says what was wrong on screen. Never
  amend, never delete a step folder, never edit a script that already ran (a helper that must behave differently
  gets a new name in `kit.py`).
- **A failed script** changes nothing in the scene; the tool still records and commits it. Say what went wrong, fix
  the script file, run it again: it becomes a new step.
- **More looks whenever you are unsure**, without changing anything:
  `python3 .../tools/render.py <film> --frames 10,48,96 --sheet 3` (one sheet of several frames),
  `--shots --sheet 3` (three frames of every shot), `--clay` (one clay material). Open the sheet it names. Look at
  the first and the last frame of every shot at least once: cuts hide mistakes. Never delete `.local/render/`: the
  pictures you opened are part of the record.
- **Scripts are deterministic and self-contained**: fixed random seeds, no file from outside the film, no clock.
  `tools/replay.py <film>` rebuilds the scene from an empty file and must say `REPLAY OK`; run it when the blockout
  is done and before release. A simulation is run inside one step, baked to keyframes, its world removed, and the
  baked numbers kept in `build/data/<name>.json`, which the step reads when it exists.
- **Never touch `scene.blend` any other way.** Read-only scripts that print or render are fine and write only under
  `.local/`.

## Build order

Each stage is many steps; the output skill says how far each goes.

1. **Start**: `kit.start_film(width, height, fps, frames, name=...)` with `--new`.
2. **Blockout**: every object of the treatment as rough massing, right size and place, one step per object; one
   camera per shot, one step each (`kit.shot_camera(name, first_frame, lens, collection)` binds it to a timeline
   marker at the cut); the blocked animation, one beat per step.
3. **The grey-box video**: render the whole timeline and look at a sheet of it (`--shots --sheet 3`); fix staging,
   framing and timing **now**, one fix per step. Everything after this costs ten times more to move. For a `final`
   film this stage's video is a deliverable:
   `tools/render.py <film> --all --pct 50 --out greybox --mp4 out/greybox.mp4`, committed (`greybox.render` row).
4. **Models** (final: detailed; greybox: outlines made readable), one object per step, keeping object names
   (`kit.swap_mesh`).
5. **Materials** (final only), one material family per step.
6. **Lighting** (final: designed; greybox: the plain rig).
7. **Animation and camera polish**: easing, holds, overlap; one beat or one shot per step.
8. **Render settings, colour, compositing** (final only), one concern per step.
9. **Critique rounds** (final: at least 2; greybox: at least 1). A round: render three frames of every shot, look at
   each, hold it against the script beat it shows, write every weakness into `Docs/Critique.md` under `## Round <n>`
   (shot, what is weak, the fix) and as one `critique.issue` row each, commit, then fix each issue in its own step.
10. **Shot list, report, release** ("Deliverables").

The order is the default, not a cage: going back is fine, in a new step that says why.

## Cameras, shots and the shot list

- **One camera object per shot**, named `Cam_S<k>_<What>`, bound to a timeline marker at the shot's first frame.
  The shots tile the scene's frame range. Changing a cut is its own step (`kit.retime_shot`).
- **Camera moves are plain and nameable**: static, pan, tilt, dolly, truck, pedestal, orbit, crane, zoom, handheld.
  Two keys with linear or eased interpolation, or a pivot empty for an orbit. A camera never passes through
  geometry and never jumps inside a shot. Slow and steady unless the script says otherwise.
- **Visibility is keyed on `hide_render` only** (`kit.show_between`). An object hidden in the viewport is not
  evaluated in background mode, so anything read from it is stale.
- **`shotlist.json`**: one entry per shot (docs/film-format.md): frames, video times, camera, `camera_move`,
  `shot_size`, `camera_angle`, the `subject` object, the script lines it covers, a description, `events`.
  **The values must be true of the scene**: `python3 .../tools/shots.py <film>` measures every shot on every frame
  (`--subject 1=<object>` tries a subject) and names every declared fact that does not hold (docs/shot-facts.md).
  Write the list from what it prints; change the scene or the list until it says `SHOT FACTS HOLD`.

## Animation

- Motion has weight: ease in and out, anticipation, overlap; nothing starts or stops on one frame unless it is hit.
  Things fall at 9.81 m/s² (0.8 m takes 10 frames at 24 fps). Real scale, in metres.
- A cut lands on movement when the story speeds up and on stillness when it rests.
- Blender 5 keeps F-Curves in an action's slot (`action.fcurves` is gone): use `kit.fcurves`, `kit.key`,
  `kit.set_interp`, `kit.clear_anim`.

## Everything is made here

Geometry, materials, textures and animation are made in this session, in code. **Download nothing**: no external
models, textures, HDRIs, fonts, add-ons or asset libraries. Images are painted by your scripts (numpy is in Blender)
into `textures/` and loaded as `//textures/<name>.png`. The only files from outside are the script and the
storyboard pictures of the input.

## Names

Never write the names of the company or the tools that run this (any spelling of the tool repo's name), the
machine's account name or a machine path in the film: scripts, comments, docs, commit messages, rows, object names.
Paths are written relative to the film. `tools/validate-film.py` reports them.

**Every object is named for what it is** (`TeaBowl`, `Cam_S3_ChestEdge`, `Lantern_Light`): no `Cube`, no `Light`,
no `.001`. Every rendered mesh has a material. Nothing of the default file is left.

## Deliverables

1. `shotlist.json` written from `tools/shots.py` (`SHOT FACTS HOLD`), committed (`shotlist.write` row).
2. `Docs/Report.md`, plain facts, committed (`report.write` row): what was made; a table of the script's beats and
   the shot that shows each (and every beat that is not shown as written, with why); what is weak; render settings
   and seconds per frame; steps and how many failed.
3. `python3 .../tools/release.py <film>` renders `out/film.mp4` and `out/animatic_clay.mp4`, builds
   `out/contact_sheet.png`, copies `out/scene.blend`, runs the replay, the shot facts, the trajectory export and
   `validate-film.py --release`, and commits when the film is VALID for release. Check the seconds per frame first
   (`tools/render.py <film> --shots`); if the render would not fit your time, lower the samples before you cut
   shots.
4. Open the contact sheet, and a sheet of consecutive frames around every cut and every fast action. A flicker, a
   pop or a smeared first frame is fixed before release.
5. Tell the person the commit sha and the validator's last lines. A reviewer then scores the film and its record
   (`tools/review.py`, docs/review.md); what they send back is fixed one step per point.

## Completion standard

In this order: the record is whole and honest (a note and a look before every step, one step per visible change,
the replay passes); the film shows the script; the film is whole (every frame renders, the format is met); the shot
list is true; taste. No polishing loops outside the critique rounds, and no re-doing a step to get a nicer picture
of it: the pictures are a record, not a portfolio.

## Working with the person

- Resolve ordinary creative ambiguities independently and record the chosen interpretation in the breakdown or treatment. Report required permissions or technical blockers clearly.
- **Every direction from the person is recorded before you act on it** (blender-film-commit-always skill), then
  fixed one step per point.
- Push only when told.
