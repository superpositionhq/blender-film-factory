"""Runs inside Blender, started by tools/step.py. Executes one step script, then records the scene state, a preview
picture and a .blend checkpoint for that step. A failed script leaves scene.blend as it was.

  blender -b [scene.blend | --factory-startup] --python harness.py -- <script> <step dir> <scene.blend> <checkpoint>
Environment: BFF_PREVIEW=0 no picture; BFF_FRAME=<n> the frame of the picture (default: the scene's current frame).
"""
import json
import os
import sys
import time
import traceback

import bpy

script_path, step_dir, blend_out, checkpoint = sys.argv[sys.argv.index('--') + 1:][:4]
PREVIEW_WIDTH = 960


def vec(v):
    return [round(float(x), 5) for x in v]


def scene_state():
    scene = bpy.context.scene
    deps = bpy.context.evaluated_depsgraph_get()
    objects = []
    for ob in scene.objects:
        row = {
            'name': ob.name, 'type': ob.type, 'parent': ob.parent.name if ob.parent else None,
            'collections': [c.name for c in ob.users_collection],
            'location': vec(ob.matrix_world.translation), 'rotation_euler': vec(ob.matrix_world.to_euler()),
            'scale': vec(ob.matrix_world.to_scale()), 'hide_render': ob.hide_render,
            'animated': bool(ob.animation_data and ob.animation_data.action),
            'modifiers': [m.type for m in ob.modifiers], 'constraints': [c.type for c in ob.constraints],
            'materials': [s.material.name for s in ob.material_slots if s.material],
        }
        if ob.type == 'MESH':
            try:
                ev = ob.evaluated_get(deps)
                me = ev.to_mesh()
                me.calc_loop_triangles()
                row['verts'], row['tris'] = len(me.vertices), len(me.loop_triangles)
                ev.to_mesh_clear()
            except Exception:
                pass
        if ob.type == 'CAMERA':
            row['lens'], row['sensor_width'], row['dof'] = round(ob.data.lens, 3), ob.data.sensor_width, ob.data.dof.use_dof
        if ob.type == 'LIGHT':
            row['light_type'], row['energy'] = ob.data.type, ob.data.energy
        objects.append(row)
    materials = []
    for m in bpy.data.materials:
        nodes = [n.bl_idname for n in m.node_tree.nodes] if m.node_tree else []
        materials.append({'name': m.name, 'users': m.users, 'nodes': len(nodes), 'node_types': sorted(set(nodes))})
    markers = [{'name': mk.name, 'frame': mk.frame, 'camera': mk.camera.name if mk.camera else None}
               for mk in sorted(scene.timeline_markers, key=lambda k: k.frame)]
    return {
        'blender': bpy.app.version_string, 'scene': scene.name, 'frame_start': scene.frame_start,
        'frame_end': scene.frame_end, 'fps': scene.render.fps / scene.render.fps_base,
        'resolution': [scene.render.resolution_x, scene.render.resolution_y], 'engine': scene.render.engine,
        'active_camera': scene.camera.name if scene.camera else None, 'markers': markers, 'objects': objects,
        'materials': materials,
        'images': [{'name': i.name, 'filepath': i.filepath, 'packed': bool(i.packed_file)} for i in bpy.data.images
                   if i.type == 'IMAGE'],
        'libraries': [l.filepath for l in bpy.data.libraries],
        'counts': {
            'objects': len(objects), 'meshes': sum(o['type'] == 'MESH' for o in objects),
            'tris': sum(o.get('tris', 0) for o in objects), 'materials': len(materials),
            'lights': sum(o['type'] == 'LIGHT' for o in objects), 'cameras': sum(o['type'] == 'CAMERA' for o in objects),
            'markers': len(markers), 'animated_objects': sum(o['animated'] for o in objects),
            'actions': len(bpy.data.actions),
        },
    }


def render_preview(path):
    scene = bpy.context.scene
    frame = os.environ.get('BFF_FRAME')
    if frame:
        scene.frame_set(int(frame))
    if not scene.camera:
        return None
    r = scene.render
    keep = (r.resolution_percentage, r.filepath, r.image_settings.file_format)
    r.resolution_percentage = max(10, int(100 * PREVIEW_WIDTH / max(r.resolution_x, 1)))
    r.image_settings.file_format = 'PNG'
    r.filepath = path
    samples = None
    if r.engine == 'CYCLES':
        samples, scene.cycles.samples = scene.cycles.samples, min(scene.cycles.samples, 24)
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        r.resolution_percentage, r.filepath, r.image_settings.file_format = keep
        if samples is not None:
            scene.cycles.samples = samples
    return scene.frame_current


result = {'ok': True, 'error': None}
t0 = time.time()
try:
    src = open(script_path, encoding='utf-8').read()
    exec(compile(src, script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
except SystemExit:
    pass
except Exception:
    result['ok'] = False
    result['error'] = traceback.format_exc()
    traceback.print_exc()
result['script_seconds'] = round(time.time() - t0, 2)

try:
    state = scene_state()
    json.dump(state, open(os.path.join(step_dir, 'state.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    result['counts'] = state['counts']
except Exception:
    result['state_error'] = traceback.format_exc()

if result['ok']:
    bpy.ops.wm.save_as_mainfile(filepath=blend_out)
    bpy.ops.wm.save_as_mainfile(filepath=checkpoint, copy=True)
    if os.environ.get('BFF_PREVIEW', '1') == '1':
        try:
            result['preview_frame'] = render_preview(os.path.join(step_dir, 'preview.png'))
        except Exception:
            result['preview_error'] = traceback.format_exc()

json.dump(result, open(os.path.join(step_dir, 'result.json'), 'w', encoding='utf-8'), indent=1)
