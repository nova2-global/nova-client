"""What the wave 6 tests share (NOVA-19 to NOVA-23, chunk Y: the legacy
Python of the arrows, the sash, the weapon costume, the hidden costume and
the aura): the names chunk C's client exports for them, which are OLD's
(common-6.md "Python names on the client"), with C's values, stood in on
nui_game_support's modules while tools/fixtures/module_constants.json is
main's; the legacy worlds; the tooltip helpers; the locale check.

C's values are OLD's client's and NEW's GameLib/ItemData.h's: COSTUME_WEAPON 2,
COSTUME_SASH 3, COSTUME_AURA 10, WEAPON_UNLIMITED_ARROW 9, RESOURCE_AURA 12
(OLD PythonItemModule.cpp:1005); the cells from the cut's equipment start
(225): the costume sash wear 21, the weapon costume 22, the aura 39 (OLD
GameType.h:62-188); OLD's aura modes and slots (PythonItemModule.cpp:998-1003),
its aura wing flags (PythonPlayer.h:814-817) and its sash module's constants
(PythonSash.cpp:187-193, Packet.h:3821-3825)."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402

ROOT = support.ROOT
UISCRIPT = lf.UISCRIPT
EQUIPMENT_START = lf.EQUIPMENT_START
COSTUME_START = EQUIPMENT_START + 19

C_ITEM = {
    "COSTUME_TYPE_WEAPON": 2, "COSTUME_TYPE_SASH": 3, "COSTUME_TYPE_AURA": 10,
    "COSTUME_SLOT_SASH": EQUIPMENT_START + 21, "COSTUME_SLOT_WEAPON": EQUIPMENT_START + 22,
    "COSTUME_SLOT_AURA": EQUIPMENT_START + 39,
    "AURA_MODE_CLOSE": 0, "AURA_MODE_MAIN": 1, "AURA_MODE_MAX": 2, "AURA_SLOT_MAIN": 0, "AURA_SLOT_MATERIAL": 1,
    "RESOURCE_AURA": 12, "ITEM_TYPE_RESOURCE": 14, "ITEM_TYPE_COSTUME": 28, "ITEM_TYPE_WEAPON": 1,
    "ITEM_TYPE_ARMOR": 2, "WEAPON_ARROW": 6, "WEAPON_CLAW": 8, "WEAPON_UNLIMITED_ARROW": 9,
}
C_PLAYER = {"AURA_WING_FLAG_WING": 1 << 0, "AURA_WING_FLAG_AURA": 1 << 1, "AURA_WING_FLAG_EFFECT": 1 << 2,
            "AURA_WING_FLAG_ALL": 0x07}
C_SASH = {"ABSORPTION_SOCKET": 0, "ABSORBED_SOCKET": 1, "CLEAN_ATTR_VALUE0": 7, "TAKE_ATTR_VALUE0": 9,
          "WINDOW_MAX_MATERIALS": 2, "CLEAN_ATTR_VALUE_FIELD": 0, "LIMIT_RANGE": 1000}

# The vnums of NEW's runtime item_proto (nova-server share/conf/item_proto.txt).
QUIVER = 79501          # WEAPON_UNLIMITED_ARROW, REAL_TIME_FIRST_USE 86400
SASH = 85001            # COSTUME_SASH, "Lord Sash (basic)"
SASH_NEXT = 85002
AURA = 149001           # COSTUME_AURA, tier 1
AURA_LAST = 149006      # the last tier
AURA_STONE = 149988     # an aura material (RESOURCE_AURA) for the tests
WEAPON_COSTUME = 40108
BODY_COSTUME = 41001
SWORD = 10


def install_c(game, sash_state=None):
    """C's names on the world's modules, and a sash module (C's
    PythonSash.cpp) whose calls are logged as "sash.<name>" and whose
    getters answer from `sash_state` (SashState)."""
    item, player = game.modules["item"], game.modules["player"]
    for name, value in C_ITEM.items():
        setattr(item, name, value)
    for name, value in C_PLAYER.items():
        setattr(player, name, value)
    state = sash_state or SashState()
    module = support.Recording("sash", game.log, **C_SASH)
    support.define(module, "GetPrice", lambda: state.price)
    support.define(module, "GetAttachedItem", lambda slot: state.attached.get(slot, (False, 0)))
    support.define(module, "GetResultItem", lambda: state.result)
    game.put("sash", module)
    game.sash_state = state
    # localeinfo.py's NumberToString (wave 6) beside the stand-in's helpers.
    locale = game.modules.get("localeInfo")
    if locale is not None and not callable(getattr(locale, "NumberToString", None)):
        exec(compile(support.source_of("localeinfo.py", ["NumberToString"]), "localeinfo.py", "exec"), locale.__dict__)
    shown = game.shown_costumes = {"IsShowCostumes": 1, "IsShowHair": 1, "IsShowWeapon": 1, "IsShowSash": 1,
                                   "GetAuraWingFlags": C_PLAYER["AURA_WING_FLAG_ALL"]}
    for name in shown:
        support.define(player, name, lambda name=name: shown[name])
    return state


class SashState(object):
    """What C's CPythonSash holds after the server's GC::SASH frames."""

    def __init__(self):
        self.price = 0
        self.attached = {}
        self.result = (0, 0, 0)


class CheckBox(object):
    """ui.CheckBox (ui.py:3783-3843) as the legacy windows use it: a left
    click flips it and calls its ON_CHECK or ON_UNCHECK event."""

    def __init__(self, layer="UI"):
        self.checked = False
        self.text = ""
        self.shown = False
        self.position = (0, 0)
        self.events = {"ON_CHECK": None, "ON_UNCHECK": None}

    def SetParent(self, parent):
        pass

    def SetPosition(self, x, y):
        self.position = (x, y)

    def SetWindowHorizontalAlignCenter(self):
        pass

    def SetTextInfo(self, text):
        self.text = text

    def SetCheckStatus(self, flag):
        self.checked = bool(flag)

    def GetCheckStatus(self):
        return self.checked

    def SetEvent(self, func, kind):
        if kind in self.events:
            self.events[kind] = func

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def OnMouseLeftButtonUp(self):
        self.SetCheckStatus(not self.checked)
        event = self.events["ON_CHECK" if self.checked else "ON_UNCHECK"]
        if event:
            event()
        return True


class World(lf.LegacyWorld):
    """The cut's legacy world with C's names, and ui.CheckBox."""

    def __init__(self):
        lf.LegacyWorld.__init__(self)
        install_c(self.game)
        self.game.interface.IsSafeboxOpen = lambda: False
        ui = self.game.modules["ui"]
        if not hasattr(ui, "CheckBox") or not isinstance(getattr(ui, "CheckBox"), type):
            ui.CheckBox = CheckBox
        # main's exe (wave 4b, K's values; extra_inventory_test's install_k):
        # the special inventory's window and slot type, SlotTypeToInvenType.
        player = self.game.modules["player"]
        player.EXTRA_INVENTORY, player.SLOT_TYPE_EXTRA_INVENTORY = 6, 12
        windows = {player.SLOT_TYPE_INVENTORY: player.INVENTORY, 8: 3, 10: 4, 11: 5, 12: 6}
        support.define(player, "SlotTypeToInvenType", lambda slot_type: windows.get(slot_type, 0))

    def sent(self, prefix):
        return [call for call in self.game.log if call[0].startswith(prefix)]

    def chat_commands(self):
        return [args[0] for name, args in self.game.log if name == "net.SendChatPacket"]

    @property
    def mouse(self):
        return self.game.modules["mouseModule"].mouseController

    def attach(self, slot_type, slot, vnum, count=1):
        with self.game, lf.quiet():
            self.mouse.AttachObject(object(), slot_type, slot, vnum, count)


def make_inventory(world):
    """The legacy inventory as the Interface makes it, shown."""
    window = lf.make_inventory(world)
    window.SetDragonSoulRefineWindow(world.game.dragon_soul_refine)
    return window


def costume_window(world):
    """The inventory and its costume window, opened by its button."""
    inventory = make_inventory(world)
    with world.game, lf.quiet():
        inventory.ClickCostumeButton()
    return inventory, inventory.wndCostume


def toggles(widget):
    """The (up, down) events a legacy toggle button was given."""
    up = [call[1] for call in widget.calls if call[0] == "SetToggleUpEvent"]
    down = [call[1] for call in widget.calls if call[0] == "SetToggleDownEvent"]
    return (up[-1] if up else None, down[-1] if down else None)


def last_state(widget):
    """"down" or "up": the last of Down() and SetUp() a button was told."""
    for call in reversed(widget.calls):
        if call[0] == "Down":
            return "down"
        if call[0] == "SetUp":
            return "up"
    return None


# --- the tooltips -----------------------------------------------------------------------------------------

ITEM_BASE = lf.ITEM_BASE


def tooltip_world(items):
    """uitooltip.py over the corpus stand-ins with `items` and C's names."""
    corpus_tool, world = lf.tooltip_world(items)
    install_c(world.game)
    return corpus_tool, world


def tooltip_texts(corpus_tool, world, case):
    return lf.tooltip_texts(corpus_tool, world, case)


def call_texts(corpus_tool, world, case, call, extra_items=None):
    """The text rows of the item tooltip after `call(tip)`, with the case's
    state and `extra_items` ({pos: held}) beside its item."""
    base = {"sockets": [0, 0, 0, 0], "attrs": [], "player": {"level": 150, "race": 0}, "clock": 1700000000}
    base.update(case)
    with world.game, lf.quiet():
        support.apply_case(world.game, base)
        for pos, held in (extra_items or {}).items():
            world.data.case["items"][pos] = dict({"count": 1, "sockets": [0, 0, 0, 0], "attrs": [], "flags": 0,
                                                  "sell_price": 0}, **held)
        tip = world.tooltip("item")
        call(tip)
        rows = corpus_tool.stand_in_rows(tip)
    return [row[1] for row in rows if row[0] == "text"]


# --- the locales ----------------------------------------------------------------------------------------------

def locale_keys(name="locale_game.txt"):
    return dict((locale, lf.read_locale(locale, name)) for locale in lf.locales())


def check_keys(test, keys, name="locale_game.txt"):
    """Every key in every locale, a plain entry with the English text's
    format specifiers; the English text is `keys`'."""
    for locale, entries in locale_keys(name).items():
        for key, english in keys.items():
            with test.subTest(locale=locale, key=key):
                test.assertIn(key, entries)
                test.assertEqual(entries[key][1], "", "%s: no type column" % key)
                test.assertEqual(specifiers(entries[key][0]), specifiers(english))
    english = lf.read_locale("en", name)
    for key, text in keys.items():
        test.assertEqual(english[key][0], text, key)


def specifiers(text):
    import re
    return re.findall(r"%[-0-9.]*[sdif]", text.replace("%%", ""))


def module_with(name, **members):
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module
