# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, IntProperty, PointerProperty, StringProperty)

from . import core

_jumping = False


def _on_active(self, context):
    """Clicking a shot card jumps to it (pose over)."""
    global _jumping
    if _jumping:
        return
    scene = context.scene
    if 0 <= self.active_index < len(self.shots):
        _jumping = True
        try:
            scene.frame_set(core.shot_start(scene, self.active_index))
        finally:
            _jumping = False


def _on_fps(self, context):
    context.scene.render.fps = int(self.fps)
    context.scene.render.fps_base = 1.0


def _on_ghost(self, context):
    core.update_ghost(context.scene)


def _is_camera(self, ob):
    return ob.type == 'CAMERA'


class SM_Shot(bpy.types.PropertyGroup):
    uid: StringProperty()
    hold: IntProperty(name="Hold", min=1, max=96, default=2,
                      description="How many frames this shot is shown for")
    camera: PointerProperty(type=bpy.types.Object, poll=_is_camera, name="Camera",
                            description="The camera this shot is filmed with (the film cuts when it changes)")


class SM_Settings(bpy.types.PropertyGroup):
    shots: CollectionProperty(type=SM_Shot)
    live_camera: PointerProperty(type=bpy.types.Object, poll=_is_camera, name="Next shots film with",
                                 description="The camera the next shots are filmed with")
    active_index: IntProperty(default=-1, update=_on_active)

    default_hold: EnumProperty(
        name="Each shot lasts",
        items=[('1', "1 frame", "Shoot on ones"),
               ('2', "2 frames", "Shoot on twos"),
               ('3', "3 frames", "Shoot on threes")],
        default='2')
    fps: EnumProperty(
        name="Speed",
        items=[('8', "8 fps", ""), ('12', "12 fps", ""), ('24', "24 fps", "")],
        default='12', update=_on_fps)
    key_scope: EnumProperty(
        name="Shoot captures",
        items=[('ALL', "Everything", "Every puppet, prop and camera"),
               ('SELECTED', "Selected only", "Only what is selected")],
        default='ALL')

    ghost_enabled: BoolProperty(name="Ghost", default=True, update=_on_ghost,
                                description="Show earlier shots faintly over the camera view")
    ghost_opacity: FloatProperty(name="Ghost strength", min=0.0, max=1.0, default=0.35,
                                 subtype='FACTOR', update=_on_ghost)
    ghost_count: IntProperty(name="Ghost shots", min=1, max=3, default=1, update=_on_ghost)

    capture_dir: StringProperty(name="Shot pictures", subtype='DIR_PATH',
                                default="//stopmotion_shots/")
    show_hud: BoolProperty(name="Shot number on camera", default=True)
    stick_align: BoolProperty(name="Lean with the surface", default=True,
                              description="Objects you arrange tilt to follow the surface (off: they stay upright)")
    stamp_vary: FloatProperty(name="Vary size", min=0.0, max=0.6, default=0.15, subtype='FACTOR',
                              description="How much each stamped copy's size varies")
    solid_world: BoolProperty(name="Solid world", default=True,
                              description="Dragged parts and props stop at surfaces instead of passing through")


classes = (SM_Shot, SM_Settings)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.stop_motion = PointerProperty(type=SM_Settings)
    bpy.types.WindowManager.stop_motion_ui_hidden = BoolProperty(default=False)


def unregister():
    del bpy.types.WindowManager.stop_motion_ui_hidden
    del bpy.types.Scene.stop_motion
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
