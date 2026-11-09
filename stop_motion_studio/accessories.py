# SPDX-License-Identifier: GPL-3.0-or-later
"""Puppet studio: hair, hats and extras from the kit.

These ride on the head (hair, hats, glasses) or the chest (name tag, scarf)
and are fitted to whatever head and body the puppet has now, so they follow
when the head gets bigger or a different body goes on. Like every kit part
they're remade from their recipe, so changing a proportion keeps them on.
"""

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import assembly as A

OPTIONAL = ("hair", "hat", "extra")
NONE = "none"

HAIR = [(NONE, "No hair"), ("mop", "Mop"), ("bun", "Bun"), ("spiky", "Spiky")]
HATS = [(NONE, "No hat"), ("cap", "Cap"), ("bobble", "Bobble hat"), ("top", "Top hat")]
EXTRAS = [(NONE, "Nothing"), ("tag", "Name tag"), ("scarf", "Scarf"), ("glasses", "Glasses")]

COLOUR = {"hair": "brown", "hat": "red", "extra": "white"}
EXTRA_COLOUR = {"tag": "white", "scarf": "red", "glasses": "black"}
BONE = {"hair": "head", "hat": "head", "extra": "chest"}


def part_of(arm, kind):
    for ob in A.kit_parts(arm):
        try:
            if json.loads(ob["sm_part"])["kind"] == kind:
                return ob
        except (KeyError, ValueError):
            pass
    return None


def bounds(obs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    found = False
    for ob in obs:
        if ob is None or ob.type != 'MESH':
            continue
        mw = ob.matrix_world
        for v in ob.data.vertices:
            p = mw @ v.co
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
            found = True
    return (lo, hi) if found else None


def head_frame(arm):
    """(centre, half sizes, top z) of the puppet's head, from the head part when
    there is one (so a long head gets a tall hat), else from the joints."""
    J, info = A._j(arm)
    four = info["template"] == 'FOUR_LEGS'
    head = part_of(arm, "head")
    if four:
        r = (J["nose"] - J["skull"]).length * 0.42
        c = J["skull"]
        half = Vector((r * 1.05, r * 1.1, r))
        return c, half, c.z + r
    b = bounds([head]) if head is not None else None
    if b is not None:
        lo, hi = b
        c = (lo + hi) / 2
        half = (hi - lo) / 2
        half.x = min(half.x, half.z * 1.2)      # ears don't count as head width
        return c, half, hi.z
    c = (J["skull"] + J["crown"]) / 2
    r = (J["crown"] - J["skull"]).length * 0.62
    return c, Vector((r, r * 0.95, r)), c.z + r


def chest_front(arm):
    """A point on the front of the chest (where a badge goes) and the body's half width."""
    J, info = A._j(arm)
    s = A.TEMPLATES[info["template"]][1] * info["props"]["height"]
    if info["template"] == 'FOUR_LEGS':
        return J["neck"] + Vector((0, -s * 0.06, -s * 0.06)), s * 0.06
    body = part_of(arm, "body")
    b = bounds([body]) if body is not None else None
    z = (J["chest"].z * 0.6 + J["waist"].z * 0.4)
    if b is not None:
        lo, hi = b
        # the front of the body at that height: nearest point going back from out in front
        best = None
        mw = body.matrix_world
        for v in body.data.vertices:
            p = mw @ v.co
            if abs(p.z - z) < (hi.z - lo.z) * 0.06 and abs(p.x - J["chest"].x) < (hi.x - lo.x) * 0.2:
                if best is None or p.y < best:
                    best = p.y
        y = best if best is not None else lo.y
        return Vector((J["chest"].x, y, z)), (hi.x - lo.x) / 2
    return Vector((J["chest"].x, J["chest"].y - s * 0.09, z)), s * 0.11


# ------------------------------------------------------------------ shapes

def _cylinder(bm, centre, radius, depth, segs=24):
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=radius, radius2=radius, depth=depth,
                          matrix=Matrix.Translation(centre))


def _ring(bm, centre, radius, tube, axis_rot, segs=20):
    pts = [centre + axis_rot @ Vector((math.cos(a) * radius, 0, math.sin(a) * radius))
           for a in (2 * math.pi * i / segs for i in range(segs + 1))]
    A.loft(bm, pts, [tube] * len(pts), segs=8, per_span=1, caps=False)


def _text_mesh(context, text, height):
    """Text as mesh points and faces (in the XY plane, facing +Z, centred), or None."""
    cu = bpy.data.curves.new("SM tag text", 'FONT')
    cu.body = text or "?"
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.size = 1.0
    cu.extrude = 0.02
    ob = bpy.data.objects.new("SM tag text", cu)
    context.scene.collection.objects.link(ob)
    try:
        context.view_layer.update()
        dg = context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        verts = [v.co.copy() for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
    finally:
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
    if not verts:
        return None
    lo = Vector(map(min, *verts)) if len(verts) > 1 else verts[0]
    hi = Vector(map(max, *verts)) if len(verts) > 1 else verts[0]
    k = height / max(1e-6, hi.y - lo.y)
    c = (lo + hi) / 2
    return [(v - c) * k for v in verts], polys, (hi.x - lo.x) * k


def make(context, arm, kind, variant, colour=None):
    """Make a built-in hair, hat or extra and put it on. Returns the object, or None for 'none'."""
    if variant == NONE:
        return None
    J, info = A._j(arm)
    four = info["template"] == 'FOUR_LEGS'
    s = A.TEMPLATES[info["template"]][1] * info["props"]["height"]
    colour = colour or (EXTRA_COLOUR.get(variant) if kind == "extra" else COLOUR[kind])
    col = arm.users_collection[0] if arm.users_collection else context.scene.collection
    bm = bmesh.new()
    bone = BONE[kind]
    second = None                     # (faces made after this index get the second colour, colour)
    c, half, top = head_frame(arm)
    h = half.z * 2
    if kind == "hair":
        if variant == "mop":
            A.blob(bm, Vector((c.x, c.y + half.y * 0.12, top - h * 0.32)), (half.x * 1.08, half.y * 1.05, h * 0.42))
        elif variant == "bun":
            A.blob(bm, Vector((c.x, c.y + half.y * 0.15, top - h * 0.25)), (half.x * 1.04, half.y * 1.0, h * 0.32))
            A.blob(bm, Vector((c.x, c.y + half.y * 0.75, top - h * 0.02)), (half.x * 0.36,) * 3, segs=16, rings=10)
        else:   # spiky
            A.blob(bm, Vector((c.x, c.y + half.y * 0.1, top - h * 0.25)), (half.x * 1.03, half.y * 1.0, h * 0.3))
            for i in range(7):
                a = -0.9 + 1.8 * i / 6
                tip_dir = Vector((math.sin(a), 0.25, math.cos(a) * 1.0)).normalized()
                base = Vector((c.x, c.y, top - h * 0.18)) + tip_dir * half.x * 0.55
                rot = Vector((0, 0, 1)).rotation_difference(tip_dir).to_matrix().to_4x4()
                bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=half.x * 0.22, radius2=0.0,
                                      depth=h * 0.38, matrix=Matrix.Translation(base + tip_dir * h * 0.12) @ rot)
    elif kind == "hat":
        if variant == "cap":
            A.blob(bm, Vector((c.x, c.y, top - h * 0.2)), (half.x * 1.07, half.y * 1.07, h * 0.3))
            A.blob(bm, Vector((c.x, c.y - half.y * 0.95, top - h * 0.31)), (half.x * 0.72, half.y * 0.6, h * 0.045))   # the peak, above the eyes
        elif variant == "bobble":
            A.blob(bm, Vector((c.x, c.y, top - h * 0.1)), (half.x * 1.09, half.y * 1.09, h * 0.34))
            A.blob(bm, Vector((c.x, c.y, top - h * 0.225)), (half.x * 1.11, half.y * 1.11, h * 0.07))   # turn-up, above the eyes
            A.blob(bm, Vector((c.x, c.y, top + h * 0.17)), (half.x * 0.3,) * 3, segs=16, rings=10)
            second = (None, "white")
        else:   # top hat
            _cylinder(bm, Vector((c.x, c.y, top + h * 0.2)), half.x * 0.78, h * 0.62)
            _cylinder(bm, Vector((c.x, c.y, top - h * 0.09)), half.x * 1.25, h * 0.04, segs=32)
            colour = colour if colour != "red" else "black"
    else:   # extras
        if variant == "glasses":
            bone = "head"
            front = c.y - half.y * 1.02
            ez = c.z + half.z * 0.18
            rx = half.x * 0.22
            rot = Matrix.Identity(3)
            for sx in (1, -1):
                _ring(bm, Vector((c.x + sx * half.x * 0.38, front, ez)), rx, rx * 0.16, rot)
            A.loft(bm, [Vector((c.x - half.x * 0.17, front, ez + rx * 0.2)), Vector((c.x + half.x * 0.17, front, ez + rx * 0.2))],
                   [rx * 0.12, rx * 0.12], segs=8)
        elif variant == "scarf":
            n = J["neck"]
            r = s * (0.06 if not four else 0.075)
            ring_c = n + Vector((0, 0, -s * 0.012))
            _ring(bm, ring_c, r, s * 0.024, Matrix.Rotation(math.pi / 2, 3, 'X'), segs=24)
            A.loft(bm, [ring_c + Vector((r * 0.45, -r * 0.85, 0)), ring_c + Vector((r * 0.6, -r * 1.05, -s * 0.08)),
                        ring_c + Vector((r * 0.7, -r * 1.05, -s * 0.14))], [s * 0.02, s * 0.018, s * 0.017], segs=10, squash=0.45)
        else:   # name tag
            p, half_w = chest_front(arm)
            w = min(s * 0.1, half_w * 0.95)
            th = w * 0.55
            at = p + Vector((half_w * 0.35 if not four else 0, -s * 0.004, 0))
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(at) @ Matrix.Diagonal((w, s * 0.008, th, 1)))
            nbase = len(bm.faces)
            txt = _text_mesh(context, arm.name, th * 0.5)
            if txt is not None:
                verts, polys, tw = txt
                k = min(1.0, (w * 0.86) / max(1e-6, tw))
                rot = Matrix.Rotation(math.pi / 2, 3, 'X')            # +Z (facing) becomes -Y (front)
                origin = at + Vector((0, -s * 0.0045, 0))
                bv = [bm.verts.new(origin + rot @ (v * k)) for v in verts]
                for poly in polys:
                    try:
                        bm.faces.new([bv[i] for i in poly])
                    except ValueError:
                        pass
                second = (nbase, "black")
    ob = A._mesh_object(A._part_name(arm, kind), bm, colour, col)
    if second is not None:
        start, other = second
        ob.data.materials.append(A.clay(other))
        if start is None:                                      # bobble hat: the bobble and turn-up
            cut = top - h * 0.18
            for p in ob.data.polygons:
                cen = sum((ob.data.vertices[i].co for i in p.vertices), Vector()) / len(p.vertices)
                if cen.z > top + h * 0.06 or cen.z < cut:
                    p.material_index = 1
        else:
            for p in ob.data.polygons[start:]:
                p.material_index = 1
    ob["sm_part"] = json.dumps({"kind": kind, "variant": variant, "colour": colour, "side": ""})
    A.attach_rigid(ob, arm, bone)
    return ob
