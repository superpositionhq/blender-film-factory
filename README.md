# blender-film-factory

Film-**creation** data: how a short film gets made in Blender, step by step, with the finished film as ground truth.

Coding-agent sessions (Claude Code or OpenAI Codex CLI) each make one short film in Blender 5.2, headless and in
code, in its own git repo, and the creation is recorded as it happens: one step script, one picture and one commit
per visible change, the scene state after every step, a `workflow.jsonl` row per operation with its reason, and
every tool call, prompt and reply of the session. Later tasks are cut from that real history.

A film is one of four kinds:

| | from a written prompt (`text`) | from a reference clip (`video`) |
|---|---|---|
| a finished picture (`final`) | models, materials, light, grade | the clip recreated shot for shot, finished |
| a previsualisation (`previs`) | mannequins and blocks: staging, motion, camera, cuts | the clip recreated shot for shot as a white model |

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

1. **New film**: `templates/new-film.py --input text|video --output final|previs` creates `<BFF_ROOT>/films/<slug>`:
   `film.json`, the brief and treatment pages, the step kit (`build/kit.py`) and the mannequin kit
   (`build/mannequin.py`), the first `workflow.jsonl` row, the post-commit hook, the first commit, a private GitHub
   repo (not pushed).
2. **Brief** (and, for a clip, `tools/reference.py` and the breakdown), then the **treatment** with the object list
   and the shot list.
3. **Steps**: `tools/step.py <film> "<what changes on screen>" build/NNN_name.py --op .. --target .. --reason ..`
   runs one script in headless Blender and records it: `steps/NNNN-name/` (script, scene state, picture), the row,
   the commit. The session looks at the picture before the next step.
4. **Order**: blockout, cameras bound to markers, blocked animation, the blockout animatic and its fixes; then
   models, materials, lighting, animation and camera polish, render settings and grade (previs stops at mannequins,
   blocks and polish); critique rounds on rendered frames.
5. **Checks**: `tools/shots.py` measures every shot and checks `shotlist.json`; `tools/replay.py` rebuilds the scene
   from an empty file and compares; `tools/validate-film.py` says VALID or INVALID.
6. **Release**: `tools/release.py` renders the film and the clay animatic, builds the contact sheet (and the
   side-by-side comparison for a clip), copies the scene, runs the checks and commits.

## What a film leaves behind

```
<BFF_ROOT>/films/<slug>/          the film repo; its git history
  film.json  Brief.md  Docs/      the input and its modes; treatment, critique, report
  reference/                      video input: the clip, its cuts, frames and sheets, the breakdown
  build/                          every step script in order (order.txt), kit.py, mannequin.py, baked data
  steps/<NNNN>-<name>/            script.py, state.json, preview.png, result.json, stdout.log
  workflow.jsonl                  one row per operation, with its reason
  shotlist.json                   every shot: frames, camera, move, size, angle, subject, events
  out/                            film.mp4, animatic_clay.mp4, animatic_blockout.mp4, contact_sheet.png, scene.blend
<BFF_ROOT>/.recording/<slug>/
  commits.jsonl                   one row per commit
  actions.jsonl                   every tool call of the sessions that made it
  messages.jsonl                  every prompt the person typed and every reply the model wrote
```

## Read first

- [AGENTS.md](AGENTS.md): what every session reads first: the skills, the core rule, the priorities, the rules.
- [docs/film-format.md](docs/film-format.md): a film repo's files, `workflow.jsonl`, `shotlist.json`, the validator.
- [docs/shot-facts.md](docs/shot-facts.md): how camera move, shot size, angle and subject are measured.
- [machine/README.md](machine/README.md): the machine root, the config, the recording hooks.
- [docs/briefs/](docs/briefs/): the prompts that start a film session (solo and coordinated).

Films, recordings, pictures and videos do not go in this repository.
