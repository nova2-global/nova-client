"""The options of the QoL social package (NOVA-211, 212, 213, 215, 216, 217):
python3 -B -m unittest qol_options_test (from tools/).

- constInfo's saved options (config/game_options.cfg): the yang pickup line
  (NOVA-211), the camera distance (NOVA-212) and the country flags
  (NOVA-215), their defaults, the file, and what each applies;
- game.py: the yang line obeys its option, the metin queue's chat lines
  (NOVA-216), the saved options applied at game start;
- the key table (NOVA-217): the wiki on H, Help on F1, quickslot 5 without
  a default key, and the saved tables of older clients;
- the options' search index (NOVA-213): the matching rules, and one entry
  for every row of both documents;
- both game options windows (legacy and NovaUI) with the two new rows, the
  NovaUI search field, its results, the jump and the highlight in the game
  and system options."""
import io
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_sys_test as sys_test  # noqa: E402
import nui_game_support as support  # noqa: E402
import nui_test_support  # noqa: E402

ROOT = support.ROOT
WINDOWS = sys_test.WINDOWS
SAVED = "config/game_options.cfg"


class Files(object):
    """An opener over a dict of paths, as the client's open() on config/."""

    def __init__(self, files=None):
        self.files = dict(files or {})

    def __call__(self, path, mode="r"):
        if "w" in mode:
            files = self.files

            class Writer(io.StringIO):
                def close(self_inner):
                    files[path] = self_inner.getvalue()
                    io.StringIO.close(self_inner)

            return Writer()
        if path not in self.files:
            raise IOError(path)
        return io.StringIO(self.files[path])


def use_files(world, files):
    """The world's constInfo reads and writes `files`, read afresh."""
    const = world.m("constInfo")
    const.SAVED_OPTIONS_OPEN = files
    const.RELOAD_SAVED_OPTIONS()
    return const


class World(sys_test.World):
    """nui_sys_test's world with the options index loaded."""

    def __init__(self, nui_on, windows=sys_test.SYS, files=None, setup=None):
        sys_test.World.__init__(self, nui_on, windows, setup=setup)
        self.files = files if files is not None else Files()
        with self.game:
            use_files(self, self.files)


def chrmgr_calls(world, name="chrmgr.SetShowLanguageFlag"):
    return [args for (call, args) in world.game.log if call == name]


# --- constInfo's saved options ----------------------------------------------------

class SavedOptions(unittest.TestCase):
    def setUp(self):
        self.files = Files()
        self.world = World(True, files=self.files)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        self.const = self.world.m("constInfo")

    def test_the_defaults_without_a_file(self):
        c = self.const
        self.assertEqual((c.GET_SAVED_OPTION(c.OPTION_YANG_TEXT), c.GET_SAVED_OPTION(c.OPTION_COUNTRY_FLAGS),
                          c.GET_SAVED_OPTION(c.OPTION_CAMERA_ZOOM)), (1, 1, 0))
        self.assertEqual(self.files.files, {}, "reading writes nothing")

    def test_a_change_is_saved_at_once_and_read_back_at_the_next_start(self):
        c = self.const
        self.assertTrue(c.SET_SAVED_OPTION(c.OPTION_YANG_TEXT, 0))
        self.assertIn("yang_text\t0", self.files.files[SAVED].split("\n"))
        self.assertFalse(c.SET_SAVED_OPTION(c.OPTION_YANG_TEXT, 0), "no change, no write")
        c.RELOAD_SAVED_OPTIONS()
        self.assertEqual(c.GET_SAVED_OPTION(c.OPTION_YANG_TEXT), 0)

    def test_a_broken_or_unknown_line_is_skipped(self):
        self.files.files[SAVED] = "# header\nyang_text\tx\ncountry_flags\t0\nno_such\t1\ncamera_zoom\n\n"
        c = self.const
        c.RELOAD_SAVED_OPTIONS()
        self.assertEqual((c.GET_SAVED_OPTION(c.OPTION_YANG_TEXT), c.GET_SAVED_OPTION(c.OPTION_COUNTRY_FLAGS),
                          c.GET_SAVED_OPTION(c.OPTION_CAMERA_ZOOM)), (1, 0, 0))

    def test_an_unknown_option_raises(self):
        with self.assertRaises(KeyError):
            self.const.GET_SAVED_OPTION("no_such")

    def test_the_camera_distance_is_saved_and_restored_at_the_next_login(self):
        """NOVA-212 (OLD constInfo.py:340-360): the choice survives a restart."""
        c = self.const
        c.SET_CAMERA_MAX_DISTANCE_INDEX(1)
        self.assertIn("camera_zoom\t1", self.files.files[SAVED].split("\n"))
        # The next client: constInfo starts at the short distance again.
        c.CAMERA_MAX_DISTANCE = c.CAMERA_MAX_DISTANCE_LIST[0]
        c.RELOAD_SAVED_OPTIONS()
        mark = len(self.world.game.log)
        c.SET_DEFAULT_CAMERA_MAX_DISTANCE()
        self.assertEqual(c.GET_CAMERA_MAX_DISTANCE_INDEX(), 1)
        self.assertEqual(self.world.game.log[mark:], [("app.SetCameraMaxDistance", (c.CAMERA_MAX_DISTANCE_LIST[1],))])

    def test_a_saved_camera_index_out_of_range_reads_as_the_short_distance(self):
        c = self.const
        self.files.files[SAVED] = "camera_zoom\t7\n"
        c.RELOAD_SAVED_OPTIONS()
        c.SET_DEFAULT_CAMERA_MAX_DISTANCE()
        self.assertEqual(c.GET_CAMERA_MAX_DISTANCE_INDEX(), 0)

    def test_the_country_flags_apply_at_start_and_at_once_on_a_change(self):
        """NOVA-215: chrmgr.SetShowLanguageFlag at game start (the saved
        choice) and at each change."""
        c = self.const
        c.SET_DEFAULT_COUNTRY_FLAGS()
        self.assertEqual(chrmgr_calls(self.world), [(True,)])
        c.SET_SAVED_OPTION(c.OPTION_COUNTRY_FLAGS, 0)
        self.assertEqual(chrmgr_calls(self.world), [(True,), (False,)])
        c.RELOAD_SAVED_OPTIONS()
        c.SET_DEFAULT_COUNTRY_FLAGS()
        self.assertEqual(chrmgr_calls(self.world)[-1], (False,))

    def test_an_older_exe_without_the_flag_call_is_left_alone(self):
        self.world.game.modules["chrmgr"].lack("SetShowLanguageFlag")
        c = self.const
        c.SET_DEFAULT_COUNTRY_FLAGS()
        self.assertTrue(c.SET_SAVED_OPTION(c.OPTION_COUNTRY_FLAGS, 0))

    def test_a_file_that_cannot_be_written_keeps_the_choice_for_the_session(self):
        c = self.const

        def refuse(path, mode="r"):
            raise IOError(path)
        c.SAVED_OPTIONS_OPEN = refuse
        self.assertTrue(c.SET_SAVED_OPTION(c.OPTION_YANG_TEXT, 0))
        self.assertEqual(c.GET_SAVED_OPTION(c.OPTION_YANG_TEXT), 0)


# --- game.py ------------------------------------------------------------------------

GAME_METHODS = ("OnPickMoney", "BINARY_MetinQueueMessage")


def game_window(namespace):
    source = support.source_of("game.py", GAME_METHODS, inside="GameWindow")
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)
    return namespace["GameWindow"]()


class GameLines(unittest.TestCase):
    def setUp(self):
        self.log = []
        self.chat = support.Recording("chat", self.log, CHAT_TYPE_INFO=1)
        self.options = {"yang_text": 1}
        const = types.SimpleNamespace(OPTION_YANG_TEXT="yang_text", GET_SAVED_OPTION=lambda name: self.options[name])
        locale = types.SimpleNamespace(GAME_PICK_MONEY="You have received %d Yang.", METIN_QUEUE_ADDED="added",
                                       METIN_QUEUE_REMOVED="removed", METIN_QUEUE_FULL="full",
                                       METIN_QUEUE_PREMIUM_HINT="premium")
        self.player = types.SimpleNamespace(METIN_QUEUE_ADDED=1, METIN_QUEUE_REMOVED=2, METIN_QUEUE_FULL=3,
                                            METIN_QUEUE_FULL_PREMIUM_HINT=4)
        self.window = game_window({"chat": self.chat, "constInfo": const, "localeInfo": locale,
                                   "player": self.player})

    def test_the_yang_line_obeys_its_option(self):
        """NOVA-211 (OLD game.py:1463-1466)."""
        self.window.OnPickMoney(1500)
        self.assertEqual(self.log, [("chat.AppendChat", (1, "You have received 1500 Yang."))])
        self.options["yang_text"] = 0
        self.window.OnPickMoney(1500)
        self.assertEqual(len(self.log), 1, "off: no line")

    def test_the_metin_queue_lines(self):
        """NOVA-216 (OLD game.py:3885-3893, the kinds of the C++ contract):
        added, removed, full; full with the premium hint says both."""
        for kind in (1, 2, 3, 4, 0, 9):
            self.window.BINARY_MetinQueueMessage(kind)
        self.assertEqual(self.log, [("chat.AppendChat", (1, "added")), ("chat.AppendChat", (1, "removed")),
                                    ("chat.AppendChat", (1, "full")), ("chat.AppendChat", (1, "full")),
                                    ("chat.AppendChat", (1, "premium"))])

    def test_an_older_exe_without_the_kind_constants_uses_the_contracts_values(self):
        for name in list(vars(self.player)):
            delattr(self.player, name)
        self.window.BINARY_MetinQueueMessage(3)
        self.assertEqual(self.log, [("chat.AppendChat", (1, "full"))])

    def test_the_game_start_applies_the_saved_options(self):
        source = support.source_of("game.py", ("Open",), inside="GameWindow")
        self.assertIn("constInfo.SET_DEFAULT_CAMERA_MAX_DISTANCE()", source)
        self.assertIn("constInfo.SET_DEFAULT_COUNTRY_FLAGS()", source)


# --- the key table (NOVA-217) -------------------------------------------------------------

def load_keybindings():
    return nui_test_support.load_module("keybindings", os.path.join(ROOT, "keybindings.py"))


class WikiAndHelpKeys(unittest.TestCase):
    def setUp(self):
        self.kb = load_keybindings()
        self.files = Files()

    def table(self, text=None):
        if text is not None:
            self.files.files["config/keys.cfg"] = text
        bindings = self.kb.Bindings(opener=self.files)
        bindings.load()
        return bindings

    def test_the_wiki_is_on_h_and_help_on_f1(self):
        kb = self.kb
        bindings = self.table()
        self.assertEqual(bindings.keys("wiki"), [kb.key("H"), 0])
        self.assertEqual(bindings.keys("help"), [kb.key("F1"), 0])
        self.assertEqual(bindings.keys("quickslot_5"), [0, 0], "Help took its F1 (Eddy to confirm)")
        self.assertEqual(kb.ACTION["wiki"].section, "windows")
        self.assertEqual(kb.ACTION["wiki"].label, "KEYBIND_WIKI")
        self.assertEqual(bindings.actions_for(kb.DIK["H"]), ["wiki"])
        self.assertEqual(bindings.actions_for(kb.DIK["F1"]), ["help"])

    def test_one_constant_gives_f1_back_to_quickslot_5(self):
        kb = self.kb
        kb.F1_DEFAULT = "quickslot_5"
        actions = dict((a.id, a) for a in kb._actions())
        self.assertEqual(actions["quickslot_5"].defaults[0], kb.key("F1"))
        self.assertEqual(actions["help"].defaults[0], 0)
        self.assertEqual(actions["wiki"].defaults[0], kb.key("H"))

    def test_no_two_actions_share_a_default_key(self):
        seen = {}
        for a in self.kb.ACTIONS:
            for binding in a.defaults:
                if binding:
                    self.assertNotIn(binding, seen, (a.id, seen.get(binding)))
                    seen[binding] = a.id

    def test_a_player_who_kept_the_defaults_gets_the_new_ones(self):
        kb = self.kb
        bindings = self.table(kb.FILE_HEADER + "\ninventory\tM\t-\nminimap\tI\t-\n")
        self.assertEqual((bindings.first("wiki"), bindings.first("help"), bindings.first("quickslot_5")),
                         (kb.key("H"), kb.key("F1"), 0))

    def test_a_saved_help_on_h_keeps_h_and_the_wiki_gets_no_key(self):
        """An older client saved Help only when it differed from H alone: H
        with a second key. Help keeps both; H is not also the wiki's."""
        kb = self.kb
        bindings = self.table(kb.FILE_HEADER + "\nhelp\tH\tF12\n")
        self.assertEqual(bindings.keys("help"), [kb.key("H"), kb.key("F12")])
        self.assertEqual(bindings.keys("wiki"), [0, 0])
        self.assertEqual(bindings.actions_for(kb.DIK["H"]), ["help"])
        self.assertEqual(bindings.actions_for(kb.DIK["F1"]), [])

    def test_a_saved_quickslot_5_on_f1_keeps_f1_and_help_gets_no_key(self):
        kb = self.kb
        bindings = self.table(kb.FILE_HEADER + "\nquickslot_5\tF1\tNUMPAD1\n")
        self.assertEqual(bindings.keys("quickslot_5"), [kb.key("F1"), kb.key("NUMPAD1")])
        self.assertEqual(bindings.keys("help"), [0, 0])
        self.assertEqual(bindings.actions_for(kb.DIK["F1"]), ["quickslot_5"])

    def test_a_key_saved_on_h_elsewhere_keeps_it(self):
        kb = self.kb
        bindings = self.table(kb.FILE_HEADER + "\ninventory\tH\t-\nhelp\tI\t-\n")
        self.assertEqual(bindings.actions_for(kb.DIK["H"]), ["inventory"])
        self.assertEqual(bindings.keys("wiki"), [0, 0])
        self.assertEqual(bindings.first("help"), kb.key("I"))

    def test_a_saved_table_is_written_back_without_the_new_defaults(self):
        kb = self.kb
        bindings = self.table(kb.FILE_HEADER + "\nhelp\tH\tF12\n")
        bindings.save()
        lines = self.files.files["config/keys.cfg"].split("\n")
        self.assertIn("help\tH\tF12", lines)
        self.assertIn("wiki\t-\t-", lines, "the wiki's lost H is saved, so it stays lost")

    def test_the_badges_name_the_new_keys(self):
        bindings = self.table()
        self.assertEqual(self.kb.badge("wiki", bindings), "H")
        self.assertEqual(self.kb.badge("help", bindings), "F1")
        self.assertEqual(self.kb.badge("quickslot_5", bindings), "")


class TaskbarQuickslot5(unittest.TestCase):
    """The taskbars draw a quickslot's legacy key art (slot_5 is "F1") while
    the slot keeps its default key; with no default key there is no art."""

    def test_quickslot_5_shows_no_f1_art(self):
        source = support.source_of("uitaskbar.py", ("QuickSlotKey",))
        kb = load_keybindings()
        bindings = kb.Bindings(opener=Files())
        kb.set_current(bindings)
        namespace = {"keybindings": kb, "QUICKSLOT_ACTIONS": tuple("quickslot_%d" % n for n in range(1, 9))}
        exec(compile(source, "uitaskbar.py", "exec"), namespace)
        self.assertEqual(namespace["QuickSlotKey"](4), ("", False))
        self.assertEqual(namespace["QuickSlotKey"](5), ("F2", True))


# --- the search index (NOVA-213) ----------------------------------------------------------

def load_index(strings=None):
    locale = types.ModuleType("uiScriptLocale")
    for name, text in (strings or {}).items():
        setattr(locale, name, text)
    modules = nui_test_support.Modules(uiScriptLocale=locale)
    index = nui_test_support.load_module("settings_index", os.path.join(ROOT, "settings_index.py"))
    return index, modules


def ids(entries):
    return [entry.id for entry in entries]


class SearchIndex(unittest.TestCase):
    def setUp(self):
        self.index, modules = load_index({"OPTION_CAMERA_DISTANCE": "Kamera", "OPTION_KEYWORDS_CAMERA": "Abstand Zoom",
                                          "OPTION_YANG_TEXT": "Yang-Anzeige", "OPTION_INTERFACE": "Oberflaeche"})
        self.addCleanup(modules.restore)

    def search(self, text, window="system", available=None):
        return ids(self.index.search(text, window, available))

    def test_the_locale_label_the_english_label_and_both_keywords(self):
        self.assertEqual(self.search("kamera"), ["camera"])
        self.assertEqual(self.search("Camera"), ["camera", "fov"])
        self.assertEqual(self.search("abstand"), ["camera"], "the locale's keywords")
        self.assertEqual(self.search("distance"), ["camera", "fog"], "the English keywords")

    def test_labels_that_start_with_the_text_come_first(self):
        self.assertEqual(self.search("fo")[:2], ["fog", "fov"])
        self.assertEqual(self.search("view")[0], "fov", "a label holding it before keyword matches")

    def test_every_word_must_match_and_case_does_not_count(self):
        self.assertEqual(self.search("MUSIC background"), ["bgm"])
        self.assertEqual(self.search("  "), [])
        self.assertEqual(self.search("zzz"), [])

    def test_each_window_searches_its_own_rows(self):
        self.assertEqual(self.search("yang", "system"), [])
        self.assertEqual(self.search("yang", "game"), ["yang"])
        self.assertEqual(self.search("flag", "game"), ["flags"])
        self.assertEqual(self.search("hotkey", "game"), ["keys"])

    def test_rows_the_window_does_not_show_are_left_out(self):
        self.assertIn("colors", self.search("accent"))
        self.assertEqual(self.search("accent", available={"camera"}), [])

    def test_the_section_is_searched_and_shown(self):
        self.assertEqual(self.search("oberflaeche"), ["theme", "scale", "motion", "effects", "colors"])
        rows = self.index.result_rows("theme", "system", lambda text: text)
        self.assertEqual(rows, [{"id": "theme", "label": "Theme", "where": "Oberflaeche"}])

    def test_at_most_max_results(self):
        self.index.MAX_RESULTS = 2
        self.assertEqual(len(self.search("e")), 2)


def row_ids(document, prefix):
    text = sys_test.read(os.path.join(WINDOWS, document, document + ".rml"))
    return [name.replace("-", "_") for name in re.findall(r'class="%s-row %s-row--([a-z0-9-]+)' % (prefix, prefix), text)]


class EveryRowIndexed(unittest.TestCase):
    """The index is the windows' rows: a new row without an entry fails."""

    def setUp(self):
        self.index, modules = load_index()
        self.addCleanup(modules.restore)

    def test_the_game_options(self):
        self.assertEqual(ids(self.index.options("game")), row_ids("game-options", "go"))

    def test_the_system_options(self):
        rows = row_ids("system-options", "so") + ["colors"]
        rows.remove("color")   # the color slots' rows, under the colors section
        rows.remove("hue")
        rows.remove("reset")
        self.assertEqual(ids(self.index.options("system")), rows)


# --- the game options: the two rows (NOVA-211, NOVA-215) -------------------------------------

class GameOptionRows(sys_test.Pair):
    def setup_state(self, game):
        game.status[sys_test.P["LEVEL"]] = 105
        game.sash_flag = sys_test.sash_flag(game)

    def pair(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            with world.game:
                use_files(world, Files())
        a, b = legacy.make_game_options(), novaui.make_game_options()
        a.Show()
        b.Show()
        return legacy, novaui, a, b

    def test_both_rows_show_their_options(self):
        legacy, novaui, a, b = self.pair()
        self.assertEqual((sys_test.board(b).get("yang_text"), sys_test.board(b).get("country_flags")), (True, True))
        self.assertEqual([button.down for button in a.yangTextButtonList], [True, False])
        self.assertEqual([button.down for button in a.countryFlagsButtonList], [True, False])

    def test_the_yang_row_saves_its_choice(self):
        legacy, novaui, a, b = self.pair()
        calls = self.same(legacy, novaui, a.yangTextButtonList[1].click,
                          lambda: sys_test.fire(b, "choose", "yang_text", 0, 0), "yang off")
        self.assertEqual(calls, [])
        for world in (legacy, novaui):
            const = world.m("constInfo")
            self.assertEqual(const.GET_SAVED_OPTION(const.OPTION_YANG_TEXT), 0)
        self.assertIs(sys_test.board(b).get("yang_text"), False)
        self.assertEqual([button.down for button in a.yangTextButtonList], [False, True])

    def test_the_flags_row_saves_and_applies_its_choice(self):
        legacy, novaui, a, b = self.pair()
        calls = self.same(legacy, novaui, a.countryFlagsButtonList[1].click,
                          lambda: sys_test.fire(b, "choose", "country_flags", 0, 0), "flags off")
        self.assertEqual(calls, [("chrmgr.SetShowLanguageFlag", (False,))])
        self.assertEqual(self.same(legacy, novaui, a.countryFlagsButtonList[1].click,
                                   lambda: sys_test.fire(b, "choose", "country_flags", 0, 0), "again"), [],
                         "a press on the choice in effect makes no call")
        calls = self.same(legacy, novaui, a.countryFlagsButtonList[0].click,
                          lambda: sys_test.fire(b, "choose", "country_flags", 1, 0), "flags on")
        self.assertEqual(calls, [("chrmgr.SetShowLanguageFlag", (True,))])
        self.assertIs(sys_test.board(b).get("country_flags"), True)

    def test_legacys_board_grows_by_the_two_rows(self):
        # Under NOVA-188's new item row at 465 (wave 10's merge).
        legacy, novaui, a, b = self.pair()
        module = legacy.m("uiGameOption")
        self.assertEqual((module.LegacyOptionDialog.YANG_TEXT_ROW_Y, module.LegacyOptionDialog.COUNTRY_FLAGS_ROW_Y,
                          module.LegacyOptionDialog.COUNTRY_FLAGS_HEIGHT), (490, 515, 558))
        self.assertEqual(a.GetChild("board").GetHeight(), 558)


# --- the NovaUI search (NOVA-213) ---------------------------------------------------------------

def field_of(document, field):
    """The field's change event and maxlength, as the document says."""
    text = sys_test.read(os.path.join(WINDOWS, document, document + ".rml"))
    tag = re.search(r'<input[^>]*id="%s"[^>]*>' % field, text).group(0)
    event = re.search(r'data-event-change="([a-z_]+)\(ev\.value, ev\.linebreak\)"', tag).group(1)
    return event, int(re.search(r'maxlength="(\d+)"', tag).group(1))


class Search(unittest.TestCase):
    FIELD = "go-search"
    DOCUMENT = "game-options"

    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        state = self.world.game.state
        path = "nui/windows/%s/%s.rml" % (self.DOCUMENT, self.DOCUMENT)
        event, limit = field_of(self.DOCUMENT, self.FIELD)
        state.field_events[(path, self.FIELD)] = event
        state.maxlength[(path, self.FIELD)] = limit
        self.window = self.make()
        with sys_test.quiet():
            self.window.Show()

    def make(self):
        return self.world.make_game_options()

    def board(self):
        return sys_test.board(self.window)

    def type(self, text):
        with sys_test.quiet():
            self.board().set_value(self.FIELD, text)

    def test_typing_lists_the_matches(self):
        self.assertEqual((self.board().get("searching"), self.board().get("results")), (False, []))
        self.type("yang")
        self.assertIs(self.board().get("searching"), True)
        self.assertEqual([row["id"] for row in self.board().get("results")], ["yang"])
        self.type("zzz")
        self.assertEqual((self.board().get("searching"), self.board().get("results")), (True, []))
        self.type("")
        self.assertIs(self.board().get("searching"), False)

    def test_a_press_on_a_result_highlights_its_row_briefly_and_ends_the_search(self):
        state = self.world.game.state
        state.now = 100.0
        self.type("flag")
        with sys_test.quiet():
            self.board().fire("goto", "flags", 0)
        self.assertEqual((self.board().get("found"), self.board().get("found_end")), ("flags", 102.0))
        self.assertEqual((self.board().get("searching"), self.board().get_value(self.FIELD)), (False, ""))
        with sys_test.quiet():
            self.board().fire("found_done")
        self.assertEqual(self.board().get("found"), "")

    def test_a_right_press_and_an_unknown_row_do_nothing(self):
        self.type("flag")
        with sys_test.quiet():
            self.board().fire("goto", "flags", 1)
            self.board().fire("goto", "camera", 0)
        self.assertEqual(self.board().get("found"), "")

    def test_enter_opens_the_first_result(self):
        self.type("hotkey")
        with sys_test.quiet():
            self.board().fire("search", "hotkey", True)
        self.assertEqual(self.board().get("found"), "keys")

    def test_a_press_on_the_field_gives_it_the_caret(self):
        with sys_test.quiet():
            self.board().fire("search_press", 0)
        self.assertEqual(self.board().focused, self.FIELD)

    def test_a_hide_forgets_the_search(self):
        self.type("flag")
        with sys_test.quiet():
            self.window.Hide()
            self.window.Show()
        self.assertEqual((self.board().get("searching"), self.board().get("results"), self.board().get("found")),
                         (False, [], ""))


class SystemSearch(Search):
    FIELD = "so-search"
    DOCUMENT = "system-options"

    def make(self):
        return self.world.make_options()

    def test_typing_lists_the_matches(self):
        self.type("zoom")
        self.assertEqual([row["id"] for row in self.board().get("results")], ["camera", "scale"])

    def test_a_press_on_a_result_highlights_its_row_briefly_and_ends_the_search(self):
        self.world.game.state.now = 5.0
        self.type("camera")
        with sys_test.quiet():
            self.board().fire("goto", "camera", 0)
        self.assertEqual((self.board().get("found"), self.board().get("found_end")), ("camera", 7.0))

    def test_a_right_press_and_an_unknown_row_do_nothing(self):
        with sys_test.quiet():
            self.board().fire("goto", "yang", 0)
        self.assertEqual(self.board().get("found"), "")

    def test_enter_opens_the_first_result(self):
        self.type("fps")
        with sys_test.quiet():
            self.board().fire("search", "fps", True)
        self.assertEqual(self.board().get("found"), "fps")

    def test_the_colors_are_found_only_while_the_theme_offers_them(self):
        self.type("accent")
        found = [row["id"] for row in self.board().get("results")]
        has_slots = bool(self.board().get("color_slots"))
        self.assertEqual(found, ["colors"] if has_slots else [])


class CameraSaved(sys_test.Pair):
    def test_both_system_options_save_the_camera_choice(self):
        legacy, novaui = self.worlds()
        files = {}
        for world in (legacy, novaui):
            with world.game:
                files[world] = Files()
                use_files(world, files[world])
        a, b = legacy.make_options(), novaui.make_options()
        a.Show()
        b.Show()
        self.same(legacy, novaui, lambda: a.GetChild("camera_long").click(),
                  lambda: sys_test.fire(b, "choose", "camera", 1, 0), "far")
        for world in (legacy, novaui):
            self.assertIn("camera_zoom\t1", files[world].files[SAVED].split("\n"))


if __name__ == "__main__":
    unittest.main()
