# SPDX-License-Identifier: GPL-3.0-or-later
"""Puppet studio, part 1: armatures and the parts kit.

An armature template is a set of named joints and the bones between them,
like the wire inside a real stop-motion puppet. Its proportions (height,
head size, arm or body length, leg length) move the joints. Clay parts
from the kit are made to fit the armature: limbs and bodies are skinned so
they bend at the joints, heads, hands and feet ride rigidly on their bone.
Change a proportion and every kit part is made again to fit.

Bone names follow the conventions Make Puppet already reads (head, chest,
hips, hand.L, foot.L ...), so a finished build gets grab rings, pins and
knee targets with nothing else to set up.

Everything about a build is kept on the armature (arm["sm_build"]), and each
kit part keeps its recipe (ob["sm_part"]), so builds can be changed later.
"""

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

# ----------------------------------------------------------------- colours

COLOURS = {
    "skin": (0.93, 0.74, 0.58), "red": (0.80, 0.27, 0.16), "blue": (0.27, 0.42, 0.62),
    "green": (0.38, 0.58, 0.30), "yellow": (0.93, 0.74, 0.28), "brown": (0.42, 0.28, 0.17),
    "grey": (0.45, 0.45, 0.47), "white": (0.93, 0.91, 0.86), "black": (0.08, 0.07, 0.07),
    "purple": (0.48, 0.36, 0.62), "orange": (0.92, 0.50, 0.22), "fur": (0.70, 0.52, 0.32),
    "denim": (0.24, 0.30, 0.42), "dark": (0.18, 0.13, 0.11),
}


def clay(name):
    """A clay material for a colour name (shared)."""
    mat_name = "SM Clay " + name
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
        # the colours above are picked as you'd see them on screen: Blender wants linear light
        rgb = tuple(c ** 2.2 for c in COLOURS.get(name, (0.7, 0.7, 0.7)))
        mat.diffuse_color = (*rgb, 1.0)
        mat.roughness = 0.62
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.62
            for key in ("Subsurface Weight", "Subsurface"):
                if key in bsdf.inputs:
                    bsdf.inputs[key].default_value = 0.08
                    break
    return mat


# ----------------------------------------------------------------- templates
# Joints at height 1 (people) or body length 1 (four legs), in metres before
# scaling. y is front (-) to back (+). Each bone: (name, head joint, tail joint,
# parent, connected).

def _person(scale_head=1.0, child=False, tall=False):
    j = {
        "toe": (0.08, -0.10, 0.0), "ankle": (0.08, 0.0, 0.05), "knee": (0.08, -0.012, 0.27),
        "hip": (0.08, 0.0, 0.48), "pelvis": (0.0, 0.0, 0.46), "waist": (0.0, 0.0, 0.58),
        "chest": (0.0, 0.0, 0.70), "neck": (0.0, 0.0, 0.80), "skull": (0.0, 0.0, 0.84),
        "crown": (0.0, 0.0, 1.0), "shoulder": (0.17, 0.0, 0.77), "elbow": (0.20, 0.01, 0.60),
        "wrist": (0.22, 0.0, 0.45), "fingertip": (0.23, 0.0, 0.38),
    }
    return j


PERSON_BONES = [
    ("hips", "pelvis", "waist", None, False),
    ("spine", "waist", "chest", "hips", True),
    ("chest", "chest", "neck", "spine", True),
    ("neck", "neck", "skull", "chest", True),
    ("head", "skull", "crown", "neck", True),
    ("upper_arm.L", "shoulder.L", "elbow.L", "chest", False),
    ("forearm.L", "elbow.L", "wrist.L", "upper_arm.L", True),
    ("hand.L", "wrist.L", "fingertip.L", "forearm.L", True),
    ("thigh.L", "hip.L", "knee.L", "hips", False),
    ("shin.L", "knee.L", "ankle.L", "thigh.L", True),
    ("foot.L", "ankle.L", "toe.L", "shin.L", True),
]

FOUR_BONES = [
    ("hips", "rump", "back", None, False),
    ("spine", "back", "withers", "hips", True),
    ("chest", "withers", "neck", "spine", True),
    ("neck", "neck", "skull", "chest", True),
    ("head", "skull", "nose", "neck", True),
    ("tail", "tail_base", "tail_tip", "hips", False),
    ("front_upper_leg.L", "shoulder.L", "front_elbow.L", "chest", False),
    ("front_shin.L", "front_elbow.L", "front_wrist.L", "front_upper_leg.L", True),
    ("front_foot.L", "front_wrist.L", "front_toe.L", "front_shin.L", True),
    ("back_thigh.L", "hip.L", "stifle.L", "hips", False),
    ("back_shin.L", "stifle.L", "hock.L", "back_thigh.L", True),
    ("back_foot.L", "hock.L", "back_toe.L", "back_shin.L", True),
]

TEMPLATES = {
    # label, base height (m), bones, default proportions
    'PERSON': ("Person", 1.6, PERSON_BONES),
    'CHILD': ("Small child", 1.0, PERSON_BONES),
    'TALL': ("Tall", 1.9, PERSON_BONES),
    'FOUR_LEGS': ("Four legs", 0.9, FOUR_BONES),
}

DEFAULT_PROPS = {
    'PERSON': {"height": 1.0, "head": 1.0, "arms": 1.0, "legs": 1.0},
    'CHILD': {"height": 1.0, "head": 1.35, "arms": 0.9, "legs": 0.85},
    'TALL': {"height": 1.0, "head": 0.9, "arms": 1.08, "legs": 1.12},
    'FOUR_LEGS': {"height": 1.0, "head": 1.0, "arms": 1.0, "legs": 1.0},   # arms = body length here
}

PROP_LABELS = {
    "height": "Height", "head": "Head size", "arms": "Arm length", "legs": "Leg length",
}


def prop_label(template, key):
    if template == 'FOUR_LEGS' and key == "arms":
        return "Body length"
    return PROP_LABELS[key]


def _mirror(name):
    return name[:-2] + ".R" if name.endswith(".L") else name


def joints(template, props):
    """Named joint positions (armature space, metres) for a template and its proportions."""
    p = dict(DEFAULT_PROPS[template])
    p.update(props or {})
    size = TEMPLATES[template][1] * p["height"]
    if template == 'FOUR_LEGS':
        return _four_joints(size, p)
    head, arms, legs = p["head"], p["arms"], p["legs"]
    j = {}
    leg_h = 0.46 * legs                      # hip height
    lift = leg_h - 0.46
    # legs
    for side, sx in ((".L", 1), (".R", -1)):
        j["hip" + side] = Vector((0.08 * sx, 0.0, 0.48 + lift))
        j["knee" + side] = Vector((0.08 * sx, -0.012, 0.05 + (0.27 - 0.05) * legs))
        j["ankle" + side] = Vector((0.08 * sx, 0.0, 0.05))
        j["toe" + side] = Vector((0.08 * sx, -0.10, 0.0))
    j["pelvis"] = Vector((0, 0, 0.46 + lift))
    j["waist"] = Vector((0, 0, 0.58 + lift))
    j["chest"] = Vector((0, 0, 0.70 + lift))
    j["neck"] = Vector((0, 0, 0.80 + lift))
    j["skull"] = Vector((0, 0, 0.84 + lift))
    j["crown"] = Vector((0, 0, 0.84 + lift + 0.16 * head))
    for side, sx in ((".L", 1), (".R", -1)):
        sh = Vector((0.15 * sx, 0.0, 0.76 + lift))
        j["shoulder" + side] = sh
        j["elbow" + side] = sh + Vector((0.03 * sx, 0.01, -0.17)) * arms
        j["wrist" + side] = j["elbow" + side] + Vector((0.02 * sx, -0.01, -0.15)) * arms
        j["fingertip" + side] = j["wrist" + side] + Vector((0.01 * sx, 0.0, -0.07)) * max(arms, 0.8)
    # everything is in units of the base height
    return {k: v * size for k, v in j.items()}


def _four_joints(size, p):
    head, body, legs = p["head"], p["arms"], p["legs"]
    leg_h = 0.36 * legs
    j = {}
    half = 0.3 * body
    for side, sx in ((".L", 1), (".R", -1)):
        j["hip" + side] = Vector((0.09 * sx, half, leg_h))
        j["stifle" + side] = Vector((0.09 * sx, half - 0.05, leg_h * 0.55))
        j["hock" + side] = Vector((0.09 * sx, half + 0.04, leg_h * 0.2))
        j["back_toe" + side] = Vector((0.09 * sx, half - 0.04, 0.0))
        j["shoulder" + side] = Vector((0.09 * sx, -half, leg_h))
        j["front_elbow" + side] = Vector((0.09 * sx, -half + 0.03, leg_h * 0.55))
        j["front_wrist" + side] = Vector((0.09 * sx, -half, leg_h * 0.12))
        j["front_toe" + side] = Vector((0.09 * sx, -half - 0.07, 0.0))
    j["rump"] = Vector((0, half, leg_h + 0.04))
    j["back"] = Vector((0, 0.0, leg_h + 0.05))
    j["withers"] = Vector((0, -half, leg_h + 0.06))
    j["neck"] = Vector((0, -half - 0.04, leg_h + 0.08))
    j["skull"] = Vector((0, -half - 0.12, leg_h + 0.22))
    j["nose"] = j["skull"] + Vector((0, -0.2 * head, -0.02 * head))
    j["tail_base"] = Vector((0, half + 0.03, leg_h + 0.06))
    j["tail_tip"] = Vector((0, half + 0.25, leg_h + 0.22))
    return {k: v * size for k, v in j.items()}


def bone_defs(template):
    defs = []
    for name, h, t, parent, conn in TEMPLATES[template][2]:
        defs.append((name, h, t, parent, conn))
        if name.endswith(".L"):
            mp = _mirror(parent) if parent else None
            defs.append((_mirror(name), _mirror(h), _mirror(t), mp, conn))
    return defs


# ----------------------------------------------------------------- the build

def build_info(arm):
    try:
        return json.loads(arm.get("sm_build", "{}"))
    except (TypeError, ValueError):
        return {}


def set_build_info(arm, info):
    arm["sm_build"] = json.dumps(info)


def _active(context, ob):
    vl = context.view_layer
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob


def _place_bones(context, arm, template, props):
    """(Re)make the armature's bones from the template's joints, in edit mode."""
    j = joints(template, props)
    _active(context, arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    want = bone_defs(template)
    names = {d[0] for d in want}
    for b in list(eb):
        if b.name not in names:
            eb.remove(b)
    for name, h, t, _parent, _conn in want:
        b = eb.get(name) or eb.new(name)
        b.head, b.tail = j[h], j[t]
        b.roll = 0.0
    for name, _h, _t, parent, conn in want:
        b = eb[name]
        b.parent = eb[parent] if parent else None
        b.use_connect = bool(conn and parent)
    bpy.ops.object.mode_set(mode='OBJECT')
    return j


def new_build(context, name="Pip", template='PERSON', location=None):
    """A new armature to build a puppet on. Returns the armature object."""
    scene = context.scene
    data = bpy.data.armatures.new(name)
    data.display_type = 'STICK'
    arm = bpy.data.objects.new(name, data)
    scene.collection.objects.link(arm)
    if location is not None:
        arm.location = location
    arm.show_in_front = True
    props = dict(DEFAULT_PROPS[template])
    set_build_info(arm, {"template": template, "props": props, "parts": [], "hands": "MITTEN"})
    _place_bones(context, arm, template, props)
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm


def kit_parts(arm):
    return [ob for ob in arm.children if ob.get("sm_part")]


def change_build(context, arm, template=None, props=None):
    """Change the armature shape or proportions: bones move, kit parts are made again to fit."""
    info = build_info(arm)
    was_puppet = arm.stop_motion_puppet.enabled
    if was_puppet:
        _unpuppet(context, arm)
    _rest(arm)
    if template is not None and template != info.get("template"):
        # everything comes off the old armature; what fits goes back on the new one
        for ob in list(arm.children):
            if ob.get("sm_part") or ob.get("sm_face"):
                me = ob.data
                bpy.data.objects.remove(ob)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
        info["template"] = template
        info["props"] = dict(DEFAULT_PROPS[template])
        kit = KIT[template]
        keep = []
        for p in info.get("parts", []):
            if p["kind"] in kit:
                ok = {v for v, _l in kit[p["kind"]][1]}
                keep.append(dict(p, variant=p["variant"] if p["variant"] in ok else kit[p["kind"]][1][0][0]))
        info["parts"] = keep
        from . import faces as _faces
        info["faces"] = [f for f in info.get("faces", []) if f in _faces.FACE_SETS[template]]
        if template == 'FOUR_LEGS':
            info["hands_made"] = False
    if props:
        info["props"].update(props)
    set_build_info(arm, info)
    _place_bones(context, arm, info["template"], info["props"])
    remake_parts(context, arm)
    if was_puppet:
        finish_build(context, arm)
    return arm


def _rest(arm):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def _unpuppet(context, arm):
    from . import puppet
    pp = arm.stop_motion_puppet
    for r in pp.rings:
        c = puppet.pin_constraint(arm, r)
        if c is not None and not r.rig_ik:
            arm.pose.bones[r.pin_owner].constraints.remove(c)
        for o in (r.knee, r.pin):
            if o is not None:
                bpy.data.objects.remove(o)
    pp.rings.clear()
    pp.swap_sets.clear()
    pp.enabled = False


def finish_build(context, arm):
    """The build becomes a puppet: grab rings, swap sets, foot pins with knee targets."""
    from . import puppet
    _rest(arm)
    context.view_layer.update()
    puppet.make_puppet(context, arm)
    return arm.stop_motion_puppet


# ---------------------------------------------------------------- meshes

def _frames(points):
    """A smooth frame (tangent, normal, binormal) at each point (parallel transport)."""
    n = len(points)
    tangents = []
    for i in range(n):
        a = points[max(0, i - 1)]
        b = points[min(n - 1, i + 1)]
        t = (b - a)
        tangents.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    ref = Vector((1, 0, 0)) if abs(tangents[0].x) < 0.9 else Vector((0, 1, 0))
    normal = tangents[0].cross(ref).normalized()
    out = []
    for i, t in enumerate(tangents):
        if i:
            normal = (normal - t * normal.dot(t))
            normal = normal.normalized() if normal.length > 1e-9 else t.orthogonal().normalized()
        out.append((t, normal, t.cross(normal).normalized()))
    return out


def loft(bm, points, radii, segs=16, per_span=4, caps=True, squash=1.0):
    """A clay tube through `points` with `radii`, rounded at the ends."""
    pts, rad = [], []
    for i in range(len(points) - 1):
        for k in range(per_span):
            t = k / per_span
            # smooth in-between (cubic ease of the radius, straight path)
            pts.append(points[i].lerp(points[i + 1], t))
            s = t * t * (3 - 2 * t)
            rad.append(radii[i] + (radii[i + 1] - radii[i]) * s)
    pts.append(points[-1].copy())
    rad.append(radii[-1])
    frames = _frames(pts)
    rings = []

    def ring(c, r, nrm, bin_):
        vs = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            vs.append(bm.verts.new(c + (nrm * math.cos(a) + bin_ * math.sin(a) * squash) * r))
        return vs

    if caps:
        t0, n0, b0 = frames[0]
        for q in (4, 3, 2, 1):
            a = q / 5 * (math.pi / 2)
            rings.append(ring(pts[0] - t0 * rad[0] * math.sin(a), rad[0] * math.cos(a), n0, b0))
    for c, r, (t, nrm, bin_) in zip(pts, rad, frames):
        rings.append(ring(c, r, nrm, bin_))
    if caps:
        t1, n1, b1 = frames[-1]
        for q in (1, 2, 3, 4):
            a = q / 5 * (math.pi / 2)
            rings.append(ring(pts[-1] + t1 * rad[-1] * math.sin(a), rad[-1] * math.cos(a), n1, b1))
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    if caps:
        tip0 = bm.verts.new(pts[0] - frames[0][0] * rad[0])
        tip1 = bm.verts.new(pts[-1] + frames[-1][0] * rad[-1])
        first, last = rings[0], rings[-1]
        for k in range(segs):
            bm.faces.new((tip0, first[(k + 1) % segs], first[k]))
            bm.faces.new((tip1, last[k], last[(k + 1) % segs]))


def blob(bm, centre, radii, rot=None, segs=24, rings=14):
    """An ellipsoid (a ball of clay)."""
    m = Matrix.Translation(centre)
    if rot is not None:
        m = m @ rot.to_4x4()
    m = m @ Matrix.Diagonal((*radii, 1.0))
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0, matrix=m)


def _mesh_object(name, bm, colour, collection):
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(clay(colour))
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


# -------------------------------------------------------------- skinning

def _seg_dist(p, a, b):
    ab = b - a
    L = ab.length_squared
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / L))
    return (p - (a + ab * t)).length


def fill_unweighted(ob, arm, bones=None):
    """Points no bone moves (bits of clay heat weighting missed, like separate ears)
    follow the nearest bones. Returns how many were filled."""
    bones = bones or [b.name for b in arm.data.bones]
    segs = [(n, arm.data.bones[n].head_local.copy(), arm.data.bones[n].tail_local.copy()) for n in bones]
    groups = {g.name: g for g in ob.vertex_groups}
    inv = arm.matrix_world.inverted() @ ob.matrix_world
    n = 0
    for v in ob.data.vertices:
        if any(g.weight > 0.01 and ob.vertex_groups[g.group].name in groups for g in v.groups):
            continue
        p = inv @ v.co
        name = min(segs, key=lambda sg: _seg_dist(p, sg[1], sg[2]))[0]
        g = groups.get(name) or ob.vertex_groups.new(name=name)
        groups[name] = g
        g.add([v.index], 1.0, 'REPLACE')
        n += 1
    return n


def skin(ob, arm, bones, softness=0.5):
    """Bend `ob` with `bones`: each point follows the bones nearest it, blended
    across joints (softer = a wider blend)."""
    ob.vertex_groups.clear()
    segs = []
    for name in bones:
        b = arm.data.bones[name]
        segs.append((name, b.head_local.copy(), b.tail_local.copy()))
    groups = {name: ob.vertex_groups.new(name=name) for name, _a, _b in segs}
    power = 2.0 + (1.0 - softness) * 10.0
    inv = arm.matrix_world.inverted() @ ob.matrix_world
    for v in ob.data.vertices:
        p = inv @ v.co
        ds = [(max(_seg_dist(p, a, b), 1e-5), name) for name, a, b in segs]
        ds.sort()
        best = ds[:2]
        ws = [(1.0 / d) ** power for d, _n in best]
        total = sum(ws)
        for w, (_d, name) in zip(ws, best):
            if w / total > 0.01:
                groups[name].add([v.index], w / total, 'REPLACE')
    mod = ob.modifiers.get("SM Armature") or ob.modifiers.new("SM Armature", 'ARMATURE')
    mod.object = arm
    mod.use_deform_preserve_volume = True
    _parent_object(ob, arm)


def _parent_object(ob, arm):
    w = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = 'OBJECT'
    ob.matrix_parent_inverse = arm.matrix_world.inverted()
    ob.matrix_world = w


def attach_rigid(ob, arm, bone):
    """`ob` rides on `bone` (like a part pushed onto a wire), staying where it is."""
    w = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    b = arm.data.bones[bone]
    tail = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    ob.matrix_parent_inverse = tail.inverted()
    ob.matrix_basis = Matrix.Identity(4)
    ob.matrix_world = w


# ---------------------------------------------------------------- the kit
# kind -> (socket label, [(variant id, label)])

KIT = {
    'PERSON': {
        "head": ("Head", [("round", "Round head"), ("long", "Long head"), ("wide", "Wide jaw")]),
        "body": ("Body", [("pear", "Pear body"), ("barrel", "Barrel body"), ("slim", "Slim body")]),
        "arms": ("Arms", [("chunky", "Chunky arms"), ("thin", "Thin arms")]),
        "legs": ("Legs", [("trousers", "Trousers"), ("skirt", "Skirt"), ("bare", "Bare legs")]),
        "feet": ("Feet", [("shoes", "Shoes"), ("boots", "Boots"), ("bare", "Bare feet")]),
    },
    'FOUR_LEGS': {
        "head": ("Head", [("dog", "Dog head"), ("cat", "Cat head")]),
        "body": ("Body", [("barrel", "Barrel body"), ("slim", "Slim body")]),
        "legs": ("Legs", [("sturdy", "Sturdy legs"), ("thin", "Thin legs")]),
        "feet": ("Paws", [("paws", "Paws"), ("hooves", "Hooves")]),
        "tail": ("Tail", [("thick", "Thick tail"), ("thin", "Thin tail")]),
    },
}
KIT['CHILD'] = KIT['PERSON']
KIT['TALL'] = KIT['PERSON']
KIT_KINDS = {k: set(v) for k, v in KIT.items()}

DEFAULT_COLOUR = {"head": "skin", "body": "blue", "arms": "blue", "legs": "denim", "feet": "dark",
                  "tail": "fur"}
DEFAULT_COLOUR_FOUR = {"head": "fur", "body": "fur", "legs": "fur", "feet": "dark", "tail": "fur"}


def default_colour(arm, kind):
    four = build_info(arm).get("template") == 'FOUR_LEGS'
    return (DEFAULT_COLOUR_FOUR if four else DEFAULT_COLOUR).get(kind, "grey")
SIDES = {"arms", "legs", "feet"}


def kit_for(arm):
    return KIT[build_info(arm).get("template", 'PERSON')]


def _j(arm):
    info = build_info(arm)
    if info.get("joints"):            # rigged from a sculpt: its own joints
        j = {k: Vector(v) for k, v in info["joints"].items()}
    else:
        j = joints(info["template"], info["props"])
    mw = arm.matrix_world
    return {k: mw @ v for k, v in j.items()}, info


def _part_name(arm, kind, side=""):
    return "%s %s%s" % (arm.name, kind.capitalize(), (" " + side) if side else "")


def make_part(context, arm, kind, variant, colour=None, side=""):
    """Make one kit part to fit `arm`, attach it, and return the object."""
    J, info = _j(arm)
    template = info["template"]
    four = template == 'FOUR_LEGS'
    s = TEMPLATES[template][1] * info["props"]["height"]
    head_k = info["props"]["head"]
    colour = colour or default_colour(arm, kind)
    col = arm.users_collection[0] if arm.users_collection else context.scene.collection
    bm = bmesh.new()
    sx = 1 if side != "R" else -1
    sfx = "." + side if side else ""
    rigid = None
    bones = []
    if kind == "head" and not four:
        c = (J["skull"] + J["crown"]) / 2
        r = (J["crown"] - J["skull"]).length * 0.62
        if variant == "long":
            blob(bm, c, (r * 0.8, r * 0.85, r * 1.15))
        elif variant == "wide":
            blob(bm, c + Vector((0, 0, -r * 0.15)), (r * 1.12, r * 0.95, r * 0.95))
        else:
            blob(bm, c, (r, r * 0.95, r * 0.98))
        blob(bm, c + Vector((0, -r * 0.95, -r * 0.1)), (r * 0.2, r * 0.2, r * 0.18), segs=12, rings=8)   # nose
        for ex in (1, -1):
            blob(bm, c + Vector((ex * r * 0.98, 0, -r * 0.05)), (r * 0.12, r * 0.22, r * 0.28), segs=12, rings=8)  # ears
        rigid = "head"
    elif kind == "head" and four:
        a, b = J["skull"], J["nose"]
        r = (b - a).length * 0.42
        blob(bm, a, (r * 1.05, r * 1.1, r))
        loft(bm, [a + Vector((0, -r * 0.3, -r * 0.2)), b], [r * 0.62, r * 0.38], segs=14)   # snout
        blob(bm, b + Vector((0, -r * 0.05, r * 0.05)), (r * 0.18, r * 0.15, r * 0.14), segs=12, rings=8)
        for ex in (1, -1):
            if variant == "cat":
                bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r * 0.35, radius2=0.0, depth=r * 0.7,
                                      matrix=Matrix.Translation(a + Vector((ex * r * 0.6, 0.0, r * 1.0))))
            else:
                blob(bm, a + Vector((ex * r * 0.95, r * 0.15, r * 0.1)), (r * 0.18, r * 0.35, r * 0.7),
                     rot=Matrix.Rotation(ex * -0.4, 3, 'Y'), segs=12, rings=8)
        rigid = "head"
    elif kind == "body" and not four:
        bot, mid, top, neck = J["pelvis"], J["waist"], J["chest"], J["neck"]
        w = [s * x for x in {"pear": (0.13, 0.12, 0.115, 0.06), "barrel": (0.115, 0.13, 0.13, 0.06),
                             "slim": (0.095, 0.085, 0.1, 0.05)}.get(variant, (0.12, 0.12, 0.115, 0.06))]
        pts = [bot - Vector((0, 0, s * 0.03)), mid, top, neck + Vector((0, 0, s * 0.02))]
        loft(bm, pts, w, segs=20, squash=0.8)
        bones = ["hips", "spine", "chest", "neck"]
    elif kind == "body" and four:
        pts = [J["tail_base"], J["rump"], J["back"], J["withers"], J["neck"] + Vector((0, 0, s * 0.03))]
        th = 0.15 if variant == "barrel" else 0.11
        loft(bm, pts, [s * th * 0.6, s * th, s * th * 1.05, s * th * 1.0, s * th * 0.7], segs=20, squash=0.9)
        loft(bm, [J["withers"], J["neck"], J["skull"]], [s * th * 0.8, s * 0.06, s * 0.05], segs=14)
        bones = ["hips", "spine", "chest", "neck"]
    elif kind == "arms":
        a, b, c = J["shoulder" + sfx], J["elbow" + sfx], J["wrist" + sfx]
        r = s * (0.04 if variant == "chunky" else 0.028)
        inward = Vector(((J["neck"] - a).x * 0.35, 0, -s * 0.01))      # tuck the shoulder into the body
        loft(bm, [a + inward, a, b, c], [r * 1.25, r * 1.15, r, r * 0.85], segs=14, per_span=3)
        bones = ["upper_arm" + sfx, "forearm" + sfx]
    elif kind == "legs" and not four:
        a, b, c = J["hip" + sfx], J["knee" + sfx], J["ankle" + sfx]
        r = s * 0.045
        if variant == "skirt":
            loft(bm, [a + Vector((0, 0, s * 0.03)), b], [r * 1.3, r * 1.9], segs=14)
            loft(bm, [b, c + Vector((0, 0, s * 0.02))], [r * 0.6, r * 0.5], segs=12)
        else:
            loft(bm, [a + Vector((0, 0, s * 0.02)), b, c + Vector((0, 0, s * 0.02))],
                 [r * 1.15, r * 0.95, r * (0.85 if variant == "trousers" else 0.6)], segs=14)
        bones = ["thigh" + sfx, "shin" + sfx]
        if variant == "skirt":
            bones = ["hips"] + bones
    elif kind == "legs" and four:
        r = s * (0.05 if variant == "sturdy" else 0.035)
        for pre, a_, b_, c_, up, low in (("front", "shoulder", "front_elbow", "front_wrist", "front_upper_leg", "front_shin"),
                                         ("back", "hip", "stifle", "hock", "back_thigh", "back_shin")):
            loft(bm, [J[a_ + sfx] + Vector((0, 0, s * 0.03)), J[b_ + sfx], J[c_ + sfx]], [r * 1.25, r * 0.9, r * 0.75], segs=12)
            bones += [up + sfx, low + sfx]
    elif kind == "feet" and not four:
        a, t = J["ankle" + sfx], J["toe" + sfx]
        r = s * 0.035
        if variant == "boots":
            loft(bm, [a + Vector((0, 0, s * 0.09)), a], [r * 1.25, r * 1.25], segs=14)
        floor = t.z                                   # toes are on the floor
        mid = (a + t) / 2
        if variant == "bare":
            blob(bm, Vector((mid.x, mid.y, floor + r * 0.6)), (r * 0.8, (t - a).length * 0.65, r * 0.6))
        else:
            blob(bm, Vector((mid.x, mid.y - r * 0.2, floor + r * 0.75)), (r * 1.1, (t - a).length * 0.8, r * 0.75))
        rigid = "foot" + sfx
    elif kind == "feet" and four:
        objs = []
        for pre, w_, t_ in (("front", "front_wrist", "front_toe"), ("back", "hock", "back_toe")):
            bm2 = bmesh.new()
            a, t = J[w_ + sfx], J[t_ + sfx]
            r = s * 0.04
            if variant == "hooves":
                loft(bm2, [a, (a + t) / 2], [r * 0.8, r * 1.0], segs=12)
            else:
                blob(bm2, (a + t) / 2 + Vector((0, 0, r * 0.4)), (r * 0.9, (t - a).length * 0.6, r * 0.6))
            ob = _mesh_object(_part_name(arm, "%s paw" % pre, side), bm2, colour, col)
            attach_rigid(ob, arm, "%s_foot%s" % (pre, sfx))
            ob["sm_part"] = json.dumps({"kind": kind, "variant": variant, "colour": colour, "side": side})
            objs.append(ob)
        bm.free()
        return objs[0]
    elif kind == "tail":
        a, b = J["tail_base"], J["tail_tip"]
        r = s * (0.035 if variant == "thick" else 0.018)
        mid = (a + b) / 2 + Vector((0, 0, s * 0.04))
        loft(bm, [a, mid, b], [r, r * 0.9, r * 0.45], segs=12)
        bones = ["tail"]
    else:
        bm.free()
        raise ValueError("no %s part called %s" % (kind, variant))
    ob = _mesh_object(_part_name(arm, kind, side), bm, colour, col)
    ob["sm_part"] = json.dumps({"kind": kind, "variant": variant, "colour": colour, "side": side})
    if rigid:
        attach_rigid(ob, arm, rigid)
    else:
        skin(ob, arm, bones, softness=build_info(arm).get("softness", 0.5))
    return ob


def add_part(context, arm, kind, variant, colour=None):
    """Put a kit part on the puppet (both sides for arms, legs and feet). A part
    of the same kind already there is swapped out."""
    info = build_info(arm)
    remove_kind(arm, kind)
    entry = {"kind": kind, "variant": variant, "colour": colour or default_colour(arm, kind)}
    info["parts"] = [p for p in info.get("parts", []) if p["kind"] != kind] + [entry]
    set_build_info(arm, info)
    was_puppet = arm.stop_motion_puppet.enabled
    if was_puppet:
        _unpuppet(context, arm)
        _rest(arm)
    out = _make_entry(context, arm, entry)
    if was_puppet:
        finish_build(context, arm)
    return out


def _make_entry(context, arm, entry):
    context.view_layer.update()
    if entry["kind"] in SIDES:
        return [make_part(context, arm, entry["kind"], entry["variant"], entry["colour"], side)
                for side in ("L", "R")]
    return [make_part(context, arm, entry["kind"], entry["variant"], entry["colour"])]


def remove_kind(arm, kind):
    for ob in list(kit_parts(arm)):
        try:
            if json.loads(ob["sm_part"])["kind"] == kind:
                me = ob.data
                bpy.data.objects.remove(ob)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
        except (KeyError, ValueError):
            pass


def set_colour(context, arm, kind, colour):
    info = build_info(arm)
    for p in info.get("parts", []):
        if p["kind"] == kind:
            p["colour"] = colour
    set_build_info(arm, info)
    for ob in kit_parts(arm):
        if json.loads(ob["sm_part"])["kind"] == kind:
            ob.data.materials.clear()
            ob.data.materials.append(clay(colour))


def remake_parts(context, arm):
    """Make every kit part again from its recipe (after the armature changed)."""
    info = build_info(arm)
    for p in info.get("parts", []):
        remove_kind(arm, p["kind"])
    for p in info.get("parts", []):
        _make_entry(context, arm, p)
    from . import faces
    faces.remake(context, arm)


def starter(context, arm):
    """A complete first puppet, to change part by part."""
    info = build_info(arm)
    kit = KIT[info["template"]]
    for kind, (_label, variants) in kit.items():
        add_part(context, arm, kind, variants[0][0])
    return arm


# --------------------------------------------------------------- operators

from bpy.props import EnumProperty, FloatProperty, StringProperty  # noqa: E402


def _arm(context, name=""):
    ob = bpy.data.objects.get(name) if name else context.active_object
    while ob is not None and ob.type != 'ARMATURE':
        ob = ob.parent
    return ob if ob is not None and ob.get("sm_build") else None


class SM_OT_new_build(bpy.types.Operator):
    """Start a new puppet on a wire armature, with a first set of parts to change"""
    bl_idname = "stop_motion.new_build"
    bl_label = "New Puppet"
    bl_options = {'REGISTER', 'UNDO'}

    template: EnumProperty(items=[(k, v[0], "") for k, v in TEMPLATES.items()], default='PERSON')
    name: StringProperty(default="")

    def execute(self, context):
        scene = context.scene
        n = self.name or ("Pip" if self.template != 'FOUR_LEGS' else "Biscuit")
        from . import library
        loc = library._drop_point(scene, context.evaluated_depsgraph_get())
        arm = new_build(context, n, self.template, loc)
        starter(context, arm)
        _active(context, arm)
        return {'FINISHED'}


class SM_OT_build_part(bpy.types.Operator):
    """Put this part on the puppet"""
    bl_idname = "stop_motion.build_part"
    bl_label = "Use Part"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    kind: StringProperty()
    variant: StringProperty()
    colour: StringProperty(default="")

    def execute(self, context):
        arm = _arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        add_part(context, arm, self.kind, self.variant, self.colour or None)
        return {'FINISHED'}


class SM_OT_build_colour(bpy.types.Operator):
    """Colour this part"""
    bl_idname = "stop_motion.build_colour"
    bl_label = "Part Colour"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    kind: StringProperty()
    colour: StringProperty()

    def execute(self, context):
        arm = _arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        set_colour(context, arm, self.kind, self.colour)
        return {'FINISHED'}


class SM_OT_build_shape(bpy.types.Operator):
    """Change the armature: its kind or one of its proportions"""
    bl_idname = "stop_motion.build_shape"
    bl_label = "Armature"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    template: StringProperty(default="")
    prop: StringProperty(default="")
    value: FloatProperty(default=1.0)

    def execute(self, context):
        arm = _arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        props = {self.prop: self.value} if self.prop else None
        change_build(context, arm, self.template or None, props)
        return {'FINISHED'}


class SM_OT_finish_build(bpy.types.Operator):
    """Make the build a puppet: grab rings, swap parts, foot pins"""
    bl_idname = "stop_motion.finish_build"
    bl_label = "Finish Puppet"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()

    def execute(self, context):
        arm = _arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        pp = finish_build(context, arm)
        self.report({'INFO'}, "%s: %d rings, %d swap sets" % (arm.name, len(pp.rings), len(pp.swap_sets)))
        return {'FINISHED'}


classes = (SM_OT_new_build, SM_OT_build_part, SM_OT_build_colour, SM_OT_build_shape, SM_OT_finish_build)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
