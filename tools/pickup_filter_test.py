"""Tests for the client half of NOVA-50, OLD's PICK_ITEMS_AROUND: the Z and `
keys pick up every item around the player (game.GameWindow.PickUpItem calls
player.PickAroundItems), and the legacy game options window
(assets/root/uigameoption.py, uiscript/gameoptiondialog.py) shows the four
pickup filter toggles of systemSetting.Get/SetPickupFilter:
python3 -B -m unittest pickup_filter_test (from tools/).

The C++ side (the pickup rule, the categories, metin2.cfg's PICKUP_FILTER and
the bindings) is tested in nova-client-src's userinterface_tests. Here:
- game.py: PickUpItem is compiled from its own source over a recording
  player module, and the two keys still reach it;
- the options window: the legacy class made from its real uiscript by
  nui_sys_test's legacy World (nui_game_support's stand-ins), the filter
  state behind systemSetting a list the stand-in reads and writes;
- the uiscript's new row fits its board, and every locale has the strings,
  OLD's English (old/client_pack/source/locale/en/locale_interface.txt
  717-721) word for word."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_sys_test as sys_test  # noqa: E402

ROOT = support.ROOT
UISCRIPT = os.path.normpath(os.path.join(ROOT, "..", "uiscript", "uiscript", "gameoptiondialog.py"))
LOCALES = os.path.normpath(os.path.join(ROOT, "..", "locale", "locale"))
# systemSetting.PICKUP_FILTER_EQUIPMENT, _SPECIAL, _POTIONS, _OTHERS are 0 to 3.
PICKUP_CHILDREN = ("pickup_equipment_button", "pickup_special_button", "pickup_potions_button",
                   "pickup_others_button")
OLD_ENGLISH = {"OPTION_PICKUP_FILTER": "Pickup Filter", "OPTION_PICKUP_EQUIPMENT": "Equipment",
               "OPTION_PICKUP_SPECIAL": "Special", "OPTION_PICKUP_POTIONS": "Potions",
               "OPTION_PICKUP_OTHERS": "Others"}


def compiled(file_name, class_name, names, namespace=None):
    """A class with the methods `names` of a root module's class, compiled
    from its own source (the legacy code, unchanged) over `namespace`."""
    source = support.source_of(file_name, names, inside=class_name)
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(namespace or {})
    exec(compile("class %s(object):\n%s\n" % (class_name, body), file_name, "exec"), namespace)
    return namespace[class_name]


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class PickUpKeys(unittest.TestCase):
    def test_pick_up_item_picks_up_everything_around(self):
        log = []
        player = support.Recording("player", log)
        window = compiled("game.py", "GameWindow", ("PickUpItem",), {"player": player})()
        window.PickUpItem()
        self.assertEqual(log, [("player.PickAroundItems", ())])

    def test_z_and_the_backquote_still_call_pick_up_item(self):
        source = read(os.path.join(ROOT, "game.py"))
        for key in ("DIK_GRAVE", "DIK_Z"):
            self.assertRegex(source, r"onPressKeyDict\[app\.%s\]\s*=\s*lambda: self\.PickUpItem\(\)" % key)
        self.assertNotIn("player.PickCloseItem()", source)


class GameOptionsPickupFilter(unittest.TestCase):
    """The legacy window over a filter state the systemSetting stand-in reads
    and writes, as CPythonSystem does."""

    def make(self, state):
        world = sys_test.World(False)
        world.__enter__()
        self.addCleanup(world.__exit__)

        def set_filter(index, flag):
            state[index] = 1 if flag else 0
        world.game.answer("systemSetting", "GetPickupFilter", lambda index: state[index])
        world.game.answer("systemSetting", "SetPickupFilter", set_filter)
        dialog = world.make_game_options()
        self.assertEqual(type(dialog).__module__, "uiGameOption")
        return world, dialog

    def downs(self, dialog):
        return [dialog.GetChild(name).down for name in PICKUP_CHILDREN]

    def test_the_four_buttons_are_bound_in_the_filter_order(self):
        world, dialog = self.make([1, 1, 1, 1])
        self.assertEqual(dialog.pickupFilterButtonList, [dialog.GetChild(name) for name in PICKUP_CHILDREN])

    def test_each_button_shows_its_category_from_the_first_show(self):
        world, dialog = self.make([1, 0, 1, 0])
        self.assertEqual(self.downs(dialog), [True, False, True, False])
        with world.game:
            dialog.Show()
        self.assertEqual(self.downs(dialog), [True, False, True, False])

    def test_a_press_flips_its_category_and_its_button_follows(self):
        state = [1, 1, 1, 1]
        world, dialog = self.make(state)
        for index, name in enumerate(PICKUP_CHILDREN):
            with self.subTest(button=name):
                mark = world.mark()
                with world.game, sys_test.quiet():
                    dialog.GetChild(name).click()
                self.assertEqual(world.effects_since(mark), [("systemSetting.SetPickupFilter", (index, False))])
                self.assertEqual(state[index], 0)
                self.assertFalse(dialog.GetChild(name).down)
        self.assertEqual(state, [0, 0, 0, 0])

        with world.game, sys_test.quiet():
            dialog.GetChild(PICKUP_CHILDREN[2]).click()
        self.assertEqual(state, [0, 0, 1, 0], "a second press turns it back on")
        self.assertEqual(self.downs(dialog), [False, False, True, False])

    def test_the_button_shows_the_setting_even_when_it_did_not_change(self):
        """RefreshPickupFilter, not the toggle's own flip, decides the look:
        a setting that refused the change keeps the button where it was."""
        state = [1, 1, 1, 1]
        world, dialog = self.make(state)
        world.game.answer("systemSetting", "SetPickupFilter", lambda index, flag: None)
        with world.game, sys_test.quiet():
            dialog.GetChild(PICKUP_CHILDREN[0]).click()
        self.assertTrue(dialog.GetChild(PICKUP_CHILDREN[0]).down)


class GameOptionsScript(unittest.TestCase):
    def script(self):
        """The uiscript's window dictionary, its strings their keys."""
        names = {}
        with mock.patch.dict(sys.modules, {"uiScriptLocale": support.support.LocaleInfo()}):
            exec(compile(read(UISCRIPT), UISCRIPT, "exec"), names)
        return names["window"]

    @staticmethod
    def children(window):
        return {child["name"]: child for child in window["children"][0]["children"]}

    def test_the_pickup_row_has_its_label_and_four_toggles_inside_the_board(self):
        window = self.script()
        board = window["children"][0]
        self.assertEqual(window["height"], board["height"])
        children = self.children(window)
        self.assertEqual(children["pickup_filter"]["text"], "OPTION_PICKUP_FILTER")
        lowest = 0
        for name, key in zip(PICKUP_CHILDREN, ("OPTION_PICKUP_EQUIPMENT", "OPTION_PICKUP_SPECIAL",
                                               "OPTION_PICKUP_POTIONS", "OPTION_PICKUP_OTHERS")):
            child = children[name]
            self.assertEqual(child["type"], "toggle_button")
            self.assertEqual(child["text"], key)
            lowest = max(lowest, child["y"] + 25)
        self.assertLessEqual(lowest, board["height"] - 8, "the last row inside the board's bottom edge")
        self.assertGreater(min(children[name]["y"] for name in PICKUP_CHILDREN),
                           max(child["y"] for name, child in children.items()
                               if name.startswith("salestext")), "under the shop name row")

    def test_the_toggles_do_not_overlap(self):
        children = self.children(self.script())
        places = [(children[name]["x"], children[name]["y"]) for name in PICKUP_CHILDREN]
        self.assertEqual(len(set(places)), 4)


class Locales(unittest.TestCase):
    def test_every_locale_has_the_pickup_strings_and_english_is_olds(self):
        locales = [name for name in sorted(os.listdir(LOCALES))
                   if os.path.exists(os.path.join(LOCALES, name, "locale_interface.txt"))]
        self.assertEqual(len(locales), 17)
        for locale in locales:
            text = read(os.path.join(LOCALES, locale, "locale_interface.txt"))
            self.assertTrue(text.endswith("\n"), locale)
            keys = dict(line.split("\t", 1) for line in text.split("\n") if "\t" in line)
            for key in OLD_ENGLISH:
                with self.subTest(locale=locale, key=key):
                    self.assertTrue(keys.get(key, "").strip())
            if locale == "en":
                self.assertEqual({key: keys[key] for key in OLD_ENGLISH}, OLD_ENGLISH)


if __name__ == "__main__":
    unittest.main()
