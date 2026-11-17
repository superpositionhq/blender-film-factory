"""Wiring of the recording hooks into each agent's settings; used by machine/bootstrap.py and machine/check.py.

Claude Code reads hooks from <claude home>/settings.json. Codex reads them from <codex home>/hooks.json and runs one
only once it is trusted: config.toml holds
    [hooks.state.'<hooks.json path>:<event>:<group index>:<handler index>']
    trusted_hash = "sha256:<hex>"
where <hex> is the SHA-256 of the compact, key-sorted JSON of the hook's normalized identity
    {"event_name": "post_tool_use", "matcher": "*", "hooks": [{"type": "command", "command": "...", "timeout": 60, "async": true}]}
(a missing timeout counts as 600, a missing matcher is left out). An untrusted or changed hook is skipped without an
error, so bootstrap.py writes these entries for the blender-film-factory hooks (and only those) and check.py compares
them. Typing /hooks in Codex shows the same trust state and can trust them by hand. Standard library only.
"""
import hashlib
import json
import re
from pathlib import Path

MINE = re.compile(r'record-film-action\.py')
EVENT_LABELS = {'PreToolUse': 'pre_tool_use', 'PermissionRequest': 'permission_request', 'PostToolUse': 'post_tool_use',
                'PreCompact': 'pre_compact', 'PostCompact': 'post_compact', 'SessionStart': 'session_start',
                'SessionEnd': 'session_end', 'UserPromptSubmit': 'user_prompt_submit', 'SubagentStart': 'subagent_start',
                'SubagentStop': 'subagent_stop', 'Stop': 'stop', 'Interrupt': 'interrupt'}
TRUST_MARKER = ('# blender-film-factory recording hooks (machine/bootstrap.py): trusted so Codex runs them; /hooks in Codex '
                'shows them')
TABLE = re.compile(r'''^\s*\[\s*hooks\.state\.(?:"((?:[^"\\]|\\.)*)"|'([^']*)')\s*\]\s*(#.*)?$''')


def fragment(name, python, hooks_dir):
    """machine/hooks/<name> with {{PYTHON}} and {{HOOKS_DIR}} filled in (forward slashes: every shell reads them)."""
    text = (Path(__file__).resolve().parents[1] / 'hooks' / name).read_text(encoding='utf-8')
    return json.loads(text.replace('{{PYTHON}}', Path(python).as_posix()).replace('{{HOOKS_DIR}}',
                                                                                 Path(hooks_dir).as_posix()))


def read_json(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() and path.read_text(
        encoding='utf-8-sig').strip() else {}


def merge(target, frag, path):
    """Merge a hook fragment into a parsed settings / hooks object: a handler of ours that differs is replaced where
    it stands, a missing one is added as a new group, everything else (other tools' hooks, another factory's
    recording hooks) stays as it was. True when something changed; a file whose "hooks" has another shape raises
    before anything is written."""
    changed = False
    hooks = target.setdefault('hooks', {})
    for ev, groups in frag['hooks'].items():
        if not isinstance(hooks, dict) or not isinstance(hooks.get(ev, []), list):
            raise SystemExit(f'{path}: "hooks" is not an object of lists (at {ev}): nothing was written to it; fix it, '
                             'then run bootstrap again')
        want = groups[0]['hooks'][0]
        found = False
        for g in hooks.get(ev, []):
            hs = g.get('hooks') if isinstance(g, dict) else None
            for i, h in enumerate(hs if isinstance(hs, list) else []):
                if isinstance(h, dict) and MINE.search(str(h.get('command', ''))):
                    if found or h != want:
                        changed = True
                    hs[i] = None if found else dict(want)   # a second copy of ours is dropped
                    found = True
            if isinstance(hs, list) and None in hs:
                g['hooks'] = [h for h in hs if h is not None]
        if not found:
            hooks.setdefault(ev, []).append(json.loads(json.dumps(groups[0])))
            changed = True
    return changed


def remove(target):
    """Take every handler of ours out of a parsed settings / hooks object (a group left empty goes too, an event
    left empty too). Other tools' hooks stay as they are. True when something was removed."""
    hooks = target.get('hooks')
    if not isinstance(hooks, dict):
        return False
    changed = False
    for ev in list(hooks):
        groups = hooks[ev] if isinstance(hooks[ev], list) else []
        for g in groups:
            hs = g.get('hooks') if isinstance(g, dict) else None
            if isinstance(hs, list):
                keep = [h for h in hs if not (isinstance(h, dict) and MINE.search(str(h.get('command', ''))))]
                if len(keep) != len(hs):
                    g['hooks'] = keep
                    changed = True
        left = [g for g in groups if not (isinstance(g, dict) and g.get('hooks') == [])]
        if len(left) != len(groups):
            hooks[ev] = left
        if isinstance(hooks[ev], list) and not hooks[ev]:
            del hooks[ev]
    return changed


def wired(target, frag):
    """The events of the fragment whose handler is not in the settings exactly as the fragment has it."""
    missing = []
    for ev, groups in frag['hooks'].items():
        have = [h for g in (target.get('hooks') or {}).get(ev) or [] if isinstance(g, dict)
                for h in g.get('hooks') or [] if isinstance(h, dict)]
        if groups[0]['hooks'][0] not in have:
            missing.append(ev)
    return missing


# Reasoning summaries: the recording reads them from the session's transcript, and they are only there with these on.
CLAUDE_SUMMARY = {'showThinkingSummaries': True, 'alwaysThinkingEnabled': True}
CODEX_SUMMARY = {'model_reasoning_summary': '"detailed"', 'hide_agent_reasoning': 'false'}   # key -> TOML text


def want_summaries(settings):
    """Turn Claude Code's reasoning summaries on in a parsed settings object. True when something changed."""
    changed = False
    for k, v in CLAUDE_SUMMARY.items():
        if settings.get(k) is not v:
            settings[k] = v
            changed = True
    return changed


def codex_top_level(config_toml):
    """{key: value text} of the top-level keys of a config.toml (the lines before its first table)."""
    p, out = Path(config_toml), {}
    if p.is_file():
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('['):
                break
            m = re.match(r'^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$', line)
            if m:
                out[m[1]] = m[2]
    return out


def set_codex_top_level(config_toml, values):
    """Write top-level keys into config.toml: a key that is there is replaced where it stands, a new one goes before
    the first table. Everything else stays as it is."""
    p = Path(config_toml)
    lines = p.read_text(encoding='utf-8').splitlines() if p.is_file() else []
    first = next((i for i, l in enumerate(lines) if l.strip().startswith('[')), len(lines))
    head, rest, left = lines[:first], lines[first:], dict(values)
    for i, l in enumerate(head):
        m = re.match(r'^\s*([A-Za-z0-9_]+)\s*=', l)
        if m and m[1] in left:
            head[i] = f'{m[1]} = {left.pop(m[1])}'
    head += [f'{k} = {v}' for k, v in left.items()]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('\n'.join(head + rest) + '\n', encoding='utf-8', newline='\n')


def codex_trust(hooks_json, hooks):
    """The trust entries for every command handler of ours in a parsed hooks.json: [(key, hash)]."""
    out = []
    for ev, groups in (hooks.get('hooks') or {}).items():
        label = EVENT_LABELS.get(ev)
        for gi, g in enumerate(groups if label and isinstance(groups, list) else []):
            for hi, h in enumerate(g.get('hooks') or []):
                if h.get('type') != 'command' or not MINE.search(str(h.get('command', ''))):
                    continue
                hd = {'type': 'command', 'command': str(h['command']),
                      'timeout': int(h['timeout']) if h.get('timeout') is not None else 600, 'async': bool(h.get('async'))}
                if h.get('statusMessage'):
                    hd['statusMessage'] = str(h['statusMessage'])
                ident = {'event_name': label, 'hooks': [hd]}
                if g.get('matcher') is not None:
                    ident['matcher'] = str(g['matcher'])
                # JSON as serde_json writes it after sorting: no spaces, keys in byte order, non-ASCII as it is
                canon = json.dumps(ident, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
                out.append((f'{hooks_json}:{label}:{gi}:{hi}', 'sha256:' + hashlib.sha256(canon.encode()).hexdigest()))
    return out


def _key(m):
    return re.sub(r'\\(["\\])', r'\1', m[1]) if m[1] is not None else m[2]


def trust_state(config_toml):
    """hooks.state entries of a config.toml: key -> trusted_hash (a small reader for exactly these tables)."""
    state, key = {}, None
    path = Path(config_toml)
    for line in path.read_text(encoding='utf-8').splitlines() if path.is_file() else []:
        if re.match(r'\s*\[', line):
            m = TABLE.match(line)
            key = _key(m) if m else None
        elif key:
            m = re.match(r'\s*trusted_hash\s*=\s*"([^"]*)"', line)
            if m:
                state[key] = m[1]
    return state


def set_trust_state(config_toml, entries):
    """Write (or replace) the hooks.state tables for `entries` in config.toml; every other line stays as it was."""
    keys = dict(entries)
    path = Path(config_toml)
    out, skip = [], False
    for line in path.read_text(encoding='utf-8').splitlines() if path.is_file() else []:
        if re.match(r'\s*\[', line):
            skip = False
            m = TABLE.match(line)
            if m and _key(m) in keys:
                skip = True
                continue
        if skip or line == TRUST_MARKER:
            continue
        # A key of ours outside a [hooks.state."<key>"] header (a dotted key, an inline table): adding its table again
        # would make the whole file invalid, and Codex then starts without its config.
        for k in keys:
            if f"'{k}'" in line or '"' + k.replace('\\', '\\\\') + '"' in line:
                raise SystemExit(f'{path} holds the trust entry {k} in a form this script does not edit: nothing was '
                                 'written to it; remove that entry, then run bootstrap again')
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    out += ['', TRUST_MARKER]
    for k, h in entries:
        q = f"'{k}'" if "'" not in k else '"' + k.replace('\\', '\\\\').replace('"', '\\"') + '"'
        out += [f'[hooks.state.{q}]', f'trusted_hash = "{h}"']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(out).lstrip('\n') + '\n', encoding='utf-8', newline='\n')
