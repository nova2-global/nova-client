"""How an inventory cell glows (NOVA-188): a newly received item until the
pointer passes over it, and an active item by its kind. Both inventories and
both UIs use it.

OLD (interfaceModule.py:2965-2978, uiInventory.py:1450-1545 and 2145-2151,
settingsData.py:201): the server flags an item that arrives from outside in
its ITEM_SET (TPacketGCItemSet.highlight); game.py's BINARY_Highlight_Item
reaches Interface.Highligt_Item, which marks the cell here. The cell glows
until a hover clears it. An active auto potion, pet, mount, tag, buff or
buffi item glows in its kind's color instead.

The colors tint the slot's active effect (wndMgr.ActivateSlot's color, a
0xRRGGBB; 0 is the untinted glow). NovaUI's slot proxies turn a color into
its name (GLOW_NAMES), which the cell's is-glow-<name> class draws.

The "new" marks are cells of a window: (player.INVENTORY, 37). They live for
the game phase (forget_all at its end) and leave a cell that empties."""

import item
import player
import constInfo

try:
	import systemSetting
except ImportError:  # plain Python outside the client
	systemSetting = None

# The tints (default, Eddy to confirm): OLD's red, blue, yellow and cyan, a
# violet for the effect tags (OLD showed them cyan), and the untinted glow
# for a new item (OLD's "new item" art is in neither OLD's nor NEW's pack).
RED = 0xFF3030
BLUE = 0x3070FF
YELLOW = 0xFFE040
CYAN = 0x03FCE3
VIOLET = 0xC080FF
NEW_ITEM = 0

COLORS = {
	"hp_potion": RED,
	"sp_potion": BLUE,
	"mount": YELLOW,
	"buff": RED,
	"pet": CYAN,
	"tag": VIOLET,
	"buffi": YELLOW,
}

# NovaUI's names of the tints (the cell's is-glow-<name> class).
GLOW_NAMES = {RED: "red", BLUE: "blue", YELLOW: "yellow", CYAN: "cyan", VIOLET: "violet"}

# The option turns off the "new" glow only; the active kinds keep their
# colors (default, Eddy to confirm: OLD's switch dropped the potions' active
# look too). True makes the option turn the kind colors into the plain glow.
OPTION_GATES_KIND_COLORS = False

# NEW's item data (ItemData.h), named here as uiinventory does, so every test
# world runs this module.
TOGGLE_ITEM_TYPE = 37
TOGGLE_PET, TOGGLE_MOUNT, TOGGLE_EFFECT, TOGGLE_BUFF = 0, 1, 2, 3
TOGGLE_ON_SOCKET = 3
PET_ITEM_TYPE = 39
PET_SUMMON = 1
PET_SUMMONED_SOCKET = 3
FAKEBUFF_ON_SOCKET = 3
AUTO_POTION_ON_SOCKET = 0

_new = set()   # (window, cell) of the items that arrived and were not hovered yet


def enabled():
	"""The option (systemSetting.IsShowNewItemHighlight, on by default)."""
	getter = getattr(systemSetting, "IsShowNewItemHighlight", None)
	return True if getter is None else bool(getter())


def mark_new(window, cell):
	"""An item arrived in the cell (the server's highlight flag). False when
	the option is off, so nothing is marked."""
	if not enabled():
		return False
	_new.add((int(window), int(cell)))
	return True


def is_new(window, cell):
	return (int(window), int(cell)) in _new


def clear_new(window, cell):
	"""The pointer passed over the cell: True when it was new, so the caller
	refreshes it."""
	key = (int(window), int(cell))
	if key in _new:
		_new.discard(key)
		return True
	return False


def forget_all():
	_new.clear()


def _socket(window, cell, index):
	if window == player.INVENTORY:
		return player.GetItemMetinSocket(cell, index)
	return player.GetItemMetinSocket(window, cell, index)


def active_kind(window, cell, vnum):
	"""The kind of an active item in the cell (a key of COLORS), or None."""
	if not vnum:
		return None
	if constInfo.IS_AUTO_POTION(vnum):
		if 0 == _socket(window, cell, AUTO_POTION_ON_SOCKET):
			return None
		return "hp_potion" if constInfo.IS_AUTO_POTION_HP(vnum) else "sp_potion"
	if constInfo.IS_FAKEBUFF_ITEM(vnum):
		return "buffi" if 0 != _socket(window, cell, FAKEBUFF_ON_SOCKET) else None
	item.SelectItem(vnum)
	item_type = item.GetItemType()
	if item_type == TOGGLE_ITEM_TYPE:
		if 0 == _socket(window, cell, TOGGLE_ON_SOCKET):
			return None
		return {TOGGLE_PET: "pet", TOGGLE_MOUNT: "mount", TOGGLE_EFFECT: "tag", TOGGLE_BUFF: "buff"}.get(
			item.GetItemSubType(), "buff")
	if item_type == PET_ITEM_TYPE and item.GetItemSubType() == PET_SUMMON:
		return "pet" if 0 != _socket(window, cell, PET_SUMMONED_SOCKET) else None
	return None


def cell_glow(window, cell, vnum):
	"""What the cell shows: a color to pass to ActivateSlot (0: the untinted
	glow), or None for no glow. An active item's kind wins over "new"."""
	kind = active_kind(window, cell, vnum)
	if kind is not None:
		if OPTION_GATES_KIND_COLORS and not enabled():
			return 0
		return COLORS[kind]
	if vnum and enabled() and is_new(window, cell):
		return NEW_ITEM
	return None


def glow_name(color):
	"""NovaUI's name of a tint ("" for the untinted glow)."""
	return GLOW_NAMES.get(int(color or 0), "")


def show(slot_window, local, window, cell, vnum):
	"""Applies cell_glow to the slot `local` of a legacy or NovaUI slot window."""
	color = cell_glow(window, cell, vnum)
	if color is None:
		slot_window.DeactivateSlot(local)
	elif color:
		slot_window.ActivateSlot(local, color)
	else:
		slot_window.ActivateSlot(local)
