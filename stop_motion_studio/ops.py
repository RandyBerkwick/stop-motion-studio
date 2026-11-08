# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shutil

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty

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
        if PLAYER["on"]:
            stop_playing(scene, back_to_live=False)
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


# ------------------------------------------------------------------ playback
# Our own player (a timer), because Blender's can't play back and forth.

PLAYER = {"on": False, "dir": 1, "start": 1, "end": 1, "scene": None, "back_to": None}


def play_range(scene):
    """(first, last) frame to play for the chosen review mode."""
    sm = scene.stop_motion
    last = core.live_frame(scene) - 1
    first = scene.frame_start
    if sm.play_mode == 'LAST' and len(sm.shots) > sm.play_last:
        first = core.shot_start(scene, len(sm.shots) - sm.play_last)
    return first, max(first, last)


def is_playing(context=None):
    if PLAYER["on"]:
        return True
    screen = getattr(context or bpy.context, "screen", None)
    return bool(screen and screen.is_animation_playing)


def _tick():
    if not PLAYER["on"]:
        return None
    scene = PLAYER["scene"]
    try:
        sm = scene.stop_motion
    except (ReferenceError, AttributeError):
        PLAYER["on"] = False
        return None
    first, last = play_range(scene)
    f = scene.frame_current + PLAYER["dir"]
    if sm.play_mode == 'BOUNCE':
        if f > last:
            PLAYER["dir"] = -1
            f = max(first, last - 1)
        elif f < first:
            PLAYER["dir"] = 1
            f = min(last, first + 1)
    elif f > last or f < first:
        f = first
    scene.frame_set(f)
    _redraw_all()
    return 1.0 / max(1.0, scene.render.fps / scene.render.fps_base)


def _redraw_all():
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", ()):
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def start_playing(scene):
    core.sync_range(scene)
    first, last = play_range(scene)
    PLAYER.update(on=True, dir=1, scene=scene, back_to=scene.frame_current)
    if not (first <= scene.frame_current <= last) or scene.frame_current >= last:
        scene.frame_set(first)
    core.update_ghost(scene)          # the ghost is hidden while playing
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.0)


def stop_playing(scene=None, back_to_live=True):
    was = PLAYER["on"]
    PLAYER["on"] = False
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    scene = scene or PLAYER["scene"]
    if was and scene is not None:
        try:
            if back_to_live:
                scene.frame_set(core.live_frame(scene))
            core.update_ghost(scene)
        except ReferenceError:
            pass
    _redraw_all()


class SM_OT_play(bpy.types.Operator):
    """Play the shots (loop, back and forth, or just the last few). Again: stop"""
    bl_idname = "stop_motion.play"
    bl_label = "Play"

    def execute(self, context):
        scene = context.scene
        screen = context.screen
        if screen is not None and screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
            return {'FINISHED'}
        if PLAYER["on"]:
            stop_playing(scene)
        else:
            start_playing(scene)
        return {'FINISHED'}


class SM_OT_export(bpy.types.Operator):
    """Make a movie or a set of frames from the shots"""
    bl_idname = "stop_motion.export"
    bl_label = "Export"

    kind: EnumProperty(items=[('MOVIE', "Movie (MP4)", ""), ('FRAMES', "Frames (PNG)", ""),
                              ('GIF', "GIF", "A small looping animation to share"),
                              ('BLEND', "Blender scene", "A copy of the scene for finishing in Blender")],
                       default='MOVIE')
    bounce: BoolProperty(name="Back and forth", default=False,
                         description="GIF plays forwards then backwards")
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
        out_dir = films_dir(scene)
        if self.kind == 'GIF':
            path = export_gif(context, scene, os.path.join(out_dir, base + ".gif"), self.quality, self.bounce)
            if path is None:
                self.report({'WARNING'}, "No shot pictures to make a GIF from")
                return {'CANCELLED'}
            self.report({'INFO'}, "Saved " + path)
            return {'FINISHED'}
        if self.kind == 'BLEND':
            path = export_blend(scene, os.path.join(out_dir, base + "_scene.blend"))
            self.report({'INFO'}, "Saved " + path)
            return {'FINISHED'}
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


def films_dir(scene):
    d = bpy.path.abspath("//films/") if bpy.data.filepath else os.path.join(core.capture_dir(scene), "films")
    os.makedirs(d, exist_ok=True)
    return d


def image_rgb(img):
    """A Blender image as an HxWx3 uint8 array, top row first."""
    import numpy as np
    w, h = img.size
    if w == 0 or h == 0:
        return None
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[::-1, :, :3]
    return np.clip(np.rint(px * 255.0), 0, 255).astype(np.uint8)


def _render_final(scene, path):
    bpy.ops.render.render(write_still=False)
    result = bpy.data.images.get("Render Result")
    if result is None:
        return None
    fmt = scene.render.image_settings.file_format
    try:
        scene.render.image_settings.file_format = 'PNG'
        result.save_render(path, scene=scene)
    finally:
        scene.render.image_settings.file_format = fmt
    return path


def gif_frames(context, scene, quality='AS_SHOT', width=640):
    """One picture per shot and how long each is held. As shot: the shot pictures; final: rendered."""
    import tempfile
    frames, holds = [], []
    keep = scene.frame_current
    tmp = os.path.join(tempfile.gettempdir(), "stop_motion_gif.png")
    try:
        for _i, shot, start, hold in core.shot_spans(scene):
            img = None
            if quality == 'FINAL':
                scene.frame_set(start)
                if _render_final(scene, tmp):
                    img = bpy.data.images.load(tmp, check_existing=False)
            else:
                img = core.shot_image(scene, shot.uid)
            rgb = image_rgb(img) if img is not None else None
            if quality == 'FINAL' and img is not None:
                bpy.data.images.remove(img)
            if rgb is None:
                if holds:
                    holds[-1] += hold      # no picture: the one before stays up longer
                continue
            from . import gif
            rgb = gif.resize(rgb, width)
            if frames and rgb.shape != frames[0].shape:
                continue
            frames.append(rgb)
            holds.append(hold)
    finally:
        scene.frame_set(keep)
    return frames, holds


def export_gif(context, scene, path, quality='AS_SHOT', bounce=False, width=640):
    from . import gif
    frames, holds = gif_frames(context, scene, quality, width)
    if not frames:
        return None
    if bounce and len(frames) > 2:
        frames = frames + frames[-2:0:-1]
        holds = holds + holds[-2:0:-1]
    return gif.write(path, frames, gif.delays_cs(holds, scene.render.fps / scene.render.fps_base))


def export_blend(scene, path):
    """A copy of the file for finishing in Blender: the shots are ordinary keyframes,
    the cuts are camera markers; the ghost pictures are left out."""
    for ob in scene.objects:
        if ob.type == 'CAMERA':
            bgs = ob.data.background_images
            for bg in list(bgs):
                if bg.image is not None and bg.image.name.startswith(core.GHOST_PREFIX):
                    bgs.remove(bg)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, relative_remap=True)
    finally:
        core.update_ghost(scene)
    return path


classes = (SM_OT_shoot, SM_OT_delete_shot, SM_OT_hold, SM_OT_duplicate_shot,
           SM_OT_goto_shot, SM_OT_step, SM_OT_go_live, SM_OT_toggle_ghost,
           SM_OT_play, SM_OT_export)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    stop_playing(back_to_live=False)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
