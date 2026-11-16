#!/usr/bin/env python3
"""Prepare a reference video for a film made from a video input: copy it in, cut it into shots, extract frames.

  python tools/reference.py <film> <video file> [--fps 4] [--cut 0.30] [--source "<where it is from, licence>"]

Writes into <film>/reference/:
  reference.<ext>        the clip, as given (Git LFS)
  reference.json         duration, frame rate, size, the detected cuts and the shots between them
  frames/s<k>_<t>.jpg    frames of each shot at --fps, 640 px wide, named by shot number and time in ms
  sheets/shot<k>.jpg     one contact sheet per shot (read these: they are how you see the clip)
  sheets/overview.jpg    one frame per shot, in order
Cuts are found with ffmpeg's scene score (--cut: lower finds more). They are a first guess: look at the sheets, and
correct the shot table in reference.json by hand when a cut is missed or a fast move is taken for one; say so in the
breakdown. Then write reference/Breakdown.md (blender-film-reference skill). Standard library; needs ffmpeg + ffprobe.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('video')
    p.add_argument('--fps', type=float, default=4)
    p.add_argument('--cut', type=float, default=0.30)
    p.add_argument('--source', default='')
    a = p.parse_args()
    film, video = Path(a.film).resolve(), Path(a.video).resolve()
    ff, fp = bffroot.ffmpeg(), bffroot.ffmpeg('ffprobe')
    if not ff or not fp:
        sys.exit('ffmpeg / ffprobe not found')
    if not (film / 'film.json').is_file() or not video.is_file():
        sys.exit('need a film folder (film.json) and a video file')
    ref = film / 'reference'
    (ref / 'frames').mkdir(parents=True, exist_ok=True)
    (ref / 'sheets').mkdir(exist_ok=True)
    clip = ref / f'reference{video.suffix.lower()}'
    if video != clip:
        shutil.copyfile(video, clip)
    meta = json.loads(subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                      'stream=width,height,r_frame_rate,nb_frames:format=duration', '-of', 'json', str(clip)],
                                     capture_output=True, text=True).stdout)
    st = meta['streams'][0]
    num, den = st['r_frame_rate'].split('/')
    fps, dur = float(num) / float(den), float(meta['format']['duration'])
    r = subprocess.run([ff, '-hide_banner', '-i', str(clip), '-vf', f"select='gt(scene,{a.cut})',showinfo", '-an', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    cuts = sorted({round(float(t), 3) for t in re.findall(r'pts_time:([\d.]+)', r.stderr) if 0.2 < float(t) < dur - 0.2})
    merged = []
    for c in cuts:                       # cuts closer than a third of a second are one cut (a flash, a dissolve)
        if not merged or c - merged[-1] > 0.34:
            merged.append(c)
    bounds = [0.0] + merged + [round(dur, 3)]
    shots = []
    for k, (s, e) in enumerate(zip(bounds[:-1], bounds[1:]), 1):
        n = max(2, min(24, round((e - s) * a.fps)))
        names = []
        for i in range(n):
            t = s + (e - s) * (i + 0.5) / n
            name = f's{k:02d}_{round(t * 1000):06d}.jpg'
            subprocess.run([ff, '-y', '-loglevel', 'error', '-ss', f'{t:.3f}', '-i', str(clip), '-frames:v', '1', '-vf', 'scale=640:-2',
                            '-q:v', '3', str(ref / 'frames' / name)])
            if (ref / 'frames' / name).is_file():
                names.append(name)
        cols = min(4, len(names))
        ins = []
        for nme in names:
            ins += ['-i', str(ref / 'frames' / nme)]
        if names:
            fc = ''.join(f'[{i}]' for i in range(len(names))) + f'concat=n={len(names)}:v=1,tile={cols}x{-(-len(names) // cols)}:padding=4:margin=4'
            subprocess.run([ff, '-y', '-loglevel', 'error', *ins, '-filter_complex', fc, '-frames:v', '1', '-q:v', '3', str(ref / 'sheets' / f'shot{k:02d}.jpg')])
        shots.append(dict(shot=k, start_s=round(s, 3), end_s=round(e, 3), seconds=round(e - s, 3), frames=names))
    mids = [s['frames'][len(s['frames']) // 2] for s in shots if s['frames']]
    if mids:
        ins = []
        for nme in mids:
            ins += ['-i', str(ref / 'frames' / nme)]
        cols = min(5, len(mids))
        fc = ''.join(f'[{i}]' for i in range(len(mids))) + f'concat=n={len(mids)}:v=1,tile={cols}x{-(-len(mids) // cols)}:padding=4:margin=4'
        subprocess.run([ff, '-y', '-loglevel', 'error', *ins, '-filter_complex', fc, '-frames:v', '1', '-q:v', '3', str(ref / 'sheets' / 'overview.jpg')])
    out = dict(schema='film-reference/v1', file=clip.name, source=a.source, duration_s=round(dur, 3), fps=round(fps, 3),
               size=[st['width'], st['height']], cut_threshold=a.cut, cuts_s=merged, shots=shots)
    (ref / 'reference.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print(f'{clip.name}: {dur:.2f} s, {fps:g} fps, {st["width"]}x{st["height"]}, {len(shots)} shots (cuts at {merged})')
    print(f'read {ref / "sheets"} (overview.jpg, then shot<k>.jpg), then write {ref / "Breakdown.md"}')


if __name__ == '__main__':
    main()
