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
- `nuigame.NuiStats` (Wave 3a, P11 spec 3.1): the loaded documents from
  the nui stand-in, their elements from Game.element_counts; a Game made
  with engine_3a=False has none (Recording.lack), as a Wave 2b exe;
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
    # Wave 3a: PythonPlayerModule.cpp:2551-2564 (Packet.h's EPKModes and block bits).
    "PK_MODE_PEACE": 0, "PK_MODE_REVENGE": 1, "PK_MODE_FREE": 2, "PK_MODE_PROTECT": 3, "PK_MODE_GUILD": 4,
    "PK_MODE_MAX_NUM": 5,
    "BLOCK_EXCHANGE": 1, "BLOCK_PARTY": 2, "BLOCK_GUILD": 4, "BLOCK_WHISPER": 8, "BLOCK_FRIEND": 16,
    "BLOCK_PARTY_REQUEST": 32,
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
# Wave 3a: the help closes on H (uihelp.py OnKeyDown).
APP_CONSTANTS.update({"DIK_H": 0x23})
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
    callable answer is called with the arguments). A name in `_missing`
    (Recording.lack) does not exist, as in an older exe."""

    def __init__(self, name, log, **members):
        types.ModuleType.__init__(self, name)
        self.__dict__["_log"] = log
        self.__dict__["_answers"] = {}
        self.__dict__["_missing"] = set()
        for key, value in members.items():
            setattr(self, key, value)

    def lack(self, *names):
        """The module has none of these names from now on."""
        for name in names:
            self.__dict__.pop(name, None)
            self.__dict__["_missing"].add(name)

    def __getattr__(self, attr):
        if attr.startswith("__") or attr in self.__dict__["_missing"]:
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

    def SetTop(self):
        """A raise, not a request to show (the inventory's OnTop)."""

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
            # CRadioButton::OnMouseLeftButtonDown: a press on the button that
            # is down calls nothing.
            if self.down:
                return
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


# --- the legacy widgets of the Wave 3a windows ----------------------------------------------------

UISCRIPT_ROOT = os.path.normpath(os.path.join(support.HERE, "..", "assets", "uiscript"))


def read_uiscript(path, screen=(1600, 900)):
    """The window dict of a legacy uiscript file, as ui.PythonScriptLoader
    reads it: the file executed with SCREEN_WIDTH and SCREEN_HEIGHT (its own
    imports come from sys.modules, the Game's stand-ins under `with game`).
    `path` is the loader's argument ("uiscript/systemdialog.py",
    "UIScript/HelpWindow.py"); the files are lower case on disk."""
    file_name = os.path.join(UISCRIPT_ROOT, path.replace("\\", "/").lower())
    with open(file_name, encoding="utf-8", errors="replace") as handle:
        source = handle.read()
    namespace = {"SCREEN_WIDTH": screen[0], "SCREEN_HEIGHT": screen[1], "__name__": "uiscript"}
    exec(compile(source, file_name, "exec"), namespace)
    return namespace["window"]


def install_wave3a_ui(game):
    """Adds to game's ui module (after install_wave2b_ui) what the Wave 3a
    legacy windows use (uisystem.py, uisystemoption.py, uiselectmusic.py,
    uigameoption.py, uirestart.py, uihelp.py, uipointreset.py): a
    PythonScriptLoader that reads the real uiscript file and makes each
    named child of its type, so a test presses legacy's buttons as a player
    does (`click()`); a SliderBar whose drag_to(fraction) lands on the
    cursor's pixel, as legacy's DragButton does (curPos = pixel / 122); a
    TitleBar and board that keep their close event (`close()`); ListBoxEx
    with its Item base. Screen 1600 x 900."""
    ui = game.modules["ui"]
    Win = ui.Window
    Button, RadioButton, ToggleButton = ui.Button, ui.RadioButton, ui.ToggleButton

    class TextLine(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "text")
            self.extraLines = []
            self.color = None

        def SetFontColor(self, r, g, b):
            self.calls.append(("SetFontColor", r, g, b))
            self.color = (r, g, b)

    class SliderBar(Win):
        """ui.SliderBar: a 175 px track and a 53 px cursor (pageSize 122)."""

        PAGE = 122

        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.curPos = 1.0
            self.eventChange = None

        def SetSliderPos(self, pos):
            self.curPos = pos

        def GetSliderPos(self):
            return self.curPos

        def SetEvent(self, event):
            self.eventChange = event

        def drag_to(self, fraction):
            self.curPos = float(int(round(fraction * self.PAGE))) / self.PAGE
            if self.eventChange:
                self.eventChange()

    class TitleBar(Win):
        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.closeEvent = None

        def SetCloseEvent(self, event):
            self.closeEvent = event

        def close(self):
            if self.closeEvent:
                self.closeEvent()

    class Board(TitleBar):
        def SetTitleName(self, name):
            self.title = name

    class ListBoxEx(Win):
        class Item(Win):
            def __init__(self, layer="UI"):
                Win.__init__(self, layer)

            def SetParent(self, parent):
                self.parent = parent

        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.itemList = []
            self.selItem = None
            self.scrollBar = None

        def IsEmpty(self):
            return 0 if self.itemList else 1

        def AppendItem(self, item):
            item.SetParent(self)
            item.SetSize(100, 16)
            self.itemList.append(item)

        def RemoveAllItems(self):
            self.selItem = None
            self.itemList = []

        def GetSelectedItem(self):
            return self.selItem

        def SelectItem(self, item):
            self.selItem = item

        def SetScrollBar(self, scrollBar):
            self.scrollBar = scrollBar

        def select(self, index):
            """A press on row `index` (Item.OnMouseLeftButtonDown)."""
            self.SelectItem(self.itemList[index])

        def texts(self):
            return [item.GetText() for item in self.itemList]

    kinds = {"button": Button, "radio_button": RadioButton, "toggle_button": ToggleButton, "sliderbar": SliderBar,
             "titlebar": TitleBar, "board": Board, "board_with_titlebar": Board, "thinboard": Board, "text": TextLine,
             "scrollbar": ui.ScrollBar}

    def build(window, value):
        for child in value.get("children", ()) or ():
            widget = kinds.get(child.get("type"), Win)()
            widget.name = child.get("name", "")
            if "text" in child:
                widget.SetText(child["text"])
            window.ElementDictionary[widget.name] = widget
            build(window, child)

    class PythonScriptLoader(object):
        loaded = []

        def LoadScriptFile(self, window, path):
            PythonScriptLoader.loaded.append(path)
            clear = getattr(window, "ClearDictionary", None)
            if clear is not None:
                clear()
            if not hasattr(window, "ElementDictionary"):
                window.ElementDictionary = {}
            if not hasattr(window, "scripts"):
                window.scripts = []
            window.scripts.append(path)
            build(window, read_uiscript(path))

    script_base = ui.ScriptWindow

    class ScriptWindow(script_base):
        def GetChild(self, name):
            return self.ElementDictionary[name]

        def __getattr__(self, attr):
            if attr.startswith("__") or not attr[:1].isupper():
                raise AttributeError(attr)
            return lambda *args, **kwargs: None

    ui.ScriptWindow = ScriptWindow
    ui.PythonScriptLoader = PythonScriptLoader
    ui.TextLine = TextLine
    ui.SliderBar = SliderBar
    ui.TitleBar = TitleBar
    ui.Board = Board
    ui.BoardWithTitleBar = Board
    ui.ListBoxEx = ListBoxEx
    return ui


# --- the game --------------------------------------------------------------------------

class Game(object):
    """One stand-in client: its state, its modules, and the root modules
    loaded over them. `with game:` puts the modules into sys.modules (the
    legacy code imports some inside its functions); load() does it too."""

    def __init__(self, nui_on=True, engine=True, engine_3a=True, engine_3b=True):
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
        self.element_counts = {}  # document -> elements, for nuigame.NuiStats (default 1)
        # Wave 3a (P11 spec 5.6): what the option windows read and write.
        self.settings = {"music_volume": 0.5, "sound_volume": 0.75, "fog_level": 1, "always_show_name": True,
                         "show_damage": True, "ui_theme": "", "ui_scale_percent": 0, "ui_reduced_motion": 0}
        self.pk_mode = 0         # player.GetPKMode
        self.guild_id = 0        # player.GetGuildID
        self.software_tiling = False  # background.IsSoftwareTiling
        self.file_lists = {"BGM/*.mp3": ["a_rhapsody_of_war.mp3", "another_way.mp3", "back_to_back.mp3",
                                         "blacksea.mp3", "catacomb_of_devil.mp3", "characterselect.mp3"]}
        self.saved_configs = 0   # systemSetting.SaveConfig calls
        self.state = support.NuiState()
        self.state.available = nui_on
        self.engine = engine
        self.engine_3a = engine and engine_3a
        # Wave 3b (P14 spec 4.9.4): _nui.FollowPointer and the nui-cells decorator.
        self.engine_3b = self.engine_3a and engine_3b
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
        define("GetPKMode", lambda: game.pk_mode)
        define("GetGuildID", lambda: game.guild_id)
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
                     "systemSetting", "background", "quest", "event", "chat", "ime", "exception", "miniMap", "shop",
                     "uiPrivateShopBuilder"):
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
        if self.engine_3b:
            nui._nui.FollowPointer = lambda *args: True
            self.state.decorators.add("nui-cells")
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
        self._wave3a_modules(modules)

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
        if not self.engine_3a:
            nuigame.lack("NuiStats")
            return

        def nui_stats():
            """P11 spec 3.1: every loaded document, whether it shows, and its
            elements (Game.element_counts, 1 by default)."""
            documents = [{"path": window.DOCUMENT, "shown": bool(window.visible),
                          "elements": game.element_counts.get(window.DOCUMENT, 1)}
                         for window in game.state.windows if window._doc]
            return {"documents": documents, "elements": sum(d["elements"] for d in documents),
                    "shown_elements": sum(d["elements"] for d in documents if d["shown"])}
        define(nuigame, "NuiStats", nui_stats)

    def loaded_documents(self):
        """The documents loaded now, as nuigame.NuiStats lists them."""
        return [window.DOCUMENT for window in self.state.windows if window._doc]

    def _wave3a_modules(self, modules):
        """The Wave 3a stand-ins (P11 spec 5.6): systemSetting's getters and
        setters of the option windows over Game.settings (and the view chat
        and sales text flags of Wave 2b), every setter and SaveConfig
        recorded; background.IsSoftwareTiling (Game.software_tiling) and
        EnableSoftwareTiling; app.GetFileList (Game.file_lists) and
        SetCameraMaxDistance. snd, net, chrmgr and uiPrivateShopBuilder are
        plain recording modules; musicInfo comes from load_music_info()."""
        game = self
        settings = self.settings
        setting = modules["systemSetting"]

        def getter(name, key, kind=lambda value: value):
            setattr(setting, name, lambda: kind(settings[key]))

        def setter(name, store):
            define(setting, name, store)

        getter("GetMusicVolume", "music_volume", float)
        getter("GetSoundVolume", "sound_volume", float)
        getter("GetFogLevel", "fog_level", int)
        getter("IsAlwaysShowName", "always_show_name", bool)
        getter("IsShowDamage", "show_damage", bool)
        getter("GetUITheme", "ui_theme")
        getter("GetUIScalePercent", "ui_scale_percent", int)
        getter("IsUIReducedMotion", "ui_reduced_motion", int)
        setter("SetMusicVolume", lambda value: settings.__setitem__("music_volume", float(value)))
        setter("SetSoundVolume", lambda value: settings.__setitem__("sound_volume", float(value)))
        setter("SetFogLevel", lambda value: settings.__setitem__("fog_level", int(value)))
        setter("SetAlwaysShowNameFlag", lambda value: settings.__setitem__("always_show_name", bool(value)))
        setter("SetShowDamageFlag", lambda value: settings.__setitem__("show_damage", bool(value)))
        setter("SetViewChatFlag", lambda value: setattr(game, "view_chat", bool(value)))
        setter("SetShowSalesTextFlag", lambda value: setattr(game, "show_sales_text", bool(value)))
        setter("SetUITheme", lambda value: settings.__setitem__("ui_theme", value))
        setter("SetUIScalePercent", lambda value: settings.__setitem__("ui_scale_percent", int(value)))
        setter("SetUIReducedMotion", lambda value: settings.__setitem__("ui_reduced_motion", int(value)))
        setter("SaveConfig", lambda: setattr(game, "saved_configs", game.saved_configs + 1))

        background = modules["background"]
        background.IsSoftwareTiling = lambda: bool(game.software_tiling)
        define(background, "EnableSoftwareTiling", lambda value: setattr(game, "software_tiling", bool(value)))

        app = modules["app"]
        app.GetFileList = lambda pattern: list(game.file_lists.get(pattern, []))

    def load_music_info(self):
        """The real assets/root/musicinfo.py (its names, fieldMusic,
        METIN2THEMA), its file writes kept in Game.files (BGM/lastplay.inf)
        instead of the folder, its SaveLastPlayFieldMusic recorded."""
        module = self.load("musicInfo", "musicinfo.py")
        module.open = self._open
        save = module.SaveLastPlayFieldMusic
        log = self.log

        def recorded_save():
            log.append(("musicInfo.SaveLastPlayFieldMusic", (module.fieldMusic,)))
            return save()
        module.SaveLastPlayFieldMusic = recorded_save
        return module

    # --- sys.modules ----------------------------------------------------------------

    def __enter__(self):
        """Reentrant: a nested `with game:` (a helper inside a test's own)
        leaves the modules in place until the outermost one ends."""
        self._depth = getattr(self, "_depth", 0) + 1
        for name, module in self.modules.items():
            self._saved.setdefault(name, sys.modules.get(name, support.MISSING))
            sys.modules[name] = module
        return self

    def __exit__(self, *exc):
        self._depth = getattr(self, "_depth", 1) - 1
        if self._depth > 0:
            return False
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


# --- Wave 5a (P12 spec 5.4) ---------------------------------------------------------------------------

# PythonEventManager.h:28-33.
QUEST_BUTTON_TYPES = {"BUTTON_TYPE_NEXT": 0, "BUTTON_TYPE_DONE": 1, "BUTTON_TYPE_CANCEL": 2}
# The DirectInput codes the legacy dialogs compare (dinput.h).
WAVE5A_APP_CONSTANTS = {"DIK_ESCAPE": 0x01, "DIK_RETURN": 0x1C, "DIK_UP": 0xC8, "DIK_DOWN": 0xD0}
# PythonCharacterModule.cpp:1334, :1435-1436 (CActorInstance::EType, CRaceMotionData).
CHR_CONSTANTS = {"INSTANCE_TYPE_BUILDING": 5, "INSTANCE_TYPE_OBJECT": 10, "MOTION_WAIT": 1}
GUILD_BUILDING_LIST = os.path.normpath(os.path.join(support.HERE, "..", "assets", "locale", "locale", "en",
                                                     "guildbuildinglist.txt"))
# The guild building rows when the real list cannot be read: (vnum, type, name, local name, x, y, z limits,
# price, material).
FALLBACK_BUILDINGS = (
    (14100, "HEADQUARTER", "headquarter_1", "Headquarters", 0, 0, 360, "20000000", ["50", "30", "20"]),
    (14200, "FACILITY", "facility_1", "Blacksmith", 0, 0, 360, "3000000", ["25", "25", "10"]),
    (14201, "FACILITY", "facility_2", "Alchemist", 0, 0, 360, "3000000", ["25", "25", "10"]),
    (14300, "OBJECT", "object_1", "Stone Lantern", 30, 30, 360, "500000", ["5", "0", "0"]),
    (14301, "OBJECT", "object_2", "Flag", 0, 0, 0, "100000", ["0", "5", "0"]),
)


def source_of(file_name, names, inside=None):
    """The source of the top-level definitions (functions, classes and simple
    assignments) `names` of a root module, or of the methods `names` of its
    class `inside`, dedented to the top level."""
    import ast
    with open(os.path.join(ROOT, file_name), encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source)
    body = tree.body
    if inside is not None:
        body = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == inside).body
    parts = []
    for node in body:
        named = getattr(node, "name", None)
        if isinstance(node, ast.Assign):
            named = next((target.id for target in node.targets if isinstance(target, ast.Name)), None)
        if named in names:
            segment = ast.get_source_segment(source, node, padded=True)
            lines = segment.split("\n")
            indent = len(lines[0]) - len(lines[0].lstrip("\t"))
            parts.append("\n".join(line[indent:] if line.startswith("\t" * indent) else line for line in lines))
    return "\n\n".join(parts)


def empty_quest_page(skin=0):
    """quest.<index>.page before the interpreter made anything (P12 spec 3.2)."""
    return {"skin": int(skin), "choices": [], "pages": 0, "button": "", "input": False,
            "images": {"left": "", "top": "", "background": "", "title": "", "title_serial": 0},
            "free_images": [], "size": {"width": 0, "height": 0},
            "fade": {"kind": "", "speed": 0.0, "serial": 0}, "delay": 10,
            "waiting": False, "locked": False, "ended": False, "done": False}


def install_wave5a_ui(game):
    """Adds to game what the Wave 5a legacy windows and facades use (P12 spec
    5.4), after install_wave2b_ui and install_wave3a_ui (made here when a test
    has not), and loads the legacy modules with their real uiscripts:

    - `uiQuest` (uiquest.py, the legacy dialog and curtain), `uiWeb`
      (uiweb.py), `consoleModule` (consolemodule.py, its os calls on
      Game.console_os) and `uiGuild` with BuildGuildBuildingWindow,
      NumberToMoneyString and its material constants (compiled from
      uiguild.py; BUILDING_DATA_LIST from the real en guildbuildinglist.txt
      through playersettingmodule.LoadGuildBuildingList, else
      FALLBACK_BUILDINGS);
    - `ui`: a Button whose CallEvent plays the click and calls its event (as
      ui.Button.CallEvent), SlotBar, MakeImageBox, and a ListBox with
      legacy's selection rule (SelectItem fires only on a change) for the
      loader, which builds listbox, slotbar and image children too;
    - `event`: BUTTON_TYPE_NEXT, DONE and CANCEL; RegisterEventSetFromString
      (the next free index, Game.event_sets holds the scripts),
      ClearEventSet (which detaches the sink, as C++ does) and
      EndEventProcess (which lowers the set's wait flag that
      Game.run_fade raises before a fade callback, as C++ does); every
      call recorded, layout getters answering 0;
    - `nuigame`: QuestAttach, QuestDetach, QuestState, QuestScript,
      QuestOpenScript (P12 spec 3.4) over Game.quest_sets, Game.publish_quest()
      standing in for the C++ driver's feeds; WebPageFollow and WebPageState
      (6.4.4) over Game.web;
    - `app`: the DIK codes, ShowWebPage, MoveWebPage, HideWebPage and
      IsWebPageMode over Game.web, IsEnableTestServerFlag (Game.test_server);
    - `chr` (the constants, GetBoundBoxOnlyXY), `background` (GetHeight,
      GetPickingPoint: Game.picking_point), `player` (GetMainCharacterPosition,
      GetMoney, GetItemCountByVnum: Game.main_position, .money,
      .material_counts), `debugInfo.IsDebugMode` (Game.debug_mode),
      `uiCommon.PopupDialog` (recording, Game.popups) when the test put no
      uiCommon of its own.

    Returns game."""
    ui = game.modules["ui"]
    if not getattr(ui, "_wave3a", False):
        install_wave2b_ui(game)
        install_wave3a_ui(game)
        ui._wave3a = True
    if getattr(ui, "_wave5a", False):
        return game
    ui._wave5a = True
    log = game.log
    _install_wave5a_ui(game, ui)
    _install_wave5a_modules(game, log)
    _load_wave5a_legacy(game)
    return game


def _install_wave5a_ui(game, ui):
    Win, Button = ui.Window, ui.Button
    snd = game.modules["snd"]

    def call_event(self):
        """ui.Button.CallEvent: the click, then the event."""
        snd.PlaySound("sound/ui/click.wav")
        if self.event:
            self.event(*self.eventArgs)
    Button.CallEvent = call_event

    class SlotBar(Win):
        pass

    class ListBox(Win):
        """ui.ListBox: rows of (number, text); SelectItem fires the event only
        when the selection changes (ui.py ListBox.SelectItem)."""

        def __init__(self, layer="UI"):
            Win.__init__(self, layer)
            self.keyDict = {}
            self.textDict = {}
            self.itemList = []
            self.selectedLine = -1
            self.basePos = 0
            self.stepSize = 17
            self.event = lambda *args: None

        def ClearItem(self):
            self.keyDict, self.textDict, self.itemList, self.selectedLine = {}, {}, [], -1

        def InsertItem(self, number, text):
            self.keyDict[len(self.itemList)] = number
            self.textDict[len(self.itemList)] = text
            self.itemList.append(text)

        def ChangeItem(self, number, text):
            for key, value in list(self.keyDict.items()):
                if value == number:
                    self.textDict[key] = text
                    self.itemList[key] = text
                    return

        def SetEvent(self, event):
            self.event = event

        def SelectItem(self, line):
            if line not in self.keyDict or line == self.selectedLine:
                return
            self.selectedLine = line
            self.event(self.keyDict.get(line, 0), self.textDict.get(line, "None"))

        def GetSelectedItem(self):
            return self.keyDict.get(self.selectedLine, 0)

        def GetItemCount(self):
            return len(self.itemList)

        def GetViewItemCount(self):
            return int(self.GetHeight() // self.stepSize) if self.GetHeight() else 8

        def SetBasePos(self, pos):
            self.basePos = pos

        def ArrangeItem(self):
            pass

        def LocateItem(self):
            pass

        def texts(self):
            return [self.textDict[i] for i in range(len(self.itemList))]

        def select(self, line):
            """A press on visible row `line` (OnMouseLeftButtonUp)."""
            self.SelectItem(line + self.basePos)

    def make_image_box(parent, filename, x, y):
        box = ui.ImageBox()
        box.SetParent(parent)
        box.LoadImage(filename)
        box.SetPosition(x, y)
        box.Show()
        return box

    ui.SlotBar = SlotBar
    ui.ListBox = ListBox
    ui.MakeImageBox = make_image_box
    # Legacy subclasses call their base's destructor (uiquest.ToolTipImageBox).
    ui.ImageBox.__del__ = lambda self: None

    class PlainToolTip(ToolTip):
        """uiToolTip.ToolTip as uiquest.ToolTipImageBox uses it: its lines kept."""

        def __init__(self, *args):
            ToolTip.__init__(self, "plain")
            self.lines = []

        def AutoAppendTextLine(self, text, *args):
            self.lines.append(text)

        def ResizeToolTip(self):
            pass

        def Show(self):
            self.visible = True
    game.modules["uiToolTip"].ToolTip = PlainToolTip
    loader = ui.PythonScriptLoader
    build_children = loader.LoadScriptFile

    def load_script_file(self, window, path):
        """The Wave 3a loader, with list boxes, slot bars and images made of
        their kinds."""
        build_children(self, window, path)
        _rebuild_kinds(window, read_uiscript(path), {"listbox": ListBox, "slotbar": SlotBar, "image": ui.ImageBox})
    loader.LoadScriptFile = load_script_file


def _rebuild_kinds(window, value, kinds):
    for child in value.get("children", ()) or ():
        cls = kinds.get(child.get("type"))
        if cls is not None:
            widget = cls()
            widget.name = child.get("name", "")
            window.ElementDictionary[widget.name] = widget
        _rebuild_kinds(window, child, kinds)


def _install_wave5a_modules(game, log):
    game.event_sets = {}         # index -> the script registered (RegisterEventSetFromString)
    game.event_waits = {}        # index -> the set's wait flag (Game.run_fade raises it, EndEventProcess lowers it)
    game.quest_sets = {}         # index -> the sink's state of an attached set (nuigame.QuestState)
    game.game_window = None      # the window QuestOpenScript calls OpenQuestWindow on
    game.web = {"mode": False, "url": "", "rect": None, "moves": [], "follow": None, "zoom": 0.0,
                "navigation": {"uri": "", "cancelled": False}}
    game.test_server = False     # app.IsEnableTestServerFlag
    game.picking_point = (12000.0, 34000.0, 100.0)  # background.GetPickingPoint
    game.main_position = (12000.0, 34000.0, 100.0)  # player.GetMainCharacterPosition
    game.money = 0               # player.GetMoney
    game.material_counts = {}    # vnum -> player.GetItemCountByVnum
    game.debug_mode = False      # debugInfo.IsDebugMode
    game.popups = []             # every uiCommon.PopupDialog the stand-in made
    game.console_os = ConsoleOs()

    event = game.modules["event"]
    for name, value in QUEST_BUTTON_TYPES.items():
        setattr(event, name, value)

    def register(script):
        index = 0
        while index in game.event_sets:
            index += 1
        game.event_sets[index] = script
        return index

    def clear(index):
        game.event_sets.pop(index, None)
        game.event_waits.pop(index, None)
        state = game.quest_sets.get(index)
        if state is not None and state["attached"]:
            detach(index)

    def end_event_process(index):
        game.event_waits[index] = False
    define(event, "RegisterEventSetFromString", register)
    define(event, "ClearEventSet", clear)
    define(event, "EndEventProcess", end_event_process)

    def run_fade(handler, index, name, speed):
        """A fade command as the interpreter runs it (PythonEventManager.cpp,
        ProcessEventSet): the set's wait flag raised, then the handler's
        FadeOut, FadeIn, WhiteOut or WhiteIn; EndEventProcess lowers it, and
        the set goes on only while it is down (Game.event_waits)."""
        game.event_waits[index] = True
        return getattr(handler, name)(speed)
    game.run_fade = run_fade

    app = game.modules["app"]
    for name, value in WAVE5A_APP_CONSTANTS.items():
        setattr(app, name, value)
    web = game.web

    def show_web_page(url, rect):
        web.update(mode=True, url=url, rect=tuple(rect))

    def move_web_page(rect):
        web["moves"].append(tuple(rect))

    def hide_web_page():
        web["mode"] = False
    define(app, "ShowWebPage", show_web_page)
    define(app, "MoveWebPage", move_web_page)
    define(app, "HideWebPage", hide_web_page)
    app.IsWebPageMode = lambda: web["mode"]
    app.IsEnableTestServerFlag = lambda: game.test_server

    chr_module = game.modules["chr"]
    for name, value in CHR_CONSTANTS.items():
        setattr(chr_module, name, value)
    chr_module.GetBoundBoxOnlyXY = lambda vid: (-100.0, -100.0, 100.0, 100.0)
    background = game.modules["background"]
    background.GetHeight = lambda x, y: 0.0
    background.GetPickingPoint = lambda: game.picking_point
    player = game.modules["player"]
    player.GetMainCharacterPosition = lambda: game.main_position
    player.GetMoney = lambda: game.money
    player.GetItemCountByVnum = lambda vnum: game.material_counts.get(vnum, 0)
    game.modules["debugInfo"] = support.stub_module("debugInfo", IsDebugMode=lambda: game.debug_mode)
    if "uiCommon" not in game.modules:
        game.modules["uiCommon"] = support.stub_module("uiCommon", PopupDialog=_popup_class(game))

    nuigame = game.modules["nuigame"]
    if nuigame is None:
        return

    def attach(index, skin):
        state = game.quest_sets.get(index)
        if index not in game.event_sets or (state is not None and state["attached"]):
            return False
        game.quest_sets[index] = {"attached": True, "skin": int(skin), "lines": [], "page": empty_quest_page(skin),
                                  "lines_revision": 0, "page_revision": 0, "updates": 0}
        return True

    def detach(index):
        state = game.quest_sets.get(index)
        if state is None:
            return None
        state["attached"] = False
        state["lines"], state["page"] = [], empty_quest_page(state["skin"])
        game.state.publish("quest.%d.lines" % index, [])
        game.state.publish("quest.%d.page" % index, empty_quest_page(state["skin"]))
        return None

    def quest_state(index):
        state = game.quest_sets.get(index)
        return dict(state) if state is not None else None

    def open_script(skin, script):
        if game.game_window is None:
            return -1
        index = register(script)
        game.game_window.OpenQuestWindow(skin, index)
        return index

    def follow(document, element_id):
        web["follow"] = (document, element_id) if document else None
        return True

    def web_state():
        following = web["follow"]
        return {"following": following is not None, "document": following[0] if following else "",
                "element": following[1] if following else "", "page_mode": web["mode"], "rect": web["rect"],
                "wanted": None, "zoom": web["zoom"], "navigation": dict(web["navigation"])}
    define(nuigame, "QuestAttach", attach)
    define(nuigame, "QuestDetach", detach)
    define(nuigame, "QuestState", quest_state)
    define(nuigame, "QuestScript", lambda index: game.event_sets.get(index, ""))
    define(nuigame, "QuestOpenScript", open_script)
    define(nuigame, "WebPageFollow", follow)
    define(nuigame, "WebPageState", web_state)

    def publish_quest(index, lines=None, **page):
        """The C++ driver's publish for set `index`: the lines as given, the
        page's keys changed (the rest kept), each feed only when given."""
        state = game.quest_sets[index]
        if lines is not None:
            state["lines"] = lines
            state["lines_revision"] += 1
            game.state.publish("quest.%d.lines" % index, lines)
        if page:
            state["page"] = dict(state["page"], **page)
            state["page_revision"] += 1
            game.state.publish("quest.%d.page" % index, state["page"])
    game.publish_quest = publish_quest


class ConsoleOs(object):
    """What consolemodule.py asks of os: a fixed folder tree (Game.console_os),
    the real os.path and os.sep."""

    R_OK = os.R_OK
    path = os.path
    sep = os.sep

    def __init__(self):
        self.tree = {"D:\\Ymir Work\\": ["effect", "item", "pc", "readme.txt"]}
        self.calls = []

    def listdir(self, path):
        self.calls.append(("listdir", path))
        for folder, names in self.tree.items():
            if os.path.normcase(folder.rstrip("\\/")) == os.path.normcase(str(path).rstrip("\\/")):
                return list(names)
        raise OSError("stand-in: no folder %s" % path)

    def stat(self, path):
        import stat
        is_dir = "." not in os.path.basename(str(path).rstrip("\\/"))
        return os.stat_result(((stat.S_IFDIR if is_dir else stat.S_IFREG) | 0o755, 0, 0, 1, 0, 0, 0, 0, 0, 0))

    def access(self, path, mode):
        self.calls.append(("access", path, mode))
        return True


def _popup_class(game):
    class PopupDialog(object):
        """uiCommon.PopupDialog: what it was given; Open records it in Game.popups."""

        def __init__(self, *args):
            self.text = ""
            self.event = None
            self.shown = False

        def SetText(self, text):
            self.text = text

        def SetAcceptEvent(self, event):
            self.event = event

        def Open(self):
            self.shown = True
            game.popups.append(self.text)

        def Close(self):
            self.shown = False

        def Destroy(self):
            self.shown = False

        def __getattr__(self, attr):
            if attr.startswith("__") or not attr[:1].isupper():
                raise AttributeError(attr)
            return lambda *args, **kwargs: None
    return PopupDialog


def _load_wave5a_legacy(game):
    if "constInfo" not in game.loaded:
        game.load("constInfo", "constinfo.py")
    if "mouseModule" not in game.loaded:
        game.load("mouseModule", "mousemodule.py")
    with contextlib.redirect_stdout(io.StringIO()):
        game.load("uiQuest", "uiquest.py").print = lambda *args, **kwargs: None
        game.load("uiWeb", "uiweb.py").print = lambda *args, **kwargs: None
        console = game.load("consoleModule", "consolemodule.py")
        console.print = lambda *args, **kwargs: None
        console.os = game.console_os
        game.modules["uiGuild"] = _legacy_guild(game)
        game.loaded["uiGuild"] = game.modules["uiGuild"]


def _legacy_guild(game):
    """uiGuild with BuildGuildBuildingWindow, compiled from uiguild.py over the
    game's stand-ins, and BUILDING_DATA_LIST filled."""
    module = types.ModuleType("uiGuild")
    module.__file__ = os.path.join(ROOT, "uiguild.py")
    names = ("NumberToMoneyString", "MATERIAL_STONE_INDEX", "MATERIAL_LOG_INDEX", "MATERIAL_PLYWOOD_INDEX",
             "MATERIAL_STONE_ID", "MATERIAL_LOG_ID", "MATERIAL_PLYWOOD_ID", "BUILDING_DATA_LIST",
             "BuildGuildBuildingWindow")
    with game:
        namespace = module.__dict__
        for name in ("app", "ui", "net", "wndMgr", "grp", "localeInfo", "player", "chr", "background", "miniMap",
                     "uiScriptLocale", "uiCommon", "constInfo", "mouseModule"):
            namespace[name] = sys.modules.get(name) or game.modules.get(name)
        exec(compile(source_of("uiguild.py", names), "uiguild.py", "exec"), namespace)
        game.modules["uiGuild"] = module
        sys.modules["uiGuild"] = module
        if not _load_building_list(game, module):
            module.BUILDING_DATA_LIST = [
                {"VNUM": vnum, "TYPE": kind, "NAME": name, "LOCAL_NAME": local, "X_ROT_LIMIT": x, "Y_ROT_LIMIT": y,
                 "Z_ROT_LIMIT": z, "PRICE": price, "MATERIAL": list(material), "SHOW": True}
                for vnum, kind, name, local, x, y, z, price, material in FALLBACK_BUILDINGS]
    return module


def _load_building_list(game, module):
    """The real LoadGuildBuildingList (playersettingmodule.py) over a stand-in
    app that reads the en list from disk. False when that fails."""
    try:
        with open(GUILD_BUILDING_LIST, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().split("\n")
    except OSError:
        return False
    files = types.SimpleNamespace(OpenTextFile=lambda name: 1, GetTextFileLineCount=lambda handle: len(lines),
                                  GetTextFileLine=lambda handle, i: lines[i].rstrip("\r"),
                                  CloseTextFile=lambda handle: None)
    namespace = {"app": files}
    try:
        exec(compile(source_of("playersettingmodule.py", ("LoadGuildBuildingList",)), "playersettingmodule.py", "exec"),
             namespace)
        namespace["LoadGuildBuildingList"]("guildbuildinglist.txt")
    except Exception:
        return False
    return bool(module.BUILDING_DATA_LIST)


# --- Wave 3b (P14 spec 9.3): the inventory, costume, belt and select item windows -----------------

# PythonPlayerModule.cpp and GameType.h today (P14 spec 3.2).
WAVE3B_PLAYER_CONSTANTS = {
    "INVENTORY_PAGE_SIZE": 45, "INVENTORY_PAGE_COUNT": 2, "INVENTORY_SLOT_COUNT": 168, "EQUIPMENT_SLOT_START": 90,
    "EQUIPMENT_PAGE_COUNT": 12, "NEW_EQUIPMENT_SLOT_START": 111, "NEW_EQUIPMENT_SLOT_COUNT": 3,
    "ATTRIBUTE_SLOT_MAX_NUM": 7, "METIN_SOCKET_TYPE_NONE": 0, "METIN_SOCKET_TYPE_SILVER": 1, "METIN_SOCKET_TYPE_GOLD": 2,
    "REFINE_CANT": 0, "REFINE_OK": 1, "REFINE_ALREADY_MAX_SOCKET_COUNT": 2, "REFINE_NEED_MORE_GOOD_SCROLL": 3,
    "REFINE_CANT_MAKE_SOCKET_ITEM": 4, "REFINE_NOT_NEXT_GRADE_ITEM": 5, "REFINE_CANT_REFINE_METIN_TO_EQUIPMENT": 6,
    "REFINE_CANT_REFINE_ROD": 7, "ATTACH_METIN_CANT": 0, "ATTACH_METIN_OK": 1, "ATTACH_METIN_NOT_MATCHABLE_ITEM": 2,
    "ATTACH_METIN_NO_MATCHABLE_SOCKET": 3, "ATTACH_METIN_NOT_EXIST_GOLD_SOCKET": 4,
    "ATTACH_METIN_CANT_ATTACH_TO_EQUIPMENT": 5, "DETACH_METIN_CANT": 0, "DETACH_METIN_OK": 1,
    "AUTO_POTION_TYPE_HP": 0, "AUTO_POTION_TYPE_SP": 1,
    "DRAGON_SOUL_PAGE_SIZE": 32, "DRAGON_SOUL_PAGE_COUNT": 5, "DRAGON_SOUL_SLOT_COUNT": 960,
    "DRAGON_SOUL_EQUIPMENT_SLOT_START": 122, "DRAGON_SOUL_EQUIPMENT_PAGE_COUNT": 2, "DRAGON_SOUL_EQUIPMENT_FIRST_SIZE": 6,
}
# PythonItemModule.cpp today (the slot numbers; the flags as CItemData's bits).
WAVE3B_ITEM_CONSTANTS = {
    "COSTUME_SLOT_START": 109, "COSTUME_SLOT_COUNT": 2, "COSTUME_SLOT_END": 111, "COSTUME_SLOT_BODY": 109,
    "COSTUME_SLOT_HAIR": 110, "BELT_INVENTORY_SLOT_START": 152, "BELT_INVENTORY_SLOT_COUNT": 16,
    "BELT_INVENTORY_SLOT_END": 168, "EQUIPMENT_COUNT": 12, "EQUIPMENT_BODY": 90, "EQUIPMENT_HEAD": 91,
    "EQUIPMENT_SHOES": 92, "EQUIPMENT_WRIST": 93, "EQUIPMENT_WEAPON": 94, "EQUIPMENT_NECK": 95, "EQUIPMENT_EAR": 96,
    "EQUIPMENT_UNIQUE1": 97, "EQUIPMENT_UNIQUE2": 98, "EQUIPMENT_ARROW": 99, "EQUIPMENT_RING1": 111,
    "EQUIPMENT_RING2": 112, "EQUIPMENT_BELT": 113, "ITEM_APPLY_MAX_NUM": 3, "ITEM_SOCKET_MAX_NUM": 3,
    "LIMIT_MAX_NUM": 2, "ITEM_ANTIFLAG_SELL": 1 << 14, "ANTIFLAG_SELL": 1 << 14, "ITEM_FLAG_CONFIRM_WHEN_USE": 1 << 15,
    "ITEM_TYPE_NONE": 0, "ITEM_TYPE_WEAPON": 1, "ITEM_TYPE_ARMOR": 2, "ITEM_TYPE_USE": 3, "ITEM_TYPE_METIN": 10,
    "ITEM_TYPE_BELT": 34, "ITEM_TYPE_COSTUME": 28, "ARMOR_BODY": 0, "ARMOR_WRIST": 3, "ARMOR_NECK": 5, "ARMOR_EAR": 6,
}
WAVE3B_APP_CONSTANTS = {"ENABLE_COSTUME_SYSTEM": 1, "ENABLE_NEW_EQUIPMENT_SYSTEM": 1}
MODULE_CONSTANTS = os.path.join(support.HERE, "fixtures", "module_constants.json")


def module_constants():
    """{module: {name: value}}: the client's item, player, skill and app int
    constants (tools/fixtures/module_constants.json, made by
    tools/nui_module_constants.py from nova-client-src), read once."""
    if not _MODULE_CONSTANTS:
        import json
        with open(MODULE_CONSTANTS, encoding="utf-8") as handle:
            _MODULE_CONSTANTS.append(json.load(handle)["modules"])
    return _MODULE_CONSTANTS[0]


_MODULE_CONSTANTS = []


def _client_values(table, module):
    """table's names with the client's values where module_constants() has
    them (the literals above stand for the rest)."""
    known = module_constants().get(module, {})
    return dict((name, known.get(name, value)) for name, value in table.items())
# The legacy dialog modules a Wave 3b legacy window makes, as stand-ins.
WAVE3B_DIALOG_MODULES = ("uiCommon", "uiPickMoney", "uiRefine", "uiAttachMetin")


class LegacySlotWindow(object):
    """ui.SlotWindow and ui.GridSlotWindow as the C++ CSlotWindow keeps them
    (P14 spec 6.0): the slots a uiscript or ArrangeSlot made, what legacy set
    on each (vnum, count, active, lock, disable, the cover button's state),
    the events in ui.py's attributes and a dict (`events`), use mode, usable
    and the slot style. A test fires an event as the C++ would
    (fire("select_item", slot)) and reads what legacy shows (shown())."""

    EVENTS = ("select_empty", "select_item", "unselect_empty", "unselect_item", "use", "over_in", "over_out")

    def __init__(self, base):
        self._base = base
        self.slots = {}
        self.events = dict.fromkeys(self.EVENTS)
        self.use_mode = False
        self.usable = False
        self.style = WNDMGR_CONSTANTS["SLOT_STYLE_PICK_UP"]
        self.start_index = 0
        self.x_count = self.y_count = 0
        self.refreshes = 0

    @staticmethod
    def empty():
        return {"vnum": 0, "count": 0, "active": False, "locked": False, "disabled": False, "cover": None,
                "unavailable": False, "always_cover": False}

    def AppendSlot(self, index, x=0, y=0, w=32, h=32):
        self.slots[int(index)] = self.empty()

    def ArrangeSlot(self, start, x_count, y_count, w=32, h=32, xb=0, yb=0):
        self.start_index, self.x_count, self.y_count = int(start), int(x_count), int(y_count)
        self.slots = dict((int(start) + i, self.empty()) for i in range(int(x_count) * int(y_count)))

    def _slot(self, index):
        return self.slots.get(int(index))

    def SetItemSlot(self, index, vnum, count=0, color=None):
        slot = self._slot(index)
        if slot is None:
            return
        if not vnum:
            self.ClearSlot(index)
            return
        if slot["vnum"] != vnum:
            slot["active"] = False
        slot.update({"vnum": int(vnum), "count": int(count), "locked": False, "disabled": False})

    def ClearSlot(self, index):
        slot = self._slot(index)
        if slot is not None:
            slot.update({"vnum": 0, "count": 0, "active": False, "locked": False, "disabled": False})

    def ActivateSlot(self, index):
        slot = self._slot(index)
        if slot is not None:
            slot["active"] = True

    def DeactivateSlot(self, index):
        slot = self._slot(index)
        if slot is not None:
            slot["active"] = False

    def SetCoverButton(self, index, up="", over="", down="", disable="", left=False, right=True):
        slot = self._slot(index)
        if slot is not None:
            slot["cover"] = (up, over, down, disable)

    def EnableCoverButton(self, index):
        slot = self._slot(index)
        if slot is not None:
            slot["unavailable"] = False

    def DisableCoverButton(self, index):
        slot = self._slot(index)
        if slot is not None:
            slot["unavailable"] = True

    def SetAlwaysRenderCoverButton(self, index, flag=True):
        slot = self._slot(index)
        if slot is not None:
            slot["always_cover"] = bool(flag)

    def LockSlot(self, index):
        slot = self._slot(index)
        if slot is not None:
            slot["locked"] = True

    def UnlockSlot(self, index):
        slot = self._slot(index)
        if slot is not None:
            slot["locked"] = False

    def SetUseMode(self, flag):
        self.use_mode = bool(flag)

    def SetUsableItem(self, flag):
        self.usable = bool(flag)

    def SetSlotStyle(self, style):
        self.style = style

    def SetSlotBaseImage(self, *args):
        pass

    def RefreshSlot(self):
        self.refreshes += 1

    def __set_event(name, attribute):
        def set_event(self, event):
            self.events[name] = event
            setattr(self, attribute, event)
        return set_event

    SetSelectEmptySlotEvent = __set_event("select_empty", "eventSelectEmptySlot")
    SetSelectItemSlotEvent = __set_event("select_item", "eventSelectItemSlot")
    SetUnselectEmptySlotEvent = __set_event("unselect_empty", "eventUnselectEmptySlot")
    SetUnselectItemSlotEvent = __set_event("unselect_item", "eventUnselectItemSlot")
    SetUseSlotEvent = __set_event("use", "eventUseSlot")
    SetOverInItemEvent = __set_event("over_in", "eventOverInItem")
    SetOverOutItemEvent = __set_event("over_out", "eventOverOutItem")
    del __set_event

    def SAFE_SetButtonEvent(self, button, state, event):
        names = {"LEFT": ("select_empty", "select_item"), "RIGHT": ("unselect_empty", "unselect_item")}[button]
        if state in ("EMPTY", "ALWAYS"):
            self.events[names[0]] = event
        if state in ("EXIST", "ALWAYS"):
            self.events[names[1]] = event

    def fire(self, name, *args):
        """The event the C++ slot window sends its handler."""
        event = self.events[name]
        if event:
            event(*args)

    def shown(self):
        """{slot: (vnum, count label, active)} of the slots that hold an item,
        as CSlotWindow draws them (SetSlotCount shows a count above 0)."""
        return dict((index, (slot["vnum"], str(slot["count"]) if slot["count"] > 0 else "", slot["active"]))
                    for index, slot in self.slots.items() if slot["vnum"])

    def __getattr__(self, attr):
        return getattr(self._base, attr)


class LegacyDialog(object):
    """A legacy common dialog (uiCommon.QuestionDialog, QuestionDialog2,
    PopupDialog; uiPickMoney.PickMoneyDialog): records Open and Close with
    its texts in the Game's log, keeps its events; accept() and cancel()
    press its buttons. Callers store attributes on it (count, slotIndex)."""

    def __init__(self, game, module, kind):
        self._game = game
        self._name = "%s.%s" % (module, kind)
        self.texts = []
        self.title = ""
        self.accept_event = None
        self.cancel_event = None
        self.max = None
        self.opened = None
        self.is_open = False
        game.dialogs.append(self)

    def _log(self, what, *args):
        self._game.log.append(("%s.%s" % (self._name, what), args))

    def SetText(self, text):
        self.texts = [text]

    def SetText1(self, text):
        self.texts[:1] = [text]

    def SetText2(self, text):
        while len(self.texts) < 1:
            self.texts.append("")
        self.texts[1:2] = [text]

    def SetTitleName(self, name):
        self.title = name

    def SetAcceptEvent(self, event):
        self.accept_event = event

    def SetCancelEvent(self, event):
        self.cancel_event = event

    def SetMax(self, digits):
        self.max = digits
        self._log("SetMax", digits)

    def Open(self, *args):
        self.opened = args
        self.is_open = True
        self._log("Open", *(tuple(self.texts) + (self.title,) + args))

    def Close(self):
        if self.is_open:
            self._log("Close")
        self.is_open = False

    def Hide(self):
        self.is_open = False

    def Show(self):
        self.is_open = True

    def IsShow(self):
        return self.is_open

    def LoadDialog(self):
        return 1

    def Destroy(self):
        self.is_open = False

    def SetTop(self):
        pass

    def SetWarningLine(self, index):
        pass

    def accept(self, *args):
        if self.accept_event:
            self.accept_event(*args)

    def cancel(self):
        if self.cancel_event:
            self.cancel_event()


class LegacyDialogWindow(object):
    """uiRefine.RefineDialog, RefineDialogNew and uiAttachMetin.AttachMetinDialog
    as the inventory sees them: Open's arguments recorded in the log."""

    def __init__(self, game, name):
        self._game = game
        self._name = name
        self.shown = False

    def Open(self, *args):
        self.shown = True
        self._game.log.append((self._name + ".Open", args))

    def Close(self):
        self.shown = False

    def Hide(self):
        self.shown = False

    def Show(self):
        self.shown = True

    def IsShow(self):
        return self.shown

    def SetTop(self):
        pass

    def Destroy(self):
        self.shown = False


def install_wave3b_ui(game):
    """Adds to game (after install_wave2b_ui and install_wave3a_ui) what the
    Wave 3b legacy windows use (uiinventory.py, uiselectitem.py, P14 spec
    9.3):
    - a PythonScriptLoader that reads the real uiscript file and makes each
      named child of its type, slot windows included (LegacySlotWindow: a
      "slot" element's slots, a "grid_table" arranged as the uiscript says),
      each widget at its size; wndMgr.Show and Hide of a handle reach its
      window (the inventory hides itself that way);
    - player, item and app with today's constants (WAVE3B_*_CONSTANTS) and
      the inventory's functions over the Game's state: money (Game.elk), the
      item flags, grades and the belt's available cells, IsEquipmentSlot and
      the other position checks, the item kinds (Game.refine_scrolls,
      .metins, .detach_scrolls, .keys, .equipment, .use_types, .antiflags,
      .item_flags_of, .prices), the cursor (Game.cursor), GetItemLink;
      CanRefine, CanAttachMetin, CanDetach and CanUnlock answer OK unless a
      test scripts them (Game.answer);
    - stand-ins of uiCommon, uiPickMoney, uiRefine and uiAttachMetin whose
      dialogs record their opens (Game.dialogs, LegacyDialog);
    - an Interface stand-in (Game.interface) whose ToggleDragonSoulWindow is
      recorded, and a dragon soul refine window that is hidden;
    - the UI layer's order as CWindowManager keeps it (Game.ui_order, the
      ScriptWindows of the UI layer, bottom first): the loader adds the
      uiscript's root "style" as flags (AddFlag), SetTop moves a "float"
      window last and runs its OnTop (CWindow::SetTop), and
      Game.press_escape() walks the shown windows last first until an
      OnPressEscapeKey returns True (CWindow::RunPressEscapeKeyEvent)."""
    ui = game.modules["ui"]
    Win = ui.Window
    windows_by_handle = {}

    class Image(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "image")
            self.size = (0, 0)
            self.position = (0, 0)

        def SetSize(self, width, height):
            self.size = (width, height)

        def GetWidth(self):
            return self.size[0]

        def GetHeight(self):
            return self.size[1]

        def SetPosition(self, x, y):
            self.position = (x, y)

    def slot_window(child):
        widget = LegacySlotWindow(Win())
        if child.get("type") == "grid_table":
            widget.ArrangeSlot(child.get("start_index", 0), child.get("x_count", 0), child.get("y_count", 0))
        for slot in child.get("slot", ()) or ():
            widget.AppendSlot(slot["index"], slot.get("x", 0), slot.get("y", 0), slot.get("width", 32), slot.get("height", 32))
        return widget

    kinds = {"button": ui.Button, "radio_button": ui.RadioButton, "toggle_button": ui.ToggleButton,
             "titlebar": ui.TitleBar, "board": ui.Board, "board_with_titlebar": ui.Board, "thinboard": ui.Board,
             "text": ui.TextLine, "image": Image, "expanded_image": Image, "ani_image": Image}

    def build(window, value):
        for child in value.get("children", ()) or ():
            kind = child.get("type")
            if kind in ("slot", "grid_table"):
                widget = slot_window(child)
            else:
                widget = kinds.get(kind, Win)()
            widget.name = child.get("name", "")
            if "text" in child and hasattr(widget, "SetText"):
                widget.SetText(child["text"])
            if "width" in child and hasattr(widget, "SetSize"):
                widget.SetSize(child.get("width", 0), child.get("height", 0))
            if "image" in child and hasattr(widget, "LoadImage"):
                widget.LoadImage(child["image"])
            window.ElementDictionary[widget.name] = widget
            build(window, child)

    class PythonScriptLoader(object):
        loaded = []

        def LoadScriptFile(self, window, path):
            PythonScriptLoader.loaded.append(path)
            clear = getattr(window, "ClearDictionary", None)
            if clear is not None:
                clear()
            if not hasattr(window, "ElementDictionary"):
                window.ElementDictionary = {}
            if not hasattr(window, "scripts"):
                window.scripts = []
            window.scripts.append(path)
            value = read_uiscript(path)
            if "width" in value:
                window.SetSize(value.get("width", 0), value.get("height", 0))
            for style in value.get("style", ()) or ():
                window.AddFlag(style)
            build(window, value)

    script_base = ui.ScriptWindow
    order = game.ui_order = []

    class ScriptWindow(script_base):
        def __init__(self, layer="UI"):
            script_base.__init__(self, layer)
            windows_by_handle[self.hWnd] = weakref.ref(self)
            self.flags = set()
            if layer == "UI":
                order.append(weakref.ref(self))

        def GetChild2(self, name):
            return self.ElementDictionary.get(name)

        def AddFlag(self, flag):
            self.flags.add(flag)

        def SetTop(self):
            """CWindow::SetTop: only a float window moves, last in its layer,
            and then hears OnTop."""
            script_base.SetTop(self)
            if "float" not in self.flags:
                return
            for ref in list(order):
                if ref() is self:
                    order.remove(ref)
                    order.append(ref)
                    break
            on_top = getattr(self, "OnTop", None)
            if on_top is not None:
                on_top()

    def press_escape():
        """CWindowManager::RunPressEscapeKey over the UI layer: the shown
        windows last first; the first whose OnPressEscapeKey answers True
        ends it. The window that took it, or None."""
        for ref in reversed(list(order)):
            window = ref()
            if window is None or not window.IsShow():
                continue
            escape = getattr(window, "OnPressEscapeKey", None)
            if escape is not None and escape():
                return window
        return None

    game.press_escape = press_escape

    ui.ScriptWindow = ScriptWindow
    ui.PythonScriptLoader = PythonScriptLoader
    ui.ImageBox = Image
    ui.SlotWindow = lambda layer="UI": LegacySlotWindow(Win(layer))
    ui.GridSlotWindow = ui.SlotWindow

    wndmgr = game.modules["wndMgr"]

    def by_handle(handle, shown):
        ref = windows_by_handle.get(handle)
        window = ref() if ref is not None else None
        if window is not None:
            window.shown = shown
    wndmgr.Show = lambda handle: by_handle(handle, True)
    wndmgr.Hide = lambda handle: by_handle(handle, False)
    wndmgr.OnceIgnoreMouseLeftButtonUpEvent = recorded(game.log, "wndMgr.OnceIgnoreMouseLeftButtonUpEvent", lambda: None)

    _wave3b_modules(game)
    return ui


def _wave3b_modules(game):
    """The player, item and app functions and the dialog stand-ins of
    install_wave3b_ui (its docstring lists them)."""
    modules = game.modules
    for attribute, value in (("elk", 0), ("cursor", APP_CONSTANTS["NORMAL"]), ("item_flags", {}), ("item_grades", {}),
                             ("belt_cells", 4), ("refine_scrolls", set()), ("metins", set()), ("detach_scrolls", set()),
                             ("keys", set()), ("equipment", set()), ("use_types", {}), ("antiflags", {}),
                             ("item_flags_of", {}), ("prices", {}), ("dialogs", [])):
        if not hasattr(game, attribute):
            setattr(game, attribute, value)

    player, item, app = modules["player"], modules["item"], modules["app"]
    ok = _client_values(WAVE3B_PLAYER_CONSTANTS, "player")
    for name, value in ok.items():
        setattr(player, name, value)
    for name, value in _client_values(WAVE3B_ITEM_CONSTANTS, "item").items():
        setattr(item, name, value)
    for name, value in WAVE3B_APP_CONSTANTS.items():
        setattr(app, name, value)

    define(player, "GetElk", lambda: game.elk)
    define(player, "IsEquipmentSlot", lambda pos: 90 <= pos < 122)
    define(player, "IsCostumeSlot", lambda pos: 109 <= pos < 111)
    define(player, "IsBeltInventorySlot", lambda pos: 152 <= pos < 168)
    define(player, "IsAvailableBeltInventoryCell", lambda pos: 0 <= pos - 152 < game.belt_cells)
    define(player, "GetItemFlags", lambda pos: game.item_flags.get(pos, 0))
    define(player, "GetItemGrade", lambda pos: game.item_grades.get(pos, 0))
    define(player, "GetItemAttribute", lambda pos, index: (0, 0))
    define(player, "CanRefine", lambda vnum, pos: ok["REFINE_OK"])
    define(player, "CanAttachMetin", lambda vnum, pos: ok["ATTACH_METIN_OK"])
    define(player, "CanDetach", lambda vnum, pos: ok["DETACH_METIN_OK"])
    define(player, "CanUnlock", lambda vnum, pos: True)
    define(player, "GetItemLink", lambda pos: "|cfff1e6c0|Hitem:%x:0:0:0:0|h[item %d]|h|r"
           % (game._item_at(pos)["vnum"], game._item_at(pos)["vnum"]))
    define(app, "GetCursor", lambda: game.cursor)

    selected = item.selected
    define(item, "GetItemName", lambda *vnum: "item %d" % (vnum[0] if vnum else selected[0]))
    define(item, "IsRefineScroll", lambda vnum: vnum in game.refine_scrolls)
    define(item, "IsMetin", lambda vnum: vnum in game.metins)
    define(item, "IsDetachScroll", lambda vnum: vnum in game.detach_scrolls)
    define(item, "IsKey", lambda vnum: vnum in game.keys)
    define(item, "IsEquipmentVID", lambda vnum: vnum in game.equipment)
    define(item, "GetUseType", lambda vnum: game.use_types.get(vnum, "USE_NONE"))
    define(item, "IsAntiFlag", lambda flag: bool(game.antiflags.get(selected[0], 0) & flag))
    define(item, "IsFlag", lambda flag: bool(game.item_flags_of.get(selected[0], 0) & flag))
    define(item, "GetISellItemPrice", lambda: game.prices.get(selected[0], 100))
    define(item, "Is1GoldItem", lambda: False)

    log = game.log

    def module_of(name, **members):
        module = types.ModuleType(name)
        for key, value in members.items():
            setattr(module, key, value)
        return module

    def dialog(module, kind):
        def make(*args):
            return LegacyDialog(game, module, kind)
        return make

    def window(name):
        def make(*args):
            return LegacyDialogWindow(game, name)
        return make

    game.put("uiCommon", module_of("uiCommon", QuestionDialog=dialog("uiCommon", "QuestionDialog"),
                                   QuestionDialog2=dialog("uiCommon", "QuestionDialog2"),
                                   PopupDialog=dialog("uiCommon", "PopupDialog")))
    game.put("uiPickMoney", module_of("uiPickMoney", PickMoneyDialog=dialog("uiPickMoney", "PickMoneyDialog")))
    game.put("uiRefine", module_of("uiRefine", RefineDialog=window("uiRefine.RefineDialog"),
                                   RefineDialogNew=window("uiRefine.RefineDialogNew")))
    game.put("uiAttachMetin", module_of("uiAttachMetin", AttachMetinDialog=window("uiAttachMetin.AttachMetinDialog")))

    class Interface(object):
        def ToggleDragonSoulWindow(self):
            log.append(("interface.ToggleDragonSoulWindow", ()))

    class DragonSoulRefine(object):
        shown = False

        def IsShow(self):
            return self.shown

        def AutoSetItem(self, *args):
            log.append(("interface.AutoSetItem", args))

    game.interface = Interface()
    game.dragon_soul_refine = DragonSoulRefine()


# --- the item data of the tooltip rules (P14 spec 5.8, 9.6) ---------------------------------------

def _constant(value, module, prefixes=()):
    """A corpus value as the client's int: an int as it is, a name of the
    module's constants (with or without one of `prefixes`), else 0."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value:
        return 0
    known = module_constants().get(module, {})
    for prefix in ("",) + tuple(prefixes):
        if prefix + value in known:
            return known[prefix + value]
    return 0


def _flags(value, module, prefixes):
    """Bit flags: an int, or a list of names OR'ed."""
    if isinstance(value, (list, tuple)):
        result = 0
        for name in value:
            result |= _constant(name, module, prefixes)
        return result
    return _constant(value, module, prefixes)


def _pairs(rows, module, prefixes, count):
    """[[type, value], ...] (types as names or ints), padded to `count` with
    (0, 0)."""
    pairs = [(_constant(kind, module, prefixes), int(value)) for kind, value in (rows or ())]
    return (pairs + [(0, 0)] * count)[:max(count, len(pairs))]


class ItemData(object):
    """The corpus's item rows (P14 spec 9.6: items {vnum: {name, type,
    subtype, size, antiflags, flags, wear, limits, applies, values, sockets,
    price, refine, icon, desc, summary}}) as CItemData answers them through
    the item module, and the case state the player, shop, exchange, safebox
    and skill modules answer (apply_case)."""

    def __init__(self, corpus):
        self.items = dict((int(vnum), row) for vnum, row in corpus.get("items", {}).items())
        self.skills = dict((int(index), row) for index, row in corpus.get("skills", {}).items())
        self.mobs = dict((int(vnum), name) for vnum, name in corpus.get("mobs", {}).items())
        self.selected = 0
        self.case = {}

    def row(self, vnum=None):
        return self.items.get(self.selected if vnum is None else int(vnum), {})

    def kind(self, vnum=None):
        return _constant(self.row(vnum).get("type", 0), "item", ("ITEM_TYPE_",))

    def subtype(self, vnum=None):
        row = self.row(vnum)
        value = row.get("subtype", 0)
        if isinstance(value, str):
            for prefix in ("", "WEAPON_", "ARMOR_", "USE_", "COSTUME_TYPE_", "METIN_", "DS_"):
                if prefix + value in module_constants()["item"]:
                    return module_constants()["item"][prefix + value]
            return 0
        return int(value or 0)

    def use_type(self, vnum):
        row = self.row(vnum)
        if row.get("use_type"):
            return row["use_type"]
        if self.kind(vnum) == module_constants()["item"].get("ITEM_TYPE_USE") and isinstance(row.get("subtype"), str):
            name = row["subtype"]
            return name if name.startswith("USE_") else "USE_" + name
        return "USE_NONE"


def install_item_data(game, corpus):
    """The item, player, skill, shop, exchange, safebox, chr, nonplayer and
    background answers of uitooltip.py's rules over a tooltip corpus (P14
    spec 5.8, 9.6), on a Game: the item module answers from the corpus's
    rows, with the client's constants (module_constants()); the others from
    the case set by apply_case(game, case) (case: {id, context, vnum,
    sockets, attrs, count, player, clock, shop, link, skill}; `pos`, the
    inventory position the case's item sits at, 0 by default). Returns the
    ItemData. Every call is recorded in the Game's log, as the other
    stand-ins'."""
    data = ItemData(corpus)
    game.item_data = data
    modules = game.modules
    item, player, skill = modules["item"], modules["player"], modules["skill"]
    for name, value in module_constants()["item"].items():
        setattr(item, name, value)
    for name in ("METIN_SOCKET_MAX_NUM", "ATTRIBUTE_SLOT_MAX_NUM", "LEVEL", "ST", "HT", "DX", "IQ", "INVENTORY",
                 "EQUIPMENT", "SKILL_INDEX_TONGSOL", "SKILL_INDEX_SUMMON", "SKILL_INDEX_RIDING", "SKILL_GRADE_MASTER",
                 "SKILL_GRADE_GRAND_MASTER", "SKILL_GRADE_PERFECT_MASTER", "METIN_SOCKET_TYPE_NONE",
                 "METIN_SOCKET_TYPE_SILVER", "METIN_SOCKET_TYPE_GOLD", "SKILL_GRADE_COUNT"):
        if name in module_constants()["player"]:
            setattr(player, name, module_constants()["player"][name])
    for name, value in module_constants()["skill"].items():
        setattr(skill, name, value)
    item_max = module_constants()["item"]
    socket_max = module_constants()["player"].get("METIN_SOCKET_MAX_NUM", 3)
    attr_max = module_constants()["player"].get("ATTRIBUTE_SLOT_MAX_NUM", 7)

    def select(vnum):
        data.selected = int(vnum)
        item.selected[0] = int(vnum)

    def size():
        value = data.row().get("size", (1, 1))
        return tuple(value) if isinstance(value, (list, tuple)) else (1, int(value or 1))

    def price(kind):
        value = data.row().get("price", 0)
        if isinstance(value, dict):
            return int(value.get(kind, 0))
        return int(value or 0) if kind == "buy" else int(value or 0) // 5

    define(item, "SelectItem", select)
    define(item, "GetItemName", lambda *vnum: data.row(vnum[0] if vnum else None).get("name", "item %d" % (vnum[0] if vnum else data.selected)))
    define(item, "GetItemType", data.kind)
    define(item, "GetItemSubType", data.subtype)
    define(item, "GetItemSize", size)
    define(item, "GetIconImageFileName", lambda: data.row().get("icon", "icon/item/%05d.tga" % data.selected))
    define(item, "GetItemDescription", lambda: data.row().get("desc", ""))
    define(item, "GetItemSummary", lambda: data.row().get("summary", ""))
    define(item, "GetValue", lambda i: int((list(data.row().get("values", ())) + [0] * 6)[i]))
    define(item, "GetAffect", lambda i: _pairs(data.row().get("applies"), "item", ("APPLY_",), item_max.get("ITEM_APPLY_MAX_NUM", 3))[i])
    define(item, "GetLimit", lambda i: _pairs(data.row().get("limits"), "item", ("LIMIT_",), item_max.get("LIMIT_MAX_NUM", 2))[i])
    define(item, "GetLimitType", lambda i: _pairs(data.row().get("limits"), "item", ("LIMIT_",), item_max.get("LIMIT_MAX_NUM", 2))[i][0])
    define(item, "GetLimitValue", lambda i: _pairs(data.row().get("limits"), "item", ("LIMIT_",), item_max.get("LIMIT_MAX_NUM", 2))[i][1])
    define(item, "IsAntiFlag", lambda flag: bool(_flags(data.row().get("antiflags", 0), "item", ("ITEM_ANTIFLAG_",)) & flag))
    define(item, "IsFlag", lambda flag: bool(_flags(data.row().get("flags", 0), "item", ("ITEM_FLAG_",)) & flag))
    define(item, "IsWearableFlag", lambda flag: bool(_flags(data.row().get("wear", 0), "item", ("WEARABLE_",)) & flag))
    define(item, "GetUseType", data.use_type)
    define(item, "IsEquipmentVID", lambda vnum: data.kind(vnum) in (item_max.get("ITEM_TYPE_WEAPON"), item_max.get("ITEM_TYPE_ARMOR")))
    define(item, "GetISellItemPrice", lambda: price("sell"))
    define(item, "GetIBuyItemPrice", lambda: price("buy"))
    define(item, "Is1GoldItem", lambda: bool(_flags(data.row().get("flags", 0), "item", ("ITEM_FLAG_",))
                                              & item_max.get("ITEM_FLAG_COUNT_PER_1GOLD", 8)))

    def case_item(*at):
        position = at[-1] if at else 0
        return data.case.get("items", {}).get(position)

    def socket(*at):
        held = case_item(*at[:-1])
        values = list(held["sockets"]) if held is not None else []
        return int((values + [0] * socket_max)[at[-1]])

    def attribute(*at):
        held = case_item(*at[:-1])
        values = [tuple(a) for a in held["attrs"]] if held is not None else []
        return (values + [(0, 0)] * attr_max)[at[-1]]

    status = {"LEVEL": "level", "ST": "st", "HT": "ht", "DX": "dx", "IQ": "iq"}
    status_keys = dict((module_constants()["player"].get(k, -1), v) for k, v in status.items())

    define(player, "GetItemIndex", lambda *at: (case_item(*at) or {}).get("vnum", 0))
    define(player, "GetItemCount", lambda *at: (case_item(*at) or {}).get("count", 0))
    define(player, "GetItemMetinSocket", socket)
    define(player, "GetItemAttribute", attribute)
    define(player, "GetStatus", lambda kind: int(data.case.get("player", {}).get(status_keys.get(kind, ""), 0)))
    define(player, "GetRace", lambda: int(data.case.get("player", {}).get("race", 0)))
    define(player, "IsEquipmentSlot", lambda pos: 90 <= pos < 122)
    define(player, "GetISellItemPrice", lambda *at: int((case_item(*at) or {}).get("sell_price", 0)))
    skill_state = lambda: data.case.get("skill", {})
    define(player, "GetSkillSlotIndex", lambda index: int(skill_state().get("slot", 0)))
    define(player, "GetSkillLevel", lambda slot: int(skill_state().get("level", 0)))
    define(player, "GetSkillGrade", lambda slot: int(skill_state().get("grade", 0)))
    define(player, "GetSkillCurrentEfficientPercentage", lambda slot: float(skill_state().get("efficient", 0.0)))
    define(player, "GetSkillNextEfficientPercentage", lambda slot: float(skill_state().get("next", 0.0)))

    chr_module = modules["chr"]
    define(chr_module, "RaceToJob", lambda race: race % 4)
    define(chr_module, "RaceToSex", lambda race: 1 if race in (0, 2, 5, 7) else 0)
    define(modules["nonplayer"], "GetMonsterName", lambda vnum: data.mobs.get(int(vnum), "mob %d" % vnum))
    define(modules["background"], "GlobalPositionToMapInfo", lambda x, y: ("metin2_map_a1", x, y))

    shop_state = lambda: data.case.get("shop", {})
    shop = modules["shop"]
    define(shop, "IsOpen", lambda: bool(shop_state().get("open", False)))
    define(shop, "IsPrivateShop", lambda: bool(shop_state().get("private", False)))
    define(shop, "GetItemID", lambda slot: (case_item(slot) or {}).get("vnum", 0))
    define(shop, "GetItemMetinSocket", lambda slot, i: socket(slot, i))
    define(shop, "GetItemAttribute", lambda slot, i: attribute(slot, i))
    define(shop, "GetItemPrice", lambda slot: int(shop_state().get("price", 0)))
    define(shop, "GetPrivateShopItemPrice", lambda kind, pos: int(shop_state().get("price", 0)))
    for name in ("exchange", "safebox", "grpText"):
        if name not in modules:
            game.put(name, Recording(name, game.log))
    exchange = modules["exchange"]
    for side in ("Self", "Target"):
        define(exchange, "GetItemVnumFrom" + side, lambda slot: (case_item(slot) or {}).get("vnum", 0))
        define(exchange, "GetItemMetinSocketFrom" + side, lambda slot, i: socket(slot, i))
        define(exchange, "GetItemAttributeFrom" + side, lambda slot, i: attribute(slot, i))
    safebox = modules["safebox"]
    for prefix in ("", "Mall"):
        define(safebox, "Get%sItemID" % prefix, lambda slot: (case_item(slot) or {}).get("vnum", 0))
        define(safebox, "Get%sItemMetinSocket" % prefix, lambda slot, i: socket(slot, i))
        define(safebox, "Get%sItemAttribute" % prefix, lambda slot, i: attribute(slot, i))
    define(safebox, "GetItemFlags", lambda slot: int((case_item(slot) or {}).get("flags", 0)))

    def skill_row(index):
        return data.skills.get(int(index), {})

    def listed(key):
        return lambda index, i, *rest: (list(skill_row(index).get(key, ())) + [""] * (i + 1))[i]
    define(skill, "GetSkillName", lambda index, grade=0: (lambda names: names[min(grade, len(names) - 1)] if isinstance(names, list) and names else names)(skill_row(index).get("name", "skill %d" % index)))
    define(skill, "GetSkillDescription", lambda index: skill_row(index).get("desc", ""))
    define(skill, "GetSkillType", lambda index: int(skill_row(index).get("type", 1)))
    define(skill, "GetSkillMaxLevel", lambda index: int(skill_row(index).get("max_level", 40)))
    define(skill, "GetSkillLevelLimit", lambda index: int(skill_row(index).get("level_limit", 0)))
    define(skill, "GetSkillAffectDescriptionCount", lambda index: len(skill_row(index).get("affects", ())))
    define(skill, "GetSkillAffectDescription", listed("affects"))
    define(skill, "GetSkillConditionDescriptionCount", lambda index: len(skill_row(index).get("conditions", ())))
    define(skill, "GetSkillConditionDescription", listed("conditions"))
    define(skill, "GetSkillNeedSP", lambda index, level: int(skill_row(index).get("need_sp", 0)))
    define(skill, "GetSkillContinuationSP", lambda index, level: int(skill_row(index).get("continuation_sp", 0)))
    define(skill, "GetSkillCoolTime", lambda index, level: int(skill_row(index).get("cool_time", 0)))
    define(skill, "GetDuration", lambda index, level: int(skill_row(index).get("duration", 0)))
    define(skill, "IsUseHPSkill", lambda index: bool(skill_row(index).get("use_hp", False)))
    define(skill, "IsSkillRequirement", lambda index: bool(skill_row(index).get("requirement")))
    define(skill, "GetSkillRequirementData", lambda index: tuple(skill_row(index).get("requirement", ("", 0, 0))))
    define(skill, "GetSkillRequireStatCount", lambda index: len(skill_row(index).get("require_stats", ())))
    define(skill, "GetSkillRequireStatData", lambda index, i: tuple(skill_row(index).get("require_stats", ())[i]))
    define(skill, "CheckRequirementSueccess", lambda index: bool(skill_row(index).get("requirement_met", True)))
    define(skill, "GetNewAffectDataCount", lambda index: len(skill_row(index).get("new_affects", ())))
    define(skill, "GetNewAffectData", lambda index, i, level: tuple(skill_row(index).get("new_affects", ())[i]))
    return data


def apply_case(game, case):
    """Puts a corpus case's state into the stand-ins of install_item_data:
    its item (vnum, count, sockets, attrs) at `pos` (0 by default) for every
    context's getters, the player's status and race, the clock
    (app.GetGlobalTimeStamp), the shop's state and the skill's."""
    data = game.item_data
    position = int(case.get("pos", 0))
    held = {"vnum": int(case.get("vnum", 0)), "count": int(case.get("count", 1)),
            "sockets": list(case.get("sockets", ())), "attrs": [tuple(a) for a in case.get("attrs", ())],
            "flags": int(case.get("flags", 0)), "sell_price": int(case.get("sell_price", 0))}
    data.case = dict(case)
    data.case["items"] = {position: held}
    if case.get("clock") is not None:
        game.timestamp = int(case["clock"])
    return held


# The sizes of the images the tooltip rules load (the legacy art's own), for
# the tooltip ui stand-in: a socket frame is 32 x 32 (metin_slot_*.sub), an
# item or hair icon 32 x 32 (64 or 96 tall for 1x2 and 1x3 items); others
# answer TOOLTIP_IMAGE_SIZES.get(path, (32, 32)).
TOOLTIP_IMAGE_SIZES = {}
# The tooltip ui stand-in's text metric: TOOLTIP_CHAR_WIDTH px per visible
# character, TOOLTIP_LINE_HEIGHT px tall (one fixed metric, P14 spec 5.8).
TOOLTIP_CHAR_WIDTH = 6
TOOLTIP_LINE_HEIGHT = 12
LOCALE_ROOT = os.path.normpath(os.path.join(support.HERE, "..", "assets", "locale", "locale"))
LOCALE_FUNCTIONS = ("DO_YOU_SELL_ITEM", "DO_YOU_BUY_ITEM", "REFINE_FAILURE_CAN_NOT_ATTACH", "REFINE_FAILURE_NO_SOCKET",
                    "REFINE_FAILURE_NO_GOLD_SOCKET", "HOW_MANY_ITEM_DO_YOU_DROP", "NumberToMoneyString",
                    "NumberToSecondaryCoinString", "SecondToDHM", "SecondToHM", "RTSecondToDHMS")


def generate_color(r, g, b, a):
    """grp.GenerateColor as the client packs it (CGraphicBase::GetColor, a
    truncation to 0xAARRGGBB) and returns it, a signed C long: negative
    while the alpha's top bit is set (P14 spec D7)."""
    value = (int(a * 255) << 24) | (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)
    return value - (1 << 32) if value & 0x80000000 else value


def locale_info(locale="en"):
    """A localeInfo over the locale's real locale_game.txt, as localeinfo.py
    loads it (the SA, SNA, SAA and SAN entries functions), with localeinfo.py's
    own helpers (NumberToMoneyString, RTSecondToDHMS and the rest of
    LOCALE_FUNCTIONS). An unknown name is still its own name."""
    module = support.LocaleInfo(RegisterReloadCallback=lambda fn: None, UI_DEF_FONT="Tahoma:12",
                                MINIMAP_ZONE_NAME_DICT={})

    def typed(kind, text):
        if kind == "SNA":
            return lambda x=0: text
        return lambda x: text % x

    with open(os.path.join(LOCALE_ROOT, locale, "locale_game.txt"), encoding="utf-8", errors="replace") as handle:
        for line in handle.read().split("\n"):
            tokens = line.split("\t")
            if len(tokens) < 2:
                continue
            kind = tokens[2].strip() if len(tokens) >= 3 else ""
            module.__dict__[tokens[0]] = typed(kind, tokens[1]) if kind in ("SA", "SNA", "SAA", "SAN") else tokens[1]
    exec(compile(source_of("localeinfo.py", LOCALE_FUNCTIONS), "localeinfo.py", "exec"), module.__dict__)
    return module


def install_tooltip_ui(game, locale="en"):
    """What uitooltip.py's widgets and strings need in plain CPython (P14
    spec 5.8): ui.ThinBoard, TextLine, ImageBox and Line with legacy
    geometry (positions, sizes, parents, shown state; a text line's size by
    one fixed metric, TOOLTIP_CHAR_WIDTH per visible character and
    TOOLTIP_LINE_HEIGHT; an image's size from TOOLTIP_IMAGE_SIZES),
    grp.GenerateColor as the client packs it, and localeInfo over the
    locale's real strings (locale_info). Each widget keeps what it was told
    (text, color, outline, feather, alignment, image, the order it was made
    in: `seq`) for the parity test's legacy side."""
    ui = game.modules["ui"]
    counter = [0]

    class Widget(object):
        def __init__(self, layer="UI"):
            counter[0] += 1
            self.seq = counter[0]
            self.layer = layer
            self.parent = None
            self.position = (0, 0)
            self.size = (0, 0)
            self.shown = False
            self.flags = set()
            self.window_align = ""

        def SetParent(self, parent):
            self.parent = parent

        def GetParentProxy(self):
            return None

        def SetPosition(self, x, y):
            self.position = (int(x), int(y))

        def GetLocalPosition(self):
            return self.position

        def GetGlobalPosition(self):
            x, y = self.position
            if self.parent is not None and hasattr(self.parent, "GetGlobalPosition"):
                px, py = self.parent.GetGlobalPosition()
                x, y = x + px, y + py
            return (x, y)

        def SetSize(self, width, height):
            self.size = (int(width), int(height))

        def GetWidth(self):
            return self.size[0]

        def GetHeight(self):
            return self.size[1]

        def Show(self):
            self.shown = True

        def Hide(self):
            self.shown = False

        def IsShow(self):
            return self.shown

        def SetTop(self):
            pass

        def AddFlag(self, flag):
            self.flags.add(flag)

        def SetWindowHorizontalAlignCenter(self):
            self.window_align = "center"

        def SetWindowHorizontalAlignRight(self):
            self.window_align = "right"

        def SetWindowVerticalAlignCenter(self):
            pass

        def Destroy(self):
            pass

        def __del__(self):
            pass

    class ThinBoard(Widget):
        def __init__(self, layer="UI"):
            Widget.__init__(self, layer)

    class TextLine(Widget):
        def __init__(self, layer="UI"):
            Widget.__init__(self, layer)
            self.text = ""
            self.font = ""
            self.color = None
            self.outline = False
            self.feather = True
            self.align = "left"

        def SetFontName(self, name):
            self.font = name

        def SetText(self, text):
            self.text = text

        def GetText(self):
            return self.text

        def SetPackedFontColor(self, color):
            self.color = int(color) & 0xFFFFFFFF

        def SetFontColor(self, r, g, b):
            self.color = generate_color(r, g, b, 1.0) & 0xFFFFFFFF

        def SetOutline(self, flag=True):
            self.outline = bool(flag)

        def SetFeather(self, flag=True):
            self.feather = bool(flag)

        def SetHorizontalAlignCenter(self):
            self.align = "center"

        def SetHorizontalAlignRight(self):
            self.align = "right"

        def SetHorizontalAlignLeft(self):
            self.align = "left"

        def GetTextSize(self):
            import nui_text
            return (TOOLTIP_CHAR_WIDTH * len(nui_text.visible_text(self.text or "")), TOOLTIP_LINE_HEIGHT)

    class ImageBox(Widget):
        def __init__(self, layer="UI"):
            Widget.__init__(self, layer)
            self.image = ""

        def LoadImage(self, path):
            self.image = path
            self.size = TOOLTIP_IMAGE_SIZES.get(path, (32, 32))

    class Line(Widget):
        def __init__(self, layer="UI"):
            Widget.__init__(self, layer)
            self.color = None

        def SetColor(self, color):
            self.color = int(color) & 0xFFFFFFFF

    ui.ThinBoard = ThinBoard
    ui.TextLine = TextLine
    ui.ImageBox = ImageBox
    ui.ExpandedImageBox = ImageBox
    ui.Line = Line
    ui.TooltipWidget = Widget
    define(game.modules["grp"], "GenerateColor", generate_color)
    game.put("localeInfo", locale_info(locale))
    return ui
