# SPDX-License-Identifier: GPL-3.0-or-later
"""Lighting: studio presets, HDRI presets, light per shot and light effects.

Lights are part of each shot, like the puppet's pose: Shoot keys every
light's brightness and colour plus the world (sky) strength and colour,
always constant. So a light change holds until you change it again.
"Apply light change" writes the current lights into this shot, this shot
and every later one, or every shot. Effects (flicker, flash, fade to
night, lights out) write a pattern across a run of shots.

Preset lights live in a "Stop Motion Lights" collection and are replaced
when you pick another preset. Your own lights are switched off (not
deleted) while a preset is on, and come back with "Use my own lights".
"""

import math
import os

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy_extras import anim_utils
from mathutils import Vector

from . import core, puppet

COLLECTION = "Stop Motion Lights"
WORLD = "Stop Motion World"
BG, ENV, MAP = "SM Background", "SM Environment", "SM Mapping"

# name: (label, [lights], world rgb, world strength)
# light: (name, type, energy at radius 1, rgb, offset (right, toward camera, up) in radii, size)
STUDIO = {
    'WARM_LAMP': ("Warm lamp", [
        ("Lamp", 'POINT', 250, (1.0, 0.72, 0.42), (-0.9, 0.9, 0.8), 0.15),
        ("Bounce", 'AREA', 50, (0.95, 0.82, 0.70), (1.6, 0.6, 1.0), 2.0)],
        (0.05, 0.035, 0.02), 1.0),
    'DAYLIGHT': ("Daylight window", [
        ("Window sun", 'SUN', 3.0, (1.0, 0.97, 0.90), (-1.0, 0.6, 1.4), 0.0),
        ("Sky fill", 'AREA', 90, (0.80, 0.88, 1.0), (1.5, 0.6, 1.0), 2.5)],
        (0.55, 0.65, 0.80), 0.5),
    'THREE_POINT': ("Three-point", [
        ("Key", 'AREA', 450, (1.0, 0.95, 0.88), (-1.2, 1.0, 1.2), 1.5),
        ("Fill", 'AREA', 130, (0.90, 0.95, 1.0), (1.4, 0.4, 1.0), 2.5),
        ("Rim", 'SPOT', 400, (1.0, 1.0, 1.0), (0.6, -1.4, 1.2), 0.2)],
        (0.02, 0.02, 0.02), 1.0),
    'MOONLIGHT': ("Moonlight", [
        ("Moon", 'AREA', 220, (0.55, 0.70, 1.0), (-1.6, -0.2, 1.6), 1.0),
        ("Night bounce", 'AREA', 18, (0.30, 0.40, 0.70), (1.5, 0.5, 0.8), 3.0)],
        (0.015, 0.02, 0.05), 1.0),
    'SPOOKY': ("Spooky under-light", [
        ("Under", 'SPOT', 600, (0.55, 1.0, 0.40), (0.1, 1.1, -0.6), 0.3),
        ("Back glow", 'AREA', 80, (0.60, 0.30, 1.0), (0.0, -1.5, 0.6), 2.0)],
        (0.0, 0.0, 0.0), 1.0),
    'FLAT': ("Flat, for checking", [
        ("Flat sun", 'SUN', 2.0, (1.0, 1.0, 1.0), (0.0, 1.0, 1.0), 0.0)],
        (0.8, 0.8, 0.8), 1.0),
}

HDRI = {
    'FOREST': ("Overcast garden", "forest.exr", 1.0),
    'COURTYARD': ("Courtyard", "courtyard.exr", 1.0),
    'SUNSET': ("Golden hour", "sunset.exr", 1.0),
    'SUNRISE': ("Sunrise", "sunrise.exr", 1.0),
    'INTERIOR': ("Cosy room", "interior.exr", 1.0),
    'STUDIO': ("Softbox studio", "studio.exr", 1.0),
    'CITY': ("City", "city.exr", 1.0),
    'NIGHT': ("Night", "night.exr", 0.7),
}


def hdri_dir():
    return bpy.utils.system_resource('DATAFILES', path="studiolights/world")


# ---------------------------------------------------------------- the stage

def stage(scene):
    """(centre, radius) of what's being filmed: the puppets, else the meshes."""
    obs = []
    for arm in puppet.puppets(scene):
        obs.extend(puppet.puppet_meshes(arm, scene))
    if not obs:
        obs = [o for o in scene.objects if o.type == 'MESH' and o.visible_get()]
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    if not pts:
        return Vector((0, 0, 1)), 1.0
    lo = Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    # ignore floors and walls: don't let one huge mesh decide
    if puppet.puppets(scene):
        return (lo + hi) / 2, max(0.5, (hi - lo).length / 2)
    return (lo + hi) / 2, max(0.5, min((hi - lo).length / 2, 3.0))


def camera_axes(scene, centre):
    cam = scene.camera
    if cam is None:
        toward = Vector((0, -1, 0))
    else:
        toward = cam.matrix_world.translation - centre
        toward.z = 0
        if toward.length < 1e-6:
            toward = Vector((0, -1, 0))
        toward.normalize()
    up = Vector((0, 0, 1))
    right = toward.cross(up).normalized() * -1
    return right, toward, up


def managed_collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def clear_managed(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        return
    for ob in list(col.objects):
        data = ob.data
        bpy.data.objects.remove(ob)
        if data is not None and data.users == 0:
            bpy.data.lights.remove(data)


def own_lights(scene):
    col = bpy.data.collections.get(COLLECTION)
    managed = set(col.objects) if col else set()
    return [o for o in scene.objects if o.type == 'LIGHT' and o not in managed]


def set_own_lights(scene, on):
    for ob in own_lights(scene):
        ob.hide_viewport = not on
        ob.hide_render = not on


# ------------------------------------------------------------------- world

def ensure_world(scene):
    world = scene.world
    if world is None or world.name != WORLD:
        world = bpy.data.worlds.get(WORLD) or bpy.data.worlds.new(WORLD)
        scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nodes = nt.nodes
    out = next((n for n in nodes if n.type == 'OUTPUT_WORLD'), None) or nodes.new("ShaderNodeOutputWorld")
    bg = nodes.get(BG)
    if bg is None:
        for n in list(nodes):
            if n.type == 'BACKGROUND':
                nodes.remove(n)
        bg = nodes.new("ShaderNodeBackground")
        bg.name = BG
        bg.location = (out.location.x - 250, out.location.y)
        nt.links.new(bg.outputs[0], out.inputs["Surface"])
    return world, bg


def set_world_colour(scene, rgb, strength):
    world, bg = ensure_world(scene)
    nt = world.node_tree
    for link in list(bg.inputs["Color"].links):
        nt.links.remove(link)
    bg.inputs["Color"].default_value = (*rgb, 1.0)
    bg.inputs["Strength"].default_value = strength
    world.color = rgb


def set_world_hdri(scene, path, strength):
    world, bg = ensure_world(scene)
    nt = world.node_tree
    nodes = nt.nodes
    env = nodes.get(ENV)
    if env is None:
        env = nodes.new("ShaderNodeTexEnvironment")
        env.name = ENV
        env.location = (bg.location.x - 320, bg.location.y)
    mp = nodes.get(MAP)
    if mp is None:
        tc = nodes.new("ShaderNodeTexCoord")
        tc.location = (env.location.x - 400, env.location.y)
        mp = nodes.new("ShaderNodeMapping")
        mp.name = MAP
        mp.location = (env.location.x - 200, env.location.y)
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    img = bpy.data.images.load(path, check_existing=True)
    if not img.packed_file and img.filepath.startswith(("/", "\\")) and "datafiles" in img.filepath.replace("\\", "/"):
        img.pack()  # Blender's own HDRIs: keep the file portable
    env.image = img
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength


def hdri_turn_socket(scene):
    world = scene.world
    if world is None or not world.use_nodes:
        return None
    mp = world.node_tree.nodes.get(MAP)
    return mp.inputs["Rotation"] if mp else None


def world_background(scene):
    world = scene.world
    if world is None or not world.use_nodes:
        return None
    return world.node_tree.nodes.get(BG)


# ----------------------------------------------------------------- presets

def apply_studio(scene, key):
    label, lights, wrgb, wstr = STUDIO[key]
    clear_managed(scene)
    col = managed_collection(scene)
    centre, radius = stage(scene)
    right, toward, up = camera_axes(scene, centre)
    for name, ltype, energy, rgb, (a, b, c), size in lights:
        data = bpy.data.lights.new(name, ltype)
        data.color = rgb
        data.energy = energy if ltype == 'SUN' else energy * radius * radius
        if ltype == 'AREA':
            data.size = size * radius
        elif ltype in ('POINT', 'SPOT'):
            data.shadow_soft_size = max(0.05, size * radius)
        if ltype == 'SPOT':
            data.spot_size = math.radians(55)
            data.spot_blend = 0.4
        ob = bpy.data.objects.new(name, data)
        col.objects.link(ob)
        ob.location = centre + (right * a + toward * b + up * c) * radius * 2.0
        ob.rotation_euler = (centre - ob.location).to_track_quat('-Z', 'Y').to_euler()
    set_world_colour(scene, wrgb, wstr)
    set_own_lights(scene, False)
    return label


def apply_hdri(scene, path, strength=1.0):
    clear_managed(scene)
    set_world_hdri(scene, path, strength)
    set_own_lights(scene, False)


# ------------------------------------------------------- lights in each shot

def light_targets(scene):
    """[(struct, prop)] that make up 'the lighting' of a shot."""
    out = []
    for ob in scene.objects:
        if ob.type == 'LIGHT':
            out.append((ob.data, "energy"))
            out.append((ob.data, "color"))
    bg = world_background(scene)
    if bg is not None:
        out.append((bg.inputs["Strength"], "default_value"))
        if not bg.inputs["Color"].is_linked:
            out.append((bg.inputs["Color"], "default_value"))
    return out


def key_lights(scene, frame):
    """Called by Shoot. Returns the IDs it keyed (for the constant pass)."""
    ids = set()
    for struct, prop in light_targets(scene):
        try:
            struct.keyframe_insert(prop, frame=frame)
        except (TypeError, RuntimeError):
            continue
        ids.add(struct.id_data)
    return ids


def _fcurves_for(struct, prop):
    idb = struct.id_data
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return []
    cb = anim_utils.animdata_get_channelbag_for_assigned_slot(ad)
    if cb is None:
        return []
    path = struct.path_from_id(prop)
    return [fc for fc in cb.fcurves if fc.data_path == path]


def write_value(struct, prop, frames, value):
    """Make the key at each frame hold `value` (scalar or tuple)."""
    if not frames:
        return
    fcs = _fcurves_for(struct, prop)
    if not fcs:
        struct.keyframe_insert(prop, frame=frames[0])
        fcs = _fcurves_for(struct, prop)
    vals = tuple(value) if hasattr(value, "__len__") else (value,)
    for fc in fcs:
        v = vals[fc.array_index] if fc.array_index < len(vals) else vals[-1]
        for f in frames:
            kp = fc.keyframe_points.insert(f, v, options={'REPLACE', 'FAST'})
            kp.interpolation = 'CONSTANT'
        fc.update()


def current_value(struct, prop):
    v = getattr(struct, prop)
    return tuple(v) if hasattr(v, "__len__") else v


def shot_frames(scene, scope, index):
    starts = [start for _i, _s, start, _h in core.shot_spans(scene)]
    if scope == 'THIS':
        return starts[index:index + 1]
    if scope == 'FROM_HERE':
        return starts[index:]
    return starts


def apply_light_change(scene, scope, index):
    values = [(s, p, current_value(s, p)) for s, p in light_targets(scene)]
    frames = shot_frames(scene, scope, index)
    for s, p, v in values:
        write_value(s, p, frames, v)
    return len(frames)


# ------------------------------------------------------------------ effects

EFFECTS = [
    ('FLICKER', "Flicker", "Lights waver over the next shots"),
    ('FLASH', "Lightning flash", "One bright white shot"),
    ('FADE_NIGHT', "Fade to night", "Dim and cool over the next shots, then stay night"),
    ('LIGHTS_OUT', "Lights out", "Lights off from this shot on"),
]
_FLICKER = (1.0, 0.55, 0.9, 0.4, 1.0, 0.7, 0.35, 0.95, 0.6, 1.0)


def _scale(v, k):
    return tuple(c * k for c in v) if isinstance(v, tuple) else v * k


def _mix(a, b, t):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    return a + (b - a) * t


def apply_effect(scene, effect, index, count):
    spans = core.shot_spans(scene)
    if not (0 <= index < len(spans)):
        return 0
    run = spans[index:index + max(1, count)] if effect in ('FLICKER', 'FADE_NIGHT') else spans[index:index + 1]
    if effect == 'LIGHTS_OUT':
        run = spans[index:]
    keep = scene.frame_current
    done = 0
    for n, (_i, _s, start, _h) in enumerate(run):
        scene.frame_set(start)
        t = n / max(1, len(run) - 1)
        for struct, prop in light_targets(scene):
            v = current_value(struct, prop)
            is_colour = isinstance(v, tuple)
            if effect == 'FLICKER':
                nv = v if is_colour else v * _FLICKER[n % len(_FLICKER)]
            elif effect == 'FLASH':
                nv = (1.0,) * len(v) if is_colour else v * 6.0
            elif effect == 'FADE_NIGHT':
                night = (0.55, 0.65, 1.0, 1.0)[:len(v)] if is_colour else v * 0.25
                nv = _mix(v, night, t) if is_colour else _mix(v, night, t)
            else:  # LIGHTS_OUT
                nv = v if is_colour else (v * 0.05 if prop == "default_value" else 0.0)
            write_value(struct, prop, [start], nv)
        done += 1
    if effect == 'FADE_NIGHT' and index + len(run) < len(spans):
        # stay at night after the fade
        last = run[-1][2]
        scene.frame_set(last)
        later = [start for _i, _s, start, _h in spans[index + len(run):]]
        for struct, prop in light_targets(scene):
            write_value(struct, prop, later, current_value(struct, prop))
    scene.frame_set(keep)
    return done


# ---------------------------------------------------------------- operators

def _shot_index(context):
    scene = context.scene
    i = core.shot_index_at(scene, scene.frame_current)
    return i


class SM_OT_light_preset(bpy.types.Operator):
    """Light the set with a ready-made studio setup"""
    bl_idname = "stop_motion.light_preset"
    bl_label = "Studio Light Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(items=[(k, v[0], "") for k, v in STUDIO.items()])

    def execute(self, context):
        label = apply_studio(context.scene, self.preset)
        self.report({'INFO'}, "Lighting: " + label + " (shoot or Apply to keep it in shots)")
        return {'FINISHED'}


class SM_OT_hdri_preset(bpy.types.Operator):
    """Light the set with a sky or room picture (HDRI)"""
    bl_idname = "stop_motion.hdri_preset"
    bl_label = "HDRI Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(items=[(k, v[0], "") for k, v in HDRI.items()])

    def execute(self, context):
        label, fname, strength = HDRI[self.preset]
        path = os.path.join(hdri_dir(), fname)
        if not os.path.exists(path):
            self.report({'ERROR'}, "Blender's %s isn't installed" % fname)
            return {'CANCELLED'}
        apply_hdri(context.scene, path, strength)
        self.report({'INFO'}, "Lighting: " + label)
        return {'FINISHED'}


class SM_OT_load_hdri(bpy.types.Operator):
    """Light the set with your own HDRI picture (.hdr or .exr)"""
    bl_idname = "stop_motion.load_hdri"
    bl_label = "Load Your Own HDRI"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.hdr;*.exr", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not os.path.exists(self.filepath):
            return {'CANCELLED'}
        apply_hdri(context.scene, self.filepath, 1.0)
        return {'FINISHED'}


class SM_OT_own_lights(bpy.types.Operator):
    """Remove the preset lights and switch your own lights back on"""
    bl_idname = "stop_motion.own_lights"
    bl_label = "Use My Own Lights"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        clear_managed(context.scene)
        set_own_lights(context.scene, True)
        return {'FINISHED'}


class SM_OT_apply_light(bpy.types.Operator):
    """Keep the lights as they are now in these shots"""
    bl_idname = "stop_motion.apply_light"
    bl_label = "Apply Light Change"
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(items=[('THIS', "This shot", ""), ('FROM_HERE', "From here on", ""),
                               ('EVERY', "Every shot", "")], default='FROM_HERE')

    def execute(self, context):
        scene = context.scene
        i = _shot_index(context)
        if i < 0 and self.scope != 'EVERY':
            self.report({'INFO'}, "You're live: the next Shoot keeps these lights")
            return {'CANCELLED'}
        n = apply_light_change(scene, self.scope, max(0, i))
        self.report({'INFO'}, "Lights kept in %d shot%s" % (n, "" if n == 1 else "s"))
        return {'FINISHED'}


class SM_OT_light_effect(bpy.types.Operator):
    """Drop a light effect onto the shots from here"""
    bl_idname = "stop_motion.light_effect"
    bl_label = "Add Light Effect"
    bl_options = {'REGISTER', 'UNDO'}

    effect: EnumProperty(items=EFFECTS)
    count: IntProperty(name="Over shots", min=1, max=200, default=6)

    def execute(self, context):
        scene = context.scene
        i = _shot_index(context)
        if i < 0:
            self.report({'WARNING'}, "Step back onto a shot first: effects go on shots you've taken")
            return {'CANCELLED'}
        n = apply_effect(scene, self.effect, i, self.count)
        self.report({'INFO'}, "%s on %d shot%s" % (dict((e[0], e[1]) for e in EFFECTS)[self.effect],
                                                   n, "" if n == 1 else "s"))
        return {'FINISHED'}


classes = (SM_OT_light_preset, SM_OT_hdri_preset, SM_OT_load_hdri, SM_OT_own_lights,
           SM_OT_apply_light, SM_OT_light_effect)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.stop_motion_effect_count = IntProperty(name="Over shots", min=1, max=200, default=6)


def unregister():
    del bpy.types.WindowManager.stop_motion_effect_count
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
