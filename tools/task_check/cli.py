"""Command line of the task checker.

  python tools/task-check.py validate <task>                 read the task file and list what is wrong with it
  python tools/task-check.py check <task> [--answers f.json] measure start.blend and reference.blend, prove the task,
                                                             write <task>/check/result.json and <task>/CARD.md
  python tools/task-check.py card <task>                     write CARD.md again from the last result
  python tools/task-check.py grade <task> <scene.blend> --out <dir> [--answers f.json]
                                                             score another scene: <dir>/grade.json and, once every
                                                             judge item is answered, <dir>/reward.json {"reward": 0..1}
  python tools/task-check.py snapshot <film> <task name> --start <step> --reference <step>
                                                             copy the two step checkpoints into <film>/Tasks/<name>/
                                                             as self-contained start.blend and reference.blend
  python tools/task-check.py split <task> --out <dir>        the solver's half (task.json without items, start.blend)

<task> is a folder holding task.json, start.blend and reference.blend. A judge item is answered by a file:
check takes {"start": {"R05": 0}, "reference": {"R05": 1}}, grade takes {"R05": 0.75}.
Exit code 0 for VALID / graded, 2 for INVALID, 3 when a judge still has to answer.
Python 3.9+ standard library only; needs Blender. docs/task-check.md.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import card, check, tasks


def opt(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if path else None


def write_card(task, result):
    (task['_dir'] / 'CARD.md').write_text(card.render(task, result), encoding='utf-8')


def snapshot(film, name, start, reference):
    film = Path(film).resolve()
    exe = check.bffroot.blender()
    out = film / 'Tasks' / name
    out.mkdir(parents=True, exist_ok=True)
    for label, step in (('start', start), ('reference', reference)):
        hits = sorted((film / '.local' / 'checkpoints').glob(f'{int(step):04d}-*.blend'))
        if not hits:
            sys.exit(f'no checkpoint for step {step} in {film / ".local" / "checkpoints"} (tools/replay.py --keep rebuilds them)')
        dest = out / f'{label}.blend'
        expr = ('import bpy\n'
                'try:\n bpy.ops.file.pack_all()\nexcept Exception as e:\n print("pack:", e)\n'
                f'bpy.ops.wm.save_as_mainfile(filepath={str(dest)!r}, copy=True, compress=True, relative_remap=True)\n')
        r = subprocess.run([exe, '-b', str(hits[0]), '--python-expr', expr], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', cwd=str(film))
        if not dest.is_file():
            sys.exit(f'could not write {dest}:\n' + (r.stdout + r.stderr)[-800:])
        print(f'{label}: step {int(step):04d} -> {dest}')


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == 'snapshot':
        snapshot(args[1], args[2], opt(args, '--start'), opt(args, '--reference'))
        return 0
    task = tasks.load(args[1])
    if cmd == 'validate':
        err, warn = tasks.validate(task)
        for w in warn:
            print('warning:', w)
        for e in err:
            print('error:', e)
        print('TASK FILE OK' if not err else f'TASK FILE: {len(err)} error(s)')
        return 2 if err else 0
    if cmd == 'check':
        result = check.check(task, read_json(opt(args, '--answers')))
        write_card(task, result)
        for w in result['warnings']:
            print('warning:', w)
        for e in result['errors']:
            print('problem:', e)
        for r in result['items']:
            print(f"  {r['id']} ({r['weight']:+d}): start {card.show(r['start']['value'])} ({card.mark(r['start'], r['weight'])}), "
                  f"reference {card.show(r['reference']['value'])} ({card.mark(r['reference'], r['weight'])})")
        if result.get('pending_judge'):
            print('waiting for a judge:', ', '.join(result['pending_judge']), '(pictures in check/start and check/reference)')
        print(result['verdict'], f"- card: {task['_dir'] / 'CARD.md'}")
        return {'VALID': 0, 'NEEDS JUDGE': 3}.get(result['verdict'], 2)
    if cmd == 'card':
        saved = task['_dir'] / 'check' / 'result.json'
        write_card(task, read_json(saved) if saved.is_file() else None)
        print(task['_dir'] / 'CARD.md')
        return 0
    if cmd == 'grade':
        out = opt(args, '--out')
        if not out or len(args) < 3:
            sys.exit(__doc__)
        g = check.grade(task, Path(args[2]).resolve(), Path(out).resolve(), read_json(opt(args, '--answers')))
        for i in g['items']:
            print(f"  {i['id']} ({i['weight']:+d}): {card.show(i['value'])} ({card.mark(i, i['weight'])})")
        print(f"reward {g['reward']}" + (' SOLVED' if g['solved'] else '') +
              (f" (provisional: waiting for a judge on {', '.join(g['pending_judge'])})" if g['pending_judge'] else ''))
        return 3 if g['pending_judge'] else 0
    if cmd == 'split':
        out = Path(opt(args, '--out')).resolve()
        out.mkdir(parents=True, exist_ok=True)
        (out / 'task.json').write_text(json.dumps(tasks.public_half(task), indent=1, ensure_ascii=False), encoding='utf-8')
        shutil.copy2(task['_dir'] / 'start.blend', out / 'start.blend')
        print(out)
        return 0
    sys.exit(__doc__)
