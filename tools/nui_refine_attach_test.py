"""Tests for the NovaUI Wave 3b dialogs (P14 spec 6.4, 6.5): the refine
dialogs (assets/root/nui_refine.py: RefineDialogNew, RefineDialog) and
attach metin stone (nui_attach_metin.py): python3 -B -m unittest
nui_refine_attach_test (from tools/).

Plain CPython over nui_game_support's stand-ins, by nui_tooltip_corpus's
DialogWorld: the legacy dialogs made from their real uiscripts with the
legacy tooltips, or the NovaUI ones with the recorder.
- facade: each NovaUI class is the legacy class's subclass, with every
  legacy method callable as legacy's callers call it, and make()'s protocol;
- differential: the legacy and the NovaUI dialog, each in a world of its own
  with the same state, driven through the same flows (the legacy widgets'
  events against the board's data events), make the same net, snd and
  dialog calls in order: open, the materials, accept (at once and through
  the question), the question's cancel, cancel, the close button, Escape;
- model: what the board shows equals what the legacy widgets show (the
  tooltip's lines, the materials, the item, the cost and probability lines);
- the legacy window stays 0 x 0; the board exists only while the dialog
  shows, at legacy's place; the fixtures against the models; no per-frame
  Python."""
import inspect
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_tooltip_corpus as corpus_tool  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS = os.path.normpath(os.path.join(HERE, "..", "assets", "nui", "nui", "windows"))
EFFECTS = ("net", "snd", "uiCommon", "chat")
PLAYER = {"level": 120, "race": 0}
CLOCK = corpus_tool.CLOCK
SILVER, GOLD = corpus_tool.SILVER, corpus_tool.GOLD


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


_DATA = []


def data():
    """The fixtures' corpus, with the glaive's next grade."""
    if not _DATA:
        corpus = corpus_tool.fixture_corpus()
        corpus["items"]["3001"] = dict(corpus["items"]["3000"], name="Glaive+1")
        _DATA.append(corpus)
    return _DATA[0]


class Pair(object):
    """A legacy world and a NovaUI world, each with its dialog `which` made as
    the Interface or the inventory makes it, and the same items."""

    def __init__(self, which, items, engine_3b=True):
        self.which = which
        self.legacy = corpus_tool.DialogWorld(data(), recorder=False)
        self.novaui = corpus_tool.DialogWorld(data(), recorder=True)
        if not engine_3b:
            game = self.novaui.game
            game.modules["nui"]._nui.FollowPointer = None
            game.state.decorators.discard("nui-cells")
        for world in self.worlds():
            with world:
                corpus_tool.place_items(world, {"vnum": 0, "player": dict(PLAYER), "clock": CLOCK}, items)
                world.dialog = world.make(which)

    def worlds(self):
        return (self.legacy, self.novaui)

    def run(self, action):
        """action(world, dialog, novaui) in both worlds; the effects each made."""
        out = []
        for world in self.worlds():
            with world:
                mark = len(world.game.log)
                with corpus_tool.quiet():
                    action(world, world.dialog, world is self.novaui)
                out.append([(name, args) for name, args in world.game.log[mark:]
                            if name.split(".", 1)[0] in EFFECTS and not support.is_getter(name)])
        return out

    def board(self):
        demand = getattr(self.novaui.dialog, "demand", None)
        return demand.board() if demand is not None else None


def press(world, dialog, novaui, which):
    """A player's press: the legacy button (or title bar), or the board's event."""
    if novaui:
        board = dialog.demand.board()
        board.fire({"accept": "accept_press", "cancel": "cancel_press", "close": "close_press"}[which], 0)
        return
    if which == "close":
        dialog.titleBar.close()
        return
    dialog.GetChild({"accept": "AcceptButton", "cancel": "CancelButton"}[which]).Click()


def last_dialog(world):
    dialogs = [d for d in world.game.dialogs if d.is_open]
    return dialogs[-1] if dialogs else None


GLAIVE = [{"pos": 5, "vnum": 3000, "sockets": [28030, SILVER, GOLD], "attrs": [[1, 1500], [5, 12], [7, 10]]}]
MATERIALS = ((27799, 2), (27990, 1))


def open_new(world, dialog, novaui, prob=90, kind=0, cost=25000):
    dialog.Open(5, 3001, cost, prob, kind)
    for vnum, count in MATERIALS:
        dialog.AppendMaterial(vnum, count)


class RefineNew(unittest.TestCase):
    """uiRefine.RefineDialogNew, the dialog the server opens (spec 6.4)."""

    def pair(self):
        return Pair("new", GLAIVE)

    def test_the_novaui_dialog_is_made_with_the_flag(self):
        pair = self.pair()
        self.assertEqual(type(pair.novaui.dialog).__name__, "RefineDialogNew")
        self.assertTrue(getattr(type(pair.novaui.dialog), "NUI_FACADE", False))
        self.assertFalse(getattr(type(pair.legacy.dialog), "NUI_FACADE", False))

    def test_open_and_the_materials_show_what_legacy_shows(self):
        pair = self.pair()
        pair.run(open_new)
        legacy, novaui = pair.legacy.dialog, pair.novaui.dialog
        board = pair.board()
        self.assertIsNotNone(board, "the board shows while the dialog does")
        model = board.model
        texts = [child.text for child in legacy.children if type(child).__name__ == "TextLine"]
        self.assertEqual([m["text"] for m in model["materials"]], texts)
        self.assertEqual([m["text"] for m in model["materials"]], ["Fishbones x 02", "Piece of Stone x 01"])
        self.assertEqual(model["item_cells"], sum(1 for slot in legacy.slotList if slot.shown))
        self.assertEqual(model["item_cells"], 3)
        self.assertEqual(model["item_icon"], "/" + legacy.itemImage.image)
        self.assertEqual(model["cost_text"], legacy.costText.text)
        # Both lines come from the uiscript, which the client's loader shows
        # (ui.py LoadDefaultData; the stand-in loader leaves them as made):
        # legacy hides the probability line only.
        self.assertEqual((model["prob_shown"], model["cost_shown"]), (legacy.probText.shown, True))
        self.assertFalse(model["prob_shown"], "legacy hides the probability line (one uiscript child, hidden at load)")
        recorder = pair.novaui.m("nui_tooltip")
        self.assertEqual(recorder.model_rows({"lines": model["lines"]}, now=pair.novaui.game.state.now),
                         corpus_tool.stand_in_rows(legacy.toolTip))
        self.assertEqual(model["min_w"], legacy.toolTip.toolTipWidth)

    def test_accept_at_100_and_of_type_5_sends_at_once(self):
        for prob, kind in ((100, 0), (90, 5)):
            pair = self.pair()
            pair.run(lambda w, d, n: open_new(w, d, n, prob=prob, kind=kind))
            legacy, novaui = pair.run(lambda w, d, n: press(w, d, n, "accept"))
            self.assertEqual(legacy, novaui)
            self.assertEqual(legacy, [("net.SendRefinePacket", (5, kind))])
            self.assertFalse(pair.novaui.dialog.IsShow())
            self.assertIsNone(pair.board(), "the board goes with the dialog")

    def test_accept_asks_first_then_sends(self):
        for kind in (0, 2, 3):
            pair = self.pair()
            pair.run(lambda w, d, n: open_new(w, d, n, kind=kind))
            asked = pair.run(lambda w, d, n: press(w, d, n, "accept"))
            self.assertEqual(asked[0], asked[1])
            self.assertEqual(asked[0][0][0], "uiCommon.QuestionDialog2.Open")
            sent = pair.run(lambda w, d, n: last_dialog(w).accept())
            self.assertEqual(sent[0], sent[1])
            self.assertIn(("net.SendRefinePacket", (5, kind)), sent[0])

    def test_the_questions_cancel_closes_it_and_sends_nothing(self):
        pair = self.pair()
        pair.run(open_new)
        pair.run(lambda w, d, n: press(w, d, n, "accept"))
        legacy, novaui = pair.run(lambda w, d, n: last_dialog(w).cancel())
        self.assertEqual(legacy, novaui)
        self.assertNotIn("net.SendRefinePacket", [name for name, args in legacy])
        self.assertTrue(pair.novaui.dialog.IsShow())

    def test_cancel_the_close_button_and_escape_send_the_cancel(self):
        for action in (lambda w, d, n: press(w, d, n, "cancel"), lambda w, d, n: press(w, d, n, "close"),
                       lambda w, d, n: d.OnPressEscapeKey()):
            pair = self.pair()
            pair.run(open_new)
            legacy, novaui = pair.run(action)
            self.assertEqual(legacy, novaui)
            self.assertEqual(legacy, [("net.SendRefinePacket", (255, 255))])
            self.assertFalse(pair.novaui.dialog.IsShow())

    def test_the_legacy_window_stays_0_by_0(self):
        pair = self.pair()
        pair.run(open_new)
        self.assertEqual(pair.novaui.dialog.size, (0, 0))
        self.assertNotEqual(pair.legacy.dialog.size, (0, 0), "legacy's own window is sized")

    def test_the_board_opens_at_legacys_place_then_where_it_was_moved(self):
        pair = self.pair()
        pair.run(open_new)
        board = pair.board()
        width, height = 1600, 900
        self.assertEqual(board.placement, ("position", width - 400.0, 70 * 800 / float(height), (0.0, 0.0)))
        pair.novaui.game.state.boxes[(board.DOCUMENT, "")] = (300.0, 200.0, 280.0, 400.0)
        pair.run(lambda w, d, n: press(w, d, n, "cancel"))
        pair.run(open_new)
        self.assertEqual(pair.board().placement, ("position", 300.0, 200.0, (0.0, 0.0)))

    def test_without_the_3b_engine_make_keeps_legacys_dialog(self):
        pair = Pair("new", GLAIVE, engine_3b=False)
        self.assertFalse(getattr(type(pair.novaui.dialog), "NUI_FACADE", False))


class RefineOld(unittest.TestCase):
    """uiRefine.RefineDialog, the inventory's (unreachable today, spec D17)."""

    ITEMS = [{"pos": 1, "vnum": 25040}, {"pos": 5, "vnum": 10, "sockets": [28030, SILVER, 0]}]

    def pair(self):
        return Pair("old", self.ITEMS)

    def test_open_shows_what_legacy_shows(self):
        pair = self.pair()
        pair.run(lambda w, d, n: d.Open(1, 5))
        legacy, model = pair.legacy.dialog, pair.board().model
        self.assertEqual(model["variant"], "old")
        self.assertEqual(model["prob_text"], legacy.successPercentage.text)
        self.assertFalse(model["prob_shown"])
        # The uiscript's Cost, which the old dialog never touches: the client's
        # loader shows every child it makes (ui.py LoadDefaultData), the
        # stand-in loader leaves them as made.
        self.assertEqual((model["cost_text"], model["cost_shown"]), (legacy.GetChild("Cost").text, True))
        self.assertEqual((model["item_cells"], model["materials"]), (0, []))
        rows = pair.novaui.m("nui_tooltip").model_rows({"lines": model["lines"]}, now=pair.novaui.game.state.now)
        self.assertEqual(rows, corpus_tool.stand_in_rows(legacy.toolTip))

    def test_a_percentage_of_0_opens_nothing(self):
        pair = Pair("old", [{"pos": 1, "vnum": 25040}, {"pos": 5, "vnum": 10, "sockets": [28030, 28030, 28030]}])
        for world in pair.worlds():
            world.dialog.makeSocketSuccessPercentage = (100, 33, 20, 0)
        pair.run(lambda w, d, n: d.Open(1, 5))
        self.assertFalse(pair.legacy.dialog.IsShow())
        self.assertFalse(pair.novaui.dialog.IsShow())
        self.assertIsNone(pair.board())

    def test_accept_asks_then_uses_the_scroll_and_the_questions_cancel_hides_it(self):
        pair = self.pair()
        pair.run(lambda w, d, n: d.Open(1, 5))
        asked = pair.run(lambda w, d, n: press(w, d, n, "accept"))
        # Legacy's question is a window of its own (uiscript questiondialog2.py),
        # NovaUI's the dialog kit's QuestionDialog2, with legacy's texts.
        question = pair.legacy.dialog.dlgQuestion
        self.assertEqual(asked[0], [])
        self.assertTrue(question.IsShow())
        self.assertEqual(asked[1], [("uiCommon.QuestionDialog2.Open",
                                     (question.GetChild("message1").text, question.GetChild("message2").text, ""))])
        legacy, novaui = pair.run(lambda w, d, n: (d.dlgQuestion.GetChild("accept").Click() if not n else last_dialog(w).accept()))
        self.assertEqual(legacy, [("net.SendItemUseToItemPacket", (1, 5))])
        self.assertEqual([c for c in novaui if c[0].startswith("net.")], legacy)

    def test_accept_at_100_uses_the_scroll_at_once(self):
        pair = Pair("old", [{"pos": 1, "vnum": 25040}, {"pos": 5, "vnum": 10, "sockets": [0, 0, 0]}])
        pair.run(lambda w, d, n: d.Open(1, 5))
        legacy, novaui = pair.run(lambda w, d, n: press(w, d, n, "accept"))
        self.assertEqual(legacy, novaui)
        self.assertEqual(legacy, [("net.SendItemUseToItemPacket", (1, 5))])

    def test_cancel_the_close_button_and_escape_close_it_with_no_packet(self):
        for action in (lambda w, d, n: press(w, d, n, "cancel"), lambda w, d, n: press(w, d, n, "close"),
                       lambda w, d, n: d.OnPressEscapeKey()):
            pair = self.pair()
            pair.run(lambda w, d, n: d.Open(1, 5))
            legacy, novaui = pair.run(action)
            self.assertEqual(legacy, novaui)
            self.assertFalse([c for c in legacy if c[0].startswith("net.")])
            self.assertFalse(pair.novaui.dialog.IsShow())
            self.assertIsNone(pair.board())

    def test_the_legacy_window_stays_0_by_0(self):
        pair = self.pair()
        pair.run(lambda w, d, n: d.Open(1, 5))
        self.assertEqual(pair.novaui.dialog.size, (0, 0))


class Attach(unittest.TestCase):
    """uiAttachMetin.AttachMetinDialog (spec 6.5)."""

    ITEMS = [{"pos": 2, "vnum": 28030}, {"pos": 0, "vnum": 10, "sockets": [SILVER, SILVER, 0], "attrs": [[1, 1500]]}]

    def pair(self, items=None):
        return Pair("attach", items or self.ITEMS)

    def test_open_shows_both_tooltips_and_the_stone_as_legacy(self):
        pair = self.pair()
        pair.run(lambda w, d, n: d.Open(2, 0))
        legacy, model = pair.legacy.dialog, pair.board().model
        recorder = pair.novaui.m("nui_tooltip")
        now = pair.novaui.game.state.now
        self.assertEqual(recorder.model_rows({"lines": model["new_lines"]}, now=now), corpus_tool.stand_in_rows(legacy.newToolTip))
        self.assertEqual(recorder.model_rows({"lines": model["old_lines"]}, now=now), corpus_tool.stand_in_rows(legacy.oldToolTip))
        self.assertEqual((model["old_min_w"], model["new_min_w"]), (legacy.oldToolTip.toolTipWidth, legacy.newToolTip.toolTipWidth))
        self.assertEqual(model["old_min_w"], model["new_min_w"], "the old one takes the new one's width")
        self.assertEqual(model["metin_icon"], "/" + legacy.metinImage.image)
        sockets = [e for e in model["new_lines"] if e["t"] == "socket"]
        self.assertEqual(sockets[0]["icon"], "/icon/item/28000.tga", "the stone in the first silver socket")

    def test_yes_uses_the_stone_and_plays_its_sound(self):
        pair = self.pair()
        pair.run(lambda w, d, n: d.Open(2, 0))
        legacy, novaui = pair.run(lambda w, d, n: press(w, d, n, "accept"))
        self.assertEqual(legacy, novaui)
        self.assertEqual(legacy, [("net.SendItemUseToItemPacket", (2, 0)), ("snd.PlaySound", ("sound/ui/metinstone_insert.wav",))])
        self.assertFalse(pair.novaui.dialog.IsShow())

    def test_no_and_the_close_button_send_nothing(self):
        for which in ("cancel", "close"):
            pair = self.pair()
            pair.run(lambda w, d, n: d.Open(2, 0))
            legacy, novaui = pair.run(lambda w, d, n: press(w, d, n, which))
            self.assertEqual(legacy, novaui)
            self.assertEqual(legacy, [])
            self.assertFalse(pair.novaui.dialog.IsShow())
            self.assertIsNone(pair.board())

    def test_a_gold_stone_takes_the_gold_socket(self):
        items = [{"pos": 2, "vnum": 900004}, {"pos": 0, "vnum": 10, "sockets": [SILVER, GOLD, 0]}]
        pair = self.pair(items)
        pair.run(lambda w, d, n: d.Open(2, 0))
        sockets = [e for e in pair.board().model["new_lines"] if e["t"] == "socket"]
        self.assertEqual([(e["frame"], bool(e["icon"])) for e in sockets], [("silver", False), ("gold", True)])

    def test_legacy_has_no_escape_here_and_novaui_adds_none(self):
        pair = self.pair()
        self.assertFalse(hasattr(type(pair.legacy.dialog), "OnPressEscapeKey") and
                         "OnPressEscapeKey" in vars(pair.legacy.m("uiAttachMetin").AttachMetinDialog))
        self.assertNotIn("OnPressEscapeKey", vars(type(pair.novaui.dialog)))

    def test_the_board_opens_at_the_corner_and_the_legacy_window_stays_0_by_0(self):
        pair = self.pair()
        pair.run(lambda w, d, n: d.Open(2, 0))
        self.assertEqual(pair.board().placement, ("position", 0, 0, (0.0, 0.0)))
        self.assertEqual(pair.novaui.dialog.size, (0, 0))


class Facades(unittest.TestCase):
    CLASSES = (("nui_refine", "RefineDialogNew", "uiRefine", "RefineDialogNew"),
               ("nui_refine", "RefineDialog", "uiRefine", "RefineDialog"),
               ("nui_attach_metin", "AttachMetinDialog", "uiAttachMetin", "AttachMetinDialog"))

    def test_every_legacy_method_is_there_with_a_signature_legacys_callers_can_use(self):
        world = corpus_tool.DialogWorld(data(), recorder=True)
        for module, cls, legacy_module, legacy_cls in self.CLASSES:
            ours, theirs = getattr(world.m(module), cls), getattr(world.m(legacy_module), legacy_cls)
            self.assertTrue(issubclass(ours, theirs))
            self.assertTrue(ours.NUI_FACADE)
            for name, member in inspect.getmembers(theirs, inspect.isfunction):
                if name.startswith("__"):
                    continue
                mine = getattr(ours, name)
                self.assertEqual(len(inspect.signature(mine).parameters), len(inspect.signature(member).parameters),
                                 "%s.%s" % (cls, name))
            for name in ("nui_ready", "nui_discard", "Show", "Hide", "SetTop", "Destroy", "UpdateDialog"):
                self.assertIn(name, dir(ours))

    def test_the_wiring_lines_are_spec_6_7s(self):
        interface = read(os.path.join(support.ROOT, "interfacemodule.py"))
        inventory = read(os.path.join(support.ROOT, "uiinventory.py"))
        self.assertIn('nui_windows.make("refine", uiRefine.RefineDialogNew, "nui_refine.RefineDialogNew")', interface)
        self.assertIn('nui_windows.make("refine", uiRefine.RefineDialog, "nui_refine.RefineDialog")', inventory)
        self.assertIn('nui_windows.make("attach-metin", uiAttachMetin.AttachMetinDialog, "nui_attach_metin.AttachMetinDialog")',
                      inventory)

    def test_no_dialog_runs_python_per_frame(self):
        for name in ("nui_refine", "nui_attach_metin"):
            text = read(os.path.join(support.ROOT, name + ".py"))
            for hook in ("def OnUpdate", "def OnRender"):
                self.assertNotIn(hook, text, name)

    def test_destroy_takes_the_board_with_it(self):
        pair = Pair("new", GLAIVE)
        pair.run(open_new)
        with pair.novaui:
            pair.novaui.dialog.Destroy()
        self.assertIsNone(pair.novaui.dialog.demand)


class Fixtures(unittest.TestCase):
    """Each fixture holds the model's keys with their kinds (and is the
    model the fixture writer builds, tools/nui_tooltip_corpus.py fixtures)."""

    def test_the_fixtures_are_current(self):
        for (window, variant), model in sorted(corpus_tool.dialog_fixtures().items()):
            name = "%s.%s.fixture.json" % (window, variant) if variant else "%s.fixture.json" % window
            self.assertEqual(json.loads(read(os.path.join(WINDOWS, window, name))), json.loads(corpus_tool._text(model)), name)

    def test_the_fixtures_hold_the_dialogs_keys(self):
        pair = Pair("new", GLAIVE)
        attach = Pair("attach", Attach.ITEMS)
        for window, state in (("refine", pair.novaui.dialog._state), ("attach-metin", attach.novaui.dialog._state)):
            model = json.loads(read(os.path.join(WINDOWS, window, window + ".fixture.json")))
            (only,) = model.values()
            self.assertEqual(sorted(only), sorted(state), window)
            for key, value in state.items():
                self.assertEqual(type(only[key]), type(value), "%s %s" % (window, key))


if __name__ == "__main__":
    unittest.main()
