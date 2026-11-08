# SPDX-License-Identifier: GPL-3.0-or-later
"""Puppet studio, part 2: rig a one-piece sculpt by placing its joints.

Joints are guessed from the sculpt's shape (the armature template fitted
to its height, each joint pulled into the clay around it), then moved by
clicking: a click puts the joint halfway through the clay at that spot
(between where the ray goes in and comes out), so no side view is needed.
Left joints are mirrored to the right. Making the rig builds bones at the
joints and skins the sculpt to them (Blender's heat weighting, else by
distance), then it's a puppet like any other.
"""

import json

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import assembly

# What the animator places, in order: (joint name, label). Sided ones end in .L and are mirrored.
PLACE = {
    'PERSON': [("crown", "Top of the head"), ("skull", "Base of the head"), ("neck", "Neck"),
               ("chest", "Chest"), ("waist", "Waist"), ("pelvis", "Hips"),
               ("shoulder.L", "Shoulders"), ("elbow.L", "Elbows"), ("wrist.L", "Wrists"), ("fingertip.L", "Fingertips"),
               ("hip.L", "Tops of the legs"), ("knee.L", "Knees"), ("ankle.L", "Ankles"), ("toe.L", "Toes")],
    'FOUR_LEGS': [("nose", "Nose"), ("skull", "Back of the head"), ("neck", "Neck"), ("withers", "Shoulders (top)"),
                  ("back", "Middle of the back"), ("rump", "Rump"), ("tail_base", "Tail base"), ("tail_tip", "Tail tip"),
                  ("shoulder.L", "Front legs (top)"), ("front_elbow.L", "Front elbows"), ("front_wrist.L", "Front wrists"),
                  ("front_toe.L", "Front toes"), ("hip.L", "Back legs (top)"), ("stifle.L", "Back knees"),
                  ("hock.L", "Hocks"), ("back_toe.L", "Back toes")],
}
PLACE['CHILD'] = PLACE['PERSON']
PLACE['TALL'] = PLACE['PERSON']


def _mirror(name):
    return name[:-2] + ".R" if name.endswith(".L") else None


def mesh_tree(context, ob):
    dg = context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    try:
        mw = oe.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        oe.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), verts


def through(tree, origin, direction):
    """The middle of the clay along a ray: halfway between where it goes in and comes out."""
    d = direction.normalized()
    hit_in = tree.ray_cast(origin, d)
    if hit_in[0] is None:
        return None
    p = hit_in[0] + d * 1e-4
    out = None
    for _ in range(8):                       # the first surface it leaves by (skip inner shells)
        h = tree.ray_cast(p, d)
        if h[0] is None:
            break
        out = h[0]
        if h[1].dot(d) > 0:
            break
        p = h[0] + d * 1e-4
    if out is None:
        return hit_in[0]
    return (hit_in[0] + out) / 2


def guess(context, ob, template='PERSON'):
    """First guess of every joint (world space) for a sculpt standing on z = its lowest point."""
    _tree, verts = mesh_tree(context, ob)
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    centre = (lo + hi) / 2
    j = assembly.joints(template, None)
    four = template == 'FOUR_LEGS'
    # fit the template's joints to the sculpt's bounds
    jlo = Vector((min(v.x for v in j.values()), min(v.y for v in j.values()), min(v.z for v in j.values())))
    jhi = Vector((max(v.x for v in j.values()), max(v.y for v in j.values()), max(v.z for v in j.values())))
    size = hi - lo
    jsize = jhi - jlo
    k = Vector((size.x / max(jsize.x, 1e-6), size.y / max(jsize.y, 1e-6) if four else 1.0, size.z / max(jsize.z, 1e-6)))
    if not four:
        k.y = k.z
    jc = (jlo + jhi) / 2
    out = {}
    h = size.z
    for name, p in j.items():
        q = Vector(((p.x - jc.x) * k.x + centre.x, (p.y - jc.y) * k.y + centre.y, (p.z - jlo.z) * k.z + lo.z))
        # pull it into the clay: centre of the nearby points in a thin slice at its height
        near = [v for v in verts if abs(v.z - q.z) < h * 0.025 and abs(v.x - q.x) < size.x * 0.12
                and (four is False or abs(v.y - q.y) < size.y * 0.12)]
        if len(near) >= 6 and not name.startswith(("crown", "toe", "nose", "tail_tip", "front_toe", "back_toe", "fingertip")):
            c = sum(near, Vector()) / len(near)
            q = Vector((c.x, c.y, q.z)) if not four else Vector((c.x, c.y, q.z))
        out[name] = q
    return out


def get_joints(ob):
    try:
        return {k: Vector(v) for k, v in json.loads(ob.get("sm_joints", "{}")).items()}
    except ValueError:
        return {}


def set_joints(ob, joints):
    ob["sm_joints"] = json.dumps({k: list(v) for k, v in joints.items()})


def place(ob, joints, name, point, mirror=True):
    """Put a joint at `point` (world); its mirror image goes to the other side."""
    joints[name] = point.copy()
    m = _mirror(name)
    if mirror and m:
        cx = (joints.get("pelvis", joints.get("back", point))).x
        joints[m] = Vector((2 * cx - point.x, point.y, point.z))
    set_joints(ob, joints)
    return joints


def make_rig(context, ob, template='PERSON', joints=None, name=None):
    """Bones at the joints, the sculpt skinned to them, then a puppet."""
    joints = joints or get_joints(ob) or guess(context, ob, template)
    for n in list(joints):
        m = _mirror(n)
        if m and m not in joints:
            cx = joints.get("pelvis", joints.get("back", joints[n])).x
            joints[m] = Vector((2 * cx - joints[n].x, joints[n].y, joints[n].z))
    set_joints(ob, joints)
    name = name or (ob.name.split(".")[0] + " rig")
    data = bpy.data.armatures.new(name)
    data.display_type = 'STICK'
    arm = bpy.data.objects.new(name, data)
    for col in ob.users_collection:
        col.objects.link(arm)
        break
    else:
        context.scene.collection.objects.link(arm)
    arm.show_in_front = True
    local = {k: list(v) for k, v in joints.items()}    # the armature sits at the origin: world = armature space
    assembly.set_build_info(arm, {"template": template, "props": dict(assembly.DEFAULT_PROPS[template]),
                                  "parts": [], "sculpt": ob.name, "joints": local})
    assembly._active(context, arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for bname, h, t, _p, _c in assembly.bone_defs(template):
        b = eb.new(bname)
        b.head, b.tail = joints[h], joints[t]
    for bname, _h, _t, parent, conn in assembly.bone_defs(template):
        b = eb[bname]
        b.parent = eb[parent] if parent else None
        b.use_connect = bool(conn and parent)
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    _skin_sculpt(context, ob, arm)
    assembly.finish_build(context, arm)
    return arm


def _skin_sculpt(context, ob, arm):
    """Heat weighting (Blender's own, follows the clay's shape); if it can't, by distance."""
    ok = False
    try:
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        with context.temp_override(active_object=arm, object=arm, selected_objects=[ob, arm],
                                   selected_editable_objects=[ob, arm]):
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        weighted = set()
        for v in ob.data.vertices:
            for g in v.groups:
                if g.weight > 0.01:
                    weighted.add(v.index)
                    break
        ok = len(weighted) > 0.9 * len(ob.data.vertices)
    except RuntimeError as exc:
        print("Stop Motion: heat weighting didn't work, weighting by distance:", exc)
    if not ok:
        for m in list(ob.modifiers):
            if m.type == 'ARMATURE':
                ob.modifiers.remove(m)
        assembly.skin(ob, arm, [b.name for b in arm.data.bones], softness=0.4)
    else:
        assembly.fill_unweighted(ob, arm)
        for m in ob.modifiers:
            if m.type == 'ARMATURE':
                m.use_deform_preserve_volume = True
    return ok


# --------------------------------------------------------------- operators

from bpy.props import EnumProperty, StringProperty  # noqa: E402


class SM_OT_guess_joints(bpy.types.Operator):
    """Guess where the sculpt's joints are (you can move any of them after)"""
    bl_idname = "stop_motion.guess_joints"
    bl_label = "Guess Joints"
    bl_options = {'REGISTER', 'UNDO'}

    mesh: StringProperty()
    template: EnumProperty(items=[('PERSON', "Person", ""), ('FOUR_LEGS', "Four legs", "")], default='PERSON')

    def execute(self, context):
        ob = bpy.data.objects.get(self.mesh) if self.mesh else context.active_object
        if ob is None or ob.type != 'MESH':
            self.report({'WARNING'}, "Pick the sculpt first")
            return {'CANCELLED'}
        ob["sm_template"] = self.template
        set_joints(ob, guess(context, ob, self.template))
        return {'FINISHED'}


class SM_OT_make_sculpt_rig(bpy.types.Operator):
    """Make the rig: bones at the joints, the clay skinned to them, grab rings and pins"""
    bl_idname = "stop_motion.make_sculpt_rig"
    bl_label = "Make the Rig"
    bl_options = {'REGISTER', 'UNDO'}

    mesh: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.mesh) if self.mesh else context.active_object
        if ob is None or ob.type != 'MESH':
            return {'CANCELLED'}
        template = ob.get("sm_template", 'PERSON')
        arm = make_rig(context, ob, template)
        pp = arm.stop_motion_puppet
        self.report({'INFO'}, "%s is rigged: %d grab rings" % (ob.name, len(pp.rings)))
        return {'FINISHED'}


classes = (SM_OT_guess_joints, SM_OT_make_sculpt_rig)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
