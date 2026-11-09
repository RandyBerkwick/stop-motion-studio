# SPDX-License-Identifier: GPL-3.0-or-later
"""Wear it: put a hat, glasses, a badge or anything else on a puppet.

Click where it goes on the puppet and it sits on the surface there, riding on
the nearest part (head, chest, hand...) from then on. Worn things aren't
animated on their own: move one and it moves in every shot, like a set piece.

Several things worn on the same part can become a swap set (a "Hat" set of a
cap, a crown and None), picked shot by shot like mouths.
"""

import re

import bmesh
import bpy
from bpy.props import StringProperty
from mathutils import Vector

from . import puppet

SWAP_SETS = ("Hat", "Hair", "Glasses", "Badge", "Extra")


def worn(scene):
    return [ob for ob in scene.objects if ob.get("sm_worn")]


def worn_on(arm):
    return [ob for ob in arm.children if ob.get("sm_worn")]


def armature_of(ob):
    """The puppet armature an object belongs to (parented, or bent by it)."""
    while ob is not None:
        if ob.type == 'ARMATURE':
            return ob
        for m in getattr(ob, "modifiers", []):
            if m.type == 'ARMATURE' and m.object is not None:
                return m.object
        ob = ob.parent
    return None


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (a + ab * t - p).length


def bone_at(arm, point):
    """The bone nearest a point on the puppet (in world space)."""
    mw = arm.matrix_world
    best = None
    for pb in arm.pose.bones:
        if pb.bone.name.startswith(("MCH", "ORG", "IK", "ik", "pole")):
            continue
        d = _seg_dist(point, mw @ pb.head, mw @ pb.tail)
        if best is None or d < best[0]:
            best = (d, pb.name)
    return best[1] if best else None


def _corners(context, ob):
    """World-space points of the object (all of its mesh points when it has any)."""
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    if ob.type == 'MESH':
        mw = ev.matrix_world
        pts = [mw @ v.co for v in ev.data.vertices]
        if pts:
            return pts
    return [ev.matrix_world @ Vector(c) for c in ob.bound_box]


def place_on(context, ob, point, normal, sink=0.08):
    """Move `ob` so its back (the side facing the surface) touches `point`, centred there."""
    n = normal.normalized()
    pts = _corners(context, ob)
    centre = sum(pts, Vector()) / len(pts)
    support = min(p.dot(n) for p in pts)          # how far back it reaches along the normal
    depth = max(p.dot(n) for p in pts) - support
    side = (point - centre) - n * (point - centre).dot(n)
    along = point.dot(n) - support - depth * sink   # sink in a little, like it's pressed on
    ob.matrix_world.translation += side + n * along
    context.view_layer.update()


def wear(context, ob, arm, bone, point=None, normal=None):
    """Put `ob` on `bone` of `arm` (at `point` on the surface, if given)."""
    from . import assembly, solid
    if solid.held_by(ob):
        solid.let_go(context, ob)
    for c in list(solid.hold_constraints(ob)):
        ob.constraints.remove(c)
    if ob.animation_data is not None:
        ob.animation_data_clear()                 # worn things ride the puppet, not their own keys
    if point is not None and normal is not None:
        place_on(context, ob, point, normal)
    assembly.attach_rigid(ob, arm, bone)
    ob["sm_worn"] = bone
    ob["sm_label"] = ob.get("sm_label") or _clean(ob.name)
    try:
        ob.stop_motion_prop = False
        ob.stop_motion_set = False
    except AttributeError:
        pass
    context.view_layer.update()
    return ob


def take_off(context, ob):
    """Off the puppet, back to being a prop where it is."""
    arm = ob.parent if ob.parent is not None and ob.parent.type == 'ARMATURE' else None
    old = swap_set_of(ob)
    w = ob.matrix_world.copy()
    ob.parent = None
    ob.matrix_world = w
    if "sm_worn" in ob:
        del ob["sm_worn"]
    ob.hide_viewport = False
    ob.hide_render = False
    label = ob.get("sm_label")
    if label and re.match(r"^(%s)_" % "|".join(SWAP_SETS), ob.name):
        ob.name = label
    try:
        ob.stop_motion_prop = True
    except AttributeError:
        pass
    if arm is not None and old:
        _drop_empty_set(arm, old)
    if arm is not None and arm.stop_motion_puppet.enabled:
        puppet.rescan_swaps(context, arm)
    context.view_layer.update()


def _clean(name):
    name = re.sub(r"\.\d{3}$", "", name)
    m = re.match(r"^(%s)_(.+)$" % "|".join(SWAP_SETS), name)
    return m.group(2) if m else name


def swap_set_of(ob):
    m = re.match(r"^(%s)_" % "|".join(SWAP_SETS), ob.name)
    return m.group(1) if m else ""


def _none_piece(context, arm, set_name, bone):
    """An empty choice for a set, so the thing can come off for a shot."""
    name = "%s_None" % set_name
    for ob in arm.children:
        if re.sub(r"\.\d{3}$", "", ob.name) == name:
            return ob
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bm.verts.new((0, 0, 0))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col = arm.users_collection[0] if arm.users_collection else context.scene.collection
    col.objects.link(ob)
    b = arm.data.bones[bone]
    ob.matrix_world = arm.matrix_world @ b.matrix_local
    from . import assembly
    assembly.attach_rigid(ob, arm, bone)
    ob["sm_worn"] = bone
    ob["sm_label"] = "None"
    ob["sm_order"] = 999
    ob.hide_viewport = True
    ob.hide_render = True
    return ob


def _drop_empty_set(arm, set_name):
    """A set left with only its None is no set at all."""
    rest = [o for o in arm.children if swap_set_of(o) == set_name and o.get("sm_label") != "None"]
    if not rest:
        for o in list(arm.children):
            if swap_set_of(o) == set_name:
                me = o.data
                bpy.data.objects.remove(o)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)


def set_swap(context, ob, set_name):
    """Make a worn thing part of a swap set ('' to take it out). It shows now."""
    arm = ob.parent if ob.parent is not None and ob.parent.type == 'ARMATURE' else None
    if arm is None or not ob.get("sm_worn"):
        return None
    label = ob.get("sm_label") or _clean(ob.name)
    old = swap_set_of(ob)
    if set_name:
        ob.name = "%s_%s" % (set_name, re.sub(r"[_\s]+", " ", label).strip().title().replace(" ", ""))
        _none_piece(context, arm, set_name, ob["sm_worn"])
    else:
        ob.name = label
    if old and old != set_name:
        _drop_empty_set(arm, old)
    ob.hide_viewport = False
    ob.hide_render = False
    if arm.stop_motion_puppet.enabled:
        puppet.rescan_swaps(context, arm)
        for s in arm.stop_motion_puppet.swap_sets:
            for i, it in enumerate(s.items):
                if it.obj == ob:
                    puppet.apply_swap(s, i)
    return ob


def wear_at(context, ob, hit_ob, point, normal):
    """Wear `ob` where a click landed on a puppet (`hit_ob` was hit at `point`)."""
    arm = armature_of(hit_ob)
    if arm is None or ob is None or ob == hit_ob or ob.type == 'ARMATURE':
        return None
    if ob.parent == arm and not ob.get("sm_worn"):
        return None                                   # one of the puppet's own parts
    if hit_ob.parent == arm and hit_ob.parent_type == 'BONE' and hit_ob.parent_bone:
        bone = hit_ob.parent_bone
    else:
        bone = bone_at(arm, point)
    if bone is None:
        return None
    return wear(context, ob, arm, bone, point, normal)


# --------------------------------------------------------------- operators

class SM_OT_wear(bpy.types.Operator):
    """Put the selected thing on the puppet: on the part nearest it (or the head)"""
    bl_idname = "stop_motion.wear"
    bl_label = "Wear It"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="")
    puppet: StringProperty(default="")
    bone: StringProperty(default="")

    def execute(self, context):
        ob = bpy.data.objects.get(self.name) if self.name else context.active_object
        arms = [bpy.data.objects.get(self.puppet)] if self.puppet else \
            [o for o in context.scene.objects if o.type == 'ARMATURE' and o.stop_motion_puppet.enabled]
        arms = [a for a in arms if a is not None]
        if ob is None or not arms or ob.type == 'ARMATURE':
            self.report({'WARNING'}, "Select the thing to wear (and have a puppet in the scene)")
            return {'CANCELLED'}
        c = sum(_corners(context, ob), Vector()) / max(1, len(_corners(context, ob)))
        arm = min(arms, key=lambda a: (a.matrix_world.translation - c).length)
        bone = self.bone or bone_at(arm, c) or "head"
        wear(context, ob, arm, bone)
        self.report({'INFO'}, "%s is on %s's %s" % (ob.name, arm.name, bone))
        return {'FINISHED'}


class SM_OT_take_off(bpy.types.Operator):
    """Take it off the puppet: it becomes a prop again, where it is"""
    bl_idname = "stop_motion.take_off"
    bl_label = "Take Off"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="")

    def execute(self, context):
        ob = bpy.data.objects.get(self.name) if self.name else context.active_object
        if ob is None or not ob.get("sm_worn"):
            return {'CANCELLED'}
        take_off(context, ob)
        return {'FINISHED'}


class SM_OT_wear_swap(bpy.types.Operator):
    """Make it one of a swap set (picked shot by shot, with None to take it off)"""
    bl_idname = "stop_motion.wear_swap"
    bl_label = "Swap Set"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="")
    set_name: StringProperty(default="")

    def execute(self, context):
        ob = bpy.data.objects.get(self.name) if self.name else context.active_object
        if ob is None or set_swap(context, ob, self.set_name) is None:
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (SM_OT_wear, SM_OT_take_off, SM_OT_wear_swap)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
