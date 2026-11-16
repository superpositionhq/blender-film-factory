# AGENTS.md — blender-film-factory: instructions for every session

This repo coordinates coding-agent sessions (Claude Code or OpenAI Codex CLI) that each make one short film in
Blender 5.2, headless and in code (`<BFF_ROOT>/films/<slug>`, private `<org>/film-<slug>` repos, `<org>` =
`github_org` in the machine config), and records how each is made: the step scripts, a picture and the scene state
of every step, `workflow.jsonl`, the git history and every tool call become a creation dataset, and later tasks are
cut from that real history. `<BFF_ROOT>` is the machine root (env `BFF_ROOT`, else `root` in
`~/.blender-film-factory/config.json`, else `~/FilmWork`); see [machine/README.md](machine/README.md). Claude Code
reads this file through [CLAUDE.md](CLAUDE.md); Codex reads it directly (and through `<root>/AGENTS.md`).

**Before every new film, update blender-film-factory:** `git -C <BFF_ROOT>/blender-film-factory pull`, then
`python3 <BFF_ROOT>/blender-film-factory/machine/bootstrap.py` (`python` on Windows) so the skills your agent reads
and the hooks that record it are the new ones. The tools, rules and validator change often; a film made with old
ones can fail the checks.

A film has an input mode and an output mode, fixed when it is created:

| | `text` input: a written prompt | `video` input: a reference clip to recreate |
|---|---|---|
| **`final` output**: a finished picture | text to film | video to film |
| **`previs` output**: mannequins and blocks | text to previs | video to previs |

Skills (one source, [skills/](skills/); `machine/bootstrap.py` copies them to `~/.claude/skills/` for Claude Code
and `~/.agents/skills/` for Codex; read the `SKILL.md` named here before the work it covers, whichever agent you
are). They carry a `blender-film-` prefix so they install next to another factory's skills:

- **blender-film-commit-always** ([SKILL.md](skills/blender-film-commit-always/SKILL.md)): every session. One step
  and one commit per visible change, never end a turn with uncommitted work, names that say what changed on screen,
  `workflow.jsonl` rows, LFS for binaries only, push only when the coordinator says.
- **blender-film-session** ([SKILL.md](skills/blender-film-session/SKILL.md)): every film. The start, the step tool
  and its pictures, the build order, cameras and markers, the shot list, names, recording, the deliverables.
- **blender-film-previs** ([SKILL.md](skills/blender-film-previs/SKILL.md)): films with `previs` output. Mannequins,
  blocks, previs colours, the plain light, what done means.
- **blender-film-final** ([SKILL.md](skills/blender-film-final/SKILL.md)): films with `final` output. Models,
  materials, lighting, depth of field, render, colour, critique rounds, floors.
- **blender-film-reference** ([SKILL.md](skills/blender-film-reference/SKILL.md)): films with `video` input. The
  clip's frames and sheets, the breakdown, timing, what must match, the comparison.

**Only these skills (owner's rule).** Contractors and every agent session working for blender-film-factory use the
skills above and no others. Never install, enable or invoke any other skill: not the person's own personal or
project skills, not a plugin's or a marketplace's skills, not the skills bundled with the agent, and not another
factory's skills even when the machine has them installed. A skill the agent offers by name or description that is
not one of these is ignored. Work no skill here covers is done by hand under these rules, or asked about (the
coordinator, or the person in a solo session). _(why: the recorded sessions are the dataset, so how a film gets made
must follow these rules only; another skill brings instructions and habits nobody here reviewed into the creation
record)_

Session briefs: [docs/briefs/film-session.md](docs/briefs/film-session.md) (started by a coordinator),
[docs/briefs/solo-film.md](docs/briefs/solo-film.md) (one person, one session). New machine:
[docs/new-machine.md](docs/new-machine.md). Film format and validator: [docs/film-format.md](docs/film-format.md).
Shot facts: [docs/shot-facts.md](docs/shot-facts.md).

**The core rule: one step, one picture, one commit per visible change.** A film's scene changes only through
`tools/step.py`: it runs one step script in headless Blender, saves the script, the scene state and a picture from
the shot camera, writes the workflow row and commits. One object, one material family, one light, one shot's
camera, one animation beat, one fix per step. A final film leaves roughly 80 to 130 steps, a previs 30 to 60.
_(why: the history is the dataset; a film built in ten big steps has no thread in it to cut a task from)_ The rule
is in the blender-film-session skill ("The step").

**Blender runs headless only.** No session opens the Blender window or takes over the screen.

**Priorities.** What ships is what matters, in this order: the film is whole (every frame renders, the format is
met, the deliverables exist); the history is dense and honest (one step per visible change, rows written as things
happened, the replay passes); the shot list is true of the scene; taste. No polishing loops outside the critique
rounds, and no re-doing a step to get a nicer picture of it.

This checkout is shared by several sessions at once: stage explicit paths only and never commit another session's
changes. A film session edits nothing here.

## What is here

| Part | Where |
|---|---|
| skills | `skills/` |
| machine setup, recording hooks (tool calls, prompts and replies, commits, the WIP auto-commit) | `machine/` ([machine/README.md](machine/README.md)) |
| film template (brief, treatment, step kit, mannequin kit) + `new-film.py` | `templates/` |
| the step tool and its Blender harness | `tools/step.py`, `tools/blender/harness.py` |
| test frames, sheets, animatics, the final video, the clay version | `tools/render.py` |
| reference clip to cuts, frames and sheets | `tools/reference.py` |
| shot facts measured from the scene, checked against `shotlist.json` | `tools/shots.py` ([docs/shot-facts.md](docs/shot-facts.md)) |
| rebuild from an empty file and compare | `tools/replay.py` |
| deliverables, checks and the release commit | `tools/release.py` |
| workflow rows | `tools/workflow-row.py` |
| film format and validator | [docs/film-format.md](docs/film-format.md), `tools/validate-film.py` |

Not here yet: task writing and task checks (no-op and oracle runs), dataset packaging, an art style library, sound
tools. Where a rule names something that is not here, do not stand in for it by hand or with another factory's
tool: ask.

## Agents

Both agents run the same skills, the same recording hooks and the same workflow; what differs:

| | Claude Code | Codex CLI |
|---|---|---|
| start | `claude` in `<root>` (reads `<root>/CLAUDE.md`) | `codex` in `<root>` (reads `<root>/AGENTS.md`) |
| skills | `~/.claude/skills/blender-film-*` (also offered by name) | `~/.agents/skills/blender-film-*` (`$<name>` or `/skills`; also offered by description) |
| recording hooks | `~/.claude/settings.json`: PostToolUse, PostToolUseFailure, Stop, UserPromptSubmit, SessionEnd | `~/.codex/hooks.json`: PostToolUse, Stop, UserPromptSubmit, SessionEnd (trusted in `config.toml`; `/hooks` shows them) |
| file edits in `actions.jsonl` | `Write` / `Edit` rows | `apply_patch` rows (the patch text) |
| permissions | as set in Claude Code (asks before commands by default) | the sandbox must let Blender use the GPU and write its caches, and allow `git push` / `gh`: `codex -s danger-full-access` where the default sandbox blocks them |
| looking at a picture | the Read tool on the `.png` | the image view tool on the `.png` |
| transcript (backfill) | `~/.claude/projects/…/<session>.jsonl` | `~/.codex/sessions/YYYY/MM/DD/rollout-…-<session>.jsonl` |

Under Codex, the shell tool is recorded as `Bash` whatever shell ran the command. Read a skill by opening its
`SKILL.md` when the task matches, even if the agent did not offer it. Both agents' hooks also store every prompt the
person typed and every reply the model wrote (`messages.jsonl`, read from the session's transcript). The person's
directions are still `user.direction` rows that the session writes itself (blender-film-commit-always skill).

Machines are macOS and Windows; every tool is Python 3 (standard library), Blender's own Python, or ffmpeg, and
there is no PowerShell. Commands in these docs write `python3` and forward slashes: on Windows the interpreter is
`python`, and a Windows path typed in Git Bash goes in single quotes, since bash drops unquoted backslashes.

## Rules

Rules for agents working in this repository. Background is in `docs/`; keep this section to rules.

### Data

- Never commit a film, a recording (`.recording/`), pictures, videos or `.blend` files here; only tools and docs.
  _(why: a film lives in its own repo with its own history; a copy here is stale the day it is made)_
- No names of people, companies, customers or machines here, no account names, no machine paths
  (`/Users/<name>/...`, `C:\Users\<name>\...`), no plans or prices. Write paths as `<BFF_ROOT>/...`.
- Step reasons are the builder's own notes at the moment of the step; never write them afterwards with a model.
  _(why: reasons written after the fact make a record a reconstruction)_
- Never edit a film's recording (`<BFF_ROOT>/.recording/<slug>/`) or its `steps/` folders by hand: the hooks and
  the step tool own them.

### Tools

- Standard library Python (3.9+) outside Blender; inside Blender only what ships with Blender 5.2 (bpy, mathutils,
  bmesh, numpy); paths through `pathlib`. No PowerShell, no shell scripts, no packages to install. _(why: the same
  file must run on macOS and Windows with nothing to install beyond bootstrap)_
- A hook never fails the agent or a commit: it ends in exit 0.
- A tool that reads a film never changes it; only `tools/step.py` changes the scene and only `tools/release.py`
  writes `out/`.
