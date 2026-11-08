# SPDX-License-Identifier: GPL-3.0-or-later
"""Studio: the app's own full-screen interface, with Blender hidden.

How it works
- One 3D view fills the window (Blender's Focus mode: no top bar, no
  status bar, no headers or side panels) and the window goes full screen.
- Everything you see apart from that 3D view is drawn by us on top of it
  (studio_kit / studio_paint), laid out like the mockups. The live 3D view
  sits in the centre box; the other view (camera or free) is a picture
  rendered off-screen into the left column.
- A modal operator watches all input. It hands Blender only what the live
  view needs (navigation, ring drags, undo) and keeps everything else, so
  Blender's own menus and panels never appear.
- Ctrl+Alt+Shift+B leaves the Studio for normal Blender, and back again.
"""

import math
import os
import time

import bpy
from bpy.app.handlers import persistent
from bpy_extras import view3d_utils
from mathutils import Matrix, Quaternion, Vector

from . import cameras, core, library, lighting, ops, puppet, sculpt, solid
from .studio_kit import Kit, Rect, Theme, studio_layout

PROJECTS_DIR = os.path.join(os.path.expanduser("~"), "Stop Motion")
ESCAPE_HINT = "Ctrl+Alt+Shift+B: Blender"

NAV_EVENTS = {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM',
              'NDOF_MOTION', 'NDOF_BUTTON_FIT', 'NDOF_BUTTON_MENU'}
ALWAYS_PASS = {'TIMER', 'TIMER0', 'TIMER1', 'TIMER2', 'TIMER_JOBS', 'TIMER_AUTOSAVE', 'TIMER_REPORT',
               'TIMERREGION', 'WINDOW_DEACTIVATE', 'ACTIONZONE_AREA', 'ACTIONZONE_REGION',
               'ACTIONZONE_FULLSCREEN', 'XR_ACTION', 'NONE',
               'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT', 'OSKEY'}


# ===================================================================== state

class FreeView:
    """The free view's eye, kept while the live box shows the camera."""

    def __init__(self):
        self.location = Vector((0.0, 0.0, 1.0))
        self.rotation = Quaternion((0.8, 0.45, 0.2, 0.33)).normalized()
        self.distance = 6.0

    def matrix(self):
        return (Matrix.Translation(self.location) @ self.rotation.to_matrix().to_4x4()
                @ Matrix.Translation((0, 0, self.distance))).inverted()

    def store(self, rv3d):
        self.location = rv3d.view_location.copy()
        self.rotation = rv3d.view_rotation.copy()
        self.distance = rv3d.view_distance

    def apply(self, rv3d):
        rv3d.view_location = self.location
        rv3d.view_rotation = self.rotation
        rv3d.view_distance = self.distance

    def orbit(self, dx, dy):
        yaw = Quaternion((0, 0, 1), -dx * 0.008)
        right = self.rotation @ Vector((1, 0, 0))
        pitch = Quaternion(right, -dy * 0.008)
        self.rotation = (yaw @ pitch @ self.rotation).normalized()

    def zoom(self, steps):
        self.distance = max(0.2, self.distance * (0.88 ** steps))


class State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.wanted = False           # re-enter after a file load
        self.area_ptr = 0
        self.mode = 'ANIMATE'         # ANIMATE | PUPPETS | REVIEW
        self.side = 'PUPPET'          # PUPPET | PROPS | LIGHT | SCULPT
        self.live = 'CAMERA'          # what the live box shows: CAMERA | FREE
        self.chrome = True
        self.free = FreeView()
        self.free_init = False
        self.layout = None
        self.went_fullscreen = False
        self.saved_space = None
        self.pending = []             # [(scene name, uid, path)] captures to render
        self.toast = ("", 0.0)
        self.overlay = None           # None | 'PROJECTS' | 'LIBRARY' | 'SWAPS'
        self.lib_file = None          # the library file picked in the browser
        self.lib_cache = {}           # path -> (mtime, items)
        self.swap_at = (0, 0)         # where D was pressed
        self.hold_drag = {}           # shot index -> pixels dragged on its edge
        self.export_kind = 'MOVIE'
        self.export_quality = 'AS_SHOT'
        self.hint_until = 0.0
        self.painter = None
        self.kit = None
        self.offscreens = {}


S = State()


def toast(text, seconds=2.5):
    S.toast = (text, time.time() + seconds)


def scale():
    try:
        v = bpy.context.preferences.system.ui_scale
    except Exception:
        v = 1.0
    return v if v and v > 0.1 else 1.0   # no window (scripts, tests): Blender reports 0


def studio_area(window=None):
    window = window or bpy.context.window
    if window is None:
        return None, None
    for area in window.screen.areas:
        if area.as_pointer() == S.area_ptr:
            return area, next((r for r in area.regions if r.type == 'WINDOW'), None)
    # Focus mode re-creates the area; the studio area is then the only 3D view.
    views = [a for a in window.screen.areas if a.type == 'VIEW_3D']
    if len(views) == 1 and window.screen.show_fullscreen:
        S.area_ptr = views[0].as_pointer()
        return views[0], next((r for r in views[0].regions if r.type == 'WINDOW'), None)
    return None, None


def live_rect():
    return S.layout["live"] if S.layout else None


def is_active():
    return S.active


# ================================================================ operations

def run(op, *args, **kwargs):
    """Call an operator as if from the studio's 3D view."""
    ctx = bpy.context
    area, region = studio_area()
    try:
        if area is not None:
            with ctx.temp_override(window=ctx.window, area=area, region=region):
                return op(*args, **kwargs)
        return op(*args, **kwargs)
    except RuntimeError as exc:
        toast(str(exc).split("\n")[0].replace("Error: ", ""))
        return {'CANCELLED'}


def redraw():
    area, _r = studio_area()
    if area is not None:
        area.tag_redraw()


def swap_views():
    area, region = studio_area()
    if area is None:
        return
    rv3d = area.spaces.active.region_3d
    if S.live == 'CAMERA':
        S.live = 'FREE'
        rv3d.view_perspective = 'PERSP'
        S.free.apply(rv3d)
    else:
        S.free.store(rv3d)
        S.live = 'CAMERA'
        rv3d.view_perspective = 'CAMERA'
        area.spaces.active.lock_camera = False
    redraw()


def init_free_view(scene):
    centre, radius = lighting.stage(scene)
    S.free.location = centre
    S.free.distance = max(2.5, radius * 3.2)
    S.free_init = True


def save_project():
    if bpy.data.filepath:
        run(bpy.ops.wm.save_mainfile)
        toast("Saved")
        return
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(PROJECTS_DIR, "Scene %02d.blend" % n)):
        n += 1
    path = os.path.join(PROJECTS_DIR, "Scene %02d.blend" % n)
    run(bpy.ops.wm.save_as_mainfile, filepath=path)
    toast("Saved as " + os.path.basename(path))


def list_projects():
    if not os.path.isdir(PROJECTS_DIR):
        return []
    files = [f for f in os.listdir(PROJECTS_DIR) if f.endswith(".blend")]
    return sorted(files, key=lambda f: -os.path.getmtime(os.path.join(PROJECTS_DIR, f)))


def open_project(name):
    S.wanted = True
    S.overlay = None
    bpy.ops.wm.open_mainfile(filepath=os.path.join(PROJECTS_DIR, name))


def new_project():
    S.wanted = True
    S.overlay = None
    bpy.ops.wm.read_homefile(use_empty=False)


def shot_index():
    scene = bpy.context.scene
    return core.shot_index_at(scene, scene.frame_current)


# ============================================================= off-screen views

def _offscreen(key, w, h):
    import gpu
    w, h = max(8, int(w)), max(8, int(h))
    off = S.offscreens.get(key)
    if off is None or off.width != w or off.height != h:
        if off is not None:
            off.free()
        off = gpu.types.GPUOffScreen(w, h)
        S.offscreens[key] = off
    return off


def perspective(fov, aspect, near, far):
    f = 1.0 / math.tan(fov / 2)
    return Matrix(((f / aspect, 0, 0, 0), (0, f, 0, 0),
                   (0, 0, (far + near) / (near - far), 2 * far * near / (near - far)), (0, 0, -1, 0)))


def render_view(context, key, w, h, which):
    """Render the camera or the free view into an off-screen texture."""
    scene = context.scene
    dg = context.evaluated_depsgraph_get()
    if which == 'CAMERA':
        cam = scene.camera
        if cam is None:
            return None
        ce = cam.evaluated_get(dg)
        view = ce.matrix_world.inverted()
        proj = ce.calc_matrix_camera(dg, x=int(w), y=int(h))
    else:
        view = S.free.matrix()
        proj = perspective(math.radians(40), w / max(1, h), 0.01 * S.free.distance + 0.01, 500.0)
    off = _offscreen(key, w, h)
    off.draw_view3d(scene, context.view_layer, context.space_data, context.region,
                    view, proj, do_color_management=True)
    return off


def render_captures(context):
    """Shoot asked for pictures: render the camera off-screen and save them."""
    if not S.pending:
        return
    import gpu
    import numpy as np
    todo, S.pending = S.pending, []
    for scene_name, uid, path in todo:
        scene = bpy.data.scenes.get(scene_name)
        if scene is None or scene != context.scene:
            continue
        rx, ry = scene.render.resolution_x, scene.render.resolution_y
        w = 960
        h = max(8, round(w * ry / max(1, rx)))
        off = render_view(context, "capture", w, h, 'CAMERA')
        if off is None:
            continue
        with off.bind():
            fb = gpu.state.active_framebuffer_get()
            buf = fb.read_color(0, 0, w, h, 4, 0, 'FLOAT')
        try:
            arr = np.frombuffer(buf, dtype=np.float32)
        except (TypeError, ValueError):
            arr = np.array(buf.to_list(), dtype=np.float32).ravel()
        img = bpy.data.images.get("SM capture") or bpy.data.images.new("SM capture", w, h, alpha=True)
        if img.size[0] != w or img.size[1] != h:
            img.scale(w, h)
        img.pixels.foreach_set(np.clip(arr, 0.0, 1.0))
        img.filepath_raw = path
        img.file_format = 'PNG'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save()
        core.refresh_image(scene, uid)


def queue_capture(context, scene, uid):
    """core.capture hook while the Studio is open."""
    path = core.capture_path(scene, uid)
    S.pending.append((scene.name, uid, path))
    redraw()
    return path


# ============================================================ camera framing

def zoom_to_fac(z):
    return ((math.sqrt(2) + z / 50.0) ** 2) / 4.0


def fac_to_zoom(f):
    return 50.0 * (2.0 * math.sqrt(max(1e-6, f)) - math.sqrt(2))


def camera_border(context, region, rv3d):
    scene = context.scene
    cam = scene.camera
    if cam is None or rv3d is None:
        return None
    corners = [cam.matrix_world @ v for v in cam.data.view_frame(scene=scene)]
    pts = [view3d_utils.location_3d_to_region_2d(region, rv3d, c) for c in corners]
    if any(p is None for p in pts):
        return None
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def fit_camera(context, region, rv3d, box):
    """Zoom the camera view so the camera frame fits `box`."""
    border = camera_border(context, region, rv3d)
    if border is None or border.w < 2:
        return border
    scene = context.scene
    aspect = scene.render.resolution_x * scene.render.pixel_aspect_x / max(1, scene.render.resolution_y * scene.render.pixel_aspect_y)
    # Blender centres the camera on the region; keep the frame inside the box around that centre.
    half_w = min(region.width / 2 - box.x, box.right - region.width / 2)
    half_h = min(region.height / 2 - box.y, box.top - region.height / 2)
    target = Rect(region.width / 2 - half_w, region.height / 2 - half_h, 2 * half_w, 2 * half_h).inset(8 * scale())
    want = target.fit_aspect(aspect)
    k = want.w / border.w
    if abs(k - 1.0) > 0.004:
        rv3d.view_camera_zoom = max(-30.0, min(600.0, fac_to_zoom(zoom_to_fac(rv3d.view_camera_zoom) * k)))
        rv3d.view_camera_offset = (0.0, 0.0)
        region.tag_redraw()
    return border


# ===================================================================== drawing

def _ghost_uids(scene):
    sm = scene.stop_motion
    if not sm.ghost_enabled or ops.is_playing():
        return []
    frame = scene.frame_current
    cur = core.shot_index_at(scene, frame)
    earlier = [s.uid for i, s, start, _h in core.shot_spans(scene) if start < frame and i != cur]
    return list(reversed(earlier[-sm.ghost_count:]))


def draw_ghost(p, scene, rect):
    sm = scene.stop_motion
    for depth, uid in enumerate(_ghost_uids(scene)):
        img = core.shot_image(scene, uid)
        if img is not None:
            p.image(rect, img, sm.ghost_opacity * (0.55 ** depth), tint=(0.62, 0.82, 1.0))


def draw_studio():
    ctx = bpy.context
    if not S.active or ctx.area is None or ctx.area.as_pointer() != S.area_ptr:
        return
    if S.painter is None:
        from .studio_paint import GPUPainter
        S.painter = GPUPainter()
        S.kit = Kit(S.painter)
    region = ctx.region
    rv3d = ctx.region_data
    scene = ctx.scene
    try:
        render_captures(ctx)
    except Exception as exc:
        print("Stop Motion: capture failed:", exc)
    s = scale()
    L = studio_layout(region.width, region.height, s, S.chrome)
    S.layout = L
    kit, p, t = S.kit, S.painter, Theme
    kit.begin(s)
    live = L["live"]

    # --- the live view: camera frame, mask round it, ghost
    if rv3d is not None and rv3d.view_perspective == 'CAMERA':
        border = fit_camera(ctx, region, rv3d, live)
        if border is not None:
            for r in (Rect(live.x, live.y, live.w, border.y - live.y),
                      Rect(live.x, border.top, live.w, live.top - border.top),
                      Rect(live.x, border.y, border.x - live.x, border.h),
                      Rect(border.right, border.y, live.right - border.right, border.h)):
                if r.w > 0 and r.h > 0:
                    p.rect(r, t.stage)
            draw_ghost(p, scene, border)
            p.rect_outline(border, t.accent if S.chrome else (0, 0, 0, 0), 0, 2 * s)
    if not S.chrome:
        draw_clean(kit, scene, live, s)
        return

    # --- chrome backgrounds (they cover the 3D view everywhere but the live box)
    for key in ("top", "head_left", "head_centre", "head_right", "left", "right", "footer"):
        p.rect(L[key], t.ground if key in ("left", "right") else t.panel)
    p.rect(Rect(L["top"].x, L["top"].y, L["top"].w, 1 * s), t.line)
    p.rect(Rect(L["footer"].x, L["footer"].top - 1 * s, L["footer"].w, 1 * s), t.line)
    for key in ("head_left", "head_centre", "head_right"):
        p.rect(Rect(L[key].x, L[key].y, L[key].w, 1 * s), t.line)
    p.rect(Rect(L["right"].x, L["right"].y, 1 * s, L["right"].h), t.line)

    draw_top(kit, L["top"], scene, s)
    draw_view_headers(kit, L, scene, s)
    draw_left(kit, L["left"], ctx, scene, s)
    draw_right(kit, L["right"], ctx, scene, s)
    draw_footer(kit, L["footer"], scene, s)
    draw_live_badge(kit, live, scene, s)
    if S.overlay == 'PROJECTS':
        draw_projects(kit, L["full"], s)
    elif S.overlay == 'LIBRARY':
        draw_library(kit, L["full"], ctx, s)
    elif S.overlay == 'SWAPS':
        draw_swap_popup(kit, L["full"], ctx, s)
    draw_toast(kit, L["full"], s)


def draw_clean(kit, scene, live, s):
    """UI hidden: just the shot number, and key hints that fade."""
    t = Theme
    idx = core.shot_index_at(scene, scene.frame_current)
    n = idx + 1 if idx >= 0 else len(scene.stop_motion.shots) + 1
    kit.p.circle(live.x + 24 * s, live.y + 28 * s, 6 * s, t.accent if idx < 0 else t.blue)
    kit.label(Rect(live.x + 36 * s, live.y + 18 * s, 80 * s, 20 * s), str(n), 15, t.text)
    if time.time() < S.hint_until:
        kit.label(Rect(live.x, live.top - 34 * s, live.w, 24 * s),
                  "Enter shoot   ← → shots   Tab swap view   F6 ghost   F5 bring the UI back",
                  12, t.muted, "center")


def draw_toast(kit, full, s):
    text, until = S.toast
    if text and time.time() < until:
        w = kit.text_width(text, 13) + 32 * s
        r = Rect(full.cx - w / 2, full.y + 160 * s, w, 34 * s)
        kit.panel(r, Theme.raised, 10, Theme.line_strong)
        kit.label(r, text, 13, Theme.text, "center")


def draw_top(kit, r, scene, s):
    t = Theme
    x = r.x + 20 * s
    kit.p.circle(x + 15 * s, r.cy, 15 * s, t.accent)
    kit.p.circle(x + 15 * s, r.cy, 6 * s, t.on_accent)
    kit.label(Rect(x + 40 * s, r.y, 220 * s, r.h), "Stop Motion Studio", 17, t.text, "left", True)
    tabs = Rect(x + 230 * s, r.cy - 18 * s, 380 * s, 36 * s)
    kit.panel(tabs, t.ground, 12)
    cells = tabs.inset(4 * s).split_cols(3, 4 * s)
    for (mode, label), cell in zip((('PUPPETS', "Puppets"), ('ANIMATE', "Animate"), ('REVIEW', "Review & export")), cells):
        kit.button("mode:" + mode, cell, label, (lambda m=mode: set_mode(m)), "tab", S.mode == mode)
    # right side
    bx = r.right - 16 * s
    for wid, label, cb, w in (("projects", "Projects", lambda: set_overlay('PROJECTS'), 96),
                              ("save", "Save", save_project, 76),
                              ("library", "Bring in…", lambda: set_overlay('LIBRARY'), 100)):
        bx -= w * s
        kit.button(wid, Rect(bx, r.cy - 17 * s, w * s, 34 * s), label, cb)
        bx -= 8 * s
    name = os.path.splitext(os.path.basename(bpy.data.filepath))[0] if bpy.data.filepath else "Not saved yet"
    state = "" if not bpy.data.is_dirty else " · changes"
    kit.label(Rect(bx - 300 * s, r.y, 290 * s, r.h), name + state, 13, t.muted, "right")


def set_mode(mode):
    S.mode = mode
    if mode == 'PUPPETS' and S.side not in ('PUPPET', 'PROPS'):
        S.side = 'PUPPET'
    if mode == 'REVIEW' and S.live != 'CAMERA':
        swap_views()
    redraw()


def set_overlay(name):
    S.overlay = None if S.overlay == name else name
    redraw()


def draw_view_headers(kit, L, scene, s):
    t = Theme
    hl, hc, hr = L["head_left"], L["head_centre"], L["head_right"]
    other = "FREE VIEW" if S.live == 'CAMERA' else "CAMERA"
    kit.label(Rect(hl.x + 16 * s, hl.y, hl.w, hl.h), other + "  ·  Tab swaps", 12,
              t.blue if S.live == 'CAMERA' else t.accent, "left", True)
    live_name = "● CAMERA  ·  live" if S.live == 'CAMERA' else "FREE VIEW  ·  live"
    kit.label(Rect(hc.x + 16 * s, hc.y, 200 * s, hc.h), live_name, 12,
              t.accent if S.live == 'CAMERA' else t.blue, "left", True)
    # camera setups (right-aligned in the centre header)
    x = hc.right - 12 * s
    area, _r = studio_area()
    moving = area is not None and area.spaces.active.lock_camera
    for wid, label, cb, w, sel in (
            ("cam:new", "", lambda: run(bpy.ops.stop_motion.new_camera) or redraw(), 30, False),
            ("cam:move", "Move camera", toggle_move_camera, 110, moving)):
        x -= w * s
        kit.button(wid, Rect(x, hc.cy - 15 * s, w * s, 30 * s), label, cb, selected=sel,
                   icon="plus" if wid == "cam:new" else None, size=12)
        x -= 6 * s
    for cam in reversed(cameras.cameras(scene)):
        lw = kit.text_width(cam.name, 12) + 40 * s
        x -= lw
        filming = cam == scene.camera
        kit.button("cam:" + cam.name, Rect(x, hc.cy - 15 * s, lw - 22 * s, 30 * s), cam.name,
                   (lambda n=cam.name: use_camera(n)), selected=filming, size=12)
        locked = cameras.is_locked(cam)
        kit.button("lock:" + cam.name, Rect(x + lw - 20 * s, hc.cy - 15 * s, 20 * s, 30 * s), "",
                   (lambda n=cam.name: run(bpy.ops.stop_motion.lock_camera, name=n)), selected=locked,
                   icon="lock" if locked else "unlock")
        x -= 6 * s
        if x < hc.x + 220 * s:
            break
    # side tabs (Review shows the export panel instead)
    if S.mode == 'REVIEW':
        kit.label(Rect(hr.x + 18 * s, hr.y, hr.w, hr.h), "EXPORT", 12, t.soft, "left", True)
        return
    tabs = (('PUPPET', "Puppet"), ('PROPS', "Set"), ('LIGHT', "Light"), ('SCULPT', "Sculpt")) \
        if S.mode != 'PUPPETS' else (('PUPPET', "Set up puppet"), ('PROPS', "Set & props"))
    cells = Rect(hr.x + 10 * s, hr.cy - 16 * s, hr.w - 20 * s, 32 * s).split_cols(len(tabs), 2 * s)
    for (key, label), cell in zip(tabs, cells):
        kit.button("side:" + key, cell, label, (lambda k=key: set_side(k)), "tab", S.side == key, size=12)


def use_camera(name):
    """Header camera buttons: live, the next shots film with it; on a shot, it cuts to it up to the next cut."""
    scene = bpy.context.scene
    before = core.shot_index_at(scene, scene.frame_current)
    run(bpy.ops.stop_motion.use_camera, name=name)
    n = len(scene.stop_motion.shots)
    if before < 0:
        toast("Next shots film with " + name)
    else:
        cams = core.shot_cameras(scene)
        j = before
        while j < n and cams[j] == cams[before]:
            j += 1
        if j - before == 1:
            toast("Shot %d films with %s" % (before + 1, name))
        else:
            toast("Shots %d–%d film with %s" % (before + 1, j, name))
    redraw()


def set_side(k):
    S.side = k
    redraw()


def toggle_move_camera():
    if S.live != 'CAMERA':
        swap_views()
    run(bpy.ops.stop_motion.move_camera)
    redraw()


def draw_left(kit, r, ctx, scene, s):
    t = Theme
    inner = r.inset(16 * s, 14 * s)
    if S.mode == 'REVIEW':
        draw_review_left(kit, inner, scene, s)
        return
    # the other view, as a picture: click swaps, drag turns it (free view), wheel zooms
    aspect = scene.render.resolution_x / max(1, scene.render.resolution_y) if S.live == 'FREE' else 1.0
    pic_box, rest = inner.take_top(min(inner.w / max(0.6, aspect), inner.h * 0.5))
    pic = pic_box.fit_aspect(aspect) if S.live == 'FREE' else pic_box
    kit.panel(pic, t.raised, 0)
    which = 'FREE' if S.live == 'CAMERA' else 'CAMERA'
    if which == 'FREE' and not S.free_init:
        init_free_view(scene)
    try:
        off = render_view(ctx, "picture", pic.w, pic.h, which)
        if off is not None:
            kit.p.texture(pic, off.texture_color)
            if which == 'CAMERA':
                draw_ghost(kit.p, scene, pic)
    except Exception as exc:
        kit.label(pic, "View unavailable", 12, t.muted, "center")
        print("Stop Motion: picture failed:", exc)
    kit.p.rect_outline(pic, t.blue if which == 'FREE' else t.accent, 6 * s, 1 * s)
    kit.area("picture", pic, on_click=swap_views,
             on_drag=(lambda dx, dy: (S.free.orbit(dx, dy), redraw())) if which == 'FREE' else None,
             on_wheel=(lambda st: (S.free.zoom(st), redraw())) if which == 'FREE' else None)
    badge = Rect(pic.right - 58 * s, pic.y + 8 * s, 50 * s, 22 * s)
    kit.panel(badge, t.blue if which == 'FREE' else t.accent, 6)
    kit.label(badge, "⇄ Tab", 11, t.on_accent, "center", True)

    y = rest.top - 14 * s
    kit.label(Rect(rest.x, y - 18 * s, rest.w, 18 * s), "SAVED VIEWS", 11, t.soft, "left", True)
    y -= 26 * s
    views = list(scene.stop_motion_views)
    cells = []
    for i in range(len(views) + 1):
        col = i % 2
        if col == 0:
            y -= 36 * s
        cells.append(Rect(rest.x + col * (rest.w / 2 + 3 * s), y, rest.w / 2 - 3 * s, 32 * s))
    for i, v in enumerate(views[:5]):
        kit.button("view:%d" % i, cells[i], "%d · %s" % (i + 1, v.name), (lambda k=i: go_view(k)), size=12)
    kit.button("view:save", cells[min(len(views), 5)], "+ Save view", save_view, size=12)
    y = cells[min(len(views), 5)].y - 22 * s
    sm = scene.stop_motion
    kit.label(Rect(rest.x, y - 18 * s, rest.w, 18 * s), "GHOST OF LAST SHOT", 11, t.soft, "left", True)
    y -= 46 * s
    kit.slider("ghost", Rect(rest.x + 8 * s, y, rest.w - 70 * s, 24 * s), sm.ghost_opacity,
               lambda v: setattr(sm, "ghost_opacity", v) or redraw())
    kit.toggle("ghost:on", Rect(rest.right - 52 * s, y - 2 * s, 52 * s, 28 * s), "On" if sm.ghost_enabled else "Off",
               sm.ghost_enabled, lambda v: setattr(sm, "ghost_enabled", v) or redraw(), t.blue)
    bottom = Rect(rest.x, rest.y, rest.w, 36 * s)
    a, b = bottom.split_cols(2, 6 * s)
    kit.button("hideui", a, "Hide UI · F5", toggle_chrome, size=12)
    kit.toggle("solid", b, "Solid: " + ("on" if sm.solid_world else "off"), sm.solid_world,
               lambda v: setattr(sm, "solid_world", v) or redraw())
    kit.label(Rect(rest.x, rest.y + 40 * s, rest.w, 16 * s), ESCAPE_HINT, 10, t.muted[:3] + (0.6,))


def go_view(i):
    scene = bpy.context.scene
    views = scene.stop_motion_views
    if not (0 <= i < len(views)):
        return
    area, _r = studio_area()
    if S.live == 'FREE' and area is not None:
        cameras.restore_view(views[i], area.spaces.active.region_3d)
    else:
        v = views[i]
        S.free.location = Vector(v.location)
        S.free.rotation = Quaternion(v.rotation)
        S.free.distance = v.distance
    redraw()


def save_view():
    scene = bpy.context.scene
    area, _r = studio_area()
    v = scene.stop_motion_views.add()
    v.name = ("View %d" % len(scene.stop_motion_views))
    if S.live == 'FREE' and area is not None:
        cameras.store_view(v, area.spaces.active.region_3d)
    else:
        v.location, v.rotation, v.distance, v.ortho = S.free.location, S.free.rotation, S.free.distance, False
    toast("Saved " + v.name)
    redraw()


def toggle_chrome():
    S.chrome = not S.chrome
    S.hint_until = time.time() + 3.0 if not S.chrome else 0.0
    redraw()


def draw_review_left(kit, r, scene, s):
    t = Theme
    sm = scene.stop_motion
    y = r.top
    kit.label(Rect(r.x, y - 24 * s, r.w, 24 * s), "Watch it back", 16, t.text, "left", True)
    y -= 78 * s
    playing = ops.is_playing()
    kit.button("rv:play", Rect(r.x, y, r.w, 44 * s), "Pause" if playing else "Play", play,
               "accent", icon="pause" if playing else "play", size=15)
    y -= 34 * s
    kit.label(Rect(r.x, y, r.w, 18 * s), "SPEED", 11, t.soft, "left", True)
    y -= 38 * s
    kit.segmented("fps", Rect(r.x, y, r.w, 32 * s), [('8', "8 fps"), ('12', "12 fps"), ('24', "24 fps")],
                  sm.fps, lambda v: setattr(sm, "fps", v) or redraw(), size=12)
    y -= 34 * s
    kit.label(Rect(r.x, y, r.w, 18 * s), "PLAY", 11, t.soft, "left", True)
    y -= 38 * s
    kit.segmented("pmode", Rect(r.x, y, r.w, 32 * s), [('LOOP', "Loop"), ('BOUNCE', "Back & forth"), ('LAST', "Last")],
                  sm.play_mode, lambda v: setattr(sm, "play_mode", v) or redraw(), size=12)
    if sm.play_mode == 'LAST':
        y -= 40 * s
        kit.label(Rect(r.x, y, 110 * s, 30 * s), "Last %d shots" % sm.play_last, 12, t.text)
        kit.slider("plast", Rect(r.x + 116 * s, y, r.w - 124 * s, 30 * s), (sm.play_last - 2) / 48.0,
                   lambda v: setattr(sm, "play_last", int(round(2 + v * 48))) or redraw())
    y -= 44 * s
    first, last = ops.play_range(scene)
    total = core.live_frame(scene) - scene.frame_start
    kit.label(Rect(r.x, y, r.w, 18 * s), "%d shots · %.1f s" % (len(sm.shots), total / max(1, scene.render.fps)), 13, t.muted)
    cut_list = core.cuts(scene)
    if len(cut_list) > 1:
        y -= 22 * s
        kit.label(Rect(r.x, y, r.w, 18 * s), "%d camera cuts" % (len(cut_list) - 1), 13, t.yellow)


def play():
    scene = bpy.context.scene
    core.sync_range(scene)
    run(bpy.ops.stop_motion.play)
    redraw()


# ----------------------------------------------------------------- right column

def draw_right(kit, r, ctx, scene, s):
    inner = r.inset(16 * s, 14 * s)
    inner = Rect(inner.x + 1 * s, inner.y, inner.w - 1 * s, inner.h)
    if S.mode == 'REVIEW':
        draw_export(kit, inner, scene, s)
    elif S.side == 'PUPPET':
        (draw_puppet_setup if S.mode == 'PUPPETS' else draw_puppet)(kit, inner, ctx, scene, s)
    elif S.side == 'PROPS':
        draw_props(kit, inner, ctx, scene, s)
    elif S.side == 'LIGHT':
        draw_light(kit, inner, scene, s)
    elif S.side == 'SCULPT':
        draw_sculpt(kit, inner, ctx, scene, s)


class Column:
    """Lays widgets out top to bottom inside a rect."""

    def __init__(self, kit, rect, s):
        self.kit, self.r, self.s = kit, rect, s
        self.y = rect.top

    def row(self, h, gap=8):
        self.y -= h * self.s
        out = Rect(self.r.x, self.y, self.r.w, h * self.s)
        self.y -= gap * self.s
        return out

    def heading(self, text, size=11):
        self.kit.label(self.row(18, 6), text, size, Theme.soft, "left", True)

    def title(self, text):
        self.kit.label(self.row(24, 10), text, 16, Theme.text, "left", True)

    def note(self, text):
        self.kit.label(self.row(16, 8), text, 11, Theme.muted)

    def room(self, h):
        return self.y - h * self.s > self.r.y


def draw_puppet(kit, r, ctx, scene, s):
    col = Column(kit, r, s)
    arm = puppet.puppet_for(ctx)
    ob = ctx.active_object
    if arm is None:
        col.title("No puppet yet")
        if ob is not None and ob.type == 'ARMATURE':
            kit.button("mkpuppet", col.row(40), "Make puppet from " + ob.name,
                       lambda: run(bpy.ops.stop_motion.make_puppet) or redraw(), "accent")
        else:
            col.note("Open the Puppets tab to set one up.")
        return
    pp = arm.stop_motion_puppet
    col.title(arm.name)
    pins = [(i, rg) for i, rg in enumerate(pp.rings) if rg.pin is not None]
    if pins:
        cells = col.row(32).split_cols(len(pins), 6 * s)
        for (i, rg), cell in zip(pins, cells):
            on = puppet.is_pinned(arm, rg)
            kit.toggle("pin:%d" % i, cell, ("Pinned " if on else "Free ") + rg.label.split()[0].lower(), on,
                       (lambda v, k=i: run(bpy.ops.stop_motion.toggle_pin, puppet=arm.name, ring=k) or redraw()))
    for si, sset in enumerate(pp.swap_sets):
        if not col.room(70):
            col.note("More swap sets in the Puppets tab")
            break
        col.heading(sset.name.upper())
        active = puppet.swap_active(sset)
        items = list(sset.items)
        for start in range(0, len(items), 4):
            cells = col.row(40, 5).split_cols(4, 5 * s)
            for k, (cell, it) in enumerate(zip(cells, items[start:start + 4])):
                ii = start + k
                kit.button("swap:%d:%d" % (si, ii), cell, it.label,
                           (lambda a=si, b=ii: run(bpy.ops.stop_motion.swap, puppet=arm.name, set_index=a, item=b) or redraw()),
                           "clay", selected=(ii == active), size=12)
        col.y -= 4 * s
    if not pp.swap_sets:
        col.note("No swap parts found (name them like Mouth_O).")


def draw_puppet_setup(kit, r, ctx, scene, s):
    col = Column(kit, r, s)
    ob = ctx.active_object
    col.title("Set up a puppet")
    if ob is not None and ob.type == 'ARMATURE':
        label = "Set up again" if ob.stop_motion_puppet.enabled else "Make puppet from " + ob.name
        kit.button("mkpuppet", col.row(40), label, lambda: run(bpy.ops.stop_motion.make_puppet) or redraw(), "accent")
    else:
        col.note("Pick the puppet's rig in the live view,")
        col.note("or bring one in from the library.")
    kit.button("lib:fromsetup", col.row(34), "Bring in…", lambda: set_overlay('LIBRARY'))
    arm = puppet.puppet_for(ctx)
    if arm is None:
        return
    pp = arm.stop_motion_puppet
    col.heading("GRAB RINGS (%d)" % len(pp.rings))
    for i, rg in enumerate(pp.rings):
        if not col.room(40):
            break
        row = col.row(30, 4)
        name, minus, plus = Rect(row.x, row.y, row.w - 70 * s, row.h), \
            Rect(row.right - 66 * s, row.y, 30 * s, row.h), Rect(row.right - 32 * s, row.y, 30 * s, row.h)
        kit.label(name, rg.label + ("  · pinned" if rg.pin else ""), 13, Theme.text)
        kit.button("rsm:%d" % i, minus, "−", (lambda g=rg: setattr(g, "size", max(0.2, g.size / 1.2)) or redraw()))
        kit.button("rsp:%d" % i, plus, "+", (lambda g=rg: setattr(g, "size", min(4.0, g.size * 1.2)) or redraw()))
    col.y -= 6 * s
    kit.button("rescan", col.row(34), "Find swap parts again", lambda: run(bpy.ops.stop_motion.rescan_swaps, puppet=arm.name) or redraw())
    col.note("%d swap sets" % len(pp.swap_sets))
    kit.button("unpuppet", col.row(34), "Remove puppet setup", lambda: run(bpy.ops.stop_motion.unpuppet, puppet=arm.name) or redraw(), "danger")


def start_arrange(stamp_from=""):
    from . import arrange
    if arrange.ARR["active"]:
        arrange.ARR["active"] = False
    else:
        run(bpy.ops.stop_motion.arrange, 'INVOKE_DEFAULT', stamp_source=stamp_from)
    redraw()


def draw_props(kit, r, ctx, scene, s):
    from . import arrange
    col = Column(kit, r, s)
    sm = scene.stop_motion
    col.title("Arrange the set")
    on = arrange.ARR["active"]
    stamping = on and arrange.ARR["stamp"]
    ob = ctx.active_object
    a, b = col.row(40).split_cols(2, 6 * s)
    kit.button("arrange", a, "Stop" if on and not stamping else "Arrange",
               lambda: start_arrange(""), "accent" if not on else "ghost", selected=on and not stamping)
    can_stamp = ob is not None and arrange.arrangeable(scene, ob)
    kit.button("stamp", b, "Stop" if stamping else "Stamp copies",
               lambda: start_arrange(ob.name if (ob and not stamping) else ""), selected=bool(stamping),
               enabled=bool(stamping) or can_stamp)
    col.note("Drag along surfaces · wheel spins · Alt leans" if not stamping
             else "Click to place %s · Esc stops" % arrange.ARR["stamp"])
    a, b = col.row(32).split_cols(2, 6 * s)
    kit.toggle("lean", a, "Lean with surface", sm.stick_align, lambda v: setattr(sm, "stick_align", v) or redraw(), Theme.blue)
    if can_stamp:
        kit.toggle("setpiece", b, "Set piece: on" if ob.stop_motion_set else "Set piece: off", ob.stop_motion_set,
                   lambda v: run(bpy.ops.stop_motion.set_piece, on=v) or redraw())
    else:
        kit.button("setpiece", b, "Set piece", lambda: None, enabled=False, size=12)
    col.y -= 8 * s
    col.title("Props")
    kit.button("mkprop", col.row(36), "Make selected a prop", lambda: run(bpy.ops.stop_motion.make_prop) or redraw())
    for p_ob in solid.props(scene):
        if not col.room(80):
            break
        held = solid.held_by(p_ob)
        col.heading(p_ob.name.upper() + ("  · held" if held else ""))
        a, b = col.row(34, 12).split_cols(2, 6 * s)
        if held:
            kit.button("letgo:" + p_ob.name, a, "Let go", lambda n=p_ob.name: run(bpy.ops.stop_motion.let_go, name=n) or redraw())
        else:
            kit.button("hold:" + p_ob.name, a, "Hold in hand", lambda n=p_ob.name: run(bpy.ops.stop_motion.hold_prop, name=n) or redraw())
        kit.button("drop:" + p_ob.name, b, "Drop", lambda n=p_ob.name: run(bpy.ops.stop_motion.drop_prop, name=n) or redraw())
    if not solid.props(scene):
        col.note("Select an object, then Make selected a prop.")


def draw_light(kit, r, scene, s):
    col = Column(kit, r, s)
    col.heading("STUDIO LIGHTS")
    keys = list(lighting.STUDIO.items())
    for start in range(0, len(keys), 2):
        cells = col.row(32, 5).split_cols(2, 5 * s)
        for cell, (k, v) in zip(cells, keys[start:start + 2]):
            kit.button("lp:" + k, cell, v[0], (lambda kk=k: run(bpy.ops.stop_motion.light_preset, preset=kk) or redraw()), size=12)
    col.y -= 6 * s
    col.heading("SKIES & ROOMS")
    keys = list(lighting.HDRI.items())
    for start in range(0, len(keys), 2):
        cells = col.row(32, 5).split_cols(2, 5 * s)
        for cell, (k, v) in zip(cells, keys[start:start + 2]):
            kit.button("hp:" + k, cell, v[0], (lambda kk=k: run(bpy.ops.stop_motion.hdri_preset, preset=kk) or redraw()), size=12)
    kit.button("ownlights", col.row(30), "Use my own lights", lambda: run(bpy.ops.stop_motion.own_lights) or redraw(), size=12)
    idx = shot_index()
    col.heading("KEEP THIS LIGHTING IN" if idx >= 0 else "LIVE: NEXT SHOOT KEEPS IT")
    cells = col.row(32).split_cols(3, 5 * s)
    for cell, (k, label) in zip(cells, (('THIS', "This shot"), ('FROM_HERE', "From here"), ('EVERY', "Every shot"))):
        kit.button("al:" + k, cell, label, (lambda kk=k: run(bpy.ops.stop_motion.apply_light, scope=kk) or redraw()),
                   size=12, enabled=(idx >= 0 or k == 'EVERY'))
    if col.room(90):
        col.heading("EFFECTS FROM THIS SHOT")
        for start in range(0, len(lighting.EFFECTS), 2):
            cells = col.row(32, 5).split_cols(2, 5 * s)
            for cell, (k, label, _d) in zip(cells, lighting.EFFECTS[start:start + 2]):
                kit.button("fx:" + k, cell, label, (lambda kk=k: run(bpy.ops.stop_motion.light_effect, effect=kk, count=6) or redraw()),
                           size=12, enabled=idx >= 0)


def draw_sculpt(kit, r, ctx, scene, s):
    col = Column(kit, r, s)
    if scene.stop_motion_sculpting and ctx.mode == 'SCULPT':
        col.title("Sculpting this shot")
        col.heading("CLAY TOOLS")
        current = sculpt.current_brush(ctx)
        tools = sculpt.CLAY_BRUSHES
        for start in range(0, len(tools), 2):
            cells = col.row(36, 5).split_cols(2, 5 * s)
            for cell, (label, name) in zip(cells, tools[start:start + 2]):
                kit.button("brush:" + name, cell, label,
                           (lambda n=name: run(bpy.ops.stop_motion.clay_brush, brush=n) or redraw()),
                           "clay", selected=(current == name), size=12)
        col.heading("SIZE")
        size = sculpt.brush_size(ctx)
        kit.slider("bsize", col.row(24), (size - 5) / 295.0,
                   lambda v: sculpt.set_brush_size(bpy.context, 5 + v * 295) or redraw())
        col.heading("STRENGTH")
        kit.slider("bstrength", col.row(24), sculpt.brush_strength(ctx),
                   lambda v: sculpt.set_brush_strength(bpy.context, max(0.02, v)) or redraw())
        col.note("Ctrl: the other way (in / deflate). Shift: smooth.")
        kit.button("donesculpt", col.row(40), "Done sculpting", lambda: run(bpy.ops.stop_motion.done_sculpting) or redraw(), "accent")
        return
    col.title("Sculpt a shot")
    idx = shot_index()
    ob = sculpt._target_mesh(ctx)
    if idx < 0:
        col.note("Step back onto a shot to sculpt it.")
    else:
        col.note("Shot %d · %s" % (idx + 1, ob.name if ob else "select a mesh"))
        a, b = col.row(40).split_cols(2, 6 * s)
        kit.button("sculpthere", a, "Sculpt here", lambda: run(bpy.ops.stop_motion.sculpt_shot) or redraw(), "accent", enabled=ob is not None)
        kit.button("sendnomad", b, "Send to Nomad", lambda: run(bpy.ops.stop_motion.send_nomad) or redraw(), enabled=ob is not None)
    if ob is not None:
        order = {sh.uid: i for i, sh in enumerate(scene.stop_motion.shots)}
        for uid in sorted(sculpt.shots_with_sculpt(scene, ob), key=lambda u: order.get(u, 1e9)):
            if not col.room(50):
                break
            n = order.get(uid)
            col.heading("SHOT %s" % (n + 1 if n is not None else "?"))
            a, b, c = col.row(30, 8).split_cols(3, 5 * s)
            kit.button("sk1:" + uid, a, "Just this", (lambda u=uid: run(bpy.ops.stop_motion.sculpt_keep, obj=ob.name, uid=u, keep='ONE_OFF')), size=12)
            kit.button("sk2:" + uid, b, "Carry on", (lambda u=uid: run(bpy.ops.stop_motion.sculpt_keep, obj=ob.name, uid=u, keep='CARRY_ON')), size=12)
            kit.button("skx:" + uid, c, "Remove", (lambda u=uid: run(bpy.ops.stop_motion.remove_sculpt, obj=ob.name, uid=u) or redraw()), "danger", size=12)
    for item in scene.stop_motion_nomad:
        if not col.room(30):
            break
        col.note("%s: %s" % (os.path.basename(item.path), item.status))


def draw_export(kit, r, scene, s):
    col = Column(kit, r, s)
    col.title("Export")
    kinds = (('MOVIE', "Movie (MP4)"), ('FRAMES', "Frames (PNG)"), ('GIF', "GIF"), ('BLEND', "Blender scene"))
    for pair in (kinds[:2], kinds[2:]):
        cells = col.row(48).split_cols(2, 6 * s)
        for cell, (k, label) in zip(cells, pair):
            kit.button("ek:" + k, cell, label, (lambda kk=k: setattr(S, "export_kind", kk) or redraw()), selected=S.export_kind == k)
    if S.export_kind != 'BLEND':
        col.heading("QUALITY")
        cells = col.row(40).split_cols(2, 6 * s)
        for cell, (k, label) in zip(cells, (('AS_SHOT', "As shot"), ('FINAL', "Final render"))):
            kit.button("eq:" + k, cell, label, (lambda kk=k: setattr(S, "export_quality", kk) or redraw()), selected=S.export_quality == k)
        col.note("As shot is quick. Final render uses full lighting.")
    if S.export_kind == 'GIF':
        sm = scene.stop_motion
        bounce = sm.play_mode == 'BOUNCE'
        col.note("Plays back and forth (from Play)" if bounce else "Loops (Play › Back & forth makes it bounce)")
    if S.export_kind == 'BLEND':
        col.note("A copy of the scene: shots are keyframes, cuts are camera markers.")
    label = {'MOVIE': "Make the movie", 'FRAMES': "Save the frames", 'GIF': "Make the GIF",
             'BLEND': "Save the scene"}[S.export_kind]
    kit.button("export", col.row(48), label, do_export, "accent", size=15, enabled=len(scene.stop_motion.shots) > 0)


def do_export():
    scene = bpy.context.scene
    bounce = scene.stop_motion.play_mode == 'BOUNCE'
    r = run(bpy.ops.stop_motion.export, 'EXEC_DEFAULT', kind=S.export_kind, quality=S.export_quality, bounce=bounce)
    if r == {'FINISHED'}:
        toast("Saved in the films folder" if S.export_kind in {'GIF', 'BLEND'} else "Exporting to the films folder")
    redraw()


# ------------------------------------------------------------------ footer

def draw_footer(kit, r, scene, s):
    t = Theme
    sm = scene.stop_motion
    bar, strip = r.inset(16 * s, 12 * s).take_top(52 * s)
    x = bar.x
    kit.button("prev", Rect(x, bar.cy - 22 * s, 44 * s, 44 * s), "", lambda: step('PREV'), icon="prev")
    x += 52 * s
    idx = shot_index()
    label = "Shoot" if idx < 0 else "Replace shot %d" % (idx + 1)
    w = kit.text_width(label, 17) + 80 * s
    kit.button("shoot", Rect(x, bar.cy - 26 * s, w, 52 * s), label, shoot, "accent", icon="rec", size=17)
    x += w + 8 * s
    kit.button("next", Rect(x, bar.cy - 22 * s, 44 * s, 44 * s), "", lambda: step('NEXT'), icon="next")
    x += 62 * s
    kit.label(Rect(x, bar.y, 110 * s, bar.h), "Each shot lasts", 13, t.muted)
    x += 112 * s
    kit.segmented("hold", Rect(x, bar.cy - 17 * s, 250 * s, 34 * s),
                  [('1', "1 frame"), ('2', "2 frames"), ('3', "3 frames")], sm.default_hold,
                  lambda v: setattr(sm, "default_hold", v) or redraw(), size=12)
    x += 262 * s
    if idx >= 0:
        cur = sm.shots[idx]
        for wid, label, cb, w in (("dup", "Duplicate", lambda: run(bpy.ops.stop_motion.duplicate_shot) or redraw(), 96),
                                  ("del", "Delete", lambda: run(bpy.ops.stop_motion.delete_shot) or redraw(), 80),
                                  ("hm", "−", lambda: run(bpy.ops.stop_motion.hold, delta=-1) or redraw(), 34),
                                  ("hp", "+", lambda: run(bpy.ops.stop_motion.hold, delta=1) or redraw(), 34)):
            if wid == "hm":
                kit.label(Rect(x, bar.y, 70 * s, bar.h), "hold %d" % cur.hold, 12, t.muted, "center")
                x += 72 * s
            kit.button(wid, Rect(x, bar.cy - 17 * s, w * s, 34 * s), label, cb, "danger" if wid == "del" else "ghost", size=12)
            x += (w + 6) * s
        kit.button("live", Rect(x + 6 * s, bar.cy - 17 * s, 110 * s, 34 * s), "Back to live", lambda: run(bpy.ops.stop_motion.go_live) or redraw(), size=12)
    playing = ops.is_playing()
    total = core.live_frame(scene) - scene.frame_start
    info = "%d shots · %.1f s" % (len(sm.shots), total / max(1, scene.render.fps))
    iw = kit.text_width(info, 13)
    kit.label(Rect(bar.right - iw, bar.y, iw, bar.h), info, 13, t.muted, "right")
    kit.button("play", Rect(bar.right - iw - 116 * s, bar.cy - 20 * s, 100 * s, 40 * s),
               "Pause" if playing else "Play", play, icon="pause" if playing else "play", size=14)
    draw_strip(kit, strip, scene, s)


def draw_strip(kit, r, scene, s):
    t = Theme
    sm = scene.stop_motion
    p = kit.p
    card_h = r.h
    unit = 30 * s   # width per frame of hold
    spans = core.shot_spans(scene)
    total_w = sum(max(54 * s, h * unit) + 6 * s for _i, _s, _st, h in spans) + 90 * s
    off = kit.scroll.get("strip", None)
    cur = core.shot_index_at(scene, scene.frame_current)
    if off is None or (cur < 0 and total_w > r.w):
        off = max(0.0, total_w - r.w)   # follow the live end
    off = max(0.0, min(off, max(0.0, total_w - r.w)))
    kit.scroll["strip"] = off
    p.clip(r)
    x = r.x - off
    kit.area("strip", r, on_wheel=lambda st: kit.scroll.__setitem__("strip", kit.scroll.get("strip", 0) - st * 60 * s) or redraw())
    cut_list = core.cuts(scene)
    many = len({c for _i, c in cut_list} | {core.live_camera(scene)} - {None}) > 1
    cut_at = dict(cut_list) if many else {}
    for i, shot, start, hold in spans:
        w = max(54 * s, hold * unit)
        card = Rect(x, r.y, w, card_h)
        if card.right >= r.x and card.x <= r.right and i in cut_at:
            # a cut: the film switches camera here
            p.rect(Rect(card.x - 4.5 * s, r.y, 3 * s, card_h), t.yellow, 1.5 * s)
        if card.right >= r.x and card.x <= r.right:
            sel = i == cur
            p.rect(card, t.raised, 7 * s)
            thumb = card.inset(3 * s)
            thumb = Rect(thumb.x, thumb.y + 16 * s, thumb.w, thumb.h - 16 * s)
            img = core.shot_image(scene, shot.uid)
            if img is not None:
                p.image(thumb, img)
            else:
                p.rect(thumb, t.line, 4 * s)
            p.text(Rect(card.x + 6 * s, card.y + 2 * s, w, 14 * s), str(i + 1), 11 * s, t.soft, "left", sel)
            p.text(Rect(card.x, card.y + 2 * s, w - 12 * s, 14 * s), "%df" % hold, 11 * s,
                   t.text if hold != int(sm.default_hold) else t.muted, "right")
            if i in cut_at:
                name = cut_at[i].name
                tw = min(thumb.w - 4 * s, kit.text_width(name, 10) + 10 * s)
                tag = Rect(thumb.x + 2 * s, thumb.y + 2 * s, tw, 14 * s)
                p.rect(tag, t.yellow, 3 * s)
                p.text(tag, name, 10 * s, t.ground, "center", True)
            if sel:
                p.rect_outline(card, t.blue, 7 * s, 2 * s)
            kit.area("shot:%d" % i, card, on_click=(lambda k=i: run(bpy.ops.stop_motion.goto_shot, index=k) or redraw()),
                     on_wheel=lambda st: kit.scroll.__setitem__("strip", kit.scroll.get("strip", 0) - st * 60 * s) or redraw())
            # the right edge is a handle: drag it to hold this shot longer or shorter
            grip = Rect(card.right - 9 * s, card.y, 12 * s, card.h)
            hot = kit.hover == "hold:%d" % i or (kit.drag is not None and kit.drag[0] == "hold:%d" % i)
            tab = Rect(card.right - 8 * s, card.cy - 2 * s, 8 * s, 22 * s)
            p.rect(tab, t.blue if hot else t.panel, 3 * s)
            for gx in (tab.x + 2 * s, tab.x + 5 * s):
                p.rect(Rect(gx, tab.y + 5 * s, 1.2 * s, 12 * s), t.on_accent if hot else t.muted)
            kit.area("hold:%d" % i, grip, on_drag=(lambda dx, dy, k=i: drag_hold(k, dx)))
        x += w + 6 * s
    if kit.drag is None:
        S.hold_drag.clear()
    live = Rect(x, r.y, 80 * s, card_h)
    p.rect_outline(live, t.accent, 7 * s, 2 * s)
    p.text(live, "● LIVE", 11 * s, t.accent, "center", True)
    lc = core.live_camera(scene)
    cams = core.shot_cameras(scene)
    if lc is not None and cams and cams[-1] != lc:
        p.rect(Rect(live.x - 4.5 * s, r.y, 3 * s, card_h), t.yellow, 1.5 * s)
        p.text(Rect(live.x, live.y + 4 * s, live.w, 14 * s), lc.name, 10 * s, t.yellow, "center", True)
    kit.area("strip:live", live, on_click=lambda: run(bpy.ops.stop_motion.go_live) or redraw())
    p.unclip()


def drag_hold(index, dx):
    """Dragging a card's edge: every card-frame-width of drag is one frame of hold."""
    scene = bpy.context.scene
    shots = scene.stop_motion.shots
    if not (0 <= index < len(shots)):
        return
    unit = max(1.0, 30 * scale())
    acc = S.hold_drag.get(index, 0.0) + dx
    while acc >= unit:
        run(bpy.ops.stop_motion.hold, delta=1, index=index)
        acc -= unit
    while acc <= -unit:
        if shots[index].hold > 1:
            run(bpy.ops.stop_motion.hold, delta=-1, index=index)
        acc += unit
    S.hold_drag[index] = acc
    toast("Shot %d holds %d frame%s" % (index + 1, shots[index].hold, "" if shots[index].hold == 1 else "s"), 1.2)
    redraw()


def draw_live_badge(kit, live, scene, s):
    t = Theme
    idx = core.shot_index_at(scene, scene.frame_current)
    if idx >= 0:
        text, col, fg = "POSING OVER  shot %d" % (idx + 1), t.blue, (0.04, 0.13, 0.21, 1)
    else:
        text, col, fg = "● LIVE  shot %d" % (len(scene.stop_motion.shots) + 1), t.accent, t.on_accent
    w = kit.text_width(text, 13) + 20 * s
    r = Rect(live.x + 14 * s, live.y + 12 * s, w, 26 * s)
    kit.panel(r, col, 6)
    kit.label(r, text, 13, fg, "center", True)
    if scene.stop_motion.solid_world and S.live in ('CAMERA', 'FREE'):
        pass


def draw_projects(kit, full, s):
    t = Theme
    kit.area("overlay:shade", full, on_click=lambda: set_overlay('PROJECTS'))
    kit.p.rect(full, (0, 0, 0, 0.55))
    box = Rect(full.cx - 260 * s, full.cy - 220 * s, 520 * s, 440 * s)
    kit.area("overlay:box", box)
    kit.panel(box, t.panel, 14, t.line_strong)
    col = Column(kit, box.inset(24 * s, 20 * s), s)
    col.title("Projects")
    col.note(PROJECTS_DIR)
    kit.button("proj:new", col.row(38), "New project", new_project, "accent")
    for name in list_projects()[:8]:
        kit.button("proj:" + name, col.row(34, 5), os.path.splitext(name)[0], (lambda n=name: open_project(n)))
    if not list_projects():
        col.note("Nothing saved yet. Save puts projects here.")


def lib_items(path):
    try:
        m = os.path.getmtime(path)
    except OSError:
        return []
    hit = S.lib_cache.get(path)
    if hit is None or hit[0] != m:
        hit = (m, library.contents(path))
        S.lib_cache[path] = hit
    return hit[1]


def bring_in(path, item, kind):
    r = run(bpy.ops.stop_motion.bring_in, path=path, item=item, kind=kind)
    if r == {'FINISHED'}:
        S.overlay = None
        label = os.path.splitext(os.path.basename(path))[0] if item == library.WHOLE_FILE else item
        toast("%s is in: %s" % (label, {"PUPPET": "drag its rings to pose it", "PROP": "a prop, drag its green ring",
                                       "SET": "a set piece, arrange it in the Set tab"}[kind if kind != 'AUTO' else 'PROP']))
        if kind == 'PUPPET':
            set_mode('ANIMATE')
    redraw()


def add_selection_to_library():
    ctx = bpy.context
    if not ctx.selected_objects:
        toast("Select something first (click it in the live view)")
        return
    r = run(bpy.ops.stop_motion.add_to_library)
    if r == {'FINISHED'}:
        toast("Saved to the library")
    redraw()


def draw_library(kit, full, ctx, s):
    t = Theme
    kit.area("overlay:shade", full, on_click=lambda: set_overlay('LIBRARY'))
    kit.p.rect(full, (0, 0, 0, 0.55))
    box = Rect(full.cx - 360 * s, full.cy - 250 * s, 720 * s, 500 * s)
    kit.area("overlay:box", box)
    kit.panel(box, t.panel, 14, t.line_strong)
    inner = box.inset(24 * s, 20 * s)
    head, body = inner.take_top(64 * s)
    kit.label(Rect(head.x, head.top - 26 * s, head.w, 26 * s), "Bring in a puppet, prop or set piece", 16, t.text, "left", True)
    kit.label(Rect(head.x, head.top - 50 * s, head.w, 18 * s), library.LIBRARY_DIR, 11, t.muted)
    files = library.list_files()
    left = Rect(body.x, body.y + 52 * s, body.w * 0.42, body.h - 52 * s)
    right = Rect(left.right + 16 * s, body.y + 52 * s, body.right - left.right - 16 * s, body.h - 52 * s)
    col = Column(kit, left, s)
    col.heading("FILES")
    if not files:
        col.note("The library is empty.")
        col.note("Put .blend files of puppets, props and sets")
        col.note("in the folder, or add what's selected.")
    for f in files:
        if not col.room(36):
            col.note("…more in the folder")
            break
        kit.button("lib:" + f, col.row(32, 5), os.path.splitext(f)[0],
                   (lambda n=f: setattr(S, "lib_file", n) or redraw()), "tab", S.lib_file == f, size=12)
    col = Column(kit, right, s)
    if S.lib_file and S.lib_file in files:
        path = os.path.join(library.LIBRARY_DIR, S.lib_file)
        items = lib_items(path)
        col.heading("IN THIS FILE")
        if not items:
            col.note("Nothing to bring in from this file.")
        for name, label in items:
            if not col.room(44):
                break
            row = col.row(34, 6)
            name_r = Rect(row.x, row.y, row.w - 228 * s, row.h)
            kit.label(name_r, label, 13, t.text)
            for k, (kind, text) in enumerate((('PUPPET', "Puppet"), ('PROP', "Prop"), ('SET', "Set"))):
                b = Rect(row.right - (3 - k) * 76 * s, row.y, 72 * s, row.h)
                kit.button("bring:%s:%s:%s" % (S.lib_file, name, kind), b, text,
                           (lambda pth=path, nm=name, kd=kind: bring_in(pth, nm, kd)),
                           "accent" if kind == 'PUPPET' else "ghost", size=12)
        col.note("Puppet: a rig, set up with grab rings. Prop: can be moved and held.")
        col.note("Set: stays put in every shot.")
    else:
        col.heading("PICK A FILE")
        col.note("Its puppets and props are listed here.")
    foot = Rect(body.x, body.y, body.w, 40 * s)
    a, b = foot.split_cols(2, 10 * s)
    kit.button("lib:add", a, "Add what's selected to the library", add_selection_to_library, size=12,
               enabled=bool(ctx.selected_objects))
    kit.button("lib:open", b, "Show the library folder", lambda: run(bpy.ops.stop_motion.open_library), size=12)


def draw_swap_popup(kit, full, ctx, s):
    """D: the swap parts of the puppet you're posing, at the mouse."""
    t = Theme
    arm = puppet.puppet_for(ctx)
    kit.area("overlay:shade", full, on_click=lambda: set_overlay('SWAPS'))
    if arm is None or not arm.stop_motion_puppet.swap_sets:
        r = Rect(S.swap_at[0] - 120 * s, S.swap_at[1] - 20 * s, 240 * s, 40 * s)
        kit.area("overlay:box", r)
        kit.panel(r, t.raised, 10, t.line_strong)
        kit.label(r, "No swap parts on this puppet", 12, t.muted, "center")
        return
    pp = arm.stop_motion_puppet
    h = (24 + sum(24 + 34 * ((len(ss.items) + 3) // 4) for ss in pp.swap_sets)) * s
    w = 360 * s
    x = min(max(full.x + 8 * s, S.swap_at[0] - w / 2), full.right - w - 8 * s)
    y = min(max(full.y + 8 * s, S.swap_at[1] - h / 2), full.top - h - 8 * s)
    box = Rect(x, y, w, h)
    kit.area("overlay:box", box)
    kit.panel(box, t.panel, 12, t.line_strong)
    col = Column(kit, box.inset(14 * s, 12 * s), s)
    for si, sset in enumerate(pp.swap_sets):
        col.heading(sset.name.upper())
        active = puppet.swap_active(sset)
        items = list(sset.items)
        for start in range(0, len(items), 4):
            cells = col.row(30, 4).split_cols(4, 5 * s)
            for k, (cell, it) in enumerate(zip(cells, items[start:start + 4])):
                ii = start + k
                kit.button("pswap:%d:%d" % (si, ii), cell, it.label,
                           (lambda a=si, b=ii: run(bpy.ops.stop_motion.swap, puppet=arm.name, set_index=a, item=b) or redraw()),
                           "clay", selected=(ii == active), size=12)


# ================================================================ studio input

def step(direction):
    run(bpy.ops.stop_motion.step, direction=direction)
    redraw()


def shoot():
    run(bpy.ops.stop_motion.shoot)
    redraw()


class SM_OT_studio_loop(bpy.types.Operator):
    """Runs while the Studio is open: routes input to the Studio's own interface"""
    bl_idname = "stop_motion.studio_loop"
    bl_label = "Stop Motion Studio"

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not S.active:
            return {'FINISHED'}
        area, region = studio_area(context.window)
        if area is None or region is None or S.kit is None:
            return {'PASS_THROUGH'}
        kit = S.kit
        t, v = event.type, event.value
        mx, my = event.mouse_x - region.x, event.mouse_y - region.y
        live = live_rect()
        in_live = live is not None and live.contains(mx, my) and not kit.over_ui(mx, my)

        # the hidden way back to Blender
        if t == 'B' and v == 'PRESS' and event.ctrl and event.alt and event.shift:
            exit_studio(context)
            return {'FINISHED'}

        if t in ALWAYS_PASS:
            return {'PASS_THROUGH'}

        if t in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            if kit.drag is not None:
                kit.on_move(mx, my)
                area.tag_redraw()
                return {'RUNNING_MODAL'}
            if kit.on_move(mx, my):
                area.tag_redraw()
            return {'PASS_THROUGH'}

        if t == 'LEFTMOUSE':
            if v == 'PRESS':
                if kit.on_press(mx, my):
                    area.tag_redraw()
                    return {'RUNNING_MODAL'}
                return {'PASS_THROUGH'} if (in_live and S.overlay is None) else {'RUNNING_MODAL'}
            if v == 'RELEASE':
                if kit.pressed is not None or kit.drag is not None:
                    kit.on_release(mx, my)
                    area.tag_redraw()
                    return {'RUNNING_MODAL'}
                return {'PASS_THROUGH'}
            return {'PASS_THROUGH'} if in_live else {'RUNNING_MODAL'}

        if t in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE'):
            steps = 1 if t == 'WHEELUPMOUSE' else -1
            if kit.on_wheel(mx, my, steps):
                area.tag_redraw()
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'} if self._can_navigate(area, in_live) else {'RUNNING_MODAL'}

        if t in NAV_EVENTS:
            return {'PASS_THROUGH'} if self._can_navigate(area, in_live) else {'RUNNING_MODAL'}

        if t == 'Z' and (event.ctrl or event.oskey):          # undo / redo
            redraw()
            return {'PASS_THROUGH'}

        if v == 'PRESS' and self._hotkey(context, event):
            area.tag_redraw()
            return {'RUNNING_MODAL'}
        if v == 'PRESS' and context.mode == 'SCULPT' and t in ('F', 'LEFT_BRACKET', 'RIGHT_BRACKET'):
            return {'PASS_THROUGH'}  # brush size in sculpt mode
        return {'RUNNING_MODAL'}     # everything else stays out of Blender

    def _can_navigate(self, area, in_live):
        if not in_live or S.overlay is not None:
            return False
        space = area.spaces.active
        # The camera view stays framed; navigating it only moves the camera in Move camera mode.
        return S.live == 'FREE' or space.lock_camera

    def _hotkey(self, context, event):
        t = event.type
        cmd = event.ctrl or event.oskey
        if S.overlay is not None and t == 'ESC':
            S.overlay = None
            return True
        if t in ('RET', 'NUMPAD_ENTER'):
            shoot()
        elif t == 'LEFT_ARROW':
            step('PREV')
        elif t == 'RIGHT_ARROW':
            step('NEXT')
        elif t in ('BACK_SPACE', 'DEL') and (event.alt or t == 'DEL'):
            run(bpy.ops.stop_motion.delete_shot)
        elif t == 'TAB':
            swap_views()
        elif t == 'F5':
            toggle_chrome()
        elif t == 'ESC' and not S.chrome:
            toggle_chrome()
        elif t == 'F6':
            sm = context.scene.stop_motion
            sm.ghost_enabled = not sm.ghost_enabled
        elif t == 'SPACE':
            play()
        elif t == 'S' and cmd:
            save_project()
        elif t == 'D' and not cmd and context.mode != 'SCULPT':
            S.swap_at = (event.mouse_region_x, event.mouse_region_y)
            set_overlay('SWAPS')
        elif t == 'O' and cmd:
            set_overlay('PROJECTS')
        elif t in ('ONE', 'TWO', 'THREE', 'FOUR', 'FIVE') and not cmd:
            go_view(('ONE', 'TWO', 'THREE', 'FOUR', 'FIVE').index(t))
        else:
            return False
        return True


# ================================================================ enter / exit

def _configure_space(space):
    keys = ("show_gizmo", "show_gizmo_navigate", "show_gizmo_tool", "show_gizmo_context",
            "show_gizmo_object_translate", "show_gizmo_object_rotate", "show_gizmo_object_scale")
    saved = {k: getattr(space, k) for k in keys if hasattr(space, k)}
    saved["overlay"] = space.overlay.show_overlays
    saved["shading"] = space.shading.type
    space.show_gizmo = True
    for k in keys[1:]:
        if hasattr(space, k):
            setattr(space, k, False)
    space.overlay.show_overlays = False
    space.shading.type = 'MATERIAL'
    space.shading.use_scene_lights = True
    space.shading.use_scene_world = True
    space.lock_camera = False
    return saved


def enter_studio(context):
    window = context.window
    if window is None or S.active:
        return False
    screen = window.screen
    areas = [a for a in screen.areas if a.type == 'VIEW_3D'] or list(screen.areas)
    area = max(areas, key=lambda a: a.width * a.height)
    if area.type != 'VIEW_3D':
        area.type = 'VIEW_3D'
    region = next(r for r in area.regions if r.type == 'WINDOW')
    S.saved_space = _configure_space(area.spaces.active)
    if not screen.show_fullscreen:
        with context.temp_override(window=window, area=area, region=region):
            bpy.ops.screen.screen_full_area(use_hide_panels=True)
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    S.area_ptr = area.as_pointer()
    rv3d = area.spaces.active.region_3d
    if context.scene.camera is not None:
        rv3d.view_perspective = 'CAMERA'
        S.live = 'CAMERA'
    else:
        S.live = 'FREE'
    init_free_view(context.scene)
    S.active = True
    S.wanted = True
    S.chrome = True
    S.overlay = None
    if not S.went_fullscreen:
        with context.temp_override(window=window):
            bpy.ops.wm.window_fullscreen_toggle()
        S.went_fullscreen = True
    core.capture_hook = queue_capture
    region = next(r for r in area.regions if r.type == 'WINDOW')
    try:
        with context.temp_override(window=window, area=area, region=region):
            started = bpy.ops.stop_motion.studio_loop('INVOKE_DEFAULT')
    except RuntimeError as exc:
        started = {'CANCELLED'}
        print("Stop Motion: the Studio couldn't take over input:", exc)
    if 'RUNNING_MODAL' not in started:
        exit_studio(context)  # never leave Blender half-hidden
        return False
    area.tag_redraw()
    return True


def exit_studio(context):
    window = context.window
    S.active = False
    S.wanted = False
    core.capture_hook = None
    area, region = studio_area(window)
    if area is not None:
        space = area.spaces.active
        saved = S.saved_space or {}
        for k, v in saved.items():
            if k == "overlay":
                space.overlay.show_overlays = v
            elif k == "shading":
                space.shading.type = v
            elif hasattr(space, k):
                setattr(space, k, v)
        if window.screen.show_fullscreen:
            with context.temp_override(window=window, area=area, region=region):
                bpy.ops.screen.screen_full_area(use_hide_panels=True)
    if S.went_fullscreen:
        with context.temp_override(window=window):
            bpy.ops.wm.window_fullscreen_toggle()
        S.went_fullscreen = False
    for off in S.offscreens.values():
        try:
            off.free()
        except Exception:
            pass
    S.offscreens.clear()


class SM_OT_studio(bpy.types.Operator):
    """Open the Stop Motion Studio (Blender hidden). Ctrl+Alt+Shift+B switches back and forth"""
    bl_idname = "stop_motion.studio"
    bl_label = "Open Stop Motion Studio"

    def execute(self, context):
        if S.active:
            exit_studio(context)
            self.report({'INFO'}, "Blender. Ctrl+Alt+Shift+B goes back to the Studio")
        else:
            enter_studio(context)
        return {'FINISHED'}


# ===================================================================== hooks

_handle = None
_keymaps = []


def open_in_first_window():
    """Timers run without a window in the context: give them the first one."""
    wm = bpy.context.window_manager
    if not wm.windows:
        return False
    window = wm.windows[0]
    with bpy.context.temp_override(window=window, screen=window.screen):
        return enter_studio(bpy.context)


def _reenter():
    try:
        if S.wanted and not S.active:
            open_in_first_window()
    except Exception as exc:
        print("Stop Motion: couldn't open the Studio:", exc)
    return None


@persistent
def _on_load(_dummy=None):
    if S.active:
        # the file changed underneath us: the area and the loop are gone
        S.active = False
        S.went_fullscreen = S.went_fullscreen  # window stays full screen across loads
        S.offscreens.clear()
        S.painter = None
    if S.wanted:
        bpy.app.timers.register(_reenter, first_interval=0.2)


classes = (SM_OT_studio_loop, SM_OT_studio)


def register():
    global _handle
    for c in classes:
        bpy.utils.register_class(c)
    _handle = bpy.types.SpaceView3D.draw_handler_add(draw_studio, (), 'WINDOW', 'POST_PIXEL')
    bpy.app.handlers.load_post.append(_on_load)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is not None:
        km = kc.keymaps.new(name="Window", space_type='EMPTY')
        kmi = km.keymap_items.new("stop_motion.studio", 'B', 'PRESS', ctrl=True, alt=True, shift=True)
        _keymaps.append((km, kmi))


def unregister():
    global _handle
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
    S.active = False
    core.capture_hook = None
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
