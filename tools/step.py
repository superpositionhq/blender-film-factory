#!/usr/bin/env python3
"""Run one build step of a film: the only way a film's scene changes. One step = one visible change = one commit.

  python tools/step.py <film> "<what changes on screen>" build/<NNN>_<name>.py --op <op> --target <object or area>
      --reason "<brief action purpose or visible issue>" [--frame <n>] [--new] [--no-preview] [--direction <row id>] [--no-commit]

It runs the script in headless Blender on <film>/scene.blend (--new: on an empty factory file; first step only) and
records the step in <film>/steps/<NNNN>-<name>/:
  script.py     the exact code that ran          stdout.log   Blender's output
  state.json    the scene after the step         preview.png  a 960 px picture from the shot camera at --frame
  result.json   ok / error / seconds
A checkpoint .blend of the step goes to <film>/.local/checkpoints/ (not committed). Then, in this order: the script
is added to build/order.txt (the replay order), one workflow.jsonl row is written (op, target, reason; params: step,
script, ok, seconds, counts, preview frame), and everything is committed with the step name as the subject.
A script that fails changes nothing in scene.blend; its step folder, row (status failed) and commit are still made:
dead ends are record. Fix the script and run the step again as a new step.
Blender: env BLENDER, else the machine config, else the usual places. Python 3.9+ standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402


def git(film, *args):
    return subprocess.run(['git', '-C', str(film), *args], capture_output=True, text=True, encoding='utf-8', errors='replace')


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('name')
    p.add_argument('script')
    p.add_argument('--op', required=True)
    p.add_argument('--target', required=True)
    p.add_argument('--reason', required=True)
    p.add_argument('--frame', type=int)
    p.add_argument('--new', action='store_true', help='start from an empty file (first step only)')
    p.add_argument('--no-preview', action='store_true')
    p.add_argument('--direction')
    p.add_argument('--no-commit', action='store_true')
    a = p.parse_args()

    film = Path(a.film).resolve()
    script = (film / a.script).resolve() if not Path(a.script).is_absolute() else Path(a.script).resolve()
    if not (film / 'film.json').is_file():
        sys.exit(f'{film} is not a film (no film.json): templates/new-film.py makes one')
    if not script.is_file() or film / 'build' not in script.parents:
        sys.exit(f'the step script must be a file under {film / "build"} (got {a.script})')
    exe = bffroot.blender()
    if not exe:
        sys.exit('Blender not found: set env BLENDER or run machine/bootstrap.py --blender <path>')
    blend = film / 'scene.blend'
    if a.new and blend.exists():
        sys.exit('--new is for the first step only: scene.blend exists')
    if not a.new and not blend.exists():
        sys.exit('scene.blend does not exist: run the first step with --new')

    steps = film / 'steps'
    steps.mkdir(exist_ok=True)
    n = len([d for d in steps.iterdir() if re.match(r'\d{4}-', d.name)]) + 1
    slug = re.sub(r'[^a-z0-9]+', '-', a.name.lower()).strip('-')[:60].strip('-')
    step_id = f'{n:04d}-{slug}'
    step_dir = steps / step_id
    step_dir.mkdir()
    shutil.copyfile(script, step_dir / 'script.py')
    ckpt = film / '.local' / 'checkpoints'
    ckpt.mkdir(parents=True, exist_ok=True)

    cmd = [exe, '-b'] + (['--factory-startup'] if a.new else [str(blend)])
    cmd += ['--python-exit-code', '1', '--python', str(REPO / 'tools' / 'blender' / 'harness.py'), '--',
            str(script), str(step_dir), str(blend), str(ckpt / f'{step_id}.blend')]
    env = dict(os.environ, BFF_PREVIEW='0' if a.no_preview else '1')
    if a.frame is not None:
        env['BFF_FRAME'] = str(a.frame)
    t0 = time.time()
    with open(step_dir / 'stdout.log', 'w', encoding='utf-8') as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=str(film)).returncode
    seconds = round(time.time() - t0, 1)
    res_path = step_dir / 'result.json'
    res = json.loads(res_path.read_text(encoding='utf-8')) if res_path.is_file() else {'ok': False, 'error': f'blender exit {rc}'}
    ok = bool(res.get('ok'))
    backup = film / 'scene.blend1'
    if backup.exists():
        backup.unlink()
    # machine paths never go into the repo: keep the log relative to the film
    log = (step_dir / 'stdout.log').read_text(encoding='utf-8', errors='replace')
    for full in sorted({str(film), str(film.resolve()), str(REPO), str(Path.home())}, key=len, reverse=True):
        log = log.replace(full, '<film>' if full.startswith(str(film)) else '<tools>' if full == str(REPO) else '~')
    (step_dir / 'stdout.log').write_text(log, encoding='utf-8')
    if res.get('error'):
        err = res['error']
        for full in sorted({str(film), str(REPO), str(Path.home())}, key=len, reverse=True):
            err = err.replace(full, '<film>' if full == str(film) else '<tools>' if full == str(REPO) else '~')
        res['error'] = err
        res_path.write_text(json.dumps(res, indent=1), encoding='utf-8')

    rel = script.relative_to(film).as_posix()
    order = film / 'build' / 'order.txt'
    listed = order.read_text(encoding='utf-8').split() if order.is_file() else []
    if ok and rel not in listed:
        with open(order, 'a', encoding='utf-8', newline='\n') as f:
            f.write(rel + '\n')

    row_cmd = [sys.executable, str(REPO / 'tools' / 'workflow-row.py'), str(film), '--op', a.op, '--target', a.target,
               '--reason', a.reason, '--script', rel, '--status', 'observed' if ok else 'failed',
               '--param', f'step={json.dumps(step_id)}', '--param', f'ok={json.dumps(ok)}', '--param', f'seconds={seconds}',
               '--param', 'counts=' + json.dumps(res.get('counts')), '--param', 'preview_frame=' + json.dumps(res.get('preview_frame'))]
    if a.direction:
        row_cmd += ['--direction', a.direction]
    r = subprocess.run(row_cmd, capture_output=True, text=True)
    row_id = r.stdout.strip() if r.returncode == 0 else None
    if not row_id:
        print(f'WARNING: no workflow row written: {r.stderr.strip()}', file=sys.stderr)

    sha = None
    if not a.no_commit:
        git(film, 'add', '-A')
        subject = (a.name if ok else f'Failed: {a.name}')[:100]
        body = f'{a.reason}\n\nstep: {step_id}' + (f'\nworkflow: {row_id}' if row_id else '')
        if a.direction:
            body += f'\nDirection: {a.direction}'
        c = git(film, 'commit', '-q', '-m', subject, '-m', body)
        if c.returncode:
            print(f'WARNING: commit failed: {(c.stderr or c.stdout).strip()}', file=sys.stderr)
        sha = git(film, 'rev-parse', '--short', 'HEAD').stdout.strip()

    print(json.dumps(dict(step=step_id, ok=ok, seconds=seconds, row=row_id, commit=sha, counts=res.get('counts'))))
    if not ok:
        print((res.get('error') or '').strip()[-1500:], file=sys.stderr)
        print(f'step failed; see {step_dir / "stdout.log"}', file=sys.stderr)
        sys.exit(1)
    pic = step_dir / 'preview.png'
    print(f'preview: {pic}' if pic.is_file() else 'no preview (no camera yet, or --no-preview)'
          + (f'; {res["preview_error"].strip().splitlines()[-1]}' if res.get('preview_error') else ''))


if __name__ == '__main__':
    main()
