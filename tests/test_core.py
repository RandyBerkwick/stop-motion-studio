import sys, math
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import bpy
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core

scene = bpy.context.scene
scene.frame_start = 1
# puppet: armature with 2 bones, rigged mesh with shape keys, a prop
bpy.ops.object.armature_add(location=(0,0,0))
arm = bpy.context.object; arm.name = "Rig"
bpy.ops.object.mode_set(mode='EDIT')
b = arm.data.edit_bones.new("hand"); b.head=(0,0,1); b.tail=(0,0,1.5); b.parent = arm.data.edit_bones[0]
bpy.ops.object.mode_set(mode='OBJECT')
mesh = bpy.data.objects["Cube"]
mod = mesh.modifiers.new("Armature", 'ARMATURE'); mod.object = arm
mesh.shape_key_add(name="Basis"); sk = mesh.shape_key_add(name="Smile")
arm.pose.bones["hand"]["ik_fk"] = 0.0

hand = arm.pose.bones["hand"]
def pose(x, smile): hand.location.x = x; sk.value = smile
def shoot():
    r = bpy.ops.stop_motion.shoot(); assert r == {'FINISHED'}, r

pose(0.0, 0.0); shoot()
pose(1.0, 0.5); shoot()
pose(2.0, 1.0); shoot()
sm = scene.stop_motion
print("shots", [(s.uid, s.hold) for s in sm.shots], "live", core.live_frame(scene), "end", scene.frame_end, "cur", scene.frame_current)
assert core.live_frame(scene) == 7 and scene.frame_end == 6 and scene.frame_current == 7

def at(f):
    scene.frame_set(f); return round(hand.location.x, 3), round(sk.value, 3)
print("eval", [at(f) for f in range(1, 8)])
assert [at(f) for f in range(1,7)] == [(0,0),(0,0),(1,.5),(1,.5),(2,1),(2,1)]

# interpolation constant everywhere
for idb in core.animated_ids(scene):
    for fc in core.fcurves_of(idb):
        assert all(k.interpolation == 'CONSTANT' for k in fc.keyframe_points), fc.data_path
print("constant ok; deformed mesh transform keyed?", any(fc.data_path=='location' for fc in core.fcurves_of(mesh)))
assert not any(fc.data_path=='location' for fc in core.fcurves_of(mesh))
assert any('ik_fk' in fc.data_path for fc in core.fcurves_of(arm))

# pose over shot 2 (frame 3)
scene.frame_set(4); pose(5.0, 0.2); shoot()
assert len(sm.shots) == 3 and at(3) == (5.0, 0.2) and at(5) == (2.0, 1.0), (at(3), at(5))
print("pose over ok")

# hold shot 1 longer: +2
bpy.ops.stop_motion.hold(delta=2, index=0)
print("after hold", [at(f) for f in range(1, 10)], "end", scene.frame_end)
assert [at(f) for f in range(1,9)] == [(0,0)]*4 + [(5,.2)]*2 + [(2,1)]*2 and scene.frame_end == 8

# delete shot 2
bpy.ops.stop_motion.delete_shot(index=1)
print("after delete", [at(f) for f in range(1, 8)], "end", scene.frame_end, [s.hold for s in sm.shots])
assert [at(f) for f in range(1,7)] == [(0,0)]*4 + [(2,1)]*2 and scene.frame_end == 6

# duplicate shot 1 -> becomes shot 2
bpy.ops.stop_motion.duplicate_shot(index=0)
print("after dup", [at(f) for f in range(1, 12)], "end", scene.frame_end, [s.hold for s in sm.shots])
assert [at(f) for f in range(1,11)] == [(0,0)]*8 + [(2,1)]*2 and scene.frame_end == 10

# step / live
scene.frame_set(1); bpy.ops.stop_motion.step(direction='NEXT'); assert scene.frame_current == 5
bpy.ops.stop_motion.go_live(); assert scene.frame_current == core.live_frame(scene) == 11
# shoot at live after edits keeps pose from last shot and adds new
pose(9.0, 0.0); shoot(); assert at(11) == (9.0, 0.0) and len(sm.shots) == 4
print("ALL CORE TESTS PASSED")
sms.unregister()
