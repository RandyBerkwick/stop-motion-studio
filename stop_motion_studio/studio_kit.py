# SPDX-License-Identifier: GPL-3.0-or-later
"""A small immediate-mode UI kit for the Studio screen.

Every redraw, the screen code calls widget functions (button, segmented,
slider, ...). Each one paints itself through a Painter and records a hit
box. Input arrives separately (from the Studio modal operator) and is
matched against the hit boxes recorded by the last redraw.

Painting and input are split so the logic can be tested without a GPU:
tests use a Painter that only records calls.
"""

# ------------------------------------------------------------------ theme

def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


class Theme:
    ground = hexc("1c1916")
    panel = hexc("26221e")
    raised = hexc("332e28")
    line = hexc("3a342d")
    line_strong = hexc("4a4239")
    text = hexc("f1ebe3")
    soft = hexc("d8cfc4")
    muted = hexc("a89e92")
    accent = hexc("ff6a3d")
    on_accent = hexc("1a0e08")
    blue = hexc("7cc4ff")
    yellow = hexc("f5c84c")
    green = hexc("9ed98c")
    danger = hexc("e2553f")
    clay = hexc("f3e6cf")
    clay_text = hexc("3a2618")
    stage = hexc("0e0c0a")


# ------------------------------------------------------------------ rects

class Rect:
    """Pixel rectangle, origin bottom-left (Blender region space)."""
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = float(x), float(y), float(max(0, w)), float(max(0, h))

    def __repr__(self):
        return "Rect(%.0f, %.0f, %.0f, %.0f)" % (self.x, self.y, self.w, self.h)

    @property
    def right(self):
        return self.x + self.w

    @property
    def top(self):
        return self.y + self.h

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def contains(self, px, py):
        return self.x <= px < self.right and self.y <= py < self.top

    def inset(self, dx, dy=None):
        dy = dx if dy is None else dy
        return Rect(self.x + dx, self.y + dy, self.w - 2 * dx, self.h - 2 * dy)

    def take_top(self, h):
        return Rect(self.x, self.top - h, self.w, h), Rect(self.x, self.y, self.w, self.h - h)

    def take_bottom(self, h):
        return Rect(self.x, self.y, self.w, h), Rect(self.x, self.y + h, self.w, self.h - h)

    def take_left(self, w):
        return Rect(self.x, self.y, w, self.h), Rect(self.x + w, self.y, self.w - w, self.h)

    def take_right(self, w):
        return Rect(self.right - w, self.y, w, self.h), Rect(self.x, self.y, self.w - w, self.h)

    def split_cols(self, n, gap=0):
        w = (self.w - gap * (n - 1)) / n
        return [Rect(self.x + i * (w + gap), self.y, w, self.h) for i in range(n)]

    def split_rows(self, n, gap=0):
        """Top to bottom."""
        h = (self.h - gap * (n - 1)) / n
        return [Rect(self.x, self.top - (i + 1) * h - i * gap, self.w, h) for i in range(n)]

    def fit_aspect(self, aspect):
        """Largest rect of width/height `aspect` centred inside this one."""
        if self.w / max(1e-6, self.h) > aspect:
            w = self.h * aspect
            return Rect(self.cx - w / 2, self.y, w, self.h)
        h = self.w / aspect
        return Rect(self.x, self.cy - h / 2, self.w, h)


def studio_layout(width, height, s=1.0, chrome=True):
    """The Studio's regions, in pixels. `s` is the UI scale.

    Left and right columns are the same width and the top band matches the
    footer as closely as possible, so the live 3D view (which Blender
    centres in the whole window) stays centred in its own box."""
    full = Rect(0, 0, width, height)
    if not chrome:
        return {"full": full, "live": full}
    top_bar, rest = full.take_top(56 * s)
    headers, rest = rest.take_top(52 * s)
    footer, rest = rest.take_bottom(140 * s)
    side = min(300 * s, width * 0.24)
    left, rest = rest.take_left(side)
    right, live = rest.take_right(side)
    lh, hrest = headers.take_left(side)
    rh, ch = hrest.take_right(side)
    return {"full": full, "top": top_bar, "head_left": lh, "head_centre": ch, "head_right": rh,
            "left": left, "right": right, "live": live, "footer": footer}


# ------------------------------------------------------------------ kit

class Kit:
    """Immediate-mode widgets. Call begin() each redraw, then widgets."""

    def __init__(self, painter, theme=Theme):
        self.p = painter
        self.t = theme
        self.hits = []          # [(id, rect, kind, data)] from the last redraw
        self.hover = None
        self.pressed = None
        self.drag = None        # (id, start_x, start_y, data) for sliders / pictures
        self.scroll = {}        # id -> pixels
        self.s = 1.0
        self.mouse = (-1, -1)

    # ---- frame
    def begin(self, scale):
        self.s = scale
        self.hits = []

    def _hit(self, wid, rect, kind, **data):
        self.hits.append((wid, rect, kind, data))
        return wid == self.hover, wid == self.pressed

    # ---- painting helpers
    def panel(self, rect, color=None, radius=0, border=None):
        self.p.rect(rect, color or self.t.panel, radius * self.s)
        if border:
            self.p.rect_outline(rect, border, radius * self.s, 1)

    def label(self, rect, text, size=13, color=None, align="left", bold=False):
        self.p.text(rect, text, size * self.s, color or self.t.text, align, bold)

    def text_width(self, text, size=13):
        return self.p.text_width(text, size * self.s)

    # ---- widgets
    def button(self, wid, rect, label, on_click, style="ghost", selected=False, enabled=True,
               size=13, icon=None, tooltip=None):
        hov, prs = self._hit(wid, rect, "button", on_click=on_click if enabled else None)
        t = self.t
        r = 9 * self.s
        if style == "accent":
            bg, fg, br = t.accent, t.on_accent, None
            if hov:
                bg = tuple(min(1, c * 1.08) for c in bg[:3]) + (1,)
        elif style == "tab":
            bg = t.line if selected else (t.raised if hov else (0, 0, 0, 0))
            fg = t.text if selected or hov else t.muted
            br = None
        elif style == "clay":
            bg, fg = t.clay, t.clay_text
            br = t.accent if selected else None
        elif style == "danger":
            bg, fg, br = (0.89, 0.33, 0.25, 0.12), (1.0, 0.73, 0.65, 1), (0.71, 0.33, 0.23, 1)
        else:  # ghost
            if selected:
                bg, fg, br = (0.49, 0.77, 1.0, 0.16), t.text, t.blue
            else:
                bg = t.raised if hov else (0, 0, 0, 0)
                fg, br = t.soft, t.line_strong
        if not enabled:
            fg = t.muted[:3] + (0.5,)
        if prs and enabled:
            rect_draw = rect.inset(1 * self.s)
        else:
            rect_draw = rect
        self.p.rect(rect_draw, bg, r)
        if br is not None:
            self.p.rect_outline(rect_draw, br, r, 2 if (style == "clay" and selected) else 1)
        if icon:
            iw = 14 * self.s
            tw = self.text_width(label, size) if label else 0
            gap = 7 * self.s if label else 0
            x0 = rect.cx - (iw + gap + tw) / 2
            self.p.icon(icon, Rect(x0, rect.cy - iw / 2, iw, iw), fg)
            if label:
                self.p.text(Rect(x0 + iw + gap, rect.y, tw + 4, rect.h), label, size * self.s, fg, "left",
                            style in ("accent", "tab") and selected or style == "accent")
        else:
            self.p.text(rect, label, size * self.s, fg, "center", style == "accent" or selected)
        return hov

    def segmented(self, wid, rect, options, value, on_change, size=13):
        """options: [(value, label)]. One button per option."""
        cells = rect.split_cols(len(options), gap=4 * self.s)
        for (val, text), cell in zip(options, cells):
            self.button("%s:%s" % (wid, val), cell, text, (lambda v=val: on_change(v)),
                        selected=(val == value), size=size)

    def slider(self, wid, rect, value, on_change, color=None):
        """value 0..1; drag anywhere on the track."""
        self._hit(wid, rect, "slider", on_change=on_change)
        t = self.t
        track = Rect(rect.x, rect.cy - 3 * self.s, rect.w, 6 * self.s)
        self.p.rect(track, t.line, 3 * self.s)
        fill = Rect(track.x, track.y, track.w * max(0.0, min(1.0, value)), track.h)
        self.p.rect(fill, color or t.blue, 3 * self.s)
        knob = 16 * self.s
        kx = rect.x + rect.w * max(0.0, min(1.0, value))
        self.p.circle(kx, rect.cy, knob / 2, t.text)

    def toggle(self, wid, rect, label, value, on_toggle, color=None):
        col = color or self.t.yellow
        hov, _p = self._hit(wid, rect, "button", on_click=lambda: on_toggle(not value))
        r = 9 * self.s
        if value:
            self.p.rect(rect, col[:3] + (0.14,), r)
            self.p.rect_outline(rect, col, r, 1)
        else:
            self.p.rect(rect, self.t.raised if hov else (0, 0, 0, 0), r)
            self.p.rect_outline(rect, self.t.line_strong, r, 1)
        self.p.text(rect, label, 12 * self.s, self.t.text if value else self.t.soft, "center", value)

    def area(self, wid, rect, on_click=None, on_drag=None, on_wheel=None):
        """An invisible hit box (pictures, cards): click, drag and wheel."""
        return self._hit(wid, rect, "area", on_click=on_click, on_drag=on_drag, on_wheel=on_wheel)

    # ---- input (called by the modal operator) -> True when the kit used the event
    def _find(self, x, y):
        for wid, rect, kind, data in reversed(self.hits):  # topmost last drawn
            if rect.contains(x, y):
                return wid, rect, kind, data
        return None

    def over_ui(self, x, y):
        return self._find(x, y) is not None

    def on_move(self, x, y):
        self.mouse = (x, y)
        if self.drag is not None:
            wid, sx, sy, data = self.drag
            if data.get("kind") == "slider":
                rect = data["rect"]
                data["on_change"](max(0.0, min(1.0, (x - rect.x) / max(1.0, rect.w))))
            elif data.get("on_drag"):
                moved = abs(x - sx) + abs(y - sy) > 4 * self.s
                if moved or data.get("dragging"):
                    data["dragging"] = True
                    data["on_drag"](x - data.get("lx", sx), y - data.get("ly", sy))
                    data["lx"], data["ly"] = x, y
            return True
        hit = self._find(x, y)
        new = hit[0] if hit else None
        changed = new != self.hover
        self.hover = new
        return changed

    def on_press(self, x, y):
        hit = self._find(x, y)
        if hit is None:
            return False
        wid, rect, kind, data = hit
        self.pressed = wid
        if kind == "slider":
            self.drag = (wid, x, y, {"kind": "slider", "rect": rect, "on_change": data["on_change"]})
            data["on_change"](max(0.0, min(1.0, (x - rect.x) / max(1.0, rect.w))))
        elif kind == "area" and data.get("on_drag"):
            self.drag = (wid, x, y, dict(data, kind="area"))
        return True

    def on_release(self, x, y):
        wid = self.pressed
        drag = self.drag
        self.pressed = None
        self.drag = None
        if wid is None:
            return False
        if drag is not None:
            if drag[3].get("kind") == "area" and not drag[3].get("dragging"):
                cb = drag[3].get("on_click")
                if cb:
                    cb()
            return True
        hit = self._find(x, y)
        if hit and hit[0] == wid:
            cb = hit[3].get("on_click")
            if cb:
                cb()
        return True

    def on_wheel(self, x, y, steps):
        hit = self._find(x, y)
        if hit and hit[3].get("on_wheel"):
            hit[3]["on_wheel"](steps)
            return True
        return False
