"""Draws the Stop Motion Studio app icon (1024px PNG) into the app template.

    python3 tools/make_icon.py

A warm dark tile with the Studio's orange "record" button: the same mark
as the Studio's top bar."""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app_template", "StopMotionStudio", "icon.png")
N, SS = 1024, 3          # size, supersampling
n = N * SS
y, x = np.mgrid[0:n, 0:n].astype(np.float32) / SS


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


img = np.zeros((n, n, 4), np.float32)
# macOS icon grid: an 824px rounded square centred in 1024, radius ~185
m, r = 100.0, 185.0
cx = np.clip(x, m + r, N - m - r)
cy = np.clip(y, m + r, N - m - r)
tile = ((x - cx) ** 2 + (y - cy) ** 2 <= r * r) & (x >= m) & (x <= N - m) & (y >= m) & (y <= N - m)
top, bottom = hexc("2b2520"), hexc("1c1916")
t = ((y - m) / (N - 2 * m))[..., None]
img[..., :3] = np.where(tile[..., None], top * (1 - t) + bottom * t, 0)
img[..., 3] = tile
c = N / 2
d = np.sqrt((x - c) ** 2 + (y - c) ** 2)
orange, cream = hexc("ff6a3d"), hexc("f3e6d3")
ring = (d <= 300) & (d >= 262)
img[ring, :3] = cream * 0.92
disc = d <= 238
img[disc, :3] = orange
dot = d <= 92
img[dot, :3] = cream
# a soft clay highlight on the disc
hl = disc & (((x - (c - 80)) ** 2 + (y - (c - 90)) ** 2) <= 120 ** 2) & ~dot
img[hl, :3] = img[hl, :3] * 0.85 + np.array([1.0, 0.62, 0.48]) * 0.15
small = img.reshape(N, SS, N, SS, 4).mean(axis=(1, 3))

import bpy
im = bpy.data.images.new("icon", N, N, alpha=True)
im.pixels.foreach_set(small[::-1].ravel())          # Blender rows go bottom-up
im.filepath_raw = OUT
im.file_format = 'PNG'
im.save()
print("saved", OUT)
