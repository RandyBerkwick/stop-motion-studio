import os, sys, runpy
from types import SimpleNamespace
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy
from mathutils import Quaternion, Vector
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import cameras, core, lighting

scene = bpy.context.scene
cam_a = scene.camera
own = [o for o in scene.objects if o.type == 'LIGHT']

# --- cameras
bpy.ops.stop_motion.new_camera()
cam_b = scene.camera
assert cam_b is not cam_a and cam_b.name == "Camera A", cam_b.name   # first free letter
fv = cameras.find_free_view(bpy.context.screen)
expect = fv.spaces.active.region_3d.view_matrix.inverted().translation if fv else cam_a.matrix_world.translation
assert (cam_b.location - expect).length < 1e-4, (cam_b.location, expect)
bpy.ops.stop_motion.lock_camera(name=cam_b.name)
assert cameras.is_locked(cam_b) and cam_b.hide_select
bpy.ops.stop_motion.lock_camera(name=cam_b.name)
assert not cameras.is_locked(cam_b)
bpy.ops.stop_motion.use_camera(name=cam_a.name)
assert scene.camera is cam_a
print("cameras ok")

# --- saved views (store / restore round trip)
r3d = SimpleNamespace(view_location=Vector((1, 2, 3)), view_rotation=Quaternion((0.7, 0.7, 0, 0)),
                      view_distance=4.5, view_perspective='PERSP')
v = scene.stop_motion_views.add()
cameras.store_view(v, r3d)
r3d2 = SimpleNamespace(view_location=None, view_rotation=None, view_distance=0, view_perspective='ORTHO')
cameras.restore_view(v, r3d2)
assert tuple(r3d2.view_location) == (1, 2, 3) and abs(r3d2.view_distance - 4.5) < 1e-6 and r3d2.view_perspective == 'PERSP'
print("views ok")

# --- studio preset
bpy.ops.stop_motion.light_preset(preset='THREE_POINT')
col = bpy.data.collections[lighting.COLLECTION]
assert sorted(o.name for o in col.objects) == ["Fill", "Key", "Rim"], [o.name for o in col.objects]
assert all(o.hide_render for o in own)
key = bpy.data.objects["Key"]
aim = key.matrix_world.to_quaternion() @ Vector((0, 0, -1))
centre, _r = lighting.stage(scene)
assert aim.dot((centre - key.location).normalized()) > 0.99   # aimed at the stage
bpy.ops.stop_motion.light_preset(preset='MOONLIGHT')
assert sorted(o.name for o in col.objects) == ["Moon", "Night bounce"]
assert not bpy.data.objects.get("Key")
print("studio preset ok")

# --- HDRI preset
bpy.ops.stop_motion.hdri_preset(preset='FOREST')
bg = lighting.world_background(scene)
assert bg.inputs["Color"].is_linked and len(col.objects) == 0
env = scene.world.node_tree.nodes[lighting.ENV]
assert env.image and env.image.packed_file, "Blender's HDRI should be packed"
bpy.ops.stop_motion.own_lights()
assert not any(o.hide_render for o in own)
print("hdri ok")

# --- light per shot
bpy.ops.stop_motion.light_preset(preset='WARM_LAMP')
lamp = bpy.data.objects["Lamp"].data
base = lamp.energy
for _ in range(3):
    bpy.ops.stop_motion.shoot()
def energy(f):
    scene.frame_set(f); return round(lamp.energy, 3)
assert [energy(f) for f in (1, 3, 5)] == [round(base, 3)] * 3
scene.frame_set(3); lamp.energy = 10.0
bpy.ops.stop_motion.apply_light(scope='FROM_HERE')
assert [energy(f) for f in (1, 3, 5)] == [round(base, 3), 10.0, 10.0]
scene.frame_set(1); lamp.energy = 2.0
bpy.ops.stop_motion.apply_light(scope='THIS')
assert [energy(f) for f in (1, 3, 5)] == [2.0, 10.0, 10.0]
# world strength is part of the shot
bg = lighting.world_background(scene)
scene.frame_set(5); bg.inputs["Strength"].default_value = 0.3
bpy.ops.stop_motion.apply_light(scope='THIS')
scene.frame_set(1); s1 = bg.inputs["Strength"].default_value
scene.frame_set(5); s3 = bg.inputs["Strength"].default_value
assert abs(s3 - 0.3) < 1e-6 and abs(s1 - 0.3) > 1e-3
print("light per shot ok")

# --- effects
scene.frame_set(3)
bpy.ops.stop_motion.light_effect(effect='FLASH')
assert [energy(f) for f in (1, 3, 5)] == [2.0, 60.0, 10.0], [energy(f) for f in (1, 3, 5)]
scene.frame_set(5)
bpy.ops.stop_motion.light_effect(effect='LIGHTS_OUT')
assert energy(5) == 0.0 and energy(3) == 60.0
for _ in range(4):
    scene.frame_set(core.live_frame(scene)); lamp.energy = 8.0
    bpy.ops.stop_motion.shoot()
scene.frame_set(core.shot_start(scene, 3))
bpy.ops.stop_motion.light_effect(effect='FADE_NIGHT', count=3)
e = [energy(core.shot_start(scene, i)) for i in range(3, 7)]
print("fade", e)
assert e[0] == 8.0 and e[1] < 8.0 and e[2] == 2.0 and e[3] == 2.0, e
print("effects ok")

# --- lights follow shots when timing changes
bpy.ops.stop_motion.delete_shot(index=0)
assert energy(1) == 60.0 and energy(3) == 0.0, (energy(1), energy(3))
for idb in core.animated_ids(scene):
    for fc in core.fcurves_of(idb):
        assert all(k.interpolation == 'CONSTANT' for k in fc.keyframe_points), (idb, fc.data_path)
print("CAMERA AND LIGHT TESTS PASSED")
sms.unregister()
