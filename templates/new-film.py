#!/usr/bin/env python3
"""Create a new film repo from templates/film (Blender 5.2, built headless, one recorded step at a time).

  python <root>/blender-film-factory/templates/new-film.py --slug <slug> --path <root>/films/<slug> \
      --title "<Title>" --description "<one line>" --input script|storyboard --output final|greybox
      [--width N --height N --min-seconds N --max-seconds N --min-shots N] [--id-prefix <letters>]
      [--reason "<why>"] [--org <github org>] [--no-remote]
  (<root> written out, e.g. /Users/<you>/FilmWork or C:\\Users\\<you>\\FilmWork)

--input says what the film is made from: `script` (a written script) or `storyboard` (a script with storyboard
pictures).
--output says what is delivered: `final` (a finished picture: materials, lighting, grade; 1920x1080, 20-45 s, at
least 5 shots unless the brief says otherwise) or `greybox` (a grey-box video: mannequins and
blocks, staging, motion, camera and cuts only; 1280x720, 6-60 s). It writes the skeleton (film.json, Brief.md, Docs/Treatment.md, build/kit.py and
build/mannequin.py, an empty shot list, root-anchored .gitignore, LFS for pictures, videos and .blend), the first
workflow.jsonl row (op film.create), git on `main` with the post-commit hook (the commit recorder), the first commit,
and the private GitHub repo <org>/film-<slug> (not pushed; <org> = --org, else the config's github_org; --no-remote
leaves it out, and a repo that cannot be made is a warning, not an error).

--path is required: the absolute film folder <root>/films/<slug>, written out in the command. The recording hooks
see the command text, so $BFF_ROOT or ~ would not map the session; this call files the session under the film, and
the hooks import its earlier calls from the transcript. Any other path is refused.
Placeholders replaced in the template: __SLUG__, __TITLE__, __DESCRIPTION__, __INPUT__, __OUTPUT__ and the format.
Python 3.9+ standard library only.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / 'templates' / 'film'
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402


def run(cmd, cwd=None):
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    return subprocess.run([exe, *cmd[1:]], cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('--slug', required=True)
    p.add_argument('--path', help='required: the absolute <root>/films/<slug>, written out')
    p.add_argument('--title', help='default from the slug: lantern-yard -> Lantern Yard')
    p.add_argument('--description', default='')
    p.add_argument('--input', choices=['script', 'storyboard'], required=True)
    p.add_argument('--output', choices=['final', 'greybox'], required=True)
    for k in ('width', 'height', 'min-seconds', 'max-seconds', 'min-shots'):
        p.add_argument('--' + k, type=int)
    p.add_argument('--id-prefix', help="workflow row id prefix; default the slug's initials (ly) or its first two letters")
    p.add_argument('--reason', default='Create the film from the standard skeleton (film.json, brief, treatment, the step kit and the '
                   'mannequin kit, LFS for pictures, videos and .blend)')
    p.add_argument('--org', help="default: the config's github_org (BFF_ORG)")
    p.add_argument('--no-remote', action='store_true', help='make no GitHub repo (tests, offline)')
    a = p.parse_args()

    if not re.fullmatch(r'(?!.*--)[a-z0-9][a-z0-9-]*[a-z0-9]', a.slug):
        sys.exit(f"slug '{a.slug}' must be lower-case letters, digits and single hyphens (lantern-yard)")
    root, org = bffroot.root(), a.org or bffroot.org()
    if not org and not a.no_remote:
        sys.exit('no GitHub org: set github_org (machine/bootstrap.py --org <org>), pass --org, or --no-remote')
    # Pre-flight, first: the recording hooks tie this session to the film when a tool call names the film
    # folder as an absolute path, so the call must carry --path <root>/films/<slug> literally.
    want = root / 'films' / a.slug
    if not a.path:
        sys.exit(f'pass --path {want} (the absolute film folder, written out, so the recording hooks file this '
                 'session under the film)')
    path = Path(a.path)
    if not path.is_absolute() or path.resolve() != want.resolve():
        sys.exit(f"--path must be the absolute folder {want} (got '{a.path}')")
    print(f'film folder: {want} (this call maps the session to {a.slug} for recording)')
    words = a.slug.split('-')
    title = a.title or ' '.join(w.capitalize() for w in words)
    prefix = a.id_prefix or (''.join(w[0] for w in words) if len(words) >= 2 else a.slug[:2])
    if not re.fullmatch(r'[a-z]+', prefix):
        sys.exit(f"workflow row id prefix '{prefix}' must be lower-case letters (pass --id-prefix)")
    # The title lands in film.json and the README's heading: keep it plain text.
    if re.search(r'[<>&"\\\r\n]', title):
        sys.exit(f"no quotes, angle brackets, ampersands, backslashes or line breaks in the title: '{title}'")
    # Names that must never appear inside a film. The repo's own name counts: film-<slug> is checked too.
    for v in (a.slug, f'film-{a.slug}', title, a.description, a.reason):
        if bffroot.banned_in(v) or (org and org.lower() in v.lower()):
            sys.exit(f"banned name in '{v}' (see the blender-film-session skill, \"Names\")")
    if want.exists() and any(want.iterdir()):
        sys.exit(f'{want} exists and is not empty')
    if not shutil.which('git'):
        sys.exit('git not found')

    final = a.output == 'final'
    fmt = dict(width=a.width or (1920 if final else 1280), height=a.height or (1080 if final else 720),
               min_seconds=a.min_seconds or (20 if final else 6), max_seconds=a.max_seconds or (45 if final else 60),
               min_shots=a.min_shots or (5 if final else 1))
    fill = {'__SLUG__': a.slug, '__TITLE__': title, '__DESCRIPTION__': a.description, '__INPUT__': a.input,
            '__OUTPUT__': a.output, '__WIDTH__': str(fmt['width']), '__HEIGHT__': str(fmt['height']),
            '__MIN_S__': str(fmt['min_seconds']), '__MAX_S__': str(fmt['max_seconds']), '__MIN_SHOTS__': str(fmt['min_shots'])}
    count = 0
    for src in sorted(f for f in TEMPLATE.rglob('*') if f.is_file() and f.name != '.DS_Store' and '__pycache__' not in f.parts):
        text = src.read_text(encoding='utf-8')
        for k, v in fill.items():
            text = text.replace(k, v)
        dst = want / src.relative_to(TEMPLATE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding='utf-8', newline='\n')
        count += 1
    json.loads((want / 'film.json').read_text(encoding='utf-8'))   # the filled template must be valid JSON

    # workflow.jsonl, first row: the operation this script just performed. The hash is of this script as committed (LF).
    script_sha = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    r = run(['git', '-C', str(REPO), 'rev-parse', '--short=12', 'HEAD'])
    row_id = f'{prefix}-00001'
    row = dict(schema='film-workflow/v0', id=row_id, seq=1, time=bffroot.now(), actor='agent', op='film.create',
               target='film.json',
               params=dict(engine='blender 5.2', input=a.input, output=a.output, format=fmt, template='film',
                           template_commit=r.stdout.strip() or None if r and r.returncode == 0 else None, files=count),
               reason=a.reason, reason_source='agent_note', status='observed',
               source=dict(script='new-film.py', sha256=script_sha, commit=None))
    bffroot.append_jsonl(want / 'workflow.jsonl', [row])

    # git + LFS + recorder, the packages, then the first commit (the post-commit hook records it).
    run(['git', '-C', str(want), 'init', '-q', '-b', 'main'])
    lfs = run(['git', '-C', str(want), 'lfs', 'install', '--local'])
    if not lfs or lfs.returncode:
        print('WARNING: git-lfs is not installed: install it before the first step (pictures, videos and .blend go through it)')
    hook = run([sys.executable, str(REPO / 'machine' / 'install-git-hook.py'), str(want)])
    if 'WARNING' in hook.stdout or hook.returncode:
        print((hook.stdout + hook.stderr).strip())
    run(['git', '-C', str(want), 'add', '-A'])
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(f'Create the {title} film ({a.input} in, {a.output} out)\n\n'
                'film.json, the brief and treatment pages, the step kit and the mannequin kit\n'
                f'(build/), an empty shot list, LFS for pictures, videos and .blend.\n\nworkflow: {row_id}\n')
    r = run(['git', '-C', str(want), 'commit', '-q', '-F', f.name])
    Path(f.name).unlink()
    if r.returncode:
        # what is left (the files, git, no commit) makes a second run refuse the folder as not empty
        sys.exit(f'commit failed (git user.name / user.email set?): {r.stderr.strip()}\nset them, delete {want} and '
                 'run new-film.py again')
    sha = run(['git', '-C', str(want), 'rev-parse', '--short', 'HEAD']).stdout.strip()

    remote = 'none (--no-remote)'
    if not a.no_remote:
        full = f'{org}/film-{a.slug}'
        make = f'gh repo create {full} --private; git -C "{want}" remote add origin https://github.com/{full}.git'
        if not shutil.which('gh'):
            remote = f'none. WARNING: gh (the GitHub CLI) is not installed: no repo made. Install it, then: {make}'
        elif run(['gh', 'repo', 'view', full, '--json', 'name']).returncode == 0:
            # never linked unseen: it may be another film's (same slug) or public
            remote = (f"none. WARNING: {full} already exists: not linked. Check that it is this film's and private, "
                      f'then: git -C "{want}" remote add origin https://github.com/{full}.git')
        elif run(['gh', 'repo', 'create', full, '--private', '--description', title]).returncode == 0:
            run(['git', '-C', str(want), 'remote', 'add', 'origin', f'https://github.com/{full}.git'])
            remote = f'https://github.com/{full} (private; not pushed: push when told)'
        else:
            remote = f'none. WARNING: could not create {full}; create it later: {make}'

    print(f'created {title} ({a.input} in, {a.output} out, {fmt["width"]}x{fmt["height"]}) at {want}')
    print(f'  files: {count}, first row {row_id}, commit {sha}')
    print(f'  remote: {remote}')
    print(f'  recording: {root / ".recording" / a.slug}')
    print('  next: put the input in Brief.md, write Docs/Treatment.md, then build in the staged order with tools/step.py')


if __name__ == '__main__':
    main()
