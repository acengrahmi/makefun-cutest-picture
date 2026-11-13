#!/usr/bin/env python3
"""Cutest-picture entry, v2: an extreme close-up of a chubby baby kitten.

Design goals (from the brief): cute at one glance, soft round shapes,
huge glossy eyes, chubby proportions, exactly one charm touch (a tiny
pink bow), clean craft, and a composition bold enough to still read as
cute when the image is downscaled to about 300 px.

Pure Python standard library, no network, fully deterministic.
Renders one PNG to argv[1] (default /output/entry.png).

Technique: a float framebuffer painted with signed-distance shapes.
Every edge is anti-aliased from its distance field, so curves stay
smooth without any supersampling cost.
"""

import math
import os
import struct
import sys
import zlib

W = 800
H = 800

# Float framebuffer, one flat list per channel.
FR = [0.0] * (W * H)
FG = [0.0] * (W * H)
FB = [0.0] * (W * H)


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(c1, c2, t):
    return (lerp(c1[0], c2[0], t),
            lerp(c1[1], c2[1], t),
            lerp(c1[2], c2[2], t))


def smooth(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def blend_px(i, col, a):
    """Alpha-blend colour `col` over framebuffer pixel `i`."""
    if a <= 0.0:
        return
    ia = 1.0 - a
    FR[i] = FR[i] * ia + col[0] * a
    FG[i] = FG[i] * ia + col[1] * a
    FB[i] = FB[i] * ia + col[2] * a


def background():
    """Soft pastel backdrop: warm cream melting into pink, vignetted."""
    top = (1.000, 0.949, 0.878)
    mid = (1.000, 0.851, 0.902)
    bot = (0.984, 0.749, 0.851)
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            c = lerp3(top, mid, smooth(t / 0.55))
        else:
            c = lerp3(mid, bot, smooth((t - 0.55) / 0.45))
        base = y * W
        for x in range(W):
            dx = (x - W / 2) / (W / 2)
            dy = (y - H / 2) / (H / 2)
            v = 1.0 - 0.15 * clamp(dx * dx + dy * dy - 0.55)
            i = base + x
            FR[i] = c[0] * v
            FG[i] = c[1] * v
            FB[i] = c[2] * v


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter type 0 for every scanline
        base = y * W
        for x in range(W):
            i = base + x
            raw.append(int(clamp(FR[i]) * 255.0 + 0.5))
            raw.append(int(clamp(FG[i]) * 255.0 + 0.5))
            raw.append(int(clamp(FB[i]) * 255.0 + 0.5))
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)


# ---------------------------------------------------------------------------
# Distance-field shape primitives. Each one only visits its own bounding
# box, blends with a coverage factor derived from the signed distance to
# the shape's edge, and accepts an optional per-pixel colour function.
# ---------------------------------------------------------------------------

def ellipse(cx, cy, rx, ry, col, alpha=1.0, feather=1.4, rot=0.0,
            colorfn=None):
    """Filled ellipse; `feather` is the edge softness in pixels."""
    cr = math.cos(rot)
    sr = math.sin(rot)
    reach = max(rx, ry) + feather * 2.0 + 2.0
    x0 = max(0, int(cx - reach))
    x1 = min(W - 1, int(cx + reach))
    y0 = max(0, int(cy - reach))
    y1 = min(H - 1, int(cy + reach))
    mn = min(rx, ry)
    for y in range(y0, y1 + 1):
        py = y + 0.5 - cy
        base = y * W
        for x in range(x0, x1 + 1):
            px = x + 0.5 - cx
            if rot:
                qx = px * cr + py * sr
                qy = -px * sr + py * cr
            else:
                qx, qy = px, py
            d = math.sqrt((qx / rx) * (qx / rx) + (qy / ry) * (qy / ry))
            sd = (d - 1.0) * mn  # approximate signed distance, in pixels
            cov = clamp(0.5 - sd / feather)
            if cov <= 0.0:
                continue
            c = colorfn(x + 0.5, y + 0.5) if colorfn is not None else col
            blend_px(base + x, c, cov * alpha)


def capsule(x1, y1, x2, y2, r, col, alpha=1.0, feather=1.4):
    """Thick round-capped line segment (used for the forehead stripes)."""
    reach = r + feather * 2.0 + 2.0
    x0 = max(0, int(min(x1, x2) - reach))
    x1b = min(W - 1, int(max(x1, x2) + reach))
    y0 = max(0, int(min(y1, y2) - reach))
    y1b = min(H - 1, int(max(y1, y2) + reach))
    dx = x2 - x1
    dy = y2 - y1
    seg2 = dx * dx + dy * dy
    for y in range(y0, y1b + 1):
        py = y + 0.5
        base = y * W
        for x in range(x0, x1b + 1):
            px = x + 0.5
            if seg2 > 0.0:
                t = clamp(((px - x1) * dx + (py - y1) * dy) / seg2)
            else:
                t = 0.0
            qx = x1 + dx * t
            qy = y1 + dy * t
            sd = math.hypot(px - qx, py - qy) - r
            cov = clamp(0.5 - sd / feather)
            if cov > 0.0:
                blend_px(base + x, col, cov * alpha)


def arc(cx, cy, r, a0, a1, width, col, alpha=1.0, feather=1.2):
    """Ring segment between angles a0..a1 (radians, y-axis pointing down,
    so angles in (0, pi) sweep the bottom half of the circle)."""
    reach = r + width + feather * 2.0 + 2.0
    x0 = max(0, int(cx - reach))
    x1 = min(W - 1, int(cx + reach))
    y0 = max(0, int(cy - reach))
    y1 = min(H - 1, int(cy + reach))
    half = width / 2.0
    for y in range(y0, y1 + 1):
        py = y + 0.5 - cy
        base = y * W
        for x in range(x0, x1 + 1):
            px = x + 0.5 - cx
            d = math.hypot(px, py)
            sd = abs(d - r) - half
            if sd > feather:
                continue
            ang = math.atan2(py, px)
            if ang < a0 or ang > a1:
                # allow the caps to round off near the segment ends
                ea = min(abs(ang - a0), abs(ang - a1)) * r
                if ea > half + feather:
                    continue
                sd = max(sd, ea - half)
            cov = clamp(0.5 - sd / feather)
            if cov > 0.0:
                blend_px(base + x, col, cov * alpha)


# ---------------------------------------------------------------------------
# The kitten. Painted back to front: backdrop sparkles, ears, head,
# shading, stripes, muzzle, blush, eyes, nose, mouth, and finally the
# single charm touch -- a tiny pink bow on the right ear.
# ---------------------------------------------------------------------------

FUR = (0.992, 0.706, 0.427)       # warm orange-cream fur
FUR_DEEP = (0.945, 0.545, 0.235)  # stripe orange
CREAM = (1.000, 0.937, 0.835)     # muzzle cream
PINK = (1.000, 0.478, 0.639)      # bow / nose pink family


def shade_head():
    """Roundness for the head: a soft light from upper centre and a
    gentle darkening toward the rim. Masked by the head ellipse."""
    cx, cy, rx, ry = 400.0, 445.0, 335.0, 305.0
    x0 = max(0, int(cx - rx - 2))
    x1 = min(W - 1, int(cx + rx + 2))
    y0 = max(0, int(cy - ry - 2))
    y1 = min(H - 1, int(cy + ry + 2))
    for y in range(y0, y1 + 1):
        py = y + 0.5
        base = y * W
        for x in range(x0, x1 + 1):
            px = x + 0.5
            d = math.sqrt(((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2)
            if d > 1.0:
                continue
            i = base + x
            gx = (px - 400.0) / 300.0
            gy = (py - 350.0) / 300.0
            glow = math.exp(-(gx * gx + gy * gy))
            rim = smooth((d - 0.80) / 0.20)
            shade = 1.0 - 0.13 * rim
            FR[i] = clamp(FR[i] * shade + 0.10 * glow)
            FG[i] = clamp(FG[i] * shade + 0.085 * glow)
            FB[i] = clamp(FB[i] * shade + 0.055 * glow)


def draw_eye(cx, cy):
    """One huge glossy eye: radial iris, dark pupil, amber crescent
    along the bottom, then two catchlights and a tiny sparkle."""
    R = 82.0

    def iris(px, py):
        d = math.hypot(px - cx, py - cy) / R
        return lerp3((0.472, 0.298, 0.153), (0.118, 0.063, 0.035),
                     smooth(d))

    ellipse(cx, cy, R, R * 1.06, None, 1.0, 1.6, colorfn=iris)
    # top lid shadow gives the eye a gentle, sleepy-cute weight
    arc(cx, cy, R * 0.99, -math.pi * 0.92, -math.pi * 0.08, 15.0,
        (0.10, 0.05, 0.03), 0.35, 6.0)
    # pupil
    ellipse(cx, cy + 5, 40, 49, (0.045, 0.027, 0.020), 1.0, 1.6)
    # warm crescent reflection along the bottom of the iris
    arc(cx, cy, R * 0.70, math.pi * 0.22, math.pi * 0.78, 8.0,
        (0.98, 0.62, 0.28), 0.26, 3.5)
    # catchlights
    ellipse(cx - 27, cy - 33, 24, 24, (1.0, 1.0, 1.0), 0.96, 1.6)
    ellipse(cx + 23, cy + 28, 11, 11, (1.0, 1.0, 1.0), 0.85, 1.4)
    ellipse(cx + 31, cy - 41, 5, 5, (1.0, 1.0, 1.0), 0.90, 1.2)


def draw_bow(cx, cy):
    """The one charm touch: a small pink bow, drawn with a soft drop
    shadow, two rotated wings, a knot, and a knot highlight."""
    shadow = (0.55, 0.20, 0.32)
    ellipse(cx - 34 + 4, cy + 6, 40, 24, shadow, 0.30, 2.5, rot=-0.45)
    ellipse(cx + 34 + 4, cy + 6, 40, 24, shadow, 0.30, 2.5, rot=0.45)
    wing_dark = (0.929, 0.337, 0.510)
    ellipse(cx - 34, cy, 40, 24, wing_dark, 1.0, 1.6, rot=-0.45)
    ellipse(cx + 34, cy, 40, 24, wing_dark, 1.0, 1.6, rot=0.45)
    wing = (1.000, 0.478, 0.639)
    ellipse(cx - 36, cy - 3, 33, 18, wing, 1.0, 1.6, rot=-0.45)
    ellipse(cx + 36, cy - 3, 33, 18, wing, 1.0, 1.6, rot=0.45)
    ellipse(cx, cy, 16, 15, (0.965, 0.302, 0.498), 1.0, 1.5)
    ellipse(cx - 4, cy - 5, 6, 4, (1.0, 1.0, 1.0), 0.55, 1.2, rot=-0.4)


def draw_kitten():
    background()
    # dreamy out-of-focus dots floating in the backdrop
    ellipse(105, 118, 46, 46, (1.0, 1.0, 1.0), 0.16, 55.0)
    ellipse(706, 84, 33, 33, (1.0, 1.0, 1.0), 0.14, 45.0)
    ellipse(84, 648, 40, 40, (1.0, 1.0, 1.0), 0.11, 50.0)
    ellipse(722, 668, 48, 48, (1.0, 1.0, 1.0), 0.11, 55.0)
    # soft contact shadow under the chin
    ellipse(400, 764, 295, 26, (0.83, 0.42, 0.52), 0.20, 26.0)

    # ears, tucked in so they peek from behind the head rather than
    # sticking out like lollipops
    ellipse(140, 226, 94, 112, FUR, 1.0, 1.6, rot=-0.33)
    ellipse(660, 226, 94, 112, FUR, 1.0, 1.6, rot=0.33)
    ellipse(148, 234, 46, 62, (0.992, 0.639, 0.671), 0.90, 2.2, rot=-0.33)
    ellipse(652, 234, 46, 62, (0.992, 0.639, 0.671), 0.90, 2.2, rot=0.33)

    # the big round chubby head
    ellipse(400, 445, 335, 305, FUR, 1.0, 1.6)
    shade_head()

    # faint tabby stripes on the forehead
    capsule(400, 192, 400, 238, 12, FUR_DEEP, 0.26, 4.0)
    capsule(350, 204, 336, 244, 11, FUR_DEEP, 0.22, 4.0)
    capsule(450, 204, 464, 244, 11, FUR_DEEP, 0.22, 4.0)

    # muzzle and blush
    ellipse(400, 580, 152, 94, CREAM, 0.95, 2.0)
    ellipse(168, 548, 58, 30, (1.0, 0.620, 0.710), 0.50, 26.0)
    ellipse(632, 548, 58, 30, (1.0, 0.620, 0.710), 0.50, 26.0)

    # huge glossy eyes
    draw_eye(262, 415)
    draw_eye(538, 415)

    # tiny pink nose with a pinpoint highlight
    ellipse(400, 548, 27, 19, (0.996, 0.475, 0.580), 1.0, 1.5)
    ellipse(391, 541, 9, 5, (1.0, 1.0, 1.0), 0.55, 1.2, rot=-0.4)
    # the little "w" kitten mouth under the nose
    mouth = (0.663, 0.373, 0.263)
    capsule(400, 562, 400, 574, 3, mouth, 0.55, 1.2)
    arc(381, 574, 17, math.pi * 0.12, math.pi * 0.92, 4.5, mouth, 0.75, 1.2)
    arc(419, 574, 17, math.pi * 0.08, math.pi * 0.88, 4.5, mouth, 0.75, 1.2)

    # the single charm: a tiny bow riding the right ear
    draw_bow(636, 140)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    draw_kitten()
    write_png(path)


if __name__ == "__main__":
    main()
