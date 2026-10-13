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

# The slot grid v2 full cells (nui_slots' model, 4 x 3): an item with a
# count, a skill with its cover and level, a cooldown at 60% at the
# snapshot's --time 1, an active effect, a disabled, a locked, a picked, a
# selected, a hovered and an empty cell, a cooldown that ended at 0.9 (its
# finish burst plays at --time 1) and the requirement sign (P14 spec 4.5,
# 4.6). The drop footprint's states show in the lean grid.
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
	{"kind": "skill", "type": 2, "ref": 10, "icon": _SKILLS + "geomgyeong_01.sub", "count": "5", "cover": True,
	 "cd_start": -4.1, "cd_end": 0.9},
	{"kind": "item", "type": 1, "ref": 11, "icon": "/icon/item/27005.tga"},
]
_SLOT_PICKED, _SLOT_SELECTED, _SLOT_HOVER, _SLOT_SIGN = 6, 7, 8, 11
# The single cell beside them: a locked 1x2 bow.
_TALL_ICON = "/icon/item/02000.tga"

# A 5 x 3 lean grid (P14 spec 4.2): anchors with their size, the cells they
# cover, and the states of the drop footprint and the use mode.
_LEAN_COLUMNS, _LEAN_ROWS = 5, 3
_LEAN_ITEMS = [(0, {"icon": "/icon/item/00010.tga", "h": 2}),
               (2, {"icon": "/icon/item/03000.tga", "h": 3}),
               (3, {"icon": "/icon/item/72723.tga", "active": True}),
               (4, {"icon": "/icon/item/27001.tga", "count": "200", "picked": True}),
               (8, {"icon": "/icon/item/27002.tga", "count": "35", "target": "usable"}),
               (11, {"icon": "/icon/item/27003.tga", "target": "unusable"})]
_LEAN_TARGETS = {9: "move", 14: "move", 6: "blocked"}
_LEAN_UNAVAILABLE = (10,)
_LEAN_HOVER = 1


def _empty_slot(index):
	"""nui_slots.empty_slot, without importing the game modules it needs."""
	return {"index": index, "kind": "", "type": 0, "ref": 0, "icon": "", "count": "", "w": 1, "h": 1,
		"cd_start": 0.0, "cd_end": 0.0, "active": False, "cover": False, "disabled": False, "locked": False}


def _empty_cell(index):
	"""nui_slots.empty_cell, without the game modules."""
	cell = _empty_slot(index)
	cell.update({"covered": False, "target": "", "picked": False, "unavailable": False})
	return cell


def _slots():
	slots = []
	for index, values in enumerate(_SLOTS):
		slot = _empty_slot(index)
		slot.update(values)
		slots.append(slot)
	return slots


def _lean_cells():
	"""The lean grid's cells, as nui_slots.item_cells makes them: each item on
	its anchor, the cells it covers marked covered (owner's ref kept)."""
	cells = [_empty_cell(index) for index in range(_LEAN_COLUMNS * _LEAN_ROWS)]
	for anchor, values in _LEAN_ITEMS:
		cells[anchor].update(values, kind="item", type=1, ref=anchor)
	for anchor, values in _LEAN_ITEMS:
		for dy in range(1, values.get("h", 1)):
			covered = anchor + dy * _LEAN_COLUMNS
			cells[covered].update(covered=True, type=1, ref=anchor)
	for index, state in _LEAN_TARGETS.items():
		cells[index]["target"] = state
	for index in _LEAN_UNAVAILABLE:
		cells[index]["unavailable"] = True
	return cells


# A chat line with the legacy tags: a colored run, an item link (the client's
# link colors) and text that stays as written in a nui-text.
_TAGGED = '|cff9fe6c3Test|r: look |cfff1e6c0|Hitem:6b:0:0:0:0|h[Red Potion]|h|r and @ui.OK {{ x }}, as written'


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
			"slot_sign": _SLOT_SIGN,
			"tall_icon": _TALL_ICON,
			"lean": _lean_cells(),
			"lean_hover": _LEAN_HOVER,
			"tagged": _TAGGED,
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
