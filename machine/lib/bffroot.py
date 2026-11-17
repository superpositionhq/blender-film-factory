"""Machine root and config for every Python tool and hook of blender-film-factory. Standard library only.

Root order: env BFF_ROOT, then "root" in the config file, then ~/FilmWork.
Config file order: env BFF_CONFIG, then config.json beside the hooks folder this file was installed into
(<config dir>/hooks/bffroot.py -> <config dir>/config.json), then ~/.blender-film-factory/config.json.

Use from a script in the repo:
    sys.path.insert(0, str(<blender-film-factory>/machine/lib)); import bffroot; bffroot.root()
"""
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Names that never appear inside a project (code, comments, docs, commit messages, workflow rows, builds): the owner,
# the tool repos, the agents and their makers. The project-session skill, "Names".
BANNED = (r'(?i)superposition', r'(?i)game[-_ ]?factory', r'(?i)(?:three(?:\.?js)?|blender[-_ ]?film|film)[-_ ]?factory', r'(?i)\banthropic\b',
          r'(?i)\bclaude\b', r'(?i)\bopenai\b')


def config_path():
    if os.environ.get('BFF_CONFIG'):
        return Path(os.environ['BFF_CONFIG'])
    beside = HERE.parent / 'config.json'   # an installed copy: <config dir>/hooks/bffroot.py
    if HERE.name == 'hooks' and beside.is_file():
        return beside
    return Path.home() / '.blender-film-factory' / 'config.json'


def config():
    p = config_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding='utf-8-sig'))
        except ValueError as e:   # a Windows path typed with single backslashes is the usual cause
            sys.exit(f'{p} is not valid JSON ({e}): write a Windows path in it with doubled backslashes or forward '
                     'slashes')
    return {}


def root():
    if os.environ.get('BFF_ROOT'):
        return Path(os.environ['BFF_ROOT']).absolute()
    r = config().get('root')
    return Path(r).absolute() if r else Path.home() / 'FilmWork'


def hooks_dir():
    """Where bootstrap.py installs the recording hooks and where they keep their state: next to the config file."""
    return config_path().parent / 'hooks'


def repo():
    """The blender-film-factory checkout: "repo" in the config (bootstrap.py writes it), else <root>/blender-film-factory."""
    r = config().get('repo')
    return Path(r) if r else root() / 'blender-film-factory'


def org():
    """GitHub organisation (or user) owning the film-<slug> repos: env BFF_ORG, else "github_org" in the config."""
    return (os.environ.get('BFF_ORG') or config().get('github_org') or '').strip()


def blender():
    """The Blender executable: env BLENDER, else "blender" in the config (bootstrap.py finds and writes it), else the
    usual install places, else `blender` on PATH. None when there is none."""
    import shutil
    cands = [os.environ.get('BLENDER'), config().get('blender'), '/Applications/Blender.app/Contents/MacOS/Blender']
    for base in (os.environ.get('ProgramFiles'), os.environ.get('ProgramW6432')):
        if base and (Path(base) / 'Blender Foundation').is_dir():
            cands += [str(p) for p in sorted((Path(base) / 'Blender Foundation').glob('Blender */blender.exe'), reverse=True)]
    cands.append(shutil.which('blender'))
    for c in cands:
        if c and Path(c).is_file():
            return str(c)
    return None


def ffmpeg(name='ffmpeg'):
    """ffmpeg or ffprobe: "ffmpeg_dir" in the config, else PATH. None when missing."""
    import shutil
    d = config().get('ffmpeg_dir')
    if d:
        for n in (name, name + '.exe'):
            if (Path(d) / n).is_file():
                return str(Path(d) / n)
    return shutil.which(name)


def root_pattern(r=None):
    """A regex that finds the root in a command line or a path, however it is spelled: either slash, any case on
    Windows, C:\\..., /c/... (Git Bash) or /mnt/c/... there, and on macOS both /tmp/... and /private/tmp/..."""
    spell = {str(Path(r or root()).absolute())}
    try:
        spell.add(str(Path(r or root()).resolve()))
    except OSError:
        pass
    alts = []
    for full in sorted(spell):
        m = re.match(r'^([A-Za-z]):[\\/]*(.*)$', full)
        if m:   # Windows
            parts = [re.escape(p) for p in re.split(r'[\\/]+', m[2]) if p]
            alts.append(rf'(?<![\w.-])(?:{m[1]}:|/{m[1]}|/mnt/{m[1]})' + ''.join(r'[\\/]+' + p for p in parts))
        else:
            parts = [re.escape(p) for p in full.split('/') if p]
            alts.append(r'(?<![\w.-])' + ''.join('/+' + p for p in parts))
    return ('(?i)' if os.name == 'nt' else '') + '(?:' + '|'.join(alts) + ')'


def banned_in(text):
    """The banned names a text holds, as written there."""
    return sorted({m.group(0) for p in BANNED for m in re.finditer(p, text or '')})


class Lock:
    """One lock for every writer of this factory's recording (both agents' hooks, the commit recorder): a lock file
    in the hooks folder. Waits up to `wait` seconds, then goes on without it (a row late is better than a row lost);
    a lock file older than a minute was left by a killed hook and is taken over."""

    def __init__(self, wait=30):
        self.path, self.wait, self.held = hooks_dir() / 'recording.lock', wait, False

    def acquire(self):
        end = time.time() + self.wait
        while not self.held:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                self.held = True
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 60:
                        self.path.unlink()
                        continue
                except OSError:
                    continue
                if time.time() > end:
                    break
                time.sleep(0.05)
            except OSError:
                break
        return self.held

    def release(self):
        if self.held:
            self.held = False
            try:
                self.path.unlink()
            except OSError:
                pass

    __enter__ = lambda self: (self.acquire(), self)[1]
    __exit__ = lambda self, *a: self.release()


def now():
    """Local time, ISO 8601 with milliseconds and offset: 2026-01-31T14:05:09.123+01:00."""
    t = time.time()
    lt = time.localtime(t)
    off = lt.tm_gmtoff
    sign = '+' if off >= 0 else '-'
    return (time.strftime('%Y-%m-%dT%H:%M:%S', lt) + f'.{int(t % 1 * 1000):03d}'
            + f'{sign}{abs(off) // 3600:02d}:{abs(off) % 3600 // 60:02d}')


def append_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, separators=(',', ':'))) + '\n')
