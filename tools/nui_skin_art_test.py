"""Unit tests for nui_skin_art.py: python3 -B -m unittest nui_skin_art_test (from tools/;
-B keeps __pycache__ out of the repository)."""
import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest

from PIL import Image

import nui_skin_art as art


def manifest():
    return {
        "name": "skin", "out_dir": "out", "scales": [1, 2], "sheet_width": 64,
        "sprites": [
            {"id": "fill", "kind": "chamfer-fill", "size": 16, "chamfer": 4, "corners": ["tl", "br"], "alpha": 1.0},
            {"id": "faint", "kind": "chamfer-fill", "size": 16, "chamfer": 4, "corners": ["tl", "br"], "alpha": 0.3},
            {"id": "edge", "kind": "chamfer-edge", "size": 32, "chamfer": 4, "corners": ["tl", "br"], "line": 1, "glow": 4,
             "glow_alpha": 0.5},
            {"id": "line", "kind": "chamfer-edge", "size": 16, "chamfer": 4, "corners": ["tr"], "line": 1, "glow": 0},
        ],
    }


def alpha_at(alpha, x, y):
    return int(alpha[y][x] * 255.0 + 0.5)


class Validation(unittest.TestCase):

    def refuse(self, change, text):
        broken = copy.deepcopy(manifest())
        change(broken)
        with self.assertRaises(art.ArtError) as caught:
            art.validate(broken)
        self.assertIn(text, str(caught.exception))

    def test_the_example_manifest_is_valid(self):
        art.validate(manifest())

    def test_an_unknown_key_is_refused(self):
        self.refuse(lambda m: m.update(colour="red"), "unknown key colour")
        self.refuse(lambda m: m["sprites"][0].update(tint="red"), "unknown key tint")

    def test_scales_start_at_one_and_hold_at_most_two(self):
        self.refuse(lambda m: m.update(scales=[2]), "scales")
        self.refuse(lambda m: m.update(scales=[1, 2, 3]), "at most one more")

    def test_corners_are_the_four_names_once_each(self):
        self.refuse(lambda m: m["sprites"][0].update(corners=["tl", "tl"]), "corners")
        self.refuse(lambda m: m["sprites"][0].update(corners=["top"]), "corners")

    def test_ids_are_unique_and_never_end_in_inner(self):
        self.refuse(lambda m: m["sprites"][1].update(id="fill"), "unique")
        self.refuse(lambda m: m["sprites"][0].update(id="fill-inner"), "-inner")

    def test_the_ninepatch_rectangle_holds_the_chamfer_and_leaves_a_center(self):
        self.refuse(lambda m: m["sprites"][0].update(inner=3), "does not hold")
        self.refuse(lambda m: m["sprites"][0].update(inner=8), "leaves no center")

    def test_a_glow_needs_its_strength(self):
        self.refuse(lambda m: m["sprites"][2].update(glow_alpha=0), "glow_alpha")

    def test_the_shipped_manifests_are_valid(self):
        for path in art.manifests():
            art.load_manifest(path)


class Drawing(unittest.TestCase):

    def test_a_fill_is_opaque_inside_and_clear_in_its_cut_corners(self):
        alpha = art.draw(manifest()["sprites"][0], 1)
        self.assertEqual(alpha_at(alpha, 8, 8), 255)
        self.assertEqual(alpha_at(alpha, 0, 0), 0)
        self.assertEqual(alpha_at(alpha, 15, 15), 0)
        # Uncut corners stay square.
        self.assertEqual(alpha_at(alpha, 15, 0), 255)
        self.assertEqual(alpha_at(alpha, 0, 15), 255)
        # The 45-degree cut: half of the texel the diagonal crosses.
        self.assertEqual(alpha_at(alpha, 3, 0), 128)
        self.assertEqual(alpha_at(alpha, 4, 0), 255)

    def test_a_faint_fill_carries_its_alpha(self):
        alpha = art.draw(manifest()["sprites"][1], 1)
        self.assertEqual(alpha_at(alpha, 8, 8), 77)

    def test_an_edge_is_a_line_at_its_inset_with_a_glow_around_it(self):
        sprite = manifest()["sprites"][2]
        alpha = art.draw(sprite, 1)
        # The line runs along the inset (4 px), across the straight sides.
        self.assertEqual(alpha_at(alpha, 16, 4), 255)
        self.assertEqual(alpha_at(alpha, 4, 16), 255)
        self.assertEqual(alpha_at(alpha, 27, 16), 255)
        # The glow next to the line is below glow_alpha (its peak is on the
        # line), and fades outward.
        outside = alpha_at(alpha, 16, 3)
        self.assertTrue(64 <= outside <= 128, outside)
        self.assertLess(alpha_at(alpha, 16, 1), outside)
        self.assertLess(alpha_at(alpha, 16, 0), 8)
        # The middle is clear: only the line glows.
        self.assertEqual(alpha_at(alpha, 16, 16), 0)

    def test_an_edge_without_glow_has_its_line_on_the_sprite_side(self):
        alpha = art.draw(manifest()["sprites"][3], 1)
        self.assertEqual(alpha_at(alpha, 0, 8), 255)
        self.assertEqual(alpha_at(alpha, 8, 15), 255)
        self.assertEqual(alpha_at(alpha, 8, 8), 0)
        # The cut corner (tr): its tip is clear.
        self.assertEqual(alpha_at(alpha, 15, 0), 0)

    def test_the_straight_sides_are_uniform_inside_the_ninepatch_rectangle(self):
        for sprite in manifest()["sprites"]:
            for scale in (1, 2):
                alpha = art.draw(sprite, scale)
                size, inner = sprite["size"] * scale, art.default_inner(sprite) * scale
                for y in range(size):
                    row = [alpha_at(alpha, x, y) for x in range(inner, size - inner)]
                    self.assertEqual(len(set(row)), 1, (sprite["id"], scale, y))
                for x in range(size):
                    column = [alpha_at(alpha, x, y) for y in range(inner, size - inner)]
                    self.assertEqual(len(set(column)), 1, (sprite["id"], scale, x))

    def test_the_2x_art_is_drawn_from_the_numbers_doubled_not_upscaled(self):
        sprite = manifest()["sprites"][2]
        one, two = art.draw(sprite, 1), art.draw(sprite, 2)
        self.assertEqual(len(two), 64)
        # A 2 px line at an 8 px inset.
        self.assertEqual(alpha_at(two, 32, 8), 255)
        self.assertEqual(alpha_at(two, 32, 9), 255)
        self.assertLess(alpha_at(two, 32, 10), 255)
        upscaled = [[one[y // 2][x // 2] for x in range(64)] for y in range(64)]
        self.assertNotEqual([[alpha_at(two, x, y) for x in range(64)] for y in range(64)],
                            [[alpha_at(upscaled, x, y) for x in range(64)] for y in range(64)])

    def test_drawing_is_deterministic(self):
        first = art.build_outputs(manifest())
        second = art.build_outputs(manifest())
        for path, value in first.items():
            other = second[path]
            self.assertEqual(value if isinstance(value, str) else value.tobytes(),
                             other if isinstance(other, str) else other.tobytes())


class Sheets(unittest.TestCase):

    def setUp(self):
        self.outputs = art.build_outputs(manifest())
        self.rcss = self.outputs[os.path.join("out", "skin-sprites.rcss")]

    def rect(self, block, name):
        for line in block.splitlines():
            if line.strip().startswith(name + ":"):
                return [int(v[:-2]) for v in line.split(":")[1].strip().rstrip(";").split()]
        self.fail("no sprite %s" % name)

    def test_every_sprite_has_its_inner_rectangle_inside_it(self):
        one = self.rcss.split("@media")[0]
        for sprite in manifest()["sprites"]:
            x, y, w, h = self.rect(one, "skin-" + sprite["id"])
            ix, iy, iw, ih = self.rect(one, "skin-%s-inner" % sprite["id"])
            self.assertEqual((w, h), (sprite["size"], sprite["size"]))
            self.assertTrue(x < ix and y < iy and ix + iw < x + w and iy + ih < y + h)

    def test_the_2x_block_doubles_the_1x_rectangles_under_min_resolution(self):
        one, two = self.rcss.split("@media (min-resolution: 1.125x)")
        self.assertIn("resolution: 2x;", two)
        self.assertIn("src: skin-2x.png;", two)
        for sprite in manifest()["sprites"]:
            for name in ("skin-" + sprite["id"], "skin-%s-inner" % sprite["id"]):
                self.assertEqual([2 * v for v in self.rect(one, name)], self.rect(two, name))

    def test_the_sheet_holds_each_sprite_at_its_rectangle_inside_a_gutter_of_its_own_edge(self):
        sheet = self.outputs[os.path.join("out", "skin-1x.png")]
        x, y, w, h = self.rect(self.rcss.split("@media")[0], "skin-edge")
        drawn = art.to_image(art.draw(manifest()["sprites"][2], 1))
        self.assertEqual(sheet.crop((x, y, x + w, y + h)).tobytes(), drawn.tobytes())
        pixels = sheet.load()
        for offset in (1, 2):
            for v in range(h):
                self.assertEqual(pixels[x - offset, y + v], pixels[x, y + v])
                self.assertEqual(pixels[x + w - 1 + offset, y + v], pixels[x + w - 1, y + v])
            for u in range(w):
                self.assertEqual(pixels[x + u, y - offset], pixels[x + u, y])
                self.assertEqual(pixels[x + u, y + h - 1 + offset], pixels[x + u, y + h - 1])

    def test_the_art_is_white_so_no_texel_is_the_color_key(self):
        for name, value in self.outputs.items():
            if isinstance(value, Image.Image):
                colors = {pixel[:3] for pixel in value.getdata()}
                self.assertEqual(colors, {(255, 255, 255)}, name)

    def test_a_sprite_wider_than_the_sheet_is_refused(self):
        wide = manifest()
        wide["sheet_width"] = 16
        with self.assertRaises(art.ArtError):
            art.build_outputs(wide)


class Commands(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="skin-art-test-")
        self.saved = art.REPO
        art.REPO = self.root
        self.path = os.path.join(self.root, "art.json")
        with open(self.path, "w") as handle:
            json.dump(manifest(), handle)

    def tearDown(self):
        art.REPO = self.saved
        shutil.rmtree(self.root, ignore_errors=True)

    def run_command(self, command):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = art.main([command, "--manifest", self.path])
        return status, out.getvalue()

    def test_build_writes_and_check_then_passes(self):
        status, text = self.run_command("check")
        self.assertEqual(status, 1)
        self.assertIn("stale", text)
        self.assertEqual(self.run_command("build")[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "out", "skin-2x.png")))
        status, text = self.run_command("check")
        self.assertEqual(status, 0, text)
        self.assertIn("unchanged", self.run_command("build")[1])

    def test_check_finds_a_changed_sheet_and_a_changed_rcss(self):
        self.run_command("build")
        sheet = os.path.join(self.root, "out", "skin-1x.png")
        with Image.open(sheet) as image:
            image.load()
            changed = image.copy()
        changed.putpixel((0, 0), (255, 255, 255, 1))
        changed.save(sheet)
        self.assertEqual(self.run_command("check")[0], 1)
        self.run_command("build")
        with open(os.path.join(self.root, "out", "skin-sprites.rcss"), "a") as handle:
            handle.write("\n")
        self.assertEqual(self.run_command("check")[0], 1)

    def test_a_broken_manifest_fails_with_its_reason(self):
        with open(self.path, "w") as handle:
            json.dump({"name": "skin"}, handle)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(art.main(["check", "--manifest", self.path]), 1)
        self.assertIn("out_dir", err.getvalue())


class Shipped(unittest.TestCase):

    def test_the_committed_sheets_are_what_build_writes(self):
        for path in art.manifests():
            for relative, value in art.build_outputs(art.load_manifest(path)).items():
                self.assertTrue(art.same(os.path.join(art.REPO, relative), value), "%s is stale; run %s" % (relative, art.COMMAND))


if __name__ == "__main__":
    unittest.main()
