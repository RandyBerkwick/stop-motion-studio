import math, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, bmesh
from mathutils import Matrix, Vector
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import arrange, core, solid

ctx = bpy.context
scene = ctx.scene
for ob in list(scene.objects):
    if ob.type == 'MESH':
        bpy.data.objects.remove(ob)

def mesh_ob(name, build, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); build(bm); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); scene.collection.objects.link(o); o.location = loc
    return o

floor = mesh_ob("Floor", lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=3.0))
rng = random.Random(4)
def bush_build(bm):
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=0.5)
    for v in bm.verts:                        # lumpy, like a bush
        v.co *= 1.0 + 0.12 * math.sin(7 * v.co.x) * math.cos(5 * v.co.y) + rng.uniform(-0.03, 0.03)
bush = mesh_ob("Bush", bush_build, (0, 0, 0.55))
def flower_build(bm):
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.01, radius2=0.01, depth=0.12,
                          matrix=Matrix.Translation((0, 0, 0.06)))
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.03, matrix=Matrix.Translation((0, 0, 0.13)))
flower = mesh_ob("Flower", flower_build, (2.0, 2.0, 0.5))      # floating somewhere off to the side
cup = mesh_ob("Cup", lambda bm: bmesh.ops.create_cube(bm, size=0.1), (1.0, -1.0, 0.7))
ctx.view_layer.update()
dg = ctx.evaluated_depsgraph_get()

def signed_inside(tree, pts):
    """Deepest a point sits inside the obstacles (0 if none)."""
    worst = 0.0
    for p in pts:
        loc, n, _i, d = tree.find_nearest(p)
        if loc is not None and (p - loc).dot(n) < 0:
            worst = max(worst, d)
    return worst

def world_pts(ob):
    ctx.view_layer.update()
    return [ob.matrix_world @ v.co for v in ob.data.vertices]

# --- rays skip what's excluded and what isn't solid
hit = arrange.cast(scene, dg, (0, 0, 3), (0, 0, -1))
assert hit and hit[2] == bush, hit
hit = arrange.cast(scene, dg, (0, 0, 3), (0, 0, -1), exclude={bush})
assert hit and hit[2] == floor and abs(hit[0].z) < 1e-5
bush.stop_motion_solid = False
assert arrange.cast(scene, dg, (0, 0, 3), (0, 0, -1))[2] == floor
bush.stop_motion_solid = True
print("rays ok")

# --- a cup slid onto the floor sits on it, upright, nothing below the floor
pts = arrange.local_points(ctx, cup)
tree = solid.obstacle_tree(scene, dg, {cup})
loc, n, _o = arrange.cast(scene, dg, (1.0, -1.0, 2), (0, 0, -1), {cup})
cup.matrix_world = arrange.placement(cup.matrix_world.copy(), pts, loc, n, True, 0.0, Vector((0, 0, 1)), tree)
zs = [p.z for p in world_pts(cup)]
print("cup bottom", round(min(zs), 4))
assert 0 <= min(zs) < 0.003 and abs(cup.matrix_world.to_quaternion().angle) < 1e-4

# --- a flower stuck on the side of the bush stands out along the surface and isn't buried
tree = solid.obstacle_tree(scene, dg, {flower})
pts = arrange.local_points(ctx, flower)
side = arrange.cast(scene, dg, (2.0, 0.3, 0.7), (-1, 0, 0), {flower})
assert side and side[2] == bush
flower.matrix_world = arrange.placement(flower.matrix_world.copy(), pts, side[0], side[1], True, 0.4,
                                        Vector((0, 0, 1)), tree)
stem = flower.matrix_world.to_quaternion() @ Vector((0, 0, 1))
print("stem vs surface normal", round(stem.dot(side[1]), 3), "| buried", round(signed_inside(tree, world_pts(flower)), 4))
assert stem.dot(side[1]) > 0.99, "leans out with the surface"
assert signed_inside(tree, world_pts(flower)) < 0.003, "nothing inside the bush"
base = flower.matrix_world @ Vector((0, 0, 0))
assert (base - side[0]).length < 0.05, "sits where it was put"
# same spot, upright: stays upright, still not inside
flower.matrix_world = arrange.placement(Matrix.Translation((2, 2, 0.5)), pts, side[0], side[1], False, 0.0,
                                        Vector((0, 0, 1)), tree)
up = flower.matrix_world.to_quaternion() @ Vector((0, 0, 1))
print("upright", round(up.z, 3), "| buried", round(signed_inside(tree, world_pts(flower)), 4))
assert up.z > 0.999 and signed_inside(tree, world_pts(flower)) < 0.003
print("placement ok")

# --- stamping flowers all over the bush
flower.matrix_world = Matrix.Translation((2, 2, 0.5))
ctx.view_layer.update()
dg = ctx.evaluated_depsgraph_get()
tree = solid.obstacle_tree(scene, dg, {flower})
r = random.Random(7)
copies = []
for i in range(24):
    a = 2 * math.pi * i / 24
    origin = Vector((1.6 * math.cos(a), 1.6 * math.sin(a), 0.55 + 0.6 * math.sin(3 * a)))
    h = arrange.cast(scene, dg, origin, Vector((0, 0, 0.55)) - origin, {flower})
    if h and h[2] == bush:
        copies.append(arrange.stamp(ctx, flower, h[0], h[1], True, rng=r, vary=0.15, tree=tree))
ctx.view_layer.update()
assert len(copies) >= 20, len(copies)
assert all(c.data == flower.data and c.stop_motion_set for c in copies), "linked copies, set pieces"
scales = {round(c.matrix_world.to_scale().x, 3) for c in copies}
assert len(scales) > 5 and all(0.84 < k < 1.16 for k in scales), scales
worst = max(signed_inside(tree, [c.matrix_world @ v.co for v in c.data.vertices]) for c in copies)
print("stamped", len(copies), "| deepest inside", round(worst, 4))
assert worst < 0.004
print("stamp ok")

# --- set pieces are left out of the shots
bpy.ops.stop_motion.shoot()
assert not any(c.animation_data for c in copies), "set pieces aren't keyed"
assert cup.animation_data is not None, "ordinary objects still are"
copies[0].location.z += 0.2; z = copies[0].location.z
bpy.ops.stop_motion.shoot(); scene.frame_set(1)
assert abs(copies[0].location.z - z) < 1e-6, "a moved set piece stays moved in every shot"
cup.select_set(True); ctx.view_layer.objects.active = cup
w = cup.matrix_world.copy()
bpy.ops.stop_motion.set_piece(on=True)
assert cup.stop_motion_set and cup.animation_data is None and (cup.matrix_world.translation - w.translation).length < 1e-6
print("ARRANGE TESTS PASSED")
sms.unregister()
