"""Which measurements moved when a person's direction was acted on.

For every direction in a film's workflow.jsonl that steps carry, and every closed task thread, the scene saved just
before the work and the scene saved after it are measured with every probe that needs no task (objects, materials,
lights, world, render, shots, the file, and per shot: framing, motion and the rendered picture, whole and per
object). A field that reads differently in the two scenes is listed. A direction where nothing moved names a
measurement that does not exist yet.

Nothing here judges: a field that moved is a candidate for checking the direction, never proof that it measures it.
The film is only read. Output: <out>/moved.json and <out>/MOVED.md, and the raw rows per step in <out>/steps/.
"""
import json
import shutil
import subprocess
from pathlib import Path

from . import check

SCHEMA = 'film-task-moved/1'
MOMENTS = ['start', 'mid', 'end']
IDENTITY = ('shot', 'at', 'name', 'part', 'material')                 # which row of a probe a value belongs to
IGNORE = ('frame', 'frame_from', 'frame_to', 'samples', 'marker')    # where a row was read, not what it read


def queries(width):
    solid = {'type': ['MESH', 'CURVE', 'SURFACE', 'FONT', 'META']}
    return [
        {'id': 'object', 'probe': 'object'},
        {'id': 'material', 'probe': 'material'},
        {'id': 'light', 'probe': 'light'},
        {'id': 'world', 'probe': 'world'},
        {'id': 'render', 'probe': 'render'},
        {'id': 'shots', 'probe': 'shots'},
        {'id': 'file', 'probe': 'file'},
        {'id': 'framing', 'probe': 'framing', 'select': solid, 'sweep': MOMENTS},
        {'id': 'motion', 'probe': 'motion', 'sweep': ['span']},
        {'id': 'picture', 'probe': 'picture', 'width': width, 'reuse': True, 'sweep': MOMENTS},
        {'id': 'subject', 'probe': 'picture', 'width': width, 'reuse': True, 'sweep': MOMENTS, 'each': True},
    ]


def step_no(row):
    step = str((row.get('params') or {}).get('step') or '')
    return int(step[:4]) if step[:4].isdigit() else None


def number(step):
    return int(str(step)[:4])


def runs(steps):
    """Steps in runs of consecutive numbers: [37, 38, 43] -> [[37, 38], [43]]."""
    out = []
    for s in sorted(steps):
        if out and s == out[-1][-1] + 1:
            out[-1].append(s)
        else:
            out.append([s])
    return out


def pairs(rows, thread=None):
    """The before/after pairs to compare: one per run of steps a direction's work took, one per closed thread."""
    by_id = {r['id']: r for r in rows}
    out = []
    opens = [r for r in rows if r.get('op') == 'task.open' and (not thread or r.get('target') == thread)]
    closes = {r['target']: r for r in rows if r.get('op') == 'task.close'}
    wanted = None
    if thread:
        wanted = set()
        for o in opens:
            ids = (o.get('params') or {}).get('directions') or []
            wanted.update(ids if isinstance(ids, list) else [ids])
        lo = min((number(o['params']['start_step']) for o in opens), default=0)
        hi = max((number(closes[o['target']]['params']['reference_step']) for o in opens if o['target'] in closes), default=10 ** 6)
        wanted.update(r['direction'] for r in rows if r.get('direction') and step_no(r) and lo < step_no(r) <= hi)
    carried = {}
    for r in rows:
        if r.get('direction') and step_no(r) is not None and (wanted is None or r['direction'] in wanted):
            carried.setdefault(r['direction'], []).append(r)
    for did, srows in carried.items():
        d = by_id.get(did) or {}
        text = (d.get('params') or {}).get('direction') or d.get('reason') or ''
        for run in runs({step_no(r) for r in srows}):
            touched = sorted({r.get('target') for r in srows if step_no(r) in run and r.get('target')})
            out.append(dict(kind='direction', id=did, direction=text, steps=run, before=run[0] - 1, after=run[-1], touched=touched))
    for o in opens:
        c = closes.get(o['target'])
        if not c:
            continue
        p, cp = o.get('params') or {}, c.get('params') or {}
        a, b = number(p['start_step']), number(cp['reference_step'])
        touched = sorted({r.get('target') for r in rows if step_no(r) is not None and a < step_no(r) <= b and r.get('target')})
        out.append(dict(kind='thread', id=o['target'], direction=p.get('ask') or '', steps=list(range(a + 1, b + 1)),
                        before=a, after=b, touched=touched, verdict=cp.get('verdict')))
    return out


def measure(film, step, out, width, fresh=False):
    """The rows of every sweep query for one step's saved scene (kept in <out>/steps/NNNN/probe.json)."""
    work = out / 'steps' / f'{step:04d}'
    saved = work / 'probe.json'
    if saved.is_file() and not fresh:
        return json.loads(saved.read_text(encoding='utf-8'))
    hits = sorted((film / '.local' / 'checkpoints').glob(f'{step:04d}-*.blend'))
    if not hits:
        raise SystemExit(f'no checkpoint for step {step} in {film / ".local" / "checkpoints"} (tools/replay.py --keep rebuilds them)')
    exe = check.bffroot.blender()
    if not exe:
        raise SystemExit('Blender not found (machine/bootstrap.py)')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / 'queries.json').write_text(json.dumps({'queries': queries(width)}, indent=1), encoding='utf-8')
    r = subprocess.run([exe, '-b', str(hits[0]), '--python', str(check.PROBE), '--', str(work / 'queries.json'),
                        str(saved), str(work)], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(film))
    (work / 'blender.log').write_text((r.stdout or '') + (r.stderr or ''), encoding='utf-8')
    if not saved.is_file():
        raise SystemExit(f'the probe did not finish on {hits[0]}:\n' + ((r.stdout or '') + (r.stderr or ''))[-1500:])
    for png in work.glob('*.png'):                       # the pictures were only there to be measured
        png.unlink()
    return json.loads(saved.read_text(encoding='utf-8'))


def flatten(probe):
    """{(query, row identity): {field: value}} for one scene."""
    flat = {}
    for qid, rows in (probe.get('rows') or {}).items():
        for n, row in enumerate(rows or []):
            ident = tuple((k, row[k]) for k in IDENTITY if k in row)
            key = (qid, ident or (('row', n),))
            flat[key] = {k: v for k, v in row.items() if k not in IDENTITY and k not in IGNORE}
    return flat


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def change(a, b, abs_tol, rel_tol):
    """How far a value moved, as a share of its size (None when it did not move). Lists of numbers by their largest part."""
    if is_num(a) and is_num(b):
        d = abs(a - b)
        return d / max(abs(a), abs(b), 1e-9) if d > max(abs_tol, rel_tol * max(abs(a), abs(b))) else None
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and a and all(is_num(x) for x in a + b):
        parts = [change(x, y, abs_tol, rel_tol) for x, y in zip(a, b)]
        parts = [p for p in parts if p is not None]
        return max(parts) if parts else None
    return None if a == b else 1.0


def where(key):
    qid, ident = key
    d = dict(ident)
    bits = [qid]
    if 'shot' in d:
        bits.append(f"shot {d['shot']} {d.get('at', '')}".strip())
    for k in ('name', 'part', 'material'):
        if k in d and not (k == 'part' and d[k] == d.get('name')):
            bits.append(str(d[k]))
    return ' / '.join(bits)


def compare(before, after, touched, shots_after, abs_tol, rel_tol):
    """Every field that reads differently in the two scenes, the ones on what the steps touched first."""
    A, B = flatten(before), flatten(after)
    cams = {s['camera']: s['shot'] for s in shots_after}
    touched_shots = {cams[t] for t in touched if t in cams}
    moved, same = [], 0
    for key in sorted(set(A) | set(B), key=str):
        d = dict(key[1])
        on = d.get('name') in touched or d.get('part') in touched or (d.get('shot') in touched_shots and bool(touched_shots))
        if key not in A or key not in B:
            moved.append(dict(where=where(key), field='(row)', before='absent' if key not in A else 'present',
                              after='present' if key in B else 'absent', size=1.0, on_touched=on, query=key[0]))
            continue
        for f in sorted(set(A[key]) | set(B[key])):
            a, b = A[key].get(f), B[key].get(f)
            size = change(a, b, abs_tol, rel_tol)
            if size is None:
                same += 1
            else:
                moved.append(dict(where=where(key), field=f, before=a, after=b, size=round(size, 4), on_touched=on, query=key[0]))
    moved.sort(key=lambda m: (not m['on_touched'], -m['size'], m['where'], m['field']))
    return moved, same


def show(v):
    if isinstance(v, float):
        return f'{v:.4g}'
    if isinstance(v, list):
        return '[' + ', '.join(show(x) for x in v) + ']'
    return str(v)


def report(film, result, limit):
    """MOVED.md: per pair, what switched (yes/no values, rows that came or went), then the numbers by field."""
    out = [f"# What moved: {film.name}", '',
           'For each direction a person gave: the fields that read differently in the scene saved before the work and '
           'the scene saved after it. A field that moved is a candidate for checking the direction, not proof that it '
           'measures it. A direction with nothing on the list names a measurement that does not exist yet. '
           'Every moved field is in moved.json.', '']
    for p in result['pairs']:
        head = {'thread': 'Thread', 'direction': 'Direction'}.get(p['kind'], 'Steps')
        on = [m for m in p['moved'] if m['on_touched']]
        out += [f"## {head} {p['id']}: step {p['before']:04d} to {p['after']:04d}", '']
        if p['direction']:
            out += [f"> {p['direction']}", '']
        out += [f"Steps {p['steps']} changed: {', '.join(p['touched']) or 'nothing named'}. {len(p['moved'])} field(s) moved "
                f"({len(on)} on what the steps changed, {len(p['moved']) - len(on)} elsewhere), {p['unchanged']} did not.", '']
        switched = [m for m in p['moved'] if not is_num(m['before']) and not isinstance(m['before'], list)]
        if switched:
            out += [f"**Switched** ({len(switched)}): a yes/no or a named value changed, or a row came or went", '',
                    '| Where | Field | Before | After |', '|---|---|---|---|']
            out += [f"| {m['where']} | `{m['field']}` | {show(m['before'])} | {show(m['after'])} |" for m in switched[:limit]]
            if len(switched) > limit:
                out.append(f"| ... | {len(switched) - limit} more | | |")
            out.append('')
        groups = {}
        for m in p['moved']:
            if m not in switched:
                groups.setdefault((m['query'], m['field']), []).append(m)
        if groups:
            out += [f"**Numbers that moved, by field** ({len(groups)} fields)", '',
                    '| Probe | Field | Places | Largest change | Before | After |', '|---|---|---|---|---|---|']
            for (q, f), ms in sorted(groups.items(), key=lambda kv: (not any(m['on_touched'] for m in kv[1]), -len(kv[1]))):
                both = [m for m in ms if m['before'] is not None and m['after'] is not None] or ms   # a real before and after
                top = max(both, key=lambda m: m['size'])
                out.append(f"| {q} | `{f}` | {len(ms)} | {top['where']} | {show(top['before'])} | {show(top['after'])} |")
            out.append('')
        if not p['moved']:
            out += ['**Nothing moved.** No existing field reads this change.', '']
    return '\n'.join(out) + '\n'


def run(film, out=None, thread=None, before=None, after=None, width=320, abs_tol=0.004, rel_tol=0.02, limit=40, fresh=False):
    film = Path(film).resolve()
    out = Path(out).resolve() if out else film.parent.parent / 'tasks' / film.name / 'moved'   # never inside the film
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in (film / 'workflow.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    if before is not None and after is not None:
        a, b = int(before), int(after)
        touched = sorted({r.get('target') for r in rows if step_no(r) is not None and a < step_no(r) <= b and r.get('target')})
        todo = [dict(kind='steps', id=f'{a:04d}-{b:04d}', direction='', steps=list(range(a + 1, b + 1)), before=a, after=b, touched=touched)]
    else:
        todo = pairs(rows, thread)
    scenes = {}
    for p in todo:
        for s in (p['before'], p['after']):
            if s not in scenes:
                print(f'measuring step {s:04d}', flush=True)
                scenes[s] = measure(film, s, out, width, fresh)
        errors = {**scenes[p['before']].get('errors', {}), **scenes[p['after']].get('errors', {})}
        p['moved'], p['unchanged'] = compare(scenes[p['before']], scenes[p['after']], set(p['touched']),
                                             scenes[p['after']]['rows'].get('shots') or [], abs_tol, rel_tol)
        p['probe_errors'] = errors
    result = dict(schema=SCHEMA, film=film.name, width=width, abs_tol=abs_tol, rel_tol=rel_tol, pairs=todo)
    (out / 'moved.json').write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
    (out / 'MOVED.md').write_text(report(film, result, limit), encoding='utf-8')
    for p in todo:
        on = sum(1 for m in p['moved'] if m['on_touched'])
        print(f"{p['kind']} {p['id']} ({p['before']:04d} -> {p['after']:04d}): {len(p['moved'])} moved, {on} on what the steps changed"
              + (f"; probe errors: {', '.join(p['probe_errors'])}" if p['probe_errors'] else ''))
    print(out / 'MOVED.md')
    return 0
