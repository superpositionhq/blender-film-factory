#!/usr/bin/env python3
"""Report what of blender-film-factory is installed on this machine. Changes nothing.

  python machine/check.py [--config <file>] [--root <dir>] [--claude-home <dir>] [--codex-home <dir>]
      [--agents-skills <dir>]

One line per item: PASS, WARN (works, with a limit) or FAIL (run machine/bootstrap.py, or install what the line
names). Exit code 0 without a FAIL, else 1. Give it the same folder options bootstrap.py was given.
Python 3.9+ standard library only.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import agenthooks  # noqa: E402
import bffroot  # noqa: E402

COUNT = {'PASS': 0, 'WARN': 0, 'FAIL': 0}


def say(state, what, detail=''):
    COUNT[state] += 1
    print(f'  {state}  {what}' + (f': {detail}' if detail else ''))


def version(cmd):
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    r = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return (r.stdout or r.stderr).strip().splitlines()[0] if r.returncode == 0 and (r.stdout or r.stderr).strip() else ''


def same(a, b):
    return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('--root')
    p.add_argument('--config')
    p.add_argument('--claude-home', default=str(Path.home() / '.claude'))
    p.add_argument('--codex-home', default=os.environ.get('CODEX_HOME') or str(Path.home() / '.codex'))
    p.add_argument('--agents-skills', default=str(Path.home() / '.agents' / 'skills'))
    a = p.parse_args()
    if a.config:
        os.environ['BFF_CONFIG'] = str(Path(a.config).absolute())
    if a.root:
        os.environ['BFF_ROOT'] = str(Path(a.root).absolute())
    cfg_path, cfg, root, hooks_dir = bffroot.config_path(), bffroot.config(), bffroot.root(), bffroot.hooks_dir()
    agents = cfg.get('agents') or ['claude', 'codex']
    print(f'blender-film-factory check: root {root}, config {cfg_path}')

    # toolchain
    say('PASS' if sys.version_info >= (3, 9) else 'FAIL', 'python', sys.version.split()[0] + ' (3.9+)')
    v = version(['git', '--version'])
    say('PASS' if v else 'FAIL', 'git', v or 'not on PATH')
    v = version(['git', 'lfs', 'version'])
    say('PASS' if v else 'FAIL', 'git-lfs', v or 'not installed: films keep pictures, videos and .blend files in it')
    exe = bffroot.blender()
    v = (version([exe, '--version']) if exe else '') or ''
    say('PASS' if v.startswith('Blender 5.2') else 'FAIL', 'blender', (f'{v} at {exe}' if v else 'not found') + ' (5.2 LTS)')
    for tool in ('ffmpeg', 'ffprobe'):
        t = bffroot.ffmpeg(tool)
        say('PASS' if t else 'FAIL', tool, t or 'not on PATH')
    org = bffroot.org()
    if org:                                    # GitHub is used only when an organisation is set
        v = version(['gh', '--version'])
        say('PASS' if v else 'WARN', 'gh', v or f'not installed: new-film.py cannot make {org}/film-<slug> without it')

    # config and root
    say('PASS' if cfg else 'FAIL', 'config', str(cfg_path) if cfg else f'{cfg_path} is missing: run machine/bootstrap.py')
    say('PASS', 'github_org', org or 'not set: films stay on this machine (no GitHub account needed)')
    for d in (root / 'films', root / '.recording'):
        say('PASS' if d.is_dir() else 'FAIL', str(d))
    say('PASS' if (bffroot.repo() / 'tools' / 'step.py').is_file() else 'FAIL', 'repo', str(bffroot.repo()))

    # hooks
    for f, src in (('record-film-action.py', REPO / 'machine' / 'hooks'), ('record-film-commit.py', REPO / 'machine' / 'hooks'),
                   ('bffroot.py', REPO / 'machine' / 'lib')):
        ok = same(src / f, hooks_dir / f)
        say('PASS' if ok else 'FAIL', f'hooks/{f}', '' if ok else 'missing or older than the repo: run machine/bootstrap.py')
    python = None
    if 'claude' in agents:
        personal = agenthooks.read_json(Path(a.claude_home) / 'settings.json')
        if any(agenthooks.MINE.search(str(h.get('command', ''))) for gs in (personal.get('hooks') or {}).values() if isinstance(gs, list)
               for g in gs if isinstance(g, dict) for h in g.get('hooks') or [] if isinstance(h, dict)):
            say('FAIL', 'Claude Code personal settings', 'still hold the recording hooks: they belong in the film root only; run machine/bootstrap.py')
        path = root / '.claude' / 'settings.json'
        settings = agenthooks.read_json(path)
        on = all(settings.get(k) is v for k, v in agenthooks.CLAUDE_SUMMARY.items())
        say('PASS' if on else 'FAIL', 'Claude Code reasoning summaries', '' if on else f'showThinkingSummaries / alwaysThinkingEnabled are not on in {path}: run machine/bootstrap.py')
        cmds = [h.get('command', '') for gs in (settings.get('hooks') or {}).values() for g in gs for h in g.get('hooks') or []
                if agenthooks.MINE.search(str(h.get('command', '')))]
        python = re.match(r'"([^"]+)"', cmds[0])[1] if cmds and re.match(r'"([^"]+)"', cmds[0]) else sys.executable
        missing = agenthooks.wired(settings, agenthooks.fragment('settings-hooks.json', python, hooks_dir))
        say('FAIL' if missing else 'PASS', 'Claude Code hooks', f'{path}: ' + (f'missing or changed: {", ".join(missing)}'
            if missing else 'PostToolUse, PostToolUseFailure, Stop, UserPromptSubmit, SessionEnd'))
    if 'codex' in agents:
        path = Path(a.codex_home) / 'hooks.json'
        hooks = agenthooks.read_json(path)
        cmds = [h.get('command', '') for gs in (hooks.get('hooks') or {}).values() for g in gs for h in g.get('hooks') or []
                if agenthooks.MINE.search(str(h.get('command', '')))]
        py = re.match(r'"([^"]+)"', cmds[0])[1] if cmds and re.match(r'"([^"]+)"', cmds[0]) else sys.executable
        python = python or py
        missing = agenthooks.wired(hooks, agenthooks.fragment('codex-hooks.json', py, hooks_dir))
        say('FAIL' if missing else 'PASS', 'Codex hooks', f'{path}: ' + (f'missing or changed: {", ".join(missing)}'
            if missing else 'PostToolUse, Stop, UserPromptSubmit, SessionEnd'))
        state = agenthooks.trust_state(path.with_name('config.toml'))
        trust = agenthooks.codex_trust(str(path), hooks)
        bad = [k for k, h in trust if state.get(k) != h]
        say('FAIL' if bad or not trust else 'PASS', 'Codex hook trust', f'{len(trust) - len(bad)} of {len(trust)} handler(s) '
            'trusted in config.toml' + (' (an untrusted hook is skipped without a word: run machine/bootstrap.py)' if bad else ''))
    if python and not Path(python).is_file():
        say('FAIL', 'hook interpreter', f'{python} is gone (a Python update?): run machine/bootstrap.py')

    # skills
    targets = ([('Claude Code', root / '.claude' / 'skills')] if 'claude' in agents else []) + \
              ([('Codex', root / '.agents' / 'skills')] if 'codex' in agents else [])
    for label, personal in (('Claude Code', Path(a.claude_home) / 'skills'), ('Codex', Path(a.agents_skills))):
        left = sorted(d.name for d in personal.glob('blender-film-*')) if personal.is_dir() else []
        if left:
            say('FAIL', f'{label} personal skills', f'{", ".join(left)} in {personal}: the film skills are project skills of the root; run machine/bootstrap.py')
    for label, folder in targets:
        for s in sorted(d for d in (REPO / 'skills').iterdir() if (d / 'SKILL.md').is_file()):
            ok = same(s / 'SKILL.md', folder / s.name / 'SKILL.md')
            say('PASS' if ok else 'FAIL', f'{label} skill {s.name}', '' if ok else f'{folder / s.name} missing or older than '
                'the repo: run machine/bootstrap.py')

    # root instructions
    for agent, name in (('claude', 'CLAUDE.md'), ('codex', 'AGENTS.md')):
        if agent in agents:
            f = root / name
            ok = f.is_file() and 'blender-film-factory' in f.read_text(encoding='utf-8')
            say('PASS' if ok else 'FAIL', str(f), '' if ok else 'does not name the blender-film-factory instructions')

    # project repos
    projects = sorted(g for g in (root / 'films').iterdir() if (g / '.git').exists()) if (root / 'films').is_dir() else []
    for g in projects:
        hook = g / '.git' / 'hooks' / 'post-commit'
        ok = hook.is_file() and (hooks_dir / 'record-film-commit.py').as_posix() in hook.read_text(encoding='utf-8')
        say('PASS' if ok else 'FAIL', f'films/{g.name} post-commit', '' if ok else 'does not run this hooks '
            "folder's record-film-commit.py: run machine/bootstrap.py")

    print(f'\n{COUNT["PASS"]} PASS, {COUNT["WARN"]} WARN, {COUNT["FAIL"]} FAIL')
    sys.exit(1 if COUNT['FAIL'] else 0)


if __name__ == '__main__':
    main()
