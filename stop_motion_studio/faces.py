# SPDX-License-Identifier: GPL-3.0-or-later
"""Puppet studio, part 3: faces and hands as swap parts.

Like a box of replacement mouths: each set is several separate pieces on
one socket, and one shows at a time. Pieces are named Set_Part (Mouth_O,
LeftHand_Fist), so Make Puppet turns them into swap sets that each shot
remembers. Mouths are picked by hand, shot by shot.

Pieces sit on the kit head's surface (found by casting onto it from the
front), and are made again when the armature's proportions change.
"""

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import assembly

FACE_SETS = {
    'PERSON': {
        "Mouth": ["Rest", "AI", "E", "O", "U", "MBP", "FV", "Smile"],
        "Eyes": ["Open", "Half", "Shut", "LookLeft", "LookRight"],
        "Brows": ["Flat", "Up", "Cross"],
    },
    'FOUR_LEGS': {
        "Mouth": ["Shut", "Open", "Pant", "Growl"],
        "Eyes": ["Open", "Half", "Shut"],
    },
}
FACE_SETS['CHILD'] = FACE_SETS['PERSON']
FACE_SETS['TALL'] = FACE_SETS['PERSON']
HAND_SHAPES = ["Open", "Relaxed", "Fist", "Point", "Grip", "ThumbsUp"]
HAND_STYLES = [("MITTEN", "Mitten", "Mitten hands"), ("FINGERS", "4 fingers", "Hands with four fingers")]


def face_pieces(arm):
    return [ob for ob in arm.children if ob.get("sm_face")]


def _remove_set(arm, set_name):
    for ob in face_pieces(arm):
        if ob["sm_face"].split("_", 1)[0] == set_name:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)


def _head_part(arm):
    for ob in assembly.kit_parts(arm):
        if json.loads(ob["sm_part"])["kind"] == "head":
            return ob
    sculpt = assembly.build_info(arm).get("sculpt")     # a rigged sculpt: pieces go on its own face
    return bpy.data.objects.get(sculpt) if sculpt else None


def _head_tree(context, head):
    context.view_layer.update()
    dg = context.evaluated_depsgraph_get()
    he = head.evaluated_get(dg)
    me = he.to_mesh()
    try:
        mw = he.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        he.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def _on_face(tree, origin, forward):
    """Where the head's surface is in front of `origin` (looking back from out in
    front along -forward); (point, outward normal) or None."""
    loc, nrm, _i, _d = tree.ray_cast(origin + forward * 5.0, -forward, 10.0)
    if loc is None:
        return None
    if nrm.dot(forward) < 0:
        nrm = -nrm
    return loc, nrm


def _flat(bm, outline, centre, right, up, out, depth):
    """A flat piece (mouth, lid) from a 2D outline, set into the surface."""
    top = [bm.verts.new(centre + right * x + up * y + out * depth * 0.4) for x, y in outline]
    bot = [bm.verts.new(centre + right * x + up * y - out * depth * 0.6) for x, y in outline]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    n = len(outline)
    for k in range(n):
        bm.faces.new((top[k], bot[k], bot[(k + 1) % n], top[(k + 1) % n]))


def _arc(cx, cy, rx, ry, a0, a1, steps=10):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * k / steps), cy + ry * math.sin(a0 + (a1 - a0) * k / steps))
            for k in range(steps + 1)]


def mouth_outline(shape, w):
    """2D outline of a mouth shape, about `w` wide. Returns (outline, teeth outline or None)."""
    pi = math.pi
    if shape in ("Rest", "Shut"):
        return [(-w / 2, 0.02 * w), (0, -0.04 * w), (w / 2, 0.02 * w), (w / 2, -0.04 * w), (0, -0.1 * w), (-w / 2, -0.04 * w)], None
    if shape in ("AI", "Open"):
        return _arc(0, 0, w / 2, 0.45 * w, pi, 2 * pi) + _arc(0, 0, w / 2, 0.06 * w, 0, pi)[1:-1], None
    if shape == "E":
        o = _arc(0, 0, w / 2, 0.22 * w, pi, 2 * pi) + _arc(0, 0, w / 2, 0.05 * w, 0, pi)[1:-1]
        return o, [(-w * 0.38, 0.0), (w * 0.38, 0.0), (w * 0.36, -0.06 * w), (-w * 0.36, -0.06 * w)]
    if shape == "O":
        return _arc(0, 0, 0.26 * w, 0.32 * w, 0, 2 * pi, 16)[:-1], None
    if shape == "U":
        return _arc(0, 0, 0.15 * w, 0.18 * w, 0, 2 * pi, 12)[:-1], None
    if shape == "MBP":
        return [(-w * 0.42, 0.0), (w * 0.42, 0.0), (w * 0.42, -0.05 * w), (-w * 0.42, -0.05 * w)], None
    if shape == "FV":
        o = _arc(0, 0, w * 0.42, 0.18 * w, pi, 2 * pi) + [(w * 0.42, 0.02 * w), (-w * 0.42, 0.02 * w)]
        return o, [(-w * 0.3, 0.02 * w), (w * 0.3, 0.02 * w), (w * 0.28, -0.07 * w), (-w * 0.28, -0.07 * w)]
    if shape == "Smile":
        outer = _arc(0, 0.12 * w, w / 2, 0.42 * w, pi * 1.05, pi * 1.95)
        inner = _arc(0, 0.12 * w, w * 0.42, 0.3 * w, pi * 1.92, pi * 1.08)
        return outer + inner, None
    if shape == "Pant":
        return _arc(0, 0, w / 2, 0.5 * w, pi, 2 * pi) + _arc(0, 0, w / 2, 0.05 * w, 0, pi)[1:-1], None
    if shape == "Growl":
        o = _arc(0, 0, w / 2, 0.25 * w, pi, 2 * pi) + _arc(0, 0, w / 2, 0.08 * w, 0, pi)[1:-1]
        return o, [(-w * 0.4, 0.0), (w * 0.4, 0.0), (w * 0.3, -0.12 * w), (-w * 0.3, -0.12 * w)]
    return mouth_outline("Rest", w)


def _piece(arm, set_name, part, bm, colour, bone, collection, extra=None):
    me = bpy.data.meshes.new("%s_%s" % (set_name, part))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(assembly.clay(colour))
    if extra:
        me.materials.append(assembly.clay(extra))
    ob = bpy.data.objects.new("%s_%s" % (set_name, part), me)
    collection.objects.link(ob)
    assembly.attach_rigid(ob, arm, bone)
    ob["sm_face"] = "%s_%s" % (set_name, part)
    ob["sm_order"] = len([o for o in arm.children if o.get("sm_face", "").split("_", 1)[0] == set_name]) - 1
    ob.hide_render = ob.hide_viewport = False
    return ob


def make_set(context, arm, set_name):
    """Make every piece of a face set on the puppet's head. Returns the pieces."""
    info = assembly.build_info(arm)
    template = info["template"]
    head = _head_part(arm)
    if head is None:
        raise ValueError("Put a head on first")
    _remove_set(arm, set_name)
    tree = _head_tree(context, head)
    J, _i = assembly._j(arm)
    mw3 = arm.matrix_world.to_3x3()
    up = (mw3 @ Vector((0, 0, 1))).normalized()
    right = (mw3 @ Vector((-1, 0, 0))).normalized()      # the puppet's right, seen from the front
    four = template == 'FOUR_LEGS'
    if four:
        a, b = J["skull"], J["nose"]
        fwd = (b - a).normalized()
        r = (b - a).length * 0.42
        centre = a
        up = (up - fwd * up.dot(fwd)).normalized()
    else:
        fwd = (mw3 @ Vector((0, -1, 0))).normalized()
        centre = (J["skull"] + J["crown"]) / 2
        r = (J["crown"] - J["skull"]).length * 0.62
    col = arm.users_collection[0] if arm.users_collection else context.scene.collection
    out = []
    names = FACE_SETS[template][set_name]
    for k, part in enumerate(names):
        bm = bmesh.new()
        if set_name == "Mouth":
            if four:
                hit = _on_face(tree, b - fwd * r * 0.25 - up * r * 0.1, -up) or (b - up * r * 0.3, -up)
                p, n = hit
                rt = right
                upv = -fwd
            else:
                hit = _on_face(tree, centre - up * r * 0.42, fwd)
                if hit is None:
                    continue
                p, n = hit
                rt, upv = right, up
            outline, teeth = mouth_outline(part, r * 0.62)
            _flat(bm, outline, p, rt, upv, n, r * 0.12)
            if teeth:
                n_faces = len(bm.faces)
                _flat(bm, teeth, p + n * r * 0.02, rt, upv, n, r * 0.06)
                for f in list(bm.faces)[n_faces:]:
                    f.material_index = 1
            out.append(_piece(arm, "Mouth", part, bm, "dark", "head", col, "white" if teeth else None))
        elif set_name == "Eyes":
            for side in (1, -1):
                o = centre + up * r * (0.12 if not four else 0.3) + right * side * r * 0.36
                hit = _on_face(tree, o, fwd)
                if hit is None:
                    continue
                p, n = hit
                er = r * 0.2
                c = p - n * er * 0.35
                assembly.blob(bm, c, (er, er, er * 1.1), segs=16, rings=10)
                look = {"LookLeft": -1, "LookRight": 1}.get(part, 0)
                pupil = c + n * er * 0.85 + right * look * er * 0.45
                n_before = len(bm.faces)
                assembly.blob(bm, pupil, (er * 0.38, er * 0.38, er * 0.38), segs=12, rings=8)
                for f in list(bm.faces)[n_before:]:
                    f.material_index = 1
                if part in ("Half", "Shut"):
                    n_before = len(bm.faces)
                    lid_c = c + up * er * (0.35 if part == "Half" else -0.1)
                    assembly.blob(bm, lid_c + n * er * 0.12, (er * 1.08, er * 1.08, er * (0.7 if part == "Half" else 1.15)),
                                  segs=16, rings=10)
                    for f in list(bm.faces)[n_before:]:
                        f.material_index = 2
            ob = _piece(arm, "Eyes", part, bm, "white", "head", col, "black")
            hp = _head_part(arm)
            lid = json.loads(hp["sm_part"])["colour"] if hp.get("sm_part") else "skin"
            ob.data.materials.append(assembly.clay(lid))
            out.append(ob)
        elif set_name == "Brows":
            for side in (1, -1):
                o = centre + up * r * 0.42 + right * side * r * 0.36
                hit = _on_face(tree, o, fwd)
                if hit is None:
                    continue
                p, n = hit
                tilt = {"Flat": 0.0, "Up": 0.0, "Cross": -0.35 * side}[part]
                lift = {"Flat": 0.0, "Up": r * 0.12, "Cross": 0.0}[part]
                inner = p + right * -side * r * 0.16 + up * (lift + tilt * r * 0.25)
                outer = p + right * side * r * 0.16 + up * (lift - tilt * r * 0.25)
                arch = (inner + outer) / 2 + up * r * (0.06 if part != "Cross" else 0.0) + n * r * 0.04
                assembly.loft(bm, [inner + n * r * 0.02, arch, outer + n * r * 0.02], [r * 0.045, r * 0.055, r * 0.04], segs=8)
            out.append(_piece(arm, "Brows", part, bm, "dark", "head", col))
    info.setdefault("faces", [])
    if set_name not in info["faces"]:
        info["faces"].append(set_name)
    assembly.set_build_info(arm, info)
    _show_first(out)
    return out


def _show_first(pieces):
    for i, ob in enumerate(pieces):
        ob.hide_viewport = ob.hide_render = (i != 0)


def make_hands(context, arm, style=None):
    """Hand shapes on both hands (people only): open, fist, point, grip."""
    info = assembly.build_info(arm)
    if info["template"] == 'FOUR_LEGS':
        return []
    style = style or info.get("hands", "MITTEN")
    info["hands"] = style
    assembly.set_build_info(arm, info)
    J, _i = assembly._j(arm)
    s = assembly.TEMPLATES[info["template"]][1] * info["props"]["height"]
    col = arm.users_collection[0] if arm.users_collection else context.scene.collection
    skin = "skin"
    head = _head_part(arm)
    if head is not None and head.get("sm_part"):
        skin = json.loads(head["sm_part"])["colour"]
    out = []
    for side, sname in (("L", "LeftHand"), ("R", "RightHand")):
        _remove_set(arm, sname)
        sfx = "." + side
        w, tip = J["wrist" + sfx], J["fingertip" + sfx]
        along = (tip - w).normalized()
        sx = 1 if side == "L" else -1
        mw3 = arm.matrix_world.to_3x3()
        fwd = (mw3 @ Vector((0, -1, 0))).normalized()
        outward = along.cross(fwd).normalized() * -sx
        palm_c = w + along * (tip - w).length * 0.42
        pr = s * 0.032
        pieces = []
        for shape in HAND_SHAPES:
            bm = bmesh.new()
            rot = Matrix((outward, fwd, along)).transposed()
            if shape in ("Fist", "Point", "ThumbsUp"):
                assembly.blob(bm, palm_c, (pr * 0.95, pr * 0.9, pr * 1.0), rot=rot)
            elif shape == "Relaxed":
                assembly.blob(bm, palm_c - fwd * pr * 0.05, (pr * 0.85, pr * 0.6, pr * 1.05), rot=rot)
                arc = [palm_c + fwd * pr * 0.25 * math.cos(a) + along * pr * (0.75 + 0.35 * math.sin(a)) for a in (-0.4, 0.5, 1.3)]
                assembly.loft(bm, arc, [pr * 0.4] * 3, segs=10, per_span=3)
            elif shape == "Grip":
                assembly.blob(bm, palm_c - fwd * pr * 0.1, (pr * 0.6, pr * 0.95, pr * 1.0), rot=rot)
                arc = [palm_c + fwd * pr * 0.3 * math.cos(a) + along * pr * (0.6 + 0.5 * math.sin(a)) - outward * pr * 0.2
                       for a in (-0.3, 0.8, 1.9, 2.8)]
                assembly.loft(bm, arc, [pr * 0.42] * 4, segs=10, per_span=3)
            else:
                assembly.blob(bm, palm_c, (pr * 0.9, pr * 0.45, pr * 1.1), rot=rot)
            # thumb (pointing up, away from the fingers, for a thumbs-up)
            if shape == "ThumbsUp":
                a = palm_c - fwd * pr * 0.6 - along * pr * 0.35
                assembly.loft(bm, [a, a - along * pr * 1.1], [pr * 0.3, pr * 0.26], segs=10)
            else:
                assembly.blob(bm, palm_c - fwd * pr * 0.55 - along * pr * 0.2, (pr * 0.3, pr * 0.3, pr * 0.55),
                              rot=Matrix.Rotation(0.5 * sx, 3, along) @ rot, segs=12, rings=8)
            if style == "FINGERS" and shape == "Open":
                for k in range(4):
                    off = outward * pr * (0.6 - 0.4 * k)
                    a = palm_c + along * pr * 0.9 + off
                    assembly.loft(bm, [a, a + along * pr * (0.9 + 0.15 * (1.5 - abs(1.5 - k)))], [pr * 0.2, pr * 0.17], segs=8)
            if shape == "Point":
                a = palm_c + along * pr * 0.7 + outward * pr * 0.45 - fwd * pr * 0.2
                assembly.loft(bm, [a, a + along * pr * 1.3], [pr * 0.22, pr * 0.19], segs=8)
            pieces.append(_piece(arm, sname, shape, bm, skin, "hand" + sfx, col))
        _show_first(pieces)
        out += pieces
    return out


def remake(context, arm):
    """After the armature changed: make the face sets and hands again to fit."""
    info = assembly.build_info(arm)
    for name in list(info.get("faces", [])):
        if _head_part(arm) is not None:
            make_set(context, arm, name)
    if info.get("hands_made") and info["template"] != 'FOUR_LEGS':
        make_hands(context, arm)


def make_all(context, arm):
    """The face sets for this kind of puppet, and hands."""
    info = assembly.build_info(arm)
    was = arm.stop_motion_puppet.enabled
    if was:
        assembly._unpuppet(context, arm)
        assembly._rest(arm)
    for name in FACE_SETS[info["template"]]:
        make_set(context, arm, name)
    if info["template"] != 'FOUR_LEGS':
        make_hands(context, arm)
        info = assembly.build_info(arm)
        info["hands_made"] = True
        assembly.set_build_info(arm, info)
    if was:
        assembly.finish_build(context, arm)


# --------------------------------------------------------------- operators

from bpy.props import EnumProperty, StringProperty  # noqa: E402


class SM_OT_make_faces(bpy.types.Operator):
    """Make mouths, eyes, brows and hand shapes as swap parts"""
    bl_idname = "stop_motion.make_faces"
    bl_label = "Make Face and Hands"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    only: StringProperty(default="")

    def execute(self, context):
        arm = assembly._arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        if _head_part(arm) is None:
            self.report({'WARNING'}, "Put a head on first")
            return {'CANCELLED'}
        was = arm.stop_motion_puppet.enabled
        if self.only:
            if was:
                assembly._unpuppet(context, arm)
                assembly._rest(arm)
            make_set(context, arm, self.only)
            if was:
                assembly.finish_build(context, arm)
        else:
            make_all(context, arm)
        return {'FINISHED'}


class SM_OT_hand_style(bpy.types.Operator):
    """Mitten hands or hands with fingers"""
    bl_idname = "stop_motion.hand_style"
    bl_label = "Hand Style"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    style: EnumProperty(items=HAND_STYLES)

    def execute(self, context):
        arm = assembly._arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        was = arm.stop_motion_puppet.enabled
        if was:
            assembly._unpuppet(context, arm)
            assembly._rest(arm)
        make_hands(context, arm, self.style)
        info = assembly.build_info(arm)
        info["hands_made"] = True
        assembly.set_build_info(arm, info)
        if was:
            assembly.finish_build(context, arm)
        return {'FINISHED'}


classes = (SM_OT_make_faces, SM_OT_hand_style)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
