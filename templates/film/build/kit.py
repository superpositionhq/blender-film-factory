"""Shared helpers for this film's step scripts (build/NNN_*.py). It is the film's own file: add what the film needs.
Functions are only ever ADDED here, never changed: an earlier step script must replay the same way, so a helper that
needs to behave differently gets a new name (wood_material2). Every step script starts with:

    import bpy, sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kit
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler, Quaternion

FILM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def start_film(width=1920, height=1080, fps=24, frames=240, engine='BLENDER_EEVEE', name='Film'):
    """First step (run with --new): empty the factory file and set the film format."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for blocks in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.materials, bpy.data.collections):
        for b in list(blocks):
            blocks.remove(b)
    scene = bpy.context.scene
    scene.name = name
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
    scene.render.fps, scene.render.fps_base = fps, 1.0
    scene.frame_start, scene.frame_end = 1, frames
    scene.frame_set(1)
    scene.render.engine = engine
    scene.unit_settings.system = 'METRIC'
    world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    world.name = 'FilmWorld'
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.52, 0.55, 1)
    return scene


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(ob, collection):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)
    return ob


def mesh_obj(name, verts, faces, collection, smooth=False, mat=None, edges=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], list(edges), [tuple(f) for f in faces])
    me.update()
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def bm_obj(name, bm, collection, smooth=False, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def swap_mesh(ob, bm, smooth=False, mats=()):
    """Replace the mesh data of an existing object (keeps name, transform, animation)."""
    old = ob.data
    me = bpy.data.meshes.new(ob.name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    ob.data = me
    for m in mats:
        me.materials.append(m)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def box_bm(size, center=(0, 0, 0), bm=None):
    """Adds an axis-aligned box to a bmesh."""
    bm = bm or bmesh.new()
    sx, sy, sz = size
    m = Matrix.Translation(center) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return bm


def lathe_bm(profile, segments=32, bm=None, close_bottom=False):
    """Revolves a list of (radius, z) points around Z. Points with radius 0 become poles."""
    bm = bm or bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-9:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segments),
                                        r * math.sin(2 * math.pi * i / segments), z))
                          for i in range(segments)])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[i], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[i], a[j], b[0]))
            else:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def look_at(ob, target, roll=0.0):
    d = Vector(target) - ob.location
    q = d.to_track_quat('-Z', 'Y')
    ob.rotation_euler = (q @ Quaternion((0, 0, 1), roll)).to_euler()


def fcurves(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(cb.fcurves) if cb else []


def key(idblock, path, frame, value=None, interp=None, index=-1):
    """Set a value and insert a keyframe; optionally set the interpolation of that key."""
    if value is not None:
        if index >= 0:
            getattr(idblock, path)[index] = value
        else:
            setattr(idblock, path, value)
    idblock.keyframe_insert(path, frame=frame, index=index)
    if interp:
        for fc in fcurves(idblock):
            if fc.data_path == path and (index < 0 or fc.array_index == index):
                for kp in fc.keyframe_points:
                    if abs(kp.co[0] - frame) < 1e-4:
                        kp.interpolation = interp


def set_interp(idblock, interp, path=None, easing=None):
    for fc in fcurves(idblock):
        if path and fc.data_path != path:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            if easing:
                kp.easing = easing


def clear_anim(idblock, path=None):
    """Remove all keys (or only those of one data path) from an object."""
    ad = idblock.animation_data
    if not ad or not ad.action:
        return
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    if not cb:
        return
    for fc in list(cb.fcurves):
        if path is None or fc.data_path == path:
            cb.fcurves.remove(fc)


def shot_camera(name, frame, lens, collection):
    """A camera for one shot, bound to a timeline marker at the shot's first frame (the cut)."""
    scene = bpy.context.scene
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = 36.0
    cam.clip_start = 0.02
    cam.clip_end = 200.0
    ob = bpy.data.objects.new(name, cam)
    collection.objects.link(ob)
    mk = scene.timeline_markers.new(name, frame=frame)
    mk.camera = ob
    return ob


def retime_shot(name, frame):
    """Move a shot's cut: the marker of that camera goes to another frame."""
    for mk in bpy.context.scene.timeline_markers:
        if mk.name == name:
            mk.frame = frame


def clay():
    m = bpy.data.materials.get("Clay")
    if not m:
        m = bpy.data.materials.new("Clay")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.62, 0.60, 0.57, 1)
        b.inputs["Roughness"].default_value = 0.85
    return m


def show_between(ob, ranges):
    """Object renders only inside the given frame ranges [(f0, f1), ...]. Keys hide_render only:
    objects disabled in the viewport are not evaluated in background mode, so hide_viewport stays off."""
    clear_anim(ob, "hide_render")
    clear_anim(ob, "hide_viewport")
    ob.hide_viewport = False
    keys = {}
    if ranges[0][0] > 1:
        keys[1] = True
    for f0, f1 in ranges:
        keys[f0] = False
        keys[f1 + 1] = True
    for f in sorted(keys):
        if f > bpy.context.scene.frame_end:
            continue
        ob.hide_render = keys[f]
        ob.keyframe_insert("hide_render", frame=f)
    set_interp(ob, 'CONSTANT', "hide_render")


# ---- modelling helpers ----
def add_bevel(ob, width=0.002, segments=2, angle=35):
    m = ob.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.harden_normals = False
    return m


def box_between(bm, lo, hi):
    """Adds a box given by two corners; returns its new verts."""
    before = set(bm.verts)
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    s = [abs(hi[i] - lo[i]) for i in range(3)]
    box_bm(s, c, bm)
    return [v for v in bm.verts if v not in before]


def smooth_by_angle(ob, angle=40):
    me = ob.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.set_sharp_from_angle(angle=math.radians(angle))


def smooth_path(points, n_per=6):
    """Catmull-Rom resampling of a polyline (list of Vectors)."""
    pts = [Vector(p) for p in points]
    out = []
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, len(pts) - 1)]
        for k in range(n_per):
            t = k / n_per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


def tube(bm, points, radii, sides=8, cap=True):
    """Adds a tube along a polyline with a radius per point. Returns the rings of verts."""
    rings = []
    up = Vector((0, 0, 1))
    prev_x = None
    for i, p in enumerate(points):
        a = points[max(i - 1, 0)]; b = points[min(i + 1, len(points) - 1)]
        t = (Vector(b) - Vector(a)).normalized()
        x = t.cross(up)
        if x.length < 1e-4:
            x = t.cross(Vector((1, 0, 0)))
        x.normalize()
        if prev_x is not None and x.dot(prev_x) < 0:
            x = -x
        prev_x = x
        y = t.cross(x)
        r = radii[i] if hasattr(radii, "__len__") else radii
        rings.append([bm.verts.new(Vector(p) + (x * math.cos(2 * math.pi * k / sides) + y * math.sin(2 * math.pi * k / sides)) * r)
                      for k in range(sides)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(sides):
            f = bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
            f.smooth = True
    if cap:
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1])
    return rings


# ---- material helpers ----
def new_mat(name):
    """Fresh node material with Principled BSDF. Returns (material, node_tree, bsdf)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    return m, nt, b


def nd(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        if k in n.inputs:
            n.inputs[k].default_value = v
        else:
            setattr(n, k, v)
    return n


def _feed(nt, sock, val):
    if isinstance(val, bpy.types.NodeSocket):
        nt.links.new(val, sock)
    elif val is not None:
        if isinstance(val, (tuple, list)) and len(val) == 3 and len(sock.default_value) == 4:
            val = (*val, 1.0)
        sock.default_value = val


def mix(nt, fac, a, b, blend='MIX'):
    """Colour mix; fac/a/b may be sockets or constants. Returns the result socket."""
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = 'RGBA'
    n.blend_type = blend
    _feed(nt, n.inputs[0], fac)
    _feed(nt, n.inputs[6], a)
    _feed(nt, n.inputs[7], b)
    return n.outputs[2]


def math_node(nt, op, a, b=None, c=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    _feed(nt, n.inputs[0], a)
    if b is not None:
        _feed(nt, n.inputs[1], b)
    if c is not None:
        _feed(nt, n.inputs[2], c)
    return n.outputs[0]


def ramp(nt, fac, stops, interp='LINEAR'):
    """stops: [(pos, (r,g,b)) ...]. Returns the colour socket."""
    n = nt.nodes.new("ShaderNodeValToRGB")
    n.color_ramp.interpolation = interp
    els = n.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (p, c) in zip(els, stops):
        e.position = p
        e.color = (*c, 1.0) if len(c) == 3 else c
    _feed(nt, n.inputs[0], fac)
    return n.outputs[0]


def remap(nt, val, lo, hi, to_lo=0.0, to_hi=1.0):
    n = nt.nodes.new("ShaderNodeMapRange")
    n.clamp = True
    _feed(nt, n.inputs[0], val)
    n.inputs[1].default_value, n.inputs[2].default_value = lo, hi
    n.inputs[3].default_value, n.inputs[4].default_value = to_lo, to_hi
    return n.outputs[0]


def coords(nt, kind="Object", scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0)):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Location"].default_value = loc
    mp.inputs["Rotation"].default_value = rot
    nt.links.new(tc.outputs[kind], mp.inputs["Vector"])
    return mp.outputs[0]


def noise(nt, vec, scale, detail=2.0, rough=0.5, distortion=0.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    if vec is not None:
        nt.links.new(vec, n.inputs["Vector"])
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["Distortion"].default_value = distortion
    return n.outputs[0]


def bump(nt, height, strength=0.2, distance=0.001, normal=None):
    n = nt.nodes.new("ShaderNodeBump")
    n.inputs["Strength"].default_value = strength
    n.inputs["Distance"].default_value = distance
    _feed(nt, n.inputs["Height"], height)
    if normal is not None:
        nt.links.new(normal, n.inputs["Normal"])
    return n.outputs[0]


def set_mat(ob, mat, slot=0):
    mats = ob.data.materials
    while len(mats) <= slot:
        mats.append(None)
    mats[slot] = mat


# ---- lighting helpers ----
def key_values(idblock, path, keys, interp='CONSTANT', index=-1):
    """keys: [(frame, value), ...] on idblock.path; all keys get the same interpolation."""
    for f, v in keys:
        if index >= 0:
            getattr(idblock, path)[index] = v
        else:
            setattr(idblock, path, v)
        idblock.keyframe_insert(path, frame=f, index=index)
    set_interp(idblock, interp, path)


def key_socket(node_tree, socket, keys, interp='CONSTANT'):
    """Keyframes a node socket default_value (node tree animation)."""
    for f, v in keys:
        socket.default_value = v
        socket.keyframe_insert("default_value", frame=f)
    ad = node_tree.animation_data
    if ad and ad.action:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        path = socket.path_from_id("default_value")
        for fc in cb.fcurves:
            if fc.data_path == path:
                for kp in fc.keyframe_points:
                    kp.interpolation = interp


def aim_light(ob, direction):
    """Point a light so that it shines along the given direction."""
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector(direction).normalized().to_track_quat('-Z', 'Y')


def wood_material(name, dark, light, grain_axis='Y', band_scale=14.0, rough=0.45, coat=0.0, plank_attr=None,
                   bump_strength=0.2, contrast=0.35):
    """Procedural wood: straight grain bands of low contrast, soft blotches, fine pores, optional per-plank shift."""
    m, nt, b = new_mat(name)
    stretch = {'X': (0.03, 1, 1), 'Y': (1, 0.03, 1), 'Z': (1, 1, 0.03)}[grain_axis]
    oc = coords(nt, "Object", stretch)
    vec = oc
    shift = None
    if plank_attr:
        at = nd(nt, "ShaderNodeAttribute", attribute_name=plank_attr, attribute_type='GEOMETRY')
        add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = 'ADD'
        sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = 'SCALE'
        nt.links.new(at.outputs["Color"], sc.inputs[0]); sc.inputs[3].default_value = 7.0
        nt.links.new(oc, add.inputs[0]); nt.links.new(sc.outputs[0], add.inputs[1])
        vec = add.outputs[0]
        sepc = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(at.outputs["Color"], sepc.inputs[0])
        shift = sepc.outputs[0]
    grain = noise(nt, vec, band_scale, 4.0, 0.62, 0.6)
    fine = noise(nt, vec, band_scale * 9, 3.0, 0.6)
    pores = noise(nt, vec, 520.0, 3.0, 0.6)
    fac = math_node(nt, 'ADD', math_node(nt, 'MULTIPLY', grain, 0.75), math_node(nt, 'MULTIPLY', fine, 0.25))
    lo, hi = 0.5 - contrast, 0.5 + contrast
    col = ramp(nt, fac, [(lo, dark), (hi, light)])
    col = mix(nt, math_node(nt, 'MULTIPLY', remap(nt, pores, 0.45, 0.7), 0.25), col, tuple(c * 0.6 for c in dark))
    if shift is not None:
        hsv = nt.nodes.new("ShaderNodeHueSaturation")
        nt.links.new(col, hsv.inputs["Color"])
        nt.links.new(remap(nt, shift, 0.0, 1.0, 0.70, 1.18), hsv.inputs["Value"])
        col = hsv.outputs[0]
    nt.links.new(col, b.inputs["Base Color"])
    nt.links.new(remap(nt, math_node(nt, 'ADD', pores, fine), 0.5, 1.5, rough + 0.1, rough - 0.08), b.inputs["Roughness"])
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.2
    h = math_node(nt, 'ADD', math_node(nt, 'MULTIPLY', pores, 0.5), math_node(nt, 'MULTIPLY', fine, 0.5))
    nt.links.new(bump(nt, h, bump_strength, 0.0004), b.inputs["Normal"])
    return m


def set_dof(cam, focus_object=None, distance=None, fstop=2.8):
    d = cam.data.dof
    d.use_dof = True
    d.aperture_fstop = fstop
    if focus_object is not None:
        d.focus_object = focus_object
    elif distance is not None:
        d.focus_distance = distance
