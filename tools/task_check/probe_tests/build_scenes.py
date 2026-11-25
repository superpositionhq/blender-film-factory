"""Runs inside Blender. Builds the test task's scenes from nothing, so no .blend is kept in this repository.

  blender -b --factory-startup --python build_scenes.py -- <out dir>

Writes start.blend (everything wrong), reference.blend (everything right) and four more candidates:
half.blend (only the cup fixed), broke_lamp.blend (all fixed but the lamp was moved), renamed.blend (all fixed with
other names for everything the task does not name), empty.blend (the scene deleted).
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

out = Path(sys.argv[sys.argv.index('--') + 1])
out.mkdir(parents=True, exist_ok=True)


def mat(name, color, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    return m


def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()


def build(cup_z, cup_mat, aim_at, key_w, ease, saucer, lamp_x=3.0, names=None):
    n = dict(saucer='Saucer', cam='Cam_S1', key='Key', cupmat='CupPaint')
    n.update(names or {})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end, sc.render.fps = 1, 24, 24
    sc.render.resolution_x, sc.render.resolution_y = 640, 360
    sc.render.engine = 'BLENDER_EEVEE'            # the judge's pictures must show the materials and the light
    grey = mat('Wood', (0.4, 0.3, 0.2), 0.7)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.4))
    table = bpy.context.object
    table.name, table.scale = 'Table', (1.6, 1.0, 0.8)
    table.data.materials.append(grey)
    bpy.ops.mesh.primitive_plane_add(size=12)
    bpy.context.object.name = 'Floor'
    bpy.context.object.data.materials.append(grey)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.1, location=(0, 0, cup_z))
    cup = bpy.context.object
    cup.name = 'Cup'
    cup.data.materials.append(mat(n['cupmat'], *cup_mat))
    if saucer:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=0.01, location=(0, 0, 0.805))
        bpy.context.object.name = n['saucer']
        bpy.context.object.data.materials.append(mat('SaucerGlaze', (0.9, 0.9, 0.9), 0.3))
    bpy.ops.mesh.primitive_cone_add(radius1=0.15, depth=0.5, location=(lamp_x, 1.0, 0.25))
    bpy.context.object.name = 'Lamp'
    bpy.context.object.data.materials.append(grey)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(-2, -1.5, 0.1))
    ball = bpy.context.object
    ball.name = 'Ball'
    ball.data.materials.append(grey)
    ball.keyframe_insert('location', frame=1)
    ball.location.x = 2
    ball.keyframe_insert('location', frame=24)
    act = ball.animation_data.action
    curves = []
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                curves += list(bag.fcurves)
    for fc in curves or getattr(act, 'fcurves', []):
        for k in fc.keyframe_points:
            k.interpolation = 'BEZIER' if ease else 'LINEAR'
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
        fc.update()
    bpy.ops.object.camera_add(location=(0, -3.0, 1.6))
    cam = bpy.context.object
    cam.name = n['cam']
    aim(cam, aim_at)
    sc.camera = cam
    mk = sc.timeline_markers.new('S1', frame=1)
    mk.camera = cam
    bpy.ops.object.light_add(type='POINT', location=(1.0, -1.5, 2.5))
    bpy.context.object.name = n['key']
    bpy.context.object.data.energy = key_w
    sc.frame_set(1)
    return sc


def save(name):
    bpy.ops.wm.save_as_mainfile(filepath=str(out / name))


RIGHT = dict(cup_z=0.86, cup_mat=((0.8, 0.05, 0.05), 0.2), aim_at=(0, 0, 0.85), key_w=1000, ease=True, saucer=True)
WRONG = dict(cup_z=1.2, cup_mat=((0.5, 0.5, 0.5), 0.8), aim_at=(4, 0, 0.5), key_w=10, ease=False, saucer=False)
build(**WRONG); save('start.blend')
build(**RIGHT); save('reference.blend')
build(**dict(WRONG, cup_z=0.86, saucer=True)); save('half.blend')
build(**dict(RIGHT, lamp_x=1.0)); save('broke_lamp.blend')
build(**dict(RIGHT, cup_mat=((0.7, 0.0, 0.1), 0.1), key_w=1500),
      names=dict(cam='ShotOneCamera', key='MainLight', cupmat='Enamel')); save('renamed.blend')
bpy.ops.wm.read_factory_settings(use_empty=True); save('empty.blend')
