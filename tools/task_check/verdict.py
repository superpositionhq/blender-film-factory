"""Reduce probe rows to one value, compare it, score the items and say whether a task is VALID. No Blender here.

An item is one scoring point of a task (docs/task-format.md). A positive item (weight > 0) earns its weight when
what it asks for is there; a negative item (weight < 0) costs its weight when the error it names has happened.
"""
import math
import statistics

WEIGHTS = (10, 7, 3, -3, -7, -10)
LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
OPS = ('>=', '<=', '>', '<', '==', '!=', 'between', 'in', 'contains', 'changed', 'unchanged', 'true', 'false')


def dig(row, path):
    """row['a']['b'][2] for the path 'a.b.2'; None when it is not there."""
    cur = row
    for part in str(path).split('.'):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)) and part.lstrip('-').isdigit() and -len(cur) <= int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def keep(row, where):
    for key, want in (where or {}).items():
        got = dig(row, key)
        if isinstance(want, list):
            if got not in want:
                return False
        elif got != want:
            return False
    return True


def reduce_rows(rows, measure):
    """One value from a probe's rows: filter with `where`, read `field`, fold with `agg`. None = measured nothing."""
    rows = [r for r in (rows or []) if keep(r, measure.get('where'))]
    agg = measure.get('agg', 'first')
    if agg == 'count':
        return len(rows)
    vals = [dig(r, measure['field']) for r in rows] if 'field' in measure else []
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    if agg in ('first', 'last'):
        v = vals[0 if agg == 'first' else -1]
    elif agg == 'any':
        v = any(bool(x) for x in vals)
    elif agg == 'all':
        v = all(bool(x) for x in vals)
    elif agg == 'share':                       # the share of rows where the field is true
        v = sum(1 for x in vals if x) / len(vals)
    elif agg == 'distinct':
        v = len({str(x) for x in vals})
    else:
        nums = [float(x) for x in vals if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if not nums:
            return None
        v = {'min': min, 'max': max, 'sum': sum, 'mean': statistics.fmean, 'median': statistics.median,
             'range': lambda n: max(n) - min(n), 'delta': lambda n: n[-1] - n[0]}[agg](nums)
    if measure.get('abs') and isinstance(v, (int, float)) and not isinstance(v, bool):
        v = abs(v)
    return round(v, 5) if isinstance(v, float) else v


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def alike(a, b, tol):
    """Equal within a tolerance: numbers, or lists of numbers such as a position."""
    if is_num(a) and is_num(b):
        return math.isclose(a, b, abs_tol=tol)
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(is_num(x) for x in a + b):
        return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b))
    return a == b


def threshold(expect, start, ref):
    """The number an item compares against, from a literal or from the start / reference measurement.
    Returns (value, problem)."""
    if 'value' in expect:
        return expect['value'], None
    if 'calibrate' in expect:                   # a share of the way from the start value to the reference value
        if not is_num(start) or not is_num(ref):
            return None, 'calibrate needs a number at the start and at the reference'
        if math.isclose(start, ref, abs_tol=1e-6):
            return None, 'uncalibrated: the start and the reference measure the same'
        return round(start + float(expect['calibrate']) * (ref - start), 5), None
    if 'start_plus' in expect or 'start_times' in expect:
        if not is_num(start):
            return None, 'needs a number at the start'
        return round(start + expect['start_plus'] if 'start_plus' in expect else start * expect['start_times'], 5), None
    return None, None


def compare(value, expect, start=None, ref=None):
    """(holds, threshold, problem). holds is None when the value could not be compared."""
    op = expect.get('op')
    if value is None:
        return None, None, 'measured nothing'
    if op in ('true', 'false'):
        return bool(value) is (op == 'true'), None, None
    if op in ('changed', 'unchanged'):
        if start is None:
            return None, None, 'nothing measured at the start to compare with'
        same = alike(value, start, float(expect.get('tol', 1e-4)))
        return (not same) if op == 'changed' else same, start, None
    if op == 'between':
        lo, hi = expect['value']
        return (lo <= value <= hi) if is_num(value) else None, [lo, hi], None
    if op == 'in':
        return value in expect['value'], expect['value'], None
    if op == 'contains':
        return expect['value'] in value if isinstance(value, (list, str)) else None, expect['value'], None
    thr, problem = threshold(expect, start, ref)
    if problem:
        return None, None, problem
    if op in ('==', '!='):
        tol = float(expect.get('tol', 1e-4))
        same = math.isclose(value, thr, abs_tol=tol) if is_num(value) and is_num(thr) else value == thr
        return same if op == '==' else not same, thr, None
    if not is_num(value) or not is_num(thr):
        return None, thr, f'{op} needs numbers'
    return {'>=': value >= thr, '<=': value <= thr, '>': value > thr, '<': value < thr}[op], thr, None


def level(value, expect, start, ref):
    """A gradient item's level, one of 0 / 0.25 / 0.5 / 0.75 / 1: how far the value has come from `from` to `to`
    (each a number, "start" or "reference"), rounded down to a level."""
    g = expect['gradient']
    lo = start if g.get('from', 'start') == 'start' else ref if g.get('from') == 'reference' else g['from']
    hi = ref if g.get('to', 'reference') == 'reference' else start if g.get('to') == 'start' else g['to']
    if value is None:
        return None, 'measured nothing'
    if not (is_num(value) and is_num(lo) and is_num(hi)):
        return None, 'a gradient needs numbers'
    if math.isclose(lo, hi, abs_tol=1e-6):
        return None, 'uncalibrated: the two ends of the gradient are the same'
    share = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    return max(l for l in LEVELS if l <= share + 1e-9), None


def score_item(item, value, start=None, ref=None, answer=None):
    """One item on one scene: {'value', 'hit' (0..1 or None), 'threshold', 'problem'}.
    hit is how far a positive item is met, or how far a negative item's error happened."""
    if 'judge' in item:
        if answer is None:
            return dict(value=None, hit=None, threshold=None, problem='not judged')
        a = float(answer)
        if item.get('type') == 'gradient':
            a = min(LEVELS, key=lambda l: abs(l - a))
        else:
            a = 1.0 if a >= 0.5 else 0.0
        return dict(value=a, hit=a, threshold=None, problem=None)
    expect = item['expect']
    if 'gradient' in expect:
        hit, problem = level(value, expect, start, ref)
        return dict(value=value, hit=hit, threshold=None, problem=problem)
    holds, thr, problem = compare(value, expect, start, ref)
    return dict(value=value, hit=None if holds is None else (1.0 if holds else 0.0), threshold=thr, problem=problem)


def reward(items, scored):
    """max(0, (earned positive weight + negative weight that was hit) / all positive weight), 0..1.
    An item that could not be measured counts as not met (positive) or not happened (negative).
    Returns (reward, solved, pending): solved = every required positive item fully met and no required negative
    item hit; pending = ids of judge items nobody has answered yet."""
    pos = sum(i['weight'] for i in items if i['weight'] > 0)
    total, solved, pending = 0.0, True, []
    for i in items:
        s = scored[i['id']]
        if s['problem'] == 'not judged':
            pending.append(i['id'])
        hit = s['hit'] or 0.0
        total += hit * i['weight']
        if i.get('required', True):
            if i['weight'] > 0 and hit < 1.0:
                solved = False
            if i['weight'] < 0 and hit > 0.0:
                solved = False
    return (round(max(0.0, total / pos), 4) if pos else 0.0), solved and not pending, pending


def validity(items, start_scored, ref_scored):
    """Problems that make a task INVALID. A valid task: untouched, the start earns nothing and trips nothing;
    the reference earns everything and trips nothing; every item measured something real on the reference."""
    problems = []
    for i in items:
        s, r, name = start_scored[i['id']], ref_scored[i['id']], i['id']
        if 'judge' in i:
            if r['hit'] is None or s['hit'] is None:
                problems.append(f'{name}: judge item has no answer for the start and the reference')
                continue
        elif r['problem']:
            problems.append(f"{name}: on the reference: {r['problem']}")
            continue
        elif s['problem'] and s['problem'] != 'measured nothing':
            problems.append(f"{name}: on the start: {s['problem']}")
            continue
        if i['weight'] > 0:
            if (r['hit'] or 0) < 1.0:
                problems.append(f"{name}: the reference does not fully meet it (value {r['value']!r}, needs {r['threshold']!r})")
            if (s['hit'] or 0) > 0.0:
                problems.append(f"{name}: the untouched start already meets it (value {s['value']!r}): it would pay for doing nothing")
        else:
            if (r['hit'] or 0) > 0.0:
                problems.append(f"{name}: the reference trips this negative item (value {r['value']!r})")
            if (s['hit'] or 0) > 0.0:
                problems.append(f"{name}: the untouched start trips this negative item (value {s['value']!r})")
    return problems
