"""NovaUI dungeon drops panel (nui/windows/dungeon-drops/dungeon-drops.rml;
NOVA-25).

While the dungeon-drops flag is on, the dungeon manager (uitimerwindow
TimerWindow.LoadWindow, legacy's code in both looks) makes MobDropPopup below
through nui_windows.make() instead of uiTimerWindow.MobDropPopup: a subclass of
the legacy class (nui_facade.Facade) whose loader puts proxies where the
widgets were (the title, the info line, the two lists and the header row) and
whose row maker gives a proxy per mob or item, so which mobs and items show,
in the server's order (uiTimerWindow.DUNGEON_DROP, filled by
game.BINARY_UpdateDungeonDrop), each item's "<count>x <name>" line and its
chance's band, and the header's way back are legacy's code. A mob row's
press lists its items, the header's press goes back. The rows show the item
icons; legacy's item rows have no tooltip, nor do these. No Python runs per
frame."""

import item
import ui
import uiTimerWindow

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/dungeon-drops/dungeon-drops.rml"
KEY = "dungeon-drops"
MOB_TYPES = {0: "mob", 1: "boss", 2: "stone"}
BANDS = {1: "rare", 2: "common", 3: "guaranteed"}


class _DropsBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The panel's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "dungeon_drops"

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
			self._owner.titleBar.close()

	@nui.on("mob_press")
	def on_mob_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_mob(int(index))

	@nui.on("back_press")
	def on_back_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.header.press()


class _RowProxy(nui_proxies._Shown):
	"""uiTimerWindow.MobDropPopup.Row: a mob (its name; a press is its
	button's event) or an item (legacy's line and band), for the board."""

	def __init__(self, owner, vnum, count=0, chance=0, mtype=0, isHeader=False, isItem=False):
		self.owner = owner
		self.vnum = int(vnum)
		self.mtype = uiTimerWindow.mob_type(mtype)
		self.isHeader = isHeader
		self.isItem = isItem
		self.position = (0, 0)
		self.text = ""
		self.icon = ""
		self.band = 0
		if isItem:
			self.band = uiTimerWindow.rarity_of(chance)
			self.text = uiTimerWindow.item_line(self.vnum, count)
			self.icon = nui_slots.icon_source(item.GetIconImageFileName())

	def SetParent(self, parent):
		pass

	def SetPosition(self, x, y):
		self.position = (int(x), int(y))

	def Update(self, vnum, mtype):
		self.vnum = int(vnum)
		self.mtype = uiTimerWindow.mob_type(mtype)

	def press(self):
		"""The row's button: a mob lists its items, the header goes back (legacy's events)."""
		owner = self.owner
		if owner is None:
			return
		if self.isHeader:
			owner.RefreshMobList()
		else:
			owner.RefreshItemList(self.vnum)

	def Destroy(self):
		self.owner = None


class _ScrollProxy(nui_proxies._Shown):
	"""ui.ScrollWindow: the document scrolls by itself; shown says which list shows."""

	def __init__(self, on_show):
		self.on_show = on_show

	def SetContentWindow(self, window):
		pass

	def FitWidth(self, width):
		pass

	def OnContentWindowSizeChange(self):
		pass

	def ScrollToStart(self):
		pass

	def OnRunMouseWheel(self, length):
		return False


class MobDropPopup(nui_facade.Facade, uiTimerWindow.MobDropPopup):
	"""uiTimerWindow.MobDropPopup on NovaUI (TimerWindow.wndDrops)."""

	KEY = KEY
	BOARD = _DropsBoard
	PLACE = "center"
	OnUpdate = None

	def __init__(self, interface):
		self.nui_begin()
		try:
			uiTimerWindow.MobDropPopup.__init__(self, interface)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"info": "", "showing": "mobs", "mobs": [], "items": [], "header": {"name": "", "type": "mob"}}

	# --- legacy's board sizing and title: the board's ----------------------------------

	def SetSize(self, width, height):
		"""Nothing: the legacy window stays 0 x 0 under the board."""

	def AddFlag(self, flag):
		pass

	def SetTitleName(self, name):
		pass

	def SetCloseEvent(self, event):
		self.titleBar.SetCloseEvent(event)

	# --- the loader (uitimerwindow.py MobDropPopup.__LoadWindow, on proxies) ----------

	def _MobDropPopup__LoadWindow(self):
		self.titleBar = nui_proxies.BoardProxy()
		self.SetCloseEvent(ui.__mem_func__(self.Hide))
		self.infoLabel = nui_proxies.TextProxy(lambda text: self.nui_set(info=nui.plain_text(text)))
		self.mobList = nui_proxies.WindowProxy()
		self.itemList = nui_proxies.WindowProxy()
		self.mobScrollableWindow = _ScrollProxy(lambda shown: self._publish())
		self.itemScrollableWindow = _ScrollProxy(lambda shown: self._publish())
		self.itemScrollableWindow.shown = False
		self.header = _RowProxy(self, 0, isHeader=True)
		self.header.on_show = lambda shown: self._publish()
		self.header.shown = False

	def _MobDropPopup__MakeRow(self, parent, vnum, count=0, chance=0, mtype=0, isItem=False):
		return _RowProxy(self, vnum, count, chance, mtype, isItem=isItem)

	# --- what NovaUI changes -----------------------------------------------------------

	def press_mob(self, index):
		if 0 <= index < len(self.mobRows):
			self.mobRows[index].press()

	def RefreshMobList(self):
		uiTimerWindow.MobDropPopup.RefreshMobList(self)
		self._publish()

	def RefreshItemList(self, vnum):
		uiTimerWindow.MobDropPopup.RefreshItemList(self, vnum)
		self._publish()

	def Destroy(self):
		self.nui_discard()
		uiTimerWindow.MobDropPopup.Destroy(self)

	# --- the board's model -------------------------------------------------------------

	def _publish(self):
		if self.__dict__.get("_state") is None or "mobRows" not in self.__dict__:
			return
		import nonplayer
		mob = lambda row: {"name": nui.plain_text(nonplayer.GetMonsterName(row.vnum)), "type": MOB_TYPES[row.mtype]}
		showing = "items" if self.itemScrollableWindow.IsShow() else "mobs"
		self.nui_set(showing=showing, mobs=[mob(row) for row in self.mobRows],
		             items=[{"text": nui.plain_text(row.text), "icon": row.icon, "band": BANDS[row.band],
		                     "type": MOB_TYPES[row.mtype]} for row in self.itemRows],
		             header=mob(self.header))
