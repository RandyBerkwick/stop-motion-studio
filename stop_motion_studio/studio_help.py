"""Help panels for the Studio: step-by-step guides with small animated pictures.

Each view has a guide (TOPICS). The help column opens on the left of the Studio
(the ? Help button, or H) and follows the view you're on; arrows browse the
others. The pictures are drawn live with the Studio's own painter, so they
match the look (dark or Sketchbook) and loop while the panel is open."""

import math
import time

from .studio_kit import Rect, Theme

# ------------------------------------------------------------------ guides

TOPICS = {
    'ANIMATE': ("Animating", [
        ("Pose your puppet", "Drag a ring to move that part. Alt+drag turns it. Hold Shift (or use the wheel) to push it further away or bring it nearer.", "drag_ring"),
        ("Take a picture", "Press Shoot, or Enter. The picture goes into the strip along the bottom.", "shoot"),
        ("Move it a tiny bit", "The faint ghost is your last picture. Move the puppet just a little from there: small moves make smooth films.", "ghost"),
        ("Again and again", "Pose, shoot, pose, shoot. At 12 pictures a second, a one-second wave is about six pictures held for two frames each.", "repeat"),
        ("Faces and hands", "Click a mouth, eyes or hand on the right to swap it, or press D over the puppet for the swap pop-up. Each picture keeps its own.", "swap"),
        ("Hold a picture longer", "Drag the right edge of a card in the strip: wider holds it longer. Use it for pauses and big moments.", "hold"),
        ("Fix an earlier picture", "Click its card: you're posing over it, with the ghost of the one before. Re-pose and Shoot to replace it. LIVE takes you back to the end.", "pose_over"),
        ("Watch it", "Press Space (or Play) to watch what you've made so far. Space again stops.", "play"),
    ]),
    'SET': ("Building a scene", [
        ("Bring things in", "Bring in… (top bar) opens your library: sets, props and puppets. Click one and it lands on the set where the camera is looking.", "bring_in"),
        ("Put things in place", "Click Arrange, then drag anything along the set: it slides over surfaces and sits on top, never inside. The wheel spins it.", "arrange"),
        ("Stamp copies", "Select something small, like a flower, click Stamp copies, then click or drag over the bush. Each copy is a little different.", "stamp"),
        ("Set pieces stay put", "Make the table a set piece: it isn't animated, so moving it moves it in every picture.", "set_piece"),
        ("Props in hands", "Put a prop near a hand and click Hold in hand: it follows the hand as you pose. Drop lets it go, and it lands on what's below.", "hold_prop"),
        ("Wear it", "Click Wear it on a prop, then click the puppet where it goes: a hat on the head, a badge on the chest. It rides on that part. Make a swap to pick it shot by shot.", "wear"),
        ("Cameras", "+ makes a camera from where the free view is looking. The padlock stops it moving. Pick another camera while you shoot to cut to it.", "cameras"),
    ]),
    'BRING_IN': ("Bringing things in", [
        ("Your library", "Everything you've saved or made lives here as pictures: puppets, props, whole sets.", "library"),
        ("Bring one in", "Click a picture, then say what it is: a puppet gets rings, a prop can be held and dropped, a set piece stays put.", "bring_in"),
        ("Keep things for later", "Select something on your set and click Add what's selected. It goes into the library for every project.", "save_lib"),
    ]),
    'LIGHT': ("Lighting", [
        ("Pick a lighting", "Click a preset: Three-point, Golden hour, Moonlight… It relights the whole set at once.", "light_preset"),
        ("Change it on a shot", "Go to a picture, change a light, then choose: just this picture, from here on, or every picture.", "light"),
        ("Effects", "Drop a Flash, Flicker, Fade to night or Torch sweep on a picture. It plays across the next few pictures.", "light_effect"),
    ]),
    'SCULPT': ("Sculpting a picture", [
        ("Pick the shot and the part", "Go to the picture you want to change, click the part in the live view, then Sculpt here.", "sculpt_pick"),
        ("Push the clay", "Pick a clay tool, set its size and strength, and push, pull or smooth. Only this picture changes.", "sculpt"),
        ("Keep it", "Done. Then choose: just this picture, carry it on from here, or Keep shape to make it a new swap (a new hand shape, a new mouth).", "keep_shape"),
    ]),
    'REVIEW': ("Watching and sharing", [
        ("Play it", "Play round and round, back and forth, or just the last few pictures while you work.", "play"),
        ("Pick a speed", "12 frames a second is the classic stop-motion speed. Slower feels dreamy; faster feels busy.", "speed"),
        ("Make the film", "Choose a movie, a GIF, the pictures, or a Blender scene, then Make it. It goes into a films folder next to your project.", "export"),
    ]),
    'BUILD': ("Building a puppet", [
        ("Choose how to start", "Parts kit builds one from clay parts. A sculpt rigs a figure you've sculpted. A rig uses a puppet you already have.", "start_choice"),
        ("Pick a body", "Person, small child, tall, or four legs. It starts as a wire armature, just like a real puppet.", "four_legs"),
        ("Snap on parts", "Click parts on the left: heads, bodies, arms, legs, feet. Each one snaps onto the wire.", "kit_build"),
        ("Colours and sizes", "Click a colour to paint a part. The sliders make the head bigger, the legs longer, and so on. The parts stay joined.", "proportions"),
        ("Hair, hats and extras", "Hair, Hats and Extras (a name tag, a scarf, glasses) sit on whatever head and body are on, and stay on when you change them.", "hats"),
        ("Your own parts", "Model a part in Blender and save it in Library › Kit › Hats (or Heads, Arms…). It shows under Yours with its picture and textures, and is fitted to the puppet when you click it.", "own_parts"),
        ("Next: face & hands", "When you like the shape, move on to faces and hands.", "next_step"),
    ]),
    'JOINTS': ("Rigging a sculpt", [
        ("Bring in your sculpt", "Bring in a one-piece clay figure, or click one that's already on the set.", "bring_in"),
        ("Guess the joints", "Guess them all puts dots where the neck, shoulders, elbows, hips and knees probably are.", "joints"),
        ("Put them right", "Click a joint in the list, then click in the clay where it should bend. Its mirror on the other side moves too.", "joint_fix"),
        ("Make the rig", "Make the rig: rings and foot pins appear, and the clay bends at the joints.", "make_rig"),
    ]),
    'RIG': ("Using your own rig", [
        ("Pick the rig", "Click your rigged puppet in the live view (or Bring it in).", "bring_in"),
        ("Make puppet", "Make puppet finds the head, body, hips, hands and feet, and puts rings on them. Feet get pins so they stay on the floor.", "make_rig"),
        ("Swaps", "Mouths, eyes and hands named like Mouth_Smile or LeftHand_Fist become swap sets automatically.", "swap"),
    ]),
    'FACE': ("Faces and hands", [
        ("Make them", "Make mouths, eyes and hands puts a set of each on the puppet. Only one of each shows at a time.", "face_make"),
        ("Try them on", "Click a mouth or hand to see it. While animating, you pick them picture by picture.", "swap"),
        ("Fingers", "Swap hand shapes (open, fist, point, thumbs up…), or sculpt a hand on one picture and keep it as a new shape.", "hands"),
    ]),
    'TRY': ("Trying it out", [
        ("Test poses", "Try it puts the puppet through a wave, sit, crouch and walk, and takes a picture of each.", "try"),
        ("Fix anything marked", "A marked pose has a fix button (like Soften joints). Fix it, then Try it again.", "try_fix"),
    ]),
    'SAVE': ("Saving your puppet", [
        ("Save it", "Save puts the puppet in your library with its picture, ready for any project.", "save_lib"),
        ("Use it anywhere", "In any project, Bring in… and click it. It comes in with rings, swaps and pins ready to animate.", "bring_in"),
    ]),
    'PROJECTS': ("Projects", [
        ("Save", "Save (or Cmd+S) keeps your film in the Stop Motion folder. Quitting saves too.", "save_project"),
        ("Open or start one", "Projects shows each film with its last picture. Click one to open it, or New project.", "projects"),
    ]),
}
ORDER = ['ANIMATE', 'SET', 'BRING_IN', 'LIGHT', 'SCULPT', 'REVIEW', 'BUILD', 'JOINTS', 'RIG', 'FACE', 'TRY', 'SAVE', 'PROJECTS']
LOOP = 4.0   # seconds per picture loop


class HelpState:
    def __init__(self):
        self.open = False
        self.topic = None        # a topic picked with the arrows; None follows the view
        self.view = None         # the view's topic when last drawn
        self.step = 0
        self.started = 0.0


H = HelpState()


def view_topic(S, P):
    """The guide for what's on screen."""
    if S.overlay == 'LIBRARY':
        return 'BRING_IN'
    if S.overlay == 'PROJECTS':
        return 'PROJECTS'
    if S.mode == 'REVIEW':
        return 'REVIEW'
    if S.mode == 'PUPPETS':
        if P.start == 'RIG':
            return 'RIG'
        return {'BUILD': 'BUILD', 'JOINTS': 'JOINTS', 'FACE': 'FACE', 'TRY': 'TRY', 'SAVE': 'SAVE'}.get(P.step, 'BUILD')
    return {'PUPPET': 'ANIMATE', 'PROPS': 'SET', 'LIGHT': 'LIGHT', 'SCULPT': 'SCULPT'}.get(S.side, 'ANIMATE')


def current(S, P):
    """Which guide shows: following the view resets when the view changes."""
    v = view_topic(S, P)
    if v != H.view:
        H.view = v
        H.topic = None
        H.step = 0
        H.started = time.time()
    return H.topic or v


def toggle():
    H.open = not H.open
    H.started = time.time()
    return H.open


def go_step(i, n):
    H.step = max(0, min(n - 1, i))
    H.started = time.time()


def browse(key, direction):
    i = (ORDER.index(key) + direction) % len(ORDER)
    H.topic = ORDER[i]
    H.step = 0
    H.started = time.time()


def phase(now=None):
    now = time.time() if now is None else now
    return ((now - H.started) % LOOP) / LOOP


def wrap(measure, text, width):
    lines, line = [], ""
    for word in text.split():
        trial = word if not line else line + " " + word
        if measure(trial) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ------------------------------------------------------------------ the panel

def draw(kit, r, S, P, s, actions, now=None):
    """Draw the help column into `r`. `actions` has close(), redraw()."""
    t = Theme
    key = current(S, P)
    title, steps = TOPICS[key]
    n = len(steps)
    H.step = min(H.step, n - 1)
    inner = r.inset(14 * s, 12 * s)

    # header: ? Help · close
    head, rest = inner.take_top(30 * s)
    kit.p.circle(head.x + 13 * s, head.cy, 13 * s, t.blue)
    kit.label(Rect(head.x, head.y, 26 * s, head.h), "?", 15, t.on_accent, "center", True)
    kit.label(Rect(head.x + 34 * s, head.y, head.w - 80 * s, head.h), "How to…", 15, t.text, "left", True)
    kit.button("help:close", Rect(head.right - 30 * s, head.cy - 15 * s, 30 * s, 30 * s), "", actions["close"], icon="x")

    # topic, with arrows to browse the others
    _gap, rest = rest.take_top(8 * s)
    trow, rest = rest.take_top(34 * s)
    kit.button("help:prevtopic", Rect(trow.x, trow.y, 30 * s, trow.h), "", lambda: (browse(key, -1), actions["redraw"]()), icon="prev")
    kit.button("help:nexttopic", Rect(trow.right - 30 * s, trow.y, 30 * s, trow.h), "", lambda: (browse(key, 1), actions["redraw"]()), icon="next")
    kit.label(Rect(trow.x + 34 * s, trow.y, trow.w - 68 * s, trow.h), title, 16, t.text, "center", True)
    if H.topic is not None and H.topic != H.view:
        _g, rest = rest.take_top(2 * s)
        back, rest = rest.take_top(22 * s)
        kit.button("help:here", Rect(back.cx - 80 * s, back.y, 160 * s, back.h), "Back to this view's guide",
                   lambda: (setattr(H, "topic", None), go_step(0, n), actions["redraw"]()), size=11)

    # the picture
    _gap, rest = rest.take_top(10 * s)
    pic, rest = rest.take_top(min(rest.w * 0.7, rest.h * 0.42))
    kit.panel(pic, t.raised, 10, t.line_strong)
    box = pic.inset(4 * s)
    kit.p.clip(box)
    try:
        SCENES.get(steps[H.step][2], scene_blank)(Ill(kit.p, box, s, phase(now)))
    except Exception as exc:   # a picture must never take the Studio down
        print("Stop Motion: help picture failed:", exc)
    kit.p.unclip()
    kit.area("help:pic", pic, on_click=lambda: (go_step(H.step + 1 if H.step + 1 < n else 0, n), actions["redraw"]()))

    # step dots
    _gap, rest = rest.take_top(10 * s)
    drow, rest = rest.take_top(20 * s)
    dot_w = 22 * s
    x0 = drow.cx - dot_w * n / 2
    for i in range(n):
        c = Rect(x0 + i * dot_w, drow.y, dot_w, drow.h)
        done = i < H.step
        kit.p.circle(c.cx, c.cy, (6 if i == H.step else 4.5) * s,
                     t.accent if i == H.step else (t.soft if done else t.line_strong))
        kit.area("help:dot:%d" % i, c, on_click=(lambda k=i: (go_step(k, n), actions["redraw"]())))

    # the step itself
    _gap, rest = rest.take_top(8 * s)
    stitle, text, _scene = steps[H.step]
    srow, rest = rest.take_top(24 * s)
    kit.label(srow, "%d.  %s" % (H.step + 1, stitle), 15, t.text, "left", True)
    measure = lambda line: kit.text_width(line, 13)   # noqa: E731
    for line in wrap(measure, text, rest.w):
        if rest.h < 70 * s:
            break
        lr, rest = rest.take_top(19 * s)
        kit.label(lr, line, 13, t.soft)

    # the other steps, as a list you can jump to
    buttons, rest = rest.take_bottom(40 * s)
    _gap, rest = rest.take_top(12 * s)
    for i, (st, _x, _y) in enumerate(steps):
        if rest.h < 24 * s:
            break
        lr, rest = rest.take_top(24 * s)
        here = i == H.step
        kit.button("help:step:%d" % i, lr, "", (lambda k=i: (go_step(k, n), actions["redraw"]())), "tab", here, size=12)
        kit.label(Rect(lr.x + 8 * s, lr.y, lr.w - 12 * s, lr.h), "%d  %s" % (i + 1, st), 12,
                  t.text if here else t.muted, "left", here)

    a, b = buttons.split_cols(2, 8 * s)
    kit.button("help:back", a, "Back", lambda: (go_step(H.step - 1, n), actions["redraw"]()), enabled=H.step > 0, icon="prev")
    last = H.step == n - 1
    kit.button("help:next", b, "Start again" if last else "Next", lambda: (go_step(0 if last else H.step + 1, n), actions["redraw"]()),
               "accent", icon=None if last else "next")


# ------------------------------------------------------------------ pictures

SKIN = (0.92, 0.71, 0.54, 1)
RED = (0.85, 0.31, 0.18, 1)
BLUE = (0.30, 0.44, 0.66, 1)
DARK = (0.18, 0.12, 0.09, 1)
WALL = (0.80, 0.88, 0.82, 1)
FLOOR = (0.85, 0.73, 0.55, 1)
WOOD = (0.60, 0.40, 0.21, 1)
GREEN = (0.36, 0.60, 0.30, 1)
PINK = (0.96, 0.63, 0.71, 1)
WHITE = (1, 1, 1, 1)
INK = (0.15, 0.15, 0.15, 1)
YELLOW = (0.98, 0.83, 0.30, 1)
RING = (0.49, 0.77, 1.0, 1)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def seg(t, a, b):
    """Progress 0..1 between times a and b of the loop, eased."""
    return ease((t - a) / (b - a)) if b > a else float(t >= a)


def lerp(a, b, f):
    return a + (b - a) * f


def fade(c, a):
    return (c[0], c[1], c[2], c[3] * a)


class Ill:
    """Drawing in a box with 0..1 coordinates (v goes up)."""

    def __init__(self, p, box, s, t):
        self.p, self.box, self.s, self.t = p, box, s, t

    def X(self, u):
        return self.box.x + u * self.box.w

    def Y(self, v):
        return self.box.y + v * self.box.h

    def L(self, u):            # a length, in box heights
        return u * self.box.h

    def stage(self, wall=WALL, floor=FLOOR, horizon=0.32, dim=0.0):
        b = self.box
        self.p.rect(Rect(b.x, self.Y(horizon), b.w, b.h * (1 - horizon)), wall)
        self.p.rect(Rect(b.x, b.y, b.w, b.h * horizon), floor)
        if dim > 0:
            self.p.rect(b, (0.05, 0.06, 0.15, dim))

    def ellipse(self, cx, cy, rx, ry, color, rot=0.0, seg_n=22):
        c, sn = math.cos(rot), math.sin(rot)
        pts = [(cx + rx * math.cos(a) * c - ry * math.sin(a) * sn, cy + rx * math.cos(a) * sn + ry * math.sin(a) * c)
               for a in (2 * math.pi * i / seg_n for i in range(seg_n))]
        self.p.polygon(pts, color)

    def limb(self, x0, y0, x1, y1, w, color):
        self.p.lines([(x0, y0), (x1, y1)], color, w)
        self.p.circle(x0, y0, w / 2, color)
        self.p.circle(x1, y1, w / 2, color)

    def figure(self, u, v, h, arm_l=0.15, arm_r=0.15, crouch=0.0, alpha=1.0, mouth="smile",
               body=RED, legs=BLUE, eyes="open", look=0.0, head_scale=1.0, lean=0.0):
        """A little clay puppet standing at (u, v), h box-heights tall. Arm angles are
        radians out from hanging down."""
        k = self.L(h)
        x, y = self.X(u), self.Y(v)
        a = alpha
        hip_y = y + k * (0.45 - 0.12 * crouch)
        knee_out = k * 0.08 * crouch
        w = k * 0.1
        for side in (-1, 1):
            hx = x + side * k * 0.07
            fx = x + side * k * 0.09
            ky = (hip_y + y) / 2
            self.limb(hx, hip_y, hx + side * knee_out, ky, w, fade(legs, a))
            self.limb(hx + side * knee_out, ky, fx, y + w * 0.4, w, fade(legs, a))
            self.ellipse(fx + side * k * 0.03, y + w * 0.3, k * 0.08, k * 0.04, fade(DARK, a))
        bx = x + lean * k * 0.1
        by = hip_y + k * 0.17
        self.ellipse(bx, by, k * 0.16, k * 0.21, fade(body, a))
        for side, ang in ((-1, arm_l), (1, arm_r)):
            sx, sy = bx + side * k * 0.13, by + k * 0.13
            ex = sx + side * math.sin(ang) * k * 0.32
            ey = sy - math.cos(ang) * k * 0.32
            self.limb(sx, sy, ex, ey, w * 0.95, fade(body, a))
            self.p.circle(ex, ey, k * 0.055, fade(SKIN, a))
        hr = k * 0.13 * head_scale
        hx, hy = bx, by + k * 0.21 + hr * 0.9
        self.p.circle(hx, hy, hr, fade(SKIN, a))
        self.face(hx + look * hr * 0.3, hy, hr, mouth, eyes, a)
        return {"hand_l": None}

    def hand_pos(self, u, v, h, arm, side=1, crouch=0.0, lean=0.0):
        k = self.L(h)
        x, y = self.X(u), self.Y(v)
        hip_y = y + k * (0.45 - 0.12 * crouch)
        bx, by = x + lean * k * 0.1, hip_y + k * 0.17
        sx, sy = bx + side * k * 0.13, by + k * 0.13
        return sx + side * math.sin(arm) * k * 0.32, sy - math.cos(arm) * k * 0.32

    def face(self, cx, cy, r, mouth="smile", eyes="open", a=1.0):
        er = r * 0.2
        for side in (-1, 1):
            ex, ey = cx + side * r * 0.36, cy + r * 0.18
            if eyes == "shut":
                self.p.lines([(ex - er, ey), (ex + er, ey)], fade(DARK, a), max(1.0, r * 0.08))
            else:
                self.p.circle(ex, ey, er, fade(WHITE, a))
                self.p.circle(ex + er * 0.2, ey - er * 0.1, er * 0.5, fade(DARK, a))
        my = cy - r * 0.38
        dk = fade((0.36, 0.12, 0.08, 1), a)
        if mouth == "o":
            self.ellipse(cx, my, r * 0.14, r * 0.2, dk)
        elif mouth == "aah":
            self.ellipse(cx, my, r * 0.3, r * 0.17, dk)
        elif mouth == "line":
            self.p.lines([(cx - r * 0.25, my), (cx + r * 0.25, my)], dk, max(1.0, r * 0.1))
        else:
            pts = [(cx + r * 0.32 * math.cos(ang), my + r * 0.12 + r * 0.25 * math.sin(ang))
                   for ang in (math.pi * (1.15 + 0.7 * i / 8) for i in range(9))]
            self.p.lines(pts, dk, max(1.0, r * 0.1))

    def ring(self, x, y, r, color=RING, active=False):
        self.p.ring(x, y, r, color, (3 if active else 2) * self.s)

    def cursor(self, x, y, press=0.0):
        s = self.s
        if press > 0:
            self.p.ring(x, y, (6 + 14 * press) * s, fade(INK, 1 - press), 2 * s)
        pts = [(x, y), (x + 1 * s, y - 19 * s), (x + 14 * s, y - 13 * s)]
        self.p.polygon(pts, WHITE)
        self.p.lines(pts, INK, 1.5 * s, closed=True)

    def button(self, u, v, w, h, label, color=None, text=WHITE, pressed=False, size=11):
        color = color or Theme.accent
        r = Rect(self.X(u) - self.box.w * w / 2, self.Y(v) - self.box.h * h / 2, self.box.w * w, self.box.h * h)
        if pressed:
            r = Rect(r.x + 1.5 * self.s, r.y - 1.5 * self.s, r.w, r.h)
        self.p.rect(r, color, 6 * self.s)
        self.p.rect_outline(r, INK[:3] + (0.5,), 6 * self.s, 1.2 * self.s)
        self.p.text(r, label, size * self.s, text, "center", True)
        return r

    def label(self, u, v, text, size=11, color=None, align="center", bold=False, w=0.9):
        color = color or INK
        self.p.text(Rect(self.X(u) - self.box.w * w / 2, self.Y(v) - 9 * self.s, self.box.w * w, 18 * self.s),
                    text, size * self.s, color, align, bold)

    def strip(self, n, v=0.06, h=0.18, shown=None, widths=None, cut_at=None, play=None, sel=None, count=None):
        """The shot strip: n cards along the bottom."""
        b = self.box
        self.p.rect(Rect(b.x, b.y, b.w, self.L(v + h + 0.04)), (0.97, 0.96, 0.93, 0.92))
        x = self.X(0.04)
        cw = b.w * 0.13
        rects = []
        for i in range(n):
            w = cw * (widths[i] if widths else 1)
            r = Rect(x, self.Y(v), w - 3 * self.s, self.L(h))
            show = shown[i] if shown else 1.0
            if show > 0:
                rr = Rect(r.x, r.y - (1 - show) * self.L(0.2), r.w, r.h)
                self.p.rect(rr, fade(WALL, show))
                self.p.rect(Rect(rr.x, rr.y, rr.w, rr.h * 0.35), fade(FLOOR, show))
                self.p.circle(rr.cx, rr.y + rr.h * 0.55, rr.h * 0.2, fade(RED, show))
                self.p.circle(rr.cx, rr.y + rr.h * 0.82, rr.h * 0.12, fade(SKIN, show))
                self.p.rect_outline(rr, fade(INK if sel != i else Theme.blue, show), 0, (2.5 if sel == i else 1) * self.s)
                if cut_at and i in cut_at:
                    self.p.rect(Rect(rr.x - 3 * self.s, rr.y, 3 * self.s, rr.h), YELLOW)
            rects.append(r)
            x += w
        if play is not None and rects:
            px = lerp(rects[0].x, rects[-1].right, play)
            self.p.rect(Rect(px - 1 * self.s, self.Y(v - 0.02), 2.5 * self.s, self.L(h + 0.04)), Theme.accent)
        return rects

    def table(self, u, v, w=0.3, h=0.2):
        x0, x1 = self.X(u - w / 2), self.X(u + w / 2)
        top = self.Y(v + h)
        self.p.rect(Rect(x0, top - self.L(0.03), x1 - x0, self.L(0.03)), WOOD, 2 * self.s)
        for lx in (x0 + self.L(0.02), x1 - self.L(0.04)):
            self.p.rect(Rect(lx, self.Y(v), self.L(0.02), top - self.L(0.03) - self.Y(v)), (0.48, 0.30, 0.15, 1))
        return top

    def mug(self, x, y, size, alpha=1.0, rot=0.0):
        s = self.L(size)
        self.p.rect(Rect(x - s / 2, y, s, s * 1.1), fade(WHITE, alpha), 3 * self.s)
        self.p.rect_outline(Rect(x - s / 2, y, s, s * 1.1), fade((0.6, 0.6, 0.6, 1), alpha), 3 * self.s, 1 * self.s)
        self.p.ring(x + s * 0.62, y + s * 0.55, s * 0.24, fade((0.6, 0.6, 0.6, 1), alpha), 2 * self.s)

    def flower(self, x, y, size, color=PINK, alpha=1.0):
        s = self.L(size)
        self.p.lines([(x, y), (x, y + s)], fade(GREEN, alpha), max(1.5, s * 0.12))
        for i in range(5):
            a = 2 * math.pi * i / 5
            self.p.circle(x + math.cos(a) * s * 0.28, y + s + math.sin(a) * s * 0.28, s * 0.22, fade(color, alpha))
        self.p.circle(x, y + s, s * 0.16, fade(YELLOW, alpha))

    def bush(self, u, v, w=0.36):
        for du, dv, r in ((-0.1, 0.06, 0.1), (0.1, 0.07, 0.11), (0.0, 0.13, 0.12), (-0.02, 0.05, 0.11)):
            self.p.circle(self.X(u + du * w / 0.36), self.Y(v + dv), self.L(r), (0.30 + r, 0.55 + r * 0.6, 0.27, 1))

    def card(self, u, v, w, h, color=WHITE, border=INK, radius=6):
        r = Rect(self.X(u) - self.box.w * w / 2, self.Y(v) - self.box.h * h / 2, self.box.w * w, self.box.h * h)
        self.p.rect(r, color, radius * self.s)
        self.p.rect_outline(r, border, radius * self.s, 1.2 * self.s)
        return r

    def camera(self, x, y, size, color=INK, label=""):
        s = self.L(size)
        self.p.rect(Rect(x - s, y - s * 0.6, s * 1.5, s * 1.2), color, 3 * self.s)
        self.p.polygon([(x + s * 0.5, y), (x + s * 1.1, y + s * 0.5), (x + s * 1.1, y - s * 0.5)], color)
        if label:
            self.p.text(Rect(x - s, y - s * 0.6, s * 1.5, s * 1.2), label, max(8, s * 0.9), WHITE, "center", True)

    def lamp(self, x, y, size, on=1.0):
        s = self.L(size)
        if on > 0:
            self.p.polygon([(x, y), (x - s * 2.2, y - s * 4), (x + s * 2.2, y - s * 4)], (1, 0.95, 0.7, 0.22 * on))
        self.p.circle(x, y, s * 0.6, lerp_c((0.5, 0.5, 0.5, 1), YELLOW, on))
        self.p.lines([(x, y + s * 0.6), (x, self.box.top)], INK, 1.5 * self.s)


def lerp_c(a, b, f):
    return tuple(lerp(a[i], b[i], f) for i in range(4))


# each picture: one loop of LOOP seconds, t from 0 to 1

def scene_blank(d):
    d.stage()


def scene_drag_ring(d):
    t = d.t
    lift = seg(t, 0.25, 0.7) - seg(t, 0.85, 1.0)
    arm = lerp(0.15, 2.4, lift)
    d.stage()
    d.figure(0.5, 0.18, 0.62, arm_r=arm)
    hx, hy = d.hand_pos(0.5, 0.18, 0.62, arm)
    d.ring(hx, hy, d.L(0.07), active=0.25 < t < 0.85)
    start = (d.X(0.85), d.Y(0.2))
    reach = seg(t, 0.0, 0.25)
    cx = lerp(start[0], hx, reach) if t < 0.25 else hx
    cy = lerp(start[1], hy, reach) if t < 0.25 else hy
    if t > 0.85:
        back = seg(t, 0.85, 1.0)
        cx, cy = lerp(hx, start[0], back), lerp(hy, start[1], back)
    d.cursor(cx + 4 * d.s, cy - 4 * d.s, press=seg(t, 0.22, 0.32) if t < 0.4 else 0)
    d.label(0.5, 0.93, "drag the ring", 11, INK, bold=True)


def scene_shoot(d):
    t = d.t
    d.stage()
    d.figure(0.4, 0.36, 0.5, arm_r=1.2, arm_l=0.3)
    press = 0.3 < t < 0.42
    flash = 1 - seg(t, 0.36, 0.55) if t > 0.34 else 0
    if flash > 0:
        d.p.rect(d.box, (1, 1, 1, 0.75 * flash))
    shown = [1, 1, seg(t, 0.45, 0.75)]
    d.strip(3, v=0.03, h=0.15, shown=shown)
    b = d.button(0.8, 0.36, 0.28, 0.13, "Shoot", pressed=press)
    d.cursor(b.cx + 4 * d.s, b.cy - 2 * d.s, press=seg(t, 0.3, 0.5) if t < 0.55 else 0)
    d.label(0.5, 0.93, "Shoot, or Enter", 11, INK, bold=True)


def scene_ghost(d):
    t = d.t
    d.stage()
    d.figure(0.5, 0.18, 0.62, arm_r=0.9, alpha=0.28)
    move = seg(t, 0.2, 0.7)
    d.figure(0.5, 0.18, 0.62, arm_r=lerp(0.9, 1.25, move))
    d.label(0.22, 0.86, "ghost", 11, (0.3, 0.3, 0.3, 1), bold=True, w=0.3)
    d.p.lines([(d.X(0.25), d.Y(0.8)), (d.X(0.36), d.Y(0.66))], (0.3, 0.3, 0.3, 1), 1.5 * d.s)
    d.label(0.5, 0.93, "a tiny move from the ghost", 11, INK, bold=True)


def scene_repeat(d):
    t = d.t
    n = 6
    i = min(n - 1, int(t * n))
    f = (t * n) % 1
    d.stage()
    u = 0.25 + 0.08 * i
    swing = math.sin(i * 1.1) * 0.5
    d.figure(u, 0.3, 0.5, arm_l=0.3 - swing, arm_r=0.3 + swing, lean=0.4)
    if f < 0.15:
        d.p.rect(d.box, (1, 1, 1, 0.5 * (1 - f / 0.15)))
    d.strip(n, v=0.03, h=0.15, shown=[1 if k < i else (seg(f, 0.0, 0.4) if k == i else 0) for k in range(n)])
    d.label(0.5, 0.93, "pose, shoot, pose, shoot…", 11, INK, bold=True)


def scene_swap(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    mouths = ["smile", "o", "aah", "line"]
    i = min(3, int(t * 4))
    d.p.circle(d.X(0.33), d.Y(0.5), d.L(0.33), SKIN)
    d.face(d.X(0.33), d.Y(0.5), d.L(0.33), mouths[i], "open")
    for k, m in enumerate(mouths):
        r = d.card(0.78, 0.8 - k * 0.2, 0.26, 0.16, color=(Theme.yellow if k == i else WHITE))
        d.face(r.cx, r.cy + r.h * 0.15, r.h * 0.45, m, "open")
    sel = d.Y(0.8 - i * 0.2)
    d.cursor(d.X(0.84), sel - 4 * d.s, press=((t * 4) % 1) * 2 if ((t * 4) % 1) < 0.5 else 0)


def scene_hold(d):
    t = d.t
    d.stage()
    d.figure(0.5, 0.4, 0.45, arm_r=1.4)
    grow = seg(t, 0.25, 0.7) * (1 - seg(t, 0.9, 1.0))
    widths = [1, 1, 1 + 1.4 * grow, 1]
    rects = d.strip(4, v=0.05, h=0.22, widths=widths)
    r = rects[2]
    d.p.rect(Rect(r.right - 4 * d.s, r.y, 4 * d.s, r.h), Theme.blue)
    d.p.text(Rect(r.x, r.top - 16 * d.s, r.w - 4 * d.s, 14 * d.s), "%df" % (2 + round(2 * grow)), 9 * d.s, INK, "right", True)
    d.cursor(r.right, r.cy, press=seg(t, 0.15, 0.3) if t < 0.35 else 0)
    d.label(0.5, 0.93, "drag a card's edge", 11, INK, bold=True)


def scene_pose_over(d):
    t = d.t
    d.stage()
    picked = t > 0.2
    redo = seg(t, 0.45, 0.7)
    d.figure(0.5, 0.36, 0.5, arm_r=0.6, alpha=0.3 if picked else 1)
    if picked:
        d.figure(0.5, 0.36, 0.5, arm_r=lerp(0.6, 1.6, redo))
        d.p.rect(Rect(d.X(0.04), d.Y(0.86), d.box.w * 0.42, d.L(0.1)), Theme.blue, 5 * d.s)
        d.label(0.25, 0.91, "POSING OVER 2", 9, WHITE, bold=True, w=0.42)
    rects = d.strip(5, v=0.03, h=0.15, sel=1 if picked else None)
    r = rects[1]
    d.cursor(r.cx, r.cy, press=seg(t, 0.15, 0.3) if t < 0.35 else 0)
    if t > 0.75:
        d.p.rect(d.box, (1, 1, 1, 0.6 * (1 - seg(t, 0.75, 0.9))))


def scene_play(d):
    t = d.t
    n = 6
    i = min(n - 1, int(t * n))
    d.stage()
    swing = math.sin(i * 1.1) * 0.6
    d.figure(0.3 + 0.07 * i, 0.32, 0.48, arm_l=0.3 - swing, arm_r=0.3 + swing, lean=0.4)
    d.strip(n, v=0.03, h=0.15, play=t)
    d.p.icon("play", Rect(d.X(0.06), d.Y(0.84), d.L(0.09), d.L(0.09)), Theme.accent)
    d.label(0.5, 0.93, "Space plays", 11, INK, bold=True)


def scene_speed(d):
    t = d.t
    d.stage()
    for k, (fps, v) in enumerate(((8, 0.7), (12, 0.45), (24, 0.2))):
        i = int(t * fps * 0.6) % 5
        d.figure(0.2 + 0.12 * i, v, 0.2, arm_l=0.3 + 0.3 * (i % 2), arm_r=0.9 - 0.3 * (i % 2), lean=0.4)
        d.label(0.85, v + 0.08, "%d fps" % fps, 11, Theme.accent if fps == 12 else INK, bold=True, w=0.3)


def scene_bring_in(d):
    t = d.t
    d.stage()
    top = d.table(0.62, 0.12, 0.34, 0.24)
    fall = seg(t, 0.45, 0.75)
    d.mug(d.X(0.6), lerp(d.Y(1.05), top, fall), 0.09)
    if t < 0.5:
        panel = d.card(0.33, 0.6, 0.5, 0.62, color=(0.98, 0.97, 0.94, 1))
        for k, (name, c) in enumerate((("Mug", WHITE), ("Pip", RED), ("Bush", GREEN), ("Table", WOOD))):
            cu, cv = 0.2 + (k % 2) * 0.26, 0.72 - (k // 2) * 0.26
            r = d.card(cu, cv, 0.2, 0.2, color=(Theme.yellow if k == 0 and t > 0.25 else (0.93, 0.91, 0.86, 1)))
            d.p.circle(r.cx, r.cy + 3 * d.s, r.h * 0.22, c)
            d.p.text(Rect(r.x, r.y, r.w, 12 * d.s), name, 8 * d.s, INK, "center")
        d.cursor(d.X(0.22), d.Y(0.7), press=seg(t, 0.22, 0.4) if t < 0.45 else 0)
    d.label(0.5, 0.93, "Bring in…", 11, INK, bold=True)


def scene_library(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    things = (("Pip", RED), ("Biscuit", WOOD), ("Mug", WHITE), ("Bush", GREEN), ("Table", WOOD), ("Flower", PINK))
    for k, (name, c) in enumerate(things):
        pop = seg(t, k * 0.08, k * 0.08 + 0.2)
        cu, cv = 0.2 + (k % 3) * 0.3, 0.68 - (k // 3) * 0.4
        r = d.card(cu, cv, 0.25 * pop + 0.001, 0.32 * pop + 0.001)
        if pop > 0.5:
            d.p.circle(r.cx, r.cy + 4 * d.s, r.h * 0.25, c)
            d.p.text(Rect(r.x, r.y + 2 * d.s, r.w, 12 * d.s), name, 8 * d.s, INK, "center")


def scene_save_lib(d):
    t = d.t
    d.stage()
    go = seg(t, 0.3, 0.75)
    u, v = lerp(0.35, 0.78, go), lerp(0.25, 0.42, go)
    box = d.card(0.78, 0.35, 0.3, 0.26, color=(0.93, 0.85, 0.7, 1))
    d.p.text(Rect(box.x, box.y + 4 * d.s, box.w, 14 * d.s), "Library", 9 * d.s, INK, "center", True)
    if go < 0.98:
        d.figure(u, v, lerp(0.55, 0.12, go), arm_r=1.0)
    b = d.button(0.3, 0.86, 0.36, 0.13, "Save" if t < 0.6 else "Saved ✓", pressed=0.15 < t < 0.3,
                 color=Theme.accent if t < 0.6 else (0.23, 0.56, 0.31, 1))
    if t < 0.3:
        d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.1, 0.3))


def scene_arrange(d):
    t = d.t
    d.stage()
    top = d.table(0.42, 0.12, 0.4, 0.26)
    # slide along the table top, off the edge, down to the floor
    if t < 0.5:
        x = lerp(d.X(0.28), d.X(0.6), seg(t, 0.05, 0.5))
        y = top
    else:
        x = lerp(d.X(0.6), d.X(0.82), seg(t, 0.5, 0.75))
        y = lerp(top, d.Y(0.12), seg(t, 0.55, 0.75))
    d.mug(x, y, 0.09)
    d.cursor(x + d.L(0.03), y + d.L(0.06), press=seg(t, 0.0, 0.1) if t < 0.12 else 0)
    d.label(0.5, 0.93, "slides along, sits on top", 11, INK, bold=True)


def scene_stamp(d):
    t = d.t
    d.stage()
    d.bush(0.5, 0.15)
    spots = ((0.38, 0.38), (0.5, 0.48), (0.62, 0.36), (0.45, 0.28), (0.58, 0.26), (0.68, 0.24))
    for k, (u, v) in enumerate(spots):
        at = 0.1 + k * 0.12
        pop = seg(t, at, at + 0.08)
        if pop > 0:
            d.flower(d.X(u), d.Y(v), 0.07 * pop * (1 + 0.15 * (k % 2)), color=PINK if k % 2 else (0.98, 0.9, 0.95, 1))
    k = min(5, max(0, int((t - 0.1) / 0.12)))
    u, v = spots[k]
    d.cursor(d.X(u) + 3 * d.s, d.Y(v) + d.L(0.06), press=((t - 0.1) / 0.12) % 1 if t > 0.1 else 0)
    d.label(0.5, 0.93, "Stamp copies", 11, INK, bold=True)


def scene_set_piece(d):
    t = d.t
    d.stage()
    shift = seg(t, 0.25, 0.6) * 0.3
    d.table(0.3 + shift, 0.36, 0.34, 0.2)
    d.p.icon("pin", Rect(d.X(0.3 + shift) - d.L(0.03), d.Y(0.66), d.L(0.06), d.L(0.06)), Theme.accent)
    rects = d.strip(5, v=0.03, h=0.17)
    for r in rects:
        tx = r.x + r.w * (0.1 + shift)
        d.p.rect(Rect(tx, r.y + r.h * 0.3, r.w * 0.45, 2 * d.s), WOOD)
    d.label(0.5, 0.93, "moves in every picture", 11, INK, bold=True)


def scene_hold_prop(d):
    t = d.t
    d.stage()
    top = d.table(0.75, 0.12, 0.3, 0.24)
    raise_ = seg(t, 0.3, 0.6) - seg(t, 0.75, 0.9)
    arm = lerp(0.9, 1.8, raise_)
    d.figure(0.42, 0.12, 0.6, arm_r=arm)
    hx, hy = d.hand_pos(0.42, 0.12, 0.6, arm)
    if t < 0.85:
        d.mug(hx + d.L(0.02), hy - d.L(0.03), 0.07)
    else:
        d.mug(hx + d.L(0.02), lerp(hy - d.L(0.03), top, seg(t, 0.85, 0.95)), 0.07)
    d.label(0.5, 0.93, "Hold in hand · Drop", 11, INK, bold=True)


def scene_cameras(d):
    t = d.t
    d.stage()
    d.figure(0.5, 0.36, 0.45, arm_r=1.0)
    use_b = 0.5 < t
    d.camera(d.X(0.12), d.Y(0.75), 0.06, Theme.accent if not use_b else INK, "A")
    d.camera(d.X(0.84), d.Y(0.75), 0.06, Theme.accent if use_b else INK, "B")
    n_shot = min(5, int(t * 6))
    d.strip(5, v=0.03, h=0.15, shown=[1 if k <= n_shot else 0 for k in range(5)], cut_at={3} if n_shot >= 3 else None)
    d.label(0.5, 0.93, "pick a camera to cut", 11, INK, bold=True)


def scene_light_preset(d):
    t = d.t
    i = min(2, int(t * 3))
    looks = ((WALL, FLOOR, 0.0, "Three-point"), ((0.98, 0.85, 0.65, 1), (0.9, 0.7, 0.45, 1), 0.0, "Golden hour"),
             ((0.35, 0.42, 0.6, 1), (0.3, 0.32, 0.45, 1), 0.25, "Moonlight"))
    wall, floor, dim, name = looks[i]
    d.stage(wall=wall, floor=floor, dim=dim)
    d.figure(0.5, 0.2, 0.55, arm_r=0.4)
    for k, (_w, _f, _d, nm) in enumerate(looks):
        d.button(0.18 + k * 0.32, 0.9, 0.3, 0.11, nm, color=Theme.yellow if k == i else WHITE, text=INK, size=9)


def scene_light(d):
    t = d.t
    lamp = 1 - seg(t, 0.2, 0.6) * 0.8
    d.stage(dim=0.45 * (1 - lamp))
    d.lamp(d.X(0.3), d.Y(0.82), 0.04, lamp)
    d.figure(0.55, 0.3, 0.48, arm_r=0.4)
    tr = Rect(d.X(0.55), d.Y(0.86), d.box.w * 0.38, 4 * d.s)
    d.p.rect(tr, (0.8, 0.8, 0.8, 1), 2 * d.s)
    d.p.circle(tr.x + tr.w * lamp, tr.cy, 6 * d.s, WHITE)
    d.p.ring(tr.x + tr.w * lamp, tr.cy, 6 * d.s, INK, 1.5 * d.s)
    d.strip(5, v=0.03, h=0.15, sel=2)
    if t > 0.65:
        d.button(0.5, 0.65, 0.5, 0.12, "From here on", color=Theme.yellow, text=INK, size=10)


def scene_light_effect(d):
    t = d.t
    i = min(4, int(t * 5))
    flash = (i == 2) and ((t * 5) % 1) < 0.5
    d.stage(dim=[0.0, 0.0, 0.0, 0.25, 0.5][i])
    d.figure(0.5, 0.3, 0.48, arm_l=0.3, arm_r=0.3, eyes="shut" if flash else "open", mouth="o" if i >= 2 else "smile")
    if flash:
        d.p.rect(d.box, (1, 1, 1, 0.7))
    d.strip(5, v=0.03, h=0.15, sel=i)
    d.label(0.5, 0.93, ["", "", "Flash!", "Fade to night…", "…dark"][i], 11, INK if i < 3 else WHITE, bold=True)


def scene_sculpt_pick(d):
    t = d.t
    d.stage()
    d.figure(0.5, 0.18, 0.62, arm_r=0.3)
    hx, hy = d.X(0.5), d.Y(0.18) + d.L(0.62) * 0.92
    if t > 0.35:
        d.p.ring(hx, hy, d.L(0.62) * 0.15, Theme.accent, 2 * d.s)
    d.cursor(hx + d.L(0.03), hy, press=seg(t, 0.25, 0.4) if t < 0.45 else 0)
    if t > 0.55:
        d.button(0.78, 0.15, 0.36, 0.13, "Sculpt here", pressed=0.75 < t < 0.85)


def scene_sculpt(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    cx, cy, r = d.X(0.45), d.Y(0.48), d.L(0.32)
    bulge = seg(t, 0.15, 0.7)
    shade = (0.80, 0.58, 0.42, 1)
    br = r * 0.5 * bulge
    if br > 1:
        d.ellipse(cx + r * 0.78, cy - r * 0.2, br * 1.08, br * 0.98, shade)
    d.p.circle(cx, cy, r, SKIN)
    if br > 1:
        d.ellipse(cx + r * 0.76, cy - r * 0.2, br, br * 0.9, SKIN)
    d.face(cx, cy, r, "smile", "open")
    bx = cx + r * (0.85 + 0.35 * bulge) + r * 0.06 * math.sin(t * 20)
    by = cy - r * 0.2
    d.p.ring(bx, by, d.L(0.08), Theme.accent, 2 * d.s)
    for k, nm in enumerate(("Push", "Pull", "Smooth")):
        d.button(0.88, 0.8 - k * 0.17, 0.2, 0.12, nm, color=Theme.yellow if k == 0 else WHITE, text=INK, size=9)


def scene_keep_shape(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    # a hand shape becomes a new swap
    hand = d.card(0.3, 0.55, 0.3, 0.4, color=(0.99, 0.97, 0.94, 1))
    d.p.circle(hand.cx, hand.cy, hand.h * 0.22, SKIN)
    for k in range(4):
        d.limb(hand.cx - hand.h * 0.12 + k * hand.h * 0.08, hand.cy + hand.h * 0.15, hand.cx - hand.h * 0.14 + k * hand.h * 0.09,
               hand.cy + hand.h * (0.32 - 0.1 * seg(t, 0.1, 0.3)), hand.h * 0.07, SKIN)
    b = d.button(0.3, 0.17, 0.36, 0.13, "Keep shape", pressed=0.32 < t < 0.42)
    d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.32, 0.5) if t < 0.5 else 0)
    go = seg(t, 0.5, 0.8)
    for k, nm in enumerate(("Open", "Fist", "Shape 1")):
        show = 1 if k < 2 else go
        if show > 0:
            r = d.card(0.78, 0.78 - k * 0.24, 0.3, 0.18, color=fade(Theme.yellow if k == 2 else WHITE, show), border=fade(INK, show))
            d.p.text(r, nm, 9 * d.s, fade(INK, show), "center", k == 2)


def scene_export(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    film = d.card(0.22, 0.55, 0.3, 0.42, color=(0.25, 0.25, 0.25, 1))
    d.p.circle(film.cx, film.cy, film.h * 0.2, RED)
    b = d.button(0.22, 0.17, 0.3, 0.13, "Make it!", pressed=0.15 < t < 0.25)
    d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.15, 0.35) if t < 0.35 else 0)
    for k, nm in enumerate(("Movie", "GIF", "Pictures", "Blender")):
        at = 0.3 + k * 0.12
        pop = seg(t, at, at + 0.12)
        if pop <= 0:
            continue
        u = lerp(0.3, 0.75, pop)
        r = d.card(u, 0.8 - k * 0.2, 0.3, 0.15, color=fade(WHITE, pop), border=fade(INK, pop))
        d.p.text(r, nm, 9 * d.s, fade(INK, pop), "center", True)


def scene_start_choice(d):
    t = d.t
    i = min(2, int(t * 3))
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    for k, nm in enumerate(("Parts kit", "A sculpt", "A rig")):
        r = d.card(0.18 + k * 0.32, 0.86, 0.3, 0.13, color=Theme.yellow if k == i else WHITE)
        d.p.text(r, nm, 9 * d.s, INK, "center", True)
    if i == 0:
        _wire(d, 0.5, 0.12, 0.6)
        d.figure(0.5, 0.12, 0.6, arm_r=0.3, alpha=seg((t * 3) % 1, 0.2, 0.8))
    elif i == 1:
        d.ellipse(d.X(0.5), d.Y(0.45), d.L(0.14), d.L(0.22), (0.82, 0.62, 0.5, 1))
        d.p.circle(d.X(0.5), d.Y(0.72), d.L(0.09), (0.82, 0.62, 0.5, 1))
    else:
        d.figure(0.5, 0.12, 0.6, arm_r=0.3)
        for (u, v) in ((0.5, 0.65), (0.5, 0.42), (0.44, 0.15), (0.56, 0.15)):
            d.ring(d.X(u), d.Y(v), d.L(0.05))


def _wire(d, u, v, h, upto=1.0):
    k = d.L(h)
    x, y = d.X(u), d.Y(v)
    ink = (0.35, 0.35, 0.35, 1)
    pts = [((x, y + k * 0.45), (x, y + k * 0.82)),               # spine
           ((x - k * 0.13, y + k * 0.75), (x + k * 0.13, y + k * 0.75)),
           ((x - k * 0.13, y + k * 0.75), (x - k * 0.18, y + k * 0.45)),
           ((x + k * 0.13, y + k * 0.75), (x + k * 0.18, y + k * 0.45)),
           ((x - k * 0.07, y + k * 0.45), (x - k * 0.09, y)),
           ((x + k * 0.07, y + k * 0.45), (x + k * 0.09, y)),
           ((x - k * 0.07, y + k * 0.45), (x + k * 0.07, y + k * 0.45))]
    for (a, b) in pts:
        d.p.lines([a, b], ink, 2 * d.s)
    for (a, b) in pts:
        d.p.circle(a[0], a[1], 2.5 * d.s, ink)


def scene_four_legs(d):
    t = d.t
    i = min(3, int(t * 4))
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    names = ("Small child", "Person", "Tall", "Four legs")
    for k, nm in enumerate(names):
        r = d.card(0.13 + k * 0.245, 0.9, 0.23, 0.11, color=Theme.yellow if k == i else WHITE)
        d.p.text(r, nm, 8 * d.s, INK, "center", True)
    if i < 3:
        _wire(d, 0.5, 0.1, (0.45, 0.6, 0.72)[i])
    else:
        k = d.L(0.3)
        x, y = d.X(0.5), d.Y(0.1)
        ink = (0.35, 0.35, 0.35, 1)
        d.p.lines([(x - k, y + k * 0.7), (x + k * 0.8, y + k * 0.7)], ink, 2 * d.s)
        for lx in (x - k * 0.9, x - k * 0.6, x + k * 0.5, x + k * 0.75):
            d.p.lines([(lx, y + k * 0.7), (lx, y)], ink, 2 * d.s)
        d.p.lines([(x - k, y + k * 0.7), (x - k * 1.25, y + k * 1.05)], ink, 2 * d.s)
        d.p.lines([(x + k * 0.8, y + k * 0.7), (x + k * 1.1, y + k * 1.1)], ink, 2 * d.s)


def scene_kit_build(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    _wire(d, 0.5, 0.1, 0.72)
    k = d.L(0.72)
    x, y = d.X(0.5), d.Y(0.1)
    legs = seg(t, 0.05, 0.25)
    body = seg(t, 0.25, 0.45)
    arms = seg(t, 0.45, 0.65)
    head = seg(t, 0.65, 0.85)
    w = k * 0.1
    if legs > 0:
        drop = (1 - legs) * k * 0.3
        for side in (-1, 1):
            d.limb(x + side * k * 0.07, y + k * 0.45 + drop, x + side * k * 0.09, y + w * 0.4 + drop, w, fade(BLUE, legs))
    if body > 0:
        d.ellipse(x, y + k * 0.62 + (1 - body) * k * 0.3, k * 0.16, k * 0.21, fade(RED, body))
    if arms > 0:
        for side in (-1, 1):
            d.limb(x + side * k * 0.13, y + k * 0.75 + (1 - arms) * k * 0.2, x + side * k * 0.18, y + k * 0.45 + (1 - arms) * k * 0.2, w, fade(RED, arms))
    if head > 0:
        hy = y + k * 0.96 + (1 - head) * k * 0.3
        d.p.circle(x, hy, k * 0.13, fade(SKIN, head))
        if head > 0.9:
            d.face(x, hy, k * 0.13)
    d.label(0.5, 0.93, "click a part: it snaps on", 11, INK, bold=True)


def scene_proportions(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    big = seg(t, 0.15, 0.55) * (1 - seg(t, 0.85, 1.0))
    colour = RED if t < 0.6 else (0.3, 0.6, 0.3, 1)
    d.figure(0.38, 0.1, 0.62, arm_r=0.3, head_scale=1 + 0.45 * big, body=colour)
    tr = Rect(d.X(0.68), d.Y(0.7), d.box.w * 0.26, 4 * d.s)
    d.p.text(Rect(tr.x, tr.y + 8 * d.s, tr.w, 14 * d.s), "head", 9 * d.s, INK, "left", True)
    d.p.rect(tr, (0.8, 0.8, 0.8, 1), 2 * d.s)
    d.p.circle(tr.x + tr.w * (0.4 + 0.5 * big), tr.cy, 6 * d.s, WHITE)
    d.p.ring(tr.x + tr.w * (0.4 + 0.5 * big), tr.cy, 6 * d.s, INK, 1.5 * d.s)
    for k, c in enumerate((RED, (0.3, 0.6, 0.3, 1), BLUE, YELLOW)):
        cx, cy = d.X(0.7 + k * 0.07), d.Y(0.42)
        d.p.circle(cx, cy, d.L(0.035), c)
        if (k == 1 and t >= 0.6) or (k == 0 and t < 0.6):
            d.p.ring(cx, cy, d.L(0.045), INK, 2 * d.s)
    if 0.5 < t < 0.65:
        d.cursor(d.X(0.77), d.Y(0.42), press=seg(t, 0.5, 0.65))


def scene_next_step(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    d.figure(0.3, 0.12, 0.62, arm_r=1.2 + 0.4 * math.sin(t * 2 * math.pi))
    b = d.button(0.72, 0.2, 0.46, 0.14, "Next: face & hands", pressed=0.5 < t < 0.6, size=9)
    d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.5, 0.7) if 0.4 < t < 0.75 else 0)


def scene_face_make(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    cx, cy, r = d.X(0.3), d.Y(0.5), d.L(0.3)
    d.p.circle(cx, cy, r, SKIN)
    if t > 0.75:
        d.face(cx, cy, r, "o")
    for k, m in enumerate(("smile", "o", "aah", "line")):
        pop = seg(t, 0.1 + k * 0.1, 0.25 + k * 0.1)
        if pop > 0:
            rr = d.card(0.7 + (k % 2) * 0.18, 0.66 - (k // 2) * 0.3, 0.16 * pop + 0.001, 0.22 * pop + 0.001,
                        color=Theme.yellow if (k == 1 and t > 0.75) else WHITE)
            if pop > 0.6:
                d.face(rr.cx, rr.cy, rr.h * 0.38, m)


def scene_hands(d):
    t = d.t
    i = min(3, int(t * 4))
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    shapes = ("Open", "Fist", "Point", "Thumbs up")
    cx, cy, r = d.X(0.32), d.Y(0.48), d.L(0.2)
    d.p.circle(cx, cy, r, SKIN)
    fingers = {0: (1, 1, 1, 1), 1: (0, 0, 0, 0), 2: (1, 0, 0, 0), 3: (0, 0, 0, 0)}[i]
    for k, up in enumerate(fingers):
        fx = cx - r * 0.55 + k * r * 0.37
        d.limb(fx, cy + r * 0.5, fx, cy + r * (0.6 + 0.9 * up), r * 0.28, SKIN)
    if i == 3:
        d.limb(cx - r * 0.9, cy, cx - r * 0.95, cy + r * 1.3, r * 0.3, SKIN)
    else:
        d.limb(cx - r * 0.9, cy, cx - r * 1.3, cy + r * 0.4, r * 0.3, SKIN)
    for k, nm in enumerate(shapes):
        rr = d.card(0.78, 0.8 - k * 0.2, 0.3, 0.15, color=Theme.yellow if k == i else WHITE)
        d.p.text(rr, nm, 9 * d.s, INK, "center", k == i)


def scene_try(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    poses = (dict(arm_r=2.5), dict(crouch=1.0, arm_l=0.6, arm_r=0.6), dict(crouch=0.6, arm_l=0.9, arm_r=0.9), dict(arm_l=0.5, arm_r=-0.4, lean=0.6))
    names = ("Wave", "Sit", "Crouch", "Walk")
    for k, (pz, nm) in enumerate(zip(poses, names)):
        pop = seg(t, k * 0.15, k * 0.15 + 0.15)
        if pop <= 0:
            continue
        r = d.card(0.14 + k * 0.24, 0.52, 0.21, 0.7, color=fade(WHITE, pop), border=fade(INK, pop))
        d.figure(0.14 + k * 0.24, 0.26, 0.4, alpha=pop, **pz)
        d.p.text(Rect(r.x, r.y + 3 * d.s, r.w, 12 * d.s), nm, 8 * d.s, fade(INK, pop), "center", True)
        if t > 0.7:
            ok = k != 0
            d.p.text(Rect(r.x, r.top - 16 * d.s, r.w - 4 * d.s, 14 * d.s), "✓" if ok else "!", 11 * d.s,
                     (0.23, 0.56, 0.31, 1) if ok else Theme.accent, "right", True)


def scene_try_fix(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    fixed = t > 0.5
    d.figure(0.3, 0.12, 0.62, arm_r=2.5)
    if not fixed:
        d.p.ring(d.X(0.3) + d.L(0.62) * 0.13, d.Y(0.12) + d.L(0.62) * 0.73, d.L(0.06), Theme.accent, 2.5 * d.s)
    b = d.button(0.74, 0.55, 0.42, 0.13, "Soften joints", pressed=0.35 < t < 0.45, size=9)
    d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.35, 0.5) if 0.25 < t < 0.55 else 0)
    d.label(0.74, 0.35, "fixed ✓" if fixed else "folds in", 11, (0.23, 0.56, 0.31, 1) if fixed else Theme.accent, bold=True, w=0.4)


def scene_joints(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    clay = (0.82, 0.62, 0.5, 1)
    x, y, k = d.X(0.5), d.Y(0.08), d.L(0.8)
    for side in (-1, 1):
        d.limb(x + side * k * 0.07, y + k * 0.45, x + side * k * 0.09, y + k * 0.03, k * 0.1, clay)
        d.limb(x + side * k * 0.13, y + k * 0.72, x + side * k * 0.2, y + k * 0.42, k * 0.09, clay)
    d.ellipse(x, y + k * 0.6, k * 0.16, k * 0.2, clay)
    d.p.circle(x, y + k * 0.9, k * 0.12, clay)
    dots = ((0, 0.8), (-0.13, 0.72), (0.13, 0.72), (-0.17, 0.57), (0.17, 0.57), (-0.07, 0.45), (0.07, 0.45), (-0.08, 0.24), (0.08, 0.24))
    for n, (du, dv) in enumerate(dots):
        pop = seg(t, 0.1 + n * 0.06, 0.18 + n * 0.06)
        if pop > 0:
            d.p.circle(x + du * k, y + dv * k, 5 * d.s * pop, WHITE)
            d.p.ring(x + du * k, y + dv * k, 5 * d.s * pop, INK, 1.5 * d.s)
    d.button(0.18, 0.88, 0.3, 0.12, "Guess them all", pressed=t < 0.1, size=8)


def scene_joint_fix(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    clay = (0.82, 0.62, 0.5, 1)
    x, y, k = d.X(0.42), d.Y(0.08), d.L(0.8)
    for side in (-1, 1):
        d.limb(x + side * k * 0.13, y + k * 0.72, x + side * k * 0.26, y + k * 0.42, k * 0.09, clay)
    d.ellipse(x, y + k * 0.6, k * 0.16, k * 0.2, clay)
    move = seg(t, 0.35, 0.6)
    for side in (-1, 1):
        ex = x + side * k * lerp(0.15, 0.2, move)
        ey = y + k * lerp(0.66, 0.57, move)
        d.p.circle(ex, ey, 5 * d.s, Theme.yellow if side == 1 else WHITE)
        d.p.ring(ex, ey, 5 * d.s, INK, 1.5 * d.s)
    if t > 0.6:
        d.label(0.17, 0.72, "mirror", 9, INK, bold=True, w=0.3)
    tx, ty = x + k * 0.2, y + k * 0.57
    d.cursor(tx, ty, press=seg(t, 0.3, 0.5) if 0.25 < t < 0.55 else 0)
    for n, nm in enumerate(("Neck", "Shoulder", "Elbow", "Hip")):
        r = d.card(0.84, 0.82 - n * 0.16, 0.26, 0.12, color=Theme.yellow if n == 2 else WHITE)
        d.p.text(r, nm, 8 * d.s, INK, "center", n == 2)


def scene_make_rig(d):
    t = d.t
    d.stage()
    b = d.button(0.78, 0.88, 0.36, 0.12, "Make the rig", pressed=0.1 < t < 0.2, size=9)
    d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.1, 0.3) if t < 0.3 else 0)
    nod = math.sin(max(0, t - 0.5) * 12) * 0.3 if t > 0.5 else 0
    d.figure(0.42, 0.1, 0.66, arm_r=0.3 + 1.2 * seg(t, 0.55, 0.8), look=nod)
    if t > 0.3:
        a = seg(t, 0.3, 0.45)
        k = d.L(0.66)
        for (du, dv) in ((0, 0.92), (0, 0.62), (0, 0.45), (-0.3, 0.42), (0.3, 0.42)):
            d.ring(d.X(0.42) + du * k * 0.6, d.Y(0.1) + dv * k, d.L(0.05) * a)
        for side in (-1, 1):
            d.p.ring(d.X(0.42) + side * k * 0.12, d.Y(0.1) + 4 * d.s, d.L(0.04) * a, YELLOW, 2 * d.s)


def scene_save_project(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    b = d.button(0.3, 0.6, 0.36, 0.16, "Save" if t < 0.5 else "Saved ✓", pressed=0.2 < t < 0.3,
                 color=Theme.accent if t < 0.5 else (0.23, 0.56, 0.31, 1))
    d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.2, 0.4) if t < 0.45 else 0)
    d.label(0.72, 0.6, "⌘S", 18, INK, bold=True, w=0.3)
    d.label(0.5, 0.25, "~/Stop Motion", 11, (0.4, 0.4, 0.4, 1), bold=True)


def scene_projects(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    for k, nm in enumerate(("Pip says hi", "Biscuit runs", "Snow day")):
        r = d.card(0.2 + k * 0.3, 0.55, 0.26, 0.4, color=Theme.yellow if (k == 1 and t > 0.5) else WHITE)
        pic = Rect(r.x + 4 * d.s, r.y + 18 * d.s, r.w - 8 * d.s, r.h - 22 * d.s)
        d.p.rect(pic, WALL)
        d.p.circle(pic.cx, pic.cy, pic.h * 0.2, RED)
        d.p.text(Rect(r.x, r.y + 3 * d.s, r.w, 12 * d.s), nm, 8 * d.s, INK, "center", True)
    d.cursor(d.X(0.5), d.Y(0.5), press=seg(t, 0.45, 0.6) if 0.4 < t < 0.65 else 0)
    d.button(0.8, 0.12, 0.34, 0.12, "New project", size=9)


def _hat(d, x, y, r, kind, color):
    if kind == "bobble":
        d.ellipse(x, y + r * 0.55, r * 1.08, r * 0.55, color)
        d.ellipse(x, y + r * 0.3, r * 1.12, r * 0.16, WHITE)
        d.p.circle(x, y + r * 1.15, r * 0.26, WHITE)
    elif kind == "top":
        d.p.rect(Rect(x - r * 0.75, y + r * 0.55, r * 1.5, r * 1.1), INK)
        d.p.rect(Rect(x - r * 1.2, y + r * 0.5, r * 2.4, r * 0.14), INK)
    elif kind == "crown":
        pts = [(x - r * 0.9, y + r * 0.5), (x + r * 0.9, y + r * 0.5), (x + r * 1.0, y + r * 1.3), (x + r * 0.5, y + r * 0.9),
               (x, y + r * 1.35), (x - r * 0.5, y + r * 0.9), (x - r * 1.0, y + r * 1.3)]
        d.p.polygon(pts, YELLOW)
    elif kind == "mop":
        d.ellipse(x, y + r * 0.45, r * 1.12, r * 0.7, (0.42, 0.26, 0.14, 1))
    else:   # cap
        d.ellipse(x, y + r * 0.55, r * 1.05, r * 0.5, color)
        d.ellipse(x - r * 0.7, y + r * 0.35, r * 0.75, r * 0.12, color)


def _head_of(d, u, v, h):
    k = d.L(h)
    x, y = d.X(u), d.Y(v)
    hip_y = y + k * 0.45
    by = hip_y + k * 0.17
    hr = k * 0.13
    return x, by + k * 0.21 + hr * 0.9, hr


def scene_hats(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    looks = (("mop", None), ("bobble", RED), ("top", None), ("cap", BLUE))
    i = min(3, int(t * 4))
    d.figure(0.36, 0.08, 0.7, arm_r=0.3)
    x, y, r = _head_of(d, 0.36, 0.08, 0.7)
    kind, c = looks[i]
    _hat(d, x, y, r, kind, c or RED)
    if i == 3:   # with a name tag too
        d.p.rect(Rect(x + r * 0.2, y - r * 2.6, r * 0.8, r * 0.45), WHITE)
    for k, nm in enumerate(("Mop", "Bobble hat", "Top hat", "Cap + tag")):
        rr = d.card(0.78, 0.8 - k * 0.2, 0.34, 0.15, color=Theme.yellow if k == i else WHITE)
        d.p.text(rr, nm, 9 * d.s, INK, "center", k == i)


def scene_own_parts(d):
    t = d.t
    d.stage(wall=(0.95, 0.92, 0.86, 1), floor=(0.95, 0.92, 0.86, 1))
    # a folder with your hat file, its picture card, then it on the puppet
    f = d.card(0.2, 0.78, 0.32, 0.24, color=(0.98, 0.85, 0.5, 1))
    d.p.text(Rect(f.x, f.top - 16 * d.s, f.w, 14 * d.s), "Kit › Hats", 8 * d.s, INK, "center", True)
    d.p.text(Rect(f.x, f.y + 4 * d.s, f.w, 14 * d.s), "Crown.blend", 8 * d.s, INK, "center")
    show = seg(t, 0.15, 0.35)
    if show > 0:
        card = d.card(0.2, 0.38, 0.26 * show + 0.001, 0.34 * show + 0.001, color=WHITE)
        if show > 0.8:
            _hat(d, card.cx, card.cy - card.h * 0.25, card.h * 0.22, "crown", YELLOW)
            d.p.text(Rect(card.x, card.y + 2 * d.s, card.w, 12 * d.s), "Crown", 8 * d.s, INK, "center", True)
    d.cursor(d.X(0.22), d.Y(0.36), press=seg(t, 0.45, 0.6) if 0.4 < t < 0.65 else 0)
    d.figure(0.68, 0.08, 0.7, arm_r=0.3 + (1.6 if t > 0.85 else 0))
    x, y, r = _head_of(d, 0.68, 0.08, 0.7)
    drop = seg(t, 0.55, 0.8)
    if drop > 0:
        _hat(d, x, y + (1 - drop) * d.L(0.3), r, "crown", YELLOW)


def scene_wear(d):
    t = d.t
    d.stage()
    d.figure(0.42, 0.08, 0.72, arm_r=0.3, mouth="o" if t > 0.75 else "smile")
    x, y, r = _head_of(d, 0.42, 0.08, 0.72)
    # the hat waits on the table, Wear it is pressed, then a click on the head
    top = d.table(0.82, 0.08, 0.26, 0.24)
    go = seg(t, 0.55, 0.75)
    hx, hy = lerp(d.X(0.82), x, go), lerp(top + r * 0.1, y, go)
    _hat(d, hx, hy - (r * 0.5 if go < 1 else 0), r, "cap", RED)
    b = d.button(0.82, 0.85, 0.3, 0.12, "Wear it", pressed=0.1 < t < 0.2, size=9)
    if t < 0.3:
        d.cursor(b.cx, b.cy - 3 * d.s, press=seg(t, 0.1, 0.25))
    elif t < 0.6:
        f = seg(t, 0.3, 0.45)
        d.cursor(lerp(b.cx, x + r * 0.2, f), lerp(b.cy, y + r * 0.8, f), press=seg(t, 0.45, 0.6) if t > 0.45 else 0)
    d.label(0.5, 0.06, "click where it goes", 11, INK, bold=True)


SCENES = {name[6:]: fn for name, fn in globals().items() if name.startswith("scene_") and callable(fn)}
