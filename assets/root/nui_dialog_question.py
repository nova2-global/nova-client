"""The question dialog of the NovaUI dialog kit (nui/windows/dialog-question):
a modal with lines of text and two buttons, for uiCommon.QuestionDialog and
QuestionDialog2. uiCommon.QuestionDialogWithTimeLimit stays legacy: its
countdown needs a timer, which comes with the C++ data feeds (G8).

The buttons call their events and leave the dialog open, as the legacy
buttons do: callers close it themselves. Enter presses the accept button,
which has the focus (new; legacy Enter did nothing here). Escape only closes
it, with no event (uicommon.py:294-296). QuestionDialog2.SetWarningLine
marks one of its two texts as a warning (the point reset's confirmation,
which legacy colors red); every other facade of the kind shows none. See
nui_dialog_kit.py for the shared rules.
"""

import nui
import nui_dialog_kit as kit
import ui


class QuestionWindow(kit.KindWindow):
	DOCUMENT = "nui/windows/dialog-question/dialog-question.rml"
	MODEL = "dialog_question"
	BOX = "dialog-question"
	DEFAULT = "dialog-question-accept"

	def initial_model(self):
		return {"lines": [], "accept_label": "@ui.YES", "cancel_label": "@ui.NO", "warn_line": -1}

	@nui.on("accept")
	def on_accept(self):
		self.forward("_nui_accept")

	@nui.on("cancel")
	def on_cancel(self):
		self.forward("_nui_cancel")


class QuestionDialog(kit.DialogFacade):
	"""uiCommon.QuestionDialog (uicommon.py:217-296)."""

	KIND = QuestionWindow
	LEGACY = "uiCommon.LegacyQuestionDialog"

	def __init__(self):
		self._text = ""
		self._accept_text = None
		self._cancel_text = None
		self._accept_event = None
		self._cancel_event = None
		kit.DialogFacade.__init__(self)

	def _lines(self):
		return kit.text_lines(self._text)

	def _warn_row(self):
		"""The row of the model's lines that shows as a warning: -1 here, so a
		facade that claims the window takes any mark another one left off."""
		return -1

	def _fill(self):
		return {
			"lines": self._lines(),
			"accept_label": "@ui.YES" if self._accept_text is None else nui.plain_text(self._accept_text),
			"cancel_label": "@ui.NO" if self._cancel_text is None else nui.plain_text(self._cancel_text),
			"warn_line": self._warn_row(),
		}

	def _replay_text(self, legacy):
		legacy.SetText(self._text)

	def _replay(self, legacy):
		self._replay_text(legacy)
		if self._accept_text is not None:
			legacy.SetAcceptText(self._accept_text)
		if self._cancel_text is not None:
			legacy.SetCancelText(self._cancel_text)
		legacy.SetAcceptEvent(self._accept_event)
		legacy.SetCancelEvent(self._cancel_event)

	def _refresh(self, **values):
		if self._held():
			self._window.set(**values)

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

	def SetWidth(self, width):
		if self._legacy is not None:
			self._legacy.SetWidth(width)

	def SetText(self, text):
		self._text = text
		if self._legacy is not None:
			self._legacy.SetText(text)
		self._refresh(lines=self._lines())

	def SetAcceptText(self, text):
		self._accept_text = text
		if self._legacy is not None:
			self._legacy.SetAcceptText(text)
		self._refresh(accept_label=nui.plain_text(text))

	def SetCancelText(self, text):
		self._cancel_text = text
		if self._legacy is not None:
			self._legacy.SetCancelText(text)
		self._refresh(cancel_label=nui.plain_text(text))

	def SetAcceptEvent(self, event):
		self._accept_event = event
		if self._legacy is not None:
			self._legacy.SetAcceptEvent(event)

	def SetCancelEvent(self, event):
		self._cancel_event = event
		if self._legacy is not None:
			self._legacy.SetCancelEvent(event)

	def SAFE_SetAcceptEvent(self, event):
		self.SetAcceptEvent(ui.__mem_func__(event))

	def SAFE_SetCancelEvent(self, event):
		self.SetCancelEvent(ui.__mem_func__(event))

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def _nui_accept(self):
		kit.call_event(self._accept_event)

	def _nui_cancel(self):
		kit.call_event(self._cancel_event)

	def _nui_escape(self):
		return self.OnPressEscapeKey()


class QuestionDialog2(QuestionDialog):
	"""uiCommon.QuestionDialog2 (uicommon.py:298-351): two messages, each of one
	or more lines. SetText sets the first."""

	LEGACY = "uiCommon.LegacyQuestionDialog2"

	# The legacy warning color, uipointreset.py's SetFontColor(1.0, 0.3, 0.3).
	WARNING_COLOR = (1.0, 0.3, 0.3)

	def __init__(self):
		self._text2 = ""
		self._warning = -1
		QuestionDialog.__init__(self)

	def _lines(self):
		return kit.text_lines(self._text) + kit.text_lines(self._text2)

	def _warn_row(self):
		"""Text 0 starts at row 0, text 1 after text 0's lines; a warning
		text of several lines marks its first."""
		if self._warning == 0 and kit.text_lines(self._text):
			return 0
		if self._warning == 1 and kit.text_lines(self._text2):
			return len(kit.text_lines(self._text))
		return -1

	def _replay_text(self, legacy):
		legacy.SetText1(self._text)
		legacy.SetText2(self._text2)
		self._replay_warning(legacy)

	def _replay_warning(self, legacy):
		line = {0: "textLine1", 1: "textLine2"}.get(self._warning)
		target = getattr(legacy, line, None) if line else None
		if target is not None:
			target.SetFontColor(*self.WARNING_COLOR)

	def SetWarningLine(self, index):
		"""Marks text line `index` (0 the text of SetText1, 1 of SetText2) as
		a warning, or none with -1 (the default). New: legacy colors its text
		line itself (uipointreset.py:40)."""
		self._warning = index if index in (0, 1) else -1
		if self._legacy is not None:
			self._replay_warning(self._legacy)
		self._refresh(warn_line=self._warn_row())

	def SetText(self, text):
		self.SetText1(text)

	def SetText1(self, text):
		self._text = text
		if self._legacy is not None:
			self._legacy.SetText1(text)
		self._refresh(lines=self._lines(), warn_line=self._warn_row())

	def SetText2(self, text):
		self._text2 = text
		if self._legacy is not None:
			self._legacy.SetText2(text)
		self._refresh(lines=self._lines(), warn_line=self._warn_row())
