# SPDX-License-Identifier: GPL-3.0-or-later
"""The library: puppets, props and set pieces kept as .blend files.

The library is a folder (~/Stop Motion/Library). Each .blend in it can hold
one thing or many: its collections are listed as separate items; a file
with no collections is one item (everything in it). Bringing an item in
appends it, stands it on whatever is in the middle of the camera's view,
and sets it up: a rig becomes a puppet, otherwise it becomes a prop or a
set piece. "Add to library" writes the selection out as a new file.
"""

import os

import bpy
from bpy.props import EnumProperty, StringProperty
from mathutils import Vector

LIBRARY_DIR = os.path.join(os.path.expanduser("~"), "Stop Motion", "Library")
WHOLE_FILE = "*"


def library_dir():
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    return LIBRARY_DIR


def list_files(folder=None):
    folder = folder or library_dir()
    try:
        names = [f for f in os.listdir(folder) if f.lower().endswith(".blend")]
    except OSError:
        return []
    return sorted(names, key=str.lower)


def contents(path):
    """Items in a library file: [(name, label)]."""
    try:
        with bpy.data.libraries.load(path) as (src, _dst):
            cols = [c for c in src.collections if c and not c.startswith(".")]
            nobs = len(src.objects)
    except (OSError, RuntimeError):
        return []
    if cols:
        return [(c, c) for c in cols]
    if nobs:
        return [(WHOLE_FILE, os.path.splitext(os.path.basename(path))[0])]
    return []


def _drop_point(scene, depsgraph):
    """Where new things go: whatever the camera looks at in the middle of its view, else the origin."""
    cam = scene.camera
    if cam is not None:
        o = cam.matrix_world.translation
        d = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        hit, loc, _n, _i, _ob, _m = scene.ray_cast(depsgraph, o, d)
        if hit:
            return loc
    hit, loc, _n, _i, _ob, _m = scene.ray_cast(depsgraph, Vector((0, 0, 50)), Vector((0, 0, -1)))
    return loc if hit else Vector((0, 0, 0))


def _bottom_centre(objects):
    pts = []
    for ob in objects:
        if ob.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
            pts.extend(ob.matrix_world @ Vector(c) for c in ob.bound_box)
    if not pts:
        pts = [ob.matrix_world.translation for ob in objects]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))


def bring_in(context, path, item=WHOLE_FILE, kind='AUTO', place=True):
    """Append `item` from `path` into the scene. Returns (new objects, what it became)."""
    scene = context.scene
    dg = context.evaluated_depsgraph_get()
    target = _drop_point(scene, dg) if place else None
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        if item == WHOLE_FILE:
            dst.objects = list(src.objects)
        else:
            dst.collections = [item]
    new_cols = [c for c in dst.collections if c is not None]
    for c in new_cols:
        scene.collection.children.link(c)
    if item == WHOLE_FILE:
        for ob in dst.objects:
            if ob is not None and ob.name not in scene.objects:
                scene.collection.objects.link(ob)
    # things they depend on (a puppet's foot pins) come too: put them in the scene
    for ob in bpy.data.objects:
        if ob not in before and ob.name not in scene.objects and ob.users_collection == ():
            scene.collection.objects.link(ob)
    context.view_layer.update()
    new = [ob for ob in bpy.data.objects if ob not in before and ob.name in scene.objects]
    if not new:
        return [], None
    roots = [ob for ob in new if ob.parent is None or ob.parent not in new]
    if target is not None:
        offset = target - _bottom_centre(new)
        for ob in roots:
            ob.matrix_world.translation += offset
        context.view_layer.update()
    arms = [ob for ob in new if ob.type == 'ARMATURE']
    if kind == 'AUTO':
        kind = 'PUPPET' if arms else 'PROP'
    from . import puppet
    if kind == 'PUPPET' and arms:
        for arm in arms:
            if not arm.stop_motion_puppet.enabled:
                puppet.make_puppet(context, arm)
        what = 'PUPPET'
    elif kind == 'SET':
        for ob in roots:
            ob.stop_motion_set = True
        what = 'SET'
    else:
        for ob in roots:
            if ob.type in {'MESH', 'EMPTY'}:
                ob.stop_motion_prop = True
        what = 'PROP'
    for ob in context.selected_objects:
        ob.select_set(False)
    for ob in roots:
        ob.select_set(True)
    context.view_layer.objects.active = arms[0] if arms else roots[0]
    return new, what


def add_to_library(context, objects, name):
    """Write `objects` (and everything under them) into a new library file."""
    keep = set()
    for ob in objects:
        keep.add(ob)
        keep.update(ob.children_recursive)
        pp = getattr(ob, "stop_motion_puppet", None)
        if pp is not None and pp.enabled:
            keep.update(o for r in pp.rings for o in (r.pin, r.knee) if o is not None)   # foot pins live beside the rig
    folder = library_dir()
    base = "".join(ch for ch in name if ch not in '/\\:*?"<>|').strip() or "Thing"
    path = os.path.join(folder, base + ".blend")
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, "%s %d.blend" % (base, n))
        n += 1
    bpy.data.libraries.write(path, keep, fake_user=True, path_remap='ABSOLUTE')
    return path


class SM_OT_bring_in(bpy.types.Operator):
    """Bring a puppet, prop or set piece in from the library"""
    bl_idname = "stop_motion.bring_in"
    bl_label = "Bring In"
    bl_options = {'REGISTER', 'UNDO'}

    path: StringProperty()
    item: StringProperty(default=WHOLE_FILE)
    kind: EnumProperty(items=[('AUTO', "Automatic", "A rig becomes a puppet, anything else a prop"),
                              ('PUPPET', "Puppet", ""), ('PROP', "Prop", ""), ('SET', "Set piece", "")],
                       default='AUTO')

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        path = self.path if os.path.isabs(self.path) else os.path.join(library_dir(), self.path)
        if not os.path.exists(path):
            self.report({'WARNING'}, "Not found: " + path)
            return {'CANCELLED'}
        new, what = bring_in(context, path, self.item, self.kind)
        if not new:
            self.report({'WARNING'}, "Nothing to bring in")
            return {'CANCELLED'}
        label = os.path.splitext(os.path.basename(path))[0] if self.item == WHOLE_FILE else self.item
        self.report({'INFO'}, "%s is in, as a %s" % (label, {'PUPPET': "puppet", 'PROP': "prop", 'SET': "set piece"}[what]))
        return {'FINISHED'}


class SM_OT_add_to_library(bpy.types.Operator):
    """Keep the selected objects in the library, to bring into other projects"""
    bl_idname = "stop_motion.add_to_library"
    bl_label = "Add to Library"

    name: StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        obs = list(context.selected_objects)
        # a puppet's meshes come with its rig
        roots = []
        for ob in obs:
            while ob.parent is not None:
                ob = ob.parent
            if ob not in roots:
                roots.append(ob)
        name = self.name or (context.active_object.name if context.active_object else roots[0].name)
        path = add_to_library(context, roots, name)
        self.report({'INFO'}, "Saved to the library: " + os.path.basename(path))
        return {'FINISHED'}


class SM_OT_open_library(bpy.types.Operator):
    """Show the library folder (put .blend files of puppets, props and sets in it)"""
    bl_idname = "stop_motion.open_library"
    bl_label = "Show Library Folder"

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=library_dir())
        return {'FINISHED'}


classes = (SM_OT_bring_in, SM_OT_add_to_library, SM_OT_open_library)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
