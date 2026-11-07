# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop Motion Studio: move-and-shoot stop-motion animation inside full Blender."""

from . import props, puppet, solid, ops, rings, cameras, lighting, sculpt, layout, studio, ui

_modules = (props, puppet, solid, ops, rings, cameras, lighting, sculpt, layout, studio, ui)


def register():
    for m in _modules:
        m.register()


def unregister():
    for m in reversed(_modules):
        m.unregister()
