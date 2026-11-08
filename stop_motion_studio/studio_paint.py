# SPDX-License-Identifier: GPL-3.0-or-later
"""Draws the Studio kit with Blender's gpu and blf modules (pixel space)."""

import math
import os

import blf
import gpu
from gpu_extras.batch import batch_for_shader

from .studio_kit import Theme

FONT = 0
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONTS = {}


def font_ids():
    """(body, bold) font ids for the current look. Sketchbook uses hand-lettered fonts
    shipped with the extension (Patrick Hand and Kalam, SIL Open Font Licence)."""
    if not Theme.sketchy:
        return FONT, FONT
    if not _FONTS:
        for key, name in (("body", "PatrickHand-Regular.ttf"), ("bold", "Kalam-Bold.ttf")):
            fid = -1
            try:
                fid = blf.load(os.path.join(FONT_DIR, name))
            except Exception:
                pass
            _FONTS[key] = fid if fid is not None and fid >= 0 else FONT
    return _FONTS["body"], _FONTS["bold"]


def _noise(seed, t):
    """Smooth, repeatable wobble in -1..1 along an outline."""
    return (math.sin(t * 0.11 + seed) * 0.6 + math.sin(t * 0.037 + seed * 1.7) * 0.4)


def _wobbly(pts, amount, seed, step=18.0):
    """Densify a closed outline and nudge each point sideways, like a hand-drawn line."""
    out = []
    n = len(pts)
    run = 0.0
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        k = max(1, int(L / step))
        nx, ny = (-dy / L, dx / L) if L > 1e-6 else (0.0, 0.0)
        for j in range(k):
            f = j / k
            d = _noise(seed, run + L * f) * amount
            out.append((x0 + dx * f + nx * d, y0 + dy * f + ny * d))
        run += L
    return out


def _rounded(rect, r, seg=6):
    r = max(0.0, min(r, rect.w / 2, rect.h / 2))
    if r < 0.5:
        return [(rect.x, rect.y), (rect.right, rect.y), (rect.right, rect.top), (rect.x, rect.top)]
    pts = []
    for cx, cy, a0 in ((rect.right - r, rect.y + r, -90), (rect.right - r, rect.top - r, 0),
                       (rect.x + r, rect.top - r, 90), (rect.x + r, rect.y + r, 180)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


class GPUPainter:
    def __init__(self):
        self._uni = None
        self._line = None
        self._img = None

    @property
    def uni(self):
        if self._uni is None:
            self._uni = gpu.shader.from_builtin('UNIFORM_COLOR')
        return self._uni

    @property
    def line(self):
        if self._line is None:
            self._line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        return self._line

    @property
    def img(self):
        if self._img is None:
            self._img = gpu.shader.from_builtin('IMAGE_COLOR')
        return self._img

    # ---- shapes
    def _fill(self, pts, color):
        if color[3] <= 0.001 or len(pts) < 3:
            return
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        tris = []
        for i in range(len(pts)):
            tris.extend([(cx, cy), pts[i], pts[(i + 1) % len(pts)]])
        gpu.state.blend_set('ALPHA')
        sh = self.uni
        batch = batch_for_shader(sh, 'TRIS', {"pos": tris})
        sh.bind()
        sh.uniform_float("color", color)
        batch.draw(sh)

    def _stroke(self, pts, color, width, closed=True):
        if color[3] <= 0.001 or len(pts) < 2:
            return
        if closed:
            pts = list(pts) + [pts[0]]
        gpu.state.blend_set('ALPHA')
        sh = self.line
        batch = batch_for_shader(sh, 'LINE_STRIP', {"pos": pts})
        sh.bind()
        sh.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        sh.uniform_float("lineWidth", width)
        sh.uniform_float("color", color)
        batch.draw(sh)

    def _shape(self, rect, radius):
        pts = _rounded(rect, radius)
        if Theme.sketchy and radius > 0.5 and rect.w > 12 and rect.h > 12:
            # the seed follows the box's size, not its place, so a button keeps its wobble when it moves
            seed = (round(rect.w) * 7 + round(rect.h) * 13) % 97
            pts = _wobbly(pts, min(1.6, 0.8 + min(rect.w, rect.h) * 0.004), seed)
        return pts

    def rect(self, rect, color, radius=0):
        self._fill(self._shape(rect, radius), color)

    def rect_outline(self, rect, color, radius=0, width=1):
        self._stroke(self._shape(rect.inset(width / 2), radius), color, width)

    def grid(self, rect, step, color):
        """Squared paper: thin lines every `step` pixels, lined up with the window."""
        if color is None or step < 4:
            return
        lines = []
        x = math.ceil(rect.x / step) * step
        while x < rect.right:
            lines += [(x, rect.y), (x, rect.top)]
            x += step
        y = math.ceil(rect.y / step) * step
        while y < rect.top:
            lines += [(rect.x, y), (rect.right, y)]
            y += step
        if not lines:
            return
        gpu.state.blend_set('ALPHA')
        sh = self.uni
        batch = batch_for_shader(sh, 'LINES', {"pos": lines})
        sh.bind()
        sh.uniform_float("color", color)
        batch.draw(sh)

    def circle(self, cx, cy, r, color, seg=24):
        pts = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        self._fill(pts, color)

    def ring(self, cx, cy, r, color, width=2, seg=32):
        pts = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        self._stroke(pts, color, width)

    def lines(self, pts, color, width=2, closed=False):
        self._stroke(pts, color, width, closed)

    def polygon(self, pts, color):
        self._fill(pts, color)

    # ---- text
    def _font(self, size, bold=False):
        body, heavy = font_ids()
        fid = heavy if bold else body
        if Theme.sketchy:
            size *= 1.18   # hand fonts draw small for their size
        blf.size(fid, size)
        return fid

    def text_width(self, text, size, bold=False):
        fid = self._font(size, bold)
        return blf.dimensions(fid, text)[0]

    def text(self, rect, text, size, color, align="left", bold=False):
        if not text:
            return
        FONT = self._font(size, bold)
        real_bold = bold and Theme.sketchy and font_ids()[1] != font_ids()[0]
        w = blf.dimensions(FONT, text)[0]
        if w > rect.w and rect.w > size:
            while text and blf.dimensions(FONT, text + "…")[0] > rect.w:
                text = text[:-1]
            text += "…"
            w = blf.dimensions(FONT, text)[0]
        cap = blf.dimensions(FONT, "H")[1]
        if align == "center":
            x = rect.cx - w / 2
        elif align == "right":
            x = rect.right - w
        else:
            x = rect.x
        y = rect.cy - cap / 2
        blf.color(FONT, *color)
        blf.position(FONT, round(x), round(y), 0)
        blf.draw(FONT, text)
        if bold and not real_bold:  # the default font has no bold weight here: a faint double strike reads as bolder
            blf.position(FONT, round(x) + 0.6, round(y), 0)
            blf.draw(FONT, text)

    # ---- pictures
    def texture(self, rect, tex, alpha=1.0, tint=(1, 1, 1)):
        if tex is None:
            return
        gpu.state.blend_set('ALPHA')
        sh = self.img
        batch = batch_for_shader(sh, 'TRI_FAN', {
            "pos": ((rect.x, rect.y), (rect.right, rect.y), (rect.right, rect.top), (rect.x, rect.top)),
            "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1))})
        sh.bind()
        sh.uniform_sampler("image", tex)
        sh.uniform_float("color", (*tint, alpha))
        batch.draw(sh)

    def image(self, rect, image, alpha=1.0, tint=(1, 1, 1)):
        try:
            tex = gpu.texture.from_image(image)
        except Exception:
            return
        self.texture(rect, tex, alpha, tint)

    # ---- clipping
    def clip(self, rect):
        gpu.state.scissor_test_set(True)
        gpu.state.scissor_set(int(rect.x), int(rect.y), int(rect.w), int(rect.h))

    def unclip(self):
        gpu.state.scissor_test_set(False)

    # ---- icons (simple strokes so they scale crisply)
    def icon(self, name, r, color):
        s = r.w
        x, y = r.x, r.y
        w = max(1.5, s / 9)
        if name == "play":
            self.polygon([(x + s * 0.2, y), (x + s, y + s / 2), (x + s * 0.2, y + s)], color)
        elif name == "pause":
            self.rect(type(r)(x + s * 0.15, y, s * 0.25, s), color)
            self.rect(type(r)(x + s * 0.6, y, s * 0.25, s), color)
        elif name == "rec":
            self.circle(x + s / 2, y + s / 2, s * 0.42, color)
        elif name == "prev":
            self.lines([(x + s * 0.65, y + s * 0.1), (x + s * 0.3, y + s / 2), (x + s * 0.65, y + s * 0.9)], color, w)
        elif name == "next":
            self.lines([(x + s * 0.35, y + s * 0.1), (x + s * 0.7, y + s / 2), (x + s * 0.35, y + s * 0.9)], color, w)
        elif name == "plus":
            self.lines([(x + s / 2, y + s * 0.1), (x + s / 2, y + s * 0.9)], color, w)
            self.lines([(x + s * 0.1, y + s / 2), (x + s * 0.9, y + s / 2)], color, w)
        elif name == "x":
            self.lines([(x + s * 0.2, y + s * 0.2), (x + s * 0.8, y + s * 0.8)], color, w)
            self.lines([(x + s * 0.2, y + s * 0.8), (x + s * 0.8, y + s * 0.2)], color, w)
        elif name in ("lock", "unlock"):
            self.rect(type(r)(x + s * 0.15, y, s * 0.7, s * 0.55), color, s * 0.1)
            pts = [(x + s * 0.3 + s * 0.2 * (1 - math.cos(math.pi * i / 12)), y + s * 0.55 + s * 0.35 * math.sin(math.pi * i / 12))
                   for i in range(13)]
            if name == "unlock":
                pts = pts[:9]
            self.lines(pts, color, w)
        elif name == "pin":
            self.circle(x + s / 2, y + s * 0.7, s * 0.28, color)
            self.lines([(x + s / 2, y + s * 0.45), (x + s / 2, y)], color, w)
        elif name == "swap":
            self.lines([(x, y + s * 0.65), (x + s, y + s * 0.65), (x + s * 0.75, y + s * 0.9)], color, w)
            self.lines([(x + s, y + s * 0.35), (x, y + s * 0.35), (x + s * 0.25, y + s * 0.1)], color, w)
        elif name == "eye":
            self.lines([(x, y + s / 2), (x + s / 2, y + s * 0.85), (x + s, y + s / 2), (x + s / 2, y + s * 0.15)], color, w, True)
            self.circle(x + s / 2, y + s / 2, s * 0.15, color)
        elif name == "trash":
            self.lines([(x + s * 0.1, y + s * 0.85), (x + s * 0.9, y + s * 0.85)], color, w)
            self.lines([(x + s * 0.2, y + s * 0.85), (x + s * 0.28, y), (x + s * 0.72, y), (x + s * 0.8, y + s * 0.85)], color, w)
        elif name == "copy":
            self.rect_outline(type(r)(x + s * 0.3, y, s * 0.7, s * 0.7), color, s * 0.1, w)
            self.lines([(x, y + s * 0.3), (x, y + s), (x + s * 0.7, y + s)], color, w)
        elif name == "camera":
            self.rect_outline(type(r)(x, y + s * 0.15, s * 0.7, s * 0.7), color, s * 0.1, w)
            self.polygon([(x + s * 0.7, y + s / 2), (x + s, y + s * 0.75), (x + s, y + s * 0.25)], color)
        else:  # dot
            self.circle(x + s / 2, y + s / 2, s * 0.2, color)
