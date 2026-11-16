#!/usr/bin/env python3
"""Append one row to a project's workflow.jsonl, at the moment of the operation (blender-film-commit-always skill).

  python workflow-row.py <project> --op <op> --target <what> --reason "<why, as you see it now>"
      [--param key=value ...] [--script <file in the project>] [--direction <row id>] [--status observed|failed|reverted]
  python workflow-row.py <project> --op user.direction --target <area> --reason "<the direction, rewritten>"
      [--via direct|coordinator]

It fills in the schema (film-workflow/v0), the next id and seq (the id prefix is the first row's), the time, and
`source`: the HEAD commit the work stands on and, with --script, that file's path and sha256. A --param value that
parses as JSON is stored as JSON (count=3, parts=["roof","door"]), anything else as text. A user.direction row gets
actor "user", the direction as params.direction and reason_source "user_direction". Prints the new row's id.
It refuses a row that holds a banned name, and never edits a row that is there. Python 3.9+ standard library only.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'machine' / 'lib'))
import bffroot  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('project')
    p.add_argument('--op', required=True)
    p.add_argument('--target', required=True)
    p.add_argument('--reason', required=True)
    p.add_argument('--param', action='append', default=[])
    p.add_argument('--script')
    p.add_argument('--direction')
    p.add_argument('--via', choices=['direct', 'coordinator'], default='direct')
    p.add_argument('--status', choices=['observed', 'failed', 'reverted', 'unrecorded'], default='observed')
    a = p.parse_args()
    project = Path(a.project)
    log = project / 'workflow.jsonl'
    rows = [json.loads(l) for l in log.read_text(encoding='utf-8').splitlines() if l.strip()] if log.is_file() else []
    if not rows:
        sys.exit(f'{log} has no first row: templates/new-film.py writes it')
    params = {}
    for kv in a.param:
        k, _, v = kv.partition('=')
        try:
            params[k] = json.loads(v)
        except ValueError:
            params[k] = v
    if a.direction and a.direction not in {r['id'] for r in rows if r.get('op') == 'user.direction'}:
        sys.exit(f'--direction {a.direction} is not an earlier user.direction row')
    head = subprocess.run(['git', '-C', str(project), 'rev-parse', '--short=12', 'HEAD'], capture_output=True, text=True)
    source = dict(script=None, sha256=None, commit=head.stdout.strip() or None)
    if a.script:
        f = project / a.script
        if not f.is_file():
            sys.exit(f'--script {a.script} is not a file of the project')
        source.update(script=Path(a.script).as_posix(), sha256=hashlib.sha256(f.read_bytes().replace(b'\r\n', b'\n')).hexdigest())
    seq = max(int(r.get('seq', 0)) for r in rows) + 1
    row = dict(schema='film-workflow/v0', id=f"{rows[0]['id'].rsplit('-', 1)[0]}-{seq:05d}", seq=seq, time=bffroot.now())
    if a.op == 'user.direction':
        row.update(actor='user', op=a.op, target=a.target, params=dict(params, direction=a.reason, via=a.via),
                   reason_source='user_direction', status='observed', source=source)
    else:
        row.update(actor='agent', op=a.op, target=a.target, params=params, reason=a.reason, reason_source='agent_note',
                   status=a.status, source=source)
        if a.direction:
            row['direction'] = a.direction
    bad = bffroot.banned_in(json.dumps(row, ensure_ascii=False))
    home = Path.home().name
    if len(home) >= 4 and home.lower() in json.dumps(row, ensure_ascii=False).lower():
        bad.append('the account name (a machine path? write it relative to the project)')
    if bad:
        sys.exit(f'not written: the row holds {", ".join(bad)} (blender-film-session skill, "Names")')
    bffroot.append_jsonl(log, [row])
    print(row['id'])


if __name__ == '__main__':
    main()
