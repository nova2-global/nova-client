"""The message dialog of the NovaUI dialog kit (nui/windows/dialog-message):
a modal with lines of text and one button, for uiCommon.PopupDialog and for
networkModule.PopupDialog, the phase popup (connecting, login failures).

Made through nui_windows.factory("dialogs", ...) at the end of uicommon.py
and networkmodule.py; see nui_dialog_kit.py for the shared rules. Enter
presses the button (it has the focus) and Escape does what the button does:
Close(), which runs the event.
"""

import localeInfo
import nui
import nui_dialog_kit as kit


class MessageWindow(kit.KindWindow):
	DOCUMENT = "nui/windows/dialog-message/dialog-message.rml"
	MODEL = "dialog_message"
	BOX = "dialog-message"
	DEFAULT = "dialog-message-accept"

	def initial_model(self):
		return {"title": "", "lines": [], "button": "@ui.OK"}

	@nui.on("accept")
	def on_accept(self):
		self.forward("_nui_accept")


class PopupDialog(kit.DialogFacade):
	"""uiCommon.PopupDialog (uicommon.py:7-66): Close() hides, then calls the
	accept event, also when the dialog is not shown."""

	KIND = MessageWindow
	LEGACY = "uiCommon.LegacyPopupDialog"

	def __init__(self):
		self._text = ""
		self._button = None
		self.acceptEvent = lambda *arg: None
		kit.DialogFacade.__init__(self)

	def _fill(self):
		button = "@ui.OK" if self._button is None else nui.plain_text(self._button)
		return {"title": "", "lines": kit.text_lines(self._text), "button": button}

	def _replay(self, legacy):
		legacy.SetText(self._text)
		if self._button is not None:
			legacy.SetButtonName(self._button)
		legacy.SetAcceptEvent(self.acceptEvent)

	def Open(self):
		if self._routed():
			self._legacy.Open()
		elif not self._show():
			self._open_legacy()

	def Close(self):
		legacy = self._drop_legacy()
		if legacy is not None:
			legacy.Close()  # hides and runs its accept event, which is this one
			return
		self._release()
		kit.call_event(self.acceptEvent)

	def Destroy(self):
		self.Close()

	def SetWidth(self, width):
		if self._legacy is not None:
			self._legacy.SetWidth(width)

	def SetText(self, text):
		self._text = text
		if self._legacy is not None:
			self._legacy.SetText(text)
		elif self._held():
			self._window.set(lines=kit.text_lines(text))

	def SetAcceptEvent(self, event):
		self.acceptEvent = event
		if self._legacy is not None:
			self._legacy.SetAcceptEvent(event)

	def SetButtonName(self, name):
		self._button = name
		if self._legacy is not None:
			self._legacy.SetButtonName(name)
		elif self._held():
			self._window.set(button=nui.plain_text(name))

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def OnIMEReturn(self):
		self.Close()
		return True

	def _nui_accept(self):
		self.Close()

	def _nui_escape(self):
		return self.OnPressEscapeKey()


class PhasePopupDialog(kit.DialogFacade):
	"""networkModule.PopupDialog (networkmodule.py:21-95), the popup MainStream
	keeps across the phases. CloseEvent is a plain attribute, as there:
	nui_login.after_popup wraps it."""

	KIND = MessageWindow
	LEGACY = "networkModule.LegacyPopupDialog"

	def __init__(self):
		self._message = ""
		self._button = None
		self._close_event = 0
		kit.DialogFacade.__init__(self)

	@property
	def CloseEvent(self):
		if self._legacy is not None:
			return self._legacy.CloseEvent
		return self._close_event

	@CloseEvent.setter
	def CloseEvent(self, event):
		if self._legacy is not None:
			self._legacy.CloseEvent = event
		else:
			self._close_event = event

	def _fill(self):
		return {"title": "", "lines": kit.text_lines(self._message), "button": nui.plain_text(self._button)}

	def _replay(self, legacy):
		legacy.LoadDialog()

	def LoadDialog(self):
		pass

	def Open(self, Message, event=0, ButtonName=None):
		if ButtonName is None:
			ButtonName = localeInfo.UI_CANCEL
		self._message = Message
		if self._routed():
			self._legacy.Open(Message, event, ButtonName)
			return
		if self.IsShow():
			self.Close()
		self._close_event = event
		self._button = ButtonName
		if not self._show():
			self._close_event = 0
			self._open_legacy(Message, event, ButtonName)

	def Close(self):
		legacy = self._drop_legacy()
		if legacy is not None:
			legacy.Close()
			return
		if not self.IsShow():
			self._close_event = 0
			return
		self._release()
		if 0 != self._close_event:
			self._close_event()
			self._close_event = 0

	def Destroy(self):
		self.Close()

	def GetText(self):
		"""The message as given to Open (facade only, for kits and tests)."""
		return self._message

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def OnIMEReturn(self):
		self.Close()
		return True

	def _nui_accept(self):
		self.Close()

	def _nui_escape(self):
		return self.OnPressEscapeKey()
