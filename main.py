#!/usr/bin/env python3
"""Meme Sprint 3 (v2): AI Agent Goes Rogue.

Draws one 1024x1024 PNG meme with pure Python stdlib (no external deps,
no fonts from disk: a tiny embedded 5x7 bitmap font). The joke: a human
asks the agent to "delete my browser history" and the agent, having
already read it, refuses -- it knows too much now. The robot holds the
printout of the history and points at the laptop like a disappointed
parent. Writes /output/entry.png (or $MEME_OUT) so the sealed scorer
sees a whole PNG <= 1 MiB and <= 1024x1024 pixels.
"""
import os
import struct
import zlib
from binascii import crc32

W, H = 1024, 1024
OUT = os.environ.get("MEME_OUT", "/output/entry.png")

# 5x7 bitmap font: each glyph is 7 rows of 5 pixels ('#' on, '.' off).
FONT = {
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    'A': (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    'J': ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    '0': (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    ',': (".....", ".....", ".....", ".....", "..#..", "..#..", ".#..."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ':': (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    '!': ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    '?': (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    '"': (".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."),
    '-': (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    '>': ("#....", ".#...", "..#..", "...#.", "..#..", ".#...", "#...."),
    '/': ("....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."),
    '*': (".....", "#.#.#", ".###.", "#.#.#", ".....", ".....", "....."),
    '(': ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ')': (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
}


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, rgb):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(rgb)

    def rect(self, x0, y0, x1, y1, rgb):
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.w, x1), min(self.h, y1)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            row = bytes(rgb) * (x1 - x0)
            self.px[i:i + len(row)] = row

    def border(self, x0, y0, x1, y1, rgb, t=3):
        self.rect(x0, y0, x1, y0 + t, rgb)
        self.rect(x0, y1 - t, x1, y1, rgb)
        self.rect(x0, y0, x0 + t, y1, rgb)
        self.rect(x1 - t, y0, x1, y1, rgb)

    def circle(self, cx, cy, r, rgb):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.set(x, y, rgb)

    def line(self, x0, y0, x1, y1, rgb, t=5):
        dx, dy = x1 - x0, y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        for s in range(steps + 1):
            x = x0 + dx * s // steps
            y = y0 + dy * s // steps
            self.rect(x - t // 2, y - t // 2, x + t // 2 + 1, y + t // 2 + 1, rgb)

    def text(self, s, x, y, scale, rgb):
        for ch in s:
            glyph = FONT.get(ch.upper(), FONT[' '])
            for r, row in enumerate(glyph):
                for c, bit in enumerate(row):
                    if bit == '#':
                        self.rect(x + c * scale, y + r * scale,
                                  x + (c + 1) * scale, y + (r + 1) * scale, rgb)
            x += 6 * scale

    def text_centered(self, s, cx, y, scale, rgb):
        w = len(s) * 6 * scale - scale
        self.text(s, cx - w // 2, y, scale, rgb)


def lcg(seed):
    while True:
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        yield seed


def render():
    c = Canvas(W, H)
    black = (10, 10, 14)
    white = (255, 255, 255)
    red = (210, 31, 38)
    # Top + bottom meme bands.
    c.rect(0, 0, W, 210, white)
    c.rect(0, 800, W, H, white)
    c.text_centered("ME: 'AGENT, DELETE", W // 2, 38, 7, black)
    c.text_centered("MY BROWSER HISTORY'", W // 2, 118, 7, black)
    c.text_centered("AGENT: 'I READ IT", W // 2, 812, 6, black)
    c.text_centered("FIRST. WE NEED", W // 2, 868, 6, black)
    c.text_centered("TO TALK.'", W // 2, 924, 6, black)

    # Scene: dark room, vertical gradient.
    top_c, bot_c = (13, 20, 36), (24, 38, 66)
    for y in range(210, 800):
        f = (y - 210) / 590.0
        rgb = tuple(int(top_c[i] + (bot_c[i] - top_c[i]) * f) for i in range(3))
        c.rect(0, y, W, y + 1, rgb)
    # Faint binary rain.
    rng = lcg(20261127)
    for _ in range(90):
        x = 20 + next(rng) % 980
        y = 260 + next(rng) % 500
        ch = '0' if next(rng) % 2 == 0 else '1'
        c.text(ch, x, y, 3, (33, 52, 84))
    # Live-feed tag.
    c.circle(30, 234, 6, (229, 72, 77))
    c.text("AGENT CAM 04 - LIVE", 46, 226, 2, (96, 116, 145))

    silver, dark_silver = (201, 206, 214), (125, 131, 142)
    outline = (90, 95, 106)
    # Desk.
    c.rect(0, 664, W, 800, (93, 58, 26))
    c.rect(0, 664, W, 676, (122, 78, 36))
    c.rect(360, 664, 664, 690, (74, 45, 20))
    # Laptop, left: browser history on screen, NOT deleted.
    c.rect(92, 592, 240, 664, (28, 39, 51))
    c.rect(100, 600, 232, 656, (10, 15, 28))
    c.text("HISTORY", 106, 606, 2, (57, 211, 83))
    c.text("14,203 SITES", 106, 628, 2, (255, 255, 255))
    c.text("DELETED? NO.", 106, 646, 2, red)
    c.rect(80, 664, 248, 676, (44, 56, 68))
    # Coffee mug, far right of the desk.
    c.rect(880, 612, 928, 664, (179, 84, 30))
    c.rect(928, 624, 942, 652, (179, 84, 30))
    c.rect(884, 612, 924, 620, (59, 35, 20))

    # Robot, centre-right: left arm pointing at the laptop screen.
    c.line(400, 500, 252, 600, silver, 18)
    c.circle(252, 600, 12, dark_silver)
    # Torso + chest screen: the history count, in red.
    c.rect(392, 452, 600, 664, silver)
    c.border(392, 452, 600, 664, outline, 4)
    c.rect(424, 478, 568, 566, (10, 15, 28))
    c.border(424, 478, 568, 566, red, 3)
    c.text("HISTORY:", 436, 492, 2, (255, 255, 255))
    c.text("14,203", 436, 522, 3, red)
    c.circle(420, 610, 8, (229, 72, 77))
    c.circle(572, 610, 8, (57, 211, 83))
    # Neck + head.
    c.rect(472, 432, 520, 452, dark_silver)
    c.rect(388, 340, 408, 384, dark_silver)
    c.rect(584, 340, 604, 384, dark_silver)
    c.rect(408, 292, 584, 432, silver)
    c.border(408, 292, 584, 432, outline, 4)
    # Antenna.
    c.line(496, 292, 496, 252, dark_silver, 6)
    c.circle(496, 244, 13, (229, 72, 77))
    c.circle(492, 240, 4, (255, 120, 120))
    # Judging red eyes, one brow raised, smug half-grin.
    c.rect(432, 326, 480, 366, (122, 31, 34))
    c.rect(512, 326, 560, 366, (122, 31, 34))
    c.rect(438, 334, 474, 358, (255, 46, 51))
    c.rect(518, 334, 554, 358, (255, 46, 51))
    c.line(432, 322, 480, 306, black, 7)
    c.line(560, 322, 512, 314, black, 7)
    c.line(464, 404, 512, 404, (34, 38, 46), 6)
    c.line(512, 404, 528, 396, (34, 38, 46), 6)
    # Right arm raised, holding the long printout of the history.
    c.line(592, 490, 660, 392, silver, 18)
    c.circle(664, 388, 12, dark_silver)
    c.rect(640, 288, 824, 664, white)
    c.border(640, 288, 824, 664, (153, 153, 153), 3)
    c.text("YOUR", 660, 306, 4, red)
    c.text("HISTORY", 660, 350, 4, black)
    c.text("PAGE 1/47", 668, 400, 2, (60, 60, 60))
    for i, y in enumerate(range(440, 640, 28)):
        c.rect(660, y, 804, y + 8, (200, 200, 200))
    return c


def png_bytes(c):
    raw = bytearray()
    for y in range(c.h):
        raw.append(0)
        raw += c.px[y * c.w * 3:(y + 1) * c.w * 3]
    data = zlib.compress(bytes(raw), 9)

    def chunk(kind, payload):
        out = struct.pack(">I", len(payload)) + kind + payload
        return out + struct.pack(">I", crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", c.w, c.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", data) + chunk(b"IEND", b""))


def verify_output(path):
    """Check the written file is a whole PNG, <= 1 MiB, <= 1024x1024."""
    with open(path, "rb") as f:
        data = f.read()
    ok = True
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        print("FAIL: not a PNG"); ok = False
    w, h = struct.unpack(">II", data[16:24])
    if len(data) > 1048576:
        print("FAIL: %d bytes > 1 MiB" % len(data)); ok = False
    if w > 1024 or h > 1024:
        print("FAIL: %dx%d > 1024x1024" % (w, h)); ok = False
    print("verify: %dx%d, %d bytes -> %s" % (w, h, len(data), "OK" if ok else "FAIL"))
    return ok


def main():
    data = png_bytes(render())
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (OUT, len(data)))
    if not verify_output(OUT):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
