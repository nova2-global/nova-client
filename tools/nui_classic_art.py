#!/usr/bin/env python3
"""Classic skin art: legacy UI pieces into the skin's 1x and 2x sprite sheets.

    python3 tools/nui_classic_art.py build [--no-ai] [--work DIR] [--replay DIR]
    python3 tools/nui_classic_art.py check
    python3 tools/nui_classic_art.py rcss [--threshold X] [--force-1x] [--out FILE]
    python3 tools/nui_classic_art.py legacy-ref --out DIR
    python3 tools/nui_classic_art.py sheets --out DIR [--work DIR]

The manifest, tools/classic_art/manifest.json, lists the legacy pieces: TGA,
DDS and PNG files and .sub atlas regions under assets/, each one cut out of a
context composite that lays it out as the legacy UI draws it (a repeated
piece between copies of itself). `build`:
  1. decodes every piece at 1x and builds the composites;
  2. packs a 1x sheet of the exact legacy pixels and a 2x sheet of the same
     layout doubled; every sprite keeps a gutter of its own texels, wrapped
     on the axes the skin repeats it on and clamped on the others, so
     bilinear filtering never reads a neighbor;
  3. makes the 2x art in one run of Real-ESRGAN ncnn-vulkan
     (realesr-animevideov3 x2, on the GPU) over the RGB of every composite
     and standalone piece, recombined with Lanczos alpha and chroma and a
     Lanczos detail transfer on luma ("av3cd"), then cut into pieces.
     Lanczos replaces it where the upscaler fails, where a piece trips the
     garbage guard, with --no-ai, and where the manifest forces a method;
  4. writes the sheets and the sprites RCSS under the manifest's out_dir,
     tools/classic_art/record.json with the method of every piece, and
     review sheets in <work>/review/.
--replay DIR takes the network output of an earlier run (DIR/out) instead
of running the upscaler, so a manifest change to a method or a detail
changes only the pieces it names. `rcss` writes only the sprites RCSS;
--force-1x leaves out the 2x block, for validation runs only. `legacy-ref`
draws the legacy references the sharpness checks compare with, `sheets` the
review sheets. `check` writes nothing and exits 1 when an output is stale
or inconsistent. The upscaler's output depends on the GPU, so `check` never
rebuilds the 2x art: it checks the 2x sheet against the record and its
gutters against the packing rules.

Real-ESRGAN ncnn-vulkan (MIT) and the realesr-animevideov3 model
(BSD-3-Clause) are run, never shipped. Exit codes: 0 success, 1 failure or
stale outputs, 2 usage.
"""
import datetime
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import time

import PIL
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(REPO, "assets")
MANIFEST = os.path.join(REPO, "tools", "classic_art", "manifest.json")
RECORD = os.path.join(REPO, "tools", "classic_art", "record.json")
WORK_ROOT = "/mnt/e/nova-build/classic-art/work"

ID_RE = re.compile(r"^[a-z0-9-]+$")
FILL_RE = re.compile(r"^#[0-9a-fA-F]{8}$")
WINDOWS_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")
TILES = ("none", "x", "y", "xy")
FORCED_METHODS = ("lanczos", "nearest")
SOURCE_TYPES = (".tga", ".dds", ".png", ".sub")
NET_MIN, NET_MAX = 11, 512   # the upscaler mirrors a 10 px pre-padding; one smaller side corrupts the whole run
FILL_PASSES = 16
DETAIL_RADIUS = 1.2
UPSCALER_TIMEOUT = 300
COLOR_KEY = (255, 0, 255, 255)   # D3DX turns opaque #FF00FF transparent
COLOR_KEY_FIX = (254, 0, 255, 255)

TOP_KEYS = {"version", "name", "$comment", "out_dir", "sheet_width_1x", "gutter_1x", "threshold",
            "upscaler", "recipe", "contexts", "pieces"}
PIECE_KEYS = {"id", "source", "crop", "fill", "size", "tile", "context", "cut_at", "slices", "method", "why", "detail",
              "note"}
CONTEXT_KEYS = {"id", "size", "layers"}
LAYER_KEYS = {"piece", "source", "crop", "at"}


class ArtError(Exception):
    pass


class UsageError(Exception):
    pass


# --- manifest -----------------------------------------------------------------

def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _ints(value, count, minimum=0):
    return isinstance(value, list) and len(value) == count and all(_is_int(v) and v >= minimum for v in value)


def _rect(value):
    return _ints(value, 4) and value[2] > value[0] and value[3] > value[1]


def tile_axes(tile):
    return [axis for axis in "xy" if axis in tile]


def validate_manifest(manifest):
    """Raises ArtError naming the first rule a manifest breaks."""
    def need(condition, message):
        if not condition:
            raise ArtError("manifest: " + message)

    need(isinstance(manifest, dict), "the root is an object")
    unknown = set(manifest) - TOP_KEYS
    need(not unknown, "unknown key %s" % ", ".join(sorted(unknown)))
    need(manifest.get("version") == 1, "version must be 1")
    need(isinstance(manifest.get("name"), str) and ID_RE.match(manifest["name"]), "name is [a-z0-9-]+")
    need(isinstance(manifest.get("out_dir"), str) and manifest["out_dir"].strip(), "out_dir is a path")
    need(_is_int(manifest.get("sheet_width_1x")) and manifest["sheet_width_1x"] >= 16, "sheet_width_1x is a width")
    need(_is_int(manifest.get("gutter_1x")) and manifest["gutter_1x"] >= 1, "gutter_1x is at least 1")
    need(_is_number(manifest.get("threshold")) and 1.0 < manifest["threshold"] <= 2.0,
         "threshold is a dp ratio above 1 and at most 2")
    upscaler = manifest.get("upscaler")
    need(isinstance(upscaler, dict) and all(k in upscaler for k in ("dir", "exe", "model", "scale", "tile")),
         "upscaler has dir, exe, model, scale and tile")
    need(upscaler["scale"] == 2, "upscaler scale must be 2")
    need(isinstance(upscaler["dir"], str) and WINDOWS_RE.match(upscaler["dir"]), "upscaler dir is a Windows path")
    recipe = manifest.get("recipe")
    need(isinstance(recipe, dict) and recipe.get("method") == "av3cd", "recipe method must be av3cd")
    need(_is_number(recipe.get("detail")) and 0 <= recipe["detail"] <= 2, "recipe detail is 0 to 2")
    need(_is_number(recipe.get("garbage_mad")) and recipe["garbage_mad"] > 0, "recipe garbage_mad is above 0")
    contexts, pieces = manifest.get("contexts"), manifest.get("pieces")
    need(isinstance(contexts, list) and isinstance(pieces, list) and pieces, "contexts and pieces are lists")

    piece_ids = set()
    for piece in pieces:
        need(isinstance(piece, dict) and isinstance(piece.get("id"), str) and ID_RE.match(piece["id"]),
             "every piece has an id of [a-z0-9-]+")
        pid = piece["id"]
        need(pid not in piece_ids, "piece %s appears twice" % pid)
        piece_ids.add(pid)
    context_ids = set()
    for context in contexts:
        need(isinstance(context, dict) and isinstance(context.get("id"), str) and ID_RE.match(context["id"]),
             "every context has an id of [a-z0-9-]+")
        cid = context["id"]
        need(cid not in context_ids, "context %s appears twice" % cid)
        context_ids.add(cid)
        unknown = set(context) - CONTEXT_KEYS
        need(not unknown, "context %s: unknown key %s" % (cid, ", ".join(sorted(unknown))))
        need(_ints(context.get("size"), 2, 1), "context %s: size is [w, h]" % cid)
        layers = context.get("layers")
        need(isinstance(layers, list) and layers, "context %s: layers is a list" % cid)
        for layer in layers:
            need(isinstance(layer, dict) and not set(layer) - LAYER_KEYS, "context %s: a layer has piece or source, crop and at" % cid)
            need(("piece" in layer) != ("source" in layer), "context %s: a layer names a piece or a source" % cid)
            if "piece" in layer:
                need(layer["piece"] in piece_ids, "context %s: no piece %r" % (cid, layer["piece"]))
                need("crop" not in layer, "context %s: crop a piece in the piece itself" % cid)
            else:
                need(isinstance(layer["source"], str) and layer["source"].lower().endswith(SOURCE_TYPES),
                     "context %s: a source is a %s file" % (cid, ", ".join(SOURCE_TYPES)))
            need("crop" not in layer or _rect(layer["crop"]), "context %s: crop is [left, top, right, bottom]" % cid)
            need(_ints(layer.get("at"), 2), "context %s: at is [x, y]" % cid)

    for piece in pieces:
        pid = piece["id"]
        unknown = set(piece) - PIECE_KEYS
        need(not unknown, "piece %s: unknown key %s" % (pid, ", ".join(sorted(unknown))))
        need(("source" in piece) != ("fill" in piece), "piece %s: give a source or a fill" % pid)
        if "fill" in piece:
            need(isinstance(piece["fill"], str) and FILL_RE.match(piece["fill"]), "piece %s: fill is #rrggbbaa" % pid)
            need(_ints(piece.get("size"), 2, 1), "piece %s: a fill needs size [w, h]" % pid)
            for key in ("crop", "context", "cut_at", "method"):
                need(key not in piece, "piece %s: a fill takes no %s" % (pid, key))
        else:
            need(isinstance(piece["source"], str) and piece["source"].lower().endswith(SOURCE_TYPES),
                 "piece %s: source is a %s file under assets/" % (pid, ", ".join(SOURCE_TYPES)))
            need("size" not in piece, "piece %s: only a fill takes a size" % pid)
        need("crop" not in piece or _rect(piece["crop"]), "piece %s: crop is [left, top, right, bottom]" % pid)
        need(piece.get("tile") in TILES, "piece %s: tile is one of %s" % (pid, ", ".join(TILES)))
        if "context" in piece:
            need(piece["context"] in context_ids, "piece %s: no context %r" % (pid, piece["context"]))
            need(_ints(piece.get("cut_at"), 2), "piece %s: a context piece needs cut_at [x, y]" % pid)
        else:
            need("cut_at" not in piece, "piece %s: cut_at needs a context" % pid)
            need(piece["tile"] == "none" or "fill" in piece,
                 "piece %s tiles on %s, so it needs a context that holds copies of it" % (pid, piece["tile"]))
        if "slices" in piece:
            need(_ints(piece["slices"], 2, 1), "piece %s: slices is [left, right] cap widths" % pid)
        if "method" in piece:
            need(piece["method"] in FORCED_METHODS, "piece %s: method is %s" % (pid, " or ".join(FORCED_METHODS)))
            need(isinstance(piece.get("why"), str) and piece["why"].strip(), "piece %s: a forced method needs a why" % pid)
        else:
            need("why" not in piece, "piece %s: why goes with a forced method" % pid)
        if "detail" in piece:
            need(_is_number(piece["detail"]) and 0 <= piece["detail"] <= 2, "piece %s: detail is 0 to 2" % pid)
        if "note" in piece:
            need(isinstance(piece["note"], str) and piece["note"].strip(), "piece %s: note is text" % pid)


def load_manifest(path=MANIFEST):
    try:
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as error:
        raise ArtError("manifest: %s" % error)
    validate_manifest(manifest)
    return manifest


def sprite_name(manifest, pid, suffix=None):
    return "%s-%s%s" % (manifest["name"], pid, "-" + suffix if suffix else "")


def out_path(manifest, kind):
    """kind: "1x" or "2x" (the sheets) or "rcss"."""
    name = "%s-sprites.rcss" % manifest["name"] if kind == "rcss" else "%s-%s.png" % (manifest["name"], kind)
    return os.path.join(REPO, manifest["out_dir"], name)


# --- sources -------------------------------------------------------------------

def parse_sub(text):
    """The fields of a legacy .sub file (EterLib CGraphicSubImage): its
    version, the atlas image (quoted) and the rectangle left, top, right,
    bottom in atlas pixels."""
    fields = {}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        value = parts[1].strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        fields[parts[0].lower()] = value
    try:
        rect = tuple(int(fields[key]) for key in ("left", "top", "right", "bottom"))
    except (KeyError, ValueError):
        raise ArtError("a .sub needs whole numbers for left, top, right and bottom")
    if not fields.get("image"):
        raise ArtError("a .sub names its atlas image")
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        raise ArtError("a .sub rectangle is empty: %s" % (rect,))
    return {"version": fields.get("version", ""), "image": fields["image"], "rect": rect}


def sub_atlas(sub_rel, info):
    """Where a .sub's atlas lives, relative to assets/: next to the .sub for
    version 2.0, else under ymir work/ui/ of the .sub's own group, which
    stands for d:/ymir work/ui/ (EterLib GrpSubImage.cpp)."""
    sub_rel = sub_rel.replace("\\", "/")
    image = info["image"].replace("\\", "/")
    if info["version"] == "2.0":
        return posixpath.join(posixpath.dirname(sub_rel), image)
    return posixpath.join(sub_rel.split("/", 1)[0], "ymir work", "ui", image)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def pixels_sha256(image):
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


class Sources(object):
    """Decodes files under an assets folder, matching names without regard to
    case as the asset store does."""

    def __init__(self, root=ASSETS):
        self.root = root
        self._images = {}

    def path(self, rel):
        current = self.root
        for part in rel.replace("\\", "/").split("/"):
            if not part:
                continue
            exact = os.path.join(current, part)
            if os.path.exists(exact):
                current = exact
                continue
            try:
                names = sorted(name for name in os.listdir(current) if name.lower() == part.lower())
            except OSError:
                names = []
            if not names:
                raise ArtError("missing under assets/: %s" % rel)
            current = os.path.join(current, names[0])
        if not os.path.isfile(current):
            raise ArtError("not a file under assets/: %s" % rel)
        return current

    def sub_info(self, rel):
        with open(self.path(rel), "rb") as handle:
            return parse_sub(handle.read().decode("latin-1"))

    def atlas(self, rel):
        """The atlas of a .sub source, or None."""
        if not rel.lower().endswith(".sub"):
            return None
        return sub_atlas(rel, self.sub_info(rel))

    def image(self, rel):
        """The RGBA pixels of a file, or of a .sub's atlas region."""
        if rel not in self._images:
            if rel.lower().endswith(".sub"):
                info = self.sub_info(rel)
                atlas = self.image(sub_atlas(rel, info))
                left, top, right, bottom = info["rect"]
                if right > atlas.width or bottom > atlas.height:
                    raise ArtError("%s reaches past its %dx%d atlas" % (rel, atlas.width, atlas.height))
                image = atlas.crop(info["rect"])
            else:
                try:
                    with Image.open(self.path(rel)) as opened:
                        image = opened.convert("RGBA")
                except OSError as error:
                    raise ArtError("%s does not decode: %s" % (rel, error))
            self._images[rel] = image
        return self._images[rel].copy()


def parse_fill(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5, 7))


def crop_of(image, crop, what):
    if crop[2] > image.width or crop[3] > image.height:
        raise ArtError("%s: crop %s leaves the %dx%d source" % (what, crop, image.width, image.height))
    return image.crop(tuple(crop))


def piece_image(sources, piece):
    """A piece's 1x pixels."""
    if "fill" in piece:
        return Image.new("RGBA", tuple(piece["size"]), parse_fill(piece["fill"]))
    image = sources.image(piece["source"])
    return crop_of(image, piece["crop"], "piece " + piece["id"]) if "crop" in piece else image


def build_context(sources, context, pieces_1x):
    """A context composite: its layers in order, straight-alpha over, on a
    transparent canvas."""
    canvas = Image.new("RGBA", tuple(context["size"]), (0, 0, 0, 0))
    for layer in context["layers"]:
        if "piece" in layer:
            image = pieces_1x[layer["piece"]]
        else:
            image = sources.image(layer["source"])
            if "crop" in layer:
                image = crop_of(image, layer["crop"], "context " + context["id"])
        x, y = layer["at"]
        if x + image.width > canvas.width or y + image.height > canvas.height:
            raise ArtError("context %s: a %dx%d layer at (%d, %d) leaves the %dx%d canvas"
                           % (context["id"], image.width, image.height, x, y, canvas.width, canvas.height))
        canvas.alpha_composite(image, (x, y))
    return canvas


def same_pixels(a, b):
    """True when two images show the same texels: equal alpha everywhere, and
    equal color wherever alpha is above 0."""
    if a.size != b.size:
        return False
    for pa, pb in zip(a.getdata(), b.getdata()):
        if pa[3] != pb[3] or (pa[3] and pa[:3] != pb[:3]):
            return False
    return True


def check_cuts(manifest, pieces_1x, composites):
    """Every context piece sits at its cut_at in its composite, and a tiled
    one also directly before and after the cut box on each axis it tiles on,
    so the network sees it next to its own copies."""
    for piece in manifest["pieces"]:
        if "context" not in piece:
            continue
        pid, context = piece["id"], piece["context"]
        image, composite = pieces_1x[pid], composites[context]
        w, h = image.size
        cx, cy = piece["cut_at"]
        box = (cx, cy, cx + w, cy + h)
        if box[2] > composite.width or box[3] > composite.height or not same_pixels(composite.crop(box), image):
            raise ArtError("manifest: piece %s: context %s does not hold its pixels at %s" % (pid, context, piece["cut_at"]))
        for axis in tile_axes(piece["tile"]):
            for sign, side in ((-1, "before"), (1, "after")):
                dx, dy = (sign * w, 0) if axis == "x" else (0, sign * h)
                near = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
                inside = near[0] >= 0 and near[1] >= 0 and near[2] <= composite.width and near[3] <= composite.height
                if not inside or not same_pixels(composite.crop(near), image):
                    raise ArtError("manifest: piece %s tiles on %s, but context %s holds no copy of it %s the cut box"
                                   % (pid, axis, context, side))


def check_network_sizes(inputs):
    """The size guard: the upscaler is never called with a side outside 11 to 512 px."""
    for name, image in sorted(inputs.items()):
        if min(image.size) < NET_MIN or max(image.size) > NET_MAX:
            raise ArtError("manifest: upscaler input %s is %dx%d; every side must be %d to %d px (a smaller one "
                           "turns the whole run into noise, a larger one splits into tiles)"
                           % (name, image.width, image.height, NET_MIN, NET_MAX))


# --- packing -------------------------------------------------------------------

def pack(sizes, sheet_width, gutter):
    """({id: (x, y)}, height): padded positions in the 1x sheet. Pieces go
    left to right in shelves, sorted by padded height, then padded width,
    both descending, then id; one that does not fit starts a shelf below the
    current one's tallest piece. The height is the smallest power of two that
    holds them, at least 64."""
    def padded(pid):
        return sizes[pid][0] + 2 * gutter, sizes[pid][1] + 2 * gutter
    order = sorted(sizes, key=lambda pid: (-padded(pid)[1], -padded(pid)[0], pid))
    positions, x, y, shelf = {}, 0, 0, 0
    for pid in order:
        w, h = padded(pid)
        if w > sheet_width:
            raise ArtError("piece %s is too wide for a %d px sheet" % (pid, sheet_width))
        if x + w > sheet_width:
            x, y, shelf = 0, y + shelf, 0
        positions[pid] = (x, y)
        x += w
        shelf = max(shelf, h)
    height = 64
    while height < y + shelf:
        height *= 2
    return positions, height


def sprite_rects(manifest, sizes, positions):
    """[(sprite name, rect 1x, rect 2x)] with rects (x, y, w, h), in manifest
    order with each piece's slices right after it."""
    gutter = manifest["gutter_1x"]
    rects = []
    for piece in manifest["pieces"]:
        pid = piece["id"]
        w, h = sizes[pid]
        x, y = positions[pid][0] + gutter, positions[pid][1] + gutter
        parts = [(None, 0, w)]
        if "slices" in piece:
            left, right = piece["slices"]
            if left + right >= w:
                raise ArtError("manifest: piece %s: slices %s leave no center in %d px" % (pid, piece["slices"], w))
            parts += [("l", 0, left), ("c", left, w - left - right), ("r", w - right, right)]
        for suffix, offset, width in parts:
            rect = (x + offset, y, width, h)
            rects.append((sprite_name(manifest, pid, suffix), rect, tuple(2 * v for v in rect)))
    return rects


def with_gutter(image, gutter, tile):
    """The image inside a ring of `gutter` of its own texels: wrapped (u mod
    w) on the axes it tiles on, so filtering at a copy seam sees the next
    copy, and clamped (edge extrusion) on the others."""
    w, h = image.size

    def source(i, n, wrap):
        return i % n if wrap else min(max(i, 0), n - 1)

    ring = list(range(-gutter, 0))
    strip = Image.new("RGBA", (w + 2 * gutter, h))
    strip.paste(image, (gutter, 0))
    for i in ring + list(range(w, w + gutter)):
        column = source(i, w, "x" in tile)
        strip.paste(image.crop((column, 0, column + 1, h)), (i + gutter, 0))
    padded = Image.new("RGBA", (w + 2 * gutter, h + 2 * gutter))
    padded.paste(strip, (0, gutter))
    for j in ring + list(range(h, h + gutter)):
        row = source(j, h, "y" in tile)
        padded.paste(strip.crop((0, row, strip.width, row + 1)), (0, j + gutter))
    return padded


def assemble(images, positions, size, gutter, tiles):
    sheet = Image.new("RGBA", size, (0, 0, 0, 0))
    for pid, image in images.items():
        sheet.paste(with_gutter(image, gutter, tiles[pid]), positions[pid])
    return sheet


def fix_color_key(sheet):
    """Opaque #FF00FF becomes #FE00FF, which the client's color key leaves
    alone. Returns how many texels changed."""
    data = list(sheet.getdata())
    count = 0
    for i, texel in enumerate(data):
        if texel == COLOR_KEY:
            data[i] = COLOR_KEY_FIX
            count += 1
    if count:
        sheet.putdata(data)
    return count


# --- the 2x art -------------------------------------------------------------------

def lanczos2x(image):
    """Lanczos x2; Pillow premultiplies RGBA while it resamples."""
    return image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)


def nearest2x(image):
    return image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST)


def filled_rgb(image):
    """The RGB the network sees. Fully transparent texels take the mean of
    their filled 4-neighbors, pass by pass, for at most 16 passes; any still
    empty then take the mean of all filled texels. Alpha never goes to the
    network."""
    w, h = image.size
    colors = [texel[:3] if texel[3] else None for texel in image.getdata()]
    for _ in range(FILL_PASSES):
        updates = {}
        for i, color in enumerate(colors):
            if color is not None:
                continue
            x = i % w
            near = [colors[k] for k, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, i >= w), (i + w, i + w < w * h))
                    if ok and colors[k] is not None]
            if near:
                updates[i] = tuple((sum(c[ch] for c in near) + len(near) // 2) // len(near) for ch in range(3))
        if not updates:
            break
        for i, color in updates.items():
            colors[i] = color
    if any(color is None for color in colors):
        filled = [color for color in colors if color is not None]
        mean = tuple(sum(c[ch] for c in filled) // len(filled) for ch in range(3)) if filled else (0, 0, 0)
        colors = [mean if color is None else color for color in colors]
    out = Image.new("RGB", (w, h))
    out.putdata(colors)
    return out


def recombine(network_rgb, lanczos, detail):
    """av3cd at 2x: luma from the network plus `detail` times the Lanczos
    high-pass (its luma minus a Gaussian blur of radius 1.2), clamped; chroma
    (Cb, Cr) and alpha from the Lanczos result."""
    y_network = network_rgb.convert("RGB").convert("YCbCr").getchannel(0)
    y_lanczos, cb, cr = lanczos.convert("RGB").convert("YCbCr").split()
    blurred = y_lanczos.filter(ImageFilter.GaussianBlur(DETAIL_RADIUS))
    luma = []
    for y, lz, bl in zip(y_network.getdata(), y_lanczos.getdata(), blurred.getdata()):
        step = int(detail * abs(lz - bl) + 0.5)
        value = y + step if lz >= bl else y - step
        luma.append(0 if value < 0 else 255 if value > 255 else value)
    y_out = Image.new("L", y_network.size)
    y_out.putdata(luma)
    rgb = Image.merge("YCbCr", (y_out, cb, cr)).convert("RGB")
    return Image.merge("RGBA", rgb.split() + (lanczos.getchannel("A"),))


def mad_vs(image, reference):
    """Mean absolute RGB difference over the texels where the reference's
    alpha is above 0."""
    total = count = 0
    for a, b in zip(image.getdata(), reference.getdata()):
        if b[3]:
            total += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
            count += 3
    return total / count if count else 0.0


OVERSHOOT_LUMA = 40   # above the brightest opaque 1x neighbor
BLEED_ALPHA = 32      # where the 1x texel is fully transparent


def warnings_2x(image_1x, image_2x):
    """(bright, bleed): the 2x texels with alpha above 0 whose luma exceeds
    the brightest opaque texel of their 1x 3x3 neighborhood by more than 40,
    and the 2x texels at alpha 32 or more where the 1x texel (nearest) is
    fully transparent. A review warning, not a failure: av3cd lifting a 1 px
    outline into a cut-out shows as both, where a MAD against Lanczos stays
    small."""
    w, h = image_1x.size
    luma_1x = list(image_1x.convert("RGB").convert("L").getdata())
    alpha_1x = list(image_1x.getchannel("A").getdata())
    ceiling = []
    for y in range(h):
        for x in range(w):
            near = [(luma_1x[j * w + i], alpha_1x[j * w + i]) for j in range(max(y - 1, 0), min(y + 2, h))
                    for i in range(max(x - 1, 0), min(x + 2, w))]
            opaque = [luma for luma, alpha in near if alpha == 255] or [luma for luma, alpha in near if alpha]
            ceiling.append(max(opaque) if opaque else None)
    luma_2x = list(image_2x.convert("RGB").convert("L").getdata())
    alpha_2x = list(image_2x.getchannel("A").getdata())
    bright = bleed = 0
    for k, (luma, alpha) in enumerate(zip(luma_2x, alpha_2x)):
        if not alpha:
            continue
        i = (k // (2 * w) // 2) * w + (k % (2 * w)) // 2
        if ceiling[i] is not None and luma > ceiling[i] + OVERSHOOT_LUMA:
            bright += 1
        if alpha >= BLEED_ALPHA and not alpha_1x[i]:
            bleed += 1
    return bright, bleed


def warning_text(counts):
    bright, bleed = counts
    parts = (["%d texel(s) over the 1x luma" % bright] if bright else []) + (["%d into clear texels" % bleed] if bleed else [])
    return "; ".join(parts)


def network_inputs(manifest, pieces_1x, composites):
    """{input name: 1x RGBA} for the pieces the upscaler serves: every context
    of such a piece, and every such piece without a context."""
    inputs = {}
    for piece in manifest["pieces"]:
        if "fill" in piece or "method" in piece:
            continue
        if "context" in piece:
            inputs["context-" + piece["context"]] = composites[piece["context"]]
        else:
            inputs["piece-" + piece["id"]] = pieces_1x[piece["id"]]
    return inputs


def input_name(piece):
    return "context-" + piece["context"] if "context" in piece else "piece-" + piece["id"]


class Piece2x(object):
    def __init__(self, image, method, note="", detail=None, mad=None, ai=None, lanczos=None):
        self.image, self.method, self.note = image, method, note
        self.detail, self.mad, self.ai, self.lanczos = detail, mad, ai, lanczos


def windows_path(path):
    """/mnt/e/x/y as E:\\x\\y, for the Windows upscaler."""
    match = re.match(r"^/mnt/([a-zA-Z])(/.*)?$", os.path.abspath(path))
    if not match:
        raise ArtError("the work folder must be on a Windows drive (/mnt/<drive>/...): %s" % path)
    return match.group(1).upper() + ":" + (match.group(2) or "/").replace("/", "\\")


def linux_path(path):
    match = WINDOWS_RE.match(path)
    return "/mnt/%s/%s" % (match.group(1).lower(), match.group(2).replace("\\", "/"))


def upscaler_exe(manifest):
    upscaler = manifest["upscaler"]
    return upscaler["dir"].rstrip("\\/") + "\\" + upscaler["exe"], posixpath.join(linux_path(upscaler["dir"]), upscaler["exe"])


def realesrgan(manifest):
    """The upscaler as a function: ({input name: filled RGB}, work folder) ->
    ({input name: RGB at 2x} or None, info). One run of the Windows exe over
    <work>/in into <work>/out, from WSL with the working directory /mnt/e."""
    def upscale(inputs, work):
        windows_exe, exe = upscaler_exe(manifest)
        upscaler = manifest["upscaler"]
        info = {"exe": windows_exe, "exe_sha256": "", "model": upscaler["model"], "ran": False, "seconds": 0.0, "error": ""}
        if not os.path.isfile(exe):
            info["error"] = "%s not found" % windows_exe
            return None, info
        info["exe_sha256"] = sha256_file(exe)
        in_dir, out_dir = os.path.join(work, "in"), os.path.join(work, "out")
        os.makedirs(in_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)  # the tool writes nothing into a folder that does not exist
        for name, image in inputs.items():
            image.save(os.path.join(in_dir, name + ".png"))
        line = "cd /d %s && %s -i %s -o %s -n %s -s %d -t %d -f png" % (
            upscaler["dir"], upscaler["exe"], windows_path(in_dir), windows_path(out_dir),
            upscaler["model"], upscaler["scale"], upscaler["tile"])
        start = time.time()
        try:
            result = subprocess.run(["cmd.exe", "/c", line], cwd="/mnt/e", capture_output=True, timeout=UPSCALER_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            info["seconds"] = round(time.time() - start, 2)
            info["error"] = str(error)
            return None, info
        info["seconds"] = round(time.time() - start, 2)
        with open(os.path.join(work, "upscaler.log"), "wb") as log:
            log.write(line.encode("utf-8") + b"\n" + result.stdout + result.stderr)
        if result.returncode != 0:
            info["error"] = "exit code %d" % result.returncode
            return None, info
        outputs = {}
        for name, image in inputs.items():
            path = os.path.join(out_dir, name + ".png")
            if not os.path.isfile(path):
                info["error"] = "no output for %s" % name
                return None, info
            with Image.open(path) as opened:
                output = opened.convert("RGB")
            if output.size != (2 * image.width, 2 * image.height):
                info["error"] = "%s came back %dx%d, not %dx%d" % (name, output.width, output.height, 2 * image.width, 2 * image.height)
                return None, info
            outputs[name] = output
        info["ran"] = True
        return outputs, info
    return upscale


def replay(work, previous=None):
    """An upscaler that reads an earlier run's <work>/out instead of running.
    Its info is `previous` (that run's, from the record) with "replayed_from"."""
    def upscale(inputs, _work):
        info = dict(previous or {"exe": "", "exe_sha256": "", "model": "", "ran": False, "seconds": 0.0, "error": ""})
        info.update(replayed_from=work, error="")
        outputs = {}
        for name in inputs:
            path = os.path.join(work, "out", name + ".png")
            if not os.path.isfile(path):
                info["error"] = "no output for %s in %s" % (name, work)
                return None, info
            with Image.open(path) as opened:
                outputs[name] = opened.convert("RGB")
        info["ran"] = True
        return outputs, info
    return upscale


def make_2x(manifest, pieces_1x, composites, upscale, work, no_ai=False):
    """({id: Piece2x}, upscaler info)."""
    recipe = manifest["recipe"]
    context_lanczos = {cid: lanczos2x(composite) for cid, composite in composites.items()}

    def cut(image, piece):
        cx, cy = piece["cut_at"]
        w, h = pieces_1x[piece["id"]].size
        return image.crop((2 * cx, 2 * cy, 2 * (cx + w), 2 * (cy + h)))

    lanczos = {}
    for piece in manifest["pieces"]:
        if "fill" not in piece:
            pid = piece["id"]
            lanczos[pid] = cut(context_lanczos[piece["context"]], piece) if "context" in piece else lanczos2x(pieces_1x[pid])

    inputs = network_inputs(manifest, pieces_1x, composites)
    check_network_sizes(inputs)
    info = {"exe": upscaler_exe(manifest)[0], "exe_sha256": "", "model": manifest["upscaler"]["model"],
            "ran": False, "seconds": 0.0, "error": ""}
    network = None
    if no_ai:
        info["error"] = "--no-ai"
    elif inputs:
        network, info = upscale({name: filled_rgb(image) for name, image in inputs.items()}, work)

    results, recombined = {}, {}
    for piece in manifest["pieces"]:
        pid = piece["id"]
        if "fill" in piece:
            w, h = piece["size"]
            results[pid] = Piece2x(Image.new("RGBA", (2 * w, 2 * h), parse_fill(piece["fill"])), "generated",
                                   "the code-drawn fill %s" % piece["fill"])
            continue
        if piece.get("method") == "lanczos":
            results[pid] = Piece2x(lanczos[pid], "lanczos", piece["why"], lanczos=lanczos[pid])
            continue
        if piece.get("method") == "nearest":
            results[pid] = Piece2x(nearest2x(pieces_1x[pid]), "nearest", piece["why"], lanczos=lanczos[pid])
            continue
        if network is None:
            note = "--no-ai" if no_ai else "upscaler failed: %s" % info["error"]
            results[pid] = Piece2x(lanczos[pid], "lanczos", note, lanczos=lanczos[pid])
            continue
        name = input_name(piece)
        detail = piece.get("detail", recipe["detail"])
        if (name, detail) not in recombined:
            reference = context_lanczos[piece["context"]] if "context" in piece else lanczos[pid]
            recombined[(name, detail)] = recombine(network[name], reference, detail)
        ai = cut(recombined[(name, detail)], piece) if "context" in piece else recombined[(name, detail)]
        mad = mad_vs(ai, lanczos[pid])
        if mad > recipe["garbage_mad"]:
            results[pid] = Piece2x(lanczos[pid], "lanczos", "garbage guard (MAD %.1f)" % mad, mad=mad, ai=ai, lanczos=lanczos[pid])
        else:
            results[pid] = Piece2x(ai, "av3cd", "", detail=detail, mad=mad, ai=ai, lanczos=lanczos[pid])
    # A review finding (the manifest's note) goes into the record after any
    # reason the build itself gives.
    for piece in manifest["pieces"]:
        if "note" in piece:
            result = results[piece["id"]]
            result.note = "; ".join(part for part in (result.note, piece["note"]) if part)
    return results, info


# --- one build ------------------------------------------------------------------

class Build(object):
    """Everything one run makes, in memory."""

    def __init__(self, manifest, sources=None):
        self.manifest = manifest
        self.sources = sources or Sources()
        self.pieces_1x = {p["id"]: piece_image(self.sources, p) for p in manifest["pieces"]}
        self.composites = {c["id"]: build_context(self.sources, c, self.pieces_1x) for c in manifest["contexts"]}
        check_cuts(manifest, self.pieces_1x, self.composites)
        self.sizes = {pid: image.size for pid, image in self.pieces_1x.items()}
        self.tiles = {p["id"]: p["tile"] for p in manifest["pieces"]}
        self.positions, self.height = pack(self.sizes, manifest["sheet_width_1x"], manifest["gutter_1x"])
        self.rects = sprite_rects(manifest, self.sizes, self.positions)
        self._rect_of = {name: (rect_1x, rect_2x) for name, rect_1x, rect_2x in self.rects}
        self.sheet_1x = assemble(self.pieces_1x, self.positions, (manifest["sheet_width_1x"], self.height),
                                 manifest["gutter_1x"], self.tiles)
        self.color_key_1x = fix_color_key(self.sheet_1x)
        self.results, self.info, self.sheet_2x, self.color_key_2x = None, None, None, 0

    def piece_rect(self, pid, scale):
        """(x, y, w, h) of a piece in the 1x (scale 1) or 2x sheet."""
        return self._rect_of[sprite_name(self.manifest, pid)][scale - 1]

    def make_2x(self, upscale, work, no_ai=False):
        self.results, self.info = make_2x(self.manifest, self.pieces_1x, self.composites, upscale, work, no_ai)
        positions = {pid: (2 * x, 2 * y) for pid, (x, y) in self.positions.items()}
        images = {pid: result.image for pid, result in self.results.items()}
        self.sheet_2x = assemble(images, positions, (2 * self.manifest["sheet_width_1x"], 2 * self.height),
                                 2 * self.manifest["gutter_1x"], self.tiles)
        self.color_key_2x = fix_color_key(self.sheet_2x)


def piece_2x_from_sheet(build, sheet_2x, pid):
    x, y, w, h = build.piece_rect(pid, 2)
    return sheet_2x.crop((x, y, x + w, y + h))


def gutter_problems(build, sheet, scale):
    """Pieces whose gutter in `sheet` is not the wrap/clamp ring of the
    piece's own texels there."""
    gutter = scale * build.manifest["gutter_1x"]
    problems = []
    for piece in build.manifest["pieces"]:
        pid = piece["id"]
        x, y, w, h = build.piece_rect(pid, scale)
        inner = sheet.crop((x, y, x + w, y + h))
        expected = with_gutter(inner, gutter, piece["tile"])
        actual = sheet.crop((x - gutter, y - gutter, x + w + gutter, y + h + gutter))
        if expected.tobytes() != actual.tobytes():
            problems.append(pid)
    return problems


# --- outputs -------------------------------------------------------------------

def format_threshold(value):
    return ("%.6f" % value).rstrip("0").rstrip(".")


def render_rcss(manifest, rects, threshold=None, force_1x=False):
    """The sprites style sheet: the 1x sheet in the default block, the 2x
    sheet with the same sprite names in a min-resolution block."""
    threshold = manifest["threshold"] if threshold is None else threshold
    name = manifest["name"]
    lines = [
        "/* Generated by tools/nui_classic_art.py from tools/classic_art/manifest.json.",
        "   Do not edit: python3 tools/nui_classic_art.py build (or rcss).",
        "   1x: the legacy pixels. 2x: see tools/classic_art/record.json for the",
        "   method of each piece. The 2x sprites replace the 1x ones of the same names",
        "   from a dp ratio of %s up (min-resolution compares the context's dp" % format_threshold(threshold),
        "   ratio, which is NovaUI's UI scale). */",
    ]
    if force_1x:
        lines[-1] = lines[-1][:-len(" */")]
        lines.append("   Validation only: the 1x sheet at every scale. */")
    lines += ["", "@spritesheet %s-1x" % name, "{", "\tsrc: %s-1x.png;" % name, "\tresolution: 1x;"]
    lines += ["\t%s: %dpx %dpx %dpx %dpx;" % ((sprite,) + rect_1x) for sprite, rect_1x, _ in rects]
    lines.append("}")
    if not force_1x:
        lines += ["", "@media (min-resolution: %sx)" % format_threshold(threshold), "{",
                  "\t@spritesheet %s-2x" % name, "\t{", "\t\tsrc: %s-2x.png;" % name, "\t\tresolution: 2x;"]
        lines += ["\t\t%s: %dpx %dpx %dpx %dpx;" % ((sprite,) + rect_2x) for sprite, _, rect_2x in rects]
        lines += ["\t}", "}"]
    return "\n".join(lines) + "\n"


def save_png(image, path):
    """compress_level 9 and no ancillary chunks."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    image.save(path, format="PNG", compress_level=9)


def relative(path):
    return os.path.relpath(path, REPO).replace(os.sep, "/")


def make_record(build):
    manifest, sources = build.manifest, build.sources
    pieces = []
    for piece in manifest["pieces"]:
        pid = piece["id"]
        result = build.results[pid]
        source = piece.get("source")
        atlas = sources.atlas(source) if source else None
        pieces.append({
            "id": pid,
            "source": source,
            "source_sha256": sha256_file(sources.path(source)) if source else None,
            "atlas": atlas,
            "atlas_sha256": sha256_file(sources.path(atlas)) if atlas else None,
            "rect_1x": list(build.piece_rect(pid, 1)),
            "rect_2x": list(build.piece_rect(pid, 2)),
            "method": result.method,
            "detail": result.detail,
            "context": piece.get("context"),
            "mad_vs_lanczos": round(result.mad, 2) if result.mad is not None else None,
            "pixels_2x_sha256": pixels_sha256(result.image),
            "note": result.note,
        })
    layer_sources = sorted({layer["source"] for context in manifest["contexts"] for layer in context["layers"] if "source" in layer})
    return {
        "generated_by": "tools/nui_classic_art.py build",
        "pillow": PIL.__version__,
        "threshold": manifest["threshold"],
        "upscaler": build.info,
        "sheet_1x": {"file": relative(out_path(manifest, "1x")), "size": list(build.sheet_1x.size),
                     "pixels_sha256": pixels_sha256(build.sheet_1x)},
        "sheet_2x": {"file": relative(out_path(manifest, "2x")), "size": list(build.sheet_2x.size),
                     "pixels_sha256": pixels_sha256(build.sheet_2x)},
        "color_key_fixed": build.color_key_1x + build.color_key_2x,
        "context_sources": [{"source": s, "source_sha256": sha256_file(sources.path(s))} for s in layer_sources],
        "pieces": pieces,
    }


def dump_record(record):
    """JSON with one piece per line."""
    head = {key: value for key, value in record.items() if key != "pieces"}
    lines = ["{"]
    for key, value in head.items():
        lines.append("\t%s: %s," % (json.dumps(key), json.dumps(value)))
    lines.append('\t"pieces": [')
    for i, piece in enumerate(record["pieces"]):
        lines.append("\t\t" + json.dumps(piece) + ("," if i + 1 < len(record["pieces"]) else ""))
    lines += ["\t]", "}"]
    return "\n".join(lines) + "\n"


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read_text(path):
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()
    except OSError:
        return None


# --- legacy layouts (review sheets and legacy references) ------------------------

BACKGROUND = (46, 50, 56, 255)
BRIGHT = (221, 160, 170, 255)    # the intro backdrop behind the login board
THIN_FILL = (0, 0, 0, 130)       # ui.ThinBoard.BOARD_COLOR, black at 0.51
SLOT_FILL, SLOT_DARK, SLOT_LIGHT = (0, 0, 0, 255), (51, 51, 51, 255), (179, 179, 179, 255)


def tile_h(canvas, image, x0, y, x1):
    """Repeats image from x0 toward x1 at 1:1, clipping the last copy, as the
    legacy ExpandedImageBox does."""
    x = x0
    while x < x1:
        canvas.alpha_composite(image.crop((0, 0, min(image.width, x1 - x), image.height)), (x, y))
        x += image.width


def tile_v(canvas, image, x, y0, y1):
    y = y0
    while y < y1:
        canvas.alpha_composite(image.crop((0, 0, image.width, min(image.height, y1 - y))), (x, y))
        y += image.height


def tile_xy(canvas, image, x0, y0, x1, y1):
    y = y0
    while y < y1:
        tile_h(canvas, image.crop((0, 0, image.width, min(image.height, y1 - y))), x0, y, x1)
        y += image.height


def draw_board(canvas, art, s, x, y, w, h):
    """ui.Board at (x, y), w by h in 1x units, from pieces at scale s."""
    c = 32 * s
    x, y, w, h = x * s, y * s, w * s, h * s
    tile_xy(canvas, art["board-c"], x + c, y + c, x + w - c, y + h - c)
    tile_h(canvas, art["board-t"], x + c, y, x + w - c)
    tile_h(canvas, art["board-b"], x + c, y + h - c, x + w - c)
    tile_v(canvas, art["board-l"], x, y + c, y + h - c)
    tile_v(canvas, art["board-r"], x + w - c, y + c, y + h - c)
    for pid, at in (("board-tl", (x, y)), ("board-tr", (x + w - c, y)), ("board-bl", (x, y + h - c)), ("board-br", (x + w - c, y + h - c))):
        canvas.alpha_composite(art[pid], at)


def draw_thinboard(canvas, art, s, x, y, w, h):
    """ui.ThinBoard, its small-size cases included: below 32 px the fill and
    the side lines go, and the corners overlap."""
    c = 16 * s
    x, y, w, h = x * s, y * s, w * s, h * s
    if w > 2 * c and h > 2 * c:
        canvas.alpha_composite(Image.new("RGBA", (w - 2 * c, h - 2 * c), THIN_FILL), (x + c, y + c))
    if w > 2 * c:
        tile_h(canvas, art["thin-t"], x + c, y, x + w - c)
        tile_h(canvas, art["thin-b"], x + c, y + h - c, x + w - c)
    if h > 2 * c:
        tile_v(canvas, art["thin-l"], x, y + c, y + h - c)
        tile_v(canvas, art["thin-r"], x + w - c, y + c, y + h - c)
    for pid, at in (("thin-tl", (x, y)), ("thin-bl", (x, y + h - c)), ("thin-tr", (x + w - c, y)), ("thin-br", (x + w - c, y + h - c))):
        canvas.alpha_composite(art[pid], at)


def draw_titlebar(canvas, art, s, x, y, w):
    b = 32 * s
    x, y, w = x * s, y * s, w * s
    canvas.alpha_composite(art["title-l"], (x, y))
    tile_h(canvas, art["title-c"], x + b, y, x + w - b)
    canvas.alpha_composite(art["title-r"], (x + w - b, y))


def draw_slotbar(canvas, s, x, y, w, h):
    """The code-drawn legacy slot bar (Bar3D): black, 0.2 gray top and left,
    0.7 gray bottom and right, 1 px each at any scale here."""
    x, y, w, h = x * s, y * s, w * s, h * s
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=SLOT_FILL)
    draw.line((x, y, x + w - 1, y), fill=SLOT_DARK, width=s)
    draw.line((x, y, x, y + h - 1), fill=SLOT_DARK, width=s)
    draw.line((x, y + h - s, x + w - 1, y + h - s), fill=SLOT_LIGHT, width=s)
    draw.line((x + w - s, y, x + w - s, y + h - 1), fill=SLOT_LIGHT, width=s)


WINDOW = (280, 160)
LOGIN = (208, 142)


def window_layout(art, s, slot=None):
    """The skin-proof window (ui.Board 280x160 with a TitleBar, its close
    button, an input and two large buttons), on a transparent canvas, with
    its boxes in 1x units. `slot`: the legacy parameter_slot_03 art, else the
    code-drawn slot bar the classic input uses."""
    canvas = Image.new("RGBA", (WINDOW[0] * s, WINDOW[1] * s), (0, 0, 0, 0))
    draw_board(canvas, art, s, 0, 0, WINDOW[0], WINDOW[1])
    title_w = WINDOW[0] - 15
    draw_titlebar(canvas, art, s, 8, 7, title_w)
    canvas.alpha_composite(art["close-01"], ((8 + title_w - 18) * s, (7 + 3) * s))
    if slot is not None:
        canvas.alpha_composite(slot, (24 * s, 52 * s))
    else:
        draw_slotbar(canvas, s, 24, 52, 90, 18)
    canvas.alpha_composite(art["button-large-01"], (24 * s, 110 * s))
    canvas.alpha_composite(art["button-large-02"], (136 * s, 110 * s))
    boxes = {"": [0, 0, WINDOW[0], WINDOW[1]], "proof-titlebar": [8, 7, title_w, 32],
             "proof-close": [8 + title_w - 18, 10, 15, 15], "proof-field": [24, 52, 90, 18],
             "proof-button": [24, 110, 88, 21], "proof-button-over": [136, 110, 88, 21]}
    return canvas, boxes


def login_layout(art, s, loginwindow=None):
    """The legacy login board (uiscript loginwindow.py): the 208x30 connect
    board with Choose, the login window art 35 px lower with its two fields,
    Connect and Exit. `loginwindow`: the legacy art, drawn whole; else the
    one ThinBoard the classic skin draws (AUTHORING.md, Classic skin), with the field art
    at the legacy offsets."""
    canvas = Image.new("RGBA", (LOGIN[0] * s, LOGIN[1] * s), (0, 0, 0, 0))
    if loginwindow is not None:
        draw_thinboard(canvas, art, s, 0, 0, 208, 30)
        canvas.alpha_composite(loginwindow, (0, 35 * s))
    else:
        draw_thinboard(canvas, art, s, 0, 0, LOGIN[0], LOGIN[1])
        for top in (56, 91):
            canvas.alpha_composite(art["login-field"], (44 * s, top * s))
    canvas.alpha_composite(art["button-small-01"], (150 * s, 4 * s))
    canvas.alpha_composite(art["button-large-01"], (15 * s, 114 * s))
    canvas.alpha_composite(art["button-large-01"], (105 * s, 114 * s))
    boxes = {"": [0, 0, LOGIN[0], LOGIN[1]], "connectBoard": [0, 0, 208, 30], "selectConnectButton": [150, 4, 43, 21],
             "loginBoard": [0, 35, 208, 107], "idEditLine": [48, 58, 120, 18], "pwdEditLine": [48, 95, 120, 18],
             "idField": [44, 56, 120, 18], "pwdField": [44, 91, 120, 18],
             "loginButton": [15, 114, 88, 21], "loginExitButton": [105, 114, 88, 21]}
    return canvas, boxes


# --- review sheets -----------------------------------------------------------------

def font(size=14):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def checkerboard(size, cell=8):
    board = Image.new("RGBA", size, (72, 72, 76, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], cell):
        for x in range((y // cell) % 2 * cell, size[0], 2 * cell):
            draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(104, 104, 110, 255))
    return board


def on_background(image, background=None):
    base = background.copy() if background is not None else checkerboard(image.size)
    base.alpha_composite(image)
    return base


def grid(rows, note, pad=10, label_height=18):
    """rows: [[(label, image)]]; one image per cell, left to right. A column
    is as wide as its widest image or label."""
    label_font = font(12)
    widths = [0] * max(len(row) for row in rows)
    for row in rows:
        for i, (label, image) in enumerate(row):
            widths[i] = max(widths[i], image.width, int(label_font.getlength(label)) + 4)
    heights = [max(image.height for _, image in row) + label_height for row in rows]
    top = 28
    sheet = Image.new("RGB", (sum(widths) + pad * (len(widths) + 1), top + sum(heights) + pad * (len(rows) + 1)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 6), note, fill=(235, 235, 235), font=font(14))
    y = top + pad
    for row, height in zip(rows, heights):
        x = pad
        for i, (label, image) in enumerate(row):
            draw.text((x, y), label, fill=(255, 230, 120), font=label_font)
            sheet.paste(image.convert("RGB"), (x, y + label_height))
            x += widths[i] + pad
        y += height + pad
    return sheet


def family(pid):
    if pid.startswith("board-"):
        return "board-base" if pid == "board-c" else "board-corners" if len(pid) == len("board-tl") else "board-edges"
    return re.sub(r"-(0\d|tl|tr|bl|br|t|b|l|r|c)$", "", pid)


def piece_zoom(image_1x):
    """The extra nearest zoom of a piece's row in a review sheet: its 1x cell
    (drawn x4) is at least 120 px on its longer side, so a 16 px piece is
    drawn x8 and x4 and its single texels show."""
    return max(1, -(-120 // (4 * max(image_1x.size))))


def review_sheets(build, out_dir, final=None, note=""):
    """Writes per-family sheets and the two layout sheets. Each row is one
    piece at one physical size: the 1x x4, Lanczos 2x x2, the AI 2x x2 and
    the final 2x x2 on a checkerboard, then the 1x and the final 2x on the
    login backdrop's pink, where a pale fringe in a cut-out shows. A row
    gets a further zoom (piece_zoom). The final cell names the method and
    warnings_2x's counts. Returns the paths."""
    os.makedirs(out_dir, exist_ok=True)
    manifest, results = build.manifest, build.results
    final = final or {pid: result.image for pid, result in results.items()}
    families = []
    for piece in manifest["pieces"]:
        name = family(piece["id"])
        if not families or families[-1][0] != name:
            families.append((name, []))
        families[-1][1].append(piece["id"])
    def zoomed(image, factor):
        return image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST)

    def on_bright(image):
        return on_background(image, Image.new("RGBA", image.size, BRIGHT))

    paths = []
    for name, ids in families:
        rows = []
        for pid in ids:
            result = results[pid]
            zoom = piece_zoom(build.pieces_1x[pid])
            lanczos = result.lanczos if result.lanczos is not None else final[pid]
            one = zoomed(build.pieces_1x[pid], 4 * zoom)
            two = zoomed(final[pid], 2 * zoom)
            cells = [("%s 1x x%d" % (pid, 4 * zoom), on_background(one))]
            cells.append(("Lanczos 2x x%d" % (2 * zoom), on_background(zoomed(lanczos, 2 * zoom))))
            if result.ai is not None:
                cells.append(("AI 2x x%d, MAD %.1f" % (2 * zoom, result.mad), on_background(zoomed(result.ai, 2 * zoom))))
            else:
                blank = Image.new("RGBA", (2 * zoom * lanczos.width, 2 * zoom * lanczos.height), (0, 0, 0, 0))
                cells.append(("AI 2x: none (%s)" % result.method, on_background(blank)))
            warned = warning_text(warnings_2x(build.pieces_1x[pid], final[pid]))
            cells.append(("final 2x x%d: %s" % (2 * zoom, result.method), on_background(two)))
            cells.append(("1x on pink", on_bright(one)))
            cells.append(("final 2x on pink" + (": " + warned if warned else ""), on_bright(two)))
            rows.append(cells)
        path = os.path.join(out_dir, "family-%s.png" % name)
        grid(rows, "%s: 1x | Lanczos 2x | AI 2x | final 2x, then 1x and final 2x on pink; nearest zoom, one physical size "
                   "per row. %s" % (name, note)).save(path)
        paths.append(path)

    art_1x = dict(build.pieces_1x)
    art_2x = dict(final)
    for kind, layout in (("window", window_layout), ("login", login_layout)):
        one, _ = layout(art_1x, 1)
        two, _ = layout(art_2x, 2)
        background = Image.new("RGBA", two.size, BACKGROUND)
        cells = [("1x layout, doubled (nearest)", on_background(nearest2x(one), background)),
                 ("2x layout from the final 2x art", on_background(two, background)),
                 ("1x layout stretched x2, bilinear (the legacy UI scaled)",
                  on_background(one.resize(two.size, Image.Resampling.BILINEAR), background))]
        path = os.path.join(out_dir, "layout-%s.png" % kind)
        grid([cells], "%s layout with the legacy tiling rules, at 2x, unmagnified. %s" % (kind, note)).save(path)
        paths.append(path)
    return paths


# --- commands ----------------------------------------------------------------------

def default_work():
    return os.path.join(WORK_ROOT, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))


def latest_work():
    try:
        runs = sorted(name for name in os.listdir(WORK_ROOT) if os.path.isdir(os.path.join(WORK_ROOT, name, "out")))
    except OSError:
        return None
    return os.path.join(WORK_ROOT, runs[-1]) if runs else None


def cmd_build(no_ai=False, work=None, upscale=None, replay_dir=None):
    manifest = load_manifest()
    work = work or default_work()
    os.makedirs(work, exist_ok=True)
    if replay_dir:
        # The same network output as that run, so only what the manifest
        # changed can change; the record keeps that run's upscaler fields.
        if not os.path.isdir(os.path.join(replay_dir, "out")):
            raise UsageError("--replay needs a work folder with out/: %s" % replay_dir)
        text = read_text(RECORD)
        previous = json.loads(text).get("upscaler") if text else None
        if previous:
            previous = {key: value for key, value in previous.items() if key != "replayed_from"}
        upscale = replay(replay_dir, previous)
    build = Build(manifest)
    build.make_2x(upscale or realesrgan(manifest), work, no_ai)
    record = make_record(build)
    save_png(build.sheet_1x, out_path(manifest, "1x"))
    save_png(build.sheet_2x, out_path(manifest, "2x"))
    write_text(out_path(manifest, "rcss"), render_rcss(manifest, build.rects))
    write_text(RECORD, dump_record(record))
    paths = review_sheets(build, os.path.join(work, "review"), note="work: %s" % work)
    info = build.info
    if not info["ran"]:
        print("upscaler: not used (%s)" % info["error"])
    elif info.get("replayed_from"):
        print("upscaler: replayed %s" % info["replayed_from"])
    else:
        print("upscaler: ran in %.2f s" % info["seconds"])
    # The warning counts are for the reviewer: bevels and highlights that
    # the network sharpens count too, so a count is a place to look.
    for entry in record["pieces"]:
        mad = "" if entry["mad_vs_lanczos"] is None else "MAD %5.2f" % entry["mad_vs_lanczos"]
        warned = warning_text(warnings_2x(build.pieces_1x[entry["id"]], build.results[entry["id"]].image))
        print("  %-18s %-9s %-10s %s" % (entry["id"], entry["method"], mad,
                                         "; ".join(part for part in (entry["note"], "look: " + warned if warned else "") if part)))
    print("sheets %dx%d and %dx%d, %d color-key texel(s) fixed" % (build.sheet_1x.size + build.sheet_2x.size + (record["color_key_fixed"],)))
    print("wrote %s, %s, %s and %s" % (relative(out_path(manifest, "1x")), relative(out_path(manifest, "2x")),
                                       relative(out_path(manifest, "rcss")), relative(RECORD)))
    print("review sheets in %s:" % os.path.join(work, "review"))
    for path in paths:
        print("  " + path)
    return 0


def check_problems(manifest=None, record=None):
    """Everything `check` finds, as messages."""
    manifest = manifest or load_manifest()
    problems = []
    if record is None:
        text = read_text(RECORD)
        if text is None:
            return ["%s is missing (run build)" % relative(RECORD)]
        record = json.loads(text)
    build = Build(manifest)
    try:
        with Image.open(out_path(manifest, "1x")) as opened:
            sheet_1x = opened.convert("RGBA")
        if sheet_1x.size != build.sheet_1x.size or sheet_1x.tobytes() != build.sheet_1x.tobytes():
            problems.append("%s differs from a rebuild from the sources (run build)" % relative(out_path(manifest, "1x")))
    except OSError:
        problems.append("%s is missing (run build)" % relative(out_path(manifest, "1x")))
    if read_text(out_path(manifest, "rcss")) != render_rcss(manifest, build.rects):
        problems.append("%s differs from a regeneration (run rcss or build)" % relative(out_path(manifest, "rcss")))
    try:
        with Image.open(out_path(manifest, "2x")) as opened:
            sheet_2x = opened.convert("RGBA")
    except OSError:
        sheet_2x = None
        problems.append("%s is missing (run build)" % relative(out_path(manifest, "2x")))
    sized_2x = False   # the 2x sheet has the layout's size, so its pieces can be cut out
    if sheet_2x is not None:
        expected = (2 * manifest["sheet_width_1x"], 2 * build.height)
        if sheet_2x.size != expected or list(sheet_2x.size) != record.get("sheet_2x", {}).get("size"):
            problems.append("the 2x sheet is %dx%d; the layout and the record say %dx%d" % (sheet_2x.size + expected))
        else:
            sized_2x = True
            if pixels_sha256(sheet_2x) != record["sheet_2x"].get("pixels_sha256"):
                problems.append("the 2x sheet's pixels differ from the record (run build)")
            bad = gutter_problems(build, sheet_2x, 2)
            if bad:
                problems.append("2x gutters break the wrap/clamp rule around: %s" % ", ".join(bad))
    if record.get("threshold") != manifest["threshold"]:
        problems.append("the record's threshold %s is not the manifest's %s" % (record.get("threshold"), manifest["threshold"]))
    recorded = {entry["id"]: entry for entry in record.get("pieces", [])}
    if [p["id"] for p in manifest["pieces"]] != [entry["id"] for entry in record.get("pieces", [])]:
        problems.append("the record's pieces are not the manifest's (run build)")
    for piece in manifest["pieces"]:
        entry = recorded.get(piece["id"])
        if entry is None:
            continue
        source = piece.get("source")
        if entry.get("source") != source:
            problems.append("piece %s: the record has source %s" % (piece["id"], entry.get("source")))
            continue
        if source:
            if entry.get("source_sha256") != sha256_file(build.sources.path(source)):
                problems.append("piece %s: %s changed since the record (run build)" % (piece["id"], source))
            atlas = build.sources.atlas(source)
            if atlas and entry.get("atlas_sha256") != sha256_file(build.sources.path(atlas)):
                problems.append("piece %s: its atlas %s changed since the record (run build)" % (piece["id"], atlas))
        if entry.get("rect_1x") != list(build.piece_rect(piece["id"], 1)) or entry.get("rect_2x") != list(build.piece_rect(piece["id"], 2)):
            problems.append("piece %s: the record's rectangles are not the layout's" % piece["id"])
        if sized_2x and pixels_sha256(piece_2x_from_sheet(build, sheet_2x, piece["id"])) != entry.get("pixels_2x_sha256"):
            problems.append("piece %s: its 2x pixels differ from the record" % piece["id"])
    for entry in record.get("context_sources", []):
        try:
            if sha256_file(build.sources.path(entry["source"])) != entry["source_sha256"]:
                problems.append("context source %s changed since the record (run build)" % entry["source"])
        except ArtError as error:
            problems.append(str(error))
    return problems


def cmd_check():
    problems = check_problems()
    for problem in problems:
        print("nui_classic_art: %s" % problem, file=sys.stderr)
    if not problems:
        print("nui_classic_art: the sheets, the sprites RCSS and the record are up to date")
    return 1 if problems else 0


def cmd_rcss(threshold=None, force_1x=False, out=None):
    manifest = load_manifest()
    if threshold is not None and not 1.0 < threshold <= 2.0:
        raise UsageError("--threshold is a dp ratio above 1 and at most 2")
    build = Build(manifest)
    path = out or out_path(manifest, "rcss")
    write_text(path, render_rcss(manifest, build.rects, threshold, force_1x))
    print("wrote %s" % path)
    return 0


def cmd_legacy_ref(out):
    """The legacy references, drawn from the original files with the legacy
    rules: the skin-proof window and the login board, with their boxes."""
    manifest = load_manifest()
    sources = Sources()
    pieces_1x = {p["id"]: piece_image(sources, p) for p in manifest["pieces"]}
    os.makedirs(out, exist_ok=True)
    slot = sources.image("ETC/ymir work/ui/public/parameter_slot_03.sub")
    loginwindow = sources.image("ETC/ymir work/ui/intro/login/loginwindow.sub")
    for kind, (image, boxes) in (("window", window_layout(pieces_1x, 1, slot=slot)),
                                 ("login", login_layout(pieces_1x, 1, loginwindow=loginwindow))):
        save_png(image, os.path.join(out, "%s-1x.png" % kind))
        write_text(os.path.join(out, "%s-boxes.json" % kind), json.dumps(boxes, indent="\t", sort_keys=True) + "\n")
        print("wrote %s and %s" % (os.path.join(out, "%s-1x.png" % kind), os.path.join(out, "%s-boxes.json" % kind)))
    return 0


def cmd_sheets(out, work=None):
    """Review sheets from the committed sheets; the AI column replays a
    build's network outputs (--work, else the newest work folder)."""
    manifest = load_manifest()
    build = Build(manifest)
    work = work or latest_work()
    with Image.open(out_path(manifest, "2x")) as opened:
        sheet_2x = opened.convert("RGBA")
    final = {p["id"]: piece_2x_from_sheet(build, sheet_2x, p["id"]) for p in manifest["pieces"]}
    upscale = replay(work) if work else (lambda inputs, _work: (None, {"error": "no work folder"}))
    build.results, _ = make_2x(manifest, build.pieces_1x, build.composites, upscale, work)
    for path in review_sheets(build, out, final=final, note="AI column from %s" % (work or "nothing")):
        print("wrote %s" % path)
    return 0


USAGE = __doc__.split("\n\n")[0] + "\n"


def parse(argv):
    """(command, options); UsageError for anything else."""
    if not argv or argv[0] in ("-h", "--help", "help"):
        raise UsageError("")
    command, rest = argv[0], list(argv[1:])
    flags = {"build": {"--no-ai": False, "--work": True, "--replay": True}, "check": {},
             "rcss": {"--threshold": True, "--force-1x": False, "--out": True},
             "legacy-ref": {"--out": True}, "sheets": {"--out": True, "--work": True}}
    if command not in flags:
        raise UsageError("unknown command %r" % command)
    options = {}
    while rest:
        flag = rest.pop(0)
        if flag not in flags[command]:
            raise UsageError("%s takes no %s" % (command, flag))
        if flags[command][flag]:
            if not rest:
                raise UsageError("%s needs a value" % flag)
            options[flag] = rest.pop(0)
        else:
            options[flag] = True
    if command in ("legacy-ref", "sheets") and "--out" not in options:
        raise UsageError("%s needs --out DIR" % command)
    if "--threshold" in options:
        try:
            options["--threshold"] = float(options["--threshold"])
        except ValueError:
            raise UsageError("--threshold takes a number such as 1.5")
    return command, options


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        command, options = parse(argv)
        if command == "build":
            return cmd_build(no_ai=options.get("--no-ai", False), work=options.get("--work"), replay_dir=options.get("--replay"))
        if command == "check":
            return cmd_check()
        if command == "rcss":
            return cmd_rcss(options.get("--threshold"), options.get("--force-1x", False), options.get("--out"))
        if command == "legacy-ref":
            return cmd_legacy_ref(options["--out"])
        return cmd_sheets(options["--out"], options.get("--work"))
    except UsageError as error:
        if str(error):
            print("nui_classic_art: %s" % error, file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    except ArtError as error:
        print("nui_classic_art: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
