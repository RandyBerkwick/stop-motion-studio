import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import bpy, os
import stop_motion_studio as sms; sms.register()
from stop_motion_studio import core
scene = bpy.context.scene
for i in range(3):
    scene.objects["Cube"].location.x = i; bpy.ops.stop_motion.shoot()
sm = scene.stop_motion
# fake pictures
for s in sm.shots:
    img = bpy.data.images.new("tmp", 32, 18); img.filepath_raw = core.capture_path(scene, s.uid); img.file_format='PNG'; img.save(); bpy.data.images.remove(img)
sm.ghost_count = 2
scene.frame_set(core.live_frame(scene))
bgs = scene.camera.data.background_images
print("live ghosts:", [(b.image.name, round(b.alpha,3)) for b in bgs])
assert [b.image.name for b in bgs] == [core.GHOST_PREFIX+sm.shots[2].uid, core.GHOST_PREFIX+sm.shots[1].uid]
scene.frame_set(3)  # on shot 2 -> ghost shot 1 only
print("on shot 2:", [b.image.name for b in bgs])
assert [b.image.name for b in bgs] == [core.GHOST_PREFIX+sm.shots[0].uid]
sm.ghost_enabled = False; assert len(bgs) == 0
print("icon id", core.shot_icon(scene, sm.shots[0].uid))
bpy.ops.stop_motion.delete_shot(index=0)
assert not os.path.exists(core.capture_path(scene, "x")) 
print("GHOST TESTS PASSED")
sms.unregister(); sms.register(); sms.unregister()
print("re-register ok")
