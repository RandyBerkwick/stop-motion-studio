"""The Studio's layout and widget input, without a GPU."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from importlib import import_module
kitmod = import_module("stop_motion_studio.studio_kit")
Kit, Rect, studio_layout = kitmod.Kit, kitmod.Rect, kitmod.studio_layout


class FakePainter:
    def __init__(self): self.calls = []
    def __getattr__(self, name):
        def rec(*a, **k): self.calls.append(name)
        return rec
    def text_width(self, text, size): return len(text) * size * 0.55


# --- layout: the live box is centred left/right, side columns match, nothing overlaps
for w, h, sc in ((1440, 900, 1.0), (2880, 1800, 2.0), (1280, 800, 1.0)):
    L = studio_layout(w, h, sc)
    live = L["live"]
    assert abs(L["left"].w - L["right"].w) < 1e-6
    assert abs(live.cx - w / 2) < 1e-6, (w, live.cx)
    assert abs(live.cy - h / 2) < 20 * sc, "live box nearly centred top/bottom"
    total = sum(L[k].w * L[k].h for k in ("top", "head_left", "head_centre", "head_right", "left", "right", "live", "footer"))
    assert abs(total - w * h) < 1.0, "regions tile the window exactly"
assert studio_layout(1440, 900, 1.0, chrome=False)["live"].w == 1440
print("layout ok")

# --- rect helpers
r = Rect(0, 0, 160, 90)
assert r.fit_aspect(1.0).w == 90 and r.fit_aspect(4.0).h == 40
top, rest = r.take_top(10)
assert top.y == 80 and rest.h == 80
assert [round(c.y) for c in Rect(0, 0, 10, 100).split_rows(2, 10)] == [55, 0]

# --- clicks: press + release on the same button fires once; dragging off cancels
p = FakePainter(); kit = Kit(p)
clicks = []
def frame():
    kit.begin(1.0)
    kit.button("a", Rect(10, 10, 100, 40), "Shoot", lambda: clicks.append("a"), "accent")
    kit.button("b", Rect(120, 10, 100, 40), "Other", lambda: clicks.append("b"))
    kit.button("off", Rect(230, 10, 100, 40), "Disabled", lambda: clicks.append("off"), enabled=False)
frame()
assert kit.over_ui(20, 20) and not kit.over_ui(500, 500)
assert kit.on_press(20, 20) and kit.on_release(25, 25) and clicks == ["a"]
kit.on_press(20, 20); kit.on_release(150, 20)
assert clicks == ["a"], "releasing over another button doesn't click either"
kit.on_press(240, 20); kit.on_release(240, 20)
assert clicks == ["a"], "disabled buttons don't click"
assert not kit.on_press(600, 600), "presses outside the UI go to the 3D view"
print("buttons ok")

# --- slider: press sets, drag follows, clamps
vals = []
kit.begin(1.0); kit.slider("g", Rect(0, 100, 200, 20), 0.5, vals.append)
kit.on_press(50, 110); kit.on_move(150, 110); kit.on_move(400, 110); kit.on_release(400, 110)
assert [round(v, 2) for v in vals] == [0.25, 0.75, 1.0], vals
print("slider ok")

# --- areas: a click swaps, a drag orbits (and then doesn't click), wheel scrolls
ev = []
kit.begin(1.0)
kit.area("pic", Rect(0, 200, 200, 200), on_click=lambda: ev.append("click"),
         on_drag=lambda dx, dy: ev.append(("drag", dx, dy)), on_wheel=lambda st: ev.append(("wheel", st)))
kit.on_press(50, 250); kit.on_release(51, 250)
assert ev == ["click"]
ev.clear(); kit.on_press(50, 250); kit.on_move(70, 260); kit.on_move(90, 270); kit.on_release(90, 270)
assert ev == [("drag", 20, 10), ("drag", 20, 10)], ev
ev.clear(); assert kit.on_wheel(10, 210, -1) and ev == [("wheel", -1)]
print("areas ok")

# --- segmented: each option is its own button
got = []
kit.begin(1.0); kit.segmented("hold", Rect(0, 500, 300, 30), [('1', "1"), ('2', "2"), ('3', "3")], '2', got.append)
kit.on_press(250, 510); kit.on_release(250, 510)
assert got == ['3']
print("STUDIO KIT TESTS PASSED")

# --- a hold handle on a card: dragging reports pixel moves, a plain press doesn't click
moves = []
kit.begin(1.0)
kit.area("shot:0", Rect(0, 600, 60, 40), on_click=lambda: moves.append("card"))
kit.area("hold:0", Rect(51, 600, 12, 40), on_drag=lambda dx, dy: moves.append(dx))
kit.on_press(57, 620); kit.on_move(70, 620); kit.on_move(100, 620); kit.on_release(100, 620)
assert moves == [13, 30], moves      # the handle wins over the card under it
moves.clear(); kit.on_press(20, 620); kit.on_release(20, 620)
assert moves == ["card"]
print("HOLD HANDLE TESTS PASSED")
