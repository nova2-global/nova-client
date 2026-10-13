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
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
FLAGS = "+inventory,+select-item"
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
        slot_window = self._where(place)[1]
        target = number if legacy is None else legacy
        if button == 0:
            self._select(slot_window, target)
        elif not self.world.mouse.isAttached():
            slot = slot_window.slots.get(target)
            slot_window.fire("unselect_item" if slot and slot["vnum"] else "unselect_empty", target)

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
            fire(window, event, 0)
            return
        getattr(window, legacy_name).Click()

    def tab(self, page):
        if self.nui:
            fire(self.window, "page_press", page, 0)
            return
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
    """The legacy lines of P14 spec 6.7, exactly."""

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
            text = read(os.path.join(ROOT, file_name)).split("\n")
            for number, line in lines:
                self.assertEqual(text[number - 1].strip(), line, "%s:%d" % (file_name, number))

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

    # --- tooltips, the belt, the costume, closing -------------------------------------------

    def test_a_hover_shows_the_item_s_tooltip(self):
        def flow(w, win, i):
            i.over("bag", 4)
            i.over("bag", 0, cell=5)
        self.same(flow)

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
                self.assertEqual(w.game.loaded_documents(), [])
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


class OnDemand(unittest.TestCase):
    def test_no_document_while_hidden_and_the_board_made_at_show(self):
        world = World(True)
        with world.game, quiet():
            window = world.nui_windows.make("inventory", world.m("uiInventory").InventoryWindow,
                                            "nui_inventory.InventoryWindow")
            window.BindInterfaceClass(world.interface)
            window.Hide()
        self.assertEqual(world.game.loaded_documents(), [])
        with world.game, quiet():
            window.Show()
        self.assertEqual(sorted(world.game.loaded_documents()),
                         ["nui/windows/belt-inventory/belt-inventory.rml", "nui/windows/inventory/inventory.rml"])
        with world.game, quiet():
            window.Hide()
        self.assertEqual(world.game.loaded_documents(), [])

    def test_destroy_unloads_every_board(self):
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
    number child, and no state of its own needs another element."""

    def cell_template(self, name, collection):
        text = read(os.path.join(WINDOWS, name, name + ".rml"))
        match = re.search(r'<div class="nui-slot[^"]*"[^>]*data-for="c : %s".*?</div>' % collection, text, re.S)
        self.assertIsNotNone(match, name)
        return match.group(0)

    def test_each_lean_cell_is_three_elements(self):
        for name, collection, grid in (("inventory", "bag", "inv-bag"), ("belt-inventory", "cells", "belt-grid"),
                                       ("select-item", "cells", "select-grid")):
            template = self.cell_template(name, collection)
            tags = re.findall(r"<([a-z-]+)[\s>/]", template)
            self.assertEqual(tags, ["div", "img", "nui-number"], name)
            text = read(os.path.join(WINDOWS, name, name + ".rml"))
            self.assertRegex(text, r'id="%s" class="nui-slot-grid nui-slot-grid--lean[ "]' % grid, name)


if __name__ == "__main__":
    unittest.main()
