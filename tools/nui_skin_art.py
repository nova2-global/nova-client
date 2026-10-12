#!/usr/bin/env python3
"""Generated skin art: white sprites with alpha, drawn from numbers.

    python3 tools/nui_skin_art.py build [--manifest FILE]
    python3 tools/nui_skin_art.py check [--manifest FILE]

A skin that needs a shape RCSS cannot draw (a 45-degree cut corner on a box
of any size) keeps a manifest, nui/skins/<skin>/art.json, that describes
each sprite by numbers. `build` draws every sprite white with alpha at each
scale of the manifest (never an upscale: the 2x sprite is drawn from the
numbers doubled), packs them into one sheet per scale with a gutter of each
sprite's own edge texels (2 px at 1x, 4 px at 2x), and writes, into the
manifest's out_dir:

    <name>-1x.png, <name>-2x.png      the sheets
    <name>-sprites.rcss               @spritesheet <name>-1x, and <name>-2x
                                      under @media (min-resolution: 1.125x)

Each sprite <id> is the sprite <name>-<id>, plus, but for a ring,
<name>-<id>-inner, the rectangle a ninepatch decorator stretches:
ninepatch(<name>-<id>, <name>-<id>-inner). The art is white, so the
skin tints it with image-color from its tokens (docs/ui/AUTHORING.md
"Adding a theme").
`check` writes nothing and exits 1 when an output differs from what
`build` would write (pixels and text; the PNG encoding may differ).
Without --manifest both commands take every nui/skins/*/art.json that
lists sprites.

The manifest:

    {"name": "cyberpunk", "out_dir": "assets/nui/nui/skins/cyberpunk", "scales": [1, 2],
     "sheet_width": 256,
     "sprites": [
        {"id": "panel", "kind": "chamfer-fill", "size": 48, "chamfer": 10, "corners": ["tl", "br"], "alpha": 1.0},
        {"id": "panel-edge", "kind": "chamfer-edge", "size": 64, "chamfer": 10, "corners": ["tl", "br"],
         "line": 1, "glow": 6, "glow_alpha": 0.45}]}

Lengths are pixels at 1x. A chamfer-fill is a square of `size` whose listed
corners (tl, tr, bl, br) are cut at 45 degrees, `chamfer` pixels along each
side, filled at `alpha`. A chamfer-edge is the outline of that shape, `line`
pixels wide, inset by `glow` pixels from the sprite's sides, with a glow
around the line: the line's alpha blurred (a Gaussian of sigma glow / 3),
scaled so its peak is `glow_alpha`, under the line. `inner` (optional) is
the inset of the ninepatch rectangle from every side; by default it holds
the inset, the chamfer and 2 pixels, and for an edge one more glow width
(the glow bends around the chamfer's ends), so the stretched patches are
uniform along their length. A ring is a circle's outline, `line` pixels
wide, its outer edge `glow` pixels inside the sprite's sides, at `alpha`
(1 by default), with the same glow; it is drawn whole, never as a
ninepatch, so it has no -inner rectangle (a circular progress bar's
fill-image, which the element cuts by its value). `sheet_width`
(optional, 1x pixels) is the packing width, 256 by default. Every value
is drawn exactly: coverage is exact along x and sampled 16 times per
pixel along y, and the blur is computed in Python, so a build gives the
same pixels on every machine.

Exit codes: 0 success, 1 failure or stale outputs, 2 usage.
"""
import argparse
import glob
import io
import json
import math
import os
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(REPO, "assets", "nui", "nui", "skins")
COMMAND = "python3 tools/nui_skin_art.py build"
KINDS = ("chamfer-fill", "chamfer-edge", "ring")
CORNERS = ("tl", "tr", "bl", "br")
TOP_KEYS = {"$comment", "name", "out_dir", "scales", "sheet_width", "sprites"}
SPRITE_KEYS = {"chamfer-fill": {"id", "kind", "size", "chamfer", "corners", "alpha", "inner", "$comment"},
               "chamfer-edge": {"id", "kind", "size", "chamfer", "corners", "line", "glow", "glow_alpha", "inner", "$comment"},
               "ring": {"id", "kind", "size", "line", "glow", "glow_alpha", "alpha", "$comment"}}
GUTTER_1X = 2
# Rows of samples per pixel; x coverage is exact.
SUBROWS = 16
# The 2x sheet replaces the 1x one from this dp ratio up, as the classic
# skin's does (min-resolution compares the context's dp ratio, the UI scale).
THRESHOLD = "1.125x"
NAME_RE_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


class ArtError(Exception):
    pass


# --- the manifest --------------------------------------------------------------

def _number(value, low, high=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if integer and not isinstance(value, int):
        return False
    return value >= low and (high is None or value <= high)


def _name(value):
    return isinstance(value, str) and value[:1].isalpha() and value[:1].islower() and set(value) <= NAME_RE_CHARS


def validate(manifest, where="art.json"):
    """The manifest's rules; ArtError names the first one broken."""
    def need(condition, message):
        if not condition:
            raise ArtError("%s: %s" % (where, message))
    need(isinstance(manifest, dict), "an object")
    need(not set(manifest) - TOP_KEYS, "unknown key %s" % ", ".join(sorted(set(manifest) - TOP_KEYS)))
    need(_name(manifest.get("name")), "name is a skin name of lowercase letters, digits and '-'")
    need(isinstance(manifest.get("out_dir"), str) and manifest["out_dir"] and not os.path.isabs(manifest["out_dir"]),
         "out_dir is a path relative to the repository root")
    scales = manifest.get("scales")
    need(isinstance(scales, list) and scales and all(_number(s, 1, 4, integer=True) for s in scales)
         and len(set(scales)) == len(scales) and scales[0] == 1 and scales == sorted(scales),
         "scales is [1] or [1, 2] (whole numbers from 1, ascending)")
    need(len(scales) <= 2, "scales holds 1x and at most one more (the sheet the min-resolution block names)")
    need(_number(manifest.get("sheet_width", 256), 16, 4096, integer=True), "sheet_width is 16 to 4096 pixels")
    sprites = manifest.get("sprites")
    need(isinstance(sprites, list), "sprites is a list")
    ids = set()
    for sprite in sprites:
        at = "sprite %r" % (sprite.get("id") if isinstance(sprite, dict) else sprite)
        need(isinstance(sprite, dict) and sprite.get("kind") in KINDS, "%s: kind is %s" % (at, " or ".join(KINDS)))
        kind = sprite["kind"]
        need(not set(sprite) - SPRITE_KEYS[kind], "%s: unknown key %s" % (at, ", ".join(sorted(set(sprite) - SPRITE_KEYS[kind]))))
        need(_name(sprite.get("id")) and sprite["id"] not in ids, "%s: id is a unique name of lowercase letters, digits and '-'" % at)
        need(not sprite["id"].endswith("-inner"), "%s: an id ending in -inner would clash with a ninepatch rectangle" % at)
        ids.add(sprite["id"])
        need(_number(sprite.get("size"), 4, 512, integer=True), "%s: size is 4 to 512 pixels" % at)
        if kind == "ring":
            need(_number(sprite.get("line"), 0.5), "%s: line is at least 0.5 pixels" % at)
            need(_number(sprite.get("glow", 0), 0), "%s: glow is 0 or more pixels" % at)
            need(_number(sprite.get("glow_alpha", 0.0), 0.0, 1.0), "%s: glow_alpha is 0 to 1" % at)
            need(sprite.get("glow", 0) == 0 or sprite.get("glow_alpha", 0) > 0, "%s: a glow needs a glow_alpha above 0" % at)
            need(_number(sprite.get("alpha", 1.0), 0.0, 1.0) and sprite.get("alpha", 1.0) > 0, "%s: alpha is above 0 and at most 1" % at)
            need(2 * (sprite.get("glow", 0) + sprite["line"]) < sprite["size"], "%s: the line and the glow do not fit the sprite" % at)
            continue
        corners = sprite.get("corners")
        need(isinstance(corners, list) and all(c in CORNERS for c in corners) and len(set(corners)) == len(corners),
             "%s: corners lists tl, tr, bl and br, each at most once" % at)
        need(_number(sprite.get("chamfer"), 0), "%s: chamfer is 0 or more pixels" % at)
        if kind == "chamfer-fill":
            need(_number(sprite.get("alpha"), 0.0, 1.0) and sprite["alpha"] > 0, "%s: alpha is above 0 and at most 1" % at)
        else:
            need(_number(sprite.get("line"), 0.5) , "%s: line is at least 0.5 pixels" % at)
            need(_number(sprite.get("glow", 0), 0), "%s: glow is 0 or more pixels" % at)
            need(_number(sprite.get("glow_alpha", 0.0), 0.0, 1.0), "%s: glow_alpha is 0 to 1" % at)
            need(sprite.get("glow", 0) == 0 or sprite.get("glow_alpha", 0) > 0, "%s: a glow needs a glow_alpha above 0" % at)
        pad = sprite.get("glow", 0) if kind == "chamfer-edge" else 0
        inner = sprite.get("inner", default_inner(sprite))
        need(_number(inner, 1, integer=True), "%s: inner is a whole number of pixels" % at)
        need(2 * inner < sprite["size"], "%s: the ninepatch rectangle (inner %s) leaves no center in a %s sprite" % (at, inner, sprite["size"]))
        need(inner >= pad + sprite["chamfer"], "%s: inner %s does not hold the inset and the chamfer (%s)" % (at, inner, pad + sprite["chamfer"]))
        need(2 * (pad + sprite["chamfer"]) < sprite["size"], "%s: the chamfers do not fit the sprite" % at)
    return manifest


def default_inner(sprite):
    """The inset, the chamfer and 2 pixels; an edge's glow also bends around
    the chamfer's ends, so an edge keeps one more glow width out of the
    stretched patches."""
    glow = sprite.get("glow", 0) if sprite.get("kind") == "chamfer-edge" else 0
    return int(math.ceil(2 * glow + sprite.get("chamfer", 0))) + 2


def load_manifest(path):
    try:
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as error:
        raise ArtError("%s: %s" % (path, error))
    return validate(manifest, os.path.relpath(path, REPO))


def manifests():
    """Every nui/skins/*/art.json that lists sprites."""
    found = []
    for path in sorted(glob.glob(os.path.join(SKINS, "*", "art.json"))):
        if load_manifest(path)["sprites"]:
            found.append(path)
    return found


# --- drawing -------------------------------------------------------------------

def row_span(y, box, chamfers):
    """The [left, right) span of a chamfered box on the horizontal line y, or
    None. box: (x0, y0, x1, y1); chamfers: {corner: length}."""
    x0, y0, x1, y1 = box
    if y < y0 or y >= y1:
        return None
    left = x0 + max(0.0, chamfers.get("tl", 0) - (y - y0), chamfers.get("bl", 0) - (y1 - y))
    right = x1 - max(0.0, chamfers.get("tr", 0) - (y - y0), chamfers.get("br", 0) - (y1 - y))
    return (left, right) if right > left else None


def coverage(size, box, chamfers):
    """[row][column] in 0..1: the share of each pixel the chamfered box covers."""
    rows = []
    for py in range(size):
        row = [0.0] * size
        for sub in range(SUBROWS):
            span = row_span(py + (sub + 0.5) / SUBROWS, box, chamfers)
            if span is None:
                continue
            left, right = span
            first, last = max(0, int(math.floor(left))), min(size - 1, int(math.ceil(right)) - 1)
            for px in range(first, last + 1):
                overlap = min(right, px + 1) - max(left, px)
                if overlap > 0:
                    row[px] += overlap / SUBROWS
        rows.append(row)
    return rows


def gaussian_kernel(sigma):
    radius = int(math.ceil(3 * sigma))
    weights = [math.exp(-(i * i) / (2.0 * sigma * sigma)) for i in range(-radius, radius + 1)]
    total = sum(weights)
    return [w / total for w in weights], radius


def blur(rows, sigma):
    """A separable Gaussian blur; outside the image counts as 0."""
    if sigma <= 0:
        return [list(row) for row in rows]
    kernel, radius = gaussian_kernel(sigma)
    h, w = len(rows), len(rows[0])
    across = [[sum(kernel[k + radius] * row[x + k] for k in range(-radius, radius + 1) if 0 <= x + k < w) for x in range(w)]
              for row in rows]
    return [[sum(kernel[k + radius] * across[y + k][x] for k in range(-radius, radius + 1) if 0 <= y + k < h) for x in range(w)]
            for y in range(h)]


def ring_coverage(size, outer, inner):
    """[row][column] in 0..1: the share of each pixel the annulus between the
    radii covers, around the sprite's center; exact along x, SUBROWS samples
    along y."""
    center = size / 2.0
    rows = []
    for py in range(size):
        row = [0.0] * size
        for sub in range(SUBROWS):
            dy = py + (sub + 0.5) / SUBROWS - center
            if abs(dy) >= outer:
                continue
            half_outer = math.sqrt(outer * outer - dy * dy)
            half_inner = math.sqrt(inner * inner - dy * dy) if abs(dy) < inner else 0.0
            spans = [(center - half_outer, center - half_inner), (center + half_inner, center + half_outer)]
            for left, right in spans:
                if right <= left:
                    continue
                first, last = max(0, int(math.floor(left))), min(size - 1, int(math.ceil(right)) - 1)
                for px in range(first, last + 1):
                    overlap = min(right, px + 1) - max(left, px)
                    if overlap > 0:
                        row[px] += overlap / SUBROWS
        rows.append(row)
    return rows


def with_glow(line, sprite, scale):
    """The line's alpha with the sprite's glow under it."""
    glow = sprite.get("glow", 0)
    if not glow:
        return line
    halo = blur(line, glow * scale / 3.0)
    peak = max(max(row) for row in halo) or 1.0
    strength = sprite["glow_alpha"]
    return [[r + (1.0 - r) * min(1.0, g / peak) * strength for r, g in zip(rrow, grow)] for rrow, grow in zip(line, halo)]


def draw(sprite, scale):
    """The sprite at a scale: a size x size list of alpha rows in 0..1."""
    size = sprite["size"] * scale
    if sprite["kind"] == "ring":
        outer = size / 2.0 - sprite.get("glow", 0) * scale
        cover = ring_coverage(size, outer, outer - sprite["line"] * scale)
        alpha = sprite.get("alpha", 1.0)
        return with_glow([[min(1.0, c) * alpha for c in row] for row in cover], sprite, scale)
    chamfer = sprite["chamfer"] * scale
    chamfers = {corner: chamfer for corner in sprite["corners"]}
    if sprite["kind"] == "chamfer-fill":
        cover = coverage(size, (0, 0, size, size), chamfers)
        return [[min(1.0, c) * sprite["alpha"] for c in row] for row in cover]
    pad = sprite.get("glow", 0) * scale
    line = sprite["line"] * scale
    outer = coverage(size, (pad, pad, size - pad, size - pad), chamfers)
    # The inner shape: the outer one inset by the line; a 45-degree side moves
    # by line * sqrt(2) along x, so its chamfer shrinks by (2 - sqrt(2)) * line.
    inner_chamfer = max(0.0, chamfer - (2.0 - math.sqrt(2.0)) * line)
    inner = coverage(size, (pad + line, pad + line, size - pad - line, size - pad - line),
                     {corner: inner_chamfer for corner in sprite["corners"]})
    ring = [[max(0.0, min(1.0, o) - min(1.0, i)) for o, i in zip(orow, irow)] for orow, irow in zip(outer, inner)]
    return with_glow(ring, sprite, scale)


def to_image(alpha):
    size = len(alpha)
    image = Image.new("RGBA", (size, size))
    image.putdata([(255, 255, 255, int(math.floor(a * 255.0 + 0.5))) for row in alpha for a in row])
    return image


def with_gutter(image, gutter):
    """The image inside a ring of `gutter` of its own edge texels (clamped:
    the sprites are stretched, never tiled), so bilinear filtering at a
    sprite's edge reads only the sprite."""
    w, h = image.size
    out = Image.new("RGBA", (w + 2 * gutter, h + 2 * gutter))
    source = image.load()
    target = out.load()
    for y in range(h + 2 * gutter):
        for x in range(w + 2 * gutter):
            target[x, y] = source[min(w - 1, max(0, x - gutter)), min(h - 1, max(0, y - gutter))]
    return out


def pack(sprites, sheet_width):
    """1x positions {id: (x, y)} of each sprite's top-left texel (inside its
    gutter), shelf by shelf in manifest order, and the sheet's 1x size."""
    positions, x, y, shelf = {}, 0, 0, 0
    for sprite in sprites:
        cell = sprite["size"] + 2 * GUTTER_1X
        if cell > sheet_width:
            raise ArtError("sprite %s (%d px with its gutter) is wider than sheet_width %d" % (sprite["id"], cell, sheet_width))
        if x + cell > sheet_width:
            x, y, shelf = 0, y + shelf, 0
        positions[sprite["id"]] = (x + GUTTER_1X, y + GUTTER_1X)
        x += cell
        shelf = max(shelf, cell)
    height = y + shelf
    return positions, (sheet_width, max(4, (height + 3) // 4 * 4))


def build_outputs(manifest):
    """{relative path: bytes or str}: the sheets (as Images) and the RCSS."""
    name = manifest["name"]
    sprites = manifest["sprites"]
    positions, (width, height) = pack(sprites, manifest.get("sheet_width", 256))
    out_dir = manifest["out_dir"]
    outputs = {}
    blocks = []
    for scale in manifest["scales"]:
        sheet = Image.new("RGBA", (width * scale, height * scale), (255, 255, 255, 0))
        lines = []
        for sprite in sprites:
            x, y = positions[sprite["id"]]
            gutter = GUTTER_1X * scale
            image = with_gutter(to_image(draw(sprite, scale)), gutter)
            sheet.paste(image, (x * scale - gutter, y * scale - gutter))
            size = sprite["size"] * scale
            lines.append("\t%s-%s: %dpx %dpx %dpx %dpx;" % (name, sprite["id"], x * scale, y * scale, size, size))
            if sprite["kind"] == "ring":
                continue
            inner = sprite.get("inner", default_inner(sprite)) * scale
            lines.append("\t%s-%s-inner: %dpx %dpx %dpx %dpx;" % (name, sprite["id"], x * scale + inner, y * scale + inner,
                                                                  size - 2 * inner, size - 2 * inner))
        sheet_file = "%s-%dx.png" % (name, scale)
        outputs[os.path.join(out_dir, sheet_file)] = sheet
        blocks.append((scale, ["@spritesheet %s-%dx" % (name, scale), "{", "\tsrc: %s;" % sheet_file,
                               "\tresolution: %dx;" % scale] + lines + ["}"]))
    text = ["/* Generated by tools/nui_skin_art.py from %s/art.json. Do not edit:" % out_dir.replace("assets/nui/", ""),
            "   %s (check verifies it). White art with alpha," % COMMAND,
            "   tinted by image-color; each sprite <id> but a ring has <id>-inner, the",
            "   rectangle a ninepatch decorator stretches. The 2x sheet replaces the 1x",
            "   one from a dp ratio of %s up (min-resolution compares the context's dp" % THRESHOLD[:-1],
            "   ratio, which is NovaUI's UI scale). */", ""]
    for scale, block in blocks:
        if scale == 1:
            text += block
        else:
            text += ["", "@media (min-resolution: %s)" % THRESHOLD, "{"] + ["\t" + line for line in block] + ["}"]
    outputs[os.path.join(out_dir, "%s-sprites.rcss" % name)] = "\n".join(text) + "\n"
    return outputs


def same(path, value):
    """Whether the file at path holds value: an Image compares by pixels, a
    str by text."""
    if not os.path.isfile(path):
        return False
    if isinstance(value, str):
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read() == value
    with Image.open(path) as image:
        image.load()
        return image.mode == "RGBA" and image.size == value.size and image.tobytes() == value.tobytes()


def write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(value, str):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
    else:
        buffer = io.BytesIO()
        value.save(buffer, format="PNG", optimize=True)
        with open(path, "wb") as handle:
            handle.write(buffer.getvalue())


def run(command, manifest_paths, out=None):
    out = out or sys.stdout
    stale = 0
    for path in manifest_paths:
        manifest = load_manifest(path)
        for relative, value in sorted(build_outputs(manifest).items()):
            target = os.path.join(REPO, relative)
            if command == "build":
                if same(target, value):
                    print("unchanged %s" % relative, file=out)
                else:
                    write(target, value)
                    print("wrote     %s" % relative, file=out)
            elif not same(target, value):
                print("stale     %s" % relative, file=out)
                stale += 1
            else:
                print("ok        %s" % relative, file=out)
    return 1 if stale else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--manifest", help="one skin's art.json (default: every nui/skins/*/art.json that lists sprites)")
    args = parser.parse_args(argv)
    try:
        paths = [os.path.abspath(args.manifest)] if args.manifest else manifests()
        status = run(args.command, paths)
    except ArtError as error:
        print("nui_skin_art: %s" % error, file=sys.stderr)
        return 1
    if args.command == "check":
        print("nui_skin_art: %s" % ("outputs are stale; run %s" % COMMAND if status else "every output is up to date"),
              file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
