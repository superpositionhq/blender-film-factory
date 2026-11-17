#!/usr/bin/env python3
"""Called by each film repo's git post-commit hook: record the new commit.

  python record-film-commit.py <repo>

Appends the commit to <root>/.recording/<repo name>/commits.jsonl (schema commit/v0: n = its number in the history,
sha, parents, author, times, message, files), whoever made it. The picture of a step is not taken here: tools/step.py
renders it before the commit and it is part of the commit (steps/<n>-<name>/preview.png).

Nothing is recorded when BFF_NO_RECORDING is set. machine/install-git-hook.py adds the hook line to a repo.
Standard library only.
"""
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
sys.path[:0] = [str(HOOKS), str(HOOKS.parent / 'lib')]
import bffroot  # noqa: E402


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '-c', 'core.quotepath=off', *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout


def main():
    if os.environ.get('BFF_NO_RECORDING') or len(sys.argv) < 2:
        return
    repo = Path(sys.argv[1]).resolve()
    root = bffroot.root().resolve()
    out = root / '.recording' / repo.name
    sha = git(repo, 'rev-parse', 'HEAD').strip()
    if not sha:
        return
    parents, author, atime, ctime, message = git(repo, 'log', '-1', '--format=%P%x00%an%x00%aI%x00%cI%x00%B',
                                                 sha).split('\0', 4)
    files = [{'status': f[0], 'path': f[-1]} for line in git(repo, 'show', '--name-status', '--format=', sha)
             .splitlines() if line.strip() for f in [line.split('\t')]]
    n = int(git(repo, 'rev-list', '--count', sha).strip() or 0)
    row = dict(schema='commit/v0', recorded_at=bffroot.now(), project=repo.name, n=n, sha=sha,
               parents=parents.split(), author=author, author_time=atime, commit_time=ctime,
               message=message.strip(), files=files)
    with bffroot.Lock():
        bffroot.append_jsonl(out / 'commits.jsonl', [row])



if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
