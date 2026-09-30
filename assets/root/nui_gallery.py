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

_ICONS = [
	("icon/item/27001.tga", 200), ("icon/item/27002.tga", 35), ("icon/item/27003.tga", 1),
	("icon/item/27004.tga", 5), ("icon/item/27100.tga", 1), ("icon/item/27101.tga", 12),
	("icon/item/30000.tga", 1), ("icon/item/50001.tga", 3), ("icon/item/70001.tga", 1),
	("icon/item/71001.tga", 1), ("", 0), ("", 0),
]


def _slots():
	slots = []
	for index, (icon, count) in enumerate(_ICONS):
		slots.append({"icon": icon, "count": count, "locked": index == 4, "selected": index == 2, "hover": index == 1})
	return slots


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
		}

	def _on_theme(self, event):
		nui.set_theme("light" if nui.get_theme() == "dark" else "dark")

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
