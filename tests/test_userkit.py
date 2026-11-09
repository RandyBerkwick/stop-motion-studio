"""Your own kit parts (Library › Kit), the built-in hair/hats/extras, and Wear it."""
import json, math, os, shutil, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, bmesh
from mathutils import Matrix, Vector
import stop_motion_studio as sms
sms.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
from stop_motion_studio import accessories, assembly, library, puppet, userkit, wear, solid

ctx = bpy.context
lib = tempfile.mkdtemp(prefix="smkit")
library.LIBRARY_DIR = lib
root = userkit.ensure_folders()
assert all(os.path.isdir(os.path.join(root, f)) for f in userkit.FOLDERS.values())
assert os.path.exists(os.path.join(root, "Read me.txt"))


def world_pts(ob):
    return [ob.matrix_world @ v.co for v in ob.data.vertices]


def bounds(ob):
    pts = world_pts(ob)
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def part(arm, kind, side=""):
    for o in assembly.kit_parts(arm):
        d = json.loads(o["sm_part"])
        if d["kind"] == kind and d.get("side", "") == side:
            return o
    return None


# ---- make some kit files, the way someone would in Blender

def mesh_ob(name, maker, matrix=Matrix.Identity(4)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    maker(bm)
    bm.transform(matrix)
    bm.to_mesh(me)
    bm.free()
    return bpy.data.objects.new(name, me)


def textured(name):
    img = bpy.data.images.new(name + " tex", 8, 8)
    img.pixels = [1.0, 0.8, 0.1, 1.0] * 64
    img.pack()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    m.node_tree.links.new(tex.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    return m


def write(path, ids):
    bpy.data.libraries.write(path, set(ids), fake_user=True)


# Hats.blend: two collections, "Cap" and "Crown", textured gold crown, modelled big and off to the side
gold = textured("Gold")
cap = mesh_ob("CapMesh", lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1.0),
              Matrix.Translation((10, 0, 0)) @ Matrix.Diagonal((1, 1, 0.5, 1)))
crown = mesh_ob("CrownMesh", lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=2, radius2=2.4, depth=1.5),
                Matrix.Translation((-4, 3, 7)))
crown.data.materials.append(gold)
c_cap = bpy.data.collections.new("Cap"); c_cap.objects.link(cap)
c_crown = bpy.data.collections.new("Crown"); c_crown.objects.link(crown)
write(os.path.join(root, "Hats", "Hats.blend"), [c_cap, c_crown])
# a square head, 3 m tall, far away
head = mesh_ob("Head", lambda bm: bmesh.ops.create_cube(bm, size=1.0), Matrix.Translation((5, 5, 5)) @ Matrix.Diagonal((2.5, 2.4, 3, 1)))
write(os.path.join(root, "Heads", "Square head.blend"), [head])
# a noodle arm lying along X, from near the middle outwards (as if modelled in a T-pose)
arm_m = mesh_ob("Noodle", lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.12, radius2=0.08, depth=1.8),
                Matrix.Translation((1.1, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
write(os.path.join(root, "Arms", "Noodle arm.blend"), [arm_m])
# a clog
clog = mesh_ob("Clog", lambda bm: bmesh.ops.create_cube(bm, size=1.0), Matrix.Diagonal((0.4, 1.0, 0.3, 1)))
write(os.path.join(root, "Feet", "Clog.blend"), [clog])
for ob in (cap, crown, head, arm_m, clog):
    me = ob.data
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
for c in (c_cap, c_crown):
    bpy.data.collections.remove(c)
bpy.data.materials.remove(gold)

# ---- listing
hats = userkit.parts("hat")
assert [l for _v, l, _p, _i in hats] == ["Cap", "Crown"], hats
assert [l for _v, l, _p, _i in userkit.parts("head")] == ["Square head"]
assert userkit.parts("body") == [] and userkit.parts("nope") == []
assert library.list_files() == [], "kit parts don't clutter Bring in…"
v_crown = hats[1][0]
assert userkit.label_of(v_crown) == "Crown" and userkit.is_user(v_crown)

# ---- a person, with your head
arm = assembly.new_build(ctx, "Pip", 'PERSON', Vector((0, 0, 0)))
assembly.starter(ctx, arm)
assert part(arm, "hair") is None and part(arm, "hat") is None, "no hair or hat to start with"
J, _info = assembly._j(arm)
assembly.add_part(ctx, arm, "head", userkit.parts("head")[0][0])
h = part(arm, "head")
assert h.parent_type == 'BONE' and h.parent_bone == "head"
lo, hi = bounds(h)
want = (J["crown"] - J["skull"]).length * 1.22
assert abs((hi.z - lo.z) - want) < 1e-3, (hi.z - lo.z, want)
mid = (J["skull"] + J["crown"]) / 2
assert ((lo + hi) / 2 - mid).length < 1e-3, "centred on the head joints"
assert h.data.materials[0].name.startswith("SM Clay"), "an untextured part takes the kit colour"

# a textured crown on top
assembly.add_part(ctx, arm, "hat", v_crown)
hat = part(arm, "hat")
assert hat.parent_bone == "head"
assert hat.data.materials[0].name.startswith("Gold"), "your texture is kept"
img_nodes = [n for n in hat.data.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE']
assert img_nodes and img_nodes[0].image is not None and img_nodes[0].image.packed_file is not None
hlo, hhi = bounds(hat)
c, half, top = accessories.head_frame(arm)
assert abs(hlo.z - (top - half.z * 2 * 0.28)) < 1e-3, "the crown sits down over the top of the head"
assert abs((hhi.x - hlo.x) - half.x * 2 * 1.15) < 1e-3
assembly.set_colour(ctx, arm, "hat", "blue")
assert hat.data.materials[0].name.startswith("Gold"), "colouring doesn't paint over your texture"

# a bigger head: head and hat are made again, and the hat still sits on top
assembly.change_build(ctx, arm, props={"head": 1.4})
h2, hat2 = part(arm, "head"), part(arm, "hat")
c2, half2, top2 = accessories.head_frame(arm)
assert top2 > top + 0.02
assert abs(bounds(hat2)[0].z - (top2 - half2.z * 2 * 0.28)) < 1e-3

# the part is read once and kept: it still works with the file gone
os.rename(os.path.join(root, "Hats", "Hats.blend"), os.path.join(root, "Hats", "away.tmp"))
assembly.change_build(ctx, arm, props={"head": 1.2})
assert part(arm, "hat") is not None and part(arm, "hat").data.materials[0].name.startswith("Gold")
os.rename(os.path.join(root, "Hats", "away.tmp"), os.path.join(root, "Hats", "Hats.blend"))
srcs = [m for m in bpy.data.meshes if m.get("sm_kit_src")]
assert len(srcs) == 2 and all(m.use_fake_user for m in srcs), [m.name for m in srcs]

# your arms: the left as modelled, the right a mirror, each from shoulder to wrist and bending
assembly.add_part(ctx, arm, "arms", userkit.parts("arms")[0][0])
J, _info = assembly._j(arm)
for side in ("L", "R"):
    a = part(arm, "arms", side)
    assert a is not None and a.modifiers.get("SM Armature") is not None
    assert {g.name for g in a.vertex_groups} == {"upper_arm." + side, "forearm." + side}
    pts = world_pts(a)
    near_sh = min((p - J["shoulder." + side]).length for p in pts)
    near_wr = min((p - J["wrist." + side]).length for p in pts)
    assert near_sh < 0.08 and near_wr < 0.08, (side, near_sh, near_wr)
    assert all(len(v.groups) for v in a.data.vertices), "every point bends with a bone"
la, ra = bounds(part(arm, "arms", "L")), bounds(part(arm, "arms", "R"))
assert la[0].x > 0 and ra[1].x < 0, "left arm on the left, right arm mirrored to the right"
# your feet on the floor
assembly.add_part(ctx, arm, "feet", userkit.parts("feet")[0][0])
for side in ("L", "R"):
    f = part(arm, "feet", side)
    assert abs(bounds(f)[0].z - J["toe." + side].z) < 1e-4 and f.parent_bone == "foot." + side

# ---- the built-in hair, hats and extras
for kind, variants in (("hair", ["mop", "bun", "spiky"]), ("hat", ["cap", "bobble", "top"]), ("extra", ["tag", "scarf", "glasses"])):
    for v in variants:
        assembly.add_part(ctx, arm, kind, v)
        ob = part(arm, kind)
        assert ob is not None and len(ob.data.vertices) > 20, (kind, v)
        assert ob.parent_type == 'BONE' and ob.parent_bone in ("head", "chest"), (kind, v, ob.parent_bone)
    assembly.add_part(ctx, arm, kind, "none")
    assert part(arm, kind) is None, kind
assembly.add_part(ctx, arm, "extra", "tag")
tag = part(arm, "extra")
assert len(tag.data.materials) == 2 and any(p.material_index == 1 for p in tag.data.polygons), "the name is written on"
assembly.add_part(ctx, arm, "hair", "mop")
hair = part(arm, "hair")
hb = bounds(hair)
c, half, top = accessories.head_frame(arm)
assert hb[1].z > top and hb[0].y > c.y - half.y * 1.1, "hair on top, not over the face"

# swapping the body fits the tag to it again
assembly.add_part(ctx, arm, "body", "barrel")
assert part(arm, "extra") is not None

# ---- a puppet: the crown rides on the head
assembly.add_part(ctx, arm, "hat", v_crown)
assembly.finish_build(ctx, arm)
ctx.view_layer.update()
before = bounds(part(arm, "hat"))[1].copy()
pb = arm.pose.bones["head"]
pb.rotation_mode = 'XYZ'
pb.rotation_euler = (0.5, 0, 0)
ctx.view_layer.update()
assert (bounds(part(arm, "hat"))[1] - before).length > 0.01, "the hat moves with the head"
pb.rotation_euler = (0, 0, 0)
ctx.view_layer.update()

# ---- wear it: a badge on the chest, then a hat swap set
badge = mesh_ob("Star badge", lambda bm: bmesh.ops.create_cube(bm, size=1.0), Matrix.Translation((2, -2, 0.5)) @ Matrix.Diagonal((0.04, 0.01, 0.04, 1)))
ctx.scene.collection.objects.link(badge)
badge.stop_motion_prop = True
ctx.view_layer.update()
body = part(arm, "body")
J, _info = assembly._j(arm)
chest_pt, _hw = accessories.chest_front(arm)
assert wear.bone_at(arm, chest_pt) in ("chest", "spine")
assert wear.wear_at(ctx, badge, body, chest_pt, Vector((0, -1, 0))) is not None
assert badge.get("sm_worn") in ("chest", "spine") and badge.parent == arm and not badge.stop_motion_prop
blo, bhi = bounds(badge)
assert abs(bhi.y - chest_pt.y) < 0.01 and blo.y < chest_pt.y, "its back is pressed onto the chest"
assert abs((blo.z + bhi.z) / 2 - chest_pt.z) < 1e-3, "centred where it was clicked"
assert badge not in solid.props(ctx.scene)
# your own parts can't be "worn" onto the puppet they belong to
assert wear.wear_at(ctx, part(arm, "head"), body, chest_pt, Vector((0, -1, 0))) is None

party = mesh_ob("Party hat", lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.05, radius2=0, depth=0.12), Matrix.Translation((3, 0, 0)))
ctx.scene.collection.objects.link(party)
ctx.view_layer.update()
c, half, top = accessories.head_frame(arm)
wear.wear(ctx, party, arm, "head", Vector((c.x, c.y, top)), Vector((0, 0, 1)))
assert abs(bounds(party)[0].z - (top - 0.12 * 0.08)) < 2e-3, "sits on the top of the head"
wear.set_swap(ctx, party, "Hat")
assert party.name == "Hat_PartyHat" and bpy.data.objects.get("Hat_None") is not None
sets = {s.name: s for s in arm.stop_motion_puppet.swap_sets}
assert "Hat" in sets and len(sets["Hat"].items) == 2, list(sets)
assert puppet.swap_active(sets["Hat"]) == [it.obj for it in sets["Hat"].items].index(party), "the new one shows"
none_i = [it.label for it in sets["Hat"].items].index("None")
puppet.apply_swap(sets["Hat"], none_i)
assert party.hide_viewport and party.hide_render
assert party in puppet.swap_objects(arm), "which hat shows is kept with each shot"
puppet.apply_swap(sets["Hat"], 1 - none_i)

# take it off: a prop again, its name back, and the empty set goes
wear.take_off(ctx, party)
assert party.parent is None and party.stop_motion_prop and party.name == "Party hat"
assert bpy.data.objects.get("Hat_None") is None and "Hat" not in {s.name for s in arm.stop_motion_puppet.swap_sets}
assert not party.hide_viewport

# operators
assert bpy.ops.stop_motion.take_off(name=badge.name) == {'FINISHED'} and badge.parent is None
assert bpy.ops.stop_motion.wear(name=badge.name, puppet=arm.name, bone="chest") == {'FINISHED'}
assert badge.parent == arm and badge.parent_bone == "chest"
hat_before = part(arm, "hat").name
assert bpy.ops.stop_motion.build_part(puppet=arm.name, kind="hat", variant="user:Hats/Gone.blend|X") == {'CANCELLED'}
assert part(arm, "hat") is not None and part(arm, "hat").name == hat_before, "a missing file doesn't cost you your hat"

# saved to the library, the hat and the badge go with the puppet
path = library.add_to_library(ctx, [arm], "Pip with hat")
with bpy.data.libraries.load(path) as (src, _dst):
    names = set(src.objects)
assert part(arm, "hat").name in names and badge.name in names, names

shutil.rmtree(lib, ignore_errors=True)
print("userkit ok")
