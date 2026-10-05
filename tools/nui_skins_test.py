"""Tests the skin layout of assets/nui/nui (docs/ui/AUTHORING.md, Skins)
without nuitool: theme classes appear only in skin and theme sheets, every
selector of a skin sheet is scoped under its skin's class, and every window
overlay belongs to a window and to a skin of themes.json.

    cd tools && python3 -B -m unittest nui_skins_test
"""
import glob
import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUI = os.path.join(REPO, "assets", "nui", "nui")
THEME_CLASS = re.compile(r"\.(skin|theme)-[a-z0-9-]*")


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def selectors(text):
    """(line, selector) of every style rule in an RCSS text, inside @media
    blocks too; the bodies of @decorator, @spritesheet and @keyframes are
    not rules."""
    text = strip_comments(text)
    out, depth, start, skip_depth = [], 0, 0, None
    for index, char in enumerate(text):
        if char == "{":
            raw = text[start:index]
            prelude = raw.strip()
            if skip_depth is None and prelude.startswith("@") and not prelude.startswith("@media"):
                skip_depth = depth
            elif skip_depth is None and not prelude.startswith("@"):
                line = text.count("\n", 0, start + len(raw) - len(raw.lstrip())) + 1
                out += [(line, part.strip()) for part in prelude.split(",") if part.strip()]
            depth += 1
            start = index + 1
        elif char == "}":
            depth -= 1
            if skip_depth is not None and depth == skip_depth:
                skip_depth = None
            start = index + 1
    return out


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def skins_of_themes():
    with open(os.path.join(NUI, "theme", "themes.json"), encoding="utf-8") as handle:
        themes = json.load(handle)["themes"]
    return {name[len("skin-"):] for theme in themes for name in theme["body"] if name.startswith("skin-")}


class Selectors(unittest.TestCase):
    def test_the_selector_reader_finds_rules_in_media_and_skips_at_rule_bodies(self):
        text = ("/* .skin-x in a comment */\n@decorator d : image { image: a; }\n.a, .b\n{ color: red; }\n"
                "@media (max-height: 10dp)\n{\n\t.skin-c .a\n\t{\n\t\tdisplay: block;\n\t}\n}\n"
                "@keyframes k { from { opacity: 0; } to { opacity: 1; } }\n")
        self.assertEqual(selectors(text), [(3, ".a"), (3, ".b"), (7, ".skin-c .a")])


class ThemeClasses(unittest.TestCase):
    def test_windows_and_components_name_no_skin_or_theme_class(self):
        sheets = glob.glob(os.path.join(NUI, "windows", "*", "*.rcss")) + glob.glob(os.path.join(NUI, "components", "*.rcss"))
        self.assertTrue(sheets)
        found = []
        for path in sheets:
            for line, selector in selectors(read(path)):
                if THEME_CLASS.search(selector):
                    found.append("%s:%d: %s" % (os.path.relpath(path, REPO), line, selector))
        self.assertEqual(found, [])

    def test_window_documents_put_no_skin_or_theme_class_in_markup(self):
        for path in glob.glob(os.path.join(NUI, "windows", "*", "*.rml")):
            for classes in re.findall(r'\bclass="([^"]*)"', read(path)):
                for name in classes.split():
                    self.assertFalse(name.startswith(("skin-", "theme-")), "%s: %s" % (os.path.relpath(path, REPO), name))


class SkinFolders(unittest.TestCase):
    def test_every_selector_of_a_skin_starts_with_its_class(self):
        for skin in os.listdir(os.path.join(NUI, "skins")):
            scope = re.compile(r"^(?:[a-z]+)?\.skin-%s(?![\w-])" % re.escape(skin))
            for path in glob.glob(os.path.join(NUI, "skins", skin, "**", "*.rcss"), recursive=True):
                for line, selector in selectors(read(path)):
                    self.assertRegex(selector, scope, "%s:%d" % (os.path.relpath(path, REPO), line))

    def test_every_overlay_belongs_to_a_window_and_a_skin_in_use(self):
        skins = skins_of_themes()
        overlays = glob.glob(os.path.join(NUI, "skins", "*", "windows", "*.rcss"))
        self.assertTrue(overlays)
        for path in overlays:
            skin = os.path.basename(os.path.dirname(os.path.dirname(path)))
            window = os.path.basename(path)[:-len(".rcss")]
            self.assertIn(skin, skins, path)
            self.assertTrue(os.path.isfile(os.path.join(NUI, "windows", window, window + ".rml")), path)

    def test_every_skin_sheet_has_a_rule_because_rmlui_refuses_an_empty_one(self):
        for path in glob.glob(os.path.join(NUI, "**", "*.rcss"), recursive=True):
            text = strip_comments(read(path))
            self.assertIn("{", text, os.path.relpath(path, REPO))

    def test_every_skin_folder_belongs_to_a_theme(self):
        self.assertEqual(sorted(os.listdir(os.path.join(NUI, "skins"))), sorted(skins_of_themes() - {"modern"}))


if __name__ == "__main__":
    unittest.main()
