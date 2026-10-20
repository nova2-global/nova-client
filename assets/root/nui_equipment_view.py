"""NovaUI equipment view: another player's equipment
(nui/windows/equipment-view/equipment-view.rml; P16 spec 5.6).

While the equipment-view flag is on, Interface.OpenEquipmentDialog makes
EquipmentDialog below through nui_windows.make() instead of
uiEquipmentDialog.EquipmentDialog, one per viewed player, as legacy: a
subclass of the legacy class (nui_facade.Facade) whose uiscript loader puts
proxies where the widgets were: the board (its title the player's name, its
close) and the slot window of the view's slots. Its slots come from the
limits module's view table (nui_limits.view_equip_table: today's 11 view
indices, the wear positions 0 to 10; OLD's 16 at the foundation, with the
rings and the belt, and two costume entries that do not show), each placed
by its wear name in every skin (D22). The items, their sockets and
attributes, the tooltips (AddItemData on hover), the close and its event are
legacy's code.

The board is instanced (nui.Window.INSTANCED, spec 4.4): each open dialog
binds its own model, equipment_view_<n>, so two views of two players can
show at once. A second view of the same player replaces the first, as
legacy's: the Interface drops the earlier dialog (equipmentDialogDict), whose
legacy window leaves the screen when it is collected; its board goes at the
new Open (nui_hud.take_over under the player's vid). The board draws below
the legacy UI layer, as legacy's window lived in it.

The Interface makes a new dialog for each view and drops it at its close,
so a dialog cannot keep its board; the boards are pooled instead (P18:
WAVE4.md measured 17.2 to 18.9 ms of UI work at its first open, a 60 fps
frame or more): a closed view's board waits, hidden, in POOL, its places
and cells gone (equip_on) and no dialog behind it (nui_hud.Pooled), and the
next view takes it with no load. At most POOL_BOUND wait."""

import ui
import uiEquipmentDialog

import nui
import nui_facade
import nui_hud
import nui_limits
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/equipment-view/equipment-view.rml"
# P18: the boards that wait for the next view. Two: a player who compares
# two players' equipment opens both views with no load again, while a
# waiting board, emptied, keeps 11 elements (17 in cyberpunk).
POOL_BOUND = 2
POOL = nui_hud.BoardPool("equipment-view", POOL_BOUND)


class _EquipmentViewBoard(nui_hud.Pooled, nui_hud.RaisesOnPress, nui.Window):
	"""An equipment view's document; its events go to its dialog (none while
	it waits in POOL). A press on it raises the dialog, as legacy's window
	manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "equipment_view"
	INSTANCED = True

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._cell_events.out(int(index))

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()


class _TitledBoard(nui_proxies.BoardProxy):
	"""ui.BoardWithTitleBar's SetTitleName, handed to the window."""

	def __init__(self, width, height, on_title):
		nui_proxies.BoardProxy.__init__(self, width, height)
		self._on_title = on_title

	def SetTitleName(self, name):
		nui_proxies.BoardProxy.SetTitleName(self, name)
		self._on_title(self.title)


class EquipmentDialog(nui_facade.Facade, uiEquipmentDialog.EquipmentDialog):
	"""uiEquipmentDialog.EquipmentDialog on NovaUI (Interface.equipmentDialogDict)."""

	# None: the Interface keeps one per viewed player, and none takes over another.
	KEY = None
	BOARD = _EquipmentViewBoard
	PLACE = "center"

	def __init__(self):
		self._view_key = None
		self.nui_begin()
		try:
			uiEquipmentDialog.EquipmentDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		limits = self._limits
		table = nui_limits.view_equip_table(limits)
		return {
			"title": "",
			"table": nui_limits.view_equip_id(limits),
			"places": [{"index": slot.index, "name": slot.name, "shown": slot.group == "shown"} for slot in table],
			"cells": [nui_slots.empty_cell(i) for i in range(len(table))],
			# P18: the places and cells, a list of one entry while the board
			# shows, none while it waits in POOL.
			"equip_on": [1],
		}

	def nui_demand(self):
		"""P18: the board comes from POOL and goes back to it."""
		return nui_hud.PooledBoard(POOL, self._make_board, self._restore_board, self._keep_board,
		                           self._empty_board, self._adopt_board)

	def _adopt_board(self, board):
		board.adopt(self)

	def _empty_board(self, board):
		"""Nothing of this player stays on a board that waits."""
		board.set(equip_on=[], title="")

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_cells(self, cells):
		self.nui_set(cells=cells)

	def _on_title(self, title):
		self.nui_set(title=nui.plain_text(title))

	# --- the loader (uiequipmentdialog.py:21-36, on proxies) ---------------------------------

	def _EquipmentDialog__LoadDialog(self):
		# The uiscript's style (equipmentdialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		table = nui_limits.view_equip_table(self._limits)
		self.board = _TitledBoard(180, 230, self._on_title)
		self.slotWindow = nui_slots.SlotWindowProxy([slot.index for slot in table], self._on_cells)

		self.board.SetCloseEvent(ui.__mem_func__(self.Close))
		self.slotWindow.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.slotWindow.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(self.slotWindow))

	# --- what NovaUI changes (P16 spec 5.6.3) -----------------------------------------

	def SetEquipmentDialogItem(self, slotIndex, vnum, count):
		"""Legacy's, then the proxy's refresh: legacy's slot window draws
		itself, the proxy builds its cells at RefreshSlot."""
		uiEquipmentDialog.EquipmentDialog.SetEquipmentDialogItem(self, slotIndex, vnum, count)
		self.slotWindow.RefreshSlot()

	# --- one view per player (the Interface's dict) -----------------------------------------

	def Open(self, vid):
		"""Legacy's, after the earlier view of this player lost its board:
		Interface.OpenEquipmentDialog replaces its dict entry without Destroy,
		and that dialog's close would delete this one's entry."""
		self._forget_view()
		self._view_key = "equipment-view:%s" % (vid,)
		nui_hud.take_over(self._view_key, self)
		uiEquipmentDialog.EquipmentDialog.Open(self, vid)

	def Close(self):
		uiEquipmentDialog.EquipmentDialog.Close(self)
		self._forget_view()

	def nui_discard(self):
		self._forget_view()
		nui_facade.Facade.nui_discard(self)

	def _forget_view(self):
		key, self._view_key = getattr(self, "_view_key", None), None
		if key is not None:
			nui_hud.forget(key, self)
