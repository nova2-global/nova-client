"""Tests for the social client's legacy windows (foundation wave, chunk C3):
python3 -B -m unittest social_test (from tools/).

The C++ half (the packets, CPythonMessenger, the net/messenger/chat names) is
tested in nova-client-src's userinterface_tests. Here the legacy windows are
made from their real uiscripts by nui_game_support's stand-ins (nui_w4_world's
World with the social windows), once with every NovaUI flag off (the legacy
windows) and once with the social flags on (NovaUI's facades over the same
legacy classes), and driven as the C++ handlers drive them:
- the messenger's staff rosters (NOVA-30, NOVA-46): the Helper and Team
  groups at the C++ indices 2 and 3, their rows, the language flags, a list
  that empties a group, and the indices a NovaUI window has no group for;
- every new locale key in all 17 locales, OLD's text where OLD's locale has
  it and English otherwise."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

ROOT = support.ROOT
ASSETS = os.path.normpath(os.path.join(ROOT, ".."))
LOCALES = os.path.join(ASSETS, "locale", "locale")
OLD_LOCALES = os.path.normpath(os.path.join(ROOT, "..", "..", "..", "..", "..", "old", "client_pack", "source",
                                            "locale"))
FLAGS = os.path.join(LOCALES, "common", "ui", "flag", "32")
FRIEND, GUILD, HELPER, TEAMLER = 0, 1, 2, 3

# The keys each feature adds, with the English text (OLD's where OLD has the
# key): {file: {key: English}}.
ROSTER_KEYS = {"game": {"MESSENGER_HELPER": "Helper", "MESSENGER_TEAMLER": "Team"}}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def last_call(widget, *names):
    """The last of a stand-in widget's recorded calls named one of `names`."""
    for call in reversed(widget.calls):
        if call[0] in names:
            return call
    return None


def enabled(button):
    """A legacy button's state: its last Enable or Disable (enabled when it
    had neither, as a fresh button is)."""
    call = last_call(button, "Enable", "Disable")
    return call is None or call[0] == "Enable"


def position(widget):
    call = last_call(widget, "SetPosition")
    return call[1:] if call else (0, 0)


def locale_entries(path):
    """{key: text} of a locale file, the last line of a key winning, as the
    client's loader reads it."""
    entries = {}
    for line in read(path).split("\n"):
        if "\t" in line:
            tokens = line.split("\t")
            entries[tokens[0]] = tokens[1].rstrip()
    return entries


class MessengerWorld(unittest.TestCase):
    def world(self, nui_on):
        world = w4.World(nui_on, social=True)
        window = world.make("messenger", "uiMessenger", "MessengerWindow", "nui_messenger.MessengerWindow")
        with world.game, w4.quiet():
            window.SetWhisperButtonEvent(lambda name: None)
            window.SetGuildButtonEvent(lambda: None)
            window.InitializeHandler()
        return world, window

    def call(self, world, window, name, *args):
        with world.game, w4.quiet():
            return getattr(window, name)(*args)

    @staticmethod
    def names(group):
        return [member.GetName() for member in group.memberList]


class Rosters(MessengerWorld):
    def test_the_legacy_window_has_olds_groups_in_olds_order(self):
        world, window = self.world(False)
        locale = world.m("localeInfo")
        messenger = world.m("uiMessenger")
        self.assertEqual((messenger.FRIEND, messenger.GUILD, messenger.HELPER, messenger.TEAMLER), (0, 1, 2, 3))
        self.assertEqual([group.GetName() for group in window.groupList[:4]],
                         [locale.MESSENGER_FRIEND, locale.MESSENGER_GUILD, "Helper", "Team"])
        self.assertIsInstance(window.groupList[HELPER], messenger.MessengerHelperGroup)
        self.assertIsInstance(window.groupList[TEAMLER], messenger.MessengerTeamlerGroup)

    def test_a_staff_member_logs_in_and_out_and_can_never_be_removed(self):
        world, window = self.world(False)
        messenger = world.m("uiMessenger")
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.call(world, window, "OnLogout", TEAMLER, "[GM]Nova")

        helper = window.groupList[HELPER].FindMember("[SM]Lucius")
        teamler = window.groupList[TEAMLER].FindMember("[GM]Nova")
        self.assertIsInstance(helper, messenger.MessengerHelperItem)
        self.assertIsInstance(teamler, messenger.MessengerTeamlerItem)
        self.assertTrue(helper.IsOnline())
        self.assertFalse(teamler.IsOnline())
        self.assertFalse(helper.CanRemove())
        self.assertFalse(teamler.CanRemove())
        self.assertTrue(helper.CanWhisper(), "an online staff member can be whispered")

        # A logout keeps the name, offline, as the friends' does.
        self.call(world, window, "OnLogout", HELPER, "[SM]Lucius")
        self.assertIs(window.groupList[HELPER].FindMember("[SM]Lucius"), helper)
        self.assertFalse(helper.IsOnline())

        self.call(world, window, "OnSelectItem", helper)
        self.assertFalse(enabled(window.removeButton))

    def test_the_rows_show_each_language_flag_after_the_name(self):
        world, window = self.world(False)
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.call(world, window, "SetLanguagesFlags", HELPER, "[SM]Lucius", "en pt xx")

        member = window.groupList[HELPER].FindMember("[SM]Lucius")
        self.assertEqual(member.GetLanguages(), "en pt xx")
        self.assertEqual([flag.image for flag in member.flagImageList],
                         ["locale/common/ui/flag/32/en.tga", "locale/common/ui/flag/32/pt.tga"],
                         "a code with no flag file shows none")
        start = 20 + 6 * len("[SM]Lucius") + 4
        self.assertEqual([position(flag) for flag in member.flagImageList], [(start, 0), (start + 18, 0)])

        # A later login keeps the flags after the name; new languages replace them.
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.assertEqual(len(member.flagImageList), 2)
        old_flags = list(member.flagImageList)
        self.call(world, window, "SetLanguagesFlags", HELPER, "[SM]Lucius", "")
        self.assertEqual(member.flagImageList, [])
        self.assertTrue(all(not flag.IsShow() for flag in old_flags))

    def test_languages_for_a_name_the_group_lacks_change_nothing(self):
        world, window = self.world(False)
        self.call(world, window, "SetLanguagesFlags", TEAMLER, "Nobody", "en")
        self.assertEqual(window.groupList[TEAMLER].memberList, [])

    def test_a_list_empties_its_group_first_and_takes_a_selected_row_with_it(self):
        world, window = self.world(False)
        self.call(world, window, "OnLogin", HELPER, "Old")
        self.call(world, window, "OnLogin", FRIEND, "Alice")
        old = window.groupList[HELPER].FindMember("Old")
        self.call(world, window, "OnSelectItem", old)

        self.call(world, window, "OnRemoveAllList", HELPER)

        self.assertEqual(window.groupList[HELPER].memberList, [])
        self.assertIsNone(window.selectedItem)
        self.assertFalse(old.IsShow(), "the removed row leaves the screen")
        self.assertEqual(self.names(window.groupList[FRIEND]), ["Alice"], "other groups are untouched")

    def test_the_helper_and_team_rows_follow_the_guild_rows(self):
        world, window = self.world(False)
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.call(world, window, "OnLogin", TEAMLER, "[GM]Nova")
        names = [item.GetName() for item in window.showingItemList]
        self.assertLess(names.index("Helper"), names.index("[SM]Lucius"))
        self.assertLess(names.index("[SM]Lucius"), names.index("Team"))
        self.assertLess(names.index("Team"), names.index("[GM]Nova"))

    def test_under_novaui_the_roster_calls_find_no_group_and_change_nothing(self):
        world, window = self.world(True)
        self.assertEqual(len(window.groupList), 2, "NovaUI's window holds Friend and Guild")
        for name, args in (("OnLogin", (HELPER, "[SM]Lucius")), ("OnLogout", (TEAMLER, "[GM]Nova")),
                           ("SetLanguagesFlags", (HELPER, "[SM]Lucius", "en")), ("OnRemoveAllList", (TEAMLER,)),
                           ("OnRemoveList", (HELPER, "[SM]Lucius")), ("OnLogin", (4, "Pest"))):
            with self.subTest(call=name, args=args):
                self.call(world, window, name, *args)
        self.assertEqual([len(group.memberList) for group in window.groupList], [0, 0])


class LanguageFlags(unittest.TestCase):
    def setUp(self):
        game = support.Game()
        game.load_standard()
        self.const = game.loaded["constInfo"]

    def test_every_known_code_has_its_flag_file_from_old(self):
        self.assertEqual(len(self.const.LANGUAGE_FLAG_CODES), 16)
        for code in self.const.LANGUAGE_FLAG_CODES:
            with self.subTest(code=code):
                self.assertTrue(os.path.isfile(os.path.join(FLAGS, code + ".tga")))
        self.assertEqual(sorted(name[:-4] for name in os.listdir(FLAGS)), sorted(self.const.LANGUAGE_FLAG_CODES))

    def test_a_code_maps_to_its_vfs_path_and_an_unknown_one_to_nothing(self):
        flag = self.const.GET_LANGUAGE_FLAG
        self.assertEqual(flag("en"), "locale/common/ui/flag/32/en.tga")
        self.assertEqual(flag(" PT "), "locale/common/ui/flag/32/pt.tga")
        self.assertEqual(flag("br"), "", "OLD shipped no br flag")
        self.assertEqual(flag(""), "")


class Locales(unittest.TestCase):
    KEYS = (ROSTER_KEYS,)

    def test_every_locale_has_every_new_key_olds_text_or_english(self):
        locales = [name for name in sorted(os.listdir(LOCALES))
                   if os.path.isfile(os.path.join(LOCALES, name, "locale_game.txt"))]
        self.assertEqual(len(locales), 17)
        for locale in locales:
            for keys in self.KEYS:
                for kind, english in keys.items():
                    path = os.path.join(LOCALES, locale, "locale_%s.txt" % kind)
                    self.assertTrue(read(path).endswith("\n"), path)
                    entries = locale_entries(path)
                    old_path = os.path.join(OLD_LOCALES, locale, "locale_%s.txt" % kind)
                    old = locale_entries(old_path) if os.path.isfile(old_path) else {}
                    for key, text in english.items():
                        with self.subTest(locale=locale, key=key):
                            self.assertTrue(entries.get(key, "").strip())
                            if os.path.isdir(OLD_LOCALES):
                                self.assertEqual(entries[key], old.get(key) or text)
                            if locale == "en":
                                self.assertEqual(entries[key], text)


if __name__ == "__main__":
    unittest.main()
