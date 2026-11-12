"""The auto-shout window (NOVA-204; OLD uiChat.py:1571-1840 AutoShoutWindow).

Opened from the button by the chat input (Interface.ToggleAutoShoutWindow).
The message field opens with the character's message (the last shout the
player sent, autoshout.message()); Start sends "/auto_shout on <text>",
Stop "/auto_shout off" (autoshout.py; the server owns the repeat). The state
line says Off, Starting... (until the server's state) or On with the time to
the next shout, from the server's last AutoShoutState. Enter in the field is
Start, Escape closes. While the NovaUI flag is on the Interface makes
nui_auto_shout.AutoShoutWindow instead, a facade over this class.

OLD bugs not ported: OLD's client re-sent the shout itself on a timer (any
client could shout faster), through client-side word lists, and keyed the
message by the account name."""

import ui

import autoshout
import localeInfo

UISCRIPT = "UIScript/AutoShoutWindow.py"


def time_text(seconds):
	"""M:SS, as the NovaUI countdown's ms format."""
	seconds = max(0, int(seconds + 0.999))
	return "%d:%02d" % (seconds // 60, seconds % 60)


class AutoShoutWindow(ui.ScriptWindow):

	# The state the window shows: "off", "waiting" or "on".
	shownState = "off"

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.board = None
		self.messageLine = None
		self.statusText = None
		self.nextText = None
		self.toggleButton = None
		self.isLoaded = False
		self.__LoadWindow()
		autoshout.listen(self)

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			ui.PythonScriptLoader().LoadScriptFile(self, UISCRIPT)
		except:
			import exception
			exception.Abort("AutoShoutWindow.LoadWindow.LoadScript")

		try:
			GetObject = self.GetChild
			self.board = GetObject("board")
			self.messageLine = GetObject("message")
			self.statusText = GetObject("status")
			self.nextText = GetObject("next")
			self.toggleButton = GetObject("toggle")
		except:
			import exception
			exception.Abort("AutoShoutWindow.LoadWindow.BindObject")

		self.board.SetCloseEvent(ui.__mem_func__(self.Close))
		self.messageLine.SetReturnEvent(ui.__mem_func__(self.OnToggle))
		self.messageLine.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.toggleButton.SetEvent(ui.__mem_func__(self.OnToggle))
		self.isLoaded = True

	def Destroy(self):
		autoshout.forget(self)
		self.ClearDictionary()
		self.board = None
		self.messageLine = None
		self.statusText = None
		self.nextText = None
		self.toggleButton = None

	def Open(self):
		"""The field with the character's message, the state, the window
		centered and the field focused."""
		self.messageLine.SetText(autoshout.message())
		self.OnAutoShoutChanged()
		self.SetCenterPosition()
		self.Show()
		self.SetTop()
		self.messageLine.SetFocus()

	def Close(self):
		self.messageLine.KillFocus()
		self.Hide()

	def Toggle(self):
		if self.IsShow():
			self.Close()
		else:
			self.Open()

	def OnToggle(self):
		"""Start with the field's text, or Stop."""
		if autoshout.is_on():
			autoshout.stop()
		else:
			autoshout.start(self.messageLine.GetText())
		return True

	def State(self):
		if autoshout.is_confirmed():
			return "on"
		if autoshout.is_on():
			return "waiting"
		return "off"

	## autoshout's listener: every change of the switch or the server's state.
	def OnAutoShoutChanged(self):
		if not self.isLoaded:
			return
		state = self.shownState = self.State()
		self.statusText.SetText({"off": localeInfo.AUTO_SHOUT_STATUS_OFF, "waiting": localeInfo.AUTO_SHOUT_STATUS_WAITING,
		                         "on": localeInfo.AUTO_SHOUT_STATUS_ON}[state])
		self.toggleButton.SetText(localeInfo.AUTO_SHOUT_START if state == "off" else localeInfo.AUTO_SHOUT_STOP)
		self.__RefreshNext()

	def __RefreshNext(self):
		if self.shownState == "on":
			self.nextText.SetText("%s %s" % (localeInfo.AUTO_SHOUT_NEXT, time_text(autoshout.seconds_left())))
		else:
			self.nextText.SetText("")

	def OnUpdate(self):
		"""Legacy's countdown, while shown."""
		if self.shownState == "on":
			self.__RefreshNext()

	def OnPressEscapeKey(self):
		self.Close()
		return True
