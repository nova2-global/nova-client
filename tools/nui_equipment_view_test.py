"""Tests for the NovaUI equipment view (assets/root/nui_equipment_view.py,
P16 spec 5.6): python3 -B -m unittest nui_equipment_view_test (from tools/).

The legacy uiEquipmentDialog.EquipmentDialog (made from its real uiscript
by nui_game_support's stand-ins) and the NovaUI one, each in a world of its
own with the same state (nui_w4_world.World), driven as
Interface.OpenEquipmentDialog and the view-equip packet's handlers drive
them (spec 5.6.4): the open, the items, sockets and attributes by view
index, the hover's tooltip (ClearToolTip, AddItemData, ShowToolTip), the
close and its event, Escape. They make the same calls and tooltip calls,
and the board shows what legacy's slot window shows, placed by the limits
module's view table (today's 11, OLD's 16 at the foundation). Two views
show at once, each with its own instanced model."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

DOCUMENT = "nui/windows/equipment-view/equipment-view.rml"
PARTNER, OTHER = 77, 78
SWORD, HELMET, ARMOR, RING, BELT = 10, 12200, 11200, 18000, 73001


class RecordingTooltip(support.ToolTip):
    """The item tooltip as the equipment view calls it: ClearToolTip and
    AddItemData recorded with the stand-in's other calls."""

    def ClearToolTip(self):
        self.calls.append(("ClearToolTip",))

    def AddItemData(self, vnum, sockets, attrs):
        self.calls.append(("AddItemData", vnum, tuple(sockets), tuple(attrs)))
        self.shown.append(("AddItemData", vnum))


def names(game):
    game.w4["names"].update({PARTNER: "Partner", OTHER: "Other"})
    game.item_sizes[SWORD] = (1, 2)
    game.item_sizes[ARMOR] = (1, 2)


class EquipmentViewTest(unittest.TestCase):
    def world(self, nui_on, **kwargs):
        return w4.World(nui_on, setup=names, **kwargs)

    def make(self, world):
        return world.make("equipment-view", "uiEquipmentDialog", "EquipmentDialog", "nui_equipment_view.EquipmentDialog")

    def open(self, world, vid=PARTNER, items=((4, SWORD, 1), (1, HELMET, 1), (0, ARMOR, 1))):
        """Interface.OpenEquipmentDialog(vid) and the view-equip packet: an
        item per view slot, the sword's socket and an attribute."""
        window = self.make(world)
        closed = []
        tooltip = RecordingTooltip("item")
        with world.game, w4.quiet():
            window.SetItemToolTip(tooltip)
            window.SetCloseEvent(lambda vid: closed.append(vid))
            window.Open(vid)
            for slot, vnum, count in items:
                window.SetEquipmentDialogItem(slot, vnum, count)
            window.SetEquipmentDialogSocket(4, 0, 28030)
            window.SetEquipmentDialogAttr(4, 0, 1, 500)
        return window, tooltip, closed

    def worlds(self):
        return [(nui_on, self.world(nui_on)) for nui_on in (False, True)]

    def assert_one_empty_board_waits(self, world):
        """P18: a closed view's board waits in the pool, hidden, emptied,
        with no dialog behind it: the only document left."""
        (board,) = world.m("nui_equipment_view").POOL.boards()
        self.assertEqual(world.documents(), [DOCUMENT])
        self.assertFalse(board.is_visible())
        self.assertEqual((board.model["equip_on"], board.model["title"]), ([], ""))
        self.assertIs(board._owner, world.m("nui_hud").NO_OWNER)
        return board


class Model(EquipmentViewTest):
    def test_the_board_shows_legacy_s_items_by_view_index_and_the_name(self):
        (_, legacy), (_, novaui) = self.worlds()
        a, _, _ = self.open(legacy)
        b, _, _ = self.open(novaui)
        legacy_items = dict((index, slot["vnum"]) for index, slot in a.slotWindow.slots.items() if slot["vnum"])
        vnums = b.slotWindow.vnums()
        board = w4.board(b)
        cells = dict((cell["index"], vnums[cell["index"]]) for cell in board.model["cells"] if cell["kind"])
        places = [place["name"] for place in board.model["places"]]
        self.assertEqual(dict((board.model["places"][i]["index"], vnum) for i, vnum in cells.items()), legacy_items)
        self.assertEqual(places, ["body", "head", "foots", "wrist", "weapon", "neck", "ear", "unique1", "unique2", "arrow",
                                  "shield"])
        self.assertEqual((board.model["title"], board.model["table"]), ("Partner", "new"))
        self.assertEqual(board.model["cells"][4]["h"], 2, "the sword's size, drawn in the weapon's place")

    def test_legacy_s_belt_slot_23_is_not_a_place(self):
        (_, legacy), (_, novaui) = self.worlds()
        a, _, _ = self.open(legacy, items=((23, BELT, 1),))
        b, _, _ = self.open(novaui, items=((23, BELT, 1),))
        self.assertEqual(a.slotWindow.slots[23]["vnum"], BELT, "legacy's uiscript slot nothing fills in game")
        self.assertEqual([cell for cell in w4.board(b).model["cells"] if cell["kind"]], [])

    def test_a_count_above_one_shows(self):
        world = self.world(True)
        window, _, _ = self.open(world, items=((9, 8000, 200),))
        self.assertEqual(w4.board(window).model["cells"][9]["count"], "200")

    def test_the_foundation_s_view_table_places_the_rings_and_the_belt(self):
        world = self.world(True)
        limits = world.m("nui_limits")
        limits.use(limits.foundation())
        try:
            window, _, _ = self.open(world, items=((13, RING, 1), (15, BELT, 1), (11, ARMOR, 1)))
            model = w4.board(window).model
            self.assertEqual(model["table"], "old")
            self.assertEqual(len(model["places"]), 16)
            shown = dict((place["name"], place["shown"]) for place in model["places"])
            self.assertEqual((shown["costume_body"], shown["costume_hair"], shown["ring1"], shown["belt"]),
                             (False, False, True, True))
            items = dict((cell["index"], cell["ref"]) for cell in model["cells"] if cell["kind"])
            self.assertEqual(items, {11: 11, 13: 13, 15: 15})
        finally:
            limits.use(None)


class Flows(EquipmentViewTest):
    def test_hover_shows_the_item_s_data_as_legacy_s(self):
        results = []
        for nui_on, world in self.worlds():
            window, tooltip, _ = self.open(world)
            with world.game, w4.quiet():
                if nui_on:
                    for event, index in (("cell_over", 4), ("cell_out", 4), ("cell_over", 2), ("cell_out", 2)):
                        w4.fire(window, event, index)
                else:
                    window.slotWindow.fire("over_in", 4)
                    window.slotWindow.fire("over_out")
            results.append(tooltip.calls)
        legacy, novaui = results
        self.assertEqual(novaui, legacy)
        self.assertEqual([call[0] for call in novaui], ["ClearToolTip", "AddItemData", "ShowToolTip", "HideToolTip"],
                         "an empty place (foots, 2) shows nothing")
        self.assertEqual(novaui[1][:2], ("AddItemData", SWORD))
        self.assertEqual((novaui[1][2][0], novaui[1][3][0]), (28030, (1, 500)), "the socket and the attribute legacy kept")

    def test_close_escape_and_the_close_button_call_the_close_event(self):
        for how in ("close", "escape", "x"):
            results = []
            for nui_on, world in self.worlds():
                window, _, closed = self.open(world)
                mark = world.mark()
                with world.game, w4.quiet():
                    if how == "escape":
                        window.OnPressEscapeKey()
                    elif how == "close":
                        window.Close()
                    elif nui_on:
                        w4.press(window, "close_press", 0)
                    else:
                        window.board.close()
                results.append((world.effects_since(mark), closed, window, world))
            (legacy, a_closed, _, _), (novaui, b_closed, b, world) = results
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual((a_closed, b_closed), ([PARTNER], [PARTNER]))
                self.assertFalse(b.IsShow())
                self.assert_one_empty_board_waits(world)

    def test_two_views_show_at_once_each_with_its_own_model(self):
        world = self.world(True)
        first, _, _ = self.open(world, PARTNER)
        second, _, _ = self.open(world, OTHER, items=((1, HELMET, 1),))
        a, b = w4.board(first), w4.board(second)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a.MODEL, b.MODEL)
        self.assertTrue(a.MODEL.startswith("equipment_view_") and b.MODEL.startswith("equipment_view_"))
        self.assertEqual((a.model["title"], b.model["title"]), ("Partner", "Other"))
        with world.game, w4.quiet():
            second.Close()
        self.assertIsNotNone(w4.board(first), "closing one view keeps the other")
        with world.game:
            self.assertTrue(first.nui_ready())

    def test_a_second_view_of_the_same_player_replaces_the_first(self):
        """Interface.OpenEquipmentDialog replaces the dict entry of a vid it
        views again without Destroy; legacy's dropped window leaves the
        screen when it is collected. The first board went on the screen
        until the client exited, and its close deleted the new dialog's
        entry (review)."""
        world = self.world(True)
        dialogs = {}

        def close(vid):
            dialogs.pop(vid, None)

        views = []
        for _ in range(2):
            window, _, _ = self.open(world, PARTNER)
            with world.game, w4.quiet():
                window.SetCloseEvent(close)
            dialogs[PARTNER] = window
            views.append(window)
        first, second = views
        self.assertIsNone(w4.board(first), "the earlier view's board went at the new Open")
        self.assertIsNone(first.demand)
        self.assertIsNotNone(w4.board(second))
        self.assertTrue(w4.board(second).is_visible())
        # P18: one shows; the other waits, hidden, in the pool (the second
        # view's probe found none waiting, then the first view's board went).
        shown = [window for window in world.game.state.windows if window._doc and window.DOCUMENT == DOCUMENT
                 and window.visible]
        self.assertEqual(shown, [w4.board(second)])
        self.assertEqual(len(world.m("nui_equipment_view").POOL), 1)
        other, _, _ = self.open(world, OTHER)
        self.assertIsNotNone(w4.board(second), "another player's view takes no other's place")
        with world.game, w4.quiet():
            second.Close()
        self.assertEqual(dialogs, {})
        self.assertIsNotNone(w4.board(other))

    def test_open_centers_it_and_a_press_raises_it(self):
        world = self.world(True)
        window, _, _ = self.open(world)
        self.assertEqual(w4.board(window).placement, ("center",))
        raised = []
        original = window.SetTop
        window.SetTop = lambda: (raised.append(True), original())
        w4.fire(window, "board_press", 0)
        self.assertEqual(raised, [True])


class Facade(EquipmentViewTest):
    def test_the_class_the_methods_and_no_per_frame_python(self):
        world = self.world(True)
        window = self.make(world)
        legacy_class = world.m("uiEquipmentDialog").EquipmentDialog
        self.assertIsInstance(window, legacy_class)
        self.assertTrue(window.NUI_FACADE)
        for name in ("SetItemToolTip", "SetCloseEvent", "Open", "Close", "Destroy", "SetEquipmentDialogItem",
                     "SetEquipmentDialogSocket", "SetEquipmentDialogAttr"):
            self.assertTrue(callable(getattr(window, name)), name)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        module = world.m("nui_equipment_view")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == "nui_equipment_view":
                for attr in ("OnUpdate", "OnRender"):
                    self.assertFalse(callable(getattr(cls, attr, None)), "%s.%s" % (name, attr))
        self.assertTrue(module._EquipmentViewBoard.INSTANCED)

    def test_make_builds_legacy_with_the_flag_off_or_an_older_exe(self):
        world = self.world(False)
        self.assertIs(type(self.make(world)), world.m("uiEquipmentDialog").EquipmentDialog)
        world = self.world(True, engine_4=False)
        self.assertIs(type(self.make(world)), world.m("uiEquipmentDialog").EquipmentDialog)

    def test_the_probe_s_board_waits_for_the_open_and_the_0_by_0_window(self):
        (_, legacy), (_, novaui) = self.worlds()
        a = self.make(legacy)
        b = self.make(novaui)
        # P18: the probe's board waits, hidden, in the pool for the open.
        self.assertIsNone(w4.board(b))
        self.assertEqual(novaui.documents(), [DOCUMENT])
        self.assertEqual(len(novaui.m("nui_equipment_view").POOL), 1)
        self.assertEqual((b.GetWidth(), b.GetHeight()), (0, 0))
        self.assertEqual(b.flags, a.flags)
        self.assertIn("float", b.flags)

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world = self.world(True)
        window = self.make(world)
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "empty"):
            self.assertEqual(w4.fixture_keys(window, "equipment-view", variant), kinds, variant)

    def test_the_interface_makes_it_through_make(self):
        text = w4.read(os.path.join(w4.ROOT, "interfacemodule.py"))
        self.assertIn('dlg = nui_windows.make("equipment-view", uiEquipmentDialog.EquipmentDialog, '
                      '"nui_equipment_view.EquipmentDialog")', text)


class Pool(EquipmentViewTest):
    """P18: the Interface makes a dialog per view and drops it at its close;
    the closed view's board waits, emptied, in a pool of two for the next
    view, which shows its own player with no load."""

    def test_the_bound_is_two(self):
        module = self.world(True).m("nui_equipment_view")
        self.assertEqual((module.POOL_BOUND, module.POOL.bound), (2, 2))

    def test_the_next_view_takes_the_waiting_board_and_shows_its_own_player(self):
        world = self.world(True)
        first, _, _ = self.open(world, PARTNER)
        board = w4.board(first)
        with world.game, w4.quiet():
            first.Close()
        self.assert_one_empty_board_waits(world)
        pool = world.m("nui_equipment_view").POOL
        loads = pool.loads
        second, tooltip, closed = self.open(world, OTHER, items=((1, HELMET, 1),))
        self.assertIs(w4.board(second), board, "no load: the waiting board")
        self.assertEqual(pool.loads, loads)
        self.assertEqual((board.model["title"], board.model["equip_on"]), ("Other", [1]))
        vnums = second.slotWindow.vnums()
        shown = [vnums[cell["index"]] for cell in board.model["cells"] if cell["kind"]]
        self.assertEqual(shown, [HELMET], "the other player's items only")
        with world.game, w4.quiet():
            w4.press(second, "close_press", 0)
        self.assertEqual(closed, [OTHER], "its close is the new view's")

    def test_a_view_dropped_without_close_gives_its_board_back_when_collected(self):
        import gc
        world = self.world(True)
        window, _, _ = self.open(world, PARTNER)
        board = w4.board(window)
        with world.game, w4.quiet():
            window.Hide()
        del window
        gc.collect()
        self.assertEqual(world.m("nui_equipment_view").POOL.boards(), [board])

    def test_never_more_than_two_wait_and_the_phase_end_unloads_them(self):
        world = self.world(True)
        views = [self.open(world, vid)[0] for vid in (PARTNER, OTHER, 79)]
        with world.game, w4.quiet():
            for view in views:
                view.Close()
        pool = world.m("nui_equipment_view").POOL
        self.assertEqual(len(pool), 2)
        self.assertLessEqual(pool.most, 2)
        self.assertEqual(world.documents().count(DOCUMENT), 2)
        with world.game, w4.quiet():
            world.m("nui_windows").end_phase()
        self.assertNotIn(DOCUMENT, world.documents())

    def test_a_waiting_board_s_events_reach_no_view(self):
        world = self.world(True)
        window, tooltip, closed = self.open(world)
        board = w4.board(window)
        with world.game, w4.quiet():
            window.Close()
            mark = world.mark()
            calls = len(tooltip.calls)
            board.fire("cell_over", 4)
            board.fire("cell_out", 4)
            board.fire("close_press", 0)
            board.fire("board_press", 0)
        self.assertEqual(world.effects_since(mark), [])
        self.assertEqual(len(tooltip.calls), calls)
        self.assertEqual(closed, [PARTNER])


if __name__ == "__main__":
    unittest.main()
