# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop Motion Studio app template.

Blender started with this template (File > New > Stop Motion Studio, or
`Blender --app-template StopMotionStudio`, which the Mac launcher does)
opens straight into the Studio with Blender hidden. Ctrl+Alt+Shift+B
switches to normal Blender and back.

The template has its own preferences, so nothing here changes your normal
Blender setup.
"""

import addon_utils
import bpy
from bpy.app.handlers import persistent


def _extension_module():
    import sys
    for mod in addon_utils.modules():
        if mod.__name__.split(".")[-1] == "stop_motion_studio":
            return mod.__name__
    for name in list(sys.modules):  # already loaded some other way (e.g. a dev link)
        if name.split(".")[-1] == "stop_motion_studio":
            return name
    return None


def _open_studio():
    try:
        name = _extension_module()
        if name is None:
            print("Stop Motion Studio: the extension isn't installed (see the README)")
            return None
        running = hasattr(bpy.types, "STOP_MOTION_OT_studio")
        if not running and not addon_utils.check(name)[1]:
            addon_utils.enable(name, default_set=True, persistent=True)
        prefs = bpy.context.preferences
        prefs.view.show_splash = False
        import importlib
        studio = importlib.import_module(name + ".studio")
        if not studio.S.active:
            studio.S.wanted = True
            studio.open_in_first_window()
    except Exception as exc:  # never stop Blender starting
        print("Stop Motion Studio: couldn't open the Studio:", exc)
    return None


@persistent
def _on_startup(_dummy=None):
    bpy.app.timers.register(_open_studio, first_interval=0.3)


def register():
    bpy.app.handlers.load_factory_startup_post.append(_on_startup)
    _on_startup()


def unregister():
    if _on_startup in bpy.app.handlers.load_factory_startup_post:
        bpy.app.handlers.load_factory_startup_post.remove(_on_startup)
