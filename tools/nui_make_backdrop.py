#!/usr/bin/env python3
"""Writes docs/ui/snapshots/backdrop.png, the synthetic world the translucent
and backdrop-blur golden cases are snapped over ("backdrop" in a case file,
nuitool snap --backdrop; P13 spec 7.7): 2560 x 1440, colored bands with fine
stripes across them, so a panel's translucency and a backdrop blur both show
(a blur smooths the stripes into the band's mean). Deterministic: the pixels
are a function of their coordinates.

    python3 tools/nui_make_backdrop.py           # write it
    python3 tools/nui_make_backdrop.py --check   # exit 1 when the committed file differs
"""
import argparse
import os
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "ui", "snapshots", "backdrop.png")
WIDTH, HEIGHT = 2560, 1440
# Band colors, top to bottom: a dusk sky, foliage, warm stone, water, earth,
# a lit wall. Muted and mid-bright, as a game world behind a window is.
BANDS = ((70, 96, 150), (52, 110, 74), (150, 118, 82), (40, 92, 120), (110, 76, 58), (170, 150, 120))
STRIPE = (232, 228, 214)   # the fine stripes: every 6th column and every 9th row, 2 px wide


def pixel(x, y):
    band = BANDS[min(len(BANDS) - 1, y * len(BANDS) // HEIGHT)]
    # A slow diagonal shade inside each band, so the bands are not flat.
    shade = ((x + y) % 512) / 511.0 - 0.5
    color = tuple(max(0, min(255, int(round(c + 26 * shade)))) for c in band)
    if x % 6 < 2 or y % 9 < 2:
        color = tuple((c + s) // 2 for c, s in zip(color, STRIPE))
    return color


def render():
    image = Image.new("RGB", (WIDTH, HEIGHT))
    image.putdata([pixel(x, y) for y in range(HEIGHT) for x in range(WIDTH)])
    return image


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when the committed file differs")
    args = parser.parse_args(argv)
    image = render()
    if args.check:
        if not os.path.isfile(OUT):
            print("nui_make_backdrop: %s is missing" % os.path.relpath(OUT, REPO), file=sys.stderr)
            return 1
        with Image.open(OUT) as committed:
            same = committed.convert("RGB").tobytes() == image.tobytes()
        print("nui_make_backdrop: %s" % ("up to date" if same else "differs; run python3 tools/nui_make_backdrop.py"))
        return 0 if same else 1
    image.save(OUT, optimize=True)
    print("nui_make_backdrop: wrote %s" % os.path.relpath(OUT, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
