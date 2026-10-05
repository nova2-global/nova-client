"""The pick money dialog of the NovaUI dialog kit (nui/windows/pick-money): a
small window with a digits-only field and the maximum, for
uiPickMoney.PickMoneyDialog (splitting a stack, money out of the inventory,
the safebox and the exchange).

It is not modal, as in legacy: it opens over the inventory, which stays
usable. Open() places it above the mouse (G6), its bottom center 20dp over
the pointer, kept on the screen. Enter in the field accepts (the amount,
capped at the maximum, goes to the accept event when it is above 0) and
closes; Escape in the field, Cancel and the close button close it. See
nui_dialog_kit.py for the shared rules.
"""

import app
import nui
import nui_dialog_kit as kit
import wndMgr

FIELD = "pick-money-field"
DIGITS = "0123456789"


def digits_of(text):
	return "".join(c for c in text if c in DIGITS)


class PickMoneyWindow(kit.KindWindow):
	DOCUMENT = "nui/windows/pick-money/pick-money.rml"
	MODEL = "pick_money"
	MODAL = False
	BOX = ""
	FIELD = FIELD

	def initial_model(self):
		return {"title": "", "max": 6, "limit": " / 0"}

	@nui.on("edit")
	def on_edit(self, value, linebreak):
		self.forward("_nui_edit", value, linebreak)

	@nui.on("accept")
	def on_accept(self):
		self.forward("_nui_accept")

	@nui.on("cancel")
	def on_cancel(self):
		self.forward("_nui_cancel")


class PickMoneyDialog(kit.DialogFacade):
	"""uiPickMoney.PickMoneyDialog (uipickmoney.py:6-104)."""

	KIND = PickMoneyWindow
	LEGACY = "uiPickMoney.LegacyPickMoneyDialog"

	def __init__(self):
		self.unitValue = 1
		self.maxValue = 0
		self.eventAccept = 0
		self._title = None
		self._max = None
		self._value = ""
		kit.DialogFacade.__init__(self)

	def _limit(self):
		return ("/%d" if app.IsRTL() else " / %d") % self.maxValue

	def _fill(self):
		return {
			"title": "@ui.PICK_MONEY_TITLE" if self._title is None else nui.plain_text(self._title),
			"max": 6 if self._max is None else int(self._max),
			"limit": nui.plain_text(self._limit()),
		}

	def _field_text(self):
		return self._value

	def _place(self, window):
		mouse_x, mouse_y = wndMgr.GetMousePosition()
		scale = nui.get_scale() or 1.0
		window.set_position(mouse_x / scale, mouse_y / scale - 20, origin=(0.5, 1.0))

	def _replay(self, legacy):
		legacy.LoadDialog()
		if self._title is not None:
			legacy.SetTitleName(self._title)
		legacy.SetAcceptEvent(self.eventAccept)
		if self._max is not None:
			legacy.SetMax(self._max)

	# --- the legacy surface -----------------------------------------------------------

	def LoadDialog(self):
		pass

	def Destroy(self):
		legacy = self._drop_legacy()
		if legacy is not None:
			legacy.Destroy()
		else:
			self._release()
		self.eventAccept = 0
		self.maxValue = 0

	def SetTitleName(self, text):
		self._title = text
		if self._legacy is not None:
			self._legacy.SetTitleName(text)
		elif self._held():
			self._window.set(title=nui.plain_text(text))

	def SetAcceptEvent(self, event):
		self.eventAccept = event
		if self._legacy is not None:
			self._legacy.SetAcceptEvent(event)

	def SetMax(self, max):
		self._max = int(max)
		if self._legacy is not None:
			self._legacy.SetMax(max)
		elif self._held():
			self._window.set(max=self._max)

	def Open(self, maxValue, unitValue=1):
		if self._routed():
			self._legacy.Open(maxValue, unitValue)
			return
		self.unitValue = unitValue
		self.maxValue = maxValue
		self._value = str(unitValue)
		if not self._show():
			self._open_legacy(maxValue, unitValue)

	def Close(self):
		legacy = self._drop_legacy()
		if legacy is not None:
			legacy.Close()
			return
		self._release()

	def SetPosition(self, x, y):
		if self._legacy is not None:
			self._legacy.SetPosition(x, y)
		elif self._held():
			scale = nui.get_scale() or 1.0
			self._window.set_position(x / scale, y / scale)

	def OnAccept(self):
		if self._legacy is not None:
			self._legacy.OnAccept()
			return
		text = self._text()
		if len(text) > 0 and text.isdigit():
			money = min(int(text), self.maxValue)
			if money > 0 and self.eventAccept:
				self.eventAccept(money)
		self.Close()

	def _text(self):
		if self._held():
			value = self._window.get_value(FIELD)
			if value is not None:
				return value
		return self._value

	# --- window callbacks -------------------------------------------------------------

	def _nui_edit(self, value, linebreak):
		value = "" if value is None else str(value)
		if digits_of(value) != value:
			value = digits_of(value)
			if self._held():
				self._window.set_value(FIELD, value, caret="end")
		self._value = value
		if linebreak:
			self.OnAccept()

	def _nui_accept(self):
		self.OnAccept()

	def _nui_cancel(self):
		self.Close()

	def _nui_escape(self):
		self.Close()
		return True
