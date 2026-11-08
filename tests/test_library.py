"""Library: add things to it, list them, bring them in as a puppet / prop / set piece, standing on the set."""
import os, sys, runpy, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import library, puppet

lib = tempfile.mkdtemp(prefix="sm_lib_")
library.LIBRARY_DIR = lib

# --- build Bramble in its own scene and keep him (rig + meshes) in the library
g = runpy.run_path(os.path.join(ROOT, "scripts", "make_test_puppet.py"))
arm = g["arm"]
src_scene = g["scene"]
with bpy.context.temp_override(scene=src_scene, view_layer=src_scene.view_layers[0]):
    path = library.add_to_library(bpy.context, [arm], "Bramble")
assert os.path.basename(path) == "Bramble.blend", path
# a puppet already set up keeps its foot pins
with bpy.context.temp_override(scene=src_scene, view_layer=src_scene.view_layers[0]):
    puppet.make_puppet(bpy.context, arm)
    pins = [r.pin.name for r in arm.stop_motion_puppet.rings if r.pin]
    library.add_to_library(bpy.context, [arm], "Bramble ready")
assert pins
mug = bpy.data.objects["Mug"]
library.add_to_library(bpy.context, [mug], "Mug")
library.add_to_library(bpy.context, [mug], "Mug")            # a second one doesn't overwrite
files = library.list_files()
print("library", files)
assert files == ["Bramble ready.blend", "Bramble.blend", "Mug 2.blend", "Mug.blend"], files
items = library.contents(os.path.join(lib, "Bramble.blend"))
assert items == [(library.WHOLE_FILE, "Bramble")], items

# a file with collections lists each collection
coll_file = os.path.join(lib, "Garden.blend")
c1, c2 = bpy.data.collections.new("Bush"), bpy.data.collections.new("Flower")
for c, size in ((c1, 1.0), (c2, 0.2)):
    me = bpy.data.meshes.new(c.name)
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=size); bm.to_mesh(me); bm.free()
    c.objects.link(bpy.data.objects.new(c.name + " mesh", me))
bpy.data.libraries.write(coll_file, {c1, c2}, fake_user=True)
assert sorted(library.contents(coll_file)) == [("Bush", "Bush"), ("Flower", "Flower")]

# --- a fresh stage: floor + camera looking at the middle
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
library.LIBRARY_DIR = lib
scene = bpy.context.scene
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
cam = bpy.data.objects.new("Camera A", bpy.data.cameras.new("Camera A"))
scene.collection.objects.link(cam)
cam.location = (0, -6, 2)
import math
from mathutils import Vector
direction = Vector((0.5, 0, 0)) - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
bpy.context.view_layer.update()

assert bpy.ops.stop_motion.bring_in(path="Bramble.blend", kind='PUPPET') == {'FINISHED'}
bram = [o for o in scene.objects if o.type == 'ARMATURE']
assert len(bram) == 1 and bram[0].stop_motion_puppet.enabled, "came in as a puppet"
pp = bram[0].stop_motion_puppet
print("puppet rings", len(pp.rings), "swap sets", len(pp.swap_sets))
assert len(pp.rings) >= 5 and len(pp.swap_sets) >= 2
meshes = [o for o in scene.objects if o.type == 'MESH' and o.parent == bram[0]]
assert meshes, "his meshes came with him"
dg = bpy.context.evaluated_depsgraph_get()
low = min((o.matrix_world @ Vector(c)).z for o in meshes if o.visible_get() for c in o.bound_box)
centre = sum((o.matrix_world.translation for o in meshes), Vector()) / len(meshes)
print("stands at", tuple(round(v, 2) for v in centre), "lowest point", round(low, 3))
assert abs(low) < 0.02, "standing on the floor"
assert abs(centre.x - 0.5) < 0.3 and abs(centre.y) < 0.3, "where the camera is looking"

assert bpy.ops.stop_motion.bring_in(path="Bramble ready.blend", kind='PUPPET') == {'FINISHED'}
b2 = [o for o in scene.objects if o.type == 'ARMATURE' and o not in bram][0]
pins2 = [r.pin for r in b2.stop_motion_puppet.rings if r.pin]
assert pins2 and all(p.name in scene.objects for p in pins2), "foot pins came with him, in the scene"
assert bpy.ops.stop_motion.bring_in(path="Mug.blend", kind='PROP') == {'FINISHED'}
mugs = [o for o in scene.objects if o.name.startswith("Mug")]
assert len(mugs) == 1 and mugs[0].stop_motion_prop, mugs

assert bpy.ops.stop_motion.bring_in(path="Garden.blend", item="Bush", kind='SET') == {'FINISHED'}
bush = scene.objects.get("Bush mesh")
assert bush is not None and bush.stop_motion_set and not bush.stop_motion_prop
assert "Flower mesh" not in scene.objects, "only the collection asked for"
print("LIBRARY TESTS PASSED")
sms.unregister()
