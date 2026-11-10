"""The ingame wiki's third round (NOVA-42, after Eddy's live test on r39):
the wiki opens in front of every window that opens it, a right press on a
tab offers Close and Close other tabs, and every page links, not only an
item's or a mob's: a list, the home page and a search link as
syswiki:list:<path>, which opens that list again and costs no prism on the
server (srv input_main.cpp IsWikiHyperlink)."""

import json
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_qol_test as qol  # noqa: E402

ASSETS = qol.ASSETS
WINDOWS_DIR = os.path.join(ASSETS, "nui", "nui", "windows")
WIKI_DIR = qol.WIKI_DIR
ITEM, MOB, SWORD, WOLF = qol.ITEM, qol.MOB, qol.SWORD, qol.WOLF
LEFT, RIGHT, MIDDLE = qol.LEFT, qol.RIGHT, qol.MIDDLE

# The server's rule for a free list link (srv/src/game/input_main.cpp
# IsWikiHyperlink): this prefix, then 1 to 64 of [a-z0-9_:], then |h.
SERVER_LIST_LINK = re.compile(r"\|Hsyswiki:list:([a-z0-9_:]{1,64})\|h")
PATH_MAX = 64


def body_classes(window):
    with open(os.path.join(WINDOWS_DIR, window, "%s.rml" % window), encoding="utf-8") as handle:
        text = handle.read()
    return re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", text).group(1).split()


def costume_hair(module):
    for i, category in enumerate(module.TREE):
        for j, sub in enumerate(category["subs"]):
            if sub["label"] == "WIKI_SUB_COSTUME_HAIR":
                return i, j
    raise AssertionError("no hair styles list")


class R3Test(qol.QolTest):
    def linked(self, world, window, event="link_press", *args):
        pasted = []
        with world.game, w4.quiet():
            window.SetPasteLinkEvent(pasted.append)
        self.press(world, window, event, *(args + (LEFT,)))
        return pasted

    def menu(self, window):
        return [m["label"] for m in self.model(window)["menu"]]


class ZOrder(R3Test):
    def test_the_dungeon_manager_draws_in_the_wikis_band(self):
        # The wiki is nui-below-legacy-ui, as the inventory, the chat and the
        # whisper are, so BringToFront cannot lift it over a document of the
        # band above (RenderBand.h). The dungeon manager drew there, so its
        # Wiki button opened the wiki behind it (Eddy, r39). Its legacy
        # window (uitimerwindow.TimerWindow, a ScriptWindow) lives in the UI
        # layer, so by AUTHORING's rule it belongs below the legacy UI too.
        self.assertIn("nui-below-legacy-ui", body_classes("wiki"))
        for opener in ("dungeon-timer", "inventory", "chat", "chat-log", "whisper"):
            with self.subTest(opener=opener):
                self.assertIn("nui-below-legacy-ui", body_classes(opener))

    def raised_on(self, open_call):
        world, window = self.world()
        board_fronts = []
        with world.game, w4.quiet():
            open_call(window)
            board = w4.board(window)
            board_fronts.append(board.front if board is not None else 0)
            fronts = list(world.game.state.fronts)
        return board, board_fronts[0], fronts

    def test_every_open_brings_the_wiki_to_the_front(self):
        for name, call in (("Open", lambda w: w.Open()), ("Toggle", lambda w: w.Toggle()),
                           ("OpenItem", lambda w: w.OpenItem(SWORD)), ("OpenMob", lambda w: w.OpenMob(WOLF)),
                           ("OpenList", lambda w: w.OpenList("home"))):
            with self.subTest(call=name):
                board, front, fronts = self.raised_on(call)
                self.assertIsNotNone(board)
                self.assertGreater(front, 0)
                self.assertIs(fronts[-1], board, "the wiki is raised last")

    def test_an_open_wiki_comes_to_the_front_again_on_a_link(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            before = w4.board(window).front
            window.OpenList("home")
            window.OpenMob(WOLF)
        self.assertEqual(w4.board(window).front, before + 2)


class _Window(object):
    """A shown window that can be weakly referenced, as a facade can."""

    def __init__(self):
        self.shown = True

    def IsShow(self):
        return self.shown


class BuriedWiki(R3Test):
    """The Wiki button (inventory, system menu: Interface.ToggleWiki) on a
    wiki that is open but behind another window brings it to the front; only
    a wiki already on top closes (the coordinator, after Eddy's r39 notes)."""

    def other_window_raised(self, world):
        hud = world.m("nui_hud")
        other = _Window()
        hud.note_top(other)
        self.other = other   # held: the record is weak
        return other

    def test_the_button_on_a_buried_wiki_brings_it_to_the_front(self):
        world, window = self.opened()
        other = self.other_window_raised(world)
        with world.game, w4.quiet():
            before = w4.board(window).front
            window.Toggle()
        self.assertTrue(window.IsShow())
        self.assertEqual(w4.board(window).front, before + 1)
        self.assertTrue(world.m("nui_hud").is_top(window))
        self.assertIsNotNone(other)

    def test_the_button_on_the_top_wiki_closes_it(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.Toggle()
        self.assertFalse(window.IsShow())

    def test_a_hidden_window_raised_later_does_not_bury_the_wiki(self):
        world, window = self.opened()
        other = self.other_window_raised(world)
        other.shown = False
        with world.game, w4.quiet():
            window.Toggle()
        self.assertFalse(window.IsShow())

    def test_a_facade_records_its_raise(self):
        world, window = self.opened()
        hud = world.m("nui_hud")
        self.other_window_raised(world)
        self.assertFalse(hud.is_top(window))
        with world.game, w4.quiet():
            window.SetTop()
        self.assertTrue(hud.is_top(window))


class TabMenu(R3Test):
    def two_tabs(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.press(world, window, "home_press", MIDDLE)
        self.press(world, window, "home_press", MIDDLE)
        self.assertEqual(len(self.model(window)["tabs"]), 3)
        return world, window

    def test_a_right_press_on_a_tab_opens_its_menu(self):
        world, window = self.two_tabs()
        self.assertEqual(self.model(window)["menu"], [])
        self.press(world, window, "tab_press", 1, RIGHT)
        self.assertEqual(self.menu(window), ["Close", "Close other tabs"])
        self.assertEqual(self.model(window)["tabs"][0]["active"], True, "the menu switches no tab")

    def test_close_closes_that_tab(self):
        world, window = self.two_tabs()
        self.press(world, window, "tab_press", 1, RIGHT)
        self.press(world, window, "menu_press", 0, LEFT)
        self.assertEqual(len(self.model(window)["tabs"]), 2)
        self.assertEqual(self.model(window)["page_vnum"], SWORD, "the shown tab stays")
        self.assertEqual(self.model(window)["menu"], [])

    def test_close_other_tabs_keeps_only_that_tab_and_shows_it(self):
        world, window = self.two_tabs()
        self.press(world, window, "tab_press", 2, RIGHT)
        self.press(world, window, "menu_press", 1, LEFT)
        tabs = self.model(window)["tabs"]
        self.assertEqual(len(tabs), 1)
        self.assertTrue(tabs[0]["active"])
        self.assertTrue(self.model(window)["home"])

    def test_close_other_tabs_is_off_with_one_tab(self):
        world, window = self.opened()
        self.press(world, window, "tab_press", 0, RIGHT)
        self.assertEqual([m["off"] for m in self.model(window)["menu"]], [False, True])
        self.press(world, window, "menu_press", 1, LEFT)
        self.assertEqual(self.model(window)["menu"], [], "an off entry still closes the menu")
        self.assertEqual(len(self.model(window)["tabs"]), 1)

    def test_a_press_elsewhere_closes_the_menu(self):
        world, window = self.two_tabs()
        self.press(world, window, "tab_press", 1, RIGHT)
        self.press(world, window, "board_press", LEFT)
        self.assertEqual(self.model(window)["menu"], [])
        self.assertEqual(len(self.model(window)["tabs"]), 3)

    def test_a_left_press_on_a_tab_closes_the_menu(self):
        world, window = self.two_tabs()
        self.press(world, window, "tab_press", 1, RIGHT)
        self.press(world, window, "tab_press", 2, LEFT)
        self.assertEqual(self.model(window)["menu"], [])

    def test_the_menu_is_placed_under_the_pressed_tab(self):
        world, window = self.two_tabs()
        boxes = world.game.state.boxes
        doc = "nui/windows/wiki/wiki.rml"
        boxes[(doc, "")] = (100, 50, 860, 600)
        boxes[(doc, "wiki-tab-1")] = (300, 120, 90, 24)
        self.press(world, window, "tab_press", 1, RIGHT)
        scale = world.m("nui").get_scale() or 1.0
        self.assertAlmostEqual(self.model(window)["menu_x"], 200 / scale)
        self.assertAlmostEqual(self.model(window)["menu_y"], 94 / scale)

    def test_the_menu_goes_with_the_window(self):
        world, window = self.two_tabs()
        self.press(world, window, "tab_press", 1, RIGHT)
        with world.game, w4.quiet():
            window.Close()
            window.Open()
        self.assertEqual(self.model(window)["menu"], [])


class ListLinks(R3Test):
    def test_every_list_has_a_path_the_server_takes_as_free(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        paths = set()
        for i, category in enumerate(module.TREE):
            for j, sub in enumerate(category["subs"]):
                path = module.list_path(("sub", i, j))
                with self.subTest(path=path):
                    self.assertTrue(SERVER_LIST_LINK.fullmatch("|Hsyswiki:list:%s|h" % path))
                    self.assertNotIn(path, paths)
                    self.assertEqual(module.list_of_path(path), ("sub", i, j))
                paths.add(path)
        self.assertEqual(module.list_path(None), "home")

    def test_a_list_page_links_as_a_syswiki_list(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = costume_hair(module)
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.assertTrue(self.model(window)["page_link"])
        self.assertEqual(self.linked(world, window),
                         ["|cff00c0fc|Hsyswiki:list:costumes:costume_hair|h[Costumes > Hair Styles]|h|r"])

    def test_the_home_page_links(self):
        world, window = self.opened()
        self.assertTrue(self.model(window)["page_link"])
        self.assertEqual(self.linked(world, window), ["|cff00c0fc|Hsyswiki:list:home|h[Wiki]|h|r"])

    def test_a_search_links_its_text_in_hex(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "wolf")
        (link,) = self.linked(world, window)
        self.assertTrue(link.startswith("|cff00c0fc|Hsyswiki:list:search:776f6c66|h["), link)
        self.assertTrue(SERVER_LIST_LINK.search(link))

    def test_a_long_search_is_cut_on_a_character_to_fit_the_cap(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        path = module.list_path(("search", "é" * 40))
        self.assertLessEqual(len(path), PATH_MAX)
        self.assertTrue(SERVER_LIST_LINK.fullmatch("|Hsyswiki:list:%s|h" % path))
        # 28 bytes of UTF-8 fit in the 57 characters after "search:": 14 of these.
        self.assertEqual(module.list_of_path(path), ("search", "é" * 14))

    def test_the_link_button_shows_on_every_page(self):
        with open(os.path.join(WIKI_DIR, "wiki.rml"), encoding="utf-8") as handle:
            rml = handle.read()
        button = re.search(r"<button id=\"wiki-link\"[^>]*>", rml).group(0)
        self.assertNotIn("data-if", button)

    def test_a_list_link_opens_that_list(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = costume_hair(module)
        with world.game, w4.quiet():
            self.assertTrue(window.OpenList("costumes:costume_hair"))
        model = self.model(window)
        self.assertFalse(model["home"])
        self.assertEqual(model["page_state"], "")
        self.assertEqual([c["label"] for c in model["crumbs"]], ["Home", "Costumes", "Hair Styles"])
        self.assertTrue(any(s["selected"] for s in model["tree"][cat]["subs"]))

    def test_a_search_link_opens_that_search(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            self.assertTrue(window.OpenList("search:776f6c66"))
        self.assertEqual([r["vnum"] for r in self.model(window)["list"]], [WOLF])
        self.assertEqual(w4.board(window).fields.get("wiki-search"), "wolf")

    def test_a_home_link_opens_the_home_page(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
            self.assertTrue(window.OpenList("home"))
        self.assertTrue(self.model(window)["home"])

    def test_an_unknown_path_opens_nothing(self):
        world, window = self.world()
        for path in ("nowhere:at_all", "costumes", "search:zz", "search:", "", "home:x"):
            with self.subTest(path=path):
                with world.game, w4.quiet():
                    self.assertFalse(window.OpenList(path))
                self.assertFalse(window.IsShow())

    def test_a_list_link_opens_through_the_chat_link_handler(self):
        called = []
        holder = types.SimpleNamespace(OpenWikiItem=lambda v: called.append(("item", v)),
                                       OpenWikiMob=lambda v: called.append(("mob", v)),
                                       OpenWikiList=lambda p: called.append(("list", p)),
                                       hyperlinkItemTooltip=None)
        method = qol.interface_method("MakeHyperlinkTooltip")
        opener = qol.interface_method("__OpenWikiLink")
        setattr(holder, "__OpenWikiLink", lambda kind, ident: opener(holder, kind, ident))
        method(holder, "syswiki:list:costumes:costume_hair")
        method(holder, "syswiki:list:home?y=12")
        method(holder, "syswiki:mob:%d" % WOLF)
        self.assertEqual(called, [("list", "costumes:costume_hair"), ("list", "home"), ("mob", WOLF)])

    def test_the_interface_opens_a_list_link_in_the_wiki(self):
        opened = []
        holder = types.SimpleNamespace(wndWiki=types.SimpleNamespace(OpenList=lambda p: opened.append(p) or True))
        self.assertTrue(qol.interface_method("OpenWikiList")(holder, "home"))
        self.assertEqual(opened, ["home"])
        holder.wndWiki = None
        self.assertFalse(qol.interface_method("OpenWikiList")(holder, "home"))


class UnknownKinds(R3Test):
    """NOVA-139's text pages (syswiki:page:<path>) are another agent's: the
    chat handler passes every kind it does not open itself to one hook,
    Interface.OpenWikiLink(kind, ident), which asks wndWiki.OpenLink."""

    def handler(self):
        called = []
        holder = types.SimpleNamespace(OpenWikiItem=lambda v: called.append(("item", v)),
                                       OpenWikiMob=lambda v: called.append(("mob", v)),
                                       OpenWikiList=lambda p: called.append(("list", p)),
                                       OpenWikiLink=lambda k, i: called.append(("hook", k, i)),
                                       OpenWikiPage=lambda p: called.append(("page", p)),
                                       hyperlinkItemTooltip=None)
        method = qol.interface_method("MakeHyperlinkTooltip")
        opener = qol.interface_method("__OpenWikiLink")
        setattr(holder, "__OpenWikiLink", lambda kind, ident: opener(holder, kind, ident))
        return method, holder, called

    def test_an_unknown_kind_reaches_the_hook_with_its_whole_path(self):
        method, holder, called = self.handler()
        method(holder, "syswiki:quiz:a:b?y=3")
        self.assertEqual(called, [("hook", "quiz", "a:b")])

    def test_a_page_link_opens_that_text_page(self):
        # NOVA-139 (feature/wiki-pages): wndWiki.OpenPage(path).
        method, holder, called = self.handler()
        method(holder, "syswiki:page:dungeons/demon_tower")
        method(holder, "syswiki:page:guides/a?y=3")
        self.assertEqual(called, [("page", "dungeons/demon_tower"), ("page", "guides/a")])

    def test_open_wiki_page_asks_the_wiki_and_brings_it_to_the_front(self):
        calls = []
        wiki = types.SimpleNamespace(OpenPage=lambda p: calls.append(("OpenPage", p)) or True,
                                     SetTop=lambda: calls.append(("SetTop",)))
        holder = types.SimpleNamespace(wndWiki=wiki)
        self.assertTrue(qol.interface_method("OpenWikiPage")(holder, "dungeons/demon_tower"))
        self.assertEqual(calls, [("OpenPage", "dungeons/demon_tower"), ("SetTop",)])

    def test_open_wiki_page_does_nothing_before_the_pages_branch(self):
        # OpenPage exists only once feature/wiki-pages is merged.
        holder = types.SimpleNamespace(wndWiki=types.SimpleNamespace(SetTop=lambda: None))
        self.assertFalse(qol.interface_method("OpenWikiPage")(holder, "a"))
        holder.wndWiki = None
        self.assertFalse(qol.interface_method("OpenWikiPage")(holder, "a"))
        world, window = self.world()
        holder.wndWiki = window
        with world.game, w4.quiet():
            self.assertFalse(qol.interface_method("OpenWikiPage")(holder, "a"))

    def test_the_hook_asks_the_wiki(self):
        asked = []
        holder = types.SimpleNamespace(wndWiki=types.SimpleNamespace(OpenLink=lambda k, i: asked.append((k, i)) or True))
        self.assertTrue(qol.interface_method("OpenWikiLink")(holder, "page", "x"))
        self.assertEqual(asked, [("page", "x")])
        holder.wndWiki = types.SimpleNamespace()
        self.assertFalse(qol.interface_method("OpenWikiLink")(holder, "page", "x"))
        holder.wndWiki = None
        self.assertFalse(qol.interface_method("OpenWikiLink")(holder, "page", "x"))

    def test_the_wiki_opens_its_own_kinds_and_refuses_others_quietly(self):
        world, window = self.world()
        with world.game, w4.quiet():
            self.assertTrue(window.OpenLink("list", "home"))
            self.assertTrue(window.OpenLink("mob", str(WOLF)))
            self.assertFalse(window.OpenLink("page", "dungeons/demon_tower"))
            self.assertFalse(window.OpenLink("item", "12a"))
        self.assertEqual(self.model(window)["page_vnum"], WOLF)


class CrumbMenu(R3Test):
    def at_page(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = costume_hair(module)
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.press(world, window, "row_press", 0, LEFT)
        self.assertEqual(len(self.model(window)["crumbs"]), 4)
        self.page = self.model(window)["page_vnum"]
        return world, window

    def test_a_right_press_on_a_crumb_offers_open_in_new_tab_and_link(self):
        world, window = self.at_page()
        for index in (0, 2, 3):
            with self.subTest(crumb=index):
                self.press(world, window, "crumb_press", index, RIGHT)
                self.assertEqual(self.menu(window), ["Open in new tab", "Link"])

    def test_the_category_label_has_no_menu(self):
        world, window = self.at_page()
        self.press(world, window, "crumb_press", 1, RIGHT)
        self.assertEqual(self.model(window)["menu"], [])

    def test_link_on_a_list_crumb_links_that_list(self):
        world, window = self.at_page()
        self.press(world, window, "crumb_press", 2, RIGHT)
        pasted = self.linked(world, window, "menu_press", 1)
        self.assertEqual(pasted, ["|cff00c0fc|Hsyswiki:list:costumes:costume_hair|h[Costumes > Hair Styles]|h|r"])
        self.assertEqual(self.model(window)["menu"], [])
        self.assertEqual(self.model(window)["page_vnum"], self.page, "the page stays")

    def test_link_on_the_page_crumb_links_the_page(self):
        world, window = self.at_page()
        self.press(world, window, "crumb_press", 3, RIGHT)
        pasted = self.linked(world, window, "menu_press", 1)
        self.assertEqual(pasted, ["|cff00c0fc|Hsyswiki:item:%d|h[Item %d]|h|r" % (self.page, self.page)])

    def test_open_in_new_tab_opens_that_place_behind_this_tab(self):
        world, window = self.at_page()
        self.press(world, window, "crumb_press", 2, RIGHT)
        self.press(world, window, "menu_press", 0, LEFT)
        tabs = self.model(window)["tabs"]
        self.assertEqual(len(tabs), 2)
        self.assertTrue(tabs[0]["active"])
        self.assertEqual(tabs[1]["label"], "Hair Styles")
        self.assertEqual(self.model(window)["page_vnum"], self.page)

    def test_a_right_press_still_navigates_nowhere(self):
        world, window = self.at_page()
        self.press(world, window, "crumb_press", 0, RIGHT)
        self.assertFalse(self.model(window)["home"])


class Fixtures(unittest.TestCase):
    def test_every_variant_has_the_main_fixtures_keys(self):
        with open(os.path.join(WIKI_DIR, "wiki.fixture.json"), encoding="utf-8") as handle:
            keys = set(json.load(handle)["wiki"])
        self.assertTrue({"menu", "menu_x", "menu_y"} <= keys)
        for variant in ("home", "long", "menu", "crumb-menu"):
            with self.subTest(variant=variant):
                with open(os.path.join(WIKI_DIR, "wiki.%s.fixture.json" % variant), encoding="utf-8") as handle:
                    self.assertEqual(set(json.load(handle)["wiki"]), keys)

    def test_the_menus_have_goldens_in_every_theme_and_classic_scale(self):
        folder = os.path.join(os.path.dirname(ASSETS), "docs", "ui", "snapshots")
        names = ["wiki-menu-%s-100" % t for t in ("dark", "light", "cyber", "classic")]
        names += ["wiki-menu-classic-150", "wiki-menu-classic-200"]
        names += ["wiki-crumb-menu-%s-100" % t for t in ("dark", "light", "cyber", "classic")]
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(os.path.isfile(os.path.join(folder, name + ".png")))

    def test_the_new_strings_are_in_every_locale(self):
        keys = ("WIKI_MENU_CLOSE", "WIKI_MENU_CLOSE_OTHERS", "WIKI_MENU_NEW_TAB")
        folder = os.path.join(ASSETS, "locale", "locale")
        locales = sorted(d for d in os.listdir(folder) if os.path.isfile(os.path.join(folder, d, "locale_game.txt")))
        self.assertEqual(len(locales), 17)
        for locale in locales:
            with open(os.path.join(folder, locale, "locale_game.txt"), "rb") as handle:
                data = handle.read()
            found = set(line.split(b"\t", 1)[0].decode("ascii", "replace") for line in data.split(b"\n"))
            with self.subTest(locale=locale):
                self.assertFalse(set(keys) - found)


if __name__ == "__main__":
    unittest.main()
