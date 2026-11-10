"""Tests of the ingame wiki's item and mob browser (NOVA-42): the NovaUI window
(assets/root/nui_wiki.py, no legacy window), its data lists
(assets/root/nui_wiki_data.py), the game's answer handler and the links that
open it. The server's rate limit answers WIKI_STATUS_BUSY, and the window must
ask again (a dropped request must never leave the page empty)."""

import ast
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402

ROOT = os.path.join(os.path.dirname(HERE), "assets", "root")

ITEM, MOB = 0, 1
OK, BUSY = 0, 1
SWORD, CHEST = 200019, 50012
WEAPON_TYPE, ARMOR_TYPE, COSTUME_TYPE = 1, 2, 28


def setup(game):
    item = game.modules["item"]
    for name, value in (("ITEM_TYPE_WEAPON", WEAPON_TYPE), ("ITEM_TYPE_ARMOR", ARMOR_TYPE),
                        ("ITEM_TYPE_BELT", 18), ("ITEM_TYPE_RING", 34), ("ITEM_TYPE_COSTUME", COSTUME_TYPE),
                        ("ARMOR_BODY", 0), ("ARMOR_HEAD", 1), ("ARMOR_SHIELD", 2), ("ARMOR_WRIST", 3),
                        ("ARMOR_FOOTS", 4), ("ARMOR_NECK", 5), ("ARMOR_EAR", 6),
                        ("COSTUME_TYPE_BODY", 0), ("COSTUME_TYPE_HAIR", 1), ("COSTUME_TYPE_WEAPON", 2),
                        ("COSTUME_TYPE_SASH", 3), ("COSTUME_TYPE_SASH2", 4),
                        ("ITEM_ANTIFLAG_WARRIOR", 1), ("ITEM_ANTIFLAG_ASSASSIN", 2), ("ITEM_ANTIFLAG_SURA", 4),
                        ("ITEM_ANTIFLAG_SHAMAN", 8), ("ITEM_ANTIFLAG_MALE", 16), ("ITEM_ANTIFLAG_FEMALE", 32)):
        setattr(item, name, value)
    locale = game.modules["localeInfo"]
    for key, text in (("WIKI_LEVEL", "Lv. %d"), ("WIKI_ORIGIN_MOB", "Dropped by"), ("WIKI_ORIGIN_CHEST", "Found in"),
                      ("WIKI_ORIGIN_CRAFT", "Crafted at"), ("WIKI_ORIGIN_SHOP", "Sold by")):
        setattr(locale, key, text)
    locale.NumberToMoneyString = lambda n: "%d Yang" % n
    game.answer("item", "SelectItem", lambda v: True)
    game.answer("item", "GetItemName", lambda: "Item %d" % item.selected[0])
    game.answer("item", "GetIconImageFileName", lambda: "icon.tga")
    game.answer("item", "GetItemType", lambda: WEAPON_TYPE)
    game.answer("item", "GetItemSubType", lambda: 0)
    game.answer("item", "GetValue", lambda i: 0)
    game.answer("item", "IsAntiFlag", lambda f: False)
    game.answer("item", "ListByType", lambda t, s: (SWORD,))
    game.answer("item", "Search", lambda text, limit: (SWORD,) if text == "sword" else ())
    nonplayer = game.modules["nonplayer"]
    game.answer("nonplayer", "GetMonsterName", lambda v: "Mob %d" % v)
    game.answer("nonplayer", "GetMonsterLevel", lambda v: 42)
    game.answer("nonplayer", "List", lambda k, lo, hi: (8002,))
    game.answer("nonplayer", "Search", lambda text, limit: (8002,) if text == "wolf" else ())
    previews = types.ModuleType("modelpreview")
    previews.calls = []
    previews.Select = lambda name, race: previews.calls.append(("Select", name, race)) or (race != 0)
    previews.SetParts = lambda name, a, w, h, s: previews.calls.append(("SetParts", name, a, w, h, s)) or True
    previews.Show = lambda name, show: previews.calls.append(("Show", name, show))
    previews.Clear = lambda name: previews.calls.append(("Clear", name))
    game.modules["modelpreview"] = previews


class WikiTest(unittest.TestCase):
    def world(self):
        world = w4.World(True, windows="+items,+wiki", setup=setup)
        with world.game, w4.quiet():
            world.game.load("nui_wiki_data", "nui_wiki_data.py")
            module = world.game.load("nui_wiki", "nui_wiki.py")
            module.ANSWERS.clear()
        # The search field's data-event-change (wiki.rml).
        world.game.state.field_events[("nui/windows/wiki/wiki.rml", "wiki-search")] = "search_change"
        with world.game, w4.quiet():
            window = world.nui_windows.make("wiki", type("Unused", (), {}), "nui_wiki.WikiWindow")
        return world, window

    def sent(self, world, mark):
        return [args for name, args in world.calls_since(mark, "net.") if name == "net.SendWikiRequest"]

    def answer(self, world, window, kind, status, vnum, **rows):
        with world.game, w4.quiet():
            window.WikiAnswer(kind, status, vnum, rows.get("flags", 0), rows.get("origins", ()), rows.get("chest", ()),
                              rows.get("refine", ()), rows.get("drops", ()))


class Listing(WikiTest):
    def test_a_category_lists_its_items_and_drops_blacklisted_ones(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            window.Open()
            sub = [s for s in module.TREE[0]["subs"] if s["item_type"] == "ITEM_TYPE_WEAPON"][0]
            world.game.answer("item", "ListByType", lambda t, s: (SWORD, 300))  # 300: OLD's ITEM_BLACKLIST
            window._open_sub(sub)
        rows = w4.board(window).model["list"]
        self.assertEqual([r["vnum"] for r in rows], [SWORD])
        self.assertEqual(w4.board(window).model["list_state"], "ready")

    def test_a_mob_band_lists_its_mobs_with_their_level(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            window.Open()
            sub = module.TREE[2]["subs"][0]
            window._open_sub(sub)
        rows = w4.board(window).model["list"]
        self.assertEqual([r["mob"] for r in rows], [True])
        self.assertEqual(rows[0]["note"], "Lv. 42")

    def test_search_finds_items_and_mobs(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.search("sword")
        self.assertEqual([r["vnum"] for r in w4.board(window).model["list"]], [SWORD])
        with world.game, w4.quiet():
            window.search("wolf")
        self.assertEqual([r["vnum"] for r in w4.board(window).model["list"]], [8002])
        with world.game, w4.quiet():
            window.search("xyzzy")
        self.assertEqual(w4.board(window).model["list_state"], "empty")

    def test_a_hand_kept_list_shows_its_vnums_though_select_item_answers_none(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        world.game.answer("item", "SelectItem", lambda v: None)  # the client's item.SelectItem
        with world.game, w4.quiet():
            window.Open()
            chests = module.TREE[1]["subs"][1]
            window._open_sub(chests)
        rows = w4.board(window).model["list"]
        self.assertEqual([r["vnum"] for r in rows], sorted(chests["vnums"]))
        self.assertTrue(rows)

    def test_opening_a_category_clears_the_search_field(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            window.Open()
            w4.board(window).insert_text("wiki-search", "wolf")
        self.assertEqual(w4.board(window).fields["wiki-search"], "wolf")
        with world.game, w4.quiet():
            window._open_sub(module.TREE[2]["subs"][0])
        self.assertEqual(w4.board(window).fields["wiki-search"], "")

    def test_the_text_pages_have_a_place_to_plug_in(self):
        world, window = self.world()
        data = world.m("nui_wiki_data")
        self.assertEqual(data.TEXT_CATEGORIES, ())


class Request(WikiTest):
    def test_a_page_is_asked_for_once_and_kept_for_the_session(self):
        world, window = self.world()
        mark = world.mark()
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.assertEqual(self.sent(world, mark), [(ITEM, SWORD)])
        self.assertEqual(w4.board(window).model["page_state"], "loading")
        self.answer(world, window, ITEM, OK, SWORD, origins=((0, 8002), (3, 9001)), refine=((0, 0, 500, ((30000, 2),)),))
        model = w4.board(window).model
        self.assertEqual(model["page_state"], "ready")
        self.assertEqual([o["name"] for o in model["origins"]], ["Mob 8002", "Mob 9001"])
        self.assertEqual(model["origins"][0]["label"], "Dropped by")
        self.assertEqual(model["refine"][0]["cost"], "500 Yang")
        self.assertEqual(model["refine"][0]["label"], "+1")
        mark = world.mark()
        with world.game, w4.quiet():
            window.open_item(SWORD)
        self.assertEqual(self.sent(world, mark), [], "the answer is cached")
        self.assertEqual(w4.board(window).model["page_state"], "ready")

    def test_a_mob_page_shows_its_drops(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.OpenMob(8002)
        self.answer(world, window, MOB, OK, 8002, drops=((30000, 2),))
        rows = w4.board(window).model["drops"]
        self.assertEqual(rows[0]["count"], "2")
        self.assertEqual(w4.board(window).model["page_kind"], "mob")

    def test_an_answer_with_no_rows_shows_nothing_known_not_loading(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.answer(world, window, ITEM, OK, SWORD)
        model = w4.board(window).model
        self.assertEqual(model["page_state"], "ready")
        self.assertEqual(model["origins"], [])

    def test_an_answer_for_another_page_is_kept_and_not_shown(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.answer(world, window, ITEM, OK, CHEST, chest=((27001, 3),))
        self.assertIn((ITEM, CHEST), module.ANSWERS)
        self.assertEqual(w4.board(window).model["page_state"], "loading")

    def test_a_busy_answer_retries_the_shown_page_after_a_moment(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.answer(world, window, ITEM, BUSY, SWORD)
        self.assertGreater(w4.board(window).model["retry_at"], 0, "the retry clock is armed")
        self.assertEqual(w4.board(window).model["page_state"], "loading")
        mark = world.mark()
        with world.game, w4.quiet():
            window.retry_fire()
        self.assertEqual(self.sent(world, mark), [(ITEM, SWORD)], "the dropped request is sent again")

    def test_a_busy_answer_for_another_page_does_not_retry_it(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.answer(world, window, ITEM, BUSY, CHEST)
        self.assertEqual(w4.board(window).model["retry_at"], 0.0)

    def test_a_request_that_is_never_answered_is_asked_again_then_gives_up(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        for _ in range(module.TRIES_MAX - 1):
            mark = world.mark()
            with world.game, w4.quiet():
                window.timeout_fire()
            self.assertEqual(self.sent(world, mark), [(ITEM, SWORD)])
        with world.game, w4.quiet():
            window.timeout_fire()
        self.assertEqual(w4.board(window).model["page_state"], "failed", "the page says so instead of waiting forever")
        with world.game, w4.quiet():
            window.open_item(SWORD)
        self.assertEqual(w4.board(window).model["page_state"], "loading", "opening it again asks again")

    def test_after_a_failed_page_the_retry_budget_starts_over(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
            for _ in range(module.TRIES_MAX):
                window.timeout_fire()
            window.open_item(SWORD)
        self.answer(world, window, ITEM, BUSY, SWORD)
        self.assertGreater(w4.board(window).model["retry_at"], 0)

    def test_a_retry_after_an_answer_arrived_sends_nothing(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.answer(world, window, ITEM, OK, SWORD)
        mark = world.mark()
        with world.game, w4.quiet():
            window.retry_fire()
            window.timeout_fire()
        self.assertEqual(self.sent(world, mark), [])


class Preview(WikiTest):
    def calls(self, world):
        return world.game.modules["modelpreview"].calls

    def test_a_mob_page_shows_the_mob(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.open_item  # the window needs no item for a mob
            window.OpenMob(8002)
        self.assertIn(("Select", "wiki", 8002), self.calls(world))
        self.assertTrue(w4.board(window).model["model_view"])

    def test_a_weapon_is_dressed_on_the_players_body(self):
        world, window = self.world()
        world.game.answer("player", "GetRace", lambda: 3)
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.assertIn(("Select", "wiki", 3), self.calls(world))
        self.assertIn(("SetParts", "wiki", 0, SWORD, 0, 0), self.calls(world))

    def test_a_race_the_item_excludes_picks_the_first_allowed_race(self):
        world, window = self.world()
        world.game.answer("player", "GetRace", lambda: 0)
        world.game.answer("item", "IsAntiFlag", lambda f: f == 1)  # no warriors
        with world.game, w4.quiet():
            window.Open()
            window.open_item(SWORD)
        self.assertIn(("Select", "wiki", 1), self.calls(world))

    def test_a_pet_shows_its_item_value3_race(self):
        world, window = self.world()
        data = world.m("nui_wiki_data")
        pet = sorted(data.COSTUME_PETS)[0]
        world.game.answer("item", "GetValue", lambda i: 34001 if i == 3 else 0)
        with world.game, w4.quiet():
            window.Open()
            window.open_item(pet)
        self.assertIn(("Select", "wiki", 34001), self.calls(world))
        self.assertFalse([c for c in self.calls(world) if c[0] == "SetParts"])

    def test_a_wing_is_icon_only(self):
        world, window = self.world()
        data = world.m("nui_wiki_data")
        wing = sorted(data.COSTUME_WINGS)[0]
        with world.game, w4.quiet():
            window.Open()
            window.open_item(wing)
        self.assertFalse([c for c in self.calls(world) if c[0] == "Select" and c[1] == "wiki"])
        self.assertFalse(w4.board(window).model["model_view"])

    def test_a_race_the_client_cannot_make_falls_back_to_the_icon(self):
        world, window = self.world()
        world.game.modules["modelpreview"].Select = lambda name, race: False
        with world.game, w4.quiet():
            window.Open()
            window.OpenMob(8002)
        self.assertFalse(w4.board(window).model["model_view"])

    def test_hiding_stops_the_previews(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.OpenMob(8002)
            window.Hide()
        self.assertIn(("Show", "wiki", False), self.calls(world))

    def test_hover_shows_the_second_preview_and_stops_it(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
            window.search("wolf")
            window.over_row(0)
        self.assertIn(("Select", "wiki_hover", 8002), self.calls(world))
        self.assertTrue(w4.board(window).model["hover_view"])
        with world.game, w4.quiet():
            window.out_row()
        self.assertFalse(w4.board(window).model["hover_view"])
        self.assertIn(("Show", "wiki_hover", False), self.calls(world))


class Lifecycle(WikiTest):
    def test_hide_and_show_before_init(self):
        world, window = self.world()
        cls = type(window)
        with world.game, w4.quiet():
            bare = cls.__new__(cls)
            bare.nui_begin()
            bare.Hide()
            bare.Show()
            bare.nui_discard()

    def test_the_fixture_has_every_model_key(self):
        world, window = self.world()
        with world.game, w4.quiet():
            window.Open()
        self.assertEqual(set(w4.fixture_keys(window, "wiki")), set(w4.board(window).model))

    def test_nothing_runs_per_frame(self):
        world, window = self.world()
        self.assertIsNone(type(window).OnUpdate)

    def test_the_answer_handler_reaches_the_interface(self):
        source = open(os.path.join(ROOT, "game.py"), encoding="utf-8").read()
        node = next(n for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.FunctionDef) and n.name == "BINARY_WikiAnswer")
        scope = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "game.py", "exec"), scope)
        seen = []
        holder = types.SimpleNamespace(interface=types.SimpleNamespace(WikiAnswer=lambda *a: seen.append(a)))
        scope["BINARY_WikiAnswer"](holder, 0, 0, SWORD, 0, (), (), (), ())
        self.assertEqual(seen, [(0, 0, SWORD, 0, (), (), (), ())])

    def test_unavailable_window_is_a_quiet_stand_in(self):
        import importlib.util as util
        spec = util.spec_from_file_location("uiwiki", os.path.join(ROOT, "uiwiki.py"))
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        window = module.UnavailableWindow()
        window.Hide()
        window.Toggle()
        window.OpenItem(1)
        window.OpenMob(1)
        window.WikiAnswer(0, 0, 1, 0, (), (), (), ())
        self.assertFalse(window.IsShow())


class SyswikiLink(unittest.TestCase):
    """OLD's chat link syswiki:<kind>:<ident>[?y=NNN] (interfaceModule.py:1154)
    opens item and mob pages in the browser."""

    def method(self):
        source = open(os.path.join(ROOT, "interfacemodule.py"), encoding="utf-8").read()
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Interface")
        node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__OpenWikiLink")
        scope = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "interfacemodule.py", "exec"), scope)
        return scope["__OpenWikiLink"]

    def test_item_and_mob_links_open_their_pages(self):
        called = []
        holder = types.SimpleNamespace(OpenWikiItem=lambda v: called.append(("item", v)),
                                       OpenWikiMob=lambda v: called.append(("mob", v)),
                                       OpenWikiLink=lambda k, i: called.append(("hook", k, i)),
                                       OpenWikiPage=lambda p: called.append(("page", p)))
        method = self.method()
        method(holder, "item", "19")
        method(holder, "mob", "8002")
        method(holder, "page", "guide")
        method(holder, "item", "x")
        # Since round 3 a page link goes to OpenWikiPage (NOVA-139's text
        # pages), and any other kind to the OpenWikiLink hook.
        self.assertEqual(called, [("item", 19), ("mob", 8002), ("page", "guide")])


if __name__ == "__main__":
    unittest.main()
