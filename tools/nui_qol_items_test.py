"""Tests for the wave 10 item conveniences (story NOVA-184): python3 -B -m
unittest nui_qol_items_test (from tools/).

- NOVA-191: a right press or a double click on a safebox item takes it out
  to a cell the server picks (net.SAFEBOX_CHECKOUT_ANY_CELL).
- The dialog kit's question with a third button (uiCommon.QuestionDialog3
  and its facade, nui_dialog_question.QuestionDialog3), for NOVA-189 and
  NOVA-201.
- NOVA-189: Destroy in the drop question of a main or special inventory
  item (game.py's own drop methods, compiled over the world's modules).
- NOVA-201: the inventory's mall button opens the storage choice.
- NOVA-190: "Split all" in the pick money dialog of a stack's split.
- NOVA-187: marks to sell at an NPC shop (uiShop's store), in both
  inventories and the shop's mark board.

Each flow runs on the legacy window and on the NovaUI one, each in a world
of its own with the same state (nui_w4_world.World), and the two make the
same calls (W4_COMPARED, the sounds and the dialogs) in the same order."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_dialogs_test as kit_test  # noqa: E402
import nui_extra_inventory_test as extra_test  # noqa: E402
import nui_game_support as support  # noqa: E402
import nui_inventory_test as inventory_test  # noqa: E402
import nui_safebox_test as safebox_test  # noqa: E402
import nui_shop_test as shop_test  # noqa: E402
import nui_w4_world as w4  # noqa: E402

P = w4.P
ANY_CELL = 0xFFFF
POTION, HELMET = safebox_test.POTION, safebox_test.HELMET


def stock_any_cell(game):
    """The safebox tester's stock, on an exe with the any-cell constant."""
    safebox_test.stock(game)
    game.modules["net"].SAFEBOX_CHECKOUT_ANY_CELL = ANY_CELL


def stock_older_exe(game):
    """The safebox tester's stock, on an exe without the constant."""
    safebox_test.stock(game)
    game.modules["net"].lack("SAFEBOX_CHECKOUT_ANY_CELL")


def sends(calls):
    return [call for call in calls if call[0].startswith("net.")]


# --- NOVA-191: right-click a safebox item to take it out ---------------------------------------------

class SafeboxRightClick(safebox_test.SafeboxTest):
    def use(self, world, window, cell):
        """A double click on a cell (the slot window's use event)."""
        if world.nui_on:
            w4.fire(window, "cell_use", cell)
        else:
            window.wndItem.fire("use", cell)

    def test_a_right_press_on_an_item_takes_it_out_to_any_cell(self):
        def flow(world, window):
            self.press(world, window, 2, button=1)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [("net.SendSafeboxCheckoutPacket", (2, P["INVENTORY"], ANY_CELL))])
        self.assertFalse(world.mouse.isAttached())

    def test_a_double_click_on_page_two_sends_the_global_cell(self):
        def flow(world, window):
            self.page(world, window, 1)
            self.use(world, window, 0)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [("net.SendSafeboxCheckoutPacket", (45, P["INVENTORY"], ANY_CELL))])

    def test_an_older_exe_sends_the_protocol_s_value(self):
        def flow(world, window):
            self.press(world, window, 1, button=1)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup=stock_older_exe)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [("net.SendSafeboxCheckoutPacket", (1, P["INVENTORY"], ANY_CELL))])

    def test_an_empty_cell_sends_nothing(self):
        def flow(world, window):
            self.use(world, window, 20)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [])

    def test_with_an_item_attached_it_only_drops_the_attach(self):
        """A double click while something is attached cancels the attach and
        takes nothing out (OLD did both)."""
        def flow(world, window):
            self.press(world, window, 2)
            self.use(world, window, 1)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertIn(("mouse.DeattachObject", ()), novaui)
        self.assertEqual(sends(novaui), [])
        self.assertFalse(world.mouse.isAttached())


# --- the kit's question with a third button (NOVA-189, NOVA-201) ----------------------------------

QUESTION = kit_test.QUESTION


class Question3(kit_test.KitTest):
    def make(self):
        dialog = self.uiCommon.QuestionDialog3()
        dialog.SetText("HOW_MANY_ITEM_DO_YOU_DROP")
        dialog.SetMiddleText("Destroy")
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.SetMiddleEvent(self.events("middle"))
        dialog.SetCancelEvent(self.events("cancel"))
        return dialog

    def test_the_kit_shows_three_buttons_and_each_calls_its_event_leaving_it_open(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(QUESTION)
        self.assertEqual((window.model["middle_on"], window.model["middle_label"]), (True, "Destroy"))
        self.assertEqual((window.model["accept_label"], window.model["cancel_label"]), ("@ui.YES", "@ui.NO"))
        self.assertEqual(window.focused, "dialog-question-accept")
        window.fire("accept")
        window.fire("middle")
        window.fire("cancel")
        self.assertEqual(self.events.seen, [("accept",), ("middle",), ("cancel",)])
        self.assertTrue(dialog.IsShow())
        dialog.Close()
        self.assertFalse(dialog.IsShow())

    def test_a_plain_question_after_it_shows_two_buttons(self):
        first = self.make()
        first.Open()
        self.assertTrue(self.kit_window(QUESTION).model["middle_on"])
        first.Close()
        plain = self.uiCommon.QuestionDialog()
        plain.SetText("LOCALE_CHANGE_CONFIRM")
        plain.Open()
        self.assertFalse(self.kit_window(QUESTION).model["middle_on"])
        self.assertEqual(self.kit_window(QUESTION).model["middle_label"], "")

    def test_the_label_follows_while_shown_and_the_safe_event_binds_weakly(self):
        dialog = self.uiCommon.QuestionDialog3()
        dialog.Open()
        dialog.SetMiddleText("Safebox")
        seen = []

        class Owner(object):
            def on_middle(self):
                seen.append("middle")

        owner = Owner()
        dialog.SAFE_SetMiddleEvent(owner.on_middle)
        window = self.kit_window(QUESTION)
        self.assertEqual(window.model["middle_label"], "Safebox")
        window.fire("middle")
        self.assertEqual(seen, ["middle"])

    def test_a_busy_kit_gives_the_legacy_dialog_the_third_button(self):
        first = self.uiCommon.QuestionDialog()
        first.SetText("party")
        first.Open()
        second = self.make()
        second.Open()
        legacy = second._legacy
        self.assertIsInstance(legacy, self.uiCommon.LegacyQuestionDialog3)
        self.assertEqual(legacy.middleButton.text, "Destroy")
        legacy.middleButton.Click()
        self.assertEqual(self.events.seen, [("middle",)])

    def test_the_facade_has_every_legacy_method(self):
        import nui_dialog_question
        facade = nui_dialog_question.QuestionDialog3
        for name in kit_test.legacy_methods("uicommon.py", "QuestionDialog3"):
            self.assertTrue(hasattr(facade, name), name)
        self.assertIsInstance(self.uiCommon.QuestionDialog3(), facade)


class Question3FlagOff(kit_test.KitTest):
    flags = ""

    def test_the_legacy_dialog_puts_the_buttons_at_oldss_places(self):
        """OLD's questiondialogitem.py: accept at -60, the third at 0, cancel
        at +60 of the center, on the text's last line."""
        dialog = self.uiCommon.QuestionDialog3()
        self.assertIsInstance(dialog, self.uiCommon.LegacyQuestionDialog3)
        dialog.SetText("HOW_MANY_ITEM_DO_YOU_DROP")
        dialog.SetMiddleText("Destroy")
        dialog.SetMiddleEvent(self.events("middle"))
        y = dialog.BUTTON_Y + 10
        self.assertEqual([c for c in dialog.acceptButton.calls if c[0] == "SetPosition"][-1], ("SetPosition", -60, y))
        self.assertEqual([c for c in dialog.middleButton.calls if c[0] == "SetPosition"][-1], ("SetPosition", 0, y))
        self.assertEqual([c for c in dialog.cancelButton.calls if c[0] == "SetPosition"][-1], ("SetPosition", 60, y))
        self.assertEqual(dialog.middleButton.text, "Destroy")
        dialog.middleButton.Click()
        self.assertEqual(self.events.seen, [("middle",)])


# --- NOVA-189: Destroy in the drop question ------------------------------------------------------

GAME_DESTROY = inventory_test.GAME_DROP


def game_window(world):
    """A GameWindow with game.py's own drop and destroy methods over the
    world's modules, the ground under the pointer (no character picked)."""
    source = support.source_of("game.py", GAME_DESTROY, inside="GameWindow")
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(world.game.modules)
    namespace.update(world.game.loaded)
    exec(compile("class GameWindow(object):\n" + body + "\n", "game.py", "exec"), namespace)
    window = namespace["GameWindow"]()
    window.interface = type("Interface", (), {"BUILD_OnMouseLeftButtonUp": lambda self: False})()
    window.PickingCharacterIndex = 0
    window.itemDropQuestionDialog = None
    window.destroyQuestionDialog = None
    return window


def opened(calls):
    return [name for name, _ in calls if name.endswith(".Open")]


class DestroyFromInventory(inventory_test.Pair):
    def setups(self, *changes):
        return inventory_test.with_state(*changes)

    def test_destroy_then_yes_destroys_the_stack_the_question_names(self):
        def flow(w, win, i):
            i.press("bag", 4)
            game = game_window(w)
            game.OnMouseLeftButtonUp()
            drop = w.game.dialogs[-1]
            self.assertEqual(drop.middle_text, "DESTROY")
            drop.middle()
            w.game.dialogs[-1].accept()
            self.assertIsNone(game.itemDropQuestionDialog)
            self.assertIsNone(game.destroyQuestionDialog)
        legacy, world, _ = self.same(flow, setup=self.setups(),
                                     expect=["uiCommon.QuestionDialog3.Open", "uiCommon.QuestionDialog.Open"])
        self.assertEqual(opened(legacy), ["uiCommon.QuestionDialog3.Open", "uiCommon.QuestionDialog.Open"])
        warning = [args for name, args in legacy if name == "uiCommon.QuestionDialog.Open"][0]
        self.assertEqual(warning[0], world.game.modules["localeInfo"].DESTROY_ITEM_WARNING)
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendItemDestroyPacket", (P["INVENTORY"], 4, inventory_test.POTION, 10))])
        self.assertEqual([d.is_open for d in world.game.dialogs[-2:]], [False, False])

    def test_a_split_stack_destroys_only_the_split_count(self):
        def flow(w, win, i):
            w.game.pressed.add(inventory_test.A["DIK_LSHIFT"])
            i.press("bag", 4)
            inventory_test.accept_last(w, 3)
            w.game.pressed.clear()
            game_window(w).OnMouseLeftButtonUp()
            w.game.dialogs[-1].middle()
            w.game.dialogs[-1].accept()
        legacy, _, _ = self.same(flow, setup=self.setups())
        self.assertIn(("net.SendItemDestroyPacket", (P["INVENTORY"], 4, inventory_test.POTION, 3)), legacy)

    def test_no_in_the_warning_keeps_the_drop_question_and_yes_there_drops(self):
        def flow(w, win, i):
            i.press("bag", 4)
            game = game_window(w)
            game.OnMouseLeftButtonUp()
            drop = w.game.dialogs[-1]
            drop.middle()
            w.game.dialogs[-1].cancel()
            self.assertTrue(drop.is_open)
            drop.accept()
        legacy, _, _ = self.same(flow, setup=self.setups())
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendItemDropPacketNew", (P["INVENTORY"], 4, 10))])

    def test_a_warning_left_open_after_the_drop_question_closed_destroys_nothing(self):
        def flow(w, win, i):
            i.press("bag", 4)
            game = game_window(w)
            game.OnMouseLeftButtonUp()
            w.game.dialogs[-1].middle()
            warning = w.game.dialogs[-1]
            game.RequestDropItem(False)  # Escape on the game window
            warning.accept()
        legacy, _, _ = self.same(flow, setup=self.setups())
        self.assertEqual([call for call in legacy if call[0].startswith("net.")], [])

    def test_money_and_dragon_soul_items_get_the_two_button_question(self):
        world = inventory_test.World(False, setup=self.setups())
        with world.game, inventory_test.quiet():
            game = game_window(world)
            player = world.game.modules["player"]
            game._GameWindow__DropMoney(player.SLOT_TYPE_INVENTORY, 500)
            game.RequestDropItem(False)
            game._GameWindow__DropItem(player.SLOT_TYPE_DRAGON_SOUL_INVENTORY, 0, 3, 1)
        self.assertEqual([d._name for d in world.game.dialogs], ["uiCommon.QuestionDialog", "uiCommon.QuestionDialog"])

    def test_a_private_shop_being_built_refuses_the_destroy(self):
        def flow(w, win, i):
            i.press("bag", 4)
            game = game_window(w)
            game.OnMouseLeftButtonUp()
            w.game.dialogs[-1].middle()
            w.game.modules["uiPrivateShopBuilder"].IsBuildingPrivateShop = lambda: True
            w.game.dialogs[-1].accept()
            w.game.modules["uiPrivateShopBuilder"].IsBuildingPrivateShop = lambda: False
        legacy, _, _ = self.same(flow, setup=self.setups())
        self.assertNotIn("net.SendItemDestroyPacket", [name for name, _ in legacy])
        self.assertIn("chat.AppendChat", [name for name, _ in legacy])


class DestroyFromExtraInventory(extra_test.Pair):
    def test_a_special_inventory_stack_is_destroyed_with_its_window(self):
        def flow(w, win, i):
            i.category(extra_test.MATERIALS)
            i.press(0)
            game_window(w).OnMouseLeftButtonUp()
            drop = w.game.dialogs[-1]
            self.assertEqual(drop._name, "uiCommon.QuestionDialog3")
            drop.middle()
            w.game.dialogs[-1].accept()
        legacy, _, _ = self.same(flow, setup=extra_test.stock)
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendItemDestroyPacket",
                                  (extra_test.EXTRA, extra_test.cell(extra_test.MATERIALS, 0), extra_test.ORE, 37))])


# --- NOVA-201: the storage choice ----------------------------------------------------------------

def sent_commands(calls):
    return [args[0] for name, args in calls if name == "net.SendChatPacket"]


class StorageChoice(inventory_test.Pair):
    """The legacy inventory's choice is OLD's board, the NovaUI one the kit's
    three-button question: both send the same commands."""

    def choose(self, world, window, which):
        """The mall button, then the choice's button: "mall", "safebox" or
        "cancel"."""
        inventory_test.Input(world, window).button("mallButton", "mall_press")
        if world.nui_on:
            dialog = world.game.dialogs[-1]
            {"mall": dialog.accept, "safebox": dialog.middle, "cancel": dialog.cancel}[which]()
            return dialog
        board = window.storageChoice
        self.assertTrue(board.IsShow())
        if which == "cancel":
            board.close()
        else:
            {"mall": window.storageMallButton, "safebox": window.storageSafeboxButton}[which].click()
        return board

    def run_choice(self, which):
        results = []
        for world in self.worlds(inventory_test.stock):
            window = world.make_inventory()
            with world.game, inventory_test.quiet():
                mark = world.mark()
                shown = self.choose(world, window, which)
                results.append((sent_commands(world.effects_since(mark)), shown, world, window))
        return results

    def test_the_button_alone_sends_nothing(self):
        for world in self.worlds(inventory_test.stock):
            window = world.make_inventory()
            with world.game, inventory_test.quiet():
                mark = world.mark()
                inventory_test.Input(world, window).button("mallButton", "mall_press")
                self.assertEqual(sent_commands(world.effects_since(mark)), [])
                if world.nui_on:
                    dialog = world.game.dialogs[-1]
                    self.assertEqual(dialog._name, "uiCommon.QuestionDialog3")
                    self.assertTrue(dialog.is_open)
                    self.assertEqual(dialog.texts, ["STORAGE_TITLE"])
                    self.assertEqual((dialog.accept_text, dialog.middle_text, dialog.cancel_text),
                                     ("SYSTEM_MALL", "SAFE_TITLE", "CANCEL"))
                else:
                    self.assertTrue(window.storageChoice.IsShow())

    def test_item_mall_sends_click_mall_and_closes_the_choice(self):
        for commands, shown, world, window in self.run_choice("mall"):
            self.assertEqual(commands, ["/click_mall"], world.nui_on)
            self.assertFalse(shown.IsShow() if not world.nui_on else shown.is_open)

    def test_safebox_sends_click_safebox_and_closes_the_choice(self):
        for commands, shown, world, window in self.run_choice("safebox"):
            self.assertEqual(commands, ["/click_safebox"], world.nui_on)
            self.assertFalse(shown.IsShow() if not world.nui_on else shown.is_open)

    def test_cancel_sends_nothing(self):
        for commands, shown, world, window in self.run_choice("cancel"):
            self.assertEqual(commands, [], world.nui_on)
            self.assertFalse(shown.IsShow() if not world.nui_on else shown.is_open)

    def test_a_second_press_of_the_legacy_button_closes_the_board(self):
        world = inventory_test.World(False, setup=inventory_test.stock)
        window = world.make_inventory()
        with world.game, inventory_test.quiet():
            window.mallButton.Click()
            self.assertTrue(window.storageChoice.IsShow())
            window.mallButton.Click()
            self.assertFalse(window.storageChoice.IsShow())


# --- NOVA-190: Split all ---------------------------------------------------------------------------

PICK = kit_test.PICK


def pick_dialog(world):
    return [d for d in world.game.dialogs if d._name == "uiPickMoney.PickMoneyDialog"][-1]


class SplitAllInventory(inventory_test.Pair):
    def split(self, count, tick=True):
        def flow(w, win, i):
            w.game.pressed.add(inventory_test.A["DIK_LSHIFT"])
            i.press("bag", 4)
            w.game.pressed.clear()
            dialog = pick_dialog(w)
            self.assertTrue(dialog.item_mode)
            self.assertFalse(dialog.split_all, "unchecked at each open")
            if tick:
                dialog.tick()
            dialog.accept(count)
            dialog.Close()
        return self.same(flow)

    def test_ticked_the_stack_is_split_into_piles_on_the_server(self):
        legacy, world, _ = self.split(3)
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendItemSplitPacket", (P["INVENTORY"], 4, inventory_test.POTION, 3))])
        self.assertNotIn("mouse.AttachObject", [name for name, _ in legacy])
        self.assertFalse(world.mouse.isAttached())

    def test_unticked_the_count_is_attached_as_before(self):
        legacy, world, _ = self.split(3, tick=False)
        self.assertIn(("mouse.AttachObject", (P["SLOT_TYPE_INVENTORY"], 4, inventory_test.POTION, 3)), legacy)
        self.assertNotIn("net.SendItemSplitPacket", [name for name, _ in legacy])

    def test_the_whole_stack_has_nothing_to_split_and_is_attached(self):
        legacy, _, _ = self.split(10)
        self.assertNotIn("net.SendItemSplitPacket", [name for name, _ in legacy])
        self.assertIn(("mouse.AttachObject", (P["SLOT_TYPE_INVENTORY"], 4, inventory_test.POTION, 10)), legacy)

    def test_the_money_pick_shows_no_box(self):
        def flow(w, win, i):
            i.button("wndMoneySlot", "money_press")
            self.assertFalse(pick_dialog(w).item_mode)
        legacy, _, _ = self.same(flow)
        self.assertNotIn("uiPickMoney.PickMoneyDialog.SetItemMode", [name for name, _ in legacy])


class SplitAllExtraInventory(extra_test.Pair):
    def test_ticked_a_special_inventory_stack_is_split_in_its_window(self):
        def flow(w, win, i):
            i.category(extra_test.MATERIALS)
            i.keys("DIK_LSHIFT")
            i.press(0)
            i.keys()
            dialog = pick_dialog(w)
            self.assertTrue(dialog.item_mode)
            dialog.tick()
            dialog.accept(10)
            dialog.Close()
        legacy, _, _ = self.same(flow)
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendItemSplitPacket",
                                  (extra_test.EXTRA, extra_test.cell(extra_test.MATERIALS, 0), extra_test.ORE, 10))])


class SplitAllKit(kit_test.KitTest):
    def make(self):
        dialog = self.uiPickMoney.PickMoneyDialog()
        dialog.LoadDialog()
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.SetTitleName("PICK_ITEM_TITLE")
        return dialog

    def test_item_mode_shows_the_box_unchecked_and_a_press_on_its_row_ticks_it(self):
        dialog = self.make()
        dialog.SetItemMode()
        dialog.Open(200)
        window = self.kit_window(PICK)
        self.assertEqual((window.model["split_on"], window.model["split_checked"]), (True, False))
        self.assertFalse(dialog.IsSplitAll())
        window.fire("split", 1)
        self.assertFalse(dialog.IsSplitAll(), "a right press does nothing")
        window.fire("split", 0)
        self.assertTrue(dialog.IsSplitAll())
        self.assertTrue(window.model["split_checked"])
        seen = []
        dialog.SetAcceptEvent(lambda count: seen.append((count, dialog.IsSplitAll())))
        window.fire("accept")
        self.assertEqual(seen, [(1, True)], "the event reads the box before the close")
        self.assertFalse(dialog.IsShow())

    def test_the_next_open_without_item_mode_shows_no_box(self):
        dialog = self.make()
        dialog.SetItemMode()
        dialog.Open(200)
        self.kit_window(PICK).fire("split", 0)
        dialog.Close()
        dialog.Open(1000)
        window = self.kit_window(PICK)
        self.assertEqual((window.model["split_on"], window.model["split_checked"]), (False, False))
        self.assertFalse(dialog.IsSplitAll())

    def test_a_second_item_open_starts_unchecked(self):
        dialog = self.make()
        dialog.SetItemMode()
        dialog.Open(200)
        self.kit_window(PICK).fire("split", 0)
        dialog.Close()
        dialog.SetItemMode()
        dialog.Open(200)
        self.assertFalse(self.kit_window(PICK).model["split_checked"])
        self.assertFalse(dialog.IsSplitAll())

    def test_the_facade_has_the_legacy_methods(self):
        import nui_pick_money
        for name in ("SetItemMode", "SetMoneyMode", "IsSplitAll"):
            self.assertTrue(hasattr(nui_pick_money.PickMoneyDialog, name), name)


class LegacyCheckBox(kit_test.support.Widget):
    """ui.CheckBox for the kit's legacy ui stand-in."""

    checked = False

    def SetCheckStatus(self, flag):
        self.checked = bool(flag)

    def GetCheckStatus(self):
        return self.checked

    def IsShow(self):
        return self.shown


class SplitAllKitFlagOff(kit_test.KitTest):
    flags = ""

    def setUp(self):
        kit_test.KitTest.setUp(self)
        self.ui.CheckBox = LegacyCheckBox

    def test_the_legacy_box_shows_in_item_mode_and_goes_with_close(self):
        dialog = self.uiPickMoney.PickMoneyDialog()
        dialog.LoadDialog()
        self.assertIsInstance(dialog, self.uiPickMoney.LegacyPickMoneyDialog)
        self.assertFalse(dialog.IsSplitAll())
        dialog.SetItemMode()
        box = dialog.splitAllCheckBox
        self.assertIsNotNone(box)
        dialog.Open(200)
        self.assertFalse(dialog.IsSplitAll())
        box.checked = True
        self.assertTrue(dialog.IsSplitAll())
        self.assertEqual([c for c in dialog.acceptButton.calls if c[0] == "SetPosition"][-1], ("SetPosition", 19, 78))
        dialog.Close()
        self.assertFalse(dialog.IsSplitAll())
        self.assertEqual([c for c in dialog.acceptButton.calls if c[0] == "SetPosition"][-1], ("SetPosition", 19, 58))


# --- NOVA-187: mark to sell at an NPC shop ------------------------------------------------------

DIK_TAB = 0x0F
GOLD = (1.0, 0xDF / 255.0, 0.0, 1.0)


def with_tab(game):
    """The client's app.DIK_TAB (the stand-in's app has no Tab)."""
    game.modules["app"].DIK_TAB = DIK_TAB


class FakeShop(object):
    """The open NPC shop as the store sees it: its board's refreshes."""

    def __init__(self):
        self.refreshes = 0

    def RefreshSellMarkBoard(self):
        self.refreshes += 1


def open_npc_shop(world):
    """uiShop loaded into an item window world and an NPC shop open."""
    with world.game, inventory_test.quiet():
        store = world.game.loaded.get("uiShop") or world.game.load("uiShop", "uishop.py")
    world.fake_shop = FakeShop()
    store.BeginSellMarks(world.fake_shop)
    return store


def bag_sell(world, window):
    """{bag cell: marked} as each UI shows it: legacy's gold icon, NovaUI's
    "sell" key."""
    if world.nui_on:
        return dict((c["index"], c["sell"]) for c in inventory_test.board(window).model["bag"] if c["kind"] == "item")
    colors = window.wndItem.__dict__.get("colors", {})
    return dict((index, colors.get(index) == GOLD) for index, slot in window.wndItem.slots.items() if slot["vnum"])


class MarkSellInventory(inventory_test.Pair):
    def run_marks(self, flow, setup=None, shop_open=True):
        results = []
        for world in self.worlds(setup or inventory_test.with_state(with_tab)):
            store = open_npc_shop(world) if shop_open else None
            if store is None:
                with world.game, inventory_test.quiet():
                    store = world.game.load("uiShop", "uishop.py")
            window = world.make_inventory()
            with world.game, inventory_test.quiet():
                mark = world.mark()
                flow(world, window, inventory_test.Input(world, window), store)
                world.game.pressed.clear()
                results.append((world.effects_since(mark), world, window, store))
        (legacy, lw, lwin, lstore), (novaui, nw, nwin, nstore) = results
        self.assertEqual(legacy, novaui)
        self.assertEqual(bag_sell(lw, lwin), bag_sell(nw, nwin))
        self.assertEqual(dict(lstore._sellMarks), dict(nstore._sellMarks))
        return results

    def tab_press(self, w, i, cell):
        w.game.pressed.add(DIK_TAB)
        i.press("bag", cell)
        w.game.pressed.discard(DIK_TAB)

    def test_tab_and_a_press_marks_the_item_which_glows_and_is_not_picked(self):
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
            self.assertFalse(w.mouse.isAttached())
        (legacy, world, window, store), _ = self.run_marks(flow)
        self.assertEqual(dict(store._sellMarks), {(P["INVENTORY"], 4): inventory_test.POTION})
        self.assertTrue(bag_sell(world, window)[4])
        self.assertNotIn("mouse.AttachObject", [name for name, _ in legacy])
        self.assertGreater(world.fake_shop.refreshes, 0, "the shop's board shows the mark")

    def test_a_second_tab_press_unmarks_it(self):
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
            self.tab_press(w, i, 4)
        (_, world, window, store), _ = self.run_marks(flow)
        self.assertEqual(dict(store._sellMarks), {})
        self.assertFalse(bag_sell(world, window)[4])

    def test_a_marked_item_is_neither_picked_nor_used_nor_a_drop_target(self):
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
            i.press("bag", 4)
            self.assertFalse(w.mouse.isAttached(), "no pick")
            i.use("bag", 4)
            i.press("bag", 20)
            self.assertTrue(w.mouse.isAttached())
            i.press("bag", 4)
            self.assertFalse(w.mouse.isAttached(), "the attach goes back")
        legacy, _ = self.run_marks(flow)[0][:2]
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [])
        attached = [args for name, args in legacy if name == "mouse.AttachObject"]
        self.assertEqual([args[1] for args in attached], [20])

    def test_an_item_the_npc_does_not_buy_is_not_marked(self):
        def antiflag(game):
            with_tab(game)
            game.antiflags[inventory_test.POTION] = game.modules["item"].ANTIFLAG_SELL
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
        (_, _, _, store), _ = self.run_marks(flow, setup=inventory_test.with_state(antiflag))
        self.assertEqual(dict(store._sellMarks), {})

    def test_without_an_npc_shop_tab_and_a_press_picks_as_before(self):
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
        (legacy, world, _, store), _ = self.run_marks(flow, shop_open=False)
        self.assertEqual(dict(store._sellMarks), {})
        self.assertIn("mouse.AttachObject", [name for name, _ in legacy])

    def test_a_worn_item_is_never_marked(self):
        def flow(w, win, i, store):
            w.game.pressed.add(DIK_TAB)
            i.press("wear", inventory_test.I["EQUIPMENT_BODY"])
            w.game.pressed.discard(DIK_TAB)
        (_, _, _, store), _ = self.run_marks(flow)
        self.assertEqual(dict(store._sellMarks), {})

    def test_sell_sends_one_sell_per_mark_at_its_full_count_and_clears(self):
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
            self.tab_press(w, i, 20)
            self.assertEqual(store.GetSellMarkTotal(), store.SellPriceOf(inventory_test.POTION, 10) +
                             store.SellPriceOf(inventory_test.SCROLL, 3))
            store.SellMarkedItems()
        (legacy, world, window, store), _ = self.run_marks(flow)
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendShopSellPacketNew", (4, 10, P["INVENTORY"])),
                                 ("net.SendShopSellPacketNew", (20, 3, P["INVENTORY"]))])
        self.assertIn(("snd.PlaySound", ("sound/ui/money.wav",)), legacy)
        self.assertEqual(dict(store._sellMarks), {})
        self.assertFalse(any(bag_sell(world, window).values()))

    def test_a_cell_whose_item_changed_is_skipped_and_the_total_reads_the_current_count(self):
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
            self.tab_press(w, i, 20)
            w.game.items[4]["count"] = 7
            self.assertEqual(store.GetSellMarkTotal(), store.SellPriceOf(inventory_test.POTION, 7) +
                             store.SellPriceOf(inventory_test.SCROLL, 3))
            w.game.items[20]["vnum"] = inventory_test.STONE
            store.SellMarkedItems()
        legacy = self.run_marks(flow)[0][0]
        sends = [call for call in legacy if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendShopSellPacketNew", (4, 7, P["INVENTORY"]))])

    def test_the_shop_s_close_clears_the_marks_and_the_glow(self):
        def flow(w, win, i, store):
            self.tab_press(w, i, 4)
            store.EndSellMarks()
            self.assertFalse(store.IsSellMarkActive())
        (_, world, window, store), _ = self.run_marks(flow)
        self.assertEqual(dict(store._sellMarks), {})
        self.assertFalse(bag_sell(world, window)[4])


class MarkSellExtraInventory(extra_test.Pair):
    def test_the_special_inventory_s_own_item_decides_and_its_cell_glows(self):
        """OLD read the inventory's item of the same number for the sell
        flag; the extra cell's own item decides here."""
        def setup(game):
            extra_test.stock(game)
            with_tab(game)
            game.antiflags[extra_test.POTION] = game.modules["item"].ANTIFLAG_SELL   # the inventory's cell 4: not sold
        def flow(w, win, i):
            store = w.store
            i.category(extra_test.MATERIALS)
            w.game.pressed = {DIK_TAB}
            i.press(4)   # the pearl at the materials' cell 4
            w.game.pressed = set()
            self.assertFalse(w.mouse.isAttached())
            i.press(4)
            self.assertFalse(w.mouse.isAttached())
            store.SellMarkedItems()

        results = []
        for world in self.worlds(setup):
            world.store = open_npc_shop(world)
            window = world.make_extra()
            with world.game, extra_test.quiet():
                mark = world.mark()
                flow(world, window, extra_test.Input(world, window))
                results.append(world.effects_since(mark))
        self.assertEqual(results[0], results[1])
        sends = [call for call in results[0] if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendShopSellPacketNew",
                                  (extra_test.cell(extra_test.MATERIALS, 4), 1, extra_test.EXTRA))])

    def test_a_marked_cell_glows_in_both_uis(self):
        def setup(game):
            extra_test.stock(game)
            with_tab(game)
        shown = []
        for world in self.worlds(setup):
            open_npc_shop(world)
            window = world.make_extra()
            with world.game, extra_test.quiet():
                i = extra_test.Input(world, window)
                i.category(extra_test.MATERIALS)
                world.game.pressed = {DIK_TAB}
                i.press(0)
                world.game.pressed = set()
            if world.nui_on:
                shown.append(sorted(c["index"] for c in extra_test.board(window).model["cells"] if c["sell"]))
            else:
                colors = window.wndItem.__dict__.get("colors", {})
                shown.append(sorted(index for index, color in colors.items() if color == GOLD))
        self.assertEqual(shown, [[0], [0]])


class MarkSellShopBoard(shop_test.ShopTest):
    """The shop's mark board: legacy's SellMarkBoard under the window, the
    NovaUI shop's panel."""

    def board_state(self, world, window):
        if world.nui_on:
            board = w4.board(window)
            model = board.model if board is not None else window._state
            return (model["mark_shown"], model["mark_total"])
        board = window.sellMarkBoard
        shown = bool(board) and board.IsShow()
        return (shown, board.priceText.GetText() if shown else "")

    def sell(self, world, window):
        if world.nui_on:
            w4.press(window, "mark_sell_press", 0)
        else:
            window.sellMarkBoard.sellButton.click()

    def test_marks_show_the_board_with_the_total_and_sell_sells_them(self):
        def flow(world, window):
            store = world.m("uiShop")
            self.assertEqual(self.board_state(world, window), (False, ""))
            store.ToggleSellMark(P["INVENTORY"], 4)
            total = world.m("localeInfo").NumberToMoneyString(store.SellPriceOf(POTION, 50))
            self.assertEqual(self.board_state(world, window), (True, total))
            self.sell(world, window)
            self.assertEqual(self.board_state(world, window)[0], False)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        sends = [call for call in novaui if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendShopSellPacketNew", (4, 50, P["INVENTORY"]))])

    def test_the_close_drops_the_marks_and_the_board(self):
        def flow(world, window):
            store = world.m("uiShop")
            store.ToggleSellMark(P["INVENTORY"], 4)
            window.Close()
            self.assertEqual(dict(store._sellMarks), {})
            self.assertFalse(store.IsSellMarkActive())
            self.assertEqual(self.board_state(world, window)[0], False)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)

    def test_a_player_s_shop_takes_no_marks(self):
        def flow(world, window):
            store = world.m("uiShop")
            self.assertFalse(store.IsSellMarkActive())
            self.assertFalse(store.ToggleSellMark(P["INVENTORY"], 4))
        self.run_both(flow, vid=shop_test.PLAYER_SHOP)

    def test_the_sell_rule_is_the_attached_sell_s(self):
        world, _ = self.world(False)
        store = world.m("uiShop")
        with world.game:
            self.assertEqual(store.SellPriceOf(POTION, 50), 100 * 50 // 5)
            self.assertEqual(store.SellPriceOf(POTION, 0), 100 // 5)


if __name__ == "__main__":
    unittest.main()
