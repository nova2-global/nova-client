"""NovaUI side of the buffi (NOVA-38): python3 -B -m unittest nui_buffi_test
(from tools/).

- The costume window (nui_costume.CostumeWindow over the foundation's wear
  table, the live client's) holds the buffi's costume body, hair and weapon
  costume cells (nui_limits' costume group, wear 31-33; the companion block
  of the sheet, has_companion), bound to the inventory's legacy handlers as
  legacy's window binds them: a drop, a use and a hover make legacy's calls,
  and a refresh shows what legacy shows. The buffi's wings and facial cells
  (wear 34, 35) stay hidden, as legacy's window does not show them.
- The game options (nui_game_options.OptionDialog) have legacy's hide-buffi
  row: the model's hide_buffi is the server's state (player.IsHideBuffi),
  a choice sends /hide_buffi only when it changes, and RefreshHideBuffi
  (Interface.OnBuffiHide on GC::BUFFI_HIDE) refreshes the row.
- The fixtures carry the new keys."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffi_test  # noqa: E402
import nui_inventory_test as inv  # noqa: E402
import nui_sys_test as sys_test  # noqa: E402

WINDOWS = inv.WINDOWS
EQUIPMENT_START = 225
BUFFI_BODY, BUFFI_HAIR, BUFFI_WEAPON = EQUIPMENT_START + 31, EQUIPMENT_START + 32, EQUIPMENT_START + 33
COMPANION = ("buffi_costume_body", "buffi_costume_hair", "buffi_costume_weapon")


def load_limits():
    import nui_w3b_fixtures
    return nui_w3b_fixtures.LIMITS


def with_buffi(*changes):
    def setup(game):
        inv.stock(game)
        buffi_test.install_buffi(game)
        for change in changes:
            change(game)
    return setup


class WearTable(unittest.TestCase):
    def test_the_live_tables_costume_group_holds_the_buffi_s_three_cells(self):
        limits = load_limits()
        names = [slot.name for slot in limits.wear_group("costume", limits.foundation())]
        for name in COMPANION:
            self.assertIn(name, names)
        cells = dict((slot.name, slot.cell) for slot in limits.wear_group("costume", limits.foundation()))
        self.assertEqual([cells[name] for name in COMPANION], [BUFFI_BODY, BUFFI_HAIR, BUFFI_WEAPON])

    def test_the_wings_and_facial_stay_hidden(self):
        limits = load_limits()
        groups = dict((slot.name, slot.group) for slot in limits.wear_table(limits.foundation()))
        self.assertEqual(groups["buffi_costume_sash2"], "hidden")
        self.assertEqual(groups["buffi_costume_facial"], "hidden")

    def test_today_s_table_has_no_companion(self):
        limits = load_limits()
        names = [slot.name for slot in limits.wear_group("costume", limits.read({}))]
        self.assertFalse([name for name in names if name.startswith("buffi_")])


class CostumeCells(inv.Pair):
    def open_costume(self, world, window):
        window.ClickCostumeButton()

    def test_a_costume_dropped_on_the_buffi_s_body_cell_moves_there(self):
        def flow(w, win, i):
            i.press("bag", 30)
            i.release("costume", BUFFI_BODY)
        legacy, world, window = self.same(flow, with_buffi(lambda game: game.give(30, inv.COSTUME)), self.open_costume,
                                          expect=["net.SendItemMovePacket"])
        moves = [args for name, args in legacy if name == "net.SendItemMovePacket"]
        self.assertEqual(moves, [(30, BUFFI_BODY, 1)])

    def test_a_use_takes_a_buffi_costume_off_and_a_hover_shows_its_tooltip(self):
        def worn(game):
            game.give(BUFFI_WEAPON, 40108)

        def flow(w, win, i):
            i.over("costume", BUFFI_WEAPON)
            i.use("costume", BUFFI_WEAPON)
        legacy, world, window = self.same(flow, with_buffi(worn), self.open_costume, expect=["net.SendItemUsePacket"])
        self.assertIn(("SetInventoryItem", BUFFI_WEAPON), window.tooltipItem.shown)

    def test_the_board_shows_the_worn_buffi_costumes_and_the_companion_block(self):
        def worn(game):
            game.give(BUFFI_BODY, inv.COSTUME)
            game.give(BUFFI_HAIR, 45001)
        world = inv.World(True, setup=with_buffi(worn))
        window = world.make_inventory()
        with world.game, inv.quiet():
            window.ClickCostumeButton()
        model = inv.board(window.wndCostume).model
        self.assertTrue(model["has_companion"])
        names = dict((cell["name"], cell) for cell in model["slots"])
        self.assertEqual(set(COMPANION) & set(names), set(COMPANION))
        self.assertTrue(names["buffi_costume_body"]["icon"])
        self.assertTrue(names["buffi_costume_hair"]["icon"])
        self.assertEqual(names["buffi_costume_weapon"]["icon"], "")
        self.assertNotIn("buffi_costume_sash2", names)
        self.assertNotIn("buffi_costume_facial", names)


class GameOptions(unittest.TestCase):
    def make(self, hidden):
        world = sys_test.World(True)
        state = buffi_test.install_buffi(world.game, {"hidden": hidden})
        options = world.make_game_options()
        with world.game, sys_test.quiet():
            options.Show()
        return world, state, options

    def test_the_model_shows_the_server_s_state(self):
        world, state, options = self.make(True)
        self.assertTrue(sys_test.board(options).model["hide_buffi"])
        world, state, options = self.make(False)
        self.assertFalse(sys_test.board(options).model["hide_buffi"])

    def test_a_choice_sends_hide_buffi_only_when_it_changes_and_waits_for_the_server(self):
        world, state, options = self.make(False)
        mark = len(world.game.log)
        with world.game, sys_test.quiet():
            sys_test.board(options).fire("choose", "hide_buffi", 0, 0)
            sys_test.board(options).fire("choose", "hide_buffi", 1, 0)
        sent = [args for name, args in world.game.log[mark:] if name == "net.SendChatPacket"]
        self.assertEqual(sent, [("/hide_buffi 1",)], "Show is in effect: only Hide sends")
        self.assertFalse(sys_test.board(options).model["hide_buffi"], "the row waits for GC::BUFFI_HIDE")
        state["hidden"] = True
        with world.game, sys_test.quiet():
            options.RefreshHideBuffi()
        self.assertTrue(sys_test.board(options).model["hide_buffi"])


class Fixtures(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(WINDOWS, name.split(".")[0], name), encoding="utf-8") as handle:
            return json.load(handle)

    def test_the_game_options_fixtures_have_hide_buffi(self):
        for name in ("game-options.fixture.json", "game-options.blocked.fixture.json"):
            with self.subTest(fixture=name):
                self.assertIn("hide_buffi", self.read(name)["game_options"])

    def test_the_live_costume_fixture_holds_the_companion(self):
        model = self.read("costume.foundation.fixture.json")["costume"]
        self.assertTrue(model["has_companion"])
        self.assertEqual([cell["name"] for cell in model["slots"] if cell["name"].startswith("buffi_")], list(COMPANION))


if __name__ == "__main__":
    unittest.main()
