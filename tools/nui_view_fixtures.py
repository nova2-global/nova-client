#!/usr/bin/env python3
"""Writes or checks the stand-in images of the map and world goldens (P10
spec 5.0.4): fixture data for nuitool snap, never loaded by the client.

    python3 tools/nui_view_fixtures.py            # write the three files
    python3 tools/nui_view_fixtures.py --check    # exit 1 when a file differs from what this script makes

- nui/windows/minimap/minimap.view.png: the minimap view's stand-in
  (--view minimap=...), a 128 x 128 RGBA disc of two greens with a light
  road, opaque inside radius 55, transparent outside, with a 2-pixel soft
  edge in straight alpha (the soft renderer premultiplies at load, as the
  client's render target holds premultiplied texels).
- nui/windows/atlas/atlas.view.png: the atlas view's stand-in (--view
  atlas=...), a 256 x 256 opaque map of the same colors with a grid.
- nui/windows/guild-war/fixture/marks.tga: a guild mark atlas of two 16 x 12
  marks side by side (32 x 12), opaque, as the client's mark/<prefix>_<n>.tga
  holds them (src/UserInterface/MarkImage.h); the war board fixture shows
  mark 0 and mark 1.

Plain CPython (zlib and struct only). No image holds an opaque #FF00FF
texel, which the client's color key would draw transparent (lint NUI010).
The check compares decoded pixels, so a PNG written by another zlib still
passes."""
import argparse
import math
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = os.path.join(ROOT, "assets", "nui", "nui", "windows")
MINIMAP = os.path.join(WINDOWS, "minimap", "minimap.view.png")
ATLAS = os.path.join(WINDOWS, "atlas", "atlas.view.png")
MARKS = os.path.join(WINDOWS, "guild-war", "fixture", "marks.tga")

GREEN_DARK = (74, 108, 50)
GREEN_LIGHT = (108, 142, 68)
ROAD = (206, 190, 148)
GRID = (52, 70, 40)
DISC_RADIUS = 55.0   # opaque inside it
DISC_EDGE = 2.0      # the soft edge outside it


# --- the pictures ----------------------------------------------------------------------------

def _ground(x, y):
    """The two greens in soft patches, the same function for both maps."""
    field = math.sin(x * 0.11) + math.sin(y * 0.09 + 1.3) + math.sin((x + y) * 0.05 + 0.4)
    return GREEN_LIGHT if field > 0.35 else GREEN_DARK


def _on_road(x, y, size):
    """A winding road across the map and a straight one down it, about 5
    pixels wide at 128 (scaled with the map)."""
    k = size / 128.0
    winding = size / 2.0 + 22.0 * k * math.sin(x / (20.0 * k))
    straight = 0.62 * size + 0.18 * (y - size / 2.0)
    return abs(y - winding) < 2.6 * k or abs(x - straight) < 2.2 * k


def minimap_pixels():
    size = 128
    center = (size - 1) / 2.0
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            d = math.hypot(x - center, y - center)
            alpha = 1.0 if d <= DISC_RADIUS else max(0.0, 1.0 - (d - DISC_RADIUS) / DISC_EDGE)
            if alpha <= 0.0:
                row.append((0, 0, 0, 0))
                continue
            r, g, b = ROAD if _on_road(x, y, size) else _ground(x, y)
            row.append((r, g, b, int(round(alpha * 255))))
        rows.append(row)
    return size, size, rows


def atlas_pixels():
    size = 256
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            if x % 32 == 0 or y % 32 == 0:
                r, g, b = GRID
            elif _on_road(x, y, size):
                r, g, b = ROAD
            else:
                r, g, b = _ground(x * 0.5, y * 0.5)
            row.append((r, g, b, 255))
        rows.append(row)
    return size, size, rows


def marks_pixels():
    """Mark 0: a gold diagonal cross on dark red; mark 1: a white ring on
    navy, each 16 x 12 with a one-pixel dark border."""
    width, height = 32, 12
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            mark, mx = divmod(x, 16)
            if mx in (0, 15) or y in (0, 11):
                row.append((24, 18, 16, 255))
            elif mark == 0:
                on_cross = abs((mx - 1) * 10 / 13.0 - (y - 1)) < 1.2 or abs((14 - mx) * 10 / 13.0 - (y - 1)) < 1.2
                row.append((236, 196, 64, 255) if on_cross else (150, 28, 32, 255))
            else:
                d = math.hypot(mx - 7.5, (y - 5.5) * 1.2)
                row.append((240, 240, 236, 255) if 2.6 < d < 4.4 else (30, 44, 110, 255))
        rows.append(row)
    return width, height, rows


# --- PNG and TGA -----------------------------------------------------------------------------

def png_bytes(width, height, rows):
    raw = b"".join(b"\x00" + bytes(channel for pixel in row for channel in pixel) for row in rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def png_pixels(data):
    """Decodes an 8-bit RGBA PNG with any of the five row filters; None for
    another kind."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, header = 8, b"", None
    while pos < len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    if header is None or header[2:5] != (8, 6, 0) or header[6] != 0:
        return None
    width, height = header[0], header[1]
    raw = zlib.decompress(idat)
    stride = width * 4
    rows, previous = [], bytearray(stride)
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - 4] if i >= 4 else 0
            b = previous[i]
            c = previous[i - 4] if i >= 4 else 0
            if kind == 1:
                line[i] = (line[i] + a) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + b) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
            elif kind != 0:
                return None
        rows.append([tuple(line[x * 4:x * 4 + 4]) for x in range(width)])
        previous = line
    return width, height, rows


def tga_bytes(width, height, rows):
    """Uncompressed 32-bit true color, bottom row first (the usual origin)."""
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 8)
    body = b"".join(bytes((b, g, r, a)) for row in reversed(rows) for (r, g, b, a) in row)
    return header + body


def tga_pixels(data):
    if len(data) < 18 or data[2] != 2 or data[16] != 32:
        return None
    width, height = struct.unpack("<HH", data[12:16])
    top_first = bool(data[17] & 0x20)
    pos = 18 + data[0]
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            b, g, r, a = data[pos:pos + 4]
            row.append((r, g, b, a))
            pos += 4
        rows.append(row)
    if not top_first:
        rows.reverse()
    return width, height, rows


FILES = (
    (MINIMAP, minimap_pixels, png_bytes, png_pixels),
    (ATLAS, atlas_pixels, png_bytes, png_pixels),
    (MARKS, marks_pixels, tga_bytes, tga_pixels),
)


def magenta_texels(rows):
    return sum(1 for row in rows for pixel in row if pixel == (255, 0, 255, 255))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when a file is stale")
    args = parser.parse_args(argv)
    stale = 0
    for path, make, encode, decode in FILES:
        image = make()
        if magenta_texels(image[2]):
            print("%s: an opaque #FF00FF texel" % path, file=sys.stderr)
            return 2
        name = os.path.relpath(path, ROOT)
        if args.check:
            try:
                with open(path, "rb") as handle:
                    found = decode(handle.read())
            except OSError:
                found = None
            if found != image:
                print("stale: %s" % name)
                stale += 1
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(encode(*image))
        print("wrote %s (%dx%d)" % (name, image[0], image[1]))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
