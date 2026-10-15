"""Tests for the Wave 4 shared pieces (P16 spec 4.3, 4.4, 11.3):
nui_hud.has_engine_4(), nui.Window.INSTANCED in assets/root/nui.py, and the
Wave 4 stand-ins of nui_game_support (install_wave4_ui, leave_range,
load_wave4_legacy): python3 -B -m unittest nui_w4_support_test (from
tools/)."""
import contextlib
import io
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_test_support  # noqa: E402


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def wave4_game(engine_3b=True):
    game = support.Game(engine_3b=engine_3b)
    support.install_wave2b_ui(game)
    support.install_wave3a_ui(game)
    support.install_wave3b_ui(game)
    support.install_wave4_ui(game)
    game.modules["localeInfo"] = support.locale_info("en")
    game.load_standard()
    return game


class EngineProbe(unittest.TestCase):
    def test_has_engine_4_needs_the_range_watch_the_whisper_feed_and_instanced_documents(self):
        game = wave4_game()
        hud = game.loaded["nui_hud"]
        with game:
            self.assertTrue(hud.has_engine_3b())
            self.assertTrue(hud.has_engine_4())
            for name in ("WatchLeaveRange", "WhisperAttach"):
                saved = getattr(game.modules["nuigame"], name)
                game.modules["nuigame"].lack(name)
                self.assertFalse(hud.has_engine_4(), name)
                game.modules["nuigame"].__dict__["_missing"].discard(name)
                setattr(game.modules["nuigame"], name, saved)
            self.assertTrue(hud.has_engine_4())
            nui = game.modules["nui"]
            del nui._nui.LoadDocumentAs
            self.assertFalse(hud.has_engine_4(), "an exe without _nui.LoadDocumentAs")

    def test_without_the_wave3b_engine_there_is_no_wave4_engine(self):
        game = wave4_game(engine_3b=False)
        with game:
            self.assertFalse(game.loaded["nui_hud"].has_engine_4())


class FakeNui(object):
    """A _nui over which assets/root/nui.py runs: available, records the
    model and document calls."""

    def __init__(self):
        self.calls = []
        self.next = [10]

    def IsAvailable(self):
        return True

    def SetReloadHandler(self, fn):
        pass

    def HasStrings(self):
        return True

    def CreateModel(self, name, initial):
        self.calls.append(("CreateModel", name))
        self.next[0] += 1
        return self.next[0]

    def ModelOn(self, model, event, fn):
        self.calls.append(("ModelOn", model, event))

    def LoadDocument(self, path):
        self.calls.append(("LoadDocument", path))
        self.next[0] += 1
        return self.next[0]

    def LoadDocumentAs(self, path, model):
        self.calls.append(("LoadDocumentAs", path, model))
        self.next[0] += 1
        return self.next[0]

    def DestroyModel(self, model):
        self.calls.append(("DestroyModel", model))

    def Close(self, doc):
        self.calls.append(("Close", doc))


class Instanced(unittest.TestCase):
    def load(self, fake):
        modules = nui_test_support.Modules(_nui=fake)
        self.addCleanup(modules.restore)
        return modules.load("nui")

    def window_classes(self, nui):
        class Board(nui.Window):
            DOCUMENT = "nui/windows/equipment-view/equipment-view.rml"
            MODEL = "equipment_view"
            INSTANCED = True

            def initial_model(self):
                return {"title": ""}

            @nui.on("close_press")
            def on_close(self, button):
                pass

        class Plain(nui.Window):
            DOCUMENT = "nui/windows/shop/shop.rml"
            MODEL = "shop"
        return Board, Plain

    def test_each_instance_binds_its_own_model_and_loads_its_copy(self):
        fake = FakeNui()
        nui = self.load(fake)
        Board, Plain = self.window_classes(nui)
        self.assertFalse(nui.Window.INSTANCED)
        first, second = Board(), Board()
        plain = Plain()
        self.assertEqual((first.MODEL, second.MODEL), ("equipment_view_1", "equipment_view_2"))
        self.assertEqual(Board.MODEL, "equipment_view", "the class keeps the document's name")
        self.assertEqual(plain.MODEL, "shop")
        self.assertIn(("CreateModel", "equipment_view_1"), fake.calls)
        self.assertIn(("LoadDocumentAs", Board.DOCUMENT, "equipment_view_1"), fake.calls)
        self.assertIn(("LoadDocumentAs", Board.DOCUMENT, "equipment_view_2"), fake.calls)
        self.assertIn(("LoadDocument", Plain.DOCUMENT), fake.calls)
        self.assertTrue(first._doc and second._doc and first._doc != second._doc)
        first.destroy()
        third = Board()
        self.assertEqual(third.MODEL, "equipment_view_3", "a name is never used again")

    def test_an_exe_without_load_document_as_leaves_an_instanced_window_unavailable(self):
        class Older(FakeNui):
            LoadDocumentAs = None
        fake = Older()
        modules = nui_test_support.Modules(_nui=fake)
        self.addCleanup(modules.restore)
        nui = modules.load("nui")
        Board, Plain = self.window_classes(nui)
        board = Board()
        self.assertEqual((board._doc, board._model), (0, 0))
        self.assertFalse(board.show())
        self.assertNotIn("CreateModel", [call[0] for call in fake.calls], "no model is made for it")
        self.assertTrue(Plain()._doc, "a plain window still loads")


class StandIns(unittest.TestCase):
    def test_the_leave_range_watches_follow_nui_range_watch(self):
        game = wave4_game()
        nuigame = game.modules["nuigame"]
        fired = []
        game.w4["position"] = (100.0, 200.0, 0.0)
        nuigame.WatchLeaveRange("exchange", 1000, lambda: fired.append("exchange"), True)
        nuigame.WatchLeaveRange("shop", 1000, lambda: fired.append("shop"), False)
        self.assertEqual(nuigame.LeaveRangeState("exchange")["start"], [100.0, 200.0])
        game.w4["position"] = (1200.0, 200.0, 0.0)
        self.assertTrue(support.leave_range(game, "exchange"))
        self.assertEqual(nuigame.LeaveRangeState("exchange")["start"], [1200.0, 200.0], "rearm: the start moves")
        self.assertTrue(support.leave_range(game, "shop"))
        self.assertFalse(support.leave_range(game, "shop"), "no rearm: one fire until armed again")
        self.assertTrue(support.leave_range(game, "exchange"))
        self.assertEqual(fired, ["exchange", "shop", "exchange"])
        self.assertTrue(nuigame.StopLeaveRange("shop"))
        self.assertIsNone(nuigame.LeaveRangeState("shop"))
        self.assertFalse(support.leave_range(game, "safebox"))

    def test_the_stand_in_window_is_instanced_only_with_load_document_as(self):
        game = wave4_game()
        nui = game.modules["nui"]

        class Board(nui.Window):
            DOCUMENT = "nui/windows/equipment-view/equipment-view.rml"
            MODEL = "equipment_view"
            INSTANCED = True
        with game:
            first, second = Board(), Board()
            self.assertEqual((first.MODEL, second.MODEL), ("equipment_view_1", "equipment_view_2"))
            self.assertTrue(first._doc)
            del nui._nui.LoadDocumentAs
            third = Board()
            self.assertEqual(third._doc, 0)

    def test_the_legacy_windows_load_from_their_uiscripts_and_read_game_w4(self):
        game = wave4_game()
        modules = support.load_wave4_legacy(game, social=True)
        game.w4["exchange"]["self"][3] = {"vnum": 27001, "count": 5}
        game.w4["exchange"]["target_name"] = "Partner"
        with game, quiet():
            exchange = modules["uiExchange"].ExchangeDialog()
            exchange.LoadDialog()
            exchange.OpenDialog()
            exchange.Refresh()
            shop = modules["uiShop"].ShopDialog()
            shop.LoadDialog()
            safebox = modules["uiSafebox"].SafeboxWindow()
            password = modules["uiSafebox"].PasswordDialog()
            builder = modules["uiPrivateShopBuilder"].PrivateShopBuilder()
            view = modules["uiEquipmentDialog"].EquipmentDialog()
        self.assertEqual(exchange.OwnerSlot.shown(), {3: (27001, "5", False)})
        self.assertEqual(exchange.TitleName.GetText(), game.modules["localeInfo"].EXCHANGE_TITLE % "Partner")
        self.assertEqual(type(password.passwordValue).__name__, "EditLine")
        self.assertEqual(type(shop.smallRadioButtonGroup).__name__, "RadioButtonGroup")
        self.assertEqual(type(builder.itemSlot).__name__, "LegacySlotWindow")
        self.assertEqual(sorted(view.slotWindow.slots), list(range(11)) + [23])
        self.assertEqual(len(safebox.pageButtonList), 1, "SetTableSize(3) at load: one page")
        for name in ("uiGuild", "uiMessenger", "uiWhisper", "uiUploadMark"):
            self.assertIn(name, modules)
        del view
        with quiet():
            import gc
            gc.collect()  # legacy's __del__ prints, once its cycle goes

    def test_w4_compared_names_the_spec_s_modules(self):
        self.assertEqual(support.W4_COMPARED,
                         ("player", "net", "mouse", "app", "shop", "safebox", "exchange", "messenger", "guild", "chat"))
        self.assertEqual(set(support.w4_state()) >= {"exchange", "shop", "safebox", "messenger", "guild", "whisper",
                                                      "files", "images", "leave_range"}, True)


if __name__ == "__main__":
    unittest.main()
