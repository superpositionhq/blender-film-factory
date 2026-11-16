#!/usr/bin/env python3
"""Make a film's deliverables from its finished scene, check them, and commit them.

  python tools/release.py <film> [--pct 100] [--samples N] [--audio <wav in the film>] [--resume] [--no-commit]

In this order (each line says what it did):
  1. out/film.mp4            every frame at full size (final) or with the greybox look as built (greybox)
  2. out/animatic_clay.mp4   the same frames with one clay material and a plain light
  3. out/contact_sheet.png   three frames of every shot, from the film's frames
  4. out/greybox.mp4         final films only: must be there already (the grey-box video of the blockout stage)
  5. out/scene.blend         a copy of the finished scene
  6. tools/replay.py, tools/shots.py, tools/trajectory.py (the recorded session as one ordered trajectory, in
     <BFF_ROOT>/.recording/<slug>/trajectory/), tools/validate-film.py --release
  7. one commit "Release: film, clay animatic, contact sheet, scene" when the film is VALID for release
Frames stay in .local/render/final and .local/render/clay; --resume goes on where a render stopped, and renders again
every frame from before the last step (older than scene.blend), so a fix made since is in the video.
Check the time per frame with tools/render.py --shots first: 5 s per frame is 6 minutes for a 30 s film at 24 fps.
Python 3.9+ standard library only; needs Blender and ffmpeg.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402


def tool(name, *args):
    r = subprocess.run([sys.executable, str(REPO / 'tools' / name), *map(str, args)], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print('  ' + out.replace('\n', '\n  '))
    return r.returncode


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('--pct', type=int, default=100)
    p.add_argument('--samples', type=int)
    p.add_argument('--audio')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--no-commit', action='store_true')
    a = p.parse_args()
    film = Path(a.film).resolve()
    meta = json.loads((film / 'film.json').read_text(encoding='utf-8'))
    ff = bffroot.ffmpeg()
    extra = (['--samples', a.samples] if a.samples else []) + (['--resume'] if a.resume else [])
    print('1. film')
    if tool('render.py', film, '--all', '--pct', a.pct, '--out', 'final', '--mp4', 'out/film.mp4', *(['--audio', a.audio] if a.audio else []), *extra):
        sys.exit(1)
    print('2. clay animatic')
    if tool('render.py', film, '--all', '--clay', '--pct', min(a.pct, 100), '--samples', 16, '--out', 'clay', '--mp4', 'out/animatic_clay.mp4', *(['--resume'] if a.resume else [])):
        sys.exit(1)
    print('3. contact sheet')
    steps = sorted((film / 'steps').glob('*/state.json'))
    state = json.loads(steps[-1].read_text(encoding='utf-8'))
    marks = [m for m in state['markers'] if m['camera']]
    ends = [m['frame'] - 1 for m in marks[1:]] + [state['frame_end']]
    frames = []
    for m, e in zip(marks, ends):
        s = m['frame']
        pad = min(10, (e - s) // 4)
        frames += [s + pad, (s + e) // 2, e - pad]
    ins = []
    for f in frames:
        ins += ['-i', str(film / '.local' / 'render' / 'final' / f'f{f:05d}.png')]
    fc = ''.join(f'[{i}]scale=640:-2[v{i}];' for i in range(len(frames))) + ''.join(f'[v{i}]' for i in range(len(frames))) + \
        f'concat=n={len(frames)}:v=1,tile=3x{len(marks)}:padding=6:margin=6:color=0x111111'
    r = subprocess.run([ff, '-y', '-loglevel', 'error', *ins, '-filter_complex', fc, '-frames:v', '1', str(film / 'out' / 'contact_sheet.png')], capture_output=True, text=True)
    print(f'  out/contact_sheet.png: frames {frames}' if r.returncode == 0 else '  FAILED: ' + r.stderr.strip()[-300:])
    if meta.get('output') == 'final':
        have = (film / 'out' / 'greybox.mp4').is_file()
        print('4. grey-box video\n  out/greybox.mp4 ' + ('is there' if have else 'IS MISSING: render it from the blockout stage (blender-film-session skill, "Build order", 3)'))
    print('5. scene')
    shutil.copyfile(film / 'scene.blend', film / 'out' / 'scene.blend')
    print('  out/scene.blend')
    print('6. checks')
    tool('replay.py', film)
    tool('shots.py', film)
    tool('trajectory.py', film)
    ok = tool('validate-film.py', film, '--release') == 0
    if ok and not a.no_commit:
        subprocess.run(['git', '-C', str(film), 'add', '-A'])
        subprocess.run(['git', '-C', str(film), 'commit', '-q', '-m', 'Release: film, clay animatic, contact sheet, scene'])
        print('7. committed ' + subprocess.run(['git', '-C', str(film), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip())
    elif not ok:
        print('7. not committed: fix what the validator names, then run release.py --resume')
        sys.exit(2)


if __name__ == '__main__':
    main()
