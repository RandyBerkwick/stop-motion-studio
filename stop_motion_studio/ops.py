# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shutil

import bpy
from bpy.props import EnumProperty, IntProperty

from . import core


def _target_index(context, index):
    scene = context.scene
    if index >= 0:
        return index
    return core.shot_index_at(scene, scene.frame_current)


def _set_active(scene, index):
    from . import props
    props._jumping = True
    try:
        scene.stop_motion.active_index = index
    finally:
        props._jumping = False


class SM_OT_shoot(bpy.types.Operator):
    """Take the shot: holds the current pose for the chosen number of frames.
On an earlier shot, this replaces it with the new pose"""
    bl_idname = "stop_motion.shoot"
    bl_label = "Shoot"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        sm = scene.stop_motion
        objs = core.tracked_objects(scene, context, sm.key_scope)
        index = core.shot_index_at(scene, scene.frame_current)

        if index >= 0:  # posing over an existing shot
            shot = sm.shots[index]
            start = core.shot_start(scene, index)
            core.delete_keys_in(scene, start, start + shot.hold)
            core.key_pose(scene, start, objs)
            core.capture(context, scene, shot.uid)
            core.update_ghost(scene)
            self.report({'INFO'}, "Replaced shot %d" % (index + 1))
            return {'FINISHED'}

        frame = core.live_frame(scene)
        cam = core.live_camera(scene)
        shot = sm.shots.add()
        shot.uid = core.new_uid()
        shot.hold = int(sm.default_hold)
        shot.camera = cam
        core.key_pose(scene, frame, objs)
        core.sync_range(scene)
        core.capture(context, scene, shot.uid)
        scene.frame_set(core.live_frame(scene))
        _set_active(scene, len(sm.shots) - 1)
        core.update_ghost(scene)
        return {'FINISHED'}


class SM_OT_delete_shot(bpy.types.Operator):
    """Delete this shot. The shots after it close up the gap"""
    bl_idname = "stop_motion.delete_shot"
    bl_label = "Delete Shot"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return len(context.scene.stop_motion.shots) > 0

    def execute(self, context):
        scene = context.scene
        sm = scene.stop_motion
        i = _target_index(context, self.index)
        if i < 0:
            i = sm.active_index
        if not (0 <= i < len(sm.shots)):
            self.report({'WARNING'}, "No shot here to delete")
            return {'CANCELLED'}
        before = core.snapshot(scene)
        shot = sm.shots[i]
        uid = shot.uid
        start = core.shot_start(scene, i)
        core.delete_keys_in(scene, start, start + shot.hold)
        sm.shots.remove(i)
        core.retime(scene, before)
        core.forget_capture(scene, uid)
        if i < len(sm.shots):
            scene.frame_set(core.shot_start(scene, i))
            _set_active(scene, i)
        else:
            scene.frame_set(core.live_frame(scene))
            _set_active(scene, len(sm.shots) - 1)
        core.update_ghost(scene)
        self.report({'INFO'}, "Shot %d deleted (Ctrl+Z to undo)" % (i + 1))
        return {'FINISHED'}


class SM_OT_hold(bpy.types.Operator):
    """Show this shot for more or fewer frames"""
    bl_idname = "stop_motion.hold"
    bl_label = "Hold"
    bl_options = {'REGISTER', 'UNDO'}

    delta: IntProperty(default=1)
    index: IntProperty(default=-1, options={'SKIP_SAVE'})

    def execute(self, context):
        scene = context.scene
        sm = scene.stop_motion
        i = _target_index(context, self.index)
        if i < 0:
            i = sm.active_index
        if not (0 <= i < len(sm.shots)):
            return {'CANCELLED'}
        before = core.snapshot(scene)
        sm.shots[i].hold = max(1, sm.shots[i].hold + self.delta)
        core.retime(scene, before)
        scene.frame_set(core.shot_start(scene, i))
        return {'FINISHED'}


class SM_OT_duplicate_shot(bpy.types.Operator):
    """Copy this shot and put the copy straight after it, ready to pose over"""
    bl_idname = "stop_motion.duplicate_shot"
    bl_label = "Duplicate Shot"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1, options={'SKIP_SAVE'})

    def execute(self, context):
        scene = context.scene
        sm = scene.stop_motion
        i = _target_index(context, self.index)
        if i < 0:
            i = sm.active_index
        if not (0 <= i < len(sm.shots)):
            return {'CANCELLED'}
        before = core.snapshot(scene)
        src = sm.shots[i]
        src_uid, hold = src.uid, src.hold
        new = sm.shots.add()
        new.uid = core.new_uid()
        new.hold = hold
        new.camera = core.shot_cameras(scene)[i]
        sm.shots.move(len(sm.shots) - 1, i + 1)
        core.retime(scene, before)
        # Evaluate the source pose, then key it into the new slot.
        scene.frame_set(core.shot_start(scene, i))
        dst = core.shot_start(scene, i + 1)
        core.key_pose(scene, dst, core.tracked_objects(scene, context, sm.key_scope))
        try:
            shutil.copyfile(core.capture_path(scene, src_uid), core.capture_path(scene, new.uid))
        except OSError:
            pass
        scene.frame_set(dst)
        _set_active(scene, i + 1)
        core.update_ghost(scene)
        return {'FINISHED'}


class SM_OT_goto_shot(bpy.types.Operator):
    """Jump to a shot to look at it or pose over it"""
    bl_idname = "stop_motion.goto_shot"
    bl_label = "Go to Shot"

    index: IntProperty(default=0)

    def execute(self, context):
        scene = context.scene
        if 0 <= self.index < len(scene.stop_motion.shots):
            scene.frame_set(core.shot_start(scene, self.index))
            _set_active(scene, self.index)
        return {'FINISHED'}


class SM_OT_step(bpy.types.Operator):
    """Step to the previous or next shot"""
    bl_idname = "stop_motion.step"
    bl_label = "Step Shot"

    direction: EnumProperty(items=[('PREV', "Previous", ""), ('NEXT', "Next", "")])

    def execute(self, context):
        scene = context.scene
        n = len(scene.stop_motion.shots)
        cur = core.shot_index_at(scene, scene.frame_current)
        if cur < 0:
            cur = n  # live
        tgt = cur - 1 if self.direction == 'PREV' else cur + 1
        if tgt >= n:
            scene.frame_set(core.live_frame(scene))
            _set_active(scene, n - 1)
        elif tgt >= 0:
            scene.frame_set(core.shot_start(scene, tgt))
            _set_active(scene, tgt)
        return {'FINISHED'}


class SM_OT_go_live(bpy.types.Operator):
    """Back to the live camera, ready for the next shot"""
    bl_idname = "stop_motion.go_live"
    bl_label = "Back to Live"

    def execute(self, context):
        scene = context.scene
        scene.frame_set(core.live_frame(scene))
        _set_active(scene, len(scene.stop_motion.shots) - 1)
        return {'FINISHED'}


class SM_OT_toggle_ghost(bpy.types.Operator):
    """Ghost of the last shot on or off"""
    bl_idname = "stop_motion.toggle_ghost"
    bl_label = "Toggle Ghost"

    def execute(self, context):
        sm = context.scene.stop_motion
        sm.ghost_enabled = not sm.ghost_enabled
        return {'FINISHED'}


class SM_OT_play(bpy.types.Operator):
    """Play the shots in a loop"""
    bl_idname = "stop_motion.play"
    bl_label = "Play"

    def execute(self, context):
        scene = context.scene
        core.sync_range(scene)
        if not context.screen.is_animation_playing:
            if scene.frame_current >= scene.frame_end:
                scene.frame_set(scene.frame_start)
        bpy.ops.screen.animation_play()
        return {'FINISHED'}


class SM_OT_export(bpy.types.Operator):
    """Make a movie or a set of frames from the shots"""
    bl_idname = "stop_motion.export"
    bl_label = "Export"

    kind: EnumProperty(items=[('MOVIE', "Movie (MP4)", ""), ('FRAMES', "Frames (PNG)", "")],
                       default='MOVIE')
    quality: EnumProperty(items=[('AS_SHOT', "As shot", "Quick: like the camera view"),
                                 ('FINAL', "Final render", "Full lighting, takes longer")],
                          default='AS_SHOT')

    @classmethod
    def poll(cls, context):
        return len(context.scene.stop_motion.shots) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        r = scene.render
        core.sync_range(scene)
        base = os.path.splitext(bpy.path.basename(bpy.data.filepath))[0] or "stop_motion"
        out_dir = bpy.path.abspath("//films/") if bpy.data.filepath else os.path.join(core.capture_dir(scene), "films")
        os.makedirs(out_dir, exist_ok=True)
        if self.kind == 'MOVIE':
            r.image_settings.file_format = 'FFMPEG'
            r.ffmpeg.format = 'MPEG4'
            r.ffmpeg.codec = 'H264'
            r.filepath = os.path.join(out_dir, base + "_")
        else:
            r.image_settings.file_format = 'PNG'
            r.filepath = os.path.join(out_dir, base + "_frames", "frame_")
        if self.quality == 'AS_SHOT':
            area, region = core.find_camera_area(context.screen)
            if area is not None:
                with context.temp_override(area=area, region=region):
                    bpy.ops.render.opengl('INVOKE_DEFAULT', animation=True, view_context=True)
            else:
                bpy.ops.render.opengl('INVOKE_DEFAULT', animation=True, view_context=False)
        else:
            bpy.ops.render.render('INVOKE_DEFAULT', animation=True)
        self.report({'INFO'}, "Saving to " + out_dir)
        return {'FINISHED'}


classes = (SM_OT_shoot, SM_OT_delete_shot, SM_OT_hold, SM_OT_duplicate_shot,
           SM_OT_goto_shot, SM_OT_step, SM_OT_go_live, SM_OT_toggle_ghost,
           SM_OT_play, SM_OT_export)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
