"""Runs inside Blender (started by tools/render.py). Read-only: renders frames, never saves the scene.

  blender -b scene.blend --python render_frames.py -- <out dir> <frames, comma separated> [pct=50] [samples=16]
      [clay=1] [skip=1]
clay=1: one clay override material on everything, the film's lights and volumes off, a soft sun that follows the
shot camera plus a grey world, no compositing: the white-model version of the same cameras and animation.
skip=1: a frame already there is kept when it was rendered after the .blend was last saved (by the last step), and
rendered again when it is older: it shows the scene as it was before that step.
"""
import os
import sys
import time

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out, frames = argv[0], [int(x) for x in argv[1].split(',')]
opt = dict(a.split('=', 1) for a in argv[2:])
sc = bpy.context.scene
r = sc.render
r.resolution_percentage = int(opt.get('pct', 100))
if 'samples' in opt:
    sc.eevee.taa_render_samples = int(opt['samples'])
    if hasattr(sc, 'cycles'):
        sc.cycles.samples = int(opt['samples'])

clay_sun = None
if opt.get('clay') == '1':
    clay = bpy.data.materials.new('ClayOverride')
    clay.use_nodes = True
    b = clay.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.62, 0.60, 0.57, 1)
    b.inputs['Roughness'].default_value = 0.85
    for vl in sc.view_layers:
        vl.material_override = clay
    for ob in sc.objects:
        if ob.type in ('LIGHT', 'LIGHT_PROBE', 'VOLUME'):
            ob.hide_render = True
            if ob.animation_data:
                ob.animation_data_clear()
        elif ob.type == 'MESH' and any(s.material and s.material.node_tree and any(
                n.bl_idname.startswith('ShaderNodeVolume') for n in s.material.node_tree.nodes) for s in ob.material_slots):
            ob.hide_render = True
            if ob.animation_data:
                ob.animation_data_clear()
    w = sc.world or bpy.data.worlds.new('ClayWorld')
    sc.world = w
    w.use_nodes = True
    if w.node_tree.animation_data:
        w.node_tree.animation_data_clear()
    bg = w.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.55, 0.57, 0.60, 1)
        bg.inputs['Strength'].default_value = 0.9
    ld = bpy.data.lights.new('ClaySun', 'SUN')
    ld.energy, ld.angle = 2.2, 0.3
    ld.use_shadow = False       # interiors: a shadowed sun would leave closed rooms black
    clay_sun = bpy.data.objects.new('ClaySun', ld)
    sc.collection.objects.link(clay_sun)
    clay_sun.rotation_mode = 'QUATERNION'
    r.use_compositing = False
    r.use_motion_blur = False
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    if hasattr(sc.eevee, 'use_raytracing'):
        sc.eevee.use_raytracing = False

r.image_settings.file_format = 'PNG'
r.image_settings.color_mode = 'RGB'
r.image_settings.compression = 15
os.makedirs(out, exist_ok=True)
saved = os.path.getmtime(bpy.data.filepath) if bpy.data.filepath else float('inf')
for f in frames:
    path = os.path.join(out, 'f%05d.png' % f)
    if opt.get('skip') == '1' and os.path.exists(path) and os.path.getmtime(path) >= saved:
        continue
    sc.frame_set(f)
    if clay_sun and sc.camera:
        q = sc.camera.matrix_world.to_quaternion()
        # light from over the camera's left shoulder
        d = (q @ Vector((0.45, -0.55, -1.0))).normalized()
        clay_sun.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    r.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('RENDERED', f, round(time.time() - t, 2), flush=True)
