"""Fingers are posed by swapping hand shapes, or by sculpting a hand on a shot and keeping it as a new shape."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
from mathutils import Vector
import stop_motion_studio as sms
sms.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
from stop_motion_studio import assembly, core, faces, puppet, sculpt

ctx = bpy.context
scene = ctx.scene
cam = bpy.data.objects.new("Camera A", bpy.data.cameras.new("Camera A")); scene.collection.objects.link(cam); scene.camera = cam
pip = assembly.new_build(ctx, "Pip", 'PERSON'); assembly.starter(ctx, pip); faces.make_all(ctx, pip)
pp = assembly.finish_build(ctx, pip)
hands = {s.name: [i.label for i in s.items] for s in pp.swap_sets if "hand" in s.name}
print("hand shapes", hands)
assert hands["Left hand"] == ["Open", "Relaxed", "Fist", "Point", "Grip", "Thumbs up"]

for _ in range(3):
    assert bpy.ops.stop_motion.shoot() == {'FINISHED'}
uid = scene.stop_motion.shots[1].uid
hand = bpy.data.objects["LeftHand_Open"]
# sculpt shot 2's open hand: pull the fingers out
kb = sculpt.sculpt_key(hand, uid, create=True)
base = hand.data.shape_keys.key_blocks[0]
tip = max(range(len(hand.data.vertices)), key=lambda i: -base.data[i].co.z)
for i, d in enumerate(kb.data):
    d.co = base.data[i].co + Vector((0, -0.01, 0)) * (1 if i == tip else 0.2)
new = sculpt.save_as_new_piece(ctx, hand, uid)
assert new is not None and new.name == "LeftHand_Shape1", new
assert new.data.shape_keys is None and (new.data.vertices[tip].co - base.data[tip].co).length > 0.005
assert sculpt.sculpt_key(hand, uid, create=False) is None, "the one-off sculpt is gone: the shot uses the new shape"
sets = {s.name: s for s in pip.stop_motion_puppet.swap_sets}
labels = [i.label for i in sets["Left hand"].items]
print("left hand now", labels)
assert labels[-1] == "Shape 1" and len(labels) == 7

def showing(f):
    scene.frame_set(f)
    return [i.obj.name for i in sets["Left hand"].items if not i.obj.hide_viewport]
starts = [core.shot_start(scene, i) for i in range(3)]
print("shot 1, 2, 3 show", [showing(f) for f in starts])
assert showing(starts[1]) == ["LeftHand_Shape1"]
assert showing(starts[0]) == ["LeftHand_Open"] and showing(starts[2]) == ["LeftHand_Open"]
print("HAND SHAPES TESTS PASSED")
sms.unregister()
