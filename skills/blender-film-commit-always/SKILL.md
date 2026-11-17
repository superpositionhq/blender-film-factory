---
name: blender-film-commit-always
description: 'Commit discipline for every blender-film-factory session (film sessions and helpers). Use whenever you change files in a film repo or in blender-film-factory, before ending any turn, and when deciding what may be committed or pushed. Covers the step tool (one step, one picture, one commit), messages, workflow.jsonl rows, LFS, what never to commit, push policy and the WIP auto-commit hook.'
---

# Commit always (Blender films)

Save the build as a sequence of small, useful commits. Each commit should show one concrete change
and retain the files needed to reproduce it. Commit throughout the session, including incomplete work,
failed steps and subsequent fixes. Finish each turn with all of your changes saved in git.

A complete film must have a complete build history: scripts, workflow rows, rendered step images and
commits. Keep each change small enough to review on its own. Do not manufacture empty steps.

## The step tool makes the commit

A film's scene changes only through `tools/step.py` (blender-film-session skill, "The step"). One call runs one step
script in Blender, saves the step folder with its picture, writes the workflow row and **commits**. So the cadence of
commits is the cadence of steps:

- **One step per visible change**: one object's blockout; one object's model (a large one in 2-3 steps); one
  material family; one light; one shot's camera; one animation beat; one fix.
- **Never batch.** Never several objects in one step script, never several fixes, never "model and material" of an
  object together. _(why: a task is cut from one thread of the history, one object from blockout to finished or one
  issue from finding to fix; a step that holds three threads belongs to none of them)_
- **A step script is short**: one thing a viewer could point at. Past about 120 lines of new code it is two steps.
  Never split one change into empty steps to make the history longer.
- **A failed step is committed too** (the tool does it): the folder, the row with status `failed`, the commit
  `Failed: ...`. Then fix the script and run it again as a new step. Dead ends are the most useful part of the record.
- **Never end a turn with uncommitted work of yours.** Last thing of every turn: `git status` in the film repo,
  commit what is yours, report the sha.

Everything that is not a scene change is committed by hand, one thing per commit: the brief, the breakdown, the
treatment, a critique round's notes, the shot list, the report.

## Which repo, which files

- **Film session:** your film repo (`<BFF_ROOT>/films/<slug>`): `git add -A` is fine there, it is yours alone. You
  edit nothing in blender-film-factory.
- **Helper:** blender-film-factory is one checkout shared by several sessions. Stage explicit paths
  only, never `git add -A` / `git commit -a`, never commit another session's changes.

## Message

- A step's subject is the step name you give the tool: **what changed on screen**, imperative, specific, under ~72
  characters: `Block out the chest as a box against the back wall`, `Give the bowl a foot ring and a rounded rim`,
  `Fix the bowl sinking into the floor at the impact`. Not `Update scene`, not `Add objects`, not `Progress`.
  A change nobody can see (render settings, a rename) says what it does instead.
- The tool writes the body: the reason you gave, `step: <NNNN-name>`, `workflow: <row id>`.
- A fix names what was wrong on screen in its subject; its reason names the picture it was seen in.
- A hand commit: the same subject rule; the body says why, and ends with the workflow rows it covers
  (`workflow: ks-00041..ks-00043`). A commit that acts on a human direction names it:
  `Direction: ks-00038 (<the direction in a few words>)` (the tool adds it with `--direction`).
- Film repos: no AI attribution trailers or footers (`Co-Authored-By: <agent> ...`, `Generated with <tool>`) and
  never the names in the blender-film-session skill, "Names": commit messages ship in the dataset.
  blender-film-factory commits follow the normal attribution rules.

## workflow.jsonl

- One row per real operation, written **when it happens** (schema `film-workflow/v0`: `schema, id, seq, time, actor,
  op, target, params, reason` (brief action purpose or visible issue), `reason_source, status` (`observed`/`failed`/`reverted`),
  `source {script, sha256, commit}`).
- **A step's row is written by `tools/step.py`** from `--op`, `--target` and `--reason`. Ops for steps:
  `scene.start`, `scene.blockout`, `camera.shot`, `anim.block`, `object.model`, `material.make`, `light.setup`,
  `fx.add`, `anim.polish`, `camera.polish`, `render.settings`, `comp.grade`, `critique.fix`, `fix`.
- **Everything else you write with the row tool**, as you do it:
  `python3 <BFF_ROOT>/blender-film-factory/tools/workflow-row.py <BFF_ROOT>/films/<slug> --op <op> --target <what> --reason "<brief action purpose or visible issue>" [--param key=value]`
  (`python` on Windows). Ops: `brief.write`, `breakdown.write`, `treatment.write`, `greybox.render`,
  `critique.issue` (one per issue: target the object or shot, `--param round=<n> --param frame=<n>`, the reason
  says what is wrong on screen), `shotlist.write`, `report.write`, `release`. A `critique.fix` step names its
  issue: put the issue row's id in the reason (`fixes ks-00101`).
- Never edit, delete, reorder or backfill rows. Missed something: one `op:"log.gap"`, `--status unrecorded` row
  saying what and when.
- **One exception: banned names.** A row that contains a banned name is edited in place to remove it and nothing
  else, then one `op:"log.correct"` row is appended (`--param rows=[ids]`), and the commit message names the rows.
  The tool refuses a new row that holds one.
- **Human directions (owner's rule: "not direct user messages, more like user directions").** Whoever receives a
  user message REWRITES it as a direction: what to change and why, one or two neutral sentences, without tone,
  profanity, names or chat wording. The direction is SAVED at once, before any action:
  `workflow-row.py <film> --op user.direction --target <area> --reason "<the direction>"`
  (`target`: `story`, `camera`, `lighting`, `animation`, `art`, `edit`, `sound`, `process`...). Every later step
  that acts on it carries `--direction <that row id>`. The raw message is never stored in the repo (the machine's
  hooks keep every prompt as typed in the recording's `messages.jsonl`). One row per direction, not per message.

## What to commit

Everything needed to rebuild the film from the repo alone: `film.json`, `Brief.md`, `Docs/`, `build/` (every step
script, `kit.py`, `mannequin.py`, `order.txt`, `build/data/`), `steps/`, `workflow.jsonl`, `shotlist.json`,
`textures/` (images your scripts generate), `storyboard/` (a storyboard input), `out/`, `README.md`.

- **Binaries go through Git LFS, and only binaries**: pictures, videos, sound, `.blend`. The template's
  `.gitattributes` covers them; check a new type with `git check-attr filter -- <file>` (must say `lfs`). Scripts,
  JSON and Markdown are plain text: the diffs are the dataset.
- **`scene.blend` is not committed while you build** (it is ignored): it is the result of `build/order.txt`, and a
  copy per step would be hundreds of megabytes. `tools/release.py` commits the finished one as `out/scene.blend`.
- **Never commit** `.local/` (checkpoints, test renders, frames), `__pycache__`, logs outside `steps/`, secrets,
  anything under `<BFF_ROOT>/.recording/` (hook-owned; never edit it either), or a file from outside the film
  that the rules do not allow (blender-film-session skill, "Everything is made here").

## Never rewrite

**Never amend, squash or rebase a commit you made**: `commits.jsonl` and the step folders name its sha. A step that
came out wrong stays, and the next step fixes it. Never renumber or delete a step folder.

## Push policy

- **Never push unless the person says so.**
- When told: `git push origin main --follow-tags`, then verify `git ls-remote origin main` matches
  `git rev-parse HEAD` and `git lfs push origin main --dry-run` lists nothing left.
- Film repos live at `<org>/film-<slug>` (private; `<org>` = `github_org` in the machine config). Never force-push.

## The WIP auto-commit

The Stop hook commits leftover changes in a film repo as `WIP` at the end of every turn, except while conflicts
are unresolved or HEAD is detached. It is a safety net so nothing is lost, not a way of working: a `WIP` commit
carries no reason and no row ids (`tools/validate-film.py` counts them). If one of yours appears, say in your next
commit's body what it contained. Do not squash or amend it away. The hook does not cover blender-film-factory.
