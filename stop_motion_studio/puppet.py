# SPDX-License-Identifier: GPL-3.0-or-later
"""Puppets: an armature made animator-friendly.

- Grab rings: a handful of big rings (head, body, hips, hands, feet) that
  stand in for the bones. The animator drags rings, never bones.
- Swap sets: replacement parts (eyes, mouths, hands). Either shape keys on
  the puppet's mesh, or separate meshes parented to the rig and shown one
  at a time.
- Pins: for simple rigs, Make Puppet adds a two-bone IK pin to each foot so
  feet stay planted while the body moves. Pinning can be switched off.
"""

import re

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, IntProperty, PointerProperty, StringProperty)

PIN_CONSTRAINT = "SM Pin"


# ---------------------------------------------------------------------- data

class SM_SwapItem(bpy.types.PropertyGroup):
    label: StringProperty()
    shape_key: StringProperty()
    obj: PointerProperty(type=bpy.types.Object)


class SM_SwapSet(bpy.types.PropertyGroup):
    kind: EnumProperty(items=[('SHAPE', "Shape keys", ""), ('MESH', "Meshes", "")])
    mesh: PointerProperty(type=bpy.types.Object, description="Mesh holding the shape keys")
    items: CollectionProperty(type=SM_SwapItem)


class SM_Ring(bpy.types.PropertyGroup):
    label: StringProperty()
    bone: StringProperty()
    pin: PointerProperty(type=bpy.types.Object, description="Pin the ring moves, if any")
    pin_owner: StringProperty(description="Bone carrying the pin's IK")
    size: FloatProperty(name="Ring size", min=0.2, max=4.0, default=1.0)


class SM_Puppet(bpy.types.PropertyGroup):
    enabled: BoolProperty(default=False)
    rings: CollectionProperty(type=SM_Ring)
    swap_sets: CollectionProperty(type=SM_SwapSet)


def puppets(scene):
    return [ob for ob in scene.objects
            if ob.type == 'ARMATURE' and ob.stop_motion_puppet.enabled]


def puppet_for(context):
    """The puppet the animator most likely means right now."""
    ob = context.active_object
    if ob is not None:
        if ob.type == 'ARMATURE' and ob.stop_motion_puppet.enabled:
            return ob
        par = ob.parent
        while par is not None:
            if par.type == 'ARMATURE' and par.stop_motion_puppet.enabled:
                return par
            par = par.parent
        for m in getattr(ob, "modifiers", []):
            if m.type == 'ARMATURE' and m.object and m.object.stop_motion_puppet.enabled:
                return m.object
    found = puppets(context.scene)
    return found[0] if found else None


# ------------------------------------------------------------ bone guessing

_SKIP = re.compile(r"^(mch|def|org|vis|tweak)[-_.]", re.I)


def side_of(name):
    n = name.lower()
    if re.search(r"(^|[._\-\s])(l|left)([._\-\s\d]|$)", n) or n.startswith("left"):
        return "Left"
    if re.search(r"(^|[._\-\s])(r|right)([._\-\s\d]|$)", n) or n.startswith("right"):
        return "Right"
    return ""


def kind_of(name):
    n = name.lower()
    if "toe" in n or "finger" in n or "thumb" in n or "eye" in n or "jaw" in n:
        return None
    if "head" in n:
        return "Head"
    if "hand" in n or "wrist" in n:
        return "hand"
    if "foot" in n or "ankle" in n:
        return "foot"
    if "hip" in n or "pelvis" in n:
        return "Hips"
    if "chest" in n or "torso" in n:
        return "Body"
    return None


def guess_rings(arm):
    """[(label, bone_name)] for the bones an animator would grab."""
    best = {}
    for b in arm.data.bones:
        if _SKIP.match(b.name):
            continue
        k = kind_of(b.name)
        if k is None:
            continue
        s = side_of(b.name) if k in ("hand", "foot") else ""
        label = ("%s %s" % (s, k)).strip() if k in ("hand", "foot") else k
        if k in ("hand", "foot") and not s:
            label = k.capitalize()
        score = (0 if "ik" in b.name.lower() else 1, len(b.name))
        if label not in best or score < best[label][0]:
            best[label] = (score, b.name)
    if "Body" not in best:
        spines = [b for b in arm.data.bones if "spine" in b.name.lower() and not _SKIP.match(b.name)]
        if spines:
            top = max(spines, key=lambda b: len(b.parent_recursive))
            best["Body"] = ((1, 0), top.name)
    if not best:  # unknown naming: roots and tips
        bones = [b for b in arm.data.bones if not _SKIP.match(b.name)]
        picks = [b for b in bones if b.parent is None] + [b for b in bones if not b.children]
        seen = []
        for b in picks:
            if b.name not in seen:
                seen.append(b.name)
        return [(n.replace("_", " ").replace(".", " ").title(), n) for n in seen[:8]]
    order = ["Head", "Body", "Hips", "Left hand", "Right hand", "Hand", "Left foot", "Right foot", "Foot"]
    return [(lbl, best[lbl][1]) for lbl in order if lbl in best] + \
           [(lbl, v[1]) for lbl, v in best.items() if lbl not in order]


# ------------------------------------------------------------- swap guessing

def _split(name):
    m = re.match(r"^(.+?)[_.\-\s](.+)$", name)
    return (m.group(1), m.group(2)) if m else (None, None)


def _nice(s):
    return s.replace("_", " ").replace(".", " ").replace("-", " ").strip().capitalize()


def puppet_meshes(arm, scene):
    out = []
    for ob in scene.objects:
        if ob.type != 'MESH':
            continue
        if ob.parent == arm or any(m.type == 'ARMATURE' and m.object == arm for m in ob.modifiers):
            out.append(ob)
    return out


def guess_swap_sets(arm, scene):
    """[(name, kind, mesh, [(label, key_or_obj)])]"""
    found = []
    meshes = puppet_meshes(arm, scene)
    for me in meshes:
        sk = me.data.shape_keys
        if not sk:
            continue
        groups = {}
        for kb in sk.key_blocks[1:]:
            pre, rest = _split(kb.name)
            if pre:
                groups.setdefault(pre, []).append((_nice(rest), kb.name))
        for pre, items in groups.items():
            if len(items) >= 2:
                found.append((_nice(pre), 'SHAPE', me, items))
    groups = {}
    for ob in meshes:
        if ob.parent != arm:
            continue
        pre, rest = _split(ob.name)
        if pre:
            groups.setdefault(pre, []).append((_nice(rest), ob))
    for pre, items in groups.items():
        if len(items) >= 2:
            items.sort(key=lambda t: t[1].name)
            found.append((_nice(pre), 'MESH', None, items))
    return found


# ------------------------------------------------------------------- swaps

def swap_active(sset):
    if sset.kind == 'SHAPE':
        sk = sset.mesh.data.shape_keys if sset.mesh else None
        if not sk:
            return -1
        vals = [sk.key_blocks[it.shape_key].value if it.shape_key in sk.key_blocks else 0.0
                for it in sset.items]
        if not vals or max(vals) < 0.5:
            return -1
        return vals.index(max(vals))
    for i, it in enumerate(sset.items):
        if it.obj and not it.obj.hide_viewport:
            return i
    return -1


def apply_swap(sset, index):
    if sset.kind == 'SHAPE':
        sk = sset.mesh.data.shape_keys if sset.mesh else None
        if not sk:
            return
        for i, it in enumerate(sset.items):
            kb = sk.key_blocks.get(it.shape_key)
            if kb:
                kb.value = 1.0 if i == index else 0.0
    else:
        for i, it in enumerate(sset.items):
            if it.obj:
                hide = i != index
                it.obj.hide_viewport = hide
                it.obj.hide_render = hide


def swap_objects(arm):
    """Meshes whose visibility is part of the pose (for keying)."""
    return [it.obj for s in arm.stop_motion_puppet.swap_sets if s.kind == 'MESH'
            for it in s.items if it.obj]


# --------------------------------------------------------------------- pins

def add_foot_pin(scene, arm, foot_name):
    """IK pin on the bone above the foot. Returns (empty, owner_bone_name) or None."""
    pb = arm.pose.bones.get(foot_name)
    if pb is None or pb.parent is None or pb.parent.parent is None:
        return None
    owner = pb.parent
    if any(c.name == PIN_CONSTRAINT for c in owner.constraints):
        c = owner.constraints[PIN_CONSTRAINT]
        return c.target, owner.name
    empty = bpy.data.objects.new("Pin %s" % foot_name, None)
    empty.empty_display_type = 'SPHERE'
    empty.empty_display_size = max(0.02, pb.length * 0.35)
    for col in arm.users_collection:
        col.objects.link(empty)
        break
    else:
        scene.collection.objects.link(empty)
    empty.parent = arm
    empty.matrix_parent_inverse.identity()
    empty.location = owner.tail  # pose space == armature-object space
    empty.hide_render = True
    c = owner.constraints.new('IK')
    c.name = PIN_CONSTRAINT
    c.target = empty
    c.chain_count = 2
    c.use_tail = True
    return empty, owner.name


def pin_constraint(arm, ring):
    owner = arm.pose.bones.get(ring.pin_owner) if ring.pin_owner else None
    if owner is None:
        return None
    return owner.constraints.get(PIN_CONSTRAINT)


def is_pinned(arm, ring):
    c = pin_constraint(arm, ring)
    return c is not None and c.influence > 0.5


def set_pinned(context, arm, ring, pinned):
    """Switch a pin without the foot jumping."""
    c = pin_constraint(arm, ring)
    if c is None or ring.pin is None:
        return
    owner = arm.pose.bones[ring.pin_owner]
    upper = owner.parent
    if pinned:
        context.view_layer.update()
        ring.pin.location = owner.tail.copy()
        c.influence = 1.0
    else:
        # Bake the IK result into the bones, then let go.
        context.view_layer.update()
        mats = [(upper, upper.matrix.copy()), (owner, owner.matrix.copy())]
        c.influence = 0.0
        for pb, m in mats:
            pb.matrix = m
            context.view_layer.update()


# --------------------------------------------------------------- make puppet

def make_puppet(context, arm, pin_feet=True):
    scene = context.scene
    pp = arm.stop_motion_puppet
    pp.enabled = True
    pp.rings.clear()
    for label, bone in guess_rings(arm):
        r = pp.rings.add()
        r.label = label
        r.bone = bone
        if pin_feet and "foot" in label.lower() and "ik" not in bone.lower():
            res = add_foot_pin(scene, arm, bone)
            if res:
                r.pin, r.pin_owner = res
    rescan_swaps(context, arm)
    return pp


def rescan_swaps(context, arm):
    pp = arm.stop_motion_puppet
    pp.swap_sets.clear()
    for name, kind, mesh, items in guess_swap_sets(arm, context.scene):
        s = pp.swap_sets.add()
        s.name = name
        s.kind = kind
        if mesh is not None:
            s.mesh = mesh
        for label, ref in items:
            it = s.items.add()
            it.label = label
            if kind == 'SHAPE':
                it.shape_key = ref
            else:
                it.obj = ref
        if kind == 'MESH':
            showing = [it for it in s.items if it.obj and not it.obj.hide_viewport]
            if len(showing) != 1:  # exactly one part shows at a time
                apply_swap(s, max(0, swap_active(s)))


# ----------------------------------------------------------------- operators

class SM_OT_make_puppet(bpy.types.Operator):
    """Turn the selected rig into a puppet: grab rings, swap parts and pinned feet are set up for you"""
    bl_idname = "stop_motion.make_puppet"
    bl_label = "Make Puppet"
    bl_options = {'REGISTER', 'UNDO'}

    pin_feet: BoolProperty(name="Pin feet", default=True,
                           description="Feet stay planted while you move the body")

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'ARMATURE'

    def execute(self, context):
        arm = context.active_object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        pp = make_puppet(context, arm, self.pin_feet)
        pins = sum(1 for r in pp.rings if r.pin)
        self.report({'INFO'}, "%s: %d rings, %d swap sets, %d pins" %
                    (arm.name, len(pp.rings), len(pp.swap_sets), pins))
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                sp = area.spaces.active
                if sp.region_3d and sp.region_3d.view_perspective != 'CAMERA':
                    sp.overlay.show_bones = False
        return {'FINISHED'}


class SM_OT_rescan_swaps(bpy.types.Operator):
    """Look again for swap parts: shape keys named like 'Mouth_O', or meshes parented to the rig named like 'Eyes_Open'"""
    bl_idname = "stop_motion.rescan_swaps"
    bl_label = "Find Swap Parts"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()

    def execute(self, context):
        arm = bpy.data.objects.get(self.puppet)
        if arm is None:
            return {'CANCELLED'}
        rescan_swaps(context, arm)
        return {'FINISHED'}


class SM_OT_swap(bpy.types.Operator):
    """Swap in this part"""
    bl_idname = "stop_motion.swap"
    bl_label = "Swap Part"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    set_index: IntProperty()
    item: IntProperty()

    def execute(self, context):
        arm = bpy.data.objects.get(self.puppet)
        if arm is None:
            return {'CANCELLED'}
        sets = arm.stop_motion_puppet.swap_sets
        if not (0 <= self.set_index < len(sets)):
            return {'CANCELLED'}
        apply_swap(sets[self.set_index], self.item)
        return {'FINISHED'}


class SM_OT_toggle_pin(bpy.types.Operator):
    """Pin this foot to the floor, or let it follow the leg"""
    bl_idname = "stop_motion.toggle_pin"
    bl_label = "Pin"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    ring: IntProperty()

    def execute(self, context):
        arm = bpy.data.objects.get(self.puppet)
        if arm is None:
            return {'CANCELLED'}
        ring = arm.stop_motion_puppet.rings[self.ring]
        set_pinned(context, arm, ring, not is_pinned(arm, ring))
        return {'FINISHED'}


class SM_OT_unpuppet(bpy.types.Operator):
    """Stop treating this rig as a puppet (pins are removed)"""
    bl_idname = "stop_motion.unpuppet"
    bl_label = "Remove Puppet Setup"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()

    def execute(self, context):
        arm = bpy.data.objects.get(self.puppet)
        if arm is None:
            return {'CANCELLED'}
        pp = arm.stop_motion_puppet
        for r in pp.rings:
            c = pin_constraint(arm, r)
            if c is not None:
                arm.pose.bones[r.pin_owner].constraints.remove(c)
            if r.pin is not None:
                bpy.data.objects.remove(r.pin)
        pp.rings.clear()
        pp.swap_sets.clear()
        pp.enabled = False
        return {'FINISHED'}


classes = (SM_SwapItem, SM_SwapSet, SM_Ring, SM_Puppet,
           SM_OT_make_puppet, SM_OT_rescan_swaps, SM_OT_swap, SM_OT_toggle_pin, SM_OT_unpuppet)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Object.stop_motion_puppet = PointerProperty(type=SM_Puppet)


def unregister():
    del bpy.types.Object.stop_motion_puppet
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
