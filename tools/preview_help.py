"""Contact sheet of every help picture at a few moments in its loop, for checking by eye.

    python3 tools/preview_help.py /tmp/help_sheet.png [DARK|SKETCH]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bpy  # noqa: E402
import gpu  # noqa: E402
from mathutils import Matrix  # noqa: E402

from stop_motion_studio import studio_help  # noqa: E402
from stop_motion_studio.studio_kit import Rect, Theme, apply_look  # noqa: E402
from stop_motion_studio.studio_paint import GPUPainter  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/help_sheet.png"
apply_look(sys.argv[2] if len(sys.argv) > 2 else "DARK")
names = sorted(studio_help.SCENES)
phases = (0.15, 0.4, 0.65, 0.9)
cw, ch, pad, label = 230, 160, 10, 18
cols = len(phases)
W = cols * (cw + pad) + pad
H = len(names) * (ch + pad + label) + pad
gpu.init()
off = gpu.types.GPUOffScreen(W, H)
p = GPUPainter()
with off.bind():
    fb = gpu.state.active_framebuffer_get()
    fb.clear(color=(*Theme.ground[:3], 1.0))
    gpu.matrix.load_matrix(Matrix.Identity(4))
    gpu.matrix.load_projection_matrix(Matrix(((2 / W, 0, 0, -1), (0, 2 / H, 0, -1), (0, 0, -1, 0), (0, 0, 0, 1))))
    for row, name in enumerate(names):
        y = H - (row + 1) * (ch + pad + label)
        p.text(Rect(pad, y + ch + 2, 400, label), name, 12, Theme.text, "left", True)
        for col, ph in enumerate(phases):
            box = Rect(pad + col * (cw + pad), y, cw, ch)
            p.rect(box, Theme.raised)
            p.clip(box)
            studio_help.SCENES[name](studio_help.Ill(p, box, 1.0, ph))
            p.unclip()
            p.rect_outline(box, Theme.line_strong, 0, 1)
    buf = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
import numpy as np  # noqa: E402
arr = np.frombuffer(buf, dtype=np.float32)
img = bpy.data.images.new("sheet", W, H, alpha=True)
img.pixels.foreach_set(np.clip(arr, 0, 1))
img.filepath_raw = out
img.file_format = 'PNG'
img.save()
print("saved", out, len(names), "pictures")
