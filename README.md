# blender-film-factory

Film-**making trajectories**: how a short film gets made in Blender from a script, step by step, as training data.

Coding-agent sessions (Claude Code or OpenAI Codex CLI) each make one short film in Blender 5.2, headless and in
code, in its own git repo. What is recorded as it happens: the model's note before each step (what the picture
shows, what comes next and why), one step script, one picture and one commit per visible change, the scene state
after every step, and every tool call with its whole result. `tools/trajectory.py` exports that as one ordered
trajectory per film; a person reviews the film and its record before it is used.

| Input | Output |
|---|---|
| `script`: a written script | `greybox`: a grey-box video (mannequins and blocks: staging, motion, camera, cuts) |
| `storyboard`: a script with storyboard pictures | `final`: a fully rendered film, which also delivers its grey-box video |

## Getting started

**Before every new film, update blender-film-factory:** `git -C <BFF_ROOT>/blender-film-factory pull`, then
`python3 <BFF_ROOT>/blender-film-factory/machine/bootstrap.py` (`python` on Windows).

On a Mac or a Windows PC with git, Git LFS, Python 3.9+, Blender 5.2 LTS, ffmpeg, the GitHub CLI and a coding agent
(Claude Code, or OpenAI Codex CLI):

1. Clone this repo into the machine root: `git clone <this repo> ~/FilmWork/blender-film-factory`.
2. `python3 ~/FilmWork/blender-film-factory/machine/bootstrap.py --org <org>` (`<org>` = the GitHub organisation
   or user that will own the private `film-<slug>` repos). It writes the machine config, finds Blender and ffmpeg,
   installs the skills and, after asking, the recording hooks.
3. `python3 ~/FilmWork/blender-film-factory/machine/check.py` until nothing says FAIL
   ([docs/new-machine.md](docs/new-machine.md)).
4. Start the first session: in a terminal in the root (`claude`, or `codex`), one film with
   [docs/briefs/solo-film.md](docs/briefs/solo-film.md).

## How a film goes from input to release

1. **New film**: `templates/new-film.py --input script|storyboard --output greybox|final` creates `<BFF_ROOT>/films/<slug>`:
   `film.json`, the brief and treatment pages, the step kit (`build/kit.py`) and the mannequin kit
   (`build/mannequin.py`), the first `workflow.jsonl` row, the post-commit hook, the first commit, a private GitHub
   repo (not pushed).
2. **Brief** (the script, word for word; storyboard pictures through `tools/storyboard.py`), the **breakdown** of
   the script into cast, places and timed beats, then the **treatment** with the object list and the shot list.
3. **Steps**: `tools/step.py <film> "<what changes on screen>" build/NNN_name.py --op .. --target .. --reason ..`
   runs one script in headless Blender and records it: `steps/NNNN-name/` (script, scene state, picture), the row,
   the commit. The session looks at the picture before the next step.
4. **Order**: blockout, cameras bound to markers, blocked animation, the grey-box video and its fixes; a greybox
   film then polishes and stops; a final film goes on to models, materials, lighting, polish, render settings and
   grade; critique rounds on rendered frames against the script.
5. **Checks**: `tools/shots.py` measures every shot and checks `shotlist.json`; `tools/replay.py` rebuilds the scene
   from an empty file and compares; `tools/validate-film.py` says VALID or INVALID.
6. **Release**: `tools/release.py` renders the film and the clay animatic, builds the contact sheet, copies the
   scene, exports the trajectory, runs the checks and commits.
7. **Review**: a second person scores the film and its record (`tools/review.py`, [docs/review.md](docs/review.md)).

## What a film leaves behind

```
<BFF_ROOT>/films/<slug>/          the film repo; its git history
  film.json  Brief.md  Docs/      the script; breakdown, treatment, critique, report
  storyboard/                     storyboard input: the pages as given
  build/                          every step script in order (order.txt), kit.py, mannequin.py, baked data
  steps/<NNNN>-<name>/            script.py, state.json, preview.png, result.json, stdout.log
  workflow.jsonl                  one row per operation, with its reason
  shotlist.json                   every shot: frames, camera, move, size, angle, subject, events
  out/                            film.mp4, greybox.mp4 (final films), animatic_clay.mp4, contact_sheet.png, scene.blend
  review/                         a reviewer's scores and decision
<BFF_ROOT>/.recording/<slug>/
  commits.jsonl                   one row per commit
  actions.jsonl                   every tool call of the sessions that made it
  messages.jsonl                  every prompt the person typed and every reply the model wrote
  trajectory/                     trajectory.jsonl, trajectory.md, images/, analysis.json (tools/trajectory.py)
```

## Read first

- [AGENTS.md](AGENTS.md): what every session reads first: the skills, the core rule, the priorities, the rules.
- [docs/film-format.md](docs/film-format.md): a film repo's files, `workflow.jsonl`, `shotlist.json`, the validator.
- [docs/shot-facts.md](docs/shot-facts.md): how camera move, shot size, angle and subject are measured.
- [machine/README.md](machine/README.md): the machine root, the config, the recording hooks.
- [docs/briefs/solo-film.md](docs/briefs/solo-film.md): the prompt that starts a film session.
- [docs/review.md](docs/review.md): how a released film and its record are scored.

Films, recordings, pictures and videos do not go in this repository.
