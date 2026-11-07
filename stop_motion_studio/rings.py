# SPDX-License-Identifier: GPL-3.0-or-later
"""Grab rings in the free view. Drag a ring to move that part; Alt+drag
twists it. Bones that can't move on their own (joined to their parent,
like most heads) twist on a plain drag. Rings never show in the camera view."""

import bpy
from bpy.props import IntProperty, StringProperty
from mathutils import Matrix

from . import puppet, solid

RING_COLOR = (0.49, 0.77, 1.0)
PIN_COLOR = (0.96, 0.78, 0.30)
HOT_COLOR = (1.0, 0.42, 0.24)
PROP_COLOR = (0.62, 0.85, 0.55)


def ring_world_position(arm, ring):
    if ring.pin is not None and puppet.is_pinned(arm, ring):
        return ring.pin.matrix_world.translation.copy()
    pb = arm.pose.bones.get(ring.bone)
    if pb is None:
        return None
    return arm.matrix_world @ pb.head


def _inside(region, rv3d, pos, box):
    """In the Studio, rings outside the live box would draw over its panels."""
    if box is None:
        return True
    from bpy_extras import view3d_utils
    p2 = view3d_utils.location_3d_to_region_2d(region, rv3d, pos)
    return p2 is not None and box.contains(p2.x, p2.y)


class SM_OT_grab_ring(bpy.types.Operator):
    """Drag to move this part. Alt+drag to twist it"""
    bl_idname = "stop_motion.grab_ring"
    bl_label = "Grab Ring"
    bl_options = {'REGISTER', 'UNDO'}

    puppet: StringProperty()
    ring: IntProperty()

    def invoke(self, context, event):
        arm = bpy.data.objects.get(self.puppet)
        if arm is None:
            return {'CANCELLED'}
        rings = arm.stop_motion_puppet.rings
        if not (0 <= self.ring < len(rings)):
            return {'CANCELLED'}
        ring = rings[self.ring]
        twist = event.alt
        vl = context.view_layer

        solid_world = context.scene.stop_motion.solid_world
        if ring.pin is not None and puppet.is_pinned(arm, ring) and not twist:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            for ob in context.selected_objects:
                ob.select_set(False)
            ring.pin.select_set(True)
            vl.objects.active = ring.pin
            if solid_world:
                bpy.ops.stop_motion.solid_drag('INVOKE_DEFAULT', puppet=arm.name, ring=self.ring)
            else:
                bpy.ops.transform.translate('INVOKE_DEFAULT', release_confirm=True)
            return {'FINISHED'}

        pb = arm.pose.bones.get(ring.bone)
        if pb is None:
            return {'CANCELLED'}
        if vl.objects.active is not arm or context.mode != 'POSE':
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            for ob in context.selected_objects:
                ob.select_set(False)
            arm.select_set(True)
            vl.objects.active = arm
            bpy.ops.object.mode_set(mode='POSE')
        for other in arm.pose.bones:
            other.select = False
        pb.select = True
        arm.data.bones.active = arm.data.bones[ring.bone]
        if twist or pb.bone.use_connect:
            bpy.ops.transform.rotate('INVOKE_DEFAULT', release_confirm=True)
        elif solid_world:
            bpy.ops.stop_motion.solid_drag('INVOKE_DEFAULT', puppet=arm.name, ring=self.ring)
        else:
            bpy.ops.transform.translate('INVOKE_DEFAULT', release_confirm=True)
        return {'FINISHED'}


class SM_GGT_rings(bpy.types.GizmoGroup):
    bl_idname = "SM_GGT_rings"
    bl_label = "Stop Motion Grab Rings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        rv3d = context.region_data
        if rv3d is None:
            return False
        from . import studio
        if rv3d.view_perspective == 'CAMERA' and not studio.is_active():
            return False
        if context.screen and context.screen.is_animation_playing:
            return False
        return bool(puppet.puppets(context.scene)) or bool(solid.props(context.scene))

    def _signature(self, context):
        return (tuple((arm.name, tuple((r.bone, r.pin.name if r.pin else "") for r in arm.stop_motion_puppet.rings))
                      for arm in puppet.puppets(context.scene)),
                tuple(p.name for p in solid.props(context.scene)))

    def _rebuild(self, context):
        for gz in list(self.gizmos):
            self.gizmos.remove(gz)
        self.slots = []
        for arm in puppet.puppets(context.scene):
            for i, ring in enumerate(arm.stop_motion_puppet.rings):
                gz = self.gizmos.new("GIZMO_GT_move_3d")
                gz.draw_style = 'RING_2D'
                gz.use_draw_modal = False
                gz.line_width = 3.0
                gz.alpha = 0.75
                gz.color_highlight = HOT_COLOR
                gz.alpha_highlight = 1.0
                op = gz.target_set_operator("stop_motion.grab_ring")
                op.puppet = arm.name
                op.ring = i
                self.slots.append((gz, arm.name, i))
        for ob in solid.props(context.scene):
            gz = self.gizmos.new("GIZMO_GT_move_3d")
            gz.draw_style = 'RING_2D'
            gz.use_draw_modal = False
            gz.line_width = 3.0
            gz.alpha = 0.75
            gz.color = PROP_COLOR
            gz.color_highlight = HOT_COLOR
            gz.alpha_highlight = 1.0
            gz.target_set_operator("stop_motion.grab_prop").name = ob.name
            self.slots.append((gz, ob.name, -1))
        self.sig = self._signature(context)

    def setup(self, context):
        self.slots = []
        self.sig = None
        self._rebuild(context)

    def refresh(self, context):
        if self._signature(context) != self.sig:
            self._rebuild(context)

    def draw_prepare(self, context):
        rv3d = context.region_data
        view_rot = rv3d.view_rotation.to_matrix().to_4x4() if rv3d else Matrix()
        from . import studio
        box = studio.live_rect() if studio.is_active() and studio.S.chrome else None
        region = context.region
        for gz, arm_name, i in self.slots:
            if i < 0:  # a prop
                ob = bpy.data.objects.get(arm_name)
                if ob is None or not ob.visible_get():
                    gz.hide = True
                    continue
                gz.hide = not _inside(region, rv3d, ob.matrix_world.translation, box)
                gz.matrix_basis = Matrix.Translation(ob.matrix_world.translation) @ view_rot
                gz.scale_basis = 0.18
                continue
            arm = bpy.data.objects.get(arm_name)
            if arm is None or i >= len(arm.stop_motion_puppet.rings):
                gz.hide = True
                continue
            ring = arm.stop_motion_puppet.rings[i]
            pos = ring_world_position(arm, ring)
            if pos is None:
                gz.hide = True
                continue
            gz.hide = not _inside(region, rv3d, pos, box)
            gz.matrix_basis = Matrix.Translation(pos) @ view_rot
            gz.scale_basis = 0.22 * ring.size
            gz.color = PIN_COLOR if (ring.pin is not None and puppet.is_pinned(arm, ring)) else RING_COLOR


classes = (SM_OT_grab_ring, SM_GGT_rings)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
