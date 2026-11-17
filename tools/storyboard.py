#!/usr/bin/env python3
"""Bring the storyboard pictures of a script-with-storyboard input into a film, in order.

  python tools/storyboard.py <film> <picture or folder> [<picture or folder> ...] [--source "<where from>"]

Copies the pictures (png, jpg, jpeg, webp; a folder gives its pictures sorted by name) to
<film>/storyboard/page_<NN>.<ext> in the order given, writes storyboard/storyboard.json (film-storyboard/v1: one
entry per page with its original file name and size) and storyboard/sheet.jpg (all pages on one sheet, numbered by
position: left to right, top to bottom). A page may hold one panel or many: you number the panels yourself in
Docs/Breakdown.md (blender-film-storyboard skill). Open every page with your image tool; the sheet is only the map.
Python 3.9+ standard library only; needs ffmpeg + ffprobe.
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

EXT = {'.png', '.jpg', '.jpeg', '.webp'}


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('pictures', nargs='+')
    p.add_argument('--source', default='')
    a = p.parse_args()
    film = Path(a.film).resolve()
    ff, fp = bffroot.ffmpeg(), bffroot.ffmpeg('ffprobe')
    if not (film / 'film.json').is_file():
        sys.exit(f'{film} is not a film (no film.json)')
    files = []
    for x in a.pictures:
        x = Path(x).resolve()
        files += sorted(f for f in x.iterdir() if f.suffix.lower() in EXT) if x.is_dir() else [x]
    files = [f for f in files if f.is_file() and f.suffix.lower() in EXT]
    if not files:
        sys.exit('no pictures given (png, jpg, jpeg, webp)')
    sb = film / 'storyboard'
    if sb.exists() and any(sb.glob('page_*')):
        sys.exit(f'{sb} already holds pages: a storyboard is brought in once')
    sb.mkdir(exist_ok=True)
    pages = []
    for n, f in enumerate(files, 1):
        dst = sb / f'page_{n:02d}{f.suffix.lower()}'
        shutil.copyfile(f, dst)
        size = None
        if fp:
            r = subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', str(dst)],
                               capture_output=True, text=True)
            try:
                size = [int(v) for v in r.stdout.strip().split(',')[:2]]
            except ValueError:
                pass
        pages.append(dict(page=n, file=dst.name, original_name=f.name, size=size))
    (sb / 'storyboard.json').write_text(json.dumps(dict(schema='film-storyboard/v1', source=a.source, pages=pages), indent=1) + '\n', encoding='utf-8')
    if ff:
        cols = min(4, len(pages))
        ins = []
        for pg in pages:
            ins += ['-i', str(sb / pg['file'])]
        fc = ''.join(f'[{i}]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:white,setsar=1[v{i}];' for i in range(len(pages))) + \
            ''.join(f'[v{i}]' for i in range(len(pages))) + f'concat=n={len(pages)}:v=1,tile={cols}x{-(-len(pages) // cols)}:padding=6:margin=6:color=0x222222'
        subprocess.run([ff, '-y', '-loglevel', 'error', *ins, '-filter_complex', fc, '-frames:v', '1', '-q:v', '3', str(sb / 'sheet.jpg')])
    print(f'{len(pages)} page(s) in {sb}: open each page_<NN> with your image tool, then number the panels in Docs/Breakdown.md')


if __name__ == '__main__':
    main()
