# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop Motion Studio: move-and-shoot stop-motion animation inside full Blender."""

from . import props, puppet, solid, arrange, ops, rings, cameras, lighting, sculpt, library, assembly, userkit, wear, faces, trial, rigsculpt, layout, studio, strip, ui

_modules = (props, puppet, solid, arrange, ops, rings, cameras, lighting, sculpt, library, assembly, userkit, wear, faces, trial, rigsculpt, layout, studio, strip, ui)


def register():
    for m in _modules:
        m.register()


def unregister():
    for m in reversed(_modules):
        m.unregister()
