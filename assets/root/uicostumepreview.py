"""The costume preview popup of the legacy UI (NOVA-202): a thin board on the
top layer with the player's model wearing the hovered costume (the model
preview "costume", in a ui.RenderTarget) over the costume's name.
costume_preview decides when it shows and what it shows; NovaUI's popup is
nui_costume_preview.CostumePreview, made in its place by nui_windows."""

import ui
import item
import wndMgr

import costume_preview

# The board and the model view in it, in pixels.
NAME_HEIGHT = 20
VIEW_MARGIN = 6


def _modelpreview():
	try:
		import modelpreview
	except ImportError:
		return None
	return modelpreview


def show_model(look):
	"""Selects the player's race and the look in the preview; True when the
	client can make that model."""
	preview = _modelpreview()
	if preview is None:
		return False
	race, armor, weapon, hair, sash = look
	if not preview.Select(costume_preview.PREVIEW, race):
		return False
	if not preview.SetParts(costume_preview.PREVIEW, armor, weapon, hair, sash):
		return False
	preview.Show(costume_preview.PREVIEW, True)
	return True


def hide_model():
	preview = _modelpreview()
	if preview is not None:
		preview.Show(costume_preview.PREVIEW, False)


class CostumePreview(ui.ThinBoard):
	"""ShowPreview(vnum, look) and HidePreview() for costume_preview."""

	view = None
	nameLine = None

	def __init__(self):
		ui.ThinBoard.__init__(self, "TOP_MOST")
		self.AddFlag("not_pick")
		self.SetSize(costume_preview.POPUP_WIDTH, costume_preview.POPUP_HEIGHT)
		self.view = None
		renderTarget = getattr(ui, "RenderTarget", None)
		if renderTarget is not None and renderTarget.IsAvailable():
			view = renderTarget("TOP_MOST")
			view.SetParent(self)
			view.AddFlag("not_pick")
			view.SetPosition(VIEW_MARGIN, VIEW_MARGIN)
			view.SetSize(costume_preview.POPUP_WIDTH - 2 * VIEW_MARGIN,
			             costume_preview.POPUP_HEIGHT - 2 * VIEW_MARGIN - NAME_HEIGHT)
			view.SetRenderTarget(costume_preview.PREVIEW)
			view.Show()
			self.view = view
		nameLine = ui.TextLine()
		nameLine.SetParent(self)
		nameLine.SetPosition(0, costume_preview.POPUP_HEIGHT - NAME_HEIGHT)
		nameLine.SetWindowHorizontalAlignCenter()
		nameLine.SetHorizontalAlignCenter()
		nameLine.Show()
		self.nameLine = nameLine

	def Destroy(self):
		hide_model()
		self.view = None
		self.nameLine = None
		self.Hide()

	def ShowPreview(self, vnum, look):
		if self.view is None or not show_model(look):
			self.HidePreview()
			return False
		item.SelectItem(vnum)
		self.nameLine.SetText(item.GetItemName())
		(mouseX, mouseY) = wndMgr.GetMousePosition()
		(x, y) = costume_preview.popup_origin(mouseX, mouseY, wndMgr.GetScreenWidth())
		self.SetPosition(x, min(y, max(0, wndMgr.GetScreenHeight() - costume_preview.POPUP_HEIGHT)))
		self.Show()
		self.SetTop()
		return True

	def HidePreview(self):
		hide_model()
		self.Hide()
