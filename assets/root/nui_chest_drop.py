"""NovaUI chest-drop preview (nui/windows/chest-drop/chest-drop.rml; Wave 7,
NOVA-18).

While the chest-drop flag is on, Interface.__MakeWindows makes ChestDropWindow
below through nui_windows.make() instead of uiChestDrop.ChestDropWindow: a
subclass of the legacy class (nui_facade.Facade) whose loader puts proxies
where the widgets were: the board and its title, the info lines, the chest's
icon and name, and the row list (RowListProxy: Clear, AppendRow, Done). So
the request (uiChestDrop.request, once a chest a session), the rows kept in
constInfo.CHESTS_PREVIEW, OLD's tier rule (uiChestDrop.rows_with_tiers), the
"<count>x <name>" text and the info text are legacy's code; the board shows
what the proxies were told. The tier names are the document's own strings
(@game.CHEST_DROP_TIER_*), picked by the row's tier.

Nothing runs per frame (legacy's window had no OnUpdate); the list scrolls
in RmlUi. The board exists only while the window shows.
"""

import ui
import uiChestDrop

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/chest-drop/chest-drop.rml"
KEY = "chest-drop"


class _ChestDropBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The preview's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "chest_drop"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()


class _TitleBoardProxy(nui_proxies.BoardProxy):
	"""ui.BoardWithTitleBar: SetTitleName hands the title to the window."""

	def __init__(self, width, height, on_title):
		nui_proxies.BoardProxy.__init__(self, width, height)
		self._on_title = on_title

	def SetTitleName(self, name):
		nui_proxies.BoardProxy.SetTitleName(self, name)
		self._on_title(self.title)


class RowListProxy(object):
	"""uiChestDrop.RowList on NovaUI: the rows as model entries, handed to the
	window at Done (legacy's list size and scroll reset)."""

	def __init__(self, on_rows):
		self._on_rows = on_rows
		self.rows = []

	def Clear(self):
		self.rows = []

	def AppendRow(self, vnum, count, tier):
		self.rows.append({
			"icon": nui_slots.icon_source(uiChestDrop.icon_of(vnum)),
			"name": nui.plain_text(uiChestDrop.row_name(vnum, count)),
			"tier": int(tier),
		})

	def Done(self):
		self._on_rows(list(self.rows))

	def OnRunMouseWheel(self, length):
		pass

	def Destroy(self):
		self.rows = []


class ChestDropWindow(nui_facade.Facade, uiChestDrop.ChestDropWindow):
	"""uiChestDrop.ChestDropWindow on NovaUI (Interface.wndChestDrop)."""

	KEY = KEY
	BOARD = _ChestDropBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiChestDrop.ChestDropWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"title": "",
			"info": "",
			"opens": "",
			"chest_icon": "",
			"chest_name": "",
			"rows": [],
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_title(self, title):
		self.nui_set(title=nui.plain_text(title))

	def _on_rows(self, rows):
		self.nui_set(rows=rows)

	def _on_icon(self, path):
		self.nui_set(chest_icon=nui_slots.icon_source(path))

	# --- the loader (uichestdrop.py __LoadWindow, on proxies) ---------------------------

	def _ChestDropWindow__LoadWindow(self):
		self.AddFlag("movable")
		self.AddFlag("float")
		self.board = _TitleBoardProxy(self.WIDTH, self.HEIGHT, self._on_title)
		self.board.SetTitleName(uiChestDrop.localeInfo.CHEST_DROP_TITLE)
		self.board.SetCloseEvent(ui.__mem_func__(self.Close))
		self.infoLabel = nui_proxies.TextProxy(lambda text: self.nui_set(info=nui.plain_text(text)))
		self.openLabel = nui_proxies.TextProxy(lambda text: self.nui_set(opens=nui.plain_text(text)))
		self.header = nui_proxies.WindowProxy()
		self.chestIcon = nui_proxies.ImageProxy(self._on_icon)
		self.chestName = nui_proxies.TextProxy(lambda text: self.nui_set(chest_name=nui.plain_text(text)))
		self.rowList = RowListProxy(self._on_rows)
