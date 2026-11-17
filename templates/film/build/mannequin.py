"""Grey-box figures and blocks for this film's step scripts: a jointed mannequin of rounded boxes, flat greybox
colours, a walk along a path, simple poses. It is the film's own file; functions are only ever added, never changed.

    import bpy, sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kit, mannequin
    anna = mannequin.build('Anna', height=1.68, colour='red', collection=kit.coll('Characters'))
    anna.location = (0, -2, 0)
    mannequin.walk(anna, [(0, -2, 0), (0, 2, 0), (3, 4, 0)], 1, 96)
    mannequin.pose(anna, 110, UpperArm_R=(-70, 0, 0), LowerArm_R=(-40, 0, 0), Head=(10, 0, 20))

A figure is a tree of objects named <Name> (root empty on the ground, its -Y is the way it faces), <Name>_Hips,
<Name>_Torso, <Name>_Head, <Name>_UpperArm_L/R, <Name>_LowerArm_L/R, <Name>_UpperLeg_L/R, <Name>_LowerLeg_L/R.
Each part's origin is its joint, so rotating the part bends the joint. Angles are degrees, (x, y, z): x swings
forward (negative) and back, y swings sideways, z twists. Shot lists name the root or a part as the subject.
"""
import math

import bmesh
import bpy
from mathutils import Vector

COLOURS = {
    'grey': (0.55, 0.55, 0.55), 'white': (0.85, 0.85, 0.83), 'dark': (0.12, 0.12, 0.13),
    'red': (0.75, 0.16, 0.12), 'blue': (0.13, 0.30, 0.70), 'green': (0.18, 0.52, 0.24),
    'yellow': (0.88, 0.68, 0.10), 'orange': (0.88, 0.40, 0.08), 'purple': (0.45, 0.22, 0.62),
    'teal': (0.08, 0.50, 0.52), 'pink': (0.85, 0.42, 0.55), 'brown': (0.36, 0.22, 0.12),
}
PARTS = ('Hips', 'Torso', 'Head', 'UpperArm_L', 'LowerArm_L', 'UpperArm_R', 'LowerArm_R',
         'UpperLeg_L', 'LowerLeg_L', 'UpperLeg_R', 'LowerLeg_R')


def greybox_mat(colour='grey'):
    """One flat matte material per greybox colour (a name from COLOURS, or an (r, g, b))."""
    rgb = COLOURS[colour] if isinstance(colour, str) else tuple(colour)
    name = 'Greybox_' + (colour if isinstance(colour, str) else '%02x%02x%02x' % tuple(int(c * 255) for c in rgb))
    m = bpy.data.materials.get(name)
    if not m:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*rgb, 1)
        b.inputs['Roughness'].default_value = 0.8
    return m


def _box(name, size, centre, collection, mat, bevel=0.012):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + centre[0], v.co.y * size[1] + centre[1], v.co.z * size[2] + centre[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    me.materials.append(mat)
    if bevel:
        mod = ob.modifiers.new('Bevel', 'BEVEL')
        mod.width, mod.segments = bevel, 2
    ob.rotation_mode = 'XYZ'
    return ob


def block(name, size, location, colour='grey', collection=None, bevel=0.01):
    """A greybox prop or set piece: a bevelled box with its origin at the centre of its base."""
    collection = collection or bpy.context.scene.collection
    ob = _box(name, size, (0, 0, size[2] / 2), collection, greybox_mat(colour), bevel)
    ob.location = location
    return ob


def light_rig(sun_direction=(0.4, 0.5, -0.75), world=(0.60, 0.62, 0.66)):
    """The plain greybox light: one soft sun named Greybox_Sun and an even grey-blue world. Call it once."""
    scene = bpy.context.scene
    ld = bpy.data.lights.new('Greybox_Sun', 'SUN')
    ld.energy, ld.angle = 3.0, 0.12
    ob = bpy.data.objects.new('Greybox_Sun', ld)
    scene.collection.objects.link(ob)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector(sun_direction).normalized().to_track_quat('-Z', 'Y')
    w = scene.world or bpy.data.worlds.new('FilmWorld')
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*world, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    return ob


def build(name, height=1.75, colour='grey', collection=None, build=1.0):
    """A mannequin standing at the origin facing -Y. Returns the root empty. build: 0.8 slight .. 1.3 heavy."""
    collection = collection or bpy.context.scene.collection
    mat, skin = greybox_mat(colour), greybox_mat('white')
    h, w = height, build
    hip, leg = 0.53 * h, 0.245 * h          # hip height; upper and lower leg lengths
    root = bpy.data.objects.new(name, None)
    root.empty_display_type, root.empty_display_size = 'ARROWS', 0.25
    root.rotation_mode = 'XYZ'
    collection.objects.link(root)
    root['mannequin'] = True
    root['figure'] = True
    root['height'] = height

    def part(key, size, centre, parent, pivot, m=mat):
        ob = _box(f'{name}_{key}', size, centre, collection, m)
        ob.parent = parent
        ob.location = pivot
        return ob

    hips = part('Hips', (0.19 * h * w, 0.11 * h * w, 0.10 * h), (0, 0, 0.02 * h), root, (0, 0, hip))
    torso = part('Torso', (0.21 * h * w, 0.12 * h * w, 0.27 * h), (0, 0, 0.135 * h), hips, (0, 0, 0.07 * h))
    part('Head', (0.095 * h, 0.105 * h, 0.125 * h), (0, 0, 0.085 * h), torso, (0, 0, 0.275 * h), skin)
    for side, sx in (('L', 1), ('R', -1)):
        ua = part(f'UpperArm_{side}', (0.05 * h * w, 0.05 * h * w, 0.17 * h), (0, 0, -0.085 * h), torso,
                  (sx * 0.135 * h * w, 0, 0.25 * h))
        part(f'LowerArm_{side}', (0.045 * h * w, 0.045 * h * w, 0.20 * h), (0, 0, -0.10 * h), ua, (0, 0, -0.17 * h))
        ul = part(f'UpperLeg_{side}', (0.075 * h * w, 0.08 * h * w, leg), (0, 0, -leg / 2), hips, (sx * 0.055 * h * w, 0, 0))
        ll = part(f'LowerLeg_{side}', (0.06 * h * w, 0.065 * h * w, leg + 0.04 * h), (0, 0, -(leg + 0.04 * h) / 2), ul, (0, 0, -leg))
        foot = _box(f'{name}_Foot_{side}', (0.06 * h * w, 0.15 * h, 0.035 * h), (0, -0.04 * h, 0.0175 * h), collection, greybox_mat('dark'))
        foot.parent = ll
        foot.location = (0, 0, -(leg + 0.04 * h))
    return root


def parts(root):
    """{'Hips': object, ...} for a figure."""
    return {k: bpy.data.objects[f'{root.name}_{k}'] for k in PARTS}


def pose(root, frame, interp='BEZIER', **angles):
    """Key joint rotations at a frame: pose(fig, 48, UpperArm_L=(-60, 0, 0), Head=(0, 0, 30)). Degrees."""
    p = parts(root)
    for key, deg in angles.items():
        ob = p[key]
        ob.rotation_euler = tuple(math.radians(d) for d in deg)
        ob.keyframe_insert('rotation_euler', frame=frame)
        _interp(ob, 'rotation_euler', frame, interp)


def rest(root, frame):
    """Key every joint back to the standing pose at a frame."""
    pose(root, frame, **{k: (0, 0, 0) for k in PARTS})


def place(root, frame, location, facing_deg=None, interp='BEZIER'):
    """Key the figure's place (and the way it faces: 0 = -Y, 90 = +X) at a frame."""
    root.location = location
    root.keyframe_insert('location', frame=frame)
    _interp(root, 'location', frame, interp)
    if facing_deg is not None:
        root.rotation_euler = (0, 0, math.radians(facing_deg))
        root.keyframe_insert('rotation_euler', frame=frame)
        _interp(root, 'rotation_euler', frame, interp)


def walk(root, path, f0, f1, stride=None, arm_swing=28, ease=True):
    """Walk along a polyline of (x, y, z) points from frame f0 to f1: the root follows the path and turns into each
    leg of it, the legs and arms swing in step with the distance covered, the hips bob. The figure starts and ends
    standing. Keys every 2 frames, linear."""
    pts = [Vector(p) for p in path]
    seg = [(b - a).length for a, b in zip(pts[:-1], pts[1:])]
    total = sum(seg)
    stride = stride or 0.42 * root.get('height', 1.75)       # one step
    p = parts(root)
    hip0 = p['Hips'].location.z

    def at(d):
        for i, L in enumerate(seg):
            if d <= L or i == len(seg) - 1:
                t = min(1.0, d / L) if L > 1e-9 else 0.0
                return pts[i].lerp(pts[i + 1], t), pts[i + 1] - pts[i]
            d -= L

    prev_yaw = None
    frames = list(range(f0, f1 + 1, 2))
    if frames[-1] != f1:
        frames.append(f1)
    for f in frames:
        u = (f - f0) / max(1, f1 - f0)
        s = u * u * (3 - 2 * u) if ease else u            # ease in and out of the walk
        d = s * total
        pos, direction = at(d)
        yaw = math.atan2(direction.x, -direction.y) if direction.length > 1e-9 else 0.0
        if prev_yaw is not None:                           # shortest turn
            while yaw - prev_yaw > math.pi:
                yaw -= 2 * math.pi
            while yaw - prev_yaw < -math.pi:
                yaw += 2 * math.pi
        prev_yaw = yaw
        amp = min(1.0, 4 * u, 4 * (1 - u)) if ease else 1.0   # the swing dies away at both ends
        ph = math.pi * d / stride
        root.location = pos
        root.rotation_euler = (0, 0, yaw)
        root.keyframe_insert('location', frame=f)
        root.keyframe_insert('rotation_euler', frame=f)
        sw = math.sin(ph)
        rot = {
            'UpperLeg_L': (-30 * sw * amp, 0, 0), 'UpperLeg_R': (30 * sw * amp, 0, 0),
            'LowerLeg_L': (38 * max(0.0, -math.cos(ph)) * amp * (1 if sw > 0 else 0.35), 0, 0),
            'LowerLeg_R': (38 * max(0.0, math.cos(ph)) * amp * (1 if sw < 0 else 0.35), 0, 0),
            'UpperArm_L': (arm_swing * sw * amp, 0, 0), 'UpperArm_R': (-arm_swing * sw * amp, 0, 0),
            'LowerArm_L': (-14 * amp - 10 * max(0.0, sw) * amp, 0, 0), 'LowerArm_R': (-14 * amp - 10 * max(0.0, -sw) * amp, 0, 0),
            'Torso': (-3 * amp, 0, 5 * sw * amp),
        }
        for key, deg in rot.items():
            p[key].rotation_euler = tuple(math.radians(x) for x in deg)
            p[key].keyframe_insert('rotation_euler', frame=f)
        p['Hips'].location.z = hip0 - 0.02 * root.get('height', 1.75) * abs(sw) * amp
        p['Hips'].keyframe_insert('location', frame=f)
    for ob in [root] + list(p.values()):
        _all_linear(ob, f0, f1)


def sit(root, frame, seat_height=0.45):
    """Key a seated pose at a frame (hips at seat height, thighs forward, shins down)."""
    p = parts(root)
    h = root.get('height', 1.75)
    p['Hips'].location.z = seat_height + 0.05 * h
    p['Hips'].keyframe_insert('location', frame=frame)
    pose(root, frame, UpperLeg_L=(-88, 0, 0), UpperLeg_R=(-88, 0, 0), LowerLeg_L=(88, 0, 0), LowerLeg_R=(88, 0, 0),
         Torso=(4, 0, 0), UpperArm_L=(-25, 0, 0), UpperArm_R=(-25, 0, 0), LowerArm_L=(-50, 0, 0), LowerArm_R=(-50, 0, 0))


def stand(root, frame):
    """Key the hips back to standing height and every joint to rest at a frame."""
    p = parts(root)
    p['Hips'].location.z = 0.53 * root.get('height', 1.75)
    p['Hips'].keyframe_insert('location', frame=frame)
    rest(root, frame)


def _fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(cb.fcurves) if cb else []


def _interp(ob, path, frame, interp):
    for fc in _fcurves(ob):
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                if abs(kp.co[0] - frame) < 1e-4:
                    kp.interpolation = interp


def _all_linear(ob, f0, f1):
    for fc in _fcurves(ob):
        for kp in fc.keyframe_points:
            if f0 <= kp.co[0] <= f1:
                kp.interpolation = 'LINEAR'
