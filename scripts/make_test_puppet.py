# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds a test puppet scene for Stop Motion Studio.

Run it either way:
  - Blender › Scripting tab › Open this file › Run Script
  - Terminal: /Applications/Blender.app/Contents/MacOS/Blender --python scripts/make_test_puppet.py

It adds a NEW scene called "Puppet Test" (your current scene is left alone):
a chunky clay figure "Bramble" with a rig whose bone names Make Puppet
recognises, swap parts (eyes, mouth, right hand as meshes; brows as
shape keys), a floor, a table, a camera and lights.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

SCENE_NAME = "Puppet Test"


# ------------------------------------------------------------------ helpers

def material(name, rgb, rough=0.55):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
    return mat


def add_sphere(bm, matrix, mat_index=0, segs=24, rings=14):
    res = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0, matrix=matrix)
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mat_index
        f.smooth = True
    return res["verts"]


def add_tube(bm, a, b, radius, mat_index=0, segs=16):
    a, b = Vector(a), Vector(b)
    d = b - a
    rot = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    m = Matrix.Translation((a + b) / 2) @ rot
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=radius, radius2=radius * 0.9,
                                depth=d.length, matrix=m)
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mat_index
        f.smooth = True
    return res["verts"]


def mesh_object(name, bm, mats, collection):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def S(x, y, z, sx, sy=None, sz=None):
    sy = sx if sy is None else sy
    sz = sx if sz is None else sz
    return Matrix.Translation((x, y, z)) @ Matrix.Diagonal((sx, sy, sz, 1.0))


def parent_to_bone(ob, arm, bone):
    ob.parent = arm
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    # keep the object where it was built: undo the bone's rest matrix
    b = arm.data.bones[bone]
    rest = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    ob.matrix_parent_inverse = rest.inverted()


# -------------------------------------------------------------------- build

def build():
    scene = bpy.data.scenes.get(SCENE_NAME)
    if scene is not None:
        bpy.data.scenes.remove(scene)
    scene = bpy.data.scenes.new(SCENE_NAME)
    scene.render.fps = 12
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.frame_start = scene.frame_end = 1
    col = scene.collection
    if bpy.context.window is not None:
        bpy.context.window.scene = scene

    red = material("Clay red", (0.55, 0.10, 0.05))
    skin = material("Clay skin", (0.78, 0.52, 0.36))
    navy = material("Clay trousers", (0.10, 0.14, 0.22))
    boot = material("Clay boots", (0.24, 0.15, 0.09))
    white = material("Clay eye white", (0.95, 0.93, 0.88), 0.35)
    dark = material("Clay dark", (0.05, 0.03, 0.02))
    mouth_m = material("Clay mouth", (0.30, 0.08, 0.05))
    hair = material("Clay hair", (0.35, 0.21, 0.12))
    wood = material("Wood", (0.36, 0.20, 0.10), 0.7)
    wall = material("Felt wall", (0.16, 0.28, 0.22), 0.9)

    # --- rig (names chosen so Make Puppet recognises them)
    arm = bpy.data.objects.new("Bramble", bpy.data.armatures.new("Bramble rig"))
    col.objects.link(arm)
    arm.show_in_front = True
    bones = {}

    def bone(name, head, tail, parent=None, connect=False):
        bones[name] = (head, tail, parent, connect)

    bone("hips", (0, 0, 0.95), (0, 0, 1.10))
    bone("spine", (0, 0, 1.10), (0, 0, 1.40), "hips", True)
    bone("chest", (0, 0, 1.40), (0, 0, 1.62), "spine", True)
    bone("head", (0, 0, 1.62), (0, 0, 2.15), "chest", True)
    for s, x in (("L", 1), ("R", -1)):
        bone("thigh." + s, (0.16 * x, 0, 0.95), (0.17 * x, -0.03, 0.52), "hips")
        bone("shin." + s, (0.17 * x, -0.03, 0.52), (0.17 * x, 0, 0.12), "thigh." + s, True)
        bone("foot." + s, (0.17 * x, 0, 0.12), (0.17 * x, -0.22, 0.04), "shin." + s, True)
        bone("upper_arm." + s, (0.30 * x, 0, 1.52), (0.52 * x, 0, 1.26), "chest")
        bone("forearm." + s, (0.52 * x, 0, 1.26), (0.66 * x, -0.04, 1.02), "upper_arm." + s, True)
        bone("hand." + s, (0.66 * x, -0.04, 1.02), (0.72 * x, -0.06, 0.90), "forearm." + s, True)

    view_layer = bpy.context.view_layer if bpy.context.scene == scene else scene.view_layers[0]
    # Edit bones need the armature active in edit mode in *this* scene's view layer.
    prev_active = view_layer.objects.active
    view_layer.objects.active = arm
    with bpy.context.temp_override(scene=scene, view_layer=view_layer, active_object=arm,
                                   object=arm, edit_object=arm):
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        for name, (h, t, p, c) in bones.items():
            b = eb.new(name)
            b.head, b.tail = h, t
        for name, (h, t, p, c) in bones.items():
            if p:
                eb[name].parent = eb[p]
                eb[name].use_connect = c
        bpy.ops.object.mode_set(mode='OBJECT')
    view_layer.objects.active = prev_active

    # --- body: one mesh, bent by the rig
    bm = bmesh.new()
    add_sphere(bm, S(0, 0, 1.28, 0.30, 0.25, 0.40), 0)                  # jumper
    add_sphere(bm, S(0, 0, 1.92, 0.33, 0.29, 0.30), 1)                  # head
    add_sphere(bm, S(0, -0.27, 1.86, 0.09, 0.08, 0.07), 1)              # nose
    for s in (1, -1):
        add_sphere(bm, S(0.32 * s, 0, 1.90, 0.06, 0.04, 0.08), 1)      # ears
        add_tube(bm, (0.16 * s, 0, 0.98), (0.17 * s, -0.03, 0.52), 0.10, 2)
        add_tube(bm, (0.17 * s, -0.03, 0.52), (0.17 * s, 0, 0.12), 0.09, 2)
        add_sphere(bm, S(0.17 * s, -0.08, 0.07, 0.12, 0.19, 0.08), 3)  # boots
        add_tube(bm, (0.28 * s, 0, 1.52), (0.52 * s, 0, 1.26), 0.075, 0)
        add_tube(bm, (0.52 * s, 0, 1.26), (0.66 * s, -0.04, 1.02), 0.07, 0)
    add_sphere(bm, S(0.69, -0.05, 0.96, 0.08), 1)                        # left hand (fixed)
    body = mesh_object("Body", bm, [red, skin, navy, boot], col)
    mod = body.modifiers.new("Rig", 'ARMATURE')
    mod.object = arm
    body.parent = arm

    # weights: each vertex follows its nearest bone
    seg = {n: (Vector(h), Vector(t)) for n, (h, t, _p, _c) in bones.items()}
    groups = {n: body.vertex_groups.new(name=n) for n in seg}
    for v in body.data.vertices:
        best, bd = None, 1e9
        for n, (h, t) in seg.items():
            d = t - h
            k = max(0.0, min(1.0, (v.co - h).dot(d) / d.length_squared))
            dist = (v.co - (h + d * k)).length
            if dist < bd:
                best, bd = n, dist
        groups[best].add([v.index], 1.0, 'REPLACE')

    # --- swap parts parented to bones (meshes named Set_Part)
    def part(name, bone_name, build_fn, mats):
        bm2 = bmesh.new()
        build_fn(bm2)
        ob = mesh_object(name, bm2, mats, col)
        parent_to_bone(ob, arm, bone_name)
        return ob

    def eyes_open(b):
        for s in (1, -1):
            add_sphere(b, S(0.11 * s, -0.25, 1.98, 0.085, 0.05, 0.10), 0)
            add_sphere(b, S(0.10 * s, -0.295, 1.97, 0.025), 1)

    def eyes_shut(b):
        for s in (1, -1):
            add_sphere(b, S(0.11 * s, -0.25, 1.96, 0.085, 0.05, 0.025), 0)

    def eyes_look(b):
        for s in (1, -1):
            add_sphere(b, S(0.11 * s, -0.25, 1.98, 0.085, 0.05, 0.10), 0)
            add_sphere(b, S(0.11 * s + 0.04, -0.29, 1.97, 0.025), 1)

    part("Eyes_Open", "head", eyes_open, [skin, dark])  # material 0 overridden below
    part("Eyes_Shut", "head", eyes_shut, [skin])
    part("Eyes_Look", "head", eyes_look, [skin, dark])
    for n in ("Eyes_Open", "Eyes_Look"):
        bpy.data.objects[n].data.materials[0] = white
    bpy.data.objects["Eyes_Shut"].data.materials[0] = skin

    part("Mouth_Grin", "head", lambda b: add_sphere(b, S(0, -0.25, 1.76, 0.14, 0.04, 0.045), 0), [mouth_m])
    part("Mouth_O", "head", lambda b: add_sphere(b, S(0, -0.26, 1.76, 0.05, 0.04, 0.06), 0), [mouth_m])
    part("Mouth_Closed", "head", lambda b: add_sphere(b, S(0, -0.255, 1.765, 0.10, 0.03, 0.012), 0), [mouth_m])

    part("Hand_Open", "hand.R", lambda b: add_sphere(b, S(-0.69, -0.05, 0.94, 0.06, 0.11, 0.10), 0), [skin])
    part("Hand_Fist", "hand.R", lambda b: add_sphere(b, S(-0.69, -0.05, 0.96, 0.08), 0), [skin])

    # brows: one mesh with shape keys Brows_Up / Brows_Cross
    bm3 = bmesh.new()
    for s in (1, -1):
        bmesh.ops.create_cube(bm3, size=1.0, matrix=S(0.11 * s, -0.24, 2.10, 0.09, 0.03, 0.02))
    brows = mesh_object("Brows", bm3, [hair], col)
    parent_to_bone(brows, arm, "head")
    brows.shape_key_add(name="Basis")
    up = brows.shape_key_add(name="Brows_Up")
    cross = brows.shape_key_add(name="Brows_Cross")
    for i, v in enumerate(brows.data.vertices):
        up.data[i].co = v.co + Vector((0, 0, 0.05))
        tilt = -0.04 if abs(v.co.x) < 0.11 else 0.02
        cross.data[i].co = v.co + Vector((0, 0, tilt))
    up.value = cross.value = 0.0  # new shape keys start fully on in Blender 5.x

    # --- set
    bmf = bmesh.new()
    bmesh.ops.create_grid(bmf, x_segments=1, y_segments=1, size=4.0)
    floor = mesh_object("Floor", bmf, [wood], col)
    bmw = bmesh.new()
    bmesh.ops.create_grid(bmw, x_segments=1, y_segments=1, size=4.0,
                          matrix=Matrix.Translation((0, 2.0, 2.0)) @ Matrix.Rotation(math.radians(90), 4, 'X'))
    mesh_object("Wall", bmw, [wall], col)
    bmt = bmesh.new()
    bmesh.ops.create_cube(bmt, size=1.0, matrix=S(1.05, 0.2, 0.78, 1.15, 0.85, 0.05))
    for x in (0.55, 1.55):
        for y in (-0.15, 0.55):
            bmesh.ops.create_cube(bmt, size=1.0, matrix=S(x, y, 0.38, 0.05, 0.05, 0.76))
    mesh_object("Table", bmt, [wood], col)

    # a prop to drop and hold: a mug floating above the table (Drop puts it on the top)
    bmm = bmesh.new()
    add_tube(bmm, (0, 0, -0.05), (0, 0, 0.05), 0.05, 0)
    mug = mesh_object("Mug", bmm, [white], col)
    mug.location = (0.95, 0.1, 1.05)
    if hasattr(mug, "stop_motion_prop"):
        mug.stop_motion_prop = True

    # --- camera and lights
    cam = bpy.data.objects.new("Camera A", bpy.data.cameras.new("Camera A"))
    cam.data.lens = 35
    col.objects.link(cam)
    cam.location = (0.6, -5.2, 1.55)
    cam.rotation_euler = (math.radians(87), 0, math.radians(6))
    scene.camera = cam

    key = bpy.data.objects.new("Key light", bpy.data.lights.new("Key light", 'AREA'))
    key.data.energy = 600
    key.data.size = 2.0
    key.data.color = (1.0, 0.88, 0.72)
    key.location = (-2.5, -3.0, 3.5)
    key.rotation_euler = (math.radians(50), 0, math.radians(-40))
    col.objects.link(key)
    fill = bpy.data.objects.new("Fill light", bpy.data.lights.new("Fill light", 'AREA'))
    fill.data.energy = 150
    fill.data.size = 3.0
    fill.data.color = (0.75, 0.85, 1.0)
    fill.location = (3.0, -2.5, 2.0)
    fill.rotation_euler = (math.radians(65), 0, math.radians(50))
    col.objects.link(fill)

    world = bpy.data.worlds.new("Puppet Test world")
    world.color = (0.05, 0.05, 0.06)
    scene.world = world
    return scene, arm


scene, arm = build()
print("Built scene %r with puppet %r. Next: select %s, then Stop Motion › Puppet › Make Puppet."
      % (scene.name, arm.name, arm.name))
