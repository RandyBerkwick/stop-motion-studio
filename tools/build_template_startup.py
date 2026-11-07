"""Writes app_template/StopMotionStudio/startup.blend: a ready stage
(floor, back wall, camera, warm light, 12 fps, 1080p) instead of the cube.
    python3 tools/build_template_startup.py"""
import math, os
import bpy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bpy.ops.wm.read_factory_settings(use_empty=False)
scene = bpy.context.scene
for ob in list(scene.objects):
    if ob.type in {'MESH'}:
        bpy.data.objects.remove(ob)
scene.render.fps = 12
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.frame_start = scene.frame_end = 1
scene.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else scene.render.engine
import bmesh
def plane(name, size, matrix):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size, matrix=matrix); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); return ob
from mathutils import Matrix
plane("Floor", 3.0, Matrix.Identity(4))
plane("Back wall", 3.0, Matrix.Translation((0, 2.0, 2.0)) @ Matrix.Rotation(math.radians(90), 4, 'X'))
cam = scene.camera
cam.name = "Camera A"; cam.data.lens = 35
cam.location = (0.0, -5.0, 1.4); cam.rotation_euler = (math.radians(86), 0, 0)
light = next((o for o in scene.objects if o.type == 'LIGHT'), None)
if light is not None:
    light.name = "Lamp"; light.data.energy = 600; light.data.color = (1.0, 0.85, 0.65)
    light.location = (-2.0, -2.5, 3.0)
path = os.path.join(ROOT, "app_template", "StopMotionStudio", "startup.blend")
bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
print("wrote", path)
