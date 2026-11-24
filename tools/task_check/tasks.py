"""Read a task and say what is wrong with it before anything runs. docs/task-format.md has the format."""
import json
import re
from pathlib import Path

from . import verdict

SCHEMA = 'film-task/1'
PHASES = ('layout', 'look', 'motion_light', 'final')
KINDS = ('correction', 'bug_fix', 'feature', 'change')
DIMENSIONS = ('completeness', 'requirement_alignment', 'staging', 'modelling', 'materials', 'lighting', 'motion',
              'render_quality', 'engineering')
PROBES = ('object', 'material', 'light', 'world', 'render', 'shots', 'framing', 'motion', 'contact', 'file', 'screen')
AGGS = ('first', 'last', 'count', 'any', 'all', 'share', 'distinct', 'min', 'max', 'sum', 'mean', 'median', 'range', 'delta')
SELECTOR_KEYS = ('select', 'a', 'b')


def load(path):
    path = Path(path)
    if path.is_dir():
        path = path / 'task.json'
    task = json.loads(path.read_text(encoding='utf-8'))
    task['_dir'] = path.parent
    return task


def selector_names(item):
    """Object names an item's measure or judge picks by name: the ones the second-solution rule is about."""
    names = []
    m = item.get('measure') or {}
    for key in SELECTOR_KEYS:
        sel = m.get(key)
        if isinstance(sel, str):
            names.append(sel)
        elif isinstance(sel, dict) and 'name' in sel:
            names += sel['name'] if isinstance(sel['name'], list) else [sel['name']]
    for holder in [m] + list((item.get('judge') or {}).get('shots') or []):
        if isinstance(holder.get('camera'), str):
            names.append(holder['camera'])
        if isinstance(holder.get('at'), str):
            names.append(holder['at'])
    return names


def validate(task):
    """(errors, warnings) from the task file alone."""
    err, warn = [], []
    if task.get('schema') != SCHEMA:
        err.append(f'schema must be {SCHEMA!r}')
    for key in ('name', 'title', 'instruction'):
        if not str(task.get(key) or '').strip():
            err.append(f'{key} is missing')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,60}', str(task.get('name') or '')):
        err.append('name: lower-case letters, digits and hyphens, 3 to 61 characters')
    if task.get('phase') not in PHASES:
        err.append(f'phase must be one of {", ".join(PHASES)}')
    if task.get('kind') not in KINDS:
        err.append(f'kind must be one of {", ".join(KINDS)}')
    seed = task.get('seed') or {}
    for key in ('start', 'reference'):
        if not seed.get(key):
            err.append(f'seed.{key} (the step the snapshot was taken at) is missing')
    items = task.get('items') or []
    ids = [i.get('id') for i in items]
    if len(set(ids)) != len(ids):
        err.append('item ids repeat')
    for n, i in enumerate(items, 1):
        tag = i.get('id') or f'item {n}'
        if not re.fullmatch(r'R\d{2,}', str(i.get('id') or '')):
            err.append(f'{tag}: id is R01, R02, ...')
        if len(str(i.get('description') or '')) < 15:
            err.append(f'{tag}: description says in a sentence what is judged')
        if i.get('dimension') not in DIMENSIONS:
            err.append(f'{tag}: dimension must be one of {", ".join(DIMENSIONS)}')
        if i.get('criterion_type') not in ('Objective', 'Subjective'):
            err.append(f'{tag}: criterion_type is Objective or Subjective')
        if i.get('criterion_necessity') not in ('Explicit', 'Implicit'):
            err.append(f'{tag}: criterion_necessity is Explicit or Implicit')
        if i.get('type') not in ('binary', 'gradient'):
            err.append(f'{tag}: type is binary or gradient')
        if i.get('weight') not in verdict.WEIGHTS:
            err.append(f'{tag}: weight is one of {verdict.WEIGHTS}')
        has_measure, has_judge = 'measure' in i, 'judge' in i
        if has_measure == has_judge:
            err.append(f'{tag}: exactly one of measure (with expect) or judge')
            continue
        if has_judge:
            j = i['judge']
            if i.get('criterion_type') != 'Subjective':
                err.append(f'{tag}: a judge item is Subjective')
            if not j.get('shots'):
                err.append(f'{tag}: judge.shots names at least one frame to render')
            if len(str(j.get('question') or '')) < 15:
                err.append(f'{tag}: judge.question is one question a picture can answer')
            if i.get('type') == 'gradient' and sorted((j.get('levels') or {}).keys()) != ['0', '0.25', '0.5', '0.75', '1']:
                err.append(f'{tag}: a gradient judge item describes the five levels "1", "0.75", "0.5", "0.25", "0"')
            if i.get('weight', 0) >= 10:
                warn.append(f'{tag}: a +10 item decided by a judge; prefer a measurement for what decides the task')
            continue
        m, e = i['measure'], i.get('expect') or {}
        if i.get('criterion_type') != 'Objective':
            err.append(f'{tag}: a measured item is Objective')
        if m.get('probe') not in PROBES:
            err.append(f'{tag}: measure.probe must be one of {", ".join(PROBES)}')
        if m.get('agg', 'first') not in AGGS:
            err.append(f'{tag}: measure.agg must be one of {", ".join(AGGS)}')
        if m.get('agg') != 'count' and 'field' not in m:
            err.append(f'{tag}: measure.field is missing')
        if 'gradient' in e:
            if i.get('type') != 'gradient':
                err.append(f'{tag}: expect.gradient belongs to a gradient item')
        else:
            if i.get('type') == 'gradient':
                err.append(f'{tag}: a gradient item needs expect.gradient')
            if e.get('op') not in verdict.OPS:
                err.append(f'{tag}: expect.op must be one of {", ".join(verdict.OPS)}')
            elif e['op'] not in ('true', 'false', 'changed', 'unchanged') and not any(
                    k in e for k in ('value', 'calibrate', 'start_plus', 'start_times')):
                err.append(f'{tag}: expect needs value, calibrate, start_plus or start_times')
        if m.get('probe') == 'screen' and 'value' in e and e.get('op') not in ('true', 'false'):
            warn.append(f'{tag}: a brightness threshold as a literal; calibrate it or make it relative to the start')
    pos = [i for i in items if isinstance(i.get('weight'), int) and i['weight'] > 0]
    neg = [i for i in items if isinstance(i.get('weight'), int) and i['weight'] < 0]
    if sum(1 for i in pos if i['weight'] == 10) < 2:
        err.append('at least 2 items of weight +10 (what decides whether the task is done)')
    if not neg:
        err.append('at least 1 negative item (an error that would spoil the result, such as breaking what was right)')
    if pos and sum(-i['weight'] for i in neg) >= 0.5 * sum(i['weight'] for i in pos):
        err.append('the negative weights must add up to less than half the positive weights')
    measured = [i for i in pos if 'measure' in i and i.get('required', True)]
    if len(measured) < 3:
        err.append('at least 3 required positive items that are measured, not judged')
    return err, warn


def second_solution(task, start_objects):
    """Names an item selects must exist in the start scene or be given in the instruction: a check that leans on a
    name only the reference has would fail a different, equally good solution."""
    problems = []
    text = task.get('instruction') or ''
    for i in task.get('items') or []:
        for name in selector_names(i):
            if name not in start_objects and name not in text:
                problems.append(f"{i['id']}: selects {name!r}, which is not in the start scene and not named in the instruction")
    return problems


def public_half(task):
    """What the solving agent is given: no items, no reference."""
    seed = {k: v for k, v in (task.get('seed') or {}).items() if k not in ('reference',)}
    return {k: v for k, v in task.items() if k in ('schema', 'name', 'title', 'instruction', 'phase', 'kind', 'limits')} | {'seed': seed}
