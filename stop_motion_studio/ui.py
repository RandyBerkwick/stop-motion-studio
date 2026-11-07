# SPDX-License-Identifier: GPL-3.0-or-later
import blf
import bpy
from bpy.app.handlers import persistent

from . import core

CATEGORY = "Stop Motion"


# ------------------------------------------------------------------ shot list

class SM_UL_shots(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        scene = context.scene
        icon_id = core.shot_icon(scene, item.uid)
        if self.layout_type == 'GRID':
            col = layout.column(align=True)
            if icon_id:
                col.template_icon(icon_value=icon_id, scale=3.0)
            col.label(text="%d" % (index + 1) + ("  ×%d" % item.hold if item.hold != 2 else ""))
        else:
            row = layout.row(align=True)
            if icon_id:
                row.label(text="Shot %d" % (index + 1), icon_value=icon_id)
            else:
                row.label(text="Shot %d" % (index + 1), icon='RENDER_STILL')
            row.label(text="%d frames" % item.hold)


# --------------------------------------------------------------------- panels

class SM_PT_shoot(bpy.types.Panel):
    bl_label = "Shoot"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 0

    def draw(self, context):
        scene = context.scene
        sm = scene.stop_motion
        layout = self.layout

        if scene.camera is None:
            layout.label(text="Add a camera to start filming", icon='ERROR')
        if bpy.data.workspaces.get("Stop Motion") is None or context.workspace.name != "Stop Motion":
            layout.operator("stop_motion.setup_workspace", icon='WORKSPACE')

        idx = core.shot_index_at(scene, scene.frame_current)
        box = layout.box()
        if idx >= 0:
            box.label(text="Posing over shot %d" % (idx + 1), icon='GHOST_ENABLED')
            label = "Replace shot %d" % (idx + 1)
        else:
            box.label(text="LIVE · next is shot %d" % (len(sm.shots) + 1), icon='RADIOBUT_ON')
            label = "Shoot"
        row = box.row(align=True)
        row.scale_y = 1.4
        row.operator("stop_motion.step", text="", icon='TRIA_LEFT').direction = 'PREV'
        big = row.row(align=True)
        big.scale_x = 3.0
        big.operator("stop_motion.shoot", text=label, icon='REC')
        row.operator("stop_motion.step", text="", icon='TRIA_RIGHT').direction = 'NEXT'
        if idx >= 0:
            box.operator("stop_motion.go_live", icon='LOOP_FORWARDS')

        layout.label(text="Each shot lasts")
        layout.row().prop(sm, "default_hold", expand=True)

        row = layout.row(align=True)
        row.prop(sm, "ghost_enabled", text="Ghost", toggle=True, icon='GHOST_ENABLED')
        sub = row.row(align=True)
        sub.active = sm.ghost_enabled
        sub.prop(sm, "ghost_opacity", text="")
        sub.prop(sm, "ghost_count", text="")


class SM_PT_shots(bpy.types.Panel):
    bl_label = "Shots"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 1

    def draw(self, context):
        scene = context.scene
        sm = scene.stop_motion
        layout = self.layout
        total = core.live_frame(scene) - scene.frame_start
        layout.label(text="%d shots · %.1f s" % (len(sm.shots), total / max(1, scene.render.fps)))
        layout.template_list("SM_UL_shots", "", sm, "shots", sm, "active_index",
                             type='GRID', columns=4, rows=3)
        idx = core.shot_index_at(scene, scene.frame_current)
        if idx < 0:
            return
        shot = sm.shots[idx]
        box = layout.box()
        box.label(text="Shot %d" % (idx + 1))
        row = box.row(align=True)
        row.operator("stop_motion.hold", text="", icon='REMOVE').delta = -1
        row.label(text="Hold %d frames" % shot.hold)
        row.operator("stop_motion.hold", text="", icon='ADD').delta = 1
        row = box.row(align=True)
        row.operator("stop_motion.duplicate_shot", icon='DUPLICATE')
        row.operator("stop_motion.delete_shot", icon='TRASH')


class SM_PT_review(bpy.types.Panel):
    bl_label = "Review & Export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 2

    def draw(self, context):
        sm = context.scene.stop_motion
        layout = self.layout
        row = layout.row(align=True)
        playing = context.screen.is_animation_playing
        row.operator("stop_motion.play", text="Pause" if playing else "Play",
                     icon='PAUSE' if playing else 'PLAY')
        row.prop(sm, "fps", text="")
        row = layout.row(align=True)
        op = row.operator("stop_motion.export", text="Movie", icon='FILE_MOVIE')
        op.kind = 'MOVIE'
        op = row.operator("stop_motion.export", text="Frames", icon='IMAGE_DATA')
        op.kind = 'FRAMES'


class SM_PT_view(bpy.types.Panel):
    bl_label = "View"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        sm = context.scene.stop_motion
        layout = self.layout
        layout.operator("stop_motion.toggle_ui", text="Hide UI (F5)", icon='HIDE_ON')
        layout.operator("stop_motion.focus_camera", text="Camera only (Shift F5)", icon='FULLSCREEN_ENTER')
        layout.prop(sm, "key_scope")
        layout.prop(sm, "show_hud")
        layout.prop(sm, "capture_dir")
        if not bpy.data.filepath:
            layout.label(text="Save your file to keep shot pictures", icon='INFO')


# ------------------------------------------------------------- HUD on camera

_hud = None


def draw_hud():
    ctx = bpy.context
    rv3d = ctx.region_data
    scene = ctx.scene
    if rv3d is None or rv3d.view_perspective != 'CAMERA' or not scene.stop_motion.show_hud:
        return
    idx = core.shot_index_at(scene, scene.frame_current)
    ui = ctx.preferences.system.ui_scale
    font = 0
    blf.size(font, 15 * ui)
    blf.enable(font, blf.SHADOW)
    blf.shadow(font, 3, 0.0, 0.0, 0.0, 0.9)
    blf.shadow_offset(font, 1, -1)
    x, y = 16 * ui, 16 * ui
    if idx >= 0:
        blf.color(font, 0.49, 0.77, 1.0, 1.0)
        text = "POSING OVER  shot %d" % (idx + 1)
    else:
        blf.color(font, 1.0, 0.42, 0.24, 1.0)
        text = "●  LIVE  shot %d" % (len(scene.stop_motion.shots) + 1)
    blf.position(font, x, y, 0)
    blf.draw(font, text)
    blf.disable(font, blf.SHADOW)


# ------------------------------------------------------------------ handlers

@persistent
def on_frame_change(scene, _depsgraph=None):
    screen = bpy.context.screen
    if screen is not None and screen.is_animation_playing:
        return
    if bpy.app.is_job_running('RENDER'):
        return
    core.update_ghost(scene)


# -------------------------------------------------------------------- keymap

_keymaps = []


def _register_keys():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="3D View", space_type='VIEW_3D')
    for args, op, props in (
        (dict(type='RET', value='PRESS'), "stop_motion.shoot", {}),
        (dict(type='NUMPAD_ENTER', value='PRESS'), "stop_motion.shoot", {}),
        (dict(type='BACK_SPACE', value='PRESS', alt=True), "stop_motion.delete_shot", {}),
        (dict(type='LEFT_ARROW', value='PRESS'), "stop_motion.step", {"direction": 'PREV'}),
        (dict(type='RIGHT_ARROW', value='PRESS'), "stop_motion.step", {"direction": 'NEXT'}),
        (dict(type='F5', value='PRESS'), "stop_motion.toggle_ui", {}),
        (dict(type='F5', value='PRESS', shift=True), "stop_motion.focus_camera", {}),
        (dict(type='F6', value='PRESS'), "stop_motion.toggle_ghost", {}),
    ):
        kmi = km.keymap_items.new(op, **args)
        for k, v in props.items():
            setattr(kmi.properties, k, v)
        _keymaps.append((km, kmi))


classes = (SM_UL_shots, SM_PT_shoot, SM_PT_shots, SM_PT_review, SM_PT_view)


def register():
    global _hud
    for c in classes:
        bpy.utils.register_class(c)
    _hud = bpy.types.SpaceView3D.draw_handler_add(draw_hud, (), 'WINDOW', 'POST_PIXEL')
    bpy.app.handlers.frame_change_post.append(on_frame_change)
    _register_keys()


def unregister():
    global _hud
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    if on_frame_change in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(on_frame_change)
    if _hud is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_hud, 'WINDOW')
        _hud = None
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
