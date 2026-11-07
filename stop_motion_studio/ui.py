# SPDX-License-Identifier: GPL-3.0-or-later
import os

import blf
import bpy
from bpy.app.handlers import persistent

from . import cameras, core, lighting, puppet, sculpt, solid

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


def draw_swaps(layout, arm):
    for si, sset in enumerate(arm.stop_motion_puppet.swap_sets):
        layout.label(text=sset.name)
        active = puppet.swap_active(sset)
        grid = layout.grid_flow(row_major=True, columns=4, even_columns=True, align=True)
        for ii, it in enumerate(sset.items):
            op = grid.operator("stop_motion.swap", text=it.label, depress=(ii == active))
            op.puppet = arm.name
            op.set_index = si
            op.item = ii


class SM_PT_puppet(bpy.types.Panel):
    bl_label = "Puppet"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        ob = context.active_object
        arm = puppet.puppet_for(context)
        if ob is not None and ob.type == 'ARMATURE' and not ob.stop_motion_puppet.enabled:
            layout.operator("stop_motion.make_puppet", icon='ARMATURE_DATA')
        if arm is None:
            if ob is None or ob.type != 'ARMATURE':
                layout.label(text="Select a rig, then Make Puppet", icon='INFO')
            return
        pp = arm.stop_motion_puppet
        layout.label(text=arm.name, icon='OUTLINER_OB_ARMATURE')

        pins = [(i, r) for i, r in enumerate(pp.rings) if r.pin is not None]
        if pins:
            row = layout.row(align=True)
            for i, r in pins:
                on = puppet.is_pinned(arm, r)
                op = row.operator("stop_motion.toggle_pin", text="Pin " + r.label.lower(),
                                  icon='PINNED' if on else 'UNPINNED', depress=on)
                op.puppet = arm.name
                op.ring = i

        if pp.swap_sets:
            draw_swaps(layout, arm)
        else:
            layout.label(text="No swap parts found", icon='INFO')
        row = layout.row(align=True)
        row.operator("stop_motion.rescan_swaps", icon='FILE_REFRESH').puppet = arm.name

        box = layout.box()
        box.label(text="Grab rings (drag; Alt+drag twists)")
        for r in pp.rings:
            row = box.row(align=True)
            row.prop(r, "label", text="")
            row.prop(r, "size", text="")
        layout.operator("stop_motion.unpuppet", icon='X').puppet = arm.name


class SM_PT_swap_popup(bpy.types.Panel):
    bl_label = "Swap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 14

    def draw(self, context):
        arm = puppet.puppet_for(context)
        if arm is None or not arm.stop_motion_puppet.swap_sets:
            self.layout.label(text="No swap parts on this puppet")
            return
        self.layout.label(text=arm.name)
        draw_swaps(self.layout, arm)


class SM_PT_props(bpy.types.Panel):
    bl_label = "Props & Solid World"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 2

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.prop(scene.stop_motion, "solid_world", toggle=True,
                    icon='MOD_PHYSICS' if scene.stop_motion.solid_world else 'GHOST_DISABLED')
        if scene.stop_motion.solid_world:
            layout.label(text="Dragged parts stop at surfaces · Ctrl passes through")
        ob = context.active_object
        if ob is not None and ob.type == 'MESH':
            row = layout.row(align=True)
            row.prop(ob, "stop_motion_solid", text="%s is solid" % ob.name)
        layout.operator("stop_motion.make_prop", text="Make Selected a Prop", icon='OBJECT_DATA')
        for p in solid.props(scene):
            box = layout.box()
            row = box.row(align=True)
            held = solid.held_by(p)
            row.label(text=p.name, icon='HAND' if held else 'OBJECT_DATA')
            row.operator("stop_motion.unprop", text="", icon='X').name = p.name
            row = box.row(align=True)
            if held:
                row.operator("stop_motion.let_go", icon='UNLINKED').name = p.name
            else:
                row.operator("stop_motion.hold_prop", text="Hold in hand", icon='LINKED').name = p.name
                row.operator("stop_motion.drop_prop", text="Drop", icon='SORT_ASC').name = p.name
            box.prop(p, "stop_motion_falls")


class SM_PT_cameras(bpy.types.Panel):
    bl_label = "Cameras & Views"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        col = layout.column(align=True)
        for cam in cameras.cameras(scene):
            row = col.row(align=True)
            filming = cam == scene.camera
            row.operator("stop_motion.use_camera", text="",
                         icon='RADIOBUT_ON' if filming else 'RADIOBUT_OFF',
                         depress=filming).name = cam.name
            row.prop(cam, "name", text="")
            locked = cameras.is_locked(cam)
            row.operator("stop_motion.lock_camera", text="",
                         icon='LOCKED' if locked else 'UNLOCKED', depress=locked).name = cam.name
        row = layout.row(align=True)
        row.operator("stop_motion.new_camera", text="New from free view", icon='ADD')
        area, _r = core.find_camera_area(context.screen)
        moving = area is not None and area.spaces.active.lock_camera
        row.operator("stop_motion.move_camera", text="Move camera", icon='VIEW_CAMERA', depress=moving)

        layout.label(text="Saved free views")
        col = layout.column(align=True)
        for i, v in enumerate(scene.stop_motion_views):
            row = col.row(align=True)
            row.operator("stop_motion.go_view", text="", icon='HIDE_OFF').index = i
            row.prop(v, "name", text="")
            row.operator("stop_motion.forget_view", text="", icon='X').index = i
        layout.operator("stop_motion.save_view", icon='BOOKMARKS')


class SM_PT_lighting(bpy.types.Panel):
    bl_label = "Lighting"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        wm = context.window_manager
        layout = self.layout
        layout.label(text="Studio lights")
        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for key, (label, _l, _w, _s) in lighting.STUDIO.items():
            grid.operator("stop_motion.light_preset", text=label).preset = key
        layout.label(text="HDRI skies & rooms")
        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for key, (label, _f, _s) in lighting.HDRI.items():
            grid.operator("stop_motion.hdri_preset", text=label).preset = key
        row = layout.row(align=True)
        row.operator("stop_motion.load_hdri", icon='FILE_IMAGE')
        row.operator("stop_motion.own_lights", icon='LIGHT')
        turn = lighting.hdri_turn_socket(scene)
        bg = lighting.world_background(scene)
        if bg is not None:
            row = layout.row(align=True)
            row.prop(bg.inputs["Strength"], "default_value", text="Sky strength")
            if turn is not None and bg.inputs["Color"].is_linked:
                row.prop(turn, "default_value", index=2, text="Turn")

        lights = [o for o in scene.objects if o.type == 'LIGHT' and o.visible_get()]
        if lights:
            box = layout.box()
            for ob in lights:
                row = box.row(align=True)
                row.label(text=ob.name, icon='LIGHT_%s' % ob.data.type)
                row.prop(ob.data, "energy", text="")
                row.prop(ob.data, "color", text="")
        idx = core.shot_index_at(scene, scene.frame_current)
        layout.label(text="Keep this lighting in" + ("" if idx >= 0 else " (live: next Shoot keeps it)"))
        row = layout.row(align=True)
        row.enabled = idx >= 0
        row.operator("stop_motion.apply_light", text="This shot").scope = 'THIS'
        row.operator("stop_motion.apply_light", text="From here on").scope = 'FROM_HERE'
        layout.operator("stop_motion.apply_light", text="Every shot").scope = 'EVERY'

        layout.label(text="Light effects (from this shot)")
        layout.prop(wm, "stop_motion_effect_count")
        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        grid.enabled = idx >= 0
        for key, label, _d in lighting.EFFECTS:
            op = grid.operator("stop_motion.light_effect", text=label)
            op.effect = key
            op.count = wm.stop_motion_effect_count


class SM_PT_sculpt(bpy.types.Panel):
    bl_label = "Sculpt a Shot"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        if scene.stop_motion_sculpting and context.mode == 'SCULPT':
            obj, uid = scene.stop_motion_sculpting.split("|", 1)
            layout.label(text="Sculpting: only this shot changes", icon='SCULPTMODE_HLT')
            layout.operator("stop_motion.done_sculpting", icon='CHECKMARK')
            return
        idx = core.shot_index_at(scene, scene.frame_current)
        ob = sculpt._target_mesh(context)
        if idx < 0:
            layout.label(text="Step onto a shot to sculpt it", icon='INFO')
        else:
            layout.label(text="Shot %d · %s" % (idx + 1, ob.name if ob else "select a mesh"))
            row = layout.row(align=True)
            row.enabled = ob is not None
            row.operator("stop_motion.sculpt_shot", text="Sculpt here", icon='SCULPTMODE_HLT')
            row.operator("stop_motion.send_nomad", text="Send to Nomad", icon='EXPORT')
        if ob is not None:
            done = sculpt.shots_with_sculpt(scene, ob)
            if done:
                box = layout.box()
                box.label(text="Sculpted shots on " + ob.name)
                order = {s.uid: i for i, s in enumerate(scene.stop_motion.shots)}
                for uid in sorted(done, key=lambda u: order.get(u, 1e9)):
                    row = box.row(align=True)
                    n = order.get(uid)
                    row.operator("stop_motion.goto_shot", text="Shot %s" % (n + 1 if n is not None else "?"),
                                 icon='SCULPTMODE_HLT').index = n if n is not None else 0
                    for key, label in (('ONE_OFF', "Just this"), ('CARRY_ON', "Carry on")):
                        op = row.operator("stop_motion.sculpt_keep", text=label)
                        op.obj, op.uid, op.keep = ob.name, uid, key
                    op = row.operator("stop_motion.sculpt_to_swap", text="", icon='FILE_NEW')
                    op.obj, op.uid = ob.name, uid
                    op = row.operator("stop_motion.remove_sculpt", text="", icon='X')
                    op.obj, op.uid = ob.name, uid
        sends = scene.stop_motion_nomad
        layout.separator()
        layout.label(text="Nomad Sculpt bridge")
        layout.prop(scene, "stop_motion_nomad_dir", text="")
        layout.operator("stop_motion.open_bridge", icon='FILEBROWSER')
        for i, item in enumerate(sends):
            row = layout.row(align=True)
            row.label(text="%s: %s" % (os.path.basename(item.path), item.status),
                      icon='TIME' if item.status.startswith("Waiting") else 'CHECKMARK')
            row.operator("stop_motion.nomad_back", text="", icon='IMPORT').index = i
            row.operator("stop_motion.nomad_forget", text="", icon='X').index = i


class SM_PT_shots(bpy.types.Panel):
    bl_label = "Shots"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_order = 6

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
    bl_order = 7

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
    bl_order = 8
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
        (dict(type='D', value='PRESS'), "wm.call_panel", {"name": "SM_PT_swap_popup", "keep_open": True}),
    ):
        kmi = km.keymap_items.new(op, **args)
        for k, v in props.items():
            setattr(kmi.properties, k, v)
        _keymaps.append((km, kmi))


classes = (SM_UL_shots, SM_PT_shoot, SM_PT_puppet, SM_PT_swap_popup, SM_PT_props, SM_PT_cameras, SM_PT_lighting, SM_PT_sculpt,
           SM_PT_shots, SM_PT_review, SM_PT_view)


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
