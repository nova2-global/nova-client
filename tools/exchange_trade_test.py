"""Tests for the legacy client's 24-slot trade window (wave 4b, chunk C2;
NOVA-12): python3 -B -m unittest exchange_trade_test (from tools/).

The C++ half (CPythonExchange's 24 slots, exchange.GetRaceFrom* and
GetLevelFrom*) is tested in nova-client-src's userinterface_tests, the
server's 6 x 4 grid and the trade log in nova-server-src. Here
uiexchange.ExchangeDialog runs from its real uiscript over the Wave 4
stand-ins (nui_w4_world's World, every NovaUI window off; the exchange
module with 24 slots and C1's race and level getters stood in):
- the uiscript: two 6 x 4 grids, the faces, the name, the level, "You", the
  money and accept row under each grid, the history, inside the board;
- a refresh shows all 24 display slots of each side;
- the faces by race, the partner's name and level;
- the history: ready at the open, then a line for each accept and each
  take-back, with the time, the last three shown;
- an accepted side's slots are green;
- giving something for nothing asks first (OLD's three cases);
- every new key in all 17 locales, its format the English one's."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402
import extra_inventory_test as ext  # noqa: E402

SLOTS = 24
HELMET, GLAIVE, POTION = 12200, 3000, 27001
TIME = r"\[\d\d:\d\d:\d\d\]"
NEW_KEYS = {
    "interface": {"NEW_EXCHANGE_YOU": "You"},
    "game": {"NEW_EXCHANGE_YOU_READY": "%s You are ready to trade.", "NEW_EXCHANGE_YOU_ACCEPT": "%s You accept the trade.",
             "NEW_EXCHANGE_ACCEPT": "%s %s accept the trade.", "NEW_EXCHANGE_YOU_ABORT": "%s You abort the trade.",
             "NEW_EXCHANGE_ABORT": "%s %s abort the trade.", "NEW_EXCHANGE_LEVEL": "Lv. %d",
             "NEW_EXCHANGE_ALERT1": "You are giving things away for nothing in exchange,",
             "NEW_EXCHANGE_ALERT2": "and won't be able to get the Yang or items back."},
}


def stock(game):
    """A trade of 24 slots a side: the partner (Partner, a sura, level 37)
    offers a glaive at 23; the tester (an assassin) a helmet at 22."""
    ex = game.w4["exchange"]
    ex["self"] = [None] * SLOTS
    ex["target"] = [None] * SLOTS
    ex["target"][23] = {"vnum": GLAIVE, "count": 1}
    ex["self"][22] = {"vnum": HELMET, "count": 2}
    ex["target_name"] = "Partner"
    ex["target_level"] = 37
    ex["self_race"], ex["target_race"] = 5, 2
    game.elk = 5000000


class Trade(unittest.TestCase):
    def world(self, setup=stock):
        world = w4.World(False, setup=setup)
        game = world.game
        ex = game.w4["exchange"]
        exchange = game.modules["exchange"]
        exchange.EXCHANGE_ITEM_MAX_NUM = SLOTS
        # The client's 12 digits of yang in a trade (PythonPlayerModule.cpp, Q13).
        game.modules["player"].EXCHANGE_MONEY_DIGITS = 12
        support.define(exchange, "GetRaceFromSelf", lambda: ex.get("self_race", 0))
        support.define(exchange, "GetRaceFromTarget", lambda: ex.get("target_race", 0))
        window = world.make("exchange", "uiExchange", "ExchangeDialog", "nui_exchange.ExchangeDialog")
        with game, w4.quiet():
            window.LoadDialog()
            window.SetItemToolTip(world.tooltip)
        bases = window.slot_bases = {"owner": [], "target": []}
        for side, slots in (("owner", window.OwnerSlot), ("target", window.TargetSlot)):
            slots.SetSlotBaseImage = (lambda side: lambda *args: bases[side].append(args))(side)
        return world, window

    def run_in(self, world, fn, *args):
        with world.game, w4.quiet():
            return fn(*args)

    def open(self, world, window):
        self.run_in(world, window.OpenDialog)
        self.run_in(world, window.Refresh)

    def logs(self, window):
        return [line.GetText() for line in window.ExchangeLogLines]

    def test_the_uiscript_has_two_6_by_4_grids_and_olds_header_inside_the_board(self):
        world = w4.World(False)
        with world.game:
            window = lf.read_uiscript(os.path.join(lf.UISCRIPT, "exchangedialog.py"))["window"]
        board = lf.child(window, "board")
        for side in ("Owner", "Target"):
            grid = lf.child(window, side + "_Slot")
            self.assertEqual((grid["x_count"], grid["y_count"]), (6, 4))
            box = lf.child(window, side)
            self.assertGreaterEqual(box["height"], 4 * 32 + 4 + 21)
            self.assertLessEqual(box["x"] + 6 * 32, board["width"] - 8)
            self.assertLessEqual(box["y"] + box["height"], lf.child(window, "ExchangeLogs")["y"])
        self.assertGreaterEqual(lf.child(window, "Owner")["x"], lf.child(window, "Target")["x"] + 6 * 32)
        for name in ("FaceOwner_Image", "FaceOwner_Slot", "FaceTarget_Image", "FaceTarget_Slot", "target_NameText",
                     "target_LvText", "Owner_Money_Value", "Target_Money_Value", "Owner_Accept_Light",
                     "Target_Accept_Light", "Owner_Accept_Button", "TitleName"):
            lf.child(window, name)
        self.assertEqual(lf.child(window, "own_Text")["text"], "NEW_EXCHANGE_YOU")
        logs = lf.child(window, "ExchangeLogs")
        self.assertEqual([child["name"] for child in logs["children"]], ["ExchangeLog_0", "ExchangeLog_1", "ExchangeLog_2"])
        self.assertLessEqual(logs["y"] + logs["height"], board["height"] - 8)
        self.assertEqual(window["width"], board["width"])

    def test_a_refresh_shows_all_24_slots_of_each_side(self):
        world, window = self.world()
        self.open(world, window)
        self.assertEqual(window.OwnerSlot.shown(), {22: (HELMET, "2", False)})
        self.assertEqual(window.TargetSlot.shown(), {23: (GLAIVE, "", False)})

    def test_the_faces_the_name_and_the_level(self):
        world, window = self.world()
        self.open(world, window)
        self.assertEqual(window.FaceOwnerImage.image, "icon/face/assassin_m.tga")
        self.assertEqual(window.FaceTargetImage.image, "icon/face/sura_m.tga")
        self.assertEqual(window.TargetName.GetText(), "Partner")
        self.assertEqual(window.TargetLevel.GetText(), "Lv. 37")

    def test_the_history_writes_a_line_for_each_change_and_shows_the_last_three(self):
        world, window = self.world()
        ex = world.game.w4["exchange"]
        self.open(world, window)
        self.assertRegex(self.logs(window)[0], "^%s You are ready to trade.$" % TIME)
        self.assertEqual(self.logs(window)[1:], ["", ""])
        for side, value in (("target_accept", True), ("self_accept", True), ("self_accept", True),
                            ("target_accept", False)):
            ex[side] = value
            self.run_in(world, window.Refresh)
        self.assertEqual(len(window.exchangeLogs), 4, "a refresh that changes nothing writes nothing")
        expected = ["Partner accept the trade.", "You accept the trade.", "Partner abort the trade."]
        for line, text in zip(self.logs(window), expected):
            self.assertRegex(line, "^%s %s$" % (TIME, re.escape(text)))
        ex["self_accept"] = False
        self.run_in(world, window.Refresh)
        self.assertRegex(self.logs(window)[-1], "^%s You abort the trade.$" % TIME)

    def test_an_accepted_side_s_slots_are_green(self):
        world, window = self.world()
        ex = world.game.w4["exchange"]
        self.open(world, window)
        ex["target_accept"] = True
        self.run_in(world, window.Refresh)
        self.assertEqual(window.slot_bases["target"][-1], ("d:/ymir work/ui/public/slot_base.sub", 0.35, 0.85, 0.35, 1.0))
        self.assertEqual(window.slot_bases["owner"][-1], ("d:/ymir work/ui/public/slot_base.sub", 1.0, 1.0, 1.0, 1.0))

    def accept(self, setup):
        world, window = self.world(setup)
        self.open(world, window)
        mark = world.mark()
        self.run_in(world, window.AcceptButton.click)
        return world, window, mark

    def test_the_partner_offers_something_so_accept_sends(self):
        world, window, mark = self.accept(stock)
        self.assertEqual(world.calls_since(mark, "net."), [("net.SendExchangeAcceptPacket", ())])

    def test_you_give_something_for_nothing_so_it_asks_first(self):
        def nothing_back(game):
            stock(game)
            game.w4["exchange"]["target"][23] = None
        for answer in ("accept", "cancel"):
            with self.subTest(answer=answer):
                world, window, mark = self.accept(nothing_back)
                dialog = world.game.dialogs[-1]
                self.assertEqual((dialog._name, dialog.texts),
                                 ("uiCommon.QuestionDialog2", ["You are giving things away for nothing in exchange,",
                                                               "and won't be able to get the Yang or items back."]))
                self.assertEqual(world.calls_since(mark, "net."), [])
                with world.game, w4.quiet():
                    getattr(dialog, answer)()
                sent = world.calls_since(mark, "net.")
                if answer == "accept":
                    self.assertEqual(sent, [("net.SendExchangeAcceptPacket", ())])
                else:
                    self.assertEqual(sent, [])
                    self.assertFalse(window.AcceptButton.down, "the toggle is up again")

    def test_only_yang_from_you_asks_too_and_an_empty_trade_accepts(self):
        def yang_only(game):
            stock(game)
            ex = game.w4["exchange"]
            ex["target"][23] = ex["self"][22] = None
            ex["self_elk"] = 1000
        world, window, mark = self.accept(yang_only)
        self.assertEqual(world.game.dialogs[-1]._name, "uiCommon.QuestionDialog2")

        def empty(game):
            stock(game)
            ex = game.w4["exchange"]
            ex["target"][23] = ex["self"][22] = None
        world, window, mark = self.accept(empty)
        self.assertEqual(world.calls_since(mark, "net."), [("net.SendExchangeAcceptPacket", ())])

    def test_the_money_keeps_its_12_digits(self):
        world, window = self.world()
        self.assertEqual(window.dlgPickMoney.max, 12)


class Locales(unittest.TestCase):
    def test_every_new_key_is_in_all_17_locales_with_the_english_format(self):
        locales = [name for name in sorted(os.listdir(lf.LOCALES))
                   if os.path.isfile(os.path.join(lf.LOCALES, name, "locale_game.txt"))]
        self.assertEqual(len(locales), 17)
        for locale in locales:
            for kind, keys in NEW_KEYS.items():
                entries = ext.locale_entries(os.path.join(lf.LOCALES, locale, "locale_%s.txt" % kind))
                for key, english in keys.items():
                    with self.subTest(locale=locale, key=key):
                        self.assertTrue(entries.get(key, "").strip())
                        self.assertEqual(re.findall(r"%[sd]", entries[key]), re.findall(r"%[sd]", english))
                        if locale == "en":
                            self.assertEqual(entries[key], english)


if __name__ == "__main__":
    unittest.main()
