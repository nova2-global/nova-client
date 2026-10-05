"""The input dialog of the NovaUI dialog kit (nui/windows/dialog-input): a modal
with a title bar, up to two lines of description and one text field, for
uiCommon.InputDialog, InputDialogWithDescription and
InputDialogWithDescription2.

Enter in the field calls the accept event and Escape in the field the
cancel event, as the legacy edit line did (its OnIMEReturn and
OnPressEscapeKey were the events); the buttons and the title bar's close
button call them too, and none of them closes the dialog. Number mode keeps
digits only, secret mode shows stars, and the field's value never enters a
data model. See nui_dialog_kit.py for the shared rules.
"""

import nui
import nui_dialog_kit as kit

FIELD = "dialog-input-field"
DIGITS = "0123456789"


def digits_of(text):
	return "".join(c for c in text if c in DIGITS)


class InputWindow(kit.KindWindow):
	DOCUMENT = "nui/windows/dialog-input/dialog-input.rml"
	MODEL = "dialog_input"
	BOX = "dialog-input"
	FIELD = FIELD

	def initial_model(self):
		return {"title": "", "lines": [], "secret": False, "max": 12}

	@nui.on("edit")
	def on_edit(self, value, linebreak):
		self.forward("_nui_edit", value, linebreak)

	@nui.on("accept")
	def on_accept(self):
		self.forward("_nui_accept")

	@nui.on("cancel")
	def on_cancel(self):
		self.forward("_nui_cancel")


class InputDialog(kit.DialogFacade):
	"""uiCommon.InputDialog (uicommon.py:68-146)."""

	KIND = InputWindow
	LEGACY = "uiCommon.LegacyInputDialog"

	def __init__(self):
		self._title = ""
		self._number = False
		self._secret = False
		self._max = None
		self._accept_event = None
		self._cancel_event = None
		self._value = ""
		kit.DialogFacade.__init__(self)

	def _descriptions(self):
		return []

	def _fill(self):
		return {
			"title": nui.plain_text(self._title),
			"lines": [nui.plain_text(line) for line in self._descriptions()],
			"secret": bool(self._secret),
			"max": 12 if self._max is None else int(self._max),
		}

	def _field_text(self):
		return self._value

	def _replay_descriptions(self, legacy):
		pass

	def _replay(self, legacy):
		legacy.SetTitle(self._title)
		if self._number:
			legacy.SetNumberMode()
		if self._secret:
			legacy.SetSecretMode()
		if self._max is not None:
			legacy.SetMaxLength(self._max)
		self._replay_descriptions(legacy)
		legacy.SetAcceptEvent(self._accept_event)
		legacy.SetCancelEvent(self._cancel_event)

	def _refresh(self, **values):
		if self._held():
			self._window.set(**values)

	# --- the legacy surface -----------------------------------------------------------

	def Open(self):
		if self._routed():
			self._legacy.Open()
		elif not self._show():
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

	def SetNumberMode(self):
		self._number = True
		if self._legacy is not None:
			self._legacy.SetNumberMode()

	def SetSecretMode(self):
		self._secret = True
		if self._legacy is not None:
			self._legacy.SetSecretMode()
		self._refresh(secret=True)

	def SetFocus(self):
		if self._legacy is not None:
			self._legacy.SetFocus()
		elif self._held():
			self._window.focus(FIELD)

	def SetMaxLength(self, length):
		self._max = int(length)
		if self._legacy is not None:
			self._legacy.SetMaxLength(length)
		self._refresh(max=self._max)

	def SetSlotWidth(self, width):
		if self._legacy is not None:
			self._legacy.SetSlotWidth(width)

	def SetBoardWidth(self, width):
		if self._legacy is not None:
			self._legacy.SetBoardWidth(width)

	def SetAcceptEvent(self, event):
		self._accept_event = event
		if self._legacy is not None:
			self._legacy.SetAcceptEvent(event)

	def SetCancelEvent(self, event):
		self._cancel_event = event
		if self._legacy is not None:
			self._legacy.SetCancelEvent(event)

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
		if self._number and digits_of(value) != value:
			# set_value sends a change of its own with the digits.
			value = digits_of(value)
			if self._held():
				self._window.set_value(FIELD, value, caret="end")
		self._value = value
		if linebreak:
			kit.call_event(self._accept_event)

	def _nui_accept(self):
		kit.call_event(self._accept_event)

	def _nui_cancel(self):
		kit.call_event(self._cancel_event)

	def _nui_escape(self):
		# The legacy edit line kept Escape, with or without an event.
		kit.call_event(self._cancel_event)
		return True


class InputDialogWithDescription(InputDialog):
	"""uiCommon.InputDialogWithDescription (uicommon.py:148-180): one line of
	description above the field."""

	LEGACY = "uiCommon.LegacyInputDialogWithDescription"

	def __init__(self):
		self._description = None
		InputDialog.__init__(self)

	def _descriptions(self):
		return [] if self._description is None else [str(self._description)]

	def _replay_descriptions(self, legacy):
		if self._description is not None:
			legacy.SetDescription(self._description)

	def SetDescription(self, text):
		self._description = text
		if self._legacy is not None:
			self._legacy.SetDescription(text)
		self._refresh(lines=[nui.plain_text(line) for line in self._descriptions()])


class InputDialogWithDescription2(InputDialog):
	"""uiCommon.InputDialogWithDescription2 (uicommon.py:182-215): two lines of
	description above the field."""

	LEGACY = "uiCommon.LegacyInputDialogWithDescription2"

	def __init__(self):
		self._description1 = None
		self._description2 = None
		InputDialog.__init__(self)

	def _descriptions(self):
		return [str(text) for text in (self._description1, self._description2) if text is not None]

	def _replay_descriptions(self, legacy):
		if self._description1 is not None:
			legacy.SetDescription1(self._description1)
		if self._description2 is not None:
			legacy.SetDescription2(self._description2)

	def SetDescription1(self, text):
		self._description1 = text
		if self._legacy is not None:
			self._legacy.SetDescription1(text)
		self._refresh(lines=[nui.plain_text(line) for line in self._descriptions()])

	def SetDescription2(self, text):
		self._description2 = text
		if self._legacy is not None:
			self._legacy.SetDescription2(text)
		self._refresh(lines=[nui.plain_text(line) for line in self._descriptions()])
