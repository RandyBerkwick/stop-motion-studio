import math, os, sys, runpy
from types import SimpleNamespace
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import puppet, solid

def inside_depth(tree, pts):
    worst = 0.0
    for p in pts:
        loc, n, _i, d = tree.find_nearest(p)
        if loc is not None and (p - loc).dot(n) < 0:
            worst = max(worst, d)
    return worst

# --- a stick stood on the floor, tipped over on its bottom edge: stops when the top meets the floor
floor = BVHTree.FromPolygons([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [(0, 1, 2, 3)])
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, 0.302)) @ Matrix.Diagonal((0.04, 0.04, 0.6, 1)))
stick = [v.co.copy() for v in bm.verts]; bm.free()
pivot, axis = Vector((0.02, 0, 0.002)), Vector((0, 1, 0))
a, blocked = solid.twist_limit(stick, pivot, axis, 0.0, math.radians(120), floor)
print("stick stops at", round(math.degrees(a), 1), "deg")
assert blocked and 80 < math.degrees(a) < 92, math.degrees(a)
R = Matrix.Rotation(a, 3, axis)
assert min((pivot + R @ (p - pivot)).z for p in stick) > -0.001, "nothing below the floor"
# turning back out of contact is free
b, blocked2 = solid.twist_limit(stick, pivot, axis, a, 0.0, floor)
assert not blocked2 and abs(b) < 1e-9
# out in the open nothing stops it
c, blocked3 = solid.twist_limit([p + Vector((0, 0, 5)) for p in stick], pivot + Vector((0, 0, 5)), axis, 0.0, math.radians(300), floor)
assert not blocked3 and abs(math.degrees(c) - 300) < 1e-6
print("stick ok")

# --- a box turned on the spot next to a wall: its corner stops at the wall
wall = BVHTree.FromPolygons([(0.06, -1, 0), (0.06, 1, 0), (0.06, 1, 1), (0.06, -1, 1)], [(0, 3, 2, 1)])  # faces -x
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=0.1, matrix=Matrix.Translation((0, 0, 0.05))); box = [v.co.copy() for v in bm.verts]; bm.free()
a, blocked = solid.twist_limit(box, Vector((0, 0, 0.05)), Vector((0, 0, 1)), 0.0, math.radians(45), wall)
print("box against wall stops at", round(math.degrees(a), 1), "deg")
assert blocked and 10 < math.degrees(a) < 40

# --- Bramble: swing the left arm down, the hand meets the table and stops
g = runpy.run_path(os.path.join(ROOT, "scripts", "make_test_puppet.py"))
scene, arm = g["scene"], g["arm"]
vl = scene.view_layers[0]
with bpy.context.temp_override(scene=scene, view_layer=vl):
    ctx = bpy.context
    puppet.make_puppet(ctx, arm)
    vl.update()
    ring = SimpleNamespace(pin=None, bone="upper_arm.L", pin_owner="")
    pts = solid.ring_points(ctx, arm, ring, "upper_arm.L", exclude_pinned=False)
    tree = solid.obstacle_tree(scene, ctx.evaluated_depsgraph_get(), solid.own_meshes(scene, arm))
    shoulder = arm.matrix_world @ arm.pose.bones["upper_arm.L"].head
    results = []
    for sign in (1, -1):
        a, blocked = solid.twist_limit(pts, shoulder, Vector((0, 1, 0)), 0.0, sign * math.radians(60), tree)
        R = Matrix.Rotation(a, 3, Vector((0, 1, 0)))
        moved = [shoulder + R @ (p - shoulder) for p in pts]
        results.append((sign, round(math.degrees(a), 1), blocked, round(inside_depth(tree, moved), 4)))
    print("arm swings", results)
    down = [r for r in results if r[2]]
    assert down and abs(down[0][1]) < 30, "swinging down, the hand meets the table top"
    assert all(r[3] < 0.004 for r in results), "and never ends up inside it"
    # applying it to the bone the way the twist does keeps the hand above the table
    sign, deg = down[0][0], down[0][1]
    pb = arm.pose.bones["upper_arm.L"]
    mw = arm.matrix_world
    R4 = Matrix.Translation(shoulder) @ Matrix.Rotation(math.radians(deg), 4, Vector((0, 1, 0))) @ Matrix.Translation(-shoulder)
    pb.matrix = mw.inverted() @ R4 @ mw @ pb.matrix.copy()
    vl.update()
    after = solid.ring_points(ctx, arm, ring, "upper_arm.L", exclude_pinned=False)
    print("after applying: deepest inside", round(inside_depth(tree, after), 4))
    assert inside_depth(tree, after) < 0.006
print("TWIST TESTS PASSED")
sms.unregister()
