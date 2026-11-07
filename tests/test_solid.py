import os, sys, runpy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core, puppet, solid

# --- the solver on its own: a floor at z=0, a closed box
floor = BVHTree.FromPolygons([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [(0, 1, 2, 3)])
p = [Vector((0, 0, 1))]
m, b = solid.solve(p, Vector((0, 0, -2)), floor)
assert b and abs((p[0] + m).z - 0.002) < 1e-4, m
m, b = solid.solve(p, Vector((1.5, 0, -2)), floor)
end = p[0] + m
print("slide end", tuple(round(c, 3) for c in end))
assert b and abs(end.z - 0.002) < 1e-3 and end.x > 1.0, end        # slid along the floor
m, b = solid.solve([Vector((0, 0, -1))], Vector((0, 0, 3)), floor)
assert not b and abs(m.z - 3) < 1e-6                                # from behind: passes (floor is one-sided)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0)
box = BVHTree.FromBMesh(bm)
m, b = solid.solve([Vector((0, 0, 0))], Vector((3, 0, 0)), box)
assert not b, "starting inside, moving out is allowed"
m, b = solid.solve([Vector((-3, 0, 0))], Vector((3, 0, 0)), box)
assert b and abs(m.x - 1.998) < 1e-3, m
print("solver ok")

# --- the test puppet scene
g = runpy.run_path(os.path.join(ROOT, "scripts", "make_test_puppet.py"))
scene, arm = g["scene"], g["arm"]
vl = scene.view_layers[0]
with bpy.context.temp_override(scene=scene, view_layer=vl):
    ctx = bpy.context
    puppet.make_puppet(ctx, arm)
    vl.update()

    # props: a mug above the table lands on the table; one in the open lands on the floor
    def cube(name, loc, size=0.12):
        me = bpy.data.meshes.new(name); b2 = bmesh.new(); bmesh.ops.create_cube(b2, size=size); b2.to_mesh(me); b2.free()
        o = bpy.data.objects.new(name, me); scene.collection.objects.link(o); o.location = loc; o.stop_motion_prop = True
        return o
    mug = cube("Mug", (1.0, 0.2, 1.6))
    ball = cube("Ball", (-1.6, -0.5, 1.2))
    vl.update()
    d1 = solid.drop_to_surface(ctx, mug); vl.update()
    d2 = solid.drop_to_surface(ctx, ball); vl.update()
    print("mug z", round(mug.location.z, 3), "ball z", round(ball.location.z, 3))
    assert abs(mug.location.z - (0.805 + 0.06 + 0.002)) < 0.01, mug.location   # table top is at 0.805
    assert abs(ball.location.z - (0.06 + 0.002)) < 0.01, ball.location          # floor is at 0
    assert solid.drop_to_surface(ctx, mug) < 0.001                               # already resting
    print("drop ok")

    # body drag: hips pushed down 2 m stop when the body meets the floor (feet pinned)
    hips_ring = next(i for i, r in enumerate(arm.stop_motion_puppet.rings) if r.label == "Hips")
    r = arm.stop_motion_puppet.rings[hips_ring]
    pts = solid.ring_points(ctx, arm, r, r.bone)
    legs = {"thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R"}
    assert pts and all(pt.z > 0.4 for pt in pts), "pinned legs are not part of a body drag"
    tree = solid.obstacle_tree(scene, ctx.evaluated_depsgraph_get(), solid.own_meshes(scene, arm))
    move, blocked = solid.solve(pts, Vector((0, 0, -2.0)), tree)
    print("hips can drop", round(move.z, 3))
    # the left hand hangs over the table: it lands on the table top first
    assert blocked and -0.12 < move.z < -0.04, move
    stick_out = solid.solve(pts, Vector((-0.6, 0, -2.0)), tree)[0]   # step away from the table, then down
    print("away from table", tuple(round(c, 3) for c in stick_out))
    assert stick_out.z < -0.5, stick_out
    # a pinned foot can't be pushed through the floor
    foot = next(r for r in arm.stop_motion_puppet.rings if r.label == "Left foot")
    fpts = solid.ring_points(ctx, arm, foot, foot.bone, exclude_pinned=False)
    move, blocked = solid.solve(fpts, Vector((-0.3, 0, -1.0)), tree)
    print("foot move", tuple(round(c, 3) for c in move))
    assert blocked and move.z > -0.05 and move.x < -0.29, move  # stays on the floor, slides sideways
    move, blocked = solid.solve(fpts, Vector((0.6, 0, 0)), tree)
    print("foot into table leg", tuple(round(c, 3) for c in move))
    assert blocked and 0.15 < move.x < 0.3, move                # bumps the table's front leg
    print("puppet solid ok")

    # hold and let go
    hand = arm.pose.bones["hand.R"]
    stick = cube("Stick", tuple(arm.matrix_world @ hand.tail), 0.05)
    vl.update()
    found = solid.nearest_hand(scene, stick, ctx)
    assert found and found[2] == "hand.R", found
    W = lambda: solid.world_matrix(ctx, stick).translation.copy()
    before = W()
    solid.hold(ctx, stick, arm, "hand.R")
    assert (W() - before).length < 1e-4, "holding must not make it jump"
    arm.pose.bones["upper_arm.R"].rotation_quaternion = (0.9, 0.43, 0.0, 0.0)  # swing the arm
    moved = W()
    assert (moved - before).length > 0.1, "a held prop follows the hand"
    solid.let_go(ctx, stick)
    assert (W() - moved).length < 1e-4, "letting go leaves it where it is"
    arm.pose.bones["upper_arm.R"].rotation_quaternion = (1, 0, 0, 0)
    assert (W() - moved).length < 1e-4, "once let go it no longer follows"
    # hold again later reuses the constraint without moving earlier shots
    solid.hold(ctx, stick, arm, "hand.R")
    assert (W() - moved).length < 1e-4
    assert len(solid.hold_constraints(stick)) == 1
    print("hold ok")
print("SOLID TESTS PASSED")
sms.unregister()
