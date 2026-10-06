"""Controller for the NovaUI gallery (nui/windows/gallery/gallery.rml), the
developer page that shows every component in every state it styles.

The model holds the same data as gallery.fixture.json, so the client shows
what the snapshots in docs/ui/snapshots/ show. The page has no data-event
handlers; its two title bar buttons are bound by id with element_on().

Open it from a debug command:
	import nui_gallery
	nui_gallery.open_gallery()
"""
import nui

# Same data as gallery.fixture.json, so the client shows what snapshots show.
_ROWS = [
	{"id": 1, "name": "Warrior", "meta": "Lv. 42", "disabled": False, "hover": False, "focus": False},
	{"id": 2, "name": "Ninja", "meta": "Lv. 37", "disabled": False, "hover": False, "focus": True},
	{"id": 3, "name": "Sura", "meta": "Lv. 51", "disabled": False, "hover": True, "focus": False},
	{"id": 4, "name": "Shaman", "meta": "Lv. 12", "disabled": True, "hover": False, "focus": False},
	{"id": 5, "name": "Lycan", "meta": "Lv. 29", "disabled": False, "hover": False, "focus": False},
]

_SKILLS = "d:/ymir work/ui/skill/warrior/"

# The slot grid v2 cells (nui_slots' model): an item with a count, a skill
# with its cover and level, a cooldown at 60% at the snapshot's --time 1, an
# active effect, a disabled, a locked, a picked, a selected, a hovered and an
# empty cell.
_SLOTS = [
	{"kind": "item", "type": 1, "ref": 0, "icon": "/icon/item/27001.tga", "count": "200"},
	{"kind": "skill", "type": 2, "ref": 1, "icon": _SKILLS + "samyeon_02.sub", "count": "m1", "cover": True},
	{"kind": "skill", "type": 2, "ref": 2, "icon": _SKILLS + "palbang_01.sub", "count": "10", "cover": True,
	 "cd_start": -1.0, "cd_end": 4.0},
	{"kind": "skill", "type": 2, "ref": 3, "icon": _SKILLS + "jeongwi_02.sub", "count": "20", "cover": True, "active": True},
	{"kind": "item", "type": 1, "ref": 4, "icon": "/icon/item/27002.tga", "count": "35", "disabled": True},
	{"kind": "item", "type": 1, "ref": 5, "icon": "/icon/item/27003.tga", "locked": True},
	{"kind": "item", "type": 1, "ref": 6, "icon": "/icon/item/27004.tga", "count": "5"},
	{"kind": "item", "type": 1, "ref": 7, "icon": "/icon/item/27100.tga"},
	{"kind": "item", "type": 1, "ref": 8, "icon": "/icon/item/30000.tga"},
	{},
]
_SLOT_PICKED, _SLOT_SELECTED, _SLOT_HOVER = 6, 7, 8

# A 5 x 3 layered grid: a 1x2 sword at cell 0, a locked 1x2 bow at cell 1, a
# 2x3 armor at cell 2, an active auto potion at cell 10, and the footprint of
# a 1x2 item held over cell 4.
_BAG_COLUMNS, _BAG_ROWS = 5, 3
_BAG_ITEMS = [(0, {"icon": "/icon/item/00010.tga", "w": 1, "h": 2}),
              (1, {"icon": "/icon/item/02000.tga", "w": 1, "h": 2, "locked": True}),
              (2, {"icon": "/icon/item/03000.tga", "w": 2, "h": 3, "count": "2"}),
              (10, {"icon": "/icon/item/72723.tga", "active": True})]
_BAG_TARGET = (4, 9)


def _empty_slot(index):
	"""nui_slots.empty_slot, without importing the game modules it needs."""
	return {"index": index, "kind": "", "type": 0, "ref": 0, "icon": "", "count": "", "w": 1, "h": 1,
		"cd_start": 0.0, "cd_end": 0.0, "active": False, "cover": False, "disabled": False, "locked": False}


def _slots():
	slots = []
	for index, values in enumerate(_SLOTS):
		slot = _empty_slot(index)
		slot.update(values)
		slots.append(slot)
	return slots


def _bag_cells():
	return [{"index": index, "target": index in _BAG_TARGET} for index in range(_BAG_COLUMNS * _BAG_ROWS)]


def _bag_items():
	"""nui_slots.item_layer's entries for _BAG_ITEMS."""
	items = []
	for cell, values in _BAG_ITEMS:
		item = _empty_slot(cell)
		item.update(values, kind="item", type=1, ref=cell)
		item["c"], item["r"] = cell % _BAG_COLUMNS, cell // _BAG_COLUMNS
		items.append(item)
	return items


class GalleryWindow(nui.Window):
	DOCUMENT = "nui/windows/gallery/gallery.rml"
	MODEL = "gallery"

	def __init__(self):
		nui.Window.__init__(self)
		self.element_on("gallery-theme", "click", self._on_theme)
		self.element_on("gallery-close", "click", self._on_close)

	def initial_model(self):
		return {
			"gold": 1234567,
			"hint": "Username",
			"show_hint": True,
			"selected": 2,
			"rows": _ROWS,
			"slots": _slots(),
			"slot_picked": _SLOT_PICKED,
			"slot_selected": _SLOT_SELECTED,
			"slot_hover": _SLOT_HOVER,
			"bag_cells": _bag_cells(),
			"bag_items": _bag_items(),
		}

	def _on_theme(self, event):
		# The next player theme after the one in use, wrapping around.
		themes = [theme_id for theme_id, _ in nui.get_themes()]
		if not themes:
			return
		current = nui.get_theme()
		following = themes.index(current) + 1 if current in themes else 0
		nui.set_theme(themes[following % len(themes)])

	def _on_close(self, event):
		self.hide()


_window = None


def open_gallery():
	global _window
	if not nui.is_available():
		return None
	if _window is None:
		_window = GalleryWindow()
	_window.show()
	return _window
