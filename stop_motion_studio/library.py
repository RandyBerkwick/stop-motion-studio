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
    render_thumbnail(sorted(keep, key=lambda o: o.name), thumb_path(path))
    return path


# ---------------------------------------------------------------- pictures

THUMB_SIZE = 320
_THUMB_QUEUE = []          # [(blend path, item)] waiting for a picture
_ID_KINDS = ("objects", "meshes", "materials", "armatures", "actions", "images", "collections",
             "cameras", "lights", "curves", "node_groups", "textures", "lattices", "grease_pencils")


def thumb_path(blend_path, item=WHOLE_FILE):
    base = os.path.splitext(blend_path)[0]
    if item and item != WHOLE_FILE:
        base += " -- " + "".join(ch for ch in item if ch not in '/\\:*?"<>|')
    return base + ".png"


def _bounds(objects):
    pts = []
    for ob in objects:
        if ob.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'} and not ob.hide_render:
            pts.extend(ob.matrix_world @ Vector(c) for c in ob.bound_box)
    if not pts:
        pts = [ob.matrix_world.translation for ob in objects] or [Vector()]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def render_thumbnail(objects, out_path, size=THUMB_SIZE):
    """A picture of `objects` from a three-quarter front view, on a clear background."""
    import math
    objects = [ob for ob in objects if ob is not None]
    if not objects:
        return None
    tmp = bpy.data.scenes.new("SM Thumbnail")
    cam = None
    try:
        for ob in objects:
            if ob.name not in tmp.collection.objects:
                tmp.collection.objects.link(ob)
        tmp.view_layers[0].update()          # where things really are (parents, rigs, constraints)
        dg = tmp.view_layers[0].depsgraph
        lo, hi = _bounds([ob.evaluated_get(dg) for ob in objects])
        centre = (lo + hi) / 2
        radius = max((hi - lo).length / 2, 0.01)
        cam_data = bpy.data.cameras.new("SM Thumbnail")
        cam_data.lens = 50
        cam = bpy.data.objects.new("SM Thumbnail", cam_data)
        tmp.collection.objects.link(cam)
        fov = 2 * math.atan(cam_data.sensor_width / (2 * cam_data.lens))
        d = Vector((0.45, -1.0, 0.35)).normalized()          # front is -Y
        rot = (-d).to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot.to_euler()
        # back off just far enough that every corner of the bounds is in frame (with a margin)
        inv = rot.to_matrix().inverted()
        tan = math.tan(fov / 2) * 0.86
        need = 0.0
        for x in (lo.x, hi.x):
            for y in (lo.y, hi.y):
                for z in (lo.z, hi.z):
                    c = inv @ (Vector((x, y, z)) - centre)    # camera space: -z looks at it
                    need = max(need, c.z + abs(c.x) / tan, c.z + abs(c.y) / tan)
        cam.location = centre + d * max(need, radius * 0.5)
        cam_data.clip_end = max(100.0, radius * 20)
        tmp.camera = cam
        r = tmp.render
        r.engine = 'BLENDER_WORKBENCH'
        r.resolution_x = r.resolution_y = size
        r.resolution_percentage = 100
        r.film_transparent = True
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGBA'
        r.filepath = out_path
        tmp.view_settings.view_transform = 'Standard'
        tmp.view_settings.exposure = 0.3
        sh = tmp.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'MATERIAL'
        sh.show_shadows = True
        sh.show_cavity = True
        bpy.ops.render.render(write_still=True, scene=tmp.name)
    except Exception as exc:
        print("Stop Motion: couldn't make a picture:", exc)
        return None
    finally:
        if cam is not None:
            data = cam.data
            bpy.data.objects.remove(cam)
            bpy.data.cameras.remove(data)
        bpy.data.scenes.remove(tmp)
    _forget_image(out_path)
    return out_path if os.path.exists(out_path) else None


def make_file_thumbnail(path, item=WHOLE_FILE):
    """Load an item from a library file just long enough to take its picture."""
    before = {k: set(getattr(bpy.data, k)) for k in _ID_KINDS if hasattr(bpy.data, k)}
    out = None
    try:
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            if item == WHOLE_FILE:
                dst.objects = list(src.objects)
            else:
                dst.collections = [item]
        obs = [o for o in dst.objects if o is not None] if item == WHOLE_FILE else \
            [o for c in dst.collections if c is not None for o in c.all_objects]
        out = render_thumbnail(obs, thumb_path(path, item))
    except (OSError, RuntimeError) as exc:
        print("Stop Motion: couldn't read %s: %s" % (path, exc))
    finally:
        new = []
        for k, old in before.items():
            new.extend(i for i in getattr(bpy.data, k) if i not in old)
        if new:
            bpy.data.batch_remove(new)
    return out


def missing_thumbnails(folder=None):
    folder = folder or library_dir()
    out = []
    for f in list_files(folder):
        path = os.path.join(folder, f)
        for name, _label in contents(path):
            tp = thumb_path(path, name)
            if not os.path.exists(tp) or os.path.getmtime(tp) < os.path.getmtime(path):
                out.append((path, name))
    return out


def queue_thumbnails(items):
    for it in items:
        if it not in _THUMB_QUEUE:
            _THUMB_QUEUE.append(it)
    if _THUMB_QUEUE and not bpy.app.timers.is_registered(_thumb_tick):
        bpy.app.timers.register(_thumb_tick, first_interval=0.2)


def _thumb_tick():
    """One picture at a time, so the Studio stays responsive."""
    if not _THUMB_QUEUE:
        return None
    path, item = _THUMB_QUEUE.pop(0)
    if os.path.exists(path):
        make_file_thumbnail(path, item)
    try:
        from . import studio
        studio.redraw()
    except Exception:
        pass
    return 0.05 if _THUMB_QUEUE else None


def _image_name(png):
    return "SM thumb " + str(abs(hash(png)))


def _forget_image(png):
    img = bpy.data.images.get(_image_name(png))
    if img is not None:
        bpy.data.images.remove(img)


def thumb_image(png):
    """The picture as a Blender image (reloaded when the file changes), or None."""
    if not os.path.exists(png):
        return None
    name = _image_name(png)
    img = bpy.data.images.get(name)
    m = os.path.getmtime(png)
    if img is not None and img.get("sm_mtime") != m:
        bpy.data.images.remove(img)
        img = None
    if img is None:
        try:
            img = bpy.data.images.load(png, check_existing=False)
        except RuntimeError:
            return None
        img.name = name
        img["sm_mtime"] = m
    return img


class SM_OT_make_thumbnails(bpy.types.Operator):
    """Take a picture of everything in the library that doesn't have one yet"""
    bl_idname = "stop_motion.make_thumbnails"
    bl_label = "Make Library Pictures"

    def execute(self, context):
        todo = missing_thumbnails()
        for path, item in todo:
            make_file_thumbnail(path, item)
        self.report({'INFO'}, "%d picture%s made" % (len(todo), "" if len(todo) == 1 else "s"))
        return {'FINISHED'}


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


classes = (SM_OT_bring_in, SM_OT_add_to_library, SM_OT_open_library, SM_OT_make_thumbnails)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
