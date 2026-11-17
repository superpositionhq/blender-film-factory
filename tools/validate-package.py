#!/usr/bin/env python3
"""Validate an unpacked dataset folder or dataset ZIP, without requiring Git."""
import argparse
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath


def validate(names, read):
    errors = []
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
            errors.append(f'forbidden package path: {name}')
    for name in ('film/film.json', 'history/commits.jsonl', 'trajectory/trajectory.jsonl',
                 'trajectory/analysis.json', 'DATASET.md'):
        if name not in names:
            errors.append(f'missing {name}')
    if errors:
        return errors
    seen, steps = set(), set()
    try:
        rows = [json.loads(line) for line in read('history/commits.jsonl').decode('utf-8').splitlines() if line.strip()]
        if not rows:
            errors.append('commit history is empty')
        for i, row in enumerate(rows, 1):
            if set(row) != {'schema','seq','commit','parents','authored_at','committed_at','message','patch'}:
                raise ValueError(f'commit row {i}: unexpected or missing fields')
            sha = row['commit']
            if row['schema'] != 'film-commit/v1' or type(row['seq']) is not int or row['seq'] != i:
                raise ValueError(f'commit row {i}: invalid schema or sequence')
            if not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',sha) or sha in seen:
                raise ValueError(f'commit row {i}: invalid or duplicate hash')
            if not isinstance(row['parents'],list) or any(not isinstance(p,str) or p not in seen for p in row['parents']):
                raise ValueError(f'commit row {i}: parent missing or out of order')
            for key in ('authored_at','committed_at'):
                if datetime.fromisoformat(row[key].replace('Z','+00:00')).tzinfo is None:
                    raise ValueError(f'commit row {i}: timestamp needs timezone')
            if not isinstance(row['message'],str) or not isinstance(row['patch'],str):
                raise ValueError(f'commit row {i}: message and patch must be strings')
            seen.add(sha)
            steps.update(re.findall(r'(?m)^step: (\d{4}-\S+)',row['message']))
        folders = {PurePosixPath(n).parts[2] for n in names if n.startswith('film/steps/') and len(PurePosixPath(n).parts)>3}
        for step in sorted(folders - steps):
            errors.append(f'step missing from commit history: {step}')
        for name in ('film/film.json','trajectory/analysis.json'):
            if not isinstance(json.loads(read(name)),dict):
                errors.append(f'{name}: expected an object')
        for name in ('film/workflow.jsonl','trajectory/trajectory.jsonl'):
            if name in names:
                for i,line in enumerate(read(name).decode('utf-8').splitlines(),1):
                    if line.strip() and not isinstance(json.loads(line),dict):
                        errors.append(f'{name}:{i}: expected an object')
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        errors.append(str(exc))
    return errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    args=parser.parse_args()
    path=Path(args.package)
    try:
        if path.is_dir():
            names={p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()}
            errors=validate(names,lambda name:(path/name).read_bytes())
        else:
            with zipfile.ZipFile(path) as z:
                entries=[n for n in z.namelist() if not n.endswith('/')]
                if len(entries)!=len(set(entries)):
                    raise ValueError('duplicate ZIP entries')
                roots={n.split('/')[0] for n in entries}
                if len(roots)!=1:
                    raise ValueError('expected one dataset root folder')
                prefix=next(iter(roots))+'/'
                errors=validate({n[len(prefix):] for n in entries},lambda name:z.read(prefix+name))
    except (OSError,ValueError,zipfile.BadZipFile) as exc:
        errors=[str(exc)]
    for error in errors: print('ERROR '+error)
    print('INVALID package' if errors else 'VALID package')
    return 2 if errors else 0

if __name__=='__main__':
    sys.exit(main())
