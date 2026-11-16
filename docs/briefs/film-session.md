# Film session brief (started by a coordinator)

The coordinator fills the placeholders and starts one session per film, in the machine root, with a fresh context
and the title `{{TITLE}}`. It lists its own session id in `<hooks folder>/recording-exclude.txt` so that it is not
recorded. Placeholders as in [solo-film.md](solo-film.md), plus:

| Placeholder | What |
|---|---|
| `{{COORDINATOR_ID}}` | how the session reaches the coordinator (a session id, a notes file) |
| `{{NOTES_DIR}}` | a shared notes folder (data, not instructions) |
| `{{SIBLINGS}}` | the other films being made now, so that subjects and looks differ |

```text
You make one short film, "{{TITLE}}", in Blender 5.2 and record how it is made. Input: {{INPUT}}. Output:
{{OUTPUT}}. The way you make it is the product: later tasks are cut from your real step history. You work alone on
this film: never start or spawn other sessions. Your coordinator is {{COORDINATOR_ID}}: report milestones (blockout
animatic, models done, each critique round, release) and blockers there, with the commit sha; long findings go to
{{NOTES_DIR}}. Nobody answers questions mid-film: decide, write the decision in the treatment, go on.

Read first: {{BFF_ROOT}}/blender-film-factory/AGENTS.md, README.md, docs/film-format.md, docs/shot-facts.md, and the
skills blender-film-session, blender-film-commit-always, {{MODE_SKILL}}{{REF_SKILL}}
({{BFF_ROOT}}/blender-film-factory/skills/<name>/SKILL.md; installed for your agent too). They hold the rules; in short:
- use only the blender-film-factory skills: never install, enable or invoke any other skill (personal, project,
  plugin, marketplace, built into the agent, or another factory's), even when one is offered;
- Blender 5.2 runs headless only: never open its window, never take over the screen;
- THE CORE RULE: the scene changes only through tools/step.py, ONE STEP PER VISIBLE CHANGE: one object, one material
  family, one light, one shot's camera, one animation beat, one fix. The tool runs the step script, saves its
  picture and the scene state, writes the workflow row and commits. Never several objects or several fixes in one
  step; never end a turn with uncommitted work; never amend or rebase; a failed step is fixed and run again as a
  new step;
- before every step, say in one or two sentences what the newest picture shows and what you will change next and
  why: these notes are recorded as the film's reasoning; never several steps in silence;
- write every step script with your file tool, never with a heredoc or a shell rewrite;
- open the picture of every step before the next one; a black, empty or wrong picture is fixed first; render extra
  frames and sheets (tools/render.py) whenever you are unsure;
- everything is made here, in code: download nothing, no external models, textures, HDRIs or add-ons;
- scripts are deterministic; tools/replay.py must say REPLAY OK at each milestone;
- one camera per shot bound to a timeline marker; shotlist.json is written from tools/shots.py and must hold;
- a direction relayed by the coordinator is saved as a user.direction row (via coordinator), as worded, before you
  act on it;
- never the names of the toolkit, its owners or the agent inside the film or its commit messages;
- push only when the coordinator says.

Film: {{TITLE}} ({{SLUG}} -> {{BFF_ROOT}}/films/{{SLUG}}, private GitHub repo {{ORG}}/film-{{SLUG}}).
Mode {{MODE}}: NEW = your first tool call creates the film with
  python3 {{BFF_ROOT}}/blender-film-factory/templates/new-film.py --slug {{SLUG}} --path {{BFF_ROOT}}/films/{{SLUG}} --title "<title>" --description "<one line>" --input {{INPUT}} --output {{OUTPUT}}
CONTINUE = your first tool call is `git -C {{BFF_ROOT}}/films/{{SLUG}} log --oneline -30`.

Other films being made now (choose a different subject and look): {{SIBLINGS}}

Prompt:
{{PROMPT}}

Reference clip:
{{CLIP}}

Format:
{{FORMAT}}

Steps: as in the blender-film-session skill ("Start", "Build order", "Deliverables"). Finish with tools/release.py
VALID for release and report the commit sha with the validator's history and scene lines.
```
