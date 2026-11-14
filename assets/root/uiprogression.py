"""The character progression switches of wave 10 (NOVA-199, NOVA-200).

- The anti-EXP switch: the server keeps it (the chat command /anti_exp and the
  quest flag anti_exp.on) and tells the client with "AntiExpState <0|1>" at
  login and at each change; game.py hands that to set_anti_exp(), which keeps
  it here and shows it on the taskbar (legacy uitaskbar and nui_taskbar both
  have SetAntiExp). A press on the taskbar's EXP gauge sends /anti_exp, which
  flips it; the server's answer comes back here.
- The checkpoint level-up: at levels 105, 115, 120, 130 and 135 the server
  holds the level-up and sends "ConfirmLevelUp"; LevelUpQuestion asks the
  player. Yes sends /confirm_level_up; no turns anti-EXP on (/anti_exp 1), as
  OLD meant to (OLD game.py:4119-4168 toggled it only when it was already
  on, so a "no" left EXP flowing).

The dialog is uiCommon.QuestionDialog, which is the dialog kit's NovaUI dialog
while the "dialogs" window flag is on, and the legacy one otherwise."""

import net
import player
import ui
import uiCommon
import localeInfo

# The state the server last told; False until it does.
ANTI_EXP_ON = False


def is_anti_exp_on():
	return ANTI_EXP_ON


def set_anti_exp(on, taskbar=None):
	"""The server's "AntiExpState": keeps it and shows it on the taskbar."""
	global ANTI_EXP_ON
	ANTI_EXP_ON = bool(int(on))
	if taskbar is not None and hasattr(taskbar, "SetAntiExp"):
		taskbar.SetAntiExp(ANTI_EXP_ON)


class LevelUpQuestion(object):
	"""One open question at a time; a second "ConfirmLevelUp" while it shows
	only raises it."""

	def __init__(self):
		self.dialog = None

	def Open(self):
		if self.dialog is not None:
			self.dialog.SetTop()
			return
		nextLevel = int(player.GetStatus(player.LEVEL)) + 1
		dialog = uiCommon.QuestionDialog()
		dialog.SetText(localeInfo.CONFIRM_LEVEL_UP_QUESTION % nextLevel)
		dialog.SetWidth(400)
		dialog.SetAcceptEvent(ui.__mem_func__(self.__OnAccept))
		dialog.SetCancelEvent(ui.__mem_func__(self.__OnCancel))
		dialog.Open()
		self.dialog = dialog

	def IsOpen(self):
		return self.dialog is not None

	def Close(self):
		dialog, self.dialog = self.dialog, None
		if dialog is not None:
			dialog.Close()

	def __OnAccept(self):
		# Once per question: the dialog goes before the command is sent.
		if self.dialog is None:
			return
		self.Close()
		net.SendChatPacket("/confirm_level_up")

	def __OnCancel(self):
		if self.dialog is None:
			return
		self.Close()
		if not ANTI_EXP_ON:
			net.SendChatPacket("/anti_exp 1")
