import os, sys, runpy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy
import stop_motion_studio as sms
sms.register()
g = runpy.run_path(os.path.join(ROOT, "scripts", "make_test_puppet.py"))
scene, arm = g["scene"], g["arm"]
vl = scene.view_layers[0]
vl.update()
assert len(arm.data.bones) == 16, len(arm.data.bones)
eo = bpy.data.objects["Eyes_Open"]
centre = sum((eo.matrix_world @ v.co for v in eo.data.vertices), __import__("mathutils").Vector()) / len(eo.data.vertices)
print("eyes centre", tuple(round(x, 3) for x in centre))
assert abs(centre.z - 1.975) < 0.03 and abs(centre.y + 0.26) < 0.03, centre
with bpy.context.temp_override(scene=scene, view_layer=vl, active_object=arm, object=arm, selected_objects=[arm]):
    from stop_motion_studio import puppet
    pp = puppet.make_puppet(bpy.context, arm)
print("rings", [(r.label, bool(r.pin)) for r in pp.rings])
print("swaps", [(s.name, s.kind, [i.label for i in s.items]) for s in pp.swap_sets])
assert len(pp.rings) == 7 and sum(bool(r.pin) for r in pp.rings) == 2
names = sorted(s.name for s in pp.swap_sets)
assert names == ["Brows", "Eyes", "Hand", "Mouth"], names
for s in pp.swap_sets:
    if s.kind == 'MESH':
        assert sum(1 for i in s.items if not i.obj.hide_viewport) == 1, s.name
# hand ring drag stand-in: moving the hand bone moves the swap hand with it
hand = bpy.data.objects["Hand_Fist"]
before = hand.matrix_world.translation.copy()
arm.pose.bones["upper_arm.R"].rotation_quaternion = (0.9, 0.0, 0.43, 0.0)
vl.update()
assert (hand.matrix_world.translation - before).length > 0.1
print("TEST PUPPET SCRIPT PASSED")
