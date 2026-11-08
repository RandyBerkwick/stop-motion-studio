"""GIF and Blender-scene export, and the review modes (loop, back and forth, last N shots)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
import numpy as np
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core, ops, gif

tmp = tempfile.mkdtemp(prefix="sm_export_")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(tmp, "film.blend"))
scene = bpy.context.scene
scene.frame_start = 1
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 320, 180, 100
sm = scene.stop_motion
sm.fps = '12'
cube = bpy.data.objects["Cube"]
holds = [2, 1, 3, 2, 2]
for i, h in enumerate(holds):
    cube.location.x = i * 0.5
    sm.default_hold = str(min(3, h))
    assert bpy.ops.stop_motion.shoot() == {'FINISHED'}
    sm.shots[-1].hold = h
core.sync_range(scene)

# headless there is no viewport capture: make shot pictures by hand (a different colour each)
for i, shot in enumerate(sm.shots):
    img = bpy.data.images.new("tmp", 96, 54)
    px = np.zeros((54, 96, 4), np.float32)
    px[..., 0] = i / 4.0
    px[..., 1] = 0.3
    px[..., 3] = 1
    px[:10, :, 2] = 1.0           # a blue band along the bottom (Blender rows go bottom-up)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = core.capture_path(scene, shot.uid)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    core.refresh_image(scene, shot.uid)

# --- GIF, as shot: one picture per shot, held for its hold
assert bpy.ops.stop_motion.export(kind='GIF', quality='AS_SHOT') == {'FINISHED'}
path = os.path.join(tmp, "films", "film.gif")
assert os.path.exists(path), path
from PIL import Image
im = Image.open(path)
n, durs, firsts = 0, [], []
while True:
    a = np.array(im.convert("RGB"))
    firsts.append((int(a[0, 0, 2]), int(a[-1, 0, 2]), int(a[a.shape[0] // 2, 0, 0])))
    durs.append(im.info["duration"])
    n += 1
    try:
        im.seek(n)
    except EOFError:
        break
print("gif frames", n, "durations ms", durs, "size", im.size)
assert n == 5 and im.size == (96, 54)
assert abs(sum(durs) - sum(holds) * 1000 / 12) < 15, "total length matches the film"
assert durs[2] > durs[1] * 2.5, "a 3-frame hold shows 3x as long as a 1-frame hold"
assert firsts[0][1] > 200 and firsts[0][0] < 60, "picture is the right way up (blue band at the bottom)"
assert firsts[4][2] > firsts[0][2] + 150, "each shot is its own picture"

# back and forth: forwards then backwards without repeating the ends
assert bpy.ops.stop_motion.export(kind='GIF', quality='AS_SHOT', bounce=True) == {'FINISHED'}
im = Image.open(path)
assert im.n_frames == 8, im.n_frames

# --- GIF, final render (Workbench here)
frames, fholds = ops.gif_frames(bpy.context, scene, 'FINAL', width=160)
assert len(frames) == 5 and frames[0].shape == (90, 160, 3) and fholds == holds, (len(frames), frames[0].shape, fholds)
assert not np.array_equal(frames[0], frames[4]), "the cube moved between shots"
print("final gif frames ok")

# --- Blender scene copy
assert bpy.ops.stop_motion.export(kind='BLEND') == {'FINISHED'}
bpath = os.path.join(tmp, "films", "film_scene.blend")
assert os.path.exists(bpath) and os.path.getsize(bpath) > 10000
with bpy.data.libraries.load(bpath) as (src, _dst):
    assert scene.name in src.scenes
assert bpy.data.filepath.endswith("film.blend"), "still working in the original file"
print("blend copy ok")

# --- review modes (drive the player's tick by hand)
def run_ticks(n):
    seen = []
    for _ in range(n):
        ops._tick()
        seen.append(scene.frame_current)
    return seen

last = core.live_frame(scene) - 1          # 10
sm.play_mode = 'LOOP'
ops.start_playing(scene)
assert ops.is_playing() and scene.frame_current == 1
seen = run_ticks(12)
print("loop", seen)
assert seen[:10] == list(range(2, 11)) + [1]
sm.play_mode = 'BOUNCE'
scene.frame_set(8)
seen = run_ticks(6)
print("bounce", seen)
assert seen == [9, 10, 9, 8, 7, 6], seen
scene.frame_set(2)
ops.PLAYER["dir"] = -1
assert run_ticks(2) == [1, 2]
sm.play_mode = 'LAST'
sm.play_last = 2
first, _l = ops.play_range(scene)
assert first == core.shot_start(scene, 3) == 7, first
scene.frame_set(10)
seen = run_ticks(5)
print("last 2 shots", seen)
assert seen == [7, 8, 9, 10, 7], seen
# shooting stops playback
assert bpy.ops.stop_motion.shoot() == {'FINISHED'} and not ops.is_playing()
ops.start_playing(scene)
ops.stop_playing(scene)
assert not ops.is_playing() and scene.frame_current == core.live_frame(scene), "stopping goes back to live"
print("EXPORT/REVIEW TESTS PASSED")
sms.unregister()
