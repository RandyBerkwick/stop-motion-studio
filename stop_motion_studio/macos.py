# SPDX-License-Identifier: GPL-3.0-or-later
"""Small macOS touches, through the Objective-C runtime (ctypes, no extra packages).

set_dock_icon: while the Studio runs, the Dock shows the Studio's icon
instead of Blender's. Does nothing on other systems."""

import os
import sys

ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")


def set_dock_icon(path=ICON):
    if sys.platform != "darwin" or not os.path.exists(path):
        return False
    try:
        import ctypes
        import ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        def send(obj, sel, *args, argtypes=()):
            f = objc.objc_msgSend
            f.restype = ctypes.c_void_p
            f.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + list(argtypes)
            return f(obj, objc.sel_registerName(sel), *args)

        ns_path = send(objc.objc_getClass(b"NSString"), b"stringWithUTF8String:",
                       path.encode("utf-8"), argtypes=[ctypes.c_char_p])
        image = send(send(objc.objc_getClass(b"NSImage"), b"alloc"), b"initWithContentsOfFile:",
                     ns_path, argtypes=[ctypes.c_void_p])
        if not image:
            return False
        app = send(objc.objc_getClass(b"NSApplication"), b"sharedApplication")
        send(app, b"setApplicationIconImage:", image, argtypes=[ctypes.c_void_p])
        return True
    except Exception as exc:     # a nicety: never let it get in the way
        print("Stop Motion: couldn't set the Dock icon:", exc)
        return False


def reset_dock_icon():
    """Back to Blender's own icon (when leaving the Studio)."""
    if sys.platform != "darwin":
        return False
    try:
        import ctypes
        import ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        f = objc.objc_msgSend
        f.restype = ctypes.c_void_p
        f.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        app = f(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
        f.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        f(app, objc.sel_registerName(b"setApplicationIconImage:"), None)
        return True
    except Exception:
        return False
