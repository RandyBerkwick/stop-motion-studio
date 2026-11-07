# SPDX-License-Identifier: GPL-3.0-or-later
"""Shot model, keying, retiming, captures and ghost.

A shot is one pose held for `hold` frames. Shots live in
scene.stop_motion.shots in film order; their frames are derived:
shot 0 starts at scene.frame_start, each next shot starts where the
previous one's hold ends. The "live" frame is the first frame after the
last shot: that is where the next Shoot lands.

Every key is CONSTANT, so a pose holds exactly until the next shot.
"""

import os
import tempfile
import uuid

import bpy
from bpy_extras import anim_utils

GHOST_PREFIX = "SM shot "


# ---------------------------------------------------------------- shot timing

def settings(scene):
    return scene.stop_motion


def shot_spans(scene):
    """[(index, shot, start, hold)] in film order."""
    out = []
    f = scene.frame_start
    for i, s in enumerate(settings(scene).shots):
        out.append((i, s, f, s.hold))
        f += s.hold
    return out


def live_frame(scene):
    sm = settings(scene)
    return scene.frame_start + sum(s.hold for s in sm.shots)


def shot_index_at(scene, frame):
    for i, _s, start, hold in shot_spans(scene):
        if start <= frame < start + hold:
            return i
    return -1


def shot_start(scene, index):
    return scene.frame_start + sum(s.hold for s in list(settings(scene).shots)[:index])


def is_live(scene):
    return scene.frame_current >= live_frame(scene)


def sync_range(scene):
    scene.frame_end = max(scene.frame_start, live_frame(scene) - 1)


def new_uid():
    return uuid.uuid4().hex[:10]


# ------------------------------------------------------------ what gets keyed

def _is_deformed_by_rig(ob):
    if ob.type != 'MESH':
        return False
    for m in ob.modifiers:
        if m.type == 'ARMATURE' and m.object is not None:
            return True
    return False


def tracked_objects(scene, context=None, scope='ALL'):
    """Objects whose pose is captured by a shot.

    Meshes bent by a rig follow the rig, so their own transform is not
    keyed (their shape keys still are, see key_pose)."""
    if scope == 'SELECTED' and context is not None:
        pool = list(context.selected_objects)
    else:
        pool = list(scene.objects)
    return [ob for ob in pool if not _is_deformed_by_rig(ob)]


def _rotation_path(t):
    mode = t.rotation_mode
    if mode == 'QUATERNION':
        return "rotation_quaternion"
    if mode == 'AXIS_ANGLE':
        return "rotation_axis_angle"
    return "rotation_euler"


def _key_transform(t, frame):
    for path in ("location", _rotation_path(t), "scale"):
        try:
            t.keyframe_insert(path, frame=frame)
        except (TypeError, RuntimeError):
            pass


def _key_custom_props(t, frame):
    """Rig controls (IK/FK switches, sliders) are usually custom props."""
    for k in list(t.keys()):
        if k.startswith("_"):
            continue
        v = t[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        try:
            t.keyframe_insert('["%s"]' % k, frame=frame)
        except (TypeError, RuntimeError):
            pass


def key_pose(scene, frame, objects):
    """Key the full current pose of `objects` at `frame`, constant."""
    touched = set()
    for ob in objects:
        _key_transform(ob, frame)
        _key_custom_props(ob, frame)
        touched.add(ob)
        if ob.type == 'ARMATURE' and ob.pose:
            for pb in ob.pose.bones:
                _key_transform(pb, frame)
                _key_custom_props(pb, frame)
    # Shape keys (replacement faces, mouths) on every mesh, rigged or not.
    for ob in scene.objects:
        if ob.type == 'MESH' and ob.data.shape_keys:
            key = ob.data.shape_keys
            for kb in key.key_blocks[1:]:
                try:
                    kb.keyframe_insert("value", frame=frame)
                except (TypeError, RuntimeError):
                    pass
            touched.add(key)
    # Puppets: which swap mesh is showing, and whether each pin is on.
    from . import puppet as _puppet
    for arm in _puppet.puppets(scene):
        for ob in _puppet.swap_objects(arm):
            for path in ("hide_viewport", "hide_render"):
                try:
                    ob.keyframe_insert(path, frame=frame)
                except (TypeError, RuntimeError):
                    pass
            touched.add(ob)
        for pb in arm.pose.bones:
            c = pb.constraints.get(_puppet.PIN_CONSTRAINT)
            if c is not None:
                c.keyframe_insert("influence", frame=frame)
                touched.add(arm)
    # Lighting is part of the shot too: brightness, colour, sky.
    from . import lighting as _lighting
    touched |= _lighting.key_lights(scene, frame)
    for idb in touched:
        for fc in fcurves_of(idb):
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.5:
                    kp.interpolation = 'CONSTANT'


# ----------------------------------------------------------- fcurve plumbing

def animated_ids(scene):
    seen = set()
    for ob in scene.objects:
        for idb in (ob, getattr(ob, "data", None)):
            if idb is not None and idb not in seen:
                seen.add(idb)
                yield idb
        if ob.type == 'MESH' and ob.data.shape_keys and ob.data.shape_keys not in seen:
            seen.add(ob.data.shape_keys)
            yield ob.data.shape_keys
    world = scene.world
    if world is not None and world.node_tree is not None and world.node_tree not in seen:
        seen.add(world.node_tree)
        yield world.node_tree


def fcurves_of(idb):
    ad = getattr(idb, "animation_data", None)
    if ad is None or ad.action is None:
        return []
    cb = anim_utils.animdata_get_channelbag_for_assigned_slot(ad)
    return list(cb.fcurves) if cb else []


def delete_keys_in(scene, start, end):
    """Remove every key with start <= frame < end."""
    for idb in animated_ids(scene):
        for fc in fcurves_of(idb):
            idx = [i for i, kp in enumerate(fc.keyframe_points)
                   if start - 0.5 < kp.co.x < end - 0.5]
            for i in reversed(idx):
                fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
            if idx:
                fc.update()


def snapshot(scene):
    """uid -> (start, hold) for later retime()."""
    return {s.uid: (start, hold) for _i, s, start, hold in shot_spans(scene)}


def retime(scene, before):
    """Move keys so each shot's keys follow it to its new start frame."""
    after = snapshot(scene)
    spans = sorted(((st, st + h, after[uid][0] - st)
                    for uid, (st, h) in before.items() if uid in after),
                   key=lambda t: t[0])
    old_end = max((st + h for st, h in before.values()), default=scene.frame_start)
    new_end = live_frame(scene)

    def shift(x):
        for st, en, d in spans:
            if st - 0.5 < x < en - 0.5:
                return d
        if x >= old_end - 0.5:
            return new_end - old_end
        return 0

    for idb in animated_ids(scene):
        for fc in fcurves_of(idb):
            moved = False
            for kp in fc.keyframe_points:
                d = shift(kp.co.x)
                if d:
                    kp.co.x += d
                    kp.handle_left.x += d
                    kp.handle_right.x += d
                    moved = True
            if moved:
                fc.update()
    sync_range(scene)


# ------------------------------------------------------------------ captures

def capture_dir(scene):
    sm = settings(scene)
    if bpy.data.filepath:
        d = bpy.path.abspath(sm.capture_dir)
    else:
        d = os.path.join(tempfile.gettempdir(), "stop_motion_unsaved", bpy.path.clean_name(scene.name))
    os.makedirs(d, exist_ok=True)
    return d


def capture_path(scene, uid):
    return os.path.join(capture_dir(scene), "shot_%s.png" % uid)


def find_camera_area(screen):
    if screen is None:
        return None, None
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            if space.region_3d and space.region_3d.view_perspective == 'CAMERA':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                return area, region
    return None, None


def capture(context, scene, uid):
    """Viewport-render the camera view to the shot's picture. Returns path or None."""
    path = capture_path(scene, uid)
    window = getattr(context, "window", None)
    area, region = find_camera_area(getattr(context, "screen", None))
    img_settings = scene.render.image_settings
    old_format = img_settings.file_format
    old_overlays = None
    try:
        img_settings.file_format = 'PNG'
        if area is not None and window is not None:
            space = area.spaces.active
            old_overlays = space.overlay.show_overlays
            space.overlay.show_overlays = False  # ghost and gizmos stay out of the picture
            with context.temp_override(window=window, area=area, region=region):
                bpy.ops.render.opengl(write_still=False, view_context=True)
        else:
            bpy.ops.render.opengl(write_still=False, view_context=False)
        result = bpy.data.images.get("Render Result")
        if result is None:
            return None
        result.save_render(path, scene=scene)
    except Exception as exc:  # capture must never block shooting
        print("Stop Motion: capture failed:", exc)
        return None
    finally:
        img_settings.file_format = old_format
        if old_overlays is not None:
            area.spaces.active.overlay.show_overlays = old_overlays
    refresh_image(scene, uid)
    return path


def shot_image(scene, uid, load=True):
    name = GHOST_PREFIX + uid
    img = bpy.data.images.get(name)
    if img is None and load:
        path = capture_path(scene, uid)
        if not os.path.exists(path):
            return None
        img = bpy.data.images.load(path, check_existing=False)
        img.name = name
    return img


def refresh_image(scene, uid):
    img = shot_image(scene, uid, load=False)
    if img is not None:
        img.filepath = capture_path(scene, uid)
        img.reload()
        if img.preview:
            img.preview.reload()
    else:
        shot_image(scene, uid)


def shot_icon(scene, uid):
    img = shot_image(scene, uid)
    if img is None:
        return 0
    img.preview_ensure()
    return img.preview.icon_id


def forget_capture(scene, uid):
    img = shot_image(scene, uid, load=False)
    if img is not None:
        bpy.data.images.remove(img)
    path = capture_path(scene, uid)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


# --------------------------------------------------------------------- ghost

def update_ghost(scene):
    cam = scene.camera
    if cam is None or cam.type != 'CAMERA':
        return
    sm = settings(scene)
    bgs = cam.data.background_images
    for bg in list(bgs):
        if bg.image is not None and bg.image.name.startswith(GHOST_PREFIX):
            bgs.remove(bg)
    if not sm.ghost_enabled:
        return
    frame = scene.frame_current
    earlier = [s.uid for _i, s, start, _h in shot_spans(scene) if start < frame
               and shot_index_at(scene, frame) != _i]
    picks = list(reversed(earlier[-sm.ghost_count:]))
    added = False
    for depth, uid in enumerate(picks):
        img = shot_image(scene, uid)
        if img is None:
            continue
        bg = bgs.new()
        bg.image = img
        bg.alpha = sm.ghost_opacity * (0.55 ** depth)
        bg.display_depth = 'FRONT'
        bg.frame_method = 'STRETCH'
        bg.show_expanded = False
        added = True
    if added:
        cam.data.show_background_images = True
