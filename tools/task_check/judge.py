"""Ask a vision judge the judge items of a task. The judge is a command on this machine, named in the environment:

  BFF_JUDGE="python3 /path/to/judge-adapter.py"

For every judge item the command gets one JSON request on stdin and prints one JSON answer:

  in:  {"question": "...", "type": "binary" | "gradient", "levels": {"1": "...", "0.75": "...", ...}, "pictures": [paths]}
  out: {"answer": 0..1, "reason": "one sentence"}

The judge sees the question and the pictures only: not the instruction, not the other items, not which scene it is.
Which model answers is the machine's business; nothing here knows. No command set = no judge (answers from a file).
"""
import json
import os
import shlex
import subprocess
from pathlib import Path


def command():
    line = os.environ.get('BFF_JUDGE', '').strip()
    return shlex.split(line, posix=os.name != 'nt') if line else None


def ask(task, work, shots, have=None):
    """Answers for the judge items of one measured scene: ({id: 0..1}, {id: reason}). `shots` is the probe's
    {shot id: file name} and `work` the folder they are in. Items already in `have` are not asked again."""
    cmd = command()
    answers, reasons = dict(have or {}), {}
    if not cmd:
        return answers, reasons
    for i in task['items']:
        if 'judge' not in i or i['id'] in answers:
            continue
        j = i['judge']
        pictures = [str(Path(work) / shots[f"{i['id']}_{n}"]) for n in range(1, len(j['shots']) + 1) if f"{i['id']}_{n}" in shots]
        if not pictures:
            reasons[i['id']] = 'no picture was rendered'
            continue
        request = dict(question=j['question'], type=i.get('type', 'binary'), levels=j.get('levels'), pictures=pictures)
        try:
            r = subprocess.run(cmd, input=json.dumps(request), capture_output=True, text=True, encoding='utf-8', timeout=180)
            reply = json.loads(r.stdout.strip().splitlines()[-1])
            answers[i['id']] = max(0.0, min(1.0, float(reply['answer'])))
            reasons[i['id']] = str(reply.get('reason', ''))[:400]
        except Exception as e:                    # a judge that fails leaves the item waiting: never a guessed score
            reasons[i['id']] = f'the judge did not answer: {type(e).__name__}: {e}'[:400]
    return answers, reasons
