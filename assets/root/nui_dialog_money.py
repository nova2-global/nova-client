"""The money dialog of the NovaUI dialog kit (nui/windows/dialog-money): a modal
with a title bar, a digits-only field and the amount spelled out under it,
for uiCommon.MoneyInputDialog (the private shop's price).

Open() clears the field; callers set a value after it (SetValue). The line
under the field is the header and localeInfo.NumberToMoneyString of the
digits, updated on every edit. The field takes at most the client's
player.MONEY_DIGITS digits, as legacy's (13, OLD's, for 64-bit gold since
NOVA-96; legacy kept 9 before). Enter and Escape in the field call the
accept and cancel events, as in the input dialog. See nui_dialog_kit.py for
the shared rules.
"""

import localeInfo
import nui
import nui_dialog_kit as kit
import player

FIELD = "dialog-money-field"
DIGITS = "0123456789"


def max_digits():
	"""The most digits the field takes: the client's player.MONEY_DIGITS,
	as legacy's MoneyInputDialog reads it (its constructor and
	SetMaxLength, uicommon.py)."""
	return player.MONEY_DIGITS


def digits_of(text):
	return "".join(c for c in text if c in DIGITS)


def money_of(text):
	"""The amount the legacy dialog shows for the field's text
	(uicommon.py:460-472): 0 for none, 199999999 when int() fails."""
	money = 0
	if text and text.isdigit():
		try:
			money = int(text)
		except ValueError:
			money = 199999999
	return money


class MoneyWindow(kit.KindWindow):
	DOCUMENT = "nui/windows/dialog-money/dialog-money.rml"
	MODEL = "dialog_money"
	BOX = "dialog-money"
	FIELD = FIELD

	def initial_model(self):
		return {"title": "", "max": max_digits(), "money": "", "check_on": False, "check_text": "", "checked": False}

	@nui.on("edit")
	def on_edit(self, value, linebreak):
		self.forward("_nui_edit", value, linebreak)

	@nui.on("accept")
	def on_accept(self):
		self.forward("_nui_accept")

	@nui.on("cancel")
	def on_cancel(self):
		self.forward("_nui_cancel")

	@nui.on("check")
	def on_check(self, button):
		"""A left press on the check box's row (the document takes no click
		to forward from its label, as the system options' toggles)."""
		if int(button) == 0:
			self.forward("_nui_check")


class MoneyInputDialog(kit.DialogFacade):
	"""uiCommon.MoneyInputDialog (uicommon.py MoneyInputDialog)."""

	KIND = MoneyWindow
	LEGACY = "uiCommon.LegacyMoneyInputDialog"

	def __init__(self):
		self._header = localeInfo.MONEY_INPUT_DIALOG_SELLPRICE
		self._title = ""
		self._max = max_digits()
		self._accept_event = None
		self._cancel_event = None
		self._value = ""
		kit.DialogFacade.__init__(self)

	def _money_text(self):
		return nui.plain_text(self._header + localeInfo.NumberToMoneyString(money_of(self._value)))

	def _check(self):
		"""The check box row's keys: none here (BulkMoneyInputDialog has one)."""
		return {"check_on": False, "check_text": "", "checked": False}

	def _fill(self):
		values = {"title": nui.plain_text(self._title), "max": int(self._max), "money": self._money_text()}
		values.update(self._check())
		return values

	def _field_text(self):
		return self._value

	def _replay(self, legacy):
		legacy.SetTitle(self._title)
		legacy.SetMaxLength(self._max)
		legacy.SetMoneyHeaderText(self._header)
		legacy.SetAcceptEvent(self._accept_event)
		legacy.SetCancelEvent(self._cancel_event)

	def _refresh(self, **values):
		if self._held():
			self._window.set(**values)

	# --- the legacy surface -----------------------------------------------------------

	def Open(self):
		if self._routed():
			self._legacy.Open()
			return
		self._value = ""
		if not self._show():
			self._open_legacy()

	def Close(self):
		legacy = self._drop_legacy()
		if legacy is not None:
			legacy.Close()
			return
		self._release()

	def SetTitle(self, name):
		self._title = name
		if self._legacy is not None:
			self._legacy.SetTitle(name)
		self._refresh(title=nui.plain_text(name))

	def SetFocus(self):
		if self._legacy is not None:
			self._legacy.SetFocus()
		elif self._held():
			self._window.focus(FIELD)

	def SetMaxLength(self, length):
		self._max = min(max_digits(), int(length))
		if self._legacy is not None:
			self._legacy.SetMaxLength(length)
		self._refresh(max=self._max)

	def SetMoneyHeaderText(self, text):
		self._header = text
		if self._legacy is not None:
			self._legacy.SetMoneyHeaderText(text)
		self._refresh(money=self._money_text())

	def SetAcceptEvent(self, event):
		self._accept_event = event
		if self._legacy is not None:
			self._legacy.SetAcceptEvent(event)

	def SetCancelEvent(self, event):
		self._cancel_event = event
		if self._legacy is not None:
			self._legacy.SetCancelEvent(event)

	def SetValue(self, value):
		value = str(value)
		if self._legacy is not None:
			self._legacy.SetValue(value)
			return
		self._value = value
		if self._held():
			self._window.set_value(FIELD, value, caret="end")
		self._refresh(money=self._money_text())

	def GetText(self):
		if self._legacy is not None:
			return self._legacy.GetText()
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
		self._refresh(money=self._money_text())
		if linebreak:
			kit.call_event(self._accept_event)

	def _nui_accept(self):
		kit.call_event(self._accept_event)

	def _nui_cancel(self):
		kit.call_event(self._cancel_event)

	def _nui_escape(self):
		kit.call_event(self._cancel_event)
		return True

	def _nui_check(self):
		"""Only BulkMoneyInputDialog shows the row."""


class BulkMoneyInputDialog(MoneyInputDialog):
	"""uiCommon.BulkMoneyInputDialog (uicommon.py BulkMoneyInputDialog; OLD
	uiCommon.py:700-713): the money dialog with a check box under the amount,
	the offline shop's "bulk add" of a price. SetBulkMode shows the box,
	IsBulkMode reads it, and Close takes it away, as legacy's Close drops its
	check box. A press on the row flips it, as legacy's CheckBox does."""

	LEGACY = "uiCommon.LegacyBulkMoneyInputDialog"

	def __init__(self):
		self._check_text = None
		self._checked = False
		MoneyInputDialog.__init__(self)

	def _check(self):
		return {"check_on": self._check_text is not None,
		        "check_text": nui.plain_text(self._check_text or ""), "checked": bool(self._checked)}

	def _replay(self, legacy):
		MoneyInputDialog._replay(self, legacy)
		if self._check_text is not None:
			legacy.SetBulkMode(self._check_text, self._checked)

	def SetBulkMode(self, text=None, checked=False):
		if text is None:
			text = localeInfo.OFFLINE_SHOP_BULK_ADD
		self._check_text = text
		self._checked = bool(checked)
		if self._legacy is not None:
			self._legacy.SetBulkMode(text, checked)
		self._refresh(**self._check())

	def IsBulkMode(self):
		if self._legacy is not None:
			return self._legacy.IsBulkMode()
		return self._check_text is not None and bool(self._checked)

	def Close(self):
		self._check_text = None
		self._checked = False
		MoneyInputDialog.Close(self)

	def _nui_check(self):
		if self._check_text is None:
			return
		self._checked = not self._checked
		self._refresh(checked=self._checked)
