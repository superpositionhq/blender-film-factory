# Film format

A film is one git repo, `<BFF_ROOT>/films/<slug>`, made by `templates/new-film.py` and checked by
`python3 tools/validate-film.py <film> [--release]` (VALID, or INVALID with one line per error).

## Files

| Path | What | When |
|---|---|---|
| `film.json` | `schema film/v1`, slug, title, description, `input` (`text` / `video`), `output` (`final` / `previs`), `format` (width, height, fps, min/max seconds, min shots), blender version | creation |
| `Brief.md` | the input, word for word; for a clip, where it is from and its licence | before the treatment |
| `reference/` | video input: `reference.<ext>`, `reference.json` (`film-reference/v1`: duration, fps, size, cuts, shots), `frames/`, `sheets/`, `Breakdown.md` | before the treatment |
| `Docs/Treatment.md` | idea, look, object list, shot list, rhythm, status | before the first step |
| `build/` | step scripts `NNN_name.py`, `kit.py`, `mannequin.py`, `order.txt` (the scripts that ran, in order), `data/` (baked numbers a step reads) | as built |
| `steps/<NNNN>-<name>/` | `script.py` (the code that ran), `state.json`, `preview.png`, `result.json`, `stdout.log` | one per step |
| `workflow.jsonl` | one row per operation | as built |
| `textures/` | images painted by step scripts, loaded as `//textures/...` | as built |
| `Docs/Critique.md` | `## Round <n>` sections: shot, what is weak, the fix | critique rounds |
| `shotlist.json` | one entry per shot (below) | before release |
| `Docs/Report.md` | what was made, what works, what is weak, render settings and time, steps, what next | before release |
| `out/` | `film.mp4`, `animatic_clay.mp4`, `animatic_blockout.mp4`, `contact_sheet.png`, `scene.blend`, and `comparison.mp4` for a clip | release |

Not in the repo: `scene.blend` at the root (rebuilt by `build/order.txt`), `.local/` (checkpoints, renders).
Pictures, videos, sound and `.blend` go through Git LFS.

## state.json (per step)

Written by the step harness after the script: Blender version, scene name, frame range, fps, resolution, engine,
the active camera, the markers (name, frame, camera), every object (name, type, parent, collections, world
location / rotation / scale, `hide_render`, whether it is animated, modifiers, constraints, materials, and for a
mesh its evaluated vertex and triangle counts, for a camera its lens and depth of field, for a light its type and
energy), every material (name, users, node count, node types), images, linked libraries, and the counts.

## workflow.jsonl

`film-workflow/v0`, one JSON object per line: `schema, id` (`<prefix>-<seq 5 digits>`), `seq, time` (ISO 8601 with
milliseconds and offset), `actor` (`agent` / `user`), `op, target, params, reason, reason_source` (`agent_note` /
`user_direction`), `status` (`observed` / `failed` / `reverted` / `unrecorded`), `source {script, sha256, commit}`,
and `direction` (the id of the `user.direction` row a row acts on). A step's row carries `params.step`, `ok`,
`seconds`, `counts`, `preview_frame`. Rows are appended and never edited.

## shotlist.json

A list, one entry per shot, in order:

```json
{"shot": 1, "name": "Dusk room", "frame_start": 1, "frame_end": 120, "video_start_s": 0.0, "video_end_s": 5.0,
 "camera": "Cam_S1_DuskRoom", "camera_move": "dolly", "shot_size": "extreme wide", "camera_angle": "eye level",
 "subject": "TeaBowl", "description": "Dusk. The room: the bowl on the chest under the lit lantern. Slow dolly in.",
 "events": [{"name": "lantern starts to swing", "object": "Lantern_Pivot", "frame": 132}]}
```

Every value is checked against the scene by `tools/shots.py` ([shot-facts.md](shot-facts.md)).

## The scene

One scene, one timeline, the film's format as in `film.json`; one camera object per shot, each bound to a timeline
marker at its first frame; every object named for what it is; every rendered mesh with a material; nothing left of
the default file; nothing linked or loaded from outside the film.

## Floors by output mode

| | `final` | `previs` |
|---|---|---|
| successful steps | 40 (80 to 130 is normal) | 12 (30 to 60 is normal) |
| evaluated triangles | 300,000 | none |
| mesh objects | 40 | 5 |
| materials in use, share that are more than a bare shader | 12, 60 % | 2, none |
| lights | 3 | none |
| animated objects besides cameras | 5 | 1 |
| shots with depth of field | 1 | none |
| critique rounds | 2 | 1 |

Warnings while the film is being built, errors with `--release`.

## Release checks (`--release`)

`out/film.mp4` is H.264 at the scene's size and frame rate with exactly the scene's frame count and no
near-uniform frame; `out/animatic_clay.mp4` has the same frame count and rate; the contact sheet, the scene copy,
the critique and the report exist; `shotlist.json` holds (`tools/shots.py`); the last `tools/replay.py` said
`REPLAY OK`; a clip input also has its reference files and `out/comparison.mp4`.

## Names

No tracked text file and no commit message holds the names of the toolkit, its owners, an agent, a model or their
makers, an attribution trailer, or a machine path with the account name.
