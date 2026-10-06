"""NovaUI gift icon (nui/windows/gift-box/gift-box.rml).

The NovaUI taskbar (nui_taskbar.TaskBar.LoadWindow) makes GiftBox below
through nui_windows.make("gift-box", ...) while the "gift-box" flag is on;
the legacy taskbar keeps its own legacy gift box (spec D17). GiftBox is the
facade of uiTaskBar.GiftBox: the taskbar's ShowGift and HideGift reach its
Show and Hide. Its document has no model and no events."""

import nui
import nui_hud

DOCUMENT = "nui/windows/gift-box/gift-box.rml"


class GiftBoxBoard(nui.Window):
	DOCUMENT = DOCUMENT


class GiftBox(object):
	"""uiTaskBar.GiftBox on NovaUI (the taskbar's wndGiftBox)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over("gift-box", self)
		self._nui_discarded = False
		self.board = None
		if not nui_hud.has_engine():
			return
		try:
			self.board = GiftBoxBoard()
		except Exception:
			self.nui_discard()
			raise

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("gift-box", self)

	def LoadWindow(self):
		"""The document loaded with the facade; nothing is left to do."""
		pass

	def Show(self):
		if self.board is not None:
			self.board.show()

	def Hide(self):
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	def Destroy(self):
		self.nui_discard()
