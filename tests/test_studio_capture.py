"""Studio renders shot pictures and the view picture off-screen (software GPU)."""
import os, sys, runpy, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, gpu
try:
    gpu.init()          # Blender's Python module with a software GPU
except Exception as exc:  # e.g. the Blender app in -b mode: no off-screen GPU here
    print("STUDIO CAPTURE TESTS SKIPPED (no GPU):", exc)
    sys.exit(0)
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core, puppet, studio

g = runpy.run_path(os.path.join(ROOT, "scripts", "make_test_puppet.py"))
scene, arm = g["scene"], g["arm"]
vl = scene.view_layers[0]
scr = bpy.data.screens['Layout']
area = next(a for a in scr.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
space = area.spaces.active
space.shading.type = 'MATERIAL'
space.shading.use_scene_lights = space.shading.use_scene_world = True
space.overlay.show_overlays = False
scene.stop_motion.capture_dir = tempfile.mkdtemp() + "/"

with bpy.context.temp_override(scene=scene, view_layer=vl, area=area, region=region):
    ctx = bpy.context
    puppet.make_puppet(ctx, arm)
    core.capture_hook = studio.queue_capture         # as when the Studio is open
    sm = scene.stop_motion
    sh = sm.shots.add(); sh.uid = "cap01"; sh.hold = 2
    stale = core.capture_path(scene, "cap01")
    if os.path.exists(stale):
        os.remove(stale)   # unsaved files share a temp folder between runs
    path = core.capture(ctx, scene, "cap01")
    assert studio.S.pending and not os.path.exists(path), "Shoot only queues; the next redraw renders"
    studio.render_captures(ctx)
    assert os.path.exists(path) and not studio.S.pending
    img = core.shot_image(scene, "cap01")
    assert img is not None and img.size[0] == 960 and img.size[1] == 540, tuple(img.size)
    import numpy as np
    px = np.array(img.pixels[:], dtype=np.float32).reshape(540, 960, 4)
    print("capture mean", px[..., :3].mean().round(3), "->", path)
    assert 0.05 < px[..., :3].mean() < 0.95 and px[..., :3].std() > 0.03, "a real picture, not blank"
    # the free-view picture
    studio.init_free_view(scene)
    off = studio.render_view(ctx, "picture", 400, 300, 'FREE')
    assert off is not None and off.width == 400
    # drag a shot's edge in the strip: every 30 px is one frame of hold, never below 1
    for k in range(2):
        x = sm.shots.add(); x.uid = "hd%d" % k; x.hold = 2
    studio.drag_hold(1, 65)
    assert [x.hold for x in sm.shots] == [2, 4, 2], [x.hold for x in sm.shots]
    studio.drag_hold(1, -200)
    assert [x.hold for x in sm.shots] == [2, 1, 2], [x.hold for x in sm.shots]
    studio.S.hold_drag.clear()
    print("hold drag ok")
    core.capture_hook = None
    import shutil; shutil.copy(path, "/tmp/studio_capture.png")
print("STUDIO CAPTURE TESTS PASSED")
