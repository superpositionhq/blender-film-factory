"""Runs inside Blender (tools/replay.py): execute every step script of build/order.txt in one process, save.

  blender -b --factory-startup --python replay.py -- <film> <out.blend>
The work file is saved inside the film folder first so that relative paths (//textures/...) resolve as they did
when the steps were recorded; it is removed at the end.
"""
import os
import sys

import bpy

film, out = sys.argv[sys.argv.index('--') + 1:][:2]
work = os.path.join(film, '_replay_work.blend')
bpy.ops.wm.save_as_mainfile(filepath=work)
try:
    for line in open(os.path.join(film, 'build', 'order.txt'), encoding='utf-8'):
        rel = line.strip()
        if not rel:
            continue
        path = os.path.join(film, rel)
        print('REPLAY', rel, flush=True)
        exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), {'__name__': '__main__', '__file__': path})
    bpy.ops.wm.save_as_mainfile(filepath=out)
finally:
    for junk in (work, work + '1'):
        if os.path.exists(junk):
            os.remove(junk)
