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
from mathutils import Matrix, Vector
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
    rig_ik: StringProperty(description="The rig's own IK constraint used as this ring's pin (rigs with IK feet)")
    knee: PointerProperty(type=bpy.types.Object, description="Where the knee points")
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
    if "foot" in n or "ankle" in n or "paw" in n or "hoof" in n:
        return "foot"
    if "tail" in n and "tip" not in n:
        return "Tail"
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
        if k == "foot":                  # four legs: front and back feet
            low = b.name.lower()
            end = "front " if ("front" in low or "fore" in low) else "back " if ("back" in low or "hind" in low or "rear" in low) else ""
            if end:
                label = (end + label[0].lower() + label[1:]).capitalize()
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
    order = ["Head", "Body", "Hips", "Tail", "Left hand", "Right hand", "Hand", "Left foot", "Right foot", "Foot",
             "Front left foot", "Front right foot", "Back left foot", "Back right foot"]
    return [(lbl, best[lbl][1]) for lbl in order if lbl in best] + \
           [(lbl, v[1]) for lbl, v in best.items() if lbl not in order]


# ------------------------------------------------------------- swap guessing

def _split(name):
    m = re.match(r"^(.+?)[_.\-\s](.+)$", name)
    return (m.group(1), m.group(2)) if m else (None, None)


def _nice(s):
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)          # LeftHand -> Left Hand, LookLeft -> Look Left
    s = s.replace("_", " ").replace(".", " ").replace("-", " ").strip()
    if s.isupper() and len(s) <= 4:
        return s                                          # mouth shapes: AI, MBP, FV stay as they are
    return s.capitalize()


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
        if ob.parent != arm or ob.get("sm_part"):   # kit body parts aren't swaps
            continue
        pre, rest = _split(ob.name)
        if pre:
            groups.setdefault(pre, []).append((_nice(rest), ob))
    for pre, items in groups.items():
        if len(items) >= 2:
            items.sort(key=lambda t: (t[1].get("sm_order", 999), t[1].name))
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


def _signed_angle(u, v, normal):
    a = u.angle(v)
    if u.cross(v).dot(normal) > 0:
        a = -a
    return a


def pole_angle(upper, lower, pole_location):
    """IK pole angle that keeps a two-bone chain bent the way it is now
    (armature space)."""
    root = upper.head
    pole_normal = (lower.tail - root).cross(pole_location - root)
    projected = pole_normal.cross(upper.tail - root)
    x_axis = upper.matrix.to_3x3().col[0]
    return _signed_angle(x_axis, projected, upper.tail - root)


def add_knee(context, arm, ring):
    """A knee target for a pinned leg, so the knee keeps pointing the same way
    on big poses instead of flipping. It follows the foot's pin."""
    c = pin_constraint(arm, ring)
    if c is None or ring.pin is None or c.pole_target is not None or ring.rig_ik:
        return None
    owner = arm.pose.bones[ring.pin_owner]
    upper = owner.parent
    if upper is None:
        return None
    context.view_layer.update()
    hip, knee, ankle = upper.head, owner.head, owner.tail
    mid = (hip + ankle) / 2
    bend = knee - mid
    leg = (ankle - hip).length
    if bend.length < leg * 0.02:
        # straight leg: knees point the way the puppet faces (-Y, Blender's front)
        bend = Vector((0, -1, 0))
        bend = bend - (ankle - hip).normalized() * bend.dot((ankle - hip).normalized())
    pole_pos = knee + bend.normalized() * leg * 0.6
    empty = bpy.data.objects.new("Knee %s" % ring.bone, None)
    empty.empty_display_type = 'CONE'
    empty.empty_display_size = max(0.015, leg * 0.06)
    empty.hide_render = True
    empty.hide_viewport = True             # animators steer knees with the foot, not this
    for col in (ring.pin.users_collection or arm.users_collection):
        col.objects.link(empty)
        break
    else:
        context.scene.collection.objects.link(empty)
    empty.matrix_world = arm.matrix_world @ Matrix.Translation(pole_pos)
    # follow the foot pin (keep where it is now)
    empty.parent = ring.pin
    empty.matrix_parent_inverse = ring.pin.matrix_world.inverted()
    want = [(b, (arm.matrix_world @ b.matrix).copy()) for b in (upper, owner)]
    c.pole_target = empty
    c.pole_angle = pole_angle(upper, owner, pole_pos)
    ring.knee = empty
    _settle_pole(context, arm, c, want)
    return empty


def _settle_pole(context, arm, c, want, tol=1e-4):
    """Make sure the knee target didn't turn the leg (rigs differ in bone roll):
    nudge the pole angle until the leg is back where it was."""
    import math

    def err(angle):
        c.pole_angle = angle
        context.view_layer.update()
        ae = arm.evaluated_get(context.evaluated_depsgraph_get())
        total = 0.0
        for b, m in want:
            now = ae.matrix_world @ ae.pose.bones[b.name].matrix
            total += sum((now.col[i].xyz - m.col[i].xyz).length for i in range(3))
        return total

    best = c.pole_angle
    e = err(best)
    if e > tol:
        for k in range(36):                       # coarse search all the way round
            a = -math.pi + k * math.pi / 18
            ea = err(a)
            if ea < e:
                best, e = a, ea
        step = math.pi / 36
        while step > 1e-4 and e > tol:            # then home in
            for a in (best - step, best + step):
                ea = err(a)
                if ea < e:
                    best, e = a, ea
                    break
            else:
                step /= 2
    c.pole_angle = best
    context.view_layer.update()


def find_rig_ik(arm, bone):
    """A rig's own IK constraint aimed at `bone` (an IK foot control). (owner bone, constraint) or None."""
    for pb in arm.pose.bones:
        for c in pb.constraints:
            if c.type == 'IK' and c.name != PIN_CONSTRAINT and c.target == arm and c.subtarget == bone:
                return pb, c
    return None


def pin_constraint(arm, ring):
    owner = arm.pose.bones.get(ring.pin_owner) if ring.pin_owner else None
    if owner is None:
        return None
    return owner.constraints.get(ring.rig_ik or PIN_CONSTRAINT)


def has_pin(ring):
    return ring.pin is not None or bool(ring.rig_ik)


def is_pinned(arm, ring):
    c = pin_constraint(arm, ring)
    return c is not None and c.influence > 0.5


def _ik_chain(owner, c):
    chain, b = [], owner
    n = c.chain_count or 99
    while b is not None and len(chain) < n:
        chain.append(b)
        b = b.parent
    return list(reversed(chain))


def set_pinned(context, arm, ring, pinned):
    """Switch a pin without the foot jumping."""
    c = pin_constraint(arm, ring)
    if c is None or not has_pin(ring):
        return
    owner = arm.pose.bones[ring.pin_owner]
    if ring.rig_ik:
        # the rig's own IK: the foot control is where the foot goes
        context.view_layer.update()
        if pinned:
            ctrl = arm.pose.bones.get(ring.bone)
            if ctrl is not None:
                m = ctrl.matrix.copy()
                m.translation = owner.tail.copy()
                ctrl.matrix = m
            c.influence = 1.0
        else:
            mats = [(b, b.matrix.copy()) for b in _ik_chain(owner, c)]
            c.influence = 0.0
            for pb, m in mats:
                pb.matrix = m
                context.view_layer.update()
        return
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
        if pin_feet and "foot" in label.lower():
            rig = find_rig_ik(arm, bone)
            if rig is not None:
                # the rig already has IK feet: use its IK as the pin
                r.pin_owner, r.rig_ik = rig[0].name, rig[1].name
            elif "ik" not in bone.lower():
                res = add_foot_pin(scene, arm, bone)
                if res:
                    r.pin, r.pin_owner = res
                    add_knee(context, arm, r)
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
        if kind == 'SHAPE':
            kbs = mesh.data.shape_keys.key_blocks
            if sum(1 for it in s.items if kbs[it.shape_key].value > 0.5) > 1:
                for it in s.items:  # several parts fully on: start neutral
                    kbs[it.shape_key].value = 0.0
        if kind == 'MESH':
            showing = [it for it in s.items if it.obj and not it.obj.hide_viewport]
            if len(showing) != 1:  # exactly one part shows at a time
                labels = [it.label.lower() for it in s.items]
                start = next((labels.index(w) for w in ("open", "neutral", "closed", "default", "rest")
                              if w in labels), max(0, swap_active(s)))
                apply_swap(s, start)


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
        pins = sum(1 for r in pp.rings if has_pin(r))
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
            if c is not None and not r.rig_ik:
                arm.pose.bones[r.pin_owner].constraints.remove(c)
            if r.knee is not None:
                bpy.data.objects.remove(r.knee)
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
