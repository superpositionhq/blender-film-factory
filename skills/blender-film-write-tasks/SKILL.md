---
name: blender-film-write-tasks
description: 'How a blender-film-factory session writes the tasks a film ships with: what a task is (a thread of the film''s real history that a person directed and that took several steps or rounds to settle, never a single fix), task threads opened and closed while the film is made, picking the start and the reference step, the two scene snapshots, the brief written as what a viewer sees, the scoring points composed from the checker''s probes (measured, never a picture judge asked about taste), proving every task with tools/task-check.py, the list of threads that could not be written and why, and what must never reach the solver. Use when the person asks for tasks, at the end of a film session after the release, and when a task comes back from review.'
---

# Writing a film's tasks

A task gives another agent one stretch of this film's real work to do again: a saved scene to start from, a brief,
and nothing else. A checker then scores what that agent hands back. Tasks are written from how the film was really
made, never invented at the end.

Tasks live outside the film: `<BFF_ROOT>/tasks/<slug>/<task name>/`. _(why: a film's repo is its record; task work
is not part of how the film was made)_ Nothing in the film repo names them. Use this skill and the blender-film-factory
tools only.

## 1. What a task is

**A task is a thread.** A thread is a stretch of the film's history that:

1. **a person asked for**: one or more `user.direction` rows, given during the work or at a review stop
   (blender-film-session, "Review stops and task threads"). A weakness the session found by itself is not a thread;
2. **took real work to settle**: at least 3 steps acted on it, or the first attempt did not hold and the person
   asked again;
3. **settled several things**: at least 3 outcomes that can each be checked on their own, so part of the work earns
   part of the score;
4. **ended in a verdict**: the person said the result was right. The step they accepted is the reference. A fix the
   person called no better is not a reference: extend the thread to the round they accepted, or drop it;
5. **can be checked**: every outcome can be measured by the checker's probes (section 5). A thread nothing can
   measure is not a task: it goes on the skipped list (section 7).

**Never a single fix.** One step, one setting, one object moved: a strong agent does that in a minute, and it tells
nobody anything. Merge, don't split: a direction that took three rounds is one task from before the first attempt to
the accepted one; several issues raised together at one review stop are one task with a scoring point per issue.

**Spans may overlap; issues may not.** Two tasks may share steps. No two tasks check the same outcome.

Fewer tasks is an acceptable result. A film whose person gave few directions has few tasks; do not make threads up.

| kind | the thread | start | reference |
|---|---|---|---|
| `correction` | a direction that took several steps or rounds to satisfy | the last step before the first direction | the step the person accepted |
| `bug_fix` | something broken that the person reported (floating, passing through, popping, lost from frame) | the last step before the first attempt | the fix that held |
| `feature` | something the person asked to be added, built over several steps | the last step before it | its last step, once accepted |
| `change` | a look or timing pass the person asked for (light, colour, materials, camera, pace) | the last step before the pass | its last step, once accepted |

`phase` says which stage of the film the thread belongs to: `layout` (blocks, cameras, cuts), `look` (models and
materials), `motion_light` (animation and lighting), `final` (render, colour, the finished picture).

## 2. Threads are opened while the film is made

The session opens and closes threads as the work happens (blender-film-session, "Review stops and task threads"): a
`task.open` row holds the start step, the ask in a viewer's words and the plan for checking it, written **before**
any fix exists; a `task.close` row holds the reference step and the verdict. _(why: a check planned after the fix
leans on the names, places and timings the fix happened to invent, and fails every other good solution)_

When you write tasks, list the film's threads first:

```
python3 <BFF_ROOT>/blender-film-factory/tools/task-check.py threads <BFF_ROOT>/films/<slug>
```

It prints every opened thread with its direction rows, its steps, its plan and whether it closed. Write one task per
closed thread that meets section 1. A film made before threads were recorded has none: read `workflow.jsonl` for
`user.direction` rows and the steps that carry them (`"direction"`), and treat each run of directions on one subject
as a thread; its checks are then planned after the fact, so hold them all the harder to section 5's second-solution
rule.

## 3. The two snapshots

```
python3 <BFF_ROOT>/blender-film-factory/tools/task-check.py snapshot <BFF_ROOT>/films/<slug> <task name> --start <step> --reference <step>
```

copies the saved scene of each step into the task folder as `start.blend` and `reference.blend`, each with its
textures packed inside. `<task name>` is `<slug>-<kind>-<what>` in lower case and hyphens (`k7-change-key-light`).
If a step's saved scene is gone, `tools/replay.py <film> --keep` rebuilds them.

- **Open the start and confirm the issue is there**: render the start step's picture and look. If the start already
  shows what the brief asks for, the start is too late.
- **The start comes before the first attempt**, so the solver faces everything the thread settled.
- **The reference does everything the brief asks.** An ask the reference does not meet is taken out of the brief, or
  the reference moves to a later step that meets it.

## 4. The brief

`instruction` in `task.json`. The reader is a capable 3D artist who has never seen the film and gets only
`start.blend` and these words.

- **Only what a viewer sees.** What is wrong or missing in the picture or the motion, item by item, then what is
  wanted. No cause, no place to look, no setting, modifier, node or value, unless the person's direction itself
  named a number ("the shot should last four seconds").
- **Written from the context, never quoted.** No chat wording, no tone, no names of people.
- **Name what the start already has** by the name it has there (an object, a camera, a shot), so the solver and the
  checks mean the same thing. Anything the solver must add gets its name in the brief only if a check needs to find
  it by name; otherwise checks find new things by what they are (section 5).
- **Say what must stay as it is** when the thread kept it on purpose (the camera, the set, the timing).
- **Never describe the fix or any step of the thread.** Never say how many changes are needed.
- Close with the bar the film was held to: everything is made in the scene, no placeholder shapes left visible, the
  file still opens and renders.

## 5. Scoring points

`items` in `task.json`: the format, every probe and every field are in
[docs/task-check.md](../../docs/task-check.md). Read it before writing an item.

**One required measured point per outcome the thread settled, at least 3.** Go through the brief ask by ask and give
each its own item. Weights: +10 for what decides whether the task is done (at least two), +7 for what a good answer
also has, +3 for finish. Negative items (-3, -7, -10) name an error that would spoil the result, above all changing
what the brief said to keep.

**Measure; never ask a picture judge about taste (rule).** A point about how something looks is scored by a
measurement of the scene or of the rendered frame, with its threshold taken from this film's own start and reference.
A judge item may ask one plain fact a picture shows, a fact two people would answer the same way ("is the cup on the
table", "is the face visible"). It never asks whether something is good, balanced, appealing, intentional or well
made. An outcome that only such a question could score is not scored: if it was one of the thread's three, the
thread goes on the skipped list.

| the brief asks that | measure with |
|---|---|
| something stands, sits or rests where it should; nothing floats or passes through | `object` (`gap_below`), `contact` |
| something is in the shot, at a size, away from the edge, not hidden | `framing`, `picture` (`area_share`, `edge_margin`, `visible_share`) |
| a colour, a finish, a surface | `material`, `picture` (`subject_saturation`, `hue_distance`, `hue_groups`) |
| the subject is lit, stands out, nothing is blown out or lost in black | `light`, `picture` (`separation`, `clipped_share`, `crushed_share`) |
| a movement eases, holds, arrives, does not jump | `motion` |
| shots, their order, their length, which camera | `shots`, `render` |
| the file is whole | `file` |

Rules every item meets:

- **It fails on the start for the reason the brief gives, and passes on the reference.** The checker proves this.
- **Thresholds come from the two snapshots** (`calibrate`, `start_plus`, `start_times`, or a `gradient` from start to
  reference), or from a number the brief states. Never from a number that only happens to fit the reference.
- **A different good solution passes too** (the second-solution rule). An item picks objects by a name the start
  already has or the brief gives, or by what they are (`"new": true`, a type, a place). Never by a name, a material
  name, a modifier or a keyframe count that only the reference has. Measure what the viewer gets (the cup stands on
  the table), not how the film got it (a constraint named `Stick`).
- **One point per outcome.** Never score the same thing twice.
- **Nothing the brief does not ask.** A point the brief never mentions is a hidden preference.
- **What must stay** is a negative item with `"op": "changed"` on what the brief said to keep.

**Never make a task easier.** If the reference fails an item, the item or the task is wrong: fix the item so it asks
exactly what the brief asks, move the reference, or drop the task. Never widen a threshold, make a required point
optional or remove an ask so that the check passes.

## 6. Prove every task

```
python3 <BFF_ROOT>/blender-film-factory/tools/task-check.py check <BFF_ROOT>/tasks/<slug>/<task name>
```

measures both snapshots and writes `check/result.json` and `CARD.md`. Only **VALID** tasks ship: the untouched start
scores 0, the reference scores everything, every name passes the second-solution rule. Read every problem line, fix
the task, run it again. Then open `CARD.md` and read it as the reviewer will: one page, the brief, each point in a
sentence, what it read on the start and on the reference.

Judge difficulty yourself, with the person: would a strong agent given only the brief and the start solve it in a
few minutes? It would when the brief points at one thing, or the issues share one obvious cause. Then extend the
thread to an earlier attempt, merge it with its neighbours, or drop it. Do not start another agent on the task to
find out.

## 7. The skipped list

Every closed thread that did not become a task is one line in `<BFF_ROOT>/tasks/<slug>/skipped.jsonl`:

```
{"thread": "<slug>", "directions": ["<row id>", ...], "ask": "<what the person wanted, in a viewer's words>", "reason": "too_short | no_verdict | cannot_measure | start_already_right | reference_does_not_meet_it", "detail": "<one sentence: for cannot_measure, exactly what would have to be measured and why no probe reads it>"}
```

_(why: `cannot_measure` lines are how the checker grows. Each one names a measurement that does not exist yet; when
it does, the thread is written)_ Never drop a thread silently, and never bend a thread into a task by checking
something easier than what the person asked.

## 8. What must never reach the solver

The solver gets `tools/task-check.py split <task> --out <dir>`: `task.json` without its items, and `start.blend`.
The scoring points, `reference.blend`, `check/`, `CARD.md` and the film's repo never reach it. So the brief holds
nothing of the scoring points, and `start.blend` holds nothing of the answer: no hidden finished copy of an object,
no text, name or custom property that spells out what to do. Open the start's object list and check.

## 9. When a task comes back from review

A reviewer reads `CARD.md` and answers four questions: does each point follow from the brief; would another good
solution earn every point; is anything counted twice or scored from something the brief never says; does each error
item name something that would really spoil the result. Fix what they name under section 5's rules, run the check
again, and say in one line what changed. A task that cannot be fixed without easing it is dropped and goes on the
skipped list.
