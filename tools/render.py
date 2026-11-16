#!/usr/bin/env python3
"""Render frames of a film without changing it: test frames, sheets, animatics and the final video.

  python tools/render.py <film> --frames 1,60,120 [--pct 50] [--samples 16] [--clay] [--out <dir>] [--sheet <cols>]
  python tools/render.py <film> --shots [--per-shot 3] ...        first / middle / last (or N) frames of every shot
  python tools/render.py <film> --all [--mp4 out/film.mp4] [--audio <wav>] [--resume] [--pct 100] [--clay]

Frames go to <film>/.local/render/<name>/f<frame>.png (name: --out, default "test"; .local is never committed).
--sheet N tiles the frames just rendered into <out>/sheet.png, N per row, so one picture shows them all.
--all renders frame_start..frame_end; with --mp4 it then encodes H.264 (yuv420p, crf 16) at the scene's frame rate,
scaled to the full film size when --pct is under 100, with --audio muxed in. --resume skips frames that are there.
--clay renders the white-model version (one clay material, plain light): the previs look and the clay animatic.
It prints the seconds per frame. Python 3.9+ standard library only; needs Blender and ffmpeg.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402


def last_state(film):
    steps = sorted(d for d in (film / 'steps').iterdir() if (d / 'state.json').is_file() and
                   json.loads((d / 'result.json').read_text(encoding='utf-8')).get('ok'))
    if not steps:
        sys.exit('no successful step yet')
    return json.loads((steps[-1] / 'state.json').read_text(encoding='utf-8'))


def shot_ranges(state):
    marks = [m for m in state['markers'] if m['camera']]
    ends = [m['frame'] - 1 for m in marks[1:]] + [state['frame_end']]
    return [(m['frame'], e) for m, e in zip(marks, ends)]


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--frames')
    g.add_argument('--shots', action='store_true')
    g.add_argument('--all', action='store_true')
    p.add_argument('--per-shot', type=int, default=3)
    p.add_argument('--pct', type=int, default=50)
    p.add_argument('--samples', type=int)
    p.add_argument('--clay', action='store_true')
    p.add_argument('--out', default='test')
    p.add_argument('--sheet', type=int)
    p.add_argument('--mp4')
    p.add_argument('--audio')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    film = Path(a.film).resolve()
    exe, ff = bffroot.blender(), bffroot.ffmpeg()
    if not exe:
        sys.exit('Blender not found (machine/bootstrap.py)')
    state = last_state(film)
    if a.frames:
        frames = [int(x) for x in a.frames.split(',')]
    elif a.shots:
        frames = []
        for s, e in shot_ranges(state):
            n = max(1, a.per_shot)
            frames += [s + round((e - s) * (i + 0.5) / n) for i in range(n)] if n != 3 else [s + min(8, (e - s) // 4), (s + e) // 2, e - min(8, (e - s) // 4)]
    else:
        frames = list(range(state['frame_start'], state['frame_end'] + 1))
    out = film / '.local' / 'render' / a.out
    out.mkdir(parents=True, exist_ok=True)
    opts = [f'pct={a.pct}'] + ([f'samples={a.samples}'] if a.samples else []) + (['clay=1'] if a.clay else []) + (['skip=1'] if a.resume else [])
    times = []
    for i in range(0, len(frames), 400):   # the frame list rides on the command line: keep each call short
        chunk = frames[i:i + 400]
        proc = subprocess.Popen([exe, '-b', str(film / 'scene.blend'), '--python', str(REPO / 'tools' / 'blender' / 'render_frames.py'),
                                 '--', str(out), ','.join(map(str, chunk)), *opts], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', cwd=str(film))
        tail = []
        for line in proc.stdout:
            tail = (tail + [line])[-30:]
            m = re.match(r'RENDERED (\d+) ([\d.]+)', line)
            if m:
                times.append(float(m[2]))
                if a.all and len(times) % 48 == 0:
                    print(f'  {len(times)} frames, {sum(times) / len(times):.1f} s per frame', flush=True)
        if proc.wait():
            sys.exit('render failed:\n' + ''.join(tail))
    have = [f for f in frames if (out / f'f{f:05d}.png').is_file()]
    print(f'{len(have)} of {len(frames)} frames in {out}' + (f', {sum(times) / len(times):.2f} s per frame, longest {max(times):.2f}' if times else ''))
    if a.sheet and have and ff:
        cols = a.sheet
        rows = -(-len(have) // cols)
        ins = []
        for f in have:
            ins += ['-i', str(out / f'f{f:05d}.png')]
        w = 640 if len(have) > 4 else 960
        fc = ''.join(f'[{i}]scale={w}:-2[v{i}];' for i in range(len(have))) + ''.join(f'[v{i}]' for i in range(len(have))) + \
            f'concat=n={len(have)}:v=1,tile={cols}x{rows}:padding=4:margin=4:color=0x111111'
        r = subprocess.run([ff, '-y', '-loglevel', 'error', *ins, '-filter_complex', fc, '-frames:v', '1', str(out / 'sheet.png')], capture_output=True, text=True)
        print(f'sheet: {out / "sheet.png"} (frames {", ".join(map(str, have))})' if r.returncode == 0 else f'sheet failed: {r.stderr.strip()[-300:]}')
    if a.all and a.mp4:
        if not ff:
            sys.exit('ffmpeg not found')
        if len(have) != len(frames):
            sys.exit('frames are missing: no video written')
        dst = film / a.mp4
        dst.parent.mkdir(parents=True, exist_ok=True)
        fps, (W, H) = state['fps'], state['resolution']
        cmd = [ff, '-y', '-loglevel', 'error', '-framerate', f'{fps:g}', '-start_number', str(frames[0]), '-i', str(out / 'f%05d.png')]
        if a.audio:
            cmd += ['-i', str((film / a.audio) if not Path(a.audio).is_absolute() else a.audio)]
        cmd += ['-vf', f'scale={W}:{H}:flags=lanczos', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow', '-r', f'{fps:g}']
        cmd += (['-c:a', 'aac', '-b:a', '192k', '-shortest'] if a.audio else []) + ['-movflags', '+faststart', str(dst)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(f'video: {dst} ({len(frames)} frames, {len(frames) / fps:.2f} s)' if r.returncode == 0 else f'encode failed: {r.stderr.strip()[-400:]}')


if __name__ == '__main__':
    main()
