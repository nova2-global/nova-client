"""The ingame wiki's usability round (NOVA-42, after Eddy's live test on r38):
lists and the tree that scroll inside the window, a search field that takes
the caret, back and forward, a home page with quick links and the recently
viewed pages, a title trail, browser tabs (a middle press or a Ctrl press
opens a link in a new tab, a close button per tab, at most TABS_MAX), and a
Link button that puts the page's syswiki link into the chat input or the
whisper that has the focus."""

import ast
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_test as base  # noqa: E402

ASSETS = os.path.join(os.path.dirname(HERE), "assets")
ROOT = os.path.join(ASSETS, "root")
WIKI_DIR = os.path.join(ASSETS, "nui", "nui", "windows", "wiki")
NUITOOL = os.environ.get("NUITOOL", "")

ITEM, MOB = base.ITEM, base.MOB
SWORD, CHEST = base.SWORD, base.CHEST
WOLF = 8002
LEFT, RIGHT, MIDDLE = 0, 1, 2


def weapons(module):
    return [(0, j) for j, s in enumerate(module.TREE[0]["subs"]) if s["item_type"] == "ITEM_TYPE_WEAPON"][0]


class QolTest(base.WikiTest):
    def opened(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
        return world, window

    def model(self, window):
        return w4.board(window).model

    def press(self, world, window, event, *args):
        with world.game, w4.quiet():
            return w4.press(window, event, *args)

    def ctrl(self, world, down=True):
        app = world.game.modules["app"]
        if down:
            world.game.pressed.add(app.DIK_LCONTROL)
        else:
            world.game.pressed.discard(app.DIK_LCONTROL)


class SearchField(QolTest):
    def rule(self, selector):
        with open(os.path.join(WIKI_DIR, "wiki.rcss"), encoding="utf-8") as handle:
            text = handle.read()
        match = re.search(r"(^|\n)\s*%s\s*\{([^}]*)\}" % re.escape(selector), text)
        return match.group(2) if match else ""

    def test_the_search_field_can_take_the_focus_the_body_refuses(self):
        # RmlUi's focus is inherited (StyleSheetSpecification.cpp:376), and the
        # body takes none so that a press on the window keeps another field's
        # caret: the field must ask for its own.
        self.assertIn("focus: none", self.rule("body.wiki"))
        self.assertIn("focus: auto", self.rule(".wiki__search"))

    def test_a_press_on_the_search_field_gives_it_the_caret(self):
        world, window = self.opened()
        self.press(world, window, "search_press", LEFT)
        self.assertEqual(w4.board(window).focused, "wiki-search")

    def test_the_field_text_never_enters_the_model(self):
        with open(os.path.join(WIKI_DIR, "wiki.rml"), encoding="utf-8") as handle:
            rml = handle.read()
        field = re.search(r"<input[^>]*id=\"wiki-search\"[^>]*>", rml).group(0)
        self.assertNotIn("data-attr-value", field)
        world, window = self.opened()
        self.assertNotIn("search", self.model(window))

    def test_typing_lists_the_matches_and_a_category_clears_the_field(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "wolf")
        self.assertEqual([r["vnum"] for r in self.model(window)["list"]], [WOLF])
        cat, sub = weapons(module)
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.assertEqual(w4.board(window).fields.get("wiki-search"), "")
        self.assertEqual([r["vnum"] for r in self.model(window)["list"]], [SWORD])


class Navigation(QolTest):
    def test_back_and_forward_walk_the_tabs_history(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = weapons(module)
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.press(world, window, "row_press", 0, LEFT)
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        self.assertEqual(self.model(window)["page_vnum"], WOLF)
        self.assertTrue(self.model(window)["can_back"])
        self.assertFalse(self.model(window)["can_forward"])
        self.press(world, window, "back_press", LEFT)
        self.assertEqual((self.model(window)["page_kind"], self.model(window)["page_vnum"]), ("item", SWORD))
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(self.model(window)["page_state"], "")
        self.assertEqual([r["vnum"] for r in self.model(window)["list"]], [SWORD], "the list stays")
        self.assertTrue(self.model(window)["can_forward"])
        self.press(world, window, "forward_press", LEFT)
        self.assertEqual(self.model(window)["page_vnum"], SWORD)

    def test_a_new_page_after_back_drops_the_forward_pages(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
            window.OpenMob(WOLF)
        self.press(world, window, "back_press", LEFT)
        with world.game, w4.quiet():
            window.OpenItem(CHEST)
        self.assertFalse(self.model(window)["can_forward"])
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(self.model(window)["page_vnum"], SWORD)

    def test_back_to_a_search_puts_its_text_back_in_the_field(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "wolf")
        self.press(world, window, "row_press", 0, LEFT)
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.press(world, window, "back_press", LEFT)
        self.press(world, window, "home_press", LEFT)
        self.assertEqual(w4.board(window).fields.get("wiki-search"), "")
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(w4.board(window).fields.get("wiki-search"), "wolf")
        self.assertEqual([r["vnum"] for r in self.model(window)["list"]], [WOLF])
        self.assertEqual(self.model(window)["page_vnum"], WOLF)

    def test_enter_in_the_search_field_opens_the_first_match(self):
        world, window = self.opened()
        board = w4.board(window)
        with world.game, w4.quiet():
            board.insert_text("wiki-search", "wolf")
            board.insert_text("wiki-search", "\n")
        self.assertEqual((self.model(window)["page_kind"], self.model(window)["page_vnum"]), ("mob", WOLF))
        self.assertEqual(self.model(window)["list_sel"], 0)

    def test_enter_with_no_match_opens_nothing(self):
        world, window = self.opened()
        board = w4.board(window)
        with world.game, w4.quiet():
            board.insert_text("wiki-search", "xyzzy")
            board.insert_text("wiki-search", "\n")
        self.assertEqual(self.model(window)["page_state"], "")

    def test_typing_a_search_is_one_step_of_history(self):
        world, window = self.opened()
        board = w4.board(window)
        with world.game, w4.quiet():
            for letter in "wolf":
                board.insert_text("wiki-search", letter)
        self.press(world, window, "back_press", LEFT)
        self.assertTrue(self.model(window)["home"])

    def test_home_shows_the_categories_and_the_pages_seen_last(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        self.assertTrue(self.model(window)["home"], "the wiki opens on its home page")
        quick = self.model(window)["quick"]
        self.assertEqual([c["cat"] for c in quick], list(range(len(module.TREE))))
        self.assertEqual(quick[0]["subs"][0]["label"], "Weapons")
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
            window.OpenMob(WOLF)
            window.OpenItem(SWORD)
        self.press(world, window, "home_press", LEFT)
        self.assertTrue(self.model(window)["home"])
        recent = self.model(window)["recent"]
        self.assertEqual([(r["mob"], r["vnum"]) for r in recent], [(False, SWORD), (True, WOLF)])
        self.press(world, window, "recent_press", 1, LEFT)
        self.assertFalse(self.model(window)["home"])
        self.assertEqual(self.model(window)["page_vnum"], WOLF)

    def test_the_recent_pages_are_capped(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            for vnum in range(1, module.RECENT_MAX + 5):
                window.OpenMob(vnum)
        self.press(world, window, "home_press", LEFT)
        self.assertEqual(len(self.model(window)["recent"]), module.RECENT_MAX)
        self.assertEqual(self.model(window)["recent"][0]["vnum"], module.RECENT_MAX + 4)

    def test_a_quick_link_opens_its_list(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = weapons(module)
        self.press(world, window, "quick_press", cat, sub, LEFT)
        self.assertFalse(self.model(window)["home"])
        self.assertEqual([r["vnum"] for r in self.model(window)["list"]], [SWORD])

    def test_the_trail_names_where_the_page_is_and_goes_back_up(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = weapons(module)
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.press(world, window, "row_press", 0, LEFT)
        crumbs = self.model(window)["crumbs"]
        self.assertEqual([c["label"] for c in crumbs],
                         ["Home", "Equipment", "Weapons", "Item %d" % SWORD])
        self.assertEqual([c["last"] for c in crumbs], [False, False, False, True])
        self.press(world, window, "crumb_press", 2, LEFT)
        self.assertEqual(self.model(window)["page_state"], "")
        self.assertEqual([r["vnum"] for r in self.model(window)["list"]], [SWORD])
        self.press(world, window, "crumb_press", 0, LEFT)
        self.assertTrue(self.model(window)["home"])

    def test_a_search_trail_names_the_search(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "wolf")
        labels = [c["label"] for c in self.model(window)["crumbs"]]
        self.assertEqual(labels[0], "Home")
        self.assertIn("wolf", labels[1])

    def test_the_tree_marks_the_open_list_and_unfolds_its_category(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = weapons(module)
        self.press(world, window, "quick_press", cat, sub, LEFT)
        tree = self.model(window)["tree"]
        self.assertTrue(tree[cat]["open"])
        self.assertEqual([s["selected"] for s in tree[cat]["subs"]][sub], True)
        self.assertEqual(sum(s["selected"] for c in tree for s in c["subs"]), 1)

    def test_the_shown_page_is_marked_in_the_list(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "sword")
        self.assertEqual(self.model(window)["list_sel"], -1)
        self.press(world, window, "row_press", 0, LEFT)
        self.assertEqual(self.model(window)["list_sel"], 0)

    def test_the_list_says_what_it_lists(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = weapons(module)
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.assertEqual(self.model(window)["list_title"], "Weapons")
        self.assertEqual(self.model(window)["list_count"], "1")

    def test_a_right_press_navigates_nowhere(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = weapons(module)
        self.press(world, window, "quick_press", cat, sub, RIGHT)
        self.assertTrue(self.model(window)["home"])


class Hover(QolTest):
    """The FPS drop on hover (coordinator, from the FPS investigation): RmlUi
    6.3 bubbles mouseover, so entering a row onto its icon fired row_over up
    to three times, each a Select and a SetParts."""

    def hovered(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "wolf")
        calls = world.game.modules["modelpreview"].calls
        del calls[:]
        del w4.board(window).calls[:]
        return world, window, calls

    def hover_sets(self, window):
        return [c for c in w4.board(window).calls if c[0] == "set" and "hover_view" in c[1]]

    def test_the_same_row_again_selects_nothing(self):
        world, window, calls = self.hovered()
        with world.game, w4.quiet():
            window.over_row(0)
            window.over_row(0)
            window.over_row(0)
        self.assertEqual([c for c in calls if c[0] == "Select"], [("Select", "wiki_hover", WOLF)])
        self.assertTrue(self.model(window)["hover_view"])

    def test_hover_view_is_set_only_when_it_changes(self):
        world, window, calls = self.hovered()
        with world.game, w4.quiet():
            window.over_row(0)
            window.over_row(0)
            window.out_row()
            window.out_row()
        self.assertEqual([c[1]["hover_view"] for c in self.hover_sets(window)], [True, False])

    def test_a_row_entered_again_after_leaving_shows_again(self):
        world, window, calls = self.hovered()
        with world.game, w4.quiet():
            window.over_row(0)
            window.out_row()
            window.over_row(0)
        self.assertTrue(self.model(window)["hover_view"])
        self.assertEqual(len([c for c in calls if c[0] == "Select"]), 2)

    def test_a_rows_children_take_no_pointer(self):
        with open(os.path.join(WIKI_DIR, "wiki.rcss"), encoding="utf-8") as handle:
            text = handle.read()
        match = re.search(r"\.wiki__row > \*, \.wiki__loot > \*, \.wiki__mat > \*\s*\{([^}]*)\}", text)
        self.assertIsNotNone(match)
        self.assertIn("pointer-events: none", match.group(1))


class Tabs(QolTest):
    def tabs(self, window):
        return self.model(window)["tabs"]

    def test_the_wiki_opens_with_one_home_tab(self):
        world, window = self.opened()
        self.assertEqual([(t["label"], t["active"]) for t in self.tabs(window)], [("Home", True)])

    def test_a_middle_press_opens_a_row_in_a_new_tab_behind_this_one(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "wolf")
        mark = world.mark()
        self.press(world, window, "row_press", 0, MIDDLE)
        self.assertEqual(len(self.tabs(window)), 2)
        self.assertTrue(self.tabs(window)[0]["active"])
        self.assertEqual(self.tabs(window)[1]["label"], "Mob %d" % WOLF)
        self.assertEqual(self.model(window)["page_state"], "", "this tab keeps its page")
        self.assertEqual(self.sent(world, mark), [], "a tab behind asks for nothing yet")

    def test_a_ctrl_press_opens_in_a_new_tab(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        cat, sub = weapons(module)
        self.ctrl(world)
        self.press(world, window, "quick_press", cat, sub, LEFT)
        self.assertEqual(len(self.tabs(window)), 2)
        self.assertTrue(self.model(window)["home"])
        self.assertEqual(self.tabs(window)[1]["label"], "Weapons")

    def test_middle_and_ctrl_reach_every_link(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.answer(world, window, ITEM, base.OK, SWORD, origins=((0, WOLF),), chest=((27001, 2),))
        self.press(world, window, "origin_press", 0, MIDDLE)
        self.press(world, window, "loot_press", 0, 27001, MIDDLE)
        self.press(world, window, "home_press", MIDDLE)
        self.assertEqual([t["label"] for t in self.tabs(window)][1:], ["Mob %d" % WOLF, "Item 27001", "Home"])
        self.assertEqual(self.model(window)["page_vnum"], SWORD)

    def test_a_tab_keeps_its_own_page_and_history(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.press(world, window, "new_tab_press", LEFT)
        self.assertTrue(self.tabs(window)[1]["active"])
        self.assertTrue(self.model(window)["home"])
        self.assertFalse(self.model(window)["can_back"])
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        calls = world.game.modules["modelpreview"].calls
        del calls[:]
        self.press(world, window, "tab_press", 0, LEFT)
        self.assertEqual(self.model(window)["page_vnum"], SWORD)
        self.assertTrue(self.model(window)["can_back"])
        self.assertIn(("Select", "wiki", 0), calls, "the page's preview follows the tab")
        self.press(world, window, "tab_press", 1, LEFT)
        self.assertEqual(self.model(window)["page_vnum"], WOLF)

    def test_a_background_tab_asks_for_its_page_when_shown(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "wolf")
        self.press(world, window, "row_press", 0, MIDDLE)
        mark = world.mark()
        self.press(world, window, "tab_press", 1, LEFT)
        self.assertEqual(self.sent(world, mark), [(MOB, WOLF)])
        self.assertEqual(self.model(window)["page_state"], "loading")

    def test_the_close_button_closes_a_tab_and_the_next_one_shows(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.press(world, window, "new_tab_press", LEFT)
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        self.press(world, window, "tab_close_press", 1, LEFT)
        self.assertEqual(len(self.tabs(window)), 1)
        self.assertEqual(self.model(window)["page_vnum"], SWORD)

    def test_closing_the_last_tab_leaves_a_home_tab(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.press(world, window, "tab_close_press", 0, LEFT)
        self.assertEqual([t["label"] for t in self.tabs(window)], ["Home"])
        self.assertTrue(self.model(window)["home"])
        self.assertFalse(self.model(window)["can_back"])

    def test_a_middle_press_on_a_tab_closes_it(self):
        world, window = self.opened()
        self.press(world, window, "new_tab_press", LEFT)
        self.press(world, window, "tab_press", 0, MIDDLE)
        self.assertEqual(len(self.tabs(window)), 1)
        self.assertTrue(self.tabs(window)[0]["active"])

    def test_tabs_are_capped(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        for _ in range(module.TABS_MAX - 1):
            self.press(world, window, "new_tab_press", LEFT)
        self.assertTrue(self.model(window)["tabs_full"])
        mark = world.mark()
        self.press(world, window, "new_tab_press", LEFT)
        self.press(world, window, "home_press", MIDDLE)
        self.assertEqual(len(self.tabs(window)), module.TABS_MAX)
        said = [args for name, args in world.calls_since(mark, "chat.") if name == "chat.AppendChat"]
        self.assertEqual(len(said), 2)
        self.press(world, window, "tab_close_press", 3, LEFT)
        self.assertFalse(self.model(window)["tabs_full"])

    def test_a_long_label_is_shortened(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        world.game.answer("nonplayer", "GetMonsterName", lambda v: "A Very Long Monster Name Indeed")
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        label = self.tabs(window)[0]["label"]
        self.assertLessEqual(len(label), module.TAB_LABEL_MAX)
        self.assertTrue(label.endswith("..."))

    def test_tabs_and_pages_survive_a_close_and_reopen(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
            w4.board(window).insert_text("wiki-search", "wolf")
        self.press(world, window, "new_tab_press", LEFT)
        with world.game, w4.quiet():
            window.Close()
            window.Open()
        self.assertEqual(len(self.tabs(window)), 2)
        self.press(world, window, "tab_press", 0, LEFT)
        self.assertEqual(w4.board(window).fields.get("wiki-search"), "wolf")


class Link(QolTest):
    def linked(self, world, window):
        pasted = []
        with world.game, w4.quiet():
            window.SetPasteLinkEvent(pasted.append)
        self.press(world, window, "link_press", LEFT)
        return pasted

    def test_an_item_page_links_as_a_syswiki_item(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.assertTrue(self.model(window)["page_link"])
        self.assertEqual(self.linked(world, window), ["|cff00c0fc|Hsyswiki:item:%d|h[Item %d]|h|r" % (SWORD, SWORD)])

    def test_a_mob_page_links_as_a_syswiki_mob(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        self.assertEqual(self.linked(world, window), ["|cff00c0fc|Hsyswiki:mob:%d|h[Mob %d]|h|r" % (WOLF, WOLF)])

    def test_a_name_cannot_break_the_link(self):
        world, window = self.opened()
        world.game.answer("nonplayer", "GetMonsterName", lambda v: "Bad|h]|Hname")
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        (link,) = self.linked(world, window)
        self.assertEqual(link.count("|"), 5)
        self.assertTrue(link.startswith("|cff00c0fc|Hsyswiki:mob:%d|h[" % WOLF))

    def test_home_links_too(self):
        # Round 3 (Eddy's r39 notes): every page links; the home page as
        # syswiki:list:home (nui_wiki_r3_test.ListLinks).
        world, window = self.opened()
        self.assertTrue(self.model(window)["page_link"])
        self.assertEqual(self.linked(world, window), ["|cff00c0fc|Hsyswiki:list:home|h[Wiki]|h|r"])

    def test_the_link_leaves_the_search_field_first(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            window.OpenItem(SWORD)
        self.press(world, window, "search_press", LEFT)
        self.linked(world, window)
        self.assertEqual(w4.board(window).focused, module.PARK)

    def test_the_link_opens_its_page_through_the_chat_link_handler(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        (link,) = self.linked(world, window)
        hyperlink = re.search(r"\|H(.*?)\|h", link).group(1)
        called = []
        holder = types.SimpleNamespace(OpenWikiItem=lambda v: called.append(("item", v)),
                                       OpenWikiMob=lambda v: called.append(("mob", v)),
                                       hyperlinkItemTooltip=None)
        method = interface_method("MakeHyperlinkTooltip")
        scope = method.__globals__
        opener = interface_method("__OpenWikiLink")
        # Compiled outside the class, self.__OpenWikiLink is not mangled.
        setattr(holder, "__OpenWikiLink", lambda kind, ident: opener(holder, kind, ident))
        method(holder, hyperlink)
        self.assertEqual(called, [("mob", WOLF)])

    def test_the_unavailable_window_takes_the_link_event(self):
        import importlib.util as util
        spec = util.spec_from_file_location("uiwiki", os.path.join(ROOT, "uiwiki.py"))
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.UnavailableWindow().SetPasteLinkEvent(lambda link: None)


def interface_method(name):
    source = open(os.path.join(ROOT, "interfacemodule.py"), encoding="utf-8").read()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Interface")
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "interfacemodule.py", "exec"), scope)
    return scope[name]


class _Line(object):
    def __init__(self, focused=False):
        self.focused = focused

    def IsFocus(self):
        return self.focused

    def SetFocus(self):
        self.focused = True


class _Whisper(object):
    def __init__(self, focused=False, shown=True, proxy=None):
        self.chatLine = _Line(focused)
        self.shown = shown
        if proxy is not None:
            self.focusProxy = types.SimpleNamespace(has_focus=lambda: proxy)

    def IsShow(self):
        return self.shown


class _Chat(object):
    def __init__(self, open_=False):
        self.open = open_
        self.calls = []

    def IsEditMode(self):
        return self.open

    def OpenChat(self):
        self.calls.append("OpenChat")
        self.open = True

    def SetChatFocus(self):
        self.calls.append("SetChatFocus")


class PasteWikiLink(unittest.TestCase):
    """Interface.PasteWikiLink: the wiki's Link button."""

    def paste(self, whispers, chat, web_shown=False):
        pasted = []
        ime = types.ModuleType("ime")
        ime.PasteString = lambda text: pasted.append((text, [w.chatLine.focused for w in whispers], chat.open))
        saved = sys.modules.get("ime")
        sys.modules["ime"] = ime
        try:
            holder = types.SimpleNamespace(
                whisperDialogDict=dict(("w%d" % i, w) for i, w in enumerate(whispers)), wndChat=chat,
                wndWeb=types.SimpleNamespace(IsShow=lambda: web_shown))
            holder.ToggleChat = lambda: interface_method("ToggleChat")(holder)
            holder.SetChatFocus = lambda: interface_method("SetChatFocus")(holder)
            result = interface_method("PasteWikiLink")(holder, "LINK")
        finally:
            if saved is None:
                sys.modules.pop("ime", None)
            else:
                sys.modules["ime"] = saved
        return result, pasted

    def test_a_focused_legacy_whisper_gets_the_link(self):
        whispers = [_Whisper(), _Whisper(focused=True)]
        chat = _Chat()
        result, pasted = self.paste(whispers, chat)
        self.assertTrue(result)
        self.assertEqual(pasted, [("LINK", [False, True], False)])
        self.assertEqual(chat.calls, [])

    def test_a_novaui_whisper_answers_by_its_focus_proxy(self):
        whispers = [_Whisper(focused=True, proxy=False), _Whisper(proxy=True)]
        chat = _Chat()
        result, pasted = self.paste(whispers, chat)
        self.assertEqual(pasted, [("LINK", [True, True], False)], "the second one's field takes the focus first")

    def test_a_hidden_whisper_is_passed_over(self):
        whispers = [_Whisper(focused=True, shown=False)]
        chat = _Chat()
        result, pasted = self.paste(whispers, chat)
        self.assertEqual(chat.calls, ["OpenChat"])
        self.assertEqual(pasted, [("LINK", [True], True)])

    def test_with_no_whisper_the_chat_opens_for_the_link(self):
        chat = _Chat()
        result, pasted = self.paste([], chat)
        self.assertTrue(result)
        self.assertEqual(chat.calls, ["OpenChat"])
        self.assertEqual(pasted, [("LINK", [], True)])

    def test_an_open_chat_keeps_its_text_and_takes_the_focus(self):
        chat = _Chat(open_=True)
        result, pasted = self.paste([], chat)
        self.assertEqual(chat.calls, ["SetChatFocus"])
        self.assertEqual(len(pasted), 1)

    def test_a_chat_that_cannot_open_takes_nothing(self):
        chat = _Chat()
        result, pasted = self.paste([], chat, web_shown=True)
        self.assertFalse(result)
        self.assertEqual(pasted, [])

    def test_the_interface_gives_the_wiki_its_link_event(self):
        source = open(os.path.join(ROOT, "interfacemodule.py"), encoding="utf-8").read()
        self.assertRegex(source, r"wndWiki\.SetPasteLinkEvent\(ui\.__mem_func__\(self\.PasteWikiLink\)\)")


def _long_fixture():
    """The golden fixture with a long list, every category unfolded with its
    subs, a long page and eight tabs: what overflowed the window on r38."""
    with open(os.path.join(WIKI_DIR, "wiki.fixture.json"), encoding="utf-8") as handle:
        fixture = json.load(handle)
    model = fixture["wiki"]
    row = model["list"][0]
    model["list"] = [dict(row, i=i, name="Weapon %d" % i) for i in range(80)]
    model["tree"] = [{"cat": c, "label": "Category %d" % c, "open": True,
                      "subs": [{"cat": c, "sub": s, "label": "Sub %d" % s, "selected": False} for s in range(10)]}
                     for c in range(7)]
    loot = model["chest"][0]
    model["chest"] = [dict(loot, i=i) for i in range(40)]
    return fixture


@unittest.skipUnless(NUITOOL and os.path.isfile(NUITOOL), "NUITOOL is not set")
class Layout(unittest.TestCase):
    """Eddy's notes 1 and 2: a long list and an unfolded tree ran out of the
    window with no scroll. Every scrolling viewport stays inside the window."""

    VIEWPORTS = ("wiki-tree", "wiki-rows", "wiki-page")

    def boxes(self, theme, fixture):
        work = tempfile.mkdtemp(prefix="wiki-qol-")
        fixture_path = os.path.join(work, "fixture.json")
        with open(fixture_path, "w", encoding="utf-8") as handle:
            json.dump(fixture, handle)
        boxes_path = os.path.join(work, "boxes.json")
        subprocess.run([NUITOOL, "snap", "--root", os.path.join(ASSETS, "nui"), "--root", os.path.join(ASSETS, "ETC"),
                        "--root", os.path.join(ASSETS, "icon"),
                        "--locale", os.path.join(ASSETS, "locale", "locale", "en"),
                        "--doc", "nui/windows/wiki/wiki.rml", "--fixture", fixture_path,
                        "--theme", theme, "--scale", "1", "--size", "1000x800",
                        "--out", os.path.join(work, "frame.png"), "--boxes", boxes_path],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(boxes_path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_the_lists_and_the_tree_scroll_inside_the_window(self):
        for theme in ("modern-dark", "classic", "cyberpunk"):
            boxes = self.boxes(theme, _long_fixture())
            x, y, w, h = boxes[""]
            for name in self.VIEWPORTS:
                with self.subTest(theme=theme, viewport=name):
                    self.assertIn(name, boxes)
                    bx, by, bw, bh = boxes[name]
                    self.assertGreater(bh, 100)
                    self.assertLessEqual(by + bh, y + h + 0.5)
                    self.assertLessEqual(bx + bw, x + w + 0.5)
            with self.subTest(theme=theme, what="the window's height"):
                self.assertLess(h, 700)

    def test_the_home_page_scrolls_inside_the_window(self):
        fixture = _long_fixture()
        model = fixture["wiki"]
        model["home"] = True
        model["page_state"] = ""
        model["quick"] = [{"cat": c, "label": "Category %d" % c,
                           "subs": [{"cat": c, "sub": s, "label": "Sub %d" % s} for s in range(10)]} for c in range(7)]
        model["recent"] = [{"i": i, "vnum": 19, "mob": False, "icon": "", "name": "Page %d" % i, "note": ""}
                           for i in range(10)]
        for theme in ("modern-dark", "classic"):
            boxes = self.boxes(theme, fixture)
            x, y, w, h = boxes[""]
            with self.subTest(theme=theme):
                self.assertIn("wiki-home", boxes)
                bx, by, bw, bh = boxes["wiki-home"]
                self.assertLessEqual(by + bh, y + h + 0.5)


class Fixtures(unittest.TestCase):
    def test_every_variant_has_the_main_fixtures_keys(self):
        with open(os.path.join(WIKI_DIR, "wiki.fixture.json"), encoding="utf-8") as handle:
            keys = set(json.load(handle)["wiki"])
        for variant in ("home", "long"):
            with self.subTest(variant=variant):
                with open(os.path.join(WIKI_DIR, "wiki.%s.fixture.json" % variant), encoding="utf-8") as handle:
                    self.assertEqual(set(json.load(handle)["wiki"]), keys)

    def test_the_new_strings_are_in_every_locale(self):
        keys = ("WIKI_HOME", "WIKI_RECENT", "WIKI_NO_RECENT", "WIKI_CATEGORIES", "WIKI_LINK", "WIKI_TABS_FULL",
                "WIKI_SEARCH_HINT", "WIKI_SEARCH_TRAIL", "WIKI_TAB_HINT")
        folder = os.path.join(ASSETS, "locale", "locale")
        locales = sorted(d for d in os.listdir(folder) if os.path.isfile(os.path.join(folder, d, "locale_game.txt")))
        self.assertEqual(len(locales), 17)
        for locale in locales:
            with open(os.path.join(folder, locale, "locale_game.txt"), "rb") as handle:
                data = handle.read()
            found = set(line.split(b"\t", 1)[0].decode("ascii", "replace") for line in data.split(b"\n"))
            with self.subTest(locale=locale):
                self.assertFalse(set(keys) - found)
                self.assertTrue(data.endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
