"""The wiki's fourth round (NOVA-42 and NOVA-139, after Eddy's live test on r41):

1. Equipment by class, as OLD's wiki had it (inGameWikiUI.py CLASS_BUTTONS,
   GameLib/ItemManager.cpp IsFilteredAntiflag): an item shows under a class
   when it lacks that class's anti-flag, so an item several classes use shows
   under each of them and an item any class uses under every one. The filter
   starts on the player's own class and is part of the list's place, so tabs,
   Back and Forward, list links and search keep it.
2. Items embedded in text pages with their icon and their tooltip, as OLD's
   [IMG=icon/item/N.tga; ITEM_TOOLTIP=N] did: ![[item:N]].
3. The model viewer: a press on a page's model preview opens it over the
   wiki's content area, where a drag turns it, the wheel zooms, a double
   click resets the view, and the close button, Escape or a press outside the
   model close it."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_test as base  # noqa: E402
import nui_wiki_pages_test as pages_test  # noqa: E402

ASSETS = os.path.join(os.path.dirname(HERE), "assets")
ROOT = os.path.join(ASSETS, "root")
WIKI_DIR = os.path.join(ASSETS, "nui", "nui", "windows", "wiki")
LOCALES = os.path.join(ASSETS, "locale", "locale")
SHIPPED = os.path.join(LOCALES, "en", "wiki")
LEFT, RIGHT, MIDDLE = 0, 1, 2
ITEM, MOB = 0, 1

sys.path.insert(0, ROOT)
import nui_wiki_page_format as fmt  # noqa: E402

# The stand-in's anti-flags (nui_wiki_test.setup): warrior 1, assassin 2,
# sura 4, shaman 8.
W, N, SU, SH = 1, 2, 4, 8
ONLY_WARRIOR, ONLY_NINJA, WARRIOR_AND_SURA, ANY_CLASS, ONLY_SHAMAN = 21000, 21010, 21020, 21030, 21040
ANTI = {
    ONLY_WARRIOR: N | SU | SH,
    ONLY_NINJA: W | SU | SH,
    WARRIOR_AND_SURA: N | SH,
    ANY_CLASS: 0,
    ONLY_SHAMAN: W | N | SU,
}
EVERY = [ONLY_WARRIOR, ONLY_NINJA, WARRIOR_AND_SURA, ANY_CLASS, ONLY_SHAMAN]


def equipment(module, label="WIKI_SUB_WEAPONS"):
    for j, sub in enumerate(module.TREE[0]["subs"]):
        if sub["label"] == label:
            return 0, j
    raise AssertionError("no %s" % label)


def category_of(module, label):
    for i, category in enumerate(module.TREE):
        for j, sub in enumerate(category["subs"]):
            if sub["label"] == label:
                return i, j
    raise AssertionError("no %s" % label)


class R4Test(base.WikiTest):
    RACE = 0

    def world(self):
        world, window = base.WikiTest.world(self)
        item = world.game.modules["item"]
        world.game.answer("item", "ListByType", lambda t, s: tuple(EVERY))
        world.game.answer("item", "IsAntiFlag", lambda flag: bool(ANTI.get(item.selected[0], 0) & flag))
        world.game.answer("player", "GetRace", lambda: self.RACE)
        locale = world.game.modules["localeInfo"]
        for key, text in (("TOOLTIP_WARRIOR", "Warrior"), ("TOOLTIP_ASSASSIN", "Ninja"), ("TOOLTIP_SURA", "Sura"),
                          ("TOOLTIP_SHAMAN", "Shaman"), ("WIKI_CLASS_ALL", "All"), ("WIKI_HOME", "Home"),
                          ("WIKI_TITLE", "Wiki"), ("WIKI_SEARCH_TRAIL", "Search: %s"),
                          ("WIKI_LIST_RANGE", "%d-%d / %d")):
            setattr(locale, key, text)
        return world, window

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

    def vnums(self, window):
        return [r["vnum"] for r in self.model(window)["list"]]

    def classes(self, window):
        return [(c["id"], c["on"]) for c in self.model(window)["classes"]]

    def chosen(self, window):
        return [c["id"] for c in self.model(window)["classes"] if c["on"]]

    def class_index(self, window, ident):
        for c in self.model(window)["classes"]:
            if c["id"] == ident:
                return c["i"]
        self.fail("no class %s in %r" % (ident, self.model(window)["classes"]))

    def weapons(self, world, window, button=LEFT):
        cat, sub = equipment(world.m("nui_wiki"))
        self.press(world, window, "sub_press", cat, sub, button)


# --- 1. equipment by class ---------------------------------------------------------------

class ClassFilter(R4Test):
    def test_none_of_the_stand_ins_vnums_is_blacklisted(self):
        world, window = self.world()
        data = world.m("nui_wiki_data")
        self.assertFalse(set(EVERY) & set(data.ITEM_BLACKLIST))

    def test_an_equipment_list_offers_the_classes_as_old_did(self):
        world, window = self.opened()
        self.weapons(world, window)
        # OLD's buttons, in OLD's order (warrior, ninja, shaman, sura), and All.
        self.assertEqual([c[0] for c in self.classes(window)], ["warrior", "ninja", "shaman", "sura", "all"])
        self.assertEqual([c["label"] for c in self.model(window)["classes"]],
                         ["Warrior", "Ninja", "Shaman", "Sura", "All"])

    def test_the_filter_starts_on_the_player_s_own_class(self):
        for race, ident in ((0, "warrior"), (4, "warrior"), (1, "ninja"), (5, "ninja"), (2, "sura"), (6, "sura"),
                            (3, "shaman"), (7, "shaman")):
            with self.subTest(race=race):
                self.RACE = race
                world, window = self.opened()
                self.weapons(world, window)
                self.assertEqual(self.chosen(window), [ident])

    def test_each_class_lists_what_it_can_use(self):
        world, window = self.opened()
        self.weapons(world, window)
        expected = {
            "warrior": [ONLY_WARRIOR, WARRIOR_AND_SURA, ANY_CLASS],
            "ninja": [ONLY_NINJA, ANY_CLASS],
            "sura": [WARRIOR_AND_SURA, ANY_CLASS],
            "shaman": [ANY_CLASS, ONLY_SHAMAN],
            "all": EVERY,
        }
        for ident, vnums in expected.items():
            with self.subTest(cls=ident):
                self.press(world, window, "class_press", self.class_index(window, ident), LEFT)
                self.assertEqual(self.chosen(window), [ident])
                self.assertEqual(self.vnums(window), vnums)
                self.assertEqual(self.model(window)["list_count"], str(len(vnums)))

    def test_every_equipment_list_is_filtered(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        for j, sub in enumerate(module.TREE[0]["subs"]):
            with self.subTest(sub=sub["label"]):
                self.press(world, window, "sub_press", 0, j, LEFT)
                self.assertEqual(self.vnums(window), [ONLY_WARRIOR, WARRIOR_AND_SURA, ANY_CLASS])

    def test_other_lists_have_no_filter(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        for label in ("WIKI_SUB_COSTUME_WEAPONS", "WIKI_SUB_BOSS_CHESTS", "WIKI_SUB_LV1_109"):
            with self.subTest(sub=label):
                cat, sub = category_of(module, label)
                self.press(world, window, "sub_press", cat, sub, LEFT)
                self.assertEqual(self.model(window)["classes"], [])
        with world.game, w4.quiet():
            window.search("sword")
        self.assertEqual(self.model(window)["classes"], [], "a search lists every class's items")

    def test_back_and_forward_walk_the_filters(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "ninja"), LEFT)
        self.press(world, window, "class_press", self.class_index(window, "shaman"), LEFT)
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(self.chosen(window), ["ninja"])
        self.assertEqual(self.vnums(window), [ONLY_NINJA, ANY_CLASS])
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(self.chosen(window), ["warrior"])
        self.press(world, window, "forward_press", LEFT)
        self.press(world, window, "forward_press", LEFT)
        self.assertEqual(self.chosen(window), ["shaman"])

    def test_the_filter_stays_for_the_next_equipment_list(self):
        # OLD kept its class button across the equipment categories.
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "sura"), LEFT)
        cat, sub = equipment(world.m("nui_wiki"), "WIKI_SUB_ARMOR")
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.assertEqual(self.chosen(window), ["sura"])
        self.assertEqual(self.vnums(window), [WARRIOR_AND_SURA, ANY_CLASS])

    def test_a_middle_press_on_a_class_opens_it_in_a_new_tab(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "ninja"), MIDDLE)
        self.assertEqual(self.chosen(window), ["warrior"], "this tab keeps its filter")
        self.assertEqual(len(self.model(window)["tabs"]), 2)
        self.press(world, window, "tab_press", 1, LEFT)
        self.assertEqual(self.chosen(window), ["ninja"])
        self.assertEqual(self.vnums(window), [ONLY_NINJA, ANY_CLASS])

    def test_each_tab_keeps_its_own_filter(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "new_tab_press", LEFT)
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "shaman"), LEFT)
        self.press(world, window, "tab_press", 0, LEFT)
        self.assertEqual(self.chosen(window), ["warrior"])
        self.press(world, window, "tab_press", 1, LEFT)
        self.assertEqual(self.chosen(window), ["shaman"])

    def test_a_page_opened_from_a_filtered_list_goes_back_to_it(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "ninja"), LEFT)
        self.press(world, window, "row_press", 0, LEFT)
        self.assertEqual(self.model(window)["page_vnum"], ONLY_NINJA)
        self.assertEqual(self.chosen(window), ["ninja"], "the list beside the page stays filtered")
        self.assertEqual(self.model(window)["list_sel"], 0)
        crumbs = self.model(window)["crumbs"]
        self.press(world, window, "crumb_press", len(crumbs) - 2, LEFT)
        self.assertEqual(self.model(window)["page_state"], "")
        self.assertEqual(self.chosen(window), ["ninja"])

    def test_a_class_change_keeps_the_page_shown(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "row_press", 2, LEFT)
        self.press(world, window, "class_press", self.class_index(window, "all"), LEFT)
        self.assertEqual(self.model(window)["page_vnum"], ANY_CLASS)
        self.assertEqual(self.model(window)["list_sel"], 3)

    def test_the_tree_marks_a_filtered_list(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "sura"), LEFT)
        marked = [s for c in self.model(window)["tree"] for s in c["subs"] if s["selected"]]
        self.assertEqual([s["label"] for s in marked], ["Weapons"])

    def test_search_and_back_keep_the_filter(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "shaman"), LEFT)
        with world.game, w4.quiet():
            w4.board(window).insert_text("wiki-search", "sword")
        self.assertEqual(self.model(window)["classes"], [])
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(self.chosen(window), ["shaman"])
        self.assertEqual(self.vnums(window), [ANY_CLASS, ONLY_SHAMAN])

    def test_a_right_press_or_a_bad_index_does_nothing(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "ninja"), RIGHT)
        self.press(world, window, "class_press", 99, LEFT)
        self.assertEqual(self.chosen(window), ["warrior"])
        self.assertFalse(self.model(window)["can_forward"])


class ClassLinks(R4Test):
    def link(self, world, window):
        pasted = []
        with world.game, w4.quiet():
            window.SetPasteLinkEvent(pasted.append)
        self.press(world, window, "link_press", LEFT)
        return pasted[-1]

    def test_a_list_link_keeps_its_filter(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.press(world, window, "class_press", self.class_index(window, "sura"), LEFT)
        link = self.link(world, window)
        self.assertIn("|Hsyswiki:list:equipment:weapons:sura|h", link)
        # The server takes it as a free list link ([a-z0-9_:], at most 64).
        self.assertRegex(link, r"\|Hsyswiki:list:[a-z0-9_:]{1,64}\|h")

    def test_a_list_link_opens_with_its_filter(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            self.assertTrue(window.OpenList("equipment:weapons:ninja"))
        self.assertEqual(self.chosen(window), ["ninja"])
        self.assertEqual(self.vnums(window), [ONLY_NINJA, ANY_CLASS])
        with world.game, w4.quiet():
            self.assertTrue(window.OpenList("equipment:armor:all"))
        self.assertEqual(self.chosen(window), ["all"])
        self.assertEqual(self.vnums(window), EVERY)

    def test_a_link_without_a_class_opens_on_the_player_s_class(self):
        # r3's links had none.
        self.RACE = 3
        world, window = self.opened()
        with world.game, w4.quiet():
            self.assertTrue(window.OpenList("equipment:weapons"))
        self.assertEqual(self.chosen(window), ["shaman"])

    def test_a_bad_class_or_a_class_on_another_list_opens_nothing(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        for path in ("equipment:weapons:lycan", "equipment:weapons:", "costumes:costume_hair:sura",
                     "equipment:weapons:sura:sura"):
            with self.subTest(path=path):
                self.assertIs(module.list_of_path(path), module.NO_LIST)

    def test_paths_round_trip(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        cat, sub = equipment(module)
        for ident in ("warrior", "ninja", "shaman", "sura", "all"):
            key = ("sub", cat, sub, ident)
            with self.subTest(cls=ident):
                self.assertEqual(module.list_of_path(module.list_path(key)), key)
        hair = category_of(module, "WIKI_SUB_COSTUME_HAIR")
        self.assertEqual(module.list_path(("sub",) + hair), "costumes:costume_hair")


# --- 4. long lists: every item, a page of rows at a time ---------------------------------------

class LongLists(R4Test):
    """r41: the costume lists stopped at 500 (LIST_ROWS_MAX) and a search
    at 200. Every list now has all its items; the window lays out one page
    of rows at a time, so a long list costs no more than a short one."""

    def costumes(self, world, window):
        cat, sub = category_of(world.m("nui_wiki"), "WIKI_SUB_COSTUME_WEAPONS")
        self.press(world, window, "sub_press", cat, sub, LEFT)
        return sorted(world.m("nui_wiki_data").COSTUME_WEAPONS)

    def walk(self, world, window):
        seen = list(self.vnums(window))
        while self.model(window)["list_next"]:
            self.press(world, window, "list_next_press", LEFT)
            seen += self.vnums(window)
        return seen

    def test_the_costume_list_lists_every_item_past_500(self):
        world, window = self.opened()
        vnums = self.costumes(world, window)
        self.assertGreater(len(vnums), 500)
        self.assertEqual(self.model(window)["list_count"], str(len(vnums)))
        self.assertEqual(self.walk(world, window), vnums)

    def test_one_page_of_rows_is_laid_out(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        vnums = self.costumes(world, window)
        self.assertEqual(len(self.model(window)["list"]), module.LIST_PAGE_ROWS)
        self.assertFalse(self.model(window)["list_prev"])
        self.assertTrue(self.model(window)["list_next"])
        self.assertEqual(self.model(window)["list_range"], "1-%d / %d" % (module.LIST_PAGE_ROWS, len(vnums)))

    def test_rows_keep_their_place_in_the_whole_list(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        vnums = self.costumes(world, window)
        self.press(world, window, "list_next_press", LEFT)
        first = self.model(window)["list"][0]
        self.assertEqual(first["i"], module.LIST_PAGE_ROWS)
        self.press(world, window, "row_press", first["i"], LEFT)
        self.assertEqual(self.model(window)["page_vnum"], vnums[module.LIST_PAGE_ROWS])
        self.assertEqual(self.model(window)["list_sel"], module.LIST_PAGE_ROWS)
        self.press(world, window, "list_prev_press", LEFT)
        self.assertEqual(self.model(window)["list"][0]["i"], 0)

    def test_a_page_of_the_list_shows_the_page_that_holds_it(self):
        world, window = self.opened()
        module = world.m("nui_wiki")
        vnums = self.costumes(world, window)
        far = vnums[2 * module.LIST_PAGE_ROWS + 3]
        with world.game, w4.quiet():
            window.OpenItem(far)
        self.assertIn(far, self.vnums(window))
        self.assertEqual(self.model(window)["list_sel"], 2 * module.LIST_PAGE_ROWS + 3)
        self.press(world, window, "back_press", LEFT)
        self.assertEqual(self.model(window)["page_state"], "")

    def test_a_short_list_has_no_pager(self):
        world, window = self.opened()
        self.weapons(world, window)
        self.assertEqual((self.model(window)["list_prev"], self.model(window)["list_next"]), (False, False))
        self.assertEqual(self.model(window)["list_range"], "")

    def test_a_new_list_starts_on_its_first_page(self):
        world, window = self.opened()
        self.costumes(world, window)
        self.press(world, window, "list_next_press", LEFT)
        cat, sub = category_of(world.m("nui_wiki"), "WIKI_SUB_COSTUME_ARMOR")
        self.press(world, window, "sub_press", cat, sub, LEFT)
        self.assertEqual(self.model(window)["list"][0]["i"], 0)

    def test_a_search_finds_every_match(self):
        world, window = self.opened()
        many = tuple(range(30000, 30800))
        asked = []
        world.game.answer("item", "Search", lambda text, limit: asked.append(limit) or many[:limit])
        with world.game, w4.quiet():
            window.search("stone")
        self.assertGreaterEqual(min(asked), len(many))
        self.assertEqual(self.model(window)["list_count"], str(len(many)))


# --- 2. items embedded in text pages ---------------------------------------------------------

HEAD = "---\ntitle: Demon Tower\ncategory: dungeons\n---\n"


def runs_of(text):
    result = fmt.parse(HEAD + text)
    return result, result.blocks[0]["runs"]


class EmbedFormat(unittest.TestCase):
    def test_an_embed_is_a_link_with_a_bang(self):
        result, runs = runs_of("Get the ![[item:30304]] from the Reaper.\n")
        self.assertEqual(result.problems, [])
        embed = [r for r in runs if r["link"]]
        self.assertEqual(len(embed), 1)
        self.assertEqual(embed[0]["link"], ("item", "30304", None))
        self.assertTrue(embed[0]["embed"])
        self.assertEqual(runs[0]["t"], "Get the ")
        self.assertFalse(runs[0]["embed"])
        self.assertEqual(runs[-1]["t"], " from the Reaper.")

    def test_an_embed_takes_a_text(self):
        result, runs = runs_of("![[item:30330|Maat Stones]] x5\n")
        self.assertEqual(result.problems, [])
        self.assertEqual(runs[0]["link"], ("item", "30330", "Maat Stones"))
        self.assertTrue(runs[0]["embed"])
        self.assertEqual(runs[1]["t"], " x5")

    def test_a_plain_link_is_not_an_embed(self):
        result, runs = runs_of("See [[item:30304]].\n")
        self.assertFalse([r for r in runs if r["link"]][0]["embed"])

    def test_only_items_embed(self):
        for body in ("![[mob:1093]]\n", "![[page:dungeons/demon_tower]]\n"):
            with self.subTest(body=body):
                result, runs = runs_of(body)
                self.assertTrue(result.problems)
                self.assertTrue(runs[0]["e"], "an error run where the embed was")
                self.assertIn("only items embed", result.problems[0][1])

    def test_an_escaped_bang_is_text_before_a_link(self):
        result, runs = runs_of("Wow\\![[item:19]]\n")
        self.assertEqual(result.problems, [])
        self.assertEqual(runs[0]["t"], "Wow!")
        self.assertFalse(runs[1]["embed"])

    def test_a_lone_bang_stays_text(self):
        result, runs = runs_of("Hurry! It ends soon!\n")
        self.assertEqual(runs[0]["t"], "Hurry! It ends soon!")

    def test_a_line_that_starts_with_an_embed_is_a_paragraph(self):
        result = fmt.parse(HEAD + "![[item:30304]] opens the door.\n")
        self.assertEqual(result.problems, [])
        self.assertEqual([b["k"] for b in result.blocks], ["p"])

    def test_embeds_in_lists_tables_and_bold(self):
        result = fmt.parse(HEAD + "- **![[item:19]]**\n\n| Grade | Sash |\n|---|---|\n| Basic | ![[item:85001]] |\n")
        self.assertEqual(result.problems, [])
        bullet = result.blocks[0]["items"][0]["runs"]
        self.assertTrue(bullet[0]["embed"] and bullet[0]["b"])
        cell = result.blocks[1]["rows"][1]["cells"][1]["runs"]
        self.assertTrue(cell[0]["embed"])

    def test_the_search_text_has_the_embed_s_text(self):
        result = fmt.parse(HEAD + "Use ![[item:30330|Maat Stones]].\n")
        self.assertIn("maat stones", result.search_text)


class EmbedTest(pages_test.PagesTest):
    PAGE = """---
title: Demon Tower
category: dungeons
---
# Demon Tower
Defeat the [[mob:1093]] to get the ![[item:30304]], then [[item:19|a sword]].
"""

    def world(self, extra=None):
        store = {"locale/en/wiki/dungeons/demon_tower.txt": self.PAGE.encode()}
        store.update(extra or {})
        world, window = pages_test.PagesTest.world(self, store)
        self.tip = Tip()
        with world.game, w4.quiet():
            window.SetItemToolTip(self.tip)
        return world, window

    def embedded(self):
        world, window = self.world()
        self.open_page(world, window, "dungeons/demon_tower")
        return world, window, self.runs(window)


class Tip(object):
    """The Interface's item tooltip (nui_item_tooltip.ItemToolTip)."""

    def __init__(self):
        self.calls = []

    def SetItemToolTip(self, vnum):
        self.calls.append(("SetItemToolTip", vnum))

    def HideToolTip(self):
        self.calls.append(("HideToolTip",))


class EmbedModel(EmbedTest):
    def test_an_embed_shows_the_item_s_icon_and_name(self):
        world, window, runs = self.embedded()
        embed = [r for r in runs if r["m"] == "item"]
        self.assertEqual(len(embed), 1)
        self.assertEqual(embed[0]["t"], "Item 30304")
        self.assertTrue(embed[0]["icon"])
        with world.game, w4.quiet():
            self.assertEqual(embed[0]["icon"], world.m("nui_wiki")._item_icon(30304))
        self.assertGreaterEqual(embed[0]["l"], 0)

    def test_text_and_plain_links_are_not_embeds(self):
        world, window, runs = self.embedded()
        others = [r for r in runs if r["m"] != "item"]
        self.assertTrue(others)
        for run in others:
            self.assertEqual((run["m"], run["icon"]), ("", ""))

    def test_a_press_on_an_embed_opens_the_item_s_page(self):
        world, window, runs = self.embedded()
        embed = [r for r in runs if r["m"] == "item"][0]
        self.press(world, window, "tp_link", embed["l"], LEFT)
        self.assertEqual((self.model(window)["page_kind"], self.model(window)["page_vnum"]), ("item", 30304))

    def test_hovering_an_embed_shows_the_item_s_tooltip_once(self):
        world, window, runs = self.embedded()
        embed = [r for r in runs if r["m"] == "item"][0]
        with world.game, w4.quiet():
            w4.fire(window, "tp_over", embed["l"])
            w4.fire(window, "tp_over", embed["l"])  # RmlUi bubbles a child's mouseover
        self.assertEqual(self.tip.calls, [("SetItemToolTip", 30304)])
        with world.game, w4.quiet():
            w4.fire(window, "tp_out")
        self.assertEqual(self.tip.calls[-1], ("HideToolTip",))
        with world.game, w4.quiet():
            w4.fire(window, "tp_over", embed["l"])
        self.assertEqual(self.tip.calls[-1], ("SetItemToolTip", 30304), "entered again, it shows again")

    def test_hovering_a_plain_link_or_text_shows_no_tooltip(self):
        world, window, runs = self.embedded()
        plain = [r for r in runs if r["l"] >= 0 and r["m"] == ""]
        with world.game, w4.quiet():
            for run in plain:
                w4.fire(window, "tp_over", run["l"])
            w4.fire(window, "tp_over", -1)
            w4.fire(window, "tp_over", 99)
        self.assertEqual([c for c in self.tip.calls if c[0] == "SetItemToolTip"], [])

    def test_leaving_the_page_hides_the_tooltip(self):
        world, window, runs = self.embedded()
        embed = [r for r in runs if r["m"] == "item"][0]
        with world.game, w4.quiet():
            w4.fire(window, "tp_over", embed["l"])
            window.OpenMob(1093)
        self.assertEqual(self.tip.calls[-1], ("HideToolTip",))

    def test_the_wiki_s_other_tooltips_use_the_interface_s(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.over_vnum(19)
        self.assertEqual(self.tip.calls, [("SetItemToolTip", 19)])


class EmbedMarkup(unittest.TestCase):
    def rml(self):
        with open(os.path.join(WIKI_DIR, "wiki.rml"), encoding="utf-8") as handle:
            return handle.read()

    def test_every_place_a_run_shows_can_show_an_embed(self):
        rml = self.rml()
        runs = rml.count('class="wp__run"')
        self.assertEqual(rml.count('class="wp__embed"'), runs)
        self.assertEqual(rml.count('data-event-mouseover="tp_over(r.l)"'), runs)
        self.assertEqual(rml.count('data-event-mouseout="tp_out()"'), runs)

    def test_an_embed_s_children_take_no_pointer(self):
        # A hover over a row's children must not fire once per child.
        with open(os.path.join(WIKI_DIR, "wiki-pages.rcss"), encoding="utf-8") as handle:
            rcss = handle.read()
        self.assertRegex(rcss, r"\.wp__embed\s*>\s*\*[^{]*\{[^}]*pointer-events:\s*none")


# --- the converter -----------------------------------------------------------------------------

class Converter(unittest.TestCase):
    def convert(self, lines):
        import wiki_convert_old as convert
        return convert.Converter("dungeons/x.txt", "X", None).convert(["skipped"] + lines)

    def test_an_old_item_icon_becomes_an_embed(self):
        text = self.convert(["[IMG=icon/item/30304.tga; ITEM_TOOLTIP=30304; X= 270; Y=133;]"])
        self.assertIn("![[item:30304]]", text)
        self.assertNotIn(" [[item:30304]]", text)

    def test_its_count_follows(self):
        text = self.convert(["[IMG=icon/item/30330.tga; ITEM_TOOLTIP=30330; item_count=5; X= 1; Y=2;]"])
        self.assertIn("![[item:30330]] x5", text)

    def test_visual_bonuses_after_the_vnum_are_dropped(self):
        text = self.convert(["[IMG=icon/item/19.tga; ITEM_TOOLTIP=19:1:500:2:30; X= 1; Y=2;]"])
        self.assertIn("![[item:19]]", text)

    def test_a_goto_item_stays_a_link(self):
        text = self.convert(["[GOTO=item:19]A sword"])
        self.assertIn("[[item:19|A sword]]", text)
        self.assertNotIn("![[item:19", text)

    def test_the_drafts_are_the_converter_s_output(self):
        out = tempfile.mkdtemp()
        result = subprocess.run([sys.executable, "-B", os.path.join(HERE, "wiki_convert_old.py"), "--out", out],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        drafts = os.path.join(os.path.dirname(HERE), "docs", "wiki", "drafts", "en")
        made = 0
        for folder, _, names in os.walk(os.path.join(out, "en")):
            for name in names:
                path = os.path.join(folder, name)
                rel = os.path.relpath(path, os.path.join(out, "en"))
                with open(path, encoding="utf-8") as a, open(os.path.join(drafts, rel), encoding="utf-8") as b:
                    self.assertEqual(a.read(), b.read(), rel)
                made += 1
        self.assertEqual(made, 60)


# --- the shipped pages and strings -----------------------------------------------------------

class Shipped(unittest.TestCase):
    def read(self, path):
        with open(os.path.join(SHIPPED, path + ".txt"), encoding="utf-8") as handle:
            return handle.read()

    def test_the_demon_tower_key_shows_as_an_icon(self):
        self.assertIn("![[item:30304]]", self.read("dungeons/demon_tower"))

    def test_the_items_old_showed_as_icons_are_embedded(self):
        for path, vnums in (("dungeons/spider_baroness", (30327,)), ("dungeons/nemere", (30332, 30333)),
                            ("dungeons/razador", (30329, 30330)), ("systems/gaya", (50926, 39064, 39063)),
                            ("systems/shoulder_sash", (85001, 85002, 85003, 85004))):
            text = self.read(path)
            for vnum in vnums:
                with self.subTest(path=path, vnum=vnum):
                    self.assertIn("![[item:%d" % vnum, text)

    def test_the_new_strings_are_in_every_locale(self):
        keys = ("WIKI_CLASS_ALL", "WIKI_VIEWER_HINT", "WIKI_LIST_RANGE", "TOOLTIP_WARRIOR", "TOOLTIP_ASSASSIN", "TOOLTIP_SURA",
                "TOOLTIP_SHAMAN")
        locales = sorted(d for d in os.listdir(LOCALES) if os.path.isfile(os.path.join(LOCALES, d, "locale_game.txt")))
        self.assertEqual(len(locales), 17)
        for locale in locales:
            with open(os.path.join(LOCALES, locale, "locale_game.txt"), "rb") as handle:
                data = handle.read()
            found = set(line.split(b"\t", 1)[0].decode("ascii", "replace") for line in data.split(b"\n"))
            with self.subTest(locale=locale):
                self.assertFalse(set(keys) - found)

    def test_writing_md_documents_the_embed(self):
        with open(os.path.join(os.path.dirname(HERE), "docs", "wiki", "WRITING.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("![[item:30304]]", text)


# --- 3. the model viewer -----------------------------------------------------------------------

class Viewer(R4Test):
    def world(self):
        world, window = R4Test.world(self)
        previews = world.game.modules["modelpreview"]
        previews.SetTurn = lambda name, turning: previews.calls.append(("SetTurn", name, bool(turning)))
        previews.SetRotation = lambda name, degrees: previews.calls.append(("SetRotation", name, float(degrees)))
        previews.SetZoom = lambda name, zoom: previews.calls.append(("SetZoom", name, float(zoom)))
        self.previews = previews
        return world, window

    def calls(self, name="wiki_viewer"):
        return [c for c in self.previews.calls if c[1] == name]

    def on_mob_page(self):
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenMob(8002)
        self.assertTrue(self.model(window)["model_view"])
        del self.previews.calls[:]
        return world, window

    def viewing(self):
        world, window = self.on_mob_page()
        self.press(world, window, "preview_press", LEFT)
        return world, window

    def test_a_press_on_the_preview_opens_the_viewer_with_the_same_model(self):
        world, window = self.viewing()
        self.assertTrue(self.model(window)["viewer"])
        self.assertIn(("Select", "wiki_viewer", 8002), self.calls())
        self.assertIn(("Show", "wiki_viewer", True), self.calls())
        self.assertEqual(self.model(window)["viewer_name"], "Mob 8002")

    def test_the_viewer_wears_the_page_s_parts(self):
        self.RACE = 1  # the stand-in's Select makes no model of race 0
        world, window = self.opened()
        with world.game, w4.quiet():
            window.OpenItem(base.SWORD)
        page = [c for c in self.previews.calls if c[1] == "wiki" and c[0] in ("Select", "SetParts")]
        del self.previews.calls[:]
        self.press(world, window, "preview_press", LEFT)
        viewer = [c[:1] + c[2:] for c in self.calls() if c[0] in ("Select", "SetParts")]
        self.assertEqual(viewer, [c[:1] + c[2:] for c in page])
        # NOVA-259: the look comes with the race, in one Select.
        self.assertEqual(viewer, [("Select", 1, 0, base.SWORD, 0, 0)], "a weapon is worn")

    def test_the_viewer_starts_turning_at_the_natural_distance(self):
        world, window = self.viewing()
        self.assertIn(("SetTurn", "wiki_viewer", True), self.calls())
        self.assertIn(("SetZoom", "wiki_viewer", 1.0), self.calls())

    def test_the_page_s_small_view_rests_while_the_viewer_shows(self):
        world, window = self.viewing()
        self.assertIn(("Show", "wiki", False), self.calls("wiki"))
        self.press(world, window, "viewer_close_press", LEFT)
        self.assertEqual(self.calls("wiki")[-1], ("Show", "wiki", True))

    def test_no_model_no_viewer(self):
        world, window = self.opened()
        self.previews.Select = lambda name, race: False
        with world.game, w4.quiet():
            window.OpenMob(8002)
        self.assertFalse(self.model(window)["model_view"])
        self.press(world, window, "preview_press", LEFT)
        self.assertFalse(self.model(window)["viewer"])

    def test_only_a_left_press_opens_it(self):
        world, window = self.on_mob_page()
        for button in (RIGHT, MIDDLE):
            self.press(world, window, "preview_press", button)
        self.assertFalse(self.model(window)["viewer"])

    def test_a_drag_turns_the_model_and_stops_its_turn(self):
        world, window = self.viewing()
        with world.game, w4.quiet():
            w4.fire(window, "viewer_grab", 100.0)
            w4.fire(window, "viewer_drag", 150.0)
            w4.fire(window, "viewer_drag", 130.0)
        self.assertIn(("SetTurn", "wiki_viewer", False), self.calls())
        rotations = [c[2] for c in self.calls() if c[0] == "SetRotation"]
        self.assertEqual(len(rotations), 2)
        self.assertNotEqual(rotations[0], rotations[1])
        self.assertTrue(all(0.0 <= r < 360.0 for r in rotations))

    def test_the_wheel_zooms_within_limits(self):
        world, window = self.viewing()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            for _ in range(40):
                w4.fire(window, "viewer_wheel", -1.0)
        zooms = [c[2] for c in self.calls() if c[0] == "SetZoom"]
        self.assertGreater(zooms[1], zooms[0], "wheel up zooms in")
        self.assertEqual(zooms[-1], module.VIEWER_ZOOM_MAX)
        with world.game, w4.quiet():
            for _ in range(80):
                w4.fire(window, "viewer_wheel", 1.0)
        self.assertEqual([c[2] for c in self.calls() if c[0] == "SetZoom"][-1], module.VIEWER_ZOOM_MIN)

    def test_a_double_click_resets_the_view(self):
        world, window = self.viewing()
        with world.game, w4.quiet():
            w4.fire(window, "viewer_grab", 0.0)
            w4.fire(window, "viewer_drag", 80.0)
            w4.fire(window, "viewer_wheel", -3.0)
            del self.previews.calls[:]
            w4.fire(window, "viewer_reset")
        self.assertEqual([c for c in self.calls() if c[0] in ("SetTurn", "SetRotation", "SetZoom")],
                         [("SetRotation", "wiki_viewer", 0.0), ("SetZoom", "wiki_viewer", 1.0),
                          ("SetTurn", "wiki_viewer", True)])

    def test_the_close_button_releases_the_viewer_s_target(self):
        world, window = self.viewing()
        self.press(world, window, "viewer_close_press", LEFT)
        self.assertFalse(self.model(window)["viewer"])
        self.assertIn(("Clear", "wiki_viewer"), self.calls())

    def test_a_press_outside_the_model_closes_it_and_one_on_it_does_not(self):
        world, window = self.viewing()
        self.press(world, window, "viewer_stage_press", LEFT)
        self.assertTrue(self.model(window)["viewer"], "a press on the model is a drag")
        self.press(world, window, "viewer_backdrop_press", LEFT)
        self.assertFalse(self.model(window)["viewer"])

    def test_the_stage_press_bubbling_to_the_backdrop_keeps_it_open(self):
        # RmlUi bubbles the stage's mousedown to the backdrop that holds it.
        world, window = self.viewing()
        with world.game, w4.quiet():
            w4.fire(window, "viewer_stage_press", LEFT)
            w4.fire(window, "viewer_backdrop_press", LEFT)
        self.assertTrue(self.model(window)["viewer"])

    def test_escape_closes_the_viewer_first(self):
        world, window = self.viewing()
        with world.game, w4.quiet():
            self.assertTrue(window.OnPressEscapeKey())
        self.assertFalse(self.model(window)["viewer"])
        self.assertTrue(window.IsShow())
        with world.game, w4.quiet():
            self.assertFalse(window.OnPressEscapeKey(), "with no viewer the key goes on as before")

    def test_leaving_the_page_or_hiding_closes_it(self):
        for leave in (lambda w: w.OpenItem(base.SWORD), lambda w: w.back(), lambda w: w.Hide(),
                      lambda w: w.new_tab()):
            with self.subTest():
                world, window = self.viewing()
                with world.game, w4.quiet():
                    leave(window)
                self.assertIn(("Clear", "wiki_viewer"), self.calls())
                if w4.board(window) is not None:
                    self.assertFalse(self.model(window)["viewer"])

    def test_a_client_without_the_viewer_calls_still_opens_it(self):
        world, window = self.on_mob_page()
        for name in ("SetTurn", "SetRotation", "SetZoom"):
            delattr(self.previews, name)
        self.press(world, window, "preview_press", LEFT)
        with world.game, w4.quiet():
            w4.fire(window, "viewer_grab", 0.0)
            w4.fire(window, "viewer_drag", 40.0)
            w4.fire(window, "viewer_wheel", 1.0)
        self.assertTrue(self.model(window)["viewer"])


class ViewerMarkup(unittest.TestCase):
    def test_the_viewer_has_its_own_view_and_drags_without_python_per_child(self):
        with open(os.path.join(WIKI_DIR, "wiki.rml"), encoding="utf-8") as handle:
            rml = handle.read()
        self.assertIn('name="model-wiki-viewer"', rml)
        stage = re.search(r'<div[^>]*id="wiki-viewer-stage"[^>]*>', rml).group(0)
        for event in ("dragstart", "drag", "mousescroll", "dblclick", "mousedown"):
            with self.subTest(event=event):
                self.assertIn("data-event-%s=" % event, stage)
        with open(os.path.join(WIKI_DIR, "wiki.rcss"), encoding="utf-8") as handle:
            rcss = handle.read()
        self.assertRegex(rcss, r"\.wiki__stage\s*\{[^}]*drag:\s*drag")
        self.assertRegex(rcss, r"\.wiki__stage\s*>\s*\*[^{]*\{[^}]*pointer-events:\s*none")


class Fixtures(unittest.TestCase):
    def test_the_new_fixtures_have_the_main_fixture_s_keys(self):
        with open(os.path.join(WIKI_DIR, "wiki.fixture.json"), encoding="utf-8") as handle:
            keys = set(json.load(handle)["wiki"])
        for variant in ("classes", "embed", "viewer"):
            with self.subTest(variant=variant):
                with open(os.path.join(WIKI_DIR, "wiki.%s.fixture.json" % variant), encoding="utf-8") as handle:
                    self.assertEqual(set(json.load(handle)["wiki"]), keys)


if __name__ == "__main__":
    unittest.main()
