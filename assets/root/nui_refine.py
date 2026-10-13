"""NovaUI refine dialogs (nui/windows/refine/refine.rml; P14 spec 6.4).

While the refine flag is on, the Interface makes RefineDialogNew below
(Interface.dlgRefineNew, the dialog the server opens: OpenRefineDialog, then
AppendMaterialToRefineDialog per material) and the inventory makes
RefineDialog (InventoryWindow.refineDialog, which today's flow never opens:
RefineItem returns after its use packet, spec D17), both through
nui_windows.make(). Each is a subclass of its legacy class (spec D25): the
uiscript loader is replaced by proxies standing where the legacy widgets
were (nui_proxies, and nui_tooltip.EmbeddedItemToolTip for the tooltip),
bound to the legacy handlers as the legacy loader bound its widgets, so
Open, the materials, the questions (uiCommon.QuestionDialog2, the dialog
kit's facade while dialogs is on), Accept, the cancel packet and Escape are
legacy's own code. Legacy's ScriptWindow stays underneath, 0 x 0 in the UI
layer (its UpdateDialog's own SetSize is left out), so IsShow, SetTop and
the Escape chain (OnPressEscapeKey: the cancel) are legacy's.

One document serves both variants (variant: "new" or "old"). It exists only
while its dialog shows (nui_hud.OnDemand) and opens where legacy's does,
(W - 400, 70 * 800 / H) in dp (spec D21). Legacy hides its probability line
in both dialogs (probText and successPercentage are one uiscript child,
hidden at load), and the old dialog keeps the uiscript's cost text: the
model carries each line's shown state, as the proxies were told."""

import app
import item
import localeInfo
import ui
import uiRefine
import uiScriptLocale
import wndMgr

import nui
import nui_hud
import nui_limits
import nui_proxies
import nui_slots
import nui_tooltip

DOCUMENT = "nui/windows/refine/refine.rml"
PLACE_X, PLACE_Y_NUMERATOR = 400, 70 * 800   # uiscript/refinedialog.py: x SCREEN_WIDTH - 400, y 70 * 800 / SCREEN_HEIGHT


class _RefineBoard(nui.Window):
	"""The refine document; its events go to its dialog."""

	DOCUMENT = DOCUMENT
	MODEL = "refine"

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


class _Dialog(object):
	"""What both refine dialogs share: the board on demand, the model, the
	proxies' callbacks, Show, Hide, SetTop and the place."""

	NUI_FACADE = True
	VARIANT = None
	KEY = None
	LEGACY = None

	def _nui_init(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._state = {"variant": self.VARIANT, "prob_text": "", "prob_shown": False, "cost_text": "", "cost_shown": False,
		               "item_icon": "", "item_cells": 0, "materials": [], "lines": [],
		               "min_w": nui_tooltip.uiToolTip.ToolTip.TOOL_TIP_WIDTH}
		self._place = None
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_3b():
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_3b()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	def _set(self, **values):
		self._state.update(values)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return _RefineBoard(self, self._state)

	def _restore_board(self, board):
		"""The model, and the place: legacy's at the first open, then where
		the dialog was (legacy's window keeps a place it was dragged to)."""
		board.set(**self._state)
		if self._place is not None:
			board.set_position(self._place[0], self._place[1])
			return
		scale = nui.get_scale() or 1.0
		width, height = wndMgr.GetScreenWidth() / scale, wndMgr.GetScreenHeight() / scale
		board.set_position(width - PLACE_X, PLACE_Y_NUMERATOR / float(max(height, 1.0)))

	def _keep_board(self, board):
		box = board.element_box("")
		if box:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def _text(self, key, shown_key):
		"""A TextProxy that writes `key` and the shown state `shown_key`."""
		proxy = nui_proxies.TextProxy(lambda text: self._set(**{key: nui.plain_text(text)}))
		proxy.on_show = lambda shown: self._set(**{shown_key: bool(shown)})
		return proxy

	def _on_tooltip(self, model):
		self._set(lines=model["lines"], min_w=model["min_w"])

	def _tooltip(self):
		"""The dialog's tooltip, as the legacy loader makes it (uirefine.py:50-54,
		:228-232): an item tooltip that does not follow the pointer, shown."""
		tooltip = nui_tooltip.EmbeddedItemToolTip()
		tooltip.on_model = self._on_tooltip
		tooltip.SetFollow(False)
		tooltip.Show()
		return tooltip

	def _buttons(self, accept, cancel):
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.acceptButton.SetEvent(accept)
		self.cancelButton.SetEvent(cancel)

	# --- what NovaUI changes -----------------------------------------------------------

	def Show(self):
		if self.demand is not None:
			self.demand.show()
		self.LEGACY.Show(self)

	def Hide(self):
		self.LEGACY.Hide(self)
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		self.LEGACY.SetTop(self)

	def Destroy(self):
		self.nui_discard()
		self.LEGACY.Destroy(self)


class RefineDialogNew(_Dialog, uiRefine.RefineDialogNew):
	"""uiRefine.RefineDialogNew on NovaUI (Interface.dlgRefineNew)."""

	VARIANT = "new"
	KEY = "refine-new"
	LEGACY = uiRefine.RefineDialogNew

	def __init__(self):
		self._nui_init()
		uiRefine.RefineDialogNew.__init__(self)
		if self.demand is not None:
			self.loaded = self.demand.probe()

	def _RefineDialogNew__LoadScript(self):
		"""Legacy's loader (uirefine.py:206-251) on proxies."""
		self.board = nui_proxies.BoardProxy()
		self.titleBar = nui_proxies.BoardProxy()
		self.probText = self._text("prob_text", "prob_shown")
		self.probText.SetText(uiScriptLocale.REFINE_INFO)
		self.probText.Show()
		self.costText = self._text("cost_text", "cost_shown")
		self.costText.SetText(uiScriptLocale.REFINE_COST)
		self.costText.Show()
		self.successPercentage = self.probText   # one uiscript child, "SuccessPercentage"
		self._buttons(self.OpenQuestionDialog, self.CancelRefine)

		self.successPercentage.Hide()

		self.toolTip = self._tooltip()

		self.slotList = []
		for i in range(self._limits.REFINE_ITEM_CELLS_MAX):
			slot = nui_proxies.ImageProxy()
			slot.LoadImage("d:/ymir work/ui/public/slot_base.sub")
			slot.on_show = lambda shown: self._set(item_cells=sum(1 for s in self.slotList if s.IsShow()))
			self.slotList.append(slot)

		self.itemImage = nui_proxies.ImageProxy(lambda path: self._set(item_icon=nui_slots.icon_source(path)))

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.CancelRefine))
		self.isLoaded = True

	def Open(self, targetItemPos, nextGradeItemVnum, cost, prob, type):
		self._set(materials=[], item_cells=0)
		uiRefine.RefineDialogNew.Open(self, targetItemPos, nextGradeItemVnum, cost, prob, type)

	def AppendMaterial(self, vnum, count):
		"""Legacy's (uirefine.py:349-387): one row of the materials, its
		icon and legacy's "name x 02" text, and legacy's dialogHeight."""
		item.SelectItem(vnum)
		row = {"icon": nui_slots.icon_source(item.GetIconImageFileName()),
		       "text": nui.plain_text("%s x %02d" % (item.GetItemName(), count))}
		self._set(materials=self._state["materials"] + [row])
		self.dialogHeight += 34
		self.UpdateDialog()

	def UpdateDialog(self):
		"""Legacy's (uirefine.py:389-409) on the proxies, without the legacy
		window's own SetSize and SetPosition: it stays 0 x 0, never picked
		over the UI, and the document lays itself out. NovaUI never runs in a
		right-to-left locale, so legacy's mirrored board is left out."""
		newWidth = self.toolTip.GetWidth() + 60
		newHeight = self.dialogHeight + 79 - 8
		self.board.SetSize(newWidth, newHeight)
		self.toolTip.SetPosition(15 + 35, 38)
		self.titleBar.SetWidth(newWidth - 15)


class RefineDialog(_Dialog, uiRefine.RefineDialog):
	"""uiRefine.RefineDialog on NovaUI (InventoryWindow.refineDialog)."""

	VARIANT = "old"
	KEY = "refine-old"
	LEGACY = uiRefine.RefineDialog

	def __init__(self):
		self._nui_init()
		uiRefine.RefineDialog.__init__(self)
		if self.demand is not None:
			self.loaded = self.demand.probe()

	def _RefineDialog__LoadScript(self):
		"""Legacy's loader (uirefine.py:26-57) on proxies."""
		self._RefineDialog__LoadQuestionDialog()

		self.board = nui_proxies.BoardProxy()
		self.titleBar = nui_proxies.BoardProxy()
		self.successPercentage = self._text("prob_text", "prob_shown")
		self.successPercentage.SetText(uiScriptLocale.REFINE_INFO)
		self.successPercentage.Show()
		cost = self._text("cost_text", "cost_shown")
		cost.SetText(uiScriptLocale.REFINE_COST)
		cost.Show()
		self._cost = cost   # the uiscript's Cost: the old dialog never touches it
		self._buttons(self.OpenQuestionDialog, self.Close)

		self.successPercentage.Hide()

		self.toolTip = self._tooltip()

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

	def _RefineDialog__LoadQuestionDialog(self):
		"""Legacy's question window (uirefine.py:62-80; uiscript
		questiondialog2.py) as the dialog kit's question, with legacy's texts
		and events."""
		self.dlgQuestion = nui_proxies.QuestionWindowProxy()

		GetObject = self.dlgQuestion.GetChild
		GetObject("message1").SetText(localeInfo.REFINE_DESTROY_WARNING)
		GetObject("message2").SetText(localeInfo.REFINE_WARNING2)
		GetObject("accept").SetEvent(ui.__mem_func__(self.Accept))
		GetObject("cancel").SetEvent(ui.__mem_func__(self.dlgQuestion.Hide))

	def UpdateDialog(self):
		"""Legacy's (uirefine.py:150-164) on the proxies, without the legacy
		window's own SetSize and SetPosition."""
		newWidth = self.toolTip.GetWidth() + 30
		newHeight = self.toolTip.GetHeight() + 108
		self.board.SetSize(newWidth, newHeight)
		self.titleBar.SetWidth(newWidth - 15)

	def Destroy(self):
		dialog = getattr(self, "dlgQuestion", None)
		if dialog:
			dialog.Destroy()
		_Dialog.Destroy(self)
