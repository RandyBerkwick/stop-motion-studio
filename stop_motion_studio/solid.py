# SPDX-License-Identifier: GPL-3.0-or-later
"""Solid world: things stop at surfaces instead of passing through them.

When the solid world is on, dragging a ring (or a prop) uses our own drag
instead of Blender's move tool. Each mouse move, the part's points are
pushed along the move; anything solid in the way stops them, and the rest
of the move slides along the surface they hit (so a foot dragged down and
sideways ends up sliding along the floor). Hold Ctrl while dragging to
pass through.

Dragging and turning are full 3D: Shift (or the wheel) pushes a part
further away or nearer, X/Y/Z keep it to one direction; turning rolls it
like a ball, or round one axis (X/Y/Z) or the view (V). With the solid
world off the same tools just don't stop at surfaces.

Solid = every visible mesh, except the thing being moved (and, for a
puppet, its own body). Untick "Solid" on an object to let things pass.

Props are objects you mark as props: they get a ring, fall onto whatever
is under them when let go, and can be held in a puppet's hand.
"""

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import puppet

HOLD_PREFIX = "SM Hold "
MAX_POINTS = 240


# --------------------------------------------------------------- obstacles

def obstacle_tree(scene, depsgraph, exclude):
    """One BVH of every solid, visible mesh not in `exclude`, in world space."""
    verts, polys = [], []
    for ob in scene.objects:
        if ob.type != 'MESH' or ob in exclude or not ob.visible_get():
            continue
        if not getattr(ob, "stop_motion_solid", True):
            continue
        ob_eval = ob.evaluated_get(depsgraph)
        me = ob_eval.to_mesh()
        try:
            base = len(verts)
            mw = ob_eval.matrix_world
            verts.extend(mw @ v.co for v in me.vertices)
            polys.extend(tuple(base + i for i in p.vertices) for p in me.polygons)
        finally:
            ob_eval.to_mesh_clear()
    if not polys:
        return None
    return BVHTree.FromPolygons(verts, polys)


def solve(points, move, tree, eps=0.002, slide=True, iterations=3, step=0.08, max_steps=16):
    """Like solve_once, but in small steps, so a part that slides off an
    edge carries on moving the way it was pushed (off the table, down to
    the floor) instead of gliding on at the height of the edge."""
    if tree is None or not points or not slide:
        return solve_once(points, move, tree, eps, slide, iterations)
    import math
    n = max(1, min(max_steps, int(math.ceil(move.length / step))))
    part = move / n
    total = Vector((0.0, 0.0, 0.0))
    blocked = False
    for _ in range(n):
        moved = [p + total for p in points]
        m, b = solve_once(moved, part, tree, eps, slide, iterations)
        total += m
        blocked = blocked or b
    return total, blocked


def solve_once(points, move, tree, eps=0.002, slide=True, iterations=3):
    """How far `points` can go along `move` without entering anything.

    Returns (allowed_move, blocked). Hits are only counted when a point
    enters a surface from its front, so a part that starts slightly inside
    something can always move back out."""
    if tree is None or not points:
        return move.copy(), False
    total = Vector((0.0, 0.0, 0.0))
    remaining = move.copy()
    blocked = False
    for _ in range(iterations):
        length = remaining.length
        if length < 1e-9:
            break
        direction = remaining / length
        best, best_n = length + eps, None
        for p in points:
            loc, normal, _i, dist = tree.ray_cast(p + total, direction, length + eps)
            if loc is not None and normal.dot(direction) < 0.0 and dist <= best:
                best, best_n = dist, normal
        if best_n is None:
            total += remaining
            break
        step = max(0.0, best - eps)
        total += direction * step
        blocked = True
        if not slide:
            break
        left = remaining - direction * step
        remaining = left - best_n * left.dot(best_n)  # keep only the sideways part
    return total, blocked


# ----------------------------------------------------------- moving points

def _subtree(arm, root):
    out, stack = set(), [arm.data.bones[root]]
    while stack:
        b = stack.pop()
        out.add(b.name)
        stack.extend(b.children)
    return out


def _pinned_chain_bones(arm):
    """Bones whose shape is decided by a pin (they bend, not move rigidly)."""
    out = set()
    for r in arm.stop_motion_puppet.rings:
        c = puppet.pin_constraint(arm, r)
        if c is not None and c.influence > 0.5:
            owner = arm.data.bones[r.pin_owner]
            out.add(owner.name)
            if owner.parent:
                out.add(owner.parent.name)
            out |= _subtree(arm, r.bone)
    return out


def _thin(points):
    if len(points) <= MAX_POINTS:
        return points
    step = len(points) / MAX_POINTS
    return [points[int(i * step)] for i in range(MAX_POINTS)]


def ring_points(context, arm, ring, moving_bone, exclude_pinned=True):
    """World points of everything that moves rigidly with `moving_bone`.

    Pinned legs bend rather than move rigidly when the body moves, so they
    are left out of a body drag (exclude_pinned); a pinned foot's own drag
    keeps them."""
    dg = context.evaluated_depsgraph_get()
    scene = context.scene
    bones = _subtree(arm, moving_bone)
    if exclude_pinned:
        bones -= _pinned_chain_bones(arm)
    pts = []
    for ob in puppet.puppet_meshes(arm, scene):
        if not ob.visible_get():
            continue
        ob_eval = ob.evaluated_get(dg)
        if ob.parent_type == 'BONE' and ob.parent == arm:
            if ob.parent_bone in bones:
                me = ob_eval.to_mesh()
                pts.extend(ob_eval.matrix_world @ v.co for v in me.vertices)
                ob_eval.to_mesh_clear()
            continue
        names = {g.index: g.name for g in ob.vertex_groups}
        me = ob_eval.to_mesh()
        try:
            same = len(me.vertices) == len(ob.data.vertices)
            for i, v in enumerate(ob.data.vertices):
                if not v.groups:
                    continue
                g = max(v.groups, key=lambda e: e.weight)
                if names.get(g.group) in bones:
                    co = me.vertices[i].co if same else v.co
                    pts.append(ob_eval.matrix_world @ co)
        finally:
            ob_eval.to_mesh_clear()
    return _thin(pts)


def object_points(context, ob):
    dg = context.evaluated_depsgraph_get()
    pts = []
    for o in [ob] + [c for c in ob.children_recursive if c.type == 'MESH']:
        if o.type != 'MESH' or not o.visible_get():
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        pts.extend(oe.matrix_world @ v.co for v in me.vertices)
        oe.to_mesh_clear()
    return _thin(pts)


def own_meshes(scene, arm):
    return set(puppet.puppet_meshes(arm, scene))


# ------------------------------------------------------------------- props

def is_prop(ob):
    return getattr(ob, "stop_motion_prop", False)


def props(scene):
    return [ob for ob in scene.objects if is_prop(ob)]


def world_matrix(context, ob):
    """Where the object really is now (constraints, parents, IK included)."""
    context.view_layer.update()
    return ob.evaluated_get(context.evaluated_depsgraph_get()).matrix_world.copy()


def bone_world(context, arm, bone):
    context.view_layer.update()
    ae = arm.evaluated_get(context.evaluated_depsgraph_get())
    return ae.matrix_world @ ae.pose.bones[bone].matrix


def hold_constraints(ob):
    return [c for c in ob.constraints if c.name.startswith(HOLD_PREFIX)]


def held_by(ob):
    for c in hold_constraints(ob):
        if c.influence > 0.5:
            return c
    return None


def drop_to_surface(context, ob, eps=0.002):
    """Let a prop fall onto whatever is under it. Returns the drop distance."""
    if held_by(ob) is not None:
        return 0.0
    scene = context.scene
    dg = context.evaluated_depsgraph_get()
    pts = object_points(context, ob)
    exclude = {ob} | set(ob.children_recursive)
    tree = obstacle_tree(scene, dg, exclude)
    if tree is None or not pts:
        return 0.0
    lowest = min(p.z for p in pts)
    band = [p for p in pts if p.z < lowest + 0.25 * (max(p.z for p in pts) - lowest + 1e-6)]
    move, blocked = solve(band or pts, Vector((0, 0, -100.0)), tree, eps, slide=False, iterations=1)
    if not blocked:
        return 0.0  # nothing underneath: leave it where it is
    world = world_matrix(context, ob)
    ob.matrix_world = Matrix.Translation(move) @ world
    return -move.z


def nearest_hand(scene, ob, context=None):
    best = None
    pos = (world_matrix(context, ob) if context else ob.matrix_world).translation
    for arm in puppet.puppets(scene):
        for r in arm.stop_motion_puppet.rings:
            if "hand" not in r.label.lower():
                continue
            pb = arm.pose.bones.get(r.bone)
            if pb is None:
                continue
            tail = (bone_world(context, arm, r.bone) @ Vector((0, pb.length, 0))) if context \
                else arm.matrix_world @ pb.tail
            d = (tail - pos).length
            if best is None or d < best[0]:
                best = (d, arm, r.bone)
    return best


def hold(context, ob, arm, bone):
    """Put the prop in the hand: it follows the hand from now on, no jump."""
    world = world_matrix(context, ob)
    name = HOLD_PREFIX + bone
    c = ob.constraints.get(name)
    if c is None:
        c = ob.constraints.new('CHILD_OF')
        c.name = name
        c.target = arm
        c.subtarget = bone
        c.inverse_matrix = bone_world(context, arm, bone).inverted()
        c.influence = 0.0
    for other in hold_constraints(ob):
        other.influence = 0.0
    # Keep the first inverse (it isn't animatable); fit the prop's own transform instead.
    parent = bone_world(context, arm, bone)
    ob.matrix_basis = c.inverse_matrix.inverted() @ parent.inverted() @ world
    c.influence = 1.0
    context.view_layer.update()


def let_go(context, ob):
    world = world_matrix(context, ob)
    for c in hold_constraints(ob):
        c.influence = 0.0
    ob.matrix_basis = world
    context.view_layer.update()


# ------------------------------------------------------- shared 3D helpers

AXES = {'X': Vector((1.0, 0.0, 0.0)), 'Y': Vector((0.0, 1.0, 0.0)), 'Z': Vector((0.0, 0.0, 1.0))}
AXIS_COLORS = {'X': (1.0, 0.35, 0.35, 0.95), 'Y': (0.55, 0.9, 0.35, 0.95),
               'Z': (0.4, 0.62, 1.0, 0.95), 'VIEW': (1.0, 0.8, 0.35, 0.95)}
AXIS_WORDS = {'X': "side to side (X)", 'Y': "front to back (Y)", 'Z': "up and down (Z)", 'VIEW': "around the view"}


def view_frame(rv3d):
    """(right, up, toward viewer, eye) of a 3D view, in world space."""
    vi = rv3d.view_matrix.inverted()
    right = vi.col[0].xyz.normalized()
    up = vi.col[1].xyz.normalized()
    back = vi.col[2].xyz.normalized()
    return right, up, back, vi.translation.copy()


def axis_point(origin, direction, anchor, axis):
    """The point on the line anchor + t·axis closest to the ray origin + s·direction."""
    w0 = anchor - origin
    a, b, c = axis.dot(axis), axis.dot(direction), direction.dot(direction)
    d, e = axis.dot(w0), direction.dot(w0)
    den = a * c - b * b
    if abs(den) < 1e-9:
        return anchor.copy()      # looking straight down the axis
    return anchor + axis * ((b * e - c * d) / den)


def _first_hit(cur, nxt, tree, eps):
    """Smallest fraction of the step cur→nxt at which any point enters a surface from its front."""
    best = None
    for p0, p1 in zip(cur, nxt):
        seg = p1 - p0
        length = seg.length
        if length < 1e-9:
            continue
        d = seg / length
        loc, normal, _i, dist = tree.ray_cast(p0, d, length + eps)
        if loc is not None and normal.dot(d) < 0.0:
            frac = max(0.0, (dist - eps) / length)
            best = frac if best is None else min(best, frac)
    return best


def turn_limit(points, pivot, q_from, q_to, tree, eps=0.002, step_deg=2.0):
    """Turn `points` about `pivot` from rotation q_from toward q_to (any 3D turn).

    Returns (allowed rotation, blocked). The turn is swept in steps of at
    most `step_deg`; the first step that would carry a point into a surface
    from its front stops just short of it. Turning out of contact is free."""
    import math
    if tree is None or not points:
        return q_to.copy(), False
    ang = q_from.rotation_difference(q_to).angle
    if ang < 1e-9:
        return q_to.copy(), False
    n = max(1, int(math.ceil(ang / math.radians(step_deg))))
    rel = [p - pivot for p in points]
    cur = [pivot + q_from @ r for r in rel]
    for i in range(1, n + 1):
        q = q_from.slerp(q_to, i / n)
        nxt = [pivot + q @ r for r in rel]
        f = _first_hit(cur, nxt, tree, eps)
        if f is not None:
            return q_from.slerp(q_to, (i - 1 + f) / n), True
        cur = nxt
    return q_to.copy(), False


def _rotate_about(pivot, axis, angle):
    return Matrix.Translation(pivot) @ Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-pivot)


def twist_limit(points, pivot, axis, start, end, tree, eps=0.002, step_deg=2.0):
    """Turn `points` about one axis from angle `start` toward `end`.
    Returns (allowed angle, blocked); see turn_limit."""
    import math
    if tree is None or not points or abs(end - start) < 1e-9:
        return end, False
    axis = axis.normalized()
    n = max(1, int(math.ceil(abs(end - start) / math.radians(step_deg))))
    da = (end - start) / n
    a = start
    rel = [p - pivot for p in points]
    rot_a = Matrix.Rotation(a, 3, axis)
    cur = [pivot + rot_a @ r for r in rel]
    for _ in range(n):
        rot_b = Matrix.Rotation(a + da, 3, axis)
        nxt = [pivot + rot_b @ r for r in rel]
        f = _first_hit(cur, nxt, tree, eps)
        if f is not None:
            return a + da * f, True
        a += da
        cur = nxt
    return a, False


# ------------------------------------------------------- axis line drawing

_GUIDE = {"handle": None, "origin": None, "axis": None, "color": None}


def _draw_guide():
    if _GUIDE["origin"] is None:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    o, a = _GUIDE["origin"], _GUIDE["axis"]
    sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'LINES', {"pos": [o - a * 50.0, o + a * 50.0]})
    region = bpy.context.region
    gpu.state.blend_set('ALPHA')
    sh.bind()
    sh.uniform_float("viewportSize", (region.width, region.height))
    sh.uniform_float("lineWidth", 2.0)
    sh.uniform_float("color", _GUIDE["color"])
    batch.draw(sh)
    gpu.state.blend_set('NONE')


def show_guide(origin, axis_name, axis=None):
    if axis_name is None:
        hide_guide()
        return
    _GUIDE["origin"] = origin.copy()
    _GUIDE["axis"] = (axis if axis is not None else AXES[axis_name]).normalized()
    _GUIDE["color"] = AXIS_COLORS[axis_name]
    if _GUIDE["handle"] is None:
        _GUIDE["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw_guide, (), 'WINDOW', 'POST_VIEW')
    _redraw_views()


def hide_guide():
    _GUIDE["origin"] = None
    if _GUIDE["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_GUIDE["handle"], 'WINDOW')
        _GUIDE["handle"] = None
    _redraw_views()


def _redraw_views():
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", ()):
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _say(context, text):
    from . import studio
    if studio.is_active():
        studio.toast(text, 0.8)
        studio.redraw()
    elif context.area:
        context.area.header_text_set(text)


def _axis_key(event):
    if event.value == 'PRESS' and event.type in {'X', 'Y', 'Z'} and not (event.ctrl or event.oskey):
        return event.type
    return None


# -------------------------------------------------------------- solid drag

class SM_OT_solid_drag(bpy.types.Operator):
    """Drag a part or prop in 3D. Shift (or the wheel): further away / nearer. X/Y/Z: along one axis.
    With the solid world on it stops at anything solid; Ctrl passes through. Esc/right-click: cancel"""
    bl_idname = "stop_motion.solid_drag"
    bl_label = "Solid Drag"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    puppet: StringProperty()
    ring: IntProperty(default=-1)
    prop: StringProperty()

    def _setup(self, context):
        scene = context.scene
        dg = context.evaluated_depsgraph_get()
        self.target_ob = None
        self.target_bone = None
        if self.prop:
            ob = bpy.data.objects.get(self.prop)
            if ob is None:
                return False
            self.target_ob = ob
            self.start = world_matrix(context, ob)
            self.anchor = self.start.translation.copy()
            self.points = object_points(context, ob)
            exclude = {ob} | set(ob.children_recursive)
        else:
            arm = bpy.data.objects.get(self.puppet)
            if arm is None or not (0 <= self.ring < len(arm.stop_motion_puppet.rings)):
                return False
            ring = arm.stop_motion_puppet.rings[self.ring]
            self.arm = arm
            exclude = own_meshes(scene, arm)
            if ring.pin is not None and puppet.is_pinned(arm, ring):
                self.target_ob = ring.pin
                self.anchor = ring.pin.matrix_world.translation.copy()
                self.start = ring.pin.matrix_world.copy()
                self.points = ring_points(context, arm, ring, ring.bone, exclude_pinned=False)
            else:
                pb = arm.pose.bones[ring.bone]
                self.target_bone = pb
                self.anchor = arm.matrix_world @ pb.head
                self.start = pb.matrix.copy()
                self.to_pose = arm.matrix_world.to_3x3().inverted()
                self.points = ring_points(context, arm, ring, ring.bone)
        self.solid = scene.stop_motion.solid_world
        self.tree = obstacle_tree(scene, dg, exclude) if self.solid else None
        return True

    def _apply(self, move):
        if self.target_ob is not None:
            self.target_ob.matrix_world = Matrix.Translation(move) @ self.start
        else:
            m = self.start.copy()
            m.translation = m.translation + self.to_pose @ move
            self.target_bone.matrix = m

    # -- where the mouse says the part should go (a move from the start)
    def _ray_dir(self, point):
        _r, _u, back, eye = view_frame(self.rv3d)
        if self.rv3d.is_perspective:
            d = point - eye
            if d.length > 1e-6:
                return d.normalized()
        return -back

    def _here(self, mouse, depth_point):
        return view3d_utils.region_2d_to_location_3d(self.region, self.rv3d, mouse, depth_point)

    def wanted(self):
        """The move the mouse asks for, from the drag's start."""
        origin = self.anchor + self.base
        if self.lock:
            axis = AXES[self.lock]
            _r, _u, back, _e = view_frame(self.rv3d)
            facing = axis.dot(back)
            if abs(facing) > 0.6:
                # the axis points at you: the mouse can't follow it, so up/down pushes along it
                away = -1.0 if facing > 0 else 1.0
                return self.base + axis * (away * (self.eff.y - self.press.y) * self._step_depth() * 0.002)
            def t(mouse):
                o = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d, mouse)
                v = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d, mouse)
                return (axis_point(o, v, origin, axis) - origin).dot(axis)
            return self.base + axis * (t(self.eff) - t(self.press))
        target = origin + self._ray_dir(origin) * self.depth
        return self.base + (self._here(self.eff, target) - self._here(self.press, target)) + (target - origin)

    def _rebase(self):
        """Keep where the part is now, and measure the next movement from here."""
        self.base = self.move.copy()
        self.press = self.eff.copy()
        self.depth = 0.0

    def _step_depth(self):
        _r, _u, _b, eye = view_frame(self.rv3d)
        dist = ((self.anchor + self.base) - eye).length if self.rv3d.is_perspective else self.rv3d.view_distance
        return max(0.01, dist)

    def invoke(self, context, event):
        if context.region_data is None or not self._setup(context):
            return {'CANCELLED'}
        self.region = context.region
        self.rv3d = context.region_data
        m = Vector((event.mouse_region_x, event.mouse_region_y))
        self.press, self.eff, self.last = m.copy(), m.copy(), m.copy()
        self.base = Vector((0.0, 0.0, 0.0))
        self.move = Vector((0.0, 0.0, 0.0))
        self.depth = 0.0
        self.lock = None
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('HAND')
        self._hint(context, False)
        return {'RUNNING_MODAL'}

    def _hint(self, context, blocked):
        if blocked:
            _say(context, "Touching something solid · Ctrl to pass through")
        elif self.lock:
            _say(context, "Moving %s only · %s again: free" % (AXIS_WORDS[self.lock], self.lock))
        else:
            _say(context, "Drag · Shift or wheel: further / nearer · X Y Z: one direction · Esc: cancel")

    def _update(self, context, event):
        want = self.wanted()
        if event.ctrl or self.tree is None:
            self.move, blocked = want, False
        else:
            self.move, blocked = solve(self.points, want, self.tree)
        self._apply(self.move)
        self._hint(context, blocked)

    def _finish(self, context, cancelled):
        hide_guide()
        context.window.cursor_modal_restore()
        if context.area:
            context.area.header_text_set(None)
        if cancelled:
            self._apply(Vector((0, 0, 0)))
            return {'CANCELLED'}
        if self.solid and self.target_ob is not None and is_prop(self.target_ob) and \
                getattr(self.target_ob, "stop_motion_falls", True):
            drop_to_surface(context, self.target_ob)
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            m = Vector((event.mouse_region_x, event.mouse_region_y))
            delta = m - self.last
            self.last = m
            if event.shift and not self.lock:
                # Shift: up/down pushes it away from you / pulls it nearer, it stays put on screen
                self.depth += delta.y * self._step_depth() * 0.002
            else:
                self.eff = self.eff + delta
            self._update(context, event)
            return {'RUNNING_MODAL'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and not self.lock:
            self.depth += (1 if event.type == 'WHEELUPMOUSE' else -1) * self._step_depth() * 0.05
            self._update(context, event)
            return {'RUNNING_MODAL'}
        key = _axis_key(event)
        if key:
            self._rebase()
            self.lock = None if self.lock == key else key
            if self.lock:
                show_guide(self.anchor + self.base, self.lock)
            else:
                hide_guide()
            self._update(context, event)
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value in {'RELEASE', 'PRESS'}:
            if event.type != 'LEFTMOUSE' or event.value == 'RELEASE':
                return self._finish(context, False)
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._finish(context, True)
        return {'RUNNING_MODAL'}


# -------------------------------------------------------------- solid turn

class SM_OT_solid_twist(bpy.types.Operator):
    """Turn a part or prop in 3D, like rolling a ball. X/Y/Z: around one axis, V: around the view.
    With the solid world on it stops where it would touch something; Ctrl passes through. Esc: cancel"""
    bl_idname = "stop_motion.solid_twist"
    bl_label = "Solid Turn"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    puppet: StringProperty()
    ring: IntProperty(default=-1)
    prop: StringProperty()

    def _setup(self, context):
        scene = context.scene
        dg = context.evaluated_depsgraph_get()
        self.ob = None
        self.pb = None
        if self.prop:
            ob = bpy.data.objects.get(self.prop)
            if ob is None:
                return False
            self.ob = ob
            self.start = world_matrix(context, ob)
            pts = object_points(context, ob)
            self.pivot = (sum(pts, Vector((0, 0, 0))) / len(pts)) if pts else self.start.translation.copy()
            exclude = {ob} | set(ob.children_recursive)
        else:
            arm = bpy.data.objects.get(self.puppet)
            if arm is None or not (0 <= self.ring < len(arm.stop_motion_puppet.rings)):
                return False
            ring = arm.stop_motion_puppet.rings[self.ring]
            pb = arm.pose.bones.get(ring.bone)
            if pb is None:
                return False
            self.arm, self.pb = arm, pb
            self.start = pb.matrix.copy()
            self.pivot = arm.matrix_world @ pb.head
            pts = ring_points(context, arm, ring, ring.bone, exclude_pinned=(ring.pin is None))
            exclude = own_meshes(scene, arm)
        self.points = pts
        self.solid = scene.stop_motion.solid_world
        self.tree = obstacle_tree(scene, dg, exclude) if self.solid else None
        return True

    def _apply(self, q):
        R = Matrix.Translation(self.pivot) @ q.to_matrix().to_4x4() @ Matrix.Translation(-self.pivot)
        if self.ob is not None:
            self.ob.matrix_world = R @ self.start
        else:
            mw = self.arm.matrix_world
            self.pb.matrix = mw.inverted() @ R @ mw @ self.start

    def _screen_angle(self, m):
        import math
        return math.atan2(m.y - self.pivot2d.y, m.x - self.pivot2d.x)

    def _axis(self):
        if self.mode == 'VIEW':
            return view_frame(self.rv3d)[2]
        return AXES[self.mode]

    def turn_for(self, delta, m, fine):
        """The extra turn (a Quaternion) a mouse movement asks for."""
        import math
        from mathutils import Quaternion
        k = 0.01 * (0.25 if fine else 1.0)     # radians per pixel
        right, up, back, _eye = view_frame(self.rv3d)
        if self.mode == 'BALL':
            axis = up * delta.x - right * delta.y
            if axis.length < 1e-9:
                return Quaternion()
            return Quaternion(axis.normalized(), delta.length * k)
        axis = self._axis()
        facing = axis.dot(back)
        a = self._screen_angle(m)
        if abs(facing) > 0.35:
            # the axis points at you (or away): turn by going round the part on screen
            d = (a - self.last_screen + math.pi) % (2 * math.pi) - math.pi
            angle = d * (1.0 if facing > 0 else -1.0) * (0.25 if fine else 1.0)
        else:
            # the axis lies across the screen: push across it
            p0 = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, self.pivot)
            p1 = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, self.pivot + axis)
            if p0 is None or p1 is None or (p1 - p0).length < 1e-6:
                return Quaternion()
            s = (p1 - p0).normalized()
            across = Vector((-s.y, s.x))
            angle = -(delta.x * across.x + delta.y * across.y) * k
        return Quaternion(axis, angle)

    def invoke(self, context, event):
        from mathutils import Quaternion
        rv3d = context.region_data
        if rv3d is None or not self._setup(context):
            return {'CANCELLED'}
        self.region, self.rv3d = context.region, rv3d
        p2 = view3d_utils.location_3d_to_region_2d(context.region, rv3d, self.pivot)
        if p2 is None:
            return {'CANCELLED'}
        self.pivot2d = p2
        m = Vector((event.mouse_region_x, event.mouse_region_y))
        self.last = m
        self.last_screen = self._screen_angle(m)
        self.q = Quaternion()     # the turn so far (allowed)
        self.mode = 'BALL'
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('SCROLL_XY')
        self._hint(context, False)
        return {'RUNNING_MODAL'}

    def _hint(self, context, blocked):
        if blocked:
            _say(context, "Touching something solid · Ctrl to pass through")
        elif self.mode == 'BALL':
            _say(context, "Turn like a ball · X Y Z: one axis · V: around the view · Shift: fine · Esc: cancel")
        else:
            _say(context, "Turning %s · %s again: free" % (AXIS_WORDS[self.mode], self.mode[0]))

    def _finish(self, context, cancel):
        from mathutils import Quaternion
        hide_guide()
        context.window.cursor_modal_restore()
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            self._apply(Quaternion())
            return {'CANCELLED'}
        if self.solid and self.ob is not None and is_prop(self.ob) and \
                getattr(self.ob, "stop_motion_falls", True) and held_by(self.ob) is None:
            drop_to_surface(context, self.ob)   # a tipped prop settles back onto its surface
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            m = Vector((event.mouse_region_x, event.mouse_region_y))
            delta = m - self.last
            dq = self.turn_for(delta, m, event.shift)
            self.last = m
            self.last_screen = self._screen_angle(m)
            want = dq @ self.q
            if event.ctrl or self.tree is None:
                self.q, blocked = want, False
            else:
                self.q, blocked = turn_limit(self.points, self.pivot, self.q, want, self.tree)
            self._apply(self.q)
            self._hint(context, blocked)
            return {'RUNNING_MODAL'}
        key = _axis_key(event) or ('VIEW' if event.type == 'V' and event.value == 'PRESS' else None)
        if key:
            self.mode = 'BALL' if self.mode == key else key
            if self.mode == 'BALL':
                hide_guide()
            else:
                show_guide(self.pivot, self.mode, self._axis())
            self._hint(context, False)
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value in {'RELEASE', 'PRESS'}:
            if event.type != 'LEFTMOUSE' or event.value == 'RELEASE':
                return self._finish(context, False)
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._finish(context, True)
        return {'RUNNING_MODAL'}


# ---------------------------------------------------------------- operators

class SM_OT_make_prop(bpy.types.Operator):
    """Make the selected objects props: they get a grab ring, land on surfaces and can be held"""
    bl_idname = "stop_motion.make_prop"
    bl_label = "Make Prop"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type in {'MESH', 'EMPTY'} for o in context.selected_objects)

    def execute(self, context):
        n = 0
        for ob in context.selected_objects:
            if ob.type in {'MESH', 'EMPTY'} and not (ob.parent and ob.parent.type == 'ARMATURE'):
                ob.stop_motion_prop = True
                n += 1
        self.report({'INFO'}, "%d prop%s" % (n, "" if n == 1 else "s"))
        return {'FINISHED'}


class SM_OT_unprop(bpy.types.Operator):
    """Stop treating this object as a prop"""
    bl_idname = "stop_motion.unprop"
    bl_label = "Not a Prop"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is not None:
            ob.stop_motion_prop = False
        return {'FINISHED'}


class SM_OT_drop_prop(bpy.types.Operator):
    """Let this prop fall onto whatever is under it"""
    bl_idname = "stop_motion.drop_prop"
    bl_label = "Drop to Surface"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        d = drop_to_surface(context, ob)
        if d <= 0 and held_by(ob) is None:
            self.report({'INFO'}, "Already resting (or nothing underneath)")
        return {'FINISHED'}


class SM_OT_hold_prop(bpy.types.Operator):
    """Put this prop in the nearest puppet hand"""
    bl_idname = "stop_motion.hold_prop"
    bl_label = "Hold"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        found = nearest_hand(context.scene, ob, context)
        if found is None:
            self.report({'WARNING'}, "No puppet hand to hold it (make a puppet first)")
            return {'CANCELLED'}
        _d, arm, bone = found
        hold(context, ob, arm, bone)
        self.report({'INFO'}, "%s is holding %s" % (arm.name, ob.name))
        return {'FINISHED'}


class SM_OT_let_go(bpy.types.Operator):
    """Let go of this prop: it stays where it is"""
    bl_idname = "stop_motion.let_go"
    bl_label = "Let Go"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        let_go(context, ob)
        if getattr(ob, "stop_motion_falls", True):
            drop_to_surface(context, ob)
        return {'FINISHED'}


class SM_OT_grab_prop(bpy.types.Operator):
    """Drag to move this prop (Shift: nearer/further). Alt+drag to turn it in 3D"""
    bl_idname = "stop_motion.grab_prop"
    bl_label = "Grab Prop"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def invoke(self, context, event):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        if held_by(ob) is not None:
            # in a hand: Blender's own tools move it relative to the hand
            if event.alt:
                bpy.ops.transform.rotate('INVOKE_DEFAULT', release_confirm=True)
            else:
                bpy.ops.transform.translate('INVOKE_DEFAULT', release_confirm=True)
        elif event.alt:
            bpy.ops.stop_motion.solid_twist('INVOKE_DEFAULT', prop=ob.name)
        else:
            bpy.ops.stop_motion.solid_drag('INVOKE_DEFAULT', prop=ob.name)
        return {'FINISHED'}


classes = (SM_OT_solid_drag, SM_OT_solid_twist, SM_OT_make_prop, SM_OT_unprop, SM_OT_drop_prop,
           SM_OT_hold_prop, SM_OT_let_go, SM_OT_grab_prop)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Object.stop_motion_prop = BoolProperty(name="Prop", default=False)
    bpy.types.Object.stop_motion_solid = BoolProperty(
        name="Solid", default=True, description="Puppets and props stop at this object instead of passing through")
    bpy.types.Object.stop_motion_falls = BoolProperty(
        name="Falls onto surfaces", default=True, description="When you let go, it drops onto whatever is under it")


def unregister():
    try:
        hide_guide()
    except Exception:
        pass
    del bpy.types.Object.stop_motion_falls
    del bpy.types.Object.stop_motion_solid
    del bpy.types.Object.stop_motion_prop
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
