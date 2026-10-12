"""Tests the skin layout of assets/nui/nui (docs/ui/AUTHORING.md, Skins)
without nuitool: theme classes appear only in skin and theme sheets, every
selector of a skin sheet is scoped under its skin's class, every window
overlay belongs to a window and to a skin of themes.json, and no modern
window or component file names chrome art: every image they name is in
nui/content-art.json, and every entry there is named ("Code-drawn by
default"). With NUITOOL set, lint's NUI016 must report nothing either.

    cd tools && python3 -B -m unittest nui_skins_test
"""
import glob
import json
import os
import posixpath
import re
import shutil
import subprocess
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


# --- Code-drawn by default: content art versus chrome art ------------------------------

CONTENT_ART = os.path.join(NUI, "content-art.json")
CONTENT_KINDS = {"item-icon", "skill-icon", "action-icon", "affect-icon", "party-bonus-icon", "emblem", "flag",
                 "guild-mark", "map", "portrait", "quest-picture", "technical", "test-page"}
IMAGE_EXT = re.compile(r"\.(png|tga|jpg|jpeg|bmp|dds|sub)\b", re.I)
NUITOOL = os.environ.get("NUITOOL") or shutil.which("nuitool")


def modern_files():
    """The files the design rule covers: every window document and sheet, every
    component sheet, the template and the base sheet."""
    return sorted(glob.glob(os.path.join(NUI, "windows", "*", "*.rml")) + glob.glob(os.path.join(NUI, "windows", "*", "*.rcss"))
                  + glob.glob(os.path.join(NUI, "components", "*.rcss")) + [os.path.join(NUI, "nui.rtpl"), os.path.join(NUI, "base.rcss")])


def blank_comments(text, rcss):
    pattern = r"/\*.*?\*/" if rcss else r"<!--.*?-->"
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def image_references(text, rcss):
    """(line, kind, path) of every image a document or sheet names: <img src>,
    image() decorators, @spritesheet sources, fill-image, the skin-art
    properties (--frames-list, --frames-pattern, --number-path), nui-frames
    frames and pattern, nui-number path, and the string literals of a bound
    source that look like a path (a separator or an image extension; a bare
    '/', the store-root prefix of a bound store path, is not one)."""
    text = blank_comments(text, rcss)
    found = []

    def add(index, kind, path):
        found.append((text.count("\n", 0, index) + 1, kind, path.strip()))
    if rcss:
        for m in re.finditer(r"image\(\s*(?:\"([^\"]+)\"|([^\"\s)]+))", text):
            add(m.start(), "decorator", m.group(1) or m.group(2))
        for m in re.finditer(r"@spritesheet[^{]*\{[^}]*?src:\s*\"?([^\";]+)", text):
            add(m.start(), "spritesheet", m.group(1))
        for m in re.finditer(r"fill-image:\s*\"?([^\";]+)", text):
            add(m.start(), "fill-image", m.group(1))
        for m in re.finditer(r"(--frames-list|--frames-pattern|--number-path):\s*\"?([^\";]+)", text):
            for part in m.group(2).split(",") if m.group(1) == "--frames-list" else [m.group(2)]:
                add(m.start(), "property", part)
    else:
        for m in re.finditer(r"<img\b[^>]*?\ssrc=\"([^\"]+)\"", text, re.S):
            add(m.start(), "src", m.group(1))
        for m in re.finditer(r"\sframes=\"([^\"]+)\"", text):
            for part in m.group(1).split(","):
                add(m.start(), "frames", part)
        for m in re.finditer(r"\spattern=\"([^\"]+)\"", text):
            add(m.start(), "pattern", m.group(1))
        for m in re.finditer(r"<nui-number\b[^>]*?\spath=\"([^\"]+)\"", text, re.S):
            add(m.start(), "number-path", m.group(1))
        for m in re.finditer(r"\sdata-attr-(?:src|frames|pattern|path)=\"([^\"]+)\"", text):
            for literal in re.findall(r"'([^']*)'", m.group(1)):
                if literal != "/" and ("/" in literal or IMAGE_EXT.search(literal)):
                    add(m.start(), "bound", literal)
    return found


def store_path(path, owner):
    """The store path a reference names from `owner` (a file under NUI): d:/ and
    / paths as written, a relative one against the file's folder."""
    path = path.split("#", 1)[0]
    if re.match(r"^[a-zA-Z]:/", path) or path.startswith("/"):
        return path.lower()
    folder = "/nui/" + os.path.relpath(os.path.dirname(owner), NUI).replace(os.sep, "/")
    return posixpath.normpath(posixpath.join(folder, path)).lower()


def entry_pattern(path):
    """A content-art entry as a regular expression: * is anything but a '/',
    %d and %0Nd are digits."""
    parts = re.split(r"(\*|%0?\d*d)", path.lower())
    return re.compile("^" + "".join("[^/]*" if p == "*" else "[0-9]+" if p.startswith("%") else re.escape(p) for p in parts) + "$")


def content_art():
    with open(CONTENT_ART, encoding="utf-8") as handle:
        return json.load(handle)


class ChromeArt(unittest.TestCase):
    def test_the_scanner_finds_each_kind_of_reference(self):
        rml = ('<!-- <img src="x.sub"/> -->\n<img class="a" src="d:/ymir work/a.sub"/>\n'
               '<nui-frames frames="b.sub, c.sub"/><nui-frames pattern="d/%02d.sub" count="2"/>\n'
               '<img data-attr-src="\'/\' + icon"/><img data-attr-src="\'d:/ymir work/\' + art + \'.sub\'"/>\n'
               '<nui-number path="d:/ymir work/digits/"/>')
        self.assertEqual(image_references(rml, False), [
            (2, "src", "d:/ymir work/a.sub"), (3, "frames", "b.sub"), (3, "frames", "c.sub"), (3, "pattern", "d/%02d.sub"),
            (5, "number-path", "d:/ymir work/digits/"), (4, "bound", "d:/ymir work/"), (4, "bound", ".sub")])
        rcss = ('/* image("no.tga") */\n.a { decorator: image("d:/ymir work/a.sub" scale-none left top); }\n'
                '@spritesheet s { src: d:/ymir work/s.tga; s: 0px 0px 1px 1px; }\n.b { fill-image: "f.sub"; }\n'
                '.c { --frames-list: "x.sub, y.sub"; --number-path: "d:/n/"; }')
        self.assertEqual(image_references(rcss, True), [
            (2, "decorator", "d:/ymir work/a.sub"), (3, "spritesheet", "d:/ymir work/s.tga"), (4, "fill-image", "f.sub"),
            (5, "property", "x.sub"), (5, "property", "y.sub"), (5, "property", "d:/n/")])

    def test_the_content_list_has_its_exact_form(self):
        data = content_art()
        self.assertEqual(set(data), {"$comment", "content"})
        paths = [entry["path"] for entry in data["content"]]
        self.assertEqual(len(paths), len(set(paths)), "an entry is listed once")
        for entry in data["content"]:
            self.assertEqual(set(entry), {"path", "kind", "why"}, entry)
            self.assertIn(entry["kind"], CONTENT_KINDS, entry)
            self.assertTrue(entry["why"].strip(), entry)
            self.assertRegex(entry["path"], r"^([a-z]:/|/)", "%s: a store path" % entry["path"])

    def test_no_modern_window_or_component_file_names_chrome_art(self):
        patterns = [entry_pattern(entry["path"]) for entry in content_art()["content"]]
        chrome = []
        for path in modern_files():
            for line, kind, reference in image_references(read(path), path.endswith(".rcss")):
                if not any(p.match(store_path(reference, path)) for p in patterns):
                    chrome.append("%s:%d: %s %s" % (os.path.relpath(path, REPO), line, kind, reference))
        self.assertEqual(chrome, [], "chrome art in a modern file: give the modern look in code and put the art in "
                                     "nui/skins/<skin>/ (docs/ui/AUTHORING.md \"Code-drawn by default\")")

    def test_every_content_art_entry_is_named_by_a_modern_file(self):
        named = [store_path(reference, path) for path in modern_files()
                 for _, _, reference in image_references(read(path), path.endswith(".rcss"))]
        for entry in content_art()["content"]:
            pattern = entry_pattern(entry["path"])
            self.assertTrue(any(pattern.match(path) for path in named), "%s is named by no modern file" % entry["path"])

    @unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
    def test_lint_reports_no_chrome_art(self):
        roots = []
        for root in ("assets/nui", "assets/icon", "assets/ETC", "assets/locale", "assets/uiloading", "assets/season1",
                     "assets/metin2_patch_eu4", "assets/metin2_patch_etc", "assets/metin2_patch_ds"):
            roots += ["--root", root]
        result = subprocess.run([NUITOOL, "lint", "--no-load"] + roots + ["--locale", "assets/locale/locale/en"],
                                cwd=REPO, capture_output=True, text=True)
        self.assertEqual([line for line in result.stdout.splitlines() if "NUI016" in line], [])


if __name__ == "__main__":
    unittest.main()
