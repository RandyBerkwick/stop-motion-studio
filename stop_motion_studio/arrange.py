# SPDX-License-Identifier: GPL-3.0-or-later
"""Arranging the set: objects that ride along surfaces and stick to them.

Arrange mode: press on an object and drag. Instead of floating in the
air, it slides along whatever surface is under the mouse and sits on it:
its lowest side touches the surface, and anything that would end up
inside something else is pushed back out. With "Lean with the surface"
on, it tilts to follow the surface (a flower stands out from the side of
a bush); off, it stays upright (a cup on a table).

While dragging: mouse wheel spins it around the surface, Alt flips the
lean setting, Ctrl lets it go anywhere (no sticking), Esc puts it back.

Stamp: pick an object, then each click on a surface places a copy of it,
a little different in spin and size each time (flowers on a bush).

Set pieces stay where you put them: they aren't part of the shots, so
moving one moves it in every shot, and lots of them don't slow Shoot.
"""

import math
import random

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Quaternion, Vector

from . import puppet, solid

EPS = 0.001
ARR = {"active": False, "stamp": "", "count": 0}


# ------------------------------------------------------------- rays and hits

def cast(scene, depsgraph, origin, direction, exclude=(), max_hops=12):
    """First solid, visible surface along a ray, skipping `exclude`.
    Returns (location, normal facing the ray, object) or None."""
    origin = Vector(origin)
    direction = Vector(direction).normalized()
    for _ in range(max_hops):
        ok, loc, normal, _i, ob, _m = scene.ray_cast(depsgraph, origin, direction)
        if not ok:
            return None
        if ob is not None and ob.original is not None:
            ob = ob.original
        if ob in exclude or not getattr(ob, "stop_motion_solid", True):
            origin = loc + direction * 1e-4
            continue
        n = normal.normalized()
        if n.dot(direction) > 0:
            n = -n
        return loc, n, ob
    return None


def mouse_ray(region, rv3d, mouse):
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
    return origin, direction


# ------------------------------------------------------------- placement

def local_points(context, ob):
    """The object's shape (and its children's) in its own space."""
    dg = context.evaluated_depsgraph_get()
    inv = ob.matrix_world.inverted()
    pts = []
    for o in [ob] + [c for c in ob.children_recursive if c.type == 'MESH']:
        if o.type != 'MESH':
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        m = inv @ oe.matrix_world
        pts.extend(m @ v.co for v in me.vertices)
        oe.to_mesh_clear()
    if not pts:
        pts = [Vector((0, 0, 0))]
    return solid._thin(pts)


def surface_frame(scene, depsgraph, ob, pts_world, exclude):
    """The surface the object is resting on now (its normal), else straight up."""
    if not pts_world:
        return Vector((0, 0, 1))
    low = min(pts_world, key=lambda p: p.z)
    hit = cast(scene, depsgraph, low + Vector((0, 0, 0.01)), Vector((0, 0, -1)), exclude)
    if hit is None or (hit[0] - low).length > 0.25:
        return Vector((0, 0, 1))
    return hit[1]


def placement(start_matrix, pts_local, hit, normal, align, spin, n0=Vector((0, 0, 1)), tree=None, push=True):
    """World matrix that sits the object on `hit`, facing out along `normal`.

    The object keeps how it sat on its old surface (n0); with `align` the
    whole thing tips over to the new surface's normal. `spin` turns it
    around the normal. Then anything inside an obstacle is pushed out."""
    loc0, rot0, scale0 = start_matrix.decompose()
    n = normal.normalized()
    if align:
        tilt = n0.normalized().rotation_difference(n)
        rot = Quaternion(n, spin) @ tilt @ rot0
        up = n
    else:
        rot = Quaternion((0, 0, 1), spin) @ rot0
        up = Vector((0, 0, 1)) if n.z > 0.2 else n
    lin = rot.to_matrix() @ Matrix.Diagonal(scale0)
    rel = [lin @ p for p in pts_local]
    depths = [p.dot(up) for p in rel]
    d_min = min(depths)
    extent = max(depths) - d_min
    band = d_min + max(1e-5, 0.08 * extent)
    base = [p for p, d in zip(rel, depths) if d <= band]
    centre = sum(base, Vector((0, 0, 0))) / len(base)
    # base centre goes onto the surface point (lifted a hair along `up`)
    t = hit - centre + up * (centre.dot(up) - d_min) + up * EPS
    if tree is not None and push:
        size = max(extent, max((p - centre).length for p in rel), 1e-3)
        t = t + up * min(penetration(tree, [t + p for p in rel], up), 0.6 * size)
    return Matrix.Translation(t) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal(scale0.to_4d())


def penetration(tree, pts, direction, rounds=4):
    """How far along `direction` to push points so none sit inside the obstacles."""
    total = 0.0
    for _ in range(rounds):
        worst = 0.0
        for p in pts:
            q = p + direction * total
            loc, nrm, _i, dist = tree.find_nearest(q)
            if loc is None:
                continue
            if (q - loc).dot(nrm) < 0:                 # behind the surface: inside
                worst = max(worst, dist + EPS)
        if worst <= EPS:
            break
        total += worst
    return total


def arrangeable(scene, ob):
    """Anything but a puppet's own body (puppets move with their rings)."""
    if ob is None or ob.type not in {'MESH', 'EMPTY', 'CURVE', 'FONT'}:
        return False
    for arm in puppet.puppets(scene):
        if ob in puppet.puppet_meshes(arm, scene):
            return False
    return True


def root_of(ob):
    """Drag the top of a little hierarchy (a flower made of parts), not one part."""
    while ob.parent is not None and ob.parent.type != 'ARMATURE':
        ob = ob.parent
    return ob


def is_animated(ob):
    ad = ob.animation_data
    return ad is not None and ad.action is not None


def slide_check(context, d, new, surf):
    """Sliding along the same surface, a thing stops at whatever stands on it
    (it doesn't pass through a vase on the table). Moving onto another
    object is a lift: it goes straight there."""
    last = d.get("last")
    bumped = False
    if last is not None and d.get("surf") == surf:
        key = surf.name
        tree = d["trees"].get(key)
        if tree is None:
            tree = solid.obstacle_tree(context.scene, context.evaluated_depsgraph_get(), d["exclude"] | {surf})
            d["trees"][key] = tree
        if tree is not None:
            move = new.translation - last.translation
            pts = [last @ p for p in d["pts"]]
            allowed, bumped = solid.solve(pts, move, tree)
            if bumped:
                new = Matrix.Translation(allowed - move) @ new
    d["last"], d["surf"] = new.copy(), surf
    return new, bumped


# ------------------------------------------------------------------ stamping

def stamp_spacing(context, source):
    """How far apart painted copies go: the object's size times the spacing setting."""
    pts = ARR.get("_pts_" + source.name) or local_points(context, source)
    ARR["_pts_" + source.name] = pts
    sc = source.matrix_world.to_scale()
    xs = [p.x * sc.x for p in pts]
    ys = [p.y * sc.y for p in pts]
    size = max(max(xs) - min(xs), max(ys) - min(ys), 1e-3)
    return size * context.scene.stop_motion.stamp_spacing


def stamp(context, source, hit, normal, align, rng=None, vary=0.15, tree=None):
    """Place a linked copy of `source` on the surface. Returns the copy."""
    rng = rng or random
    copy = source.copy()            # shares the mesh: hundreds of flowers stay light
    if copy.animation_data is not None:
        copy.animation_data_clear()
    for col in source.users_collection:
        col.objects.link(copy)
    copy.stop_motion_set = True
    copy.stop_motion_prop = False
    k = 1.0 + rng.uniform(-vary, vary)
    base = source.matrix_world.copy()
    base = base @ Matrix.Diagonal((k, k, k, 1.0))
    pts = ARR.get("_pts_" + source.name) or local_points(context, source)
    ARR["_pts_" + source.name] = pts
    copy.matrix_world = placement(base, pts, hit, normal, align, rng.uniform(0, 2 * math.pi),
                                  Vector((0, 0, 1)), tree)
    ARR["count"] += 1
    return copy


# ---------------------------------------------------------- the arrange session

def _studio():
    from . import studio
    return studio


class SM_OT_arrange(bpy.types.Operator):
    """Arrange the set: drag objects along surfaces, or stamp copies onto them. Esc to stop"""
    bl_idname = "stop_motion.arrange"
    bl_label = "Arrange the Set"

    stamp_source: StringProperty(options={'SKIP_SAVE'})

    def invoke(self, context, event):
        if ARR["active"]:
            ARR["active"] = False   # a second press ends the running session
            return {'CANCELLED'}
        studio = _studio()
        if studio.is_active():
            self.area, self.region = studio.studio_area(context.window)
        else:
            self.area, self.region = context.area, context.region
        if self.region is None or self.area is None or self.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Arrange works in a 3D view")
            return {'CANCELLED'}
        ARR["active"] = True
        ARR["stamp"] = self.stamp_source
        ARR["count"] = 0
        self.drag = None
        self.paint = None
        context.window_manager.modal_handler_add(self)
        self._say(context, "Stamp: click or drag over surfaces to place copies · Esc to stop" if self.stamp_source
                  else "Arrange: drag an object along surfaces · wheel spins · Alt lean · Esc to stop")
        return {'RUNNING_MODAL'}

    # ---- helpers
    def _say(self, context, text):
        studio = _studio()
        if studio.is_active():
            studio.toast(text, 3.0)
            studio.redraw()
        elif self.area is not None:
            self.area.header_text_set(text)

    def _rv3d(self):
        return self.area.spaces.active.region_3d

    def _mouse(self, event):
        return Vector((event.mouse_x - self.region.x, event.mouse_y - self.region.y))

    def _in_view(self, context, m):
        if not (0 <= m.x < self.region.width and 0 <= m.y < self.region.height):
            return False
        studio = _studio()
        if studio.is_active():
            live = studio.live_rect()
            kit = studio.S.kit
            if live is None or not live.contains(m.x, m.y):
                return False
            if kit is not None and kit.over_ui(m.x, m.y):
                return False
        return True

    def _paint_at(self, context, m):
        pt = self.paint
        hit = self._hit(context, m, pt["exclude"])
        if hit is None:
            return
        if pt["last"] is not None and (hit[0] - pt["last"]).length < pt["spacing"]:
            return
        sm = context.scene.stop_motion
        stamp(context, pt["src"], hit[0], hit[1], sm.stick_align, vary=sm.stamp_vary, tree=pt["tree"])
        pt["last"] = hit[0].copy()
        pt["n"] += 1
        self._say(context, "%d placed · keep dragging · Esc to stop" % ARR["count"])

    def _hit(self, context, m, exclude):
        origin, direction = mouse_ray(self.region, self._rv3d(), m)
        return cast(context.scene, context.evaluated_depsgraph_get(), origin, direction, exclude)

    # ---- drag
    def _begin(self, context, ob):
        scene = context.scene
        dg = context.evaluated_depsgraph_get()
        exclude = {ob} | set(ob.children_recursive)
        pts = local_points(context, ob)
        world = [ob.matrix_world @ p for p in pts]
        self.drag = {
            "ob": ob, "start": ob.matrix_world.copy(), "pts": pts, "exclude": exclude,
            "n0": surface_frame(scene, dg, ob, world, exclude),
            "tree": solid.obstacle_tree(scene, dg, exclude),
            "spin": 0.0, "anchor": ob.matrix_world.translation.copy(),
            "last": None, "surf": None, "trees": {},
        }
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob

    def _update(self, context, event):
        d = self.drag
        m = self._mouse(event)
        align = context.scene.stop_motion.stick_align != event.alt
        if event.ctrl:   # free: follow the mouse in the view plane, no sticking
            here = view3d_utils.region_2d_to_location_3d(self.region, self._rv3d(), m, d["anchor"])
            d["ob"].matrix_world = Matrix.Translation(here - d["anchor"]) @ d["start"]
            return
        hit = self._hit(context, m, d["exclude"])
        if hit is None:
            return
        loc, normal, surf = hit
        new = placement(d["start"], d["pts"], loc, normal, align, d["spin"], d["n0"], d["tree"])
        new, bumped = slide_check(context, d, new, surf)
        d["ob"].matrix_world = new
        if bumped:
            self._say(context, "Bumped into something · move the mouse onto it to put it on top")

    def _finish_drag(self, context, cancel=False):
        d = self.drag
        self.drag = None
        if cancel:
            d["ob"].matrix_world = d["start"]
            return
        ob = d["ob"]
        if is_animated(ob) and not ob.stop_motion_set:
            self._say(context, "%s is part of the shots: moved for this shot. Make it a set piece to move it everywhere" % ob.name)
        bpy.ops.ed.undo_push(message="Arrange %s" % ob.name)

    # ---- events
    def modal(self, context, event):
        if not ARR["active"]:
            return self._end(context)
        t, v = event.type, event.value
        m = self._mouse(event)

        if t in {'ESC', 'RIGHTMOUSE'} and v == 'PRESS':
            if self.paint is not None:
                if self.paint["n"]:
                    bpy.ops.ed.undo_push(message="Stamp %d" % self.paint["n"])
                self.paint = None
                return {'RUNNING_MODAL'}
            if self.drag is not None:
                self._finish_drag(context, cancel=True)
                return {'RUNNING_MODAL'}
            return self._end(context)

        if self.drag is not None:
            if t in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'LEFT_ALT', 'RIGHT_ALT', 'LEFT_CTRL', 'RIGHT_CTRL'}:
                self._update(context, event)
                return {'RUNNING_MODAL'}
            if t in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                self.drag["spin"] += math.radians(15 if t == 'WHEELUPMOUSE' else -15)
                self._update(context, event)
                return {'RUNNING_MODAL'}
            if t == 'LEFTMOUSE' and v == 'RELEASE':
                self._finish_drag(context)
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if self.paint is not None:
            # painting copies: one every `spacing` along the stroke
            if t in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                self._paint_at(context, m)
                return {'RUNNING_MODAL'}
            if t == 'LEFTMOUSE' and v == 'RELEASE':
                n = self.paint["n"]
                self.paint = None
                if n:
                    bpy.ops.ed.undo_push(message="Stamp %d" % n)
                self._say(context, "%d placed · drag over surfaces to paint more · Esc to stop" % ARR["count"])
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if t == 'LEFTMOUSE' and v == 'PRESS' and self._in_view(context, m):
            scene = context.scene
            if ARR["stamp"]:
                src = bpy.data.objects.get(ARR["stamp"])
                if src is None:
                    return self._end(context)
                exclude = {src} | set(src.children_recursive)
                self.paint = {"src": src, "exclude": exclude, "last": None, "n": 0,
                              "tree": solid.obstacle_tree(scene, context.evaluated_depsgraph_get(), exclude),
                              "spacing": stamp_spacing(context, src)}
                self._paint_at(context, m)
                return {'RUNNING_MODAL'}
            hit = self._hit(context, m, ())
            if hit is not None:
                ob = root_of(hit[2])
                if arrangeable(scene, ob):
                    self._begin(context, ob)
                    return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}
        return {'PASS_THROUGH'}

    def _end(self, context):
        ARR["active"] = False
        ARR["stamp"] = ""
        for k in [k for k in ARR if k.startswith("_pts_")]:
            del ARR[k]
        studio = _studio()
        if studio.is_active():
            studio.toast("Arranging done", 1.5)
            studio.redraw()
        elif self.area is not None:
            self.area.header_text_set(None)
        return {'FINISHED'}


class SM_OT_stop_arrange(bpy.types.Operator):
    """Stop arranging or stamping"""
    bl_idname = "stop_motion.stop_arrange"
    bl_label = "Stop Arranging"

    def execute(self, context):
        ARR["active"] = False
        return {'FINISHED'}


class SM_OT_set_piece(bpy.types.Operator):
    """Set pieces stay where you put them in every shot and aren't keyed when you shoot"""
    bl_idname = "stop_motion.set_piece"
    bl_label = "Make Set Piece"
    bl_options = {'REGISTER', 'UNDO'}

    on: BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        n = 0
        for ob in context.selected_objects:
            if not arrangeable(context.scene, ob):
                continue
            ob.stop_motion_set = self.on
            if self.on and ob.animation_data is not None:
                world = ob.matrix_world.copy()
                ob.animation_data_clear()   # its old per-shot keys would pull it back
                ob.matrix_world = world
            n += 1
        self.report({'INFO'}, "%d set piece%s" % (n, "" if n == 1 else "s") if self.on else "%d back in the shots" % n)
        return {'FINISHED'}


classes = (SM_OT_arrange, SM_OT_stop_arrange, SM_OT_set_piece)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Object.stop_motion_set = BoolProperty(
        name="Set piece", default=False,
        description="Stays where you put it in every shot; not keyed when you shoot")


def unregister():
    ARR["active"] = False
    del bpy.types.Object.stop_motion_set
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
