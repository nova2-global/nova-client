"""Unit tests for nui_classic_art.py: python3 -B -m unittest nui_classic_art_test (from tools/;
-B keeps __pycache__ out of the repository). No GPU: the upscaler is a stand-in function."""
import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest

from PIL import Image

import nui_classic_art as art


def solid(w, h, color):
    return Image.new("RGBA", (w, h), color)


def gradient(w, h):
    """A piece whose every texel differs, so a gutter shows where it comes from."""
    image = Image.new("RGBA", (w, h))
    image.putdata([(16 * x % 256, 16 * y % 256, (x * 7 + y * 13) % 256, 255) for y in range(h) for x in range(w)])
    return image


class Fixture(object):
    """A small assets tree: a TGA-free set of PNG pieces, an atlas with a v1.0
    and a v2.0 .sub, and a manifest over them."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="classic-art-test-")
        self.assets = os.path.join(self.root, "assets")
        ui = os.path.join(self.assets, "ETC", "ymir work", "ui")
        os.makedirs(os.path.join(ui, "public"))
        os.makedirs(os.path.join(ui, "intro", "login"))
        os.makedirs(os.path.join(ui, "pattern"))
        atlas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        atlas.paste(gradient(20, 12), (4, 8))
        atlas.save(os.path.join(ui, "Public.png"))
        with open(os.path.join(ui, "public", "button.sub"), "w") as handle:
            handle.write('title subImage\nversion 1.0\nimage "public.png"\nleft 4\ntop 8\nright 24\nbottom 20')
        login = Image.new("RGBA", (40, 30), (10, 20, 30, 255))
        login.save(os.path.join(ui, "intro", "login", "login.png"))
        with open(os.path.join(ui, "intro", "login", "window.sub"), "w") as handle:
            handle.write('title subImage\nversion 2.0\nimage "login.png"\nleft 0\ntop 0\nright 40\nbottom 30\n')
        gradient(16, 12).save(os.path.join(ui, "pattern", "edge.png"))
        gradient(12, 12).save(os.path.join(ui, "pattern", "corner.png"))

    def manifest(self):
        return {
            "version": 1, "name": "skin", "out_dir": "out", "sheet_width_1x": 64, "gutter_1x": 2,
            "threshold": 1.125,
            "upscaler": {"dir": "E:\\tools", "exe": "up.exe", "model": "realesr-animevideov3", "scale": 2, "tile": 512},
            "recipe": {"method": "av3cd", "detail": 0.5, "garbage_mad": 30},
            "contexts": [
                {"id": "edge", "size": [60, 12], "layers": [
                    {"piece": "corner", "at": [0, 0]},
                    {"piece": "edge", "at": [12, 0]}, {"piece": "edge", "at": [28, 0]}, {"piece": "edge", "at": [44, 0]}]},
            ],
            "pieces": [
                {"id": "corner", "source": "ETC/ymir work/ui/pattern/corner.png", "tile": "none", "context": "edge", "cut_at": [0, 0]},
                {"id": "edge", "source": "ETC/ymir work/ui/pattern/edge.png", "tile": "x", "context": "edge", "cut_at": [28, 0]},
                {"id": "button", "source": "ETC/ymir work/ui/public/button.sub", "tile": "none", "slices": [3, 4]},
                {"id": "fill", "fill": "#00000082", "size": [8, 8], "tile": "xy"},
            ],
        }

    def sources(self):
        return art.Sources(self.assets)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)

    def build(self, manifest=None):
        manifest = manifest or self.fixture.manifest()
        art.validate_manifest(manifest)
        return art.Build(manifest, self.fixture.sources())


def fake_upscaler(transform=None, fail=None):
    """An upscaler that returns a nearest 2x of each input, changed by
    `transform`; or fails with the message `fail`."""
    calls = []

    def upscale(inputs, work):
        calls.append(sorted(inputs))
        if fail:
            return None, {"exe": "", "exe_sha256": "", "model": "", "ran": False, "seconds": 0.0, "error": fail}
        outputs = {}
        for name, image in inputs.items():
            out = image.resize((2 * image.width, 2 * image.height), Image.Resampling.NEAREST)
            outputs[name] = transform(name, out) if transform else out
        return outputs, {"exe": "", "exe_sha256": "", "model": "", "ran": True, "seconds": 0.0, "error": ""}
    upscale.calls = calls
    return upscale


class Manifest(FixtureTest):
    def assertRejected(self, manifest, fragment):
        with self.assertRaises(art.ArtError) as caught:
            art.validate_manifest(manifest)
        self.assertIn(fragment, str(caught.exception))

    def test_the_fixture_and_the_committed_manifest_are_valid(self):
        art.validate_manifest(self.fixture.manifest())
        art.load_manifest()

    def test_a_tiled_piece_without_a_context_is_refused(self):
        manifest = self.fixture.manifest()
        del manifest["pieces"][1]["context"], manifest["pieces"][1]["cut_at"]
        self.assertRejected(manifest, "tiles on x, so it needs a context")

    def test_a_tiled_piece_whose_context_lacks_its_neighbors_is_refused(self):
        manifest = self.fixture.manifest()
        manifest["contexts"][0]["layers"].pop()          # no copy after the cut box
        with self.assertRaises(art.ArtError) as caught:
            self.build(manifest)
        self.assertIn("holds no copy of it after the cut box", str(caught.exception))

    def test_a_cut_box_that_misses_the_piece_is_refused(self):
        manifest = self.fixture.manifest()
        manifest["pieces"][1]["cut_at"] = [20, 0]
        with self.assertRaises(art.ArtError) as caught:
            self.build(manifest)
        self.assertIn("does not hold its pixels", str(caught.exception))

    def test_a_forced_method_needs_a_reason(self):
        manifest = self.fixture.manifest()
        manifest["pieces"][2]["method"] = "nearest"
        self.assertRejected(manifest, "needs a why")
        manifest["pieces"][2]["method"] = "bicubic"
        manifest["pieces"][2]["why"] = "test"
        self.assertRejected(manifest, "method is lanczos or nearest")

    def test_ids_keys_and_fills_are_checked(self):
        cases = [
            (lambda m: m["pieces"][0].update(id="Corner"), "id of [a-z0-9-]+"),
            (lambda m: m["pieces"].append(dict(m["pieces"][0])), "appears twice"),
            (lambda m: m["pieces"][0].update(colour="red"), "unknown key colour"),
            (lambda m: m["pieces"][3].update(fill="#000000"), "fill is #rrggbbaa"),
            (lambda m: m["pieces"][0].update(context="nowhere"), "no context 'nowhere'"),
            (lambda m: m["pieces"][2].update(cut_at=[0, 0]), "cut_at needs a context"),
            (lambda m: m["contexts"][0]["layers"].append({"piece": "ghost", "at": [0, 0]}), "no piece 'ghost'"),
            (lambda m: m["pieces"][0].update(source="x.jpg"), "source is a"),
            (lambda m: m["upscaler"].update(scale=4), "scale must be 2"),
        ]
        for change, fragment in cases:
            manifest = self.fixture.manifest()
            change(manifest)
            self.assertRejected(manifest, fragment)


class SubFiles(FixtureTest):
    def test_a_version_1_sub_names_its_atlas_under_ymir_work_ui_of_its_group(self):
        info = art.parse_sub('title subImage\nversion 1.0\nimage "Public.dds"\nleft 25\ntop 425\nright 40\nbottom 440')
        self.assertEqual(info, {"version": "1.0", "image": "Public.dds", "rect": (25, 425, 40, 440)})
        self.assertEqual(art.sub_atlas("ETC/ymir work/ui/public/close_button_01.sub", info), "ETC/ymir work/ui/Public.dds")

    def test_a_version_2_sub_names_its_atlas_next_to_itself(self):
        info = art.parse_sub('title subImage\nversion 2.0\nimage "login.dds"\nleft 0\ntop 0\nright 208\nbottom 107\n')
        self.assertEqual(art.sub_atlas("ETC/ymir work/ui/intro/login/loginwindow.sub", info),
                         "ETC/ymir work/ui/intro/login/login.dds")

    def test_a_sub_region_decodes_from_its_atlas_without_regard_to_case(self):
        sources = self.fixture.sources()
        self.assertEqual(sources.image("ETC/ymir work/ui/public/button.sub").tobytes(), gradient(20, 12).tobytes())
        self.assertEqual(sources.image("etc/YMIR WORK/ui/intro/login/window.sub").size, (40, 30))

    def test_a_broken_sub_is_an_error(self):
        for text in ("version 1.0\nleft 0\ntop 0\nright 4\nbottom 4", 'image "a.dds"\nleft 0\ntop 0\nright 0\nbottom 4',
                     'image "a.dds"\nleft x\ntop 0\nright 4\nbottom 4'):
            with self.assertRaises(art.ArtError):
                art.parse_sub(text)


class Packing(FixtureTest):
    def test_packing_is_deterministic_and_nothing_overlaps(self):
        sizes = {"a": (30, 10), "b": (12, 30), "c": (12, 30), "d": (5, 5), "e": (40, 8), "f": (5, 5)}
        first = art.pack(sizes, 64, 2)
        self.assertEqual(first, art.pack(dict(reversed(list(sizes.items()))), 64, 2))
        positions, height = first
        boxes = [(x, y, x + sizes[k][0] + 4, y + sizes[k][1] + 4) for k, (x, y) in positions.items()]
        for i, a in enumerate(boxes):
            self.assertTrue(a[2] <= 64 and a[3] <= height)
            for b in boxes[i + 1:]:
                self.assertFalse(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3], (a, b))
        self.assertEqual(height, 64)

    def test_taller_pieces_go_first_and_a_full_shelf_starts_a_new_one(self):
        positions, height = art.pack({"wide": (50, 4), "tall": (4, 50), "next": (40, 4)}, 64, 2)
        self.assertEqual(positions["tall"], (0, 0))
        self.assertEqual(positions["wide"], (8, 0))
        self.assertEqual(positions["next"], (0, 54), "below the tallest piece of the first shelf")
        self.assertEqual(height, 64)

    def test_the_sheet_height_is_a_power_of_two_of_at_least_64(self):
        self.assertEqual(art.pack({"a": (10, 10)}, 64, 2)[1], 64)
        self.assertEqual(art.pack({"a": (10, 70)}, 64, 2)[1], 128)


class Gutters(unittest.TestCase):
    def test_a_piece_that_does_not_tile_extrudes_its_edges(self):
        piece = gradient(6, 4)
        padded = art.with_gutter(piece, 2, "none")
        self.assertEqual(padded.size, (10, 8))
        self.assertEqual(padded.crop((2, 2, 8, 6)).tobytes(), piece.tobytes())
        for x in range(10):
            for y in range(8):
                u, v = min(max(x - 2, 0), 5), min(max(y - 2, 0), 3)
                self.assertEqual(padded.getpixel((x, y)), piece.getpixel((u, v)), (x, y))

    def test_a_piece_wraps_on_the_axes_it_tiles_on_and_clamps_on_the_other(self):
        piece = gradient(6, 4)
        padded = art.with_gutter(piece, 2, "x")
        for x in range(10):
            for y in range(8):
                u, v = (x - 2) % 6, min(max(y - 2, 0), 3)
                self.assertEqual(padded.getpixel((x, y)), piece.getpixel((u, v)), (x, y))
        both = art.with_gutter(piece, 4, "xy")
        self.assertEqual(both.getpixel((0, 0)), piece.getpixel(((0 - 4) % 6, (0 - 4) % 4)))

    def test_the_committed_gutter_check_finds_a_broken_ring(self):
        fixture = Fixture()
        self.addCleanup(fixture.close)
        manifest = fixture.manifest()
        build = art.Build(manifest, fixture.sources())
        build.make_2x(fake_upscaler(), None)
        self.assertEqual(art.gutter_problems(build, build.sheet_2x, 2), [])
        self.assertEqual(art.gutter_problems(build, build.sheet_1x, 1), [])
        x, y, w, h = build.piece_rect("edge", 2)
        build.sheet_2x.putpixel((x - 1, y + 1), (1, 2, 3, 255))
        self.assertEqual(art.gutter_problems(build, build.sheet_2x, 2), ["edge"])


class Rects(FixtureTest):
    def test_2x_rects_are_twice_the_1x_ones_and_slices_follow_their_piece(self):
        build = self.build()
        names = [name for name, _, _ in build.rects]
        self.assertEqual(names, ["skin-corner", "skin-edge", "skin-button", "skin-button-l", "skin-button-c",
                                 "skin-button-r", "skin-fill"])
        for _, rect_1x, rect_2x in build.rects:
            self.assertEqual(rect_2x, tuple(2 * v for v in rect_1x))
        rects = {name: rect for name, rect, _ in build.rects}
        x, y, w, h = rects["skin-button"]
        self.assertEqual((w, h), (20, 12))
        self.assertEqual(rects["skin-button-l"], (x, y, 3, h))
        self.assertEqual(rects["skin-button-c"], (x + 3, y, 13, h))
        self.assertEqual(rects["skin-button-r"], (x + 16, y, 4, h))

    def test_the_1x_sheet_holds_the_exact_legacy_pixels_at_each_rect(self):
        build = self.build()
        x, y, w, h = build.piece_rect("button", 1)
        self.assertEqual(build.sheet_1x.crop((x, y, x + w, y + h)).tobytes(), gradient(20, 12).tobytes())
        self.assertEqual(build.piece_rect("button", 1)[:2], tuple(v + 2 for v in build.positions["button"]))

    def test_slices_must_leave_a_center(self):
        manifest = self.fixture.manifest()
        manifest["pieces"][2]["slices"] = [10, 10]
        with self.assertRaises(art.ArtError):
            self.build(manifest)


class Rcss(FixtureTest):
    def test_the_sheets_share_sprite_names_and_the_2x_one_sits_in_a_resolution_block(self):
        build = self.build()
        text = art.render_rcss(build.manifest, build.rects)
        self.assertTrue(text.startswith("/* Generated by tools/nui_classic_art.py from tools/classic_art/manifest.json.\n"))
        self.assertIn("from a dp ratio of 1.125 up", text)
        self.assertIn("\n@spritesheet skin-1x\n{\n\tsrc: skin-1x.png;\n\tresolution: 1x;\n", text)
        self.assertIn("\n@media (min-resolution: 1.125x)\n{\n\t@spritesheet skin-2x\n\t{\n\t\tsrc: skin-2x.png;\n\t\tresolution: 2x;\n", text)
        x, y, w, h = build.piece_rect("corner", 1)
        self.assertIn("\n\tskin-corner: %dpx %dpx %dpx %dpx;\n" % (x, y, w, h), text)
        self.assertIn("\n\t\tskin-corner: %dpx %dpx %dpx %dpx;\n" % (2 * x, 2 * y, 2 * w, 2 * h), text)
        self.assertTrue(text.endswith("\t}\n}\n"))
        one = text[text.index("@spritesheet skin-1x"):text.index("@media")]
        two = text[text.index("@media"):]
        names = lambda block: [line.split(":")[0].strip() for line in block.splitlines() if line.strip().startswith("skin-")]
        self.assertEqual(names(one), names(two))

    def test_threshold_and_force_1x(self):
        build = self.build()
        text = art.render_rcss(build.manifest, build.rects, threshold=1.5)
        self.assertIn("@media (min-resolution: 1.5x)", text)
        self.assertIn("from a dp ratio of 1.5 up", text)
        self.assertIn("@media (min-resolution: 2x)", art.render_rcss(build.manifest, build.rects, threshold=2.0))
        forced = art.render_rcss(build.manifest, build.rects, force_1x=True)
        self.assertNotIn("@media", forced)
        self.assertNotIn("skin-2x", forced)
        self.assertIn("ratio, which is NovaUI's UI scale).\n   Validation only: the 1x sheet at every scale. */\n", forced)


class TheTwoX(FixtureTest):
    def test_the_upscaler_sees_each_context_once_and_every_standalone_piece(self):
        build = self.build()
        upscale = fake_upscaler()
        build.make_2x(upscale, None)
        self.assertEqual(upscale.calls, [["context-edge", "piece-button"]])
        self.assertEqual(build.results["edge"].method, "av3cd")
        self.assertEqual(build.results["fill"].method, "generated")
        self.assertEqual(build.results["fill"].image.getpixel((3, 3)), (0, 0, 0, 0x82))
        self.assertEqual(build.sheet_2x.size, (128, 128))

    def test_the_size_guard_keeps_a_small_input_from_the_upscaler(self):
        manifest = self.fixture.manifest()
        manifest["pieces"][2]["crop"] = [0, 0, 20, 10]   # 10 px tall
        build = self.build(manifest)
        upscale = fake_upscaler()
        with self.assertRaises(art.ArtError) as caught:
            build.make_2x(upscale, None)
        self.assertIn("piece-button is 20x10", str(caught.exception))
        self.assertEqual(upscale.calls, [], "the upscaler is never called")

    def test_a_piece_far_from_lanczos_falls_back_to_lanczos(self):
        def garbage(name, image):
            return Image.new("RGB", image.size, (255, 0, 255)) if name == "piece-button" else image
        build = self.build()
        build.make_2x(fake_upscaler(garbage), None)
        result = build.results["button"]
        self.assertEqual(result.method, "lanczos")
        self.assertTrue(result.note.startswith("garbage guard (MAD "), result.note)
        self.assertGreater(result.mad, 30)
        self.assertEqual(result.image.tobytes(), art.lanczos2x(gradient(20, 12)).tobytes())
        self.assertEqual(build.results["edge"].method, "av3cd")

    def test_a_failed_run_makes_every_ai_piece_lanczos_and_says_why(self):
        build = self.build()
        build.make_2x(fake_upscaler(fail="exit code 1"), None)
        for pid in ("corner", "edge", "button"):
            self.assertEqual(build.results[pid].method, "lanczos")
            self.assertEqual(build.results[pid].note, "upscaler failed: exit code 1")

    def test_no_ai_never_calls_the_upscaler(self):
        build = self.build()
        upscale = fake_upscaler()
        build.make_2x(upscale, None, no_ai=True)
        self.assertEqual(upscale.calls, [])
        self.assertEqual({r.method for r in build.results.values()}, {"lanczos", "generated"})

    def test_a_context_piece_falls_back_to_the_cut_of_the_lanczos_composite(self):
        build = self.build()
        build.make_2x(fake_upscaler(fail="no GPU"), None)
        composite = art.lanczos2x(build.composites["edge"])
        self.assertEqual(build.results["edge"].image.tobytes(), composite.crop((56, 0, 88, 24)).tobytes())

    def test_a_forced_method_skips_the_upscaler_for_that_piece(self):
        manifest = self.fixture.manifest()
        manifest["pieces"][2].update(method="nearest", why="pixel art")
        build = self.build(manifest)
        upscale = fake_upscaler()
        build.make_2x(upscale, None)
        self.assertEqual(upscale.calls, [["context-edge"]])
        self.assertEqual(build.results["button"].method, "nearest")
        self.assertEqual(build.results["button"].note, "pixel art")
        self.assertEqual(build.results["button"].image.tobytes(), art.nearest2x(gradient(20, 12)).tobytes())

    def test_a_review_note_reaches_the_record_after_the_builds_own_reason(self):
        def garbage(name, image):
            return Image.new("RGB", image.size, (255, 0, 255)) if name == "piece-button" else image
        manifest = self.fixture.manifest()
        manifest["pieces"][1]["note"] = "checked by eye"
        manifest["pieces"][2]["note"] = "the AI piece looked clean"
        build = self.build(manifest)
        build.make_2x(fake_upscaler(garbage), None)
        self.assertEqual(build.results["edge"].note, "checked by eye")
        self.assertTrue(build.results["button"].note.startswith("garbage guard (MAD "))
        self.assertTrue(build.results["button"].note.endswith("; the AI piece looked clean"))
        manifest["pieces"][1]["note"] = " "
        with self.assertRaises(art.ArtError):
            art.validate_manifest(manifest)

    def test_a_piece_detail_overrides_the_recipe_for_its_context(self):
        def noisy(name, image):
            return image.filter(art.ImageFilter.GaussianBlur(2))
        manifest = self.fixture.manifest()
        for piece in manifest["pieces"][:2]:
            piece["detail"] = 1.25
        build = self.build(manifest)
        build.make_2x(fake_upscaler(noisy), None)
        self.assertEqual(build.results["corner"].detail, 1.25)
        self.assertEqual(build.results["edge"].detail, 1.25)
        self.assertEqual(build.results["button"].detail, 0.5)
        recipe = self.build()
        recipe.make_2x(fake_upscaler(noisy), None)
        self.assertNotEqual(build.results["edge"].image.tobytes(), recipe.results["edge"].image.tobytes())
        self.assertEqual(build.results["button"].image.tobytes(), recipe.results["button"].image.tobytes())

    def test_the_warnings_count_a_lifted_outline_and_texels_grown_into_a_cut_out(self):
        # A 1 px gray outline (85) under a transparent row, as on the thin-board corners.
        piece = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        for x in range(4):
            piece.putpixel((x, 2), (85, 85, 85, 255))
            piece.putpixel((x, 3), (8, 8, 8, 255))
        self.assertEqual(art.warnings_2x(piece, art.nearest2x(piece)), (0, 0))
        fringe = art.nearest2x(piece)
        for x in range(8):
            fringe.putpixel((x, 3), (180, 180, 180, 61))   # into the clear row
            fringe.putpixel((x, 4), (175, 175, 175, 203))  # the outline, lifted
        self.assertEqual(art.warnings_2x(piece, fringe), (16, 8))
        self.assertEqual(art.warning_text((16, 8)), "16 texel(s) over the 1x luma; 8 into clear texels")
        self.assertEqual(art.warning_text((0, 0)), "")

    def test_a_review_row_draws_a_small_piece_large_enough_to_see_its_texels(self):
        self.assertEqual(art.piece_zoom(Image.new("RGBA", (16, 16))), 2)
        self.assertEqual(art.piece_zoom(Image.new("RGBA", (15, 15))), 2)
        self.assertEqual(art.piece_zoom(Image.new("RGBA", (10, 4))), 3)
        self.assertEqual(art.piece_zoom(Image.new("RGBA", (64, 64))), 1)
        for pid, image in art.Build(art.load_manifest()).pieces_1x.items():
            self.assertGreaterEqual(4 * art.piece_zoom(image) * max(image.size), 120, pid)

    def test_review_sheets_show_the_pieces_on_pink_too(self):
        # The layout sheets need the committed pieces; no network (--no-ai).
        build = art.Build(art.load_manifest())
        build.make_2x(fake_upscaler(), None, no_ai=True)
        paths = art.review_sheets(build, os.path.join(self.fixture.root, "review"))
        names = [os.path.basename(p) for p in paths]
        self.assertIn("family-thin.png", names)
        self.assertEqual(names[-2:], ["layout-window.png", "layout-login.png"])
        with Image.open(paths[names.index("family-thin.png")]) as sheet:
            colors = [color for _, color in sheet.convert("RGB").getcolors(1 << 22)]
        self.assertIn(art.BRIGHT[:3], colors)

    def test_a_replay_serves_an_earlier_run_and_keeps_that_runs_upscaler_fields(self):
        work = os.path.join(self.fixture.root, "work")
        os.makedirs(os.path.join(work, "out"))
        Image.new("RGB", (4, 2), (9, 8, 7)).save(os.path.join(work, "out", "context-edge.png"))
        previous = {"exe": "E:\\up.exe", "exe_sha256": "ab", "model": "m", "ran": True, "seconds": 1.5, "error": ""}
        outputs, info = art.replay(work, previous)({"context-edge": None}, None)
        self.assertEqual(outputs["context-edge"].getpixel((0, 0)), (9, 8, 7))
        self.assertEqual(info, dict(previous, replayed_from=work))
        outputs, info = art.replay(work, previous)({"piece-button": None}, None)
        self.assertIsNone(outputs)
        self.assertIn("no output for piece-button", info["error"])

    def test_recombination_takes_alpha_and_chroma_from_lanczos(self):
        # Mild chroma, so the luma swap does not clip in RGB.
        piece = Image.new("RGBA", (12, 12))
        piece.putdata([(110 + 2 * x, 120, 110 + 2 * y, 255 if (x + y) % 5 else 128) for y in range(12) for x in range(12)])
        lanczos = art.lanczos2x(piece)
        network = Image.new("RGB", lanczos.size, (128, 128, 128))
        out = art.recombine(network, lanczos, 0.0)
        self.assertEqual(out.getchannel("A").tobytes(), lanczos.getchannel("A").tobytes())
        _, cb, cr = out.convert("RGB").convert("YCbCr").split()
        _, cb_l, cr_l = lanczos.convert("RGB").convert("YCbCr").split()
        self.assertLessEqual(max(abs(a - b) for a, b in zip(cb.getdata(), cb_l.getdata())), 2)
        self.assertLessEqual(max(abs(a - b) for a, b in zip(cr.getdata(), cr_l.getdata())), 2)

    def test_transparent_texels_are_filled_from_their_neighbors_for_the_network(self):
        image = Image.new("RGBA", (5, 1), (0, 0, 0, 0))
        image.putpixel((0, 0), (100, 0, 0, 255))
        image.putpixel((4, 0), (0, 0, 200, 10))
        self.assertEqual(list(art.filled_rgb(image).getdata()),
                         [(100, 0, 0), (100, 0, 0), (50, 0, 100), (0, 0, 200), (0, 0, 200)])
        self.assertEqual(art.filled_rgb(Image.new("RGBA", (3, 3))).getpixel((1, 1)), (0, 0, 0))


class ColorKey(unittest.TestCase):
    def test_opaque_magenta_becomes_fe00ff_and_is_counted(self):
        sheet = Image.new("RGBA", (4, 1), (255, 0, 255, 255))
        sheet.putpixel((1, 0), (255, 0, 255, 128))
        sheet.putpixel((2, 0), (1, 2, 3, 255))
        self.assertEqual(art.fix_color_key(sheet), 2)
        self.assertEqual(list(sheet.getdata()), [(254, 0, 255, 255), (255, 0, 255, 128), (1, 2, 3, 255), (254, 0, 255, 255)])
        self.assertEqual(art.fix_color_key(sheet), 0)


class CommandLine(unittest.TestCase):
    def test_usage_errors_exit_2(self):
        for argv in ([], ["paint"], ["rcss", "--threshold"], ["rcss", "--threshold", "big"], ["sheets"],
                     ["check", "--now"], ["legacy-ref"]):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(art.main(argv), 2, argv)

    def test_windows_paths_round_trip(self):
        self.assertEqual(art.windows_path("/mnt/e/nova-build/classic-art/work/x"), "E:\\nova-build\\classic-art\\work\\x")
        self.assertEqual(art.linux_path("E:\\nova-build\\tools\\realesrgan"), "/mnt/e/nova-build/tools/realesrgan")
        with self.assertRaises(art.ArtError):
            art.windows_path("/tmp/work")


class CommittedOutputs(unittest.TestCase):
    def test_check_passes_on_the_committed_sheets_rcss_and_record(self):
        self.assertEqual(art.check_problems(), [])

    def test_the_record_names_a_method_for_every_piece_and_a_reason_for_every_fallback(self):
        with open(art.RECORD, encoding="utf-8") as handle:
            record = json.load(handle)
        manifest = art.load_manifest()
        self.assertEqual([entry["id"] for entry in record["pieces"]], [p["id"] for p in manifest["pieces"]])
        for entry in record["pieces"]:
            self.assertIn(entry["method"], ("av3cd", "lanczos", "nearest", "generated"))
            if entry["method"] != "av3cd":
                self.assertTrue(entry["note"], entry["id"])
        self.assertEqual(record["sheet_1x"]["size"], [512, 256])
        self.assertEqual(record["sheet_2x"]["size"], [1024, 512])

    def test_a_record_out_of_step_with_the_sheet_is_reported(self):
        with open(art.RECORD, encoding="utf-8") as handle:
            record = json.load(handle)
        broken = copy.deepcopy(record)
        broken["sheet_2x"]["pixels_sha256"] = "0" * 64
        broken["pieces"][0]["source_sha256"] = "0" * 64
        problems = art.check_problems(record=broken)
        self.assertTrue(any("differ from the record" in p for p in problems), problems)
        self.assertTrue(any("changed since the record" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
