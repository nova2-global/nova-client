"""NovaUI offline shop decoration (nui/windows/shop-deco/shop-deco.rml; Wave 5,
NOVA-9).

While the shop-deco flag is on, Interface.__MakeWindows makes
MyShopDecorationWindow below through nui_windows.make() instead of
uiMyShopDecoration.MyShopDecorationWindow: a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the widgets were (the
title bar and its text, the description, the list and its scroll bar, the
preview and its name, the four buttons) and whose preview maker (__MakePreview)
makes a proxy that names the sign style it shows. So the two steps (the
shop's model, then its sign's style, both from CONFIG and shop_deco.txt), the
choice that only Complete commits (uiPrivateShopBuilder.SHOP_DECO and
SHOP_STYLE, with CONFIG's decoration item in the inventory) and Cancel, X and
Escape keeping what was committed are legacy's code.

The name dialog's decoration button opens it (Interface.OpenMyShopDecoWnd)
while that dialog, a kit modal, is shown: the window covers the kit
(nui_dialog_kit.cover, when the kit is loaded), so the modal steps aside until the window hides, as
for a legacy dialog opened above NovaUI. On the model step the preview shows
the model turning over its name (NOVA-137: the document's nui-view
"model-shop-deco", the client's "shop_deco" model preview, which legacy's
player.SelectShopModel and MyShopDecoShow drive; a client without it shows the
stall mark instead), or the style's sign. No Python runs per frame."""

import sys

import ui
import uiMyShopDecoration

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/shop-deco/shop-deco.rml"
KEY = "shop-deco"
# shop_deco.txt's styles the sheets draw (1 to OFFLINE_SHOP_SIGN_STYLE_MAX - 1);
# a style past them shows as 0, the plain board (legacy's L15).
STYLE_CLASSES = 5


def style_class(style):
	"""The sheets' style number of a sign style: 1 to STYLE_CLASSES, else 0."""
	try:
		style = int(style)
	except (TypeError, ValueError):
		return 0
	return style if 1 <= style <= STYLE_CLASSES else 0


class _DecoBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The decoration's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "shop_deco"

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

	@nui.on("entry_press")
	def on_entry_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.itemList.press(int(index))

	@nui.on("button_press")
	def on_button_press(self, name, button):
		self.raise_for(button)
		if button != 0:
			return
		widget = {"next": "nextButton", "cancel": "cancelButton", "prev": "prevButton",
		          "complete": "completeButton"}.get(name)
		if widget:
			getattr(self._owner, widget).click()


class _ListProxy(nui_proxies._Shown):
	"""ui.ListBox (uiscript "listbox", 160 x 230): its entries and selected
	line for the board, SelectItem's rule (a new line runs the event) and the
	view count legacy sizes its scroll bar by; the board's list scrolls by
	itself, so SetBasePos records only."""

	STEP = 17      # ui.ListBox.stepSize
	HEIGHT = 230   # myshopdecorationwindow.py's LIST_HEIGHT

	def __init__(self, on_change):
		self.items = []
		self.selectedLine = -1
		self.basePos = 0
		self.event = None
		self.on_change = on_change

	def _changed(self):
		if self.on_change:
			self.on_change()

	def SetEvent(self, event):
		self.event = event

	def ClearItem(self):
		self.items = []
		self.selectedLine = -1
		self.basePos = 0
		self._changed()

	def InsertItem(self, key, name):
		self.items.append((key, "" if name is None else str(name)))
		self._changed()

	def GetViewItemCount(self):
		return self.HEIGHT // self.STEP

	def GetItemCount(self):
		return len(self.items)

	def SetBasePos(self, pos):
		self.basePos = int(pos)

	def SelectItem(self, line):
		"""ui.ListBox.SelectItem: a line that exists and is not the selected
		one becomes it, then the event runs with its key and text."""
		if not 0 <= line < len(self.items) or line == self.selectedLine:
			return
		self.selectedLine = line
		self._changed()
		if self.event:
			key, name = self.items[line]
			self.event(key, name)

	def GetSelectedItem(self):
		if 0 <= self.selectedLine < len(self.items):
			return self.items[self.selectedLine][0]
		return 0

	def press(self, index):
		"""A left press on a row (ListBox.OnMouseLeftButtonUp's SelectItem)."""
		self.SelectItem(index)


class _PreviewProxy(nui_proxies._Shown):
	"""The preview's sign (ui.ShopDecoTitle or ui.ThinBoard2): the style it
	shows, for the board."""

	def __init__(self, owner, style):
		self.owner = owner
		self.style = style
		self.shown = False

	def AddFlag(self, flag):
		pass

	def SetSize(self, width, height):
		pass

	def Show(self):
		self.shown = True
		self.owner._publish_preview(self)

	def Hide(self):
		self.shown = False
		self.owner._publish_preview(self)


class _ModelViewProxy(nui_proxies._Shown):
	"""The preview's render target (ui.RenderTarget): the document's view of the
	"shop_deco" model preview, shown while legacy shows it."""

	def __init__(self, owner):
		self.owner = owner
		self.shown = False

	def Show(self):
		self.shown = True
		self.owner.nui_set(model_view=True)

	def Hide(self):
		self.shown = False
		self.owner.nui_set(model_view=False)


class MyShopDecorationWindow(nui_facade.Facade, uiMyShopDecoration.MyShopDecorationWindow):
	"""uiMyShopDecoration.MyShopDecorationWindow on NovaUI (Interface.wndMyShopDeco)."""

	KEY = KEY
	BOARD = _DecoBoard
	PLACE = "center"
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiMyShopDecoration.MyShopDecorationWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"step": 1,
			"title": "",
			"description": "",
			"entries": [],
			"selected": -1,
			"preview_name": "",
			# The sign the preview shows on the style step: the sheets' style (0 to
			# STYLE_CLASSES), -1 for none (the model step).
			"preview_style": -1,
			# The model step shows the client's model preview (NOVA-137).
			"model_view": False,
			"next": True,
			"cancel": True,
			"prev": False,
			"complete": False,
		}

	# --- the loader (uimyshopdecoration.py __LoadWindow, on proxies) -------------------

	def _MyShopDecorationWindow__LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		# The uiscript's style (myshopdecorationwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.titleBar = nui_proxies.BoardProxy(365, 21)
		self.titleName = nui_proxies.TextProxy(lambda text: self.nui_set(title=nui.plain_text(text)))
		self.descriptionText = nui_proxies.TextProxy(lambda text: self.nui_set(description=nui.plain_text(text)))
		self.itemList = _ListProxy(self._publish_list)
		self.scrollBar = nui_proxies.ScrollBarProxy()
		self.previewWindow = nui_proxies.WindowProxy()
		self.modelName = nui_proxies.TextProxy(lambda text: self.nui_set(preview_name=nui.plain_text(text)))
		self.nextButton = self._button("next")
		self.cancelButton = self._button("cancel")
		self.prevButton = self._button("prev")
		self.completeButton = self._button("complete")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.itemList.SetEvent(ui.__mem_func__(self.OnSelectEntry))
		self.scrollBar.SetScrollEvent(ui.__mem_func__(self.OnScroll))
		self.nextButton.SetEvent(ui.__mem_func__(self.UseNextButton))
		self.cancelButton.SetEvent(ui.__mem_func__(self.Close))
		self.prevButton.SetEvent(ui.__mem_func__(self.UsePrevButton))
		self.completeButton.SetEvent(ui.__mem_func__(self.UseCompleteButton))

	def _button(self, key):
		"""A footer button; its shown state is the model key `key`."""
		return nui_proxies.ButtonProxy(lambda button, key=key: self.nui_set(**{key: button.IsShow()}))

	def _MyShopDecorationWindow__MakePreview(self, style):
		return _PreviewProxy(self, style)

	def _MyShopDecorationWindow__MakeModelView(self):
		if not uiMyShopDecoration.model_preview_available():
			return None
		return _ModelViewProxy(self)

	# --- what NovaUI changes -----------------------------------------------------------

	def Open(self):
		"""Legacy's; then the window covers the dialog kit when the kit is in
		use (as nui_windows.legacy_dialog_layer does): the kit's modal name
		dialog steps aside until the window hides."""
		uiMyShopDecoration.MyShopDecorationWindow.Open(self)
		kit = sys.modules.get("nui_dialog_kit")
		if kit is not None:
			kit.cover(self)

	# --- the board's model -------------------------------------------------------------

	def _publish_list(self):
		if self.__dict__.get("_state") is None:
			return
		items = self.itemList.items
		self.nui_set(entries=[{"key": str(key), "name": nui.plain_text(name)} for key, name in items],
		             selected=self.itemList.selectedLine, step=int(self.step))

	def _publish_preview(self, preview):
		"""A preview shown or hidden (legacy keeps it in self.preview after
		its Show, and hides the last one before it makes the next)."""
		if self.__dict__.get("_state") is None:
			return
		self.nui_set(preview_style=style_class(preview.style) if preview.shown else -1)
