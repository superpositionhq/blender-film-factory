#!/usr/bin/env python3
"""Validate a film repo against the film format (docs/film-format.md).

    python tools/validate-film.py <films>/<slug> [--release] [--json <file>] [--quiet]

Checks, each ERROR (the film is INVALID) or WARN:
  files      film.json, Brief.md, Docs/Breakdown.md, Docs/Treatment.md, build/kit.py, build/order.txt, workflow.jsonl, steps/
  steps      every step folder is whole (script, result, state; a picture once there is a camera); every script of
             build/order.txt exists; the scene was only changed through steps
  workflow   rows parse, ids and seq run on without gaps, one row per step
  scene      (from the newest step's state) film format as in film.json, one camera per shot bound to a marker, no
             default-file leftovers, every mesh has a material, nothing linked or loaded from outside the film
  fidelity   counts of the scene against what a film of that output usually has (warnings only: a person judges
             the picture, tools/review.py)
  trajectory (--release) the recorded session: a note and a look at a picture before 90 % of the steps, every
             opened picture still there, no name or address that must not ship (tools/trajectory.py)
  names      banned names and machine paths in tracked text files and commit messages
  history    commits, one per step; WIP commits; steps batched or missing
  release    (--release) out/film.mp4 and out/animatic_clay.mp4 (codec, size, frame rate, length, the same frame
             count, no dead frames), out/contact_sheet.png, out/scene.blend, shotlist.json (tools/shots.py),
             Docs/Critique.md, Docs/Report.md, for a final film out/greybox.mp4, for a storyboard input its pages
Exit code 0 VALID, 2 INVALID. Python 3.9+ standard library only; ffprobe/ffmpeg and Blender only for --release.
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

FLOORS = {
    'final': dict(tris=300000, meshes=40, materials=12, rich_share=0.6, lights=3, animated=5, dof=1, critique_rounds=2),
    'greybox': dict(tris=0, meshes=5, materials=2, rich_share=0.0, lights=0, animated=1, dof=0, critique_rounds=1),
}
TEXT = {'.py', '.md', '.json', '.jsonl', '.txt', '.log', '.gitignore', '.gitattributes'}


class Report:
    def __init__(self):
        self.errors, self.warns, self.info = [], [], {}

    def error(self, area, msg):
        self.errors.append(f'[{area}] {msg}')

    def warn(self, area, msg):
        self.warns.append(f'[{area}] {msg}')


def git(film, *args):
    return subprocess.run(['git', '-C', str(film), '-c', 'core.quotepath=off', *args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace').stdout


def probe(path):
    fp = bffroot.ffmpeg('ffprobe')
    if not fp:
        return None
    r = subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries',
                        'stream=codec_name,width,height,r_frame_rate,nb_read_frames', '-of', 'json', str(path)], capture_output=True, text=True)
    try:
        s = json.loads(r.stdout)['streams'][0]
        n, d = s['r_frame_rate'].split('/')
        return dict(codec=s['codec_name'], width=s['width'], height=s['height'], fps=float(n) / float(d), frames=int(s['nb_read_frames']))
    except Exception:
        return None


def dead_frames(path):
    ff = bffroot.ffmpeg()
    r = subprocess.run([ff, '-hide_banner', '-i', str(path), '-vf', "select='not(mod(n\\,6))',signalstats,metadata=print:file=-", '-an', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    lo = [float(x) for x in re.findall(r'signalstats\.YMIN=([\d.]+)', r.stdout)]
    hi = [float(x) for x in re.findall(r'signalstats\.YMAX=([\d.]+)', r.stdout)]
    return [i * 6 for i, (a, b) in enumerate(zip(lo, hi)) if b - a < 12]


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('--release', action='store_true')
    p.add_argument('--json')
    p.add_argument('--quiet', action='store_true')
    p.add_argument('--scratch', help='directory for temporary release checks')
    a = p.parse_args()
    film, rep = Path(a.film).resolve(), Report()

    # files
    for f in ('film.json', 'Brief.md', 'Docs/Breakdown.md', 'Docs/Treatment.md', 'build/kit.py', 'build/order.txt', 'workflow.jsonl'):
        if not (film / f).is_file():
            rep.error('files', f'{f} is missing')
    try:
        meta = json.loads((film / 'film.json').read_text(encoding='utf-8'))
    except Exception as e:
        print(f'INVALID: film.json cannot be read ({e})')
        sys.exit(2)
    mode, fmt = meta.get('output'), meta.get('format', {})
    floors = FLOORS.get(mode)
    if not floors or meta.get('input') not in ('script', 'storyboard'):
        rep.error('files', 'film.json: input must be script or storyboard, output final or greybox')
        floors = FLOORS['final']
    for f, marker in (('Brief.md', '<!-- The first commit'), ('Docs/Breakdown.md', '<!-- Written from the script'),
                      ('Docs/Treatment.md', '<!-- Written and committed')):
        if (film / f).is_file() and marker in (film / f).read_text(encoding='utf-8'):
            rep.error('files', f'{f} is still the template: write it before the first step')

    # steps
    steps = sorted(d for d in (film / 'steps').iterdir() if re.match(r'\d{4}-', d.name)) if (film / 'steps').is_dir() else []
    ok_steps, state, pics, with_cam = [], None, 0, 0
    for i, d in enumerate(steps, 1):
        if int(d.name[:4]) != i:
            rep.error('steps', f'{d.name}: step numbers must run 0001, 0002, ... without gaps')
        for f in ('script.py', 'result.json', 'stdout.log'):
            if not (d / f).is_file():
                rep.error('steps', f'{d.name}/{f} is missing')
        res = json.loads((d / 'result.json').read_text(encoding='utf-8')) if (d / 'result.json').is_file() else {}
        if res.get('ok'):
            ok_steps.append(d)
            if not (d / 'state.json').is_file():
                rep.error('steps', f'{d.name}/state.json is missing')
            else:
                state = json.loads((d / 'state.json').read_text(encoding='utf-8'))
                if state.get('active_camera'):
                    with_cam += 1
                    pics += (d / 'preview.png').is_file()
    if with_cam and pics / with_cam < 0.9:
        rep.error('steps', f'only {pics} of {with_cam} steps with a camera have a picture (90 % needed): --no-preview is for steps nothing can be seen of')
    order = (film / 'build' / 'order.txt').read_text(encoding='utf-8').split() if (film / 'build' / 'order.txt').is_file() else []
    for rel in order:
        if not (film / rel).is_file():
            rep.error('steps', f'build/order.txt names {rel}, which is not there')
    if len(set(order)) != len(order):
        rep.error('steps', 'build/order.txt lists a script twice')
    rep.info.update(steps=len(steps), ok_steps=len(ok_steps), failed_steps=len(steps) - len(ok_steps))

    # workflow
    rows = []
    for n, line in enumerate((film / 'workflow.jsonl').read_text(encoding='utf-8').splitlines() if (film / 'workflow.jsonl').is_file() else [], 1):
        try:
            rows.append(json.loads(line))
        except ValueError:
            rep.error('workflow', f'line {n} is not JSON')
    if [r.get('seq') for r in rows] != list(range(1, len(rows) + 1)):
        rep.error('workflow', 'seq does not run 1, 2, 3, ... (rows edited, removed or reordered)')
    step_rows = {r.get('params', {}).get('step') for r in rows}
    missing = [d.name for d in steps if d.name not in step_rows]
    if missing:
        rep.error('workflow', f'{len(missing)} step(s) without a row (run steps with tools/step.py only): {", ".join(missing[:5])}')
    rep.info.update(rows=len(rows), critique_issues=sum(r.get('op') == 'critique.issue' for r in rows),
                    critique_fixes=sum(r.get('op') == 'critique.fix' for r in rows),
                    directions=sum(r.get('op') == 'user.direction' for r in rows))

    # scene
    if state:
        if state['resolution'] != [fmt.get('width'), fmt.get('height')] or abs(state['fps'] - fmt.get('fps', 24)) > 1e-6:
            rep.error('scene', f'the scene is {state["resolution"]} at {state["fps"]} fps; film.json says {fmt.get("width")}x{fmt.get("height")} at {fmt.get("fps")}')
        shots = [m for m in state['markers'] if m['camera']]
        cams = [m['camera'] for m in shots]
        late = rep.error if a.release else rep.warn      # the film grows into its length and shot count
        if len(shots) < fmt.get('min_shots', 1):
            late('scene', f'{len(shots)} shots (markers with a camera); film.json asks for at least {fmt.get("min_shots")}')
        if len(set(cams)) != len(cams):
            rep.error('scene', 'two shots share one camera: every shot has its own camera object')
        if shots and shots[0]['frame'] != state['frame_start']:
            rep.error('scene', f'the first shot starts at frame {shots[0]["frame"]}, the scene at {state["frame_start"]}')
        secs = (state['frame_end'] - state['frame_start'] + 1) / state['fps']
        if not fmt.get('min_seconds', 0) <= secs <= fmt.get('max_seconds', 1e9):
            late('scene', f'the film is {secs:.2f} s long; film.json asks for {fmt.get("min_seconds")} to {fmt.get("max_seconds")} s')
        objs = state['objects']
        for o in objs:
            if o['name'] in ('Cube', 'Light', 'Camera') or re.fullmatch(r'(Cube|Sphere|Cylinder|Plane|Cone|Torus|Icosphere|Suzanne|Empty|Light|Camera|Point|Sun|Area|Spot|BezierCurve)(\.\d{3})?', o['name']):
                rep.error('scene', f'object "{o["name"]}" has a default name: name every object for what it is')
            elif re.search(r'\.\d{3}$', o['name']):
                rep.warn('scene', f'object "{o["name"]}" carries a duplicate suffix')
            if o['type'] == 'MESH' and not o['hide_render'] and not o['materials'] and o.get('tris'):
                rep.error('scene', f'mesh "{o["name"]}" has no material')
        if state.get('libraries'):
            rep.error('scene', f'linked libraries: {state["libraries"]}')
        for im in state.get('images', []):
            fpth = im['filepath']
            if fpth and not im['packed'] and not fpth.startswith('//'):
                rep.error('scene', f'image "{im["name"]}" is loaded from outside the film ({Path(fpth).name}): generate it into the film and load it as //textures/...')
        used = {m for o in objs for m in o['materials']}
        rich = [m for m in state['materials'] if m['name'] in used and m['nodes'] >= 6]
        c = state['counts']
        fid = dict(tris=c['tris'], meshes=c['meshes'], materials=len(used), rich_share=round(len(rich) / len(used), 2) if used else 0,
                   lights=c['lights'], animated=sum(o['animated'] for o in objs if o['type'] != 'CAMERA'),
                   dof=sum(1 for o in objs if o['type'] == 'CAMERA' and o.get('dof')), shots=len(shots), seconds=round(secs, 2))
        rep.info['fidelity'] = fid
        for k in ('tris', 'meshes', 'materials', 'rich_share', 'lights', 'animated', 'dof'):
            if fid[k] < floors[k]:
                rep.warn('fidelity', f'{k} = {fid[k]}; a {mode} film usually has {floors[k]} or more')
    else:
        rep.warn('scene', 'no successful step yet')

    # names
    home = Path.home().name
    tracked = [f for f in git(film, 'ls-files').splitlines() if Path(f).suffix.lower() in TEXT or Path(f).name in TEXT]
    for f in tracked:
        try:
            text = (film / f).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        bad = bffroot.banned_in(text)
        if len(home) >= 4 and re.search(r'(?i)(?:/Users/|/home/|\\Users\\)' + re.escape(home), text):
            bad.append('a machine path with the account name')
        if bad:
            rep.error('names', f'{f}: {", ".join(sorted(set(bad)))}')
    log = git(film, 'log', '--format=%H%x00%s%x00%b%x01')
    commits = [c.strip().split('\0') for c in log.split('\x01') if c.strip()]
    for c in commits:
        bad = bffroot.banned_in(' '.join(c[1:]))
        if bad or re.search(r'(?i)co-authored-by|generated with', ' '.join(c[1:])):
            rep.error('names', f'commit {c[0][:7]}: {", ".join(bad) or "an attribution trailer"} in the message')

    # history
    step_commits = {m for c in commits for m in re.findall(r'(?m)^step: (\d{4}-\S+)', c[2] if len(c) > 2 else '')}
    wip = sum(1 for c in commits if c[1] == 'WIP')
    unc = [d.name for d in steps if d.name not in step_commits]
    if unc:
        rep.error('history', f'{len(unc)} step(s) without their own commit: {", ".join(unc[:5])}')
    if wip:
        rep.warn('history', f'{wip} WIP commit(s): the turn ended with uncommitted work')
    if git(film, 'status', '--porcelain').strip():
        rep.warn('history', 'uncommitted changes in the film repo')
    rep.info.update(commits=len(commits), wip_commits=wip)

    # release
    if a.release:
        out = film / 'out'
        fp = probe(out / 'film.mp4') if (out / 'film.mp4').is_file() else None
        if not fp:
            rep.error('release', 'out/film.mp4 is missing or cannot be read (ffprobe)')
        elif state:
            want = state['frame_end'] - state['frame_start'] + 1
            if fp['codec'] != 'h264' or [fp['width'], fp['height']] != state['resolution'] or abs(fp['fps'] - state['fps']) > 1e-3:
                rep.error('release', f'out/film.mp4 is {fp["codec"]} {fp["width"]}x{fp["height"]} at {fp["fps"]:g} fps; it must be h264 at the scene format')
            if fp['frames'] != want:
                rep.error('release', f'out/film.mp4 has {fp["frames"]} frames, the scene {want}')
            dead = dead_frames(out / 'film.mp4')
            if dead:
                rep.error('release', f'out/film.mp4: {len(dead)} near-uniform frame(s), first at frame {dead[0]}')
        cp = probe(out / 'animatic_clay.mp4') if (out / 'animatic_clay.mp4').is_file() else None
        if not cp:
            rep.error('release', 'out/animatic_clay.mp4 is missing or cannot be read')
        elif fp and (cp['frames'] != fp['frames'] or abs(cp['fps'] - fp['fps']) > 1e-3):
            rep.error('release', f'out/animatic_clay.mp4 has {cp["frames"]} frames at {cp["fps"]:g} fps; the film has {fp["frames"]} at {fp["fps"]:g}')
        need = ['out/contact_sheet.png', 'out/scene.blend', 'Docs/Critique.md', 'Docs/Report.md', 'shotlist.json']
        if meta.get('input') == 'storyboard':
            need += ['storyboard/storyboard.json']
        if mode == 'final':
            need += ['out/greybox.mp4']
        for f in need:
            if not (film / f).is_file():
                rep.error('release', f'{f} is missing')
        crit = (film / 'Docs' / 'Critique.md').read_text(encoding='utf-8') if (film / 'Docs' / 'Critique.md').is_file() else ''
        rounds = len(re.findall(r'(?m)^## Round', crit))
        if rounds < floors['critique_rounds']:
            rep.error('release', f'Docs/Critique.md has {rounds} round(s) ("## Round ..."); a {mode} film needs {floors["critique_rounds"]}')
        r = subprocess.run([sys.executable, str(REPO / 'tools' / 'shots.py'), str(film), '--json', *(['--work-dir', str(Path(a.scratch) / 'shots')] if a.scratch else [])], capture_output=True, text=True)
        try:
            for pr in json.loads(r.stdout)['problems']:
                rep.error('shots', pr)
        except Exception:
            rep.error('shots', 'tools/shots.py could not measure the scene: ' + (r.stderr or r.stdout)[-200:])
        r = subprocess.run([sys.executable, str(REPO / 'tools' / 'trajectory.py'), str(film), '--json', *(['--out', str(Path(a.scratch) / 'trajectory')] if a.scratch else [])], capture_output=True, text=True)
        try:
            t = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            t = dict(ok=False, error='tools/trajectory.py failed: ' + (r.stderr or r.stdout)[-200:])
        rep.info['trajectory'] = {k: t.get(k) for k in ('events', 'step_calls', 'note_coverage', 'reply_coverage', 'looked_coverage', 'pictures_missing', 'leak_events', 'secrets_redacted')}
        if not t.get('ok'):
            rep.warn('trajectory', t.get('error', 'no recording'))
        else:
            if t['step_calls'] and t['note_coverage'] < 0.9:
                rep.error('trajectory', f"a note before only {t['note_coverage']:.0%} of the steps (90 % needed): no reply and no saved reasoning summary before the others: say what the picture shows and what comes next before every step, and check that reasoning summaries are on (machine/check.py)")
            if t['step_calls'] and t['looked_coverage'] < 0.9:
                rep.error('trajectory', f"a picture was opened before only {t['looked_coverage']:.0%} of the steps (90 % needed)")
            if t['pictures_missing']:
                rep.error('trajectory', f"{t['pictures_missing']} picture(s) the session opened are gone (they are part of the record: never delete .local/render before release)")
            if t['leak_events']:
                rep.error('trajectory', f"{t['leak_events']} event(s) of the recording hold a name, address or secret that must not ship (tools/trajectory.py lists them)")
            if t.get('secrets_redacted'):
                rep.warn('trajectory', f"{t['secrets_redacted']} event(s) of the recording held a secret (redacted in the export; analysis.json lists them): the session saw it, so rotate it")
        rj = film / '.local' / 'replay' / 'result.json'
        if not rj.is_file() or not json.loads(rj.read_text(encoding='utf-8')).get('ok'):
            rep.error('release', 'no passing replay: run tools/replay.py (it must say REPLAY OK)')

    result = dict(film=film.name, valid=not rep.errors, errors=rep.errors, warnings=rep.warns, info=rep.info)
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1), encoding='utf-8')
    if not a.quiet:
        for e in rep.errors:
            print('ERROR', e)
        for w in rep.warns:
            print('WARN ', w)
        i = rep.info
        print(f"history: {i.get('commits')} commits, {i.get('ok_steps')} steps ({i.get('failed_steps')} failed), {i.get('rows')} rows, "
              f"{i.get('critique_issues')} critique issues / {i.get('critique_fixes')} fixes, {i.get('wip_commits')} WIP")
        if 'fidelity' in i:
            print('scene:   ' + ', '.join(f'{k} {v}' for k, v in i['fidelity'].items()))
        if 'trajectory' in i:
            print('record:  ' + ', '.join(f'{k} {v}' for k, v in i['trajectory'].items()))
    print(('VALID' if not rep.errors else f'INVALID ({len(rep.errors)} error(s))') + (' for release' if a.release else ''))
    sys.exit(0 if not rep.errors else 2)


if __name__ == '__main__':
    main()
