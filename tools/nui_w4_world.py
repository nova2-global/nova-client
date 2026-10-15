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
# In import order: a module's NovaUI imports load before it (the two password
# dialogs' boards before nui_safebox).
TRADE_MODULES = ("nui_limits", "nui_proxies", "nui_form_proxies", "nui_facade", "nui_exchange", "nui_shop",
                 "nui_private_shop", "nui_safebox_password", "nui_change_password", "nui_safebox", "nui_mall",
                 "nui_equipment_view")
# The social windows (SOCIAL, P16 spec 11.4), in import order after the shared
# modules: the grade name dialog's board before the guild window.
SOCIAL_FLAGS = "+social"
SOCIAL_MODULES = ("nui_limits", "nui_proxies", "nui_form_proxies", "nui_facade", "nui_text", "nui_messenger",
                  "nui_whisper", "nui_guild_mark", "nui_guild_war_declare", "nui_guild_war_accept",
                  "nui_guild_grade_name", "nui_guild")
P = support.module_constants()["player"]


def _read_uiscript_as_the_client(path, screen=(1600, 900)):
    """nui_game_support.read_uiscript with the names legacy's
    ui.PythonScriptLoader puts in every uiscript's namespace (ui.py
    LoadScriptFile: PLAYER_NAME_MAX_LEN, DRAGON_SOUL_EQUIPMENT_SLOT_START,
    LOCALE_PATH, LOCALE_PATH_COMMON), which the whisper dialog's uiscript
    reads; the stand-in client answers them as the en client does."""
    file_name = os.path.join(support.UISCRIPT_ROOT, path.replace("\\", "/").lower())
    with open(file_name, encoding="utf-8", errors="replace") as handle:
        source = handle.read()
    namespace = {"SCREEN_WIDTH": screen[0], "SCREEN_HEIGHT": screen[1], "__name__": "uiscript",
                 "PLAYER_NAME_MAX_LEN": 12, "DRAGON_SOUL_EQUIPMENT_SLOT_START": 122, "LOCALE_PATH": "locale/en",
                 "LOCALE_PATH_COMMON": "locale/common"}
    exec(compile(source, file_name, "exec"), namespace)
    return namespace["window"]


# The stand-in loaders look read_uiscript up at each load.
support.read_uiscript = _read_uiscript_as_the_client


def quiet():
    """The legacy windows print banners."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def install_social_ui(game):
    """What the legacy social windows build in code beyond install_wave4_ui's
    stand-ins (uiguild.py's pages, P16 spec 5.9): ui.MakeImageBox,
    MakeTextLine, MakeButton and MakeSlotBar (ui.py:3656-3691), ui.SlotBar,
    a ui.ComboBox that keeps legacy's state (its text, items, enabled and
    open list; select(key) is a pick in its list, OnSelectItem), and the
    slot window calls of the guild skill page (SetSkillSlot, SetSlotCount,
    GetStartIndex, HasSlot, the slot buttons, cooldowns), recorded on the
    stand-in slot window as CSlotWindow keeps them."""
    ui = game.modules["ui"]
    Win = ui.Window

    def make_image_box(parent, name, x, y):
        image = ui.ImageBox()
        image.SetParent(parent)
        image.LoadImage(name)
        image.SetPosition(x, y)
        image.Show()
        return image

    def make_text_line(parent):
        line = ui.TextLine()
        line.SetParent(parent)
        line.Show()
        return line

    def make_button(parent, x, y, tooltip_text, path, up, over, down):
        button = ui.Button()
        button.SetParent(parent)
        button.SetPosition(x, y)
        button.SetToolTipText(tooltip_text)
        button.Show()
        return button

    def make_slot_bar(parent, x, y, width, height):
        bar = Win()
        bar.SetParent(parent)
        bar.SetSize(width, height)
        bar.SetPosition(x, y)
        bar.Show()
        return bar

    class ComboBox(Win):
        """ui.ComboBox (ui.py:2624-2781): its text, items (key, name), enabled
        state and open list; press() is its button's release, select(key)
        a pick in its list."""

        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.text = ""
            self.items = []
            self.enable = True
            self.isListOpened = False
            self.selected = None
            self.event = lambda *arg: None

        def SetEvent(self, event):
            self.event = event

        def Enable(self):
            self.enable = True

        def Disable(self):
            self.enable = False
            self.text = ""
            self.CloseListBox()

        def ClearItem(self):
            self.CloseListBox()
            self.items = []

        def InsertItem(self, index, name):
            self.items.append((index, name))

        def SetCurrentItem(self, text):
            self.text = text

        def SelectItem(self, key):
            self.selected = key

        def CloseListBox(self):
            self.isListOpened = False

        def Destroy(self):
            pass

        def press(self):
            if not self.enable:
                return
            if self.isListOpened:
                self.CloseListBox()
            elif self.items:
                self.isListOpened = True

        def select(self, key):
            self.CloseListBox()
            self.event(key)

    # The guild's image widgets call ui.ImageBox.__del__ (uiguild.py:514, :570).
    if "__del__" not in vars(ui.ImageBox):
        ui.ImageBox.__del__ = lambda self: None
    class PlainToolTip(support.ToolTip):
        """uiToolTip.ToolTip as the war dialogs and the messenger's love point
        build it: its title and lines kept (lines)."""

        def __init__(self, *args):
            support.ToolTip.__init__(self, "plain")
            self.lines = []

        def SetTitle(self, title):
            self.lines.append(("title", title))

        def AppendSpace(self, space):
            self.lines.append(("space", space))

        def AutoAppendTextLine(self, text, *args):
            self.lines.append(("line", text))

        def AppendTextLine(self, text, *args):
            self.lines.append(("line", text))

        def AlignHorizonalCenter(self):
            pass

        def ResizeToolTip(self):
            pass

    game.modules["uiToolTip"].ToolTip = PlainToolTip
    ui.MakeImageBox = make_image_box
    ui.MakeTextLine = make_text_line
    ui.MakeButton = make_button
    ui.MakeSlotBar = make_slot_bar
    ui.SlotBar = Win
    ui.ComboBox = ComboBox
    slots = support.LegacySlotWindow
    if not hasattr(slots, "SetSkillSlot"):
        for name, fn in _GUILD_SLOT_CALLS.items():
            setattr(slots, name, fn)
    return ui


def _set_skill_slot(self, index, skill_index, level):
    slot = self._slot(index)
    if slot is not None:
        slot.update({"vnum": int(skill_index), "count": int(level), "skill": True})


def _set_slot_count(self, index, count):
    slot = self._slot(index)
    if slot is not None:
        slot["count"] = int(count)


def _show_slot_button(self, index):
    self.__dict__.setdefault("buttons", set()).add(int(index))


def _hide_all_slot_button(self):
    self.__dict__["buttons"] = set()


def _set_slot_cool_time(self, index, cool_time, elapsed=0.0):
    self.__dict__.setdefault("cool_times", {})[int(index)] = (cool_time, elapsed)


def _set_pressed_slot_button_event(self, event):
    self.events["pressed_button"] = event


# The guild skill page's slot window calls (ui.py SlotWindow; CSlotWindow).
_GUILD_SLOT_CALLS = {
    "SetSkillSlot": _set_skill_slot,
    "SetSlotCount": _set_slot_count,
    "GetStartIndex": lambda self: self.start_index,
    "HasSlot": lambda self, index: int(index) in self.slots,
    "AppendSlotButton": lambda self, up, over="", down="": None,
    "ShowSlotButton": _show_slot_button,
    "HideAllSlotButton": _hide_all_slot_button,
    "SetSlotCoolTime": _set_slot_cool_time,
    "SetPressedSlotButtonEvent": _set_pressed_slot_button_event,
}


class World(object):
    """One stand-in client with the Wave 4 windows (module docstring)."""

    def __init__(self, nui_on, windows=FLAGS, engine_4=True, setup=None, modules=TRADE_MODULES, social=False):
        if social:
            if windows is FLAGS:
                windows = SOCIAL_FLAGS
            if modules is TRADE_MODULES:
                modules = SOCIAL_MODULES
        game = self.game = support.Game()
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        support.install_wave3b_ui(game)
        support.install_wave4_ui(game)
        if social:
            install_social_ui(game)
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
            self.legacy = support.load_wave4_legacy(game, social=social)
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


def fixture_model(name, variant=""):
    """A window's fixture model (its one model's keys and values)."""
    import json
    file_name = "%s.%s.fixture.json" % (name, variant) if variant else "%s.fixture.json" % name
    with open(os.path.join(WINDOWS_DIR, name, file_name), encoding="utf-8") as handle:
        data = json.load(handle)
    (model,) = data.values()
    return model


def model_kinds(model):
    return dict((key, type(value).__name__) for key, value in model.items())
