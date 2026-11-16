#!/usr/bin/env python3
"""Rebuild a film's scene from an empty file by running its step scripts in order, and compare with scene.blend.

  python tools/replay.py <film> [--keep]

Runs build/order.txt with plain Blender into <film>/.local/replay/scene.blend, then compares both scenes at five
frames per shot: the same objects, types, triangle counts, materials, markers and visibility, and world transforms
within 0.001. Prints REPLAY OK or the differences (exit code 2). A film whose replay differs was changed outside
its step scripts, or has a step that is not deterministic (an unseeded random, a simulation that is not baked to a
data file under build/data/). Python 3.9+ standard library only; needs Blender.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402


def compare(a, b, tol=1e-3):
    out = []
    for key in ('materials', 'markers', 'range', 'fps', 'resolution'):
        if a[key] != b[key]:
            out.append(f'{key} differ')
    if set(a['objects']) != set(b['objects']):
        out.append('objects differ: ' + ', '.join(sorted(set(a['objects']) ^ set(b['objects']))[:12]))
    worst = 0.0
    for name, ra in a['objects'].items():
        rb = b['objects'].get(name)
        if not rb:
            continue
        if ra['type'] != rb['type'] or ra.get('tris') != rb.get('tris'):
            out.append(f'{name}: mesh differs ({ra.get("tris")} / {rb.get("tris")} triangles)')
        if ra['hide'] != rb['hide']:
            out.append(f'{name}: visibility differs')
        for f, m in ra['m'].items():
            d = max(abs(x - y) for x, y in zip(m, rb['m'].get(f, m)))
            worst = max(worst, d)
            if d > tol:
                out.append(f'{name}: transform differs at frame {f} by {d:.4f}')
                break
    return out, worst


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    film = Path(sys.argv[1]).resolve()
    exe = bffroot.blender()
    if not exe:
        sys.exit('Blender not found (machine/bootstrap.py)')
    work = film / '.local' / 'replay'
    work.mkdir(parents=True, exist_ok=True)
    out = work / 'scene.blend'
    r = subprocess.run([exe, '-b', '--factory-startup', '--python-exit-code', '1', '--python', str(REPO / 'tools' / 'blender' / 'replay.py'),
                        '--', str(film), str(out)], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(film))
    if r.returncode:
        print('REPLAY FAILED: a step script raised an error when run from an empty file\n' + (r.stdout + r.stderr)[-1500:])
        sys.exit(2)
    dumps = []
    for blend, name in ((film / 'scene.blend', 'scene.json'), (out, 'replay.json')):
        subprocess.run([exe, '-b', str(blend), '--python', str(REPO / 'tools' / 'blender' / 'measure.py'), '--', 'state', str(work / name)],
                       capture_output=True, text=True, cwd=str(film))
        dumps.append(json.loads((work / name).read_text(encoding='utf-8')))
    diffs, worst = compare(*dumps)
    n = len(dumps[0]['objects'])
    tris = sum(o.get('tris', 0) for o in dumps[0]['objects'].values())
    (work / 'result.json').write_text(json.dumps(dict(ok=not diffs, objects=n, tris=tris, worst=worst, differences=diffs), indent=1), encoding='utf-8')
    if diffs:
        print(f'REPLAY DIFFERS ({len(diffs)}):\n  ' + '\n  '.join(diffs[:30]))
        sys.exit(2)
    print(f'REPLAY OK: {n} objects, {tris} triangles, largest transform difference {worst:.5f}')
    if '--keep' not in sys.argv:
        out.unlink()


if __name__ == '__main__':
    main()
