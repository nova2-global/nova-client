"""Tests for the legacy offline shop windows (wave 5, chunk Y2; NOVA-9): python3 -B -m unittest
offline_shop_test (from tools/).

The C++ half (the shop module's offline state and getters, the net senders, the
callbacks) is chunk C's, in nova-client-src's userinterface_tests; Y1 owns the
glue (game.py, interfacemodule.py) and the locale files. Here the legacy windows
run over the Wave 4 stand-ins (nui_w4_world's World, every NovaUI window off)
with what the protocol 6 client gives them, installed by install_wave5:
- K's shop.OFFLINE_SHOP_* constants (nova-client-src 9d49ac2b, GameType.h:164-230,
  PythonShop.cpp; k-report.md 5.1: not in tools/fixtures/module_constants.json);
- shop's offline getters (k-report.md 5.3) answering from World.shop, net's senders
  recorded (the Recording module), player's premium perk;
- the wave 5 locale keys (WAVE5_GAME_KEYS, WAVE5_INTERFACE_KEYS: OLD's keys and the
  Y1/Y2 contract's), over NEW's en strings;
- the ui.py and uicommon.py widgets the windows build (CheckBox, ThinBoard2,
  ShopDecoTitle, ScrollWindow, BulkMoneyInputDialog, CheckQuestionDialog), as
  recording stand-ins (ui.py's own classes are tested over the real ui.py in
  RealWidgets).
The windows are driven directly, and through stand-in glue that calls them as the
Y1/Y2 contract's table says (Glue). Spec: 5-spec-v2.md 3.8, 3.10 "Python"."""
import ast
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402

ROOT = support.ROOT
UISCRIPT = os.path.join(os.path.dirname(ROOT), "uiscript", "uiscript")
LOCALE = os.path.join(os.path.dirname(ROOT), "locale", "locale")
P = support.module_constants()["player"]
INVENTORY = P["INVENTORY"]

# K's values, generated from this client's PythonShop.cpp and GameType.h.
SHOP_CONSTANTS = support.module_constants()["shop"]
K_SHOP_GEOMETRY = dict((name, SHOP_CONSTANTS[name]) for name in
                       ("OFFLINE_SHOP_COLUMNS", "OFFLINE_SHOP_ROWS_PER_PAGE", "OFFLINE_SHOP_PAGE_COUNT",
                        "OFFLINE_SHOP_SLOT_MAX", "OFFLINE_SHOP_SIGN_STYLE_MAX"))
K_RESULTS = ("OK", "DISABLED", "MAP_NOT_ALLOWED", "CHANNEL_NOT_ALLOWED", "TOO_CLOSE", "NOT_ENOUGH_GOLD", "BAD_PRICE",
             "GOLD_CAP", "BAD_SIGN", "BAD_DECORATION", "ITEM_RESTRICTED", "BAD_SLOT", "SLOT_TAKEN", "SLOT_LOCKED",
             "ALREADY_OPEN", "NO_SHOP", "BUSY", "QUEST_RUNNING", "NOT_LOCKED", "RATE_LIMITED", "INVENTORY_FULL",
             "OWNER_GOLD_MAX", "EMPTY_SHOP", "EXPIRED", "EXTEND_CAP", "MAX_KITS", "NEED_KIT", "NOT_AT_SHOP", "SOLD_OUT",
             "PREMIUM_REQUIRED", "COOLDOWN", "SEARCH_MAP_DENIED", "TIMEOUT", "UNREACHABLE", "NOTHING_HELD",
             "OTHER_CHANNEL", "TRANSFER_LOST")
K_LOG_ACTIONS = ("OPEN", "CLOSE", "LOCK", "UNLOCK", "ADD_TIME", "ITEM_SOLD", "ITEM_INPUT", "ITEM_WITHDRAW",
                 "GOLD_WITHDRAW", "PRICE_UPDATE", "ITEM_REMOVE", "ITEM_MOVE")
# GC RESULT's op: K's EOfflineShopCG (k-report.md 5.1, offline_shop_packets.h:146), which the exe exports as
# shop.OFFLINE_SHOP_OP_<NAME> 0-16 (C: reports/c.md 3.3).
K_OPS = ("CREATE", "MANAGE", "CLOSE", "LOCK", "SIGN", "WITHDRAW_GOLD", "WITHDRAW_ITEM", "ADD_ITEM", "PRICE", "REMOVE",
         "MOVE", "EXPAND", "EXTEND", "LOGS", "WARP", "BUY", "LEAVE")
# player.PREMIUM_PERK_SEARCH_BUY (K: PythonPlayerModule.cpp:2739-2753, c_Premium_Perk_Search_Buy 4).
K_PERK_SEARCH_BUY = 4
# The server's code defaults (spec 5.2), as CONFIG carries them (TOfflineShopConfigInfo's names).
CONFIG = {"enabled": 1, "base_rows": 8, "rows_per_kit": 1, "max_kits": 16, "kit_vnum": 72350, "deco_vnum": 69500,
          "open_cost": 10000000, "renew_cost": 10000000, "duration_sec": 345600, "extend_price_per_day": 2500000,
          "extend_cap_days": 15, "tax_permille": 0, "max_gold": 9999999999999, "search_cooldown_ms": 1000,
          "model_count": 8, "models": [30000, 30002, 30003, 30004, 30005, 30006, 30007, 30008], "style_count": 6}
DAY = 86400
KIT, DECO = 72350, 69500
SWORD, POTION = 19, 27001

# The locale keys the Y2 windows use beyond NEW's own (the Y1/Y2 contract; Y1 writes them). Each is OLD's
# (OLD locale/en/locale_game.txt, locale_interface.txt) or a key the contract names; the texts are OLD's or
# the spec's. localeInfo (locale_game.txt):
WAVE5_GAME_KEYS = {
    # OLD's
    "SEARCH_SHOP_WAIT": "You need to wait 1 second between searches.",
    "SEARCH_SHOP_WRONG_NAME": "No results found for this item name.",
    "DECORATION_REQUIRES_SCROLL": "You need a decoration scroll.",
    "SEARCH_SHOP_GOLD": "Total Gold",
    "SEARCH_SHOP_PREMIMUM_STATUS": "Premium Status",
    "SEARCH_SHOP_PREMIMUM_ACTIVE": "Active",
    "SEARCH_SHOP_PREMIMUM_INACTIVE": "Inactive",
    "REQUIRED_PREMIUM_USER": "You need to be a premium user to buy from search shop.",
    # the contract's
    "OFFLINE_SHOP_SLOT_PENDING": "This item is held for a transfer.",
    "OFFLINE_SHOP_BULK_ADD": "Bulk add",
    "MYSHOP_DECO_STEP_TITLE": "Select title",
    "MYSHOP_DECO_STEP_MODEL": "Model",
    "SEARCH_SHOP_IN_STOCK": "In Stock: %s",
    "SEARCH_SHOP_FOLLOW_SIGNAL": "Follow the signal on the map, it will lead to the shop",
    "SEARCH_SHOP_OTHER_MAP": "You are in a different map, do you want to teleport?",
}
for _name in ("ALL", "WEAPONS", "EQUIPMENTS", "VOUCHERS", "COSTUMES", "CHANGERS", "STONES", "CHESTS", "ITEMS",
              "MATERIALS", "ORES", "PETS", "MOUNTS"):
    WAVE5_GAME_KEYS["SEARCH_SHOP_CAT_" + _name] = _name.title()
for _name in ("BODY", "HAIR", "WEAPON", "WING", "FACIAL", "SASH", "BODY_EFFECT", "WEAPON_EFFECT"):
    WAVE5_GAME_KEYS["SEARCH_SHOP_COSTUME_" + _name] = _name.title()
for _index, _name in enumerate(K_RESULTS):
    WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_" + _name] = "Result %s." % _name
# The codes whose text takes the result's arg (spec 1.1, 3.4): the channel, the delivery id.
WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_OTHER_CHANNEL"] = "The shop is on channel %s."
WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_TRANSFER_LOST"] = "A transfer was lost (delivery %s). Contact support."
for _index, _name in enumerate(K_LOG_ACTIONS):
    WAVE5_GAME_KEYS["OFFLINE_SHOP_LOG_ACTION_%d" % _index] = _name.title()
# uiScriptLocale (locale_interface.txt), all OLD's:
WAVE5_INTERFACE_KEYS = {
    "MYSHOP_DECO_CANCEL": "Close", "MYSHOP_DECO_DEFAULT": "Default", "MYSHOP_DECO_NEXT": "Next",
    "MYSHOP_DECO_OK": "Confirm", "MYSHOP_DECO_PREV": "Back", "MYSHOP_DECO_SELECT_MODEL": "Choose your shop's appearance.",
    "MYSHOP_DECO_SELECT_TITLE": "Choose your name's appearance.", "OFFLINE_SHOP_TITLE": "Open offline shop",
    "OFFLINE_SHOP_BUTTON_LOCK": "Lock", "OFFLINE_SHOP_BUTTON_UNLOCK": "Unlock", "OFFLINE_SHOP_BUTTON_RENEW": "Renew",
    "OFFLINE_SHOP_BUTTON_RENAME": "Rename", "OFFLINE_SHOP_BUTTON_CLOSE": "Close",
    "OFFLINE_SHOP_INPUT_SIGN_TITLE": "Change Shop Sign", "OFFLINE_SHOP_INPUT_SIGN_DESC": "Shop Name: %s",
    # The contract's one %s: localeInfo.NumberToMoneyString(CONFIG's renew_cost), which carries the unit.
    "OFFLINE_SHOP_RENEW_CONFIRM": "Renewal of the shop will cost %s.",
    "OFFLINE_SHOP_TIME_LEFT": "%d Day %02d Hour %02d Min", "SEARCH_SHOP_TITLE": "Search shop",
    "SEARCH_SHOP_BUY_CONFIGM": "Do you want to buy this item?", "SEARCH_SHOP_BOOKMARK_EMPTY": "Empty",
    "SEARCH_SHOP_BOOKMARK_FULL": "No empty slots to bookmark a search.", "SEARCH_SHOP_BOOKMARKS": "Bookmarks",
    "SEARCH_SHOP_FAVOURITES": "Favourites", "SEARCH_SHOP_SORT_UP": "Descending", "SEARCH_SHOP_SORT_DOWN": "Ascending",
    "SEARCH_SHOP_FILTER_CATEGORY": "Filter", "OFFLINE_SHOP_LOCATION": "Shop Location: ",
    "OFFLINE_SHOP_BUTTON_TELEPORT": "Teleport", "OFFLINE_SHOP_BUTTON_WITHDRAW": "Withdraw",
    "OFFLINE_SHOP_BUTTON_ADD_TIME": "Add Time", "OFFLINE_SHOP_BUTTON_VIEW_LOGS": "View Logs",
    "OFFLINE_SHOP_TEXT_EXPIRE_IN": "Shop expires in:",
    "OFFLINE_SHOP_TIME_EXCEED": "Your shop time have exceeded the limit, you can only have total of %d days",
    "OFFLINE_SHOP_NO_YANG": "You do not have any yang to withdraw!", "OFFLINE_SHOP_CHANGE_PRICE_TITLE": "Change Price",
    "OFFLINE_SHOP_CHANGE_PRICE_ALL": "Apply to all identical items",
    "OFFLINE_SHOP_CHANGE_PRICE_LOCKED": "You must lock your shop to change prices.",
    "OFFLINE_SHOP_REMOVE_ITEM_CONFIRM": 'Remove "%s" from shop?', "OFFLINE_SHOP_REMOVE_ITEM_ALL": "Remove all identical items",
    "OFFLINE_SHOP_REMOVE_ITEM_LOCKED": "You must lock your shop to remove items.", "OFFLINE_SHOP_PAGE_BUTTON": "Page %d",
    "OFFLINE_SHOP_EXPAND_BUTTON": "Expand Shop",
    "OFFLINE_SHOP_EXPAND_NO_ITEM": "You don't have the required item to expand your shop.",
    "OFFLINE_SHOP_EXPAND_ROW_CONFIRM": "Use %s to expand shop?",
}
# OLD's keys among them (OLD locale/en files), the rest are the contract's new keys.
OLD_GAME_KEYS = {"SEARCH_SHOP_WAIT", "SEARCH_SHOP_WRONG_NAME", "DECORATION_REQUIRES_SCROLL", "SEARCH_SHOP_GOLD",
                 "SEARCH_SHOP_PREMIMUM_STATUS", "SEARCH_SHOP_PREMIMUM_ACTIVE", "SEARCH_SHOP_PREMIMUM_INACTIVE",
                 "REQUIRED_PREMIUM_USER"} | {k for k in WAVE5_GAME_KEYS if k.startswith(("SEARCH_SHOP_CAT_", "SEARCH_SHOP_COSTUME_"))}
CONTRACT_GAME_KEYS = ({"OFFLINE_SHOP_SLOT_PENDING", "OFFLINE_SHOP_BULK_ADD", "MYSHOP_DECO_STEP_TITLE", "MYSHOP_DECO_STEP_MODEL",
                       "SEARCH_SHOP_IN_STOCK", "SEARCH_SHOP_FOLLOW_SIGNAL", "SEARCH_SHOP_OTHER_MAP"}
                      | {"OFFLINE_SHOP_RESULT_" + name for name in K_RESULTS}
                      | {"OFFLINE_SHOP_LOG_ACTION_%d" % i for i in range(12)})
# Y2's modules, by the names interfacemodule.py (Y1) imports them.
Y2_MODULES = (("offlineshopconst", "offlineshopconst.py"), ("itemPrices", "itemprices.py"), ("uiShop", "uishop.py"),
              ("uiPrivateShopBuilder", "uiprivateshopbuilder.py"), ("uiMyShopDecoration", "uimyshopdecoration.py"),
              ("uiOfflineShopLog", "uiofflineshoplog.py"), ("uiSearchShop", "uisearchshop.py"))


def read_locale_file(locale, name):
    keys = {}
    path = os.path.join(LOCALE, locale, name)
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle.read().split("\n"):
            tokens = line.split("\t")
            if len(tokens) >= 2 and tokens[0]:
                keys[tokens[0]] = tokens[1]
    return keys


class StrictLocale(types.ModuleType):
    """A locale module over NEW's en strings and the wave 5 keys; a name that is neither raises
    AttributeError, so a window that reads an unknown key fails its test."""

    def __init__(self, name, values):
        types.ModuleType.__init__(self, name)
        self.__dict__.update(values)


def strict_locale_info(game):
    base = support.locale_info("en")
    values = dict((k, v) for k, v in base.__dict__.items() if not k.startswith("__"))
    values.update(WAVE5_GAME_KEYS)
    return StrictLocale("localeInfo", values)


def strict_ui_script_locale():
    values = read_locale_file("en", "locale_interface.txt")
    values.update(WAVE5_INTERFACE_KEYS)
    values["LOCALE_UISCRIPT_PATH"] = "locale/en/ui/"
    return StrictLocale("uiScriptLocale", values)


def client_open():
    """assets/root/system.py's own `open`, which the client installs as builtins.open (system.py:146-155):
    (filename, mode) only, the real open behind it, over a pack that holds no such file. A patch of
    builtins.open for a with block."""
    namespace = {"pack": types.SimpleNamespace(Exist=lambda name: False), "pack_file": None, "old_open": open}
    exec(compile(support.source_of("system.py", ("open",)), "system.py", "exec"), namespace)
    return mock.patch("builtins.open", namespace["open"])


class GeometryWndMgr(lf.AnyCall):
    """wndMgr for the real ui.py that keeps each window's size, position and shown state under a handle
    of its own (AnyCall alone answers 0 for every one of them), so a layout of real widgets reads back."""

    def __init__(self):
        lf.AnyCall.__init__(self, "wndMgr")
        self.handles = 0
        self.sizes = {}
        self.positions = {}
        self.shown = set()

    def __getattr__(self, name):
        if name.startswith("Register"):
            return self.register
        return lf.AnyCall.__getattr__(self, name)

    def register(self, *args):
        self.handles += 1
        return self.handles

    def SetWindowSize(self, handle, width, height):
        self.sizes[handle] = (int(width), int(height))

    def GetWindowWidth(self, handle):
        return self.sizes.get(handle, (0, 0))[0]

    def GetWindowHeight(self, handle):
        return self.sizes.get(handle, (0, 0))[1]

    def SetWindowPosition(self, handle, x, y):
        self.positions[handle] = (int(x), int(y))

    def GetWindowLocalPosition(self, handle):
        return self.positions.get(handle, (0, 0))

    def GetWindowGlobalPosition(self, handle):
        return self.positions.get(handle, (0, 0))

    def Show(self, handle):
        self.shown.add(handle)

    def Hide(self, handle):
        self.shown.discard(handle)

    def IsShow(self, handle):
        return handle in self.shown

    def GetTextSize(self, handle):
        return (40, 12)


def _real_function(file_name, names, name):
    """A root module's function `name`, with the top-level definitions `names` it needs."""
    import re
    namespace = {"re": re}
    exec(compile(support.source_of(file_name, names), file_name, "exec"), namespace)
    return namespace[name]


def install_wave5(world):
    """What the protocol 6 exe and the wave 5 ui.py / uicommon.py give the Y2 windows (the module
    docstring), on world.game's stand-ins; the offline state lives in world.shop."""
    game = world.game
    modules = game.modules
    log = game.log
    shop_state = world.shop

    shop = modules["shop"]
    for name, value in K_SHOP_GEOMETRY.items():
        setattr(shop, name, value)
    for name in K_RESULTS:
        setattr(shop, "OFFLINE_SHOP_RESULT_" + name, SHOP_CONSTANTS["OFFLINE_SHOP_RESULT_" + name])
    for name in K_LOG_ACTIONS:
        setattr(shop, "OFFLINE_SHOP_LOG_ACTION_" + name, SHOP_CONSTANTS["OFFLINE_SHOP_LOG_ACTION_" + name])
    for value, name in enumerate(K_OPS):
        setattr(shop, "OFFLINE_SHOP_OP_" + name, value)

    def listed(slot):
        return shop_state["items"].get(int(slot))

    def field(slot, key, default=0):
        found = listed(slot)
        return found.get(key, default) if found else default
    support.define(shop, "GetConfig", lambda: dict(shop_state["config"], models=list(shop_state["config"]["models"])))
    support.define(shop, "IsOwner", lambda: int(shop_state["owner"]))
    support.define(shop, "IsLocked", lambda: int(shop_state["locked"]))
    support.define(shop, "GetGoldAmount", lambda: shop_state["gold"])
    support.define(shop, "GetOfflineShopPageCount", lambda: shop_state["pages"])
    support.define(shop, "GetOfflineShopExpandCount", lambda: shop_state["kits"])
    support.define(shop, "GetOfflineShopSlotCount", lambda: shop_state["unlocked"])
    support.define(shop, "GetOfflineShopItemID", lambda slot: field(slot, "vnum"))
    support.define(shop, "GetOfflineShopItemCount", lambda slot: field(slot, "count"))
    support.define(shop, "GetOfflineShopItemPrice", lambda slot: field(slot, "price"))
    support.define(shop, "GetOfflineShopItemMetinSocket", lambda slot, j: (list(field(slot, "sockets", ())) + [0] * 4)[j])
    support.define(shop, "GetOfflineShopItemAttribute", lambda slot, j: (list(field(slot, "attrs", ())) + [(0, 0)] * 7)[j])
    support.define(shop, "IsOfflineShopSlotPending", lambda slot: bool(field(slot, "pending", False)))
    support.define(shop, "IsOfflineShopModel", lambda vnum: vnum in shop_state["config"]["models"])
    # Not named by K or the spec (Y2's report): the owner panel MANAGE stored and a listed item's own id.
    support.define(shop, "GetOfflineShopInfo", lambda: dict(shop_state["info"]))
    support.define(shop, "GetOfflineShopItemUniqueID", lambda slot: field(slot, "id"))

    player = modules["player"]
    player.PREMIUM_PERK_SEARCH_BUY = K_PERK_SEARCH_BUY
    support.define(player, "HasPremiumPerk", lambda perk: perk in world.perks)
    support.define(player, "GetItemCountByVnum", lambda vnum: world.counts.get(vnum, 0))
    support.define(player, "GetElk", lambda: world.elk)
    support.define(player, "GetTargetVID", lambda: 0)
    support.define(player, "GetCharacterDistance", lambda vid: world.distances.get(vid))
    support.define(player, "GetItemIndex", lambda *at: (game.items.get(at if len(at) > 1 else at[0]) or {}).get("vnum", 0))
    support.define(player, "GetItemCount", lambda *at: (game.items.get(at if len(at) > 1 else at[0]) or {}).get("count", 0))
    chr_module = modules["chr"]
    support.define(chr_module, "Pick", lambda: 0)

    item = modules["item"]
    support.define(item, "GetItemName", lambda: "item %d" % world.selected[0])
    base_select = getattr(item, "SelectItem")

    def select(vnum):
        world.selected[0] = vnum
        return base_select(vnum)
    item.SelectItem = select

    background = types.ModuleType("background")
    background.GetCurrentMapName = lambda: world.map_name
    background.GlobalPositionToMapInfo = lambda x, y: ("metin2_map_a1", 0, 0)
    game.put("background", background)

    search = support.Recording("searchShop", log)
    world.search = search
    search._answers.update({"Find": lambda name: list(world.index.get(name, ())),
                            "AutoComplete": lambda query, count: [(n, v[0]) for n, v in sorted(world.index.items())
                                                                  if query.lower() in n.lower()][:count],
                            "GetPage": world.search_page,
                            "GetPriceColor": lambda price: 0xffc02221 if price > 5000000000 else 0xffb3977c})
    game.put("searchShop", search)

    game.put("localeInfo", strict_locale_info(game))
    game.put("uiScriptLocale", strict_ui_script_locale())

    pick = modules["uiPickMoney"]
    pick.ConvertTextToMoney = _real_function("uipickmoney.py", ("MONEY_SUFFIX_POWERS", "_MONEY_PATTERN", "ConvertTextToMoney"),
                                             "ConvertTextToMoney")
    # offlineshopconst.shop_deco() reads <locale path>/shop_deco.txt (the en client's).
    game.answer("app", "GetLocalePath", os.path.join(LOCALE, "en"))

    install_widgets(game)


def install_widgets(game):
    """The ui.py and uicommon.py classes wave 5 adds, as stand-ins that keep their state."""
    ui = game.modules["ui"]
    Window = ui.Window

    class Bar(Window):
        def __init__(self, layer="UI"):
            Window.__init__(self, layer)
            self.color = None
            self.size = (0, 0)
            self.position = (0, 0)
            self.onMouseLeftButtonUpEvent = None

        def SetColor(self, color):
            self.color = color

        def SetSize(self, width, height):
            self.size = (width, height)

        def SetPosition(self, x, y):
            self.position = (x, y)

        def SetOnMouseLeftButtonUpEvent(self, event):
            self.onMouseLeftButtonUpEvent = event

        def OnMouseLeftButtonUp(self):
            if self.onMouseLeftButtonUpEvent:
                self.onMouseLeftButtonUpEvent()

        def GetWidth(self):
            return self.size[0]

        def GetHeight(self):
            return self.size[1]

        def __getattr__(self, attr):
            # Every other setter of ui.Window does nothing here.
            if attr.startswith("Set") or attr in ("UpdateRect", "Lock", "Unlock"):
                return lambda *args: None
            raise AttributeError(attr)

    class Board(Bar):
        def __init__(self, *args):
            Bar.__init__(self)
            self.args = args

    class ThinBoard2(Board):
        def __init__(self, layer="UI"):
            Board.__init__(self)
            self.pattern = "new"

        def SetPattern(self, name):
            self.pattern = name

    class ShopDecoTitle(Board):
        def __init__(self, style, layer="UI"):
            Board.__init__(self)
            self.style = style

        def GetFontColor(self):
            return (1.0, 1.0, 1.0)

    class RenderTarget(Bar):
        """ui.RenderTarget (NOVA-137): the target it shows."""

        @staticmethod
        def IsAvailable():
            return True

        def __init__(self, layer="UI"):
            Bar.__init__(self, layer)
            self.target = None

        def SetRenderTarget(self, name):
            self.target = name

    class CheckBox(Bar):
        def __init__(self, layer="UI"):
            Bar.__init__(self, layer)
            self.checked = False
            self.text = ""

        def SetTextInfo(self, text):
            self.text = text

        def SetCheckStatus(self, flag):
            self.checked = bool(flag)

        def GetCheckStatus(self):
            return self.checked

    class ScrollWindow(Bar):
        def __init__(self, width, height, kind=0, layer="UI"):
            Bar.__init__(self, layer)
            self.content = None
            self.end_event = None
            self.scrolled_to_start = 0

        def SetContentWindow(self, window):
            self.content = window

        def SetOnEndScrollEvent(self, event):
            self.end_event = event

        def ScrollToStart(self):
            self.scrolled_to_start += 1

        def FitWidth(self, width):
            pass

        def AutoFitWidth(self):
            pass

        def OnContentWindowSizeChange(self):
            pass

        def reach_end(self):
            if self.end_event:
                self.end_event()

        def OnRunMouseWheel(self, length):
            return True

    class ListBox(Bar):
        def __init__(self, layer="UI"):
            Bar.__init__(self, layer)
            self.keys = []
            self.texts = []
            self.event = None
            self.selectedLine = -1

        def ClearItem(self):
            self.keys, self.texts, self.selectedLine = [], [], -1

        def InsertItem(self, key, text):
            self.keys.append(key)
            self.texts.append(text)

        def SetEvent(self, event):
            self.event = event

        def SelectItem(self, line):
            if 0 <= line < len(self.keys) and line != self.selectedLine:
                self.selectedLine = line
                self.event(self.keys[line], self.texts[line])

        def GetViewItemCount(self):
            return 13

        def press(self, line):
            """A click on a line, as ListBox.OnMouseLeftButtonUp selects it."""
            self.SelectItem(line)

    base_loader = ui.PythonScriptLoader

    def build(window, value):
        for child in value.get("children", ()) or ():
            if child.get("type") == "listbox":
                widget = ListBox()
                widget.name = child.get("name", "")
                window.ElementDictionary[widget.name] = widget
            build(window, child)

    class PythonScriptLoader(base_loader):
        """The Wave 4 loader, with the uiscripts' list boxes made as ListBox below."""

        def LoadScriptFile(self, window, path):
            base_loader.LoadScriptFile(self, window, path)
            build(window, support.read_uiscript(path))

    ui.PythonScriptLoader = PythonScriptLoader

    for name, cls in (("Bar", Bar), ("ThinBoard", Board), ("ThinBoard2", ThinBoard2), ("ShopDecoTitle", ShopDecoTitle),
                      ("CheckBox", CheckBox), ("ScrollWindow", ScrollWindow), ("CustomScrollBar", Bar),
                      ("ListBox", ListBox), ("RenderTarget", RenderTarget)):
        setattr(ui, name, cls)

    common = game.modules["uiCommon"]

    class CheckDialog(support.LegacyDialog):
        """uiCommon.BulkMoneyInputDialog and CheckQuestionDialog: the dialog and its check box."""

        def __init__(self, kind):
            support.LegacyDialog.__init__(self, game, "uiCommon", kind)
            self.text = ""
            self.checked = None
            self.check_text = None

        def SetValue(self, value):
            self.text = str(value)

        def GetText(self):
            return self.text

        def SetTitle(self, title):
            self.title = title

        def SetMaxLength(self, length):
            self.max_length = length

        def SetDescription(self, text):
            self.texts = [text]

        def SetBulkMode(self, text=None, checked=False):
            self.check_text = text if text is not None else game.modules["localeInfo"].OFFLINE_SHOP_BULK_ADD
            self.checked = bool(checked)

        def SetCheckBox(self, text, checked=False):
            self.SetBulkMode(text, checked)

        def IsBulkMode(self):
            return bool(self.checked)

        IsChecked = IsBulkMode

    common.BulkMoneyInputDialog = lambda: CheckDialog("BulkMoneyInputDialog")
    common.CheckQuestionDialog = lambda: CheckDialog("CheckQuestionDialog")
    for kind in ("QuestionDialog", "PopupDialog", "InputDialogWithDescription"):
        if not hasattr(common, kind) or kind == "InputDialogWithDescription":
            setattr(common, kind, (lambda kind=kind: CheckDialog(kind)))


class World(object):
    """A Wave 4 world (every NovaUI window off) with install_wave5 and Y2's modules loaded over it
    (each one only when its file exists, so a run on main's assets fails where a module is missing)."""

    def __init__(self, config=None):
        self.w4 = w4.World(False)
        game = self.game = self.w4.game
        self.shop = {"items": {}, "owner": False, "locked": False, "gold": 0, "pages": 1, "kits": 0, "unlocked": 80,
                     "config": dict(config or CONFIG),
                     "info": {"sign": "Bob's shop", "channel": 1, "map": 1, "x": 469300, "y": 964200,
                              "seconds_left": 4 * DAY, "kits": 0, "model_vnum": 30000, "style": 0, "gold": 0,
                              "locked": 0, "unlocked_slots": 80}}
        self.perks = set()
        self.counts = {}
        self.elk = 0
        self.distances = {}
        self.selected = [0]
        self.map_name = "metin2_map_a1"
        self.index = {}
        self.results = []
        install_wave5(self)
        self.loaded = {}
        with game, w4.quiet():
            for name, file_name in Y2_MODULES:
                if os.path.isfile(os.path.join(ROOT, file_name)):
                    self.loaded[name] = game.load(name, file_name)
        self.tooltip = self.w4.tooltip
        self.interface = FakeInterface(self)

    def search_page(self, page, per_page):
        """searchShop.GetPage over World.results (OLD's (rows, pages))."""
        if per_page <= 0 or not self.results:
            return ([], 0)
        pages = (len(self.results) + per_page - 1) // per_page
        page = max(0, min(page, pages - 1))
        return (list(self.results[page * per_page:(page + 1) * per_page]), pages)

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def m(self, name):
        if name in self.loaded:
            return self.loaded[name]
        if name in self.game.loaded:
            return self.game.loaded[name]
        raise AssertionError("assets/root has no %s" % name)

    def sent(self, prefix="net."):
        return [(name, args) for name, args in self.game.log if name.startswith(prefix)]

    def mark(self):
        return len(self.game.log)

    def since(self, mark, prefix="net."):
        return [(name, args) for name, args in self.game.log[mark:] if name.startswith(prefix)]

    def chat(self):
        return [args[1] for name, args in self.game.log if name == "chat.AppendChat"]

    def dialogs(self, kind=None):
        found = list(self.game.dialogs)
        if kind:
            found = [d for d in found if d._name.endswith("." + kind)]
        return found

    def list_item(self, slot, vnum, count=1, price=100, id=None, pending=False, sockets=(0, 0, 0, 0)):
        self.shop["items"][slot] = {"vnum": vnum, "count": count, "price": price, "id": id or 5000 + slot,
                                    "pending": pending, "sockets": list(sockets)}

    def shop_dialog(self):
        """Interface.dlgShop as __MakeDialogs makes it (LoadDialog, Hide), with the tooltip and the
        interface bound."""
        with self, w4.quiet():
            dialog = self.m("uiShop").ShopDialog()
            dialog.LoadDialog()
            dialog.Hide()
            dialog.SetItemToolTip(self.tooltip)
            dialog.BindInterface(self.interface)
        return dialog

    def builder(self):
        with self, w4.quiet():
            builder = self.m("uiPrivateShopBuilder").PrivateShopBuilder()
            builder.BindInterface(self.interface)
            builder.SetItemToolTip(self.tooltip)
        return builder


class FakeInterface(object):
    """The interface methods the Y2 windows may call (the Y1/Y2 contract), recorded."""

    def __init__(self, world):
        self.world = world
        self.calls = []
        self.privateShopAdvertisementBoardDict = {}
        self.onTopWindow = 0
        self.wndOfflineShopLog = None

    def SetOnTopWindow(self, window):
        self.onTopWindow = window

    def RefreshMarkInventoryBag(self):
        pass

    def OpenOfflineShopLog(self):
        self.calls.append(("OpenOfflineShopLog",))

    def OpenSearchShop(self, vnum=0):
        self.calls.append(("OpenSearchShop", vnum))

    def OpenWhisperDialog(self, name):
        self.calls.append(("OpenWhisperDialog", name))


def tooltip_calls(tooltip, name):
    return [call for call in tooltip.calls if call[0] == name] if hasattr(tooltip, "calls") else []


class Recorder(object):
    """Wraps an object's method to record its arguments."""

    def __init__(self, owner, name):
        self.calls = []
        base = getattr(owner, name)

        def call(*args):
            self.calls.append(args)
            return base(*args)
        setattr(owner, name, call)


def open_view(world, vid=7001, owner=False, pages=1, unlocked=80, locked=False):
    world.shop.update(owner=owner, pages=pages, unlocked=unlocked, locked=locked)
    dialog = world.shop_dialog()
    with world, w4.quiet():
        dialog.Open(vid, multiPage=True)
    return dialog


def open_panel(world, locked=True, seconds_left=4 * DAY, gold=0, from_npc=False, vid=7001):
    """The owner's panel: MANAGE open 1 (Interface.OpenOfflineShop), or the owner's VIEW at the NPC
    first (from_npc)."""
    world.shop.update(owner=True, locked=locked, gold=gold, pages=3)
    world.shop["info"].update(locked=int(locked), seconds_left=seconds_left, gold=gold)
    dialog = world.shop_dialog()
    with world, w4.quiet():
        if from_npc:
            dialog.Open(vid, multiPage=True)
        dialog.OpenOfflineShop(1)
    return dialog


class Constants(unittest.TestCase):
    def test_the_result_and_log_names_are_ks(self):
        world = World()
        const = world.m("offlineshopconst")
        self.assertEqual(tuple(const.RESULT_NAMES), K_RESULTS)
        self.assertEqual(tuple(const.LOG_ACTION_NAMES), K_LOG_ACTIONS)
        with world:
            self.assertEqual(const.result_name(36), "TRANSFER_LOST")
            self.assertEqual(const.result_name(0), "OK")
            self.assertEqual(const.result_name(99), "")

    def test_the_client_numbers_are_olds(self):
        const = World().m("offlineshopconst")
        self.assertEqual(const.BUY_CONFIRM_MIN_PRICE, 1000000000)
        self.assertEqual(const.SHOP_CLOSE_RANGE, 1000)
        self.assertEqual(const.SIGN_RANGE, 3000)
        self.assertEqual(const.SIGN_SEEN_MINUTES, 30)
        self.assertEqual((const.AUTOCOMPLETE_MIN_CHARS, const.AUTOCOMPLETE_COUNT), (3, 10))
        self.assertEqual(tuple(const.SEARCH_PAGE_SIZES), (25, 50, 100))
        self.assertEqual(const.SEARCH_BOOKMARK_MAX, 10)

    def test_the_geometry_is_the_shop_modules(self):
        world = World()
        with world:
            self.assertEqual(world.m("offlineshopconst").geometry(), (10, 8, 3, 80, 240))

    def test_config_falls_back_to_the_code_defaults(self):
        world = World()
        world.game.modules["shop"].lack("GetConfig")
        with world:
            cfg = world.m("offlineshopconst").config()
        self.assertEqual(cfg["renew_cost"], 10000000)
        self.assertEqual(cfg["models"], CONFIG["models"])

    def test_a_results_op_is_named_by_the_exe_or_by_ks_numbering(self):
        """GC RESULT's op is EOfflineShopCG: the exe's shop.OFFLINE_SHOP_OP_<NAME> (C), else K's numbering."""
        world = World()
        const = world.m("offlineshopconst")
        self.assertEqual(tuple(const.OP_NAMES), K_OPS)
        with world:
            self.assertEqual(const.op_name(13), "LOGS")
            self.assertEqual(const.op_name(0), "CREATE")
            self.assertEqual(const.op_name(99), "")
            world.game.modules["shop"].lack(*["OFFLINE_SHOP_OP_" + name for name in K_OPS])
            self.assertEqual(const.op_name(13), "LOGS")


class OwnerToolTip(unittest.TestCase):
    """o-cli bug 2: an owner's hover shows the item through Y1's ItemToolTip.SetOfflineShopItem, by
    the slot's global index (OLD called a method nobody defined)."""

    def test_an_owner_hover_on_page_two_shows_the_item_by_its_global_slot(self):
        world = World()
        world.list_item(83, SWORD)
        dialog = open_panel(world)
        calls = []
        world.tooltip.SetOfflineShopItem = lambda slot: calls.append(slot)
        with world, w4.quiet():
            dialog.SelectOfflinePage(1)
            dialog.OverInItem(3)
        self.assertEqual(calls, [83])

    def test_a_visitor_hover_reads_the_view(self):
        world = World()
        world.list_item(5, SWORD)
        dialog = open_view(world)
        calls = []
        world.tooltip.SetOfflineShopItem = lambda slot: calls.append(slot)
        with world, w4.quiet():
            dialog.OverInItem(5)
        self.assertEqual(calls, [5])


class Preview(unittest.TestCase):
    """o-cli bug 5: the hovered item is read page-aware (OLD read the 80-slot array on every page)."""

    def test_the_hovered_item_on_page_three_is_the_offline_getters(self):
        world = World()
        world.list_item(165, SWORD)
        world.game.modules["shop"]._answers["GetItemID"] = lambda slot: POTION
        dialog = open_view(world, pages=3, unlocked=240)
        world.tooltip.SetOfflineShopItem = lambda slot: None
        with world, w4.quiet():
            dialog.SelectOfflinePage(2)
            dialog.OverInItem(5)
            self.assertEqual(dialog.GetSelectedItemVnum(), SWORD)


class MultiBuy(unittest.TestCase):
    """o-cli bug 6: a player's shop has no count dialog; Shift + right press buys one item."""

    def test_shift_right_press_buys_the_slot_once_without_a_count(self):
        world = World()
        world.list_item(4, POTION, count=200, price=50, id=9004)
        dialog = open_view(world, vid=7001)
        world.game.pressed.add(support.APP_CONSTANTS["DIK_LSHIFT"])
        mark = world.mark()
        dialogs = len(world.game.dialogs)
        with world, w4.quiet():
            dialog.UnselectItemSlot(4)
        self.assertEqual(world.since(mark), [("net.SendOfflineShopBuyPacket", (7001, 4, 9004, 50))])
        self.assertEqual(len(world.game.dialogs), dialogs)
        self.assertNotIn("net.SendShopMultiBuyPacket", [name for name, _ in world.sent()])


class LockRows(unittest.TestCase):
    """OLD uiShop.py:413-479: rows past the unlocked slots are covered; the first one is the
    clickable "next" row while another kit is allowed."""

    def rows(self, page, unlocked, expandable=True):
        world = World()
        with world:
            return world.m("offlineshopconst").lock_rows(page, unlocked, expandable)

    def test_eighty_slots_lock_pages_two_and_three(self):
        self.assertEqual(self.rows(0, 80), {})
        self.assertEqual(self.rows(1, 80), dict([(0, "next")] + [(row, "locked") for row in range(1, 8)]))
        self.assertEqual(self.rows(2, 80), dict((row, "locked") for row in range(8)))

    def test_each_kit_opens_one_row(self):
        self.assertEqual(self.rows(1, 90), dict([(1, "next")] + [(row, "locked") for row in range(2, 8)]))
        self.assertEqual(self.rows(2, 160), dict([(0, "next")] + [(row, "locked") for row in range(1, 8)]))
        self.assertEqual(self.rows(2, 240), {})

    def test_no_next_row_without_a_kit_left(self):
        self.assertEqual(self.rows(1, 80, expandable=False), dict((row, "locked") for row in range(8)))

    def test_the_window_covers_its_pages_rows(self):
        world = World()
        world.shop["kits"] = 3
        dialog = open_panel(world)
        world.shop["unlocked"] = 110
        with world, w4.quiet():
            dialog.SelectOfflinePage(1)
            self.assertEqual(dialog.GetLockOverlayStates(), dict([(3, "next")] + [(row, "locked") for row in range(4, 8)]))
            world.shop["kits"] = 16
            self.assertNotIn("next", dialog.GetLockOverlayStates().values())

    def test_the_next_row_asks_for_a_kit_then_expands(self):
        world = World()
        dialog = open_panel(world)
        mark = world.mark()
        with world, w4.quiet():
            dialog.OnClickLockOverlay()
        self.assertEqual(world.since(mark), [])
        self.assertIn(WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_EXPAND_NO_ITEM"], world.dialogs()[-1].texts)
        world.counts[KIT] = 1
        with world, w4.quiet():
            dialog.OnClickLockOverlay()
            world.dialogs()[-1].accept()
        self.assertEqual(world.since(mark), [("net.SendShopExpandPacket", ())])

    def test_a_visitor_has_no_next_row(self):
        world = World()
        dialog = open_view(world, pages=2, unlocked=80)
        with world, w4.quiet():
            dialog.SelectOfflinePage(1)
            self.assertNotIn("next", dialog.GetLockOverlayStates().values())


class Renew(unittest.TestCase):
    """o-cli bug 4: the renew question carries CONFIG's renew cost (OLD's text said 1.000.000, the
    server took 10,000,000)."""

    def test_the_renew_text_is_configs_cost(self):
        world = World(dict(CONFIG, renew_cost=12345678))
        with world:
            text = world.m("offlineshopconst").renew_confirm_text()
            money = world.game.modules["localeInfo"].NumberToMoneyString(12345678)
        self.assertEqual(text, WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_RENEW_CONFIRM"] % money)

    def test_unlocking_an_expired_shop_asks_with_the_cost_then_unlocks(self):
        world = World(dict(CONFIG, renew_cost=12345678))
        dialog = open_panel(world, locked=True, seconds_left=0)
        mark = world.mark()
        with world, w4.quiet():
            dialog.offlineShopWnd.SetLock()
            question = world.dialogs()[-1]
            money = world.game.modules["localeInfo"].NumberToMoneyString(12345678)
            self.assertEqual(question.texts, [WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_RENEW_CONFIRM"] % money])
            self.assertEqual(world.since(mark), [])
            question.accept()
        self.assertEqual(world.since(mark), [("net.SendShopLockPacket", (False,))])

    def test_lock_and_an_unlock_in_time_send_at_once(self):
        world = World()
        dialog = open_panel(world, locked=False)
        mark = world.mark()
        with world, w4.quiet():
            dialog.offlineShopWnd.SetLock()
            dialog.UpdateLock(1)
            dialog.offlineShopWnd.SetLock()
        self.assertEqual(world.since(mark), [("net.SendShopLockPacket", (True,)), ("net.SendShopLockPacket", (False,))])

    def test_the_lock_button_reads_renew_once_the_time_ran_out(self):
        world = World()
        dialog = open_panel(world, locked=True, seconds_left=10)
        button = dialog.offlineShopWnd.lockButton
        self.assertEqual(button.text, WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_BUTTON_UNLOCK"])
        world.game.time += 11
        with world, w4.quiet():
            dialog.OnUpdate()
        self.assertEqual(button.text, WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_BUTTON_RENEW"])


class Extend(unittest.TestCase):
    """EXTEND takes 1 to the days the cap leaves on the result (spec 3.4.5, SB-G2), at CONFIG's price."""

    def test_the_days_left_under_the_cap(self):
        world = World()
        with world:
            days_max = world.m("offlineshopconst").extend_days_max
            self.assertEqual(days_max(0), 15)
            self.assertEqual(days_max(14 * DAY), 1)
            self.assertEqual(days_max(14 * DAY + 1), 0)
            self.assertEqual(days_max(15 * DAY), 0)
            self.assertEqual(world.m("offlineshopconst").extend_cost(3), 3 * 2500000)

    def test_add_time_at_the_cap_refuses(self):
        world = World()
        dialog = open_panel(world, seconds_left=15 * DAY)
        mark = world.mark()
        with world, w4.quiet():
            dialog.offlineShopWnd.ShopAddTime()
        self.assertEqual(world.since(mark), [])
        self.assertIn(WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_TIME_EXCEED"] % 15, world.chat())

    def test_add_time_picks_up_to_the_cap_left_and_sends_extend(self):
        """Spec 3.8: the days times CONFIG's price a day is shown before EXTEND goes (OLD charged
        without showing it)."""
        world = World(dict(CONFIG, extend_price_per_day=2000000))
        dialog = open_panel(world, seconds_left=12 * DAY)
        mark = world.mark()
        with world, w4.quiet():
            dialog.offlineShopWnd.ShopAddTime()
            picker = world.dialogs("PickMoneyDialog")[-1]
            self.assertEqual(picker.opened, (3,))
            picker.accept(9)
            self.assertEqual(world.since(mark), [])
            question = world.dialogs()[-1]
            locale = world.game.modules["localeInfo"]
            self.assertEqual(question.texts, ["%s: %d %s, %s" % (WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_BUTTON_ADD_TIME"], 3,
                                                                  locale.DAY, locale.NumberToMoneyString(6000000))])
            question.accept()
        self.assertEqual(world.since(mark), [("net.SendShopExtendTimePacket", (3,))])

    def test_a_cancelled_extend_sends_nothing(self):
        world = World()
        dialog = open_panel(world, seconds_left=2 * DAY)
        mark = world.mark()
        with world, w4.quiet():
            dialog.offlineShopWnd.ShopAddTime()
            world.dialogs("PickMoneyDialog")[-1].accept(5)
            world.dialogs()[-1].cancel()
        self.assertEqual(world.since(mark), [])


class Decoration(unittest.TestCase):
    """o-cli bug 10: a choice commits into uiPrivateShopBuilder.SHOP_DECO / SHOP_STYLE only on Complete,
    and only with CONFIG's decoration item."""

    def window(self, world):
        with world, w4.quiet():
            window = world.m("uiMyShopDecoration").MyShopDecorationWindow()
            window.BindInterface(world.interface)
            window.Open()
        return window

    def test_a_cancelled_choice_changes_nothing(self):
        world = World()
        builder = world.m("uiPrivateShopBuilder")
        window = self.window(world)
        with world, w4.quiet():
            window.OnSelectEntry(30003, "")
            window.UseNextButton()
            window.OnSelectEntry(2, "")
            window.Close()
        self.assertEqual((builder.SHOP_DECO, builder.SHOP_STYLE), (0, 0))

    def test_the_model_step_shows_the_chosen_model_turning(self):
        """NOVA-137: OLD's player.SelectShopModel and MyShopDecoShow on the "shop_deco"
        target, shown in the preview board over the model's name."""
        world = World()
        mark = len(world.game.log)
        window = self.window(world)
        calls = [(name, args) for name, args in world.game.log[mark:] if name in ("player.SelectShopModel", "player.MyShopDecoShow")]
        self.assertEqual(calls[-2:], [("player.SelectShopModel", (30000,)), ("player.MyShopDecoShow", (True,))])
        self.assertEqual(window.modelView.target, "shop_deco")
        self.assertTrue(window.modelView.IsShow())
        self.assertEqual(window.modelView.position, (3, 3))
        self.assertEqual(window.modelView.size, (160, 96))
        with world, w4.quiet():
            mark = len(world.game.log)
            window.OnSelectEntry(30003, "")
            self.assertIn(("player.SelectShopModel", (30003,)), world.game.log[mark:])
            window.UseNextButton()
        self.assertFalse(window.modelView.IsShow(), "the style step shows the sign, not the model")
        self.assertEqual(world.game.log[-1], ("player.MyShopDecoShow", (False,)))
        with world, w4.quiet():
            window.UsePrevButton()
            self.assertTrue(window.modelView.IsShow())
            window.Close()
        self.assertFalse(window.modelView.IsShow())
        self.assertEqual(world.game.log[-1], ("player.MyShopDecoShow", (False,)))

    def test_a_client_without_model_previews_names_the_model(self):
        world = World()
        world.game.modules["player"].lack("SelectShopModel", "MyShopDecoShow")
        window = self.window(world)
        self.assertIsNone(window.modelView)
        self.assertNotIn("player.SelectShopModel", [name for name, _ in world.game.log])

    def test_complete_commits_the_choice(self):
        world = World()
        world.counts[DECO] = 1
        builder = world.m("uiPrivateShopBuilder")
        window = self.window(world)
        with world, w4.quiet():
            window.OnSelectEntry(30003, "")
            window.UseNextButton()
            window.OnSelectEntry(2, "")
            window.UseCompleteButton()
        self.assertEqual((builder.SHOP_DECO, builder.SHOP_STYLE), (30003, 2))
        self.assertFalse(window.IsShow())

    def test_complete_without_the_scroll_refuses(self):
        world = World()
        builder = world.m("uiPrivateShopBuilder")
        window = self.window(world)
        with world, w4.quiet():
            window.OnSelectEntry(30003, "")
            window.UseCompleteButton()
        self.assertEqual((builder.SHOP_DECO, builder.SHOP_STYLE), (0, 0))
        self.assertIn(WAVE5_GAME_KEYS["DECORATION_REQUIRES_SCROLL"], world.chat())

    def test_the_lists_are_configs_models_with_shop_deco_names(self):
        world = World(dict(CONFIG, models=[30000, 30008], style_count=3))
        window = self.window(world)
        self.assertEqual([vnum for vnum, _ in window.models], [30000, 30008])
        self.assertEqual([style for style, _, _, _ in window.styles], [0, 1, 2])

    def test_every_locale_names_the_eight_code_default_models(self):
        world = World()
        const = world.m("offlineshopconst")
        locales = sorted(name for name in os.listdir(LOCALE) if os.path.isdir(os.path.join(LOCALE, name)))
        self.assertIn("common", locales)
        for locale in locales:
            with open(os.path.join(LOCALE, locale, "shop_deco.txt"), encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("\r", text, locale)
            models, styles = const.read_shop_deco(text.split("\n"))
            self.assertEqual(sorted(models), sorted(CONFIG["models"]), locale)
            self.assertEqual(len(styles), K_SHOP_GEOMETRY["OFFLINE_SHOP_SIGN_STYLE_MAX"] - 1, locale)
            self.assertTrue(all(models.values()), locale)


class Signs(unittest.TestCase):
    """o-cli bugs 11 and 12: a decorated sign keeps its title; every style follows the same nearest-N
    rule; an unknown style is drawn as 0 (L15)."""

    def test_a_decorated_sign_stores_its_title(self):
        world = World()
        with world, w4.quiet():
            bar = world.m("uiPrivateShopBuilder").PrivateShopTitleBar(3)
            bar.Open(7001, "Bob's shop")
            self.assertEqual((bar.title, bar.style), ("Bob's shop", 3))
            bar.UpdateTitle("Bob's bargains")
            self.assertEqual(bar.title, "Bob's bargains")

    def test_an_unknown_style_is_drawn_as_zero(self):
        world = World()
        with world, w4.quiet():
            self.assertEqual(world.m("uiPrivateShopBuilder").PrivateShopTitleBar(9).style, 0)

    def test_the_plain_board_takes_a_new_title(self):
        world = World()
        with world, w4.quiet():
            board = world.m("uiPrivateShopBuilder").PrivateShopAdvertisementBoard()
            board.Open(7002, "first")
            board.UpdateTitle("second")
            self.assertEqual(board.title, "second")

    def test_the_shop_window_titles_a_decorated_shop_from_its_sign(self):
        world = World()
        with world, w4.quiet():
            bar = world.m("uiPrivateShopBuilder").PrivateShopTitleBar(2)
            bar.Open(7001, "Bob's shop")
        world.interface.privateShopAdvertisementBoardDict[7001] = bar
        dialog = open_view(world, vid=7001)
        self.assertEqual(dialog.titleName.text, "Bob's shop")

    def test_every_style_shows_only_the_nearest(self):
        world = World()
        with world:
            const = world.m("offlineshopconst")
            vids = list(range(1, 31))
            distances = dict((vid, vid * 50) for vid in vids)
            distances[30] = 5000
            distances[2] = -1.0
            shown = const.nearest_signs(vids, distances.get, 20, always=(30,))
        # The player's own (always), then the nearest 20 within 3000; -1 is a character not in view.
        self.assertEqual(shown, [30, 1] + list(range(3, 22)))

    def test_with_the_sales_texts_off_the_own_target_and_hovered_signs_show(self):
        """OLD shows the target's and the hovered sign whatever the option (OLD uiPrivateShopBuilder.py:110);
        NEW shows the player's own stall, and the own offline shop (player.GetOwnOfflineShopVID, an NPC with
        its own VID) is the player's own too. Any other sign hides."""
        world = World()
        world.game.show_sales_text = False
        world.game.answer("player", "GetOwnOfflineShopVID", 7005)
        world.game.answer("player", "GetTargetVID", 7003)
        world.game.answer("chr", "Pick", 7004)
        with world, w4.quiet():
            module = world.m("uiPrivateShopBuilder")
            own = world.game.modules["player"].GetMainCharacterIndex()
            shown = dict((vid, module.IsBoardShown(vid)) for vid in (own, 7003, 7004, 7005, 7006))
        self.assertEqual(shown, {own: True, 7003: True, 7004: True, 7005: True, 7006: False})

    def test_a_visited_shops_sign_is_seen_for_thirty_minutes(self):
        world = World()
        with world:
            const = world.m("offlineshopconst")
            const.forget_seen()
            const.mark_seen(7001, 100.0)
            self.assertTrue(const.is_seen(7001, 100.0 + 29 * 60))
            self.assertFalse(const.is_seen(7001, 100.0 + 30 * 60))
            const.forget_seen()


class BuyConfirm(unittest.TestCase):
    """OLD uiShop.py:1095-1099: a player shop's buy asks first only from 1,000,000,000 yang on, and
    BUY carries the expected item id and price (spec 1.1 sub 15)."""

    def test_below_the_threshold_buys_at_once(self):
        world = World()
        world.list_item(2, SWORD, price=999999999, id=9002)
        dialog = open_view(world, vid=7001)
        mark = world.mark()
        with world, w4.quiet():
            dialog.UnselectItemSlot(2)
        self.assertEqual(world.since(mark), [("net.SendOfflineShopBuyPacket", (7001, 2, 9002, 999999999))])

    def test_from_the_threshold_it_asks_first(self):
        world = World()
        world.list_item(2, SWORD, price=1000000000, id=9002)
        dialog = open_view(world, vid=7001)
        mark = world.mark()
        with world, w4.quiet():
            dialog.UnselectItemSlot(2)
            self.assertEqual(world.since(mark), [])
            world.dialogs("QuestionDialog")[-1].accept()
        self.assertEqual(world.since(mark), [("net.SendOfflineShopBuyPacket", (7001, 2, 9002, 1000000000))])

    def test_an_item_dropped_on_the_inventory_buys_it(self):
        world = World()
        world.list_item(84, SWORD, price=10, id=9084)
        dialog = open_view(world, vid=7001, pages=2, unlocked=160)
        mark = world.mark()
        with world, w4.quiet():
            dialog.SelectOfflinePage(1)
            dialog.SelectItemSlot(4)
            world.w4.mouse.GetAttachedSlotNumber = lambda: 84
            dialog.DropToInventory()
        self.assertEqual(world.since(mark), [("net.SendOfflineShopBuyPacket", (7001, 84, 9084, 10))])


class Pending(unittest.TestCase):
    """Spec 3.8: a slot held for a transfer (shop.IsOfflineShopSlotPending) is drawn grayed with the
    pending tooltip and takes no action."""

    def test_a_pending_slot_is_grayed(self):
        world = World()
        world.list_item(1, SWORD, pending=True)
        world.list_item(2, SWORD)
        dialog = open_panel(world)
        recorder = Recorder(dialog.itemSlotWindow, "SetItemSlot")
        with world, w4.quiet():
            dialog.Refresh()
        colors = dict((args[0], args[3] if len(args) > 3 else None) for args in recorder.calls if args[1])
        self.assertIsNotNone(colors[1])
        self.assertIsNone(colors[2])

    def test_a_pending_slot_takes_no_action(self):
        world = World()
        world.list_item(1, SWORD, pending=True)
        dialog = open_panel(world)
        mark = world.mark()
        with world, w4.quiet():
            dialog.UnselectItemSlot(1)
            world.game.pressed.add(support.APP_CONSTANTS["DIK_LALT"])
            dialog.UnselectItemSlot(1)
            dialog.SelectItemSlot(1)
        self.assertEqual(world.since(mark), [])
        self.assertFalse(world.game.attaches)

    def test_a_pending_slot_shows_the_pending_text(self):
        world = World()
        world.list_item(1, SWORD, pending=True)
        dialog = open_panel(world)
        shown = []
        world.tooltip.SetOfflineShopItem = lambda slot: shown.append(slot)
        world.tooltip.ClearToolTip = lambda: None
        world.tooltip.ShowToolTip = lambda: None
        world.tooltip.AppendTextLine = lambda text, *args: shown.append(text)
        with world, w4.quiet():
            dialog.OverInItem(1)
        self.assertEqual(shown, [WAVE5_GAME_KEYS["OFFLINE_SHOP_SLOT_PENDING"]])


class Owner(unittest.TestCase):
    """The owner's drops, price, remove, move and withdraw (OLD uiShop.py:923-1006, 1442-1559)."""

    def test_an_item_dropped_on_an_empty_cell_lists_with_its_price(self):
        world = World()
        world.game.give((INVENTORY, 5), SWORD)
        dialog = open_panel(world)
        world.w4.attach(P["SLOT_TYPE_INVENTORY"], 5, SWORD)
        mark = world.mark()
        with world, w4.quiet():
            dialog.SelectOfflinePage(1)
            dialog.SelectEmptySlot(2)
            board = world.dialogs("BulkMoneyInputDialog")[-1]
            self.assertEqual(board.check_text, WAVE5_GAME_KEYS["OFFLINE_SHOP_BULK_ADD"])
            board.text = "5000"
            board.checked = True
            board.accept()
        self.assertEqual(world.since(mark), [("net.SendShopAddItemPacket", (INVENTORY, 5, 82, 5000, True))])
        self.assertEqual(world.m("itemPrices").get_price(SWORD), 5000)

    def test_right_press_withdraws_alt_prices_ctrl_removes(self):
        world = World()
        world.list_item(3, SWORD, price=70)
        dialog = open_panel(world, locked=True)
        mark = world.mark()
        with world, w4.quiet():
            dialog.UnselectItemSlot(3)
            world.game.pressed.add(support.APP_CONSTANTS["DIK_LALT"])
            dialog.UnselectItemSlot(3)
            price = world.dialogs("BulkMoneyInputDialog")[-1]
            price.text = "90"
            price.accept()
            world.game.pressed.clear()
            world.game.pressed.add(support.APP_CONSTANTS["DIK_LCONTROL"])
            dialog.UnselectItemSlot(3)
            remove = world.dialogs("CheckQuestionDialog")[-1]
            self.assertTrue(remove.checked)
            remove.accept()
        self.assertEqual(world.since(mark), [("net.SendShopWithdrawItemPacket", (3,)),
                                             ("net.SendShopUpdatePricePacket", (3, 90, False)),
                                             ("net.SendShopRemoveItemPacket", (3, True))])

    def test_price_and_remove_need_the_shop_locked(self):
        world = World()
        world.list_item(3, SWORD)
        dialog = open_panel(world, locked=False)
        mark = world.mark()
        with world, w4.quiet():
            world.game.pressed.add(support.APP_CONSTANTS["DIK_LALT"])
            dialog.UnselectItemSlot(3)
        self.assertEqual(world.since(mark), [])
        self.assertIn(WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_CHANGE_PRICE_LOCKED"], world.chat())

    def test_a_listed_item_dropped_on_another_cell_moves(self):
        world = World()
        world.list_item(3, SWORD)
        dialog = open_panel(world)
        mark = world.mark()
        with world, w4.quiet():
            dialog.SelectItemSlot(3)
            dialog.SelectEmptySlot(9)
        self.assertEqual(world.since(mark), [("net.SendShopMoveItemPacket", (3, 9))])

    def test_withdraw_gold_asks_the_held_yang(self):
        world = World()
        dialog = open_panel(world, gold=0)
        with world, w4.quiet():
            dialog.OpenPickMoneyDialog()
        self.assertIn(WAVE5_INTERFACE_KEYS["OFFLINE_SHOP_NO_YANG"], world.chat())
        with world, w4.quiet():
            dialog.UpdateGold(123456)
            dialog.OpenPickMoneyDialog()
            picker = world.dialogs("PickMoneyDialog")[-1]
            self.assertEqual(picker.opened, (123456,))
            mark = world.mark()
            picker.accept(1000)
        self.assertEqual(world.since(mark), [("net.SendShopWithdrawGoldPacket", (1000,))])

    def test_the_close_button_shows_only_at_the_shop(self):
        world = World()
        remote = open_panel(world)
        self.assertFalse(remote.offlineShopWnd.closeButton.shown)
        at_npc = open_panel(World(), from_npc=True)
        self.assertTrue(at_npc.offlineShopWnd.closeButton.shown)

    def test_the_panel_buttons_send_their_operations(self):
        world = World()
        dialog = open_panel(world, from_npc=True)
        mark = world.mark()
        with world, w4.quiet():
            dialog.offlineShopWnd.WarpToShop()
            dialog.offlineShopWnd.CloseShop()
            dialog.offlineShopWnd.OpenShopLogs()
            dialog.offlineShopWnd.OnPressChange()
            board = world.dialogs("InputDialogWithDescription")[-1]
            board.text = "New sign"
            board.accept()
        self.assertEqual(world.since(mark), [("net.SendWarpToShopPacket", ()), ("net.SendCloseShopPacket", ()),
                                             ("net.SendShopChangeSignPacket", ("New sign",))])
        self.assertEqual(world.interface.calls, [("OpenOfflineShopLog",)])

    def test_the_time_text_changes_once_a_second(self):
        """o-cli bug 23: OLD set the text every frame."""
        world = World()
        dialog = open_panel(world, seconds_left=2 * DAY)
        recorder = Recorder(dialog.offlineShopWnd.timeLeftText, "SetText")
        with world, w4.quiet():
            for _ in range(40):
                world.game.time += 0.1
                dialog.OnUpdate()
        self.assertIn(len(recorder.calls), (4, 5))


class Builder(unittest.TestCase):
    """The offline builder (spec 3.8, D6): CONFIG's base rows of 10 cells; OK sends CREATE with the model
    vnum and style (never the stall's CG::MYSHOP); closing it without OK sends LEAVE (spec 3.4.2)."""

    def stocked(self, world):
        builder = world.builder()
        world.game.give((INVENTORY, 5), SWORD)
        world.game.give((INVENTORY, 6), POTION, 3)
        with world, w4.quiet():
            builder.Open("Bob's shop")
            for target, cell, price in ((0, 5, 700), (11, 6, 30)):
                world.w4.attach(P["SLOT_TYPE_INVENTORY"], cell, 0)
                builder.OnSelectEmptySlot(target)
                world.dialogs()[-1].text = str(price)
                builder.priceInputBoard.GetText = lambda price=price: str(price)
                builder.AcceptInputPrice()
        return builder

    def test_closing_without_ok_sends_leave(self):
        world = World()
        builder = world.builder()
        mark = world.mark()
        with world, w4.quiet():
            builder.Open("Bob's shop")
            builder.OnClose()
            builder.Close()
        self.assertEqual(world.since(mark), [("net.SendOfflineShopLeavePacket", ())])

    def test_ok_sends_create_with_the_decoration(self):
        world = World()
        builder_module = world.m("uiPrivateShopBuilder")
        builder_module.SHOP_DECO, builder_module.SHOP_STYLE = 30005, 2
        builder = self.stocked(world)
        mark = world.mark()
        with world, w4.quiet():
            builder.OnOk()
        self.assertEqual(world.since(mark), [("net.SendOfflineShopCreatePacket",
                                              ("Bob's shop", 30005, 2, [(INVENTORY, 5, 0, 700), (INVENTORY, 6, 11, 30)]))])
        self.assertIsNone(world.shop.get("built"))
        self.assertNotIn("shop.BuildPrivateShop", [name for name, _ in world.game.log])

    def test_no_decoration_sends_configs_first_model(self):
        world = World(dict(CONFIG, models=[30001, 30000]))
        builder = self.stocked(world)
        mark = world.mark()
        with world, w4.quiet():
            builder.OnOk()
        self.assertEqual(world.since(mark)[0][1][1:3], (30001, 0))

    def test_the_builder_has_configs_base_rows(self):
        world = World(dict(CONFIG, base_rows=5))
        builder = world.builder()
        with world, w4.quiet():
            builder.Open("Bob's shop")
            self.assertEqual(builder.GetCellCount(), 50)

    def test_create_results_reach_the_builder(self):
        world = World()
        builder = world.builder()
        with world, w4.quiet():
            builder.OnOfflineShopResult(0, K_RESULTS.index("NOT_ENOUGH_GOLD"), 0)
        self.assertIn(WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_NOT_ENOUGH_GOLD"], world.chat())

    def test_the_module_names_y1_reads(self):
        module = World().m("uiPrivateShopBuilder")
        self.assertEqual((module.SHOP_DECO, module.SHOP_STYLE), (0, 0))
        self.assertTrue(callable(module.PrivateShopTitleBar))
        self.assertTrue(callable(getattr(module.PrivateShopAdvertisementBoard, "UpdateTitle", None)))


class Results(unittest.TestCase):
    """Every result code shows its OFFLINE_SHOP_RESULT_<NAME> key; a %s takes the arg."""

    def test_transfer_lost_shows_the_delivery_id(self):
        world = World()
        dialog = world.shop_dialog()
        with world, w4.quiet():
            dialog.OnOfflineShopResult(6, K_RESULTS.index("TRANSFER_LOST"), 424242)
        text = WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_TRANSFER_LOST"] % "424242"
        self.assertIn(text, world.chat())
        self.assertIn(text, world.dialogs("PopupDialog")[-1].texts)

    def test_a_code_without_an_arg_shows_its_text(self):
        world = World()
        dialog = world.shop_dialog()
        with world, w4.quiet():
            dialog.OnOfflineShopResult(3, K_RESULTS.index("NOT_LOCKED"), 77)
        self.assertEqual(world.chat(), [WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_NOT_LOCKED"]])

    def test_an_unknown_code_shows_nothing(self):
        world = World()
        dialog = world.shop_dialog()
        self.assertIn("OnOfflineShopResult", vars(world.m("uiShop").ShopDialog))
        with world, w4.quiet():
            dialog.OnOfflineShopResult(3, 200, 0)
        self.assertEqual(world.chat(), [])


class Glue(unittest.TestCase):
    """The Y1/Y2 contract's table, on Y2's side: what each Interface call does to Y2's windows."""

    def test_start_offline_shop_opens_the_view_in_pages(self):
        world = World()
        world.list_item(12, SWORD)
        dialog = open_view(world, vid=7001, pages=2, unlocked=160)
        self.assertTrue(dialog.IsShow())
        self.assertTrue(dialog.IsOfflineShopOpen())
        self.assertEqual([b.shown for b in dialog.pageButtons], [True, True, False])
        self.assertFalse(dialog.btnBuy.shown or dialog.btnSell.shown)

    def test_end_shop_closes_the_view_with_leave(self):
        world = World()
        dialog = open_view(world)
        mark = world.mark()
        with world, w4.quiet():
            dialog.Close()
        self.assertEqual(world.since(mark), [("net.SendOfflineShopLeavePacket", ())])
        self.assertFalse(dialog.IsShow())

    def test_an_npc_shop_still_ends_with_end(self):
        world = World()
        dialog = world.shop_dialog()
        world.w4.game.w4["npcs"].add(9000)
        mark = world.mark()
        with world, w4.quiet():
            dialog.Open(9000)
            dialog.Close()
        self.assertEqual(world.since(mark), [("net.SendShopEndPacket", ())])

    def test_an_npc_shop_over_the_owners_panel_buys_and_ends_with_end(self):
        """The panel from the inventory (MANAGE) is no server view, so an NPC shop may open over it (the
        server's NPC shop check reads only the view and the gaya market). The panel ends first with its
        one LEAVE; the NPC shop's right press buys and its close sends END."""
        world = World()
        world.list_item(3, SWORD, price=70)
        dialog = open_panel(world)
        world.w4.game.w4["npcs"].add(9001)
        mark = world.mark()
        with world, w4.quiet():
            dialog.Open(9001)
            self.assertFalse(dialog.IsOfflineShopOpen())
            self.assertFalse(dialog.offlineIsOwner)
            self.assertFalse(dialog.offlineShopWnd.IsShow())
            dialog.UnselectItemSlot(3)
            dialog.Close()
        self.assertEqual(world.since(mark), [("net.SendOfflineShopLeavePacket", ()), ("net.SendShopBuyPacket", (3,)),
                                             ("net.SendShopEndPacket", ())])

    def test_view_end_through_refresh_and_end_shop_sends_one_leave(self):
        """C calls RefreshShop() and then EndShop() for VIEW_END (reports/c.md 3.1): the view closes once,
        with LEAVE and no stock END; a later NPC shop still ends with END."""
        world = World()
        dialog = open_view(world)
        world.shop["pages"] = 0
        world.w4.game.w4["npcs"].add(9000)
        mark = world.mark()
        with world, w4.quiet():
            dialog.Refresh()
            dialog.Close()
        self.assertEqual(world.since(mark), [("net.SendOfflineShopLeavePacket", ())])
        mark = world.mark()
        with world, w4.quiet():
            dialog.Open(9000)
            dialog.Close()
        self.assertEqual(world.since(mark), [("net.SendShopEndPacket", ())])

    def test_refresh_shop_rereads_the_view(self):
        world = World()
        dialog = open_view(world)
        world.list_item(7, SWORD)
        recorder = Recorder(dialog.itemSlotWindow, "SetItemSlot")
        with world, w4.quiet():
            dialog.Refresh()
        self.assertIn((7, SWORD, 0), [args[:3] for args in recorder.calls])

    def test_a_refresh_after_the_view_ended_closes_it(self):
        """k-report.md 5.2 lists VIEW_END under RefreshShop(), the contract under EndShop(): either way a
        visitor whose view the client cleared (no page left) is not left in front of a dead shop."""
        world = World()
        dialog = open_view(world)
        world.shop["pages"] = 0
        mark = world.mark()
        with world, w4.quiet():
            dialog.Refresh()
        self.assertFalse(dialog.IsShow())
        self.assertFalse(dialog.IsOfflineShopOpen())
        self.assertEqual(world.since(mark), [("net.SendOfflineShopLeavePacket", ())])

    def test_an_owners_panel_survives_a_refresh_without_pages(self):
        world = World()
        dialog = open_panel(world)
        world.shop["pages"] = 0
        mark = world.mark()
        with world, w4.quiet():
            dialog.Refresh()
        self.assertTrue(dialog.IsShow())
        self.assertEqual(world.since(mark), [])

    def test_open_offline_shop_shows_the_panel_and_zero_only_refreshes(self):
        world = World()
        dialog = world.shop_dialog()
        world.shop.update(owner=True)
        with world, w4.quiet():
            dialog.OpenOfflineShop(0)
        self.assertFalse(dialog.IsShow())
        with world, w4.quiet():
            dialog.OpenOfflineShop(1)
        self.assertTrue(dialog.IsShow())
        self.assertTrue(dialog.offlineShopWnd.IsShow())
        self.assertEqual(dialog.offlineShopWnd.signText.text, "Bob's shop")
        world.shop["info"]["sign"] = "Renamed"
        with world, w4.quiet():
            dialog.OpenOfflineShop(0)
        self.assertEqual(dialog.offlineShopWnd.signText.text, "Renamed")

    def test_the_four_updates_reach_the_panel(self):
        world = World()
        dialog = open_panel(world, locked=False)
        with world, w4.quiet():
            dialog.UpdateLock(1)
            dialog.UpdateTime(3 * DAY)
            dialog.UpdateSign("Fresh")
            dialog.UpdateGold(5000)
        panel = dialog.offlineShopWnd
        self.assertTrue(panel.isLocked)
        self.assertEqual(panel.GetSecondsLeft(), 3 * DAY)
        self.assertEqual(panel.signText.text, "Fresh")
        with world:
            self.assertEqual(panel.goldText.text, world.game.modules["localeInfo"].NumberToMoneyString(5000))

    def test_results_go_to_the_builder_for_create_and_to_the_shop_otherwise(self):
        world = World()
        dialog = world.shop_dialog()
        builder = world.builder()
        for cls in (type(dialog), type(builder)):
            self.assertIn("OnOfflineShopResult", [name for klass in cls.__mro__ for name in vars(klass)], cls)
        with world, w4.quiet():
            builder.OnOfflineShopResult(0, K_RESULTS.index("TOO_CLOSE"), 0)
            dialog.OnOfflineShopResult(5, K_RESULTS.index("NOTHING_HELD"), 0)
        self.assertEqual(world.chat(), [WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_TOO_CLOSE"],
                                        WAVE5_GAME_KEYS["OFFLINE_SHOP_RESULT_NOTHING_HELD"]])

    def test_the_log_takes_its_rows(self):
        world = World()
        with world, w4.quiet():
            window = world.m("uiOfflineShopLog").OfflineShopLogWindow()
            window.BindInterface(world.interface)
            window.Open()
            window.SetData([(1700000000, 5, "Alice", SWORD, 1, 700)], 0, 1)
        self.assertEqual(len(window.GetRowTexts()), 1)

    def test_the_builder_opens_with_its_title_and_the_deco_window_opens(self):
        world = World()
        builder = world.builder()
        with world, w4.quiet():
            builder.Open("Bob's shop")
            deco = world.m("uiMyShopDecoration").MyShopDecorationWindow()
            deco.Open()
        self.assertTrue(builder.IsShow())
        self.assertEqual(builder.title, "Bob's shop")
        self.assertTrue(deco.IsShow())

    def test_every_y2_window_has_the_contracts_calls(self):
        world = World()
        for module, cls in (("uiSearchShop", "SearchShopWindow"), ("uiOfflineShopLog", "OfflineShopLogWindow"),
                            ("uiMyShopDecoration", "MyShopDecorationWindow")):
            window_class = getattr(world.m(module), cls)
            for name in ("Open", "Close", "Destroy", "IsShow", "SetTop", "BindInterface"):
                self.assertTrue(callable(getattr(window_class, name, None)), (cls, name))

    def test_the_shop_dialog_keeps_its_hooks(self):
        world = World()
        cls = world.m("uiShop").ShopDialog
        for name in ("BindInterface", "_ShopDialog__SetOnTopWindow", "_ShopDialog__GetRealIndex", "OnTop", "LoadDialog",
                     "Refresh", "Open", "Close", "SetItemToolTip", "OpenOfflineShop", "UpdateLock", "UpdateTime",
                     "UpdateSign", "UpdateGold", "OnOfflineShopResult"):
            self.assertTrue(hasattr(cls, name), name)
        builder = world.m("uiPrivateShopBuilder").PrivateShopBuilder
        for name in ("BindInterface", "SetInven", "_PrivateShopBuilder__LoadWindow", "_PrivateShopBuilder__SetOnTopWindow",
                     "Open", "Close", "OnOk", "OnOfflineShopResult"):
            self.assertTrue(hasattr(builder, name), name)


class ItemPrices(unittest.TestCase):
    """itemPrices.read_prices / write_price_list (OLD game.py:330, 458): OLD's file, and no I/O error
    reaches the UI."""

    def test_the_list_round_trips(self):
        prices = World().m("itemPrices")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "shop", "price_list.txt")
            prices.PRICE_DICT.clear()
            prices.set_price(SWORD, 700)
            prices.set_price(POTION, 5)
            self.assertTrue(prices.write_price_list(path))
            prices.PRICE_DICT.clear()
            self.assertTrue(prices.read_prices(path))
        self.assertEqual(prices.PRICE_DICT, {SWORD: 700, POTION: 5})
        self.assertEqual(prices.FILE_NAME, "shop/price_list.txt")

    def test_a_missing_or_broken_file_never_raises(self):
        prices = World().m("itemPrices")
        prices.PRICE_DICT.clear()
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(prices.read_prices(os.path.join(folder, "nothing.txt")))
            broken = os.path.join(folder, "broken.txt")
            with open(broken, "w") as handle:
                handle.write("abc\n19\tx\n\n27001\t9\n")
            self.assertTrue(prices.read_prices(broken))
            self.assertFalse(prices.write_price_list(folder))
        self.assertEqual(prices.PRICE_DICT, {POTION: 9})


class ItemPricesUnderTheClientsOpen(unittest.TestCase):
    """The client replaces builtins.open with system.py's open(filename, mode) (client_open), and Y1's
    GameWindow.Open reads the list before it shows the game: no keyword the client's open lacks, no
    exception out of read_prices or write_price_list."""

    def test_the_list_round_trips(self):
        prices = World().m("itemPrices")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "shop", "price_list.txt")
            prices.PRICE_DICT.clear()
            prices.set_price(SWORD, 700)
            with client_open():
                self.assertTrue(prices.write_price_list(path))
                prices.PRICE_DICT.clear()
                self.assertTrue(prices.read_prices(path))
                self.assertFalse(prices.read_prices(os.path.join(folder, "nothing.txt")))
        self.assertEqual(prices.PRICE_DICT, {SWORD: 700})

    def test_no_error_of_any_kind_leaves_them(self):
        prices = World().m("itemPrices")
        with client_open():
            self.assertFalse(prices.read_prices(12.5))
            self.assertFalse(prices.write_price_list(12.5))


class LocaleKeys(unittest.TestCase):
    """Every locale key the Y2 modules and uiscripts read is NEW's (en today) or a wave 5 key: one of
    OLD's or one the Y1/Y2 contract names. The report lists them for Y1's blocks."""

    FILES = ("offlineshopconst.py", "uishop.py", "uiprivateshopbuilder.py", "uimyshopdecoration.py",
             "uiofflineshoplog.py", "uisearchshop.py", "uicommon.py")
    UISCRIPTS = ("shopdialognew.py", "offlineshop.py", "offlineshoplogwindow.py", "privateshopbuildernew.py",
                 "myshopdecorationwindow.py", "searchshop.py", "searchshopfilter.py", "searchbookmarks.py")

    def used(self, module):
        names = set()
        paths = [os.path.join(ROOT, f) for f in self.FILES] + [os.path.join(UISCRIPT, f) for f in self.UISCRIPTS]
        for path in paths:
            tree = ast.parse(lf.read(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == module:
                    names.add(node.attr)
        return names

    def test_the_game_keys_are_known(self):
        new = set(read_locale_file("en", "locale_game.txt"))
        helpers = set(support.LOCALE_FUNCTIONS) | {"MINIMAP_ZONE_NAME_DICT"}
        unknown = sorted(self.used("localeInfo") - new - helpers - set(WAVE5_GAME_KEYS))
        self.assertEqual(unknown, [])

    def test_the_interface_keys_are_known(self):
        new = set(read_locale_file("en", "locale_interface.txt"))
        # uiscriptlocale.py's own name (not a locale_interface.txt key)
        unknown = sorted(self.used("uiScriptLocale") - new - set(WAVE5_INTERFACE_KEYS) - {"LOCALE_UISCRIPT_PATH"})
        self.assertEqual(unknown, [])

    def test_every_wave5_key_is_olds_or_the_contracts(self):
        self.assertEqual(sorted(set(WAVE5_GAME_KEYS) - OLD_GAME_KEYS - CONTRACT_GAME_KEYS), [])


class CommonDialogs(unittest.TestCase):
    """uicommon.py's wave 5 parts over the dialog kit's stand-ins (legacy_foundation_test's
    dialog_modules, every NovaUI window off): the name dialog's deco button, hidden until Y1 shows
    it; the money dialog's check box (OLD's "Bulk add"); the question with a check box."""

    def modules(self):
        base = support.support
        stub = base.stub_module
        state = base.NuiState()
        ui = base.make_legacy_ui()

        class CheckBox(base.Widget):
            def __init__(self):
                base.Widget.__init__(self, "checkbox")
                self.checked = False
                self.info = ""

            def SetTextInfo(self, text):
                self.info = text

            def SetCheckStatus(self, flag):
                self.checked = bool(flag)

            def GetCheckStatus(self):
                return self.checked
        ui.CheckBox = CheckBox
        modules = base.Modules(
            nui=base.make_nui(state), dbg=base.make_dbg(), systemSetting=base.make_setting(flag=0, windows=""),
            wndMgr=base.make_wndmgr(mouse=(800, 600)), ui=ui,
            localeInfo=base.LocaleInfo(MONEY_INPUT_DIALOG_SELLPRICE="Sales Price: ", NumberToMoneyString=base.number_to_money,
                                       OFFLINE_SHOP_BULK_ADD=WAVE5_GAME_KEYS["OFFLINE_SHOP_BULK_ADD"]),
            app=stub("app", IsRTL=lambda: False, GetTime=lambda: 0.0), ime=stub("ime", SetCursorPosition=lambda n: None),
            uiScriptLocale=stub("uiScriptLocale", LOCALE_UISCRIPT_PATH="locale/",
                                MYSHOP_DECO_SELECT_MODEL=WAVE5_INTERFACE_KEYS["MYSHOP_DECO_SELECT_MODEL"]),
            exception=stub("exception", Abort=lambda message: self.fail(message)), player=stub("player", MONEY_DIGITS=13))
        self.addCleanup(modules.restore)
        modules.load("nui_windows")
        return modules.load("uiCommon", "uicommon.py")

    def test_the_name_dialog_has_a_hidden_deco_button(self):
        common = self.modules()
        dialog = common.InputDialog()
        button = getattr(dialog, "decoButton", None)
        self.assertIsNotNone(button)
        self.assertFalse(button.shown)
        self.assertIs(type(dialog), common.LegacyInputDialog)

    def test_the_bulk_money_dialog_adds_its_check_box(self):
        common = self.modules()
        dialog = common.BulkMoneyInputDialog()
        self.assertFalse(dialog.IsBulkMode())
        dialog.SetBulkMode()
        self.assertEqual(dialog.checkBox.info, WAVE5_GAME_KEYS["OFFLINE_SHOP_BULK_ADD"])
        dialog.checkBox.SetCheckStatus(True)
        self.assertTrue(dialog.IsBulkMode())
        dialog.SetBulkMode("Apply to all", checked=True)
        self.assertEqual((dialog.checkBox.info, dialog.IsBulkMode()), ("Apply to all", True))

    def test_the_check_question_keeps_its_box(self):
        common = self.modules()
        dialog = common.CheckQuestionDialog()
        dialog.SetText("Remove?")
        dialog.SetCheckBox("Remove all", True)
        self.assertTrue(dialog.IsChecked())
        dialog.checkBox.SetCheckStatus(False)
        self.assertFalse(dialog.IsChecked())


class RealWidgets(unittest.TestCase):
    """ui.py's new widgets over the real ui.py (legacy_foundation_test.load_real_ui): they add classes
    only, and work without OLD's art."""

    def ui(self, exists=False, wndmgr=None):
        if wndmgr is None:
            wndmgr = lf.AnyCall("wndMgr")
            wndmgr.GetTextSize = lambda handle: (40, 12)
            wndmgr.GetWindowLocalPosition = lambda handle: (0, 0)
            wndmgr.GetWindowGlobalPosition = lambda handle: (0, 0)
        app = lf.AnyCall("app")
        app.IsExistFile = lambda name: exists
        grp = lf.AnyCall("grp")
        grp.GenerateColor = lambda r, g, b, a: (round(r, 2), round(g, 2), round(b, 2), round(a, 2))
        return lf.load_real_ui(self, wndMgr=wndmgr, app=app, grp=grp)

    def test_the_check_box_toggles_and_calls_back(self):
        ui = self.ui()
        box = ui.CheckBox()
        events = []
        box.SetEvent(lambda: events.append("on"), "ON_CHECK")
        box.SetEvent(lambda: events.append("off"), "ON_UNCHECK")
        box.SetTextInfo("Bulk add")
        box.OnMouseLeftButtonUp()
        self.assertTrue(box.GetCheckStatus())
        box.OnMouseLeftButtonUp()
        self.assertEqual(events, ["on", "off"])

    def test_the_thin_board_two_tints_without_its_art(self):
        ui = self.ui(exists=False)
        board = ui.ThinBoard2()
        board.SetPattern("purple")
        self.assertEqual(board.GetPattern(), "purple")

    def test_the_scroll_window_calls_its_end_once(self):
        ui = self.ui()
        window = ui.ScrollWindow(100, 50)
        content = ui.Window()
        heights = {"value": 200}
        content.GetHeight = lambda: heights["value"]
        window.GetHeight = lambda: 50
        content.GetLocalPosition = lambda: (0, 0)
        ends = []
        window.SetContentWindow(content)
        window.SetOnEndScrollEvent(lambda: ends.append(1))
        window.scrollBar.GetPos = lambda: 1.0
        window._ScrollWindow__OnScroll()
        window._ScrollWindow__OnScroll()
        self.assertEqual(ends, [1])

    def test_a_content_change_keeps_the_offset_and_never_calls_the_end(self):
        """OLD ui.py:8236-8244: a content that grows only resizes the bar; the end event runs from a
        user's scroll alone (:8302-8303). Here the content keeps its pixel offset and the bar follows it."""
        wndmgr = GeometryWndMgr()
        ui = self.ui(wndmgr=wndmgr)
        window = ui.ScrollWindow(100, 425)
        content = ui.Window()
        content.SetSize(100, 1)
        ends = []
        window.SetContentWindow(content)
        window.SetOnEndScrollEvent(lambda: ends.append("end"))
        content.SetSize(100, 2000)
        window.OnContentWindowSizeChange()
        self.assertEqual(ends, [])
        window.scrollBar.SetPos(1.0)                     # the user drags the bar to the bottom
        self.assertEqual(ends, ["end"])
        self.assertEqual(content.GetLocalPosition(), (0, -1575))
        content.SetSize(100, 4000)                       # the next page arrives
        window.OnContentWindowSizeChange()
        self.assertEqual(ends, ["end"])
        self.assertEqual(content.GetLocalPosition(), (0, -1575))
        self.assertAlmostEqual(window.scrollBar.GetPos(), 1575.0 / 3575.0, places=2)
        window.OnRunMouseWheel(-120)                     # the wheel down: not the end yet
        self.assertEqual(ends, ["end"])
        window.scrollBar.SetPos(1.0)
        self.assertEqual(ends, ["end", "end"])
        content.SetSize(100, 300)                        # shorter than the view: the bar hides
        window.OnContentWindowSizeChange()
        window.ScrollToStart()
        self.assertEqual(content.GetLocalPosition(), (0, 0))
        self.assertFalse(window.scrollBar.IsShow())
        self.assertEqual(ends, ["end", "end"])

    def real_log_window(self, wndmgr):
        """uiofflineshoplog's window over the real ui.py (its uiscript's children made plainly), net's
        LOGS sender recorded."""
        import importlib.util
        ui = self.ui(wndmgr=wndmgr)
        sent = []
        net = types.ModuleType("net")
        net.SendOfflineShopLogsPacket = lambda page: sent.append(page)
        for name, module in (("ui", ui), ("net", net), ("shop", types.ModuleType("shop"))):
            sys.modules[name] = module                 # load_real_ui's patch of sys.modules undoes it

        class Loader(object):
            def LoadScriptFile(self, window, path):
                title = ui.Window()
                title.SetCloseEvent = lambda event: None
                for name, child in (("board", ui.Bar()), ("TitleBar", title), ("LogsWindow", ui.Window()),
                                    ("LoadingText", ui.TextLine()), ("EmptyText", ui.TextLine())):
                    window.InsertChild(name, child)
        ui.PythonScriptLoader = Loader
        for name, file_name in (("offlineshopconst", "offlineshopconst.py"), ("uiOfflineShopLog", "uiofflineshoplog.py")):
            spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, file_name))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        return module.OfflineShopLogWindow(), sent

    def test_the_log_window_asks_each_page_once_over_the_real_scroll_window(self):
        """A page that arrives with the view at the bottom asks for nothing: SO1 refuses a LOGS within
        1 s, so an automatic ask would strand the window. The user's scroll to the new end asks once."""
        wndmgr = GeometryWndMgr()
        window, sent = self.real_log_window(wndmgr)
        rows = [(1700000000 + i, 1, "", 0, 0, 0) for i in range(100)]
        window.Open()
        window.SetData(rows, 0, 0)
        self.assertEqual(sent, [0])
        window.scrollWindow.scrollBar.SetPos(1.0)
        self.assertEqual(sent, [0, 1])
        window.SetData(rows, 1, 0)
        self.assertEqual(sent, [0, 1])
        self.assertFalse(window.IsLoading())
        window.scrollWindow.scrollBar.SetPos(1.0)
        self.assertEqual(sent, [0, 1, 2])
        window.SetData(rows[:5], 2, 1)
        window.scrollWindow.scrollBar.SetPos(0.0)
        window.scrollWindow.scrollBar.SetPos(1.0)
        self.assertEqual(sent, [0, 1, 2])
        self.assertEqual(len(window.GetRowTexts()), 205)

    def test_the_shop_deco_title_tints_without_its_art(self):
        ui = self.ui(exists=False)
        title = ui.ShopDecoTitle(2, pattern="d:/ymir work/ui/pattern/myshop/ice/p_ice", color=0xF9F4FF)
        title.SetSize(120, 32)
        self.assertEqual(title.patternCorners, [])
        self.assertEqual(title.GetFontColor(), (0xF9 / 255.0, 0xF4 / 255.0, 1.0))

    def test_the_shop_deco_title_draws_plain_without_the_rules(self):
        ui = self.ui(exists=True)
        sys.modules["offlineshopconst"] = None   # load_real_ui's patch of sys.modules undoes it
        title = ui.ShopDecoTitle(9)
        title.SetSize(120, 32)
        self.assertEqual((title.patternCorners, title.color), ([], 0xFFFFFF))


class Compiles(unittest.TestCase):
    def test_every_y2_file_compiles_under_python_3(self):
        files = [os.path.join(ROOT, f) for _, f in Y2_MODULES] + [os.path.join(ROOT, "ui.py"), os.path.join(ROOT, "uicommon.py")]
        files += [os.path.join(UISCRIPT, f) for f in LocaleKeys.UISCRIPTS]
        for path in files:
            compile(lf.read(path), path, "exec")


if __name__ == "__main__":
    unittest.main()
