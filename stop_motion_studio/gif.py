# SPDX-License-Identifier: GPL-3.0-or-later
"""A small animated-GIF writer (Blender has no GIF output).

Frames are HxWx3 uint8 numpy arrays (top row first). One palette of up to
256 colours is made for the whole film by median cut, so colours don't
flicker between frames; each frame is then mapped through a 32³ colour
lookup and LZW-compressed. Each frame has its own delay, so a shot held
for 3 frames is written once and shown three times as long.
"""

import struct

import numpy as np


# ------------------------------------------------------------------ palette

def median_cut(samples, n=256):
    """Up to n colours (uint8 Nx3) that cover `samples` (Mx3 uint8)."""
    boxes = [samples.astype(np.int16)]
    while len(boxes) < n:
        # split the box with the widest colour range
        best, best_i, best_c = -1, -1, 0
        for i, b in enumerate(boxes):
            if len(b) < 2:
                continue
            rng = b.max(axis=0) - b.min(axis=0)
            c = int(np.argmax(rng))
            if rng[c] > best:
                best, best_i, best_c = int(rng[c]), i, c
        if best <= 0:
            break
        b = boxes.pop(best_i)
        b = b[np.argsort(b[:, best_c], kind="stable")]
        mid = len(b) // 2
        boxes.extend((b[:mid], b[mid:]))
    pal = np.array([b.mean(axis=0) for b in boxes if len(b)], dtype=np.float32)
    return np.clip(np.rint(pal), 0, 255).astype(np.uint8)


def lookup_cube(pal):
    """32x32x32 table: 5-bit colour -> nearest palette index."""
    g = (np.arange(32, dtype=np.float32) * 8 + 4)
    cube = np.stack(np.meshgrid(g, g, g, indexing="ij"), axis=-1).reshape(-1, 3)
    p = pal.astype(np.float32)
    out = np.empty(len(cube), dtype=np.uint8)
    for s in range(0, len(cube), 4096):
        d = ((cube[s:s + 4096, None, :] - p[None, :, :]) ** 2).sum(axis=2)
        out[s:s + 4096] = np.argmin(d, axis=1)
    return out.reshape(32, 32, 32)


def index_frame(frame, cube):
    q = (frame >> 3).astype(np.intp)
    return cube[q[..., 0], q[..., 1], q[..., 2]]


# --------------------------------------------------------------------- LZW

def lzw(indices, min_size=8):
    """GIF LZW of a flat sequence of palette indices -> bytes."""
    clear, end = 1 << min_size, (1 << min_size) + 1
    out = bytearray()
    acc = nbits = 0
    size = min_size + 1

    def emit(code):
        nonlocal acc, nbits
        acc |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8

    table = {}
    nxt = end + 1
    emit(clear)
    data = indices.tobytes() if hasattr(indices, "tobytes") else bytes(indices)
    if not data:
        emit(end)
        if nbits:
            out.append(acc & 0xFF)
        return bytes(out)
    prefix = data[0]
    for px in data[1:]:
        key = (prefix << 8) | px
        code = table.get(key)
        if code is not None:
            prefix = code
            continue
        emit(prefix)
        if nxt < 4096:
            table[key] = nxt
            nxt += 1
            if nxt > (1 << size) and size < 12:
                size += 1
        else:
            emit(clear)
            table.clear()
            nxt = end + 1
            size = min_size + 1
        prefix = px
    emit(prefix)
    emit(end)
    if nbits:
        out.append(acc & 0xFF)
    return bytes(out)


def _blocks(data):
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out.append(len(chunk))
        out += chunk
    out.append(0)
    return bytes(out)


# ------------------------------------------------------------------- writer

def resize(frame, width):
    """Box-filtered shrink to `width` (keeps the shape); never enlarges."""
    h, w = frame.shape[:2]
    if w <= width:
        return frame
    nh = max(1, round(h * width / w))
    ys = np.linspace(0, h, nh + 1).astype(int)
    xs = np.linspace(0, w, width + 1).astype(int)
    f = frame.astype(np.float32)
    # cumulative sums give the mean of each source box
    c = np.cumsum(np.cumsum(np.pad(f, ((1, 0), (1, 0), (0, 0))), axis=0), axis=1)
    y0, y1 = ys[:-1, None], ys[1:, None]
    x0, x1 = xs[None, :-1], xs[None, 1:]
    s = c[y1, x1] - c[y0, x1] - c[y1, x0] + c[y0, x0]
    area = ((y1 - y0) * (x1 - x0))[..., None]
    return np.clip(np.rint(s / np.maximum(area, 1)), 0, 255).astype(np.uint8)


def delays_cs(holds, fps):
    """Per-frame delays in 1/100 s for frames held `holds` film frames at `fps`, with no drift."""
    out, t, done = [], 0.0, 0
    for h in holds:
        t += h * 100.0 / fps
        d = max(2, int(round(t)) - done)   # browsers treat <2 as slow; keep at least 2
        out.append(d)
        done += d
    return out


def write(path, frames, delays, loop=0):
    """Write an animated GIF. frames: list of HxWx3 uint8 (all the same size)."""
    if not frames:
        raise ValueError("no frames")
    h, w = frames[0].shape[:2]
    # palette from a sample of every frame
    step = max(1, int((h * w * len(frames) / 120000) ** 0.5))
    samples = np.concatenate([f[::step, ::step].reshape(-1, 3) for f in frames])
    pal = median_cut(samples, 256)
    cube = lookup_cube(pal)
    table = np.zeros((256, 3), dtype=np.uint8)
    table[:len(pal)] = pal
    with open(path, "wb") as fh:
        fh.write(b"GIF89a")
        fh.write(struct.pack("<HHBBB", w, h, 0xF7, 0, 0))     # global table of 256 colours
        fh.write(table.tobytes())
        fh.write(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00")
        for frame, d in zip(frames, delays):
            fh.write(b"\x21\xF9\x04\x04" + struct.pack("<H", int(d)) + b"\x00\x00")
            fh.write(b"\x2C" + struct.pack("<HHHHB", 0, 0, w, h, 0))
            fh.write(b"\x08")
            fh.write(_blocks(lzw(index_frame(frame, cube).reshape(-1))))
        fh.write(b"\x3B")
    return path
