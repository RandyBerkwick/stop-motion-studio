"""Puppet studio: armatures and the parts kit, faces and hands, joints on a sculpt, trying out, saving."""
import json, math, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy, bmesh
from mathutils import Matrix, Vector
import stop_motion_studio as sms
sms.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
from stop_motion_studio import assembly, faces, library, puppet, rigsculpt, trial

ctx = bpy.context


def bounds(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def part(arm, kind, side=""):
    for o in assembly.kit_parts(arm):
        d = json.loads(o["sm_part"])
        if d["kind"] == kind and d.get("side", "") == side:
            return o
    return None


# --- a person from the kit
assert bpy.ops.stop_motion.new_build(template='PERSON', name="Pip") == {'FINISHED'}
pip = bpy.data.objects["Pip"]
kinds = sorted({json.loads(o["sm_part"])["kind"] for o in assembly.kit_parts(pip)})
print("Pip's parts", kinds, len(assembly.kit_parts(pip)))
assert kinds == ["arms", "body", "feet", "head", "legs"] and len(assembly.kit_parts(pip)) == 8   # arms, legs, feet in pairs
for o in assembly.kit_parts(pip):
    d = json.loads(o["sm_part"])
    if d["kind"] in ("head", "feet"):
        assert o.parent_type == 'BONE', o.name
    else:
        mod = o.modifiers.get("SM Armature")
        assert mod is not None and mod.object == pip, o.name
        unweighted = [v for v in o.data.vertices if not any(g.weight > 0.01 for g in v.groups)]
        assert not unweighted, (o.name, len(unweighted))
# feet on the floor, head on top
lo, hi = bounds(part(pip, "feet", "L"))
assert abs(lo.z) < 0.02, lo.z
assert bounds(part(pip, "head"))[1].z > 1.55

# swapping a part, colouring it
assert bpy.ops.stop_motion.build_part(puppet="Pip", kind="head", variant="long") == {'FINISHED'}
assert json.loads(part(pip, "head")["sm_part"])["variant"] == "long" and len([o for o in assembly.kit_parts(pip) if json.loads(o["sm_part"])["kind"] == "head"]) == 1
assert bpy.ops.stop_motion.build_colour(puppet="Pip", kind="body", colour="red") == {'FINISHED'}
assert part(pip, "body").data.materials[0].name == "SM Clay red"

# proportions: a bigger head makes the head part bigger; longer legs make him taller
h0 = bounds(part(pip, "head"))
assert bpy.ops.stop_motion.build_shape(puppet="Pip", prop="head", value=1.4) == {'FINISHED'}
h1 = bounds(part(pip, "head"))
assert (h1[1] - h1[0]).z > (h0[1] - h0[0]).z * 1.25, "head grew"
top0 = bounds(part(pip, "head"))[1].z
assert bpy.ops.stop_motion.build_shape(puppet="Pip", prop="legs", value=1.3) == {'FINISHED'}
assert bounds(part(pip, "head"))[1].z > top0 + 0.15, "longer legs: taller"
assert abs(bounds(part(pip, "feet", "L"))[0].z) < 0.02, "still standing on the floor"
assert json.loads(part(pip, "body")["sm_part"])["colour"] == "red", "colours survive a remake"
print("kit and proportions ok")

# --- face and hands
assert bpy.ops.stop_motion.make_faces(puppet="Pip") == {'FINISHED'}
pp = assembly.finish_build(ctx, pip)
sets = {s.name: [i.label for i in s.items] for s in pp.swap_sets}
print("swap sets", sets)
assert sets["Mouth"] == ["Rest", "AI", "E", "O", "U", "MBP", "FV", "Smile"]
assert sets["Eyes"][:3] == ["Open", "Half", "Shut"] and "Left hand" in sets and "Right hand" in sets
head_c = sum(bounds(part(pip, "head")), Vector()) / 2
mouth = bpy.data.objects["Mouth_O"]
mc = sum(bounds(mouth), Vector()) / 2
ec = sum(bounds(bpy.data.objects["Eyes_Open"]), Vector()) / 2
assert mc.y < head_c.y and ec.y < head_c.y, "on the front of the face"
assert ec.z > mc.z, "eyes above the mouth"
# one of each set shows; swapping works
assert sum(1 for i in pp.swap_sets["Mouth"].items if not i.obj.hide_viewport) == 1
mouth_set = [i for i, s in enumerate(pp.swap_sets) if s.name == "Mouth"][0]
puppet.apply_swap(pp.swap_sets[mouth_set], 3)
assert not bpy.data.objects["Mouth_O"].hide_viewport and bpy.data.objects["Mouth_Rest"].hide_viewport
# face pieces are remade to fit when the head grows, and hands follow the hand bones
assert bpy.ops.stop_motion.build_shape(puppet="Pip", prop="head", value=1.0) == {'FINISHED'}
assert pip.stop_motion_puppet.enabled and len(pip.stop_motion_puppet.swap_sets) >= 5, "still a puppet with its swaps"
assert bpy.data.objects["LeftHand_Fist"].parent_bone == "hand.L"
assert bpy.ops.stop_motion.hand_style(puppet="Pip", style='FINGERS') == {'FINISHED'}
print("faces ok")

# rings, pins and knee targets
rings = [r.label for r in pip.stop_motion_puppet.rings]
assert rings == ['Head', 'Body', 'Hips', 'Left hand', 'Right hand', 'Left foot', 'Right foot'], rings
assert all(r.knee is not None for r in pip.stop_motion_puppet.rings if r.pin)

# --- four legs
assert bpy.ops.stop_motion.new_build(template='FOUR_LEGS', name="Biscuit") == {'FINISHED'}
dog = bpy.data.objects["Biscuit"]
faces.make_all(ctx, dog)
pp = assembly.finish_build(ctx, dog)
labels = [(r.label, bool(r.pin)) for r in pp.rings]
print("Biscuit's rings", labels)
assert [l for l, _p in labels] == ['Head', 'Body', 'Hips', 'Tail', 'Front left foot', 'Front right foot', 'Back left foot', 'Back right foot']
assert sum(1 for _l, p in labels if p) == 4, "four pinned feet"
assert {s.name for s in pp.swap_sets} == {"Mouth", "Eyes"}
# changing a person into four legs keeps only parts that fit
pip2 = assembly.new_build(ctx, "Morph", 'PERSON', location=(4, 0, 0))
assembly.starter(ctx, pip2)
assembly.change_build(ctx, pip2, template='FOUR_LEGS')
assert {json.loads(o["sm_part"])["kind"] for o in assembly.kit_parts(pip2)} <= set(assembly.KIT['FOUR_LEGS'])
assert "tail" in pip2.data.bones and "front_foot.L" in pip2.data.bones
print("four legs ok")

# --- trying out
res = trial.try_out(ctx, pip)
assert [r["name"] for r in res] == ["Wave", "Sit", "Crouch", "Walk"] and all(os.path.exists(r["picture"]) for r in res)
assert all(abs(pb.rotation_quaternion.angle) < 1e-6 and pb.location.length < 1e-6 for pb in pip.pose.bones), "back to standing"
# a hard bend with volume keeping off: the check notices clay folding in
arm_part = part(pip, "arms", "R")
arm_part.modifiers["SM Armature"].use_deform_preserve_volume = False
vols, _t = trial.measure(ctx, pip)
v0 = vols[arm_part.name]
saved = trial._save_pose(pip)
trial.apply_pose(ctx, pip, ("Fold", [("forearm.R", "Y", 165, "up")], 0.0))
vols, _t = trial.measure(ctx, pip)
trial._restore_pose(ctx, pip, saved)
print("arm volume folded: %.0f%%" % (100 * vols[arm_part.name] / v0))
assert vols[arm_part.name] < v0 * 0.93
soft0 = assembly.build_info(pip).get("softness", 0.5)
trial.fix(ctx, pip, "SOFTEN")
assert assembly.build_info(pip)["softness"] > soft0 and pip.stop_motion_puppet.enabled
print("trying out ok")

# --- joints on a one-piece sculpt (made from a kit puppet, so we know where its joints really are)
ref = assembly.new_build(ctx, "Ref", 'PERSON')
assembly.starter(ctx, ref)
truth = assembly.joints('PERSON', None)
dg = ctx.evaluated_depsgraph_get()
bm = bmesh.new()
for o in assembly.kit_parts(ref):
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    me.transform(o.matrix_world)
    bm.from_mesh(me)
me = bpy.data.meshes.new("Wren"); bm.to_mesh(me); bm.free()
wren = bpy.data.objects.new("Wren", me); ctx.scene.collection.objects.link(wren)
wren.location.x = -3
for o in list(ref.children_recursive) + [ref]:
    bpy.data.objects.remove(o)
ctx.view_layer.update()
assert bpy.ops.stop_motion.guess_joints(mesh="Wren", template='PERSON') == {'FINISHED'}
g = rigsculpt.get_joints(wren)
errs = {k: (g[k] - (truth[k] + Vector((-3, 0, 0)))).length for k in ("neck", "pelvis", "shoulder.L", "elbow.L", "wrist.L", "hip.L", "knee.L")}
print("joint guesses within", round(max(errs.values()), 3), "m")
assert max(errs.values()) < 0.06
# clicking puts a joint halfway through the clay; the other side follows
tree, _v = rigsculpt.mesh_tree(ctx, wren)
elbow = truth["elbow.L"] + Vector((-3, 0, 0))
mid = rigsculpt.through(tree, elbow + Vector((0, -2, 0)), Vector((0, 1, 0)))
assert mid is not None and abs(mid.y - elbow.y) < 0.03, (mid, elbow)
rigsculpt.place(wren, g, "elbow.L", mid)
assert abs(rigsculpt.get_joints(wren)["elbow.R"].x - (2 * g["pelvis"].x - mid.x)) < 1e-6
assert bpy.ops.stop_motion.make_sculpt_rig(mesh="Wren") == {'FINISHED'}
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and assembly.build_info(o).get("sculpt") == "Wren")
assert len(rig.stop_motion_puppet.rings) == 7 and sum(1 for r in rig.stop_motion_puppet.rings if r.pin) == 2
unweighted = [v for v in wren.data.vertices if not any(gr.weight > 0.01 for gr in v.groups)]
assert not unweighted, len(unweighted)
# the head moves the whole head, ears and all
pb = rig.pose.bones["head"]
before = [wren.matrix_world @ v.co for v in wren.data.vertices]
pb.rotation_quaternion = Matrix.Rotation(0.5, 4, 'X').to_quaternion()
ctx.view_layer.update()
we = wren.evaluated_get(ctx.evaluated_depsgraph_get()).to_mesh()
top = max(range(len(before)), key=lambda i: before[i].z)
moved = (wren.matrix_world @ we.vertices[top].co - before[top]).length
low = min(range(len(before)), key=lambda i: before[i].z)
still = (wren.matrix_world @ we.vertices[low].co - before[low]).length
wren.evaluated_get(ctx.evaluated_depsgraph_get()).to_mesh_clear()
print("nodding: top of the head moved", round(moved, 3), "the feet", round(still, 4))
assert moved > 0.03 and still < 1e-4
pb.rotation_quaternion = (1, 0, 0, 0)
faces.make_set(ctx, rig, "Eyes")
assert any(o.get("sm_face", "").startswith("Eyes") for o in rig.children)
print("sculpt rig ok")

# --- save to the library and bring back
lib = tempfile.mkdtemp(prefix="sm_pstudio_")
library.LIBRARY_DIR = lib
assert bpy.ops.stop_motion.save_puppet(puppet="Biscuit", name="Biscuit") == {'FINISHED'}
assert os.path.exists(os.path.join(lib, "Biscuit.blend")) and os.path.exists(os.path.join(lib, "Biscuit.png"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
library.LIBRARY_DIR = lib
assert bpy.ops.stop_motion.bring_in(path="Biscuit.blend", kind='PUPPET') == {'FINISHED'}
dog2 = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][0]
pp = dog2.stop_motion_puppet
assert pp.enabled and len(pp.rings) == 8 and {s.name for s in pp.swap_sets} == {"Mouth", "Eyes"}
assert all(r.pin.name in bpy.context.scene.objects for r in pp.rings if r.pin)
print("PUPPET STUDIO TESTS PASSED")
sms.unregister()
