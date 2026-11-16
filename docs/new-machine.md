# Setting up a new machine

A Mac or a Windows PC goes from nothing to making films in a few minutes once Blender is installed. `machine/bootstrap.py` is idempotent: after any manual step, run it again.

## Before you start

| You need | Why |
|---|---|
| git and Git LFS | film repos; LFS for pictures, videos and `.blend` |
| Python 3.9+ | every tool and hook here (standard library only) |
| Blender 5.2 LTS | every film is built and rendered with it, headless (macOS: in `/Applications`; Windows: the installer's default folder; elsewhere: `bootstrap.py --blender <path>`) |
| ffmpeg and ffprobe on PATH | videos are encoded with it; reference clips are cut into frames with it |
| The GitHub CLI (`gh`), signed in (`gh auth login`) to an account that may create private repos in `<org>` | `new-film.py` creates `<org>/film-<slug>` |
| A coding agent: Claude Code, or OpenAI Codex CLI, signed in | the agent that makes the film |

Blender runs in the background and never opens a window. EEVEE needs a GPU (any Apple Silicon Mac; a Windows PC with
a discrete or recent integrated GPU). Without one, films render with Cycles on the CPU, far slower: use it for previs
only.

## Set up

```bash
git clone <this repo> ~/FilmWork/blender-film-factory
```
```bash
python3 ~/FilmWork/blender-film-factory/machine/bootstrap.py --org <org>
```
```bash
python3 ~/FilmWork/blender-film-factory/machine/check.py
```

On Windows the interpreter is `python` and the root is `%USERPROFILE%\FilmWork`. Another root: clone there and pass
`--root <dir>` (or set `BFF_ROOT`). Bootstrap says what the recording hooks do and asks before installing them;
`--agent claude|codex|both` chooses the agents (default both). Repeat `check.py` until nothing says FAIL; a WARN
names a limit you can live with.

## First session

Open a terminal in the root (`cd ~/FilmWork`), start `claude` or `codex`, and paste the brief from
[briefs/solo-film.md](briefs/solo-film.md) with its placeholders filled.

## After every pull

`git -C <BFF_ROOT>/blender-film-factory pull`, then `bootstrap.py` again: it updates the installed skills and hooks and
every film's post-commit hook. The hook commands hold the path of the Python that ran bootstrap: after a Python
update that moved it, run bootstrap again (`check.py` says so).

Another factory on the same machine: both can live there
([../machine/README.md](../machine/README.md), "Next to another factory").
