# SPDX-License-Identifier: GPL-3.0-or-later
"""Solid world: things stop at surfaces instead of passing through them.

When the solid world is on, dragging a ring (or a prop) uses our own drag
instead of Blender's move tool. Each mouse move, the part's points are
pushed along the move; anything solid in the way stops them, and the rest
of the move slides along the surface they hit (so a foot dragged down and
sideways ends up sliding along the floor). Hold Ctrl while dragging to
pass through.

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


# -------------------------------------------------------------- solid drag

class SM_OT_solid_drag(bpy.types.Operator):
    """Drag a part or prop; it stops at anything solid. Ctrl: pass through. Esc/right-click: cancel"""
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
            self.anchor = ob.matrix_world.translation.copy()
            self.points = object_points(context, ob)
            exclude = {ob} | set(ob.children_recursive)
            self.start = ob.matrix_world.copy()
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
        self.tree = obstacle_tree(scene, dg, exclude)
        return True

    def _apply(self, move):
        if self.target_ob is not None:
            self.target_ob.matrix_world = Matrix.Translation(move) @ self.start
        else:
            m = self.start.copy()
            m.translation = m.translation + self.to_pose @ move
            self.target_bone.matrix = m

    def invoke(self, context, event):
        if context.region_data is None or not self._setup(context):
            return {'CANCELLED'}
        self.region = context.region
        self.rv3d = context.region_data
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('HAND')
        return {'RUNNING_MODAL'}

    def _finish(self, context, cancelled):
        context.window.cursor_modal_restore()
        context.area.header_text_set(None)
        if cancelled:
            self._apply(Vector((0, 0, 0)))
            return {'CANCELLED'}
        if self.target_ob is not None and is_prop(self.target_ob) and \
                getattr(self.target_ob, "stop_motion_falls", True):
            drop_to_surface(context, self.target_ob)
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            mouse = (event.mouse_region_x, event.mouse_region_y)
            here = view3d_utils.region_2d_to_location_3d(self.region, self.rv3d, mouse, self.anchor)
            want = here - self.anchor
            if event.ctrl:
                move, blocked = want, False
            else:
                move, blocked = solve(self.points, want, self.tree)
            self._apply(move)
            context.area.header_text_set(
                "Touching something solid · Ctrl to pass through" if blocked else
                "Drag · release to drop · Ctrl: pass through · Esc: cancel")
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value in {'RELEASE', 'PRESS'}:
            if event.type != 'LEFTMOUSE' or event.value == 'RELEASE':
                return self._finish(context, False)
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._finish(context, True)
        return {'RUNNING_MODAL'}


# -------------------------------------------------------------- solid twist

def _rotate_about(pivot, axis, angle):
    return Matrix.Translation(pivot) @ Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-pivot)


def twist_limit(points, pivot, axis, start, end, tree, eps=0.002, step_deg=2.0):
    """Turn `points` about `pivot`/`axis` from angle `start` toward `end`.

    Returns (allowed angle, blocked). Each small step is swept as straight
    segments; a step that would carry any point into a surface from its
    front stops the turn just short of it. Turning away from contact (out
    of a surface) is always free, like the solid drag."""
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
        if best is not None:
            return a + da * best, True
        a += da
        cur = nxt
    return a, False


class SM_OT_solid_twist(bpy.types.Operator):
    """Turn a part or prop around the view; it stops where it would touch something. Ctrl: pass through. Esc: cancel"""
    bl_idname = "stop_motion.solid_twist"
    bl_label = "Solid Twist"
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
        self.tree = obstacle_tree(scene, dg, exclude)
        return True

    def _apply(self, angle):
        R = _rotate_about(self.pivot, self.axis, angle)
        if self.ob is not None:
            self.ob.matrix_world = R @ self.start
        else:
            mw = self.arm.matrix_world
            self.pb.matrix = mw.inverted() @ R @ mw @ self.start

    def _screen_angle(self, event):
        import math
        m = (event.mouse_region_x - self.pivot2d.x, event.mouse_region_y - self.pivot2d.y)
        return math.atan2(m[1], m[0])

    def invoke(self, context, event):
        rv3d = context.region_data
        if rv3d is None or not self._setup(context):
            return {'CANCELLED'}
        p2 = view3d_utils.location_3d_to_region_2d(context.region, rv3d, self.pivot)
        if p2 is None:
            return {'CANCELLED'}
        self.pivot2d = p2
        self.axis = (rv3d.view_rotation @ Vector((0, 0, 1))).normalized()   # towards the viewer
        self.last_screen = self._screen_angle(event)
        self.want = 0.0      # where the mouse says
        self.angle = 0.0     # where the part is allowed to be
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('SCROLL_XY')
        return {'RUNNING_MODAL'}

    def _say(self, context, text):
        from . import studio
        if studio.is_active():
            studio.toast(text, 0.8)
            studio.redraw()
        elif context.area:
            context.area.header_text_set(text)

    def _finish(self, context, cancel):
        context.window.cursor_modal_restore()
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            self._apply(0.0)
            return {'CANCELLED'}
        if self.ob is not None and is_prop(self.ob) and getattr(self.ob, "stop_motion_falls", True) \
                and held_by(self.ob) is None:
            drop_to_surface(context, self.ob)   # a tipped prop settles back onto its surface
        return {'FINISHED'}

    def modal(self, context, event):
        import math
        if event.type == 'MOUSEMOVE':
            a = self._screen_angle(event)
            d = (a - self.last_screen + math.pi) % (2 * math.pi) - math.pi   # unwrap
            self.last_screen = a
            self.want += d * (0.25 if event.shift else 1.0)
            if event.ctrl:
                self.angle, blocked = self.want, False
            else:
                self.angle, blocked = twist_limit(self.points, self.pivot, self.axis, self.angle, self.want, self.tree)
            self._apply(self.angle)
            self._say(context, "Touching something solid · Ctrl to pass through" if blocked
                      else "Turn · Shift: fine · Ctrl: pass through · Esc: cancel")
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
    """Drag to move this prop. Alt+drag to turn it"""
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
        solid_on = context.scene.stop_motion.solid_world and held_by(ob) is None
        if event.alt:
            if solid_on:
                bpy.ops.stop_motion.solid_twist('INVOKE_DEFAULT', prop=ob.name)
            else:
                bpy.ops.transform.rotate('INVOKE_DEFAULT', release_confirm=True)
        elif solid_on:
            bpy.ops.stop_motion.solid_drag('INVOKE_DEFAULT', prop=ob.name)
        else:
            bpy.ops.transform.translate('INVOKE_DEFAULT', release_confirm=True)
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
    del bpy.types.Object.stop_motion_falls
    del bpy.types.Object.stop_motion_solid
    del bpy.types.Object.stop_motion_prop
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
