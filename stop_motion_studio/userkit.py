# SPDX-License-Identifier: GPL-3.0-or-later
"""Your own kit parts: models you make go in the parts kit next to the built-in ones.

Put .blend files in Library › Kit, one folder per kind of part:

    Kit/Heads   Kit/Bodies  Kit/Arms   Kit/Legs   Kit/Feet   Kit/Tails
    Kit/Hair    Kit/Hats    Kit/Extras

Each file is a part, named after the file. A file with collections gives one
part per collection, named after the collection, so Hats.blend can hold
"Cap", "Beret" and "Crown". Model at any size, anywhere: a part is fitted to
the armature when it goes on (heads, hair and hats to the head, bodies to the
spine, arms and legs from joint to joint, feet to the floor). Model one arm,
leg or foot: the other side is a mirror copy. Textures and materials are
kept; pack them into the file (File › External Data › Pack Resources) so they
travel with it.

A part is read from its file once and kept in the project, so the puppet
still works if the file moves; changing the file (and choosing the part
again) brings in the new version.
"""

import json
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import assembly as A
from . import library

FOLDERS = {"head": "Heads", "body": "Bodies", "arms": "Arms", "legs": "Legs", "feet": "Feet",
           "tail": "Tails", "hair": "Hair", "hat": "Hats", "extra": "Extras"}
PREFIX = "user:"


def kit_dir():
    return os.path.join(library.library_dir(), "Kit")


def ensure_folders():
    root = kit_dir()
    for f in FOLDERS.values():
        os.makedirs(os.path.join(root, f), exist_ok=True)
    readme = os.path.join(root, "Read me.txt")
    if not os.path.exists(readme):
        try:
            with open(readme, "w") as fh:
                fh.write(__doc__.split("\n\n", 1)[1])
        except OSError:
            pass
    return root


def variant_id(rel, item):
    return PREFIX + rel + "|" + item


def parse(variant):
    """(full path, item) for a user variant id, or None."""
    if not variant.startswith(PREFIX):
        return None
    rel, _sep, item = variant[len(PREFIX):].rpartition("|")
    return os.path.join(kit_dir(), rel), item or library.WHOLE_FILE


def is_user(variant):
    return isinstance(variant, str) and variant.startswith(PREFIX)


_LIST_CACHE = {}


def parts(kind):
    """Your parts of one kind: [(variant id, label, blend path, item)], by file then name."""
    folder = os.path.join(kit_dir(), FOLDERS.get(kind, ""))
    if kind not in FOLDERS or not os.path.isdir(folder):
        return []
    out = []
    for f in library.list_files(folder):
        path = os.path.join(folder, f)
        try:
            m = os.path.getmtime(path)
        except OSError:
            continue
        key = (path, m)
        items = _LIST_CACHE.get(key)
        if items is None:
            items = library.contents(path)
            _LIST_CACHE[key] = items
        rel = os.path.join(FOLDERS[kind], f)
        for name, label in sorted(items, key=lambda it: it[1].lower()):
            out.append((variant_id(rel, name), label, path, name))
    return out


def label_of(variant):
    p = parse(variant)
    if p is None:
        return variant
    path, item = p
    return item if item != library.WHOLE_FILE else os.path.splitext(os.path.basename(path))[0]


def missing_pictures():
    out = []
    root = kit_dir()
    for f in FOLDERS.values():
        folder = os.path.join(root, f)
        if os.path.isdir(folder):
            out += library.missing_thumbnails(folder)
    return out


# ------------------------------------------------------------- reading a part

def source_mesh(path, item):
    """The part as one mesh in the coordinates it was modelled in, read once and kept
    (a fake user keeps it in the project). Returns the mesh, or None."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    key = os.path.relpath(path, kit_dir()) + "|" + item
    for me in bpy.data.meshes:
        if me.get("sm_kit_src") == key and (mtime is None or abs(me.get("sm_kit_mtime", 0) - mtime) < 1e-3):
            return me
    if mtime is None:
        # the file's gone: use the copy we kept, whatever its age
        return next((me for me in bpy.data.meshes if me.get("sm_kit_src") == key), None)
    before_obs, before_cols = set(bpy.data.objects), set(bpy.data.collections)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        if item == library.WHOLE_FILE:
            dst.objects = list(src.objects)
        else:
            dst.collections = [item]
    obs = []
    if item == library.WHOLE_FILE:
        obs = [o for o in dst.objects if o is not None]
    else:
        for c in dst.collections:
            if c is not None:
                obs += list(c.all_objects)
    bm = bmesh.new()
    mats = []
    for ob in obs:
        if ob.type != 'MESH' or ob.data is None or not len(ob.data.vertices):
            continue
        tmp = bmesh.new()
        tmp.from_mesh(ob.data)
        tmp.transform(ob.matrix_world)
        remap = []
        for m in ob.data.materials:
            if m is not None and m not in mats:
                mats.append(m)
            remap.append(mats.index(m) if m is not None else 0)
        for f in tmp.faces:
            f.material_index = remap[f.material_index] if f.material_index < len(remap) else 0
        me_tmp = bpy.data.meshes.new("SM tmp")
        tmp.to_mesh(me_tmp)
        tmp.free()
        bm.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)
    old = next((me for me in bpy.data.meshes if me.get("sm_kit_src") == key), None)
    me = None
    if len(bm.verts):
        me = bpy.data.meshes.new("SM Kit " + key)
        bm.to_mesh(me)
        for m in mats:
            me.materials.append(m)
        me.use_fake_user = True
        me["sm_kit_src"] = key
        me["sm_kit_mtime"] = mtime
        if old is not None:
            old.use_fake_user = False
            old["sm_kit_src"] = ""
    bm.free()
    # the objects we read were only for their shapes
    for ob in set(bpy.data.objects) - before_obs:
        data = ob.data
        bpy.data.objects.remove(ob)
        if isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)
    for c in set(bpy.data.collections) - before_cols:
        bpy.data.collections.remove(c)
    return me


# ------------------------------------------------------------------ fitting

def _bbox(pts):
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def fit_box(pts, size_axis, size, anchor, target):
    """Scale evenly so the model is `size` along `size_axis` (0/1/2), then move its
    `anchor` point (a function of (lo, hi)) to `target`."""
    lo, hi = _bbox(pts)
    ext = (hi - lo)[size_axis]
    k = size / max(ext, 1e-6)
    a = anchor(lo, hi)
    return Matrix.Translation(target) @ Matrix.Scale(k, 4) @ Matrix.Translation(-a)


def fit_limb(pts, a, b, overshoot=1.06):
    """Lay a limb from joint `a` to joint `b`: its long side runs along the bone,
    the end nearest the body (or the top) at `a`."""
    lo, hi = _bbox(pts)
    ext = hi - lo
    i = max(range(3), key=lambda k: ext[k])
    c = (lo + hi) / 2
    e_lo, e_hi = c.copy(), c.copy()
    e_lo[i], e_hi[i] = lo[i], hi[i]
    if i == 2:
        start, end = e_hi, e_lo                       # standing up: the top is the shoulder or hip
    elif i == 0:
        start, end = (e_lo, e_hi) if abs(lo.x) < abs(hi.x) else (e_hi, e_lo)   # nearest the middle
    else:
        start, end = e_hi, e_lo
    d = (end - start)
    t = b - a
    rot = d.normalized().rotation_difference(t.normalized()).to_matrix().to_4x4()
    k = t.length * overshoot / max(d.length, 1e-6)
    pull = t.normalized() * t.length * 0.03          # start a little inside the joint
    return Matrix.Translation(a - pull) @ rot @ Matrix.Scale(k, 4) @ Matrix.Translation(-start)


def _object_from(src, matrix, mirror, name, colour, collection):
    bm = bmesh.new()
    bm.from_mesh(src)
    if mirror:
        bm.transform(Matrix.Diagonal((-1, 1, 1, 1)))
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.transform(matrix)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in src.materials:
        me.materials.append(m)
    if not len(me.materials):
        me.materials.append(A.clay(colour))       # an untextured model takes the kit colour
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def _points(src, mirror):
    pts = [v.co.copy() for v in src.vertices]
    if mirror:
        for p in pts:
            p.x = -p.x
    return pts


def make(context, arm, kind, variant, colour=None, side=""):
    """Fit one of your parts to `arm` and put it on. Returns the object(s) made."""
    found = parse(variant)
    if found is None:
        raise ValueError("not a part from your kit: %s" % variant)
    path, item = found
    src = source_mesh(path, item)
    if src is None:
        raise FileNotFoundError("Couldn't read %s from %s" % (item, path))
    J, info = A._j(arm)
    four = info["template"] == 'FOUR_LEGS'
    s = A.TEMPLATES[info["template"]][1] * info["props"]["height"]
    colour = colour or A.default_colour(arm, kind)
    col = arm.users_collection[0] if arm.users_collection else context.scene.collection
    mirror = side == "R"
    sfx = "." + side if side else ""
    pts = _points(src, mirror)
    recipe = json.dumps({"kind": kind, "variant": variant, "colour": colour, "side": side})
    made = []

    def finish(ob, bones=None, rigid=None):
        ob["sm_part"] = recipe
        for p in ob.data.polygons:
            p.use_smooth = True
        if rigid:
            A.attach_rigid(ob, arm, rigid)
        else:
            A.skin(ob, arm, bones, softness=info.get("softness", 0.5))
        made.append(ob)
        return ob

    name = A._part_name(arm, kind, side)
    bottom_centre = lambda lo, hi: Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))   # noqa: E731
    centre = lambda lo, hi: (lo + hi) / 2                                                # noqa: E731
    top_centre = lambda lo, hi: Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z))    # noqa: E731
    if kind == "head":
        if four:
            m = fit_box(pts, 1, (J["nose"] - J["skull"]).length * 1.6, centre, J["skull"] + (J["nose"] - J["skull"]) * 0.3)
        else:
            m = fit_box(pts, 2, (J["crown"] - J["skull"]).length * 1.22, centre, (J["skull"] + J["crown"]) / 2)
        finish(_object_from(src, m, mirror, name, colour, col), rigid="head")
    elif kind in ("hair", "hat"):
        from . import accessories
        c, half, top = accessories.head_frame(arm)
        h = half.z * 2
        if kind == "hair":
            m = fit_box(pts, 0, half.x * 2 * 1.08, top_centre, Vector((c.x, c.y + half.y * 0.08, top + h * 0.04)))
        else:
            m = fit_box(pts, 0, half.x * 2 * 1.15, bottom_centre, Vector((c.x, c.y, top - h * 0.28)))
        finish(_object_from(src, m, mirror, name, colour, col), rigid="head")
    elif kind == "extra":
        from . import accessories
        p, half_w = accessories.chest_front(arm)
        back = lambda lo, hi: Vector(((lo.x + hi.x) / 2, hi.y, (lo.z + hi.z) / 2))   # noqa: E731
        m = fit_box(pts, 0, half_w * 0.7, back, p + Vector((0, s * 0.004, 0)))
        finish(_object_from(src, m, mirror, name, colour, col), rigid="chest")
    elif kind == "body":
        if four:
            span = (J["neck"] - J["tail_base"]).length * 1.08
            m = fit_box(pts, 1, span, centre, (J["neck"] + J["tail_base"]) / 2)
        else:
            lo_z, hi_z = J["pelvis"].z - s * 0.03, J["neck"].z + s * 0.02
            m = fit_box(pts, 2, hi_z - lo_z, bottom_centre, Vector((J["waist"].x, J["waist"].y, lo_z)))
        finish(_object_from(src, m, mirror, name, colour, col), bones=["hips", "spine", "chest", "neck"])
    elif kind == "arms":
        m = fit_limb(pts, J["shoulder" + sfx], J["wrist" + sfx])
        finish(_object_from(src, m, mirror, name, colour, col), bones=["upper_arm" + sfx, "forearm" + sfx])
    elif kind == "legs" and not four:
        m = fit_limb(pts, J["hip" + sfx], J["ankle" + sfx])
        finish(_object_from(src, m, mirror, name, colour, col), bones=["thigh" + sfx, "shin" + sfx])
    elif kind == "legs" and four:
        for pre, a_, c_, up, low in (("front", "shoulder", "front_wrist", "front_upper_leg", "front_shin"),
                                     ("back", "hip", "hock", "back_thigh", "back_shin")):
            m = fit_limb(pts, J[a_ + sfx], J[c_ + sfx])
            finish(_object_from(src, m, mirror, A._part_name(arm, "%s leg" % pre, side), colour, col),
                   bones=[up + sfx, low + sfx])
    elif kind == "feet":
        pairs = ((("front_wrist", "front_toe", "front_foot"), ("hock", "back_toe", "back_foot")) if four
                 else (("ankle", "toe", "foot"),))
        for a_, t_, bone in pairs:
            a, t = J[a_ + sfx], J[t_ + sfx]
            length = (t - a).length * (1.6 if not four else 1.3)
            target = Vector(((a.x + t.x) / 2, (a.y + t.y) / 2 - length * 0.1, t.z))
            m = fit_box(pts, 1, length, bottom_centre, target)
            finish(_object_from(src, m, mirror, name if len(pairs) == 1 else A._part_name(arm, bone, side), colour, col),
                   rigid=bone + sfx)
    elif kind == "tail":
        m = fit_limb(pts, J["tail_base"], J["tail_tip"], overshoot=1.0)
        finish(_object_from(src, m, mirror, name, colour, col), bones=["tail"])
    else:
        raise ValueError("your own %s parts aren't supported" % kind)
    return made


class SM_OT_open_kit(bpy.types.Operator):
    """Open your kit folder (Library › Kit): put .blend files of your own parts in its folders"""
    bl_idname = "stop_motion.open_kit"
    bl_label = "Open My Kit Folder"

    def execute(self, context):
        root = ensure_folders()
        _LIST_CACHE.clear()
        bpy.ops.wm.path_open(filepath=root)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(SM_OT_open_kit)


def unregister():
    bpy.utils.unregister_class(SM_OT_open_kit)
