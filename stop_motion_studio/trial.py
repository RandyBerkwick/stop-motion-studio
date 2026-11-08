# SPDX-License-Identifier: GPL-3.0-or-later
"""Puppet studio, part 4: try the puppet out before animating with it.

The puppet is put through a few test poses. In each, the clay is checked:
- folds in: a bending part loses a lot of its volume at a joint;
- pokes through: two parts that were apart at rest run into each other;
- flipped knee: a pinned leg bends the wrong way.
Each problem comes with a fix. The test poses are never kept: the puppet
goes back to standing afterwards. A picture of each pose is taken.
"""

import json
import math
import os
import tempfile

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import assembly

# Each pose: [(bone, axis in the armature's space, degrees)] applied in order,
# plus an optional hips drop (fraction of leg length). The sign of a swing is
# worked out from what it should do ("up", "forward", "down", "back").
POSES = {
    'PERSON': [
        ("Wave", [("upper_arm.R", "Y", 140, "up"), ("forearm.R", "Y", 40, "up")], 0.0),
        ("Sit", [("thigh.L", "X", 85, "forward"), ("thigh.R", "X", 85, "forward"),
                 ("shin.L", "X", 85, "down"), ("shin.R", "X", 85, "down")], 0.0),
        ("Crouch", [], 0.32),
        ("Walk", [("thigh.L", "X", 28, "forward"), ("thigh.R", "X", 22, "back"), ("shin.R", "X", 30, "back"),
                  ("upper_arm.L", "X", 20, "back"), ("upper_arm.R", "X", 22, "forward")], 0.04),
    ],
    'FOUR_LEGS': [
        ("Sit", [("back_thigh.L", "X", 60, "forward"), ("back_thigh.R", "X", 60, "forward"),
                 ("spine", "X", 25, "up")], 0.0),
        ("Head up", [("neck", "X", 30, "up"), ("head", "X", 20, "up"), ("tail", "X", 40, "up")], 0.0),
        ("Crouch", [], 0.3),
        ("Walk", [("front_upper_leg.L", "X", 25, "forward"), ("back_thigh.R", "X", 25, "forward"),
                  ("front_upper_leg.R", "X", 20, "back"), ("back_thigh.L", "X", 20, "back")], 0.0),
    ],
}
POSES['CHILD'] = POSES['PERSON']
POSES['TALL'] = POSES['PERSON']

_AXES = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}
_WANT = {"up": Vector((0, 0, 1)), "down": Vector((0, 0, -1)), "forward": Vector((0, -1, 0)), "back": Vector((0, 1, 0))}


def _turn(arm, pb, axis, degrees, want):
    """Turn a bone about an axis through its head, the way that moves its tip toward `want`."""
    head = pb.head.copy()
    best = None
    for sign in (1, -1):
        R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(degrees) * sign, 4, axis) @ Matrix.Translation(-head)
        tip = (R @ pb.matrix @ Matrix.Translation((0, pb.length, 0))).translation
        score = (tip - pb.tail).dot(want)
        if best is None or score > best[0]:
            best = (score, R)
    pb.matrix = best[1] @ pb.matrix


def apply_pose(context, arm, pose):
    _name, turns, drop = pose
    from . import puppet
    turned = {b for b, _a, _d, _w in turns}
    for r in arm.stop_motion_puppet.rings:      # a leg being posed by hand isn't pinned
        c = puppet.pin_constraint(arm, r)
        if c is not None and r.pin_owner:
            chain = {r.pin_owner}
            par = arm.pose.bones[r.pin_owner].parent
            if par is not None:
                chain.add(par.name)
            if chain & turned:
                c.influence = 0.0
    context.view_layer.update()
    for bone, ax, deg, want in turns:
        pb = arm.pose.bones.get(bone)
        if pb is None:
            continue
        _turn(arm, pb, _AXES[ax], deg, _WANT[want])
        context.view_layer.update()
    if drop:
        hips = arm.pose.bones.get("hips")
        legs = [b for b in arm.data.bones if b.name.startswith(("thigh", "back_thigh"))]
        if hips is not None and legs:
            leg = sum(b.length for b in arm.data.bones if b.name in ("thigh.L", "shin.L", "back_thigh.L", "back_shin.L"))
            m = hips.matrix.copy()
            m.translation.z -= leg * drop
            hips.matrix = m
            context.view_layer.update()


def _save_pose(arm):
    pose = {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.rotation_euler.copy(), pb.scale.copy())
            for pb in arm.pose.bones}
    pins = {(pb.name, c.name): c.influence for pb in arm.pose.bones for c in pb.constraints if c.type == 'IK'}
    return pose, pins


def _restore_pose(context, arm, saved):
    pose, pins = saved
    for pb in arm.pose.bones:
        loc, q, e, sc = pose[pb.name]
        pb.location, pb.rotation_quaternion, pb.rotation_euler, pb.scale = loc, q, e, sc
    for (bone, cname), v in pins.items():
        c = arm.pose.bones[bone].constraints.get(cname)
        if c is not None:
            c.influence = v
    context.view_layer.update()


# ---------------------------------------------------------------- checks

def _mesh_data(context, ob):
    dg = context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    try:
        mw = oe.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        tris = [tuple(t.vertices) for t in me.loop_triangles] if me.loop_triangles else []
        if not tris:
            me.calc_loop_triangles()
            tris = [tuple(t.vertices) for t in me.loop_triangles]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        oe.to_mesh_clear()
    return verts, tris, polys


def volume(verts, tris):
    v = 0.0
    for a, b, c in tris:
        v += verts[a].dot(verts[b].cross(verts[c]))
    return abs(v) / 6.0


def _parts(arm):
    return [ob for ob in assembly.kit_parts(arm) if ob.type == 'MESH' and not ob.hide_render]


def _skinned(ob):
    return any(m.type == 'ARMATURE' for m in ob.modifiers)


def measure(context, arm):
    """Volumes of bending parts, and which pairs of parts touch (and how much)."""
    parts = _parts(arm)
    data = {ob.name: _mesh_data(context, ob) for ob in parts}
    vols = {n: volume(v, t) for n, (v, t, _p) in data.items() if _skinned(bpy.data.objects[n])}
    trees = {n: BVHTree.FromPolygons(v, p) for n, (v, _t, p) in data.items()}
    names = sorted(trees)
    touch = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            touch[(a, b)] = len(trees[a].overlap(trees[b]))
    return vols, touch


def _knees(context, arm):
    """The way each pinned leg's knee points (armature space)."""
    out = {}
    for r in arm.stop_motion_puppet.rings:
        if r.pin is None or not r.pin_owner:
            continue
        lower = arm.pose.bones[r.pin_owner]
        upper = lower.parent
        if upper is None:
            continue
        mid = (upper.head + lower.tail) / 2
        out[r.label] = (lower.head - mid)
    return out


def try_out(context, arm, pictures=True):
    """Put the puppet through its test poses. Returns [{name, picture, problems: [...]}]."""
    info = assembly.build_info(arm)
    template = info.get("template", 'PERSON')
    saved = _save_pose(arm)
    context.view_layer.update()
    rest_vols, rest_touch = measure(context, arm)
    rest_knees = _knees(context, arm)
    out_dir = os.path.join(tempfile.gettempdir(), "stop_motion_try")
    os.makedirs(out_dir, exist_ok=True)
    results = []
    try:
        for pose in POSES[template]:
            _restore_pose(context, arm, saved)
            apply_pose(context, arm, pose)
            vols, touch = measure(context, arm)
            problems = []
            for name, v0 in rest_vols.items():
                v = vols.get(name, v0)
                if v0 > 0 and v < v0 * 0.9:
                    problems.append({"kind": "FOLDS", "part": name,
                                     "text": "%s folds in" % _nice_part(name, arm), "loss": 1 - v / v0,
                                     "fix": "SOFTEN", "fix_label": "Soften joints"})
            for (a, b), n in touch.items():
                n0 = rest_touch.get((a, b), 0)
                if n > max(12, n0 * 2 + 8):
                    problems.append({"kind": "POKES", "part": a, "other": b,
                                     "text": "%s runs into %s" % (_nice_part(a, arm), _nice_part(b, arm).lower()),
                                     "fix": "SOFTEN", "fix_label": "Soften joints"})
            legs_free = any(b.startswith(("thigh", "shin", "back_", "front_")) for b, _a, _d, _w in pose[1])
            for label, d in ({} if legs_free else _knees(context, arm)).items():
                d0 = rest_knees.get(label)
                if d0 is not None and d0.length > 1e-6 and d.length > 1e-6 and d.dot(d0) < 0:
                    problems.append({"kind": "KNEE", "part": label, "text": "%s knee bends the wrong way" % label,
                                     "fix": "AIM_KNEES", "fix_label": "Aim knees again"})
            pic = None
            if pictures:
                from . import library
                pic = os.path.join(out_dir, "%s_%s.png" % (bpy.path.clean_name(arm.name), bpy.path.clean_name(pose[0])))
                vis = [arm] + [o for o in arm.children_recursive if not o.hide_render and o.type == 'MESH']
                library.render_thumbnail(vis, pic, 360)
            results.append({"name": pose[0], "picture": pic, "problems": problems})
    finally:
        _restore_pose(context, arm, saved)
    arm["sm_try"] = json.dumps(results)
    return results


def last_results(arm):
    try:
        return json.loads(arm.get("sm_try", "[]"))
    except ValueError:
        return []


def _nice_part(name, arm):
    n = name[len(arm.name):].strip() if name.startswith(arm.name) else name
    return n.replace(" L", " (left)").replace(" R", " (right)")


def fix(context, arm, what):
    """Apply a fix from the problem list."""
    info = assembly.build_info(arm)
    if what == "SOFTEN":
        info["softness"] = min(1.0, info.get("softness", 0.5) + 0.2)
        assembly.set_build_info(arm, info)
        was = arm.stop_motion_puppet.enabled
        if was:
            assembly._unpuppet(context, arm)
            assembly._rest(arm)
        assembly.remake_parts(context, arm)
        if was:
            assembly.finish_build(context, arm)
        return "Joints softened"
    if what == "AIM_KNEES":
        from . import puppet
        assembly._rest(arm)
        for r in arm.stop_motion_puppet.rings:
            c = puppet.pin_constraint(arm, r)
            if c is not None and r.knee is not None:
                c.pole_target = None
                bpy.data.objects.remove(r.knee)
            if r.pin is not None:
                puppet.add_knee(context, arm, r)
        return "Knees aimed again"
    return ""


# --------------------------------------------------------------- operators

from bpy.props import StringProperty  # noqa: E402


class SM_OT_try_puppet(bpy.types.Operator):
    """Put the puppet through some test poses and look for problems"""
    bl_idname = "stop_motion.try_puppet"
    bl_label = "Try It Out"

    puppet: StringProperty()

    def execute(self, context):
        arm = assembly._arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        res = try_out(context, arm)
        n = sum(len(r["problems"]) for r in res)
        self.report({'INFO'}, "%d pose%s tried · %s" % (len(res), "" if len(res) == 1 else "s",
                                                        "nothing to fix" if not n else "%d thing%s to look at" % (n, "" if n == 1 else "s")))
        return {'FINISHED'}


class SM_OT_fix_puppet(bpy.types.Operator):
    """Fix a problem found by trying the puppet out"""
    bl_idname = "stop_motion.fix_puppet"
    bl_label = "Fix"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    what: StringProperty()

    def execute(self, context):
        arm = assembly._arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        msg = fix(context, arm, self.what)
        try_out(context, arm)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class SM_OT_save_puppet(bpy.types.Operator):
    """Keep this puppet in the library (with its picture) to use in any project"""
    bl_idname = "stop_motion.save_puppet"
    bl_label = "Save to Library"

    puppet: StringProperty()
    name: StringProperty(default="")

    def execute(self, context):
        from . import library
        arm = assembly._arm(context, self.puppet)
        if arm is None:
            return {'CANCELLED'}
        if not arm.stop_motion_puppet.enabled:
            assembly.finish_build(context, arm)
        if self.name and self.name != arm.name:
            arm.name = self.name
        path = library.add_to_library(context, [arm], self.name or arm.name)
        self.report({'INFO'}, "%s is in the library" % os.path.splitext(os.path.basename(path))[0])
        return {'FINISHED'}


classes = (SM_OT_try_puppet, SM_OT_fix_puppet, SM_OT_save_puppet)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
