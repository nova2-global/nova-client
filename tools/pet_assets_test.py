"""Tests for the advanced pet's client data and art (NOVA-24, chunk Y):
python3 -B -m unittest pet_assets_test (from tools/).

- the five uiscripts load and hold every child uipet.py asks for;
- every locale key uipet.py, uitooltip.py's pet lines and the uiscripts use
  is in all 17 locales, as a plain entry with English's specifiers;
- the three data files of contract 7 parse, have 21, 10 and 21 rows and
  agree with each other;
- every file the uiscripts, uipet.py, the skill table and the 45 items'
  item_list rows name ships (or is one OLD lacks too, MISSING_IN_OLD);
- each pet mob of contract 4.3 has its model where NEW's race loader looks.

asset_list() is the list chunk Y's report writes (Y-assets.txt)."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import old_content  # noqa: E402
import wave6_support as w6  # noqa: E402

ROOT = lf.ROOT
UISCRIPT = lf.UISCRIPT
LOCALE = lf.LOCALES
SCRIPTS = {"PetHatchEggWindow": "pethatcheggwindow.py", "PetEvolutionWindow": "petevolutionwindow.py",
           "PetInterfaceWindow": "petinterfacewindow.py", "PetWindow": "petwindow.py",
           "PetAttrRefineWindow": "petrefineattrwindow.py"}
SIZES = {"pethatcheggwindow.py": (176, 184), "petevolutionwindow.py": (260, 330), "petinterfacewindow.py": (245, 135),
         "petwindow.py": (406, 513), "petrefineattrwindow.py": (260, 330)}
# Named by OLD and missing in OLD's 0.2 packs too: 55700's portrait (OLD's
# window showed none for the fixed-bonus seal). OLD's .gif art ships as .png
# (NEW's resource manager has no GIF loader).
MISSING_IN_OLD = {"d:/ymir work/ui/pet/panel_info/icon_pets/55700.png"}
PET_VNUMS = list(range(55401, 55411)) + list(range(55700, 55711)) + [55006, 55007, 55008] + list(range(55010, 55031))
# contract 4.3: the pet mobs (normal and heroic) of 55700-55710.
PET_MOBS = (34041, 34042, 34045, 34046, 34049, 34050, 34053, 34054, 34036, 34037, 34065, 34066, 34073, 34074,
            34075, 34076, 34080, 34081, 34082, 34083)
NEW_GAME_KEYS = {"PET_EGG_HATCH_IN": "Hatches in: %s", "PET_TOOLTIP_TAB_PREVIEW": "Press Tab to preview this pet",
                 "PET_INFO_NAME": "Name:", "PET_INFO_EVOLUTION": "Evo:", "PET_INFO_LEVEL": "Level:",
                 "PET_HATCH_NEED_WAIT": "You need to wait %s.", "PET_EVOLVE_PRICE": "Price %s",
                 "TARGET_INFO_EXP": "Experience: %s"}


def read(path):
    return lf.read(path)


def uiscript(name):
    import types
    module = types.ModuleType("uiScriptLocale")
    module.__getattr__ = lambda key: "@" + key
    saved = sys.modules.get("uiScriptLocale")
    sys.modules["uiScriptLocale"] = module
    try:
        return lf.read_uiscript(os.path.join(UISCRIPT, name))["window"]
    finally:
        if saved is None:
            del sys.modules["uiScriptLocale"]
        else:
            sys.modules["uiScriptLocale"] = saved


def class_sources():
    source = read(os.path.join(ROOT, "uipet.py"))
    parts = re.split(r"\nclass (\w+)\(", source)
    return dict((parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2))


def child_names(source):
    """The names a loader asks for, with "%d" names spread over 1..13."""
    names = set()
    for name in re.findall(r'(?:GetChild|GetObject)\("([^"]+)"', source):
        if "%d" in name:
            names.update(name % i for i in range(1, 14) if not (name.startswith("bonus") and i > 3))
        else:
            names.add(name)
    return names


def locale_keys(*files):
    keys = set()
    for name in files:
        source = read(os.path.join(ROOT, name)) if name.endswith(".py") and os.sep not in name else read(name)
        keys.update(re.findall(r"localeInfo\.([A-Z][A-Z0-9_]+)", source))
    return keys


def ui_keys(*paths):
    keys = set()
    for path in paths:
        keys.update(re.findall(r"uiScriptLocale\.([A-Z][A-Z0-9_]+)", read(path)))
    return keys


def sub_image(path, data):
    """The texture a .sub names (CGraphicSubImage: version 2.0 beside the
    .sub, else under the image search path d:/ymir work/ui/)."""
    fields = dict(re.findall(r'^\s*(\w+)\s+"?([^"\r\n]*)"?', data, re.M))
    if fields.get("version") == "2.0":
        return path.rsplit("/", 1)[0] + "/" + fields["image"].lower()
    return "d:/ymir work/ui/" + fields["image"].lower()


def published(path):
    """The asset group file of a store path, or None."""
    groups = [line.split("#")[0].strip() for line in open(os.path.join(lf.REPO, "assets", "groups.txt"))]
    rel = path.lower()
    rel = rel[3:] if rel.startswith("d:/") else rel
    for group in reversed([g for g in groups if g]):
        folder = os.path.join(lf.REPO, "assets", group)
        candidate = os.path.join(folder, rel)
        if os.path.exists(candidate):
            return candidate
        # case-insensitive look (the store lowercases)
        parts, here = rel.split("/"), folder
        for part in parts:
            if not os.path.isdir(here):
                here = None
                break
            names = {name.lower(): name for name in os.listdir(here)}
            if part not in names:
                here = None
                break
            here = os.path.join(here, names[part])
        if here and os.path.isfile(here):
            return here
    return None


def asset_list():
    """[(store path, referrer)] of every file the pet UI and items name."""
    wanted = []
    for name in SCRIPTS.values():
        for path in re.findall(r'"(d:/ymir work/[^"]+)"', read(os.path.join(UISCRIPT, name)), re.I):
            wanted.append((path.lower(), "uiscript/" + name))
        for path in re.findall(r'BUTTON = "(d:/ymir work/[^"]+)"', read(os.path.join(UISCRIPT, name))):
            wanted += [((path % i).lower(), "uiscript/" + name) for i in (1, 2, 3)]
    wanted = [(path, referrer) for path, referrer in wanted if "%d" not in path]
    wanted.append(("d:/ymir work/ui/pet/bg-preview.png", "uipet.py"))
    for vnum in range(55700, 55711):
        wanted.append(("d:/ymir work/ui/pet/panel_info/icon_pets/%d.png" % vnum, "uipet.py"))
    for row in rows("common", "pet_skilltable.txt"):
        # OLD's animated GIFs as PNGs of their first frame (NEW loads no GIF).
        wanted.append(("d:/ymir work/ui/pet/skill/%s/%s.png" % ("heroic" if row[2] == "1" else "normal", row[0].lower()),
                       "pet_skilltable.txt"))
    for vnum, line in item_lines().items():
        for path in line.split("\t")[2:]:
            wanted.append((path.lower(), "item_list %d" % vnum))
    for path, referrer in list(wanted):
        if path.endswith(".sub") and published(path):
            wanted.append((sub_image(path, read(published(path))), path))
    seen, out = set(), []
    for path, referrer in wanted:
        if path not in seen:
            seen.add(path)
            out.append((path, referrer))
    return out


def rows(locale, name):
    with open(os.path.join(LOCALE, locale, name), encoding="utf-8") as handle:
        data = handle.read()
    return [line.split("\t") for line in data.split("\n") if line.strip()], data


def item_lines():
    lines = {}
    for line in read(old_content.ITEM_LIST).split("\n"):
        cells = line.split("\t")
        if cells[0].isdigit() and int(cells[0]) in PET_VNUMS:
            lines[int(cells[0])] = line
    return lines


_rows = rows


def rows(locale, name):  # noqa: F811
    return _rows(locale, name)[0]


class UIScripts(unittest.TestCase):
    def test_each_loads_at_olds_size_with_every_child_the_window_asks_for(self):
        sources = class_sources()
        for cls, name in SCRIPTS.items():
            with self.subTest(script=name):
                window = uiscript(name)
                self.assertEqual((window["width"], window["height"]), SIZES[name])
                have = {child.get("name") for child in lf.children(window)}
                self.assertEqual(child_names(sources[cls]) - have, set())

    def test_no_type_new_lacks(self):
        for name in SCRIPTS.values():
            for kind in re.findall(r'"type"\s*:\s*"([^"]+)"', read(os.path.join(UISCRIPT, name))):
                self.assertNotIn(kind, ("board_new", "newtitlebar", "target_board_new"), name)


class Locales(unittest.TestCase):
    def test_every_key_the_pet_code_uses_is_in_every_locale(self):
        game = (locale_keys("uipet.py") - {"AFFECT_DICT"}) | {"PET_EGG_HATCH_IN", "PET_TOOLTIP_TAB_PREVIEW", "PET_TOOLTIP_SKILL_CUR_LEVEL",
                                          "PET_ADVANCED_ORB_WARNING", "PET_ADVANCED_ORB_ALREADY_USED",
                                          "PET_ADVANCED_ORB_ALERT", "PET_ATTR_REFINE_SUCCESS", "PET_ATTR_REFINE_FAILURE"}
        game |= {"PET_EVOLVE_GRADE_" + row[1].strip().upper() for row in rows("common", "pet_evolvetable.txt")}
        interface = ui_keys(os.path.join(ROOT, "uipet.py"), *[os.path.join(UISCRIPT, n) for n in SCRIPTS.values()])
        english_game, english_ui = lf.read_locale("en"), lf.read_locale("en", "locale_interface.txt")
        for locale in lf.locales():
            entries = lf.read_locale(locale)
            ui_entries = lf.read_locale(locale, "locale_interface.txt")
            for key in sorted(game):
                with self.subTest(locale=locale, key=key):
                    self.assertIn(key, entries)
                    self.assertEqual(w6.specifiers(entries[key][0]), w6.specifiers(english_game[key][0]))
            for key in sorted(interface):
                with self.subTest(locale=locale, key=key):
                    self.assertIn(key, ui_entries)
        for key, text in NEW_GAME_KEYS.items():
            self.assertEqual(english_game[key][0], text, key)
        self.assertEqual(english_ui["PET_UI_REQUIREMENTS"][0], "Requirements")

    def test_olds_translations_are_kept(self):
        de = lf.read_locale("de")
        self.assertEqual(de["PET_EVOLVE_GRADE_MYTHIC"][0], "Mythisch")
        self.assertEqual(de["PET_HATCH_NEED_WAIT"][0], "Du musst noch warten %s")
        self.assertEqual(lf.read_locale("br")["PET_EVOLVE_PRICE"][0], lf.read_locale("pt")["PET_EVOLVE_PRICE"][0])


class DataFiles(unittest.TestCase):
    def test_the_three_tables(self):
        skills, evolve, descs = rows("common", "pet_skilltable.txt"), rows("common", "pet_evolvetable.txt"), \
            rows("en", "pet_skilldesc.txt")
        self.assertEqual((len(skills), len(evolve), len(descs)), (21, 10, 21))
        for name in ("pet_skilltable.txt", "pet_evolvetable.txt"):
            data = _rows("common", name)[1]
            self.assertTrue(data.endswith("\n") and "\r" not in data, name)
        self.assertEqual(sorted(row[0] for row in skills), sorted(row[0] for row in descs), "a description per skill")
        self.assertEqual(sum(1 for row in skills if row[2] == "1"), 6, "six heroic skills")
        levels = [int(row[0]) for row in evolve]
        self.assertEqual(levels, [1, 15, 30, 45, 60, 75, 90, 95, 100, 105])
        self.assertEqual([row[1] for row in evolve][6], "Mythic", "OLD's trailing space trimmed")
        self.assertEqual([int(row[4]) for row in evolve], [0, 1, 2, 3, 4, 5, 6, 8, 9, 10])
        self.assertEqual([int(row[5]) for row in evolve], [0, 0, 0, 0, 0, 0, 0, 1, 2, 3])
        for row in evolve:
            float(row[3].replace(",", "."))
        for row in descs:
            self.assertTrue(row[1] and row[2], row)


class Art(unittest.TestCase):
    def test_every_file_the_pet_names_ships(self):
        missing = [(path, referrer) for path, referrer in asset_list()
                   if path not in MISSING_IN_OLD and not published(path)]
        self.assertEqual(missing, [])

    def test_the_45_items_have_olds_rows(self):
        lines = item_lines()
        self.assertEqual(sorted(lines), sorted(PET_VNUMS))
        self.assertEqual(lines[55010].split("\t")[2], "icon/item/55012.tga")
        self.assertEqual(lines[55700].split("\t")[2], "icon/item/55701.tga")

    @unittest.skipUnless(os.path.isdir(os.path.join(lf.REPO, "assets", "metin2_patch_pet1")),
                         "the sparse checkout lacks the model groups")
    def test_every_pet_mob_has_its_model(self):
        names = old_content.npclist_entries(read(old_content.NPCLIST))
        self.assertTrue(names)
        text = read(old_content.NPCLIST)
        sources = dict(re.findall(r"^0\t(\S+)\t(\S+)", text, re.M))
        for vnum in PET_MOBS:
            with self.subTest(vnum=vnum):
                name = re.search(r"^%d\t(\S+)" % vnum, text, re.M).group(1)
                folder = sources.get(name, name)
                found = any(published("d:/ymir work/%s/%s/%s.msm" % (root, folder, name))
                            for root in ("npc2", "npc", "monster", "monster2"))
                self.assertTrue(found, (vnum, name, folder))


if __name__ == "__main__":
    unittest.main()
