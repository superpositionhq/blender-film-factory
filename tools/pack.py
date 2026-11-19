#!/usr/bin/env python3
"""Assemble a released film and its recorded session into one dataset archive.

  python tools/pack.py <film> [--out <zip>] [--name <folder name>] [--no-history] [--no-check] [--keep]

Writes <film>/.local/pack/<name>/ and zips it (default <film>/.local/pack/<name>-dataset.zip; <name> defaults to
<slug>-<title in lower case with hyphens>):
  film/         every tracked file of the film repo at HEAD (brief, docs, build scripts, steps, workflow rows, shot
                list, inputs, out/), with real pictures and videos, not LFS pointers
  history/commits.jsonl  ordered commit records: original hashes, parents, timestamps, messages and text diffs
                        (--no-history leaves it out); author identities are omitted
  trajectory/   a fresh tools/trajectory.py export of the session: trajectory.jsonl, trajectory.md, images/,
                analysis.json (paths, names and secrets rewritten)
  DATASET.md    what is in the archive, with its counts
Not packed: the raw recording (<BFF_ROOT>/.recording/<slug>/), which is not scrubbed.

Checks, each printed: the film repo has no uncommitted change; tools/validate-film.py --release says VALID
(--no-check skips it); the trajectory export has no leak; no text file holds a private or banned name.
Exit code 0 with the archive written, 2 when a check fails (the archive is then not written).
The film is only read. --keep leaves the staged folder beside the zip. Python 3.9+ standard library only; needs git.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402

TEXT = {'.py', '.md', '.json', '.jsonl', '.txt', '.log', '.gitignore', '.gitattributes'}


def git(cwd, *args):
    r = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout + r.stderr).strip()


def tool(name, *args):
    r = subprocess.run([sys.executable, str(REPO / 'tools' / name), *map(str, args)], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def export_history(film, destination):
    """Export reachable commits in parent-first order; binary contents remain in film/.

    Patches compare each commit to its first parent (or the empty tree for the root).
    They are review records, not a replacement for a Git object database.
    """
    from trajectory import redact_text

    def read(*args):
        rc, text = git(film, *args)
        if rc:
            raise RuntimeError(text[-300:])
        return text

    identities = set(read('log', '--format=%an%n%ae%n%cn%n%ce', 'HEAD').splitlines())
    private = list(bffroot.config().get('private_names') or []) + (os.environ.get('BFF_PRIVATE_NAMES') or '').split(',')
    replacements = identities | set(private) | {Path.home().name, bffroot.org()}

    def scrub(text):
        for path, label in sorted([(str(film), '<film>'), (str(bffroot.root()), '<root>'),
                                   (str(REPO), '<tools>'), (str(Path.home()), '~')], key=lambda x: -len(x[0])):
            text = text.replace(path, label).replace(path.replace('/', '\\'), label)
        for name in sorted((n for n in replacements if n and len(n.strip()) >= 3), key=len, reverse=True):
            text = re.sub(re.escape(name), '<identity>', text, flags=re.I)
        for pattern in bffroot.BANNED:
            if not re.search(r'claude|anthropic|openai', pattern):
                text = re.sub(pattern, '<name>', text)
        return redact_text(text, set())

    hashes = read('rev-list', '--reverse', '--topo-order', 'HEAD').splitlines()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', encoding='utf-8', newline='\n') as out:
        for i, sha in enumerate(hashes, 1):
            parts = read('show', '-s', '--format=%P%x00%aI%x00%cI%x00%B', sha).split('\0', 3)
            parents, authored, committed, message = parts
            patch = read('diff-tree', '--root', '--no-commit-id', '-r', '-p', '--no-ext-diff',
                         '--no-textconv', '--no-renames', '--no-color',
                         *([parents.split()[0], sha] if parents else [sha]))
            row = dict(schema='film-commit/v1', seq=i, commit=sha, parents=parents.split(),
                       authored_at=authored, committed_at=committed, message=scrub(message),
                       patch=scrub(patch))
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
    return len(hashes)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('--out')
    p.add_argument('--name')
    p.add_argument('--no-history', '--no-git', dest='no_history', action='store_true')
    p.add_argument('--no-check', action='store_true')
    p.add_argument('--keep', action='store_true')
    p.add_argument('--work-dir', help='staging directory (default: film/.local/pack)')
    a = p.parse_args()
    film = Path(a.film).resolve()
    if not (film / 'film.json').is_file():
        sys.exit(f'{film} is not a film (no film.json)')
    meta = json.loads((film / 'film.json').read_text(encoding='utf-8'))
    title = re.sub(r'[^a-z0-9]+', '-', meta.get('title', '').lower()).strip('-')
    name = a.name or '-'.join(x for x in (meta.get('slug', film.name), title) if x)
    work = Path(a.work_dir).resolve() if a.work_dir else film / '.local' / 'pack'
    stage = work / name
    out = Path(a.out).resolve() if a.out else work / f'{name}-dataset.zip'
    problems, warnings = [], []

    rc, dirty = git(film, 'status', '--porcelain')
    if rc or dirty.strip():
        problems.append('the film repo has uncommitted changes (or is not a git repo): commit first')
    if not a.no_check:
        rc, text = tool('validate-film.py', film, '--release', '--scratch', work / '_checks')
        last = text.splitlines()[-1] if text else ''
        print('release check: ' + last)
        if rc:
            problems.append('the film is not valid for release: ' + last)
        warnings += [l for l in text.splitlines() if l.startswith('WARN')]

    if stage.exists():
        shutil.rmtree(stage)
    (stage / 'film').mkdir(parents=True)

    # film/: the tracked files as they are in the work tree
    rc, listed = git(film, 'ls-files', '-z')
    # notes written after a session are not part of the record (older films may still track the file)
    listed = '\0'.join(f for f in listed.split('\0') if f != 'notes-backfill.jsonl') if not rc else listed
    files = [f for f in listed.split('\0') if f]
    pointers = 0
    for rel in files:
        src, dst = film / rel, stage / 'film' / rel
        if not src.is_file():
            problems.append(f'tracked file missing in the work tree: {rel}')
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        with open(src, 'rb') as f:
            pointers += f.read(40).startswith(b'version https://git-lfs')
    if pointers:
        problems.append(f'{pointers} file(s) are Git LFS pointers, not their content: run `git lfs checkout` in the film')
    print(f'film/: {len(files)} tracked files')

    # Structured history preserves commit references without distributing a git database.
    commits = None
    if not a.no_history:
        try:
            commits = export_history(film, stage / 'history' / 'commits.jsonl')
            print(f'history/commits.jsonl: {commits} commits')
        except (RuntimeError, ValueError) as exc:
            problems.append(f'history export failed: {exc}')

    # trajectory/
    rc, text = tool('trajectory.py', film, '--out', stage / 'trajectory', '--check')
    print('trajectory: ' + (text.splitlines()[-1] if text else 'failed'))
    if rc:
        problems.append('the trajectory export needs work (notes, looked-at pictures or leaks): tools/trajectory.py lists it')
    ana = {}
    if (stage / 'trajectory' / 'analysis.json').is_file():
        ana = json.loads((stage / 'trajectory' / 'analysis.json').read_text(encoding='utf-8'))

    # names: nothing of the machine or its owner in any text file
    account = Path.home().name
    pats = [(pat, 'a banned name') for pat in bffroot.BANNED if not re.search(r'claude|anthropic|openai', pat)]
    if len(account) >= 4:
        pats.append((r'(?i)(?<![a-z0-9])' + re.escape(account) + r'(?![a-z0-9])', 'the account name'))
    if bffroot.org():
        pats.append((r'(?i)' + re.escape(bffroot.org()), 'the organisation'))
    private = list(bffroot.config().get('private_names') or []) + (os.environ.get('BFF_PRIVATE_NAMES') or '').split(',')
    pats += [('(?i)' + re.escape(n.strip()), 'a private name') for n in private if len(n.strip()) >= 3]
    hits = {}
    for f in stage.rglob('*'):
        if f.is_file() and '.git' not in f.relative_to(stage).parts and (f.suffix.lower() in TEXT or f.name in TEXT):
            text = f.read_text(encoding='utf-8', errors='replace')
            for pat, what in pats:
                if re.search(pat, text):
                    hits.setdefault(f.relative_to(stage).as_posix(), set()).add(what)
    for f, what in sorted(hits.items())[:20]:
        problems.append(f'{f} holds {", ".join(sorted(what))}')
    print(f'names: {len(hits)} text file(s) with a name that must not ship')

    # DATASET.md
    steps = sorted(d.name for d in (film / 'steps').iterdir() if re.match(r'\d{4}-', d.name)) if (film / 'steps').is_dir() else []
    rows = [l for l in (film / 'workflow.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()] if (film / 'workflow.jsonl').is_file() else []
    fmt = meta.get('format', {})
    md = [f"# {meta.get('title', name)}: dataset\n",
          f"{meta.get('description', '')}\n",
          f"Input: {meta.get('input')}. Output: {meta.get('output')}. {fmt.get('width')}x{fmt.get('height')} at {fmt.get('fps')} fps.\n",
          '| Folder | What it holds |', '|---|---|',
          f"| `film/` | the film repo at its release: {len(files)} tracked files, {len(steps)} step folders (script, scene state, picture each), {len(rows)} workflow rows, `out/` with the videos, the contact sheet and the scene |"]
    if commits is not None:
        md.append(f'| `history/commits.jsonl` | {commits} commits with original hashes, parents, timestamps, messages and text diffs |')
    md.append(f"| `trajectory/` | the recorded session in time order: {ana.get('events')} events ({ana.get('prompts')} prompts, "
              f"{ana.get('replies')} replies, {ana.get('reasoning_summaries')} reasoning summaries, {ana.get('tool_calls')} tool calls), "
              f"{ana.get('pictures_opened')} opened pictures in `images/`, `analysis.json` |")
    md += ['', '## Record', '',
           f"- steps called: {ana.get('step_calls')}; a note or reasoning summary before {ana.get('note_coverage')}, a written reply before {ana.get('reply_coverage')}, a picture looked at before {ana.get('looked_coverage')} (shares of the steps)"]
    md += [f"- leaks left in the export: {ana.get('leak_events')}; secrets redacted: {ana.get('secrets_redacted')}",
           '- not packed: the raw recording, which is not scrubbed', '',
           'File formats: `film/README.md`, and the film format page of the tools that made it.', '']
    (stage / 'DATASET.md').write_text('\n'.join(md), encoding='utf-8', newline='\n')

    if not a.no_history:
        rc, text = tool('validate-package.py', stage)
        print(text)
        if rc:
            problems.append('package format validation failed')

    for w in warnings:
        print('WARN  ' + w.replace('WARN', '').strip())
    if problems:
        print(f'NOT PACKED ({len(problems)} problem(s)):\n  ' + '\n  '.join(problems))
        sys.exit(2)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    n = size = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(stage.rglob('*')):
            if f.is_file():
                z.write(f, (Path(name) / f.relative_to(stage)).as_posix())
                n += 1
                size += f.stat().st_size
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
    if bad:
        print(f'NOT PACKED: the archive is damaged at {bad}')
        sys.exit(2)
    if not a.keep:
        shutil.rmtree(stage)
    print(f'PACKED: {out} ({n} files, {size / 1e6:.0f} MB unpacked, {out.stat().st_size / 1e6:.0f} MB zipped)')


if __name__ == '__main__':
    main()
