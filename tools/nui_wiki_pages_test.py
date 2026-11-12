"""The wiki's text pages in the window (NOVA-139): the pages' files and
categories, the model a page shows as (escaped text, links, error blocks),
links that open like the wiki's other links (a middle press or Ctrl opens a
new tab), the search over titles and text, the chat link, and the document's
markup and style rules for every block."""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_test as base  # noqa: E402

ASSETS = os.path.join(os.path.dirname(HERE), "assets")
ROOT = os.path.join(ASSETS, "root")
WIKI_DIR = os.path.join(ASSETS, "nui", "nui", "windows", "wiki")
LEFT, RIGHT, MIDDLE = 0, 1, 2
ITEM, MOB, PAGE = 0, 1, 2

TOWER = """---
title: Demon Tower
category: dungeons
decor: top-right = icon/item/30304.tga
---
# Demon Tower
Defeat the **Blue Death** and take the [[item:30304]] to [[mob:1093|the Reaper]].
Then read [[page:systems/sash]] or [[page:nowhere]].

- one @ui.WIKI_TITLE <b>bold</b>
"""
SASH = """---
title: Sashes
category: systems
---
A sash absorbs bonuses. See [[page:dungeons/demon_tower|the tower]].
"""
GUIDE = """---
title: The Basic Guide
category: guides
---
Press U for the extra inventory.
"""
GUIDE_DE = """---
title: Erste Schritte
category: guides
---
Druecke U.
"""
BROKEN = "no front matter at all\n"
INDEX = "# the wiki's pages\nguides/start\ndungeons/demon_tower\nsystems/sash\nbad/../path\nsystems/broken\n"


def files(extra=None):
    out = {
        "locale/en/wiki/index.txt": INDEX.encode(),
        "locale/en/wiki/guides/start.txt": GUIDE.encode(),
        "locale/de/wiki/guides/start.txt": GUIDE_DE.encode(),
        "locale/en/wiki/dungeons/demon_tower.txt": TOWER.encode(),
        "locale/en/wiki/systems/sash.txt": SASH.encode(),
        "locale/en/wiki/systems/broken.txt": BROKEN.encode(),
    }
    out.update(extra or {})
    return out


class PagesTest(base.WikiTest):
    LOCALE = "locale/en"

    def world(self, extra=None):
        world = w4.World(True, windows="+items,+wiki", setup=base.setup)
        locale = world.game.modules["localeInfo"]
        for key, text in (("WIKI_CAT_GUIDES", "Guides"), ("WIKI_CAT_DUNGEONS", "Dungeons"),
                          ("WIKI_CAT_SYSTEMS", "Systems"), ("WIKI_CAT_EVENTS", "Events"),
                          ("WIKI_HOME", "Home"), ("WIKI_SEARCH_TRAIL", "Search: %s")):
            setattr(locale, key, text)
        store = files(extra)
        with world.game, w4.quiet():
            world.game.load("nui_wiki_page_format", "nui_wiki_page_format.py")
            pages = world.game.load("nui_wiki_pages", "nui_wiki_pages.py")
            pages.READER = store.get
            pages.LOCALE = lambda: self.LOCALE
            pages.reset()
            world.game.load("nui_wiki_data", "nui_wiki_data.py")
            module = world.game.load("nui_wiki", "nui_wiki.py")
            module.ANSWERS.clear()
        world.game.state.field_events[("nui/windows/wiki/wiki.rml", "wiki-search")] = "search_change"
        with world.game, w4.quiet():
            window = world.nui_windows.make("wiki", type("Unused", (), {}), "nui_wiki.WikiWindow")
            window.Open()
        return world, window

    def model(self, window):
        return w4.board(window).model

    def press(self, world, window, event, *args):
        with world.game, w4.quiet():
            return w4.press(window, event, *args)

    def text_category(self, world, ident):
        module = world.m("nui_wiki")
        for i, category in enumerate(module.TREE):
            if category.get("category") == ident:
                return i
        self.fail("no category %s" % ident)

    def open_page(self, world, window, path):
        with world.game, w4.quiet():
            self.assertTrue(window.OpenPage(path))
            window.text_page_open()

    def runs(self, window, block=1):
        return self.model(window)["tp_blocks"][block]["runs"]

    def link_index(self, window, text):
        for run in self.runs(window):
            if run["t"] == text:
                return run["l"]
        self.fail("no run %r in %r" % (text, self.runs(window)))


class Tree(PagesTest):
    def test_the_text_categories_follow_the_browser_s_own_in_order(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        text = [c for c in module.TREE if c.get("category")]
        self.assertEqual([c["category"] for c in text], ["guides", "dungeons", "systems"])
        self.assertEqual([s["page"] for s in text[2]["subs"]], ["systems/sash"], "the broken page is not listed")
        self.assertEqual(module.TREE[0]["label"], "WIKI_CAT_EQUIPMENT", "the browser's categories stay first")

    def test_the_tree_shows_the_titles_in_the_player_s_language(self):
        self.LOCALE = "locale/de"
        world, window = self.world()
        cat = self.text_category(world, "guides")
        self.press(world, window, "tree_press", cat, LEFT)
        labels = [s["label"] for s in self.model(window)["tree"][cat]["subs"]]
        self.assertEqual(labels, ["Erste Schritte"])
        self.assertEqual(self.model(window)["tree"][cat]["label"], "Guides")

    def test_a_language_without_the_file_shows_the_english_one(self):
        self.LOCALE = "locale/de"
        world, window = self.world()
        self.open_page(world, window, "systems/sash")
        self.assertEqual(self.model(window)["tp_title"], "Sashes")

    def test_a_tree_row_opens_its_page_and_marks_itself(self):
        world, window = self.world()
        cat = self.text_category(world, "dungeons")
        self.press(world, window, "tree_press", cat, LEFT)
        self.press(world, window, "sub_press", cat, 0, LEFT)
        model = self.model(window)
        self.assertEqual((model["page_state"], model["page_kind"]), ("text", "text"))
        self.assertEqual(model["tp_title"], "Demon Tower")
        self.assertTrue(model["tree"][cat]["subs"][0]["selected"])
        self.assertEqual([c["label"] for c in model["crumbs"]], ["Home", "Dungeons", "Demon Tower"])
        self.assertEqual([r["name"] for r in model["list"]], ["Demon Tower"], "the category's pages")

    def test_the_category_crumb_lists_the_category_s_pages(self):
        world, window = self.world()
        self.open_page(world, window, "systems/sash")
        self.press(world, window, "crumb_press", 1, LEFT)
        model = self.model(window)
        self.assertEqual(model["page_state"], "")
        self.assertEqual([(r["name"], r["note"]) for r in model["list"]], [("Sashes", "Systems")])

    def test_the_home_page_has_chips_for_the_pages(self):
        world, window = self.world()
        cat = self.text_category(world, "guides")
        self.assertEqual([s["label"] for s in self.model(window)["quick"][cat]["subs"]], ["The Basic Guide"])


class Model(PagesTest):
    def test_text_reaches_the_model_as_escaped_text(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        blocks = self.model(window)["tp_blocks"]
        item = blocks[2]["items"][0]["runs"][0]["t"]
        self.assertEqual(item, "one @⁠ui.WIKI_TITLE <b>bold</b>")

    def test_links_show_names_and_titles(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        runs = self.runs(window)
        shown = [(r["t"], r["l"] >= 0, r["e"]) for r in runs if r["l"] >= 0 or r["e"]]
        self.assertEqual(shown, [("Item 30304", True, False), ("the Reaper", True, False), ("Sashes", True, False),
                                 ("[[page:nowhere]]", False, True)], "a missing page is an error run")

    def test_the_decor_and_the_blocks_reach_the_model(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        model = self.model(window)
        self.assertEqual(model["tp_decor"], [{"src": "/icon/item/30304.tga", "corner": "top-right"}])
        self.assertEqual([b["k"] for b in model["tp_blocks"]], ["h1", "p", "ul"])

    def test_a_broken_page_shows_an_error_block(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.OpenPage("systems/broken")
            window.text_page_open()
        model = self.model(window)
        self.assertEqual(model["page_state"], "text")
        self.assertEqual([b["k"] for b in model["tp_blocks"]], ["error"])

    def test_a_new_page_makes_its_viewport_again(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        self.assertEqual(len(self.model(window)["tp_view"]), 1)
        with world.game, w4.quiet():
            window.OpenPage("systems/sash")
        self.assertEqual(self.model(window)["tp_view"], [])
        self.assertGreater(self.model(window)["tp_open_at"], 0)
        with world.game, w4.quiet():
            w4.fire(window, "tp_open")
        self.assertEqual(len(self.model(window)["tp_view"]), 1)
        self.assertEqual(self.model(window)["tp_open_at"], 0.0)

    def test_a_text_page_after_a_loading_item_page_disarms_the_clocks(self):
        world, window = self.world()
        mark = world.mark()
        with world.game, w4.quiet():
            window.OpenItem(base.SWORD)
        self.assertGreater(self.model(window)["timeout_at"], 0)
        self.open_page(world, window, "systems/sash")
        model = self.model(window)
        self.assertEqual((model["timeout_at"], model["retry_at"]), (0.0, 0.0))
        with world.game, w4.quiet():
            window.timeout_fire()
            window.retry_fire()
        self.assertEqual(len(self.sent(world, mark)), 1, "only the item's request")

    def test_a_page_is_not_asked_of_the_server_and_shows_no_model(self):
        world, window = self.world()
        mark = world.mark()
        previews = world.game.modules["modelpreview"]
        del previews.calls[:]
        self.open_page(world, window, "systems/sash")
        self.assertEqual(self.sent(world, mark), [])
        self.assertFalse(self.model(window)["model_view"])
        self.assertNotIn("Select", [c[0] for c in previews.calls])

    def test_hovering_a_page_row_selects_no_model(self):
        world, window = self.world()
        previews = world.game.modules["modelpreview"]
        with world.game, w4.quiet():
            window.search("sash")
        self.assertEqual([r["name"] for r in self.model(window)["list"]], ["Sashes"])
        del previews.calls[:]
        self.press(world, window, "row_over", 0)
        self.assertNotIn("Select", [c[0] for c in previews.calls])
        self.assertFalse(self.model(window)["hover_view"])


class Links(PagesTest):
    def test_a_page_link_opens_the_page_in_this_tab(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        self.press(world, window, "tp_link", self.link_index(window, "Sashes"), LEFT)
        self.assertEqual(self.model(window)["tp_title"], "Sashes")
        self.assertTrue(self.model(window)["can_back"])
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(self.model(window)["tp_title"], "Demon Tower")

    def test_item_and_mob_links_open_their_pages(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        self.press(world, window, "tp_link", self.link_index(window, "the Reaper"), LEFT)
        self.assertEqual((self.model(window)["page_kind"], self.model(window)["page_vnum"]), ("mob", 1093))
        self.press(world, window, "back_press", LEFT)
        self.press(world, window, "tp_link", self.link_index(window, "Item 30304"), LEFT)
        self.assertEqual((self.model(window)["page_kind"], self.model(window)["page_vnum"]), ("item", 30304))

    def test_a_middle_press_opens_a_new_tab_behind(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        self.press(world, window, "tp_link", self.link_index(window, "the Reaper"), MIDDLE)
        model = self.model(window)
        self.assertEqual(len(model["tabs"]), 2)
        self.assertEqual(model["tp_title"], "Demon Tower", "the shown tab stays")
        self.assertEqual(model["tabs"][1]["label"], "Mob 1093")

    def test_ctrl_and_a_left_press_opens_a_new_tab(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        world.game.pressed.add(world.game.modules["app"].DIK_LCONTROL)
        runs = self.model(window)["tp_blocks"][1]["runs"]
        sash = [r["l"] for r in runs if r["t"] == "Sashes"][0]
        self.press(world, window, "tp_link", sash, LEFT)
        world.game.pressed.discard(world.game.modules["app"].DIK_LCONTROL)
        model = self.model(window)
        self.assertEqual([t["label"] for t in model["tabs"]], ["Demon Tower", "Sashes"])

    def test_a_right_press_and_a_bad_index_do_nothing(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        self.press(world, window, "tp_link", 0, RIGHT)
        self.press(world, window, "tp_link", -1, LEFT)
        self.press(world, window, "tp_link", 99, LEFT)
        self.assertEqual(self.model(window)["tp_title"], "Demon Tower")
        self.assertEqual(len(self.model(window)["tabs"]), 1)

    def test_open_page_refuses_bad_and_unknown_paths(self):
        world, window = self.world()
        with world.game, w4.quiet():
            self.assertTrue(window.OpenPage("systems/sash"))
            for path in ("../x", "/x", "Dungeons", "nowhere", "a" * 65, None):
                self.assertFalse(window.OpenPage(path), path)

    def test_the_link_button_builds_the_page_s_chat_link(self):
        world, window = self.world()
        pasted = []
        window.SetPasteLinkEvent(pasted.append)
        self.open_page(world, window, "dungeons/demon_tower")
        self.press(world, window, "link_press", LEFT)
        self.assertEqual(pasted, ["|cff00c0fc|Hsyswiki:page:dungeons/demon_tower|h[Demon Tower]|h|r"])

    def test_the_chat_link_s_path_rule(self):
        world, window = self.world()
        pages = world.m("nui_wiki_pages")
        self.assertEqual(pages.chat_link("a/b", "x|y", "ff00c0fc"), "|cff00c0fc|Hsyswiki:page:a/b|h[xy]|h|r")
        self.assertEqual(pages.chat_link("../a", "x", "ff00c0fc"), "")


class Search(PagesTest):
    def names(self, window):
        return [r["name"] for r in self.model(window)["list"]]

    def test_the_search_finds_titles_first_then_text(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.search("tower")
        self.assertEqual(self.names(window)[:2], ["Demon Tower", "Sashes"])

    def test_the_search_finds_words_of_the_text_and_keeps_items_and_mobs(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.search("blue death")
        self.assertEqual(self.names(window), ["Demon Tower"])
        with world.game, w4.quiet():
            window.search("sword")
        self.assertEqual(self.names(window), ["Item %d" % base.SWORD])

    def test_a_page_found_opens_from_the_list(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.search("absorbs")
        self.press(world, window, "row_press", 0, LEFT)
        model = self.model(window)
        self.assertEqual((model["page_state"], model["tp_title"]), ("text", "Sashes"))
        self.assertEqual(model["crumbs"][1]["label"], "Search: absorbs")


class Markup(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(*parts), encoding="utf-8") as handle:
            return handle.read()

    def test_the_document_binds_no_markup_and_follows_links(self):
        rml = self.read(WIKI_DIR, "wiki.rml")
        self.assertNotIn("data-rml", rml)
        self.assertIn('data-event-mousedown="tp_link(r.l, ev.button)"', rml)
        self.assertIn('href="wiki-pages.rcss"', rml)
        for kind in ("h1", "h2", "h3", "p", "ul", "ol", "table", "img", "hr", "note", "warn", "cols", "error"):
            with self.subTest(kind=kind):
                self.assertIn("'%s'" % kind, rml)

    def test_every_separator_style_has_a_rule_and_every_rule_a_style(self):
        sys.path.insert(0, ROOT)
        import nui_wiki_page_format as fmt
        rcss = self.read(WIKI_DIR, "wiki-pages.rcss")
        rules = set(re.findall(r"\.wp__hr--([a-z0-9-]+)", rcss))
        self.assertEqual(rules, set(fmt.SEPARATOR_STYLES))

    def test_the_sheet_uses_tokens_and_dp_only(self):
        rcss = self.read(WIKI_DIR, "wiki-pages.rcss")
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", rcss))
        self.assertIsNone(re.search(r"\d+px\b", rcss))


def client_pack(store):
    """The client's pack module as PythonPackModule.cpp has it: Exist for any
    file, Get only for .py, .pyc and .txt (it raises for anything else) and
    returns str."""
    import types
    pack = types.ModuleType("pack")
    pack.Exist = lambda path: 1 if path in store else 0

    def get(path):
        if os.path.splitext(path)[1].lower() not in (".py", ".pyc", ".txt") or path not in store:
            raise RuntimeError("pack.Get refuses %s" % path)
        return store[path].decode("utf-8")
    pack.Get = get
    return pack


class ClientPack(PagesTest):
    """r40: the shipped pages never showed. The tests above hand the module a
    reader of their own; these go through the client's pack rules."""

    def world_on_pack(self, store):
        world = w4.World(True, windows="+items,+wiki", setup=base.setup)
        world.game.modules["pack"] = client_pack(store)
        world.game.answer("app", "GetLocalePath", lambda: "locale/en")
        with world.game, w4.quiet():
            world.game.load("nui_wiki_page_format", "nui_wiki_page_format.py")
            pages = world.game.load("nui_wiki_pages", "nui_wiki_pages.py")
            pages.reset()
            world.game.load("nui_wiki_data", "nui_wiki_data.py")
            module = world.game.load("nui_wiki", "nui_wiki.py")
        return world, module, pages

    def shipped_store(self):
        """Every file under assets/locale/locale, by store path."""
        store = {}
        top = os.path.join(ASSETS, "locale")
        for folder, _, names in os.walk(os.path.join(top, "locale")):
            if os.sep + "wiki" not in folder:
                continue
            for name in names:
                full = os.path.join(folder, name)
                with open(full, "rb") as handle:
                    store[os.path.relpath(full, top).replace(os.sep, "/")] = handle.read()
        return store

    def test_the_shipped_pages_reach_the_tree_through_the_client_s_pack(self):
        world, module, pages = self.world_on_pack(self.shipped_store())
        categories = [c["category"] for c in module.TREE if c.get("category")]
        self.assertEqual(categories, ["guides", "dungeons", "systems", "events"])
        with world.game, w4.quiet():
            self.assertEqual(pages.title("dungeons/demon_tower"), "Demon Tower")

    def test_every_shipped_page_has_an_extension_pack_get_reads(self):
        for path in self.shipped_store():
            with self.subTest(path=path):
                self.assertIn(os.path.splitext(path)[1], (".txt",))


class Shipped(unittest.TestCase):
    def test_the_new_strings_are_in_every_locale(self):
        keys = ("WIKI_CAT_GUIDES", "WIKI_CAT_DUNGEONS", "WIKI_CAT_SYSTEMS", "WIKI_CAT_EVENTS", "WIKI_NOTE",
                "WIKI_WARNING", "WIKI_PAGE_ERROR")
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
                self.assertNotIn(b"\r\n", data)

    def test_the_golden_fixtures_have_the_main_fixture_s_keys(self):
        import json
        with open(os.path.join(WIKI_DIR, "wiki.fixture.json"), encoding="utf-8") as handle:
            keys = set(json.load(handle)["wiki"])
        for variant in ("page", "page-end", "landing", "home", "long"):
            with self.subTest(variant=variant):
                with open(os.path.join(WIKI_DIR, "wiki.%s.fixture.json" % variant), encoding="utf-8") as handle:
                    self.assertEqual(set(json.load(handle)["wiki"]), keys)

    def test_the_shipped_pages_have_no_problems(self):
        import subprocess
        result = subprocess.run([sys.executable, "-B", os.path.join(HERE, "nui_wiki_pages_tool.py"), "check"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("problems: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
