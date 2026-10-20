"""Tests the fallback guarantee with the test-only bare theme
(tools/fixtures/skin-bare/theme.json, built by nui_skin_bare.py): a skin
with no rules at all lints clean and snaps every window without RmlUi
problems. The nuitool cases need NUITOOL (or nuitool on PATH) and skip
without it.

    cd tools && NUITOOL=<path> python3 -B -m unittest nui_skin_bare_test
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import nui_skin_bare
import nui_tokens

REPO = nui_skin_bare.REPO
SHIPPED = os.path.join(REPO, "assets", "nui", "nui")
NUITOOL = os.environ.get("NUITOOL") or shutil.which("nuitool")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class BareFixture(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="nui-skin-bare-")
        self.addCleanup(shutil.rmtree, self.work, True)

    def test_the_bare_theme_is_never_shipped(self):
        spec = nui_skin_bare.fixture()
        shipped = load(os.path.join(SHIPPED, "theme", "themes.json"))["themes"]
        self.assertNotIn(spec["theme"]["id"], [theme["id"] for theme in shipped])
        for theme in shipped:
            for name in spec["theme"]["body"]:
                self.assertNotIn(name, theme["body"])
        self.assertNotIn(spec["palette"]["name"], load(os.path.join(SHIPPED, "theme", "tokens.json")))
        self.assertFalse(os.path.exists(os.path.join(SHIPPED, "skins", "bare")))
        golden = load(os.path.join(REPO, "docs", "ui", "snapshots", "golden-themes.json"))["themes"]
        self.assertNotIn(spec["theme"]["id"], [entry["id"] for entry in golden])

    def test_the_bare_skin_has_no_rules_of_its_own(self):
        skin = [name for name in nui_skin_bare.fixture()["theme"]["body"] if name.startswith("skin-")]
        self.assertEqual(skin, ["skin-bare"])
        for folder, _dirs, files in os.walk(SHIPPED):
            for name in files:
                if name.endswith((".rcss", ".rml", ".rtpl")):
                    with open(os.path.join(folder, name), encoding="utf-8") as handle:
                        self.assertNotIn("skin-bare", handle.read(), os.path.join(folder, name))

    def test_the_scratch_root_holds_a_valid_table_and_a_palette_that_passes_contrast(self):
        theme_id = nui_skin_bare.make_root(self.work)
        theme = os.path.join(self.work, "nui", "theme")
        tokens, themes = nui_tokens.load(os.path.join(theme, "tokens.json"), os.path.join(theme, "themes.json"))
        self.assertEqual(themes[-1][0], theme_id)
        self.assertEqual(themes[0][0], nui_tokens.DEFAULT_THEME_ID)
        failures = [row for row in nui_tokens.contrast_report(tokens, themes) if row[0] == "bare" and row[3] < row[4]]
        self.assertEqual(failures, [])
        with open(os.path.join(theme, "tokens.rcss"), encoding="utf-8") as handle:
            self.assertIn("body.theme-bare\n{", handle.read())

    def test_the_scratch_root_leaves_the_shipped_content_alone(self):
        before = load(os.path.join(SHIPPED, "theme", "themes.json"))
        nui_skin_bare.make_root(self.work)
        self.assertEqual(load(os.path.join(SHIPPED, "theme", "themes.json")), before)


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class BareSkinWithNuitool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp(prefix="nui-skin-bare-")
        cls.theme_id = nui_skin_bare.make_root(cls.work)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    def test_every_window_lints_clean_in_every_theme_with_the_bare_one(self):
        result = subprocess.run(nui_skin_bare.lint_command(NUITOOL, self.work), capture_output=True, text=True)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_golden_page_snaps_without_rmlui_problems_in_the_bare_theme(self):
        cases = nui_skin_bare.snap_cases()
        pages = [case[0] for case in cases]
        for page in nui_skin_bare.LOOK_PAGES:
            self.assertIn(page, pages)
        for case in cases:
            with self.subTest(page=case[0]):
                out = os.path.join(self.work, "%s-bare.png" % case[0])
                result = subprocess.run(nui_skin_bare.snap_command(NUITOOL, self.work, case, self.theme_id, out),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual([line for line in result.stderr.splitlines() if line.startswith("rmlui:")], [])
                self.assertTrue(os.path.getsize(out) > 0)


if __name__ == "__main__":
    unittest.main()
