#!/usr/bin/env python3
"""Add the commit recorder to a film repo's post-commit hook. Idempotent.

  python machine/install-git-hook.py <repo> [--force]

Appends one line to <repo>/.git/hooks/post-commit that runs <hooks folder>/record-film-commit.py: it writes every
new commit to <root>/.recording/<repo name>/commits.jsonl. The line is silent and ends in `|| true`: a recorder that
fails must never print into a commit's output or fail it.
Git LFS's own post-commit lines stay first: when the hook does not exist yet and the repo uses LFS, `git lfs update`
creates it before the line is appended. A line that names another hooks folder or another Python (moved since) is
replaced; when another tool's hook ends in `exit` or `exec` the line goes before that (after it, it never ran).
templates/new-film.py runs this for a new project, and machine/bootstrap.py for every repo under
<root>/films. Standard library only.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import bffroot  # noqa: E402

MARKER = '# recording: this commit to <root>/.recording/<repo>/commits.jsonl (machine/install-git-hook.py)'


def install(repo, force=False, python=None):
    """Returns a line saying what was done."""
    repo = Path(repo).resolve()
    if not (repo / '.git').exists():
        raise SystemExit(f'not a git repo (no .git): {repo}')
    git = lambda *a: subprocess.run(['git', '-C', str(repo), *a], capture_output=True, text=True)
    hook = Path(git('rev-parse', '--git-path', 'hooks/post-commit').stdout.strip())
    hook = hook if hook.is_absolute() else repo / hook
    hook.parent.mkdir(parents=True, exist_ok=True)
    attrs = repo / '.gitattributes'
    if not hook.exists() and attrs.is_file() and 'filter=lfs' in attrs.read_text(encoding='utf-8', errors='replace'):
        git('lfs', 'update')   # writes LFS's pre-push / post-checkout / post-commit / post-merge hooks

    script = bffroot.hooks_dir() / 'record-film-commit.py'
    warn = '' if script.is_file() else (f'\nWARNING: {script} is not there (machine/bootstrap.py installs it): this '
                                        "repo's commits are not recorded until it is")
    line = (f'"{Path(python or sys.executable).as_posix()}" "{script.as_posix()}" "$(pwd -W 2>/dev/null || pwd)" '
            '>/dev/null 2>&1 || true')
    text = hook.read_text(encoding='utf-8').replace('\r\n', '\n') if hook.exists() else '#!/bin/sh\n'
    new = '\n'.join(l for l in text.split('\n') if 'record-film-commit.py' not in l and l != MARKER)
    new += '' if new.endswith('\n') else '\n'
    block = f'{MARKER}\n{line}\n'
    end = re.search(r'(?m)^[ \t]*(exit|exec)\b[^\n]*\n\s*\Z', new)
    new = new[:end.start()] + block + end.group(0) if end else new + block
    if re.search(r'(?m)^[ \t]*(exit|exec)\b', new[:new.index(line)]):
        warn += (f'\nWARNING: {hook} can end before the recorder line (an exit or exec above it): move the line above '
                 "that, or this repo's commits are not recorded")
    if new == text and not force:
        return f'post-commit already records commits: {hook}{warn}'
    hook.write_text(new, encoding='utf-8', newline='\n')
    if os.name != 'nt':
        hook.chmod(hook.stat().st_mode | 0o755)
    return f'post-commit records commits via {script}: {hook}{warn}'


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--force']
    if len(args) != 1:
        sys.exit(__doc__)
    print(install(args[0], '--force' in sys.argv))
