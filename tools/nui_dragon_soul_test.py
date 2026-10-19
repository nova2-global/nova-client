"""Tests for the NovaUI dragon soul windows (assets/root/nui_dragon_soul.py and
nui_dragon_soul_refine.py, P15 spec 5.8 and 6.8): python3 -B -m unittest
nui_dragon_soul_test (from tools/).

Plain CPython over nui_game_support's stand-ins: install_wave3c_ui makes the
legacy uidragonsoul.py windows from their real uiscripts (their slot windows
a model of CSlotWindow), and the dragon soul items, their timers and the
refine stone are this file's stand-ins over the Game's state. Each test
drives a legacy world and a NovaUI world with the same state through the
same input (the legacy slot windows' C++ events and buttons against the
boards' data events) and compares:
- facade: the legacy classes' methods with signatures their callers can use,
  make()'s protocol, the wiring lines, the loaders' bindings against
  legacy's (LoaderBindsAsLegacy), the 0 x 0 windows underneath;
- model: the bag page, the deck's equipment, the kinds, grades, decks and
  activation, the refine window's placed, ghost and closed cells, the
  result and the fee equal what the legacy widgets show, today and at the
  foundation's equipment start;
- flows: P15 spec 5.5's and 6.5's rows, the same net, player, mouse
  controller, snd, chat, ime, dialog and Interface calls in the same order,
  the refine packet and the counts legacy lowers and puts back included;
  F-2's right press; the icons an attach leaves (the leak);
- the boards: on demand, the place kept, a refresh while hidden, the reset at
  a hide, the raise, no per-frame Python, the fixtures and the markup."""
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

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
DS_DOCUMENT = "nui/windows/dragon-soul/dragon-soul.rml"
DSR_DOCUMENT = "nui/windows/dragon-soul-refine/dragon-soul-refine.rml"
NUITOOL = os.environ.get("NUITOOL") or shutil.which("nuitool")
P = dict(support.PLAYER_CONSTANTS)
P.update(support._client_values(support.WAVE3B_PLAYER_CONSTANTS, "player"))
P.update(support._client_values(support.WAVE3C_PLAYER_CONSTANTS, "player"))
FLAGS = "+dragon-soul,+dragon-soul-refine"
EFFECT_MODULES = ("net", "player", "mouse", "chat", "snd", "ime", "uiCommon", "interface")
INV, DS = P["INVENTORY"], P["DRAGON_SOUL_INVENTORY"]
ST_INV, ST_DS = P["SLOT_TYPE_INVENTORY"], P["SLOT_TYPE_DRAGON_SOUL_INVENTORY"]
START = P["DRAGON_SOUL_EQUIPMENT_SLOT_START"]
PAGE = P["DRAGON_SOUL_PAGE_SIZE"]
# Packet.h DragonSoulSub: the refine's failure, net.DS_SUB_HEADER_REFINE_FAIL.
REFINE_FAIL = 5
# The item limit types the windows read (PythonItemModule.cpp, the client's values).
LIMITS = dict((name, support.module_constants()["item"][name])
              for name in ("LIMIT_NONE", "LIMIT_REAL_TIME", "LIMIT_REAL_TIME_START_FIRST_USE", "LIMIT_TIMER_BASED_ON_WEAR"))
# Queries the legacy code makes that the getter prefixes do not name.
QUERIES = ("player.GetItemLink", "player.SlotTypeToInvenType", "player.IsDSEquipmentSlot")
# The facades (P15 spec 5.4, 6.4; migration inventory 2.6 wndDragonSoul, wndDragonSoulRefine).
DS_FACADE = ("ActivateButtonClick", "ActivateDragonSoulByExtern", "Close", "DeactivateDragonSoul", "Destroy", "Hide",
             "HighlightSlot", "IsShow", "RefreshItemSlot", "RefreshStatus", "SetDragonSoulRefineWindow", "SetItemToolTip",
             "Show", "BindInterfaceClass", "OnPressEscapeKey", "SetTop")
DSR_FACADE = ("Close", "Destroy", "Hide", "IsShow", "RefineFail", "RefineSucceed", "SetInventoryWindows", "SetItemToolTip",
              "Show", "AutoSetItem", "OnPressEscapeKey", "SetTop")


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def ds_pos(kind, grade, cell):
    """A dragon soul inventory position (uidragonsoul.py
    __InventoryLocalSlotPosToGlobalSlotPos)."""
    return kind * P["DRAGON_SOUL_PAGE_COUNT"] * PAGE + grade * PAGE + cell


# --- the dragon soul stand-ins --------------------------------------------------------------------

class DSToolTip(support.ToolTip):
    """The Interface's item tooltip as the dragon soul windows use it: the
    time cache calls recorded, the window it reads kept aside."""

    def __init__(self):
        support.ToolTip.__init__(self, "item")
        self.window = None

    def SetDragonSoulWindow(self, window):
        self.window = window

    def WarmDragonSoulTimeCache(self, slots):
        self.calls.append(("WarmDragonSoulTimeCache", tuple(slots)))

    def ClearDragonSoulTimeCache(self):
        self.calls.append(("ClearDragonSoulTimeCache",))


class Interface(object):
    """What the dragon soul window calls on the Interface it is bound to."""

    def __init__(self, game):
        self._game = game

    def UseDSSButtonEffect(self, flag):
        self._game.log.append(("interface.UseDSSButtonEffect", (bool(flag),)))


def install_dragon_soul(game):
    """The item, player and net functions the dragon soul windows read, over
    the Game's state: positions of the INVENTORY window answer with or
    without the window; a dragon soul (vnum 110000 to 169999) is of type
    ITEM_TYPE_DS and its kind's subtype; Game.ds_stones maps a refine stone's
    vnum to its MATERIAL_DS_REFINE_* subtype; Game.item_limits a vnum to its
    limits; legacy's item.GetIconImage is the icon's file (the slot windows
    compare it); player.SetItemCount changes the count."""
    modules = game.modules
    player, item, net = modules["player"], modules["item"], modules["net"]
    for name, value in LIMITS.items():
        setattr(item, name, value)
    net.DS_SUB_HEADER_REFINE_FAIL = REFINE_FAIL
    game.ds_stones = {}
    game.item_limits = {}
    empty = {"vnum": 0, "count": 0, "sockets": [0, 0, 0]}

    def key_of(*at):
        key = at[0] if len(at) == 1 else tuple(at)
        if isinstance(key, tuple) and len(key) == 2 and key[0] == player.INVENTORY:
            return key[1]
        return key

    game._item_at = lambda *at: game.items.get(key_of(*at), empty)
    selected = item.selected

    def is_dragon_soul(vnum):
        return 110000 <= vnum < 170000

    def item_type():
        vnum = selected[0]
        if is_dragon_soul(vnum):
            return item.ITEM_TYPE_DS
        return item.ITEM_TYPE_MATERIAL if vnum in game.ds_stones else 0

    def item_subtype():
        vnum = selected[0]
        return vnum // 10000 - 11 if is_dragon_soul(vnum) else game.ds_stones.get(vnum, 0)

    def limit(index):
        found = list(game.item_limits.get(selected[0], ())) + [(item.LIMIT_NONE, 0)] * 2
        return found[index]

    def set_count(window, position, count):
        entry = game.items.get(key_of(window, position))
        if entry is not None:
            entry["count"] = int(count)

    support.define(item, "GetItemType", item_type)
    support.define(item, "GetItemSubType", item_subtype)
    support.define(item, "GetLimit", limit)
    support.define(item, "GetIconImage", lambda: "icon/item/%05d.tga" % selected[0])
    support.define(player, "SlotTypeToInvenType", lambda slot_type: {
        player.SLOT_TYPE_INVENTORY: player.INVENTORY,
        player.SLOT_TYPE_DRAGON_SOUL_INVENTORY: player.DRAGON_SOUL_INVENTORY}.get(slot_type, player.RESERVED_WINDOW))
    support.define(player, "IsDSEquipmentSlot", lambda window, pos: window == player.INVENTORY and START <= pos < START + 12)
    support.define(player, "SetItemCount", set_count)
    support.define(player, "GetItemLink", lambda *at: "|cfff1e6c0|Hitem:%x:0:0:0:0|h[item]|h|r" % game._item_at(*at)["vnum"])


def stock(game):
    """A qualified tester's dragon souls: on the diamond (kind 0) antique
    (grade 3) page three diamonds of step 0, one of step 3, one of strength
    1, an expired one (its wear timer at 0) and a ruby of kind 1 on its own
    page, a legendary diamond; deck I wears a diamond and a ruby, deck II a
    jade; a Green Dragon Bean (a refine stone) and a weapon in the bag."""
    wear = LIMITS["LIMIT_TIMER_BASED_ON_WEAR"]
    for vnum in (113000, 113300, 113010, 113400, 123300, 114000, 133300, 113120):
        game.item_limits[vnum] = [(wear, 0)]
    for cell, vnum in ((0, 113000), (1, 113000), (2, 113000), (3, 113300), (4, 113010), (8, 113120)):
        game.give((DS, ds_pos(0, 3, cell)), vnum, 1, sockets=(3600, 0, 0))
    game.give((DS, ds_pos(0, 3, 5)), 113400, 1, sockets=(0, 0, 0))
    game.give((DS, ds_pos(1, 3, 2)), 123300, 1, sockets=(3600, 0, 0))
    game.give((DS, ds_pos(0, 4, 0)), 114000, 1, sockets=(3600, 0, 0))
    game.give(START + 0, 113300, 1, sockets=(3600, 0, 0))
    game.give(START + 1, 123300, 1, sockets=(3600, 0, 0))
    game.give(START + 6 + 2, 133300, 1, sockets=(3600, 0, 0))
    game.give(10, 100300, 5)
    game.give(11, 19, 1)
    game.ds_stones[100300] = game.modules["item"].MATERIAL_DS_REFINE_NORMAL


class World(object):
    """One world: a Game with the legacy dragon soul windows and the NovaUI
    ones loaded over its stand-ins, the flags of `windows` on when `nui_on`."""

    def __init__(self, nui_on, windows=FLAGS, engine_3c=True, setup=stock, limits=None, before_load=None):
        game = self.game = support.Game()
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        support.install_wave3b_ui(game)
        game.modules["localeInfo"] = support.locale_info("en")
        support.install_wave3c_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        if not engine_3c:
            game.modules["nuigame"].lack("QuestIconFileName")
        for name in ("networkModule", "interfaceModule"):
            game.put(name, types.ModuleType(name))
        install_dragon_soul(game)
        if before_load is not None:
            before_load(game)
        if setup is not None:
            setup(game)
        game.load_standard()
        with quiet():
            game.load("uiInventory", "uiinventory.py").print = lambda *args, **kwargs: None
            game.load("uiDragonSoul", "uidragonsoul.py")
            for name in ("nui_limits", "nui_proxies", "nui_dragon_soul", "nui_dragon_soul_refine"):
                game.load(name, name + ".py")
        if limits is not None:
            game.loaded["nui_limits"].use(limits)
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on
        self.interface = Interface(game)
        self.tooltip = DSToolTip()
        self.ds = self.refine = None

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
                and name not in QUERIES]

    def make(self):
        """Interface.__MakeWindows' dragon soul windows (interfacemodule.py:189-192,
        217-222) and their tooltip (:339-340)."""
        with self.game, quiet():
            module = self.m("uiDragonSoul")
            ds = self.nui_windows.make("dragon-soul", module.DragonSoulWindow, "nui_dragon_soul.DragonSoulWindow")
            ds.BindInterfaceClass(self.interface)
            refine = self.nui_windows.make("dragon-soul-refine", module.DragonSoulRefineWindow,
                                           "nui_dragon_soul_refine.DragonSoulRefineWindow")
            ds.SetDragonSoulRefineWindow(refine)
            refine.SetInventoryWindows(None, ds)
            ds.SetItemToolTip(self.tooltip)
            refine.SetItemToolTip(self.tooltip)
        self.ds, self.refine = ds, refine
        return ds, refine

    def open(self, kind=None, grade=None):
        """Interface.ToggleDragonSoulWindow (a qualified tester), then the
        kind and the grade, as a player presses them."""
        if self.ds is None:
            self.make()
        with self.game, quiet():
            self.ds.Show()
        if kind is not None:
            Input(self).kind(kind)
        if grade is not None:
            Input(self).grade(grade)
        return self.ds

    def open_refine(self):
        """Interface.OpenDragonSoulRefineWindow (interfacemodule.py:1071-1078)."""
        if self.ds is None:
            self.make()
        with self.game, quiet():
            if not self.refine.IsShow():
                self.refine.Show()
                if not self.ds.IsShow():
                    self.ds.Show()
        return self.refine


def board(window):
    demand = getattr(window, "demand", None)
    return demand.board() if demand is not None else None


def model(window):
    return board(window).model


def fire(window, event, *args):
    shown = board(window)
    if shown is None:
        raise AssertionError("%s has no board" % type(window).__name__)
    return shown.fire(event, *args)


def press(window, event, *args):
    """A mousedown's data event, then the body's own (board_press), as RmlUi
    bubbles it, unless the press took the board away."""
    shown = board(window)
    result = fire(window, event, *args)
    if board(window) is shown:
        shown.fire("board_press", args[-1])
    return result


def compiled(file_name, class_name, names, world):
    """A class with the methods `names` of a legacy module's class, compiled
    from its own source over the world's modules (the legacy code, unchanged)."""
    source = support.source_of(file_name, names, inside=class_name)
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(world.game.modules)
    namespace.update(world.game.loaded)
    exec(compile("class %s(object):\n%s\n" % (class_name, body), file_name, "exec"), namespace)
    return namespace[class_name]


# The Interface's dragon soul entry points (interfacemodule.py:1015-1081): the
# keys, the server's packets and the kit's client-side refine call them.
INTERFACE_DS = ("DragonSoulActivate", "DragonSoulDeactivate", "Highligt_Item", "ToggleDragonSoulWindow",
                "ToggleDragonSoulWindowWithNoInfo", "FailDragonSoulRefine", "SucceedDragonSoulRefine",
                "OpenDragonSoulRefineWindow", "CloseDragonSoulRefineWindow")
# game.GameWindow's world drop (game.py OnMouseLeftButtonUp to
# __SendDropItemPacket), as nui_inventory_test drives it.
GAME_DROP = ("OnMouseLeftButtonUp", "__PutItem", "__PutMoney", "__DropMoney", "__DropItem", "RequestDropItem",
             "__SendDropItemPacket")


def interface_of(world, qualified=True):
    """An Interface with interfacemodule.py's own dragon soul methods over the
    world's windows; the qualification affect heard or not."""
    interface = compiled("interfacemodule.py", "Interface", INTERFACE_DS, world)()
    interface.wndDragonSoul, interface.wndDragonSoulRefine = world.ds, world.refine
    interface.DRAGON_SOUL_IS_QUALIFIED = qualified
    return interface


def game_window(world):
    """A GameWindow with game.py's own drop methods, the ground under the
    pointer (no character picked)."""
    window = compiled("game.py", "GameWindow", GAME_DROP, world)()
    window.interface = types.SimpleNamespace(BUILD_OnMouseLeftButtonUp=lambda: False)
    window.PickingCharacterIndex = 0
    window.itemDropQuestionDialog = None
    return window


# Where a cell lives: the window, the slot window's attribute, the board's event prefix.
PLACES = {"bag": ("ds", "wndItem", "bag"), "equip": ("ds", "wndEquip", "equip"),
          "cell": ("refine", "wndRefineSlot", "cell"), "result": ("refine", "wndResultSlot", "result")}


class Input(object):
    """One player input, as the legacy C++ sends it (slot window events,
    button clicks) and as the boards send it, by the window the input
    reaches (a world may mix a NovaUI window with a legacy one). A cell is
    named by its place and its legacy slot number (the bag's local cell, an
    equipment slot START + sub, a refine cell)."""

    def __init__(self, world):
        self.world = world

    @staticmethod
    def _nui(window):
        # The class's flag: a legacy stand-in window answers any name.
        return getattr(type(window), "NUI_FACADE", False) is True

    def _where(self, place):
        window_name, attribute, prefix = PLACES[place]
        window = getattr(self.world, window_name)
        return window, getattr(window, attribute), prefix

    def _cell(self, place, event, number, *args):
        window, proxy, prefix = self._where(place)
        name = "%s_%s" % (prefix, event)
        if event == "press":
            press(window, name, proxy.index_of(number), *args)
        else:
            fire(window, name, proxy.index_of(number), *args)

    @staticmethod
    def _select(slot_window, number):
        slot = slot_window._slot(number)
        slot_window.fire("select_item" if slot is not None and slot["kind"] else "select_empty", number)

    def press(self, place, number, button=0):
        with self.world.game, quiet():
            window, slot_window, _ = self._where(place)
            if self._nui(window):
                self._cell(place, "press", number, button)
                return
            window.SetTop()
            if button == 0:
                self._select(slot_window, number)
            else:
                # CSlotWindow::OnMouseRightButtonDown: the slot's unselect event
                # whatever is attached (P15 F-2).
                slot = slot_window._slot(number)
                slot_window.fire("unselect_item" if slot is not None and slot["kind"] else "unselect_empty", number)

    def right_release(self):
        """The right button's release: the window manager (or the host, over a
        nui-attach-right grid) cancels whatever is still attached."""
        with self.world.game, quiet():
            if self.world.mouse.isAttached():
                self.world.mouse.DeattachObject()

    def drop(self, place, number):
        """A press in another window released over the cell: the C++ slot
        window's release, NovaUI's nuidrop."""
        with self.world.game, quiet():
            window, slot_window, _ = self._where(place)
            if self._nui(window):
                self._cell(place, "drop", number)
                return
            self._select(slot_window, number)

    def use(self, place, number):
        with self.world.game, quiet():
            window, slot_window, _ = self._where(place)
            if self._nui(window):
                self._cell(place, "use", number)
                return
            slot = slot_window._slot(number)
            if slot is not None and slot["kind"]:
                slot_window.fire("use", number)

    def over(self, place, number):
        """CSlotWindow::OnMouseOver: the over-in event once for a slot that
        holds something (OnOverInItem), else the over-out event once."""
        with self.world.game, quiet():
            window, slot_window, _ = self._where(place)
            if self._nui(window):
                self._cell(place, "over", number)
                return
            slot = slot_window._slot(number)
            tip = getattr(slot_window, "_tip", None)
            if slot is not None and slot["kind"]:
                if tip != number:
                    slot_window._tip = number
                    slot_window.fire("over_in", number)
            elif tip is not None:
                slot_window._tip = None
                slot_window.fire("over_out")

    def out(self, place, number):
        with self.world.game, quiet():
            window, slot_window, _ = self._where(place)
            if self._nui(window):
                self._cell(place, "out", number)
                return
            if getattr(slot_window, "_tip", None) is not None:
                slot_window._tip = None
                slot_window.fire("over_out")

    def _button(self, window, legacy, event, *args):
        with self.world.game, quiet():
            if self._nui(window):
                press(window, event, *(args + (0,)))
                return
            window.SetTop()
            legacy().click()

    def kind(self, index):
        ds = self.world.ds
        self._button(ds, lambda: ds.tabButtonDict[index], "kind_press", index)

    def grade(self, index):
        ds = self.world.ds
        self._button(ds, lambda: ds.inventoryTab[index], "grade_press", index)

    def deck(self, index):
        ds = self.world.ds
        self._button(ds, lambda: ds.deckTab[index], "deck_press", index)

    def activate(self):
        ds = self.world.ds
        self._button(ds, lambda: ds.activateButton, "activate_press")

    def close(self, window_name="ds"):
        window = getattr(self.world, window_name)
        self._button(window, lambda: types.SimpleNamespace(click=window.GetChild("TitleBar").close), "close_press")

    def mode(self, name):
        refine = self.world.refine
        kinds = {"grade": refine.REFINE_TYPE_GRADE, "step": refine.REFINE_TYPE_STEP, "strength": refine.REFINE_TYPE_STRENGTH}
        self._button(refine, lambda: refine.refineChoiceButtonDict[kinds[name]], "mode_press", name)

    def do_refine(self):
        refine = self.world.refine
        self._button(refine, lambda: refine.doRefineButton, "refine_press")


# --- what the windows show ---------------------------------------------------------------------------

def legacy_cells(slot_window):
    """{slot: (kind, icon, count label, active, disabled, alpha)} of every set
    slot of a legacy slot window, as CSlotWindow draws it."""
    found = {}
    for number in sorted(slot_window.slots):
        slot = slot_window._slot(number)
        if not slot["kind"]:
            continue
        found[number] = (slot["kind"], slot["icon"], slot["label"], bool(slot["active"]), bool(slot["disabled"]),
                         slot["alpha"])
    return found


def novaui_cells(proxy, cells):
    """The same of a board's cells (the store path's leading / dropped; a
    ghost's alpha from the proxy)."""
    extras = proxy.extras()
    found = {}
    for cell in cells:
        if not cell["kind"]:
            continue
        icon = cell["icon"][1:] if cell["icon"].startswith("/") else cell["icon"]
        found[proxy.slot_number(cell["index"])] = (cell["kind"], icon, cell["count"], cell["active"], cell["disabled"],
                                                  extras[cell["index"]]["alpha"])
    return found


def legacy_chrome(ds):
    return {"kind": ds.DSKindIndex, "kinds": [ds.tabDict[i].IsShow() for i in sorted(ds.tabDict)],
            "kind_title": ds.tabText.GetText(), "grade": ds.inventoryPageIndex,
            "grades": [tab.down for tab in ds.inventoryTab], "deck": ds.deckPageIndex,
            "decks": [tab.down for tab in ds.deckTab], "activated": ds.activateButton.down}


def novaui_chrome(ds):
    data = model(ds)
    return {"kind": data["kind"], "kinds": [k["down"] for k in data["kinds"]], "kind_title": data["kind_title"],
            "grade": data["grade"], "grades": [g["down"] for g in data["grades"]], "deck": data["deck"],
            "decks": [d["down"] for d in data["decks"]], "activated": data["activated"]}


class DragonSoulTest(unittest.TestCase):
    def worlds(self, setup=stock, **kwargs):
        return World(False, setup=setup, **kwargs), World(True, setup=setup, **kwargs)

    def run_flow(self, flow, kind=0, grade=3, refine=False, setup=stock):
        """The same flow in both worlds: [(effects, world)]."""
        results = []
        for world in self.worlds(setup):
            world.open(kind, grade)
            if refine:
                world.open_refine()
            mark = world.mark()
            with world.game, quiet():
                flow(world, Input(world))
            results.append((world.effects_since(mark), world))
        return results

    def same(self, flow, **kwargs):
        (legacy, lw), (novaui, nw) = self.run_flow(flow, **kwargs)
        self.assertEqual(novaui, legacy)
        return legacy, lw, nw

    def assert_same_window(self, lw, nw):
        """Both windows show the same: the bag page, the deck, the chrome."""
        a, b = lw.ds, nw.ds
        self.assertEqual(novaui_cells(b.wndItem, model(b)["bag"]), legacy_cells(a.wndItem), "bag")
        self.assertEqual(novaui_cells(b.wndEquip, model(b)["equip"]), legacy_cells(a.wndEquip), "equipment")
        self.assertEqual(novaui_chrome(b), legacy_chrome(a))

    def assert_same_refine(self, lw, nw):
        a, b = lw.refine, nw.refine
        self.assertEqual(novaui_cells(b.wndRefineSlot, model(b)["cells"]), legacy_cells(a.wndRefineSlot), "cells")
        closed = [cell["closed"] for cell in model(b)["cells"]]
        self.assertEqual(closed, [a.wndRefineSlot._slot(i)["base"] for i in range(len(closed))], "closed cells")
        self.assertEqual(novaui_cells(b.wndResultSlot, model(b)["result"]), legacy_cells(a.wndResultSlot), "result")
        self.assertEqual(model(b)["fee"], a.GetChild("Money_Slot").GetText())
        self.assertEqual(model(b)["mode"], {0: "grade", 1: "step", 2: "strength"}[a.currentRefineType])
        self.assertEqual([m["down"] for m in model(b)["modes"]],
                         [a.refineChoiceButtonDict[kind].down for kind in range(3)])


# --- the facades --------------------------------------------------------------------------------------

class Facade(DragonSoulTest):
    def test_subclasses_of_the_legacy_classes_with_every_facade_method(self):
        world = World(True)
        legacy = world.m("uiDragonSoul")
        for ours, theirs, names in ((world.m("nui_dragon_soul").DragonSoulWindow, legacy.DragonSoulWindow, DS_FACADE),
                                    (world.m("nui_dragon_soul_refine").DragonSoulRefineWindow,
                                     legacy.DragonSoulRefineWindow, DSR_FACADE)):
            self.assertTrue(issubclass(ours, theirs))
            self.assertTrue(ours.NUI_FACADE)
            for name in names:
                method = getattr(ours, name)
                wrapped = getattr(method, "__wrapped__", method)
                original = getattr(theirs, name, None) or getattr(world.m("ui").ScriptWindow, name)
                mine = inspect.signature(wrapped)
                with self.subTest(cls=ours.__name__, name=name):
                    self.assertEqual(len(mine.parameters), len(inspect.signature(original).parameters))

    def test_make_builds_novaui_with_the_flags_and_the_3c_engine_and_legacy_otherwise(self):
        for nui_on, engine, expected in ((True, True, ("nui_dragon_soul", "nui_dragon_soul_refine")),
                                         (False, True, ("uiDragonSoul", "uiDragonSoul")),
                                         (True, False, ("uiDragonSoul", "uiDragonSoul"))):
            world = World(nui_on, engine_3c=engine)
            ds, refine = world.make()
            with self.subTest(nui_on=nui_on, engine=engine):
                self.assertEqual((type(ds).__module__, type(refine).__module__), expected)
                self.assertEqual(world.game.loaded_documents(), [], "no document while the windows are closed")

    def test_each_flag_alone(self):
        world = World(True, windows="+dragon-soul")
        ds, refine = world.make()
        self.assertEqual((type(ds).__module__, type(refine).__module__), ("nui_dragon_soul", "uiDragonSoul"))
        world = World(True, windows="+dragon-soul-refine")
        ds, refine = world.make()
        self.assertEqual((type(ds).__module__, type(refine).__module__), ("uiDragonSoul", "nui_dragon_soul_refine"))

    def test_a_document_that_does_not_load_falls_back_once_to_syserr_and_never_aborts(self):
        for document, window_id in ((DS_DOCUMENT, "dragon-soul"), (DSR_DOCUMENT, "dragon-soul-refine")):
            world = World(True)
            world.game.state.failing.add(document)
            world.make()
            with self.subTest(window=window_id):
                errors = [e for e in world.game.dbg.errors if e.startswith("nui_windows: %s:" % window_id)]
                self.assertEqual(errors, ["nui_windows: %s: the document did not load; using the legacy window" % window_id])
                self.assertFalse([name for name, args in world.game.log if name.startswith("exception.")])

    def test_a_load_that_raises_falls_back_without_aborting(self):
        world = World(True)
        world.game.state.raising.add(DS_DOCUMENT)
        ds, refine = world.make()
        self.assertEqual(type(ds).__module__, "uiDragonSoul")
        self.assertEqual(type(refine).__module__, "nui_dragon_soul_refine")
        self.assertFalse([name for name, args in world.game.log if name.startswith("exception.")])

    WIRING = (
        (190, 'wndDragonSoul = nui_windows.make("dragon-soul", uiDragonSoul.DragonSoulWindow, '
              '"nui_dragon_soul.DragonSoulWindow")'),
        (192, 'wndDragonSoulRefine = nui_windows.make("dragon-soul-refine", uiDragonSoul.DragonSoulRefineWindow, '
              '"nui_dragon_soul_refine.DragonSoulRefineWindow")'),
    )

    def test_the_interface_makes_them_through_make(self):
        text = read(os.path.join(ROOT, "interfacemodule.py")).split("\n")
        for number, line in self.WIRING:
            self.assertEqual(text[number - 1].strip(), line, "interfacemodule.py:%d" % number)
        world = World(True)
        for name in ("nui_dragon_soul.DragonSoulWindow", "nui_dragon_soul_refine.DragonSoulRefineWindow"):
            module, cls = name.split(".")
            self.assertTrue(hasattr(world.m(module), cls), name)

    def test_the_legacy_windows_underneath_have_the_uiscripts_flags_and_stay_0_by_0(self):
        legacy, novaui = World(False), World(True)
        legacy.make()
        novaui.make()
        for name in ("ds", "refine"):
            a, b = getattr(legacy, name), getattr(novaui, name)
            with self.subTest(window=name):
                self.assertEqual(b.flags, a.flags & {"movable", "float"})
                self.assertEqual(b.flags, {"movable", "float"})
                self.assertEqual((b.GetWidth(), b.GetHeight()), (0, 0))


def handler_name(event):
    """The name of what a widget's event calls: a ui.__mem_func__'s method,
    a bound method, a lambda."""
    if event is None:
        return None
    if isinstance(event, tuple):
        event = event[0]
    fn = getattr(event, "fn", event)
    fn = getattr(fn, "__func__", fn)
    return getattr(getattr(fn, "__wrapped__", fn), "__name__", repr(fn))


class LoaderBindsAsLegacy(DragonSoulTest):
    """P15 spec 13: the loaders copy legacy's bindings; each legacy handler is
    bound to the same event of the same widget in both worlds (a binding C2
    changes in uidragonsoul.py shows here)."""

    def test_the_dragon_soul_window(self):
        legacy, novaui = World(False), World(True)
        legacy.make()
        novaui.make()
        a, b = legacy.ds, novaui.ds
        for name in ("wndItem", "wndEquip"):
            theirs = dict((key, handler_name(value)) for key, value in getattr(a, name).events.items() if value)
            mine = dict((key, handler_name(value)) for key, value in getattr(b, name).handlers().items() if value)
            self.assertEqual(mine, theirs, name)
        self.assertEqual([handler_name(b.tabButtonDict[i].event) for i in sorted(b.tabButtonDict)],
                         [handler_name(a.tabButtonDict[i].event) for i in sorted(a.tabButtonDict)])
        self.assertEqual([tab.event_args for tab in b.tabButtonDict.values()],
                         [tab.eventArgs for tab in a.tabButtonDict.values()])
        for toggle_a, toggle_b in [(a.activateButton, b.activateButton)] + list(zip(a.deckTab, b.deckTab)):
            self.assertEqual((handler_name(toggle_b.event_down), handler_name(toggle_b.event_up)),
                             (handler_name(toggle_a.eventDown), handler_name(toggle_a.eventUp)))
        self.assertEqual(handler_name(b._title_bar.close_event), handler_name(a.GetChild("TitleBar").closeEvent))
        self.assertEqual(len(b.inventoryTab), len(a.inventoryTab))
        for name in ("dlgQuestion", "wndPopupDialog", "listHighlightedSlot", "isActivated", "deckPageIndex",
                     "inventoryPageIndex", "DSKindIndex", "tabText"):
            self.assertTrue(hasattr(b, name), name)

    def test_the_refine_window(self):
        legacy, novaui = World(False), World(True)
        legacy.make()
        novaui.make()
        a, b = legacy.refine, novaui.refine
        for name in ("wndRefineSlot", "wndResultSlot"):
            theirs = dict((key, handler_name(value)) for key, value in getattr(a, name).events.items() if value)
            mine = dict((key, handler_name(value)) for key, value in getattr(b, name).handlers().items() if value)
            self.assertEqual(mine, theirs, name)
        for kind in range(3):
            toggle_a, toggle_b = a.refineChoiceButtonDict[kind], b.refineChoiceButtonDict[kind]
            self.assertEqual((handler_name(toggle_b.event_down), handler_name(toggle_b.event_up)),
                             (handler_name(toggle_a.eventDown), handler_name(toggle_a.eventUp)))
        self.assertEqual(handler_name(b.doRefineButton.event), handler_name(a.doRefineButton.event))
        self.assertEqual(handler_name(b._title_bar.close_event), handler_name(a.GetChild("TitleBar").closeEvent))
        for name in ("currentRefineType", "refineItemInfo", "resultItemInfo", "currentRecipe", "refineSlotLockStartIndex",
                     "wndPopupDialog", "wndMoney"):
            self.assertTrue(hasattr(b, name), name)


# --- the model against the legacy widgets -------------------------------------------------------------------

class Model(DragonSoulTest):
    def test_the_bag_the_deck_and_the_chrome_equal_legacy_s_on_every_page_and_deck(self):
        legacy, novaui = self.worlds()
        legacy.open(0, 3)
        novaui.open(0, 3)
        self.assert_same_window(legacy, novaui)
        bag = model(novaui.ds)["bag"]
        self.assertEqual([c["kind"] != "" for c in bag[:9]], [True] * 6 + [False, False, True])
        self.assertTrue(bag[5]["disabled"], "the expired dragon soul: its timer is 0")
        self.assertEqual((bag[0]["type"], bag[0]["ref"]), (ST_DS, ds_pos(0, 3, 0)))
        equip = model(novaui.ds)["equip"]
        self.assertEqual([(c["sub"], c["type"], c["ref"]) for c in equip[:2]], [(0, ST_INV, START), (1, ST_INV, START + 1)])
        for kind, grade in ((1, 3), (0, 4), (0, 0)):
            for world in (legacy, novaui):
                Input(world).kind(kind)
                Input(world).grade(grade)
            with self.subTest(kind=kind, grade=grade):
                self.assert_same_window(legacy, novaui)
        for world in (legacy, novaui):
            Input(world).deck(1)
        self.assert_same_window(legacy, novaui)
        self.assertEqual(model(novaui.ds)["equip"][2]["ref"], START + 6 + 2)

    def test_the_kind_title_and_the_grade_labels(self):
        world = World(True)
        ds = world.open(0, 3)
        self.assertEqual(model(ds)["kind_title"], world.m("uiDragonSoul").DragonSoulWindow.KIND_TAP_TITLES[0])
        self.assertEqual([g["label"] for g in model(ds)["grades"]], ["@ui.DRAGONSOUL_PAGE_BUTTON_%d" % i for i in range(1, 6)])
        self.assertEqual([k["label"] for k in model(ds)["kinds"]], ["@ui.DRAGONSOUL_TAP_TITLE_%d" % i for i in range(1, 7)])
        self.assertEqual([d["label"] for d in model(ds)["decks"]], ["I", "II"])
        self.assertEqual(model(ds)["bag_cols"], 8)

    def test_the_foundation_s_equipment_start(self):
        """At the cut the deck's slots start at 265 (OLD's 225 + 40); the
        client's constant reaches the uiscript, legacy's code and the limits
        alike."""
        def foundation(game):
            game.modules["player"].DRAGON_SOUL_EQUIPMENT_SLOT_START = 265

        def setup(game):
            stock(game)
            game.items[265] = game.items.pop(START)
        legacy, novaui = World(False, before_load=foundation, setup=setup), World(True, before_load=foundation, setup=setup)
        self.assertEqual(novaui.m("nui_limits").current().DRAGON_SOUL_EQUIPMENT_SLOT_START, 265)
        legacy.open(0, 3)
        novaui.open(0, 3)
        self.assertEqual(novaui.ds.wndEquip.slot_numbers, list(range(265, 271)))
        self.assert_same_window(legacy, novaui)
        self.assertEqual(model(novaui.ds)["equip"][0]["ref"], 265)

    def test_the_refine_cells_in_each_mode(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.open(0, 3)
            world.open_refine()
        self.assert_same_refine(legacy, novaui)
        self.assertEqual([c["closed"] for c in model(novaui.refine)["cells"]], [False] + [True] * 14)
        for world in (legacy, novaui):
            Input(world).press("bag", 0, 1)        # S7: into the refine window
        self.assert_same_refine(legacy, novaui)
        cells = model(novaui.refine)["cells"]
        self.assertEqual([(c["kind"], c["ghost"], c["closed"]) for c in cells[:4]],
                         [("item", False, False), ("icon", True, False), ("icon", True, False), ("", False, True)])
        self.assertEqual((cells[0]["type"], cells[0]["ref"]), (ST_DS, ds_pos(0, 3, 0)))
        self.assertEqual(model(novaui.refine)["fee"], "100.000 Yang")
        self.assertEqual(model(novaui.refine)["fee_value"], 100000)
        for name in ("step", "strength", "grade"):
            for world in (legacy, novaui):
                Input(world).mode(name)
            with self.subTest(mode=name):
                self.assert_same_refine(legacy, novaui)
                self.assertEqual(model(novaui.refine)["mode"], name)


# --- the dragon soul window's flows (P15 spec 5.5) ------------------------------------------------------------

class Flows(DragonSoulTest):
    def test_s1_the_interface_opens_it_for_a_qualified_tester_and_shows_the_popup_otherwise(self):
        """S1 through interfacemodule.py's ToggleDragonSoulWindow (the O key,
        the inventory's button): unqualified, the DRAGON_SOUL_UNQUALIFIED
        popup and no window; qualified, the window; again, its Close."""
        results = []
        for world in self.worlds():
            world.make()
            mark = world.mark()
            shown = []
            with world.game, quiet():
                interface_of(world, qualified=False).ToggleDragonSoulWindow()
                shown.append((world.ds.IsShow(), world.game.loaded_documents()))
                interface = interface_of(world)
                interface.ToggleDragonSoulWindow()
                shown.append((world.ds.IsShow(), world.game.loaded_documents()))
                interface.ToggleDragonSoulWindow()
                shown.append((world.ds.IsShow(), world.game.loaded_documents()))
                interface.ToggleDragonSoulWindowWithNoInfo()
                shown.append((world.ds.IsShow(), world.game.loaded_documents()))
            results.append((world.effects_since(mark), [is_shown for is_shown, _ in shown], world))
        (legacy, legacy_shown, _), (novaui, novaui_shown, nw) = results
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui_shown, legacy_shown)
        self.assertEqual(legacy_shown, [False, True, False, True])
        locale = nw.game.modules["localeInfo"]
        self.assertEqual([args[0] for name, args in legacy if name == "uiCommon.PopupDialog.Open"],
                         [locale.DRAGON_SOUL_UNQUALIFIED])
        self.assertEqual(nw.game.loaded_documents(), [DS_DOCUMENT])
        self.assert_same_window(results[0][2], nw)

    def test_s2_kind_and_grade_send_nothing(self):
        def flow(world, input):
            input.kind(1)
            input.grade(2)
            input.grade(2)
            input.kind(0)
        calls, lw, nw = self.same(flow)
        self.assertEqual(calls, [])
        self.assert_same_window(lw, nw)

    def test_s3_s4_pick_and_move_in_the_bag(self):
        def flow(world, input):
            input.press("bag", 0)
            input.press("bag", 9)
        calls, lw, nw = self.same(flow)
        src, dst = ds_pos(0, 3, 0), ds_pos(0, 3, 9)
        self.assertEqual(calls, [("mouse.AttachObject", (ST_DS, src, 113000, 1)), ("snd.PlaySound", ("sound/ui/pick.wav",)),
                                 ("net.SendItemMovePacket", (DS, src, DS, dst, 1)), ("mouse.DeattachObject", ())])

    def test_s5_equip_by_drag_with_its_question_and_the_two_popups(self):
        def flow(world, input):
            input.press("bag", 0)               # a diamond (sub 0)
            input.press("equip", START + 2)     # the jade's place: the wrong slot
            input.press("bag", 5)               # the expired one
            input.press("equip", START + 0)     # deck I's diamond place holds one: item on item
            input.press("bag", 0)
            input.deck(1)
            input.press("equip", START + 0)     # deck II's empty diamond place
            world.ds.dlgQuestion.accept()
        calls, lw, nw = self.same(flow)
        names = [name for name, _ in calls]
        self.assertIn("uiCommon.PopupDialog.Open", names)
        self.assertIn(("net.SendItemMovePacket", (DS, ds_pos(0, 3, 0), INV, START + 6, 0)), calls)
        self.assertIn(("net.SendItemUseToItemPacket", (DS, ds_pos(0, 3, 5), INV, START)), calls)

    def test_s5_an_expired_dragon_soul_dropped_on_its_slot_shows_the_expired_popup(self):
        def flow(world, input):
            input.deck(1)
            input.press("bag", 5)
            input.press("equip", START + 0)
        calls, _, _ = self.same(flow)
        popups = [args for name, args in calls if name == "uiCommon.PopupDialog.Open"]
        self.assertEqual(len(popups), 1)
        self.assertNotIn("net.SendItemMovePacket", [name for name, _ in calls])

    def test_s6_equip_by_use_right_press_and_double_click(self):
        def flow(world, input):
            input.deck(1)
            input.press("bag", 3, 1)
            world.ds.dlgQuestion.accept()
            input.use("bag", 4)
            world.ds.dlgQuestion.cancel()
            input.use("bag", 5)
        calls, _, _ = self.same(flow)
        self.assertIn(("net.SendItemMovePacket", (DS, ds_pos(0, 3, 3), INV, START + 6, 0)), calls)
        self.assertEqual(len([1 for name, _ in calls if name == "net.SendItemMovePacket"]), 1, "the cancel sends nothing")
        self.assertEqual(len([1 for name, _ in calls if name == "uiCommon.PopupDialog.Open"]), 1, "the expired one")

    def test_s7_a_right_press_while_the_refine_window_shows_puts_the_item_there(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            input.press("bag", 1, 1)
        calls, lw, nw = self.same(flow, refine=True)
        self.assertIn(("player.SetItemCount", (DS, ds_pos(0, 3, 0), 0)), calls)
        self.assertIn(("player.SetItemCount", (DS, ds_pos(0, 3, 1), 0)), calls)
        self.assert_same_refine(lw, nw)

    def test_s8_s9_s10_unequip_by_drag_and_by_use(self):
        def flow(world, input):
            input.press("equip", START + 0)
            input.press("bag", 20)
            world.ds.dlgQuestion.accept()
            input.press("equip", START + 1, 1)
            world.ds.dlgQuestion.accept()
            input.use("equip", START + 1)
            world.ds.dlgQuestion.cancel()
        calls, _, _ = self.same(flow)
        self.assertEqual(calls[:2], [("mouse.AttachObject", (ST_INV, START, 113300, 1)), ("snd.PlaySound", ("sound/ui/pick.wav",))])
        moves = [args for name, args in calls if name == "net.SendItemMovePacket"]
        self.assertEqual(moves, [(INV, START, DS, ds_pos(0, 3, 20), 0), (INV, START + 1, 1, 1, 0)])

    def test_s11_item_on_item(self):
        def flow(world, input):
            input.press("bag", 0)
            input.press("bag", 3)
            input.press("equip", START + 1)
            input.press("equip", START + 0)
            input.press("equip", START + 0)     # onto itself: nothing, still attached
            input.right_release()
        calls, _, _ = self.same(flow)
        uses = [args for name, args in calls if name == "net.SendItemUseToItemPacket"]
        self.assertEqual(uses, [(DS, ds_pos(0, 3, 0), DS, ds_pos(0, 3, 3)), (INV, START + 1, INV, START)])

    def test_s12_s13_activate_and_deactivate_by_the_button_and_the_server(self):
        def flow(world, input):
            input.activate()
            world.ds.ActivateDragonSoulByExtern(0)
            input.activate()
            world.ds.DeactivateDragonSoul()
        calls, lw, nw = self.same(flow)
        self.assertEqual([args for name, args in calls if name == "net.SendChatPacket"],
                         [("/dragon_soul activate 0",), ("/dragon_soul deactivate",)])
        self.assertEqual([args for name, args in calls if name == "interface.UseDSSButtonEffect"], [(True,), (False,)])
        self.assert_same_window(lw, nw)

    def test_s12_the_active_deck_shows_its_items_active(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.open(0, 3)
            with world.game, quiet():
                world.ds.ActivateDragonSoulByExtern(0)
        self.assert_same_window(legacy, novaui)
        equip = model(novaui.ds)["equip"]
        self.assertEqual([c["active"] for c in equip], [True, True, False, False, False, False])
        self.assertTrue(model(novaui.ds)["activated"])
        self.assertEqual(legacy.tooltip.calls, novaui.tooltip.calls, "the time cache warmed alike")

    def test_s12_the_keys_activate_a_deck_and_switch_to_it(self):
        def flow(world, input):
            world.ds.ActivateButtonClick(1)     # Ctrl+D (game.py:433)
            world.ds.ActivateButtonClick(0)     # Ctrl+C
            world.ds.ActivateButtonClick(0)
        calls, lw, nw = self.same(flow)
        self.assertEqual([args for name, args in calls if name == "net.SendChatPacket"],
                         [("/dragon_soul activate 1",), ("/dragon_soul activate 0",), ("/dragon_soul deactivate",)])
        self.assert_same_window(lw, nw)

    def test_s14_a_deck_switch_while_active_deactivates(self):
        def flow(world, input):
            world.ds.ActivateDragonSoulByExtern(0)
            input.deck(1)
            input.deck(1)                       # the shown deck: up, then down again
            input.deck(0)
        calls, lw, nw = self.same(flow)
        self.assertEqual([args for name, args in calls if name == "net.SendChatPacket"], [("/dragon_soul deactivate",)])
        self.assert_same_window(lw, nw)

    def test_s15_sell_buy_and_link(self):
        def flow(world, input):
            world.game.cursor = world.game.modules["app"].SELL
            input.press("bag", 0)
            world.game.cursor = world.game.modules["app"].BUY
            input.press("bag", 0)
            world.game.cursor = world.game.modules["app"].NORMAL
            world.game.pressed.add(world.game.modules["app"].DIK_LALT)
            input.press("bag", 0)
            world.game.pressed.clear()

        def setup(game):
            stock(game)
            game.antiflags[113000] = game.modules["item"].ANTIFLAG_SELL
        calls, _, _ = self.same(flow, setup=setup)
        names = [name for name, _ in calls]
        self.assertIn("chat.AppendChat", names)
        self.assertIn("ime.PasteString", names)
        self.assertNotIn("net.SendShopSellPacketNew", names, "every dragon soul is ANTI_SELL: the popup only")

    def test_s16_from_the_safebox_and_the_mall(self):
        def flow(world, input):
            with world.game:
                world.mouse.AttachObject(world.ds, P["SLOT_TYPE_SAFEBOX"], 7, 113000, 1)
            input.press("bag", 20)
            with world.game:
                world.mouse.AttachObject(world.ds, P["SLOT_TYPE_MALL"], 3, 113000, 1)
            input.press("bag", 21)
        calls, _, _ = self.same(flow)
        self.assertIn(("net.SendSafeboxCheckoutPacket", (7, DS, ds_pos(0, 3, 20))), calls)
        self.assertIn(("net.SendMallCheckoutPacket", (3, DS, ds_pos(0, 3, 21))), calls)

    def test_s16_from_the_shop_the_private_shop_and_the_safebox_s_money(self):
        """S16's other rows: a shop item bought onto an empty cell, a private
        shop builder's item handed to its INVENTORY callback, the safebox's
        money withdrawn (SelectEmptySlot); each attach ends."""
        def flow(world, input):
            with world.game:
                world.mouse.AttachObject(world.ds, P["SLOT_TYPE_SHOP"], 5, 113000, 1)
            input.press("bag", 20)
            with world.game:
                world.mouse.AttachObject(world.ds, P["SLOT_TYPE_PRIVATE_SHOP"], 2, 113000, 1)
                world.mouse.SetCallBack("INVENTORY", lambda: world.game.log.append(("mouse.callback.INVENTORY", ())))
            input.press("bag", 21)
            with world.game:
                world.mouse.AttachObject(world.ds, P["SLOT_TYPE_SAFEBOX"], 0, P["ITEM_MONEY"], 500)
            input.press("bag", 22)
        calls, _, nw = self.same(flow)
        self.assertIn(("net.SendShopBuyPacket", (5,)), calls)
        self.assertIn(("mouse.callback.INVENTORY", ()), calls)
        self.assertIn(("net.SendSafeboxWithdrawMoneyPacket", (500,)), calls)
        self.assertIn(("snd.PlaySound", ("sound/ui/money.wav",)), calls)
        self.assertFalse(nw.mouse.isAttached())

    def test_s17_a_dragon_soul_released_over_the_world_asks_then_drops(self):
        """S17: the board's pick, then game.py's own release over the ground
        (its drop question for a dragon soul inventory attach); an accept
        drops it, a cancel sends nothing; the attach ends either way."""
        def flow(world, input):
            ground = game_window(world)
            input.press("bag", 0)
            ground.OnMouseLeftButtonUp()
            world.game.dialogs[-1].accept()
            input.press("bag", 1)
            ground.OnMouseLeftButtonUp()
            world.game.dialogs[-1].cancel()
        calls, _, nw = self.same(flow)
        self.assertEqual([args for name, args in calls if name == "net.SendItemDropPacketNew"],
                         [(DS, ds_pos(0, 3, 0), 1)])
        self.assertEqual(len([1 for name, _ in calls if name == "uiCommon.QuestionDialog.Open"]), 2)
        self.assertFalse(nw.mouse.isAttached())

    def test_s18_a_highlight_shows_on_its_page_until_hovered(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.open(0, 3)
            with world.game, quiet():
                world.ds.HighlightSlot(ds_pos(0, 3, 1))
                world.ds.RefreshItemSlot()
        self.assert_same_window(legacy, novaui)
        self.assertTrue(model(novaui.ds)["bag"][1]["active"])
        for world in (legacy, novaui):
            Input(world).over("bag", 1)
        self.assert_same_window(legacy, novaui)
        self.assertFalse(model(novaui.ds)["bag"][1]["active"], "a hover takes the highlight away (OverInItem)")

    def test_s19_the_tooltips(self):
        def flow(world, input):
            input.over("bag", 0)
            input.out("bag", 0)
            input.over("equip", START + 1)
            input.out("equip", START + 1)
        (_, lw), (_, nw) = self.run_flow(flow)
        calls = [call for call in nw.tooltip.calls if call[0] in ("SetInventoryItem", "HideToolTip")]
        self.assertEqual(calls, [call for call in lw.tooltip.calls if call[0] in ("SetInventoryItem", "HideToolTip")])
        self.assertIn(("SetInventoryItem", ds_pos(0, 3, 0), DS), calls)
        self.assertIn(("SetInventoryItem", START + 1), calls)

    def test_s20_close_by_the_title_bar_and_by_escape(self):
        def flow(world, input):
            input.close()
            world.ds.Show()
            world.game.press_escape()
        calls, lw, nw = self.same(flow)
        self.assertEqual(calls, [])
        self.assertFalse(lw.ds.IsShow())
        self.assertFalse(nw.ds.IsShow())
        self.assertNotIn(DS_DOCUMENT, nw.game.loaded_documents())


class F2RightPress(DragonSoulTest):
    def test_a_right_press_on_a_dragon_soul_while_another_is_attached_follows_attach_right(self):
        """F-2 (P15 spec 8.2): legacy's CSlotWindow sends the unselect event
        whatever is attached (S6's question for the clicked item); NovaUI does
        while nui_slots.ATTACH_RIGHT holds."""
        def flow(world, input):
            input.deck(1)
            input.press("bag", 0)
            input.press("bag", 3, 1)
            input.right_release()
        (legacy, _), (novaui, nw) = self.run_flow(flow)
        questions = [args for name, args in legacy if name == "uiCommon.QuestionDialog2.Open"]
        self.assertEqual(len(questions), 1, "legacy asks to equip the clicked dragon soul")
        if nw.m("nui_slots").ATTACH_RIGHT:
            self.assertEqual(novaui, legacy)
        else:
            self.assertEqual([args for name, args in novaui if name == "uiCommon.QuestionDialog2.Open"], [])
        self.assertFalse(nw.mouse.isAttached())


class Leak(DragonSoulTest):
    """P15 spec 7: a dragon soul's attach icon is freed once, by legacy's
    DeattachObject with its fix, else by nui_slots.adopt_attach."""

    def freed(self, world, flag):
        world.m("mouseModule").DEATTACH_FREES_EVERY_ICON = flag
        world.open(0, 3)
        Input(world).press("bag", 0)
        Input(world).press("bag", 9)            # the move ends the attach
        Input(world).press("bag", 1)
        Input(world).right_release()            # a cancel ends it
        made = [handle for kind, handle in world.game.created if kind == "item"]
        freed = [handle for kind, handle in world.game.deleted]
        return made, freed

    def test_each_attach_icon_is_freed_exactly_once_with_and_without_the_legacy_fix(self):
        for flag in (True, False):
            made, freed = self.freed(World(True), flag)
            with self.subTest(flag=flag):
                self.assertEqual(len(made), 2)
                self.assertEqual(sorted(freed), sorted(made))
        made, freed = self.freed(World(False), False)
        self.assertEqual(freed, [], "legacy without its fix leaks them")

    def test_a_press_that_keeps_the_attach_frees_nothing_twice(self):
        """Review R-2, through the board without the legacy fix: an F-2
        right press on an empty bag cell (the bag binds no unselect-empty
        handler, so the attach stays until the right release cancels it),
        and a right press on the picked item itself."""
        for second in (20, 0):
            world = World(True)
            world.m("mouseModule").DEATTACH_FREES_EVERY_ICON = False
            world.open(0, 3)
            Input(world).press("bag", 0)
            Input(world).press("bag", second, 1)
            Input(world).right_release()
            made = [handle for kind, handle in world.game.created if kind == "item"]
            freed = [handle for kind, handle in world.game.deleted]
            with self.subTest(second=second):
                self.assertEqual(len(made), 1)
                self.assertEqual(freed, made, "freed exactly once")


# --- the refine window's flows (P15 spec 6.5) -----------------------------------------------------------

class RefineFlows(DragonSoulTest):
    def refine_flow(self, flow, setup=stock):
        (legacy, lw), (novaui, nw) = self.run_flow(flow, refine=True, setup=setup)
        self.assertEqual(novaui, legacy)
        if nw.refine.IsShow():
            self.assert_same_refine(lw, nw)
        return legacy, lw, nw

    def test_r1_open_in_grade_mode_with_the_dragon_soul_window(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.make()
            world.open_refine()
        self.assert_same_refine(legacy, novaui)
        self.assertTrue(novaui.ds.IsShow())
        self.assertEqual(model(novaui.refine)["fee"], "0 Yang")

    def test_r3_r6_grade_drag_in_from_the_dragon_soul_window_and_refine(self):
        def flow(world, input):
            input.press("bag", 0)
            input.press("cell", 0)
            input.press("bag", 1, 1)            # R4 (S7)
            input.press("bag", 2)
            input.drop("cell", 2)
            input.do_refine()
        calls, lw, nw = self.refine_flow(flow)
        refines = [args for name, args in calls if name == "player.SendDragonSoulRefine"]
        self.assertEqual(refines, [(P["DS_SUB_HEADER_DO_UPGRADE"], {0: (DS, ds_pos(0, 3, 0), 1), 1: (DS, ds_pos(0, 3, 1), 1),
                                                                     2: (DS, ds_pos(0, 3, 2), 1)})])
        self.assertEqual(model(nw.refine)["fee"], "100.000 Yang")

    def test_r6_a_missing_cell_shows_the_popup(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            input.do_refine()
        calls, _, _ = self.refine_flow(flow)
        self.assertNotIn("player.SendDragonSoulRefine", [name for name, _ in calls])
        self.assertIn("uiCommon.PopupDialog.Open", [name for name, _ in calls])

    def test_r3_refusals_a_wrong_grade_a_stone_in_grade_mode_a_closed_cell(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            input.grade(4)
            input.press("bag", 0)               # the legendary diamond: another grade
            input.press("cell", 1)
            input.press("cell", 9)              # a closed cell: nothing, still attached
            input.right_release()
            world.mouse.AttachObject(world.ds, ST_INV, 10, 100300, 5)
            input.press("cell", 1)              # the bean: not a dragon soul
        calls, _, _ = self.refine_flow(flow)
        self.assertEqual(len([1 for name, _ in calls if name == "uiCommon.PopupDialog.Open"]), 2)

    def test_r3_r6_the_refusals_and_a_missing_cell_in_every_mode(self):
        """P15 spec 6.8, per mode: step, another step and a missing cell;
        strength, a dragon soul at its strength maximum, an item that is no
        refine stone and a missing stone; grade, another kind. Each popup is
        legacy's, nothing is refined, a mode change puts the counts back.
        (A page refresh while a placed item's count is 0 shows its cell
        empty in both UIs, legacy's rule, so no flow presses such a cell.)"""
        def setup(game):
            stock(game)
            # Antique step 0 at strength 4: dragon_soul_refine_settings' maximum.
            game.item_limits[113040] = [(LIMITS["LIMIT_TIMER_BASED_ON_WEAR"], 0)]
            game.give((DS, ds_pos(0, 3, 12)), 113040, 1, sockets=(3600, 0, 0))

        def flow(world, input):
            input.mode("step")
            input.press("bag", 0, 1)            # step 0: four needed
            input.press("bag", 3, 1)            # step 3: another step
            input.do_refine()                   # one of four
            input.mode("strength")              # the flush puts the diamond's count back
            input.press("bag", 12, 1)           # at its strength maximum
            input.press("bag", 4, 1)            # strength 1: the dragon soul cell
            world.refine.AutoSetItem((INV, 11), 1)  # a weapon: no refine stone
            input.do_refine()                   # the stone's cell is empty
            input.mode("grade")
            input.press("bag", 1, 1)            # a diamond sets the recipe
            input.kind(1)
            input.press("bag", 2)               # a ruby: another kind
            input.press("cell", 1)
        calls, lw, nw = self.refine_flow(flow, setup=setup)
        locale = nw.game.modules["localeInfo"]
        self.assertEqual([args[0] for name, args in calls if name == "uiCommon.PopupDialog.Open"],
                         [locale.DRAGON_SOUL_INVALID_DRAGON_SOUL, locale.DRAGON_SOUL_NOT_ENOUGH_MATERIAL,
                          locale.DRAGON_SOUL_CANNOT_REFINE_MORE, locale.DRAGON_SOUL_NOT_DRAGON_SOUL_REFINE_STONE,
                          locale.DRAGON_SOUL_NOT_ENOUGH_MATERIAL, locale.DRAGON_SOUL_INVALID_DRAGON_SOUL])
        self.assertNotIn("player.SendDragonSoulRefine", [name for name, _ in calls])
        counts = [args for name, args in calls if name == "player.SetItemCount"]
        self.assertEqual(counts, [(DS, ds_pos(0, 3, 0), 0), (DS, ds_pos(0, 3, 0), 1), (DS, ds_pos(0, 3, 4), 0),
                                  (DS, ds_pos(0, 3, 4), 1), (DS, ds_pos(0, 3, 1), 0)])
        cells = model(nw.refine)["cells"]
        self.assertEqual([(c["kind"], c["ghost"], c["closed"]) for c in cells[:4]],
                         [("item", False, False), ("icon", True, False), ("icon", True, False), ("", False, True)])
        self.assertEqual(model(nw.refine)["fee"], "100.000 Yang")

    def test_r5_take_out_puts_the_count_back_and_resets_with_the_last_item(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            input.press("bag", 1, 1)
            input.press("cell", 1)
            input.press("cell", 0)
        calls, lw, nw = self.refine_flow(flow)
        counts = [args for name, args in calls if name == "player.SetItemCount"]
        self.assertEqual(counts, [(DS, ds_pos(0, 3, 0), 0), (DS, ds_pos(0, 3, 1), 0), (DS, ds_pos(0, 3, 1), 1),
                                  (DS, ds_pos(0, 3, 0), 1)])
        self.assertEqual(model(nw.refine)["fee"], "0 Yang")

    def test_r2_step_mode_flushes_and_refines(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            input.mode("step")
            input.press("bag", 3, 1)
            input.do_refine()
        calls, _, nw = self.refine_flow(flow)
        self.assertIn(("player.SetItemCount", (DS, ds_pos(0, 3, 0), 1)), calls, "the mode change flushes")
        self.assertIn(("player.SendDragonSoulRefine", (P["DS_SUB_HEADER_DO_IMPROVEMENT"], {0: (DS, ds_pos(0, 3, 3), 1)})),
                      calls)
        self.assertEqual(model(nw.refine)["fee"], "50.000 Yang")
        self.assertEqual([c["closed"] for c in model(nw.refine)["cells"]][:2], [False, True])

    def test_r3_r4_strength_mode_the_stone_from_the_inventory_and_the_forced_cells(self):
        def flow(world, input):
            input.mode("strength")
            input.press("bag", 4)
            input.drop("cell", 0)                       # the stone's ghost: forced into cell 1
            world.refine.AutoSetItem((INV, 10), 1)     # the inventory's right press (uiinventory.py:1198-1201)
            input.do_refine()
        calls, _, nw = self.refine_flow(flow)
        self.assertIn(("player.SendDragonSoulRefine", (P["DS_SUB_HEADER_DO_REFINE"], {0: (INV, 10, 1),
                                                                                      1: (DS, ds_pos(0, 3, 4), 1)})), calls)
        cells = model(nw.refine)["cells"]
        self.assertEqual((cells[0]["type"], cells[0]["ref"]), (ST_INV, 10))
        self.assertEqual(model(nw.refine)["fee"], "10.000 Yang")

    def test_r7_the_result_after_a_success_and_a_fail(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            world.refine.RefineSucceed(DS, ds_pos(0, 3, 9))
            input.over("result", 0)
            input.out("result", 0)
            input.press("bag", 3, 1)
            world.refine.RefineFail(REFINE_FAIL, DS, ds_pos(0, 3, 3))
            world.refine.RefineFail(REFINE_FAIL + 1, DS, ds_pos(0, 3, 3))
        calls, lw, nw = self.refine_flow(flow)
        self.assertEqual(lw.tooltip.calls, nw.tooltip.calls)

    def test_r7_a_success_shows_the_result_cell(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.open(0, 3)
            world.open_refine()
            with world.game, quiet():
                world.refine.RefineSucceed(DS, ds_pos(0, 3, 8))
        self.assert_same_refine(legacy, novaui)
        result = model(novaui.refine)["result"][0]
        self.assertEqual((result["kind"], result["type"], result["ref"]), ("item", ST_DS, ds_pos(0, 3, 8)))

    def test_r8_close_flushes_and_sends_the_close(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            input.close("refine")
        calls, lw, nw = self.refine_flow(flow)
        self.assertEqual(calls[-2:], [("player.SetItemCount", (DS, ds_pos(0, 3, 0), 1)),
                                      ("player.SendDragonSoulRefine", (P["DRAGON_SOUL_REFINE_CLOSE"],))])
        self.assertFalse(nw.refine.IsShow())
        self.assertNotIn(DSR_DOCUMENT, nw.game.loaded_documents())

    def test_r1_r7_r8_through_the_interface_s_entry_points(self):
        """interfacemodule.py's own refine entry points, which the server's
        packets reach and the kit's client-side refine calls (P15 spec 9.5):
        a result while hidden does nothing; the open shows the dragon soul
        window too; a success and a fail show their result; the close
        flushes and sends the close; a second close does nothing."""
        results = []
        for world in self.worlds():
            world.make()
            mark = world.mark()
            with world.game, quiet():
                interface = interface_of(world)
                interface.SucceedDragonSoulRefine(DS, ds_pos(0, 3, 8))
                interface.OpenDragonSoulRefineWindow()
                opened = (world.refine.IsShow(), world.ds.IsShow())
                Input(world).grade(3)
                Input(world).press("bag", 0, 1)
                interface.SucceedDragonSoulRefine(DS, ds_pos(0, 3, 8))
                Input(world).press("bag", 3, 1)
                # The server's result names an item whose count the client
                # keeps (a placed one reads 0 until the server's update).
                interface.FailDragonSoulRefine(REFINE_FAIL, DS, ds_pos(0, 3, 2))
            results.append((world, opened, mark))
        (lw, legacy_opened, legacy_mark), (nw, novaui_opened, novaui_mark) = results
        self.assertEqual(novaui_opened, legacy_opened)
        self.assertEqual(legacy_opened, (True, True))
        self.assert_same_refine(lw, nw)
        self.assert_same_window(lw, nw)
        result = model(nw.refine)["result"][0]
        self.assertEqual((result["kind"], result["ref"]), ("item", ds_pos(0, 3, 2)))
        for world in (lw, nw):
            with world.game, quiet():
                interface = interface_of(world)
                interface.CloseDragonSoulRefineWindow()
                interface.CloseDragonSoulRefineWindow()
        legacy, novaui = lw.effects_since(legacy_mark), nw.effects_since(novaui_mark)
        self.assertEqual(novaui, legacy)
        self.assertEqual([args for name, args in legacy if name == "player.SendDragonSoulRefine"],
                         [(P["DRAGON_SOUL_REFINE_CLOSE"],)])
        self.assertFalse(nw.refine.IsShow())
        self.assertEqual(nw.game.loaded_documents(), [DS_DOCUMENT])

    def test_r9_the_tooltips_of_a_placed_item_and_an_empty_cell(self):
        def flow(world, input):
            input.press("bag", 0, 1)
            input.over("cell", 0)
            input.over("cell", 1)
            input.out("cell", 1)
        (_, lw), (_, nw) = self.run_flow(flow, refine=True)
        self.assertEqual(nw.tooltip.calls, lw.tooltip.calls)
        self.assertIn(("SetInventoryItem", ds_pos(0, 3, 0), DS), nw.tooltip.calls)

    def test_each_novaui_window_works_with_the_other_s_legacy_one(self):
        """A right press in the dragon soul window puts the item into the
        refine window (S7), whichever of the two is NovaUI's."""
        results = []
        for windows in ("+dragon-soul-refine", "+dragon-soul", FLAGS, ""):
            world = World(bool(windows), windows=windows or FLAGS)
            world.open(0, 3)
            world.open_refine()
            mark = world.mark()
            Input(world).press("bag", 0, 1)
            Input(world).press("bag", 3)
            Input(world).drop("cell", 1)
            results.append(world.effects_since(mark))
        self.assertEqual(results[0], results[3])
        self.assertEqual(results[1], results[3])
        self.assertEqual(results[2], results[3])
        self.assertIn(("player.SetItemCount", (DS, ds_pos(0, 3, 0), 0)), results[0])


# --- the boards ---------------------------------------------------------------------------------------------

class Boards(DragonSoulTest):
    def test_no_per_frame_python(self):
        world = World(True)
        for module, name in (("nui_dragon_soul", "DragonSoulWindow"), ("nui_dragon_soul_refine", "DragonSoulRefineWindow")):
            cls = getattr(world.m(module), name)
            self.assertFalse(callable(getattr(cls, "OnUpdate", None)), name)
            self.assertFalse(callable(getattr(cls, "OnRender", None)), name)
            self.assertNotRegex(read(os.path.join(ROOT, module + ".py")), r"def OnUpdate|def OnRender")

    def test_on_demand_and_the_place_kept_across_hides(self):
        world = World(True)
        world.make()
        self.assertEqual(world.game.loaded_documents(), [])
        world.open()
        self.assertEqual(world.game.loaded_documents(), [DS_DOCUMENT])
        world.game.state.boxes[(DS_DOCUMENT, "")] = (300.0, 120.0, 374.0, 539.0)
        with world.game, quiet():
            world.ds.Hide()
        self.assertEqual(world.game.loaded_documents(), [])
        world.open()
        self.assertEqual(board(world.ds).placement, ("position", 300.0, 120.0, (0.0, 0.0)))
        self.assertTrue(model(world.ds)["placed"])
        world.open_refine()
        self.assertEqual(sorted(world.game.loaded_documents()), sorted([DS_DOCUMENT, DSR_DOCUMENT]))
        with world.game, quiet():
            world.refine.Destroy()
            world.ds.Destroy()
        self.assertEqual(world.game.loaded_documents(), [])

    def test_a_refresh_while_hidden_reaches_the_next_show(self):
        world = World(True)
        world.open(0, 3)
        with world.game, quiet():
            world.ds.Hide()
            world.game.give((DS, ds_pos(0, 3, 30)), 113100, 1, sockets=(3600, 0, 0))
            world.game.item_limits[113100] = [(LIMITS["LIMIT_TIMER_BASED_ON_WEAR"], 0)]
            world.ds.RefreshItemSlot()
            world.ds.ActivateDragonSoulByExtern(0)
        world.open()
        self.assertEqual(model(world.ds)["bag"][30]["icon"], "/icon/item/113100.tga")
        self.assertTrue(model(world.ds)["activated"])
        self.assertTrue(model(world.ds)["equip"][0]["active"])

    def test_the_interface_s_calls_reach_the_shown_board(self):
        world = World(True)
        world.open(0, 3)
        with world.game, quiet():
            world.ds.ActivateDragonSoulByExtern(1)
        self.assertEqual((model(world.ds)["deck"], model(world.ds)["activated"]), (1, True))
        self.assertEqual([d["down"] for d in model(world.ds)["decks"]], [False, True])
        with world.game, quiet():
            world.ds.DeactivateDragonSoul()
        self.assertFalse(model(world.ds)["activated"])
        self.assertEqual([c["active"] for c in model(world.ds)["equip"]], [False] * 6)

    def test_a_hide_resets_the_hovered_cell(self):
        """R-1's rule (P14): the hovered cell hears no mouseout when its board
        goes, so the hide sends the over-out legacy's next mouse move sends."""
        world = World(True)
        world.open(0, 3)
        Input(world).over("bag", 0)
        self.assertTrue(world.tooltip.visible)
        with world.game, quiet():
            world.ds.Close()
            world.ds.RefreshItemSlot()
        self.assertFalse(world.tooltip.visible)
        self.assertIsNone(world.ds._bag_events.hovered)

    def test_a_press_raises_the_window_once(self):
        world = World(True)
        world.open(0, 3)
        raised = []
        original = world.ds.SetTop
        world.ds.SetTop = lambda: (raised.append(1), original())
        with world.game, quiet():
            press(world.ds, "bag_press", 7, 0)
            press(world.ds, "grade_press", 1, 0)
        self.assertEqual(raised, [1, 1])

    def test_a_hover_that_changes_nothing_sets_nothing(self):
        world = World(True)
        world.open(0, 3)
        sets = []
        shown = board(world.ds)
        original = shown.set
        shown.set = lambda **values: (sets.append(sorted(values)), original(**values))[1]
        Input(world).over("bag", 0)
        Input(world).out("bag", 0)
        self.assertEqual(sets, [], "the hover deactivates an inactive cell: nothing to draw")


# --- the fixtures and the markup -----------------------------------------------------------------------------

def kind_of(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def fixture(window, variant=None):
    name = "%s.%s.fixture.json" % (window, variant) if variant else "%s.fixture.json" % window
    data = json.loads(read(os.path.join(WINDOWS, window, name)))
    return data[list(data)[0]]


class Fixtures(DragonSoulTest):
    CASES = (("dragon-soul", (None, "deck2", "foundation", "hover", "attaching"), "ds", ("bag", "equip", "kinds", "grades", "decks")),
             ("dragon-soul-refine", (None, "step", "strength", "result", "foundation", "hover"), "refine",
              ("cells", "result", "modes")))

    def test_every_fixture_holds_the_model_s_keys_with_their_kinds(self):
        world = World(True)
        world.open(0, 3)
        world.open_refine()
        for window, variants, attribute, lists in self.CASES:
            live = model(getattr(world, attribute))
            for variant in variants:
                data = fixture(window, variant)
                with self.subTest(window=window, variant=variant):
                    self.assertEqual(sorted(data), sorted(live))
                    for key, value in live.items():
                        self.assertEqual(kind_of(data[key]), kind_of(value), key)
                    for key in lists:
                        self.assertEqual(len(data[key]), len(live[key]), key)
                        self.assertEqual(sorted(data[key][0]), sorted(live[key][0]), key)

    def test_the_fixtures_are_current(self):
        process = subprocess.run([sys.executable, "-B", os.path.join(support.support.HERE, "nui_w3c_fixtures.py"), "--check",
                                  "--window", "dragon-soul", "--window", "dragon-soul-refine"],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertNotIn("pending", process.stdout)

    def test_every_data_event_has_a_handler_and_every_grid_binds_attach_right(self):
        world = World(True)
        for window, module, board_class, grids in (
                ("dragon-soul", "nui_dragon_soul", "_DragonSoulBoard", ["ds-bag", "ds-equip"]),
                ("dragon-soul-refine", "nui_dragon_soul_refine", "_RefineBoard", ["dsr-cells", "dsr-result"])):
            markup = read(os.path.join(WINDOWS, window, window + ".rml"))
            handlers = set()
            for value in vars(getattr(world.m(module), board_class)).values():
                handlers.update(getattr(value, "_nui_events", ()))
            events = set(re.findall(r'data-event-[a-z]+="([a-z_]+)\(', markup))
            with self.subTest(window=window):
                self.assertEqual(events - handlers, set())
                found = re.findall(r'<div id="([a-z-]+)" class="nui-slot-grid[^"]*"([^>]*)>', markup)
                self.assertEqual(sorted(name for name, _ in found), sorted(grids))
                for name, attributes in found:
                    self.assertIn('data-class-nui-attach-right="attach_right"', attributes, name)

    def test_the_boards_draw_in_their_legacy_windows_band(self):
        for window in ("dragon-soul", "dragon-soul-refine"):
            body = re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", read(os.path.join(WINDOWS, window, window + ".rml")))
            self.assertIn("nui-below-legacy-ui", body.group(1).split(), window)
        source = read(os.path.join(ROOT, "uidragonsoul.py"))
        self.assertEqual(source.count("ui.ScriptWindow.__init__(self)\n"), 2, "no layer argument: the UI layer")

    def test_the_element_ids_the_kit_reads(self):
        """P15 spec 5.3 and 6.3's ids."""
        ds = read(os.path.join(WINDOWS, "dragon-soul", "dragon-soul.rml"))
        for literal in ('id="ds-close"', 'id="ds-title"', 'id="ds-kind-title"', 'id="ds-activate"', 'id="ds-bag"',
                        "'ds-kind-' + k.index", "'ds-grade-' + g.index", "'ds-deck-' + d.index", "'ds-bag-' + it_index",
                        "'ds-equip-' + c.sub"):
            self.assertIn(literal, ds)
        dsr = read(os.path.join(WINDOWS, "dragon-soul-refine", "dragon-soul-refine.rml"))
        for literal in ('id="dsr-close"', 'id="dsr-title"', 'id="dsr-fee"', 'id="dsr-refine"', "'dsr-mode-' + m.name",
                        "'dsr-cell-' + it_index", "'dsr-result-' + it_index"):
            self.assertIn(literal, dsr)


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class ElementCounts(unittest.TestCase):
    """P15 spec 10's estimates: the dragon soul window about 190 elements,
    the refine window fewer (nuitool snap --stats)."""

    def stats(self, window, size):
        work = tempfile.mkdtemp(prefix="nui-ds-")
        self.addCleanup(shutil.rmtree, work, True)
        repo = os.path.normpath(os.path.join(support.support.HERE, ".."))
        stats = os.path.join(work, "stats.json")
        command = [NUITOOL, "snap", "--root", "assets/nui", "--root", "assets/icon", "--root", "assets/ETC", "--root",
                   "assets/metin2_patch_ds", "--root", "assets/locale", "--locale", "assets/locale/locale/en", "--doc",
                   "nui/windows/%s/%s.rml" % (window, window), "--theme", "modern-dark", "--scale", "1", "--size", size,
                   "--fixture", "assets/nui/nui/windows/%s/%s.fixture.json" % (window, window),
                   "--out", os.path.join(work, "out.png"), "--stats", stats]
        process = subprocess.run(command, capture_output=True, text=True, cwd=repo)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        with open(stats, encoding="utf-8") as handle:
            return json.load(handle)

    def test_the_windows_element_counts(self):
        ds = self.stats("dragon-soul", "640x600")
        dsr = self.stats("dragon-soul-refine", "1000x600")
        self.assertLess(ds["elements"], 320, ds["elements"])
        self.assertLess(dsr["elements"], 200, dsr["elements"])



class Order(DragonSoulTest):
    """Validation VF-1 (IV-C IV-11): legacy's window manager raises the
    window under a press (SetTopUIWindow) before the press reaches it, and
    DragonSoulWindow.Show raises nothing (CWindow::Show), so the inventory
    whose dragon soul button opened the window stays above it. A NovaUI
    board shown at a Show draws above every other document, so the dragon
    soul window's Show brings back the boards raised since its own last
    raise (nui_hud.keep_order)."""

    def world(self):
        world = World(True, windows=FLAGS + ",+inventory")
        game = world.game
        with quiet():
            for name in ("nui_belt_inventory", "nui_costume", "nui_inventory"):
                game.load(name, name + ".py")
        world.make()
        interface = game.interface

        def toggle():
            # interfacemodule.py:1033-1048, a qualified tester.
            if not world.ds.IsShow():
                world.ds.Show()
            else:
                world.ds.Close()
        interface.ToggleDragonSoulWindow = toggle
        with game, quiet():
            inventory = world.nui_windows.make("inventory", world.m("uiInventory").InventoryWindow,
                                               "nui_inventory.InventoryWindow")
            inventory.BindInterfaceClass(interface)
            inventory.SetItemToolTip(game.modules["uiToolTip"].ItemToolTip())
            inventory.SetDragonSoulRefineWindow(world.refine)
        # The draw order of the documents, bottom first: a show or a
        # bring_to_front puts a document on top.
        order = world.order = []
        base = game.modules["nui"].Window
        show, front = base.show, base.bring_to_front

        def ordered(method):
            def run(window, *args):
                done = method(window, *args)
                if done:
                    if window in order:
                        order.remove(window)
                    order.append(window)
                return done
            return run
        base.show, base.bring_to_front = ordered(show), ordered(front)
        self.addCleanup(setattr, base, "show", show)
        self.addCleanup(setattr, base, "bring_to_front", front)
        return world, inventory

    def press_dss(self, world, inventory):
        """A left press on the inventory's dragon soul button: its handler,
        then the body's board_press, as RmlUi bubbles the press."""
        with world.game, quiet():
            shown = board(inventory)
            shown.fire("dss_press", 0)
            if board(inventory) is shown:
                shown.fire("board_press", 0)

    def test_the_inventory_pressed_stays_above_the_window_its_button_opens(self):
        world, inventory = self.world()
        with world.game, quiet():
            inventory.Show()
            inventory.SetTop()          # Interface.ToggleInventoryWindow
        for round in (1, 2):
            self.press_dss(world, inventory)
            with self.subTest(round=round):
                self.assertTrue(world.ds.IsShow())
                ds_board, inv_board = board(world.ds), board(inventory)
                self.assertIsNotNone(ds_board)
                self.assertLess(world.order.index(ds_board), world.order.index(inv_board),
                                "the inventory draws above the dragon soul window, as legacy's")
            # A second press reaches the button, not the window over it, and closes it.
            self.press_dss(world, inventory)
            self.assertFalse(world.ds.IsShow())

    def test_a_press_on_the_dragon_soul_window_raises_it_over_the_inventory(self):
        world, inventory = self.world()
        with world.game, quiet():
            inventory.Show()
            inventory.SetTop()
        self.press_dss(world, inventory)
        Input(world).grade(3)           # a press on the dragon soul board raises it
        self.assertLess(world.order.index(board(inventory)), world.order.index(board(world.ds)))
        # Shown again by the key (ToggleDragonSoulWindowWithNoInfo) after the
        # inventory was raised: legacy keeps the inventory above.
        with world.game, quiet():
            world.ds.Close()
            inventory.SetTop()
            world.ds.Show()
        self.assertLess(world.order.index(board(world.ds)), world.order.index(board(inventory)))
        # A window raised before the dragon soul window's last raise stays below it.
        with world.game, quiet():
            world.ds.SetTop()
            world.ds.Close()
            world.ds.Show()
        self.assertLess(world.order.index(board(inventory)), world.order.index(board(world.ds)))


if __name__ == "__main__":
    unittest.main()
