"""NovaUI point reset (the dialog kit's question, P11 spec 6.7 and D13).

While the "point-reset" window flag is on and the dialog kit is in use (the
"dialogs" flag; the Interface refuses point-reset without it),
Interface.__MakeDialogs makes PointResetDialog below through
nui_windows.make() instead of uiPointReset.PointResetDialog: the facade of
the legacy dialog, with its name, constructor and methods. C++
StartPointReset reaches it through game.StartPointReset and
Interface.OpenPointResetDialog.

It has no document of its own: its two questions are uiCommon.QuestionDialog2
facades of the dialog kit (the kit's one question document). The question
asks for the reset; its Yes opens the confirmation, whose first line is a
warning (QuestionDialog2.SetWarningLine), and whose Yes sends /pointreset.
The kit shows one question of a kind at a time, so the confirmation hides
the question, where legacy shows the confirmation over it. The texts are
locale keys (POINT_RESET_*), where legacy hard-codes Korean in every locale
(uipointreset.py:33-41). Escape closes the question shown, as the kit's
question does with no event, and as legacy's OnPressEscapeKey closes both."""

import net
import ui
import uiCommon
import uiScriptLocale

import nui_dialog_kit
import nui_hud


class PointResetDialog(nui_hud.LayoutCalls):
	"""uiPointReset.PointResetDialog on NovaUI (Interface.dlgPointReset)."""

	NUI_FACADE = True
	KEY = "point-reset"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.question = uiCommon.QuestionDialog2()
		self.ConfirmDialog = uiCommon.QuestionDialog2()
		self.__SetUp()

	def __SetUp(self):
		question, confirm = self.question, self.ConfirmDialog
		question.SetText1(uiScriptLocale.POINT_RESET_QUESTION_1)
		question.SetText2(uiScriptLocale.POINT_RESET_QUESTION_2)
		question.SetAcceptEvent(ui.__mem_func__(self.OpenConfirmDialog))
		question.SetCancelEvent(ui.__mem_func__(self.Close))
		confirm.SetText1(uiScriptLocale.POINT_RESET_CONFIRM_1)
		confirm.SetText2(uiScriptLocale.POINT_RESET_CONFIRM_2)
		confirm.SetWarningLine(0)
		confirm.SetAcceptEvent(ui.__mem_func__(self.ResetPoint))
		confirm.SetCancelEvent(ui.__mem_func__(self.Close))

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		"""Only with the kit's facades: the legacy question dialogs (the kit
		off or its document failed) would be legacy's look with these texts,
		so the legacy point reset is made instead."""
		return all(isinstance(dialog, nui_dialog_kit.DialogFacade) for dialog in (self.question, self.ConfirmDialog))

	def nui_discard(self):
		self._nui_discarded = True
		for name in ("question", "ConfirmDialog"):
			dialog = getattr(self, name, None)
			setattr(self, name, None)
			if dialog is not None:
				_drop(dialog)
		nui_hud.forget(self.KEY, self)

	# --- the Interface's calls (uipointreset.py) ------------------------------------------

	def LoadDialog(self):
		"""Both questions were set up with the facade."""
		pass

	def Destroy(self):
		self.nui_discard()

	def Show(self):
		if self.question is not None:
			self.question.Open()

	def OpenDialog(self):
		self.Show()

	def SetTop(self):
		for dialog in (self.question, self.ConfirmDialog):
			if dialog is not None and dialog.IsShow():
				dialog.SetTop()

	def OpenConfirmDialog(self):
		"""The question's Yes: one question at a time (D13)."""
		if self.question is not None:
			self.question.Close()
		if self.ConfirmDialog is not None:
			self.ConfirmDialog.Open()
			self.ConfirmDialog.SetTop()

	def ResetPoint(self):
		net.SendChatPacket("/pointreset")
		self.Close()

	def Close(self):
		for dialog in (self.ConfirmDialog, self.question):
			if dialog is not None:
				dialog.Close()
		return True

	def Hide(self):
		self.Close()

	def IsShow(self):
		return any(dialog is not None and dialog.IsShow() for dialog in (self.question, self.ConfirmDialog))

	def OnPressEscapeKey(self):
		self.Close()
		return True


def _drop(dialog):
	"""A question facade let go: hidden, its events cleared, so nothing of
	this facade stays reachable from the kit's window."""
	try:
		dialog.Close()
		dialog.SetAcceptEvent(0)
		dialog.SetCancelEvent(0)
	except Exception:
		pass
