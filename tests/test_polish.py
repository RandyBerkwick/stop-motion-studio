"""Torch sweep, painting copies, the shot strip in normal Blender, saving on quit, the Dock icon helper."""
import math, os, sys, tempfile
from types import SimpleNamespace
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy
from mathutils import Vector
import stop_motion_studio as sms
sms.register()
from stop_motion_studio import arrange, core, lighting, macos, strip, studio

scene = bpy.context.scene
scene.frame_start = 1
sm = scene.stop_motion
sm.default_hold = '2'
cube = bpy.data.objects["Cube"]
for i in range(8):
    cube.location.x = i * 0.1
    bpy.ops.stop_motion.shoot()

# --- torch sweep over shots 3-6: on and turning during the run, off before and after
scene.frame_set(core.shot_start(scene, 2))
assert bpy.ops.stop_motion.light_effect(effect='TORCH', count=4) == {'FINISHED'}
torch = scene.objects[lighting.TORCH_NAME]
yaws, energies = [], []
for i in range(8):
    scene.frame_set(core.shot_start(scene, i))
    energies.append(round(torch.data.energy, 1))
    fwd = torch.matrix_world.to_3x3() @ Vector((0, 0, -1))
    yaws.append(round(math.degrees(math.atan2(fwd.x, fwd.y)), 1))
print("torch energy per shot", energies)
print("torch heading per shot", yaws)
assert energies[0] == energies[1] == 0 and energies[6] == energies[7] == 0
assert all(e > 0 for e in energies[2:6])
run = yaws[2:6]
assert all(b > a for a, b in zip(run, run[1:])) and run[-1] - run[0] > 50, "sweeps across, one way"

# --- painting copies: one every `spacing` along the stroke
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
ground = bpy.context.object
bpy.ops.mesh.primitive_cone_add(radius1=0.1, depth=0.3, location=(5, 5, 0.15))
flower = bpy.context.object
bpy.context.view_layer.update()
sm.stamp_spacing = 2.0
spacing = arrange.stamp_spacing(bpy.context, flower)
assert abs(spacing - 0.4) < 0.02, spacing          # 0.2 wide x 2
hits = iter([(Vector((x / 20.0, 0, 0)), Vector((0, 0, 1)), ground) for x in range(0, 41)])   # a 2 m stroke
fake = SimpleNamespace(paint={"src": flower, "exclude": {flower}, "last": None, "n": 0, "tree": None,
                              "spacing": spacing},
                       _hit=lambda c, m, ex: next(hits), _say=lambda c, t: None)
arrange.ARR["count"] = 0
for _ in range(41):
    arrange.SM_OT_arrange._paint_at(fake, bpy.context, (0, 0))
print("painted", fake.paint["n"], "copies along 2 m at", round(spacing, 2), "m apart")
assert fake.paint["n"] in (5, 6), fake.paint["n"]       # about one per 0.4 m

# --- the shot strip in normal Blender: cards sized by hold, clicks find the right card
region = SimpleNamespace(width=1200, height=700, as_pointer=lambda: 1)
ctx = SimpleNamespace(scene=scene)
items = strip.layout(ctx, region)
cards = [(r, i) for r, k, i in items if k == 'CARD']
assert len(cards) == 8 and [k for _r, k, _i in items][-1] == 'LIVE'
sm.shots[3].hold = 5
items = strip.layout(ctx, region)
w = {i: r.w for r, k, i in items if k == 'CARD'}
assert w[3] > w[2] * 2, "a longer hold is a wider card"
strip.HITS[1] = items
r3 = next(r for r, k, i in items if k == 'CARD' and i == 3)
assert strip.hit(ctx, region, r3.cx, r3.cy) == ('CARD', 3)
assert strip.hit(ctx, region, r3.right - 2, r3.cy) == ('EDGE', 3), "the right edge is the hold handle"
assert strip.hit(ctx, region, 5, 600) is None, "clicks elsewhere go to Blender"

# --- quitting from the Studio saves the work, and Blender's own prompt setting comes back
projects = tempfile.mkdtemp(prefix="sm_projects_")
studio.PROJECTS_DIR = projects
prefs = bpy.context.preferences.view
prefs.use_save_prompt = True
studio.S.active = True
studio.S.saved_prompt = True
prefs.use_save_prompt = False            # what enter_studio does
cube.location.z += 0.5                   # a change, so there's something to save
studio._on_exit()
saved = os.listdir(projects)
print("saved on quit:", saved)
assert [f for f in saved if f.endswith(".blend")] == ["Scene 01.blend"], saved
assert prefs.use_save_prompt is True and studio.S.saved_prompt is None
studio.S.active = False

# --- the Dock icon only does anything on a Mac
assert os.path.exists(macos.ICON)
assert macos.set_dock_icon() is (sys.platform == "darwin") or sys.platform == "darwin"
print("POLISH TESTS PASSED")
sms.unregister()
