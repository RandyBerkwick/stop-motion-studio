# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop Motion Studio: move-and-shoot stop-motion animation inside full Blender."""

from . import props, ops, layout, ui

_modules = (props, ops, layout, ui)


def register():
    for m in _modules:
        m.register()


def unregister():
    for m in reversed(_modules):
        m.unregister()
