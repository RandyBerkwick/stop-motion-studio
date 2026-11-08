# SPDX-License-Identifier: GPL-3.0-or-later
"""Camera setups and saved free-view positions.

Camera setups are the scene's camera objects. One is filming (the scene
camera); any can be locked so it can't be knocked. Switching setups is for
checking angles: it isn't recorded in the shots.

Saved views are bookmarks for the free view (not the camera)."""

import bpy
from bpy.props import (EnumProperty, CollectionProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, StringProperty, BoolProperty)

from . import core


# --------------------------------------------------------------------- data

class SM_SavedView(bpy.types.PropertyGroup):
    location: FloatVectorProperty(size=3)
    rotation: FloatVectorProperty(size=4)
    distance: FloatProperty()
    ortho: BoolProperty()


def cameras(scene):
    return sorted((ob for ob in scene.objects if ob.type == 'CAMERA'), key=lambda o: o.name)


def is_locked(cam):
    return all(cam.lock_location) and all(cam.lock_rotation)


def set_locked(cam, locked):
    cam.lock_location = (locked,) * 3
    cam.lock_rotation = (locked,) * 3
    cam.lock_scale = (locked,) * 3
    cam.hide_select = locked
    if cam.data:
        cam.data["sm_locked"] = int(locked)


def find_free_view(screen):
    """The biggest 3D view that isn't looking through the camera."""
    best = None
    if screen is None:
        return None
    for area in screen.areas:
        if area.type != 'VIEW_3D':
            continue
        r3d = area.spaces.active.region_3d
        if r3d and r3d.view_perspective != 'CAMERA':
            if best is None or area.width * area.height > best.width * best.height:
                best = area
    return best


def next_camera_name(scene):
    used = {ob.name for ob in scene.objects}
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        name = "Camera " + letter
        if name not in used:
            return name
    return "Camera"


def store_view(saved, r3d):
    saved.location = r3d.view_location
    saved.rotation = r3d.view_rotation
    saved.distance = r3d.view_distance
    saved.ortho = r3d.view_perspective == 'ORTHO'


def restore_view(saved, r3d):
    r3d.view_location = saved.location
    r3d.view_rotation = saved.rotation
    r3d.view_distance = saved.distance
    r3d.view_perspective = 'ORTHO' if saved.ortho else 'PERSP'


# ---------------------------------------------------------------- operators

class SM_OT_use_camera(bpy.types.Operator):
    """Film through this camera. Live: the next shots. On a shot: this shot and the rest of its run, up to the next cut"""
    bl_idname = "stop_motion.use_camera"
    bl_label = "Use Camera"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()
    scope: EnumProperty(items=[('AUTO', "Auto", "Live: the next shots; on a shot: up to the next cut"),
                               ('RUN', "From here to the next cut", ""),
                               ('SHOT', "This shot only", ""),
                               ('LIVE', "The next shots", ""),
                               ('LOOK', "Just look", "Look through it without changing the film")],
                        default='AUTO', options={'SKIP_SAVE'})

    def execute(self, context):
        scene = context.scene
        cam = bpy.data.objects.get(self.name)
        if cam is None or cam.type != 'CAMERA':
            return {'CANCELLED'}
        if self.scope == 'LOOK':
            scene.camera = cam
            core.update_ghost(scene)
            return {'FINISHED'}
        index = core.shot_index_at(scene, scene.frame_current)
        scope = self.scope
        if scope == 'AUTO':
            scope = 'RUN' if index >= 0 else 'LIVE'
        a, b = core.set_camera(scene, index, cam, scope)
        core.update_ghost(scene)
        if scope == 'LIVE' or a >= len(scene.stop_motion.shots):
            self.report({'INFO'}, "Next shots film with %s" % cam.name)
        elif b - a == 1:
            self.report({'INFO'}, "Shot %d films with %s" % (a + 1, cam.name))
        else:
            self.report({'INFO'}, "Shots %d–%d film with %s" % (a + 1, b, cam.name))
        return {'FINISHED'}


class SM_OT_lock_camera(bpy.types.Operator):
    """Lock this camera so it can't be moved or selected by accident"""
    bl_idname = "stop_motion.lock_camera"
    bl_label = "Lock Camera"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        cam = bpy.data.objects.get(self.name)
        if cam is None:
            return {'CANCELLED'}
        locked = not is_locked(cam)
        set_locked(cam, locked)
        if locked:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.lock_camera = False
        return {'FINISHED'}


class SM_OT_new_camera(bpy.types.Operator):
    """New camera setup, placed where the free view is looking from"""
    bl_idname = "stop_motion.new_camera"
    bl_label = "New Camera from Free View"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        cam = bpy.data.objects.new(next_camera_name(scene), bpy.data.cameras.new("Camera"))
        cam.data.lens = 35
        scene.collection.objects.link(cam)
        area = find_free_view(context.screen)
        if area is not None:
            cam.matrix_world = area.spaces.active.region_3d.view_matrix.inverted()
        elif scene.camera is not None:
            cam.matrix_world = scene.camera.matrix_world.copy()
        scene.camera = cam
        core.update_ghost(scene)
        self.report({'INFO'}, "%s is now filming" % cam.name)
        return {'FINISHED'}


class SM_OT_move_camera(bpy.types.Operator):
    """Move the filming camera by navigating in the camera view (unlocks it while you do)"""
    bl_idname = "stop_motion.move_camera"
    bl_label = "Move Camera"

    def execute(self, context):
        cam = context.scene.camera
        area, _r = core.find_camera_area(context.screen)
        if cam is None or area is None:
            self.report({'WARNING'}, "Needs a camera view on screen")
            return {'CANCELLED'}
        space = area.spaces.active
        on = not space.lock_camera
        if on and is_locked(cam):
            set_locked(cam, False)
        space.lock_camera = on
        self.report({'INFO'}, "Navigate the camera view to move %s" % cam.name if on else "Camera stays put")
        return {'FINISHED'}


class SM_OT_save_view(bpy.types.Operator):
    """Remember where the free view is looking from"""
    bl_idname = "stop_motion.save_view"
    bl_label = "Save This View"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        area = find_free_view(context.screen)
        if area is None:
            self.report({'WARNING'}, "No free view on screen")
            return {'CANCELLED'}
        views = context.scene.stop_motion_views
        v = views.add()
        v.name = "View %d" % len(views)
        store_view(v, area.spaces.active.region_3d)
        return {'FINISHED'}


class SM_OT_go_view(bpy.types.Operator):
    """Jump the free view back to this saved view"""
    bl_idname = "stop_motion.go_view"
    bl_label = "Go to View"

    index: IntProperty()

    def execute(self, context):
        views = context.scene.stop_motion_views
        area = find_free_view(context.screen)
        if area is None or not (0 <= self.index < len(views)):
            return {'CANCELLED'}
        restore_view(views[self.index], area.spaces.active.region_3d)
        area.tag_redraw()
        return {'FINISHED'}


class SM_OT_forget_view(bpy.types.Operator):
    """Forget this saved view"""
    bl_idname = "stop_motion.forget_view"
    bl_label = "Forget View"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        views = context.scene.stop_motion_views
        if 0 <= self.index < len(views):
            views.remove(self.index)
        return {'FINISHED'}


classes = (SM_SavedView, SM_OT_use_camera, SM_OT_lock_camera, SM_OT_new_camera,
           SM_OT_move_camera, SM_OT_save_view, SM_OT_go_view, SM_OT_forget_view)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.stop_motion_views = CollectionProperty(type=SM_SavedView)


def unregister():
    del bpy.types.Scene.stop_motion_views
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
