"""Knee targets, rigs with their own IK feet, a puppet's own parts being solid,
sliding into things while arranging, and moving a prop that's held in a hand."""
import math, os, sys, runpy
from types import SimpleNamespace
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, bmesh
from mathutils import Matrix, Vector
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import arrange, puppet, solid

g = runpy.run_path(os.path.join(ROOT, "scripts", "make_test_puppet.py"))
scene, arm = g["scene"], g["arm"]
vl = scene.view_layers[0]


def world_bones(names):
    vl.update()
    ae = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return {n: (ae.matrix_world @ ae.pose.bones[n].matrix) for n in names}


with bpy.context.temp_override(scene=scene, view_layer=vl):
    ctx = bpy.context
    legs = ["thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R"]
    before = world_bones(legs)
    puppet.make_puppet(ctx, arm)
    after = world_bones(legs)
    worst = max((before[n].translation - after[n].translation).length +
                max((before[n].col[i].xyz - after[n].col[i].xyz).length for i in range(3)) for n in legs)
    print("legs moved by adding pins + knees:", round(worst, 5))
    assert worst < 1e-3, "adding the knee targets doesn't move the legs"
    rings = {r.label: r for r in arm.stop_motion_puppet.rings}
    lf = rings["Left foot"]
    assert lf.knee is not None and puppet.pin_constraint(arm, lf).pole_target == lf.knee

    # crouch a long way and push the hips forward and back: the knee keeps pointing the same way
    hips = arm.pose.bones["hips"]
    def knee_dir():
        w = world_bones(["thigh.L", "shin.L"])
        hip, knee, ankle = w["thigh.L"].translation, w["shin.L"].translation, (w["shin.L"] @ Matrix.Translation((0, arm.pose.bones["shin.L"].length, 0))).translation
        mid = (hip + ankle) / 2
        return (knee - mid)
    base = knee_dir()
    rest = hips.location.copy()
    signs = []
    for dz, dy in ((-0.08, 0), (-0.16, 0), (-0.16, 0.06), (-0.16, -0.06), (-0.2, 0.0)):
        hips.location = rest + Vector((0, dy, dz))       # bone space: y is along the bone (up)
        hips.location = rest + Vector((0, dz, dy))
        d = knee_dir()
        signs.append(round(d.y, 3))
    hips.location = rest
    print("knee forward (y) through deep crouches:", signs, "rest", round(base.y, 3))
    assert all((s < 0) == (base.y < 0) for s in signs if abs(s) > 1e-3), "the knee never flips"

    # --- own parts are solid: the left hand pushed into the chest stops
    ring = SimpleNamespace(pin=None, bone="hand.L", pin_owner="", rig_ik="")
    pts = solid.ring_points(ctx, arm, ring, "hand.L", exclude_pinned=False)
    hand = sum(pts, Vector()) / len(pts)
    # straight across into his belly, at the height of the hand
    want = Vector((-hand.x * 1.6, 0, 0))
    dg = ctx.evaluated_depsgraph_get()
    own = solid.own_meshes(scene, arm)
    extra = solid.self_geometry(ctx, arm, "hand.L")
    assert extra is not None and len(extra[1]) > 10
    t_self = solid.obstacle_tree(scene, dg, own, extra)
    move, blocked = solid.solve(pts, want, t_self)
    def deepest(tree, points):
        worst = 0.0
        for p in points:
            loc, n, _i, dd = tree.find_nearest(p)
            if loc is not None and (p - loc).dot(n) < 0:
                worst = max(worst, dd)
        return worst
    t_body_only = solid.obstacle_tree(scene, dg, set(scene.objects), extra)   # just his own other parts
    inside = deepest(t_body_only, [p + move for p in pts])
    free_inside = deepest(t_body_only, [p + want for p in pts])
    print("hand pushed across into his belly: wanted", round(want.length, 3), "got", round(move.length, 3),
          "deepest inside", round(inside, 4))
    first, _b = solid.solve(pts, want, t_self, slide=False)
    print("  first contact after", round(first.length, 3))
    assert blocked and first.length < want.length * 0.6 and inside < 0.006
    scene.stop_motion.self_solid = False
    assert solid.self_geometry(ctx, arm, "hand.L") is None, "switched off: passes through itself"
    scene.stop_motion.self_solid = True
    # the joint it turns at isn't in the way: a small swing of the hand alone is free
    small, b2 = solid.solve(pts, Vector((0, 0, 0.01)), t_self)
    assert not b2, "the forearm and upper arm it hangs from don't block it"
    # one foot can't go through the other
    lf_pts = solid.ring_points(ctx, arm, lf, "foot.L", exclude_pinned=False)
    t_feet = solid.obstacle_tree(scene, dg, own, solid.self_geometry(ctx, arm, "foot.L"))
    other = world_bones(["foot.R"])["foot.R"].translation
    mine = sum(lf_pts, Vector()) / len(lf_pts)
    across = Vector(((other - mine).x * 1.5, 0, 0))
    mv, bf = solid.solve(lf_pts, across, t_feet)
    t_feet_only = solid.obstacle_tree(scene, dg, set(scene.objects), solid.self_geometry(ctx, arm, "foot.L"))
    print("left foot across into the right: blocked", bf, "deepest", round(deepest(t_feet_only, [p + mv for p in lf_pts]), 4))
    assert bf and deepest(t_feet_only, [p + mv for p in lf_pts]) < 0.006

    # --- a held prop can be moved in 3D and stays in the hand
    mug = bpy.data.objects["Mug"]
    hr = rings["Right hand"]
    solid.hold(ctx, mug, arm, hr.bone)
    vl.update()
    w0 = solid.world_matrix(ctx, mug)
    target = Matrix.Translation((0.03, -0.02, 0.01)) @ w0 @ Matrix.Rotation(0.4, 4, 'Z')
    solid.set_world(ctx, mug, target)
    w1 = solid.world_matrix(ctx, mug)
    err = max((w1.col[i] - target.col[i]).length for i in range(4))
    print("held mug placed, error", round(err, 6))
    assert err < 1e-4 and solid.held_by(mug) is not None
    ua = arm.pose.bones["upper_arm.R"]
    ua.rotation_mode = 'XYZ'
    ua.rotation_euler.x += 0.3
    w2 = solid.world_matrix(ctx, mug)
    assert (w2.translation - w1.translation).length > 0.01, "still follows the hand"
    ua.rotation_euler.x -= 0.3
    solid.let_go(ctx, mug)

# --- a rig with its own IK foot control: its IK becomes the pin
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
scene = bpy.context.scene
ad = bpy.data.armatures.new("LegRig")
rig = bpy.data.objects.new("LegRig", ad)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
eb = ad.edit_bones
hipb = eb.new("hips"); hipb.head, hipb.tail = (0, 0, 1.0), (0, 0, 1.2)
th = eb.new("thigh.L"); th.head, th.tail = (0.1, 0, 1.0), (0.1, -0.03, 0.55); th.parent = hipb
sh = eb.new("shin.L"); sh.head, sh.tail = (0.1, -0.03, 0.55), (0.1, 0, 0.1); sh.parent = th; sh.use_connect = True
ft = eb.new("foot.L"); ft.head, ft.tail = (0.1, 0, 0.1), (0.1, -0.15, 0.0); ft.parent = sh; ft.use_connect = True
ik = eb.new("foot_ik.L"); ik.head, ik.tail = (0.1, 0, 0.1), (0.1, -0.15, 0.1)
bpy.ops.object.mode_set(mode='POSE')
c = rig.pose.bones["shin.L"].constraints.new('IK')
c.target, c.subtarget, c.chain_count = rig, "foot_ik.L", 2
bpy.ops.object.mode_set(mode='OBJECT')
with bpy.context.temp_override(scene=scene):
    ctx = bpy.context
    pp = puppet.make_puppet(ctx, rig)
    foot = next(r for r in pp.rings if "foot" in r.label.lower())
    print("rig IK foot ring:", foot.label, foot.bone, "pin by", foot.pin_owner, foot.rig_ik, "extra pin", foot.pin)
    assert foot.bone == "foot_ik.L" and foot.rig_ik == c.name and foot.pin is None
    assert puppet.has_pin(foot) and puppet.is_pinned(rig, foot)
    shin_before = (rig.matrix_world @ rig.pose.bones["shin.L"].matrix).copy()
    puppet.set_pinned(ctx, rig, foot, False)
    ctx.view_layer.update()
    assert c.influence == 0.0
    shin_after = rig.matrix_world @ rig.pose.bones["shin.L"].matrix
    assert (shin_after.translation - shin_before.translation).length < 1e-4, "unpinning doesn't make the leg jump"
    puppet.set_pinned(ctx, rig, foot, True)
    assert c.influence == 1.0
    # shooting keys the rig's own IK switch
    from stop_motion_studio import core
    core.key_pose(scene, 1, [rig])
    assert any(fc.data_path.endswith('constraints["%s"].influence' % c.name) for fc in core.fcurves_of(rig))
print("rig IK feet ok")

# --- arranging: sliding along the floor stops at a box standing on it; moving onto the box is a lift
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
scene = bpy.context.scene
bpy.ops.mesh.primitive_plane_add(size=10)
floor = bpy.context.object
bpy.ops.mesh.primitive_cube_add(size=0.4, location=(1.0, 0, 0.2))
box = bpy.context.object
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0, 0, 0.1))
cup = bpy.context.object
bpy.context.view_layer.update()
ctx = bpy.context
pts = arrange.local_points(ctx, cup)
d = {"ob": cup, "pts": pts, "exclude": {cup}, "last": None, "surf": None, "trees": {}}
x_end = None
for x in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]:
    new = Matrix.Translation((x, 0, 0.1))
    m, bumped = arrange.slide_check(ctx, d, new, floor)
    cup.matrix_world = m
    x_end = m.translation.x
print("slid along the floor towards the box, stopped at x =", round(x_end, 3))
assert 0.6 < x_end < 0.71, "stops at the box's side (box face at 0.8, cup half-width 0.1)"
# moving the mouse onto the box: placed on top, no sweep
m, bumped = arrange.slide_check(ctx, d, Matrix.Translation((1.0, 0, 0.5)), box)
assert not bumped and abs(m.translation.x - 1.0) < 1e-6
print("RIGGING/SOLID TESTS PASSED")
sms.unregister()
