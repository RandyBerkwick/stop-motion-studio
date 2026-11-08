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

    env = os.environ.get
    if env("SM_PREVIEW_CUTS") and REAL:
        cam_a = scene.camera
        cam_b = cam_a.copy(); cam_b.data = cam_a.data.copy(); cam_b.name = "Camera B"
        scene.collection.objects.link(cam_b)
        cam_b.location.x += 1.2
        core.set_camera(scene, 3, cam_b, 'RUN')
        core.set_camera(scene, 6, cam_a, 'RUN')
        scene.frame_current = core.live_frame(scene)
    studio.S.mode = mode
    studio.S.side = side
    pstep = os.environ.get("SM_PREVIEW_PSTUDIO")
    if pstep:
        from stop_motion_studio import assembly, faces, studio_puppets as sp, trial, rigsculpt
        if pstep == 'JOINTS':
            # a one-piece sculpt to place joints on: a kit puppet melted into one mesh
            ref = assembly.new_build(ctx, "Ref", 'PERSON', location=(3.0, 0.0, 0.0)); assembly.starter(ctx, ref)
            import bmesh as _bm
            dg = ctx.evaluated_depsgraph_get(); bm = _bm.new()
            for o in assembly.kit_parts(ref):
                me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world); bm.from_mesh(me)
            me = bpy.data.meshes.new("Wren"); bm.to_mesh(me); bm.free()
            wren = bpy.data.objects.new("Wren", me); scene.collection.objects.link(wren)
            wren.data.materials.append(assembly.clay("green"))
            for o in list(ref.children_recursive) + [ref]: bpy.data.objects.remove(o)
            vl.update()
            j = rigsculpt.guess(ctx, wren, 'PERSON')
            for k in ("wrist.L", "wrist.R", "fingertip.L", "fingertip.R", "hip.L", "hip.R", "knee.L", "knee.R", "ankle.L", "ankle.R", "toe.L", "toe.R"):
                j.pop(k, None)
            rigsculpt.set_joints(wren, j)
            for o in ctx.selected_objects: o.select_set(False)
            vl.objects.active = wren
            sp.P.start, sp.P.step, sp.P.joint = 'SCULPT', 'JOINTS', 8
            focus = [wren]
        else:
            pip = assembly.new_build(ctx, "Pip", 'PERSON', location=(3.0, 0.0, 0.0))
            assembly.starter(ctx, pip)
            assembly.add_part(ctx, pip, "body", "pear", "red"); assembly.set_colour(ctx, pip, "arms", "red")
            if pstep in ('FACE', 'TRY', 'SAVE'):
                faces.make_all(ctx, pip); assembly.finish_build(ctx, pip)
            if pstep == 'TRY':
                trial.try_out(ctx, pip)
                res = trial.last_results(pip)
                res[0]["problems"].append({"kind": "FOLDS", "part": "Pip Arms R", "text": "Arms (right) folds in", "fix": "SOFTEN", "fix_label": "Soften joints"})
                pip["sm_try"] = __import__("json").dumps(res)
            vl.objects.active = pip
            sp.P.start, sp.P.step, sp.P.kind = 'PARTS', pstep, "body"
            sp.P.set_name = "Mouth"
            focus = [o for o in pip.children if o.type == 'MESH' and not o.hide_render]
        pts = [o.matrix_world @ __import__("mathutils").Vector(c) for o in focus for c in o.bound_box]
        lo = __import__("mathutils").Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = __import__("mathutils").Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        studio.S.free.location = (lo + hi) / 2
        studio.S.free.distance = (hi - lo).length * 1.25
        studio.S.free_init = True
        studio.S.live = 'FREE'
    if env("SM_PREVIEW_LIB"):
        from stop_motion_studio import library
        library.LIBRARY_DIR = env("SM_PREVIEW_LIB")
        studio.S.lib_file = env("SM_PREVIEW_LIBFILE")
    if env("SM_PREVIEW_SCULPT"):
        body = next(o for o in scene.objects if o.type == 'MESH' and o.parent == arm and o.visible_get()
                    and len(o.data.vertices) > 200)
        for o in ctx.selected_objects: o.select_set(False)
        vl.objects.active = body; body.select_set(True)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='SCULPT')
        from stop_motion_studio import sculpt
        sculpt.set_brush(bpy.context, "Clay Strips")
        scene.stop_motion_sculpting = "%s|x" % body.name
    studio.S.active = False
    p = GPUPainter()
    kit = Kit(p)

    class FakeOff:
        def __init__(self, tex): self.texture_color = tex
    if not REAL:
        studio.render_view = lambda c, key, w, h, which: FakeOff(gpu.texture.from_image(live_img))
    else:
        if not os.environ.get("SM_PREVIEW_PSTUDIO"): studio.init_free_view(scene)
        cam_off = studio.render_view(ctx, "live", 1024, 576, 'FREE' if os.environ.get("SM_PREVIEW_PSTUDIO") else 'CAMERA')   # stands in for the live 3D view
        # Render the picture now: nesting off-screen buffers inside the preview's own one isn't supported
        # (in Blender the Studio draws straight to the window, so it doesn't arise there).
        pic_off = studio.render_view(ctx, "picture", 268, 268, 'CAMERA' if os.environ.get("SM_PREVIEW_PSTUDIO") else 'FREE')
        studio.render_view = lambda c, key, w, h, which: pic_off

    off = gpu.types.GPUOffScreen(W, H)
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 1.0))
        gpu.matrix.load_matrix(Matrix.Identity(4))
        gpu.matrix.load_projection_matrix(Matrix(((2 / W, 0, 0, -1), (0, 2 / H, 0, -1), (0, 0, -1, 0), (0, 0, 0, 1))))
        s = 1.0
        from stop_motion_studio.studio_kit import apply_look
        apply_look(os.environ.get("SM_PREVIEW_LOOK", "DARK"))
        help_env = os.environ.get("SM_PREVIEW_HELP")   # e.g. "ANIMATE:1:0.4" (topic, step, moment in the loop)
        from stop_motion_studio import studio_help
        if help_env:
            hk, hs, hp = (help_env.split(":") + ["0", "0.5"])[:3]
            studio_help.H.open = True
        L = studio_layout(W, H, s, True, bool(help_env))
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
            if Theme.grid is not None and key in ("left", "right"):
                p.grid(L[key], 28 * s, Theme.grid)
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
        if studio.S.mode == 'PUPPETS':
            studio.sp.draw_live(kit, live, ctx, s)
        if help_env:
            p.rect(L["help"], Theme.panel)
            if Theme.grid is not None:
                p.grid(L["help"], 28 * s, Theme.grid)
            p.rect(Rect(L["help"].right - 1, L["help"].y, 1, L["help"].h), Theme.line)
            studio_help.current(studio.S, studio.sp.P)
            if hk != "VIEW":
                studio_help.H.topic = hk
            studio_help.H.step = int(hs)
            studio_help.H.started = 1000.0
            studio_help.draw(kit, L["help"], studio.S, studio.sp.P, s, {"close": lambda: None, "redraw": lambda: None},
                             now=1000.0 + float(hp) * studio_help.LOOP)
        ov = os.environ.get("SM_PREVIEW_OVERLAY")
        if ov:
            studio.S.overlay = ov
            studio.S.swap_at = (live.cx, live.cy)
            if ov == 'LIBRARY':
                studio.draw_library(kit, L["full"], ctx, s)
            elif ov == 'SWAPS':
                studio.draw_swap_popup(kit, L["full"], ctx, s)
            elif ov == 'PROJECTS':
                if os.environ.get("SM_PREVIEW_PROJECTS"):
                    studio.PROJECTS_DIR = os.environ["SM_PREVIEW_PROJECTS"]
                studio.draw_projects(kit, L["full"], s)
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
