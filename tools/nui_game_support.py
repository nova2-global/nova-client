"""Stand-ins for the NovaUI HUD tests (nui_slots_test.py, nui_hud_core_test.py,
nui_hud_test.py): plain CPython, no client.

A Game holds the state of one stand-in client and the modules over it:

- `player`, `item`, `skill`, `guild` and `grpImage` answer from the state
  (Game.status, .items, .skills, .quick, .page, ...) and record every call;
- `net`, `chr`, `chrmgr`, `nonplayer`, `messenger`, `textTail` and `nuigame`
  record every call and answer 0 (a test sets an answer with Game.answer());
- `app` has a settable clock (Game.time, .global_time) and
  GetGlobalTimeStamp, `wndMgr` the screen size, the mouse and IsDragging;
- `localeInfo` and `uiScriptLocale` follow nui_test_support.LocaleInfo (an
  unknown name is its own name), with the SA entries the HUD reads as
  functions; `constInfo` is the real assets/root/constinfo.py;
- `mouseModule` is the real assets/root/mousemodule.py, its controller of a
  subclass that records each attach and detach (Game.attaches);
- `uiToolTip` has item and skill tooltips that record what they show;
- `ui` is nui_test_support's legacy ui stand-in, extended with the widgets
  the legacy HUD classes make: slot windows that keep which cells hold
  something, buttons that keep their event, tooltip and art, image boxes,
  text lines and number lines; ScriptWindow.GetChild raises KeyError for
  the names a legacy uiscript does not have (MISSING_CHILDREN);
- `nui` is nui_test_support's stand-in (Game.state).

Game.load(name) imports a module from assets/root over them. Game.log holds
every recorded call as (module.function, args) in order; Game.effects()
leaves out the getters (Get*, Is*, Has*, Can*, the quick slot index
conversions), as the differential tests compare them. HUD CONTENT extends
this in its own test file, not here.

Wave 2b (P10 spec 4.3) adds, for every Game:
- `chat`: CPythonChat's line store (300 lines, each with a serial) and its
  chat sets (board state, end position, modes, height, step), the wait list
  of AppendChatWithDelay, and GetLinkFromHyperlink as the client wraps an
  item link (Game.item_names gives the names); every call recorded;
- `ime`: PasteString types into the NovaUI text field that has the focus
  (NuiState.text_fields names the fields), as the client's paste bridge
  does (P10 spec D7), else into the legacy edit line with wndMgr's focus;
- `nuigame`: the Wave 2b functions (ChatAttach, ChatDetach, ChatState from
  the chat store and Game.chat_rows, ViewState, SetViewHoverFormat,
  AnchorState), recorded, a scripted answer (Game.answer) winning;
- `miniMap` (every function of PythonMiniMapModule.cpp, with the client's
  answer shapes), `shop`, `textTail`, `chr.GetProjectPosition`, the `guild`
  mark functions, `net.SendChatPacket`, `IsChatInsultIn`, `SendOnClickPacket`,
  `GetServerInfo`, `systemSetting.IsViewChat` and `IsShowSalesText`
  (Game.view_chat, .show_sales_text), `uiScriptLocale.ZONE_MAP`,
  `localeInfo.MINIMAP_ZONE_NAME_DICT`, `app.IsPressed` (Game.pressed) and the
  arrow and Alt key codes, `ui.GetHyperlink` (Game.hyperlink);
- wndMgr's focus as CWindowManager keeps it (Game.focus: ActivateWindow
  pushes the window that had it, which gets OnKillFocus; DeactivateWindow
  gives it back with OnSetFocus), behind ui.Window.SetFocus, KillFocus and
  IsFocus and wndMgr's own;
- install_wave2b_ui(game): the legacy widgets the Wave 2b legacy windows
  make (EditLine, DragButton, ScrollBar, SmallThinScrollBar, ThinBoard,
  MarkBox, Gauge, RadioButton, ToggleButton and buttons that keep their
  events), installed on request so the Wave 2a tests keep their widgets."""
import contextlib
import io
import os
import sys
import types
import weakref

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

ROOT = support.ROOT

GETTER_PREFIXES = ("Get", "Is", "Has", "Can", "LocalQuickSlotIndexTo", "Find")
# Modules whose calls the differential tests compare.
COMPARED = ("player", "net", "mouse", "app")

# Per legacy uiscript, the names it does not hold: GetChild raises KeyError
# for them, as ScriptWindow.GetChild does (taskbar.py has ExpandButton, not
# ChatButton; the left mouse button window has no button_skill, the right one
# no button_auto_attack, and neither a button_move or button_attack).
MISSING_CHILDREN = {
    "uiscript/taskbar.py": {"ChatButton"},
    "uiscript/mousebuttonwindow.py": {"button_skill", "button_move", "button_attack"},
    "uiscript/rightmousebuttonwindow.py": {"button_auto_attack", "button_move", "button_attack"},
}

PLAYER_CONSTANTS = {
    "SLOT_TYPE_NONE": 0, "SLOT_TYPE_INVENTORY": 1, "SLOT_TYPE_SKILL": 2, "SLOT_TYPE_EMOTION": 3,
    "SLOT_TYPE_SHOP": 4, "SLOT_TYPE_EXCHANGE_OWNER": 5, "SLOT_TYPE_EXCHANGE_TARGET": 6,
    "SLOT_TYPE_QUICK_SLOT": 7, "SLOT_TYPE_SAFEBOX": 8, "SLOT_TYPE_PRIVATE_SHOP": 9, "SLOT_TYPE_MALL": 10,
    "SLOT_TYPE_DRAGON_SOUL_INVENTORY": 11,
    "RESERVED_WINDOW": 0, "INVENTORY": 1, "EQUIPMENT": 2, "SAFEBOX": 3, "MALL": 4, "DRAGON_SOUL_INVENTORY": 5,
    "MBT_RIGHT": 0, "MBT_LEFT": 1, "MBT_MIDDLE": 2,
    "MBF_SMART": 0, "MBF_MOVE": 1, "MBF_CAMERA": 2, "MBF_ATTACK": 3, "MBF_SKILL": 4, "MBF_AUTO": 5,
    "MBS_CLICK": 0, "MBS_PRESS": 1,
    "LEVEL": 1, "EXP": 3, "NEXT_EXP": 4, "HP": 5, "MAX_HP": 6, "SP": 7, "MAX_SP": 8, "STAMINA": 9,
    "MAX_STAMINA": 10, "STAT": 28, "SKILL_ACTIVE": 29, "HP_RECOVERY": 32, "SP_RECOVERY": 33,
    "ENERGY": 128, "ENERGY_END_TIME": 129,
    "METIN_SOCKET_MAX_NUM": 3, "ITEM_MONEY": -1, "QUICKSLOT_PER_PAGE": 8, "QUICKSLOT_PAGES": 4,
}
SKILL_CONSTANTS = {"SKILL_TYPE_NONE": 0, "SKILL_TYPE_ACTIVE": 1, "SKILL_TYPE_SUPPORT": 2, "SKILL_TYPE_GUILD": 5}
WNDMGR_CONSTANTS = {"SLOT_STYLE_NONE": 0, "SLOT_STYLE_PICK_UP": 1, "SLOT_STYLE_SELECT": 2,
                    "HORIZONTAL_ALIGN_LEFT": 0, "HORIZONTAL_ALIGN_CENTER": 1, "HORIZONTAL_ALIGN_RIGHT": 2,
                    "VERTICAL_ALIGN_TOP": 0, "VERTICAL_ALIGN_CENTER": 1, "VERTICAL_ALIGN_BOTTOM": 2}
APP_CONSTANTS = {name: index for index, name in enumerate((
    "NORMAL", "ATTACK", "TARGET", "TALK", "CANT_GO", "PICK", "DOOR", "CHAIR", "MAGIC", "BUY", "SELL",
    "CAMERA_ROTATE", "HSIZE", "VSIZE", "HVSIZE"))}
APP_CONSTANTS.update({"ENABLE_ENERGY_SYSTEM": 1, "ENABLE_DRAGON_SOUL_SYSTEM": 1})
# Wave 2b: the keys the chat reads (app.VK_UP and VK_DOWN as the IME's
# OnIMEKeyDown gets them; the DirectInput codes app.IsPressed takes).
APP_CONSTANTS.update({"VK_UP": 0x26, "VK_DOWN": 0x28, "DIK_LALT": 0x38, "DIK_LSHIFT": 0x2A, "DIK_LCONTROL": 0x1D})
MINIMAP_CONSTANTS = {"TYPE_OPC": 0, "TYPE_OPCPVP": 1, "TYPE_OPCPVPSELF": 2, "TYPE_NPC": 3, "TYPE_MONSTER": 4, "TYPE_WARP": 5,
                     "TYPE_WAYPOINT": 6, "TYPE_PARTY": 7, "TYPE_EMPIRE": 8, "TYPE_EMPIRE_END": 12}
# miniMap's answers when a test scripts none (PythonMiniMapModule.cpp's shapes).
MINIMAP_ANSWERS = {"isShow": False, "isShowAtlas": False, "IsAtlas": False, "GetInfo": (0, "", 0, 0, 0),
                   "GetAtlasInfo": (0, "", 0, 0, 0, 0), "GetAtlasSize": (0, 0, 0), "GetGuildAreaID": 0}


def is_getter(name):
    """Whether a recorded "module.Function" is a getter the differential tests
    leave out."""
    function = name.rsplit(".", 1)[-1]
    return function.startswith(GETTER_PREFIXES)


class Recording(types.ModuleType):
    """A module that records every call of a function it does not define as
    (module.name, args) in `log` and answers `answers.get(name, 0)` (a
    callable answer is called with the arguments)."""

    def __init__(self, name, log, **members):
        types.ModuleType.__init__(self, name)
        self.__dict__["_log"] = log
        self.__dict__["_answers"] = {}
        for key, value in members.items():
            setattr(self, key, value)

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        log, answers, name = self.__dict__["_log"], self.__dict__["_answers"], self.__name__

        def record(*args):
            log.append((name + "." + attr, args))
            answer = answers.get(attr, 0)
            return answer(*args) if callable(answer) else answer
        record.__name__ = attr
        return record


def recorded(log, name, fn):
    """fn, recording (name, args) first."""
    def call(*args):
        log.append((name, args))
        return fn(*args)
    call.__name__ = name.rsplit(".", 1)[-1]
    return call


# --- the legacy ui stand-in, extended for the HUD classes ---------------------------

class LegacyWidget(support.Widget):
    """A legacy child window: records every call it does not define; keeps
    its shown state, event, tooltip text, button art, image and text."""

    def __init__(self, name=""):
        support.Widget.__init__(self, name)
        self.shown = False
        self.tooltip = None
        self.tooltip_color = None
        self.visuals = {"up": "", "over": "", "down": ""}
        self.image = ""
        self.ToolTipText = 0

    def SetToolTipText(self, text, x=0, y=0):
        self.calls.append(("SetToolTipText", text, x, y))
        self.tooltip = text

    def SetUpVisual(self, path):
        self.visuals["up"] = path

    def SetOverVisual(self, path):
        self.visuals["over"] = path

    def SetDownVisual(self, path):
        self.visuals["down"] = path

    def GetUpVisualFileName(self):
        return self.visuals["up"] or "%s_01.sub" % self.name

    def GetOverVisualFileName(self):
        return self.visuals["over"] or "%s_02.sub" % self.name

    def GetDownVisualFileName(self):
        return self.visuals["down"] or "%s_03.sub" % self.name

    def LoadImage(self, path):
        self.calls.append(("LoadImage", path))
        self.image = path

    def SetParent(self, parent):
        pass

    def SetTop(self):
        self.calls.append(("SetTop",))

    def IsIn(self):
        return False

    def GetGlobalPosition(self):
        return (0, 0)

    def GetLocalPosition(self):
        return (0, 0)


class LegacySlots(LegacyWidget):
    """A legacy slot window: keeps which cells hold something (CSlotWindow's
    isItem), their count, cover, cooldown and active state, and its events."""

    def __init__(self, name=""):
        LegacyWidget.__init__(self, name)
        self.cells = {}
        self.events = {}

    def _cell(self, index):
        return self.cells.setdefault(index, {"item": False, "count": "", "cover": False, "cool": None, "active": False})

    def ClearSlot(self, index):
        self.cells[index] = {"item": False, "count": "", "cover": False, "cool": None, "active": False}

    def SetItemSlot(self, index, vnum, count=0, color=None):
        if not vnum:
            self.ClearSlot(index)
            return
        cell = self._cell(index)
        cell.update({"item": True, "vnum": vnum, "count": str(count) if count > 1 else ""})

    def SetSkillSlotNew(self, index, skill_index, grade, level):
        self._cell(index).update({"item": True, "skill": skill_index})

    def SetEmotionSlot(self, index, emotion):
        self._cell(index).update({"item": True, "emotion": emotion})

    def SetSlotCountNew(self, index, grade, level):
        import nui_slots
        self._cell(index)["count"] = nui_slots.count_label(grade, level)

    def SetSlotCount(self, index, count):
        self._cell(index)["count"] = str(count) if count > 1 else ""

    def SetCoverButton(self, index, *args):
        self._cell(index)["cover"] = True

    def SetSlotCoolTime(self, index, cool_time, elapsed=0.0):
        self._cell(index)["cool"] = (cool_time, elapsed) if cool_time else None

    def ActivateSlot(self, index):
        self._cell(index)["active"] = True

    def DeactivateSlot(self, index):
        self._cell(index)["active"] = False

    def RefreshSlot(self):
        pass

    def is_item(self, index):
        return self._cell(index)["item"]

    def __setevent(name):
        def set_event(self, event):
            self.events[name] = event
        return set_event

    SetSelectEmptySlotEvent = __setevent("select_empty")
    SetSelectItemSlotEvent = __setevent("select_item")
    SetUnselectEmptySlotEvent = __setevent("unselect_empty")
    SetUnselectItemSlotEvent = __setevent("unselect_item")
    SetOverInItemEvent = __setevent("over_in")
    SetOverOutItemEvent = __setevent("over_out")
    SetUseSlotEvent = __setevent("use")
    del __setevent


def make_legacy_ui(log, focus=None):
    """nui_test_support's legacy ui, extended for the HUD classes; `focus`
    is wndMgr's focus (FocusModel) its windows take and give up."""
    ui = support.make_legacy_ui()
    ui.focus = focus
    Window = ui.Window

    class HudWindow(Window):
        def __init__(self, layer="UI"):
            Window.__init__(self, layer)
            self.size = (0, 0)
            self.position = (0, 0)
            self.name = ""
            if focus is not None:
                focus.register(self)

        # wndMgr's focus (Game.focus), as ui.Window reaches it.
        def SetFocus(self):
            if focus is not None:
                focus.activate(self)

        def KillFocus(self):
            if focus is not None:
                focus.kill(self)

        def IsFocus(self):
            return focus is not None and focus.is_focus(self)

        def Destroy(self):
            if focus is not None:
                focus.forget(self)

        def SetSize(self, width, height):
            self.size = (width, height)

        def SetPosition(self, x, y):
            self.position = (x, y)

        def GetLocalPosition(self):
            return self.position

        def GetGlobalPosition(self):
            return self.position

        def SetWindowName(self, name):
            self.name = name

        def AddFlag(self, flag):
            pass

        def GetWidth(self):
            return self.size[0]

        def GetHeight(self):
            return self.size[1]

    class ScriptWindow(HudWindow):
        def __init__(self, layer="UI"):
            HudWindow.__init__(self, layer)
            self.ElementDictionary = {}
            self.Children = []
            self.scripts = []

        def ClearDictionary(self):
            self.Children = []
            self.ElementDictionary = {}

        def GetChild(self, name):
            for script in getattr(self, "scripts", ()):
                if name in MISSING_CHILDREN.get(script.lower(), ()):
                    raise KeyError(name)
            if not hasattr(self, "ElementDictionary"):
                self.ElementDictionary = {}
            child = self.ElementDictionary.get(name)
            if child is None:
                child = self.ElementDictionary[name] = (LegacySlots if name.startswith("quick_slot") else LegacyWidget)(name)
            return child

        def GetChild2(self, name):
            return self.GetChild(name)

    class PythonScriptLoader(object):
        loaded = []

        def LoadScriptFile(self, window, path):
            """As the legacy loader: it clears the window's dictionary first
            (a class that skips ScriptWindow.__init__ still gets one)."""
            PythonScriptLoader.loaded.append(path)
            clear = getattr(window, "ClearDictionary", None)
            if clear is not None:
                clear()
            if not hasattr(window, "scripts"):
                window.scripts = []
            window.scripts.append(path)

    class TextLine(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "text")

    class ImageBox(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "image")

    class NumberLine(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "number")

        def SetNumber(self, text):
            self.text = text

    class Button(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "button")
            ui.handles[0] += 1
            self.hWnd = ui.handles[0]
            self.layer = layer

        def __del__(self):
            pass

    class SlotWindow(LegacySlots):
        def __init__(self, layer="UI"):
            LegacySlots.__init__(self, "slots")
            ui.handles[0] += 1
            self.hWnd = ui.handles[0]
            self.size = (0, 0)
            self.position = (0, 0)

        def __del__(self):
            pass

        def SetSize(self, width, height):
            self.size = (width, height)

        def SetPosition(self, x, y):
            self.position = (x, y)

        def GetGlobalPosition(self):
            return self.position

        def GetLocalPosition(self):
            return self.position

        def Destroy(self):
            pass

    ui.HudWindow = HudWindow
    ui.Window = HudWindow
    ui.ScriptWindow = ScriptWindow
    ui.PythonScriptLoader = PythonScriptLoader
    ui.TextLine = TextLine
    ui.ImageBox = ImageBox
    ui.ExpandedImageBox = ImageBox
    ui.AniImageBox = ImageBox
    ui.NumberLine = NumberLine
    ui.Button = Button
    ui.SlotWindow = SlotWindow
    ui.GridSlotWindow = SlotWindow
    ui.Bar = HudWindow
    return ui


# --- tooltips ----------------------------------------------------------------------

class ToolTip(object):
    """A legacy tooltip that records what it was asked to show."""

    def __init__(self, kind):
        self.kind = kind
        self.shown = []     # every Set* call, in order
        self.visible = False

    def __getattr__(self, name):
        if name.startswith("__") or not name.startswith("Set"):
            raise AttributeError(name)

        def show(*args):
            self.shown.append((name,) + args)
            self.visible = True
        return show

    def HideToolTip(self):
        self.visible = False

    def ShowToolTip(self):
        self.visible = True

    def Hide(self):
        self.visible = False


def make_tooltips():
    module = types.ModuleType("uiToolTip")
    module.ItemToolTip = lambda *args: ToolTip("item")
    module.SkillToolTip = lambda *args: ToolTip("skill")
    module.HyperlinkItemToolTip = lambda *args: ToolTip("hyperlink")
    module.ToolTip = lambda *args: ToolTip("plain")
    module.TOOLTIP_TYPE = ToolTip
    return module


# --- wndMgr's focus (Wave 2b) ---------------------------------------------------------------

class FocusModel(object):
    """wndMgr's focus as CWindowManager keeps it (PythonWindowManager.cpp
    ActivateWindow, DeactivateWindow, NotifyDestroyWindow): the active window
    and the windows that had the focus before, newest last."""

    def __init__(self):
        self.active = None
        self.stack = []
        self.windows = weakref.WeakValueDictionary()  # handle -> window

    def register(self, window):
        handle = getattr(window, "hWnd", None)
        if handle:
            self.windows[handle] = window

    @staticmethod
    def _notify(window, name):
        hook = getattr(window, name, None)
        if callable(hook):
            hook()

    def activate(self, window):
        """ActivateWindow: the window that had the focus is pushed and gets
        OnKillFocus; this one gets OnSetFocus."""
        if window in self.stack:
            self.stack.remove(window)
        if window is self.active:
            return
        previous = self.active
        if previous is not None:
            self.stack.append(previous)
        self.active = window
        if previous is not None:
            self._notify(previous, "OnKillFocus")
        self._notify(window, "OnSetFocus")

    def deactivate(self):
        """DeactivateWindow: the window pushed last gets the focus back."""
        previous = self.active
        if previous is None:
            return
        self.active = self.stack.pop() if self.stack else None
        self._notify(previous, "OnKillFocus")
        if self.active is not None:
            self._notify(self.active, "OnSetFocus")

    def kill(self, window):
        """wndMgr.KillFocus: only the window that has the focus gives it up."""
        if window is self.active:
            self.deactivate()

    def is_focus(self, window):
        return window is not None and window is self.active

    def forget(self, window):
        """NotifyDestroyWindow: a destroyed window leaves without a call."""
        if window is self.active:
            self.active = None
        while window in self.stack:
            self.stack.remove(window)

    def window(self, handle):
        return self.windows.get(handle)


# --- the chat store (Wave 2b) -------------------------------------------------------------------

CHAT_CONSTANTS = {
    "CHAT_TYPE_TALKING": 0, "CHAT_TYPE_INFO": 1, "CHAT_TYPE_NOTICE": 2, "CHAT_TYPE_PARTY": 3, "CHAT_TYPE_GUILD": 4,
    "CHAT_TYPE_COMMAND": 5, "CHAT_TYPE_SHOUT": 6, "CHAT_TYPE_WHISPER": 7,
    "WHISPER_TYPE_CHAT": 0, "WHISPER_TYPE_SYSTEM": 255, "WHISPER_TYPE_GM": 5,
    "BOARD_STATE_VIEW": 0, "BOARD_STATE_EDIT": 1, "BOARD_STATE_LOG": 2,
    "CHAT_SET_CHAT_WINDOW": 0, "CHAT_SET_LOG_WINDOW": 1,
}
CHAT_TYPE_COUNT = 9      # CHAT_TYPE_MAX_NUM (Packet.h): TALKING to BIG_NOTICE
CHAT_LINE_MAX = 300      # CPythonChat::CHAT_LINE_MAX_NUM


class ChatStore(object):
    """CPythonChat's state as the chat module shows it."""

    def __init__(self):
        self.lines = []          # [serial, type, text], oldest first
        self.serial = 0
        self.sets = {}           # id -> {"board", "end", "modes", "height", "step"}
        self.waiting = []        # (due time, type, text) of AppendChatWithDelay
        self.colors = {}

    def append(self, chat_type, text):
        self.serial += 1
        self.lines.append([self.serial, chat_type, text])
        if len(self.lines) > CHAT_LINE_MAX:
            self.lines.pop(0)

    def create(self, set_id):
        # std::map::insert keeps a set made before.
        self.sets.setdefault(set_id, {"board": 0, "end": 1.0, "modes": [1] * CHAT_TYPE_COUNT, "height": 0, "step": 15})
        return set_id

    def shows(self, set_id, chat_type):
        modes = self.sets[set_id]["modes"]
        return 0 <= chat_type < len(modes) and bool(modes[chat_type])

    def filtered(self, set_id):
        if set_id not in self.sets:
            return []
        return [line for line in self.lines if self.shows(set_id, line[1])]

    def view(self, set_id, rows):
        """P10 spec 2.3.2: the published window of lines and its end index."""
        lines = self.filtered(set_id)
        total = len(lines)
        if total == 0:
            return [], -1, total
        state = self.sets[set_id]
        if state["board"] == CHAT_CONSTANTS["BOARD_STATE_VIEW"]:
            return lines[-5:], total - 1, total
        r = min(max(rows, 1), 64)
        end = total - 1 if total <= r else min(total - 1, r + int((total - r - 1) * state["end"]))
        return lines[max(0, end - r + 1):end + 1], end, total


def link_from_hyperlink(link, names):
    """chat.GetLinkFromHyperlink (PythonChatModule.cpp:420-483): an item link
    of at least six fields of a known item, rewritten in hex, with the attribute
    pairs it carries, wrapped in the client's color and link tags; "" else."""
    fields = (link or "").split(":")
    if ":" not in (link or "") or fields[0] != "item" or len(fields) < 6:
        return ""

    def hexi(text):
        try:
            return int(text, 16)
        except ValueError:
            return -1
    vnum = hexi(fields[1])
    if vnum not in names:
        return ""
    body = "item:%x:%x:%x:%x:%x" % tuple(hexi(field) & 0xFFFFFFFF for field in fields[1:6])
    attributes = False
    if len(fields) >= 8:
        for i in range(6, len(fields) - 1, 2):
            body += ":%x:%d" % (hexi(fields[i]) & 0xFFFFFFFF, int(fields[i + 1] or 0))
            attributes = True
    color = "ffffc700" if attributes else "fff1e6c0"
    return "|c%s|H%s|h[%s]|h|r" % (color, body, names[vnum])


def define(module, name, fn):
    """A function of a Recording module that records its call; a scripted
    answer (Game.answer) wins over `fn`."""
    log = module.__dict__["_log"]
    answers = module.__dict__["_answers"]
    full = module.__name__ + "." + name

    def call(*args, **kwargs):
        log.append((full, args))
        if name in answers:
            answer = answers[name]
            return answer(*args) if callable(answer) else answer
        return fn(*args, **kwargs)
    call.__name__ = name
    setattr(module, name, call)


# --- the legacy widgets of the Wave 2b windows --------------------------------------------------

def install_wave2b_ui(game):
    """Adds to game's ui module the legacy widgets the Wave 2b legacy windows
    make (uichat.py, uiminimap.py, uiplayergauge.py, uiprivateshopbuilder.py,
    uiguild.py): windows that record what they are not asked to keep, an
    edit line that keeps its text, events and focus, a scroll bar whose
    SetPos sends its scroll event unless locked (as ui.ScrollBar.OnMove),
    radio and toggle buttons, and buttons that keep their events. Each
    widget's test helpers are lower case (type, click, drag_to)."""
    ui = game.modules["ui"]
    base = ui.HudWindow

    class Win(base):
        """A legacy window: what HudWindow keeps; every other capitalized
        call does nothing."""

        def __init__(self, layer="UI"):
            base.__init__(self, layer)
            self.shown = False
            self.parent = None
            self.flags = set()

        def __getattr__(self, attr):
            if attr.startswith("__") or not attr[:1].isupper():
                raise AttributeError(attr)
            return lambda *args, **kwargs: None

        def __del__(self):
            pass

        def SetParent(self, parent):
            self.parent = parent

        def AddFlag(self, flag):
            self.flags.add(flag)

        def GetRect(self):
            x, y = self.GetGlobalPosition()
            return (x, y, self.size[0], self.size[1])

        def IsIn(self):
            return False

        def IsRTL(self):
            return False

    class EditLine(Win):
        """ui.EditLine: the text, its limits and events; typing goes through
        type(), as the IME's update would."""

        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.text = ""
            self.max = 0
            self.userMax = 0
            self.eventReturn = lambda *args: None
            self.eventEscape = lambda *args: None
            self.eventTab = None

        def SetText(self, text):
            self.text = text

        def GetText(self):
            return self.text

        def SetMax(self, value):
            self.max = value

        def SetUserMax(self, value):
            self.userMax = value

        def SetReturnEvent(self, event):
            self.eventReturn = event

        def SetEscapeEvent(self, event):
            self.eventEscape = event

        def SetTabEvent(self, event):
            self.eventTab = event

        def OnIMEUpdate(self):
            pass

        def OnIMEKeyDown(self, key):
            return False

        def OnSetFocus(self):
            pass

        def OnKillFocus(self):
            pass

        def type(self, text):
            self.text += text
            self.OnIMEUpdate()

    class Button(LegacyWidget):
        """ui.Button that keeps its event (SetEvent, SAFE_SetEvent)."""

        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "button")
            ui.handles[0] += 1
            self.hWnd = ui.handles[0]

        def __del__(self):
            pass

        def SAFE_SetEvent(self, event, *args):
            self.event = event
            self.eventArgs = args

        def click(self):
            if self.event:
                self.event(*self.eventArgs)

    class RadioButton(Button):
        def __init__(self, layer="UI"):
            Button.__init__(self, layer)
            self.down = False

        def Down(self):
            self.down = True

        def SetUp(self):
            self.down = False

        def click(self):
            self.down = True
            Button.click(self)

    class ToggleButton(Button):
        """ui.ToggleButton: a click flips it and calls its down or up event."""

        def __init__(self, layer="UI"):
            Button.__init__(self, layer)
            self.down = False
            self.eventUp = None
            self.eventDown = None

        def SetToggleUpEvent(self, event, *args):
            self.eventUp = (event, args)

        def SetToggleDownEvent(self, event, *args):
            self.eventDown = (event, args)

        def Down(self):
            self.down = True

        def SetUp(self):
            self.down = False

        def click(self):
            self.down = not self.down
            event = self.eventDown if self.down else self.eventUp
            if event and event[0]:
                event[0](*event[1])

    class DragButton(Win):
        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.moveEvent = None

        def SetMoveEvent(self, event):
            self.moveEvent = event

        def drag_to(self, x, y):
            self.SetPosition(x, y)
            if self.moveEvent:
                self.moveEvent()

    class ScrollBar(Win):
        """ui.ScrollBar: SetPos sends the scroll event unless locked, at the
        position its pixel grid leaves (ui.py ScrollBar.SetPos, OnMove)."""

        BUTTON_HEIGHT = 17
        MIDDLE_HEIGHT = 9
        EXTRA = 7           # MIDDLE_BAR_UPPER_PLACE + MIDDLE_BAR_DOWNER_PLACE

        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.eventScroll = lambda *args: None
            self.curPos = 0.0
            self.pageSize = 1
            self.lockFlag = False

        def SetScrollEvent(self, event):
            self.eventScroll = event

        def SetScrollBarSize(self, height):
            self.pageSize = height - self.BUTTON_HEIGHT * 2 - self.MIDDLE_HEIGHT - self.EXTRA
            self.SetSize(13, height)

        def GetPos(self):
            return self.curPos

        def SetPos(self, pos):
            pos = min(max(0.0, pos), 1.0)
            if self.lockFlag or self.pageSize == 0:
                return
            self.curPos = int(float(self.pageSize) * pos) / float(self.pageSize)
            self.eventScroll()

        def LockScroll(self):
            self.lockFlag = True

        def UnlockScroll(self):
            self.lockFlag = False

        def drag_to(self, pos):
            self.SetPos(pos)

    class SmallThinScrollBar(ScrollBar):
        BUTTON_HEIGHT = 13
        MIDDLE_HEIGHT = 18
        EXTRA = 0

    class Gauge(Win):
        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.percentage = None

        def SetPercentage(self, current, maximum):
            self.percentage = (current, maximum)

    class MarkBox(Win):
        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.index = None

        def SetIndex(self, index):
            self.index = index

    for name, cls in (("Window", Win), ("EditLine", EditLine), ("Button", Button), ("RadioButton", RadioButton),
                      ("ToggleButton", ToggleButton), ("DragButton", DragButton), ("ScrollBar", ScrollBar),
                      ("ThinScrollBar", ScrollBar), ("SmallThinScrollBar", SmallThinScrollBar), ("ThinBoard", Win),
                      ("Bar", Win), ("Gauge", Gauge), ("MarkBox", MarkBox)):
        setattr(ui, name, cls)
    ui.ExpandedImageBox = ui.ImageBox
    ui.RenderRoundBox = lambda *args: None
    return ui


# --- the game --------------------------------------------------------------------------

class Game(object):
    """One stand-in client: its state, its modules, and the root modules
    loaded over them. `with game:` puts the modules into sys.modules (the
    legacy code imports some inside its functions); load() does it too."""

    def __init__(self, nui_on=True, engine=True):
        self.log = []
        self.attaches = []       # ("attach", type, slot, index, count) and ("detach", type)
        self.created = []        # icon instances made: (kind, handle)
        self.deleted = []        # icon instances freed: (kind, handle)
        self.time = 100.0        # app.GetTime(), seconds
        self.global_time = 100000  # app.GetGlobalTime(), milliseconds
        self.timestamp = 1700000000  # app.GetGlobalTimeStamp()
        self.files = {}          # path -> text, the files the legacy code reads and writes
        self.dragging = True     # wndMgr.IsDragging()
        self.status = {}         # player.GetStatus
        self.items = {}          # inventory position (or (window, position)) -> {"vnum", "count", "sockets"}
        self.item_sizes = {}     # vnum -> (w, h)
        self.quick_items = set()  # vnums item.CanAddToQuickSlotItem accepts (default: all but those in no_quick)
        self.no_quick = set()
        self.skills = {}         # skill slot -> {"index", "grade", "level", "cool", "active"}
        self.skill_types = {}    # skill index -> skill type
        self.toggle_skills = set()
        self.standing_skills = set()
        self.guild_levels = {}   # skill slot -> guild skill level
        self.quick = {}          # global quick slot -> (type, position)
        self.page = 0
        self.play_time = 1
        self.observer = False
        self.emotion_icons = {}  # emotion index -> icon path
        self.handles = [1000]
        # Wave 2b
        self.chat = ChatStore()
        self.focus = FocusModel()
        self.item_names = {}     # vnum -> name, for chat.GetLinkFromHyperlink
        self.chat_rows = {"window": 8, "log": 3}  # the rows the lines elements report
        self.view_chat = True    # systemSetting.IsViewChat
        self.show_sales_text = True  # systemSetting.IsShowSalesText
        self.pressed = set()     # app.IsPressed: the DIK codes held down
        self.hyperlink = ""      # ui.GetHyperlink: the link under the mouse
        self.legacy_pasted = []  # what ime.PasteString gave the legacy edit line
        self.state = support.NuiState()
        self.state.available = nui_on
        self.engine = engine
        self.dbg = support.make_dbg()
        self.modules = self._modules()
        self._saved = {}
        self.loaded = {}

    # --- state helpers --------------------------------------------------------------

    def give(self, position, vnum, count=1, sockets=(0, 0, 0), size=(1, 1)):
        self.items[position] = {"vnum": vnum, "count": count, "sockets": list(sockets)}
        self.item_sizes[vnum] = size

    def learn(self, slot, index, grade=0, level=1, skill_type=1, cool=None, active=False):
        self.skills[slot] = {"index": index, "grade": grade, "level": level, "cool": cool, "active": active}
        self.skill_types[index] = skill_type

    def put_quick(self, local, slot_type, position, page=None):
        self.quick[(self.page if page is None else page) * 8 + local] = (slot_type, position)

    def answer(self, module, name, value):
        self.modules[module].__dict__["_answers"][name] = value

    def effects(self, modules=COMPARED):
        """The recorded calls with an effect, in order: the getters left out,
        only the modules named."""
        return [(name, args) for name, args in self.log
                if name.split(".", 1)[0] in modules and not is_getter(name)]

    def calls(self, prefix):
        return [(name, args) for name, args in self.log if name.startswith(prefix)]

    def _handle(self, kind):
        self.handles[0] += 1
        self.created.append((kind, self.handles[0]))
        return self.handles[0]

    # --- modules ------------------------------------------------------------------------

    def _item_at(self, *at):
        key = at[0] if len(at) == 1 else tuple(at)
        return self.items.get(key, {"vnum": 0, "count": 0, "sockets": [0, 0, 0]})

    def _modules(self):
        log = self.log
        game = self
        modules = {}

        player = Recording("player", log, **PLAYER_CONSTANTS)
        define = lambda name, fn: setattr(player, name, recorded(log, "player." + name, fn))
        define("GetStatus", lambda kind: game.status.get(kind, 0))
        define("GetItemIndex", lambda *at: game._item_at(*at)["vnum"])
        define("GetItemCount", lambda *at: game._item_at(*at)["count"])
        define("GetItemMetinSocket", lambda *at: (game._item_at(*at[:-1])["sockets"] + [0, 0, 0])[at[-1]])
        define("GetSkillIndex", lambda slot: game.skills.get(slot, {}).get("index", 0))
        define("GetSkillGrade", lambda slot: game.skills.get(slot, {}).get("grade", 0))
        define("GetSkillLevel", lambda slot: game.skills.get(slot, {}).get("level", 0))
        define("IsSkillCoolTime", lambda slot: game.skills.get(slot, {}).get("cool") is not None)
        define("GetSkillCoolTime", lambda slot: game.skills.get(slot, {}).get("cool") or (0.0, 0.0))
        define("IsSkillActive", lambda slot: bool(game.skills.get(slot, {}).get("active")))
        define("GetQuickPage", lambda: game.page)
        define("GetLocalQuickSlot", lambda local: game.quick.get(game.page * 8 + local, (0, 0)))
        define("GetGlobalQuickSlot", lambda index: game.quick.get(index, (0, 0)))
        define("LocalQuickSlotIndexToGlobalQuickSlotIndex", lambda local: game.page * 8 + local)
        define("GetPlayTime", lambda: game.play_time)
        define("IsObserverMode", lambda: game.observer)
        define("GetEmotionIconFileName", lambda index: game.emotion_icons.get(index, ""))
        define("GetEmotionIconImage", lambda index: "emotion-image-%d" % index)

        def set_page(page):
            game.page = page + 4 if page < 0 else page % 4
        define("SetQuickPage", set_page)

        def set_play_time(value):
            game.play_time = value
        define("SetPlayTime", set_play_time)
        modules["player"] = player

        item = Recording("item", log)
        item.selected = [0]

        def select(vnum):
            item.selected[0] = vnum
        item.SelectItem = recorded(log, "item.SelectItem", select)
        item.GetIconImageFileName = recorded(log, "item.GetIconImageFileName",
            lambda: "icon/item/%05d.tga" % item.selected[0])
        item.GetItemSize = recorded(log, "item.GetItemSize", lambda: game.item_sizes.get(item.selected[0], (1, 1)))
        item.GetItemName = recorded(log, "item.GetItemName", lambda: "item %d" % item.selected[0])
        item.GetIconInstance = recorded(log, "item.GetIconInstance", lambda: game._handle("item"))
        item.DeleteIconInstance = recorded(log, "item.DeleteIconInstance", lambda handle: game.deleted.append(("item", handle)))
        item.CanAddToQuickSlotItem = recorded(log, "item.CanAddToQuickSlotItem",
            lambda vnum: vnum not in game.no_quick)
        modules["item"] = item

        skill = Recording("skill", log, **SKILL_CONSTANTS)
        skill.GetSkillType = recorded(log, "skill.GetSkillType", lambda index: game.skill_types.get(index, 1))
        skill.GetIconImageFileNameNew = recorded(log, "skill.GetIconImageFileNameNew",
            lambda index, grade: "d:/ymir work/ui/skill/test/%d_%02d.sub" % (index, min(max(grade, 0), 3) + 1) if index else "")
        skill.GetIconInstanceNew = recorded(log, "skill.GetIconInstanceNew", lambda index, grade: game._handle("skill"))
        skill.DeleteIconInstance = recorded(log, "skill.DeleteIconInstance", lambda handle: game.deleted.append(("skill", handle)))
        skill.IsToggleSkill = recorded(log, "skill.IsToggleSkill", lambda index: index in game.toggle_skills)
        skill.IsStandingSkill = recorded(log, "skill.IsStandingSkill", lambda index: index in game.standing_skills)
        modules["skill"] = skill

        guild = Recording("guild", log)
        guild.GetSkillLevel = recorded(log, "guild.GetSkillLevel", lambda slot: game.guild_levels.get(slot, 0))
        modules["guild"] = guild

        grp_image = Recording("grpImage", log)
        grp_image.Generate = lambda path: 1  # cursor images, not counted
        grp_image.GenerateFromHandle = recorded(log, "grpImage.GenerateFromHandle", lambda image: game._handle("emotion"))
        grp_image.Delete = recorded(log, "grpImage.Delete", lambda handle: game.deleted.append(("emotion", handle)))
        grp_image.GetWidth = lambda handle: 32
        grp_image.GetHeight = lambda handle: 32
        grp_image.SetDiffuseColor = lambda *args: None
        grp_image.SetPosition = lambda *args: None
        grp_image.Render = lambda *args: None
        modules["grpImage"] = grp_image

        app = Recording("app", log, **APP_CONSTANTS)
        app.GetTime = lambda: game.time
        app.GetGlobalTime = lambda: game.global_time
        app.GetGlobalTimeStamp = lambda: game.timestamp
        app.IsExistFile = lambda path: True
        app.IsRTL = lambda: False
        app.SetCursor = lambda *args: None
        app.IsShowCursor = lambda: True
        app.IsLiarCursorOn = lambda: False
        modules["app"] = app

        wndmgr = support.make_wndmgr()
        for key, value in WNDMGR_CONSTANTS.items():
            setattr(wndmgr, key, value)
        wndmgr.SetFocus = lambda handle: game.focus.window(handle) is not None and game.focus.activate(game.focus.window(handle))
        wndmgr.KillFocus = lambda handle=None: (game.focus.deactivate() if handle is None else
                                                game.focus.kill(game.focus.window(handle)))
        wndmgr.IsFocus = lambda handle: game.focus.is_focus(game.focus.window(handle))
        wndmgr.IsDragging = lambda: game.dragging
        wndmgr.AttachIcon = recorded(log, "wndMgr.AttachIcon", lambda *args: None)
        wndmgr.SetAttachingFlag = lambda flag: None
        wndmgr.IsAttaching = lambda: bool(game.modules["mouseModule"].mouseController.isAttached())
        for name in ("SetSlotBaseImage", "AppendSlot", "SetCoverButton", "SetSlotStyle", "Register", "Destroy",
                     "Show", "Hide", "SetTop", "SetWindowSize", "SetWindowPosition", "IsShow", "SetParent"):
            if not hasattr(wndmgr, name):
                setattr(wndmgr, name, lambda *args: 0)
        modules["wndMgr"] = wndmgr

        for name in ("net", "chr", "chrmgr", "nonplayer", "messenger", "textTail", "snd", "grp", "grpText",
                     "systemSetting", "background", "quest", "event", "chat", "ime", "exception", "miniMap", "shop"):
            modules[name] = Recording(name, log)
        modules["systemSetting"].IsSoftwareCursor = lambda: False
        modules["systemSetting"].GetUINuiWindows = lambda: "+hud"
        modules["systemSetting"].IsUINuiLogin = lambda: 0
        nuigame = Recording("nuigame", log)
        modules["nuigame"] = nuigame if self.engine else None
        self._wave2b_modules(modules)

        modules["localeInfo"] = support.LocaleInfo(
            TOOLTIP_ENERGY=lambda value: "Energy %s" % (value,),
            RegisterReloadCallback=lambda fn: None)
        modules["uiScriptLocale"] = support.LocaleInfo(LOCALE_UISCRIPT_PATH="locale/en/ui/")
        modules["uiToolTip"] = make_tooltips()
        modules["dbg"] = self.dbg
        modules["ui"] = make_legacy_ui(log, self.focus)
        modules["ui"].GetHyperlink = lambda: game.hyperlink
        modules["localeInfo"].MINIMAP_ZONE_NAME_DICT = {}
        modules["uiScriptLocale"].ZONE_MAP = "ZONE_MAP"
        nui = support.make_nui(self.state)
        if self.engine:
            nui._nui.BindFeed = lambda *args: True
        modules["nui"] = nui
        return modules

    def _wave2b_modules(self, modules):
        """The Wave 2b stand-ins (the module docstring lists them)."""
        game = self
        store = self.chat

        chat = modules["chat"]
        for name, value in CHAT_CONSTANTS.items():
            setattr(chat, name, value)

        def set_state(key):
            def apply(set_id, value):
                if set_id in store.sets:
                    store.sets[set_id][key] = value
            return apply

        def set_mode(value):
            def apply(set_id, mode):
                if set_id in store.sets and 0 <= mode < CHAT_TYPE_COUNT:
                    modes = store.sets[set_id]["modes"]
                    modes[mode] = (1 - modes[mode]) if value is None else value
            return apply

        def set_end(set_id, pos):
            if set_id in store.sets:
                store.sets[set_id]["end"] = min(max(float(pos), 0.0), 1.0)

        def visible(set_id):
            if set_id not in store.sets:
                return 0
            state = store.sets[set_id]
            return min(len(store.filtered(set_id)), (state["height"] + state["step"]) // state["step"])

        def delay(chat_type, text, ms):
            store.waiting.append((game.time + ms / 1000.0, chat_type, text))

        def update(set_id):
            due = [entry for entry in store.waiting if entry[0] <= game.time]
            store.waiting = [entry for entry in store.waiting if entry[0] > game.time]
            for _, chat_type, text in due:
                store.append(chat_type, text)

        def clear():
            store.lines = []

        define(chat, "SetChatColor", lambda chat_type, r, g, b: store.colors.__setitem__(chat_type, (r, g, b)))
        define(chat, "CreateChatSet", store.create)
        define(chat, "SetBoardState", set_state("board"))
        define(chat, "SetHeight", set_state("height"))
        define(chat, "SetStep", set_state("step"))
        define(chat, "EnableChatMode", set_mode(1))
        define(chat, "DisableChatMode", set_mode(0))
        define(chat, "ToggleChatMode", set_mode(None))
        define(chat, "SetEndPos", set_end)
        define(chat, "GetLineCount", lambda set_id: len(store.filtered(set_id)))
        define(chat, "GetVisibleLineCount", visible)
        define(chat, "GetLineStep", lambda set_id: store.sets.get(set_id, {}).get("step", 0))
        define(chat, "AppendChat", store.append)
        define(chat, "AppendChatWithDelay", delay)
        define(chat, "Update", update)
        define(chat, "Clear", clear)
        define(chat, "GetLinkFromHyperlink", lambda link: link_from_hyperlink(link, game.item_names))

        net = modules["net"]
        define(net, "IsChatInsultIn", lambda text: False)
        define(net, "GetServerInfo", lambda: "")

        def paste(text):
            """The client's paste bridge (P10 spec D7): a NovaUI text field with
            the focus takes the text at its caret, else the legacy IME."""
            for window in game.state.windows:
                if window._doc and window.visible and (window.DOCUMENT, window.focused) in game.state.text_fields:
                    window.insert_text(window.focused, text)
                    return
            game.legacy_pasted.append(text)
            active = game.focus.active
            if active is not None and hasattr(active, "type"):
                active.type(text)
        define(modules["ime"], "PasteString", paste)

        setting = modules["systemSetting"]
        setting.IsViewChat = lambda: game.view_chat
        setting.IsShowSalesText = lambda: game.show_sales_text

        mini_map = modules["miniMap"]
        for name, value in MINIMAP_CONSTANTS.items():
            setattr(mini_map, name, value)
        mini_map.__dict__["_answers"].update(MINIMAP_ANSWERS)

        define(modules["chr"], "GetProjectPosition", lambda vid, height: (-100, -100))
        define(modules["textTail"], "GetPosition", lambda vid: (0, 0, 0))
        define(modules["textTail"], "IsChat", lambda vid: False)
        guild = modules["guild"]
        define(guild, "GuildIDToMarkID", lambda guild_id: -1)
        define(guild, "GetMarkImageFilenameByMarkID", lambda mark_id: "")
        define(guild, "GetMarkIndexByMarkID", lambda mark_id: 0)
        define(guild, "GetGuildName", lambda guild_id: "guild %d" % guild_id)  # a str, as PythonGuild.cpp answers

        app = modules["app"]
        app.IsPressed = lambda key: key in game.pressed

        nuigame = modules["nuigame"]
        if nuigame is None:
            return
        attached = [False]

        def chat_state(view):
            if view not in ("window", "log"):
                raise ValueError("nuigame.ChatState: no view %r" % (view,))
            set_id = 0 if view == "window" else 1
            rows = game.chat_rows.get(view, 8)
            if set_id not in store.sets:
                return {"attached": attached[0], "rows": rows, "total": 0, "end": -1, "at_end": True,
                        "board_state": 0, "end_pos": 1.0, "mask": 0}
            state = store.sets[set_id]
            _, end, total = store.view(set_id, rows)
            mask = sum(1 << t for t in range(CHAT_TYPE_COUNT) if store.shows(set_id, t))
            return {"attached": attached[0], "rows": rows, "total": total, "end": end, "at_end": end == total - 1,
                    "board_state": state["board"], "end_pos": state["end"], "mask": mask}

        define(nuigame, "ChatAttach", lambda: attached.__setitem__(0, True))
        define(nuigame, "ChatDetach", lambda: attached.__setitem__(0, False))
        define(nuigame, "ChatState", chat_state)
        define(nuigame, "ViewState", lambda name: {"wanted": False, "renders": 0, "draws": 0, "texels": [0, 0], "natural": [0, 0], "hover": ""})
        define(nuigame, "SetViewHoverFormat", lambda name, format, names=None: True)
        define(nuigame, "AnchorState", lambda: {"source": False, "anchors": 0})
        self.chat_attached = attached

    # --- sys.modules ----------------------------------------------------------------

    def __enter__(self):
        for name, module in self.modules.items():
            self._saved.setdefault(name, sys.modules.get(name, support.MISSING))
            sys.modules[name] = module
        return self

    def __exit__(self, *exc):
        for name, value in self._saved.items():
            if value is support.MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        self._saved = {}
        return False

    def put(self, name, module):
        self.modules[name] = module
        if self._saved:
            self._saved.setdefault(name, sys.modules.get(name, support.MISSING))
            sys.modules[name] = module

    def load(self, name, file_name=None):
        """Imports assets/root/<file_name> as `name` over the stand-ins (and
        keeps it in self.modules, so later loads import it)."""
        with self:
            path = os.path.join(ROOT, file_name or (name.lower() + ".py"))
            sys.modules.pop(name, None)
            with contextlib.redirect_stdout(io.StringIO()):
                module = support.load_module(name, path)
        self.modules[name] = module
        self.loaded[name] = module
        if name == "mouseModule":
            self._record_controller(module)
        if name in ("uiTaskBar", "nui_taskbar"):
            module.open = self._open
        return module

    def load_standard(self):
        """constInfo, mouseModule and the shared NovaUI modules, in that order."""
        self.load("constInfo", "constinfo.py")
        self.load("mouseModule", "mousemodule.py")
        self.load("nui_windows", "nui_windows.py")
        self.load("nui_slots", "nui_slots.py")
        self.load("nui_hud", "nui_hud.py")
        return self

    def _record_controller(self, module):
        game = self
        base = module.CMouseController

        class RecordingController(base):
            def AttachObject(self, owner, slot_type, slot_number, item_index, count=0):
                game.attaches.append(("attach", slot_type, slot_number, item_index, count))
                game.log.append(("mouse.AttachObject", (slot_type, slot_number, item_index, count)))
                return base.AttachObject(self, owner, slot_type, slot_number, item_index, count)

            def DeattachObject(self):
                if getattr(self, "AttachedFlag", False):
                    game.attaches.append(("detach", self.AttachedType))
                    game.log.append(("mouse.DeattachObject", ()))
                return base.DeattachObject(self)

        with self:
            controller = RecordingController()
            controller.Create()
        module.mouseController = controller

    def _open(self, path, mode="r"):
        """The legacy code's config files (config/mouse.cfg), in memory."""
        game = self

        class File(io.StringIO):
            def __exit__(self, *exc):
                if "w" in mode:
                    game.files[path] = self.getvalue()
                return io.StringIO.__exit__(self, *exc)

            def close(self):
                if "w" in mode:
                    game.files[path] = self.getvalue()
                io.StringIO.close(self)

        if "r" in mode and path not in self.files:
            raise IOError("stand-in: no %s" % path)
        return File(self.files.get(path, "") if "r" in mode else "")
