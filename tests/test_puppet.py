import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
from mathutils import Vector
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core, puppet

ctx = bpy.context
scene = ctx.scene
for ob in list(scene.objects):
    if ob.type == 'MESH':
        bpy.data.objects.remove(ob)

# --- biped rig
arm_data = bpy.data.armatures.new("Biped")
arm = bpy.data.objects.new("Bramble", arm_data)
scene.collection.objects.link(arm)
ctx.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones
def bone(name, head, tail, parent=None, connect=False):
    b = eb.new(name); b.head = head; b.tail = tail
    if parent: b.parent = eb[parent]; b.use_connect = connect
    return b
bone("hips", (0,0,1.0), (0,0,1.2))
bone("spine", (0,0,1.2), (0,0,1.5), "hips", True)
bone("chest", (0,0,1.5), (0,0,1.7), "spine", True)
bone("head", (0,0,1.7), (0,0,2.0), "chest", True)
for s, x in (("L", 0.15), ("R", -0.15)):
    bone("thigh."+s, (x,0,1.0), (x,0.02,0.55), "hips")
    bone("shin."+s, (x,0.02,0.55), (x,0,0.1), "thigh."+s, True)
    bone("foot."+s, (x,0,0.1), (x,-0.15,0.0), "shin."+s, True)
    bone("upper_arm."+s, (x*2,0,1.6), (x*3,0,1.35), "chest")
    bone("forearm."+s, (x*3,0,1.35), (x*3.5,0,1.1), "upper_arm."+s, True)
    bone("hand."+s, (x*3.5,0,1.1), (x*3.6,0,1.0), "forearm."+s, True)
bpy.ops.object.mode_set(mode='OBJECT')

# --- body with shape keys, deformed by rig
body = bpy.data.objects.new("Body", bpy.data.meshes.new("Body"))
body.data.from_pydata([(0,0,0),(1,0,0),(0,1,0)], [], [(0,1,2)])
scene.collection.objects.link(body)
body.modifiers.new("Armature", 'ARMATURE').object = arm
body.shape_key_add(name="Basis")
for n in ("Mouth_Grin", "Mouth_O", "Eyes_Open", "Eyes_Shut", "Blink"):
    body.shape_key_add(name=n)
# --- replacement hands parented to rig
for n in ("Hand_Open", "Hand_Fist"):
    o = bpy.data.objects.new(n, bpy.data.meshes.new(n)); scene.collection.objects.link(o); o.parent = arm

bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True); ctx.view_layer.objects.active = arm
r = bpy.ops.stop_motion.make_puppet(); assert r == {'FINISHED'}
pp = arm.stop_motion_puppet
labels = [(x.label, x.bone, bool(x.pin)) for x in pp.rings]
print("rings:", labels)
assert [l for l, _b, _p in labels] == ["Head", "Body", "Hips", "Left hand", "Right hand", "Left foot", "Right foot"], labels
assert all(p for l, _b, p in labels if "foot" in l)
sets = {(s.name, s.kind): [i.label for i in s.items] for s in pp.swap_sets}
print("swaps:", sets)
assert sets == {("Mouth", 'SHAPE'): ["Grin", "O"], ("Eyes", 'SHAPE'): ["Open", "Shut"], ("Hand", 'MESH'): ["Fist", "Open"]}, sets
hand_set = next(s for s in pp.swap_sets if s.kind == 'MESH')
assert puppet.swap_active(hand_set) == 0 and bpy.data.objects["Hand_Open"].hide_viewport

def foot_world(side):
    ctx.view_layer.update()
    return arm.matrix_world @ arm.pose.bones["foot." + side].head

# --- pinned feet stay put when the hips drop
before = foot_world("L")
arm.pose.bones["hips"].location.y = -0.08    # bone-space y = up the bone = world z for this bone
arm.pose.bones["hips"].location.x = 0.05
after = foot_world("L")
print("foot moved by", round((after - before).length, 4))
assert (after - before).length < 0.01, (before, after)

# --- unpin without a jump, then foot follows the hips
ring_l = next(r for r in pp.rings if r.label == "Left foot")
puppet.set_pinned(ctx, arm, ring_l, False)
assert not puppet.is_pinned(arm, ring_l)
same = foot_world("L")
print("unpin jump", round((same - after).length, 4))
assert (same - after).length < 0.01
arm.pose.bones["hips"].location.x = 0.25
assert (foot_world("L") - same).length > 0.1
puppet.set_pinned(ctx, arm, ring_l, True)
held = foot_world("L")
arm.pose.bones["hips"].location.x = 0.15
assert (foot_world("L") - held).length < 0.01
print("pins ok")

# --- swaps are part of each shot
mouth = next(s for s in pp.swap_sets if s.name == "Mouth")
kb = body.data.shape_keys.key_blocks
puppet.apply_swap(mouth, 0); puppet.apply_swap(hand_set, 0)
bpy.ops.stop_motion.shoot()
puppet.apply_swap(mouth, 1); puppet.apply_swap(hand_set, 1)
puppet.set_pinned(ctx, arm, ring_l, False)
bpy.ops.stop_motion.shoot()
def state(f):
    scene.frame_set(f)
    return (round(kb["Mouth_Grin"].value), round(kb["Mouth_O"].value),
            bpy.data.objects["Hand_Fist"].hide_viewport, round(puppet.pin_constraint(arm, ring_l).influence))
print("shot states", state(1), state(3))
assert state(1) == (1, 0, False, 1) and state(3) == (0, 1, True, 0), (state(1), state(3))
for idb in core.animated_ids(scene):
    for fc in core.fcurves_of(idb):
        assert all(k.interpolation == 'CONSTANT' for k in fc.keyframe_points), fc.data_path

# --- unpuppet cleans up
bpy.ops.stop_motion.unpuppet(puppet=arm.name)
assert not pp.enabled and not any(o.name.startswith("Pin ") for o in bpy.data.objects)
assert not any(c.name == puppet.PIN_CONSTRAINT for pb in arm.pose.bones for c in pb.constraints)
print("PUPPET TESTS PASSED")
sms.unregister()
