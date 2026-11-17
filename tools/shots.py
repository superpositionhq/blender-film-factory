#!/usr/bin/env python3
"""Measure every shot of a film from its scene and check shotlist.json against the measurement.

  python tools/shots.py <film>            measure, print one line per shot, check shotlist.json when it is there
  python tools/shots.py <film> --json     the same, as JSON on stdout
  python tools/shots.py <film> --subject 1=Anna --subject 2=Ben_Head     measure with these subjects (before the
                                          list exists, or to try another subject for a shot); nothing is checked

For each shot (a timeline marker with a camera, up to the next one) and the subject shotlist.json names for it, the
scene is sampled on every frame. What is declared must be what is measured (docs/shot-facts.md has the rules):
  camera_move  static | pan | tilt | dolly | truck | pedestal | orbit | crane | zoom | handheld, joined with "+"
  shot_size    extreme wide | wide | medium | close | extreme close   (subject's height in the frame, middle frame)
  camera_angle low | eye level | high | top-down                      (camera pitch towards the subject)
  subject      an object of the scene, its centre in frame for at least 90 % of the shot
  frames       frame_start / frame_end equal the markers and tile the scene's range; video times follow from them
  events       each names an object of the scene and a frame inside the shot
Exit code 0 when every declared fact holds, 2 otherwise. Python 3.9+ standard library only; needs Blender.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402

SIZES = [(0.12, 'extreme wide'), (0.35, 'wide'), (0.75, 'medium'), (1.5, 'close'), (1e9, 'extreme close')]
# a whole standing figure as the subject (its root carries the property "figure" or "mannequin"): sizes as film
# crews use them for people: wide = the whole body in frame, medium = about the waist up, close = head and shoulders
FIGURE_SIZES = [(0.25, 'extreme wide'), (1.1, 'wide'), (2.4, 'medium'), (6.0, 'close'), (1e9, 'extreme close')]


def classify_move(m):
    """The set of moves a measured shot shows."""
    dist = m.get('subject_distance') or 3.0
    lin = max(0.02, 0.02 * dist)          # translation that counts as a move: 2 % of the subject distance, 2 cm at least
    ang = 1.5                              # degrees of rotation that count
    moves = set()
    along, side, vert = abs(m['move_along_view']), abs(m['move_sideways']), abs(m['move_vertical'])
    # a camera looking straight down: its view axis is vertical, so along-view motion is the dolly, not a pedestal
    looking_down = abs(m.get('pitch_down_deg_mid') or 0) > 60
    if not looking_down:
        vert_own = vert
    else:
        vert_own = 0.0
    orbit = m['orbit_swept_deg'] > 5 and abs(m.get('subject_distance_change') or 0) < 0.2 and abs(m['yaw_deg']) > 3
    if orbit:
        moves.add('orbit')
    else:
        if along > lin:
            moves.add('dolly')
        if side > lin:
            moves.add('truck')
        if abs(m['yaw_deg']) > ang:
            moves.add('pan')
    if vert_own > lin:
        moves.add('crane' if (along > lin or side > lin) and not orbit else 'pedestal')
        if 'crane' in moves:
            moves -= {'dolly', 'truck'}
    if abs(m['tilt_deg']) > ang and not orbit:
        moves.add('tilt')
    if abs(m['lens_end'] - m['lens_start']) > 0.01 * m['lens_start']:
        moves.add('zoom')
    if m['reversals'] > max(6, m['frames'] * 0.2) and m['path_length'] > 0.002:
        moves = {'handheld'} | (moves & {'zoom'})
    return moves or {'static'}


def size_of(h, figure=False):
    return next(name for lim, name in (FIGURE_SIZES if figure else SIZES) if h < lim)


def angle_of(pitch):
    return 'top-down' if pitch > 60 else 'high' if pitch > 15 else 'low' if pitch < -10 else 'eye level'


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    film = Path(sys.argv[1]).resolve()
    exe = bffroot.blender()
    if not exe:
        sys.exit('Blender not found (machine/bootstrap.py)')
    sl_path = film / 'shotlist.json'
    declared = json.loads(sl_path.read_text(encoding='utf-8')) if sl_path.is_file() else []
    work = film / '.local' / 'shots'
    work.mkdir(parents=True, exist_ok=True)
    subjects = {str(d.get('shot')): d.get('subject') for d in declared}
    trial = [a.split('=', 1) for i, a in enumerate(sys.argv) if i and sys.argv[i - 1] == '--subject' and '=' in a]
    if trial:
        subjects.update(dict(trial))
        declared = []
    (work / 'subjects.json').write_text(json.dumps(subjects), encoding='utf-8')
    r = subprocess.run([exe, '-b', str(film / 'scene.blend'), '--python', str(REPO / 'tools' / 'blender' / 'measure.py'), '--',
                        'shots', str(work / 'subjects.json'), str(work / 'measured.json')], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=str(film))
    if not (work / 'measured.json').is_file():
        sys.exit('measuring failed:\n' + (r.stdout + r.stderr)[-1200:])
    meas = json.loads((work / 'measured.json').read_text(encoding='utf-8'))
    names = set()
    st = sorted((film / 'steps').glob('*/state.json'))
    if st:
        names = {o['name'] for o in json.loads(st[-1].read_text(encoding='utf-8'))['objects']}
    fps, problems, lines = meas['fps'], [], []
    by = {d.get('shot'): d for d in declared}
    for m in meas['shots']:
        m['measured_move'] = '+'.join(sorted(classify_move(m)))
        m['measured_size'] = size_of(m['subject_height_mid'], m.get('subject_figure')) if m['subject_height_mid'] is not None else None
        m['measured_angle'] = angle_of(m['pitch_down_deg_mid']) if m['pitch_down_deg_mid'] is not None else None
        k, d = m['shot'], by.get(m['shot'])
        lines.append(f"shot {k}: frames {m['frame_start']}-{m['frame_end']} {m['camera']}: move {m['measured_move']}, "
                     f"size {m['measured_size']} ({m['subject_height_mid']}), angle {m['measured_angle']} ({m['pitch_down_deg_mid']}), "
                     f"subject {m['subject']} in frame {m['subject_in_frame']}, largest camera step {m['largest_step']}")
        if not declared:
            continue
        if not d:
            problems.append(f'shot {k}: not in shotlist.json')
            continue
        if (d.get('frame_start'), d.get('frame_end')) != (m['frame_start'], m['frame_end']):
            problems.append(f"shot {k}: frames {d.get('frame_start')}-{d.get('frame_end')} declared, markers give {m['frame_start']}-{m['frame_end']}")
        t0, t1 = (m['frame_start'] - meas['frame_start']) / fps, (m['frame_end'] + 1 - meas['frame_start']) / fps
        if abs((d.get('video_start_s') or 0) - t0) > 0.5 / fps + 1e-6 or abs((d.get('video_end_s') or 0) - t1) > 0.5 / fps + 1e-6:
            problems.append(f'shot {k}: video times should be {t0:.4f} to {t1:.4f} s')
        if d.get('camera') != m['camera']:
            problems.append(f"shot {k}: camera {d.get('camera')} declared, the marker has {m['camera']}")
        if not m['subject_found']:
            problems.append(f"shot {k}: subject {d.get('subject')!r} is not an object of the scene")
        else:
            if set((d.get('camera_move') or '').replace(' ', '').split('+')) != set(m['measured_move'].split('+')):
                problems.append(f"shot {k}: camera_move {d.get('camera_move')!r} declared, measured {m['measured_move']!r}")
            if d.get('shot_size') != m['measured_size']:
                problems.append(f"shot {k}: shot_size {d.get('shot_size')!r} declared, measured {m['measured_size']!r} (subject fills {m['subject_height_mid']} of the frame height)")
            if d.get('camera_angle') != m['measured_angle']:
                problems.append(f"shot {k}: camera_angle {d.get('camera_angle')!r} declared, measured {m['measured_angle']!r} (pitch {m['pitch_down_deg_mid']})")
            if m['subject_in_frame'] < 0.9:
                problems.append(f"shot {k}: subject centre in frame for {m['subject_in_frame']:.0%} of the shot (90 % needed)")
        for ev in d.get('events') or []:
            if names and ev.get('object') not in names:
                problems.append(f"shot {k}: event {ev.get('name')!r} names {ev.get('object')!r}, not an object of the scene")
            if not (m['frame_start'] <= (ev.get('frame') or -1) <= m['frame_end']):
                problems.append(f"shot {k}: event {ev.get('name')!r} at frame {ev.get('frame')} is outside the shot")
    if declared and len(declared) != len(meas['shots']):
        problems.append(f"{len(declared)} shots declared, {len(meas['shots'])} markers with a camera in the scene")
    if meas['shots'] and (meas['shots'][0]['frame_start'] != meas['frame_start']):
        problems.append(f"the first marker is at frame {meas['shots'][0]['frame_start']}, the scene starts at {meas['frame_start']}")
    (work / 'measured.json').write_text(json.dumps(dict(meas, problems=problems), indent=1), encoding='utf-8')
    if '--json' in sys.argv:
        print(json.dumps(dict(meas, problems=problems), indent=1))
    else:
        print('\n'.join(lines))
        print('nothing checked: write shotlist.json from these lines (tools/shots.py <film> --subject <shot>=<object> measures a subject)' if not declared else
              ('SHOT FACTS HOLD' if not problems else f'SHOT FACTS: {len(problems)} problem(s)\n  ' + '\n  '.join(problems)))
    sys.exit(2 if problems else 0)


if __name__ == '__main__':
    main()
