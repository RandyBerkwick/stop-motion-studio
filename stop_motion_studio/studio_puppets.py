# SPDX-License-Identifier: GPL-3.0-or-later
"""The Studio's Puppets mode: the puppet studio.

Start from a parts kit (build on a wire armature), a sculpt (place its
joints), or a rig you already have (the original setup screen). Then
face & hands, try it out, save it to the library.
"""

import json
import os

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

from . import assembly, faces, library, puppet, rigsculpt, trial
from .studio_kit import Rect, Theme

STEPS = (('BUILD', "Build"), ('JOINTS', "Joints"), ('FACE', "Face & hands"), ('TRY', "Try it"), ('SAVE', "Save"))


class PState:
    def __init__(self):
        self.start = 'PARTS'          # PARTS | SCULPT | RIG
        self.step = 'BUILD'
        self.kind = None              # kit kind shown in Build
        self.joint = 0                # which joint a click places
        self.set_name = None          # swap set shown in Face
        self.pending = {}             # proportion -> value, applied after a short pause
        self.template = 'PERSON'      # for a sculpt


P = PState()


def _studio():
    from . import studio
    return studio


def toast(text, secs=2.0):
    _studio().toast(text, secs)


def redraw():
    _studio().redraw()


def run(op, *a, **kw):
    return _studio().run(op, *a, **kw)


# -------------------------------------------------------------- what we're on

def current_build(context):
    """The armature being built (active, else the last one in the scene)."""
    arm = assembly._arm(context)
    if arm is not None:
        return arm
    builds = [o for o in context.scene.objects if o.type == 'ARMATURE' and o.get("sm_build")]
    return builds[-1] if builds else None


def current_sculpt(context):
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and not ob.get("sm_part") and not ob.get("sm_face"):
        if not any(m.type == 'ARMATURE' for m in ob.modifiers):
            return ob
    name = context.scene.get("sm_sculpt", "")
    ob = bpy.data.objects.get(name)
    return ob if ob is not None and ob.type == 'MESH' else None


def steps_for(start):
    if start == 'PARTS':
        return ['BUILD', 'FACE', 'TRY', 'SAVE']
    if start == 'SCULPT':
        return ['JOINTS', 'FACE', 'TRY', 'SAVE']
    return []


def set_start(start):
    P.start = start
    P.step = steps_for(start)[0] if steps_for(start) else 'RIG'
    redraw()


def set_step(step):
    if step in steps_for(P.start):
        P.step = step
        if step == 'TRY':
            arm = current_build(bpy.context)
            if arm is not None and not trial.last_results(arm):
                try_now()
    redraw()


def frame(ob_list):
    """Point the free view at these objects."""
    S = _studio().S
    pts = []
    for ob in ob_list:
        if ob.type == 'MESH':
            pts.extend(ob.matrix_world @ Vector(c) for c in ob.bound_box)
    if not pts:
        return
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    S.free.location = (lo + hi) / 2
    S.free.distance = max(1.0, (hi - lo).length * 1.6)
    area, _r = _studio().studio_area()
    if area is not None and S.live == 'FREE':
        S.free.apply(area.spaces.active.region_3d)


def enter():
    """Puppets mode opens on the free view, looking at the puppet."""
    st = _studio()
    if st.S.live != 'FREE':
        st.swap_views()
    arm = current_build(bpy.context)
    if arm is not None:
        frame([o for o in arm.children if o.type == 'MESH'])


# ------------------------------------------------------------------ header

def draw_headers(kit, hl, hc, s):
    t = Theme
    kit.label(Rect(hl.x + 16 * s, hl.y, 90 * s, hl.h), "START FROM", 11, t.soft, "left", True)
    cells = Rect(hl.x + 100 * s, hl.cy - 15 * s, hl.w - 112 * s, 30 * s).split_cols(3, 3 * s)
    for cell, (k, label) in zip(cells, (('PARTS', "Parts kit"), ('SCULPT', "A sculpt"), ('RIG', "A rig"))):
        kit.button("pstart:" + k, cell, label, (lambda kk=k: set_start(kk)), "tab", P.start == k, size=12)
    steps = steps_for(P.start)
    if not steps:
        kit.label(Rect(hc.x + 16 * s, hc.y, hc.w, hc.h), "Set up a rig you already have: rings, swaps and pins", 12, t.muted)
        return
    x = hc.x + 14 * s
    shown = [k for k, _l in STEPS]
    for n, (k, label) in enumerate(STEPS):
        if P.start == 'PARTS' and k == 'JOINTS':
            label = "Joints ✓"
        if P.start == 'SCULPT' and k == 'BUILD':
            continue
        w = kit.text_width(label, 12) + 46 * s
        r = Rect(x, hc.cy - 16 * s, w, 32 * s)
        here = P.step == k
        done = k in steps and steps.index(k) < steps.index(P.step) if P.step in steps else False
        if P.start == 'PARTS' and k == 'JOINTS':
            done = True
        kit.button("pstep:" + k, r, "", (lambda kk=k: set_step(kk)), "tab", here, enabled=(k in steps or done), size=12)
        dot = t.blue if here else (t.yellow if done else t.line_strong)
        if t.sketchy and not (here or done):
            kit.p.circle(r.x + 15 * s, r.cy, 10 * s, t.panel)
            kit.p.ring(r.x + 15 * s, r.cy, 10 * s, t.muted, 1.5 * s)
        else:
            kit.p.circle(r.x + 15 * s, r.cy, 10 * s, dot)
        num = "✓" if done else str(len([1 for kk in shown[:n + 1] if not (P.start == 'SCULPT' and kk == 'BUILD')]))
        num_col = (t.on_yellow if done else (t.ground if here else t.muted)) if t.sketchy else (t.ground if (here or done) else t.muted)
        kit.label(Rect(r.x + 5 * s, r.y, 20 * s, r.h), num, 11, num_col, "center", True)
        kit.label(Rect(r.x + 30 * s, r.y, w - 34 * s, r.h), label, 12, t.text if (here or done) else t.muted, "left", here)
        x += w + 6 * s
        if x > hc.right - 60 * s:
            break


# ------------------------------------------------------------------ left column

def draw_left(kit, r, ctx, scene, s, Column):
    if P.start == 'RIG':
        return False                       # the Studio draws its usual picture column
    if P.step == 'BUILD':
        _left_build(kit, r, ctx, s, Column)
    elif P.step == 'JOINTS':
        _left_joints(kit, r, ctx, s, Column)
    elif P.step == 'FACE':
        _left_face(kit, r, ctx, s, Column)
    else:
        return False
    return True


def _left_build(kit, r, ctx, s, Column):
    t = Theme
    col = Column(kit, r, s)
    arm = current_build(ctx)
    if arm is None:
        col.title("Build a puppet")
        col.note("Start on a wire armature with a first set")
        col.note("of clay parts, then change any of them.")
        a, b = col.row(44).split_cols(2, 6 * s)
        kit.button("pnew:person", a, "A person", lambda: new_build('PERSON'), "accent")
        kit.button("pnew:four", b, "Four legs", lambda: new_build('FOUR_LEGS'), "accent")
        a, b = col.row(36).split_cols(2, 6 * s)
        kit.button("pnew:child", a, "Small child", lambda: new_build('CHILD'), size=12)
        kit.button("pnew:tall", b, "Tall", lambda: new_build('TALL'), size=12)
        return
    kit_ = assembly.kit_for(arm)
    kinds = list(kit_)
    if P.kind not in kinds:
        P.kind = kinds[0]
    col.title("Parts kit · " + arm.name)
    cells = col.row(30, 6).split_cols(len(kinds), 3 * s)
    for cell, k in zip(cells, kinds):
        kit.button("pkind:" + k, cell, kit_[k][0], (lambda kk=k: setattr(P, "kind", kk) or redraw()), "tab", P.kind == k, size=11)
    info = assembly.build_info(arm)
    on = {p["kind"]: p for p in info.get("parts", [])}
    current = on.get(P.kind)
    for vid, label in kit_[P.kind][1]:
        sel = current is not None and current["variant"] == vid
        kit.button("pvar:" + vid, col.row(40, 6), label + ("  ·  on " + arm.name if sel else ""),
                   (lambda v=vid: use_part(P.kind, v)), "clay", sel, size=13)
    col.heading("COLOUR")
    colours = list(assembly.COLOURS)
    per = 7
    for start in range(0, len(colours), per):
        cells = col.row(28, 5).split_cols(per, 5 * s)
        for cell, c in zip(cells, colours[start:start + per]):
            rgb = assembly.COLOURS[c]
            sel = current is not None and current["colour"] == c
            kit.p.rect(cell, (*rgb, 1.0), 6 * s)
            if sel:
                kit.p.rect_outline(cell, t.blue, 6 * s, 2.5 * s)
            kit.area("pcol:" + c, cell, on_click=(lambda cc=c: colour_part(P.kind, cc)))
    col.note("Parts snap onto the wire: the wire is the rig.")


def _left_joints(kit, r, ctx, s, Column):
    t = Theme
    col = Column(kit, r, s)
    ob = current_sculpt(ctx)
    if ob is None:
        col.title("Rig a sculpt")
        col.note("Bring in a sculpt (Bring in…, or from Nomad)")
        col.note("and click it in the live view.")
        kit.button("pj:bring", col.row(38), "Bring in…", lambda: _studio().set_overlay('LIBRARY'))
        return
    col.title(ob.name)
    a, b = col.row(30, 6).split_cols(2, 4 * s)
    kit.button("ptpl:person", a, "Person", lambda: set_template('PERSON'), "tab", P.template != 'FOUR_LEGS', size=12)
    kit.button("ptpl:four", b, "Four legs", lambda: set_template('FOUR_LEGS'), "tab", P.template == 'FOUR_LEGS', size=12)
    joints = rigsculpt.get_joints(ob)
    places = rigsculpt.PLACE[P.template]
    col.heading("JOINTS · %d OF %d PLACED" % (sum(1 for n, _l in places if n in joints), len(places)))
    for i, (name, label) in enumerate(places):
        if not col.room(30):
            break
        here = i == P.joint
        row = col.row(26, 2)
        kit.button("pjoint:%d" % i, row, "", (lambda k=i: setattr(P, "joint", k) or redraw()), "tab", here, size=12)
        kit.p.circle(row.x + 12 * s, row.cy, 7 * s, t.accent if here else (t.yellow if name in joints else t.line_strong))
        kit.label(Rect(row.x + 26 * s, row.y, row.w - 30 * s, row.h), label, 12, t.text if here or name in joints else t.muted)
    kit.button("pj:guess", col.row(34), "Guess them all for me", lambda: guess_joints(ob))


def _left_face(kit, r, ctx, s, Column):
    t = Theme
    col = Column(kit, r, s)
    arm = current_build(ctx)
    if arm is None:
        col.title("Face & hands")
        col.note("Build or rig a puppet first.")
        return
    col.title("Swap parts")
    col.note("One shows at a time; each shot keeps yours.")
    pp = arm.stop_motion_puppet
    names = [ss.name for ss in pp.swap_sets]
    if names and P.set_name not in names:
        P.set_name = names[0]
    for ss in pp.swap_sets:
        if not col.room(44):
            break
        kit.button("pset:" + ss.name, col.row(38, 5), "%s  ·  %d" % (ss.name, len(ss.items)),
                   (lambda n=ss.name: setattr(P, "set_name", n) or redraw()), "tab", P.set_name == ss.name, size=13)
    if not names:
        col.note("None yet.")
    kit.button("pface:make", col.row(38), "Make mouths, eyes and hands" if not names else "Make them again",
               lambda: make_faces(arm), "accent" if not names else "ghost", size=12)
    col.heading("ADD A SET FROM")
    a, b = col.row(34).split_cols(2, 5 * s)
    kit.button("pface:lib", a, "The library", lambda: _studio().set_overlay('LIBRARY'), size=12)
    kit.button("pface:find", b, "Find in the rig", lambda: run(bpy.ops.stop_motion.rescan_swaps, puppet=arm.name) or redraw(), size=12)


# ------------------------------------------------------------------ right column

def draw_right(kit, r, ctx, scene, s, Column):
    if P.start == 'RIG':
        return False                       # the original setup screen
    {'BUILD': _right_build, 'JOINTS': _right_joints, 'FACE': _right_face,
     'TRY': _right_try, 'SAVE': _right_save}.get(P.step, _right_build)(kit, r, ctx, s, Column)
    return True


def _cta(kit, col, wid, label, cb, s):
    y = col.r.y
    kit.button(wid, Rect(col.r.x, y, col.r.w, 46 * s), label, cb, "accent", size=14)


def _right_build(kit, r, ctx, s, Column):
    t = Theme
    col = Column(kit, r, s)
    arm = current_build(ctx)
    col.title("Armature")
    if arm is None:
        col.note("Pick a kind of puppet on the left.")
        return
    info = assembly.build_info(arm)
    tpl = info["template"]
    for row_keys in ((('CHILD', "Small child"), ('PERSON', "Person")), (('TALL', "Tall"), ('FOUR_LEGS', "Four legs"))):
        cells = col.row(36, 5).split_cols(2, 5 * s)
        for cell, (k, label) in zip(cells, row_keys):
            kit.button("ptpl:" + k, cell, label, (lambda kk=k: change_template(arm, kk)), "tab", tpl == k, size=12)
    col.heading("PROPORTIONS")
    for key in ("height", "head", "arms", "legs"):
        v = P.pending.get(key, info["props"].get(key, 1.0))
        row = col.row(26, 4)
        kit.label(Rect(row.x, row.y, 100 * s, row.h), assembly.prop_label(tpl, key), 12, t.text)
        kit.label(Rect(row.right - 44 * s, row.y, 44 * s, row.h), "%d%%" % round(v * 100), 11, t.muted, "right")
        kit.slider("pprop:" + key, Rect(row.x + 104 * s, row.y, row.w - 152 * s, row.h), (v - 0.6) / 0.9,
                   (lambda val, kk=key: set_prop(arm, kk, 0.6 + val * 0.9)))
    if tpl != 'FOUR_LEGS':
        col.heading("HANDS")
        style = info.get("hands", "MITTEN")
        a, b = col.row(34).split_cols(2, 5 * s)
        kit.button("phand:m", a, "Mitten", lambda: run(bpy.ops.stop_motion.hand_style, puppet=arm.name, style='MITTEN') or redraw(), "tab", style == 'MITTEN', size=12)
        kit.button("phand:f", b, "4 fingers", lambda: run(bpy.ops.stop_motion.hand_style, puppet=arm.name, style='FINGERS') or redraw(), "tab", style == 'FINGERS', size=12)
    col.note("Changing a proportion moves the sockets;")
    col.note("the parts follow and stay joined.")
    _cta(kit, col, "pnext:build", "Next: face & hands", lambda: set_step('FACE'), s)


def _right_joints(kit, r, ctx, s, Column):
    col = Column(kit, r, s)
    ob = current_sculpt(ctx)
    col.title("How it bends")
    col.note("Click in the clay to put the chosen joint")
    col.note("there: it goes in the middle of the clay.")
    col.note("Left joints are copied to the right side.")
    if ob is None:
        return
    places = rigsculpt.PLACE[P.template]
    if 0 <= P.joint < len(places):
        col.heading("NOW: " + places[P.joint][1].upper())
    col.note("Making the rig adds bones at the joints,")
    col.note("skins the clay to them, and puts on rings")
    col.note("and foot pins.")
    _cta(kit, col, "pnext:rig", "Make the rig", lambda: make_rig(ob), s)


def _right_face(kit, r, ctx, s, Column):
    t = Theme
    col = Column(kit, r, s)
    arm = current_build(ctx)
    if arm is None:
        return
    pp = arm.stop_motion_puppet
    ss = next((x for x in pp.swap_sets if x.name == P.set_name), None)
    if ss is None:
        col.title("Face & hands")
        col.note("Make the swap parts on the left.")
    else:
        col.title(ss.name)
        active = puppet.swap_active(ss)
        items = list(ss.items)
        si = list(pp.swap_sets).index(ss)
        for start in range(0, len(items), 3):
            cells = col.row(40, 5).split_cols(3, 5 * s)
            for k, (cell, it) in enumerate(zip(cells, items[start:start + 3])):
                ii = start + k
                kit.button("pswap:%d" % ii, cell, it.label,
                           (lambda b=ii: run(bpy.ops.stop_motion.swap, puppet=arm.name, set_index=si, item=b) or redraw()),
                           "clay", ii == active, size=12)
        col.note("Click to see each one on the puppet.")
        col.note("Reshape one: Sculpt tab, or send it to Nomad.")
    _cta(kit, col, "pnext:face", "Next: try it out", lambda: set_step('TRY'), s)


def _right_try(kit, r, ctx, s, Column):
    t = Theme
    col = Column(kit, r, s)
    arm = current_build(ctx)
    if arm is None:
        return
    col.title("Things to look at")
    res = trial.last_results(arm)
    found = [(rr["name"], p) for rr in res for p in rr["problems"]]
    if not res:
        col.note("Try it out to see it in some test poses.")
    elif not found:
        col.note("Nothing to fix: it bends well in every pose.")
    seen = set()
    for pose, p in found:
        key = (p["text"], p["fix"])
        if key in seen or not col.room(70):
            continue
        seen.add(key)
        row = col.row(52, 6)
        kit.panel(row, t.raised, 8)
        kit.label(Rect(row.x + 10 * s, row.cy, row.w - 130 * s, 20 * s), p["text"], 12, t.text, "left", True)
        kit.label(Rect(row.x + 10 * s, row.y + 6 * s, row.w - 130 * s, 16 * s), "in the %s pose" % pose.lower(), 11, t.muted)
        kit.button("pfix:%s:%s" % key, Rect(row.right - 116 * s, row.cy - 14 * s, 108 * s, 28 * s), p["fix_label"],
                   (lambda w=p["fix"]: fix(arm, w)), size=11)
    kit.button("ptry:again", col.row(34), "Try it again", try_now, size=12)
    _cta(kit, col, "pnext:try", "Next: save", lambda: set_step('SAVE'), s)


def _right_save(kit, r, ctx, s, Column):
    t = Theme
    col = Column(kit, r, s)
    arm = current_build(ctx)
    if arm is None:
        return
    col.title("Save " + arm.name)
    col.note("Into the library, with its picture, to bring")
    col.note("into any project. It's ready to animate here too.")
    kit.button("psave", col.row(44), "Save to the library", lambda: save(arm), "accent", size=14)
    kit.button("panim", col.row(38), "Animate it now", lambda: _studio().set_mode('ANIMATE'), size=13)
    kit.button("pnewpup", col.row(34), "Build another", lambda: new_another(), size=12)


# ------------------------------------------------------------------ live view

def draw_live(kit, live, ctx, s):
    """Joint dots (Joints step), test-pose pictures (Try it)."""
    if P.start == 'SCULPT' and P.step == 'JOINTS':
        _live_joints(kit, live, ctx, s)
    elif P.step == 'TRY':
        _live_try(kit, live, ctx, s)


def _region():
    area, region = _studio().studio_area()
    if area is None:
        return None, None
    return region, area.spaces.active.region_3d


def _live_joints(kit, live, ctx, s):
    t = Theme
    ob = current_sculpt(ctx)
    region, rv3d = _region()
    if ob is None or region is None:
        return
    joints = rigsculpt.get_joints(ob)
    places = rigsculpt.PLACE[P.template]
    now = places[P.joint][0] if 0 <= P.joint < len(places) else None
    for name, p in joints.items():
        q = view3d_utils.location_3d_to_region_2d(region, rv3d, p)
        if q is None or not live.contains(q.x, q.y):
            continue
        base = name if not name.endswith(".R") else name[:-2] + ".L"
        hot = base == now
        kit.p.circle(q.x, q.y, (8 if hot else 6) * s, t.accent if hot else t.yellow)
        kit.p.circle(q.x, q.y, (3 if hot else 2) * s, t.ground)
    if now:
        label = places[P.joint][1]
        w = kit.text_width("Click the middle of: " + label, 13) + 28 * s
        r = Rect(live.x + 14 * s, live.top - 50 * s, w, 34 * s)
        kit.panel(r, Theme.raised, 8, Theme.line_strong)
        kit.label(r, "Click the middle of: " + label, 13, t.text, "center", True)


def _live_try(kit, live, ctx, s):
    t = Theme
    arm = current_build(ctx)
    if arm is None:
        return
    res = trial.last_results(arm)
    if not res:
        return
    kit.p.rect(live, (0.11, 0.10, 0.09, 0.94))
    n = len(res)
    gap = 12 * s
    cw = (live.w - gap * (n + 1)) / n
    ch = min(live.h - 2 * gap, cw * 1.25)
    y = live.cy - ch / 2
    for i, rr in enumerate(res):
        r = Rect(live.x + gap + i * (cw + gap), y, cw, ch)
        bad = bool(rr["problems"])
        kit.panel(r, t.panel, 10, t.yellow if bad else t.line)
        pic = Rect(r.x + 6 * s, r.y + 34 * s, r.w - 12 * s, r.h - 40 * s)
        kit.p.rect(pic, (0.36, 0.33, 0.30, 1.0), 6 * s)
        img = library.thumb_image(rr["picture"]) if rr.get("picture") else None
        if img is not None:
            kit.p.image(pic.inset(4 * s).fit_aspect(1.0), img)
        kit.label(Rect(r.x + 10 * s, r.y + 6 * s, r.w - 20 * s, 24 * s), rr["name"], 13, t.text, "left", True)
        kit.label(Rect(r.x + 10 * s, r.y + 6 * s, r.w - 20 * s, 24 * s),
                  ("%d to look at" % len(rr["problems"])) if bad else "fine", 11, t.mark if bad else ((0.23, 0.56, 0.31, 1) if t.sketchy else (0.72, 0.88, 0.63, 1)), "right")


def live_click(context, mx, my):
    """A click in the live view while placing joints. True if it was used."""
    if not (P.start == 'SCULPT' and P.step == 'JOINTS'):
        return False
    ob = current_sculpt(context)
    region, rv3d = _region()
    if ob is None or region is None:
        return False
    places = rigsculpt.PLACE[P.template]
    if not (0 <= P.joint < len(places)):
        return False
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, (mx, my))
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, (mx, my))
    tree, _v = rigsculpt.mesh_tree(context, ob)
    p = rigsculpt.through(tree, o, d)
    if p is None:
        toast("Click on the clay")
        return True
    joints = rigsculpt.get_joints(ob)
    rigsculpt.place(ob, joints, places[P.joint][0], p)
    if P.joint < len(places) - 1:
        P.joint += 1
    redraw()
    return True


# ------------------------------------------------------------------ actions

def new_build(template):
    r = run(bpy.ops.stop_motion.new_build, template=template)
    if r == {'FINISHED'}:
        arm = current_build(bpy.context)
        frame([o for o in arm.children if o.type == 'MESH'])
        toast("%s is on the armature: change any part" % arm.name)
    redraw()


def new_another():
    P.start, P.step = 'PARTS', 'BUILD'
    ctx = bpy.context
    for o in ctx.selected_objects:
        o.select_set(False)
    ctx.view_layer.objects.active = None
    redraw()


def use_part(kind, variant):
    arm = current_build(bpy.context)
    if arm is None:
        return
    run(bpy.ops.stop_motion.build_part, puppet=arm.name, kind=kind, variant=variant)
    bpy.context.view_layer.objects.active = arm
    redraw()


def colour_part(kind, colour):
    arm = current_build(bpy.context)
    if arm is None:
        return
    run(bpy.ops.stop_motion.build_colour, puppet=arm.name, kind=kind, colour=colour)
    redraw()


def change_template(arm, tpl):
    run(bpy.ops.stop_motion.build_shape, puppet=arm.name, template=tpl)
    bpy.context.view_layer.objects.active = arm
    frame([o for o in arm.children if o.type == 'MESH'])
    redraw()


def set_prop(arm, key, value):
    """Sliders: remember the value now, rebuild when the hand stops moving."""
    P.pending[key] = max(0.6, min(1.5, value))
    P.pending["_arm"] = arm.name
    if bpy.app.timers.is_registered(_apply_props):
        bpy.app.timers.unregister(_apply_props)
    bpy.app.timers.register(_apply_props, first_interval=0.3)
    redraw()


def _apply_props():
    pend = dict(P.pending)
    P.pending.clear()
    arm = bpy.data.objects.get(pend.pop("_arm", ""))
    if arm is None or not pend:
        return None
    try:
        assembly.change_build(bpy.context, arm, None, pend)
        bpy.context.view_layer.objects.active = arm
    except Exception as exc:
        print("Stop Motion: couldn't change the armature:", exc)
    redraw()
    return None


def set_template(tpl):
    P.template = tpl
    P.joint = 0
    ob = current_sculpt(bpy.context)
    if ob is not None:
        ob["sm_template"] = tpl
    redraw()


def guess_joints(ob):
    bpy.context.scene["sm_sculpt"] = ob.name
    run(bpy.ops.stop_motion.guess_joints, mesh=ob.name, template='FOUR_LEGS' if P.template == 'FOUR_LEGS' else 'PERSON')
    toast("Guessed: drag the view round and click any that are off")
    redraw()


def make_rig(ob):
    bpy.context.scene["sm_sculpt"] = ob.name
    ob["sm_template"] = P.template
    if not rigsculpt.get_joints(ob):
        rigsculpt.set_joints(ob, rigsculpt.guess(bpy.context, ob, P.template))
    r = run(bpy.ops.stop_motion.make_sculpt_rig, mesh=ob.name)
    if r == {'FINISHED'}:
        arm = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'
                    and assembly.build_info(o).get("sculpt") == ob.name), None)
        if arm is not None:
            bpy.context.view_layer.objects.active = arm
        P.step = 'FACE'
        toast("Rigged: rings and pins are on")
    redraw()


def make_faces(arm):
    r = run(bpy.ops.stop_motion.make_faces, puppet=arm.name)
    if r == {'FINISHED'} and not arm.stop_motion_puppet.enabled:
        assembly.finish_build(bpy.context, arm)
    bpy.context.view_layer.objects.active = arm
    redraw()


def try_now():
    arm = current_build(bpy.context)
    if arm is None:
        return
    if not arm.stop_motion_puppet.enabled:
        assembly.finish_build(bpy.context, arm)
    toast("Trying it out…", 1.0)
    run(bpy.ops.stop_motion.try_puppet, puppet=arm.name)
    redraw()


def fix(arm, what):
    run(bpy.ops.stop_motion.fix_puppet, puppet=arm.name, what=what)
    redraw()


def save(arm):
    r = run(bpy.ops.stop_motion.save_puppet, puppet=arm.name, name=arm.name)
    if r == {'FINISHED'}:
        toast("%s is in the library" % arm.name)
    redraw()
