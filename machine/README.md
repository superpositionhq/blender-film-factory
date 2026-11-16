# machine/

Everything a machine (macOS or Windows; Linux works the same way) needs outside this repo, kept in the repo and
installed by `bootstrap.py`. Step-by-step setup: [../docs/new-machine.md](../docs/new-machine.md). Everything here is
Python 3.9+ standard library; there is no PowerShell and no shell script.

## The machine root

All machine paths hang off one root, the "FilmWork" folder. Docs write it as `<BFF_ROOT>`.

```
<BFF_ROOT>/
  blender-film-factory/        this repo's clone
  films/<slug>/           one git repo per film
  .recording/<slug>/      actions.jsonl, messages.jsonl, commits.jsonl   (hook-owned: never edit)
  CLAUDE.md, AGENTS.md    pointers to this repo's instructions (sessions start in the root)
```

`lib/bffroot.py` (`sys.path.insert(0, <repo>/machine/lib)`, `bffroot.root()`) resolves the root in this order:

1. env `BFF_ROOT`;
2. `root` in the config file: env `BFF_CONFIG`, else `~/.blender-film-factory/config.json` (bootstrap writes it);
3. `~/FilmWork`.

The config:

```json
{ "root": "/Users/<name>/FilmWork", "repo": "/Users/<name>/FilmWork/blender-film-factory", "github_org": "<org>",
  "agents": ["claude", "codex"], "blender": "/Applications/Blender.app/Contents/MacOS/Blender",
  "record_extra_projects": [] }
```

| Key | Meaning |
|---|---|
| `root` | the machine root |
| `repo` | this checkout; default `<root>/blender-film-factory` |
| `blender` | the Blender 5.2 executable (bootstrap finds it, or `--blender <path>`); env `BLENDER` overrides it |
| `ffmpeg_dir` | a folder holding `ffmpeg` and `ffprobe` when they are not on PATH (optional) |
| `github_org` | the GitHub organisation or user that owns the private `film-<slug>` repos: `bootstrap.py --org` writes it, env `BFF_ORG` overrides it; `new-film.py` reads it |
| `agents` | the agents bootstrap sets up: `claude`, `codex` or both |
| `record_extra_projects` | extra top-level folders of the root the recording hooks treat as projects besides `films/<slug>` (default none) |

On Windows write paths in it with forward slashes or doubled backslashes.

### Next to another factory

This factory can live on a machine that also runs another one. It has its own root, config
(`~/.blender-film-factory/config.json`), hooks folder (`~/.blender-film-factory/hooks/`) and skills (`blender-film-*`); bootstrap
adds its hook entries next to the other factory's and never changes them. Each factory's hook maps only paths under
its own root and keeps its own session map, so a session is recorded by the factory whose film folder one of its
tool calls names.

## bootstrap.py

```bash
python3 machine/bootstrap.py --org <org>
```

Idempotent; run it again after every pull. It prints one line per item (`ok`, `added`, `changed`, `warn`):

1. the config (above);
2. `<root>/films` and `<root>/.recording`;
3. the recording hooks: the scripts copied into the hooks folder (`hooks/` next to the config), and their entries
   merged into each agent's settings: Claude Code `~/.claude/settings.json` (PostToolUse, PostToolUseFailure, Stop,
   UserPromptSubmit, SessionEnd), Codex `~/.codex/hooks.json` (PostToolUse, Stop, UserPromptSubmit, SessionEnd) plus
   the trust entries in `~/.codex/config.toml` (Codex skips an untrusted hook without a word). A backup
   `.bak-<time>` is made first, other settings and other tools' hooks stay as they are, and a handler of ours that
   is already there is replaced where it stands. It says what the hooks do and asks before wiring them; `--yes`
   skips the question, and a run that cannot ask (no terminal) leaves them out with a warning;
4. the skills: every `skills/blender-film-*` copied to `~/.claude/skills/` and `~/.agents/skills/` (copies, not links: a
   replaced one is moved to `_backup/<time>/` there; other skills are never touched);
5. `<root>/CLAUDE.md` (imports this repo's `CLAUDE.md`) and `<root>/AGENTS.md` (names this repo's `AGENTS.md`); an
   existing file gets the line appended, never rewritten;
6. Blender 5.2 (found in the usual places, or `--blender <path>`; its path is written to the config) and
   ffmpeg / ffprobe on PATH;
7. the post-commit hook of every film repo under `<root>/films` (`install-git-hook.py`).

Options: `--root <dir>`, `--org <org>`, `--agent claude|codex|both`, `--yes`, `--blender <path>`, and for a test run
against scratch folders `--config <file>`, `--claude-home <dir>`, `--codex-home <dir>`, `--agents-skills <dir>` (the
hooks folder follows the config file). The hook commands hold the absolute path of the Python that ran bootstrap, so
run bootstrap again after replacing that Python.

## check.py

```bash
python3 machine/check.py
```

Changes nothing. One line per item, `PASS`, `WARN` or `FAIL`: python, git, git-lfs, Blender 5.2, ffmpeg, ffprobe, gh;
the config and the root's folders; the hook scripts against the repo's; each agent's hook entries (and Codex's trust
entries); the skills against the repo's; the root instructions; each film's
post-commit hook. Exit code 1 with any `FAIL`. It takes the same folder options as bootstrap.

## The recording hooks (`hooks/`)

One script serves both agents: `record-film-action.py` (installed copy: `<hooks folder>/`). Both agents send the
same hook JSON on stdin (`session_id`, `transcript_path`, `cwd`, `hook_event_name`, `tool_name`, `tool_input`,
`tool_response`, `tool_use_id`).

- **Which session is recorded.** A session is tied to a film the first time one of its tool calls names a path
  under `<root>/films/<slug>`: in its `cwd`, a file path, or the text of a command (which is why the first tool
  call of a film session is `new-film.py --path <root>/films/<slug>` with the root written out). The map is
  `recording-sessions.json` in the hooks folder. After that all its calls are recorded there, whatever they name.
  Every other session on the machine is ignored. Session ids listed in `recording-exclude.txt` (one per line, e.g.
  the coordinator's) are never recorded, and nothing is while env `BFF_NO_RECORDING` is set.
- **Tool calls** (PostToolUse, PostToolUseFailure) go to `<root>/.recording/<slug>/actions.jsonl`, one row each
  (schema `agent-action/v0`: `time, project, session_id, agent, event, cwd, tool, tool_use_id, input, response`, and
  `error` for a failed call; string inputs are cut at 200,000 characters, the response at 8,000).
- **Backfill.** At the first mapping the session's earlier tool calls are imported once from its transcript, in
  order, before the mapping call's own row, with `status: "from_transcript"` (Claude Code: the session's `.jsonl` and
  its subagents' beside it; Codex: the rollout file's completed command, file-change and MCP items). Calls older than
  the transcript file (the copied context of a fork) are not imported, and a call is never written twice
  (`recording-backfill.json`).
- **Prompts and replies** (UserPromptSubmit, SessionEnd, and every Stop) go to `messages.jsonl` beside it (schema
  `agent-message/v0`: `time, project, session_id, agent, role, message_id, text`, and `model`, `images`, `mid_turn`,
  `subagent` where they apply). They are read from the session's transcript, each once
  (`recording-messages.json`: transcript file -> bytes read), so a session mapped late gets its earlier messages too.
  Only when the hook input names no transcript is the text taken from the input itself. Not recorded: the model's
  reasoning, text the agent tool puts into a turn itself, a fork's copied context.
- **Stop** also commits what the turn left behind: leftover changes in the session's film repo become a commit
  named `WIP`, unless conflicts are unresolved or HEAD is detached. The row in `actions.jsonl` (`event: "Stop"`)
  carries `auto_commit: {sha, files}`, or `auto_commit: null` for a clean tree. It is a safety net, not a way of
  working (blender-film-commit-always skill).
- A hook never fails the agent: every error ends in exit 0. Writers share one lock file (`recording.lock`) and go on
  without it after 30 s.

`record-film-commit.py` is the film repos' side: each repo's `.git/hooks/post-commit` runs it
(`install-git-hook.py <repo>` adds the line; `new-film.py` and bootstrap do that for you). It appends the commit
to `<root>/.recording/<repo name>/commits.jsonl` (schema `commit/v0`: `recorded_at, project, n, sha, parents, author,
author_time, commit_time, message, files`). The picture of a step is not taken here: `tools/step.py` renders it before the commit
and it is part of the commit (`steps/<n>-<name>/preview.png`).
