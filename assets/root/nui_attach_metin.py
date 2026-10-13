"""NovaUI attach metin stone (nui/windows/attach-metin/attach-metin.rml; P14 spec 6.5).

While the attach-metin flag is on, the inventory makes AttachMetinDialog below
(InventoryWindow.attachMetinDialog) through nui_windows.make() instead of
uiAttachMetin.AttachMetinDialog: a subclass of the legacy class whose
uiscript loader puts proxies where the legacy widgets were (the two item
tooltips as nui_tooltip.EmbeddedItemToolTip, the stone's image, the board,
the title bar and the buttons), bound to legacy's Accept and Close. Legacy's
Open (the stone put into the first socket it fits, the old tooltip as wide
as the new one) and Accept (the use packet and the sound) run unchanged.
Legacy's ScriptWindow stays underneath, 0 x 0 (its UpdateDialog's own
SetSize is left out). Legacy has no Escape action here, and NovaUI adds
none. The document exists only while the dialog shows; it opens at legacy's
place, the screen's top left corner (spec D21)."""

import ui
import uiAttachMetin

import nui
import nui_hud
import nui_proxies
import nui_slots
import nui_tooltip

DOCUMENT = "nui/windows/attach-metin/attach-metin.rml"
KEY = "attach-metin"


class _AttachBoard(nui.Window):
	"""The attach dialog's document; its events go to its dialog."""

	DOCUMENT = DOCUMENT
	MODEL = "attach_metin"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("accept_press")
	def on_accept_press(self, button):
		if button == 0:
			self._owner.acceptButton.click()

	@nui.on("cancel_press")
	def on_cancel_press(self, button):
		if button == 0:
			self._owner.cancelButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		if button == 0:
			self._owner.titleBar.close()


class AttachMetinDialog(uiAttachMetin.AttachMetinDialog):
	"""uiAttachMetin.AttachMetinDialog on NovaUI (InventoryWindow.attachMetinDialog)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		width = nui_tooltip.uiToolTip.ToolTip.TOOL_TIP_WIDTH
		self._state = {"metin_icon": "", "old_lines": [], "old_min_w": width, "new_lines": [], "new_min_w": width}
		self._place = None
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_3b():
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)
		uiAttachMetin.AttachMetinDialog.__init__(self)
		if self.demand is not None:
			self.loaded = self.demand.probe()

	# --- make()'s protocol --------------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_3b()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(KEY, self)

	# --- the model and the board ----------------------------------------------------------

	def _set(self, **values):
		self._state.update(values)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return _AttachBoard(self, self._state)

	def _restore_board(self, board):
		"""The model, and the place: legacy's corner at the first open, then
		where the dialog was (legacy keeps a place it was dragged to)."""
		board.set(**self._state)
		board.set_position(*(self._place if self._place is not None else (0, 0)))

	def _keep_board(self, board):
		box = board.element_box("")
		if box:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def _tooltip(self, prefix):
		"""A tooltip of the dialog, as the legacy loader makes it
		(uiattachmetin.py:38-54): an item tooltip that does not follow the
		pointer, shown; its model goes to the keys under `prefix`."""
		tooltip = nui_tooltip.EmbeddedItemToolTip()
		tooltip.on_model = lambda model: self._set(**{prefix + "lines": model["lines"], prefix + "min_w": model["min_w"]})
		tooltip.SetFollow(False)
		tooltip.Show()
		return tooltip

	# --- the loader (uiattachmetin.py:19-56, on proxies) ---------------------------------

	def _AttachMetinDialog__LoadScript(self):
		self.board = nui_proxies.BoardProxy()
		self.titleBar = nui_proxies.BoardProxy()
		self.metinImage = nui_proxies.ImageProxy(lambda path: self._set(metin_icon=nui_slots.icon_source(path)))
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.acceptButton.SetEvent(ui.__mem_func__(self.Accept))
		self.cancelButton.SetEvent(ui.__mem_func__(self.Close))

		self.oldToolTip = self._tooltip("old_")
		self.newToolTip = self._tooltip("new_")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

	# --- what NovaUI changes ------------------------------------------------------------

	def UpdateDialog(self):
		"""Legacy's (uiattachmetin.py:131-148) on the proxies, without the
		legacy window's own SetSize and SetPosition: it stays 0 x 0. NovaUI
		never runs in a right-to-left locale, so legacy's mirrored board is
		left out."""
		newWidth = 15 + self.oldToolTip.GetWidth() + 45 + self.newToolTip.GetWidth() + 15
		newHeight = self.newToolTip.GetHeight() + 98
		self.newToolTip.SetPosition(15 + self.oldToolTip.GetWidth() + 45, 38)
		self.board.SetSize(newWidth, newHeight)
		self.titleBar.SetWidth(newWidth - 15)

	def Show(self):
		if self.demand is not None:
			self.demand.show()
		uiAttachMetin.AttachMetinDialog.Show(self)

	def Hide(self):
		uiAttachMetin.AttachMetinDialog.Hide(self)
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		uiAttachMetin.AttachMetinDialog.SetTop(self)

	def Destroy(self):
		self.nui_discard()
		uiAttachMetin.AttachMetinDialog.Destroy(self)
