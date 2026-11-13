"""Tests of the NovaUI dungeon manager, direction D "Bestiary" (assets/root/nui_dungeon_timer.py),
its ready notice and the dungeon ranking (nui_dungeon_notice.py, nui_dungeon_rank.py; NOVA-25).

The deck of boss cards, the hide control, the merged drops grid with its filters, Run and
Practice and the Wiki button are NovaUI's; the Teleport, the ranking commands, the ticket's
tooltip and the hidden-dungeon rule (HIDDEN_DUNGEONS, session and level) stay legacy's code in
uitimerwindow.py. The ready notice and the ranking run as before, and the wiring is pinned."""
import ast
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dungeon_timer_support as dts  # noqa: E402
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

WINDOWS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "nui", "nui", "windows")
NEW_DUNGEONS = [0, 1, 2, 3, 5, 6]


def opened(nui_on=True, preview=False, select_ok=True):
    world = dts.World(nui_on, preview=preview)
    if preview and not select_ok:
        world.game.modules["modelpreview"].Select = lambda name, race: 0
    rank = world.rank()
    window = world.timer()
    world.game.state.now = 100.0
    with world.game, w4.quiet():
        window.Open()
    world.game.state.now = 110.0
    return world, window, rank


def press(world, window, event, *args):
    with world.game, w4.quiet():
        return w4.press(window, event, *args)


def model(window):
    return w4.board(window).model


def card(window, idx):
    return next(c for c in model(window)["cards"] if c["idx"] == idx)


def slots(window):
    return dict((c["idx"], c["slot"]) for c in model(window)["cards"])


class Deck(unittest.TestCase):
    def test_open_shows_every_dungeon_in_order_with_the_first_in_front(self):
        world, window, _ = opened()
        self.assertEqual([c["idx"] for c in model(window)["cards"]], NEW_DUNGEONS)
        self.assertEqual(slots(window), {0: "c", 1: "r1", 2: "r2", 3: "r3", 5: "l2", 6: "l1"})
        self.assertEqual(model(window)["selected"], 0)
        self.assertEqual((card(window, 0)["title"], card(window, 0)["level"], card(window, 0)["mono"]),
                         ("Demon Tower", "Lv 75-105", "DT"))
        self.assertEqual(card(window, 5)["mono"], "NE")

    def test_a_press_on_a_side_card_selects_it_and_the_deck_turns(self):
        world, window, _ = opened()
        press(world, window, "card_press", 2, 0)
        self.assertEqual(model(window)["selected"], 2)
        self.assertEqual(model(window)["name"], "Devil`s Catacomb")
        self.assertEqual(slots(window), {2: "c", 3: "r1", 5: "r2", 6: "r3", 0: "l2", 1: "l1"})

    def test_the_arrows_select_the_neighbors_and_wrap(self):
        world, window, _ = opened()
        press(world, window, "arrow_press", "prev", 0)
        self.assertEqual(model(window)["selected"], 6, "before the first is the last")
        press(world, window, "arrow_press", "next", 0)
        press(world, window, "arrow_press", "next", 0)
        self.assertEqual(model(window)["selected"], 1)

    def test_a_right_press_selects_nothing(self):
        world, window, _ = opened()
        press(world, window, "card_press", 2, 1)
        press(world, window, "arrow_press", "next", 1)
        self.assertEqual(model(window)["selected"], 0)

    def test_the_badge_reads_ready_then_the_clock(self):
        world, window, _ = opened()
        self.assertEqual((card(window, 5)["state"], card(window, 5)["end"]), ("ready", 0.0))
        with world.game:
            window.SetTimeLeft(5, 600)
            window.QuestTimeReady()
        self.assertEqual((card(window, 5)["state"], card(window, 5)["end"]), ("cd", 710.0))
        world.game.timestamp += 600
        with world.game, w4.quiet():
            w4.fire(window, "card_ready", 5)
        self.assertEqual((card(window, 5)["state"], card(window, 5)["end"]), ("ready", 0.0))

    def test_no_python_per_frame(self):
        world, window, rank = opened()
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(rank).OnUpdate)
        with world.game:
            window.UpdateTime()


class Bosses(unittest.TestCase):
    """One named preview per dungeon; only the visible cards' previews run."""

    def previews(self, world):
        return world.game.modules["modelpreview"].calls

    def test_each_visible_card_selects_and_shows_its_boss(self):
        world, window, _ = opened(preview=True)
        calls = self.previews(world)
        self.assertIn(("Select", "dungeon_boss_0", 1095), calls)
        self.assertIn(("Show", "dungeon_boss_0", True), calls)
        self.assertIn(("Select", "dungeon_boss_5", window.nui_race(5)), calls)
        self.assertEqual([c["view"] for c in model(window)["cards"]], [True, True, True, False, True, True],
                         "the card behind the deck has no view")

    def test_the_card_behind_the_deck_has_no_preview_until_it_comes_into_view(self):
        world, window, _ = opened(preview=True)
        self.assertFalse([c for c in self.previews(world) if c[1] == "dungeon_boss_3"])
        press(world, window, "arrow_press", "next", 0)
        self.assertIn(("Select", "dungeon_boss_3", window.nui_race(3)), self.previews(world))
        self.assertEqual(card(window, 3)["view"], True)

    def test_a_select_is_not_repeated_while_the_deck_turns(self):
        world, window, _ = opened(preview=True)
        before = len([c for c in self.previews(world) if c[0] == "Select"])
        press(world, window, "arrow_press", "next", 0)
        selects = [c for c in self.previews(world) if c[0] == "Select"]
        self.assertEqual(len(selects), before + 1, "only the card that came into view is new")
        self.assertEqual(selects[-1][1], "dungeon_boss_3")

    def test_closing_hides_every_preview_and_keeps_it_for_the_next_open(self):
        # NOVA-256: r46 cleared them at each close and made the five bosses again at each open.
        world, window, _ = opened(preview=True)
        selects = len([c for c in self.previews(world) if c[0] == "Select"])
        with world.game, w4.quiet():
            w4.press(window, "close_press", 0)
        self.assertFalse([c for c in self.previews(world) if c[0] == "Clear"], "nothing cleared at a close")
        hidden = [c[1] for c in self.previews(world)[-5:] if c[0] == "Show" and c[2] is False]
        self.assertEqual(sorted(hidden), ["dungeon_boss_%d" % i for i in (0, 1, 2, 5, 6)])
        with world.game, w4.quiet():
            window.Open()
        self.assertEqual(len([c for c in self.previews(world) if c[0] == "Select"]), selects, "no boss asked for again")
        self.assertIn(("Show", "dungeon_boss_0", True), self.previews(world)[-10:])
        self.assertEqual([c["view"] for c in model(window)["cards"]], [True, True, True, False, True, True])

    def test_destroy_clears_every_preview_that_was_made(self):
        world, window, _ = opened(preview=True)
        with world.game, w4.quiet():
            w4.press(window, "close_press", 0)
        closed = len(self.previews(world))
        with world.game, w4.quiet():
            window.Destroy()
        cleared = [c for c in self.previews(world)[closed:] if c[0] == "Clear" and c[1].startswith("dungeon_boss_")]
        self.assertEqual(sorted(c[1] for c in cleared), ["dungeon_boss_%d" % i for i in (0, 1, 2, 5, 6)])

    def test_a_race_without_a_model_shows_the_monogram(self):
        world, window, _ = opened(preview=True, select_ok=False)
        self.assertEqual([c["view"] for c in model(window)["cards"]], [False] * 6)
        self.assertEqual(card(window, 0)["mono"], "DT")

    def test_a_dungeon_without_a_boss_selects_no_model(self):
        # Race 0 is the warrior for the client now (r39), no longer "no model".
        world = dts.World(True, preview=True)
        world.rank()
        window = world.timer()
        real = window.nui_race
        window.nui_race = lambda idx: 0 if idx == 5 else real(idx)
        world.game.state.now = 100.0
        with world.game, w4.quiet():
            window.Open()
        self.assertFalse([c for c in self.previews(world) if c[1] == "dungeon_boss_5"], "no warrior on the card")
        self.assertEqual(card(window, 5)["view"], False)
        self.assertIn(("Select", "dungeon_boss_0", 1095), self.previews(world))

    def test_a_client_without_previews_still_opens(self):
        world, window, _ = opened()
        self.assertEqual([c["view"] for c in model(window)["cards"]], [False] * 6)

    def still(self, world):
        """Each preview's latest SetStill."""
        out = {}
        for c in self.previews(world):
            if c[0] == "SetStill":
                out[c[1]] = c[2]
        return out

    def test_only_the_front_card_turns_the_side_cards_keep_their_picture(self):
        # Live on r38: five bosses updated, deformed and drawn every frame.
        world, window, _ = opened(preview=True)
        front = model(window)["selected"]
        still = self.still(world)
        self.assertEqual(still.pop("dungeon_boss_%d" % front), False, "the front card turns")
        self.assertEqual(sorted(still), ["dungeon_boss_%d" % i for i in (0, 1, 2, 5, 6) if i != front])
        self.assertTrue(all(still.values()), "the side cards are still")
        press(world, window, "arrow_press", "next", 0)
        now = model(window)["selected"]
        self.assertNotEqual(now, front)
        still = self.still(world)
        self.assertEqual(still["dungeon_boss_%d" % now], False, "the new front card turns")
        self.assertEqual(still["dungeon_boss_%d" % front], True, "the old one keeps its picture")

    def test_a_client_without_still_previews_still_turns_every_card(self):
        world, window, _ = opened(preview=True)
        stub = type(world.game.modules["modelpreview"])
        set_still = stub.SetStill
        del stub.SetStill
        try:
            press(world, window, "arrow_press", "next", 0)
            self.assertEqual(card(window, 3)["view"], True)
        finally:
            stub.SetStill = set_still

    def test_the_old_single_preview_is_not_used(self):
        world, window, _ = opened(preview=True)
        self.assertFalse([c for c in self.previews(world) if c[1] == "dungeon_boss"])


class BackgroundBosses(unittest.TestCase):
    """NOVA-256: no boss is made in the open's frame. The previews are background previews
    (modelpreview.SetBackground): Select answers at once, the client makes each model over the
    next steps, front card first, and a card shows its monogram until its own boss is made."""

    def previews(self, world):
        return world.game.modules["modelpreview"]

    def poll(self, world, window):
        """The previews_check clock's end, as the board sends it."""
        self.assertGreater(model(window)["previews_check"], 0.0, "the clock runs while a boss loads")
        with world.game, w4.quiet():
            w4.fire(window, "previews_ready")

    def views(self, window):
        return dict((c["idx"], c["view"]) for c in model(window)["cards"])

    def test_every_boss_is_asked_as_a_background_preview_and_none_shows_at_the_open(self):
        world, window, _ = opened(preview="background")
        calls = self.previews(world).calls
        selects = [c[1] for c in calls if c[0] == "Select"]
        self.assertEqual(selects, ["dungeon_boss_%d" % i for i in (0, 1, 6, 2, 5)], "the front card first, then the nearest")
        for name in selects:
            self.assertLess(calls.index(("SetBackground", name, True)), calls.index(("Select", name, window.nui_race(int(name[-1])))))
        self.assertEqual(self.views(window), {0: False, 1: False, 2: False, 3: False, 5: False, 6: False}, "monograms while they load")
        self.assertGreater(model(window)["previews_check"], 0.0)

    def test_each_card_shows_its_boss_once_the_client_made_it(self):
        world, window, _ = opened(preview="background")
        mp = self.previews(world)
        self.assertEqual(mp.step(), "dungeon_boss_0")
        self.poll(world, window)
        self.assertEqual(self.views(window), {0: True, 1: False, 2: False, 3: False, 5: False, 6: False})
        self.assertGreater(model(window)["previews_check"], 0.0, "it looks again while the others load")
        while mp.step():
            pass
        self.poll(world, window)
        self.assertEqual(self.views(window), {0: True, 1: True, 2: True, 3: False, 5: True, 6: True})
        self.assertEqual(model(window)["previews_check"], 0.0, "no clock once every shown boss is made")
        selects = [c for c in mp.calls if c[0] == "Select"]
        self.assertEqual(len(selects), 5, "a boss is asked for once")

    def test_a_close_keeps_the_bosses_and_a_reopen_shows_them_at_once(self):
        world, window, _ = opened(preview="background")
        mp = self.previews(world)
        while mp.step():
            pass
        self.poll(world, window)
        with world.game, w4.quiet():
            w4.press(window, "close_press", 0)
        self.assertFalse([c for c in mp.calls if c[0] == "Clear"])
        self.assertFalse(any(mp.shown.values()), "every boss hidden")
        with world.game, w4.quiet():
            window.Open()
        self.assertEqual(self.views(window), {0: True, 1: True, 2: True, 3: False, 5: True, 6: True})
        self.assertEqual(len([c for c in mp.calls if c[0] == "Select"]), 5, "none asked again")
        self.assertEqual(model(window)["previews_check"], 0.0)

    def test_a_boss_still_loading_at_the_close_comes_at_the_next_open(self):
        world, window, _ = opened(preview="background")
        mp = self.previews(world)
        mp.step()
        with world.game, w4.quiet():
            w4.press(window, "close_press", 0)
        self.assertIsNone(mp.step(), "a hidden card's boss waits")
        with world.game, w4.quiet():
            window.Open()
        self.assertEqual(self.views(window)[0], True)
        self.assertEqual(self.views(window)[1], False)
        while mp.step():
            pass
        self.poll(world, window)
        self.assertEqual(self.views(window), {0: True, 1: True, 2: True, 3: False, 5: True, 6: True})

    def test_a_card_never_shows_another_dungeon_s_boss(self):
        world, window, _ = opened(preview="background")
        mp = self.previews(world)
        while mp.step():
            pass
        mp.models["dungeon_boss_2"] = 1095  # what a wrong model would answer
        self.poll(world, window)
        views = self.views(window)
        self.assertFalse(views[2], "a model of another race is never shown")
        self.assertTrue(views[0])

    def test_a_boss_that_makes_no_model_keeps_the_monogram_and_is_not_asked_again(self):
        world = dts.World(True, preview="background")
        world.rank()
        window = world.timer()
        world.game.modules["modelpreview"].fail.add(window.nui_race(1))
        world.game.state.now = 100.0
        with world.game, w4.quiet():
            window.Open()
        mp = self.previews(world)
        while mp.step():
            pass
        self.poll(world, window)
        self.assertEqual(self.views(window), {0: True, 1: False, 2: True, 3: False, 5: True, 6: True})
        self.assertTrue(card(window, 1)["mono"], "the card shows its monogram")
        press(world, window, "arrow_press", "next", 0)
        self.assertEqual(len([c for c in mp.calls if c[0] == "Select" and c[1] == "dungeon_boss_1"]), 1)

    def test_a_turn_brings_in_a_card_whose_boss_loads_meanwhile(self):
        world, window, _ = opened(preview="background")
        mp = self.previews(world)
        while mp.step():
            pass
        self.poll(world, window)
        press(world, window, "arrow_press", "next", 0)
        self.assertEqual(card(window, 3)["slot"], "r2")
        self.assertFalse(card(window, 3)["view"], "its monogram while it loads")
        self.assertTrue(card(window, 1)["view"])
        self.assertEqual(mp.step(), "dungeon_boss_3")
        self.poll(world, window)
        self.assertTrue(card(window, 3)["view"])

    def test_the_board_is_loaded_with_the_window_and_kept_hidden_and_empty(self):
        world = dts.World(True, preview="background")
        world.rank()
        window = world.timer()
        kept = window.demand.kept()
        self.assertIsNotNone(kept, "the window's making keeps its board")
        self.assertFalse(kept.is_visible())
        world.game.state.now = 100.0
        with world.game, w4.quiet():
            window.Open()
        self.assertIs(w4.board(window), kept, "the open loads no document")
        self.assertTrue(model(window)["cards"])
        with world.game, w4.quiet():
            w4.press(window, "close_press", 0)
        self.assertIs(window.demand.kept(), kept)
        for key in ("cards", "drops_items", "filter_chips"):
            self.assertEqual(kept.model[key], [], key)
        for key in ("go_end", "drops_retry", "drops_timeout", "previews_check"):
            self.assertEqual(kept.model[key], 0.0, key)
        with world.game, w4.quiet():
            window.Destroy()
        self.assertFalse(kept._doc, "Destroy unloads it")

    def test_hide_before_init_and_destroy_twice_survive(self):
        # ui.Window.__init__ calls Hide before __init__ has set anything (the r34 trap).
        world = dts.World(True, preview="background")
        with world.game:
            import nui_dungeon_timer
            bare = nui_dungeon_timer.TimerWindow.__new__(nui_dungeon_timer.TimerWindow)
            bare._TimerWindow__HideBossModel()
            bare._clear_previews()

    def test_a_late_look_while_hidden_runs_no_clock(self):
        world, window, _ = opened(preview="background")
        board = w4.board(window)
        with world.game, w4.quiet():
            w4.press(window, "close_press", 0)
            board.fire("previews_ready")
        self.assertEqual(board.model["previews_check"], 0.0)
        self.assertEqual(window._state["previews_check"], 0.0)


class Hiding(unittest.TestCase):
    def test_none_hidden_at_the_start(self):
        world, window, _ = opened()
        self.assertEqual(model(window)["chip"], "")
        self.assertFalse(model(window)["chip_on"])

    def test_hiding_the_front_card_leaves_the_deck_and_moves_on(self):
        world, window, _ = opened()
        press(world, window, "arrow_press", "next", 0)
        press(world, window, "hide_press", 0)
        self.assertEqual(model(window)["selected"], 2, "the next card takes the front")
        self.assertEqual(card(window, 1)["slot"], "out")
        self.assertEqual(model(window)["chip"], "1 hidden")
        self.assertEqual(window.visible_indices, [0, 2, 3, 5, 6])

    def test_hiding_keeps_the_legacy_rule(self):
        world, window, _ = opened()
        press(world, window, "hide_press", 0)
        module = world.timer_module
        self.assertEqual(module.SESSION_HIDDEN[0], 1)
        self.assertGreater(module.HIDDEN_DUNGEONS[0], 0, "hidden at the player's level")

    def test_the_last_visible_dungeon_cannot_be_hidden(self):
        world, window, _ = opened()
        for _i in range(5):
            press(world, window, "hide_press", 0)
        self.assertEqual(len(window.visible_indices), 1)
        self.assertTrue(model(window)["hide_locked"])
        last = window.index
        press(world, window, "hide_press", 0)
        self.assertEqual(window.visible_indices, [last], "a press that slips through hides nothing")

    def test_the_chip_shows_the_hidden_cards_dashed_and_becomes_done(self):
        world, window, _ = opened()
        press(world, window, "hide_press", 0)
        press(world, window, "chip_press", 0)
        self.assertTrue(model(window)["chip_on"])
        self.assertEqual(model(window)["chip"], "Done")
        hidden = card(window, 0)
        self.assertNotEqual(hidden["slot"], "out")
        self.assertEqual((hidden["hidden"], hidden["state"]), (True, "hidden"))
        press(world, window, "chip_press", 0)
        self.assertEqual(model(window)["chip"], "1 hidden")
        self.assertEqual(card(window, 0)["slot"], "out")

    def test_unhiding_from_the_shown_deck(self):
        world, window, _ = opened()
        press(world, window, "hide_press", 0)
        press(world, window, "chip_press", 0)
        press(world, window, "card_press", 0, 0)
        self.assertEqual(window.index, 0)
        self.assertTrue(model(window)["hero_hidden"])
        press(world, window, "hide_press", 0)
        self.assertFalse(card(window, 0)["hidden"])
        self.assertEqual(world.timer_module.SESSION_HIDDEN[0], 0)
        self.assertEqual(world.timer_module.HIDDEN_DUNGEONS[0], 0)
        self.assertEqual(window.index, 0, "unhiding keeps the front card")
        self.assertEqual(model(window)["chip"], "Done", "stays until Done is pressed")

    def test_a_hidden_clock_is_kept(self):
        world, window, _ = opened()
        with world.game:
            window.SetTimeLeft(1, 600)
            window.QuestTimeReady()
        press(world, window, "arrow_press", "next", 0)
        press(world, window, "hide_press", 0)
        self.assertEqual(window.GetEndTime(1), world.game.timestamp + 600)


class Details(unittest.TestCase):
    def test_the_front_cards_details(self):
        world, window, _ = opened()
        m = model(window)
        self.assertEqual((m["name"], m["boss"]), ("Demon Tower", "Boss: mob 1095"))
        self.assertEqual((m["level"], m["group"], m["cooldown"]), ("Lv 75-105", "No", "0 Mins"))
        self.assertTrue(m["ticket_none"], "no ticket reads None")

    def test_the_ticket_is_the_real_slot_with_its_tooltip(self):
        world, window, _ = opened()
        world.timer_module.DESCRIPTION[1][5] = 30750
        with world.game, w4.quiet():
            window.SetDescription(1)
            w4.fire(window, "ticket_over")
            w4.fire(window, "ticket_out")
        self.assertEqual(model(window)["ticket"]["icon"], "/icon/item/30750.tga")
        self.assertFalse(model(window)["ticket_none"])
        self.assertEqual([c[0] for c in world.tooltip.calls], ["SetItemToolTip", "HideToolTip"])

    def test_a_ticketless_dungeon_after_a_ticket_reads_none_again(self):
        world, window, _ = opened()
        world.timer_module.DESCRIPTION[1][5] = 30750
        with world.game, w4.quiet():
            window.SetDescription(1)
            window.SetDescription(2)
        self.assertTrue(model(window)["ticket_none"])
        self.assertEqual(model(window)["ticket"]["kind"], "")

    def test_the_notice_box_is_per_dungeon(self):
        world, window, _ = opened()
        press(world, window, "notice_press", 0)
        self.assertTrue(model(window)["notice"])
        press(world, window, "arrow_press", "next", 0)
        self.assertFalse(model(window)["notice"])

    def test_the_ranking_buttons_send_legacys_commands(self):
        world, window, rank = opened()
        for name in ("time", "overall", "damage"):
            press(world, window, "button_press", name, 0)
        self.assertEqual(world.chat_commands(), ["/rank_dungeon 0 0", "/rank_dungeon 1 0", "/rank_dungeon 2 0"])
        self.assertTrue(rank.IsShow())


class Wiki(unittest.TestCase):
    def test_without_the_wiki_the_button_is_off_and_sends_nothing(self):
        world, window, _ = opened()
        self.assertFalse(model(window)["wiki_on"])
        press(world, window, "wiki_press", 0)
        self.assertEqual(world.chat_commands(), [])

    def test_with_the_wiki_it_opens_the_boss(self):
        world, window, _ = opened()
        opened_with = []
        world.interface.OpenWikiMob = lambda vnum: opened_with.append(vnum) or True
        world.interface.wndWiki = object()
        with world.game, w4.quiet():
            window.Open()
        self.assertTrue(model(window)["wiki_on"])
        press(world, window, "wiki_press", 0)
        self.assertEqual(opened_with, [1095])

    def test_the_real_interface_method_reaches_the_wiki_windows_open_mob(self):
        """The button once both branches are merged: interfacemodule's real OpenWikiMob, with the
        window's OpenMob behind it (nui_wiki.WikiWindow, read from its source so it stays real)."""
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "root")
        source = open(os.path.join(root, "interfacemodule.py"), encoding="utf-8").read()
        interface_class = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "Interface")
        node = next(n for n in interface_class.body if isinstance(n, ast.FunctionDef) and n.name == "OpenWikiMob")
        scope = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "interfacemodule.py", "exec"), scope)
        wiki_source = open(os.path.join(root, "nui_wiki.py"), encoding="utf-8").read()
        wiki_class = next(n for n in ast.parse(wiki_source).body if isinstance(n, ast.ClassDef) and n.name == "WikiWindow")
        self.assertIn("OpenMob", [n.name for n in wiki_class.body if isinstance(n, ast.FunctionDef)])

        world, window, _ = opened()
        opened_with = []
        world.interface.wndWiki = types.SimpleNamespace(OpenMob=lambda vnum: opened_with.append(vnum) or True)
        world.interface.OpenWikiMob = types.MethodType(scope["OpenWikiMob"], world.interface)
        with world.game, w4.quiet():
            window.Open()
        self.assertTrue(model(window)["wiki_on"], "the button enables once the wiki is merged")
        press(world, window, "wiki_press", 0)
        self.assertEqual(opened_with, [1095])


class Drops(unittest.TestCase):
    def filled(self):
        world, window, _ = opened()
        module = world.timer_module
        with world.game, w4.quiet():
            module.add_drop(0, 2598, 1, 27001, 3, 800000)   # guaranteed
            module.add_drop(0, 2598, 1, 27002, 1, 500000)   # common
            module.add_drop(0, 2598, 1, 27003, 1, 100000)   # rare
            module.add_drop(0, 2597, 2, 27002, 2, 100000)   # the same vnum, rare beats common
            module.add_drop(0, 2597, 2, 30190, 1, 900000)   # guaranteed
            module.add_drop(0, 2597, 2, 27001, 9, 100000)   # guaranteed stays
            window.refreshMobList()
        return world, window

    def test_every_mob_merged_one_grid_best_band_kept(self):
        world, window = self.filled()
        m = model(window)
        self.assertEqual(m["drops_state"], "ready")
        self.assertEqual([(i["vnum"], i["band"], i["count"]) for i in m["drops_items"]],
                         [(27001, "guaranteed", "3"), (30190, "guaranteed", ""),
                          (27002, "rare", "2"), (27003, "rare", "")],
                         "guaranteed, common then rare; 27002 is rare, its better band")
        self.assertEqual(m["drops_count"], "4")

    def test_the_filter_chips_count_and_filter(self):
        world, window = self.filled()
        m = model(window)
        self.assertEqual([(f["band"], f["n"], f["on"]) for f in m["filter_chips"]],
                         [("guaranteed", 2, False), ("common", 0, False), ("rare", 2, False)])
        press(world, window, "filter_press", "rare", 0)
        m = model(window)
        self.assertEqual([i["vnum"] for i in m["drops_items"]], [27002, 27003])
        self.assertEqual(m["drops_count"], "2 of 4")
        self.assertEqual([f["on"] for f in m["filter_chips"]], [False, False, True])
        press(world, window, "filter_press", "rare", 0)
        self.assertEqual(model(window)["drops_count"], "4", "pressing the active chip clears it")

    def test_a_cell_gives_the_tooltip_of_the_item_it_shows(self):
        world, window = self.filled()
        press(world, window, "filter_press", "rare", 0)
        with world.game, w4.quiet():
            w4.fire(window, "drop_over", 1)
            w4.fire(window, "drop_out")
        self.assertEqual([c[:2] for c in world.tooltip.calls], [("SetItemToolTip", 27003), ("HideToolTip",)])

    def test_loading_empty_and_the_retry_inside_the_servers_second(self):
        world, window, _ = opened()
        self.assertEqual(model(window)["drops_state"], "loading")
        self.assertIn((0,), world.drop_requests())
        with world.game, w4.quiet():
            w4.press(window, "arrow_press", "next", 0)
            w4.press(window, "arrow_press", "next", 0)
        self.assertEqual(model(window)["drops_retry"] > 0, True, "a second request inside the second: retried")
        asked = len(world.drop_requests())
        world.game.state.now = 112.0
        with world.game, w4.quiet():
            w4.fire(window, "drops_retry")
        self.assertEqual(len(world.drop_requests()), asked + 1)
        self.assertEqual(world.drop_requests()[-1], (2,))
        with world.game, w4.quiet():
            w4.fire(window, "drops_timeout")
        self.assertEqual(model(window)["drops_state"], "empty")
        self.assertEqual(model(window)["drops_count"], "0")

    def test_a_second_visit_asks_nothing(self):
        world, window, _ = opened()
        before = len(world.drop_requests())
        with world.game, w4.quiet():
            world.game.state.now = 120.0
            w4.press(window, "arrow_press", "next", 0)
            w4.press(window, "arrow_press", "prev", 0)
        self.assertEqual(len([r for r in world.drop_requests() if r == (0,)]), 1)
        self.assertGreater(len(world.drop_requests()), before)


class RunAndPractice(unittest.TestCase):
    def test_run_is_teleport_when_ready(self):
        world, window, _ = opened()
        m = model(window)
        self.assertEqual((m["mode"], m["go_label"], m["go_end"], m["go_locked"]), ("run", "Teleport", 0.0, False))
        press(world, window, "go_press", 0)
        self.assertEqual(world.chat_commands(), ["/warp_dungeon 0"])
        self.assertIsNone(w4.board(window), "teleport closes the window, as legacy")

    def test_run_is_locked_with_the_live_clock_on_cooldown(self):
        world, window, _ = opened()
        with world.game:
            window.SetTimeLeft(0, 600)
            window.QuestTimeReady()
        m = model(window)
        self.assertEqual(m["go_label"], "Ready in")
        self.assertEqual((m["go_end"], m["go_locked"]), (710.0, True))
        press(world, window, "go_press", 0)
        self.assertEqual(world.chat_commands(), [], "the handler checks too, past a stale model")

    def test_practice_sends_the_command_whatever_the_cooldown(self):
        world, window, _ = opened()
        with world.game:
            window.SetTimeLeft(2, 600)
            window.QuestTimeReady()
        press(world, window, "card_press", 2, 0)
        press(world, window, "seg_press", "practice", 0)
        m = model(window)
        self.assertEqual((m["mode"], m["go_label"], m["go_end"], m["go_locked"]),
                         ("practice", "Start practice", 0.0, False))
        press(world, window, "go_press", 0)
        self.assertEqual(world.chat_commands(), ["/practice_dungeon 2"])
        self.assertIsNone(w4.board(window), "the fight starts: the window closes, as the teleport")

    def test_practice_clears_the_filter_and_the_mode_comes_back(self):
        world, window, _ = opened()
        press(world, window, "seg_press", "practice", 0)
        self.assertEqual(model(window)["mode"], "practice")
        press(world, window, "seg_press", "run", 0)
        self.assertEqual(model(window)["mode"], "run")

    def test_the_window_opens_on_run(self):
        world, window, _ = opened()
        press(world, window, "seg_press", "practice", 0)
        with world.game, w4.quiet():
            window.Close()
            window.Open()
        self.assertEqual(model(window)["mode"], "run")


class Notices(unittest.TestCase):
    def test_a_checked_dungeon_announces_once_and_the_box_goes(self):
        world, window, _ = opened(True)
        notices = window.nui_notices
        with world.game, w4.quiet():
            window.QuestTimeReady()
            w4.press(window, "card_press", 2, 0)
            w4.press(window, "notice_press", 0)
            self.assertTrue(w4.board(window).model["notice"])
            window.SetTimeLeft(2, 30)
            window.SetTimeLeft(3, 30)
        self.assertEqual([t["idx"] for t in notices.timers], [2], "only the checked dungeon's clock")
        self.assertIsNotNone(notices.board)
        with world.game:
            notices.board.fire("timer_end", 2)
        self.assertEqual([t["title"] for t in notices.toasts], ["Devil`s Catacomb"])
        self.assertTrue(window.announced[2])
        with world.game:
            notices.board.fire("toast_end", notices.toasts[0]["key"])
        self.assertIsNone(notices.board, "the document goes with the last box")

    def test_unchecking_stops_the_watch(self):
        world, window, _ = opened(True)
        with world.game, w4.quiet():
            window.QuestTimeReady()
            w4.press(window, "card_press", 6, 0)
            w4.press(window, "notice_press", 0)
            window.SetTimeLeft(6, 30)
            w4.press(window, "notice_press", 0)
        self.assertEqual(window.nui_notices.timers, [])
        self.assertIsNone(window.nui_notices.board)


class Rank(unittest.TestCase):
    def test_rows_own_title_and_loading(self):
        for nui_on in (False, True):
            world = dts.World(nui_on)
            rank = world.rank()
            world.game.dungeon_rank[:] = [[1, "Alice", 3725], [2, "Bob", 4000]]
            with world.game:
                world.interface.OpenDungeonRank()
                if nui_on:
                    self.assertTrue(w4.board(rank).model["loading"])
                rank.SetPersonalDungeonRank("2", "Bob", "4000", "0")
                rank.RefreshDungeonRank(0, 5)
            texts = [(i.rank.text if not nui_on else i.rank, i.name.text if not nui_on else i.name,
                      i.count.text if not nui_on else i.count) for i in rank.rankImages]
            if not nui_on:
                legacy = texts
            else:
                self.assertEqual(texts, legacy)
                model = w4.board(rank).model
                self.assertFalse(model["loading"])
                self.assertEqual(model["title"], "Nemeres Time Ranking")
                self.assertEqual(model["rows"][0], {"rank": "1", "name": "Alice", "count": "1:02:05"})
                self.assertEqual(model["own"], {"rank": "2", "name": "Bob", "count": "1:06:40"})

    def test_walking_away_closes_it_once(self):
        world = dts.World(True)
        rank = world.rank()
        with world.game:
            rank.Open(1, 0)
            self.assertIsNotNone(world.game.w4["leave_range"].get("dungeon-rank"))
            self.assertEqual(world.game.w4["leave_range"]["dungeon-rank"]["range"], 1500)
            self.assertTrue(support.leave_range(world.game, "dungeon-rank"))
        self.assertFalse(rank.IsShow())
        self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState("dungeon-rank"))

    def test_close_x(self):
        world = dts.World(True)
        rank = world.rank()
        with world.game:
            rank.Open(2, 0)
        press(world, rank, "close_press", 0)
        self.assertFalse(rank.IsShow())


class Factory(unittest.TestCase):
    def test_flags_off_make_the_legacy_windows(self):
        world = dts.World(False)
        self.assertEqual(type(world.timer()).__module__, "uiTimerWindow")
        self.assertEqual(type(world.rank()).__module__, "uiDungeonRank")
        self.assertEqual(type(world.interface.wndTimer.wndDrops).__module__, "uiTimerWindow")

    def test_flags_on_make_the_facades(self):
        world = dts.World(True)
        self.assertEqual(type(world.timer()).__module__, "nui_dungeon_timer")
        self.assertEqual(type(world.rank()).__module__, "nui_dungeon_rank")
        self.assertEqual(type(world.interface.wndTimer.wndDrops).__module__, "nui_dungeon_drops")

    def test_every_fixture_has_every_model_key(self):
        world, window, rank = opened(True)
        cases = (("dungeon-timer", window.nui_model()), ("dungeon-rank", rank.nui_model()),
                 ("dungeon-drops", window.wndDrops.nui_model()),
                 ("dungeon-notice", window.nui_notices.model()))
        for name, model in cases:
            for file_name in sorted(os.listdir(os.path.join(WINDOWS, name))):
                if not file_name.endswith(".fixture.json"):
                    continue
                with open(os.path.join(WINDOWS, name, file_name), encoding="utf-8") as handle:
                    (fixture,) = json.load(handle).values()
                with self.subTest(fixture=file_name):
                    self.assertEqual(sorted(fixture), sorted(model))

    def test_the_board_is_d_not_the_old_layout(self):
        rml = open(os.path.join(WINDOWS, "dungeon-timer", "dungeon-timer.rml"), encoding="utf-8").read()
        for needle in ("dungeon-timer__card", "dungeon-timer__deck", "'model-dungeon-boss-' + c.idx"):
            self.assertIn(needle, rml)
        for gone in ("dungeon-timer__row", "dungeon-timer__desc", "drop_mob_press"):
            self.assertNotIn(gone, rml)

    def test_the_registration(self):
        world = dts.World(True)
        windows = world.m("nui_windows")
        ids = [window_id for window_id, _ in windows.WINDOWS]
        self.assertEqual(ids[-1], "maintenance")
        for window_id in ("dungeon-timer", "dungeon-drops", "dungeon-rank"):
            self.assertIs(dict(windows.WINDOWS)[window_id], True)
            self.assertIn(window_id, windows.GROUPS["dungeon"])
        self.assertEqual(windows.GROUPS["dungeon"], ("dungeon-timer", "dungeon-drops", "dungeon-rank"))
        self.assertIn(("dungeon-timer", ("dungeon-timer", "dungeon-notice")), windows.ON_DEMAND_DOCUMENTS)
        self.assertIn(("dungeon-drops", ("dungeon-drops",)), windows.ON_DEMAND_DOCUMENTS)
        self.assertIn(("dungeon-rank", ("dungeon-rank",)), windows.ON_DEMAND_DOCUMENTS)
        self.assertIn("dungeon-rank", world.m("nui_facade").LEAVE_RANGE_KEYS)

if __name__ == "__main__":
    unittest.main()
