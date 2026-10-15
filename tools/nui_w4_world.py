"""The test world of the Wave 4 windows (P16 spec 11.3): a nui_game_support
Game with the Wave 2b to 4 stand-ins, the legacy Wave 4 modules loaded from
assets/root (their uiscripts read as the client reads them) and the NovaUI
modules over them. One World per side of a differential test: World(False)
makes the legacy windows (every flag off), World(True) the NovaUI ones;
both start from the same state (`setup(game)`), and their effects are the
calls of W4_COMPARED and the dialogs, getters left out."""
import contextlib
import io
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOWS_DIR = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
FLAGS = "+trade"
# The calls a differential test compares: W4_COMPARED's modules, the sounds and
# the dialogs legacy opens (uiCommon, uiPickMoney).
EFFECT_MODULES = support.W4_COMPARED + ("snd", "uiCommon", "uiPickMoney")
TRADE_MODULES = ("nui_limits", "nui_proxies", "nui_form_proxies", "nui_facade", "nui_exchange", "nui_shop",
                 "nui_private_shop", "nui_safebox", "nui_safebox_password", "nui_change_password", "nui_mall",
                 "nui_equipment_view")
P = support.module_constants()["player"]


def quiet():
    """The legacy windows print banners."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


class World(object):
    """One stand-in client with the Wave 4 windows (module docstring)."""

    def __init__(self, nui_on, windows=FLAGS, engine_4=True, setup=None, modules=TRADE_MODULES):
        game = self.game = support.Game()
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        support.install_wave3b_ui(game)
        support.install_wave4_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        game.modules["localeInfo"] = support.locale_info("en")
        for name in ("networkModule", "interfaceModule"):
            game.put(name, types.ModuleType(name))
        if not engine_4:
            game.modules["nuigame"].lack("WatchLeaveRange", "StopLeaveRange", "LeaveRangeState")
        self.nui_on = nui_on
        if setup is not None:
            setup(game)
        game.load_standard()
        with quiet():
            self.legacy = support.load_wave4_legacy(game)
            for name in modules:
                if os.path.isfile(os.path.join(ROOT, name + ".py")):
                    game.load(name, name + ".py")
        self.nui_windows = game.loaded["nui_windows"]
        self.tooltip = game.modules["uiToolTip"].ItemToolTip()

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def m(self, name):
        return self.game.loaded.get(name) or self.game.modules[name]

    @property
    def mouse(self):
        return self.m("mouseModule").mouseController

    def mark(self):
        return len(self.game.log)

    def effects_since(self, mark, modules=EFFECT_MODULES):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in modules and not support.is_getter(name)]

    def calls_since(self, mark, prefix):
        return [(name, args) for name, args in self.game.log[mark:] if name.startswith(prefix)]

    def make(self, window_id, legacy_module, legacy_class, novaui, *args):
        """nui_windows.make() as the Interface calls it."""
        with self.game, quiet():
            return self.nui_windows.make(window_id, getattr(self.m(legacy_module), legacy_class), novaui, *args)

    def attach(self, slot_type, slot_number, vnum, count=1):
        """What another window's pick attaches (the inventory's, the safebox's)."""
        with self.game:
            self.mouse.AttachObject(None, slot_type, slot_number, vnum, count)

    def attach_money(self, amount):
        with self.game:
            self.mouse.AttachMoney(None, P["SLOT_TYPE_INVENTORY"], amount)

    def documents(self):
        return self.game.loaded_documents()


def mirror_inventory(game):
    """The stand-in's items by plain inventory position, also under
    (player.INVENTORY, position), as the client answers both forms
    (player.GetItemIndex(pos) and GetItemIndex(window, pos))."""
    for key, value in list(game.items.items()):
        if isinstance(key, int):
            game.items[(P["INVENTORY"], key)] = value


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
    RmlUi runs last as the press bubbles, unless the press took the board
    away. The last argument is the button."""
    shown = board(window)
    result = fire(window, event, *args)
    if board(window) is shown and shown is not None and hasattr(type(shown), "on_board_press"):
        shown.fire("board_press", args[-1])
    return result


def fixture_keys(window, name, variant=""):
    """{key: kind} of a window's fixture model (kind: the value's type name)."""
    import json
    file_name = "%s.%s.fixture.json" % (name, variant) if variant else "%s.fixture.json" % name
    with open(os.path.join(WINDOWS_DIR, name, file_name), encoding="utf-8") as handle:
        data = json.load(handle)
    (model,) = data.values()
    return dict((key, type(value).__name__) for key, value in model.items())


def model_kinds(model):
    return dict((key, type(value).__name__) for key, value in model.items())
