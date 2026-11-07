# SPDX-License-Identifier: GPL-3.0-or-later
"""The Stop Motion workspace (camera view + free view) and hiding the UI."""

import bpy

from . import core

WORKSPACE_NAME = "Stop Motion"


def _window_region(area):
    return next((r for r in area.regions if r.type == 'WINDOW'), None)


def configure_camera_view(area):
    space = area.spaces.active
    space.region_3d.view_perspective = 'CAMERA'
    space.lock_camera = False
    space.show_gizmo = False
    space.show_region_toolbar = False
    space.show_region_ui = False
    space.show_region_tool_header = False
    sh = space.shading
    sh.type = 'MATERIAL'
    sh.use_scene_lights = True
    sh.use_scene_world = True
    ov = space.overlay
    for name in ("show_floor", "show_axis_x", "show_axis_y", "show_axis_z", "show_cursor",
                 "show_extras", "show_relationship_lines", "show_outline_selected",
                 "show_bones", "show_text", "show_stats", "show_object_origins"):
        if hasattr(ov, name):
            setattr(ov, name, False)
    ov.show_overlays = True  # needed for the ghost


def configure_free_view(area):
    space = area.spaces.active
    r3d = space.region_3d
    if r3d.view_perspective == 'CAMERA':
        r3d.view_perspective = 'PERSP'
    space.show_gizmo = True
    space.show_region_toolbar = False
    space.show_region_ui = True
    space.shading.type = 'SOLID'


def _build(window_name_hint=None):
    wm = bpy.context.window_manager
    for window in wm.windows:
        if window.workspace.name != WORKSPACE_NAME:
            continue
        screen = window.screen
        views = [a for a in screen.areas if a.type == 'VIEW_3D']
        main = max(views or list(screen.areas), key=lambda a: a.width * a.height)
        if main.type != 'VIEW_3D':
            main.type = 'VIEW_3D'
        for _ in range(12):
            others = [a for a in screen.areas if a != main]
            if not others:
                break
            with bpy.context.temp_override(window=window, screen=screen, area=others[0]):
                if bpy.ops.screen.area_close() != {'FINISHED'}:
                    break
        with bpy.context.temp_override(window=window, screen=screen, area=main,
                                       region=_window_region(main)):
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.56)
        views = sorted((a for a in screen.areas if a.type == 'VIEW_3D'), key=lambda a: a.x)
        configure_camera_view(views[0])
        for a in views[1:]:
            configure_free_view(a)
        with bpy.context.temp_override(window=window, screen=screen, area=views[0],
                                       region=_window_region(views[0])):
            bpy.ops.view3d.view_center_camera()
    return None


class SM_OT_setup_workspace(bpy.types.Operator):
    """Add a Stop Motion workspace: camera view on the left, free view on the right"""
    bl_idname = "stop_motion.setup_workspace"
    bl_label = "Set Up Stop Motion Workspace"

    def execute(self, context):
        ws = bpy.data.workspaces.get(WORKSPACE_NAME)
        if ws is not None:
            context.window.workspace = ws
            return {'FINISHED'}
        if context.scene.camera is None:
            self.report({'WARNING'}, "Add a camera first: Stop Motion films through the scene camera")
        bpy.ops.workspace.duplicate()
        context.window.workspace.name = WORKSPACE_NAME
        bpy.app.timers.register(_build, first_interval=0.05)
        return {'FINISHED'}


_saved = {}


class SM_OT_toggle_ui(bpy.types.Operator):
    """Hide all the buttons and menus, or bring them back"""
    bl_idname = "stop_motion.toggle_ui"
    bl_label = "Hide / Show UI"

    def execute(self, context):
        wm = context.window_manager
        screen = context.screen
        hide = not wm.stop_motion_ui_hidden
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            space = area.spaces.active
            key = area.as_pointer()
            if hide:
                _saved[key] = (space.show_region_header, space.show_region_ui,
                               space.show_region_toolbar, space.show_region_tool_header,
                               space.show_gizmo_navigate)
                space.show_region_header = False
                space.show_region_ui = False
                space.show_region_toolbar = False
                space.show_region_tool_header = False
                space.show_gizmo_navigate = False
                if hasattr(space, "show_region_asset_shelf"):
                    space.show_region_asset_shelf = False
            elif key in _saved:
                (space.show_region_header, space.show_region_ui, space.show_region_toolbar,
                 space.show_region_tool_header, space.show_gizmo_navigate) = _saved.pop(key)
            else:
                space.show_region_header = True
        screen.show_statusbar = not hide
        wm.stop_motion_ui_hidden = hide
        return {'FINISHED'}


class SM_OT_focus_camera(bpy.types.Operator):
    """Camera view only, full window, nothing else on screen"""
    bl_idname = "stop_motion.focus_camera"
    bl_label = "Camera Only"

    def execute(self, context):
        screen = context.screen
        if screen.show_fullscreen:
            area = context.area if context.area and context.area.type == 'VIEW_3D' else screen.areas[0]
        else:
            area, _r = core.find_camera_area(screen)
            if area is None:
                self.report({'WARNING'}, "No camera view on screen")
                return {'CANCELLED'}
        with context.temp_override(area=area, region=_window_region(area)):
            bpy.ops.screen.screen_full_area(use_hide_panels=True)
        return {'FINISHED'}


classes = (SM_OT_setup_workspace, SM_OT_toggle_ui, SM_OT_focus_camera)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
