# SPDX-License-Identifier: GPL-3.0-or-later
"""Sculpt one shot, here in Blender or in Nomad Sculpt.

A shot's sculpt is a shape key on the mesh ("SM Sculpt <shot id>"), keyed
on for that shot and off for the others, always constant. So it behaves
like swapping in a one-off clay head for one shot. Choices:
  - One-off: only this shot.
  - Carry on: this shot and every later one.
  - Save as swap part: becomes a part in a swap set (e.g. Face › Surprised)
    you can swap in on any shot.
Posing over a sculpted shot keeps its sculpt.

Nomad bridge: a file round trip. "Send to Nomad" writes the mesh as an OBJ
into a folder you can see from the tablet (iCloud Drive by default on a
Mac). Sculpt it in Nomad and export OBJ back over the same file; Stop
Motion notices the new file and puts the sculpt on the shot. Vertices are
matched by order when Nomad keeps them, otherwise by nearest surface.
"""

import os
import time

import bpy
from bpy.app.handlers import persistent
from bpy.props import CollectionProperty, EnumProperty, StringProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import core, puppet

PREFIX = "SM Sculpt "


# ------------------------------------------------------------ shape keys

def sculpt_key_name(uid):
    return PREFIX + uid


def ensure_basis(ob):
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basis", from_mix=False)
    return ob.data.shape_keys


def sculpt_key(ob, uid, create=True):
    keys = ensure_basis(ob) if create else ob.data.shape_keys
    if keys is None:
        return None
    kb = keys.key_blocks.get(sculpt_key_name(uid))
    if kb is None and create:
        kb = ob.shape_key_add(name=sculpt_key_name(uid), from_mix=False)
        kb.value = 0.0
    return kb


def set_key_over_shots(scene, kb, on_frames):
    """Key the shape key at every shot start (and the live frame): 1 on
    `on_frames`, 0 elsewhere."""
    from . import lighting  # same helper writes constant keys
    starts = [start for _i, _s, start, _h in core.shot_spans(scene)]
    frames = starts + [core.live_frame(scene)]
    for f in frames:
        lighting.write_value(kb, "value", [f], 1.0 if f in on_frames else 0.0)


def apply_keep(scene, ob, uid, keep):
    """Decide which shots show this sculpt."""
    kb = sculpt_key(ob, uid)
    spans = core.shot_spans(scene)
    index = next((i for i, s, _st, _h in spans if s.uid == uid), -1)
    if index < 0:
        return None
    starts = [start for _i, _s, start, _h in spans]
    if keep == 'CARRY_ON':
        on = set(starts[index:]) | {core.live_frame(scene)}
    else:
        on = {starts[index]}
    set_key_over_shots(scene, kb, on)
    return kb


def swap_set_of(context, ob):
    """(puppet, set index) if `ob` is one piece of a swap set made of separate meshes (a hand shape)."""
    for arm in puppet.puppets(context.scene):
        for si, sset in enumerate(arm.stop_motion_puppet.swap_sets):
            if sset.kind == 'MESH' and any(it.obj == ob for it in sset.items):
                return arm, si
    return None, -1


def save_as_new_piece(context, ob, uid, part_name=""):
    """A shot's sculpt of one swap piece (a hand, a mouth) becomes a new piece in
    that set, and the shot uses it. Returns the new object or None."""
    arm, si = swap_set_of(context, ob)
    kb = sculpt_key(ob, uid, create=False)
    if arm is None or kb is None:
        return None
    sset = arm.stop_motion_puppet.swap_sets[si]
    prefix = ob.name.split("_", 1)[0]
    if not part_name:
        n = 1
        while bpy.data.objects.get("%s_Shape%d" % (prefix, n)):
            n += 1
        part_name = "Shape%d" % n
    clean = "".join(ch for ch in part_name.title() if ch.isalnum()) or "Shape"
    # the sculpted shape, baked into its own mesh (no shape keys)
    me = ob.data.copy()
    new = ob.copy()
    new.data = me
    shaped = [kb.data[i].co.copy() for i in range(len(me.vertices))]
    new.shape_key_clear()
    for v, co in zip(me.vertices, shaped):
        v.co = co
    new.name = "%s_%s" % (prefix, clean)
    new.data.name = new.name
    if new.animation_data is not None:
        new.animation_data_clear()
    for col in ob.users_collection:
        if new.name not in col.objects:
            col.objects.link(new)
    if ob.get("sm_face"):
        new["sm_face"] = new.name
        new["sm_order"] = max((o.get("sm_order", 0) for o in arm.children if o.get("sm_face", "").startswith(prefix + "_")), default=0) + 1
    # the shot that was sculpted now shows the new piece instead of the sculpt
    scene = context.scene
    shots = {sh.uid: i for i, sh in enumerate(scene.stop_motion.shots)}
    remove_sculpt(ob, uid)
    puppet.rescan_swaps(context, arm)
    si2 = next((i for i, st in enumerate(arm.stop_motion_puppet.swap_sets) if any(it.obj == new for it in st.items)), -1)
    # it's new: on every other shot (and live) it stays hidden
    others = [core.shot_start(scene, i) for u, i in shots.items() if u != uid] + [core.live_frame(scene)]
    new.hide_viewport = new.hide_render = True
    for f in others:
        for path in ("hide_viewport", "hide_render"):
            new.keyframe_insert(path, frame=f)
    if uid in shots and si2 >= 0:
        sset = arm.stop_motion_puppet.swap_sets[si2]
        start = core.shot_start(scene, shots[uid])
        keep = scene.frame_current
        scene.frame_set(start)
        item = next(i for i, it in enumerate(sset.items) if it.obj == new)
        puppet.apply_swap(sset, item)
        for it in sset.items:
            for path in ("hide_viewport", "hide_render"):
                it.obj.keyframe_insert(path, frame=start)
            for fc in core.fcurves_of(it.obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
        scene.frame_set(keep)
    return new


def save_as_swap(context, ob, uid, set_name, part_name):
    """Turn a shot's sculpt into a swap part 'Set_Part' and refresh swap sets."""
    kb = sculpt_key(ob, uid, create=False)
    if kb is None:
        return None
    if swap_set_of(context, ob)[0] is not None:          # a hand or mouth piece: a new piece in its set
        return save_as_new_piece(context, ob, uid, part_name)
    clean = lambda s: "_".join(s.strip().split()) or "Part"
    kb.name = "%s_%s" % (clean(set_name), clean(part_name))
    arm = next((a for a in puppet.puppets(context.scene) if ob in puppet.puppet_meshes(a, context.scene)), None)
    if arm is not None:
        puppet.rescan_swaps(context, arm)
    return kb


def remove_sculpt(ob, uid):
    kb = sculpt_key(ob, uid, create=False)
    if kb is not None:
        ob.shape_key_remove(kb)


def shots_with_sculpt(scene, ob):
    keys = ob.data.shape_keys if ob.type == 'MESH' else None
    if keys is None:
        return set()
    return {kb.name[len(PREFIX):] for kb in keys.key_blocks if kb.name.startswith(PREFIX)}


# ------------------------------------------------------------- OBJ round trip

def basis_positions(ob):
    """Object-space positions without the rig: basis plus the current shape mix."""
    keys = ob.data.shape_keys
    if keys is None:
        return [v.co.copy() for v in ob.data.vertices]
    basis = keys.reference_key
    out = [d.co.copy() for d in basis.data]
    for kb in keys.key_blocks:
        if kb == basis or kb.value == 0.0 or kb.mute:
            continue
        rel = kb.relative_key
        for i, (a, b) in enumerate(zip(kb.data, rel.data)):
            out[i] += (a.co - b.co) * kb.value
    return out


def write_obj(path, positions, polygons, name):
    # Blender is Z-up, OBJ (and Nomad) are Y-up: write (x, z, -y).
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Stop Motion Studio sculpt send\no %s\n" % name)
        for p in positions:
            fh.write("v %.6f %.6f %.6f\n" % (p.x, p.z, -p.y))
        for poly in polygons:
            fh.write("f %s\n" % " ".join(str(i + 1) for i in poly))


def read_obj(path):
    verts, faces = [], []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                x, y, z = (float(t) for t in line.split()[1:4])
                verts.append(Vector((x, -z, y)))
            elif line.startswith("f "):
                idx = []
                for tok in line.split()[1:]:
                    i = int(tok.split("/")[0])
                    idx.append(i - 1 if i > 0 else len(verts) + i)
                faces.append(idx)
    return verts, faces


def match_positions(original, new_verts, new_faces):
    """Map the sculpted file back onto our vertices.

    Same count and close on average → Nomad kept the order: use it directly.
    Otherwise each of our vertices goes to the nearest point on the new surface."""
    if len(new_verts) == len(original):
        avg = sum((a - b).length for a, b in zip(original, new_verts)) / max(1, len(original))
        size = max((v.length for v in original), default=1.0) or 1.0
        if avg < 0.25 * size:
            return [v.copy() for v in new_verts], "order"
    tris = []
    for f in new_faces:
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
    if not tris:
        return None, "empty"
    tree = BVHTree.FromPolygons(new_verts, tris)
    out = []
    for p in original:
        hit = tree.find_nearest(p)
        out.append(hit[0].copy() if hit and hit[0] is not None else p.copy())
    return out, "nearest"


def put_positions(ob, kb, positions):
    """Set a shape key so the mesh (at value 1) has `positions`."""
    keys = ob.data.shape_keys
    basis = keys.reference_key
    current = basis_positions(ob)
    # Shape keys are offsets: keep everything else, add the difference.
    for i, d in enumerate(kb.data):
        d.co = basis.data[i].co + (positions[i] - current[i]) + (d.co - basis.data[i].co) * kb.value


# --------------------------------------------------------------- bridge

# ------------------------------------------------------------ clay brushes

BRUSH_FILE = "brushes/essentials_brushes-mesh_sculpt.blend"
CLAY_BRUSHES = (            # (what the animator sees, Blender's brush)
    ("Build up", "Clay Strips"),
    ("Clay", "Clay"),
    ("Thumb", "Clay Thumb"),
    ("Smooth", "Smooth"),
    ("Push & pull", "Grab"),
    ("Puff", "Inflate/Deflate"),
    ("Crease", "Crease Sharp"),
    ("Flatten", "Flatten/Contrast"),
)


def current_brush(context):
    try:
        b = context.tool_settings.sculpt.brush
        return b.name if b else ""
    except AttributeError:
        return ""


def set_brush(context, brush_name):
    """Switch the sculpt brush to one of Blender's own (brush assets in 4.3+)."""
    try:
        bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS', asset_library_identifier="",
                                     relative_asset_identifier="%s/Brush/%s" % (BRUSH_FILE, brush_name))
        return True
    except (RuntimeError, TypeError, AttributeError):
        pass
    b = bpy.data.brushes.get(brush_name)          # older Blender: brushes are plain data
    if b is not None:
        try:
            context.tool_settings.sculpt.brush = b
            return True
        except (AttributeError, TypeError):
            pass
    return False


def _ups(context):
    ts = context.tool_settings
    ups = getattr(ts.sculpt, "unified_paint_settings", None)      # 5.x
    return ups if ups is not None else getattr(ts, "unified_paint_settings", None)


def brush_size(context):
    ups = _ups(context)
    if ups.use_unified_size:
        return ups.size
    b = context.tool_settings.sculpt.brush
    return b.size if b else ups.size


def set_brush_size(context, px):
    ts = context.tool_settings
    _ups(context).size = int(px)
    b = ts.sculpt.brush
    if b is not None:
        try:
            b.size = int(px)
        except AttributeError:
            pass


def brush_strength(context):
    ups = _ups(context)
    if ups.use_unified_strength:
        return ups.strength
    b = context.tool_settings.sculpt.brush
    return b.strength if b else ups.strength


def set_brush_strength(context, v):
    ts = context.tool_settings
    _ups(context).strength = v
    b = ts.sculpt.brush
    if b is not None:
        try:
            b.strength = v
        except AttributeError:
            pass


class SM_OT_clay_brush(bpy.types.Operator):
    """Pick a clay tool for sculpting this shot"""
    bl_idname = "stop_motion.clay_brush"
    bl_label = "Clay Tool"

    brush: StringProperty()

    def execute(self, context):
        if not set_brush(context, self.brush):
            self.report({'WARNING'}, "Couldn't find the %s brush" % self.brush)
            return {'CANCELLED'}
        return {'FINISHED'}


class SM_NomadSend(bpy.types.PropertyGroup):
    obj: StringProperty()
    uid: StringProperty()
    path: StringProperty()
    sent: StringProperty(default="0")  # file time; a FloatProperty is too coarse for timestamps
    keep: StringProperty(default='ONE_OFF')
    status: StringProperty(default="Waiting for Nomad")


def default_bridge_dir():
    icloud = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")
    if os.path.isdir(icloud):
        return os.path.join(icloud, "Stop Motion Nomad")
    return os.path.join(os.path.expanduser("~"), "Stop Motion Nomad")


def bridge_dir(scene):
    d = bpy.path.abspath(scene.stop_motion_nomad_dir) if scene.stop_motion_nomad_dir else default_bridge_dir()
    os.makedirs(d, exist_ok=True)
    return d


def send_to_nomad(scene, ob, uid, keep='ONE_OFF'):
    name = "%s__shot_%s" % (bpy.path.clean_name(ob.name), uid)
    path = os.path.join(bridge_dir(scene), name + ".obj")
    write_obj(path, basis_positions(ob), [list(p.vertices) for p in ob.data.polygons], name)
    for s in scene.stop_motion_nomad:
        if s.path == path:
            item = s
            break
    else:
        item = scene.stop_motion_nomad.add()
    item.obj, item.uid, item.path, item.keep = ob.name, uid, path, keep
    item.sent = repr(os.path.getmtime(path))
    item.status = "Waiting for Nomad"
    return item


def bring_back(context, item, force=False):
    """Returns True when the sculpt was brought back."""
    scene = context.scene
    ob = bpy.data.objects.get(item.obj)
    if ob is None or not os.path.exists(item.path):
        item.status = "File or object missing"
        return False
    mtime = os.path.getmtime(item.path)
    if not force and mtime <= float(item.sent or 0) + 0.5:
        return False
    verts, faces = read_obj(item.path)
    original = basis_positions(ob)
    positions, how = match_positions(original, verts, faces)
    if positions is None:
        item.status = "Couldn't read the file"
        return False
    kb = sculpt_key(ob, item.uid)
    put_positions(ob, kb, positions)
    apply_keep(scene, ob, item.uid, item.keep)
    item.sent = repr(mtime)
    item.status = "Back from Nomad (%s)" % ("same points" if how == "order" else "fitted to surface")
    return True


def _poll_bridge():
    ctx = bpy.context
    for scene in bpy.data.scenes:
        for item in getattr(scene, "stop_motion_nomad", []):
            if item.status.startswith("Waiting"):
                try:
                    with ctx.temp_override(scene=scene):
                        bring_back(ctx, item)
                except Exception as exc:  # never break the timer
                    print("Stop Motion: Nomad bring-back failed:", exc)
    return 2.0


@persistent
def _on_load(_dummy=None):
    if not bpy.app.timers.is_registered(_poll_bridge):
        bpy.app.timers.register(_poll_bridge, first_interval=2.0, persistent=True)


# ------------------------------------------------------------- operators

KEEP_ITEMS = [('ONE_OFF', "One-off for this shot", "Only this shot shows the sculpt"),
              ('CARRY_ON', "Carry on", "This shot and every later one")]


def _target_mesh(context):
    ob = context.active_object
    if ob is not None and ob.type == 'MESH':
        return ob
    arm = puppet.puppet_for(context)
    if arm is not None:
        meshes = [m for m in puppet.puppet_meshes(arm, context.scene)
                  if any(md.type == 'ARMATURE' for md in m.modifiers)]
        if meshes:
            return max(meshes, key=lambda m: len(m.data.vertices))
    return None


class SM_OT_sculpt_shot(bpy.types.Operator):
    """Sculpt the puppet for this shot only, with Blender's sculpt tools"""
    bl_idname = "stop_motion.sculpt_shot"
    bl_label = "Sculpt This Shot"
    bl_options = {'REGISTER', 'UNDO'}

    keep: EnumProperty(items=KEEP_ITEMS, default='ONE_OFF')

    def execute(self, context):
        scene = context.scene
        idx = core.shot_index_at(scene, scene.frame_current)
        if idx < 0:
            self.report({'WARNING'}, "Step onto a shot first (shoot it, then sculpt it)")
            return {'CANCELLED'}
        ob = _target_mesh(context)
        if ob is None:
            self.report({'WARNING'}, "Select the mesh to sculpt")
            return {'CANCELLED'}
        uid = scene.stop_motion.shots[idx].uid
        kb = apply_keep(scene, ob, uid, self.keep)
        kb.value = 1.0
        ob.active_shape_key_index = list(ob.data.shape_keys.key_blocks).index(kb)
        ob.use_shape_key_edit_mode = True
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='SCULPT')
        if current_brush(context) not in {b for _l, b in CLAY_BRUSHES}:
            set_brush(context, "Clay Strips")   # start with a clay tool
        scene.stop_motion_sculpting = "%s|%s" % (ob.name, uid)
        self.report({'INFO'}, "Sculpting shot %d: only this shot changes" % (idx + 1))
        return {'FINISHED'}


class SM_OT_done_sculpting(bpy.types.Operator):
    """Finish sculpting and go back to animating"""
    bl_idname = "stop_motion.done_sculpting"
    bl_label = "Done Sculpting"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        context.scene.stop_motion_sculpting = ""
        core.update_ghost(context.scene)
        return {'FINISHED'}


class SM_OT_sculpt_keep(bpy.types.Operator):
    """Choose which shots show this sculpt"""
    bl_idname = "stop_motion.sculpt_keep"
    bl_label = "Show Sculpt In"
    bl_options = {'REGISTER', 'UNDO'}

    obj: StringProperty()
    uid: StringProperty()
    keep: EnumProperty(items=KEEP_ITEMS)

    def execute(self, context):
        ob = bpy.data.objects.get(self.obj)
        if ob is None or apply_keep(context.scene, ob, self.uid, self.keep) is None:
            return {'CANCELLED'}
        return {'FINISHED'}


class SM_OT_sculpt_to_swap(bpy.types.Operator):
    """Keep this sculpt as a swap part you can use on any shot"""
    bl_idname = "stop_motion.sculpt_to_swap"
    bl_label = "Save as Swap Part"
    bl_options = {'REGISTER', 'UNDO'}

    obj: StringProperty()
    uid: StringProperty()
    set_name: StringProperty(name="Swap set", default="Face")
    part_name: StringProperty(name="Part", default="Surprised")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ob = bpy.data.objects.get(self.obj)
        if ob is None or save_as_swap(context, ob, self.uid, self.set_name, self.part_name) is None:
            return {'CANCELLED'}
        self.report({'INFO'}, "Saved as %s › %s" % (self.set_name, self.part_name))
        return {'FINISHED'}


class SM_OT_remove_sculpt(bpy.types.Operator):
    """Throw this shot's sculpt away"""
    bl_idname = "stop_motion.remove_sculpt"
    bl_label = "Remove Sculpt"
    bl_options = {'REGISTER', 'UNDO'}

    obj: StringProperty()
    uid: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.obj)
        if ob is None:
            return {'CANCELLED'}
        if context.mode == 'SCULPT':
            bpy.ops.object.mode_set(mode='OBJECT')
        remove_sculpt(ob, self.uid)
        return {'FINISHED'}


class SM_OT_send_nomad(bpy.types.Operator):
    """Send the mesh to Nomad Sculpt for this shot. In Nomad: sculpt, then export OBJ over the same file"""
    bl_idname = "stop_motion.send_nomad"
    bl_label = "Send to Nomad"

    keep: EnumProperty(items=KEEP_ITEMS, default='ONE_OFF')

    def execute(self, context):
        scene = context.scene
        idx = core.shot_index_at(scene, scene.frame_current)
        if idx < 0:
            self.report({'WARNING'}, "Step onto a shot first")
            return {'CANCELLED'}
        ob = _target_mesh(context)
        if ob is None:
            self.report({'WARNING'}, "Select the mesh to sculpt")
            return {'CANCELLED'}
        item = send_to_nomad(scene, ob, scene.stop_motion.shots[idx].uid, self.keep)
        _on_load()
        self.report({'INFO'}, "Sent %s. In Nomad: open it, sculpt, export OBJ over the same file"
                    % os.path.basename(item.path))
        return {'FINISHED'}


class SM_OT_nomad_back(bpy.types.Operator):
    """Bring the sculpt back from Nomad now"""
    bl_idname = "stop_motion.nomad_back"
    bl_label = "Bring Back Now"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        sends = context.scene.stop_motion_nomad
        if not (0 <= self.index < len(sends)):
            return {'CANCELLED'}
        ok = bring_back(context, sends[self.index], force=True)
        self.report({'INFO'} if ok else {'WARNING'}, sends[self.index].status)
        return {'FINISHED'}


class SM_OT_nomad_forget(bpy.types.Operator):
    """Stop waiting for this Nomad file"""
    bl_idname = "stop_motion.nomad_forget"
    bl_label = "Forget"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        sends = context.scene.stop_motion_nomad
        if 0 <= self.index < len(sends):
            sends.remove(self.index)
        return {'FINISHED'}


class SM_OT_open_bridge(bpy.types.Operator):
    """Show the Nomad folder in Finder"""
    bl_idname = "stop_motion.open_bridge"
    bl_label = "Show Nomad Folder"

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=bridge_dir(context.scene))
        return {'FINISHED'}


classes = (SM_NomadSend, SM_OT_clay_brush, SM_OT_sculpt_shot, SM_OT_done_sculpting, SM_OT_sculpt_keep,
           SM_OT_sculpt_to_swap, SM_OT_remove_sculpt, SM_OT_send_nomad, SM_OT_nomad_back,
           SM_OT_nomad_forget, SM_OT_open_bridge)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.stop_motion_nomad = CollectionProperty(type=SM_NomadSend)
    bpy.types.Scene.stop_motion_nomad_dir = StringProperty(
        name="Nomad folder", subtype='DIR_PATH', default="",
        description="Folder shared with your tablet (empty: iCloud Drive › Stop Motion Nomad)")
    bpy.types.Scene.stop_motion_sculpting = StringProperty(default="")
    bpy.app.handlers.load_post.append(_on_load)
    _on_load()


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if bpy.app.timers.is_registered(_poll_bridge):
        bpy.app.timers.unregister(_poll_bridge)
    del bpy.types.Scene.stop_motion_sculpting
    del bpy.types.Scene.stop_motion_nomad_dir
    del bpy.types.Scene.stop_motion_nomad
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
