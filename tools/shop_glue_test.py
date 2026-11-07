"""Tests for the legacy client's offline shop glue (wave 5, chunk Y1; NOVA-9):
python3 -B -m unittest shop_glue_test (from tools/).

The shop windows are chunk Y2's (uishop, uiprivateshopbuilder, uicommon's
InputDialog.decoButton, uisearchshop, uiofflineshoplog, uimyshopdecoration,
itemprices) and are not on Y1's branch: the glue is driven here against
stand-ins with the names and methods the Y1/Y2 contract fixes (y1.md). C's
callbacks and bindings are K's names (k-report.md 5.2, 5.3). Here:
- game.GameWindow's callbacks reach the Interface, and the Interface's
  methods reach Y2's windows, one case per row of the contract's table;
- Interface.__MakeWindows makes Y2's windows plainly and binds them, and
  Close destroys them; HideAllWindows and __HideWindows hide the
  decoration window, as OLD did;
- uiinventory: the Offline Shop button sends MANAGE, the Search button and
  Ctrl + click open the search, CONFIG's "enabled" shows or hides them;
- uigameoption: the hide-shops option sends /hide_shops and shows
  shop.IsHideShops(), never a local guess (M5);
- uitooltip.ItemToolTip.SetOfflineShopItem(slot) (o-cli bug 2) and the
  owner's key hints, in plain text;
- every wave key (premium, gaya and shop) in all 17 locales, in one
  contiguous block at each file's end;
- shop_deco.txt (Y2's) against the runtime's shipped model list, skipped
  while the file is absent."""
import ast
import contextlib
import os
import re
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402
import extra_inventory_test as xinv  # noqa: E402
import nui_sys_test as sys_test  # noqa: E402
import premium_test  # noqa: E402
import gem_shop_test  # noqa: E402

ROOT = support.ROOT
UISCRIPT = lf.UISCRIPT
LOCALES = lf.LOCALES

# The protocol's EOfflineShopCG (nova-protocol 63ed65a, offline_shop_packets.h:146):
# CREATE is the builder's op, the others the owner panel's.
OP_CREATE, OP_LOCK, OP_LOGS = 0, 3, 13
# The runtime's shipped model list (spec 5.8, D5: nova-server share/conf/game.txt
# ships OFFLINE_SHOP_MODELS: 30000 until the Q9 assets).
SHIPPED_MODELS = (30000,)

# EOfflineShopResult 0-36 (k-report 5.1, shop.OFFLINE_SHOP_RESULT_<NAME>).
RESULT_NAMES = ("OK", "DISABLED", "MAP_NOT_ALLOWED", "CHANNEL_NOT_ALLOWED", "TOO_CLOSE", "NOT_ENOUGH_GOLD", "BAD_PRICE",
                "GOLD_CAP", "BAD_SIGN", "BAD_DECORATION", "ITEM_RESTRICTED", "BAD_SLOT", "SLOT_TAKEN", "SLOT_LOCKED",
                "ALREADY_OPEN", "NO_SHOP", "BUSY", "QUEST_RUNNING", "NOT_LOCKED", "RATE_LIMITED", "INVENTORY_FULL",
                "OWNER_GOLD_MAX", "EMPTY_SHOP", "EXPIRED", "EXTEND_CAP", "MAX_KITS", "NEED_KIT", "NOT_AT_SHOP",
                "SOLD_OUT", "PREMIUM_REQUIRED", "COOLDOWN", "SEARCH_MAP_DENIED", "TIMEOUT", "UNREACHABLE",
                "NOTHING_HELD", "OTHER_CHANNEL", "TRANSFER_LOST")
# The codes whose arg the text shows (spec 3.4.5 WARP: the channel; 3.4.9.7:
# the delivery id).
RESULTS_WITH_ARG = ("OTHER_CHANNEL", "TRANSFER_LOST")

# OLD's keys (Ol:en/locale_interface.txt, locale_game.txt; o-cli 1.6), kept
# in their file, name and spelling; OPTION_SHOW_COMPANIONS_SHOPS is OLD's
# hide-shops option label (OLD uiGameOption.py:1169-1218).
OLD_INTERFACE_KEYS = (
    "MYSHOP_DECO_CANCEL", "MYSHOP_DECO_DEFAULT", "MYSHOP_DECO_NEXT", "MYSHOP_DECO_OK", "MYSHOP_DECO_PREV",
    "MYSHOP_DECO_SELECT_MODEL", "MYSHOP_DECO_SELECT_TITLE", "OFFLINE_SHOP_TITLE", "OFFLINE_SHOP_BUTTON_LOCK",
    "OFFLINE_SHOP_BUTTON_UNLOCK", "OFFLINE_SHOP_BUTTON_RENEW", "OFFLINE_SHOP_BUTTON_RENAME", "OFFLINE_SHOP_BUTTON_CLOSE",
    "OFFLINE_SHOP_INPUT_SIGN_TITLE", "OFFLINE_SHOP_INPUT_SIGN_DESC", "OFFLINE_SHOP_RENEW_CONFIRM", "OFFLINE_SHOP_TIME_LEFT",
    "SEARCH_SHOP_TITLE", "SEARCH_SHOP_BUY_CONFIGM", "SEARCH_SHOP_BOOKMARK_EMPTY", "SEARCH_SHOP_BOOKMARK_FULL",
    "SEARCH_SHOP_BOOKMARKS", "SEARCH_SHOP_FAVOURITES", "SEARCH_SHOP_SORT_UP", "SEARCH_SHOP_SORT_DOWN",
    "SEARCH_SHOP_FILTER_CATEGORY", "OFFLINE_SHOP_LOCATION", "OFFLINE_SHOP_BUTTON_TELEPORT", "OFFLINE_SHOP_BUTTON_WITHDRAW",
    "OFFLINE_SHOP_BUTTON_ADD_TIME", "OFFLINE_SHOP_BUTTON_VIEW_LOGS", "OFFLINE_SHOP_TEXT_EXPIRE_IN",
    "OFFLINE_SHOP_TIME_EXCEED", "OFFLINE_SHOP_NO_YANG", "OFFLINE_SHOP_CHANGE_PRICE_TITLE", "OFFLINE_SHOP_CHANGE_PRICE_ALL",
    "OFFLINE_SHOP_CHANGE_PRICE_LOCKED", "OFFLINE_SHOP_REMOVE_ITEM_CONFIRM", "OFFLINE_SHOP_REMOVE_ITEM_ALL",
    "OFFLINE_SHOP_REMOVE_ITEM_LOCKED", "OFFLINE_SHOP_PAGE_BUTTON", "OFFLINE_SHOP_EXPAND_BUTTON",
    "OFFLINE_SHOP_EXPAND_NO_ITEM", "OFFLINE_SHOP_EXPAND_ROW_CONFIRM")
OPTION_KEYS = ("OPTION_SHOW_COMPANIONS_SHOPS",)
OLD_GAME_KEYS = (
    "OFFLINE_SHOP", "OFFLINE_SHOP_CHANGE_TIME", "OFFLINE_SHOP_CHANGE_TIME2", "OFFLINE_SHOP_SELECT_TIME",
    "OFFLINE_SHOP_SELECT_TIME2", "OFFLINE_SHOP_WARNING1", "OFFLINE_SHOP_WARNING2", "OFFLINE_SHOP_INPUT_NAME_DIALOG_TITLE",
    "OFFLINE_SHOP_INPUT_PRICE_DIALOG_TITLE", "OFFLINE_SHOP_CANNOT_SELL_ITEM", "REQUIRED_PREMIUM_USER", "SEARCH_SHOP_WAIT",
    "SEARCH_SHOP_PRICE_MIN", "SEARCH_SHOP_WRONG_NAME", "DECORATION_REQUIRES_SCROLL", "SEARCH_SHOP_CAT_ALL",
    "SEARCH_SHOP_CAT_WEAPONS", "SEARCH_SHOP_CAT_EQUIPMENTS", "SEARCH_SHOP_CAT_VOUCHERS", "SEARCH_SHOP_CAT_COSTUMES",
    "SEARCH_SHOP_CAT_CHANGERS", "SEARCH_SHOP_CAT_STONES", "SEARCH_SHOP_CAT_CHESTS", "SEARCH_SHOP_CAT_ITEMS",
    "SEARCH_SHOP_CAT_MATERIALS", "SEARCH_SHOP_CAT_ORES", "SEARCH_SHOP_CAT_PETS", "SEARCH_SHOP_CAT_MOUNTS",
    "SEARCH_SHOP_PREMIMUM_STATUS", "SEARCH_SHOP_PREMIMUM_ACTIVE", "SEARCH_SHOP_PREMIMUM_INACTIVE", "SEARCH_SHOP_GOLD",
    "SEARCH_SHOP_COSTUME_BODY", "SEARCH_SHOP_COSTUME_HAIR", "SEARCH_SHOP_COSTUME_WEAPON", "SEARCH_SHOP_COSTUME_WING",
    "SEARCH_SHOP_COSTUME_FACIAL", "SEARCH_SHOP_COSTUME_SASH", "SEARCH_SHOP_COSTUME_BODY_EFFECT",
    "SEARCH_SHOP_COSTUME_WEAPON_EFFECT", "OFFLINE_SHOP_TOOLTIP_WITHDRAW", "OFFLINE_SHOP_TOOLTIP_CHANGE_PRICE",
    "OFFLINE_SHOP_TOOLTIP_REMOVE")
NEW_GAME_KEYS = tuple("OFFLINE_SHOP_RESULT_" + name for name in RESULT_NAMES) + \
    tuple("OFFLINE_SHOP_LOG_ACTION_%d" % i for i in range(12)) + \
    ("OFFLINE_SHOP_SLOT_PENDING", "OFFLINE_SHOP_BULK_ADD", "MYSHOP_DECO_STEP_TITLE", "MYSHOP_DECO_STEP_MODEL",
     "SEARCH_SHOP_IN_STOCK", "SEARCH_SHOP_FOLLOW_SIGNAL", "SEARCH_SHOP_OTHER_MAP",
     # The inventory's two text buttons (OLD's were image buttons, Q9 art).
     "OFFLINE_SHOP_BUTTON", "SEARCH_SHOP_BUTTON")
# Spec-pinned texts (o-cli bug 4: the renew cost is formatted by the caller;
# the hints in plain text, as 4b's MULTI_USE_ITEM; OLD's hard-coded English).
ENGLISH = {"OFFLINE_SHOP_RENEW_CONFIRM": "Renewing the shop costs %s Yang.",
           "OFFLINE_SHOP_TOOLTIP_WITHDRAW": "Right-click: withdraw the item",
           "OFFLINE_SHOP_TOOLTIP_CHANGE_PRICE": "Alt + right-click: change the price",
           "OFFLINE_SHOP_TOOLTIP_REMOVE": "Ctrl + right-click: remove all identical items",
           "OFFLINE_SHOP_BULK_ADD": "Bulk add", "MYSHOP_DECO_STEP_TITLE": "Select title", "MYSHOP_DECO_STEP_MODEL": "Model",
           "SEARCH_SHOP_IN_STOCK": "In Stock: %s",
           "SEARCH_SHOP_FOLLOW_SIGNAL": "Follow the signal on the map, it will lead to the shop",
           "SEARCH_SHOP_OTHER_MAP": "You are in a different map, do you want to teleport?",
           "SEARCH_SHOP_PREMIMUM_ACTIVE": "Active", "SEARCH_SHOP_PREMIMUM_INACTIVE": "Inactive",
           "OFFLINE_SHOP_RESULT_TRANSFER_LOST": "The transfer could not be completed. Please contact support with the code %s.",
           "OFFLINE_SHOP_RESULT_OTHER_CHANNEL": "This shop is on channel %s."}
# OLD's log actions (OLD uiOfflineShopLog.py:12-25), 7 named for what it is.
LOG_ACTIONS = ("Opened", "Closed", "Locked", "Unlocked", "Added Time", "Sold Item", "Added Item", "Withdrew Item",
               "Withdrew Yang", "Price Updated", "Item Removed", "Item Moved")


def compiled_class(file_name, class_name, names):
    return xinv.compiled(file_name, class_name, names)


def class_methods(file_name, class_name):
    return gem_shop_test.class_methods(file_name, class_name)


class Log(object):
    """Records ("name.method", args, kwargs) of stand-in objects."""

    def __init__(self):
        self.calls = []

    def obj(self, name, **answers):
        log = self

        class Recorded(object):
            def __getattr__(self, attr):
                if attr.startswith("__"):
                    raise AttributeError(attr)

                def call(*args, **kwargs):
                    log.calls.append(("%s.%s" % (name, attr), args, kwargs))
                    return answers.get(attr)
                return call
        return Recorded()


# --- game.py --------------------------------------------------------------------------------------

GAME_ROWS = (
    # (C's callback on the game window, its arguments, the Interface call it makes)
    ("StartOfflineShop", (77,), ("interface.OpenOfflineShopDialog", (77,))),
    ("EndShop", (), ("interface.CloseShopDialog", ())),
    ("RefreshShop", (), ("interface.RefreshShopDialog", ())),
    ("OpenOfflineShop", (1,), ("interface.OpenOfflineShop", (1,))),
    ("OpenOfflineShop", (0,), ("interface.OpenOfflineShop", (0,))),
    ("UpdateShopLock", (1,), ("interface.UpdateShopLock", (1,))),
    ("UpdateShopTime", (3600,), ("interface.UpdateShopTime", (3600,))),
    ("UpdateShopSign", ("Best prices",), ("interface.UpdateShopSign", ("Best prices",))),
    ("UpdateShopGold", (9999999999999,), ("interface.UpdateShopGold", (9999999999999,))),
    ("OnOfflineShopResult", (OP_LOCK, 18, 0), ("interface.OnOfflineShopResult", (OP_LOCK, 18, 0))),
    ("BINARY_OfflineShopLog", ([(1700000000, 5, "Buyer", 19, 1, 500)], 0, 1),
     ("interface.OfflineShopLog", ([(1700000000, 5, "Buyer", 19, 1, 500)], 0, 1))),
    ("RefreshSearchShop", (), ("interface.RefreshSearchShop", ())),
    ("OnSearchShopBuyResult", (0, 1001, 4), ("interface.OnSearchShopBuyResult", (0, 1001, 4))),
    ("BINARY_OfflineShopConfig", (), ("interface.OnOfflineShopConfig", ())),
    ("BINARY_OfflineShopBuilderOpen", (), ("interface.OpenPrivateShopInputNameDialog", ())),
    ("BINARY_OfflineShopHideShops", (1,), ("interface.OnOfflineShopHideShops", (1,))),
    ("BINARY_PrivateShop_Appear", (77, "sign", 3), ("interface.AppearPrivateShop", (77, "sign", 3))),
    ("BINARY_PrivateShop_Appear", (78, "sign"), ("interface.AppearPrivateShop", (78, "sign", 0))),
)


class GameCallbacks(unittest.TestCase):
    def test_each_callback_reaches_the_interface(self):
        names = sorted(set(row[0] for row in GAME_ROWS))
        GameWindow = compiled_class("game.py", "GameWindow", names)
        for name, args, expected in GAME_ROWS:
            with self.subTest(callback=name, args=args):
                log = Log()
                window = GameWindow()
                window.interface = log.obj("interface")
                getattr(window, name)(*args)
                self.assertEqual([call[:2] for call in log.calls], [expected])

    def test_the_price_list_is_read_at_open_and_written_at_close(self):
        """OLD game.py:330, 458 (Y2's itemPrices)."""
        methods = class_methods("game.py", "GameWindow")
        self.assertIn("itemPrices.read_prices()", methods["Open"])
        self.assertIn("itemPrices.write_price_list()", methods["Close"])


# --- the Interface -------------------------------------------------------------------------------

class InterfaceWorld(object):
    """The Interface's glue methods, compiled from interfacemodule.py, over
    stand-ins of Y2's windows and widgets (the contract's names), C's shop
    and net modules, and uiCommon.InputDialog with and without Y2's deco
    button."""

    METHODS = ("OpenShopDialog", "OpenOfflineShopDialog", "CloseShopDialog", "RefreshShopDialog", "OpenOfflineShop",
               "UpdateShopLock", "UpdateShopTime", "UpdateShopSign", "UpdateShopGold", "OnOfflineShopResult",
               "OfflineShopLog", "RefreshSearchShop", "OnSearchShopBuyResult", "OnOfflineShopConfig",
               "OnOfflineShopHideShops", "OpenSearchShop", "OpenOfflineShopLog", "OpenMyShopDecoWnd", "AppearPrivateShop",
               "OpenPrivateShopInputNameDialog", "ClosePrivateShopInputNameDialog", "CancelPrivateShopInputNameDialog",
               "OpenPrivateShopBuilder")

    def __init__(self, config=None):
        self.log = log = Log()
        self.config = {"enabled": 1} if config is None else config
        self.dialogs = []
        self.hidden = False
        self.nova_signs = False
        world = self

        class Board(object):
            def __init__(self, kind, style=None):
                self.kind = kind
                self.style = style
                self.opened = None
                self.titles = []
                log.calls.append(("made", (kind, style), {}))

            def Open(self, vid, text):
                self.opened = (vid, text)

            def UpdateTitle(self, text):
                self.titles.append(text)

        class NovaSign(object):
            """A factory sign without UpdateTitle (NovaUI's nui_shop_signs.ShopSign
            had none before Wave 5's follow-up)."""

            def __init__(self):
                self.kind = "nova"
                self.opened = None
                log.calls.append(("made", ("nova", None), {}))

            def Open(self, vid, text):
                self.opened = (vid, text)

        builder = types.ModuleType("uiPrivateShopBuilder")
        builder.SHOP_DECO = 30005
        builder.SHOP_STYLE = 4
        builder.PrivateShopAdvertisementBoard = lambda: Board("advertisement")
        builder.PrivateShopTitleBar = lambda style: Board("title", style)
        self.builder = builder
        nui_windows = types.ModuleType("nui_windows")

        def make(window_id, legacy, novaui, *args):
            log.calls.append(("nui_windows.make", (window_id, novaui), {}))
            return NovaSign() if world.nova_signs else legacy(*args)
        nui_windows.make = make

        class InputDialog(object):
            def __init__(self):
                world.dialogs.append(self)
                self.decoButton = log.obj("decoButton")
                self.text = ""
                self.accept = self.cancel = None
                self.opened = False

            def SetTitle(self, title):
                self.title = title

            def SetMaxLength(self, length):
                self.max = length

            def SetAcceptEvent(self, event):
                self.accept = event

            def SetCancelEvent(self, event):
                self.cancel = event

            def Open(self):
                self.opened = True

            def GetText(self):
                return self.text

        class PlainInputDialog(InputDialog):
            """Today's uiCommon.InputDialog: no deco button (Y2 adds it)."""

            def __init__(self):
                InputDialog.__init__(self)
                del self.decoButton

        self.InputDialog = InputDialog
        self.PlainInputDialog = PlainInputDialog
        common = types.ModuleType("uiCommon")
        common.InputDialog = InputDialog
        self.common = common
        shop = types.ModuleType("shop")
        shop.GetConfig = lambda: dict(world.config) if isinstance(world.config, dict) else world.config
        shop.IsHideShops = lambda: world.hidden
        net = types.ModuleType("net")
        net.SendOfflineShopLeavePacket = lambda: log.calls.append(("net.SendOfflineShopLeavePacket", (), {}))
        ui = types.ModuleType("ui")
        setattr(ui, "__mem_func__", lambda fn: fn)
        self.modules = {"uiPrivateShopBuilder": builder, "nui_windows": nui_windows, "uiCommon": common, "shop": shop,
                        "net": net, "ui": ui, "localeInfo": support.locale_info("en")}
        with self:
            source = support.source_of("interfacemodule.py", self.METHODS, inside="Interface")
            body = "\n".join("\t" + line if line else line for line in source.split("\n"))
            namespace = dict(self.modules)
            module = ast.parse(lf.read(os.path.join(ROOT, "interfacemodule.py")))
            for node in module.body:  # the module's constants (OFFLINE_SHOP_OP_CREATE)
                if isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in node.targets):
                    exec(compile(ast.Module(body=[node], type_ignores=[]), "interfacemodule.py", "exec"), namespace)
            exec(compile("class Interface(object):\n%s\n" % body, "interfacemodule.py", "exec"), namespace)
        interface = self.interface = namespace["Interface"]()
        interface.dlgShop = log.obj("dlgShop")
        interface.privateShopBuilder = log.obj("privateShopBuilder")
        interface.wndOfflineShopLog = log.obj("wndOfflineShopLog")
        interface.wndMyShopDeco = log.obj("wndMyShopDeco")
        interface.wndInventory = log.obj("wndInventory")
        interface.dlgSystem = types.SimpleNamespace(gameOptionDlg=log.obj("gameOptionDlg"))
        interface.privateShopAdvertisementBoardDict = {}
        interface.inputDialog = None
        search = log.obj("wndSearchShop")

        class SearchShop(object):
            shown = False

            def IsShow(self):
                return self.shown

            def Open(self, vnum=0):
                self.shown = True
                log.calls.append(("wndSearchShop.Open", (vnum,), {}))

            def Close(self):
                self.shown = False
                log.calls.append(("wndSearchShop.Close", (), {}))

            def __getattr__(self, attr):
                return getattr(search, attr)
        interface.wndSearchShop = SearchShop()

    def __enter__(self):
        self._patch = mock.patch.dict(sys.modules, self.modules)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()

    def call(self, name, *args):
        with self:
            return getattr(self.interface, name)(*args)

    def calls(self, prefix=""):
        return [call for call in self.log.calls if call[0].startswith(prefix)]


INTERFACE_ROWS = (
    # (the Interface method, its arguments, the calls it makes, keyword arguments included)
    ("OpenOfflineShopDialog", (77,), [("wndInventory.Show", (), {}), ("wndInventory.SetTop", (), {}),
                                      ("dlgShop.Open", (77,), {"multiPage": True}), ("dlgShop.SetTop", (), {})]),
    ("CloseShopDialog", (), [("dlgShop.Close", (), {})]),
    ("RefreshShopDialog", (), [("dlgShop.Refresh", (), {})]),
    ("OpenOfflineShop", (1,), [("dlgShop.OpenOfflineShop", (1,), {})]),
    ("OpenOfflineShop", (0,), [("dlgShop.OpenOfflineShop", (0,), {})]),
    ("UpdateShopLock", (1,), [("dlgShop.UpdateLock", (1,), {})]),
    ("UpdateShopTime", (90,), [("dlgShop.UpdateTime", (90,), {})]),
    ("UpdateShopSign", ("sign",), [("dlgShop.UpdateSign", ("sign",), {})]),
    ("UpdateShopGold", (12,), [("dlgShop.UpdateGold", (12,), {})]),
    ("OnOfflineShopResult", (OP_CREATE, 4, 0), [("privateShopBuilder.OnOfflineShopResult", (OP_CREATE, 4, 0), {})]),
    ("OnOfflineShopResult", (OP_LOCK, 22, 0), [("dlgShop.OnOfflineShopResult", (OP_LOCK, 22, 0), {})]),
    ("OnOfflineShopResult", (OP_LOGS, 36, 9001), [("dlgShop.OnOfflineShopResult", (OP_LOGS, 36, 9001), {})]),
    ("OfflineShopLog", ([], 2, 1), [("wndOfflineShopLog.SetData", ([], 2, 1), {})]),
    ("RefreshSearchShop", (), [("wndSearchShop.RefreshItems", (), {})]),
    ("OnSearchShopBuyResult", (28, 1001, 4), [("wndSearchShop.OnBuyResult", (28, 1001, 4), {})]),
    ("OpenOfflineShopLog", (), [("wndOfflineShopLog.Open", (), {}), ("wndOfflineShopLog.SetTop", (), {})]),
    ("OpenMyShopDecoWnd", (), [("wndMyShopDeco.Open", (), {}), ("wndMyShopDeco.SetTop", (), {})]),
    ("OnOfflineShopHideShops", (1,), [("gameOptionDlg.RefreshHideShops", (), {})]),
)


class InterfaceGlue(unittest.TestCase):
    def test_each_row_of_the_contract(self):
        for name, args, expected in INTERFACE_ROWS:
            with self.subTest(method=name, args=args):
                world = InterfaceWorld()
                world.call(name, *args)
                self.assertEqual(world.log.calls, expected)

    def test_the_hide_shops_answer_without_a_game_option_window_does_nothing(self):
        for dialog in (None, object()):
            world = InterfaceWorld()
            world.interface.dlgSystem = types.SimpleNamespace(gameOptionDlg=dialog)
            world.call("OnOfflineShopHideShops", 0)
            self.assertEqual(world.log.calls, [])

    def test_the_search_button_toggles_and_a_vnum_opens_on_that_item(self):
        world = InterfaceWorld()
        world.call("OpenSearchShop")
        world.call("OpenSearchShop")
        world.call("OpenSearchShop", 27001)
        world.call("OpenSearchShop", 27002)
        self.assertEqual([call[:2] for call in world.calls("wndSearchShop.")],
                         [("wndSearchShop.Open", (0,)), ("wndSearchShop.SetTop", ()), ("wndSearchShop.Close", ()),
                          ("wndSearchShop.Open", (27001,)), ("wndSearchShop.SetTop", ()),
                          ("wndSearchShop.Open", (27002,)), ("wndSearchShop.SetTop", ())])

    def test_config_shows_or_hides_the_inventory_buttons(self):
        for config, shown in (({"enabled": 1}, True), ({"enabled": 0}, False), ({}, False), (0, False), ([], False)):
            with self.subTest(config=config):
                world = InterfaceWorld(config)
                world.call("OnOfflineShopConfig")
                self.assertEqual(world.log.calls, [("wndInventory.ShowOfflineShopButtons", (shown,), {})])

    def test_a_shop_sign_of_style_0_is_todays_board_and_a_styled_one_a_title_bar(self):
        world = InterfaceWorld()
        world.call("AppearPrivateShop", 70, "plain")
        world.call("AppearPrivateShop", 71, "styled", 4)
        world.call("AppearPrivateShop", 72, "zero", 0)
        boards = world.interface.privateShopAdvertisementBoardDict
        self.assertEqual((boards[70].kind, boards[70].opened), ("advertisement", (70, "plain")))
        self.assertEqual((boards[71].kind, boards[71].style, boards[71].opened), ("title", 4, (71, "styled")))
        self.assertEqual(boards[72].kind, "advertisement")
        self.assertEqual(world.calls("nui_windows.make"), [("nui_windows.make", ("shop-signs", "nui_shop_signs.ShopSign"), {})] * 3,
                         "every style goes through the factory (NovaUI draws the styles too)")

    def test_a_sign_shown_again_updates_its_title(self):
        world = InterfaceWorld()
        world.call("AppearPrivateShop", 70, "first")
        board = world.interface.privateShopAdvertisementBoardDict[70]
        world.call("AppearPrivateShop", 70, "second")
        self.assertIs(world.interface.privateShopAdvertisementBoardDict[70], board)
        self.assertEqual(board.titles, ["second"])
        self.assertEqual(len(world.calls("made")), 1)

    def test_a_sign_without_update_title_is_made_again(self):
        world = InterfaceWorld()
        world.nova_signs = True
        world.call("AppearPrivateShop", 70, "first")
        world.call("AppearPrivateShop", 70, "second")
        self.assertEqual(world.interface.privateShopAdvertisementBoardDict[70].opened, (70, "second"))
        self.assertEqual(len(world.calls("made")), 2)

    def test_the_builder_s_name_dialog_has_the_deco_button_and_resets_the_choice(self):
        world = InterfaceWorld()
        world.call("OpenPrivateShopInputNameDialog")
        dialog = world.dialogs[-1]
        self.assertEqual((world.builder.SHOP_DECO, world.builder.SHOP_STYLE), (0, 0), "OLD interfaceModule.py:3494-3495")
        self.assertEqual([call[:2] for call in world.calls("decoButton.")],
                         [("decoButton.SetEvent", (world.interface.OpenMyShopDecoWnd,)), ("decoButton.Show", ())])
        self.assertEqual(dialog.max, 32)
        self.assertTrue(dialog.opened)
        self.assertIs(world.interface.inputDialog, dialog)

    def test_the_name_dialog_without_a_deco_button_still_opens(self):
        world = InterfaceWorld()
        world.common.InputDialog = world.PlainInputDialog
        world.call("OpenPrivateShopInputNameDialog")
        self.assertTrue(world.dialogs[-1].opened)

    def test_cancel_sends_leave_and_accept_opens_the_builder(self):
        world = InterfaceWorld()
        world.call("OpenPrivateShopInputNameDialog")
        with world:
            world.dialogs[-1].cancel()
        self.assertEqual(world.calls("net."), [("net.SendOfflineShopLeavePacket", (), {})])
        self.assertIsNone(world.interface.inputDialog)
        world.call("OpenPrivateShopInputNameDialog")
        dialog = world.dialogs[-1]
        dialog.text = "My shop"
        with world:
            dialog.accept()
        self.assertEqual(world.calls("privateShopBuilder."), [("privateShopBuilder.Open", ("My shop",), {})])
        self.assertEqual(len(world.calls("net.")), 1, "no LEAVE on accept")
        self.assertIsNone(world.interface.inputDialog)


class InterfaceWindows(unittest.TestCase):
    def test_y2_s_windows_are_made_bound_and_destroyed(self):
        methods = class_methods("interfacemodule.py", "Interface")
        for attribute, made in (("wndSearchShop", "nui_windows.make('shop-search', uiSearchShop.SearchShopWindow, 'nui_shop_search.SearchShopWindow')"),
                                ("wndOfflineShopLog", "nui_windows.make('offline-shop-log', uiOfflineShopLog.OfflineShopLogWindow, 'nui_offline_shop_log.OfflineShopLogWindow')"),
                                ("wndMyShopDeco", "nui_windows.make('shop-deco', uiMyShopDecoration.MyShopDecorationWindow, 'nui_shop_deco.MyShopDecorationWindow')")):
            with self.subTest(window=attribute):
                self.assertIn("self.%s = %s" % (attribute, made), methods["__MakeWindows"])
                self.assertIn("self.%s.BindInterface(self)" % attribute, methods["__MakeWindows"])
                self.assertIn("self.%s.Destroy()" % attribute, methods["Close"])
                self.assertIn("self.%s = None" % attribute, methods["__init__"])
        made = [line for line in methods["__MakeWindows"].split("\n") if "nui_windows.make" in line]
        self.assertEqual(len([line for line in made if "uiSearchShop" in line]), 1)
        self.assertEqual(len([line for line in made if "uiOfflineShopLog" in line]), 1)
        self.assertEqual(len([line for line in made if "uiMyShopDecoration" in line]), 1)

    def test_the_whisper_opener_y2_calls_exists(self):
        self.assertIn("OpenWhisperDialog", class_methods("interfacemodule.py", "Interface"))

    def hiding_interface(self):
        """HideAllWindows and __HideWindows, compiled from interfacemodule.py
        over an Interface whose every other window is a shown stand-in."""

        class Window(object):
            def __init__(self):
                self.shown = True

            def Show(self):
                self.shown = True

            def Hide(self):
                self.shown = False

            def IsShow(self):
                return self.shown

            def IsEditMode(self):
                return False

        class InterfaceBase(object):
            questButtonSuppressed = False

            def __getattr__(self, attr):
                if not attr.startswith(("wnd", "dlg")):
                    raise AttributeError(attr)
                window = Window()
                setattr(self, attr, window)
                return window

            def HideAllQuestButton(self):
                pass

            def HideAllWhisperButton(self):
                pass

        source = support.source_of("interfacemodule.py", ("HideAllWindows", "__HideWindows"), inside="Interface")
        body = "\n".join("\t" + line if line else line for line in source.split("\n"))
        namespace = {"InterfaceBase": InterfaceBase, "app": types.SimpleNamespace(ENABLE_DRAGON_SOUL_SYSTEM=1)}
        exec(compile("class Interface(InterfaceBase):\n%s\n" % body, "interfacemodule.py", "exec"), namespace)
        return namespace["Interface"](), Window

    def test_a_hide_all_hides_the_decoration_window_as_old(self):
        """OLD interfaceModule.py:2761-2762 (HideAllWindows) and 3369-3370
        (__HideWindows, the HUD hide of a quest dialog or the guild building,
        which shows the same windows again)."""
        interface, Window = self.hiding_interface()
        interface.wndMyShopDeco = deco = Window()
        interface.wndGemShop = market = Window()
        interface.HideAllWindows()
        self.assertFalse(deco.IsShow())
        # OLD hides no other wave-5 window. The gaya market closes through
        # CloseShop, which tells the server: a bare Hide would keep its market
        # session, and with it the busy-window rule, open.
        self.assertTrue(market.IsShow())

        interface, Window = self.hiding_interface()
        interface.wndMyShopDeco = deco = Window()
        hidden = interface._Interface__HideWindows()
        self.assertIn(deco, hidden)
        self.assertFalse(deco.IsShow())

        interface, Window = self.hiding_interface()
        interface.wndMyShopDeco = deco = Window()
        deco.Hide()
        self.assertNotIn(deco, interface._Interface__HideWindows(), "a closed window is not shown again")

    def test_a_hide_all_without_the_decoration_window_still_hides(self):
        interface, Window = self.hiding_interface()
        interface.wndMyShopDeco = None
        interface.HideAllWindows()
        self.assertFalse(interface.wndTaskBar.IsShow())

        interface, Window = self.hiding_interface()
        interface.wndMyShopDeco = None
        hidden = interface._Interface__HideWindows()
        self.assertIn(interface.wndTaskBar, hidden)
        self.assertNotIn(None, hidden)


# --- the inventory ------------------------------------------------------------------------------

class InventoryButtons(unittest.TestCase):
    def world(self, enabled=True):
        world = xinv.World()
        world.game.interface.OpenSearchShop = lambda vnum=0: world.game.log.append(("interface.OpenSearchShop", (vnum,)))
        window = lf.make_inventory(world)
        if enabled is not None:
            with world:
                window.ShowOfflineShopButtons(enabled)
        return world, window

    def test_both_uiscripts_have_the_two_buttons_between_the_bag_and_the_money(self):
        for path in (os.path.join(UISCRIPT, "inventorywindow.py"), os.path.join(LOCALES, "ae", "ui", "inventorywindow.py")):
            with self.subTest(path=path):
                world = xinv.World()
                with world:
                    window = lf.read_uiscript(path)["window"]
                locale = world.game.modules["localeInfo"]
                board = lf.child(window, "board")
                extra = lf.child(window, "ExtraInventoryButton")
                money = lf.child(window, "Money_Slot")
                self.assertEqual(window["height"], board["height"])
                buttons = [lf.child(window, name) for name in ("OfflineShopButton", "SearchShopButton")]
                self.assertEqual([b["text"] for b in buttons], [locale.OFFLINE_SHOP_BUTTON, locale.SEARCH_SHOP_BUTTON])
                self.assertEqual([b["tooltip_text"] for b in buttons],
                                 [locale.OFFLINE_SHOP, world.game.modules["uiScriptLocale"].SEARCH_SHOP_TITLE])
                for button in buttons:
                    self.assertEqual(button["default_image"], "d:/ymir work/ui/public/middle_button_01.sub")
                    self.assertGreaterEqual(button["y"], extra["y"] + 21, "under the special inventory's button")
                    self.assertLessEqual(button["y"] + 21, board["height"] - money["y"], "over the money slot")
                    self.assertGreaterEqual(button["x"], 8)
                    self.assertLessEqual(button["x"] + 61, board["width"] - 8)
                self.assertGreaterEqual(buttons[1]["x"], buttons[0]["x"] + 61, "side by side")

    def test_the_offline_shop_button_sends_manage_and_search_opens_the_search(self):
        world, window = self.world()
        with world, lf.quiet():
            window.offlineShopButton.Click()
            window.searchShopButton.Click()
        self.assertEqual(world.sent("net.SendOfflineShopManagePacket"), [("net.SendOfflineShopManagePacket", ())])
        self.assertEqual(world.game.calls("interface.OpenSearchShop"), [("interface.OpenSearchShop", (0,))])

    def test_the_buttons_are_hidden_until_config_says_enabled(self):
        world, window = self.world(enabled=None)
        self.assertEqual((window.offlineShopButton.IsShow(), window.searchShopButton.IsShow()), (False, False))
        with world:
            window.ShowOfflineShopButtons(True)
        self.assertEqual((window.offlineShopButton.IsShow(), window.searchShopButton.IsShow()), (True, True))
        with world:
            window.ShowOfflineShopButtons(False)
        self.assertEqual((window.offlineShopButton.IsShow(), window.searchShopButton.IsShow()), (False, False))

    def test_ctrl_click_on_an_item_searches_it(self):
        world, window = self.world()
        world.game.give(3, 27001, 5)
        world.press("DIK_LCONTROL")
        with world, lf.quiet():
            window.wndItem.fire("select_item", 3)
        self.assertEqual(world.game.calls("interface.OpenSearchShop"), [("interface.OpenSearchShop", (27001,))])
        self.assertFalse(world.mouse.isAttached(), "nothing picked up")
        self.assertEqual(world.game.calls("player.RequestAddToEmptyLocalQuickSlot"), [])

    def test_ctrl_click_with_the_safebox_open_or_the_shop_off_adds_a_quick_slot_as_before(self):
        for safebox, enabled in ((True, True), (False, False)):
            with self.subTest(safebox=safebox, enabled=enabled):
                world, window = self.world(enabled)
                world.game.give(3, 27001, 5)
                world.game.safebox = safebox
                world.press("DIK_LCONTROL")
                with world, lf.quiet():
                    window.wndItem.fire("select_item", 3)
                self.assertEqual(world.game.calls("interface.OpenSearchShop"), [])
                self.assertEqual([name for name, args in world.game.calls("player.RequestAddToEmptyLocalQuickSlot")],
                                 ["player.RequestAddToEmptyLocalQuickSlot"])

    def test_a_loader_without_the_buttons_keeps_them_none(self):
        world = xinv.World()
        module = world.load("uiInventory", "uiinventory.py")
        for name in ("offlineShopButton", "searchShopButton"):
            self.assertIsNone(getattr(module.InventoryWindow, name), name)
        self.assertIs(module.InventoryWindow.offlineShopEnabled, False)
        window = object.__new__(module.InventoryWindow)
        window.ShowOfflineShopButtons(True)
        self.assertTrue(window.offlineShopEnabled)


# --- the hide-shops option --------------------------------------------------------------------------

class HideShops(unittest.TestCase):
    def world(self, hidden):
        world = sys_test.World(False)
        state = {"hidden": hidden}
        world.game.answer("shop", "IsHideShops", lambda: state["hidden"])
        world.state = state
        world.__enter__()
        self.addCleanup(world.__exit__)
        dialog = world.make_game_options()
        dialog.Show()
        return world, dialog

    def buttons(self, dialog):
        return [button.down for button in dialog.hideShopsButtonList]

    def test_the_option_shows_the_server_s_state(self):
        world, dialog = self.world(False)
        self.assertEqual(self.buttons(dialog), [True, False], "shops shown")
        world, dialog = self.world(True)
        self.assertEqual(self.buttons(dialog), [False, True], "shops hidden")

    def test_a_press_sends_the_command_and_waits_for_the_server(self):
        world, dialog = self.world(False)
        mark = world.mark()
        with sys_test.quiet():
            dialog.hideShopsButtonList[1].click()
        self.assertEqual(world.effects_since(mark), [("net.SendChatPacket", ("/hide_shops 1",))])
        self.assertEqual(self.buttons(dialog), [True, False], "no local guess")
        world.state["hidden"] = True
        dialog.RefreshHideShops()
        self.assertEqual(self.buttons(dialog), [False, True])
        mark = world.mark()
        with sys_test.quiet():
            dialog.hideShopsButtonList[0].click()
        self.assertEqual(world.effects_since(mark), [("net.SendChatPacket", ("/hide_shops 0",))])

    def test_a_press_on_the_state_in_effect_sends_nothing(self):
        world, dialog = self.world(True)
        mark = world.mark()
        with sys_test.quiet():
            dialog.hideShopsButtonList[1].click()
        self.assertEqual(world.effects_since(mark), [])

    def test_the_row_has_old_s_label_and_today_s_show_and_hide(self):
        world, dialog = self.world(False)
        self.assertEqual(dialog.hideShopsLabel.text, "OPTION_SHOW_COMPANIONS_SHOPS")
        self.assertEqual([button.text for button in dialog.hideShopsButtonList],
                         ["OPTION_SALESTEXT_VIEW_ON", "OPTION_SALESTEXT_VIEW_OFF"])


# --- the tooltip --------------------------------------------------------------------------------------

class OfflineShopToolTip(unittest.TestCase):
    SWORD = dict(lf.ITEM_BASE, name="Sword+0", type=1, subtype=0, size=[1, 2], wear=16, values=[0, 0, 15, 19, 13, 15],
                 icon="icon/item/00010.tga")
    HINTS = ("OFFLINE_SHOP_TOOLTIP_WITHDRAW", "OFFLINE_SHOP_TOOLTIP_CHANGE_PRICE", "OFFLINE_SHOP_TOOLTIP_REMOVE")

    def texts(self, owner, vnum=10, items=None, sockets=(0, 0, 0, 0), price=2500000, pending=False):
        corpus_tool, world = lf.tooltip_world(items or {10: self.SWORD})
        game = world.game
        shop = game.modules["shop"]
        held = {"vnum": vnum, "sockets": list(sockets), "price": price}
        support.define(shop, "GetOfflineShopItemID", lambda slot: held["vnum"] if slot == 17 else 0)
        support.define(shop, "GetOfflineShopItemCount", lambda slot: 1)
        support.define(shop, "GetOfflineShopItemPrice", lambda slot: held["price"] if slot == 17 else 0)
        support.define(shop, "GetOfflineShopItemMetinSocket", lambda slot, i: held["sockets"][i] if slot == 17 else 0)
        support.define(shop, "GetOfflineShopItemAttribute", lambda slot, i: (0, 0))
        support.define(shop, "IsOwner", lambda: owner)
        support.define(shop, "IsOfflineShopSlotPending", lambda slot: pending and slot == 17)
        case = {"context": "calls", "vnum": vnum, "calls": [["SetOfflineShopItem", [17]]], "clock": premium_test.CLOCK}
        texts, error = lf.tooltip_texts(corpus_tool, world, case)
        self.assertIsNone(error)
        return texts, game

    def test_a_buyer_sees_the_item_and_its_price_and_no_owner_hints(self):
        texts, game = self.texts(False)
        locale = game.modules["localeInfo"]
        self.assertIn("Sword+0", texts)
        self.assertTrue(any("2.500.000" in text for text in texts), texts)
        for key in self.HINTS:
            self.assertNotIn(ENGLISH[key], texts)
        self.assertEqual(game.calls("shop.GetItemID"), [], "the offline getters, not the NPC shop's")

    def test_the_owner_sees_the_three_key_hints_in_plain_text(self):
        texts, game = self.texts(True)
        self.assertEqual(texts[-3:], [ENGLISH[key] for key in self.HINTS])

    def test_a_pending_slot_says_so_and_offers_no_action(self):
        texts, game = self.texts(True, pending=True)
        self.assertEqual(texts[-1], "This item is being transferred.")
        for key in self.HINTS:
            self.assertNotIn(ENGLISH[key], texts)

    def test_an_empty_slot_shows_nothing(self):
        texts, game = self.texts(False, vnum=0)
        self.assertEqual(texts, [])

    def test_a_listed_returned_premium_scroll_keeps_its_time_left(self):
        """X5's tooltip half, through the offline getters."""
        scroll = dict(premium_test.SCROLL, values=[0, 1, premium_test.SCROLL_SECONDS, 0, 0, 0])
        texts, game = self.texts(False, vnum=50208, items={50208: scroll},
                                 sockets=(premium_test.CLOCK + 2 * premium_test.DAY, 0, 0, 0))
        locale = game.modules["localeInfo"]
        self.assertIn(locale.LEFT_TIME + " : " + locale.SecondToDHM(2 * premium_test.DAY), texts)


# --- the locales ----------------------------------------------------------------------------------------

def wave_keys():
    """{file: keys} of every wave key (spec 5.7), Y1's whole block."""
    game = list(premium_test.PREMIUM_KEYS) + list(gem_shop_test.GAYA_GAME_KEYS) + list(OLD_GAME_KEYS) + list(NEW_GAME_KEYS)
    interface = list(gem_shop_test.GAYA_INTERFACE_KEYS) + list(OLD_INTERFACE_KEYS) + list(OPTION_KEYS)
    return {"locale_game.txt": game, "locale_interface.txt": interface}


class Locales(unittest.TestCase):
    def test_every_locale_has_every_wave_key_in_one_block(self):
        """Wave 5's keys are one block of plain entries; wave 6 (NOVA-19 to
        NOVA-23) appends its own after it."""
        for locale in lf.locales():
            for file_name, keys in wave_keys().items():
                with self.subTest(locale=locale, file=file_name):
                    path = os.path.join(LOCALES, locale, file_name)
                    with open(path, encoding="utf-8") as handle:
                        text = handle.read()
                    self.assertTrue(text.endswith("\n"))
                    self.assertNotIn("\r", text)
                    lines = text.split("\n")[:-1]
                    names = [line.split("\t")[0] for line in lines]
                    for key in keys:
                        self.assertEqual(names.count(key), 1, key)
                    first = min(names.index(key) for key in keys)
                    block = slice(first, first + len(keys))
                    self.assertEqual(sorted(names[block]), sorted(keys), "one block")
                    for line in lines[block]:
                        self.assertEqual(len(line.split("\t")), 2, "plain entries: %r" % line)
                        self.assertTrue(line.split("\t")[1], "a text: %r" % line)

    def test_the_result_texts_take_an_arg_only_where_the_code_carries_one(self):
        for locale in lf.locales():
            game = lf.read_locale(locale)
            for name in RESULT_NAMES:
                with self.subTest(locale=locale, code=name):
                    text = game["OFFLINE_SHOP_RESULT_" + name][0]
                    self.assertEqual(text.count("%s"), 1 if name in RESULTS_WITH_ARG else 0, text)
                    self.assertEqual(text.replace("%s", "").count("%"), 0, text)

    def test_the_spec_s_texts_and_old_s_names(self):
        english = dict(lf.read_locale("en"))
        english.update(lf.read_locale("en", "locale_interface.txt"))
        for key, text in ENGLISH.items():
            self.assertEqual(english[key][0], text, key)
        for index, text in enumerate(LOG_ACTIONS):
            self.assertEqual(english["OFFLINE_SHOP_LOG_ACTION_%d" % index][0], text)
        for key in ("OFFLINE_SHOP_TOOLTIP_WITHDRAW", "OFFLINE_SHOP_TOOLTIP_CHANGE_PRICE", "OFFLINE_SHOP_TOOLTIP_REMOVE"):
            for locale in lf.locales():
                self.assertNotIn("|E", lf.read_locale(locale)[key][0], "no key-icon tags (NEW has no key-icon art)")
        for misspelled in ("SEARCH_SHOP_PREMIMUM_STATUS", "SEARCH_SHOP_BUY_CONFIGM"):
            self.assertIn(misspelled, english, "OLD's spelling stays")

    def test_the_format_specifiers_match_english_everywhere(self):
        english = {name: dict(lf.read_locale("en", name)) for name in ("locale_game.txt", "locale_interface.txt")}
        for locale in lf.locales():
            for file_name, keys in wave_keys().items():
                values = lf.read_locale(locale, file_name)
                for key in keys:
                    with self.subTest(locale=locale, key=key):
                        self.assertEqual(re.findall(r"%[-0-9.]*[sdif]", values[key][0]),
                                         re.findall(r"%[-0-9.]*[sdif]", english[file_name][key][0]))


def shop_deco_rows(text):
    """The rows of a shop_deco.txt, split on tabs, without blank and # lines."""
    return [line.split("\t") for line in text.split("\n") if line.strip() and not line.startswith("#")]


def shop_deco_models(rows):
    """The model vnums the rows name, in file order: the third column of each
    type-1 row, as OLD's reader takes them (Op:playerSettingModule.py:2229-2247,
    `__LoadShopDeco`: tokens[0] is the type, a type-1 row appends tokens[2])."""
    return [int(row[2]) for row in rows if row[0].strip() == "1" and len(row) > 2 and row[2].strip().isdigit()]


class ShopDeco(unittest.TestCase):
    def test_the_rows_are_read_in_old_s_format(self):
        """OLD's format, which Y2 keeps: a type-1 row is `1<TAB>name<TAB>model
        vnum` and a type-2 row `2<TAB>name<TAB>pattern<TAB>0xRRGGBB` (a title
        style). Runs while shop_deco.txt is absent, so the parse is checked
        before Y2 folds in."""
        text = ("# type\tname\tvnum or pattern\tcolor\n"
                "1\tDefault\t30000\n"
                "1\t1001 Nights\t30002\n"
                "\n"
                "2\tInferno\td:/ymir work/ui/pattern/myshop/fire/p_fire\t0xFF976D\n")
        self.assertEqual(shop_deco_models(shop_deco_rows(text)), [30000, 30002])

    def test_the_decoration_list_names_the_shipped_models(self):
        """Y2's shop_deco.txt against the runtime's OFFLINE_SHOP_MODELS (spec
        5.8: nova-server share/conf/game.txt ships 30000; the list there is
        the source, pinned here as SHIPPED_MODELS). Every model the server
        can send has a row in every locale's file; a file may name more
        (OLD's eight)."""
        paths = [os.path.join(LOCALES, name, "shop_deco.txt") for name in sorted(os.listdir(LOCALES))]
        paths = [path for path in paths if os.path.isfile(path)]
        if not paths:
            self.skipTest("shop_deco.txt is chunk Y2's; it runs once Y2 folds in")
        for path in paths:
            with self.subTest(path=path):
                with open(path, encoding="utf-8") as handle:
                    models = shop_deco_models(shop_deco_rows(handle.read()))
                for vnum in SHIPPED_MODELS:
                    self.assertIn(vnum, models)


if __name__ == "__main__":
    unittest.main()
