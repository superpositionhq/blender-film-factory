#!/usr/bin/env python3
"""Set this machine up for blender-film-factory (macOS, Windows, Linux). Idempotent: run it again after every pull.

  python machine/bootstrap.py [--root <dir>] [--org <github org>] [--agent claude|codex|both] [--yes]
      [--blender <path>] [--config <file>] [--claude-home <dir>] [--codex-home <dir>] [--agents-skills <dir>]

What it does, saying for each item ok / added / changed / warn:
  1. the machine config (--config, else env BFF_CONFIG, else ~/.blender-film-factory/config.json): root, repo (this
     checkout), github_org, agents;
  2. the root's folders: <root>/films, <root>/.recording;
  3. the recording hooks into the hooks folder (next to the config), and their entries merged into each agent's
     settings (Claude Code: <claude home>/settings.json; Codex: <codex home>/hooks.json plus the trust entries in
     config.toml; a backup .bak-<time> first; other settings and hooks are kept). It asks first; --yes installs
     them without asking, and a run that cannot ask leaves them out;
  4. the repo's skills (skills/, all blender-film-*) into the film root as PROJECT skills (<root>/.claude/skills
     for Claude Code, <root>/.agents/skills for Codex), so only sessions started in the root see them; copies an
     earlier bootstrap left in an agent's personal skills folder are moved out to its _backup folder;
  5. the root instructions: <root>/CLAUDE.md importing this repo's CLAUDE.md, <root>/AGENTS.md naming this repo's
     AGENTS.md (sessions start in the root);
  6. Blender 5.2 (found in the usual places or --blender; its path goes into the config) and ffmpeg / ffprobe;
  7. the post-commit hook of every film repo under <root>/films.
Any file it replaces is copied to a backup first (<folder>/_backup/<time>/). It never pushes and never signs in for
you. Test run against scratch folders:
  python machine/bootstrap.py --root /tmp/bff/root --config /tmp/bff/home/.blender-film-factory/config.json \
      --claude-home /tmp/bff/home/.claude --codex-home /tmp/bff/home/.codex --agents-skills /tmp/bff/home/.agents/skills --yes
Python 3.9+ standard library only.
"""
import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import agenthooks  # noqa: E402
import bffroot  # noqa: E402

STAMP = time.strftime('%Y%m%d-%H%M%S')
WARNED = []


def note(state, what, detail=''):
    if state == 'warn':
        WARNED.append(what)
    print(f'  [{state:^7}] {what}' + (f': {detail}' if detail else ''))


def sync_file(src, dst, backup, label):
    dst = Path(dst)
    if dst.is_file() and filecmp.cmp(src, dst, shallow=False):
        return note('ok', label)
    state = 'changed' if dst.is_file() else 'added'
    if dst.is_file():
        Path(backup).mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, Path(backup) / dst.name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    note(state, label, str(dst))


def same_dir(a, b):
    c = filecmp.dircmp(a, b, ignore=['__pycache__', '.DS_Store'])
    if c.left_only or c.right_only or c.funny_files:
        return False
    if filecmp.cmpfiles(a, b, c.common_files, shallow=False)[1:] != ([], []):
        return False
    return all(same_dir(Path(a) / d, Path(b) / d) for d in c.common_dirs)


def sync_dir(src, dst, backup, label):
    dst = Path(dst)
    if dst.is_dir() and same_dir(src, dst):
        return note('ok', label)
    state = 'changed' if dst.exists() else 'added'
    if dst.exists():
        Path(backup).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(backup))
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
    note(state, label, str(dst))


def root_file(path, line, text):
    """Sessions start in the root: its instructions file must name this repo's. An existing file gets the line
    appended (backup first), never rewritten."""
    if not path.is_file():
        path.write_text(text, encoding='utf-8', newline='\n')
        note('added', str(path), line)
    elif line in path.read_text(encoding='utf-8'):
        note('ok', str(path))
    else:
        shutil.copy2(path, f'{path}.bak-{STAMP}')
        with open(path, 'a', encoding='utf-8', newline='\n') as f:
            f.write(f'\n{line}\n')
        note('changed', str(path), f'appended {line} (backup .bak-{STAMP})')


def write_json(path, data):
    """Returns a note on the backup made, '' when the file is new."""
    had = path.is_file()
    if had:
        shutil.copy2(path, f'{path}.bak-{STAMP}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return f' (backup .bak-{STAMP})' if had else ''


def run(cmd, cwd):
    """A command by its name on PATH."""
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    return subprocess.run([exe, *cmd[1:]], cwd=str(cwd), capture_output=True, text=True, encoding='utf-8',
                          errors='replace')


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('--root')
    p.add_argument('--org')
    p.add_argument('--agent', choices=['claude', 'codex', 'both'])
    p.add_argument('--config')
    p.add_argument('--claude-home', default=str(Path.home() / '.claude'))
    p.add_argument('--codex-home', default=os.environ.get('CODEX_HOME') or str(Path.home() / '.codex'))
    p.add_argument('--agents-skills', default=str(Path.home() / '.agents' / 'skills'))
    p.add_argument('--yes', action='store_true', help='install the recording hooks without asking')
    p.add_argument('--blender', help='path to the Blender 5.2 executable (default: found in the usual places)')
    a = p.parse_args()
    if a.config:
        os.environ['BFF_CONFIG'] = str(Path(a.config).absolute())
    if a.root:
        os.environ['BFF_ROOT'] = str(Path(a.root).absolute())

    # --- 1. config ----------------------------------------------------------------------------------------------------
    cfg_path, have = bffroot.config_path(), bffroot.config()
    root = bffroot.root()
    agents = ['claude', 'codex'] if a.agent == 'both' else [a.agent] if a.agent else have.get('agents') or ['claude', 'codex']
    want = dict(have, root=str(root), repo=str(REPO), github_org=a.org or have.get('github_org') or '', agents=agents,
                record_extra_projects=have.get('record_extra_projects') or [])
    hooks_dir = bffroot.hooks_dir()
    print(f'blender-film-factory bootstrap: root {root}, repo {REPO}, agents {" + ".join(agents)}, hooks folder {hooks_dir}')
    if want == have:
        note('ok', f'config {cfg_path}')
    else:
        write_json(cfg_path, want)
        note('changed' if have else 'added', f'config {cfg_path}',
             f'root={root} github_org={want["github_org"] or "(none: --org <org>)"} agents={",".join(agents)}')
    if not want['github_org']:
        note('warn', 'github_org', 'not set: new-film.py makes no GitHub repo until bootstrap.py --org <org>')

    # --- 2. folders ---------------------------------------------------------------------------------------------------
    for d in (root / 'films', root / '.recording'):
        state = 'ok' if d.is_dir() else 'added'
        d.mkdir(parents=True, exist_ok=True)
        note(state, str(d))
    if REPO != root / 'blender-film-factory':
        note('ok', 'repo outside the root', f'{REPO} (the config names it; docs write <root>/blender-film-factory)')

    # --- 3. recording hooks ---------------------------------------------------------------------------------------------
    backup = hooks_dir / '_backup' / STAMP
    for f in ('record-film-action.py', 'record-film-commit.py'):
        sync_file(REPO / 'machine' / 'hooks' / f, hooks_dir / f, backup, f'hooks/{f}')
    sync_file(REPO / 'machine' / 'lib' / 'bffroot.py', hooks_dir / 'bffroot.py', backup, 'hooks/bffroot.py')
    for name, first in (('recording-exclude.txt', None), ('recording-sessions.json', '{}')):
        f = hooks_dir / name
        if f.is_file():
            note('ok', f'hooks/{name}', 'kept as is')
        elif first is None:
            shutil.copyfile(REPO / 'machine' / 'hooks' / name, f)
            note('added', f'hooks/{name}', 'add the coordinator session id to it')
        else:
            f.write_text(first, encoding='utf-8')
            note('added', f'hooks/{name}')

    claude_home, codex_home = Path(a.claude_home).absolute(), Path(a.codex_home).absolute()
    plans = []   # (agent label, file, parsed settings, changed, trust entries)
    if 'claude' in agents:
        path = claude_home / 'settings.json'
        settings = agenthooks.read_json(path)
        changed = agenthooks.merge(settings, agenthooks.fragment('settings-hooks.json', sys.executable, hooks_dir), path)
        plans.append(('Claude Code', path, settings, changed, None))
    if 'codex' in agents:
        path, toml = codex_home / 'hooks.json', codex_home / 'config.toml'
        hooks = agenthooks.read_json(path)
        changed = agenthooks.merge(hooks, agenthooks.fragment('codex-hooks.json', sys.executable, hooks_dir), path)
        # The key holds the hooks.json path as Codex prints it. With CODEX_HOME set, Codex canonicalizes the folder,
        # which on Windows can add the \\?\ prefix: both spellings are trusted then (an unused entry does nothing).
        trust = agenthooks.codex_trust(str(path), hooks)
        if os.name == 'nt' and os.environ.get('CODEX_HOME'):
            trust += agenthooks.codex_trust('\\\\?\\' + str(path), hooks)
        state = agenthooks.trust_state(toml)
        plans.append(('Codex', path, hooks, changed, trust if any(state.get(k) != h for k, h in trust) else []))
    todo = [x for x in plans if x[3] or x[4]]
    ok = bool(todo) and a.yes
    if todo and not a.yes:
        # Say plainly what the hooks do before wiring them into every session of the chosen agents on this account.
        print(f'\n  About to add the blender-film-factory recording hooks (a backup .bak-{STAMP} of each file is kept):')
        for label, path, *_ in todo:
            print(f'    - {label}: {path}' + (' (marked trusted in config.toml beside it)' if label == 'Codex' else ''))
        print(f'    They run {hooks_dir / "record-film-action.py"} after every tool call, at every prompt and at the\n'
              '    end of every turn of EVERY session of these agents on this account. A session is recorded only once\n'
              f'    one of its tool calls names a folder under {root / 'films'}: then its tool calls, prompts and\n'
              f'    replies go to {root / ".recording"}/<slug>/, and at the end of each turn leftover changes in that\n'
              '    project repo are committed as "WIP". Sessions listed in hooks/recording-exclude.txt never are.\n'
              "    Other hooks in those files (e.g. another factory's) stay as they are.")
        ok = sys.stdin.isatty() and input('  Install the recording hooks? [y/N] ').strip().lower() in ('y', 'yes')
    for label, path, data, changed, trust in plans:
        if (changed or trust) and not ok:
            note('warn', f'{label} hooks', 'not installed (declined or non-interactive; --yes installs them without asking)')
            continue
        if changed:
            note('changed', f'{label} hooks', f'{path} -> {hooks_dir / "record-film-action.py"}' + write_json(path, data))
        else:
            note('ok', f'{label} hooks')
        if trust:
            toml = path.with_name('config.toml')
            if toml.is_file():
                shutil.copy2(toml, f'{toml}.bak-{STAMP}')
            agenthooks.set_trust_state(toml, trust)
            note('changed', 'Codex hook trust', f'config.toml [hooks.state] for {len(trust)} handler(s); check with /hooks in Codex')
        elif label == 'Codex':
            note('ok', 'Codex hook trust')

    # --- 4. skills: one source, copied to where each agent looks for personal skills (copies, not links: links need
    # Developer Mode on Windows) ---------------------------------------------------------------------------------------
    # Project skills, in the film root: sessions started there see them and no other session on the account does.
    targets = ([('Claude Code', root / '.claude' / 'skills')] if 'claude' in agents else []) + \
              ([('Codex', root / '.agents' / 'skills')] if 'codex' in agents else [])
    for label, personal in (('Claude Code', claude_home / 'skills'), ('Codex', Path(a.agents_skills).absolute())):
        for old in sorted(personal.glob('blender-film-*')) if personal.is_dir() else []:
            dst = personal / '_backup' / STAMP / old.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(dst))
            note('changed', f'{label} personal skill {old.name}', f'moved out to {dst} (skills are project skills of the root now)')
    skills = sorted(d for d in (REPO / 'skills').iterdir() if (d / 'SKILL.md').is_file())
    for label, folder in targets:
        for s in skills:
            sync_dir(s, folder / s.name, folder / '_backup' / STAMP / s.name, f'{label} skills/{s.name}')

    # --- 5. root instructions -------------------------------------------------------------------------------------------
    in_root = REPO == root / 'blender-film-factory'
    names = ', '.join(s.name for s in skills)
    if 'claude' in agents:
        imp = '@' + ('blender-film-factory/CLAUDE.md' if in_root else (REPO / 'CLAUDE.md').as_posix())
        root_file(root / 'CLAUDE.md', imp, '# FilmWork root\n\nEvery session in this folder follows the '
                  f'blender-film-factory rules and skills:\n\n{imp}\n')
    if 'codex' in agents:
        line = f'Before anything else, read {REPO / "AGENTS.md"} and follow it (rules, skills, priorities).'
        root_file(root / 'AGENTS.md', line, '# FilmWork root\n\nEvery session in this folder follows the '
                  f'blender-film-factory rules and skills.\n{line}\nThe skills it names ({names}) are installed in '
                  f'{root / ".agents" / "skills"}.\n')

    # --- 6. Blender and ffmpeg ------------------------------------------------------------------------------------------
    exe = a.blender or bffroot.blender()
    if exe and Path(exe).is_file():
        r = subprocess.run([exe, '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        ver = (r.stdout.strip().splitlines() or ['?'])[0]
        cfg_now = bffroot.config()
        if cfg_now.get('blender') != str(exe):
            write_json(cfg_path, dict(cfg_now, blender=str(exe)))
        note('ok' if ver.startswith('Blender 5.2') else 'warn', 'blender', f'{ver} at {exe}'
             + ('' if ver.startswith('Blender 5.2') else ' (films are made with Blender 5.2 LTS: install it and pass --blender <path>)'))
    else:
        note('warn', 'blender', 'not found: install Blender 5.2 LTS, then run bootstrap again (or --blender <path to the executable>)')
    for tool in ('ffmpeg', 'ffprobe'):
        t = bffroot.ffmpeg(tool)
        note('ok' if t else 'warn', tool, t or 'not on PATH: install ffmpeg (videos are encoded and reference clips read with it)')

    # --- 7. project repos: the post-commit hook --------------------------------------------------------------------------
    for g in sorted((root / 'films').iterdir()):
        if (g / '.git').exists():
            r = subprocess.run([sys.executable, str(REPO / 'machine' / 'install-git-hook.py'), str(g)],
                               capture_output=True, text=True)
            note('warn' if r.returncode or 'WARNING' in r.stdout else 'ok', f'films/{g.name} post-commit',
                 (r.stdout + r.stderr).strip().replace('\n', ' '))

    print(f'\ndone{f", {len(WARNED)} warning(s): " + "; ".join(WARNED) if WARNED else ""}. Check with: '
          f'python {Path("machine") / "check.py"}')


if __name__ == '__main__':
    main()
