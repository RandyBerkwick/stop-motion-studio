"""Renders the Studio interface off-screen to a PNG (no window needed).

    python3 tools/preview_studio.py out.png [ANIMATE|PUPPETS|REVIEW] [PUPPET|PROPS|LIGHT|SCULPT] [live.png]

Uses Blender's Python module with a software GPU. The live view and the
picture are stand-in images (a real 3D view needs a window)."""
import os, sys, runpy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, gpu
gpu.init()
from mathutils import Matrix
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core, puppet, studio
from stop_motion_studio.studio_kit import Kit, Rect, Theme, studio_layout
from stop_motion_studio.studio_paint import GPUPainter

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/studio.png"
mode = sys.argv[2] if len(sys.argv) > 2 else "ANIMATE"
side = sys.argv[3] if len(sys.argv) > 3 else "PUPPET"
live_img_path = sys.argv[4] if len(sys.argv) > 4 else None
W, H = 1440, 900

g = runpy.run_path(os.path.join(ROOT, "scripts", "make_test_puppet.py"))
scene, arm = g["scene"], g["arm"]
vl = scene.view_layers[0]
live_img = bpy.data.images.load(live_img_path) if live_img_path and os.path.exists(live_img_path) else None
REAL = live_img is None
scr = bpy.data.screens['Layout']
area = next(a for a in scr.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
space = area.spaces.active
space.shading.type = 'MATERIAL'
space.shading.use_scene_lights = space.shading.use_scene_world = True
space.overlay.show_overlays = False
import tempfile
scene.stop_motion.capture_dir = tempfile.mkdtemp() + "/"

with bpy.context.temp_override(scene=scene, view_layer=vl, area=area, region=region):
    ctx = bpy.context
    puppet.make_puppet(ctx, arm)
    vl.objects.active = arm
    sm = scene.stop_motion
    if REAL:
        # really shoot: lift the right arm a little each shot, capture off-screen
        core.capture_hook = studio.queue_capture
        ua = arm.pose.bones["upper_arm.R"]
        from mathutils import Quaternion
        for i in range(8):
            ua.rotation_quaternion = Quaternion((1, 0, 0), -0.16 * i)
            bpy.ops.stop_motion.shoot()
            studio.render_captures(ctx)
        core.capture_hook = None
        sm.shots[4].hold = 5   # one longer hold, as if its edge had been dragged
        core.sync_range(scene); scene.frame_current = core.live_frame(scene)
        ua.rotation_quaternion = Quaternion((1, 0, 0), -0.16 * 8)
    else:
        # fake shots with stand-in pictures
        for i in range(14):
            sh = sm.shots.add(); sh.uid = "fake%02d" % i; sh.hold = 4 if i == 9 else 2
            img = live_img.copy(); img.name = core.GHOST_PREFIX + sh.uid
    scene.frame_current = core.live_frame(scene)
    scene.stop_motion_views.add().name = "Side on"
    scene.stop_motion_views.add().name = "Hands close"

    studio.S.mode = mode
    studio.S.side = side
    studio.S.active = False
    p = GPUPainter()
    kit = Kit(p)

    class FakeOff:
        def __init__(self, tex): self.texture_color = tex
    if not REAL:
        studio.render_view = lambda c, key, w, h, which: FakeOff(gpu.texture.from_image(live_img))
    else:
        studio.init_free_view(scene)
        cam_off = studio.render_view(ctx, "live", 1024, 576, 'CAMERA')   # stands in for the live 3D view
        # Render the picture now: nesting off-screen buffers inside the preview's own one isn't supported
        # (in Blender the Studio draws straight to the window, so it doesn't arise there).
        pic_off = studio.render_view(ctx, "picture", 268, 268, 'FREE')
        studio.render_view = lambda c, key, w, h, which: pic_off

    off = gpu.types.GPUOffScreen(W, H)
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 1.0))
        gpu.matrix.load_matrix(Matrix.Identity(4))
        gpu.matrix.load_projection_matrix(Matrix(((2 / W, 0, 0, -1), (0, 2 / H, 0, -1), (0, 0, -1, 0), (0, 0, 0, 1))))
        s = 1.0
        L = studio_layout(W, H, s)
        studio.S.layout = L
        kit.begin(s)
        live = L["live"]
        p.rect(live, Theme.stage)
        border = live.inset(8).fit_aspect(16 / 9)
        if live_img is not None:
            p.image(border, live_img)
        else:
            p.texture(border, cam_off.texture_color)
            studio.draw_ghost(p, scene, border)
        p.rect_outline(border, Theme.accent, 0, 2)
        for key in ("top", "head_left", "head_centre", "head_right", "left", "right", "footer"):
            p.rect(L[key], Theme.ground if key in ("left", "right") else Theme.panel)
        p.rect(Rect(L["top"].x, L["top"].y, L["top"].w, 1), Theme.line)
        p.rect(Rect(L["footer"].x, L["footer"].top - 1, L["footer"].w, 1), Theme.line)
        for key in ("head_left", "head_centre", "head_right"):
            p.rect(Rect(L[key].x, L[key].y, L[key].w, 1), Theme.line)
        p.rect(Rect(L["right"].x, L["right"].y, 1, L["right"].h), Theme.line)
        studio.draw_top(kit, L["top"], scene, s)
        studio.draw_view_headers(kit, L, scene, s)
        studio.draw_left(kit, L["left"], ctx, scene, s)
        studio.draw_right(kit, L["right"], ctx, scene, s)
        studio.draw_footer(kit, L["footer"], scene, s)
        studio.draw_live_badge(kit, live, scene, s)
        buf = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
    import numpy as np
    try:
        arr = np.frombuffer(buf, dtype=np.float32); how = "frombuffer"
    except Exception:
        arr = np.array(buf.to_list(), dtype=np.float32).ravel(); how = "to_list"
    img = bpy.data.images.new("preview", W, H, alpha=True)
    img.pixels.foreach_set(np.clip(arr, 0, 1))
    img.filepath_raw = out; img.file_format = 'PNG'; img.save()
    print("saved", out, "pixels via", how, "hits", len(kit.hits))
