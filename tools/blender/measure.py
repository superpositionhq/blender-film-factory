"""Runs inside Blender (tools/shots.py, tools/replay.py). Read-only.

  blender -b scene.blend --python measure.py -- shots <subjects json> <out json>
  blender -b scene.blend --python measure.py -- state <out json>
shots: per shot (marker with a camera .. next marker) the camera's path sampled on every frame, and for the
subject named for that shot its projected height, whether its centre is in frame, and the camera pitch towards it.
state: object names, types, world matrices and visibility at 5 frames per shot, triangle counts, used materials.
"""
import json
import math
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
sc = bpy.context.scene
marks = sorted((m for m in sc.timeline_markers if m.camera), key=lambda m: m.frame)
ends = [m.frame - 1 for m in marks[1:]] + [sc.frame_end]


def bbox_world(ob):
    """The eight corners of the world-space box around an object and everything parented under it (a mannequin's
    root is an empty: its box is the box of its parts)."""
    pts = []
    for o in [ob] + list(ob.children_recursive):
        if o.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        pts = [ob.matrix_world.translation.copy()]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


if argv[0] == 'shots':
    subjects = json.load(open(argv[1], encoding='utf-8'))
    res = []
    for k, (mk, end) in enumerate(zip(marks, ends), 1):
        cam = mk.camera
        subj = sc.objects.get(subjects.get(str(k)) or '')
        pos, fwd, lens, inframe, heights, pitch, dist = [], [], [], 0, [], [], []
        for f in range(mk.frame, end + 1):
            sc.frame_set(f)
            M = cam.matrix_world
            pos.append(M.translation.copy())
            fwd.append((M.to_quaternion() @ Vector((0, 0, -1))).normalized())
            lens.append(cam.data.lens)
            if subj:
                corners = bbox_world(subj)
                cen = sum(corners, Vector()) / 8
                co = world_to_camera_view(sc, cam, cen)
                inframe += 0 <= co.x <= 1 and 0 <= co.y <= 1 and co.z > 0
                ys = [world_to_camera_view(sc, cam, c).y for c in corners]
                heights.append(max(ys) - min(ys))
                d = cen - M.translation
                dist.append(d.length)
                pitch.append(math.degrees(math.asin(max(-1, min(1, -d.normalized().z)))))
        n = end - mk.frame + 1
        f0 = fwd[0]
        right = f0.cross(Vector((0, 0, 1)))
        right = right.normalized() if right.length > 1e-6 else Vector((1, 0, 0))
        up = right.cross(f0)
        move = pos[-1] - pos[0]
        yaw = [math.degrees(math.atan2(v.y, v.x)) for v in fwd]
        tilt = [math.degrees(math.asin(max(-1, min(1, v.z)))) for v in fwd]
        dyaw = 0.0
        for a, b in zip(yaw[:-1], yaw[1:]):
            dyaw += (b - a + 180) % 360 - 180
        steps = [(b - a) for a, b in zip(pos[:-1], pos[1:])]
        # direction reversals of the frame-to-frame motion: a hand-held camera wobbles, a dolly does not
        rev = sum(1 for a, b in zip(steps[:-1], steps[1:]) if a.length > 1e-6 and b.length > 1e-6 and a.dot(b) < 0)
        swept = 0.0
        if subj and len(pos) > 1:
            sc.frame_set((mk.frame + end) // 2)
            c = sum(bbox_world(subj), Vector()) / 8
            a0, a1 = pos[0] - c, pos[-1] - c
            a0.z = a1.z = 0
            if a0.length > 1e-6 and a1.length > 1e-6:
                swept = math.degrees(a0.angle(a1))
        jump = max((s.length for s in steps), default=0.0)
        res.append(dict(
            shot=k, camera=cam.name, marker=mk.name, frame_start=mk.frame, frame_end=end, frames=n,
            subject=subj.name if subj else None, subject_found=bool(subj),
            subject_figure=bool(subj and subj.get('figure', subj.get('mannequin'))),
            move_along_view=round(move.dot(f0), 4), move_sideways=round(move.dot(right), 4),
            move_vertical=round(move.z, 4), path_length=round(sum(s.length for s in steps), 4),
            largest_step=round(jump, 4), reversals=rev,
            yaw_deg=round(dyaw, 3), tilt_deg=round(tilt[-1] - tilt[0], 3), lens_start=lens[0], lens_end=lens[-1],
            orbit_swept_deg=round(swept, 2),
            subject_distance=round(sum(dist) / len(dist), 4) if dist else None,
            subject_distance_change=round((dist[-1] - dist[0]) / dist[0], 4) if dist and dist[0] > 1e-6 else None,
            subject_height_mid=round(heights[len(heights) // 2], 4) if heights else None,
            subject_in_frame=round(inframe / n, 4) if subj else None,
            pitch_down_deg_mid=round(pitch[len(pitch) // 2], 2) if pitch else None,
            dof=bool(cam.data.dof.use_dof)))
    json.dump(dict(fps=sc.render.fps / sc.render.fps_base, frame_start=sc.frame_start, frame_end=sc.frame_end, shots=res),
              open(argv[2], 'w', encoding='utf-8'), indent=1)

elif argv[0] == 'state':
    frames = []
    for mk, end in zip(marks, ends):
        a, b = mk.frame, end
        frames += [a, a + (b - a) // 4, a + (b - a) // 2, a + 3 * (b - a) // 4, b]
    if not frames:
        frames = [sc.frame_start, sc.frame_end]
    state = {'frames': frames, 'objects': {}, 'materials': sorted(m.name for m in bpy.data.materials if m.users),
             'markers': [[m.frame, m.name, m.camera.name] for m in marks],
             'range': [sc.frame_start, sc.frame_end], 'fps': sc.render.fps / sc.render.fps_base,
             'resolution': [sc.render.resolution_x, sc.render.resolution_y]}
    for f in frames:
        sc.frame_set(f)
        deps = bpy.context.evaluated_depsgraph_get()
        for ob in sc.objects:
            row = state['objects'].setdefault(ob.name, {'type': ob.type, 'm': {}, 'hide': {}})
            row['m'][str(f)] = [round(v, 5) for r in ob.matrix_world for v in r]
            row['hide'][str(f)] = ob.hide_render
            if ob.type == 'MESH' and 'tris' not in row:
                ev = ob.evaluated_get(deps)
                me = ev.to_mesh()
                me.calc_loop_triangles()
                row['tris'] = len(me.loop_triangles)
                ev.to_mesh_clear()
    json.dump(state, open(argv[1], 'w', encoding='utf-8'))
