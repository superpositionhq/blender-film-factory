#!/usr/bin/env python3
"""Record a reviewer's decision on a released film. Only an accepted film is packaged as a trajectory.

  python tools/review.py <film> --reviewer <id> --decision accept|reject --note "<why, one or two sentences>"
      --score story=4 --score staging=4 ... [--no-commit]

Scores are 1 to 5 per dimension (docs/review.md has the anchors). The dimensions depend on the film's output:
  greybox: story, staging, motion, camera, editing, cleanliness, workflow_record
  final:   the same, plus composition, lighting, colour, materials, modelling
`workflow_record` scores observable action notes and image inspections: visible results, intended actions and
the reason given for each change (tools/trajectory.py prints the coverage).
An accept needs every dimension scored, none under 3 and a mean of 3.5 or more; otherwise the decision must be
reject, and the note says what to fix. Writes <film>/review/review-<n>.json (film-review/v1) and commits it.
The reviewer is a different person from the writer; --reviewer is their id (dev_NN), never a name.
Python 3.9+ standard library only.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DIMS = {
    'greybox': ['story', 'staging', 'motion', 'camera', 'editing', 'cleanliness', 'workflow_record'],
    'final': ['story', 'staging', 'motion', 'camera', 'editing', 'cleanliness', 'workflow_record',
              'composition', 'lighting', 'colour', 'materials', 'modelling'],
}


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('--reviewer', required=True)
    p.add_argument('--decision', choices=['accept', 'reject'], required=True)
    p.add_argument('--note', required=True)
    p.add_argument('--score', action='append', default=[])
    p.add_argument('--no-commit', action='store_true')
    a = p.parse_args()
    film = Path(a.film).resolve()
    meta = json.loads((film / 'film.json').read_text(encoding='utf-8'))
    dims = DIMS[meta['output']]
    scores = {}
    for kv in a.score:
        k, _, v = kv.partition('=')
        if k == 'reasoning':
            k = 'workflow_record'
        if k not in dims or v not in '12345' or len(v) != 1:
            sys.exit(f'--score {kv}: dimensions for a {meta["output"]} film are {", ".join(dims)}; scores are 1 to 5')
        scores[k] = int(v)
    missing = [d for d in dims if d not in scores]
    if missing:
        sys.exit('score every dimension; missing: ' + ', '.join(missing))
    mean = sum(scores.values()) / len(scores)
    passes = min(scores.values()) >= 3 and mean >= 3.5
    if a.decision == 'accept' and not passes:
        sys.exit(f'these scores (lowest {min(scores.values())}, mean {mean:.2f}) do not allow an accept: none under 3 and a mean of 3.5')
    sha = subprocess.run(['git', '-C', str(film), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    d = film / 'review'
    d.mkdir(exist_ok=True)
    n = len(list(d.glob('review-*.json'))) + 1
    row = dict(schema='film-review/v1', n=n, time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), reviewer=a.reviewer, decision=a.decision,
               reviewed_commit=sha, scores=scores, mean=round(mean, 2), note=a.note)
    (d / f'review-{n:02d}.json').write_text(json.dumps(row, indent=1) + '\n', encoding='utf-8')
    if not a.no_commit:
        subprocess.run(['git', '-C', str(film), 'add', str(d)])
        subprocess.run(['git', '-C', str(film), 'commit', '-q', '-m', f'Review {n}: {a.decision}', '-m', a.note])
    print(f'review {n}: {a.decision} (mean {mean:.2f}, lowest {min(scores.values())}) at {sha[:7]}')


if __name__ == '__main__':
    main()
