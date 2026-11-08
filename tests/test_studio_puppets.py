"""The Studio's Puppets mode: steps, building from the kit, sliders, faces, trying out, saving, sculpt joints."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy, bmesh
import stop_motion_studio as sms
sms.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
sms.unregister(); sms.register()
from stop_motion_studio import assembly, library, rigsculpt, trial, studio_puppets as sp

ctx = bpy.context
assert sp.steps_for('PARTS') == ['BUILD', 'FACE', 'TRY', 'SAVE'] and sp.steps_for('SCULPT')[0] == 'JOINTS'
sp.set_start('SCULPT'); assert sp.P.step == 'JOINTS'
sp.set_start('PARTS'); assert sp.P.step == 'BUILD'
sp.set_step('JOINTS'); assert sp.P.step == 'BUILD', "a kit puppet has no joints step"

sp.new_build('PERSON')
arm = sp.current_build(ctx)
assert arm is not None and arm.name == "Pip"
sp.use_part("head", "wide")
assert any(json.loads(o["sm_part"])["variant"] == "wide" for o in assembly.kit_parts(arm))
sp.colour_part("legs", "green")
assert all(o.data.materials[0].name == "SM Clay green" for o in assembly.kit_parts(arm) if json.loads(o["sm_part"])["kind"] == "legs")
# sliders: values wait, then are applied together
sp.set_prop(arm, "head", 1.3); sp.set_prop(arm, "legs", 1.2)
assert assembly.build_info(arm)["props"]["head"] == 1.0
sp._apply_props()
props = assembly.build_info(arm)["props"]
assert abs(props["head"] - 1.3) < 1e-6 and abs(props["legs"] - 1.2) < 1e-6 and not sp.P.pending

sp.set_step('FACE')
sp.make_faces(arm)
assert arm.stop_motion_puppet.enabled and len(arm.stop_motion_puppet.swap_sets) == 5
sp.set_step('TRY')                       # going to Try it tries it out
res = trial.last_results(arm)
assert [r["name"] for r in res] == ["Wave", "Sit", "Crouch", "Walk"]
lib = tempfile.mkdtemp(prefix="sm_sp_")
library.LIBRARY_DIR = lib
sp.save(arm)
assert os.path.exists(os.path.join(lib, "Pip.blend")) and os.path.exists(os.path.join(lib, "Pip.png"))
print("building in the Studio ok")

# a sculpt: choose it, guess joints, make the rig
ref = assembly.new_build(ctx, "Ref", 'PERSON', location=(3, 0, 0)); assembly.starter(ctx, ref)
dg = ctx.evaluated_depsgraph_get(); bm = bmesh.new()
for o in assembly.kit_parts(ref):
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world); bm.from_mesh(me)
me = bpy.data.meshes.new("Wren"); bm.to_mesh(me); bm.free()
wren = bpy.data.objects.new("Wren", me); ctx.scene.collection.objects.link(wren)
for o in list(ref.children_recursive) + [ref]: bpy.data.objects.remove(o)
for o in ctx.selected_objects: o.select_set(False)
ctx.view_layer.objects.active = wren
sp.set_start('SCULPT')
assert sp.current_sculpt(ctx) == wren
sp.guess_joints(wren)
assert len(rigsculpt.get_joints(wren)) >= 20
sp.make_rig(wren)
rig = sp.current_build(ctx)
assert rig is not None and assembly.build_info(rig).get("sculpt") == "Wren" and sp.P.step == 'FACE'
assert len(rig.stop_motion_puppet.rings) == 7
print("STUDIO PUPPETS TESTS PASSED")
sms.unregister()
