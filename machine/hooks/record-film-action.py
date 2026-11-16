#!/usr/bin/env python3
"""Agent hook: record a project session's tool calls, prompts and replies, and commit what a turn left behind.

  python record-film-action.py [--agent claude|codex]              PostToolUse / PostToolUseFailure
  python record-film-action.py [--agent claude|codex] --stop       Stop
  python record-film-action.py [--agent claude|codex] --messages   UserPromptSubmit / SessionEnd

Both agents send the same hook JSON on stdin (session_id, transcript_path, cwd, hook_event_name, tool_name,
tool_input, tool_response, tool_use_id). Codex names its shell tool "Bash" and its file edits "apply_patch", and has
no PostToolUseFailure. Every row says which agent made it ("agent").

A session is tied to a project the first time one of its tool calls names a path under <root>/films/<slug> (or
<root>/<extra project>, config "record_extra_projects", default none): in its cwd, a file path or the command text.
After that, all its calls go to <root>/.recording/<slug>/actions.jsonl (schema agent-action/v0). At that first
mapping the session's earlier tool calls are imported once from its transcript, in order, before the mapping call's
own row, with status "from_transcript" (recording-backfill.json beside this file keeps what was imported, so a call
is never written twice).

Prompts and replies go to <root>/.recording/<slug>/messages.jsonl (schema agent-message/v0: time, project,
session_id, agent, role "user" | "assistant", message_id, text; "model"; "images"; "mid_turn" for a prompt typed while
the model was working; "subagent"). They are read from the session's transcript, never twice (recording-messages.json:
transcript file -> bytes read), so a session mapped late gets its earlier messages too. Only when the hook input names
no transcript is the message taken from the input itself (prompt, last_assistant_message). Not recorded: the model's
reasoning, text the agent tool puts into a turn itself, a fork's copied context.

On Stop, leftover changes in the session's project repo are committed as "WIP" so no work stays uncommitted: not
while conflicts are unresolved or HEAD is detached (that commit would hold the conflict markers, or land on no
branch).

Nothing is recorded when BFF_NO_RECORDING is set, or for a session id listed in recording-exclude.txt beside this
file. A hook never fails the agent: every error ends in exit 0.
machine/bootstrap.py installs this into the hooks folder (next to the machine config) and wires it into Claude Code
(~/.claude/settings.json) and Codex (~/.codex/hooks.json, trusted in ~/.codex/config.toml). Standard library only.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
sys.path[:0] = [str(HOOKS), str(HOOKS.parent / 'lib')]
import bffroot  # noqa: E402

MAX_TEXT = 200000   # chars kept per string field of tool_input
MAX_RESP = 8000     # chars kept of the tool response
MAP, BACKFILL, MESSAGES = (HOOKS / n for n in ('recording-sessions.json', 'recording-backfill.json',
                                               'recording-messages.json'))
AGENT = 'claude'


def clip(v, n):
    return v[:n] + f'...[truncated {len(v) - n} chars]' if isinstance(v, str) and len(v) > n else v


def read_map(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def write_map(path, data):
    path.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')


def recorded_ids(path, key='tool_use_id'):
    ids = set()
    if path.is_file():
        rx = re.compile('"' + key + r'":"([^"]+)"')
        with open(path, encoding='utf-8', errors='replace') as f:
            ids = {m[1] for line in f for m in [rx.search(line)] if m}
    return ids


def when(v):
    return datetime.fromisoformat(str(v).replace('Z', '+00:00'))


def local(dt):
    return dt.astimezone().isoformat(timespec='milliseconds')


def born(path):
    """When the transcript file was made (rows older than it are a fork's copied context); 0 where unknown."""
    st = os.stat(path)
    t = getattr(st, 'st_birthtime', st.st_ctime if os.name == 'nt' else 0)
    return t - 5 if t else 0


def text_of(content):
    if isinstance(content, str):
        return content
    return '\n'.join(str(b.get('text', '')) for b in content or [] if isinstance(b, dict) and b.get('type') == 'text')


# ---- the session's earlier tool calls, from its transcript -----------------------------------------------------------
def claude_calls(sid, path):
    """Claude Code: tool_use blocks and their tool_result, in the session's transcript and its subagents' beside it."""
    files = [Path(path)]
    sub = Path(path).parent / sid / 'subagents'
    if sub.is_dir():
        files += sorted(sub.glob('*.jsonl'))
    since, calls, results, n = born(path), {}, {}, 0
    for f in files:
        with open(f, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if '"tool_use"' not in line and '"tool_result"' not in line:
                    continue
                try:
                    o = json.loads(line)
                    ts = when(o['timestamp'])
                except (ValueError, KeyError, TypeError):
                    continue
                if str(o.get('sessionId')) != sid or ts.timestamp() < since:
                    continue
                content = (o.get('message') or {}).get('content')
                for b in content if isinstance(content, list) else []:
                    if b.get('type') == 'tool_use' and b.get('id') not in calls:
                        calls[b['id']] = dict(id=b['id'], name=b.get('name'), input=b.get('input') or {}, ts=ts,
                                              cwd=o.get('cwd'), sub=None if f == files[0] else f.stem, n=n)
                        n += 1
                    elif b.get('type') == 'tool_result':
                        text = text_of(b.get('content'))
                        r = o.get('toolUseResult')
                        resp = json.dumps(r, ensure_ascii=False) if isinstance(r, (dict, list)) else (r or text)
                        results[b.get('tool_use_id')] = dict(resp=resp, error=bool(b.get('is_error')), text=text, ts=ts)
    return calls, results


def codex_calls(sid, path):
    """Codex: the rollout file's completed CommandExecution / FileChange / McpToolCall items (item.id is the
    tool_use_id the hooks see)."""
    since, calls, results, n = born(path), {}, {}, 0
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if '"item_completed"' not in line:
                continue
            try:
                o = json.loads(line)
                p, ts = o['payload'], when(o['timestamp'])
                it = p['item']
            except (ValueError, KeyError, TypeError):
                continue
            if o.get('type') != 'event_msg' or p.get('type') != 'item_completed' or ts.timestamp() < since:
                continue
            if (p.get('thread_id') and str(p['thread_id']) != sid) or not it.get('id') or it['id'] in calls:
                continue
            kind = it.get('type')
            if kind == 'CommandExecution':
                c = [str(x) for x in it.get('command') or []]
                cmd = c[-1] if len(c) >= 3 and c[-2] in ('-lc', '-c', '/c', '-Command', '-NoProfile') else ' '.join(c)
                name, inp, resp = 'Bash', {'command': cmd}, str(it.get('aggregated_output') or '')
                err = it.get('exit_code') not in (None, 0) or it.get('status') == 'failed'
            elif kind == 'FileChange':
                name, inp = 'apply_patch', {'changes': it.get('changes')}
                resp = '\n'.join(x for x in (it.get('stdout'), it.get('stderr')) if x)
                err = it.get('status') != 'completed'
            elif kind == 'McpToolCall':
                name, inp = f"mcp__{it.get('server')}__{it.get('tool')}", it.get('arguments') or {}
                resp = json.dumps(it['result'], ensure_ascii=False) if it.get('result') else str(it.get('error') or '')
                err = bool(it.get('error'))
            else:
                continue   # reasoning, messages, web searches, plans: not tool calls with effects
            cwd = re.sub(r'^file://(/(?=[A-Za-z]:))?', '', str(it['cwd'])) if it.get('cwd') else None
            calls[it['id']] = dict(id=it['id'], name=name, input=inp, ts=ts, cwd=cwd, sub=None, n=n)
            results[it['id']] = dict(resp=resp, error=err, text=resp, ts=ts)
            n += 1
    return calls, results


def backfill_rows(sid, project, path, until, skip):
    """Rows for the calls the session made before the one that mapped it (`until`), oldest first."""
    calls, results = (codex_calls if AGENT == 'codex' else claude_calls)(sid, path)
    stop = calls[until]['ts'] if until in calls else None
    rows, ids = [], []
    for c in sorted(calls.values(), key=lambda c: (c['ts'], c['n'])):
        r = results.get(c['id'])
        if c['id'] == until or c['id'] in skip or not r or (stop and c['ts'] > stop):
            continue
        row = dict(schema='agent-action/v0', time=local(c['ts']), project=project, session_id=sid, agent=AGENT,
                   event='PostToolUseFailure' if r['error'] and AGENT != 'codex' else 'PostToolUse', cwd=c['cwd'],
                   status='from_transcript', tool=c['name'], tool_use_id=c['id'])
        if c['sub']:
            row['subagent'] = c['sub']
        row['input'] = {k: clip(v, MAX_TEXT) for k, v in c['input'].items()} if isinstance(c['input'], dict) else {}
        if r['error']:
            row['error'] = clip(r['text'], MAX_RESP)
        row['response'] = clip(r['resp'], MAX_RESP)
        row['result_time'] = local(r['ts'])
        rows.append(row)
        ids.append(c['id'])
    state = read_map(BACKFILL)
    state[sid] = dict(project=project, time=bffroot.now(), transcript=str(path), rows=len(rows), tool_use_ids=ids)
    return rows, state


# ---- prompts and replies: messages.jsonl ------------------------------------------------------------------------------
def tail(path, start):
    """The complete lines a file gained after byte `start`, and where they end."""
    with open(path, 'rb') as f:
        size = f.seek(0, 2)
        if start > size:
            start = 0   # a shorter file took its place
        f.seek(start)
        buf = f.read(256 * 2 ** 20)
    end = buf.rfind(b'\n')
    if end < 0:
        return [], start
    return buf[:end].decode('utf-8', 'replace').split('\n'), start + end + 1


def claude_messages(sid, lines, since):
    """A "user" row holding text or a picture is a prompt (a tool result holds neither), an "assistant" row's text
    blocks are a reply. A prompt typed while the model was working is an "attachment" row of type queued_command."""
    for line in lines:
        if '"sessionId"' not in line or '"toolUseResult"' in line:
            continue
        if len(line) > 100000:   # a pasted picture is megabytes of base64: counted by its block, never parsed
            line = re.sub(r'"data":"[A-Za-z0-9+/=]{2000,}"', '"data":""', line)
        try:
            o = json.loads(line)
            ts = when(o['timestamp'])
        except (ValueError, KeyError, TypeError):
            continue
        if str(o.get('sessionId')) != sid or not o.get('uuid') or ts.timestamp() < since:
            continue
        human = lambda x: not isinstance(x.get('origin'), dict) or x['origin'].get('kind') == 'human'
        if o.get('type') == 'attachment':
            a = o.get('attachment') or {}
            if a.get('type') != 'queued_command' or not human(a) or a.get('commandMode', 'prompt') != 'prompt':
                continue
            text = text_of(a.get('prompt'))
            if text.strip():
                yield dict(id=o['uuid'], role='user', ts=ts, text=text, mid=True)
            continue
        role = o.get('type')
        if role not in ('user', 'assistant') or not human(o):
            continue
        if o.get('isMeta') or o.get('isCompactSummary') or o.get('isApiErrorMessage'):
            continue
        content = (o.get('message') or {}).get('content')
        images = sum(1 for b in content if isinstance(b, dict) and b.get('type') == 'image') \
            if isinstance(content, list) else 0
        text = text_of(content)
        if text.strip() or images:
            yield dict(id=o['uuid'], role=role, ts=ts, text=text, images=images,
                       model=(o.get('message') or {}).get('model') if role == 'assistant' else None)


def codex_messages(sid, lines, since):
    """The rollout's finished UserMessage and AgentMessage items (item.id is the message's id)."""
    for line in lines:
        if '"item_completed"' not in line or not re.search(r'"(?:UserMessage|AgentMessage)"', line):
            continue
        try:
            o = json.loads(line)
            p, ts = o['payload'], when(o['timestamp'])
            it = p['item']
        except (ValueError, KeyError, TypeError):
            continue
        role = {'UserMessage': 'user', 'AgentMessage': 'assistant'}.get(it.get('type'))
        if not role or not it.get('id') or ts.timestamp() < since:
            continue
        if p.get('thread_id') and str(p['thread_id']) != sid:
            continue
        blocks = [b for b in it.get('content') or [] if isinstance(b, dict)]
        text = '\n'.join(str(b['text']) for b in blocks if b.get('text'))
        images = sum(1 for b in blocks if not b.get('text') and 'image' in str(b.get('type', '')).lower())
        if text.strip() or images:
            yield dict(id=it['id'], role=role, ts=ts, text=text, images=images, phase=it.get('phase'))


def find_transcript(sid):
    if AGENT == 'codex':
        home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'sessions'
        found = sorted(home.rglob(f'rollout-*{sid}*.jsonl')) if home.is_dir() else []
    else:
        home = Path.home() / '.claude' / 'projects'
        found = sorted(home.rglob(f'{sid}.jsonl')) if home.is_dir() else []
    return found[0] if found else None


def sync_messages(sid, project, path, read):
    """Append to messages.jsonl what the session's transcript (and, Claude Code, its subagents' transcripts) gained
    since the last read. `read` collects the session's own messages as (role, text). False without a transcript."""
    path = Path(path) if path else find_transcript(sid)
    if not path or not path.is_file():
        return False   # a session's first prompt comes before its transcript
    files = [path]
    sub = path.parent / sid / 'subagents'
    if AGENT != 'codex' and sub.is_dir():
        files += sorted(sub.glob('*.jsonl'))
    since, state, out = born(path), read_map(MESSAGES), bffroot.root() / '.recording' / project / 'messages.jsonl'
    seen, rows, moved = None, [], False
    for f in files:
        start = int(state.get(str(f), 0))
        lines, nxt = tail(f, start)
        if nxt == start:
            continue
        state[str(f)], moved = nxt, True
        if (nxt < start or start == 0) and seen is None:   # read from its start: never write a message twice
            seen = recorded_ids(out, 'message_id')
        for m in (codex_messages if AGENT == 'codex' else claude_messages)(sid, lines, since):
            if f == path:
                read.append((m['role'], m['text']))
            if seen is not None:
                if m['id'] in seen:
                    continue
                seen.add(m['id'])
            row = dict(schema='agent-message/v0', time=local(m['ts']), project=project, session_id=sid, agent=AGENT,
                       role=m['role'], message_id=m['id'])
            if f != path:
                row['subagent'] = f.stem
            for k, name in (('model', 'model'), ('phase', 'phase'), ('images', 'images'), ('mid', 'mid_turn')):
                if m.get(k):
                    row[name] = m[k]
            row['text'] = clip(m['text'], MAX_TEXT)
            rows.append(row)
    if rows:
        bffroot.append_jsonl(out, rows)
    if moved:
        write_map(MESSAGES, state)
    return True


def was_read(read, role, text):
    """Is the message this call is about among those read? The transcript may hold it with other text around it."""
    want = ' '.join(text.split())
    if not want:
        return True
    return any(r == role and have and (have == want or have in want or want in have)
               for r, t in read for have in [' '.join(t.split())])


# ---- Stop: commit what the turn left behind ---------------------------------------------------------------------------
def git(repo, *args):
    r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    return r.returncode, r.stdout.strip()


def wip_commit(repo, lock):
    """Returns the row's auto_commit value (None: clean tree), or ... when no commit was made or tried."""
    if not (repo / '.git').exists() or (repo / '.git' / 'index.lock').exists():
        return ...
    dirty = [l for l in git(repo, 'status', '--porcelain')[1].splitlines() if l.strip()]
    if any(re.match(r'(DD|AU|UD|UA|DU|AA|UU) ', l) for l in dirty) or git(repo, 'symbolic-ref', '-q', 'HEAD')[0]:
        return ...   # a merge, a rebase or a bisect under way: left for the session to finish
    if not dirty:
        return None
    before = git(repo, 'rev-parse', '-q', '--verify', 'HEAD')[1]
    git(repo, 'add', '-A')
    lock.release()   # the commit's post-commit hook (record-film-commit.py) takes the same lock
    made = git(repo, 'commit', '-q', '-m', 'WIP')[0] == 0
    lock.acquire()
    # the WIP commit is the one whose parent is the HEAD before it, not HEAD: while the lock was free another
    # session's commit could land on top of it
    for line in git(repo, 'rev-list', '--parents', '-n', '10', 'HEAD')[1].splitlines():
        sha, *parents = line.split()
        if made and parents[:1] == [before] and git(repo, 'log', '-1', '--format=%s', sha)[1] == 'WIP':
            return {'sha': sha, 'files': len(dirty)}
    return ...


def main():
    global AGENT
    args = sys.argv[1:]
    stop, messages = '--stop' in args, '--messages' in args
    if '--agent' in args:
        AGENT = args[args.index('--agent') + 1]
    if os.environ.get('BFF_NO_RECORDING'):
        return
    raw = sys.stdin.buffer.read().decode('utf-8', 'replace')
    if not raw.strip():
        return
    e = json.loads(raw)
    sid = str(e.get('session_id') or '')
    exclude = HOOKS / 'recording-exclude.txt'
    if not sid or (exclude.is_file() and sid in exclude.read_text(encoding='utf-8').split()):
        return
    cfg, root = bffroot.config(), bffroot.root()
    extra = [re.escape(str(x)) for x in cfg.get('record_extra_projects') or []]
    project_rx = re.compile(bffroot.root_pattern(root) + r'[\\/]+(?:films[\\/]+([A-Za-z0-9_-]+)'
                            + (f"|({'|'.join(extra)})(?![A-Za-z0-9_-])" if extra else '') + ')')
    inp = e.get('tool_input') if isinstance(e.get('tool_input'), dict) else {}
    transcript = e.get('transcript_path')

    with bffroot.Lock() as lock:
        smap = read_map(MAP)
        # which project does this call name?
        texts = [str(e.get('cwd') or '')] + [str(inp[k]) for k in ('file_path', 'path', 'notebook_path', 'command',
                                                                    'cwd') if inp.get(k)]
        named = next((m[1] or m[2] for t in texts for m in [project_rx.search(t)] if m), None)
        newly = bool(named) and sid not in smap
        if newly:
            smap[sid] = named
            write_map(MAP, smap)
        if sid not in smap:
            return
        project = smap[sid]
        actions = root / '.recording' / project / 'actions.jsonl'

        # first mapping: the session's earlier calls from its transcript, before this call's own row
        if newly and not stop and transcript and Path(transcript).is_file() and sid not in read_map(BACKFILL):
            try:
                rows, state = backfill_rows(sid, project, transcript, str(e.get('tool_use_id') or ''),
                                            recorded_ids(actions))
                bffroot.append_jsonl(actions, rows)
                write_map(BACKFILL, state)
            except Exception:   # never lose the live row over a transcript problem
                pass
        # the session's prompts and replies (never at the cost of the row)
        if stop or messages:
            try:
                role = 'assistant' if stop else 'user'
                text = str(e.get('last_assistant_message' if stop else 'prompt') or '')
                read = []
                have = sync_messages(sid, project, transcript, read)
                # the message this call is about may reach the transcript a moment after the hook starts
                for _ in range(7):
                    if not have or was_read(read, role, text):
                        break
                    time.sleep(0.3)
                    sync_messages(sid, project, transcript, read)
                if not have and text.strip():   # no transcript to read: the hook input's own copy
                    mid = 'hook-' + hashlib.sha1(f'{sid}{role}{text}{time.time()}'.encode()).hexdigest()[:16]
                    bffroot.append_jsonl(actions.with_name('messages.jsonl'), [dict(
                        schema='agent-message/v0', time=bffroot.now(), project=project, session_id=sid, agent=AGENT,
                        role=role, message_id=mid, text=clip(text, MAX_TEXT))])
            except Exception:
                pass
            if messages:
                return   # UserPromptSubmit, SessionEnd: no row in actions.jsonl
        # a call already imported from the transcript is not written twice
        if e.get('tool_use_id') and e['tool_use_id'] in (read_map(BACKFILL).get(sid) or {}).get('tool_use_ids', []):
            return

        row = dict(schema='agent-action/v0', time=bffroot.now(), project=project, session_id=sid, agent=AGENT,
                   event=str(e.get('hook_event_name') or ''), cwd=str(e.get('cwd') or ''))
        if stop:
            row['event'] = 'Stop'
            made = wip_commit(root / 'films' / project, lock)
            if made is not ...:
                row['auto_commit'] = made
        else:
            row['tool'] = str(e.get('tool_name') or '')
            row['tool_use_id'] = str(e.get('tool_use_id') or '')
            row['input'] = {k: clip(v, MAX_TEXT) for k, v in inp.items()}
            if e.get('error'):
                row['error'] = clip(str(e['error']), MAX_RESP)
            resp = e.get('tool_response')
            row['response'] = clip(resp if isinstance(resp, str) or resp is None
                                   else json.dumps(resp, ensure_ascii=False, separators=(',', ':')), MAX_RESP)
        bffroot.append_jsonl(actions, [row])


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
