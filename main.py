#!/usr/bin/env python3
"""
Make the cutest picture - make.fun bounty entry.
A chubby round kitten with huge glossy eyes, blush, soft pastel palette.
Pure Python stdlib only. Manual PNG encoder (zlib + struct).
Deterministic: no randomness, no timestamps, fixed math only.
"""
import sys
import os
import math
import zlib
import struct

W = 800
H = 800

# ---------- Framebuffer ----------
fb = bytearray(W * H * 3)

def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        fb[i] = r; fb[i+1] = g; fb[i+2] = b

def blend_px(x, y, r, g, b, a):
    """a in 0..1 : 1 = opaque new color"""
    if 0 <= x < W and 0 <= y < H and a > 0:
        if a >= 1.0:
            set_px(x, y, r, g, b)
            return
        i = (y * W + x) * 3
        inv = 1.0 - a
        fb[i]   = int(fb[i]   * inv + r * a)
        fb[i+1] = int(fb[i+1] * inv + g * a)
        fb[i+2] = int(fb[i+2] * inv + b * a)

def get_px(x, y):
    i = (y * W + x) * 3
    return fb[i], fb[i+1], fb[i+2]

# ---------- Shapes ----------
def filled_circle(cx, cy, r, color, soft=1.5):
    cr, cg, cb = color
    x0 = int(cx - r - 2); x1 = int(cx + r + 2)
    y0 = int(cy - r - 2); y1 = int(cy + r + 2)
    for y in range(max(0, y0), min(H, y1+1)):
        for x in range(max(0, x0), min(W, x1+1)):
            d = math.hypot(x - cx, y - cy)
            if d <= r - soft:
                set_px(x, y, cr, cg, cb)
            elif d <= r + soft:
                a = 0.5 - (d - r) / (2*soft)
                blend_px(x, y, cr, cg, cb, max(0.0, min(1.0, a + 0.5 if False else (r + soft - d)/(2*soft))))

def filled_ellipse(cx, cy, rx, ry, color, soft=1.5):
    cr, cg, cb = color
    x0 = int(cx - rx - 2); x1 = int(cx + rx + 2)
    y0 = int(cy - ry - 2); y1 = int(cy + ry + 2)
    for y in range(max(0, y0), min(H, y1+1)):
        for x in range(max(0, x0), min(W, x1+1)):
            dx = (x - cx) / rx; dy = (y - cy) / ry
            d = dx*dx + dy*dy
            if d <= 0.92:
                set_px(x, y, cr, cg, cb)
            elif d <= 1.08:
                a = (1.08 - d) / 0.16
                blend_px(x, y, cr, cg, cb, max(0.0, min(1.0, a)))

def filled_ellipse_alpha(cx, cy, rx, ry, color, alpha):
    cr, cg, cb = color
    x0 = int(cx - rx - 1); x1 = int(cx + rx + 1)
    y0 = int(cy - ry - 1); y1 = int(cy + ry + 1)
    for y in range(max(0, y0), min(H, y1+1)):
        for x in range(max(0, x0), min(W, x1+1)):
            dx = (x - cx) / rx; dy = (y - cy) / ry
            if dx*dx + dy*dy <= 1.0:
                blend_px(x, y, cr, cg, cb, alpha)

def polygon(points, color):
    cr, cg, cb = color
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    x0 = int(min(xs)); x1 = int(max(xs)); y0 = int(min(ys)); y1 = int(max(ys))
    n = len(points)
    for y in range(max(0, y0), min(H, y1+1)):
        for x in range(max(0, x0), min(W, x1+1)):
            # point in polygon (ray casting)
            inside = False
            j = n - 1
            for i in range(n):
                xi, yi = points[i]; xj, yj = points[j]
                if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
                    inside = not inside
                j = i
            if inside:
                set_px(x, y, cr, cg, cb)

def thick_line(x0, y0, x1, y1, width, color):
    cr, cg, cb = color
    steps = int(max(abs(x1-x0), abs(y1-y0))) + 1
    r = width / 2.0
    for s in range(steps+1):
        t = s / steps if steps else 0
        cx = x0 + (x1-x0)*t; cy = y0 + (y1-y0)*t
        filled_circle(cx, cy, r, color, soft=1.0)

def draw_heart(cx, cy, s, color):
    # s = scale; heart via two circles + triangle polygon
    filled_circle(cx - s*0.45, cy - s*0.25, s*0.52, color, soft=1.2)
    filled_circle(cx + s*0.45, cy - s*0.25, s*0.52, color, soft=1.2)
    polygon([(cx - s*0.88, cy - s*0.05), (cx + s*0.88, cy - s*0.05), (cx, cy + s*1.05)], color)

def draw_star(cx, cy, r, color, alpha=0.9):
    # 4-point sparkle star
    pts = []
    for i in range(8):
        ang = math.pi/4 * i
        rad = r if i % 2 == 0 else r*0.28
        pts.append((cx + math.cos(ang)*rad, cy + math.sin(ang)*rad))
    # draw via polygon with blending approximated by solid then smaller?
    # Use polygon solid with alpha by blending each pixel manually: fallback solid
    polygon(pts, color)

# ---------- Scene ----------
def draw():
    # Background: vertical pastel gradient cream -> pink -> mint hint at bottom
    top = (255, 243, 224)     # warm cream
    mid = (255, 214, 232)     # soft pink
    bot = (198, 240, 224)     # mint
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            k = t / 0.55
            r = int(top[0] + (mid[0]-top[0])*k)
            g = int(top[1] + (mid[1]-top[1])*k)
            b = int(top[2] + (mid[2]-top[2])*k)
        else:
            k = (t - 0.55) / 0.45
            r = int(mid[0] + (bot[0]-mid[0])*k)
            g = int(mid[1] + (bot[1]-mid[1])*k)
            b = int(mid[2] + (bot[2]-mid[2])*k)
        base = y * W * 3
        for x in range(W):
            i = base + x*3
            fb[i] = r; fb[i+1] = g; fb[i+2] = b

    # Soft bokeh dots (fixed positions)
    bokeh = [(110,120,42,(255,255,255)), (680,110,36,(255,255,255)), (720,300,24,(255,255,255)),
             (70,340,26,(255,255,255)), (150,620,30,(255,255,255)), (660,640,34,(255,255,255)),
             (580,80,20,(255,220,240)), (210,90,18,(255,220,240))]
    for (x,y,r,c) in bokeh:
        filled_ellipse_alpha(x, y, r, r, c, 0.35)

    # Ground shadow + soft grass mound
    filled_ellipse(400, 682, 290, 62, (178, 232, 205), soft=2)
    filled_ellipse_alpha(400, 688, 215, 30, (90, 160, 120), 0.22)

    # Tail (behind body, curled on right)
    # thick curved tail approximated by circles along arc
    for i in range(21):
        t = i / 20.0
        ang = -0.9 + t * 1.9
        cx = 545 + math.cos(ang) * 95
        cy = 625 + math.sin(ang) * 42
        filled_circle(cx, cy, 26, (224, 138, 82), soft=1.2)
    for i in range(21):
        t = i / 20.0
        ang = -0.9 + t * 1.9
        cx = 545 + math.cos(ang) * 95
        cy = 625 + math.sin(ang) * 42
        filled_circle(cx, cy, 19, (255, 183, 120), soft=1.2)
    # tail tip
    filled_circle(632, 600, 20, (255, 240, 220))

    OUTLINE = (146, 92, 62)
    FUR = (255, 183, 120)       # peach-orange
    FUR_LIGHT = (255, 214, 165)
    CREAM = (255, 242, 225)

    # Ears (outline then fur then inner pink) - rounded triangles via polygons + circles at tips
    # Left ear
    polygon([(272,238),(218,92),(368,150)], OUTLINE)
    polygon([(276,224),(232,112),(352,158)], FUR)
    polygon([(278,196),(252,136),(322,162)], (255, 158, 182))
    filled_circle(232, 112, 16, FUR)
    # Right ear
    polygon([(528,238),(582,92),(432,150)], OUTLINE)
    polygon([(524,224),(568,112),(448,158)], FUR)
    polygon([(522,196),(548,136),(478,162)], (255, 158, 182))
    filled_circle(568, 112, 16, FUR)

    # Body (chubby, behind head)
    filled_ellipse(400, 618, 172, 118, OUTLINE)
    filled_ellipse(400, 618, 162, 108, FUR)
    filled_ellipse(400, 632, 100, 76, CREAM)  # belly

    # Head (big round)
    filled_circle(400, 368, 198, OUTLINE)
    filled_circle(400, 368, 188, FUR)
    # Forehead / muzzle cream patch
    filled_ellipse(400, 438, 118, 82, CREAM)
    filled_ellipse(400, 300, 130, 92, FUR_LIGHT)
    filled_ellipse(400, 438, 118, 82, CREAM)

    # Orange tabby stripes on forehead (soft short thick lines)
    for (x0,y0,x1,y1) in [(368,196,362,238),(400,188,400,232),(432,196,438,238)]:
        thick_line(x0,y0,x1,y1,13,(232,148,88))
    # Cheek patches
    filled_ellipse_alpha(252, 410, 34, 48, (255,214,165), 0.55)
    filled_ellipse_alpha(548, 410, 34, 48, (255,214,165), 0.55)

    # Blush (big, soft pink)
    filled_ellipse_alpha(268, 452, 46, 26, (255, 110, 155), 0.55)
    filled_ellipse_alpha(532, 452, 46, 26, (255, 110, 155), 0.55)
    filled_ellipse_alpha(268, 452, 30, 16, (255, 130, 170), 0.5)
    filled_ellipse_alpha(532, 452, 30, 16, (255, 130, 170), 0.5)

    # HUGE glossy eyes
    for ecx in (322, 478):
        # white sclera hint / outline
        filled_circle(ecx, 378, 52, (92, 52, 38))
        filled_circle(ecx, 378, 47, (52, 32, 28))       # dark iris base
        filled_circle(ecx, 382, 40, (78, 44, 32))        # warm brown iris
        filled_circle(ecx, 386, 27, (28, 18, 16))        # pupil
        # glossy highlights (key for cuteness + readability at 300px)
        filled_circle(ecx - 14, 362, 14, (255,255,255))
        filled_circle(ecx + 12, 392, 8, (255,255,255))
        filled_circle(ecx + 16, 360, 5, (180, 230, 255))
        # lower sparkle
        filled_circle(ecx - 4, 402, 4, (255,255,255))
    # Upper eyelid lash hint: small arc of dark circles along top of eyes
    for ecx in (322, 478):
        for i in range(9):
            ang = math.pi * (1.08 + 0.84 * (i/8.0))  # top arc
            lx = ecx + math.cos(ang) * 50
            ly = 378 + math.sin(ang) * 50
            filled_circle(lx, ly, 5, (92,52,38), soft=1.0)

    # Tiny eyebrows raised (cute surprise)
    thick_line(288, 302, 342, 290, 7, (146,92,62))
    thick_line(458, 290, 514, 302, 7, (146,92,62))

    # Nose: small pink heart-ish triangle
    polygon([(386,428),(414,428),(400,446)], (240, 100, 130))
    filled_circle(393, 429, 7, (240,100,130)); filled_circle(407, 429, 7, (240,100,130))
    filled_circle(396, 426, 3, (255,200,215))

    # Mouth: tiny 'w' - two small arcs approximated by thick lines
    thick_line(400, 446, 382, 458, 6, (146,92,62))
    thick_line(382, 458, 368, 448, 6, (146,92,62))
    thick_line(400, 446, 418, 458, 6, (146,92,62))
    thick_line(418, 458, 432, 448, 6, (146,92,62))
    # tiny open smile tongue
    filled_ellipse(400, 462, 12, 8, (255,150,170))

    # Whiskers (thin, soft brown)
    for (x0,y0,x1,y1) in [(238,432,168,420),(240,452,172,458),(242,472,182,492),
                          (562,432,632,420),(560,452,628,458),(558,472,618,492)]:
        thick_line(x0,y0,x1,y1,4,(178,130,95))

    # Paws (front, chubby, with toe beans)
    for pcx in (312, 488):
        filled_ellipse(pcx, 690, 58, 36, OUTLINE)
        filled_ellipse(pcx, 688, 52, 30, FUR_LIGHT)
        # toe lines
        thick_line(pcx-18, 672, pcx-18, 686, 5, (196,130,85))
        thick_line(pcx+18, 672, pcx+18, 686, 5, (196,130,85))
        # pink pad
        filled_ellipse(pcx, 696, 14, 9, (255,158,182))

    # Small bell collar
    for i in range(25):
        t = i/24.0
        ang = 0.35 + t * (math.pi - 0.70)
        cx = 400 + math.cos(ang)*132
        cy = 500 + math.sin(ang)*58
        filled_circle(cx, cy, 10, (110, 200, 220), soft=1.0)
    filled_circle(400, 566, 20, (255, 202, 64))
    filled_circle(400, 566, 20, (255, 202, 64))
    filled_circle(394, 559, 6, (255,255,255))
    thick_line(400, 572, 400, 582, 4, (180,130,30))
    filled_circle(400, 570, 4, (120,85,20))

    # Decor: floating hearts + sparkles (story/charm)
    draw_heart(128, 232, 26, (255,110,160))
    draw_heart(676, 238, 20, (255,140,180))
    draw_heart(612, 168, 13, (255,110,160))
    draw_star(168, 520, 20, (255,205,70))
    draw_star(648, 500, 16, (255,205,70))
    draw_star(560, 92, 14, (255,180,210))
    # tiny flowers on ground
    for (fx, fy) in [(150,692),(205,716),(610,712),(652,680)]:
        for k in range(5):
            ang = 2*math.pi*k/5
            filled_circle(fx+math.cos(ang)*9, fy+math.sin(ang)*9, 7, (255,255,255), soft=1.0)
        filled_circle(fx, fy, 6, (255,202,64), soft=1.0)

# ---------- PNG encoder ----------
def png_chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    c += struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
    return c

def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter None
        start = y * W * 3
        raw.extend(fb[start:start+W*3])
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += png_chunk(b"IEND", b"")
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    draw()
    write_png(out)

if __name__ == "__main__":
    main()
