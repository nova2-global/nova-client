"""Tests for the NovaUI Wave 3b item windows (P14 spec 6.1 to 6.3, 6.6):
the inventory (assets/root/nui_inventory.py) with its costume and belt
windows (nui_costume.py, nui_belt_inventory.py), the select item window
(nui_select_item.py) and their wiring in interfacemodule.py and
uiinventory.py: python3 -B -m unittest nui_inventory_test (from tools/).

Plain CPython over nui_game_support's stand-ins (install_wave3b_ui reads the
real uiscript files, so the legacy windows are made as the client makes
them, and their slot windows fire the events the C++ CSlotWindow sends).
For every window:
- facade: every method the Interface, game.py or another window calls on
  the legacy class exists on the NovaUI class with a signature the legacy
  callers can use, with the legacy class's name and constructor;
- differential: the legacy class and the NovaUI class, each in a world of
  its own with the same state, driven through the same flows (the legacy
  slot window's C++ events against the board's data events), make the same
  net, player, mouse, app, chat, ime, interface and dialog calls in order,
  getters left out (6.1's flow table, every row);
- model: what the board shows equals what the legacy slot windows show
  (the vnum and count label of every cell, active, unavailable);
- fixture: each board, made with a stand-in owner and set from its fixture,
  holds every key of the fixture with the same kind, and logs nothing;
- on demand: no document while the window is hidden; the board made at Show
  and gone at Hide;
- no per-frame Python: no NovaUI module defines OnUpdate, OnRender or
  OnMouseOverIn;
- the lean grid's element budget (3 per cell, 5 with a count; P14 spec 4.2)
  from the document's markup."""
import contextlib
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import check_nui_snapshots  # noqa: E402

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
FLAGS = "+inventory,+select-item"
NUITOOL = os.environ.get("NUITOOL") or shutil.which("nuitool")
P = support.module_constants()["player"]
I = support.module_constants()["item"]
A = support.APP_CONSTANTS
# The modules whose calls the differential tests compare (P14 spec 6.1: net,
# player.Request* and SetAutoPotionInfo, the mouse controller, ime), and the
# chat lines, sounds, interface calls and dialogs the legacy code makes.
EFFECT_MODULES = ("net", "player", "mouse", "ime", "chat", "snd", "interface", "uiCommon", "uiPickMoney", "uiRefine",
                  "uiAttachMetin")
NOVAUI_MODULES = ("nui_inventory", "nui_costume", "nui_belt_inventory", "nui_select_item")
LOADED_NOVAUI = ("nui_limits", "nui_proxies", "nui_belt_inventory", "nui_costume", "nui_inventory", "nui_select_item")
# Item numbers the flows use (any vnum works; these are the corpus' kinds).
SWORD, GLAIVE, POTION, BLUE_POTION, AUTO_HP, SCROLL, STONE, DETACH, KEY, ARMOR, BELT, CLEAN = (
    10, 3000, 27001, 27002, 72723, 25040, 28030, 25100, 50008, 11200, 18000, 71101)
REFINE_DIALOG = "uiRefine.RefineDialog"


def quiet():
    """The legacy windows print banners."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def stock(game):
    """The state every flow starts from: page I with a 1x2 sword at 0, a 1x3
    glaive at 2, a 10 stack at 4, an active auto potion at 9, a refine
    scroll, a stone, a detach scroll, a key and a cleaning item, armor on
    the body, a belt worn, 1.234.567 Yang, page II with a potion at 45."""
    game.give(0, SWORD, size=(1, 2))
    game.give(2, GLAIVE, size=(1, 3))
    game.give(4, POTION, 10)
    game.give(9, AUTO_HP, 1, sockets=(1, 200, 1000))
    game.give(20, SCROLL, 3)
    game.give(21, STONE)
    game.give(22, DETACH)
    game.give(23, KEY)
    game.give(24, CLEAN)
    game.give(45, BLUE_POTION, 5)
    game.give(I["EQUIPMENT_BODY"], ARMOR, size=(1, 2))
    game.give(I["EQUIPMENT_BELT"], BELT)
    game.give(I["BELT_INVENTORY_SLOT_START"], POTION, 2)
    game.refine_scrolls.add(SCROLL)
    game.metins.add(STONE)
    game.detach_scrolls.add(DETACH)
    game.keys.add(KEY)
    game.use_types[CLEAN] = "USE_CLEAN_SOCKET"
    game.equipment.update((SWORD, GLAIVE, ARMOR, BELT))
    game.elk = 1234567
    game.belt_cells = 4


class World(object):
    """One world: a Game with the legacy item windows and the NovaUI ones
    loaded over its stand-ins, the flags of `windows` on when `nui_on`; the
    Interface stand-in bound as the Interface binds its windows."""

    def __init__(self, nui_on, windows=FLAGS, engine_3b=True, setup=stock, locale=True):
        game = self.game = support.Game(engine_3b=engine_3b)
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        support.install_wave3b_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        if locale:
            game.modules["localeInfo"] = support.locale_info("en")
            # localeinfo.py formats two attach refusals with names only ae's
            # locale_game.txt defines (REFINE_FAILURE_CAN_NOT_ATTACH0) or none
            # does (REFINE_FAILURE_NO_GOLD_SOCKET0): legacy raises NameError
            # there in every other locale, inherited unchanged; the stand-in
            # gives them en's texts so the flows can be compared.
            game.modules["localeInfo"].REFINE_FAILURE_CAN_NOT_ATTACH0 = "%s cannot be included in that Item."
            game.modules["localeInfo"].REFINE_FAILURE_NO_GOLD_SOCKET0 = "There is no Gold socket to include %s ."
        for name in ("networkModule", "interfaceModule"):
            game.put(name, types.ModuleType(name))
        if setup is not None:
            setup(game)
        game.load_standard()
        with quiet():
            game.load("uiInventory", "uiinventory.py").print = lambda *args, **kwargs: None
            game.load("uiselectitem", "uiselectitem.py")
            for name in LOADED_NOVAUI:
                game.load(name, name + ".py")
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on
        self.interface = self._interface()

    def _interface(self):
        return self.game.interface

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def m(self, name):
        return self.game.loaded[name]

    @property
    def mouse(self):
        return self.m("mouseModule").mouseController

    def mark(self):
        return len(self.game.log)

    def effects_since(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in EFFECT_MODULES and not support.is_getter(name)
                and name not in ("player.GetItemLink",)]

    def make_inventory(self):
        """Interface.__MakeWindows' inventory (interfacemodule.py:187-188),
        shown."""
        with self.game, quiet():
            window = self.nui_windows.make("inventory", self.m("uiInventory").InventoryWindow,
                                           "nui_inventory.InventoryWindow")
            window.BindInterfaceClass(self.interface)
            window.SetItemToolTip(self.game.modules["uiToolTip"].ItemToolTip())
            window.SetDragonSoulRefineWindow(self.game.dragon_soul_refine)
            window.Show()
        return window

    def make_select_item(self):
        with self.game, quiet():
            window = self.nui_windows.make("select-item", self.m("uiselectitem").SelectItemWindow,
                                           "nui_select_item.SelectItemWindow")
            window.SetItemToolTip(self.game.modules["uiToolTip"].ItemToolTip())
            window.Hide()
        return window


def board(window):
    demand = getattr(window, "demand", None)
    return demand.board() if demand is not None else None


def fire(window, event, *args):
    """A data event from the window's shown board."""
    shown = board(window)
    if shown is None:
        raise AssertionError("%s has no board" % type(window).__name__)
    return shown.fire(event, *args)


def press(window, event, *args):
    """A mousedown's data event, then the body's own (board_press), which
    RmlUi runs last as the press bubbles; not when the press took the board
    away, and not on a board without one (the belt's: legacy's belt window
    is not float). The last argument is the button."""
    shown = board(window)
    result = fire(window, event, *args)
    if board(window) is shown and hasattr(type(shown), "on_board_press"):
        shown.fire("board_press", args[-1])
    return result




# Where a cell lives: the window that owns the slot window (from the
# inventory), the slot window's attribute, the board's event prefix.
PLACES = {
    "bag": (lambda window: window, "wndItem", "bag"),
    "wear": (lambda window: window, "wndEquip", "wear"),
    "belt": (lambda window: window.wndBelt, "wndBeltInventorySlot", "belt"),
    "costume": (lambda window: window.wndCostume, "wndEquip", "cos"),
}


class Input(object):
    """One player input, as the legacy slot window's C++ sends it and as the
    board sends it. A cell is named by its place ("bag", "wear", "belt",
    "costume") and its legacy slot number (the bag's local cell); `legacy`
    names the slot the C++ answers when it differs (the owner of a covered
    cell), `cell` the board's index when the press is on another cell."""

    def __init__(self, world, window):
        self.world = world
        self.window = window
        self.nui = world.nui_on

    def _where(self, place):
        owner, attribute, prefix = PLACES[place]
        window = owner(self.window)
        return window, getattr(window, attribute), prefix

    def _fire(self, place, event, number, cell, *args):
        window, proxy, prefix = self._where(place)
        index = proxy.index_of(number) if cell is None else cell
        if event == "press":
            press(window, "%s_%s" % (prefix, event), index, *args)
        else:
            fire(window, "%s_%s" % (prefix, event), index, *args)

    def _select(self, slot_window, number):
        """CSlotWindow's left press: the select-item event of an unlocked
        item, else select-empty."""
        slot = slot_window.slots.get(number)
        name = "select_item" if slot is not None and slot["vnum"] and not slot["locked"] else "select_empty"
        slot_window.fire(name, number)

    def press(self, place, number, button=0, legacy=None, cell=None):
        if self.nui:
            self._fire(place, "press", number, cell, button)
            return
        window, slot_window, _ = self._where(place)
        window.SetTop()  # SetTopUIWindow, before the press reaches the window
        target = number if legacy is None else legacy
        if button == 0:
            self._select(slot_window, target)
        else:
            # CSlotWindow::OnMouseRightButtonDown: the picked slot's unselect
            # event whatever is attached (P15 F-2; `legacy` names the slot a
            # grid picks by the attached footprint when it differs).
            slot = slot_window.slots.get(target)
            slot_window.fire("unselect_item" if slot and slot["vnum"] else "unselect_empty", target)

    def right_release(self):
        """The right button's release: the window manager cancels whatever is
        still attached (PythonWindowManager.cpp, RunMouseRightButtonUp); over
        a NovaUI grid the host does the same after the press reached it
        (nui-attach-right)."""
        if self.world.mouse.isAttached():
            self.world.mouse.DeattachObject()

    def release(self, place, number, legacy=None, cell=None):
        """The release of a drag onto the cell (OnMouseLeftButtonUp)."""
        if self.nui:
            self._fire(place, "release", number, cell, 0)
            return
        self._select(self._where(place)[1], number if legacy is None else legacy)

    def use(self, place, number, legacy=None, cell=None):
        if self.nui:
            self._fire(place, "use", number, cell)
            return
        self._where(place)[1].fire("use", number if legacy is None else legacy)

    def over(self, place, number, legacy=None, cell=None):
        if self.nui:
            self._fire(place, "over", number, cell)
            return
        self._where(place)[1].fire("over_in", number if legacy is None else legacy)

    def out(self, place, number, cell=None):
        if self.nui:
            self._fire(place, "out", number, cell)
            return
        self._where(place)[1].fire("over_out")

    def drop(self, place, number, legacy=None, cell=None):
        """A press in a legacy window released over the cell: the C++ slot
        window's release, NovaUI's nuidrop."""
        if self.nui:
            self._fire(place, "drop", number, cell)
            return
        self._select(self._where(place)[1], number if legacy is None else legacy)

    def button(self, legacy_name, event, owner=None):
        """A legacy button's press or the board's control (owner: the
        window that holds the button, the inventory by default)."""
        window = owner or self.window
        if self.nui:
            press(window, event, 0)
            return
        window.SetTop()
        getattr(window, legacy_name).Click()

    def tab(self, page):
        if self.nui:
            press(self.window, "page_press", page, 0)
            return
        self.window.SetTop()
        tab = self.window.inventoryTab[page]
        tab.Down()
        tab.Click()

    def escape(self):
        """Escape on the inventory (the Interface's escape chain calls
        OnPressEscapeKey; the board's close button the same)."""
        if self.nui:
            fire(self.window, "close_press", 0)
            return
        self.window.OnPressEscapeKey()


def attach(owner_kind, slot, vnum, count=1):
    """A before() that attaches another window's item as its window does."""
    def before(world, window):
        player = world.game.modules["player"]
        world.mouse.AttachObject(object(), getattr(player, owner_kind), slot, vnum, count)
    return before


def with_state(*changes):
    """stock() and then each change(game)."""
    def setup(game):
        stock(game)
        for change in changes:
            change(game)
    return setup


def accept_last(world, *args):
    """The OK of the dialog opened last."""
    world.game.dialogs[-1].accept(*args)


class Pair(unittest.TestCase):
    """A legacy world and a NovaUI world with the same state."""

    def worlds(self, setup=stock):
        return World(False, setup=setup), World(True, setup=setup)

    def outcome(self, world, window):
        """What a flow leaves beside its calls: the mouse controller's
        attach, the windows shown, the tooltip's requests."""
        mouse = world.mouse
        attached = (mouse.isAttached(), mouse.GetAttachedType(), mouse.GetAttachedSlotNumber(),
                    mouse.GetAttachedItemIndex(), mouse.GetAttachedItemCount()) if mouse.isAttached() else (False,)
        costume = window.wndCostume
        belt = window.wndBelt
        return {
            "attached": attached,
            "inventory": bool(window.IsShow()),
            "costume": bool(costume.IsShow()) if costume else None,
            "belt": bool(belt.IsShow()) if belt else None,
            "belt_open": bool(belt.IsOpeningInventory()) if belt else None,
            "tooltip": list(window.tooltipItem.shown) if window.tooltipItem is not None else None,
            "dialogs": [(dialog._name, dialog.is_open) for dialog in world.game.dialogs],
        }

    def run_flow(self, flow, setup=stock, before=None):
        """flow(world, window, input) in both worlds; their calls and outcomes."""
        results = []
        for world in self.worlds(setup):
            window = world.make_inventory()
            with world.game, quiet():
                if before is not None:
                    before(world, window)
                if window.tooltipItem is not None:
                    window.tooltipItem.shown[:] = []
                mark = world.mark()
                flow(world, window, Input(world, window))
                results.append((world.effects_since(mark), self.outcome(world, window), world, window))
        return results

    def same(self, flow, setup=stock, before=None, expect=()):
        """The flow's calls and outcome equal in both worlds; the legacy one
        makes each call named in expect."""
        (legacy, legacy_outcome, _, _), (novaui, novaui_outcome, world, window) = self.run_flow(flow, setup, before)
        self.assertEqual(legacy, novaui)
        self.assertEqual(legacy_outcome, novaui_outcome)
        names = [name for name, _ in legacy]
        for wanted in expect:
            self.assertIn(wanted, names, "the legacy flow makes no %s call: %r" % (wanted, legacy))
        return legacy, world, window


class F2RightPressWhileAttached(Pair):
    """P15 F-2 (spec 8.2): a right press on an item while another is
    attached does what legacy's CSlotWindow does, the clicked item's
    unselect event (uiInventory.UseItemSlot uses it, then drops the
    attach), while nui_slots.ATTACH_RIGHT holds."""

    def test_a_right_press_on_a_potion_while_a_stack_is_attached_uses_the_potion(self):
        def flow(w, win, i):
            i.press("bag", 20)          # the refine scrolls, attached
            i.press("bag", 9, 1)        # a right press on the auto potion
            i.right_release()
        legacy, world, window = self.same(flow, expect=["mouse.AttachObject", "net.SendItemUsePacket"])
        used = [args for name, args in legacy if name == "net.SendItemUsePacket"]
        self.assertEqual(used, [(9,)], "the clicked item, not the attached one")
        self.assertFalse(world.mouse.isAttached())

    def test_a_right_press_on_an_empty_cell_while_attached_sends_nothing_and_the_release_drops_it(self):
        def flow(w, win, i):
            i.press("bag", 4)
            i.press("bag", 30, 1)
            i.right_release()
        legacy, world, window = self.same(flow, expect=["mouse.AttachObject"])
        self.assertFalse([name for name, _ in legacy if name.startswith("net.")])
        self.assertFalse(world.mouse.isAttached())

    def test_with_the_switch_off_the_press_uses_nothing(self):
        """Wave 3b's rule (the host cancels the attach over NovaUI and the
        press uses nothing), what reverting F-2's commit restores."""
        legacy, novaui = self.worlds()
        novaui.m("nui_slots").ATTACH_RIGHT = False
        calls = []
        for world in (novaui,):
            window = world.make_inventory()
            with world.game, quiet():
                mark = world.mark()
                i = Input(world, window)
                i.press("bag", 20)
                i.press("bag", 9, 1)
                calls = world.effects_since(mark)
        self.assertNotIn("net.SendItemUsePacket", [name for name, _ in calls])

    def test_every_grid_of_the_inventory_binds_the_switch_on(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            window.ClickCostumeButton()
        for state in (window._state, window.wndCostume._state, window.wndBelt._state):
            self.assertIs(state["attach_right"], True)


class Construction(Pair):
    def test_the_flag_makes_the_novaui_class_and_without_it_the_legacy_one(self):
        legacy, novaui = self.worlds()
        a = legacy.make_inventory()
        b = novaui.make_inventory()
        self.assertIs(type(a), legacy.m("uiInventory").InventoryWindow)
        self.assertIs(type(b), novaui.m("nui_inventory").InventoryWindow)
        self.assertIsNotNone(board(b))
        self.assertIs(type(b.wndBelt), novaui.m("nui_belt_inventory").BeltInventoryWindow)

    def test_without_the_3b_engine_or_a_document_the_legacy_class_is_made(self):
        old = World(True, engine_3b=False)
        self.assertIs(type(old.make_inventory()), old.m("uiInventory").InventoryWindow)
        failing = World(True)
        failing.game.state.failing.add("nui/windows/inventory/inventory.rml")
        self.assertIs(type(failing.make_inventory()), failing.m("uiInventory").InventoryWindow)
        self.assertEqual(failing.game.loaded_documents(), [], "the discarded facade unloads every board")

    def test_the_legacy_window_underneath_stays_0_by_0_and_shows_with_the_board(self):
        world = World(True)
        window = world.make_inventory()
        self.assertEqual((window.GetWidth(), window.GetHeight()), (0, 0))
        self.assertTrue(window.IsShow())
        self.assertEqual(window.ElementDictionary if hasattr(window, "ElementDictionary") else {}, {})
        for belt_or_costume in (window.wndBelt,):
            self.assertEqual((belt_or_costume.GetWidth(), belt_or_costume.GetHeight()), (0, 0))


class Facade(unittest.TestCase):
    """Every member the callers use, with the legacy signature (P14 spec 6.1:
    the facade surface; 6.2, 6.3, 6.6)."""

    SURFACE = {
        ("uiInventory", "InventoryWindow", "nui_inventory"): (
            "BindInterfaceClass", "Close", "Destroy", "Hide", "IsShow", "OverOutItem", "RefreshItemSlot",
            "RefreshStatus", "SetDragonSoulRefineWindow", "SetItemToolTip", "SetTop", "Show", "UseDSSButtonEffect",
            "OverInItem", "UseItemSlot", "SelectEmptySlot", "SelectItemSlot", "GetGlobalPosition", "OnTop",
            "OnPressEscapeKey", "SetInventoryPage", "SetEquipmentPage", "ClickCostumeButton", "OpenPickMoneyDialog",
            "OnMoveWindow"),
        ("uiInventory", "CostumeWindow", "nui_costume"): ("Show", "Hide", "Close", "IsShow", "SetTop",
                                                          "RefreshCostumeSlot", "Destroy"),
        ("uiInventory", "BeltInventoryWindow", "nui_belt_inventory"): (
            "Show", "Hide", "Close", "IsShow", "SetTop", "RefreshSlot", "IsOpeningInventory", "OpenInventory",
            "CloseInventory", "GetBasePosition", "AdjustPositionAndSize", "Destroy"),
        ("uiselectitem", "SelectItemWindow", "nui_select_item"): (
            "Open", "Close", "Hide", "Show", "IsShow", "SetTop", "Destroy", "SetItemToolTip", "SelectItemSlot",
            "OverInItem", "OverOutItem", "RefreshSlot", "SetTableSize"),
    }

    def setUp(self):
        self.world = World(True)

    def test_each_member_exists_with_the_legacy_signature(self):
        for (legacy_module, name, novaui_module), members in self.SURFACE.items():
            legacy = getattr(self.world.m(legacy_module), name)
            novaui = getattr(self.world.m(novaui_module), name)
            self.assertTrue(issubclass(novaui, legacy), "%s subclasses the legacy class (D25)" % name)
            self.assertEqual(novaui.__name__, name)
            self.assertTrue(novaui.NUI_FACADE)
            self.assertEqual(inspect.signature(novaui.__init__), inspect.signature(legacy.__init__))
            for member in members:
                self.assertTrue(callable(getattr(novaui, member, None)), "%s.%s" % (name, member))
                if member in vars(legacy):
                    self.assertEqual(inspect.signature(getattr(novaui, member)),
                                     inspect.signature(getattr(legacy, member)), "%s.%s" % (name, member))

    def test_every_legacy_method_a_window_overrides_keeps_its_signature(self):
        for (legacy_module, name, novaui_module), _ in self.SURFACE.items():
            legacy = getattr(self.world.m(legacy_module), name)
            novaui = getattr(self.world.m(novaui_module), name)
            for member, value in vars(novaui).items():
                if callable(value) and member in vars(legacy):
                    self.assertEqual(inspect.signature(value), inspect.signature(vars(legacy)[member]),
                                     "%s.%s" % (name, member))

    def test_each_loader_override_is_the_name_the_legacy_constructor_calls(self):
        for module, name, loader in (("nui_inventory", "InventoryWindow", "_InventoryWindow__LoadWindow"),
                                     ("nui_costume", "CostumeWindow", "_CostumeWindow__LoadWindow"),
                                     ("nui_belt_inventory", "BeltInventoryWindow", "_BeltInventoryWindow__LoadWindow"),
                                     ("nui_select_item", "SelectItemWindow", "LoadWindow")):
            cls = getattr(self.world.m(module), name)
            self.assertIn(loader, vars(cls), "%s overrides %s" % (name, loader))
            self.assertIn(loader, vars(cls.__mro__[1]), "the legacy class has %s" % loader)


class Wiring(unittest.TestCase):
    """The legacy lines of P14 spec 6.7, exactly, each file's in this order;
    the number is the line each stood at when written (P18: they are found
    by their content, so a change elsewhere in the file moves them and fails
    nothing)."""

    LINES = {
        "interfacemodule.py": (
            (187, 'wndInventory = nui_windows.make("inventory", uiInventory.InventoryWindow, "nui_inventory.InventoryWindow")'),
            (257, 'self.hyperlinkItemTooltip = nui_windows.make("tooltips", uiToolTip.HyperlinkItemToolTip, "nui_link_tooltip.HyperlinkItemToolTip")'),
            (260, 'self.tooltipItem = nui_windows.make("tooltips", uiToolTip.ItemToolTip, "nui_item_tooltip.ItemToolTip")'),
            (263, 'self.tooltipSkill = nui_windows.make("tooltips", uiToolTip.SkillToolTip, "nui_skill_tooltip.SkillToolTip")'),
            (269, 'self.dlgRefineNew = nui_windows.make("refine", uiRefine.RefineDialogNew, "nui_refine.RefineDialogNew")'),
            (303, 'self.wndItemSelect = nui_windows.make("select-item", uiselectitem.SelectItemWindow, "nui_select_item.SelectItemWindow")'),
        ),
        "uiinventory.py": (
            (21, "import nui_windows"),
            (354, 'self.refineDialog = nui_windows.make("refine", uiRefine.RefineDialog, "nui_refine.RefineDialog")'),
            (358, 'self.attachMetinDialog = nui_windows.make("attach-metin", uiAttachMetin.AttachMetinDialog, "nui_attach_metin.AttachMetinDialog")'),
        ),
    }

    def test_the_changed_lines_are_the_spec_s(self):
        for file_name, lines in self.LINES.items():
            found = support.find_lines(read(os.path.join(ROOT, file_name)), [line for _, line in lines])
            for (number, line), at in zip(lines, found):
                self.assertIsNotNone(at, "%s (line %d when written), in order: %s" % (file_name, number, line))

    def test_a_change_elsewhere_in_a_file_moves_the_lines_and_fails_nothing(self):
        """P18: the cube renewal (nova-client#3) moves interfacemodule.py's
        lines by a few; the lines are found by their content, in order. A
        changed line, or two out of their order, is still found missing."""
        for file_name, lines in self.LINES.items():
            text = read(os.path.join(ROOT, file_name))
            wanted = [line for _, line in lines]
            rows = text.split("\n")
            shifted = "\n".join(["# moved"] * 3 + rows[:150] + ["", "# a few more lines", "pass", ""] + rows[150:])
            found = support.find_lines(shifted, wanted)
            self.assertNotIn(None, found, file_name)
            self.assertEqual(found, sorted(found), file_name)
            changed = text.replace(wanted[-1], wanted[-1].replace("nui_windows.make(", "nui_windows.made("), 1)
            self.assertIsNone(support.find_lines(changed, wanted)[-1], file_name)
            if len(wanted) > 1:
                self.assertIn(None, support.find_lines(text, list(reversed(wanted))), file_name)

    def test_the_novaui_inventory_makes_the_dialogs_through_the_same_calls(self):
        source = read(os.path.join(ROOT, "nui_inventory.py"))
        self.assertIn('nui_windows.make("refine", uiRefine.RefineDialog, "nui_refine.RefineDialog")', source)
        self.assertIn('nui_windows.make("attach-metin", uiAttachMetin.AttachMetinDialog,', source)

    def test_with_the_flags_off_the_dialogs_are_legacy_s(self):
        world = World(False)
        window = world.make_inventory()
        self.assertIsInstance(window.refineDialog, support.LegacyDialogWindow)
        self.assertIsInstance(window.attachMetinDialog, support.LegacyDialogWindow)


class Model(Pair):
    """What the board shows equals what the legacy slot windows show."""

    def shown_bag(self, world, window):
        """{local cell: (vnum, count label, active)} from the board."""
        proxy = window.wndItem
        found = {}
        vnums = proxy.vnums()
        for cell in board(window).model["bag"]:
            if cell["kind"] == "item":
                found[cell["index"]] = (vnums[cell["index"]], cell["count"], cell["active"])
        return found

    def shown_named(self, cells, proxy):
        vnums = proxy.vnums()
        return dict((proxy.slot_number(cell["index"]), (vnums[cell["index"]], cell["count"], cell["active"]))
                    for cell in cells if cell["kind"] == "item")

    def test_the_bag_the_wear_cells_and_the_money_equal_legacy_s(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_inventory(), novaui.make_inventory()
        model = board(b).model
        self.assertEqual(self.shown_bag(novaui, b), a.wndItem.shown())
        self.assertEqual(self.shown_named(model["wear"], b.wndEquip), a.wndEquip.shown())
        self.assertEqual(model["money"], a.wndMoney.GetText())
        self.assertEqual(model["money_value"], 1234567)
        self.assertEqual([cell["name"] for cell in model["wear"]],
                         [slot.name for slot in novaui.m("nui_limits").wear_group("equipment")])

    def test_multi_cell_items_cover_their_cells(self):
        world = World(True)
        model = board(world.make_inventory()).model["bag"]
        self.assertEqual([cell["index"] for cell in model if cell["covered"]], [5, 7, 12])
        self.assertEqual((model[0]["h"], model[2]["h"]), (2, 3))

    def test_the_second_page_and_back(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_inventory(), novaui.make_inventory()
        for page in (1, 0):
            with legacy.game, quiet():
                Input(legacy, a).tab(page)
            with novaui.game, quiet():
                Input(novaui, b).tab(page)
            self.assertEqual(self.shown_bag(novaui, b), a.wndItem.shown(), "page %d" % page)
            self.assertEqual(board(b).model["page"], page)
            self.assertEqual(b.inventoryPageIndex, a.inventoryPageIndex)

    def test_an_auto_potion_on_page_two_is_active_at_its_local_cell(self):
        def potion(game):
            game.give(50, AUTO_HP, 1, sockets=(1, 10, 100))
        legacy, novaui = self.worlds(with_state(potion))
        a, b = legacy.make_inventory(), novaui.make_inventory()
        for world, window in ((legacy, a), (novaui, b)):
            with world.game, quiet():
                Input(world, window).tab(1)
        self.assertEqual(self.shown_bag(novaui, b)[5], (AUTO_HP, "", True))
        self.assertEqual(self.shown_bag(novaui, b), a.wndItem.shown())

    def test_a_refresh_while_hidden_reaches_the_next_board(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            window.Hide()
            self.assertIsNone(board(window))
            world.game.give(6, POTION, 7)
            world.game.elk = 99
            window.RefreshItemSlot()
            window.RefreshStatus()
            window.Show()
        model = board(window).model
        self.assertEqual(model["bag"][6]["count"], "7")
        self.assertEqual(model["money_value"], 99)

    def test_the_belt_s_cells_and_its_unavailable_ones_equal_legacy_s(self):
        def single(game):
            # The belt's refresh passes a count of 1, which CSlotWindow shows.
            game.give(I["BELT_INVENTORY_SLOT_START"] + 1, BLUE_POTION, 1)
        legacy, novaui = self.worlds(with_state(single))
        a, b = legacy.make_inventory(), novaui.make_inventory()
        cells = board(b.wndBelt).model["cells"]
        legacy_slots = a.wndBelt.wndBeltInventorySlot.slots
        self.assertEqual([cell["unavailable"] for cell in cells],
                         [legacy_slots[number]["unavailable"] for number in sorted(legacy_slots)])
        self.assertEqual(self.shown_named(cells, b.wndBelt.wndBeltInventorySlot), a.wndBelt.wndBeltInventorySlot.shown())
        self.assertEqual(cells[1]["count"], "1")

    def test_the_footprint_of_an_attached_tall_item_and_the_picked_cell(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            Input(world, window).press("bag", 0)
            Input(world, window).over("bag", 6)
        cells = board(window).model["bag"]
        self.assertEqual(dict((c["index"], c["target"]) for c in cells if c["target"]), {6: "move", 11: "move"})
        self.assertTrue(cells[0]["picked"])
        with world.game, quiet():
            Input(world, window).out("bag", 6)
        self.assertEqual([c["index"] for c in board(window).model["bag"] if c["target"]], [])

    def test_a_refine_scroll_over_an_item_marks_it_usable(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            Input(world, window).press("bag", 20)
            Input(world, window).over("bag", 0)
        cells = board(window).model["bag"]
        self.assertEqual(cells[0]["target"], "usable")
        self.assertTrue(window.wndItem.use_mode)

    def test_the_dragon_soul_button_s_effect_is_a_model_key(self):
        world = World(True)
        window = world.make_inventory()
        with world.game:
            window.UseDSSButtonEffect(True)
        self.assertTrue(board(window).model["dss_active"])
        with world.game:
            window.UseDSSButtonEffect(False)
        self.assertFalse(board(window).model["dss_active"])


class ModernMarks(unittest.TestCase):
    """What the modern skins add to the bag and the wear cells: the refine
    level ("+N", nui_slots.REFINE_KEY: the inventory's grids opt in), the
    marks of the empty unique, arrow and belt places, and the taskbar's
    inventory button, told at each Show and Hide."""

    def world(self):
        world = World(True)
        item = world.game.modules["item"]
        item.ITEM_TYPE_WEAPON, item.ITEM_TYPE_ARMOR, item.ITEM_TYPE_BELT = 1, 2, 34
        names = {SWORD: "Sword+6", GLAIVE: "Glaive+5", ARMOR: "Armour+3", POTION: "Potion+2", BELT: "Belt"}
        kinds = {SWORD: 1, GLAIVE: 1, ARMOR: 2, POTION: 3, BELT: 34}
        item.GetItemName = lambda: names.get(item.selected[0], "")
        item.GetItemType = lambda: kinds.get(item.selected[0], 0)
        return world

    def test_the_bag_and_the_wear_cells_carry_the_refine_level(self):
        model = board(self.world().make_inventory()).model
        refine = [cell["refine"] for cell in model["bag"]]
        self.assertEqual((refine[0], refine[2], refine[4], refine[5]), (6, 5, 0, 0), "a potion's +2 is no level")
        self.assertEqual(sum(1 for level in refine if level), 2)
        wear = dict((cell["name"], cell["refine"]) for cell in model["wear"])
        self.assertEqual((wear["body"], wear["belt"], wear["weapon"]), (3, 0, 0))

    def test_empty_unique_arrow_and_belt_places_show_their_mark(self):
        window = self.world().make_inventory()
        marks = dict((cell["name"], cell["marks"]) for cell in board(window).model["wear"])
        self.assertEqual((marks["unique1"], marks["unique2"], marks["arrow"]), (["unique"], ["unique"], ["arrow"]))
        self.assertEqual((marks["belt"], marks["body"], marks["weapon"]), ([], [], []), "worn, or a place without a mark")

    def test_show_and_hide_tell_the_taskbar(self):
        world = self.world()
        told = []

        class Bar(object):
            def nui_window_shown(self, name, shown):
                told.append((name, bool(shown)))
        bar = Bar()
        hud = world.m("nui_hud")
        hud.take_over("taskbar", bar)
        self.addCleanup(hud.forget, "taskbar", bar)
        window = world.make_inventory()
        with world.game, quiet():
            window.Hide()
            window.Show()
        self.assertEqual(told, [("inventory", True), ("inventory", False), ("inventory", True)])


class Flows(Pair):
    """6.1's flow table, every row: the same calls in the same order."""

    # --- use -------------------------------------------------------------------------

    def test_use_by_a_right_press(self):
        self.same(lambda w, win, i: i.press("bag", 4, 1), expect=["net.SendItemUsePacket"])

    def test_use_by_a_double_click(self):
        self.same(lambda w, win, i: i.use("bag", 4), expect=["net.SendItemUsePacket"])

    def test_use_on_a_cell_a_tall_item_covers(self):
        self.same(lambda w, win, i: i.use("bag", 0, cell=5), expect=["net.SendItemUsePacket"])
        self.same(lambda w, win, i: i.press("bag", 2, 1, cell=12), expect=["net.SendItemUsePacket"])

    def test_use_with_the_confirmation_question(self):
        def confirm(game):
            game.item_flags_of[POTION] = game.modules["item"].ITEM_FLAG_CONFIRM_WHEN_USE

        def flow(w, win, i):
            i.press("bag", 4, 1)
            accept_last(w)
        self.same(flow, with_state(confirm), expect=["uiCommon.QuestionDialog.Open", "net.SendItemUsePacket"])

    def test_no_use_while_a_private_shop_is_built(self):
        def building(game):
            game.answer("uiPrivateShopBuilder", "IsBuildingPrivateShop", 1)
        self.same(lambda w, win, i: i.press("bag", 4, 1), with_state(building), expect=["chat.AppendChat"])

    def test_use_with_the_dragon_soul_refine_window_open(self):
        def refine_open(world, window):
            world.game.dragon_soul_refine.shown = True
        self.same(lambda w, win, i: i.use("bag", 4), before=refine_open, expect=["interface.AutoSetItem"])

    def test_use_of_a_worn_item_takes_it_off(self):
        self.same(lambda w, win, i: i.press("wear", I["EQUIPMENT_BODY"], 1), expect=["net.SendItemUsePacket"])

    # --- pick, move, swap, merge ---------------------------------------------------------

    def test_pick(self):
        self.same(lambda w, win, i: i.press("bag", 4), expect=["mouse.AttachObject", "snd.PlaySound"])

    def test_pick_a_glaive_by_a_cell_it_covers(self):
        self.same(lambda w, win, i: i.press("bag", 2, cell=7), expect=["mouse.AttachObject"])

    def test_a_press_and_a_release_on_the_same_cell_keeps_the_item_attached(self):
        def flow(w, win, i):
            i.press("bag", 4)
            if i.nui:
                i.release("bag", 4)
        self.same(flow, expect=["mouse.AttachObject"])

    def test_move_by_a_second_press(self):
        def flow(w, win, i):
            i.press("bag", 4)
            i.press("bag", 6)
        self.same(flow, expect=["net.SendItemMovePacket", "mouse.DeattachObject"])

    def test_move_by_a_drag(self):
        def flow(w, win, i):
            i.press("bag", 4)
            i.release("bag", 6)
        self.same(flow, expect=["net.SendItemMovePacket"])

    def test_move_a_tall_item(self):
        def flow(w, win, i):
            i.press("bag", 0)
            i.press("bag", 1)
        self.same(flow, expect=["net.SendItemMovePacket"])

    def test_merge_onto_a_stack(self):
        def stack(game):
            game.give(6, POTION, 5)

        def flow(w, win, i):
            i.press("bag", 4)
            i.press("bag", 6)
        legacy, _, _ = self.same(flow, with_state(stack), expect=["net.SendItemMovePacket"])
        self.assertIn(("net.SendItemMovePacket", (4, 6, 0)), legacy)

    def test_move_to_the_second_page(self):
        def flow(w, win, i):
            i.press("bag", 4)
            i.tab(1)
            i.press("bag", 1)
        legacy, _, _ = self.same(flow, expect=["net.SendItemMovePacket"])
        self.assertIn(("net.SendItemMovePacket", (4, 46, 10)), legacy)

    def test_equip_by_a_drop_on_an_empty_wear_cell(self):
        def flow(w, win, i):
            i.press("bag", 0)
            i.press("wear", I["EQUIPMENT_WEAPON"])
        self.same(flow, expect=["net.SendItemMovePacket"])

    def test_equip_by_a_drop_on_a_worn_item(self):
        def flow(w, win, i):
            i.press("bag", 2)
            i.press("wear", I["EQUIPMENT_BODY"])
        self.same(flow, expect=["net.SendItemUsePacket"])

    def test_take_off_by_a_drop_in_the_bag(self):
        def flow(w, win, i):
            i.press("wear", I["EQUIPMENT_BODY"])
            i.release("bag", 6)
        self.same(flow, expect=["mouse.AttachObject", "net.SendItemMovePacket"])

    # --- split, sell, buy ------------------------------------------------------------------

    def test_split(self):
        def flow(w, win, i):
            w.game.pressed.add(A["DIK_LSHIFT"])
            i.press("bag", 4)
            accept_last(w, 3)
            w.game.pressed.clear()
            i.press("bag", 6)
        legacy, _, _ = self.same(flow, expect=["uiPickMoney.PickMoneyDialog.Open", "net.SendItemMovePacket"])
        self.assertIn(("net.SendItemMovePacket", (4, 6, 3)), legacy)

    def test_sell(self):
        def flow(w, win, i):
            w.game.cursor = A["SELL"]
            i.press("bag", 4)
            accept_last(w)
        self.same(flow, expect=["uiCommon.QuestionDialog.Open", "net.SendShopSellPacketNew", "snd.PlaySound"])

    def test_sell_of_an_item_that_cannot_be_sold(self):
        def no_sell(game):
            game.antiflags[POTION] = game.modules["item"].ANTIFLAG_SELL

        def flow(w, win, i):
            w.game.cursor = A["SELL"]
            i.press("bag", 4)
        self.same(flow, with_state(no_sell), expect=["uiCommon.PopupDialog.Open"])

    def test_the_buy_cursor(self):
        def flow(w, win, i):
            w.game.cursor = A["BUY"]
            i.press("bag", 4)
        self.same(flow, expect=["chat.AppendChat"])

    def test_buy_by_a_drag_from_a_shop(self):
        self.same(lambda w, win, i: i.press("bag", 6), before=attach("SLOT_TYPE_SHOP", 3, POTION),
                  expect=["net.SendShopBuyPacket"])

    def test_a_private_shop_item_dropped_in(self):
        def before(world, window):
            attach("SLOT_TYPE_PRIVATE_SHOP", 3, POTION)(world, window)
            world.mouse.SetCallBack("INVENTORY", lambda: world.game.log.append(("interface.PrivateShopCallBack", ())))
        self.same(lambda w, win, i: i.press("bag", 6), before=before, expect=["interface.PrivateShopCallBack"])

    # --- safebox, mall, link, quickslot ---------------------------------------------------------

    def test_safebox_money_dropped_in(self):
        self.same(lambda w, win, i: i.press("bag", 6),
                  before=attach("SLOT_TYPE_SAFEBOX", 0, P_ITEM_MONEY, 5000),
                  expect=["net.SendSafeboxWithdrawMoneyPacket", "snd.PlaySound"])

    def test_a_safebox_item_dropped_in(self):
        legacy, _, _ = self.same(lambda w, win, i: i.drop("bag", 6), before=attach("SLOT_TYPE_SAFEBOX", 7, POTION),
                                 expect=["net.SendSafeboxCheckoutPacket"])
        self.assertIn(("net.SendSafeboxCheckoutPacket", (7, 6)), legacy)

    def test_a_mall_item_dropped_in(self):
        self.same(lambda w, win, i: i.press("bag", 6), before=attach("SLOT_TYPE_MALL", 2, POTION),
                  expect=["net.SendMallCheckoutPacket"])

    def test_a_link_by_alt(self):
        def flow(w, win, i):
            w.game.pressed.add(A["DIK_LALT"])
            i.press("bag", 4)
        self.same(flow, expect=["ime.PasteString"])

    def test_a_quickslot_by_ctrl(self):
        def flow(w, win, i):
            w.game.pressed.add(A["DIK_LCONTROL"])
            i.press("bag", 4)
        self.same(flow, expect=["player.RequestAddToEmptyLocalQuickSlot"])

    def test_a_quickslot_refused(self):
        def no_quick(game):
            game.no_quick.add(POTION)

        def flow(w, win, i):
            w.game.pressed.add(A["DIK_LCONTROL"])
            i.press("bag", 4)
        self.same(flow, with_state(no_quick), expect=["chat.AppendChat"])

    # --- refine, attach, detach, item on item --------------------------------------------------

    def test_refine(self):
        def flow(w, win, i):
            i.press("bag", 20)
            i.press("bag", 0)
        legacy, _, _ = self.same(flow, expect=["net.SendItemUseToItemPacket"])
        self.assertIn(("net.SendItemUseToItemPacket", (20, 0)), legacy)

    def test_refine_on_a_cell_the_target_covers(self):
        def flow(w, win, i):
            i.press("bag", 20)
            i.press("bag", 0, cell=5)
        self.same(flow, expect=["net.SendItemUseToItemPacket"])

    def test_refine_by_a_drag(self):
        def flow(w, win, i):
            i.press("bag", 20)
            i.release("bag", 2, cell=12)
        self.same(flow, expect=["net.SendItemUseToItemPacket"])

    def test_refine_refused(self):
        def cant(game):
            game.answer("player", "CanRefine", game.modules["player"].REFINE_CANT)

        def flow(w, win, i):
            i.press("bag", 20)
            i.press("bag", 0)
        legacy, _, _ = self.same(flow, with_state(cant))
        self.assertNotIn("net.SendItemUseToItemPacket", [name for name, _ in legacy])

    def test_attach(self):
        def flow(w, win, i):
            i.press("bag", 21)
            i.press("bag", 0)
        self.same(flow, expect=["uiAttachMetin.AttachMetinDialog.Open"])

    def test_attach_refusals(self):
        for result in ("ATTACH_METIN_NOT_MATCHABLE_ITEM", "ATTACH_METIN_NO_MATCHABLE_SOCKET",
                       "ATTACH_METIN_NOT_EXIST_GOLD_SOCKET", "ATTACH_METIN_CANT_ATTACH_TO_EQUIPMENT"):
            def refused(game, result=result):
                game.answer("player", "CanAttachMetin", getattr(game.modules["player"], result))

            def flow(w, win, i):
                i.press("bag", 21)
                i.press("bag", 0)
            with self.subTest(result=result):
                self.same(flow, with_state(refused), expect=["chat.AppendChat"])

    def test_detach(self):
        def flow(w, win, i):
            i.press("bag", 22)
            i.press("bag", 0)
            accept_last(w)
        self.same(flow, expect=["uiCommon.QuestionDialog.Open", "net.SendItemUseToItemPacket"])

    def test_detach_refused(self):
        def cant(game):
            game.answer("player", "CanDetach", 0)

        def flow(w, win, i):
            i.press("bag", 22)
            i.press("bag", 0)
        self.same(flow, with_state(cant), expect=["chat.AppendChat"])

    def test_a_key_a_cleaning_item_and_an_applicable_item_on_an_item(self):
        def applicable(game):
            game.item_flags[4] = 1 << 14
        for source, setup in ((23, stock), (24, stock), (4, with_state(applicable))):
            def flow(w, win, i, source=source):
                i.press("bag", source)
                i.press("bag", 2)
            with self.subTest(source=source):
                legacy, _, _ = self.same(flow, setup, expect=["net.SendItemUseToItemPacket"])
                self.assertIn(("net.SendItemUseToItemPacket", (source, 2)), legacy)

    # --- money, pages, buttons -----------------------------------------------------------

    def test_money(self):
        def flow(w, win, i):
            i.button("wndMoneySlot", "money_press")
            accept_last(w, 1000)
        legacy, _, _ = self.same(flow, expect=["uiPickMoney.PickMoneyDialog.Open", "uiPickMoney.PickMoneyDialog.SetMax"])
        # Legacy's SetMax(player.INVENTORY_MONEY_DIGITS) since NOVA-96, the
        # client's 7 (it was a literal 7 before).
        self.assertIn(("uiPickMoney.PickMoneyDialog.SetMax", (7,)), legacy)

    def test_money_with_safebox_money_attached(self):
        self.same(lambda w, win, i: i.button("wndMoneySlot", "money_press"),
                  before=attach("SLOT_TYPE_SAFEBOX", 0, P_ITEM_MONEY, 5000),
                  expect=["net.SendSafeboxWithdrawMoneyPacket"])

    def test_no_money_no_dialog(self):
        def broke(game):
            game.elk = 0
        legacy, _, _ = self.same(lambda w, win, i: i.button("wndMoneySlot", "money_press"), with_state(broke))
        self.assertEqual(legacy, [])

    def test_pages(self):
        def flow(w, win, i):
            i.tab(1)
            i.tab(0)
        self.same(flow, expect=["player.SetAutoPotionInfo"])

    def test_the_mall_button(self):
        legacy, _, _ = self.same(lambda w, win, i: i.button("mallButton", "mall_press"), expect=["net.SendChatPacket"])
        self.assertEqual(legacy, [("net.SendChatPacket", ("/click_mall",))])

    def test_the_dragon_soul_button(self):
        self.same(lambda w, win, i: i.button("DSSButton", "dss_press"), expect=["interface.ToggleDragonSoulWindow"])

    def test_the_costume_button_opens_and_closes_the_costume_window(self):
        def flow(w, win, i):
            i.button("costumeButton", "costume_press")
        _, world, window = self.same(flow)
        self.assertTrue(window.wndCostume.IsShow())
        self.assertIsNotNone(board(window.wndCostume))

        def twice(w, win, i):
            i.button("costumeButton", "costume_press")
            i.button("costumeButton", "costume_press")
        _, world, window = self.same(twice)
        self.assertFalse(window.wndCostume.IsShow())
        self.assertIsNone(board(window.wndCostume))

    # --- the world drop (game.py's code, the inventory's attach) ---------------------------

    def test_a_stack_dropped_on_the_ground_asks_then_drops(self):
        def flow(w, win, i):
            i.press("bag", 4)
            game_window(w).OnMouseLeftButtonUp()
            accept_last(w)
        legacy, _, _ = self.same(flow, expect=["uiCommon.QuestionDialog.Open", "net.SendItemDropPacketNew"])
        self.assertIn(("net.SendItemDropPacketNew", (P["INVENTORY"], 4, 10)), legacy)

    def test_a_drop_whose_question_is_canceled_sends_nothing(self):
        def flow(w, win, i):
            i.press("bag", 0, cell=5)  # the sword's lower cell stands for its anchor
            game_window(w).OnMouseLeftButtonUp()
            w.game.dialogs[-1].cancel()
        legacy, _, _ = self.same(flow, expect=["uiCommon.QuestionDialog.Open"])
        self.assertNotIn("net.SendItemDropPacketNew", [name for name, _ in legacy])

    def test_a_split_stack_dropped_on_the_ground_drops_the_split_count(self):
        def flow(w, win, i):
            w.game.pressed.add(A["DIK_LSHIFT"])
            i.press("bag", 4)
            accept_last(w, 3)
            w.game.pressed.clear()
            game_window(w).OnMouseLeftButtonUp()
            accept_last(w)
        legacy, _, _ = self.same(flow, expect=["net.SendItemDropPacketNew"])
        self.assertIn(("net.SendItemDropPacketNew", (P["INVENTORY"], 4, 3)), legacy)

    # --- tooltips, the belt, the costume, closing -------------------------------------------

    def test_a_hover_shows_the_item_s_tooltip(self):
        def flow(w, win, i):
            i.over("bag", 4)
            i.over("bag", 0, cell=5)
        self.same(flow)

    def test_a_refresh_of_the_hidden_inventory_shows_no_tooltip(self):
        """Its board went with the pointer on a cell, so the cell heard no
        mouseout; legacy re-shows only while its slot window renders."""
        def flow(w, win, i):
            i.over("bag", 4)
            i.over("wear", I["EQUIPMENT_BODY"])
            win.Hide()
            win.tooltipItem.shown[:] = []
            win.RefreshItemSlot()
        _, world, window = self.same(flow)
        self.assertEqual(window.tooltipItem.shown, [])

    def test_the_cell_hovered_at_the_close_shows_its_tooltip_after_the_next_open(self):
        def flow(w, win, i):
            i.over("bag", 4)
            win.Hide()
            win.Show()
            win.tooltipItem.shown[:] = []
            i.over("bag", 4)
        _, world, window = self.same(flow)
        self.assertEqual(window.tooltipItem.shown, [("SetInventoryItem", 4)])

    def test_closing_with_an_item_attached_clears_the_footprint_on_the_next_board(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            Input(world, window).press("bag", 0)
            Input(world, window).over("bag", 6)
            window.Hide()
            window.Show()
        cells = board(window).model["bag"]
        self.assertEqual([c["index"] for c in cells if c["target"]], [])
        self.assertTrue(cells[0]["picked"], "the attach holds, so the item's own cell stays picked")

    def test_a_refresh_of_the_hidden_costume_and_belt_shows_no_tooltip(self):
        def costume(game):
            game.give(I["COSTUME_SLOT_BODY"] + 1, 45001)

        def before(world, window):
            window.ClickCostumeButton()
            window.wndBelt.OpenInventory()

        def flow(w, win, i):
            i.over("costume", I["COSTUME_SLOT_BODY"] + 1)
            i.over("belt", I["BELT_INVENTORY_SLOT_START"])
            win.Hide()
            win.tooltipItem.shown[:] = []
            win.RefreshItemSlot()
            win.wndCostume.RefreshCostumeSlot()
            win.wndBelt.RefreshSlot()
        _, world, window = self.same(flow, with_state(costume), before)
        self.assertEqual(window.tooltipItem.shown, [])

    def test_a_hover_while_a_scroll_is_attached(self):
        def flow(w, win, i):
            i.press("bag", 20)
            i.over("bag", 0)
        _, world, window = self.same(flow)
        self.assertIn(("SetInventoryItem", 0), window.tooltipItem.shown)

    def test_a_potion_into_the_belt_and_back(self):
        def open_belt(world, window):
            window.wndBelt.OpenInventory()

        def flow(w, win, i):
            i.press("bag", 4)
            i.press("belt", I["BELT_INVENTORY_SLOT_START"] + 1)
            i.press("belt", I["BELT_INVENTORY_SLOT_START"])
            i.release("bag", 6)
        legacy, _, _ = self.same(flow, before=open_belt, expect=["net.SendItemMovePacket"])
        start = I["BELT_INVENTORY_SLOT_START"]
        self.assertEqual([args for name, args in legacy if name == "net.SendItemMovePacket"],
                         [(4, start + 1, 10), (start, 6, 2)])

    def test_the_belt_s_expand_and_minimize_buttons(self):
        def flow(w, win, i):
            i.button("expandBtn", "expand_press", win.wndBelt)
            if i.nui:
                self.assertIsNotNone(board(win.wndBelt).model["expanded"])
            i.button("minBtn", "minimize_press", win.wndBelt)
            i.button("expandBtn", "expand_press", win.wndBelt)
        _, world, window = self.same(flow)
        self.assertTrue(board(window.wndBelt).model["expanded"])

    def test_wear_and_take_off_a_costume(self):
        def costume(game):
            game.give(30, 41001)
            game.give(I["COSTUME_SLOT_BODY"] + 1, 45001)
            game.equipment.add(41001)

        def open_costume(world, window):
            window.ClickCostumeButton()

        def flow(w, win, i):
            i.use("bag", 30)
            i.press("costume", I["COSTUME_SLOT_HAIR"])
            i.release("bag", 6)
            i.press("costume", I["COSTUME_SLOT_HAIR"], 1)
        legacy, _, _ = self.same(flow, with_state(costume), open_costume,
                                 expect=["net.SendItemUsePacket", "net.SendItemMovePacket"])

    def test_escape_closes_the_inventory_the_costume_and_the_belt_and_they_reopen(self):
        def before(world, window):
            window.ClickCostumeButton()
            window.wndBelt.OpenInventory()

        def flow(w, win, i):
            i.escape()
            if i.nui:
                # V-2 (P15 spec 8.1): the boards stay loaded, hidden.
                self.assertEqual(shown_documents(w.game), [])
            win.Show()
        _, world, window = self.same(flow, before=before)
        self.assertTrue(window.wndCostume.IsShow())
        self.assertTrue(window.wndBelt.IsOpeningInventory())

    def test_a_question_keeps_the_inventory_open(self):
        def flow(w, win, i):
            w.game.cursor = A["SELL"]
            i.press("bag", 4)
            win.Hide()
        _, world, window = self.same(flow)
        self.assertTrue(window.IsShow())
        self.assertIsNotNone(board(window))


# game.GameWindow's world drop (game.py OnMouseLeftButtonUp to
# __SendDropItemPacket; Wave 3b leaves it unchanged, P14 spec 6.1's "world
# drop, give, trade" row).
GAME_DROP = ("OnMouseLeftButtonUp", "__PutItem", "__PutMoney", "__DropMoney", "__DropItem", "RequestDropItem",
             "__SendDropItemPacket")


def game_window(world):
    """A GameWindow with game.py's own drop methods over the world's modules,
    the ground under the pointer (no character picked)."""
    source = support.source_of("game.py", GAME_DROP, inside="GameWindow")
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(world.game.modules)
    namespace.update(world.game.loaded)
    exec(compile("class GameWindow(object):\n" + body + "\n", "game.py", "exec"), namespace)
    window = namespace["GameWindow"]()
    window.interface = types.SimpleNamespace(BUILD_OnMouseLeftButtonUp=lambda: False)
    window.PickingCharacterIndex = 0
    window.itemDropQuestionDialog = None
    return window


def later_window(world):
    """A float legacy window of the UI layer made after the inventory and
    raised over it, whose Escape closes it (the NPC shop: uiscript
    shopdialog.py is "movable", "float")."""
    ui = world.game.modules["ui"]

    class Shop(ui.ScriptWindow):
        def OnPressEscapeKey(self):
            self.Hide()
            return True

    shop = Shop()
    shop.AddFlag("float")
    shop.Show()
    shop.SetTop()
    world.shop = shop
    return shop


def hover_layout(game):
    """P14b's hover fixture (inventory.hover.fixture.json): a 200 stack at
    30, a 1x3 glaive at 31 (over 36 and 41) and a 1x2 sword at 37 (over 42),
    side by side at page I's bottom edge."""
    game.give(30, POTION, 200)
    game.give(31, GLAIVE, size=(1, 3))
    game.give(37, SWORD, size=(1, 2))
    game.equipment.update((SWORD, GLAIVE))


class SlotHover(unittest.TestCase):
    """P14b: the pointer moved along the lines of tools/fixtures/hover_paths.json
    (the cells RmlUi's hit test reaches over the hover fixture, every dp, in
    every look and scale: tools/nui_hit_test.py checks them), replayed as
    Context::UpdateHoverChain sends it (the left cell's mouseout, then the
    entered one's mouseover) through the NovaUI inventory, and the tooltip
    calls legacy's OverInItem and OverOutItem make."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "hover_paths.json"), encoding="utf-8") as handle:
            cls.paths = json.load(handle)["paths"]

    def setUp(self):
        self.world = World(True, setup=hover_layout)
        self.window = self.world.make_inventory()

    def replay(self, path):
        tip = self.window.tooltipItem
        with self.world.game, quiet():
            tip.calls[:] = []
            hovered = None
            for cell in path:
                if hovered is not None:
                    fire(self.window, "bag_out", hovered)
                if cell is not None:
                    fire(self.window, "bag_over", cell)
                hovered = cell
            calls = list(tip.calls)
            if hovered is not None:
                fire(self.window, "bag_out", hovered)
        return calls

    def test_the_pointer_over_an_item_s_cells_and_gaps_shows_its_tooltip_once_and_never_hides_it(self):
        self.assertEqual(self.replay(self.paths["glaive-down"]), [("SetInventoryItem", 31)])
        self.assertEqual(self.replay(self.paths["sword-down"]), [("SetInventoryItem", 37)])

    def test_from_an_item_to_its_neighbor_one_hide_then_one_show(self):
        for name, first, second in (("across-middle", 31, 37), ("across-bottom", 31, 37), ("stack-to-glaive", 30, 31)):
            with self.subTest(path=name):
                self.assertEqual(self.replay(self.paths[name]),
                                 [("SetInventoryItem", first), ("HideToolTip",), ("SetInventoryItem", second)])

    def test_the_old_cells_with_dead_gaps_hid_the_tooltip_in_each_gap(self):
        """What the pointer met before P14b over the glaive (its cells, each
        with no hit target in the gap below): a hide and a show per gap, the
        flicker Eddy saw."""
        self.assertEqual(self.replay([31, None, 36, None, 41]), [("SetInventoryItem", 31), ("HideToolTip",),
                                                                  ("SetInventoryItem", 31), ("HideToolTip",),
                                                                  ("SetInventoryItem", 31)])

    def test_an_attach_makes_every_cell_its_own_target_and_its_end_undoes_it(self):
        """Rule 4: while an item is attached, the bag is is-attaching (each
        anchor one cell again, the covered cells targets), so the footprint
        follows the cell under the pointer; the attach's end gives the
        anchors their items back."""
        game_board = board(self.window)
        self.assertFalse(game_board.model["bag_attaching"])
        with self.world.game, quiet():
            press(self.window, "bag_press", 30, 0)
            self.assertTrue(self.world.mouse.isAttached())
            self.assertTrue(board(self.window).model["bag_attaching"])
            fire(self.window, "bag_over", 36)
            targets = dict((c["index"], c["target"]) for c in board(self.window).model["bag"] if c["target"])
            self.assertEqual(targets, {36: "blocked"})
            fire(self.window, "bag_out", 36)
            self.world.mouse.DeattachObject()
        self.assertFalse(board(self.window).model["bag_attaching"])

    def test_an_attach_from_another_window_is_seen_at_the_first_pointer_event(self):
        player = self.world.game.modules["player"]
        with self.world.game, quiet():
            self.world.mouse.AttachObject(object(), player.SLOT_TYPE_SHOP, 3, POTION, 1)
            self.assertFalse(board(self.window).model["bag_attaching"])
            fire(self.window, "bag_over", 41)
            self.assertTrue(board(self.window).model["bag_attaching"])
            fire(self.window, "bag_out", 41)
            self.world.mouse.DeattachObject()
        self.assertFalse(board(self.window).model["bag_attaching"])


class Raise(Pair):
    """A press on the board raises the window as legacy's window manager
    raises the window under a press (SetTopUIWindow), which orders the
    Escape chain and the windows (P14 V-1, the kit's IF-11 and IV-09)."""

    def order(self, world, *windows):
        """The windows' places in the UI layer, bottom first."""
        handles = [ref() for ref in world.game.ui_order]
        return [handles.index(window) for window in windows]

    def test_each_window_underneath_has_its_uiscript_s_flags(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_inventory(), novaui.make_inventory()
        with legacy.game, quiet():
            a.ClickCostumeButton()
        with novaui.game, quiet():
            b.ClickCostumeButton()
        for name in ("inventory", "costume", "belt"):
            pick = {"inventory": lambda w: w, "costume": lambda w: w.wndCostume, "belt": lambda w: w.wndBelt}[name]
            self.assertEqual(pick(b).flags, pick(a).flags, name)
        self.assertIn("float", b.flags)
        self.assertIn("float", b.wndBelt.flags, "legacy's belt constructor adds it")

    def test_after_a_press_on_the_inventory_escape_closes_it_before_a_later_window(self):
        for button, cell in ((0, 6), (1, 6), (0, 4)):
            def flow(w, win, i, button=button, cell=cell):
                later_window(w)
                i.press("bag", cell, button)
                if w.mouse.isAttached():
                    w.mouse.DeattachObject()
                w.escaped = w.game.press_escape()
            with self.subTest(button=button, cell=cell):
                (_, _, legacy, a), (_, _, novaui, b) = self.run_flow(flow)
                self.assertIs(legacy.escaped, a)
                self.assertIs(novaui.escaped, b)
                self.assertFalse(b.IsShow())
                self.assertTrue(novaui.shop.IsShow())
                self.same(flow)

    def test_without_a_press_escape_closes_the_later_window_first(self):
        def flow(w, win, i):
            later_window(w)
            w.escaped = w.game.press_escape()
        (_, _, legacy, a), (_, _, novaui, b) = self.run_flow(flow)
        self.assertIs(legacy.escaped, legacy.shop)
        self.assertIs(novaui.escaped, novaui.shop)
        self.assertTrue(b.IsShow())

    def test_a_press_on_the_title_bar_or_a_control_raises_it_too(self):
        def title(w, win, i):
            later_window(w)
            if i.nui:
                board(win).fire("board_press", 0)
            else:
                win.SetTop()
            w.escaped = w.game.press_escape()

        def tab(w, win, i):
            later_window(w)
            i.tab(1)
            w.escaped = w.game.press_escape()
        for flow in (title, tab):
            with self.subTest(flow=flow.__name__):
                legacy, world, window = self.same(flow)
                self.assertIs(world.escaped, window)

    def test_a_press_on_the_belt_raises_the_belt_which_takes_no_escape(self):
        def flow(w, win, i):
            win.wndBelt.OpenInventory()
            later_window(w)
            i.press("belt", I["BELT_INVENTORY_SLOT_START"] + 2)
            self.assertEqual(self.order(w, win.wndBelt, w.shop), sorted(self.order(w, win.wndBelt, w.shop))[::-1])
            w.escaped = w.game.press_escape()
        _, world, window = self.same(flow)
        self.assertIs(world.escaped, world.shop)

    def test_one_press_raises_once_before_the_legacy_handler_runs(self):
        """A press that opens something leaves it above: the body's own
        mousedown, last in the bubble, does not raise again."""
        world = World(True)
        window = world.make_inventory()
        seen = []
        handlers = window.wndItem._events
        select = handlers["select_empty"]
        handlers["select_empty"] = lambda *args: (seen.append("select"), select(*args))
        original = window.SetTop
        window.SetTop = lambda: (seen.append("raise"), original())
        with world.game, quiet():
            Input(world, window).press("bag", 6)
            Input(world, window).press("bag", 8)
        self.assertEqual(seen, ["raise", "select", "raise", "select"])

    def test_a_press_on_the_dragged_inventory_draws_it_over_the_costume_window(self):
        def before(world, window):
            window.ClickCostumeButton()

        def flow(w, win, i):
            if i.nui:
                board(win).fire("board_press", 0)  # the title bar's handle
            else:
                win.SetTop()
            inventory, costume = self.order(w, win, win.wndCostume)
            self.assertGreater(inventory, costume)
            if i.nui:
                boards = [b for b in w.game.state.fronts if b in (board(win), board(win.wndCostume))]
                self.assertIs(boards[-1], board(win))
        self.same(flow, before=before)


P_ITEM_MONEY = support.PLAYER_CONSTANTS["ITEM_MONEY"]


class Placement(unittest.TestCase):
    """The belt docked to the inventory, the costume beside it, the boards
    in the band below the legacy UI (D13, D16)."""

    def setUp(self):
        self.world = World(True)
        self.window = self.world.make_inventory()

    def test_the_belt_docks_at_inv_belt_dock_also_collapsed(self):
        belt = board(self.window.wndBelt)
        self.assertEqual(belt.placement, ("next_to", board(self.window), "left", 0, "inv-belt-dock"))
        with self.world.game:
            self.window.wndBelt.OpenInventory()
        self.assertEqual(belt.placement, ("next_to", board(self.window), "left", 0, "inv-belt-dock"))
        self.assertTrue(belt.model["expanded"])

    def test_the_costume_opens_beside_the_inventory(self):
        state = self.world.game.state
        state.boxes = getattr(state, "boxes", {})
        with self.world.game, quiet():
            self.window.ClickCostumeButton()
        placement = board(self.window.wndCostume).placement
        self.assertIn(placement[0], ("position", "next_to"))

    def test_the_costume_reopens_beside_the_inventory_before_the_inventory_s_layout(self):
        """Escape, then I (the kit's IV-10): the inventory's Show reopens the
        costume window while the inventory's new board waits for its
        placement (the next update), so its box is the unplaced one, sized at
        the screen's corner, as the client reports it; the costume window
        opens beside the place the inventory opens at, not at the corner."""
        state = self.world.game.state
        state.boxes = getattr(state, "boxes", {})
        inventory_doc = board(self.window).DOCUMENT
        scale = self.world.m("nui_inventory").nui.get_scale() or 1.0
        state.boxes[(inventory_doc, "")] = [1200.0 * scale, 150.0 * scale, 236.0 * scale, 699.0 * scale]
        with self.world.game, quiet():
            self.window.ClickCostumeButton()
        for unplaced in ([0.0, 0.0, 236.0 * scale, 699.0 * scale], [0.0, 0.0, 0.0, 0.0]):
            with self.subTest(box=unplaced):
                with self.world.game, quiet():
                    self.window.Close()
                state.boxes[(inventory_doc, "")] = unplaced
                with self.world.game, quiet():
                    self.window.Show()
                self.assertTrue(self.window.wndCostume.IsShow())
                # The board's rail is registered, so the costume stays clear of it.
                reach = self.world.m("nui_inventory").RAIL_REACH_DP
                self.assertEqual(board(self.window.wndCostume).placement, ("position", 1201.0 - reach, 150.0, (1.0, 0.0)))
                # Its next open beside the laid-out board reads the live box.
                state.boxes[(inventory_doc, "")] = [1100.0 * scale, 100.0 * scale, 236.0 * scale, 699.0 * scale]
                self.assertEqual(self.window.board_origin(), (1100.0, 100.0))
                state.boxes[(inventory_doc, "")] = [1200.0 * scale, 150.0 * scale, 236.0 * scale, 699.0 * scale]

    def test_set_top_raises_the_board_and_calls_legacy_s(self):
        with self.world.game:
            self.window.SetTop()
        self.assertEqual(board(self.window).front, 1)

    def test_the_documents_sit_below_the_legacy_ui_but_select_item(self):
        """D13: the inventory's windows take their legacy windows' band, the
        UI layer, under the shop, exchange and safebox windows they trade
        with; select item, a quest's window, draws above it (spec 6.6)."""
        for name, below in (("inventory", True), ("costume", True), ("belt-inventory", True), ("select-item", False)):
            text = read(os.path.join(WINDOWS, name, name + ".rml"))
            body = re.search(r"<body[^>]*>", text).group(0)
            self.assertEqual("nui-below-legacy-ui" in body, below, name)


class _NuiTaskBar(object):
    """The NovaUI taskbar facade, as far as the inventory reads it."""
    NUI_FACADE = True

    def GetBarHeight(self):
        return 48


class DefaultPlace(unittest.TestCase):
    """Above the NovaUI taskbar the board is placed from Python, and its sheet's
    right and bottom give way (inv--placed): a placement writes only left and
    top (NuiRuntime.h), so with right: 0 and bottom: 37dp the board stretched
    between its placed top and that bottom, and each placement from the
    stretched height moved it higher, to the screen's top (integration,
    2026-10-13, IV-N)."""

    def test_above_the_nui_taskbar_the_board_is_placed_and_marked_placed(self):
        world = World(True)
        world.interface.wndTaskBar = _NuiTaskBar()
        window = world.make_inventory()
        shown = board(window)
        module = world.m("nui_inventory")
        scale = module.nui.get_scale() or 1.0
        width, height = module.wndMgr.GetScreenWidth(), module.wndMgr.GetScreenHeight()
        self.assertEqual(shown.placement, ("position", width / scale, height / scale - 48 / scale, (1.0, 1.0)))
        self.assertIs(shown.model["placed"], True)

    def test_with_the_legacy_taskbar_the_sheet_places_it(self):
        world = World(True)
        window = world.make_inventory()
        shown = board(window)
        self.assertIsNone(shown.placement)
        self.assertIs(shown.model["placed"], False)

    def test_the_placed_class_hands_right_and_bottom_back(self):
        rml = read(os.path.join(WINDOWS, "inventory", "inventory.rml"))
        start = rml.index("<body")
        body = rml[start:rml.index("<div", start)]  # its attributes hold a ">"
        self.assertIn('data-class-inv--placed="placed"', body)
        rule = re.search(r"body\.inv\.inv--placed\s*\{([^}]*)\}", read(os.path.join(WINDOWS, "inventory", "inventory.rcss")))
        self.assertIsNotNone(rule)
        self.assertIn("right: auto;", rule.group(1))
        self.assertIn("bottom: auto;", rule.group(1))


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class DockBox(unittest.TestCase):
    """inv-belt-dock is on the inventory's left border-box edge in every golden
    case of the inventory, so the docked belt's right edge meets it (D16; the
    kit's IV-07-docked). The modern rule was 3dp inside the body."""

    def test_the_belt_dock_is_on_the_body_edge_in_every_inventory_case(self):
        work = tempfile.mkdtemp(prefix="nui-dock-")
        cwd = os.getcwd()
        os.chdir(check_nui_snapshots.ROOT)
        try:
            cases = [case for case in check_nui_snapshots.cases(check_nui_snapshots.ROOT)
                     if case[0].startswith("inventory-") and case[-1] is None]
            self.assertTrue(cases)
            for case in cases:
                with self.subTest(case=case[0]):
                    out = os.path.join(work, case[0] + ".png")
                    boxes = os.path.join(work, case[0] + ".boxes.json")
                    process = subprocess.run(check_nui_snapshots.command(NUITOOL, case, out) + ["--boxes", boxes],
                                             capture_output=True, text=True)
                    self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                    with open(boxes, encoding="utf-8") as handle:
                        found = json.load(handle)
                    # Within a pixel's rounding at 150 percent.
                    self.assertLessEqual(abs(found["inv-belt-dock"][0] - found[""][0]), 0.5, (found[""], found["inv-belt-dock"]))
        finally:
            os.chdir(cwd)
            shutil.rmtree(work, True)


def shown_documents(game):
    """The documents loaded and shown now."""
    return [window.DOCUMENT for window in game.state.windows if window._doc and window.visible]


class OnDemand(unittest.TestCase):
    """V-2 (P15 spec 8.1): the inventory, costume and belt load their
    documents at their first open and keep them, hidden, their lists
    emptied (nui_hud.KeptBoard)."""

    INVENTORY = ["nui/windows/belt-inventory/belt-inventory.rml", "nui/windows/inventory/inventory.rml"]

    def test_no_document_before_the_first_open_and_the_boards_kept_hidden_after(self):
        world = World(True)
        with world.game, quiet():
            window = world.nui_windows.make("inventory", world.m("uiInventory").InventoryWindow,
                                            "nui_inventory.InventoryWindow")
            window.BindInterfaceClass(world.interface)
            window.Hide()
        self.assertEqual(world.game.loaded_documents(), [])
        with world.game, quiet():
            window.Show()
        self.assertEqual(sorted(world.game.loaded_documents()), self.INVENTORY)
        self.assertEqual(sorted(shown_documents(world.game)), self.INVENTORY)
        with world.game, quiet():
            window.Hide()
        self.assertEqual(sorted(world.game.loaded_documents()), self.INVENTORY, "kept loaded")
        self.assertEqual(shown_documents(world.game), [], "and hidden")

    def test_the_second_open_loads_nothing_and_shows_the_same_boards(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            window.ClickCostumeButton()
            boards = (window.demand.board(), window.wndCostume.demand.board(), window.wndBelt.demand.board())
            window.Hide()
        made = len(world.game.state.windows)
        self.assertEqual([demand.kept() for demand in (window.demand, window.wndCostume.demand, window.wndBelt.demand)],
                         list(boards))
        with world.game, quiet():
            window.Show()
        self.assertEqual(len(world.game.state.windows), made, "no board made, no document loaded")
        self.assertIs(window.demand.board(), boards[0])
        self.assertIs(window.wndBelt.demand.board(), boards[2])
        self.assertIs(window.wndCostume.demand.board(), boards[1], "legacy's Show opens the costume again")

    def test_a_hidden_board_holds_no_list_and_the_next_show_sets_them_again(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            window.ClickCostumeButton()
            window.Hide()
        inventory, costume, belt = (window.demand.kept(), window.wndCostume.demand.kept(), window.wndBelt.demand.kept())
        self.assertEqual((inventory.model["bag_on"], inventory.model["wear_on"], inventory.model["tabs_on"]), ([], [], []))
        self.assertEqual(costume.model["wear_on"], [])
        self.assertEqual(belt.model["cells_on"], [])
        with world.game, quiet():
            world.game.give(7, POTION, 3)
            window.RefreshItemSlot()
            window.Show()
        self.assertEqual((inventory.model["bag_on"], inventory.model["wear_on"], inventory.model["tabs_on"]), ([1], [1], [1]))
        self.assertEqual(belt.model["cells_on"], [1])
        self.assertEqual(inventory.model["bag"][7]["count"], "3", "a refresh while hidden reaches the next show")

    def test_destroy_unloads_every_board_shown_or_kept(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            window.ClickCostumeButton()
            window.Hide()
            window.Destroy()
        self.assertEqual(world.game.loaded_documents(), [])
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            window.ClickCostumeButton()
            window.Destroy()
        self.assertEqual(world.game.loaded_documents(), [])


class Fixtures(unittest.TestCase):
    """Each board, made with a stand-in owner and set from its fixture, holds
    every key of the fixture with the same kind; the controllers' models
    have exactly the fixture's keys."""

    BOARDS = (("inventory", "nui_inventory", "_InventoryBoard"), ("costume", "nui_costume", "_CostumeBoard"),
              ("belt-inventory", "nui_belt_inventory", "_BeltBoard"),
              ("select-item", "nui_select_item", "_SelectItemBoard"))

    def fixtures(self, name):
        folder = os.path.join(WINDOWS, name)
        for file_name in sorted(os.listdir(folder)):
            if file_name.endswith(".fixture.json"):
                yield file_name, json.loads(read(os.path.join(folder, file_name)))

    def test_every_fixture_fills_its_board(self):
        world = World(True)
        for name, module, cls in self.BOARDS:
            for file_name, fixture in self.fixtures(name):
                (model_name, model), = fixture.items()
                board_class = getattr(world.m(module), cls)
                self.assertEqual(board_class.MODEL, model_name, file_name)
                mark = world.mark()
                with world.game:
                    shown = board_class(types.SimpleNamespace(), model)
                for key, value in model.items():
                    self.assertEqual(type(shown.model[key]), type(value), "%s %s" % (file_name, key))
                self.assertEqual(world.game.log[mark:], [], file_name)

    def test_the_controllers_models_have_the_fixtures_keys(self):
        world = World(True)
        window = world.make_inventory()
        with world.game, quiet():
            window.ClickCostumeButton()
        select = world.make_select_item()
        states = {"inventory": window._state, "costume": window.wndCostume._state, "belt-inventory": window.wndBelt._state,
                  "select-item": select._state}
        for name, state in states.items():
            for file_name, fixture in self.fixtures(name):
                (_, model), = fixture.items()
                self.assertEqual(sorted(state), sorted(model), file_name)

    def test_the_fixtures_are_the_generator_s(self):
        import nui_w3b_fixtures
        self.assertEqual(nui_w3b_fixtures.main(["--check"]), 0)


class NoPerFrameMethods(unittest.TestCase):
    def test_no_novaui_module_defines_a_per_frame_method(self):
        import ast
        for name in NOVAUI_MODULES:
            tree = ast.parse(read(os.path.join(ROOT, name + ".py")))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertFalse(defined & {"OnUpdate", "OnRender", "OnMouseOverIn"}, name)


class LeanCells(unittest.TestCase):
    """P14 spec 4.2: a lean grid's cell is one element with an icon and a
    number child, and no state of its own needs another element, but the
    bag's active effect: legacy plays its frames over an active cell (the
    auto potions), which classic shows (P14 V-5)."""

    def cell_template(self, name, collection):
        text = read(os.path.join(WINDOWS, name, name + ".rml"))
        match = re.search(r'<div class="nui-slot[^"]*"[^>]*data-for="c : %s".*?</div>' % collection, text, re.S)
        self.assertIsNotNone(match, name)
        return match.group(0)

    def test_each_lean_cell_is_three_elements_and_the_bag_s_four(self):
        for name, collection, grid, parts in (
                ("inventory", "bag", "inv-bag", ["div", "img", "nui-number", "nui-frames"]),
                ("belt-inventory", "cells", "belt-grid", ["div", "img", "nui-number"]),
                ("select-item", "cells", "select-grid", ["div", "img", "nui-number"])):
            template = self.cell_template(name, collection)
            tags = re.findall(r"<([a-z-]+)[\s>/]", template)
            self.assertEqual(tags, parts, name)
            text = read(os.path.join(WINDOWS, name, name + ".rml"))
            self.assertRegex(text, r'id="%s" class="nui-slot-grid nui-slot-grid--lean[ "]' % grid, name)

    def test_the_bag_s_active_part_shows_only_while_the_cell_is_active(self):
        template = self.cell_template("inventory", "bag")
        self.assertRegex(template, r'<nui-frames class="nui-slot__active" data-if="c.active" count="13" delay="0.0667"/>')


class ModernDoll(unittest.TestCase):
    """The modern skin's paper doll and shortcut rail (skins stage 1): the
    figure a function of the race, the stats row as the character window
    sums it, the rail's entries, presses and kept board."""

    def test_the_figures_by_race_follow_playersettingmodule(self):
        text = read(os.path.join(ROOT, "playersettingmodule.py"))
        races = dict((name, int(value)) for name, value in re.findall(r"^(RACE_\w+)\s*=\s*(\d+)", text, re.M))
        self.assertEqual(sorted(races.values()), list(range(8)))
        world = World(True)
        inventory, costume = world.m("nui_inventory"), world.m("nui_costume")
        for name, race in races.items():
            self.assertEqual(inventory.figure_for_race(race), inventory.FIGURE_KNIGHT, name)
            wanted = costume.FIGURE_FEMALE if name.endswith("_W") else costume.FIGURE_MALE
            self.assertEqual(costume.figure_for_race(race), wanted, name)
        store = os.path.normpath(os.path.join(WINDOWS, "..", ".."))
        for path in (inventory.FIGURE_KNIGHT, costume.FIGURE_MALE, costume.FIGURE_FEMALE):
            self.assertTrue(os.path.isfile(os.path.join(store, path.lstrip("/"))), path)

    def test_the_costume_figure_is_the_race_s(self):
        world = World(True)
        world.game.modules["player"].GetRace = lambda: 3
        window = world.make_inventory()
        with world.game, quiet():
            window.ClickCostumeButton()
        self.assertEqual(board(window.wndCostume).model["figure"], world.m("nui_costume").FIGURE_FEMALE)
        self.assertEqual(board(window).model["figure"], world.m("nui_inventory").FIGURE_KNIGHT)

    def test_the_stats_row_sums_as_the_character_window(self):
        world = World(True)
        player = world.game.modules["player"]
        constants = dict(support.WAVE3C_PLAYER_CONSTANTS)
        for name in ("ATT_MIN", "ATT_MAX", "ATT_BONUS", "ATTACKER_BONUS", "DEF_GRADE", "DEF_BONUS", "MAG_ATT",
                     "MIN_MAGIC_WEP", "MAX_MAGIC_WEP"):
            setattr(player, name, constants[name])
        world.game.status.update({constants["ATT_MIN"]: 900, constants["ATT_MAX"]: 1000, constants["ATT_BONUS"]: 100,
                                  constants["ATTACKER_BONUS"]: 48, constants["DEF_GRADE"]: 600, constants["DEF_BONUS"]: 42,
                                  constants["MAG_ATT"]: 200, constants["MIN_MAGIC_WEP"]: 36, constants["MAX_MAGIC_WEP"]: 52})
        window = world.make_inventory()
        defence = 642 if world.m("constInfo").ADD_DEF_BONUS_ENABLE else 600
        model = board(window).model
        self.assertEqual((model["stat_attack"], model["stat_defence"], model["stat_magic"]), ("1048-1148", str(defence), "236-252"))
        world.game.status[constants["ATT_MAX"]] = 900
        with world.game:
            window.RefreshStatus()
        self.assertEqual(board(window).model["stat_attack"], "1048", "one value when the minimum is the maximum")

    def test_the_interface_binding_registers_the_boards_five_entries(self):
        world = World(True)
        module = world.m("nui_inventory")
        window = world.make_inventory()
        rail = board(window).model["rail"]
        self.assertEqual([(e["id"], e["glyph"], e["tip"], e["soon"]) for e in rail],
                         [(entry_id, glyph, tip, soon) for entry_id, glyph, tip, soon in module.BOARD_SHORTCUTS])
        self.assertEqual([e["id"] for e in rail if not e["soon"]], ["guide"], "only the guide exists today")
        self.assertTrue(all(e["enabled"] and e["badge"] == "" for e in rail))
        with world.game:
            for entry_id in ("offline_shop", "ranking", "events", "achievements"):
                press(window, "rail_press", entry_id, 0)
        self.assertNotIn(("interface.OpenHelpWindow", ()), world.game.log, "a feature to come takes no press")
        with world.game:
            press(window, "rail_press", "guide", 1)
            press(window, "rail_press", "guide", 0)
        self.assertEqual(world.game.log.count(("interface.OpenHelpWindow", ())), 1,
                         "a left press on the guide opens the help window")

    def test_a_feature_registered_before_the_binding_keeps_its_entry(self):
        world = World(True)
        module = world.m("nui_inventory")
        pressed = []
        with world.game:
            module.register_shortcut("ranking", "ranking", "@ui.NUI_RAIL_RANKING", lambda: pressed.append("ranking"))
        window = world.make_inventory()
        self.assertEqual([e["id"] for e in board(window).model["rail"]],
                         ["ranking", "offline_shop", "events", "achievements", "guide"])
        with world.game:
            press(window, "rail_press", "ranking", 0)
            window.BindInterfaceClass(world.interface)
        self.assertEqual(pressed, ["ranking"])
        self.assertFalse(board(window).model["rail"][0]["soon"], "a second binding leaves the feature's entry")

    def test_a_registered_shortcut_shows_on_the_rail_and_a_left_press_calls_it(self):
        world = World(True)
        module = world.m("nui_inventory")
        window = world.make_inventory()
        with world.game:
            for entry in module.BOARD_SHORTCUTS:
                module.unregister_shortcut(entry[0])
        self.assertEqual(board(window).model["rail"], [], "no entry, no rail")
        pressed = []
        with world.game:
            module.register_shortcut("offline_shop", "stall", "@ui.NUI_RAIL_OFFLINE_SHOP", lambda: pressed.append("shop"))
            module.register_shortcut("guide", "guide", "@ui.NUI_RAIL_GUIDE", lambda: pressed.append("guide"), enabled=False)
        self.assertEqual(board(window).model["rail"], [
            {"id": "offline_shop", "glyph": "stall", "tip": "@ui.NUI_RAIL_OFFLINE_SHOP", "enabled": True, "soon": False,
             "badge": ""},
            {"id": "guide", "glyph": "guide", "tip": "@ui.NUI_RAIL_GUIDE", "enabled": False, "soon": False, "badge": ""}])
        with world.game:
            press(window, "rail_press", "offline_shop", 0)
            press(window, "rail_press", "offline_shop", 1)
            press(window, "rail_press", "guide", 0)
        self.assertEqual(pressed, ["shop"], "a right press and a disabled entry call nothing")
        with world.game:
            module.set_shortcut_enabled("guide", True)
            press(window, "rail_press", "guide", 0)
            module.set_shortcut_badge("offline_shop", 3)
            module.register_shortcut("offline_shop", "events", "@ui.NUI_RAIL_EVENTS", lambda: pressed.append("events"))
            press(window, "rail_press", "offline_shop", 0)
            module.unregister_shortcut("guide")
        self.assertEqual(pressed, ["shop", "guide", "events"])
        self.assertEqual(board(window).model["rail"], [
            {"id": "offline_shop", "glyph": "events", "tip": "@ui.NUI_RAIL_EVENTS", "enabled": True, "soon": False,
             "badge": "3"}], "replaced in place, its badge kept")

    def test_a_badge_shows_a_count_and_nothing_for_none(self):
        world = World(True)
        module = world.m("nui_inventory")
        window = world.make_inventory()
        badges = []
        with world.game:
            for count in (3, 0, -2, 99, 100, 2500):
                module.set_shortcut_badge("events", count)
                badges.append(board(window).model["rail"][2]["badge"])
        self.assertEqual(badges, ["3", "", "", "99", "99+", "99+"])

    def test_the_fold_button_hides_the_entries_for_the_session(self):
        world = World(True)
        module = world.m("nui_inventory")
        window = world.make_inventory()
        self.assertFalse(board(window).model["rail_folded"])
        with world.game:
            press(window, "rail_fold", 1)
        self.assertFalse(board(window).model["rail_folded"], "a right press does nothing")
        with world.game:
            press(window, "rail_fold", 0)
        self.assertTrue(board(window).model["rail_folded"])
        self.assertEqual(window.rail_reach(), module.RAIL_REACH_DP, "the folded rail keeps its column")
        with world.game, quiet():
            window.Hide()
            window.Show()
        self.assertTrue(board(window).model["rail_folded"], "kept while the window closes and opens")
        with world.game:
            press(window, "rail_fold", 0)
        self.assertFalse(board(window).model["rail_folded"])

    def test_an_entry_names_a_glyph_and_a_locale_key(self):
        module = World(True).m("nui_inventory")
        for entry_id, glyph, tip, callback in (("2shop", "shop", "@ui.OK", len), ("shop", "sword", "@ui.OK", len),
                                               ("shop", "shop", "Offline shop", len), ("shop", "shop", "@ui.OK", None)):
            with self.subTest(entry=(entry_id, glyph, tip)):
                with self.assertRaises(ValueError):
                    module.register_shortcut(entry_id, glyph, tip, callback)
        self.assertEqual(module.shortcuts(), [])
        module.register_shortcut("shop", "stall", "@ui.OK", None, soon=True)
        self.assertEqual([e["id"] for e in module.shortcuts()], ["shop"], "a feature to come needs no callback")

    def test_the_kept_board_holds_no_rail_and_the_costume_opens_beyond_it(self):
        world = World(True)
        module = world.m("nui_inventory")
        with world.game:
            module.register_shortcut("events", "events", "@ui.NUI_RAIL_EVENTS", lambda: None)
        window = world.make_inventory()
        self.assertEqual(len(board(window).model["rail"]), 5)
        state = world.game.state
        state.boxes = getattr(state, "boxes", {})
        scale = module.nui.get_scale() or 1.0
        state.boxes[(board(window).DOCUMENT, "")] = [1200.0 * scale, 150.0 * scale, 236.0 * scale, 817.0 * scale]
        with world.game, quiet():
            window.ClickCostumeButton()
        self.assertEqual(board(window.wndCostume).placement, ("position", 1201.0 - module.RAIL_REACH_DP, 150.0, (1.0, 0.0)))
        with world.game, quiet():
            window.Hide()
        self.assertEqual(window.demand.kept().model["rail"], [])
        with world.game, quiet():
            window.Show()
        self.assertEqual([entry["id"] for entry in board(window).model["rail"]],
                         ["events", "offline_shop", "ranking", "achievements", "guide"])


if __name__ == "__main__":
    unittest.main()
