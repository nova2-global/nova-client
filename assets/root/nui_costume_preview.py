"""NovaUI costume preview popup (nui/windows/costume-preview/costume-preview.rml;
NOVA-202).

The Interface makes CostumePreview below through
nui_windows.make("costume-preview", ...) instead of
uicostumepreview.CostumePreview, and hands it to costume_preview.set_popup.
It has the legacy popup's two calls: ShowPreview(vnum, look) puts the
player's model wearing the costume into the model preview "costume" (the
same engine calls as legacy's, uicostumepreview.show_model), names the
costume and places the board beside the item tooltip (costume_preview.
popup_origin, in screen pixels, turned into dp); HidePreview hides both.

The board is made at the first show and kept, hidden, for the phase; it
takes no pointer and no focus, and nothing runs per frame (the engine turns
the model)."""

import item
import wndMgr

import nui
import nui_hud
import costume_preview
import uiCostumePreview

DOCUMENT = "nui/windows/costume-preview/costume-preview.rml"
KEY = "costume-preview"


def empty_model():
	return {"name": ""}


class CostumePreviewBoard(nui.Window):
	DOCUMENT = DOCUMENT
	MODEL = "costume_preview"

	def initial_model(self):
		return empty_model()


class CostumePreview(object):
	"""uicostumepreview.CostumePreview on NovaUI."""

	NUI_FACADE = True

	def __init__(self):
		self.board = None
		self._nui_discarded = False
		nui_hud.take_over(KEY, self)

	def nui_ready(self):
		return nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget(KEY, self)

	def _board(self):
		if self.board is None and not self._nui_discarded:
			board = CostumePreviewBoard()
			if board._doc:
				self.board = board
			else:
				board.destroy()
		return self.board

	def ShowPreview(self, vnum, look):
		board = self._board()
		if board is None or not uiCostumePreview.show_model(look):
			self.HidePreview()
			return False
		item.SelectItem(vnum)
		board.set(name=nui.plain_text(item.GetItemName()))
		(mouseX, mouseY) = wndMgr.GetMousePosition()
		(x, y) = costume_preview.popup_origin(mouseX, mouseY, wndMgr.GetScreenWidth())
		scale = nui.get_scale() or 1.0
		board.set_position(x / scale, y / scale)
		board.show()
		board.bring_to_front()
		return True

	def HidePreview(self):
		uiCostumePreview.hide_model()
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	def Hide(self):
		self.HidePreview()

	def Destroy(self):
		self.nui_discard()
