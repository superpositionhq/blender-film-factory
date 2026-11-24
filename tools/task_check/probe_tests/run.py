#!/usr/bin/env python3
"""The checker's own test on a real Blender: build the test scenes, prove the test task, grade six scenes.

  python tools/task_check/probe_tests/run.py [<work dir>]

Passes when the task is VALID and each scene gets the reward and the solved flag written below. Needs Blender.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from task_check import check, tasks  # noqa: E402

# scene: (reward, solved, judge answer). The positive weights add up to 56.
EXPECT = {
    'reference': (1.0, True, 1),
    'start': (0.0, False, 0),
    'half': (0.2455, False, 0.25),        # the cup stands on a saucer (10 + 3) and the judge gives 0.25 of 3: 13.75 / 56
    'broke_lamp': (0.875, False, 1),      # everything right, minus 7 for the lamp: 49 / 56
    'renamed': (1.0, True, 1),            # another camera, light and material name: a second solution earns the same
    'empty': (0.0, False, 0),             # the scene deleted: nothing to measure, and nothing earned for that
}


def main():
    work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix='task-check-'))
    scenes, task_dir = work / 'scenes', work / 'task'
    if work.exists():
        shutil.rmtree(work)
    task_dir.mkdir(parents=True)
    exe = check.bffroot.blender()
    r = subprocess.run([exe, '-b', '--factory-startup', '--python', str(HERE / 'build_scenes.py'), '--', str(scenes)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    missing = [n for n in EXPECT if not (scenes / f'{n}.blend').is_file()]
    if missing:
        sys.exit(f'scenes not built: {missing}\n' + (r.stdout + r.stderr)[-1500:])
    for n in ('start', 'reference'):
        shutil.copy2(scenes / f'{n}.blend', task_dir / f'{n}.blend')
    shutil.copy2(HERE / 'task.json', task_dir / 'task.json')
    task = tasks.load(task_dir)
    result = check.check(task, json.loads((HERE / 'answers.json').read_text(encoding='utf-8')))
    failures = []
    if result['verdict'] != 'VALID':
        failures.append(f"task verdict {result['verdict']}: {result['errors']}")
    else:
        for name, (want, solved, answer) in EXPECT.items():
            g = check.grade(task, scenes / f'{name}.blend', work / 'grades' / name, {'R10': answer})
            ok = abs(g['reward'] - want) < 0.005 and g['solved'] == solved
            print(f"{'ok  ' if ok else 'FAIL'} {name}: reward {g['reward']} solved {g['solved']} (want {want}, {solved})")
            if not ok:
                failures.append(f"{name}: " + ', '.join(f"{i['id']}={i['hit']}" for i in g['items']))
    for f in failures:
        print('FAIL', f)
    print('PROBE TESTS PASS' if not failures else f'PROBE TESTS: {len(failures)} failure(s)', '-', work)
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
