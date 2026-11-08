# SPDX-License-Identifier: GPL-3.0-or-later
"""The shot strip in normal Blender: cards along the bottom of the camera view.

Click a card to go to that shot (pose over it), click LIVE to go back to the
live camera, drag a card's right edge to hold it longer or shorter. The
Studio draws its own strip; this one is for working in normal Blender.
"""

import bpy
from bpy.props import IntProperty

from . import core
from .studio_kit import Rect, Theme
from .studio_paint import GPUPainter

CARD_H = 64          # pixels at UI scale 1
UNIT = 26            # width per frame of hold
_painter = None
_handle = None
HITS = {}            # region pointer -> [(Rect, kind, index)]


def _scale():
    s = bpy.context.preferences.system.ui_scale
    return s if s > 0.1 else 1.0      # 0 when there's no window


def wanted(context):
    rv3d = context.region_data
    if rv3d is None or rv3d.view_perspective != 'CAMERA':
        return False
    from . import studio
    if studio.is_active():
        return False
    sm = context.scene.stop_motion
    return sm.show_strip and len(sm.shots) > 0


def layout(context, region):
    """[(Rect, kind, index)] for the cards in `region` (kind: CARD, EDGE, LIVE)."""
    scene = context.scene
    s = _scale()
    h = CARD_H * s
    pad = 10 * s
    y = pad
    spans = core.shot_spans(scene)
    widths = [max(46 * s, hold * UNIT * s) for _i, _sh, _st, hold in spans]
    total = sum(w + 5 * s for w in widths) + 70 * s
    avail = region.width - 2 * pad
    cur = core.shot_index_at(scene, scene.frame_current)
    # keep the current shot (or the live end) in view
    focus = sum(w + 5 * s for w in widths[:cur]) if cur >= 0 else total
    off = 0.0 if total <= avail else min(max(0.0, focus - avail * 0.6), total - avail)
    x = pad - off
    out = []
    for (i, _sh, _st, _hold), w in zip(spans, widths):
        card = Rect(x, y, w, h)
        if card.right > 0 and card.x < region.width:
            out.append((card, 'CARD', i))
            out.append((Rect(card.right - 8 * s, card.y, 12 * s, card.h), 'EDGE', i))
        x += w + 5 * s
    out.append((Rect(x, y, 64 * s, h), 'LIVE', -1))
    return out


def draw():
    global _painter
    ctx = bpy.context
    region = ctx.region
    if region is None or not wanted(ctx):
        return
    if _painter is None:
        _painter = GPUPainter()
    p = _painter
    scene = ctx.scene
    s = _scale()
    t = Theme
    items = layout(ctx, region)
    HITS[region.as_pointer()] = items
    cur = core.shot_index_at(scene, scene.frame_current)
    band = Rect(0, 0, region.width, (CARD_H + 20) * s)
    p.rect(band, (0.0, 0.0, 0.0, 0.35))
    cut_at = dict(core.cuts(scene)) if len({c for _i, c in core.cuts(scene)}) > 1 else {}
    spans = core.shot_spans(scene)
    for r, kind, i in items:
        if kind == 'CARD':
            shot, hold = spans[i][1], spans[i][3]
            p.rect(r, t.raised, 6 * s)
            thumb = Rect(r.x + 3 * s, r.y + 16 * s, r.w - 6 * s, r.h - 19 * s)
            img = core.shot_image(scene, shot.uid)
            if img is not None:
                try:
                    p.image(thumb, img)
                except Exception:
                    p.rect(thumb, t.line, 3 * s)
            else:
                p.rect(thumb, t.line, 3 * s)
            p.text(Rect(r.x + 5 * s, r.y + 1 * s, r.w, 14 * s), str(i + 1), 10 * s, t.soft, "left", i == cur)
            p.text(Rect(r.x, r.y + 1 * s, r.w - 10 * s, 14 * s), "%df" % hold, 10 * s, t.muted, "right")
            if i in cut_at:
                p.rect(Rect(r.x - 4 * s, r.y, 2.5 * s, r.h), t.yellow, 1 * s)
            if i == cur:
                p.rect_outline(r, t.blue, 6 * s, 2 * s)
        elif kind == 'EDGE':
            tab = Rect(r.x + 1 * s, r.cy - 9 * s, 6 * s, 18 * s)
            p.rect(tab, t.panel, 2 * s)
        elif kind == 'LIVE':
            p.rect_outline(r, t.accent, 6 * s, 2 * s)
            p.text(r, "● LIVE", 10 * s, t.accent, "center", True)


def hit(context, region, x, y):
    for r, kind, i in reversed(HITS.get(region.as_pointer(), [])):
        if r.contains(x, y):
            return kind, i
    return None


class SM_OT_strip_click(bpy.types.Operator):
    """Shot strip: click a card to go to that shot; drag its right edge to change its hold"""
    bl_idname = "stop_motion.strip_click"
    bl_label = "Shot Strip"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        region = context.region
        if region is None or not wanted(context):
            return {'PASS_THROUGH'}
        h = hit(context, region, event.mouse_region_x, event.mouse_region_y)
        if h is None:
            return {'PASS_THROUGH'}
        kind, i = h
        if kind == 'LIVE':
            bpy.ops.stop_motion.go_live()
        elif kind == 'CARD':
            bpy.ops.stop_motion.goto_shot(index=i)
        else:  # EDGE: drag to hold longer / shorter
            self.index = i
            self.x0 = event.mouse_region_x
            self.done = 0
            context.window_manager.modal_handler_add(self)
            context.window.cursor_modal_set('SCROLL_X')
            return {'RUNNING_MODAL'}
        region.tag_redraw()
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            want = int(round((event.mouse_region_x - self.x0) / (UNIT * _scale())))
            d = want - self.done
            if d:
                hold = context.scene.stop_motion.shots[self.index].hold
                d = max(d, 1 - hold)
                if d:
                    bpy.ops.stop_motion.hold(delta=d, index=self.index)
                    self.done += d
                context.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'ESC'} and event.value in {'RELEASE', 'PRESS'}:
            context.window.cursor_modal_restore()
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


_keymaps = []


def register():
    global _handle
    bpy.utils.register_class(SM_OT_strip_click)
    _handle = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type='VIEW_3D')
        kmi = km.keymap_items.new("stop_motion.strip_click", 'LEFTMOUSE', 'PRESS')
        _keymaps.append((km, kmi))


def unregister():
    global _handle
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
    bpy.utils.unregister_class(SM_OT_strip_click)
