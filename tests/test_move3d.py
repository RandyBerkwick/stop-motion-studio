"""3D move and turn: axis locks, further/nearer, trackball direction, solid stops on any 3D turn."""
import math, os, sys, runpy
from types import SimpleNamespace
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, bmesh
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector, Quaternion
from mathutils.bvhtree import BVHTree
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import puppet, solid


def close(a, b, tol=1e-4):
    return (a - b).length < tol


# --- axis_point: closest point on an axis to a mouse ray
p = solid.axis_point(Vector((0, -5, 2)), Vector((0, 1, 0)), Vector((0, 0, 0)), Vector((0, 0, 1)))
assert close(p, Vector((0, 0, 2))), p
p = solid.axis_point(Vector((3, -5, 0)), Vector((0, 1, 0)), Vector((0, 0, 0)), Vector((1, 0, 0)))
assert close(p, Vector((3, 0, 0))), p
print("axis_point ok")

# --- a fake 3D view: a camera at (0,-6,1) looking along +Y, 800x600
scene = bpy.context.scene
cam_data = bpy.data.cameras.new("TestCam")
cam = bpy.data.objects.new("TestCam", cam_data)
scene.collection.objects.link(cam)
cam.matrix_world = Matrix.Translation((0, -6, 1)) @ Matrix.Rotation(math.radians(90), 4, 'X')
bpy.context.view_layer.update()
W, H = 800, 600
win = cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=W, y=H)
view = cam.matrix_world.inverted()
rv3d = SimpleNamespace(view_matrix=view, perspective_matrix=win @ view, is_perspective=True,
                       view_perspective='PERSP', view_distance=6.0)
region = SimpleNamespace(width=W, height=H)
right, up, back, eye = solid.view_frame(rv3d)
assert close(right, Vector((1, 0, 0))) and close(up, Vector((0, 0, 1))) and close(back, Vector((0, -1, 0))), (right, up, back)
assert close(eye, Vector((0, -6, 1)))


def fake(cls, **kw):
    F = type("Fake" + cls.__name__, (), {k: v for k, v in cls.__dict__.items()
                                          if callable(v) and not k.startswith("__")})
    f = F()
    f.__dict__.update(kw)
    return f


def px(pt):
    return view3d_utils.location_3d_to_region_2d(region, rv3d, pt)


anchor = Vector((0.3, 0, 0.5))
m0 = px(anchor)
drag = fake(solid.SM_OT_solid_drag, region=region, rv3d=rv3d, anchor=anchor,
            base=Vector((0, 0, 0)), move=Vector((0, 0, 0)), press=m0.copy(), eff=m0.copy(), depth=0.0, lock=None, local=False)

assert drag.wanted().length < 1e-6, "no mouse movement, no move"
drag.eff = m0 + Vector((80, 0))
mv = drag.wanted()
assert mv.x > 0.1 and abs(mv.y) < 1e-6 and abs(mv.z) < 1e-6, ("right on screen = +X across the view", mv)
assert (px(anchor + mv) - drag.eff).length < 0.5, "the part stays under the mouse"

# further away: it slides along the line of sight, so on screen it stays put
drag.eff = m0.copy()
drag.depth = 1.5
mv = drag.wanted()
assert mv.y > 1.0, ("pushed away from the camera", mv)
assert (px(anchor + mv) - m0).length < 0.5, "and it doesn't wander on screen"
assert abs((anchor + mv - eye).length - (anchor - eye).length - 1.5) < 1e-4
print("depth ok", tuple(round(c, 3) for c in mv))

# keep the depth, then lock to Z: moving the mouse up only lifts it
drag.move = mv
drag._rebase()
assert close(drag.base, mv) and drag.depth == 0.0
drag.lock = 'Z'
drag.eff = drag.press + Vector((0, 60))
mz = drag.wanted() - drag.base
assert mz.z > 0.1 and abs(mz.x) < 1e-6 and abs(mz.y) < 1e-6, ("Z lock only goes up", mz)
drag.eff = drag.press + Vector((200, 60))          # sideways mouse movement is ignored on Z
side = drag.wanted() - drag.base
assert abs(side.x) < 1e-6 and abs(side.y) < 1e-6 and abs(side.z - mz.z) < 0.25 * mz.z, (side, mz)
# lock Y (pointing straight away from the camera): moving the mouse up the screen pushes it back
drag.lock = 'Y'
drag.eff = drag.press + Vector((0, 40))
my = drag.wanted() - drag.base
assert abs(my.x) < 1e-6 and abs(my.z) < 1e-6 and 0.2 < my.y < 1.0, ("Y lock: up pushes it gently away", my)
print("axis locks ok", tuple(round(c, 3) for c in mz), tuple(round(c, 3) for c in my))

# --- trackball direction
turn = fake(solid.SM_OT_solid_twist, region=region, rv3d=rv3d, pivot=Vector((0, 0, 0.5)), mode='BALL',
            last_screen=0.0)
turn.pivot2d = px(turn.pivot)
front = turn.pivot + back * 0.3          # a point on the side facing the camera
q = turn.turn_for(Vector((40, 0)), turn.pivot2d, False)
moved = turn.pivot + q @ (front - turn.pivot)
assert moved.x > 0.05, ("drag right: the front turns right", moved)
q = turn.turn_for(Vector((0, 40)), turn.pivot2d, False)
moved = turn.pivot + q @ (front - turn.pivot)
assert moved.z > turn.pivot.z + 0.05, ("drag up: the front turns up", moved)
qf = turn.turn_for(Vector((40, 0)), turn.pivot2d, True)
assert abs(qf.angle * 4 - turn.turn_for(Vector((40, 0)), turn.pivot2d, False).angle) < 1e-4, "Shift is a quarter speed"
# Z lock seen from the side: pushing across it turns about Z only
turn.mode = 'Z'
q = turn.turn_for(Vector((40, 0)), turn.pivot2d + Vector((40, 0)), False)
ax = q.axis
assert abs(abs(ax.z) - 1) < 1e-6 and q.angle > 0.1, q
# V: around the view, by going round the part on screen (a quarter circle = 90 degrees)
turn.mode = 'VIEW'
turn.last_screen = 0.0
q = turn.turn_for(Vector((0, 0)), turn.pivot2d + Vector((0, 50)), False)
assert abs(math.degrees(q.angle) - 90) < 1e-3 and abs(abs(q.axis.y) - 1) < 1e-6, (math.degrees(q.angle), q.axis)
print("turn directions ok")

# --- turn_limit: a stick on the floor tipped about a slanted axis stops at the floor
floor = BVHTree.FromPolygons([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [(0, 1, 2, 3)])
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, 0.302)) @ Matrix.Diagonal((0.04, 0.04, 0.6, 1)))
stick = [v.co.copy() for v in bm.verts]
bm.free()
pivot = Vector((0.02, 0.02, 0.002))        # a corner of its base: it tips over corner-first
axis = Vector((-1, 1, 0)).normalized()
q, blocked = solid.turn_limit(stick, pivot, Quaternion(), Quaternion(axis, math.radians(150)), floor)
low = min((pivot + q @ (p - pivot)).z for p in stick)
print("slanted tip stops at", round(math.degrees(q.angle), 1), "deg, lowest", round(low, 4))
assert blocked and 60 < math.degrees(q.angle) < 100 and low > -0.003
q2, b2 = solid.turn_limit(stick, pivot, q, Quaternion(), floor)
assert not b2 and q2.angle < 1e-6, "turning back is free"
# a turn that stays clear isn't stopped
q3, b3 = solid.turn_limit(stick, pivot, Quaternion(), Quaternion(Vector((0, 0, 1)), math.radians(170)), floor)
assert not b3 and abs(math.degrees(q3.angle) - 170) < 1e-3
print("turn_limit ok")

# --- Bramble: the arm rolled forward and down (a 3D turn) stops on the table
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
    found = []
    for ax in (Vector((1, 1, 0)), Vector((-1, 1, 0)), Vector((1, -1, 0)), Vector((-1, -1, 0)), Vector((0, 1, 0)), Vector((0, -1, 0))):
        q, blocked = solid.turn_limit(pts, shoulder, Quaternion(), Quaternion(ax.normalized(), math.radians(70)), tree)
        moved = [shoulder + q @ (p - shoulder) for p in pts]
        deepest = 0.0
        for p in moved:
            loc, n, _i, d = tree.find_nearest(p)
            if loc is not None and (p - loc).dot(n) < 0:
                deepest = max(deepest, d)
        found.append((tuple(ax), blocked, round(math.degrees(q.angle), 1), round(deepest, 4)))
    print("arm 3D turns", found)
    assert any(f[1] for f in found), "some way down the hand meets the table"
    assert all(f[3] < 0.004 for f in found), "and never ends up inside it"


# --- the drag and turn event handling, with made-up mouse and key events
box = bpy.data.objects.new("Box3D", bpy.data.meshes.new("Box3D"))
bpy.context.scene.collection.objects.link(box)
box.location = anchor
bpy.context.view_layer.update()
ctx = SimpleNamespace(area=None, window=SimpleNamespace(cursor_modal_restore=lambda: None))
def ev(type, value='NOTHING', x=0, y=0, shift=False, ctrl=False):
    return SimpleNamespace(type=type, value=value, mouse_region_x=x, mouse_region_y=y,
                           shift=shift, ctrl=ctrl, alt=False, oskey=False)
d = fake(solid.SM_OT_solid_drag, region=region, rv3d=rv3d, anchor=anchor.copy(), start=box.matrix_world.copy(),
         target_ob=box, target_bone=None, points=[], tree=None, solid=False, hand=None, local=False,
         base=Vector((0, 0, 0)), move=Vector((0, 0, 0)), press=m0.copy(), eff=m0.copy(), last=m0.copy(), depth=0.0, lock=None)
d.modal(ctx, ev('MOUSEMOVE', x=m0.x + 50, y=m0.y))
x_after = box.matrix_world.translation.x
assert x_after > anchor.x + 0.05
d.modal(ctx, ev('MOUSEMOVE', x=m0.x + 50, y=m0.y + 80, shift=True))      # Shift: further away, same place on screen
assert box.matrix_world.translation.y > 0.2 and abs(box.matrix_world.translation.x - x_after) < 0.2
d.modal(ctx, ev('WHEELUPMOUSE', 'PRESS', x=m0.x + 50, y=m0.y + 80))
y_after = box.matrix_world.translation.y
d.modal(ctx, ev('Z', 'PRESS', x=m0.x + 50, y=m0.y + 80))
assert d.lock == 'Z' and solid._GUIDE["origin"] is not None, "Z lock shows its line"
here = box.matrix_world.translation.copy()
d.modal(ctx, ev('MOUSEMOVE', x=m0.x + 50, y=m0.y + 140))
now = box.matrix_world.translation
assert now.z > here.z + 0.05 and abs(now.x - here.x) < 1e-5 and abs(now.y - here.y) < 1e-5, (here, now)
d.modal(ctx, ev('Z', 'PRESS'))
assert d.lock == 'Z' and d.local, "Z again: its own Z"
d.modal(ctx, ev('Z', 'PRESS'))
assert d.lock is None and solid._GUIDE["origin"] is None
r = d.modal(ctx, ev('ESC', 'PRESS'))
assert r == {'CANCELLED'} and close(box.matrix_world.translation, anchor), "Esc puts it back"
print("drag events ok")

t = fake(solid.SM_OT_solid_twist, region=region, rv3d=rv3d, pivot=anchor.copy(), pivot2d=m0.copy(),
         start=box.matrix_world.copy(), ob=box, pb=None, points=[], tree=None, solid=False, hand=None, local=False,
         last=m0.copy(), last_screen=0.0, q=Quaternion(), mode='BALL')
t.modal(ctx, ev('MOUSEMOVE', x=m0.x + 60, y=m0.y + 30))
assert box.matrix_world.to_quaternion().angle > 0.3, "ball turn turns it"
t.modal(ctx, ev('X', 'PRESS'))
assert t.mode == 'X'
q_before = t.q.copy()
t.modal(ctx, ev('MOUSEMOVE', x=m0.x + 60, y=m0.y + 90))
extra = t.q @ q_before.inverted()
assert extra.angle > 0.1 and abs(abs(extra.axis.x) - 1) < 1e-3, extra.axis
t.modal(ctx, ev('X', 'PRESS'))
assert t.mode == 'X' and t.local, "X again: around its own X"
t.modal(ctx, ev('V', 'PRESS'))
assert t.mode == 'VIEW' and not t.local
t.modal(ctx, ev('V', 'PRESS'))
assert t.mode == 'BALL'
r = t.modal(ctx, ev('LEFTMOUSE', 'RELEASE'))
assert r == {'FINISHED'} and solid._GUIDE["handle"] is None
print("turn events ok")

print("MOVE3D TESTS PASSED")
sms.unregister()
