"""A task as one page a person can read: the instruction, every scoring point in plain words, what it measured on
the start and on the reference, and the verdict. Written beside the task as CARD.md."""

PLAIN = {
    'object': 'the object {select}: its {field}',
    'material': 'the material on {select}: its {field}',
    'light': 'the lights{at}: {field}',
    'world': 'the background: its {field}',
    'render': 'the render settings: {field}',
    'shots': 'the shots of the timeline: {field}',
    'framing': '{select} as seen by {camera}: {field}',
    'motion': 'how {select} moves over the frames: {field}',
    'contact': '{a} against {b}: {field}',
    'file': 'the saved file: {field}',
    'screen': 'the rendered picture from {camera}: {field}',
    'picture': 'the rendered picture from {camera}, with {select} as the subject: {field}',
}
AGG = {'first': '', 'last': ' (last row)', 'count': 'how many there are', 'any': ' (true on any)', 'all': ' (true on all)',
       'share': ' (share of rows where true)', 'distinct': ' (number of different values)', 'min': ' (lowest)',
       'max': ' (highest)', 'sum': ' (added up)', 'mean': ' (average)', 'median': ' (median)', 'range': ' (highest minus lowest)',
       'delta': ' (last minus first)'}


def sel_text(sel):
    if sel is None:
        return 'every object'
    if isinstance(sel, str):
        return f'`{sel}`'
    parts = []
    if 'name' in sel:
        parts.append('`' + (', '.join(sel['name']) if isinstance(sel['name'], list) else sel['name']) + '`')
    if 'glob' in sel:
        parts.append(f'objects named like `{sel["glob"]}`')
    if 'type' in sel:
        parts.append(f'{sel["type"]} objects' if isinstance(sel['type'], str) else '/'.join(sel['type']) + ' objects')
    if sel.get('new'):
        parts.append('added since the start')
    if 'near' in sel:
        parts.append(f'within {sel["near"].get("radius", 1.0)} m of {sel["near"]["point"]}')
    return ' '.join(parts) or 'every object'


def frames_text(m):
    if 'frames' in m:
        f = m['frames']
        return f', frames {f["from"]} to {f["to"]}' if isinstance(f, dict) else f', frames {", ".join(map(str, f))}'
    return f', frame {m["frame"]}' if 'frame' in m else ''


def how(item):
    """One plain line saying what an item looks at."""
    if 'judge' in item:
        j = item['judge']
        shots = ', '.join(f"frame {s.get('frame', 'first')}" + (f" from {s['camera']}" if isinstance(s.get('camera'), str) else '') for s in j['shots'])
        return f'A reviewer looks at {shots} and answers: "{j["question"]}"'
    m, e = item['measure'], item['expect']
    cam = m.get('camera')
    cam = f'`{cam}`' if isinstance(cam, str) else f'the camera of shot {cam["shot"]}' if isinstance(cam, dict) else 'the shot camera'
    field = (m.get('field') or '').replace('_', ' ')
    if m.get('agg') == 'count':
        field = AGG['count']
    else:
        field += AGG.get(m.get('agg', 'first'), '')
    text = PLAIN[m['probe']].format(select=sel_text(m.get('select')), a=sel_text(m.get('a')), b=sel_text(m.get('b')),
                                    camera=cam, field=field, at=f' reaching `{m["at"]}`' if 'at' in m else '')
    text = 'Measures ' + text + frames_text(m) + '. '
    if 'gradient' in e:
        g = e['gradient']
        return text + f'Scored in five levels from {g.get("from", "start")} (0) to {g.get("to", "reference")} (1).'
    op = e.get('op')
    if op in ('true', 'false'):
        cond = f'it is {op}'
    elif op in ('changed', 'unchanged'):
        cond = f'it has {op} from the start' if op == 'changed' else 'it is the same as at the start'
    elif 'calibrate' in e:
        cond = f'it is {op} {int(e["calibrate"] * 100)} % of the way from the start value to the reference value'
    elif 'start_plus' in e:
        cond = f'it is {op} the start value plus {e["start_plus"]}'
    elif 'start_times' in e:
        cond = f'it is {op} {e["start_times"]} times the start value'
    else:
        cond = f'it is {op} {e.get("value")!r}'
    return text + ('The error counts when ' if item['weight'] < 0 else 'Met when ') + cond + '.'


def show(v):
    if v is None:
        return 'nothing'
    if isinstance(v, float):
        return f'{v:.4g}'
    return str(v)


def mark(side, weight):
    hit = side.get('hit')
    if hit is None:
        return side.get('problem') or 'not measured'
    if weight > 0:
        return 'met' if hit >= 1 else 'not met' if hit <= 0 else f'level {hit:g}'
    return 'ERROR happened' if hit >= 1 else 'no error' if hit <= 0 else f'error level {hit:g}'


def render(task, result=None):
    by = {r['id']: r for r in (result or {}).get('items', [])}
    pos = sum(i['weight'] for i in task['items'] if i['weight'] > 0)
    L = [f"# {task['title']}", '',
         f"`{task['name']}` · phase **{task.get('phase')}** · kind **{task.get('kind')}** · difficulty **{task.get('difficulty', 'not set')}**", '']
    if result:
        L += [f"**Check verdict: {result['verdict']}**", '']
        for e in result.get('errors', []):
            L.append(f'- PROBLEM: {e}')
        for w in result.get('warnings', []):
            L.append(f'- warning: {w}')
        if result.get('errors') or result.get('warnings'):
            L.append('')
    L += ['## What the solver is told', '', task['instruction'].strip(), '',
          '## What the solver starts from and what a good answer looks like', '',
          f"- Start: `start.blend`, the film at step {task['seed'].get('start')}.",
          f"- Reference: `reference.blend`, the film at step {task['seed'].get('reference')}. The solver never sees it.", '',
          '## How it is scored', '',
          f'Reward = points earned, minus points lost to errors, divided by {pos} (never below 0). '
          'Solved = every required point met and no required error.', '']
    for i in task['items']:
        r = by.get(i['id'])
        sign = f"+{i['weight']}" if i['weight'] > 0 else str(i['weight'])
        req = 'required' if i.get('required', True) else 'optional'
        L += [f"### {i['id']} ({sign}, {req}) {i['description']}", '',
              f"{i['dimension'].replace('_', ' ')} · {i['criterion_type']} · {i['criterion_necessity']} · {i['type']}", '',
              how(i), '']
        if 'judge' in i and i['type'] == 'gradient':
            for lv in ('1', '0.75', '0.5', '0.25', '0'):
                L.append(f"- {lv}: {i['judge']['levels'][lv]}")
            L.append('')
        if r:
            s, f = r['start'], r['reference']
            thr = f" Threshold: {show(f.get('threshold'))}." if f.get('threshold') is not None and not isinstance(f.get('threshold'), list) else ''
            L += [f"- Start scene: {show(s.get('value'))} ({mark(s, i['weight'])})",
                  f"- Reference scene: {show(f.get('value'))} ({mark(f, i['weight'])}){thr}", '']
    if result and result.get('verdict') != 'INVALID':
        L += ['## Result on the two snapshots', '',
              f"- Untouched start: reward {result.get('start_reward')} (must be 0).",
              f"- Reference: reward {result.get('reference_reward')} (must solve the task).", '']
    L += ['## For the reviewer', '',
          '- Does each scoring point follow from the instruction, word for word or as a necessary consequence?',
          '- Would a different, equally good solution also earn every point?',
          '- Is any point counted twice, or scored from something the instruction never says?',
          '- Does each error item name something that would really spoil the result?', '']
    return '\n'.join(L)
