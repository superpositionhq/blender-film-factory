# Film brief

For one person and one coding-agent session in a terminal, Claude Code (`claude`) or OpenAI Codex CLI (`codex`),
making one film. The rules are in the skills; this brief only names the film and starts the session.

Start: open a terminal in the machine root (`cd <root>`, e.g. `~/FilmWork`; not another factory's root) and run
`claude` (its `<root>/CLAUDE.md` loads the rules) or `codex -s danger-full-access` (its `<root>/AGENTS.md` names
them; Blender needs the GPU and its caches), then paste the `text` block below with the placeholders filled. Stay
in this one session for the whole film where you can (`claude --continue`, `codex resume --last`): the recording
follows the session.

| Placeholder | What |
|---|---|
| `{{TITLE}}`, `{{SLUG}}` | the title and a lower-case slug (`paper-boat`) |
| `{{INPUT}}` | `script`, or `storyboard` (a script with storyboard pictures) |
| `{{OUTPUT}}` | `greybox` (a grey-box video) or `final` (a fully rendered film, with its grey-box video) |
| `{{SCRIPT}}` | the script, every line |
| `{{STORYBOARD}}` | storyboard input: the absolute paths of the pictures (or their folder), in order. Else `none` |
| `{{FORMAT}}` | `default` (greybox: 1280x720, 24 fps, 6-60 s; final: 1920x1080, 24 fps, 20-45 s, 5+ shots), or the size, length and shot count |
| `{{BFF_ROOT}}` | the machine root, written out (e.g. `/Users/<name>/FilmWork`, `C:\Users\<name>\FilmWork`) |
| `{{MODE}}` | `NEW` (no repo yet) or `CONTINUE` (repo already in `{{BFF_ROOT}}/films/{{SLUG}}`) |

```text
Make "{{TITLE}}" in Blender 5.2 from the script below. Input: {{INPUT}}. Output: {{OUTPUT}}.
Work in this session without starting, spawning or messaging other sessions.
Build in small steps. Before each step, name the visible change you will make. Run the step,
open its rendered picture, then continue. Commit each object, shot, material family, animation beat
and correction separately. Save scripts, images, plans and unfinished changes throughout the build.
Resolve ordinary creative choices independently and keep the treatment current.
Report any required permission or technical blocker clearly.

Read first, and follow: {{BFF_ROOT}}/blender-film-factory/AGENTS.md and the skills it names
({{BFF_ROOT}}/blender-film-factory/skills/<name>/SKILL.md): blender-film-session and blender-film-commit-always,
the skill of your output (blender-film-greybox or blender-film-final), and blender-film-storyboard if there are
storyboard pictures. Use no other skill.

Film: {{TITLE}} ({{SLUG}} -> {{BFF_ROOT}}/films/{{SLUG}}).
Mode {{MODE}}: NEW = your first tool call creates the film with
  python3 {{BFF_ROOT}}/blender-film-factory/templates/new-film.py --slug {{SLUG}} --path {{BFF_ROOT}}/films/{{SLUG}} --title "<title>" --description "<one line>" --input {{INPUT}} --output {{OUTPUT}}
(the absolute path written out; `python` on Windows; add the format options when the format is not the default).
CONTINUE = your first tool call is `git -C {{BFF_ROOT}}/films/{{SLUG}} log --oneline -30`; read the treatment's
status, the last workflow.jsonl rows and the newest step pictures; if scene.blend is missing, tools/replay.py --keep
rebuilds it (copy .local/replay/scene.blend to scene.blend); carry on from the step it stopped at.

Format:
{{FORMAT}}

Storyboard pictures:
{{STORYBOARD}}

Script:
{{SCRIPT}}

Finish with tools/release.py until the film is VALID for release, then tell me the commit sha and the validator's
last lines.
```
