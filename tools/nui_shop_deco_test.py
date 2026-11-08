"""Tests of the NovaUI offline shop decoration (assets/root/nui_shop_deco.py;
Wave 5, NOVA-9) and the name dialog's decoration button.

Each flow runs on legacy's uimyshopdecoration.MyShopDecorationWindow and on
the NovaUI facade over offline_shop_test's protocol-6 world (nui_shop_test's
OfflineNuiWorld), and what each does must be the same: the steps, the choice,
the commit into uiPrivateShopBuilder.SHOP_DECO and SHOP_STYLE only on
Complete with CONFIG's decoration item, and the chat line without it. The
NovaUI side also checks what the board shows (the entries, the selected one,
the preview's name or sign style, the step's buttons) and that the window
covers the kit's modal name dialog while it shows."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_shop_test  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import offline_shop_test as offline  # noqa: E402

KEY = "shop-deco"
MODELS = offline.CONFIG["models"]


class DecoWorld(nui_shop_test.OfflineNuiWorld):
    """OfflineNuiWorld with the decoration module (and the NovaUI one) loaded."""

    def __init__(self, nui_on):
        nui_shop_test.OfflineNuiWorld.__init__(self, nui_on)
        with self.game, w4.quiet():
            self.loaded["uiPrivateShopBuilder"] = self.w4.m("uiPrivateShopBuilder")
            self.loaded["uiMyShopDecoration"] = self.game.load("uiMyShopDecoration", "uimyshopdecoration.py")
            if nui_on:
                self.game.load("nui_shop_deco", "nui_shop_deco.py")

    def deco_window(self):
        window = self.w4.make(KEY, "uiMyShopDecoration", "MyShopDecorationWindow", "nui_shop_deco.MyShopDecorationWindow")
        with self, w4.quiet():
            window.BindInterface(self.interface)
        return window

    def committed(self):
        builder = self.m("uiPrivateShopBuilder")
        return builder.SHOP_DECO, builder.SHOP_STYLE


class DecoTest(unittest.TestCase):
    def opened(self, nui_on, deco_items=0):
        world = DecoWorld(nui_on)
        if deco_items:
            world.counts[offline.DECO] = deco_items
        window = world.deco_window()
        with world, w4.quiet():
            window.Open()
        return world, window

    def run_both(self, flow, deco_items=0):
        outcomes = []
        for nui_on in (False, True):
            world, window = self.opened(nui_on, deco_items)
            mark = world.mark()
            with world, w4.quiet():
                flow(world, window)
            outcomes.append(((world.committed(), window.GetStep(), window.GetSelection(), bool(window.IsShow()),
                              world.chat(), world.since(mark)), world, window))
        (legacy, _, _), (novaui, _, _) = outcomes
        self.assertEqual(novaui, legacy)
        return outcomes

    @staticmethod
    def pick(world, window, line):
        if world.nui_on:
            w4.press(window, "entry_press", line, 0)
        else:
            window.itemList.press(line)

    @staticmethod
    def button(world, window, name):
        if world.nui_on:
            w4.press(window, "button_press", name, 0)
        else:
            getattr(window, name + "Button").click()

    @staticmethod
    def close(world, window):
        if world.nui_on:
            w4.press(window, "close_press", 0)
        else:
            window.titleBar.close()


class Flows(DecoTest):
    def test_complete_commits_the_model_and_the_style(self):
        def flow(world, window):
            self.pick(world, window, 2)
            self.button(world, window, "next")
            self.pick(world, window, 2)
            self.button(world, window, "complete")
        (state, _, _), _ = self.run_both(flow, deco_items=1)
        self.assertEqual(state[0], (MODELS[2], 2))
        self.assertFalse(state[3], "Complete closes the window")

    def test_complete_without_the_scroll_commits_nothing(self):
        def flow(world, window):
            self.pick(world, window, 3)
            self.button(world, window, "next")
            self.button(world, window, "complete")
        (state, _, _), _ = self.run_both(flow)
        self.assertEqual(state[0], (0, 0))
        self.assertIn(offline.WAVE5_GAME_KEYS["DECORATION_REQUIRES_SCROLL"], state[4])

    def test_close_x_and_escape_keep_what_was_committed(self):
        for leave in (lambda world, window: self.button(world, window, "cancel"), self.close,
                      lambda world, window: window.OnPressEscapeKey()):
            def flow(world, window, leave=leave):
                self.pick(world, window, 4)
                leave(world, window)
            (state, _, _), _ = self.run_both(flow)
            self.assertEqual(state[0], (0, 0))
            self.assertFalse(state[3])

    def test_back_returns_to_the_model_step_with_its_choice(self):
        def flow(world, window):
            self.pick(world, window, 5)
            self.button(world, window, "next")
            self.pick(world, window, 1)
            self.button(world, window, "prev")
        (state, _, _), (_, _, window) = self.run_both(flow)
        self.assertEqual(state[1:3], (1, (MODELS[5], 1)))
        self.assertEqual(w4.board(window).model["selected"], 5)


class Board(DecoTest):
    def test_the_model_step_shows_the_model_view_and_the_style_step_hides_it(self):
        """NOVA-137: model_view follows legacy's render target window."""
        world, window = self.opened(True)
        self.assertTrue(w4.board(window).model["model_view"])
        with world, w4.quiet():
            w4.press(window, "button_press", "next", 0)
        self.assertFalse(w4.board(window).model["model_view"])
        with world, w4.quiet():
            w4.press(window, "button_press", "prev", 0)
        self.assertTrue(w4.board(window).model["model_view"])

    def test_a_client_without_model_previews_keeps_the_stall_mark(self):
        world = DecoWorld(True)
        world.game.modules["player"].lack("SelectShopModel", "MyShopDecoShow")
        window = world.deco_window()
        with world, w4.quiet():
            window.Open()
        self.assertFalse(w4.board(window).model["model_view"])

    def test_the_model_step_lists_configs_models_and_names_the_choice(self):
        world, window = self.opened(True)
        model = w4.board(window).model
        self.assertEqual(model["step"], 1)
        self.assertEqual([entry["key"] for entry in model["entries"]], [str(vnum) for vnum in MODELS])
        self.assertEqual(model["selected"], 0, "SHOP_DECO 0: CONFIG's first model")
        self.assertEqual(model["preview_name"], model["entries"][0]["name"])
        self.assertEqual(model["preview_style"], -1, "no sign on the model step")
        self.assertEqual((model["next"], model["cancel"], model["prev"], model["complete"]), (True, True, False, False))
        self.assertTrue(model["title"] and model["description"])

    def test_the_style_step_shows_the_chosen_sign(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            self.button(world, window, "next")
        model = w4.board(window).model
        self.assertEqual((model["step"], model["selected"], model["preview_style"]), (2, 0, 0), "style 0: the plain board")
        self.assertEqual((model["next"], model["cancel"], model["prev"], model["complete"]), (False, False, True, True))
        with world, w4.quiet():
            self.pick(world, window, 3)
        model = w4.board(window).model
        self.assertEqual((model["selected"], model["preview_style"]), (3, 3))
        self.assertEqual(model["preview_name"], model["entries"][3]["name"])

    def test_a_style_past_the_sheets_shows_the_plain_sign(self):
        world, window = self.opened(True)
        module = world.game.loaded["nui_shop_deco"]
        self.assertEqual([module.style_class(s) for s in (0, 1, 5, 6, -1, "x")], [0, 1, 5, 0, 0, 0])

    def test_every_fixture_has_every_model_key(self):
        world, window = self.opened(True)
        model = set(w4.board(window).model)
        for variant in ("", "style", "style-ice", "style-plain"):
            with self.subTest(variant=variant):
                self.assertEqual(set(w4.fixture_keys(window, KEY, variant)), model)


class Kit(DecoTest):
    def test_the_window_covers_the_kit_until_it_hides(self):
        world = DecoWorld(True)
        with world, w4.quiet():
            kit = world.game.load("nui_dialog_kit", "nui_dialog_kit.py")
        window = world.deco_window()
        with world, w4.quiet():
            window.Open()
        self.assertTrue(kit.covered(), "the name dialog steps aside while the window shows")
        with world, w4.quiet():
            window.Close()
        self.assertFalse(kit.covered())


class Lifecycle(DecoTest):
    def test_hide_and_show_before_the_legacy_init_do_not_raise(self):
        """ui.Window.__init__ calls Hide before the legacy __init__ sets its
        attributes; the facade's __init__ runs nui_begin first."""
        world = DecoWorld(True)
        window = world.deco_window()
        cls = type(window)
        bare = cls.__new__(cls)
        with world, w4.quiet():
            bare.nui_begin()
            bare.Hide()
            bare.Show()

    def test_the_facade_runs_no_python_per_frame(self):
        world = DecoWorld(True)
        self.assertIsNone(type(world.deco_window()).OnUpdate)

    def test_destroy_takes_the_board(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            window.Destroy()
        self.assertIsNone(w4.board(window))


if __name__ == "__main__":
    unittest.main()
