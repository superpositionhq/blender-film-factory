"""Runs inside Blender, started by tools/task_check. Read-only: measures a saved scene and renders judge pictures.

  blender -b <scene.blend> --python task_probe.py -- <queries.json> <out.json> [<pictures dir>]

queries.json: {"exclude": [names], "queries": [{"id": .., "probe": .., ...}], "shots": [{"id": .., "frame": .., "camera": ..}]}
out.json:     {"blender": .., "objects": [names], "rows": {id: [row, ..]}, "errors": {id: text}, "shots": {id: file}}

Every probe returns a list of rows (dicts of plain numbers, strings and lists). The checker reduces them to one
value; nothing is judged here. "exclude" is the object names of the task's start scene: a selector with
"new": true picks only objects that are not in it. docs/task-probes.md lists the probes and their fields.
"""
import colorsys
import fnmatch
import json
import math
import os
import re
import sys
import traceback

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
spec = json.load(open(argv[0], encoding='utf-8'))
out_path = argv[1]
pic_dir = argv[2] if len(argv) > 2 else None
sc = bpy.context.scene
EXCLUDE = {o.name for o in sc.objects} if spec.get('exclude') == 'self' else set(spec.get('exclude') or [])
SOLID = ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META')
DEFAULT_NAME = re.compile(r'^(Cube|Sphere|Cylinder|Cone|Plane|Torus|Suzanne|Icosphere|Circle|Grid|Empty|Light|Camera|'
                          r'Point|Sun|Spot|Area|Text|BezierCurve|Material)(\.\d{3})?$')


def r5(x):
    return round(float(x), 5)


def vec(v):
    return [r5(x) for x in v]


def family(ob):
    return [ob] + list(ob.children_recursive)


def box(ob):
    """World-space box (lo, hi) around an object and everything parented under it."""
    pts = []
    for o in family(ob):
        if o.type in SOLID:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        pts = [ob.matrix_world.translation.copy()]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def corners(lo, hi):
    return [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


def point_of(p):
    """A point given as [x, y, z] or as an object name (the centre of its box)."""
    if isinstance(p, str):
        ob = sc.objects.get(p)
        if not ob:
            raise ValueError(f'no object named {p!r}')
        lo, hi = box(ob)
        return (lo + hi) / 2
    return Vector(p)


def pick(sel):
    """Objects a selector names. Keys (all that are given must hold): name, glob, type, prop, new, near."""
    if isinstance(sel, str):
        sel = {'name': sel}
    sel = sel or {}
    obs = sorted(sc.objects, key=lambda o: o.name)
    if 'name' in sel:
        names = sel['name'] if isinstance(sel['name'], list) else [sel['name']]
        obs = [o for o in obs if o.name in names]
    if 'glob' in sel:
        obs = [o for o in obs if fnmatch.fnmatchcase(o.name, sel['glob'])]
    if 'type' in sel:
        types = sel['type'] if isinstance(sel['type'], list) else [sel['type']]
        obs = [o for o in obs if o.type in types]
    if 'prop' in sel:
        obs = [o for o in obs if sel['prop'] in o.keys()]
    if sel.get('new'):
        obs = [o for o in obs if o.name not in EXCLUDE]
    if sel.get('top_level'):
        obs = [o for o in obs if o.parent is None]
    if 'near' in sel:
        c, rad = point_of(sel['near']['point']), float(sel['near'].get('radius', 1.0))
        keep = []
        for o in obs:
            lo, hi = box(o)
            if ((lo + hi) / 2 - c).length <= rad:
                keep.append(o)
        obs = keep
    return obs


def frames_of(q):
    if 'frames' in q:
        f = q['frames']
        if isinstance(f, dict):
            return list(range(int(f['from']), int(f['to']) + 1, int(f.get('step', 1))))
        return [int(x) for x in f]
    return [int(q.get('frame', sc.frame_start))]


def shot_list():
    marks = sorted((m for m in sc.timeline_markers if m.camera), key=lambda m: m.frame)
    ends = [m.frame - 1 for m in marks[1:]] + [sc.frame_end]
    return [dict(shot=k, marker=m.name, camera=m.camera.name, frame_start=m.frame, frame_end=e, frames=e - m.frame + 1)
            for k, (m, e) in enumerate(zip(marks, ends), 1)]


def camera_of(q, frame=None):
    """The camera a query names: an object name, {"shot": k}, or the camera the timeline shows at that frame."""
    c = q.get('camera')
    if isinstance(c, str):
        ob = sc.objects.get(c)
        if not ob or ob.type != 'CAMERA':
            raise ValueError(f'no camera named {c!r}')
        return ob
    shots = shot_list()
    if isinstance(c, dict) and 'shot' in c:
        hit = [s for s in shots if s['shot'] == int(c['shot'])]
        if not hit:
            raise ValueError(f'no shot {c["shot"]}')
        return sc.objects[hit[0]['camera']]
    if frame is not None:
        hit = [s for s in shots if s['frame_start'] <= frame <= s['frame_end']]
        if hit:
            return sc.objects[hit[0]['camera']]
    if not sc.camera:
        raise ValueError('the scene has no camera')
    return sc.camera


def principled(mat):
    if not mat or not mat.node_tree:
        return None
    return next((n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)


def socket(node, *names):
    for n in names:
        s = node.inputs.get(n)
        if s is not None:
            return s
    return None


def material_row(mat):
    row = {'material': mat.name, 'default_name': bool(DEFAULT_NAME.match(mat.name)), 'nodes': 0, 'principled': False,
           'image_textures': 0, 'procedural_textures': 0}
    if not mat.node_tree:
        col = list(mat.diffuse_color)[:3]
        row.update(base_color=vec(col), base_color_linked=False)
    else:
        ids = [n.bl_idname for n in mat.node_tree.nodes]
        row['nodes'] = len(ids)
        row['image_textures'] = ids.count('ShaderNodeTexImage')
        row['procedural_textures'] = sum(1 for i in ids if i.startswith('ShaderNodeTex') and i != 'ShaderNodeTexImage')
        row['node_types'] = sorted(set(ids))
        p = principled(mat)
        if p:
            row['principled'] = True
            bc = socket(p, 'Base Color')
            row.update(base_color=vec(list(bc.default_value)[:3]), base_color_linked=bool(bc.is_linked))
            for key, names in (('roughness', ('Roughness',)), ('metallic', ('Metallic',)), ('alpha', ('Alpha',)),
                               ('emission_strength', ('Emission Strength',)),
                               ('transmission', ('Transmission Weight', 'Transmission'))):
                s = socket(p, *names)
                if s is not None:
                    row[key] = r5(s.default_value)
                    row[key + '_linked'] = bool(s.is_linked)
    if 'base_color' in row:
        h, s, v = colorsys.rgb_to_hsv(*[max(0.0, min(1.0, c)) for c in row['base_color']])
        row.update(hue_deg=r5(h * 360), saturation=r5(s), value=r5(v))
    return row


def ray_gap_below(ob):
    """Height of the bottom of an object's box above the nearest surface under its centre that is not part of
    it: 0 when it stands on something, positive when it hovers, negative when it has sunk in. None when nothing
    is below it. The object is hidden from the ray while it is cast (nothing is saved)."""
    fam = family(ob)
    lo, hi = box(ob)
    keep = [o.hide_viewport for o in fam]
    try:
        for o in fam:
            o.hide_viewport = True
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        origin = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, (lo.z + hi.z) / 2))
        hit, loc, _n, _i, _hob, _m = sc.ray_cast(deps, origin, Vector((0, 0, -1)))
    finally:
        for o, h in zip(fam, keep):
            o.hide_viewport = h
        bpy.context.view_layer.update()
    return r5(lo.z - loc.z) if hit else None


def occluded(cam, ob, target):
    """True when the first surface between the camera and a point of an object belongs to something else."""
    deps = bpy.context.evaluated_depsgraph_get()
    own = {o.name for o in family(ob)}
    start = cam.matrix_world.translation
    d = target - start
    dist = d.length
    if dist < 1e-6:
        return False
    hit, loc, _n, _i, hob, _m = sc.ray_cast(deps, start, d.normalized(), distance=dist - 1e-3)
    return bool(hit and hob.name not in own)


# ---------------------------------------------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------------------------------------------

def p_object(q):
    rows = []
    obs = pick(q.get('select'))
    for f in frames_of(q):
        sc.frame_set(f)
        deps = bpy.context.evaluated_depsgraph_get()
        for ob in obs:
            lo, hi = box(ob)
            tris = verts = 0
            for o in family(ob):
                if o.type == 'MESH':
                    try:
                        ev = o.evaluated_get(deps)
                        me = ev.to_mesh()
                        me.calc_loop_triangles()
                        tris += len(me.loop_triangles)
                        verts += len(me.vertices)
                        ev.to_mesh_clear()
                    except Exception:
                        pass
            mats = sorted({s.material.name for o in family(ob) for s in o.material_slots if s.material})
            bare = sum(1 for o in family(ob) if o.type == 'MESH' and not any(s.material for s in o.material_slots))
            rows.append(dict(
                name=ob.name, frame=f, type=ob.type, parent=ob.parent.name if ob.parent else None,
                loc=vec(ob.matrix_world.translation), rot_deg=[r5(math.degrees(a)) for a in ob.matrix_world.to_euler()],
                scale=vec(ob.matrix_world.to_scale()), centre=vec((lo + hi) / 2), size=vec(hi - lo),
                bottom_z=r5(lo.z), top_z=r5(hi.z), hide_render=bool(ob.hide_render), parts=len(family(ob)),
                tris=tris, verts=verts, materials=mats, material_count=len(mats), meshes_without_material=bare,
                modifiers=sorted({m.type for o in family(ob) for m in o.modifiers}),
                animated=any(bool(o.animation_data and o.animation_data.action) for o in family(ob)),
                default_name=bool(DEFAULT_NAME.match(ob.name)), gap_below=ray_gap_below(ob)))
    return rows


def p_material(q):
    rows, seen = [], set()
    for ob in pick(q.get('select')):
        for o in family(ob):
            for s in o.material_slots:
                if s.material and (ob.name, s.material.name) not in seen:
                    seen.add((ob.name, s.material.name))
                    rows.append(dict(material_row(s.material), name=ob.name, part=o.name))
    return rows


def p_light(q):
    at = point_of(q['at']) if 'at' in q else None
    obs = [o for o in (pick(q['select']) if 'select' in q else sorted(sc.objects, key=lambda o: o.name)) if o.type == 'LIGHT']
    rows = []
    for f in frames_of(q):
        sc.frame_set(f)
        total = 0.0
        frame_rows = []
        for ob in obs:
            L = ob.data
            row = dict(name=ob.name, frame=f, light_type=L.type, energy=r5(L.energy), color=vec(L.color),
                       loc=vec(ob.matrix_world.translation), hide_render=bool(ob.hide_render),
                       shadow=bool(getattr(L, 'use_shadow', True)))
            if L.type == 'SPOT':
                row['spot_deg'] = r5(math.degrees(L.spot_size))
            if at is not None:
                d = at - ob.matrix_world.translation
                fwd = (ob.matrix_world.to_quaternion() @ Vector((0, 0, -1))).normalized()
                if ob.hide_render:
                    e = 0.0
                elif L.type == 'SUN':
                    e = L.energy
                else:
                    # radiant power spread over a sphere: watts per square metre at the point, before shadows
                    e = L.energy / (4 * math.pi * max(d.length, 1e-3) ** 2)
                    if L.type == 'SPOT' and d.length > 1e-6 and fwd.angle(d.normalized()) > L.spot_size / 2:
                        e = 0.0
                    if L.type == 'AREA' and d.length > 1e-6 and fwd.dot(d.normalized()) <= 0:
                        e = 0.0
                row['distance'] = r5(d.length)
                row['reaches'] = r5(e)
                total += e
            frame_rows.append(row)
        for row in frame_rows:
            if at is not None:
                row['share'] = r5(row['reaches'] / total) if total > 0 else 0.0
                row['total_reaching'] = r5(total)
            rows.append(row)
    return rows


def p_world(q):
    w = sc.world
    row = dict(has_world=bool(w), color=[0.0, 0.0, 0.0], strength=0.0, nodes=0, environment_texture=False)
    if w:
        row['color'] = vec(list(w.color)[:3])
        row['strength'] = 1.0
        if w.node_tree:
            ids = [n.bl_idname for n in w.node_tree.nodes]
            row['nodes'] = len(ids)
            row['environment_texture'] = 'ShaderNodeTexEnvironment' in ids or 'ShaderNodeTexSky' in ids
            bg = next((n for n in w.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None)
            if bg:
                row['color'] = vec(list(bg.inputs['Color'].default_value)[:3])
                row['strength'] = r5(bg.inputs['Strength'].default_value)
    row['luminance'] = r5((0.2126 * row['color'][0] + 0.7152 * row['color'][1] + 0.0722 * row['color'][2]) * row['strength'])
    return [row]


def p_render(q):
    r, vs = sc.render, sc.view_settings
    row = dict(engine=r.engine, resolution_x=r.resolution_x, resolution_y=r.resolution_y, percentage=r.resolution_percentage,
               fps=r5(r.fps / r.fps_base), frame_start=sc.frame_start, frame_end=sc.frame_end,
               frames=sc.frame_end - sc.frame_start + 1, seconds=r5((sc.frame_end - sc.frame_start + 1) / (r.fps / r.fps_base)),
               film_transparent=bool(r.film_transparent), view_transform=vs.view_transform, look=vs.look,
               exposure=r5(vs.exposure), gamma=r5(vs.gamma), motion_blur=bool(getattr(r, 'use_motion_blur', False)),
               compositing=bool(getattr(r, 'use_compositing', False)))
    tree = getattr(sc, 'compositing_node_group', None) or getattr(sc, 'node_tree', None)
    row['compositor_nodes'] = len(tree.nodes) if tree else 0
    if r.engine == 'CYCLES':
        row.update(samples=sc.cycles.samples, denoise=bool(sc.cycles.use_denoising))
    elif hasattr(sc, 'eevee'):
        row.update(samples=getattr(sc.eevee, 'taa_render_samples', None))
    cam = sc.camera
    row['active_camera'] = cam.name if cam else None
    return [row]


def p_shots(q):
    return shot_list()


def p_framing(q):
    obs = pick(q.get('select'))
    rows = []
    for f in frames_of(q):
        sc.frame_set(f)
        cam = camera_of(q, f)
        M = cam.matrix_world
        for ob in obs:
            lo, hi = box(ob)
            cs = corners(lo, hi)
            cen = (lo + hi) / 2
            co = world_to_camera_view(sc, cam, cen)
            pts = [world_to_camera_view(sc, cam, c) for c in cs]
            xs, ys = [p.x for p in pts], [p.y for p in pts]
            inside = sum(1 for p in pts if 0 <= p.x <= 1 and 0 <= p.y <= 1 and p.z > 0)
            d = cen - M.translation
            rows.append(dict(
                name=ob.name, frame=f, camera=cam.name, lens=r5(cam.data.lens), dof=bool(cam.data.dof.use_dof),
                centre_x=r5(co.x), centre_y=r5(co.y), in_front=bool(co.z > 0),
                centre_in_frame=bool(0 <= co.x <= 1 and 0 <= co.y <= 1 and co.z > 0),
                corners_in_frame=r5(inside / 8), height=r5(max(ys) - min(ys)), width=r5(max(xs) - min(xs)),
                distance=r5(d.length), pitch_down_deg=r5(math.degrees(math.asin(max(-1, min(1, -d.normalized().z))))) if d.length > 1e-6 else 0.0,
                off_centre=r5(math.hypot(co.x - 0.5, co.y - 0.5)), occluded=occluded(cam, ob, cen)))
    return rows


def p_motion(q):
    obs = pick(q.get('select'))
    fr = frames_of(q)
    fps = sc.render.fps / sc.render.fps_base
    track = {ob.name: [] for ob in obs}
    for f in fr:
        sc.frame_set(f)
        for ob in obs:
            lo, hi = box(ob)
            track[ob.name].append((ob.matrix_world.translation.copy(), ob.matrix_world.to_quaternion(), lo.z))
    rows = []
    for ob in obs:
        t = track[ob.name]
        steps = [(b[0] - a[0]) for a, b in zip(t[:-1], t[1:])]
        lens = [s.length for s in steps]
        turns = [math.degrees(a[1].rotation_difference(b[1]).angle) for a, b in zip(t[:-1], t[1:])]
        eps = 1e-5
        moving = [i for i, (l, a) in enumerate(zip(lens, turns)) if l > eps or a > 0.01]
        peak = max(lens, default=0.0)
        rev = sum(1 for a, b in zip(steps[:-1], steps[1:]) if a.length > eps and b.length > eps and a.dot(b) < 0)
        first, last = (moving[0], moving[-1]) if moving else (None, None)
        # how hard the motion starts and stops: the first / last moving step as a share of the fastest step
        hard_start = lens[first] / peak if moving and peak > eps else 0.0
        hard_stop = lens[last] / peak if moving and peak > eps else 0.0
        jerk = max((abs(b - a) for a, b in zip(lens[:-1], lens[1:])), default=0.0)
        rows.append(dict(
            name=ob.name, frame_from=fr[0], frame_to=fr[-1], samples=len(fr),
            displacement=r5((t[-1][0] - t[0][0]).length), path_length=r5(sum(lens)),
            largest_step=r5(peak), peak_speed=r5(peak * fps), mean_speed=r5(sum(lens) / max(len(lens), 1) * fps),
            turn_deg=r5(sum(turns)), largest_turn_deg=r5(max(turns, default=0.0)), reversals=rev,
            moving_steps=len(moving), first_moving_frame=fr[first] if moving else None,
            last_moving_frame=fr[last + 1] if moving else None,
            hard_start=r5(hard_start), hard_stop=r5(hard_stop), largest_speed_jump=r5(jerk * fps),
            lowest_bottom_z=r5(min(x[2] for x in t)), highest_bottom_z=r5(max(x[2] for x in t)),
            end_loc=vec(t[-1][0]), start_loc=vec(t[0][0])))
    return rows


def p_contact(q):
    a_obs, b_obs = pick(q.get('a')), pick(q.get('b'))
    rows = []
    for f in frames_of(q):
        sc.frame_set(f)
        for a in a_obs:
            for b in b_obs:
                if a.name == b.name:
                    continue
                alo, ahi = box(a)
                blo, bhi = box(b)
                ox = max(0.0, min(ahi.x, bhi.x) - max(alo.x, blo.x))
                oy = max(0.0, min(ahi.y, bhi.y) - max(alo.y, blo.y))
                oz = max(0.0, min(ahi.z, bhi.z) - max(alo.z, blo.z))
                foot = max((ahi.x - alo.x) * (ahi.y - alo.y), 1e-9)
                gap = [max(alo[i] - bhi[i], blo[i] - ahi[i], 0.0) for i in range(3)]
                rows.append(dict(
                    a=a.name, b=b.name, frame=f, over=r5(ox * oy / foot), rests_gap=r5(alo.z - bhi.z),
                    sunk=r5(max(0.0, bhi.z - alo.z)) if ox * oy > 0 and ahi.z > bhi.z else 0.0,
                    box_overlap=r5(ox * oy * oz), box_distance=r5(math.sqrt(sum(g * g for g in gap))),
                    centre_distance=r5((((alo + ahi) / 2) - ((blo + bhi) / 2)).length)))
    return rows


def p_file(q):
    imgs = [i for i in bpy.data.images if i.type == 'IMAGE' and i.source == 'FILE']
    missing = [i.name for i in imgs if not i.packed_file and not os.path.isfile(bpy.path.abspath(i.filepath))]
    outside = [i.name for i in imgs if not i.packed_file and not i.filepath.startswith('//')]
    meshes = [o for o in sc.objects if o.type == 'MESH']
    return [dict(
        objects=len(sc.objects), meshes=len(meshes), lights=sum(o.type == 'LIGHT' for o in sc.objects),
        cameras=sum(o.type == 'CAMERA' for o in sc.objects), materials=len([m for m in bpy.data.materials if m.users]),
        libraries=len(bpy.data.libraries), images=len(imgs), images_unpacked=sum(1 for i in imgs if not i.packed_file),
        images_missing=len(missing), images_outside=len(outside),
        default_named_objects=sum(1 for o in sc.objects if DEFAULT_NAME.match(o.name)),
        meshes_without_material=sum(1 for o in meshes if not any(s.material for s in o.material_slots)),
        tris=sum(r['tris'] for r in p_object({'select': {'type': 'MESH'}})), actions=len(bpy.data.actions),
        scenes=len(bpy.data.scenes))]


def render_still(path, frame, cam, width, samples=16):
    r = sc.render
    keep = (r.resolution_percentage, r.filepath, r.image_settings.file_format, sc.camera, sc.frame_current)
    cyc = sc.cycles.samples if r.engine == 'CYCLES' else None
    try:
        sc.frame_set(frame)
        sc.camera = cam
        r.resolution_percentage = max(5, int(100 * width / max(r.resolution_x, 1)))
        r.image_settings.file_format = 'PNG'
        r.filepath = path
        if cyc is not None:
            sc.cycles.samples = min(cyc, samples)
        bpy.ops.render.render(write_still=True)
    finally:
        r.resolution_percentage, r.filepath, r.image_settings.file_format = keep[:3]
        sc.camera = keep[3]
        if cyc is not None:
            sc.cycles.samples = cyc
        sc.frame_set(keep[4])


def p_screen(q):
    """Mean brightness of a rendered frame, the only pixel statistic: 0 black to 1 white, in display space."""
    import numpy as np
    if not pic_dir:
        raise ValueError('screen needs a pictures folder')
    rows = []
    for f in frames_of(q):
        cam = camera_of(q, f)
        path = os.path.join(pic_dir, f'screen_{q["id"]}_{f}.png')
        render_still(path, f, cam, int(q.get('width', 320)))
        img = bpy.data.images.load(path)
        px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
        lum = 0.2126 * px[:, 0] + 0.7152 * px[:, 1] + 0.0722 * px[:, 2]
        rows.append(dict(frame=f, camera=cam.name, luminance=r5(lum.mean()), dark_share=r5((lum < 0.04).mean()),
                         bright_share=r5((lum > 0.96).mean())))
        bpy.data.images.remove(img)
    return rows


def render_mask(path, frame, cam, width, subject, alone=False):
    """A picture where the subject is white and everything else black or empty: which pixels of the frame are the
    subject. alone=True hides everything else first, so the mask is the subject with nothing in front of it."""
    r, sh, vs = sc.render, sc.display.shading, sc.view_settings
    keep = (r.engine, r.film_transparent, sh.light, sh.color_type, sc.display.render_aa, vs.view_transform, vs.look,
            r.image_settings.color_mode)
    colors = {o.name: tuple(o.color) for o in sc.objects}
    hidden = {o.name: o.hide_render for o in sc.objects}
    try:
        r.engine, r.film_transparent = 'BLENDER_WORKBENCH', True
        sh.light, sh.color_type, sc.display.render_aa = 'FLAT', 'OBJECT', 'OFF'
        vs.view_transform, vs.look = 'Standard', 'None'
        r.image_settings.color_mode = 'RGBA'
        for o in sc.objects:
            o.color = (1, 1, 1, 1) if o in subject else (0, 0, 0, 1)
            if alone and o not in subject and o.type in SOLID:
                o.hide_render = True
        render_still(path, frame, cam, width)
    finally:
        for o in sc.objects:
            o.color, o.hide_render = colors[o.name], hidden[o.name]
        (r.engine, r.film_transparent, sh.light, sh.color_type, sc.display.render_aa, vs.view_transform, vs.look,
         r.image_settings.color_mode) = keep


def read_picture(path):
    """Pixels of a saved picture, top row first: an array (height, width, 4), 0..1 in display space."""
    import numpy as np
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(img)
    return px


def hsv_of(rgb):
    import numpy as np
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    sat = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    safe = np.maximum(d, 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.where(mx == r, ((g - b) / safe) % 6, np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4)) * 60.0
    return np.where(d > 1e-6, hue, 0.0), sat, mx


def mean_hue(hue, sat):
    """The average hue in degrees, each pixel counted by how coloured it is; None when nothing is coloured."""
    import numpy as np
    if sat.size == 0 or float(sat.sum()) < 1e-3:
        return None
    a = np.radians(hue)
    return r5(math.degrees(math.atan2(float((np.sin(a) * sat).sum()), float((np.cos(a) * sat).sum()))) % 360)


def p_picture(q):
    """What the rendered frame looks like, in numbers: the whole frame's light and colour and, with "select", where
    the subject sits in it and how it stands out. Positions are shares of the frame, x from the left, y from the top."""
    import numpy as np
    if not pic_dir:
        raise ValueError('picture needs a pictures folder')
    width = int(q.get('width', 480))
    subject = set()
    for o in pick(q['select']) if 'select' in q else []:
        subject.update(family(o))
    if 'select' in q and not subject:
        return []
    rows = []
    for f in frames_of(q):
        cam = camera_of(q, f)
        stem = os.path.join(pic_dir, f'picture_{q["id"]}_{f}')
        render_still(stem + '.png', f, cam, width, samples=int(q.get('samples', 32)))
        px = read_picture(stem + '.png')
        rgb = px[..., :3]
        h, w = rgb.shape[:2]
        lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        hue, sat, val = hsv_of(rgb)
        coloured = (sat > 0.2) & (val > 0.1)
        hist = np.histogram(hue[coloured], bins=12, range=(0, 360))[0] if coloured.any() else np.zeros(12)
        rg, yb = rgb[..., 0] - rgb[..., 1], 0.5 * (rgb[..., 0] + rgb[..., 1]) - rgb[..., 2]
        row = dict(frame=f, camera=cam.name, luminance=r5(lum.mean()), luminance_low=r5(np.percentile(lum, 5)),
                   luminance_high=r5(np.percentile(lum, 95)),
                   luminance_range=r5(np.percentile(lum, 95) - np.percentile(lum, 5)),
                   clipped_share=r5((lum > 0.98).mean()), crushed_share=r5((lum < 0.02).mean()),
                   saturation=r5(sat.mean()), coloured_share=r5(coloured.mean()),
                   colourfulness=r5(math.hypot(float(rg.std()), float(yb.std())) + 0.3 * math.hypot(float(rg.mean()), float(yb.mean()))),
                   hue_groups=int((hist >= 0.08 * max(hist.sum(), 1)).sum()), hue=mean_hue(hue, sat))
        if subject:
            render_mask(stem + '_mask.png', f, cam, width, subject)
            render_mask(stem + '_alone.png', f, cam, width, subject, alone=True)
            m = read_picture(stem + '_mask.png')
            a = read_picture(stem + '_alone.png')
            mask = (m[..., 0] > 0.5) & (m[..., 3] > 0.5)
            alone = (a[..., 0] > 0.5) & (a[..., 3] > 0.5)
            row.update(in_frame=bool(mask.any()), area_share=r5(mask.mean()),
                       visible_share=r5(mask.sum() / alone.sum()) if alone.any() else 0.0)
            if mask.any():
                ys, xs = np.nonzero(mask)
                x0, x1, y0, y1 = xs.min() / w, (xs.max() + 1) / w, ys.min() / h, (ys.max() + 1) / h
                cx, cy = (xs.mean() + 0.5) / w, (ys.mean() + 0.5) / h
                margin = min(x0, y0, 1 - x1, 1 - y1)
                # the surround: the subject's box grown by half its size each way, without the subject
                gx, gy = 0.5 * (x1 - x0), 0.5 * (y1 - y0)
                near = np.zeros_like(mask)
                near[max(0, int((y0 - gy) * h)):min(h, int((y1 + gy) * h) + 1), max(0, int((x0 - gx) * w)):min(w, int((x1 + gx) * w) + 1)] = True
                ring = near & ~mask
                rest = ~mask
                bright = lum >= np.percentile(lum, 95)
                sh_, rh = mean_hue(hue[mask], sat[mask]), mean_hue(hue[ring], sat[ring]) if ring.any() else None
                row.update(
                    centre_x=r5(cx), centre_y=r5(cy), box=[r5(x0), r5(y0), r5(x1), r5(y1)], width=r5(x1 - x0), height=r5(y1 - y0),
                    headroom=r5(y0), footroom=r5(1 - y1), edge_margin=r5(margin), touches_edge=bool(margin < 0.005),
                    centre_offset=r5(math.hypot(cx - 0.5, cy - 0.5)),
                    thirds_offset=r5(min(math.hypot(cx - tx, cy - ty) for tx in (1 / 3, 2 / 3) for ty in (1 / 3, 2 / 3))),
                    silhouette_fill=r5(mask.sum() / max(1.0, (x1 - x0) * w * (y1 - y0) * h)),
                    subject_luminance=r5(lum[mask].mean()), surround_luminance=r5(lum[ring].mean()) if ring.any() else None,
                    background_luminance=r5(lum[rest].mean()) if rest.any() else None,
                    separation=r5(abs(float(lum[mask].mean()) - float(lum[ring].mean()))) if ring.any() else None,
                    subject_saturation=r5(sat[mask].mean()), surround_saturation=r5(sat[ring].mean()) if ring.any() else None,
                    subject_hue=sh_, surround_hue=rh,
                    hue_distance=r5(min(abs(sh_ - rh), 360 - abs(sh_ - rh))) if sh_ is not None and rh is not None else None,
                    subject_clipped_share=r5((lum[mask] > 0.98).mean()), subject_crushed_share=r5((lum[mask] < 0.02).mean()),
                    highlights_on_subject=r5((bright & (mask | ring)).sum() / max(1, bright.sum())))
        rows.append(row)
    return rows


PROBES = dict(object=p_object, material=p_material, light=p_light, world=p_world, render=p_render, shots=p_shots,
              framing=p_framing, motion=p_motion, contact=p_contact, file=p_file, screen=p_screen, picture=p_picture)

out = {'blender': bpy.app.version_string, 'objects': sorted(o.name for o in sc.objects), 'rows': {}, 'errors': {}, 'shots': {}}
for q in spec.get('queries') or []:
    try:
        fn = PROBES.get(q.get('probe'))
        if not fn:
            raise ValueError(f'unknown probe {q.get("probe")!r}')
        out['rows'][q['id']] = fn(q)
    except Exception as e:
        out['errors'][q['id']] = f'{type(e).__name__}: {e}'
        traceback.print_exc()
for s in spec.get('shots') or []:
    try:
        frame = int(s.get('frame', sc.frame_start))
        cam = camera_of(s, frame)
        path = os.path.join(pic_dir, f'{s["id"]}.png')
        render_still(path, frame, cam, int(s.get('width', 960)), samples=int(s.get('samples', 32)))
        out['shots'][s['id']] = os.path.basename(path)
    except Exception as e:
        out['errors'][s['id']] = f'{type(e).__name__}: {e}'
        traceback.print_exc()
json.dump(out, open(out_path, 'w', encoding='utf-8'), indent=1)
