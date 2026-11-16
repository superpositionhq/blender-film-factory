#!/usr/bin/env python3
"""Export the recorded session(s) that made a film as one ordered trajectory, and check it.

  python tools/trajectory.py <film> [--out <dir>] [--recording <dir>] [--session <id> ...] [--check] [--json]

Reads the film's recording (<BFF_ROOT>/.recording/<slug>/actions.jsonl and messages.jsonl, written by the machine
hooks) and writes, to --out (default <BFF_ROOT>/.recording/<slug>/trajectory/):
  trajectory.jsonl   one event per line, in time order (film-trajectory/v1): the person's prompts, the model's
                     replies (its notes before each step), every tool call with its input and result, and for every
                     picture the model opened a reference to the picture file
  images/            the pictures the model opened (step previews, render sheets, storyboard pages), copied
  trajectory.md      the same, readable from top to bottom, pictures inline
  analysis.json      reasoning coverage and leaks (below)
Sessions: those that ran tools/step.py or templates/new-film.py for this film (or --session).

Reasoning coverage, per step (a call of tools/step.py):
  note    the model wrote at least one sentence (40 characters) after the previous step and before this one
  looked  the model opened a picture after the previous step and before this one (not asked of the first two steps)
Leaks: paths are rewritten (<film>, <tools>, <root>, ~) and the tool repo's name is replaced; what is still found
afterwards is listed: the account name, e-mail addresses, the owner's and the tool repos' names. Agent and model
names stay: a trajectory is a record of that agent at work.
Secrets are rewritten too, to <secret:kind>, and counted (secrets_redacted): private keys, the tokens and API keys of
common services (GitHub, GitLab, AWS, sk-... keys, Stripe, Slack, Google, Hugging Face, npm), JWTs, bearer tokens, the
password in a URL, and the value of NAME=value or "name": "value" where the name says secret, password, token or API
key. A secret still found afterwards is a leak.
--check: exit code 2 when note or looked coverage is under 90 % or a leak is left. Standard library only.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'machine' / 'lib'))
import bffroot  # noqa: E402

IMG = ('.png', '.jpg', '.jpeg', '.webp')
# Secrets an export never holds: a match becomes <secret:kind> (only group v when the pattern has one, so a variable's
# name stays). No pattern reaches past a quote or a backslash, so a scrubbed JSON text is still JSON.
SECRETS = [(kind, re.compile(p)) for kind, p in (
    ('private-key', r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY[A-Z ]*-----(?:(?:[^"\\]|\\.)*?-----END [A-Z0-9 ]*PRIVATE KEY'
                    r'[A-Z ]*-----|(?:[A-Za-z0-9+/=\s]|\\[rn])*)'),
    ('github-token', r'\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})'),
    ('gitlab-token', r'\bglpat-[A-Za-z0-9_-]{20,}'),
    ('aws-key', r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b'),
    ('api-key', r'\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}'),
    ('stripe-key', r'\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}'),
    ('slack-token', r'\bxox[abposr]-[A-Za-z0-9-]{10,}'),
    ('slack-webhook', r'https://hooks\.slack\.com/services/[A-Za-z0-9/_-]{20,}'),
    ('google-key', r'\bAIza[0-9A-Za-z_-]{35}'),
    ('huggingface-token', r'\bhf_[A-Za-z0-9]{30,}'),
    ('npm-token', r'\bnpm_[A-Za-z0-9]{36}'),
    ('jwt', r'\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    ('bearer-token', r'(?i)\bbearer\s+(?P<v>[A-Za-z0-9._~+/-]{20,}=*)'),
    ('url-password', r'\b[a-z][a-z0-9+.-]*://[^/\s:@\\"\']+:(?P<v>(?!<secret:)[^/\s@\\"\']+)@'),
    # NAME=value as env files, `env` and shell exports print it (upper case, no spaces: not a script's variable)
    ('assignment', r'\b[A-Z][A-Z0-9_]*(?:SECRET|PASSWORD|PASSWD|TOKEN|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|CREDENTIALS?)'
                   r'[A-Z0-9_]*=(?P<v>(?![$<{*])[^\s\'"\\]{8,})'),
    ('assignment', r'(?i)\\?"(?:password|passwd|secret|client_secret|api_?key|access_?token|refresh_?token|auth_?token|'
                   r'private_?key)\\?"\s*:\s*\\?"(?P<v>(?![$<{*])[^"\\\s]{8,})\\?"'),
)]


def load(path):
    rows = []
    if path.is_file():
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def as_text(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def redact(text, kinds):
    """The text with every secret replaced by <secret:kind>; the kinds replaced are added to the set `kinds`."""
    for kind, rx in SECRETS:
        def put(m, kind=kind, rx=rx):
            kinds.add(kind)
            if 'v' not in rx.groupindex:
                return f'<secret:{kind}>'
            return m.string[m.start():m.start('v')] + f'<secret:{kind}>' + m.string[m.end('v'):m.end()]
        text = rx.sub(put, text)
    return text


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('film')
    p.add_argument('--out')
    p.add_argument('--recording')
    p.add_argument('--session', action='append')
    p.add_argument('--check', action='store_true')
    p.add_argument('--json', action='store_true')
    a = p.parse_args()
    film = Path(a.film).resolve()
    root = bffroot.root().resolve()
    rec = Path(a.recording).resolve() if a.recording else root / '.recording' / film.name
    out = Path(a.out).resolve() if a.out else rec / 'trajectory'
    actions, messages = load(rec / 'actions.jsonl'), load(rec / 'messages.jsonl')
    if not actions and not messages:
        msg = f'no recording at {rec}: the recording hooks were not installed, or the session never named the film folder'
        print(json.dumps(dict(ok=False, error=msg)) if a.json else msg)
        sys.exit(2 if a.check else 0)

    def is_build(r):
        t = as_text(r.get('input'))
        return 'step.py' in t or 'new-film.py' in t or 'new-project.py' in t
    sessions = set(a.session or []) or {r['session_id'] for r in actions if r.get('tool') and is_build(r)} \
        or {r['session_id'] for r in actions}

    # paths, names and secrets are rewritten in every text of the export
    home = Path.home()
    swaps = sorted({(str(film), '<film>'), (str(rec), '<recording>'), (str(REPO), '<tools>'), (str(bffroot.repo()), '<tools>'),
                    (str(root), '<root>'), (str(home), '~')}, key=lambda kv: -len(kv[0]))
    def scrub(text, kinds=None):
        for full, token in swaps:
            text = text.replace(full, token).replace(full.replace('/', '\\'), token)
        text = re.sub(r'(?i)blender[-_ ]?film[-_ ]?factory', 'film-tools', text)
        return redact(re.sub(r'~/\.(claude|codex|agents)\b', '~/.agent', text), set() if kinds is None else kinds)

    events = []
    for m in messages:
        if m.get('session_id') in sessions and not m.get('subagent') and (m.get('text') or '').strip():
            events.append(dict(time=m['time'], type=m['role'], text=m['text']))
    for r in actions:
        if r.get('session_id') not in sessions or not r.get('tool') or r.get('subagent'):
            continue
        inp = r.get('input') if isinstance(r.get('input'), dict) else {'value': r.get('input')}
        ev = dict(time=r['time'], type='tool', tool=r['tool'], input=inp, error=bool(r.get('error')) or r.get('event') == 'PostToolUseFailure')
        path = str(inp.get('file_path') or inp.get('path') or '')
        if r['tool'] in ('Read', 'view_image', 'ViewImage') and path.lower().endswith(IMG):
            ev['image_source'] = path
        else:
            res = as_text(r.get('response') if r.get('response') is not None else r.get('error') or '')
            ev['result'] = res      # whole: the record holds what the model saw
        events.append(ev)
    events.sort(key=lambda e: e['time'])

    out.mkdir(parents=True, exist_ok=True)
    (out / 'images').mkdir(exist_ok=True)
    missing_images = 0
    for i, ev in enumerate(events, 1):
        ev['i'] = i
        src = ev.pop('image_source', None)
        if src:
            sp = Path(src)
            try:
                rel = sp.resolve().relative_to(film)
                name = '__'.join(rel.parts)
            except ValueError:
                name = '__'.join(sp.parts[-3:])
            name = f'{i:05d}__{name}'
            if sp.is_file():
                shutil.copyfile(sp, out / 'images' / name)
                ev['image'] = f'images/{name}'
            else:
                ev['image'] = None
                ev['image_missing'] = scrub(src)
                missing_images += 1

    # reasoning coverage
    steps, last, noted, looked, weak = 0, -1, 0, 0, []
    for k, ev in enumerate(events):
        if ev['type'] == 'tool' and ev['tool'] in ('Bash', 'shell') and 'step.py' in as_text(ev['input']):
            steps += 1
            between = events[last + 1:k]
            n_ok = any(e['type'] == 'assistant' and len(e['text'].strip()) >= 40 for e in between)
            l_ok = steps <= 2 or any(e['type'] == 'tool' and 'image' in e for e in between)
            noted += n_ok
            looked += l_ok
            if not (n_ok and l_ok):
                weak.append(dict(event=ev['i'], step_call=steps, note=n_ok, looked=l_ok))
            last = k

    # scrub, then look for what is left
    leaks, secrets = [], []
    account = home.name
    for ev in events:
        kinds = set()
        for key in ('text', 'result'):
            if key in ev:
                ev[key] = scrub(ev[key], kinds)
        ev['input'] = json.loads(scrub(json.dumps(ev['input'], ensure_ascii=False), kinds)) if 'input' in ev else None
        if ev['input'] is None:
            del ev['input']
        if kinds:
            secrets.append(dict(event=ev['i'], kinds=sorted(kinds)))
        blob = json.dumps(ev, ensure_ascii=False)
        # agent and model names belong in a trajectory (it is a record of that agent at work); the owner's and the
        # tool repos' names do not
        found = {x for x in bffroot.banned_in(blob) if not re.fullmatch(r'(?i)claude|anthropic|openai', x)}
        if len(account) >= 4 and re.search(r'(?i)(?<![a-z0-9])' + re.escape(account) + r'(?![a-z0-9])', blob):
            found.add('the account name')
        found |= set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', blob))
        found |= {f'a secret ({kind})' for kind, rx in SECRETS if rx.search(blob)}
        if found:
            leaks.append(dict(event=ev['i'], found=sorted(found)))

    with open(out / 'trajectory.jsonl', 'w', encoding='utf-8', newline='\n') as f:
        for ev in events:
            f.write(json.dumps(dict(schema='film-trajectory/v1', **ev), ensure_ascii=False) + '\n')
    md = [f'# Trajectory: {film.name}\n']
    for ev in events:
        if ev['type'] == 'user':
            md.append(f"\n---\n\n**[{ev['i']}] Person**\n\n{ev['text']}\n")
        elif ev['type'] == 'assistant':
            md.append(f"\n**[{ev['i']}] Model**\n\n{ev['text']}\n")
        else:
            inp = ev['input']
            head = inp.get('command') or inp.get('file_path') or inp.get('path') or ''
            md.append(f"\n**[{ev['i']}] {ev['tool']}**{' (failed)' if ev['error'] else ''} `{str(head)[:300]}`\n")
            body = inp.get('content') or inp.get('new_string')
            if body:
                md.append('\n```\n' + str(body)[:4000] + '\n```\n')
            if ev.get('image'):
                md.append(f"\n![{ev['image']}]({ev['image']})\n")
            elif ev.get('result'):
                md.append('\n```\n' + ev['result'][:1200] + '\n```\n')
    (out / 'trajectory.md').write_text(''.join(md), encoding='utf-8')
    cov = lambda x: round(x / steps, 3) if steps else None
    analysis = dict(ok=True, film=film.name, sessions=len(sessions), events=len(events),
                    prompts=sum(e['type'] == 'user' for e in events), replies=sum(e['type'] == 'assistant' for e in events),
                    tool_calls=sum(e['type'] == 'tool' for e in events), pictures_opened=sum('image' in e for e in events),
                    pictures_missing=missing_images, step_calls=steps, note_coverage=cov(noted), looked_coverage=cov(looked),
                    weak_steps=weak[:200], leaks=leaks[:200], leak_events=len(leaks), secrets_redacted=len(secrets),
                    secret_events=secrets[:200])
    (out / 'analysis.json').write_text(json.dumps(analysis, indent=1), encoding='utf-8')
    bad = bool(leaks) or missing_images or (steps and (cov(noted) < 0.9 or cov(looked) < 0.9))
    if a.json:
        print(json.dumps(analysis))
    else:
        print(f"{len(events)} events ({analysis['prompts']} prompts, {analysis['replies']} replies, {analysis['tool_calls']} tool calls, "
              f"{analysis['pictures_opened']} pictures opened, {missing_images} missing) from {len(sessions)} session(s)")
        print(f"steps {steps}: a note before {noted} ({cov(noted)}), a picture looked at before {looked} ({cov(looked)})")
        print(f"leaks left in {len(leaks)} event(s)" + (': ' + ', '.join(sorted({x for l in leaks for x in l['found']})[:12]) if leaks else ''))
        print(f"secrets redacted in {len(secrets)} event(s)" + (': ' + ', '.join(sorted({k for s in secrets for k in s['kinds']})) if secrets else ''))
        print(f'{"TRAJECTORY OK" if not bad else "TRAJECTORY NEEDS WORK"}: {out}')
    sys.exit(2 if a.check and bad else 0)


if __name__ == '__main__':
    main()
