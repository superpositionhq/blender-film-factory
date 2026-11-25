"""Measure a scene for a task and score it. The start and the reference are measured to prove the task; a
candidate scene is measured the same way and gets a reward."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import judge, tasks, verdict

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402

PROBE = REPO / 'tools' / 'blender' / 'task_probe.py'
RESULT_SCHEMA = 'film-task-check/1'
REDUCER_KEYS = ('field', 'agg', 'where', 'abs')


def plan(task, with_shots=True):
    """The probe's work for one scene: a query per measured item, a picture per judge shot."""
    queries, shots = [], []
    for i in task['items']:
        if 'measure' in i:
            queries.append({'id': i['id'], **{k: v for k, v in i['measure'].items() if k not in REDUCER_KEYS}})
        elif with_shots:
            for n, s in enumerate(i['judge']['shots'], 1):
                shots.append({'id': f"{i['id']}_{n}", **s})
    if with_shots:                              # one picture of the scene for the reviewer's card
        shots.append({'id': 'card', 'width': 960, **(task.get('card') or {})})
    return queries, shots


def measure(blend, task, work, exclude, with_shots=True):
    """Run the probe on one .blend. Returns its output with 'values': one reduced value per measured item."""
    exe = bffroot.blender()
    if not exe:
        raise SystemExit('Blender not found (machine/bootstrap.py)')
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    queries, shots = plan(task, with_shots)
    (work / 'queries.json').write_text(json.dumps({'exclude': exclude, 'queries': queries, 'shots': shots}, indent=1), encoding='utf-8')
    r = subprocess.run([exe, '-b', str(blend), '--python', str(PROBE), '--', str(work / 'queries.json'),
                        str(work / 'probe.json'), str(work)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    (work / 'blender.log').write_text((r.stdout or '') + (r.stderr or ''), encoding='utf-8')
    if not (work / 'probe.json').is_file():
        raise SystemExit(f'the probe did not finish on {blend}:\n' + ((r.stdout or '') + (r.stderr or ''))[-1500:])
    out = json.loads((work / 'probe.json').read_text(encoding='utf-8'))
    out['values'] = {}
    for i in task['items']:
        if 'measure' in i and i['id'] not in out['errors']:
            out['values'][i['id']] = verdict.reduce_rows(out['rows'].get(i['id']), i['measure'])
    return out


def score(task, probe, start_values, ref_values, answers=None):
    scored = {}
    for i in task['items']:
        iid = i['id']
        if iid in probe['errors']:
            scored[iid] = dict(value=None, hit=None, threshold=None, problem='probe error: ' + probe['errors'][iid])
            continue
        scored[iid] = verdict.score_item(i, probe['values'].get(iid), start_values.get(iid), ref_values.get(iid),
                                         (answers or {}).get(iid))
    return scored


def check(task, answers=None):
    """Prove a task on its own two snapshots. Returns the result (also written to <task>/check/result.json)."""
    d = task['_dir']
    start_blend, ref_blend = d / 'start.blend', d / 'reference.blend'
    errors, warnings = tasks.validate(task)
    for p in (start_blend, ref_blend):
        if not p.is_file():
            errors.append(f'{p.name} is missing')
    result = dict(schema=RESULT_SCHEMA, task=task.get('name'), verdict='INVALID', errors=errors, warnings=warnings, items=[])
    if errors:
        return result
    work = d / 'check'
    start = measure(start_blend, task, work / 'start', 'self')
    ref = measure(ref_blend, task, work / 'reference', start['objects'])
    errors += tasks.second_solution(task, set(start['objects']))
    answers = dict(answers or {})
    reasons = {}
    answers['start'], reasons['start'] = judge.ask(task, work / 'start', start['shots'], answers.get('start'))
    answers['reference'], reasons['reference'] = judge.ask(task, work / 'reference', ref['shots'], answers.get('reference'))
    s_sc = score(task, start, start['values'], ref['values'], answers.get('start'))
    r_sc = score(task, ref, start['values'], ref['values'], answers.get('reference'))
    errors += verdict.validity(task['items'], s_sc, r_sc)
    s_reward, _, s_pending = verdict.reward(task['items'], s_sc)
    r_reward, r_solved, r_pending = verdict.reward(task['items'], r_sc)
    judged = not (s_pending or r_pending)
    if judged and s_reward != 0.0:
        errors.append(f'the untouched start scores {s_reward}, not 0')
    if judged and not r_solved:
        errors.append('the reference does not solve the task')
    for i in task['items']:
        result['items'].append(dict(id=i['id'], weight=i['weight'], start=s_sc[i['id']], reference=r_sc[i['id']]))
    result.update(blender=ref['blender'], start_reward=s_reward, reference_reward=r_reward, start_objects=start['objects'],
                  start_values=start['values'], reference_values=ref['values'],
                  shots=dict(start=start['shots'], reference=ref['shots']), judge_reasons=reasons,
                  pending_judge=sorted(set(s_pending + r_pending)),
                  verdict='VALID' if not errors and judged else 'NEEDS JUDGE' if not errors else 'INVALID')
    (work / 'result.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    return result


def grade(task, blend, out_dir, answers=None):
    """Score a candidate scene. Writes grade.json always, and reward.json once nothing waits for a judge."""
    d = task['_dir']
    saved = d / 'check' / 'result.json'
    if not saved.is_file():
        raise SystemExit('check the task first: grading uses the start and reference measurements')
    base = json.loads(saved.read_text(encoding='utf-8'))
    if base['verdict'] == 'INVALID':
        raise SystemExit('the task is INVALID: it cannot grade anything')
    out_dir = Path(out_dir)
    cand = measure(blend, task, out_dir / 'candidate', base['start_objects'])
    answers, reasons = judge.ask(task, out_dir / 'candidate', cand['shots'], answers)
    sc = score(task, cand, base['start_values'], base['reference_values'], answers)
    reward, solved, pending = verdict.reward(task['items'], sc)
    detail = dict(schema='film-task-grade/1', task=task['name'], reward=reward, solved=solved, pending_judge=pending,
                  items=[dict(id=i['id'], weight=i['weight'], **sc[i['id']]) for i in task['items']], shots=cand['shots'],
                  judge_reasons=reasons)
    (out_dir / 'grade.json').write_text(json.dumps(detail, indent=1), encoding='utf-8')
    if not pending:
        (out_dir / 'reward.json').write_text(json.dumps({'reward': reward}), encoding='utf-8')
    return detail
