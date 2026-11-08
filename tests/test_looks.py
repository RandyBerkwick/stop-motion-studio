"""The Studio's looks: switching colours, sketchy widgets, preference fallback, fonts shipped."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bpy  # noqa: F401
from stop_motion_studio import studio_kit as sk
from stop_motion_studio.studio_kit import Kit, Rect, Theme, apply_look, LOOKS


class FakePainter:
    def __init__(self): self.calls = []
    def __getattr__(self, name):
        def rec(*a, **k): self.calls.append((name, a, k))
        return rec
    def text_width(self, text, size, bold=False): return len(text) * size * (0.6 if bold else 0.5)


# every look names every colour the dark one does
for name, d in LOOKS.items():
    assert set(d) == set(LOOKS["DARK"]), name

assert apply_look("SKETCH") and Theme.sketchy and Theme.grid is not None
assert not apply_look("SKETCH"), "no change, no work"
assert Theme.ground[0] > 0.9, "paper is light"
# text on a highlighter tag must be dark, and 'mark' must be readable on paper
assert sum(Theme.on_yellow[:3]) < 0.6 and sum(Theme.mark[:3]) < 2.0

# sketch buttons: ink outline and a shadow; picked = highlighter
p = FakePainter(); kit = Kit(p); kit.begin(1.0)
kit.button("a", Rect(0, 0, 100, 30), "Open", lambda: None, selected=True)
names = [c[0] for c in p.calls]
assert names.count("rect") == 2 and "rect_outline" in names, names
fills = [c[1][1] for c in p.calls if c[0] == "rect"]
assert Theme.yellow in fills, "picked button wears the highlighter"
# measuring uses the wider bold width in sketch, so bold labels fit their boxes
assert kit.text_width("Shoot", 10) == len("Shoot") * 10 * 0.6

# back to dark: everything as before
assert apply_look("DARK") and not Theme.sketchy and Theme.grid is None
assert Theme.ground == sk.hexc("1c1916")
p = FakePainter(); kit = Kit(p); kit.begin(1.0)
kit.button("a", Rect(0, 0, 100, 30), "Open", lambda: None, selected=True)
assert [c[0] for c in p.calls].count("rect") == 1
assert kit.text_width("Shoot", 10) == len("Shoot") * 10 * 0.5
assert not apply_look("NOPE") and Theme.look == "DARK", "unknown look falls back to dark"

# preference: works without the add-on enabled (falls back to a module value)
from stop_motion_studio import props
props.set_look("SKETCH"); assert props.get_look() == "SKETCH"
props.set_look("DARK"); assert props.get_look() == "DARK"

# the hand fonts ship with the extension, with their licences
fd = os.path.join(os.path.dirname(sk.__file__), "fonts")
for f in ("PatrickHand-Regular.ttf", "Kalam-Bold.ttf", "OFL-PatrickHand.txt", "OFL-Kalam.txt"):
    assert os.path.getsize(os.path.join(fd, f)) > 1000, f

# wobbly outlines stay close to the box and are repeatable
from stop_motion_studio import studio_paint as spaint
pts = spaint._rounded(Rect(10, 10, 200, 60), 9)
w1 = spaint._wobbly(pts, 1.6, 5); w2 = spaint._wobbly(pts, 1.6, 5)
assert w1 == w2 and len(w1) > len(pts)
assert all(8 - 2 <= x <= 212 and 8 - 2 <= y <= 72 for x, y in w1)
print("looks ok")
