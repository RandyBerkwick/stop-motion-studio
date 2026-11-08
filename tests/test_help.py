"""Help panels: every view has a guide, every picture exists and draws, the panel follows the view."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bpy  # noqa: F401
from stop_motion_studio import studio_help as sh
from stop_motion_studio.studio_kit import Kit, Rect, studio_layout, apply_look


class FakePainter:
    def __init__(self): self.calls = []
    def __getattr__(self, name):
        def rec(*a, **k): self.calls.append((name, a, k))
        return rec
    def text_width(self, text, size, bold=False): return len(text) * size * 0.5


# every guide is complete, and every picture it names exists
assert set(sh.ORDER) == set(sh.TOPICS)
for key, (title, steps) in sh.TOPICS.items():
    assert title and 2 <= len(steps) <= 8, key
    for st, text, scene in steps:
        assert st and len(text) > 20, (key, st)
        assert scene in sh.SCENES, (key, scene)

# every picture draws at every moment of its loop, in both looks, and stays inside its box
for look in ("DARK", "SKETCH"):
    apply_look(look)
    for name, fn in sh.SCENES.items():
        for i in range(21):
            p = FakePainter()
            box = Rect(100, 200, 260, 180)
            fn(sh.Ill(p, box, 1.0, i / 20))
            assert p.calls, name
            for call, a, _k in p.calls:
                if call == "circle":
                    x, y, r = a[0], a[1], a[2]
                    assert box.x - 40 <= x <= box.right + 40 and box.y - 40 <= y <= box.top + 40, (name, i, call, a[:3])
apply_look("DARK")


class FakeS:
    overlay = None
    mode = 'ANIMATE'
    side = 'PUPPET'


class FakeP:
    start = 'PARTS'
    step = 'BUILD'


S, P = FakeS(), FakeP()
# the guide follows the view
assert sh.view_topic(S, P) == 'ANIMATE'
S.side = 'PROPS'; assert sh.view_topic(S, P) == 'SET'
S.side = 'LIGHT'; assert sh.view_topic(S, P) == 'LIGHT'
S.side = 'SCULPT'; assert sh.view_topic(S, P) == 'SCULPT'
S.mode = 'REVIEW'; assert sh.view_topic(S, P) == 'REVIEW'
S.mode = 'PUPPETS'; assert sh.view_topic(S, P) == 'BUILD'
P.start, P.step = 'SCULPT', 'JOINTS'; assert sh.view_topic(S, P) == 'JOINTS'
P.step = 'FACE'; assert sh.view_topic(S, P) == 'FACE'
P.step = 'TRY'; assert sh.view_topic(S, P) == 'TRY'
P.step = 'SAVE'; assert sh.view_topic(S, P) == 'SAVE'
P.start = 'RIG'; assert sh.view_topic(S, P) == 'RIG'
S.overlay = 'LIBRARY'; assert sh.view_topic(S, P) == 'BRING_IN'
S.overlay = 'PROJECTS'; assert sh.view_topic(S, P) == 'PROJECTS'

# browsing keeps a picked guide until the view changes, then follows again
S.overlay, S.mode, S.side = None, 'ANIMATE', 'PUPPET'
assert sh.current(S, P) == 'ANIMATE'
sh.browse('ANIMATE', 1); assert sh.current(S, P) == 'SET' and sh.H.step == 0
sh.browse('SET', -1); sh.browse('ANIMATE', -1); assert sh.current(S, P) == 'PROJECTS'
S.side = 'LIGHT'; assert sh.current(S, P) == 'LIGHT', "a new view brings its own guide"
sh.go_step(99, 3); assert sh.H.step == 2
sh.go_step(-5, 3); assert sh.H.step == 0

# wrapping
lines = sh.wrap(lambda x: len(x) * 6, "one two three four five six seven eight nine ten", 60)
assert all(len(l) * 6 <= 60 for l in lines) and " ".join(lines).split() == "one two three four five six seven eight nine ten".split()
assert sh.wrap(lambda x: len(x) * 6, "Supercalifragilistic", 30) == ["Supercalifragilistic"], "long words still show"

# the layout makes room for the help column and the rest still tiles the window
L0 = studio_layout(1440, 900, 1.0)
L = studio_layout(1440, 900, 1.0, True, True)
assert L0["help"] is None and L["help"] is not None
hc = L["help"]
assert hc.x == 0 and abs(hc.top - L["top"].y) < 1e-6 and abs(hc.y - L["footer"].top) < 1e-6
assert abs(L["left"].x - hc.right) < 1e-6 and L["live"].w > 400
assert abs(L["right"].right - 1440) < 1e-6 and L["footer"].w == 1440

# the panel draws, and its buttons work
closed = []
for look in ("DARK", "SKETCH"):
    apply_look(look)
    for key in sh.ORDER:
        sh.H.topic, sh.H.view = key, 'ANIMATE'
        S.side = 'PUPPET'
        _t, steps = sh.TOPICS[key]
        for st in range(len(steps)):
            sh.H.step = st
            p = FakePainter(); kit = Kit(p); kit.begin(1.0)
            sh.draw(kit, hc, S, P, 1.0, {"close": lambda: closed.append(1), "redraw": lambda: None}, now=1000.3)
            texts = [a[1] for c, a, _k in p.calls if c == "text"]
            assert any(steps[st][0] in t for t in texts), (key, st)
apply_look("DARK")
p = FakePainter(); kit = Kit(p); kit.begin(1.0)
sh.H.topic, sh.H.view, sh.H.step = None, 'ANIMATE', 0
sh.draw(kit, hc, S, P, 1.0, {"close": lambda: closed.append(1), "redraw": lambda: None})
ids = {h[0] for h in kit.hits}
for wid in ("help:close", "help:next", "help:back", "help:prevtopic", "help:nexttopic", "help:pic", "help:dot:0"):
    assert wid in ids, wid
r = next(h[1] for h in kit.hits if h[0] == "help:next")
kit.on_press(r.cx, r.cy); kit.on_release(r.cx, r.cy)
assert sh.H.step == 1, "Next goes on a step"
r = next(h[1] for h in kit.hits if h[0] == "help:close")
kit.on_press(r.cx, r.cy); kit.on_release(r.cx, r.cy)
assert closed, "close closes"
assert sh.toggle() and not sh.toggle()
print("help ok")
