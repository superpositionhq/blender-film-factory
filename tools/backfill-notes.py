#!/usr/bin/env python3
"""Add the notes a session did not write before its steps, after the session, marked as added afterwards.

  python tools/backfill-notes.py <film> [--dry-run]

A step's note is the sentence the session writes before the step (blender-film-session skill, "The step"). When a
session ran steps without one, this writes <film>/notes-backfill.jsonl (schema film-note-backfill/v1), one row per
step: `step` (the step folder's name), `note`, `written` (now), `source`. The note is built from what the session
did record when the step ran: the step's subject and the reason it gave the step tool (its workflow.jsonl row).
Nothing is invented and no observation is added.

tools/trajectory.py uses a row only for a step that has no note of its own: the note is placed before that step's
call as an `assistant` event with `"backfilled": true` and its `written` time, shown in trajectory.md as "note added
after the session", and counted apart (analysis.json: `notes_backfilled`, `note_coverage_live`). The recording
itself (<BFF_ROOT>/.recording/<slug>/) is not touched. Run it again after more steps: rows already there are kept.
Commit the file (one `log.gap` row says what was missed). Python 3.9+ standard library only.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'machine' / 'lib'))
import bffroot  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    film = Path(args[0]).resolve()
    log = film / 'workflow.jsonl'
    if not log.is_file():
        sys.exit(f'{film} has no workflow.jsonl')
    rows = [json.loads(l) for l in log.read_text(encoding='utf-8').splitlines() if l.strip()]
    r = subprocess.run(['git', '-C', str(film), 'log', '--format=%s%x00%b%x01'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    subjects = {}
    for c in r.stdout.split('\x01'):
        subject, _, body = c.strip().partition('\0')
        for line in body.splitlines():
            if line.startswith('step: '):
                subjects[line[6:].strip()] = subject.removeprefix('Failed: ')
    out = film / 'notes-backfill.jsonl'
    have = {json.loads(l)['step'] for l in out.read_text(encoding='utf-8').splitlines() if l.strip()} if out.is_file() else set()
    new = []
    for row in rows:
        step = (row.get('params') or {}).get('step')
        reason = (row.get('reason') or '').strip()
        if not step or step in have or not reason:
            continue
        subject = subjects.get(step, '').strip()
        note = (f'Next step: {subject}. ' if subject else 'Next step. ') + f'Why: {reason}'
        new.append(dict(schema='film-note-backfill/v1', step=step, note=note, written=bffroot.now(),
                        source=f"workflow row {row.get('id')} and the step's commit subject, both recorded when the step ran"))
        have.add(step)
    if '--dry-run' not in sys.argv and new:
        bffroot.append_jsonl(out, new)
    print(f'{len(new)} note(s) {"would be " if "--dry-run" in sys.argv else ""}added to {out.name} ({len(have)} in all)')


if __name__ == '__main__':
    main()
