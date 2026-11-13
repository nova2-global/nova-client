"""Alt + hover costume preview on the player's own character (NOVA-202).

Holding the preview key (the "show names" hold action, Alt by default) over a
costume in a shop, the exchange, the cube or the shop search shows it on the
player's own model in a small popup. OLD (uiShop.py:1154, uiExchange.py:447,
uiCube.py:757, uiCubeRenewal.py:1205, uiSearchShop.py:686, uiCommon.py:45)
changed the player's live character for that (chr.ChangeShape,
player.SetPreviewMode) and put it back on hover out; NEW never touches the
live model: the popup has its own, on the model preview engine
(CPythonModelPreview, the modelpreview module, preview name PREVIEW).

plan(vnum) is the model: the player's race, dressed in the player's current
look (the costume body while costumes show, else the armor; the costume
weapon while it shows, else the weapon; the hair costume; the sash) with the
hovered costume in its part. None when the item is not a body, weapon, hair
or sash costume, or when the player's job or sex cannot wear it.

The windows call hover(vnum) from their OverInItem and leave() from their
OverOutItem; game.py calls key(True) and key(False) from the action's press
and release. The popup (uicostumepreview.CostumePreview or
nui_costume_preview.CostumePreview, which the Interface makes and hands to
set_popup) shows while the key is held over such an item."""

import item
import player

PREVIEW = "costume"
# The hold action that shows the preview (keybindings.py, NOVA-121).
KEY_ACTION = "show_names"

# The popup's size in screen pixels at 100%, and how far from the pointer it
# stands: beside the item tooltip, which legacy centers on the pointer
# (uitooltip.py ToolTip.OnUpdate: 190 wide) and draws 40 px below it.
POPUP_WIDTH = 180
POPUP_HEIGHT = 240
TOOLTIP_HALF = 105
POPUP_TOP = 40

_ANTIFLAG_BY_JOB = ("ITEM_ANTIFLAG_WARRIOR", "ITEM_ANTIFLAG_ASSASSIN", "ITEM_ANTIFLAG_SURA", "ITEM_ANTIFLAG_SHAMAN")
_MALE_RACES = (0, 2, 5, 7)

_state = {"hovered": 0, "held": False, "shown": False}
_popup = [None]


def _constant(module, name, default):
	value = getattr(module, name, default)
	return value if isinstance(value, int) else default


def wearable(race):
	"""Whether the selected item allows the race's job and sex."""
	job_flag = getattr(item, _ANTIFLAG_BY_JOB[race % 4], 0)
	if job_flag and item.IsAntiFlag(job_flag):
		return False
	sex_flag = getattr(item, "ITEM_ANTIFLAG_MALE" if race in _MALE_RACES else "ITEM_ANTIFLAG_FEMALE", 0)
	return not (sex_flag and item.IsAntiFlag(sex_flag))


def costume_part(vnum):
	"""The part a costume goes on ("armor", "weapon", "hair" or "sash") and
	its value for modelpreview.SetParts, or None."""
	if not vnum:
		return None
	item.SelectItem(vnum)
	if item.GetItemType() != _constant(item, "ITEM_TYPE_COSTUME", -1):
		return None
	sub = item.GetItemSubType()
	if sub == _constant(item, "COSTUME_TYPE_BODY", -1):
		return ("armor", vnum)
	if sub == _constant(item, "COSTUME_TYPE_WEAPON", -1):
		return ("weapon", vnum)
	if sub == _constant(item, "COSTUME_TYPE_HAIR", -1):
		return ("hair", int(item.GetValue(3)))
	if sub in (_constant(item, "COSTUME_TYPE_SASH", -1), _constant(item, "COSTUME_TYPE_SASH2", -1)):
		return ("sash", vnum)
	return None


def _worn(cell_name):
	cell = getattr(item, cell_name, None)
	if not isinstance(cell, int):
		return 0
	return int(player.GetItemIndex(cell))


def current_look():
	"""The player's own look: {"armor", "weapon", "hair", "sash"} as
	modelpreview.SetParts takes them (0 for the race's default)."""
	shows_costumes = bool(getattr(player, "IsShowCostumes", lambda: True)())
	shows_weapon = bool(getattr(player, "IsShowWeapon", lambda: True)())
	armor = _worn("COSTUME_SLOT_BODY") if shows_costumes else 0
	armor = armor or _worn("EQUIPMENT_BODY")
	weapon = _worn("COSTUME_SLOT_WEAPON") if shows_weapon else 0
	weapon = weapon or _worn("EQUIPMENT_WEAPON")
	hair = 0
	hair_costume = _worn("COSTUME_SLOT_HAIR") if shows_costumes else 0
	if hair_costume:
		item.SelectItem(hair_costume)
		hair = int(item.GetValue(3))
	sash = _worn("COSTUME_SLOT_SASH2") or _worn("COSTUME_SLOT_SASH")
	return {"armor": armor, "weapon": weapon, "hair": hair, "sash": sash}


def plan(vnum):
	"""(race, armor, weapon, hair, sash) of the player wearing the costume
	`vnum`, or None (see the module's docstring)."""
	part = costume_part(vnum)
	if part is None:
		return None
	race = int(player.GetRace())
	item.SelectItem(vnum)
	if not wearable(race):
		return None
	look = current_look()
	look[part[0]] = part[1]
	return (race, look["armor"], look["weapon"], look["hair"], look["sash"])


def popup_origin(mouse_x, mouse_y, screen_width, width=POPUP_WIDTH):
	"""The popup's top left in screen pixels: left of the item tooltip, which
	is centered on the pointer, at the tooltip's top; right of it where the
	left has no room."""
	x = mouse_x - TOOLTIP_HALF - width
	if x < 0:
		x = mouse_x + TOOLTIP_HALF
	x = max(0, min(x, screen_width - width))
	return (int(x), int(mouse_y + POPUP_TOP))


def set_popup(popup):
	"""The Interface's popup, or None at its Close."""
	_popup[0] = popup
	_state.update({"hovered": 0, "held": False, "shown": False})


def hover(vnum):
	"""A window's OverInItem: the item under the pointer."""
	_state["hovered"] = int(vnum or 0)
	_refresh()


def leave():
	"""A window's OverOutItem."""
	_state["hovered"] = 0
	_refresh()


def key(held):
	"""The preview key's press (True) and release (False)."""
	_state["held"] = bool(held)
	_refresh()


def hovered_plan():
	"""The plan of the hovered item, whatever the key: the tooltip's hint."""
	return plan(_state["hovered"]) if _state["hovered"] else None


def hovered_vnum():
	return _state["hovered"]


def is_shown():
	return _state["shown"]


def _refresh():
	popup = _popup[0]
	look = plan(_state["hovered"]) if _state["held"] and _state["hovered"] else None
	if look is None:
		if _state["shown"] and popup is not None:
			popup.HidePreview()
		_state["shown"] = False
		return
	if popup is None:
		return
	_state["shown"] = bool(popup.ShowPreview(_state["hovered"], look))
