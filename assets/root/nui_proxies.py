"""Widget proxies of the Wave 3b windows (P14 spec 6.0, 6.4): a NovaUI window
that subclasses its legacy controller (nui_inventory.InventoryWindow is a
uiInventory.InventoryWindow) puts these where the legacy uiscript loader put
its text lines, buttons, images and boards, so the legacy code that drives
them runs unchanged; each records what it is told and hands it to the
NovaUI window (a model key, an event the board's button calls). The slot
windows' proxy is nui_slots.SlotWindowProxy.

Every proxy has only the legacy methods its legacy widget is called with,
so a call it does not know raises AttributeError, which the tests see.
Layout calls (positions, sizes, alignment) do nothing: the document lays
itself out. Nothing here runs per frame."""

def _call(fn, *args):
	if fn:
		return fn(*args)
	return None


class _Shown(object):
	"""Show, Hide and IsShow over a `shown` flag, with an optional
	on_show(shown) callback."""

	shown = True
	on_show = None

	def Show(self):
		self.shown = True
		_call(self.on_show, True)

	def Hide(self):
		self.shown = False
		_call(self.on_show, False)

	def IsShow(self):
		return bool(self.shown)

	def SetParent(self, parent):
		"""Nothing: the document holds the element."""

	def SetPosition(self, x, y):
		"""Nothing: the document lays itself out."""

	def SetTop(self):
		"""Nothing: the board raises the document."""


class TextProxy(_Shown):
	"""ui.TextLine: SetText and GetText (on_text(text) runs at each SetText,
	the window writes a model key), the colors recorded."""

	def __init__(self, on_text=None, text=""):
		self.text = str(text)
		self.color = None
		self.on_text = on_text

	def SetText(self, text):
		self.text = "" if text is None else str(text)
		_call(self.on_text, self.text)

	def GetText(self):
		return self.text

	def SetFontColor(self, r, g, b):
		self.color = (r, g, b)

	def SetPackedFontColor(self, color):
		self.color = int(color) & 0xFFFFFFFF

	def SetHorizontalAlignCenter(self):
		pass

	def SetHorizontalAlignRight(self):
		pass

	def SetHorizontalAlignLeft(self):
		pass

	def SetWindowHorizontalAlignCenter(self):
		pass


class ButtonProxy(_Shown):
	"""ui.Button (and RadioButton): SetEvent stores the event and its
	arguments, click() calls it as the legacy CallEvent does; Down and SetUp
	keep the pressed look (`down`), Enable and Disable `enabled`;
	on_change(proxy) runs after each state change."""

	def __init__(self, on_change=None):
		self.event = None
		self.event_args = ()
		self.down = False
		self.enabled = True
		self.tooltip = ""
		self.text = ""
		self.destroyed = False
		self.on_change = on_change

	def _changed(self):
		_call(self.on_change, self)

	def SetEvent(self, event, *args):
		self.event = event
		self.event_args = args

	def click(self):
		"""The board's button: the stored event, while enabled."""
		if self.enabled and self.event:
			self.event(*self.event_args)

	def Show(self):
		self.shown = True
		self._changed()

	def Hide(self):
		self.shown = False
		self._changed()

	def Enable(self):
		self.enabled = True
		self._changed()

	def Disable(self):
		self.enabled = False
		self._changed()

	def IsEnabled(self):
		return self.enabled

	def Down(self):
		self.down = True
		self._changed()

	def SetUp(self):
		self.down = False
		self._changed()

	def IsDown(self):
		return self.down

	def SetToolTipText(self, text, x=0, y=0):
		self.tooltip = "" if text is None else str(text)

	def SetText(self, text):
		self.text = "" if text is None else str(text)
		self._changed()

	def GetText(self):
		return self.text

	def Destroy(self):
		self.destroyed = True
		self.event = None


class ImageProxy(_Shown):
	"""ui.ImageBox (and ExpandedImageBox): LoadImage records the path
	(on_image(path) runs), GetWidth and GetHeight answer the loaded image's
	size through a hidden legacy ui.ImageBox, made at the first ask."""

	def __init__(self, on_image=None, image=""):
		self.image = str(image)
		self.on_image = on_image
		self._measure = None

	def LoadImage(self, path):
		self.image = "" if path is None else str(path)
		self._measure = None
		_call(self.on_image, self.image)

	def GetImageFileName(self):
		return self.image

	def _size(self):
		if not self.image:
			return (0, 0)
		if self._measure is None:
			try:
				import ui
				box = ui.ImageBox()
				box.LoadImage(self.image)
				box.Hide()
				self._measure = (int(box.GetWidth() or 0), int(box.GetHeight() or 0))
			except Exception:
				self._measure = (0, 0)
		return self._measure

	def GetWidth(self):
		return self._size()[0]

	def GetHeight(self):
		return self._size()[1]

	def SetScale(self, x, y):
		pass

	def SetDiffuseColor(self, r, g, b, a):
		pass

	def SetWindowHorizontalAlignCenter(self):
		pass

	def SetWindowVerticalAlignCenter(self):
		pass


class BoardProxy(_Shown):
	"""ui.Board, ui.TitleBar, ui.ThinBoard or a layer window: SetSize,
	SetWidth, SetPosition record (GetWidth and GetHeight answer the last
	ones, for legacy code that sizes from them), SetCloseEvent stores the
	close event, which close() calls (the board's close button)."""

	def __init__(self, width=0, height=0, on_show=None):
		self.width = int(width)
		self.height = int(height)
		self.close_event = None
		self.title = ""
		self.on_show = on_show

	def SetSize(self, width, height):
		self.width = int(width)
		self.height = int(height)

	def SetWidth(self, width):
		self.width = int(width)

	def GetWidth(self):
		return self.width

	def GetHeight(self):
		return self.height

	def SetCloseEvent(self, event):
		self.close_event = event

	def close(self):
		_call(self.close_event)

	def SetTitleName(self, name):
		self.title = "" if name is None else str(name)

	def UpdateRect(self):
		pass

	def AddFlag(self, flag):
		pass


class QuestionWindowProxy(_Shown):
	"""The legacy refine dialog's own question window (a ui.ScriptWindow from
	uiscript/questiondialog2.py, uirefine.py:62-80) as the dialog kit's
	question: GetChild hands out the children legacy binds ("message1",
	"message2", "accept", "cancel"); Show opens a uiCommon.QuestionDialog2
	(the kit's facade while the dialogs flag is on) with the two messages and
	the bound events, Hide closes it, IsShow is its state."""

	CHILDREN = ("message1", "message2", "accept", "cancel")

	def __init__(self, make_dialog=None):
		self.shown = False
		self._make_dialog = make_dialog
		self.dialog = None
		self.children = {"message1": TextProxy(), "message2": TextProxy(), "accept": ButtonProxy(),
		                 "cancel": ButtonProxy()}

	def GetChild(self, name):
		return self.children[name]

	def _new_dialog(self):
		if self._make_dialog is not None:
			return self._make_dialog()
		import uiCommon
		return uiCommon.QuestionDialog2()

	def Show(self):
		dialog = self.dialog
		if dialog is None:
			dialog = self.dialog = self._new_dialog()
		dialog.SetText1(self.children["message1"].GetText())
		dialog.SetText2(self.children["message2"].GetText())
		accept, cancel = self.children["accept"], self.children["cancel"]
		dialog.SetAcceptEvent(lambda: accept.click())
		dialog.SetCancelEvent(lambda: cancel.click())
		dialog.Open()
		self.shown = True

	def Hide(self):
		self.shown = False
		dialog = self.dialog
		if dialog is not None:
			dialog.Close()

	def SetTop(self):
		dialog = self.dialog
		if dialog is not None and hasattr(dialog, "SetTop"):
			dialog.SetTop()

	def Destroy(self):
		dialog, self.dialog = self.dialog, None
		if dialog is not None:
			dialog.Close()
			destroy = getattr(dialog, "Destroy", None)
			if destroy is not None:
				destroy()

