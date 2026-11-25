# Task checks

A **task** is one stretch of a film's making, cut out so that another agent can be asked to do it again: the scene
as it was before (`start.blend`), an instruction that says what is wrong or wanted, the scene after the fix that
held (`reference.blend`), and a list of scoring points (**items**). `tools/task-check.py` proves a task on its own
two scenes and scores any other scene against it.

```
python3 tools/task-check.py snapshot <film> <name> --start <step> --reference <step>   # the two scenes, from step checkpoints
python3 tools/task-check.py validate <task>          # the task file alone
python3 tools/task-check.py check <task>             # measure both scenes: VALID / INVALID / NEEDS JUDGE; writes CARD.md
python3 tools/task-check.py grade <task> <scene.blend> --out <dir>    # reward 0..1 for another scene
python3 tools/task-check.py split <task> --out <dir> # the solver's half: the instruction and start.blend
python3 tools/task_check/probe_tests/run.py          # the checker's own test, on scenes it builds itself
```

A task is a folder: `task.json`, `start.blend`, `reference.blend`, then `check/` (measurements, judge pictures,
`result.json`) and `CARD.md` once checked. The two scenes are the truth of the task: they are stored, not rebuilt.

## Rules of a task

1. **Outcomes, not implementations.** An item measures what the scene is like, never how it was made. A different
   solution that is as good earns the same. _(why: the solver is free to choose its route)_
2. **Only names the solver knows.** An item may select an object by name only when that object is in the start
   scene or the instruction gives the name. Anything else is selected by what it is (`type`, `new`, `near`) or by
   shot number. The checker refuses a name that only the reference has.
3. **The untouched start earns 0.** Every positive item fails on `start.blend`, and no negative item is tripped.
4. **The reference solves it.** Every positive item is fully met on `reference.blend` and no negative item is
   tripped. An item that measures nothing on the reference makes the task INVALID.
5. **One item, one thing.** No item counts something another item already counts, and no item gives points and
   takes points for the same thing.
6. **Nothing hidden.** Every item follows from the instruction: word for word (`Explicit`) or as a consequence
   nobody could dispute (`Implicit`). A preference the instruction does not state is not scored.
7. **Measure first.** A judge is for what only a picture can show. What decides the task (the +10 items) is measured.
8. **Never ease a check to make it pass.** If the reference fails an item, the item or the task is wrong: fix that.

## task.json (`film-task/1`)

```json
{"schema": "film-task/1", "name": "cup-on-the-table", "title": "The cup hovers and reads as grey",
 "phase": "look", "kind": "correction", "difficulty": "easy",
 "seed": {"film": "<slug>", "start": 31, "reference": 36},
 "instruction": "The cup hovers above the table. It should stand on the table top. ...",
 "items": [ ... ]}
```

`phase`: `layout`, `look`, `motion_light`, `final` (the review the correction came from). `kind`: `correction`,
`bug_fix`, `feature`, `change`. `seed.start` / `seed.reference`: the steps the scenes were taken at. The
instruction describes what is seen and what is wanted, as a reviewer would; it names no cause and no method.

### An item

```json
{"id": "R01", "description": "The cup stands on the table top: neither hovering nor sunk in.",
 "dimension": "staging", "criterion_type": "Objective", "criterion_necessity": "Explicit",
 "type": "binary", "weight": 10, "required": true,
 "measure": {"probe": "object", "select": "Cup", "frame": 1, "field": "gap_below", "abs": true},
 "expect": {"op": "<=", "value": 0.02}}
```

| Field | Values |
|---|---|
| `id` | `R01`, `R02`, ... kept through revisions |
| `description` | one sentence: the thing judged, the condition, the expected result |
| `dimension` | `completeness`, `requirement_alignment`, `staging`, `modelling`, `materials`, `lighting`, `motion`, `render_quality`, `engineering` |
| `criterion_type` | `Objective` (measured) or `Subjective` (judged from pictures) |
| `criterion_necessity` | `Explicit` (the instruction says it) or `Implicit` (it must follow from it) |
| `type` | `binary` (0 or 1) or `gradient` (0, 0.25, 0.5, 0.75, 1) |
| `weight` | `10` decides the task, `7` important, `3` finish; `-3`, `-7`, `-10` an error of that size |
| `required` | default true: counts towards "solved" |

A task has at least two `+10` items, at least three required positive items that are measured, and at least one
negative item; the negative weights add up to less than half the positive ones.

**A positive item** says what must be there. **A negative item** describes an error, and its `expect` is true
when the error has happened: what was right and is now broken ("the lamp was moved": `{"op": "changed"}`), or a
fault the fix tends to bring with it.

`measure`: a `probe`, its parameters, then how the rows become one value: `where` (keep rows whose fields equal
these), `field` (a dotted path, `loc.2` is z), `agg` (`first`, `last`, `count`, `any`, `all`, `share`, `distinct`,
`min`, `max`, `sum`, `mean`, `median`, `range`, `delta`), `abs`.

`expect`: `op` is `>=`, `<=`, `>`, `<`, `==`, `!=` (with `tol`), `between`, `in`, `contains`, `true`, `false`,
`changed`, `unchanged` (against the start, with `tol`; positions compare as a whole). The number compared against is
`value`, or `calibrate: 0.5` (half-way from the start's value to the reference's), or `start_plus`, or
`start_times`. A gradient item has `{"gradient": {"from": "start", "to": "reference"}}` (or numbers): how far the
value has come, rounded down to a level.

**A judge item** has `judge` in place of `measure` and `expect`: `shots` (frames to render, each with a camera by
name or `{"shot": k}`), one `question` a picture can answer, and for a gradient item the five `levels` described.
The checker renders the pictures for the start, the reference and the scene being graded; the answers come from a
file. Until they do, the verdict is NEEDS JUDGE and no `reward.json` is written.

Set `BFF_JUDGE` to a command and the checker asks it instead of waiting for a file: one JSON request per judge item on
stdin (`question`, `type`, `levels`, `pictures`), one JSON answer on stdout (`answer` 0..1, `reason`). The judge sees the
question and the pictures only. Its reasons are kept in `result.json` and `grade.json` (`judge_reasons`). A judge that
fails leaves the item waiting; it never becomes a guessed score (`tools/task_check/judge.py`).

### Selectors

`"Cup"` or `{"name": "Cup"}`; `{"glob": "Chair_*"}`; `{"type": "LIGHT"}`; `{"new": true}` (not in the start scene);
`{"near": {"point": "Table", "radius": 1.0}}` (a name or `[x, y, z]`); `{"top_level": true}`; `{"prop": "figure"}`.
Keys combine: `{"type": "MESH", "new": true, "near": {...}}` is "a new mesh near the table". An object stands for
itself and everything parented under it.

## Probes

All lengths in metres, angles in degrees. Each returns rows; `frame` or `frames` (`[1, 12]` or
`{"from": 1, "to": 24}`) says when.

| Probe | Parameters | Fields of a row |
|---|---|---|
| `object` | `select` | `loc`, `rot_deg`, `scale`, `centre`, `size`, `bottom_z`, `top_z`, `gap_below` (0 standing, positive hovering, negative sunk in), `hide_render`, `parts`, `tris`, `verts`, `materials`, `material_count`, `meshes_without_material`, `modifiers`, `animated`, `default_name`, `type`, `parent` |
| `material` | `select` | per material of the object: `base_color`, `hue_deg`, `saturation`, `value`, `roughness`, `metallic`, `alpha`, `emission_strength`, `transmission`, `*_linked` (driven by nodes), `nodes`, `image_textures`, `procedural_textures`, `principled`, `default_name` |
| `light` | `select`, `at` (a point or object) | `light_type`, `energy`, `color`, `loc`, `shadow`, `spot_deg`; with `at`: `distance`, `reaches` (power per square metre arriving, before shadows), `share`, `total_reaching` |
| `world` | | `color`, `strength`, `luminance`, `environment_texture`, `nodes` |
| `render` | | `engine`, `resolution_x`, `resolution_y`, `fps`, `frames`, `seconds`, `samples`, `denoise`, `view_transform`, `look`, `exposure`, `gamma`, `film_transparent`, `motion_blur`, `compositing`, `compositor_nodes`, `active_camera` |
| `shots` | | per shot: `shot`, `camera`, `frame_start`, `frame_end`, `frames` |
| `framing` | `select`, `camera` | `centre_in_frame`, `corners_in_frame`, `height`, `width` (share of the frame), `centre_x`, `centre_y`, `off_centre`, `distance`, `pitch_down_deg`, `occluded`, `lens`, `dof` |
| `motion` | `select`, `frames` | per object: `displacement`, `path_length`, `peak_speed`, `mean_speed`, `largest_step`, `turn_deg`, `reversals`, `hard_start`, `hard_stop` (first / last moving step as a share of the fastest: 1 is a dead start, near 0 is eased), `largest_speed_jump`, `first_moving_frame`, `last_moving_frame`, `lowest_bottom_z`, `highest_bottom_z` |
| `contact` | `a`, `b` | `rests_gap` (a's bottom above b's top), `over` (share of a's footprint above b), `sunk`, `box_overlap`, `box_distance`, `centre_distance` |
| `file` | | `objects`, `meshes`, `lights`, `cameras`, `materials`, `tris`, `libraries`, `images_unpacked`, `images_missing`, `images_outside`, `default_named_objects`, `meshes_without_material` |
| `screen` | `camera`, `width` | `luminance` (mean brightness of the rendered frame, 0 to 1), `dark_share`, `bright_share`. The only pixel statistic; use it calibrated or against the start |
| `picture` | `select` (the subject), `camera`, `width` | The rendered frame in numbers. Whole frame: `luminance`, `luminance_low`, `luminance_high`, `luminance_range`, `clipped_share`, `crushed_share`, `saturation`, `coloured_share`, `colourfulness`, `hue_groups`, `hue`. With `select` (the subject, found by rendering a mask of it): `in_frame`, `area_share`, `visible_share`, `centre_x`, `centre_y`, `box`, `headroom`, `footroom`, `edge_margin`, `touches_edge`, `centre_offset`, `thirds_offset`, `silhouette_fill`, `subject_luminance`, `surround_luminance`, `background_luminance`, `separation`, `subject_saturation`, `surround_saturation`, `hue_distance`, `subject_clipped_share`, `subject_crushed_share`, `highlights_on_subject`. Positions are shares of the frame, x from the left, y from the top |

A `camera` is a name, `{"shot": k}`, or left out for the camera the timeline shows at that frame.

## Reward and verdict

`reward = max(0, (weight earned by positive items + weight lost to negative items) / all positive weight)`, from 0
to 1. **Solved**: every required positive item fully met and no required negative item tripped.

`check` says **VALID** when the task file is in order, rule 2 holds, the start earns exactly 0, and the reference
solves the task; **NEEDS JUDGE** when only judge answers are missing; **INVALID** with one line per problem
otherwise. `grade` writes `grade.json` (every item's value) and, when no judge is waiting, `reward.json`:
`{"reward": 0.875}`. A scene that cannot be measured earns nothing for it: an item that measures nothing is not met.

## CARD.md

What a person reads to review a task without opening Blender: the instruction, then each item as a sentence, how it
is measured in plain words, what it read on the start and on the reference, and the verdict. The reviewer's
questions are at its end. `check` writes it; a VALID verdict is needed, and it is not enough: a person still reads
each item against the instruction.
