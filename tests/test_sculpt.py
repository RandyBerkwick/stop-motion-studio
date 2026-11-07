import os, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy
from mathutils import Vector
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import core, sculpt

scene = bpy.context.scene
cube = bpy.data.objects["Cube"]
bpy.context.view_layer.objects.active = cube
for _ in range(3):
    bpy.ops.stop_motion.shoot()
sm = scene.stop_motion
uid2 = sm.shots[1].uid
name = sculpt.sculpt_key_name(uid2)

def val(f):
    scene.frame_set(f)
    return round(cube.data.shape_keys.key_blocks[name].value, 3)

# --- sculpt shot 2 here (one-off), then carry on
scene.frame_set(3)
r = bpy.ops.stop_motion.sculpt_shot(keep='ONE_OFF')
assert r == {'FINISHED'} and cube.mode == 'SCULPT' and scene.stop_motion_sculpting
kb = cube.data.shape_keys.key_blocks[name]
assert cube.active_shape_key == kb
for d in kb.data:                       # stand-in for brush strokes
    d.co.z += 0.5
bpy.ops.stop_motion.done_sculpting()
assert cube.mode == 'OBJECT'
print("one-off", [val(f) for f in (1, 3, 5, 7)])
assert [val(f) for f in (1, 3, 5, 7)] == [0, 1, 0, 0]
bpy.ops.stop_motion.sculpt_keep(obj=cube.name, uid=uid2, keep='CARRY_ON')
assert [val(f) for f in (1, 3, 5, 7)] == [0, 1, 1, 1]
bpy.ops.stop_motion.sculpt_keep(obj=cube.name, uid=uid2, keep='ONE_OFF')

# --- the sculpt stays with its shot when timing changes, and through a pose over
bpy.ops.stop_motion.delete_shot(index=0)
assert [val(f) for f in (1, 3)] == [1, 0], [val(f) for f in (1, 3)]
scene.frame_set(1); cube.location.x = 0.3
bpy.ops.stop_motion.shoot()             # replace shot 1 (the sculpted one)
assert val(1) == 1 and val(3) == 0
print("retime and pose over ok")

# --- save as swap part
bpy.ops.stop_motion.sculpt_to_swap(obj=cube.name, uid=uid2, set_name="Face", part_name="Surprised")
assert "Face_Surprised" in cube.data.shape_keys.key_blocks and name not in cube.data.shape_keys.key_blocks
print("swap ok")

# --- Nomad round trip: same points
tmp = tempfile.mkdtemp()
scene.stop_motion_nomad_dir = tmp
scene.frame_set(3)
uid = sm.shots[1].uid
r = bpy.ops.stop_motion.send_nomad(keep='ONE_OFF')
assert r == {'FINISHED'}
item = scene.stop_motion_nomad[0]
assert os.path.exists(item.path) and item.status.startswith("Waiting")
verts, faces = sculpt.read_obj(item.path)
base = sculpt.basis_positions(cube)
assert len(verts) == len(base) and max((a - b).length for a, b in zip(verts, base)) < 1e-5  # Y-up round trip exact
sculpt._poll_bridge()
assert item.status.startswith("Waiting"), item.status
with open(item.path, "w") as fh:        # "Nomad" puffs the cube up by 20%
    for v in verts:
        p = v * 1.2
        fh.write("v %f %f %f\n" % (p.x, p.z, -p.y))
    for f in faces:
        fh.write("f %s\n" % " ".join("%d/%d" % (i + 1, i + 1) for i in f))
os.utime(item.path, (time.time() + 5, time.time() + 5))
sculpt._poll_bridge()
print("status:", item.status)
assert item.status.startswith("Back from Nomad (same points)")
key = cube.data.shape_keys.key_blocks[sculpt.sculpt_key_name(uid)]
scene.frame_set(3)
after = sculpt.basis_positions(cube)
assert max((a - b * 1.2).length for a, b in zip(after, base)) < 1e-4, "shot 3 shows the Nomad sculpt"
scene.frame_set(1)
assert abs(cube.data.shape_keys.key_blocks[sculpt.sculpt_key_name(uid)].value) < 1e-6

# --- Nomad changed the points (reordered + triangulated): fit to the surface
grid = bpy.data.meshes.new("g")
import bmesh
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0); bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
bm.verts.index_update(); bm.verts.ensure_lookup_table()
n = len(bm.verts)
nv = [bm.verts[i].co * 1.1 for i in reversed(range(n))]           # reversed order
nf = [[n - 1 - v.index for v in f.verts] for f in bm.faces]       # and triangles
orig = [Vector(v) for v in [(1, 1, 1), (-1, 0.2, 0.3), (0.5, -1, -0.7)]]
fit, how = sculpt.match_positions(orig, nv, nf)
print("fit", how, [tuple(round(c, 2) for c in p) for p in fit])
assert how == "nearest" and all(abs(max(abs(c) for c in p) - 1.1) < 0.02 for p in fit)
print("SCULPT TESTS PASSED")
sms.unregister()
