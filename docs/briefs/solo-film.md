# Solo film brief (plain Claude Code or Codex)

For one person making one film with one coding-agent session in a terminal, Claude Code (`claude`) or OpenAI Codex
CLI (`codex`): no coordinator, no other sessions. The rules are the same as for a coordinated film session; what
the coordinator would do (review commits, decide pushes, relay directions) is done by you, the person at the
keyboard. With a coordinator and several films at once, start each session from [film-session.md](film-session.md).

Start: open a terminal in the machine root (`cd <root>`, e.g. `~/FilmWork`; not another factory's root, whose
`CLAUDE.md` and `AGENTS.md` load its own rules) and run `claude` (its `<root>/CLAUDE.md` loads the rules) or
`codex -s danger-full-access` (its `<root>/AGENTS.md` names them; Blender needs the GPU and its caches), then paste
the `text` block below with the placeholders filled. Stay in this one session for the whole film where you can
(`claude --continue`, `codex resume --last`): the recording follows the session, and a new session is filed under
the film only from its first tool call that names the film folder.

| Placeholder | What |
|---|---|
| `{{TITLE}}`, `{{SLUG}}` | the title and a lower-case slug (`paper-boat`) |
| `{{INPUT}}` | `text` (a written prompt) or `video` (a reference clip) |
| `{{OUTPUT}}` | `final` (a finished picture) or `previs` (mannequins and blocks) |
| `{{MODE_SKILL}}` | `blender-film-final` or `blender-film-previs`, as `{{OUTPUT}}` |
| `{{REF_SKILL}}` | ` and blender-film-reference` for a video input, else nothing |
| `{{PROMPT}}` | text input: the prompt, word for word. Video input: what is asked for (`recreate this clip shot for shot`), plus anything to leave out |
| `{{CLIP}}` | video input: the absolute path of the clip, where it is from and its licence. Text input: `none` |
| `{{FORMAT}}` | `default` (final: 1920x1080, 24 fps, 20-45 s, 5+ shots; previs: 1280x720, 24 fps, 6-60 s), or the size, length and shot count to pass to new-film.py; for a clip: `follow the clip` |
| `{{BFF_ROOT}}` | the machine root, written out (e.g. `/Users/<name>/FilmWork`, `C:\Users\<name>\FilmWork`) |
| `{{ORG}}` | the GitHub organisation (or user) owning the repos: `github_org` in the machine config |
| `{{MODE}}` | `NEW` (no repo yet) or `CONTINUE` (repo already in `{{BFF_ROOT}}/films/{{SLUG}}`) |

```text
You are the only session on this machine and the only author of one short film: make "{{TITLE}}" in Blender 5.2 and
record how it is made. Input: {{INPUT}}. Output: {{OUTPUT}}. The way you make it is the product: later tasks are cut
from your real step history, so a film built in a few big steps is worth nothing. There is no coordinator and there
are no other sessions: never start, spawn or message other sessions. Nobody answers questions mid-film: decide,
write the decision in the treatment, and finish. Whatever the skills say to send to "the coordinator" (milestones,
push requests, blockers), tell me here.

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
- my messages that change the film are directions: rewrite each as one or two neutral sentences and save it as a
  user.direction row before acting on it;
- never the names of the toolkit, its owners or the agent inside the film or its commit messages;
- push only when I say.

Film: {{TITLE}} ({{SLUG}} -> {{BFF_ROOT}}/films/{{SLUG}}, private GitHub repo {{ORG}}/film-{{SLUG}}).
Mode {{MODE}}: NEW = your first tool call creates the film with
  python3 {{BFF_ROOT}}/blender-film-factory/templates/new-film.py --slug {{SLUG}} --path {{BFF_ROOT}}/films/{{SLUG}} --title "<title>" --description "<one line>" --input {{INPUT}} --output {{OUTPUT}}
(the absolute path written out: the recording hooks match the command text; `python` on Windows, and in Git Bash
there put each Windows path in single quotes; add the format options when the format is not the default).
CONTINUE = your first tool call is `git -C {{BFF_ROOT}}/films/{{SLUG}} log --oneline -30`; read Docs/Treatment.md's
status, the last workflow.jsonl rows and the newest step pictures; if scene.blend is missing, tools/replay.py --keep
rebuilds it (copy .local/replay/scene.blend to scene.blend); carry on from the step it stopped at.

Prompt:
{{PROMPT}}

Reference clip:
{{CLIP}}

Format:
{{FORMAT}}

Steps:
1) create the film (new-film.py); 2) Brief.md with the input word for word, committed; for a clip:
tools/reference.py, read every sheet, reference/Breakdown.md, committed; 3) Docs/Treatment.md with the object list
and the shot list, committed; 4) the staged build with tools/step.py, one step per visible change, looking at each
picture: start, blockout, one camera per shot, blocked animation; the blockout animatic (out/animatic_blockout.mp4)
and its fixes; tell me when it is done; then the stages of your output mode; 5) the critique rounds, each issue
fixed in its own step; 6) shotlist.json from tools/shots.py (SHOT FACTS HOLD), Docs/Report.md, tools/replay.py
(REPLAY OK), then tools/release.py until the film is VALID for release. Report each milestone here with the commit
sha and, at the end, the validator's history and scene lines.
```
