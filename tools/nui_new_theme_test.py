"""Tests tools/nui_new_theme.py in scratch copies of the content, and the
golden policy it writes for tools/check_nui_snapshots.py. The lint case
needs NUITOOL (or nuitool on PATH) and skips without it.

    cd tools && python3 -B -m unittest nui_new_theme_test
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

import check_nui_snapshots
import nui_new_theme
import nui_tokens

REPO = nui_new_theme.REPO
NUITOOL = os.environ.get("NUITOOL") or shutil.which("nuitool")

# The scaffold runs in a copy of the live content, so the tests use ids that
# no real theme takes (the guide's examples, ember and stone, may become real
# themes). Scratch.setUp stops with a clear message if one is taken anyway.
PALETTE = "test-palette"     # a palette theme on the modern skin
SKIN = "test-skin"           # a component skin, its theme and its palette
NIGHT = "test-night"         # a palette theme on an existing skin
TEST_IDS = (PALETTE, SKIN, NIGHT)


def golden_name(theme_id):
    return theme_id.replace("-", "")


def tree_digest(folder):
    """{relative path: sha256} of every file under folder."""
    out = {}
    for current, _dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(current, name)
            with open(path, "rb") as handle:
                out[os.path.relpath(path, folder)] = hashlib.sha256(handle.read()).hexdigest()
    return out


class Scratch(unittest.TestCase):
    """A scratch repository: the nui content, the guide and the golden config."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="nui-new-theme-")
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(os.path.join(REPO, nui_new_theme.NUI), os.path.join(self.root, nui_new_theme.NUI))
        for rel in (nui_new_theme.AUTHORING_MD, nui_new_theme.GOLDEN_THEMES):
            os.makedirs(os.path.dirname(os.path.join(self.root, rel)), exist_ok=True)
            shutil.copy(os.path.join(REPO, rel), os.path.join(self.root, rel))
        self.nui = os.path.join(self.root, nui_new_theme.NUI)
        self.before = tree_digest(self.nui)
        self.assert_the_test_ids_are_free()

    def assert_the_test_ids_are_free(self):
        themes = [theme["id"] for theme in self.read_json(nui_new_theme.THEMES_JSON)["themes"]]
        palettes = nui_tokens.palettes_of(self.read_json(nui_new_theme.TOKENS_JSON))
        names = [entry["name"] for entry in self.read_json(nui_new_theme.GOLDEN_THEMES)["themes"]]
        skins = os.listdir(os.path.join(self.nui, "skins"))
        for theme_id in TEST_IDS:
            taken = [what for what, used in (("theme", themes), ("palette", palettes), ("skin", skins),
                                             ("golden name", names)) if theme_id in used or golden_name(theme_id) in used]
            self.assertEqual(taken, [], "the content now has a %s %r; give the scaffold tests other ids (TEST_IDS)"
                             % (" and ".join(taken), theme_id))

    def run_tool(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = nui_new_theme.main(list(args) + ["--root", self.root])
        return code, out.getvalue(), err.getvalue()

    def read_json(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as handle:
            return json.load(handle)

    def changed(self):
        after = tree_digest(self.nui)
        return sorted(set(path for path in set(after) | set(self.before) if after.get(path) != self.before.get(path)))

    def golden_names(self):
        return [case[0] for case in check_nui_snapshots.cases(self.root) if case[-1] is None]

    def assert_no_window_or_component_changed(self):
        for path in self.changed():
            self.assertFalse(path.startswith(("windows" + os.sep, "components" + os.sep)), path)


class PaletteOnly(Scratch):
    def test_a_palette_theme_copies_its_base_and_registers_itself(self):
        code, out, err = self.run_tool(PALETTE, "--base", "dark")
        self.assertEqual(code, 0, err)
        tokens = self.read_json(nui_new_theme.TOKENS_JSON)
        self.assertEqual(tokens[PALETTE], tokens["dark"])
        self.assertEqual(list(tokens)[-2:], [PALETTE, "skins"])
        themes = self.read_json(nui_new_theme.THEMES_JSON)["themes"]
        self.assertEqual(themes[-1], {"id": PALETTE, "label": "Test palette", "body": ["skin-modern", "theme-" + PALETTE]})
        self.assertEqual(themes[0]["id"], "modern-dark")
        self.assertIn("python3 tools/check_nui_snapshots.py --write --optimize --only=-testpalette-", out)

    def test_the_printed_golden_command_selects_exactly_the_new_goldens(self):
        before = set(self.golden_names())
        code, out, err = self.run_tool(PALETTE, "--base", "dark")
        self.assertEqual(code, 0, err)
        line = next(line for line in out.splitlines() if "tools/check_nui_snapshots.py" in line)
        argv = shlex.split(line.split("tools/check_nui_snapshots.py", 1)[1].split("   (", 1)[0])
        with contextlib.redirect_stderr(io.StringIO()):
            args = check_nui_snapshots.make_parser().parse_args(argv)  # argparse exits on a value read as an option
        self.assertTrue(args.write and args.optimize)
        selected = {case[0] for case in check_nui_snapshots.cases(self.root) if args.only in case[0]}
        self.assertEqual(selected, set(self.golden_names()) - before)
        self.assertEqual(len(selected), 12)

    def test_the_generated_outputs_are_current_for_nui_tokens(self):
        self.assertEqual(self.run_tool(PALETTE, "--base", "light")[0], 0)
        theme = os.path.join(self.nui, "theme")
        tokens, themes = nui_tokens.load(os.path.join(theme, "tokens.json"), os.path.join(theme, "themes.json"))
        with open(os.path.join(theme, "tokens.rcss"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), nui_tokens.render_rcss(tokens, themes))
        with open(os.path.join(self.root, nui_new_theme.AUTHORING_MD), encoding="utf-8") as handle:
            guide = handle.read()
        self.assertEqual(nui_tokens.splice_table(guide, nui_tokens.render_table(tokens, themes)), guide)
        self.assertIn("| %s |" % PALETTE.capitalize(), guide)

    def test_a_palette_theme_touches_only_the_theme_files(self):
        self.assertEqual(self.run_tool(PALETTE, "--base", "dark")[0], 0)
        self.assertEqual(self.changed(), sorted(os.path.join("theme", name) for name in ("themes.json", "tokens.json", "tokens.rcss")))

    def test_an_existing_skin_takes_a_new_palette_without_a_new_folder(self):
        self.assertEqual(self.run_tool(NIGHT, "--base", "classic", "--skin", "classic", "--name", golden_name(NIGHT))[0], 0)
        themes = self.read_json(nui_new_theme.THEMES_JSON)["themes"]
        self.assertEqual(themes[-1]["body"], ["skin-classic", "theme-" + NIGHT])
        self.assertEqual(self.changed(), sorted(os.path.join("theme", name) for name in ("themes.json", "tokens.json", "tokens.rcss")))

    def test_a_dry_run_writes_nothing(self):
        code, out, _err = self.run_tool(PALETTE, "--base", "dark", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would write assets/nui/nui/theme/themes.json", out)
        self.assertEqual(self.changed(), [])


class ComponentSkin(Scratch):
    def test_a_new_skin_gets_its_folder_and_its_link(self):
        with open(os.path.join(self.nui, "nui.rtpl"), encoding="utf-8") as handle:
            skin_links = re.findall(r'href="(skins/[^"]+)"', handle.read())
        self.assertTrue(skin_links)
        code, _out, err = self.run_tool(SKIN, "--base", "classic", "--skin", SKIN)
        self.assertEqual(code, 0, err)
        folder = os.path.join(self.nui, "skins", SKIN)
        self.assertEqual(sorted(os.listdir(folder)), ["README.md", SKIN + ".rcss"])
        with open(os.path.join(folder, SKIN + ".rcss"), encoding="utf-8") as handle:
            sheet = handle.read()
        self.assertIn("\n.skin-%s\n{\n}\n" % SKIN, sheet, "RmlUi refuses a sheet without a rule")
        with open(os.path.join(self.nui, "nui.rtpl"), encoding="utf-8") as handle:
            template = handle.read()
        link = 'href="skins/%s/%s.rcss"' % (SKIN, SKIN)
        self.assertLess(max(template.index('href="%s"' % href) for href in skin_links), template.index(link), "after every skin sheet")
        self.assertLess(template.index(link), template.index("</head>"))
        self.assert_no_window_or_component_changed()

    def test_layout_overrides_get_one_overlay_stub_per_window(self):
        code, _out, err = self.run_tool(SKIN, "--base", "classic", "--skin", SKIN, "--window", "login", "--window", "select")
        self.assertEqual(code, 0, err)
        overlays = os.path.join(self.nui, "skins", SKIN, "windows")
        self.assertEqual(sorted(os.listdir(overlays)), ["login.rcss", "select.rcss"])
        with open(os.path.join(overlays, "login.rcss"), encoding="utf-8") as handle:
            self.assertIn("nui/windows/login/login.rml", handle.read())
        self.assert_no_window_or_component_changed()

    def test_the_modern_skin_takes_no_overlay(self):
        code, _out, err = self.run_tool(PALETTE, "--base", "dark", "--window", "login")
        self.assertEqual(code, 1)
        self.assertIn("layout overrides need another skin", err)
        self.assertEqual(self.changed(), [])


class GoldenPolicy(Scratch):
    def setUp(self):
        super().setUp()
        self.base = self.golden_names()

    def test_the_shipped_config_lists_exactly_the_shipped_themes(self):
        golden = self.read_json(nui_new_theme.GOLDEN_THEMES)["themes"]
        shipped = self.read_json(nui_new_theme.THEMES_JSON)["themes"]
        self.assertEqual([entry["id"] for entry in golden], [theme["id"] for theme in shipped])

    def test_every_golden_case_has_its_image_and_every_image_is_a_case(self):
        # Whatever themes the content has: a theme's goldens come with it, and
        # go with it when it is removed.
        images = {name[:-len(".png")] for name in os.listdir(os.path.join(REPO, check_nui_snapshots.SNAPSHOTS)) if name.endswith(".png")}
        goldens = {case[1] for case in check_nui_snapshots.cases(REPO) if case[-1] is None}
        self.assertEqual(sorted(goldens - images), [], "write them: check_nui_snapshots.py --write --optimize --only ...")
        self.assertEqual(sorted(images - goldens), [], "no case draws these; delete them")

    def test_an_experimental_theme_gets_the_gallery_and_the_representative_pages(self):
        self.assertEqual(self.run_tool(PALETTE, "--base", "dark")[0], 0)
        entry = self.read_json(nui_new_theme.GOLDEN_THEMES)["themes"][-1]
        self.assertEqual(entry, {"name": golden_name(PALETTE), "id": PALETTE, "experimental": True,
                                 "pages": ["login", "select", "dialog-question"]})
        added = sorted(set(self.golden_names()) - set(self.base))
        expected = sorted("%s-%s-%s" % (page, golden_name(PALETTE), percent)
                          for page in ("gallery", "login", "select", "dialog-question") for percent in ("100", "150", "200"))
        self.assertEqual(added, expected)

    def test_named_pages_replace_the_representative_ones(self):
        self.assertEqual(self.run_tool(PALETTE, "--base", "dark", "--pages", "empire")[0], 0)
        added = set(self.golden_names()) - set(self.base)
        self.assertEqual(sorted(name.rsplit("-", 2)[0] for name in added), ["empire"] * 3 + ["gallery"] * 3)

    def test_a_shipped_theme_gets_the_full_matrix(self):
        self.assertEqual(self.run_tool(PALETTE, "--base", "dark", "--shipped")[0], 0)
        self.assertEqual(self.read_json(nui_new_theme.GOLDEN_THEMES)["themes"][-1], {"name": golden_name(PALETTE), "id": PALETTE})
        added = set(self.golden_names()) - set(self.base)
        # The classic-only cases (their themes list classic alone) are not in the matrix.
        classic = {name.replace("-classic-", "-%s-" % golden_name(PALETTE)) for name in self.base if "-classic-" in name
                   and not name.startswith(("skin-proof-", "select-busy-", "create-busy-", "taskbar-wide-",
                                            "energy-bar-hungry-", "energy-bar-empty-"))}
        self.assertEqual(added, classic)

    def test_a_theme_without_a_golden_entry_stops_the_checker(self):
        path = os.path.join(self.root, nui_new_theme.GOLDEN_THEMES)
        with open(path, encoding="utf-8") as handle:
            config = json.load(handle)
        removed = config["themes"].pop()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        with self.assertRaisesRegex(ValueError, "no entry for theme %s" % re.escape(removed["id"])):
            list(check_nui_snapshots.cases(self.root))


class Refusals(Scratch):
    def assert_refused(self, message, *args):
        code, _out, err = self.run_tool(*args)
        self.assertEqual(code, 1)
        self.assertIn(message, err)
        self.assertEqual(self.changed(), [])

    def test_an_id_the_table_already_holds(self):
        taken = self.read_json(nui_new_theme.THEMES_JSON)["themes"][-1]["id"]
        self.assert_refused("already has a theme %r" % taken, taken, "--base", "dark", "--palette", PALETTE, "--name", golden_name(PALETTE))

    def test_a_base_palette_that_does_not_exist(self):
        self.assert_refused("no palette 'no-such-palette'", PALETTE, "--base", "no-such-palette")

    def test_a_palette_name_already_taken(self):
        self.assert_refused("already has a section 'light'", PALETTE, "--base", "dark", "--palette", "light")

    def test_an_id_out_of_form(self):
        self.assert_refused("the id is 1 to 31", "Test-Palette", "--base", "dark")

    def test_a_golden_name_already_taken(self):
        taken = self.read_json(nui_new_theme.GOLDEN_THEMES)["themes"][0]["name"]
        self.assert_refused("already uses the name %r" % taken, PALETTE, "--base", "dark", "--name", taken)

    def test_a_page_without_golden_cases(self):
        self.assert_refused("no golden case for page 'nowhere'", PALETTE, "--base", "dark", "--pages", "nowhere")

    def test_an_unknown_window(self):
        self.assert_refused("no window 'nowhere'", SKIN, "--base", "dark", "--skin", SKIN, "--window", "nowhere")


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class ScaffoldWithNuitool(Scratch):
    def test_a_scaffolded_skin_with_an_overlay_lints_clean(self):
        code, _out, err = self.run_tool(SKIN, "--base", "classic", "--skin", SKIN, "--window", "login")
        self.assertEqual(code, 0, err)
        groups = []
        for group in ("icon", "ETC", "locale", "uiloading", "season1", "metin2_patch_eu4", "metin2_patch_etc", "metin2_patch_ds"):
            groups += ["--root", os.path.join(REPO, "assets", group)]
        result = subprocess.run([NUITOOL, "lint", "--root", os.path.join(self.root, "assets", "nui")] + groups +
                                ["--scripts", os.path.join(REPO, "assets", "root"),
                                 "--locale", os.path.join(REPO, "assets", "locale", "locale", "en")],
                                capture_output=True, text=True)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
