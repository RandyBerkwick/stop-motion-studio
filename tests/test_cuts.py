"""Camera cuts: each shot remembers its camera; markers make the film switch; edits keep cuts in place."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core

scene = bpy.context.scene
scene.frame_start = 1
sm = scene.stop_motion
sm.default_hold = '2'
cam_a = scene.camera
cam_a.name = "Camera A"
cam_b = bpy.data.objects.new("Camera B", bpy.data.cameras.new("Camera B"))
scene.collection.objects.link(cam_b)
cube = bpy.data.objects["Cube"]


def shoot(x):
    cube.location.x = x
    assert bpy.ops.stop_motion.shoot() == {'FINISHED'}


def use(cam, scope='AUTO'):
    assert bpy.ops.stop_motion.use_camera(name=cam.name, scope=scope) == {'FINISHED'}


def cams():
    return [c.name[-1] for c in core.shot_cameras(scene)]


def camera_on_frames():
    out = []
    for f in range(scene.frame_start, core.live_frame(scene) + 1):
        scene.frame_set(f)
        out.append(scene.camera.name[-1])
    return "".join(out)


shoot(0); shoot(1)
assert cams() == ['A', 'A']
assert not [m for m in scene.timeline_markers if m.name.startswith(core.CUT_PREFIX)], "one camera: no markers"

# live: switch to B, the next shots are filmed with B
use(cam_b)
assert scene.camera == cam_b and core.live_camera(scene) == cam_b
shoot(2); shoot(3)
assert cams() == ['A', 'A', 'B', 'B'], cams()
print("frames", camera_on_frames())
assert camera_on_frames() == "AAAABBBBB", "playback switches camera at the cut (frame 5) and stays on B live"

# back to A live for two more
use(cam_a)
shoot(4); shoot(5)
assert cams() == ['A', 'A', 'B', 'B', 'A', 'A']
print("cuts", [(i + 1, c.name) for i, c in core.cuts(scene)])
assert [(i, c.name[-1]) for i, c in core.cuts(scene)] == [(0, 'A'), (2, 'B'), (4, 'A')]

# on shot 2 cut to B "to the next cut": shot 2 joins the B run, the A run after stays
scene.frame_set(core.shot_start(scene, 1))
use(cam_b)
assert cams() == ['A', 'B', 'B', 'B', 'A', 'A'], cams()
# this shot only: shot 6 to B, nothing else changes, live stays A
scene.frame_set(core.shot_start(scene, 5))
use(cam_b, 'SHOT')
assert cams() == ['A', 'B', 'B', 'B', 'A', 'B'], cams()
assert core.live_camera(scene) == cam_a, core.live_camera(scene)
# start of a run: shot 3 (the B run from shot 2) back to A goes to the next cut only
scene.frame_set(core.shot_start(scene, 2))
use(cam_a)
assert cams() == ['A', 'B', 'A', 'A', 'A', 'B'], cams()

# deleting and holding keep each shot's camera (markers follow the shots)
bpy.ops.stop_motion.delete_shot(index=0)
assert cams() == ['B', 'A', 'A', 'A', 'B'], cams()
bpy.ops.stop_motion.hold(delta=2, index=0)
print("after edits", camera_on_frames())
assert camera_on_frames() == "BBBB" + "AA" * 3 + "BB" + "A", camera_on_frames()
# duplicating a shot copies its camera
bpy.ops.stop_motion.duplicate_shot(index=4)
assert cams() == ['B', 'A', 'A', 'A', 'B', 'B'], cams()

# just looking doesn't change the film
scene.frame_set(core.shot_start(scene, 1))
use(cam_b, 'LOOK')
assert scene.camera == cam_b and cams()[1] == 'A'
scene.frame_set(core.shot_start(scene, 2))
assert scene.camera == cam_a, "the film's camera comes back on the next frame change"

# ghost: only earlier shots from the same camera
sm.ghost_enabled = True
for i, s in enumerate(sm.shots):          # fake shot pictures so the ghost has something to show
    img = bpy.data.images.new(core.GHOST_PREFIX + s.uid, 4, 4)
scene.frame_set(core.shot_start(scene, 4))   # shot 5, filmed with B; shot 4 (A) is the one before
sm.ghost_count = 1
core.update_ghost(scene)
bgs = [bg.image.name for bg in cam_b.data.background_images if bg.image]
assert bgs == [core.GHOST_PREFIX + sm.shots[0].uid], ("ghost skips A shots and shows shot 1 (B)", bgs)
assert not [bg for bg in cam_a.data.background_images if bg.image and bg.image.name.startswith(core.GHOST_PREFIX)]
print("CUTS TESTS PASSED")
sms.unregister()
