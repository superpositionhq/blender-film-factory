# Film format

A film is one git repo, `<BFF_ROOT>/films/<slug>`, made by `templates/new-film.py` and checked by
`python3 tools/validate-film.py <film> [--release]` (VALID, or INVALID with one line per error).

## Files

| Path | What | When |
|---|---|---|
| `film.json` | `schema film/v1`, slug, title, description, `input` (`script` / `storyboard`), `output` (`greybox` / `final`), `format` (width, height, fps, min/max seconds, min shots), blender version | creation |
| `Brief.md` | the script, every line as given | before the breakdown |
| `storyboard/` | storyboard input: `page_<NN>.<ext>`, `storyboard.json` (`film-storyboard/v1`), `sheet.jpg` | with the brief |
| `Docs/Breakdown.md` | the script read: cast and things, places, timed beats with their script lines (and the panel table), what the input leaves open | before the treatment |
| `Docs/Treatment.md` | idea, look, object list, shot list, rhythm, status | before the first step |
| `build/` | step scripts `NNN_name.py`, `kit.py`, `mannequin.py`, `order.txt` (the scripts that ran, in order), `data/` (baked numbers a step reads) | as built |
| `steps/<NNNN>-<name>/` | `script.py` (the code that ran), `state.json`, `preview.png`, `result.json`, `stdout.log` | one per step |
| `workflow.jsonl` | one row per operation | as built |
| `textures/` | images painted by step scripts, loaded as `//textures/...` | as built |
| `Docs/Critique.md` | `## Round <n>` sections: shot, what is weak, the fix | critique rounds |
| `shotlist.json` | one entry per shot (below) | before release |
| `Docs/Report.md` | what was made, what works, what is weak, render settings and time, steps, what next | before release |
| `out/` | `film.mp4`, `animatic_clay.mp4`, `contact_sheet.png`, `scene.blend`; a final film also `greybox.mp4` (rendered at the end of its grey-box stage) | release |
| `review/review-<NN>.json` | a reviewer's scores and decision (`film-review/v1`; [review.md](review.md)) | after release |

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
 "subject": "TeaBowl", "script_lines": "1-3", "panels": ["P1"], "description": "Dusk. The room: the bowl on the chest under the lit lantern. Slow dolly in.",
 "events": [{"name": "lantern starts to swing", "object": "Lantern_Pivot", "frame": 132}]}
```

`script_lines` names the lines of `Brief.md` the shot covers; `panels` (storyboard input) the panels of the
breakdown's table. Every other value is checked against the scene by `tools/shots.py` ([shot-facts.md](shot-facts.md)).

## The scene

One scene, one timeline, the film's format as in `film.json`; one camera object per shot, each bound to a timeline
marker at its first frame; every object named for what it is; every rendered mesh with a material; nothing left of
the default file; nothing linked or loaded from outside the film.

## The trajectory

`tools/trajectory.py <film>` writes `<BFF_ROOT>/.recording/<slug>/trajectory/`: `trajectory.jsonl`
(`film-trajectory/v1`, one event per line in time order: `i, time, type` (`user` / `thinking` / `assistant` / `tool`), `text` (a `thinking` event is a reasoning summary the
agent saved), or
`tool, input, result, error`, and `image` for a picture the model opened), `images/`, `trajectory.md` and
`analysis.json` (events, step calls, `note_coverage`, `looked_coverage`, missing pictures, leaks, secrets redacted).
Tool results are kept whole. Paths are rewritten to `<film>`, `<tools>`, `<root>` and `~`, the owner's and the tool
repos' names to `<name>`, the organisation to `<org>`, the machine's account name to `<account>`, and secrets (keys,
tokens, passwords) to `<secret:kind>`. `note_coverage` is the share of steps with a reply or a
saved reasoning summary before them; `reply_coverage` counts replies alone. Nothing is added to a record after
the session.

## The dataset archive

`tools/pack.py <film> [--out <zip>]` writes one zip with a folder `<slug>-<title>/`: `film/` (every tracked file at
HEAD, pictures and videos as content), `history/commits.jsonl` (ordered commit hashes, parents, timestamps, messages and text diffs;
`--no-history` leaves it out), `trajectory/` (a fresh export) and `DATASET.md` (what is
there, with counts). It packs only when the film is valid for release, the export has no leak, the JSONL history has valid commit links and covers the saved steps, and no text file holds the account name, the organisation, a `private_names` entry of the
machine config or a banned name. The raw recording (`<BFF_ROOT>/.recording/<slug>/`: `actions.jsonl`,
`messages.jsonl`, `commits.jsonl`, as the hooks wrote them, with machine paths and names) is never packed. Commit author and committer identities are omitted.

## Release checks (`--release`)

`out/film.mp4` is H.264 at the scene's size and frame rate with exactly the scene's frame count and no
near-uniform frame; `out/animatic_clay.mp4` has the same frame count and rate; the contact sheet, the scene copy,
the critique and the report exist; `shotlist.json` holds (`tools/shots.py`); the last `tools/replay.py` said
`REPLAY OK`; a final film has `out/greybox.mp4`; a storyboard input has its pages; and the record holds: a note and
a look at a picture before at least 85 % of the steps, every opened picture still there, no account name, address,
owner's name or secret left in it (a redacted secret is a warning: rotate it). Counts of the scene (triangles, materials, lights) are reported as warnings only: a
person judges the picture ([review.md](review.md)).

## Names

No tracked text file and no commit message holds the names of the toolkit, its owners, an agent, a model or their
makers, an attribution trailer, or a machine path with the account name.

Commit records use `film-commit/v1`. Each patch compares the commit with its first parent; the root compares
with an empty tree. Binary changes are identified in the patch; current binary files are in `film/`.
Author identities are omitted and exported text is scrubbed. Commit hashes identify the original commits.

Validate an unpacked dataset or ZIP with `tools/validate-package.py <zip-or-folder>`.
This checks required files, JSONL schemas and sequence numbers, unique commit IDs, parent ordering,
timezones and step-to-commit coverage, and rejects `.git` and unsafe archive paths.
Source-film validation uses Git during production; dataset verification reads JSONL without Git.
