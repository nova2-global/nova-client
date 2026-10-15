"""Widget proxies of the Wave 4 windows (P16 spec 4.2): the trade and social
windows subclass their legacy controllers, as the Wave 3b item windows do
(nui_proxies, nui_slots.SlotWindowProxy), and their uiscript loaders put
these where the legacy edit lines, toggles, radio groups, scroll bars,
combo boxes, guild slots, marks, popups and list boxes were. Each records
what the legacy code tells it and hands it to its NovaUI window through
`on_change` (the window sets its model or its document); the board calls the
lower-case methods (press(), picked(), typed(), fire_return(), ...) where the
legacy widget's C++ or its own Python would have acted.

A module of its own, so Wave 3c's additions to nui_proxies.py and
nui_slots.py never meet Wave 4's. Every class has only the legacy methods its
Wave 4 users call, so a call it does not know raises AttributeError, which
the tests see (tools/nui_form_proxies_test.py finds those calls in the
legacy modules). Layout calls (positions, sizes, alignment, parents) only
record or do nothing: the document lays itself out. Nothing here runs per
frame."""

import nui_proxies
import nui_slots


def _call(fn, *args):
	if fn:
		return fn(*args)
	return None


def _nothing(*args):
	"""ui.Window.NoneMethod: an event nobody set."""
	return None


# --- slot windows -----------------------------------------------------------------------

class TypedSlotWindowProxy(nui_slots.SlotWindowProxy):
	"""A ui.SlotWindow or ui.GridSlotWindow whose item cells are not inventory
	items (the exchange's two grids, the shop, the safebox, the mall): its
	cells' type is `slot_type` (a player.SLOT_TYPE_* value, or a callable
	that answers one at each refresh: the shop's NPC or private type), and
	their ref is positions(slot) (the safebox's global position, the shop's
	real index), so nui_slots.LegacySlotEvents finds the picked cell by
	(type, ref) as the legacy mouse controller attached it."""

	def __init__(self, slot_numbers, on_refresh, cols=None, rows=None, positions=None, window=None, slot_type=None):
		self.slot_type = slot_type
		nui_slots.SlotWindowProxy.__init__(self, slot_numbers, on_refresh, cols=cols, rows=rows, positions=positions,
		                                   window=window)

	def _slot_type(self):
		slot_type = self.slot_type
		if callable(slot_type):
			slot_type = slot_type()
		if slot_type is None:
			return nui_slots.SlotWindowProxy._slot_type(self)
		return int(slot_type)


class GuildSkillSlotProxy(nui_slots.SlotWindowProxy):
	"""The guild skill page's slot windows: legacy's SetSkillSlot (ui.py
	SlotWindow.SetSkillSlot: the skill's icon and its level as the count)
	and the slot buttons (the "+" a skill shows while points remain). plus()
	is the shown buttons in cell order."""

	def __init__(self, slot_numbers, on_refresh, cols=None, rows=None, positions=None, window=None):
		nui_slots.SlotWindowProxy.__init__(self, slot_numbers, on_refresh, cols=cols, rows=rows, positions=positions,
		                                   window=window)
		self.button_art = ("", "", "")
		self._buttons = set()

	def SetSkillSlot(self, slot, skill_index, level):
		"""skill.GetIconImage's grade-0 art (its file through
		GetIconImageFileNameNew(index, 0)), the level as the count; a skill
		without data clears the slot, as an icon of 0 does."""
		if not self._holds(slot):
			return
		import skill
		get_icon = getattr(skill, "GetIconImageFileNameNew", None)
		icon = get_icon(skill_index, 0) if get_icon is not None else ""
		if not icon:
			self.ClearSlot(slot)
			return
		record = self._record(int(slot))
		record.update({"kind": "skill", "vnum": int(skill_index), "icon": nui_slots.icon_source(icon), "w": 1, "h": 1,
		               "locked": False, "disabled": False,
		               "count": str(int(level)) if level and int(level) > 0 else ""})

	def AppendSlotButton(self, up, over="", down=""):
		self.button_art = (str(up or ""), str(over or ""), str(down or ""))

	def ShowSlotButton(self, slot):
		if self._holds(slot):
			self._buttons.add(int(slot))

	def HideAllSlotButton(self):
		self._buttons.clear()

	def plus(self):
		"""Whether each cell's slot button shows, in cell order."""
		return [number in self._buttons for number in self.slot_numbers]


# --- text fields -------------------------------------------------------------------------

class FieldProxy(nui_proxies._Shown):
	"""ui.EditLine: the text, the focus and the limits a NovaUI field shows
	(the document's element `field_id`). The legacy code sets SetText,
	SetFocus and KillFocus, and binds its events: SetReturnEvent,
	SetEscapeEvent, SetTabEvent, or the attributes OnIMEReturn,
	OnPressEscapeKey and OnKeyDown it assigns on the instance. The board's
	keydown handlers call fire_return(), fire_escape(), fire_tab() and
	fire_key(key), as the IME called the edit line, and typed(value) from
	the field's change. on_change(proxy, what) runs after each change the
	window shows: "text", "focus", "kill_focus", "max", "secret", "shown".
	`reader`, when the window sets it, answers the field's live text
	(nui.Window.get_value), which GetText prefers: a password's text never
	enters a model."""

	def __init__(self, field_id, on_change=None):
		self.field_id = str(field_id)
		self.on_change = on_change
		self.reader = None
		self.text = ""
		self.focused = False
		self.max = 0
		self.user_max = 0
		self.limit_width = 0
		self.size = (0, 0)
		self.secret = False
		self.number_mode = False
		self.multi_line = False
		self.eventReturn = _nothing
		self.eventEscape = _nothing
		self.eventTab = None

	def _changed(self, what):
		_call(self.on_change, self, what)

	# --- what legacy calls ---------------------------------------------------------

	def SetText(self, text):
		self.text = "" if text is None else str(text)
		self._changed("text")

	def GetText(self):
		reader = self.reader
		if reader is not None:
			value = reader()
			if isinstance(value, str):
				self.text = value
		return self.text

	def SetFocus(self):
		self.focused = True
		self._changed("focus")

	def KillFocus(self):
		self.focused = False
		self._changed("kill_focus")

	def IsFocus(self):
		return bool(self.focused)

	def SetMax(self, max):
		self.max = int(max)
		self.user_max = int(max)
		self._changed("max")

	def SetLimitWidth(self, width):
		self.limit_width = int(width)

	def SetSize(self, width, height):
		self.size = (int(width), int(height))

	def GetWidth(self):
		return self.size[0]

	def GetHeight(self):
		return self.size[1]

	def SetSecretMode(self, flag):
		self.secret = bool(flag)
		self._changed("secret")

	def SetSecret(self, flag=True):
		self.SetSecretMode(flag)

	def SetNumberMode(self):
		self.number_mode = True

	def SetMultiLine(self):
		self.multi_line = True

	def SetReturnEvent(self, event):
		self.eventReturn = event

	def SetEscapeEvent(self, event):
		self.eventEscape = event

	def SetTabEvent(self, event):
		self.eventTab = event

	def Show(self):
		nui_proxies._Shown.Show(self)
		self._changed("shown")

	def Hide(self):
		nui_proxies._Shown.Hide(self)
		self._changed("shown")

	# ui.EditLine's handlers; legacy may replace them on the instance.
	def OnIMEReturn(self):
		self.eventReturn()
		return True

	def OnPressEscapeKey(self):
		self.eventEscape()
		return True

	def OnIMETab(self):
		if self.eventTab:
			self.eventTab()
			return True
		return False

	def OnKeyDown(self, key):
		return True

	# --- what the board calls --------------------------------------------------------

	def typed(self, value):
		"""The field's change: its text now (no on_change: the field shows it)."""
		self.text = "" if value is None else str(value)

	def fire_return(self):
		return self.OnIMEReturn()

	def fire_escape(self):
		return self.OnPressEscapeKey()

	def fire_tab(self):
		return self.OnIMETab()

	def fire_key(self, key):
		return self.OnKeyDown(key)


# --- buttons and groups ------------------------------------------------------------------

class ToggleProxy(nui_proxies.ButtonProxy):
	"""ui.ToggleButton: ButtonProxy's state, and the toggle events. press()
	is CToggleButton::OnMouseLeftButtonDown: nothing while disabled; a down
	button goes up and runs the up event, an up one goes down and runs the
	down event."""

	def __init__(self, on_change=None):
		nui_proxies.ButtonProxy.__init__(self, on_change)
		self.eventUp = None
		self.eventDown = None

	def SetToggleUpEvent(self, event):
		self.eventUp = event

	def SetToggleDownEvent(self, event):
		self.eventDown = event

	def press(self):
		if not self.enabled:
			return
		if self.down:
			self.SetUp()
			_call(self.eventUp)
		else:
			self.Down()
			_call(self.eventDown)


class RadioGroupProxy(object):
	"""ui.RadioButtonGroup over ButtonProxys: legacy's body, rule for rule
	(ui.py:1135-1188). selectedBtnIdx starts at -1, so the first OnClick
	raises the group's last button (an index of -1). on_change(group) runs
	after Show, Hide, SetText and OnClick."""

	def __init__(self, buttons=(), on_change=None):
		self.buttonGroup = []
		self.selectedBtnIdx = -1
		self.shown = True
		self.on_change = on_change
		for button, select_event, unselect_event in buttons:
			self.AddButton(button, select_event, unselect_event)

	def _changed(self):
		_call(self.on_change, self)

	def Show(self):
		self.shown = True
		for button, _, _ in self.buttonGroup:
			button.Show()
		self._changed()

	def Hide(self):
		self.shown = False
		for button, _, _ in self.buttonGroup:
			button.Hide()
		self._changed()

	def SetText(self, idx, text):
		if idx >= len(self.buttonGroup):
			return
		button = self.buttonGroup[idx][0]
		button.SetText(text)
		self._changed()

	def OnClick(self, btnIdx):
		if btnIdx == self.selectedBtnIdx:
			return
		(button, selectEvent, unselectEvent) = self.buttonGroup[self.selectedBtnIdx]
		if unselectEvent:
			unselectEvent()
		button.SetUp()

		self.selectedBtnIdx = btnIdx
		(button, selectEvent, unselectEvent) = self.buttonGroup[btnIdx]
		if selectEvent:
			selectEvent()

		button.Down()
		self._changed()

	def AddButton(self, button, selectEvent, unselectEvent):
		i = len(self.buttonGroup)
		button.SetEvent(lambda: self.OnClick(i))
		self.buttonGroup.append([button, selectEvent, unselectEvent])
		button.SetUp()

	@staticmethod
	def Create(rawButtonGroup, on_change=None):
		radioGroup = RadioGroupProxy(on_change=on_change)
		for (button, selectEvent, unselectEvent) in rawButtonGroup:
			radioGroup.AddButton(button, selectEvent, unselectEvent)

		radioGroup.OnClick(0)

		return radioGroup

	# --- what the window reads ------------------------------------------------------------

	def buttons(self):
		return [entry[0] for entry in self.buttonGroup]

	def selected(self):
		return self.selectedBtnIdx

	def press(self, index):
		"""A press on button `index` as CRadioButton::OnMouseLeftButtonDown:
		a button that is down ignores it; otherwise it goes down and calls
		its event (the group's OnClick)."""
		if not (0 <= index < len(self.buttonGroup)):
			return
		button = self.buttonGroup[index][0]
		if not button.enabled or button.down:
			return
		button.Down()
		button.click()


class ScrollProxy(nui_proxies._Shown):
	"""ui.ScrollBar and ui.ThinScrollBar: the position (0 to 1), the middle
	bar's share and the shown state; moved(pos) is a drag of the middle bar:
	the position, then the scroll event."""

	SCROLLBAR_WIDTH = 17

	def __init__(self, on_change=None):
		self.pos = 0.0
		self.middle = 1.0
		self.height = 0
		self.event = _nothing
		self.on_change = on_change
		self.destroyed = False

	def _changed(self):
		_call(self.on_change, self)

	def SetScrollEvent(self, event):
		self.event = event

	def SetPos(self, pos):
		self.pos = max(0.0, min(1.0, float(pos)))
		self._changed()

	def GetPos(self):
		return self.pos

	def SetScrollBarSize(self, height):
		self.height = int(height)

	def SetMiddleBarSize(self, pageScale):
		self.middle = max(0.0, min(1.0, float(pageScale)))
		self._changed()

	def GetWidth(self):
		return self.SCROLLBAR_WIDTH

	def Show(self):
		nui_proxies._Shown.Show(self)
		self._changed()

	def Hide(self):
		nui_proxies._Shown.Hide(self)
		self._changed()

	def Destroy(self):
		self.destroyed = True
		self.event = _nothing

	def moved(self, pos):
		self.pos = max(0.0, min(1.0, float(pos)))
		self._changed()
		_call(self.event)


class ComboProxy(nui_proxies._Shown):
	"""ui.ComboBox (ui.py:2624-2781): its text, items and enabled state, and
	whether its list is open. pressed() is its OnMouseLeftButtonUp (opens or
	closes the list while enabled and it has items); picked(index) is its
	list's selection: the list closes and the event runs with the index (the
	item's key, OnSelectItem)."""

	def __init__(self, line=0, on_change=None):
		self.line = line
		self.on_change = on_change
		self.text = ""
		self.enabled = True
		self.open = False
		self.items = []         # (index, name) in insertion order
		self.selected = None
		self.event = lambda *arg: None
		self.destroyed = False

	def _changed(self):
		_call(self.on_change, self)

	def SetSize(self, width, height):
		pass

	def SetEvent(self, event):
		self.event = event

	def ClearItem(self):
		self.CloseListBox()
		self.items = []
		self._changed()

	def InsertItem(self, index, name):
		self.items.append((index, "" if name is None else str(name)))
		self._changed()

	def SetCurrentItem(self, text):
		self.text = "" if text is None else str(text)
		self._changed()

	def SelectItem(self, key):
		self.selected = key
		self._changed()

	def Enable(self):
		self.enabled = True
		self._changed()

	def Disable(self):
		self.enabled = False
		self.text = ""
		self.CloseListBox()
		self._changed()

	def CloseListBox(self):
		if self.open:
			self.open = False
			self._changed()

	def Destroy(self):
		self.destroyed = True
		self.event = lambda *arg: None

	def pressed(self):
		if not self.enabled:
			return
		if self.open:
			self.CloseListBox()
		elif self.items:
			self.open = True
			self._changed()

	def picked(self, index):
		self.CloseListBox()
		self.event(index)


class CheckProxy(nui_proxies._Shown):
	"""uiguild.CheckBox: checked and enabled; pressed() is its release (the
	event, while enabled)."""

	def __init__(self, event=None, on_change=None):
		self.event = event
		self.on_change = on_change
		self.checked = False
		self.enabled = True

	def SetCheck(self, flag):
		self.checked = bool(flag)
		_call(self.on_change, self)

	def Disable(self):
		self.enabled = False
		_call(self.on_change, self)

	def pressed(self):
		if self.enabled:
			_call(self.event)


class EditableSlotProxy(nui_proxies._Shown):
	"""uiguild.EditableTextSlot: its text and enabled state; pressed() is its
	release (event(arg), while enabled)."""

	def __init__(self, on_change=None):
		self.on_change = on_change
		self.text = ""
		self.enabled = True
		self.event = lambda *arg: None
		self.arg = 0

	def SetText(self, text):
		self.text = "" if text is None else str(text)
		_call(self.on_change, self)

	def SetEvent(self, event, arg):
		self.event = event
		self.arg = arg

	def Disable(self):
		self.enabled = False
		_call(self.on_change, self)

	def pressed(self):
		if self.enabled:
			self.event(self.arg)


class CommentProxy(nui_proxies._Shown):
	"""uiguild.CommentSlot: SetText keeps the whole text (`full`), the text
	legacy shows at rest (`short`: cut by grpText.GetSplitingTextLine to
	TEXT_LIMIT - 3 plus "..." when longer than TEXT_LIMIT) and whether it is
	longer (`long`: the whole text shows on hover)."""

	TEXT_LIMIT = 35

	def __init__(self, on_change=None):
		self.on_change = on_change
		self.full = ""
		self.short = ""
		self.long = False

	def SetText(self, text):
		text = "" if text is None else str(text)
		self.full = text
		self.long = len(text) > self.TEXT_LIMIT
		if self.long:
			import grpText
			self.short = grpText.GetSplitingTextLine(text, self.TEXT_LIMIT - 3, 0) + "..."
		else:
			self.short = text
		_call(self.on_change, self)


class GaugeProxy(nui_proxies._Shown):
	"""ui.AniImageBox used as a gauge: SetPercentage(value, maximum) keeps
	value / maximum (0 for a maximum of 0)."""

	def __init__(self, on_change=None):
		self.on_change = on_change
		self.percent = 0.0

	def SetPercentage(self, value, maximum):
		self.percent = float(value) / float(maximum) if maximum else 0.0
		_call(self.on_change, self)


class MarkProxy(nui_proxies._Shown):
	"""ui.MarkBox: the guild whose mark it shows (SetIndex), its scale. The
	window asks nui_guild_war.mark_source(guild_id) for the image source and
	its rectangle when it builds its model."""

	WIDTH = 16

	def __init__(self, on_change=None):
		self.on_change = on_change
		self.guild_id = 0
		self.scale = 1

	def SetIndex(self, guild_id):
		self.guild_id = int(guild_id)
		_call(self.on_change, self)

	def SetScale(self, scale):
		self.scale = scale
		_call(self.on_change, self)

	def AddFlag(self, flag):
		pass

	def GetWidth(self):
		return int(self.WIDTH * self.scale)

	def mark(self):
		"""(src, rect) of the mark, from nui_guild_war.mark_source, or ("", "")."""
		import nui_guild_war
		found = nui_guild_war.mark_source(self.guild_id)
		return found if found else ("", "")


class MessageWindowProxy(nui_proxies._Shown):
	"""A ui.ScriptWindow loaded from uiscript/popupdialog.py (P16 spec D13):
	the change-password mismatch message, the guild window's popup, the mark
	lists' popup. GetChild("message") and GetChild("accept") hand out what
	legacy binds; Show opens one uiCommon.PopupDialog (the dialog kit's
	facade while the dialogs flag is on; the same one each time) with the
	message and the accept event, Hide closes it. Open(msg) is
	uiUploadMark.PopupDialog's."""

	def __init__(self, text_key=None, make_dialog=None):
		self.shown = False
		self.text_key = text_key
		self._make_dialog = make_dialog
		self.dialog = None
		self.children = {"message": nui_proxies.TextProxy(), "accept": nui_proxies.ButtonProxy()}

	def GetChild(self, name):
		return self.children[name]

	def _new_dialog(self):
		if self._make_dialog is not None:
			return self._make_dialog()
		import uiCommon
		return uiCommon.PopupDialog()

	def Show(self):
		dialog = self.dialog
		if dialog is None:
			dialog = self.dialog = self._new_dialog()
		dialog.SetText(self.children["message"].GetText())
		dialog.SetAcceptEvent(self._accepted)
		dialog.Open()
		self.shown = True

	def _accepted(self):
		"""The popup closed by its own hand (its OK, Escape): legacy's accept
		button's event, once per show. uiCommon.PopupDialog.Close runs its
		accept event after it hides, also when Hide below closes it, and
		legacy's accept events hide this window (OnCloseMessageDialog), so the
		event runs only while the window counts as shown."""
		if not self.shown:
			return
		self.shown = False
		self.children["accept"].click()

	def Hide(self):
		"""Legacy's Hide of the raw window runs no event: the popup closes with
		the window already hidden, so its accept event does nothing."""
		shown, self.shown = self.shown, False
		dialog = self.dialog
		if dialog is not None and shown:
			dialog.Close()

	def SetTop(self):
		dialog = self.dialog
		if dialog is not None and hasattr(dialog, "SetTop"):
			dialog.SetTop()

	def SetCenterPosition(self, x=0, y=0):
		pass

	def ClearDictionary(self):
		pass

	def Open(self, msg):
		self.children["message"].SetText(msg)
		self.Show()

	def Destroy(self):
		dialog, self.dialog = self.dialog, None
		if dialog is not None:
			dialog.Close()
			destroy = getattr(dialog, "Destroy", None)
			if destroy is not None:
				destroy()


class PageWindowProxy(nui_proxies._Shown):
	"""GuildWindow.PageWindow: a page's shown state, its uiscript name and
	whatever the guild loader sets on it (the page's slots and lists, as
	attributes)."""

	def __init__(self, name, script="", on_change=None):
		self.shown = False
		self.name = str(name)
		self.script = str(script)
		self.on_change = on_change
		self.Children = []

	def Show(self):
		nui_proxies._Shown.Show(self)
		_call(self.on_change, self)

	def Hide(self):
		nui_proxies._Shown.Hide(self)
		_call(self.on_change, self)

	def UpdateRect(self):
		pass

	def GetScriptFileName(self):
		return self.script

	def ClearDictionary(self):
		self.Children = []


class ResizeProxy(nui_proxies._Shown):
	"""uimessenger's and uiwhisper's ResizeButton (a ui.DragButton): its place
	and height; dragged(x, y) is a drag of it: the place, then the move
	event (legacy's callback switch respected)."""

	def __init__(self, x=0, y=0, height=10, on_change=None):
		self.x = int(x)
		self.y = int(y)
		self.width = 10
		self.height = int(height)
		self.on_change = on_change
		self.event = None
		self.callback = True

	def AddFlag(self, flag):
		pass

	def SetSize(self, width, height):
		self.width = int(width)
		self.height = int(height)

	def SetWindowVerticalAlignBottom(self):
		pass

	def SetPosition(self, x, y):
		self.x = int(x)
		self.y = int(y)
		_call(self.on_change, self)

	def GetLocalPosition(self):
		return (self.x, self.y)

	def GetHeight(self):
		return self.height

	def SetMoveEvent(self, event):
		self.event = event

	def TurnOffCallBack(self):
		self.callback = False

	def TurnOnCallBack(self):
		self.callback = True

	def dragged(self, x, y):
		self.x = int(x)
		self.y = int(y)
		_call(self.on_change, self)
		if self.callback:
			_call(self.event)


class ListBoxExProxy(nui_proxies._Shown):
	"""ui.ListBoxEx of the mark lists: the entries legacy appends (data
	objects with GetText()) and the selected one."""

	def __init__(self, on_change=None):
		self.on_change = on_change
		self.entries = []
		self.selected = -1
		self.scroll_bar = None

	def _changed(self):
		_call(self.on_change, self)

	def SetScrollBar(self, scrollBar):
		self.scroll_bar = scrollBar

	def AppendItem(self, entry):
		self.entries.append(entry)
		self._changed()

	def RemoveAllItems(self):
		self.entries = []
		self.selected = -1
		self._changed()

	def IsEmpty(self):
		return not self.entries

	def GetSelectedItem(self):
		if 0 <= self.selected < len(self.entries):
			return self.entries[self.selected]
		return None

	def SelectIndex(self, index):
		if 0 <= index < len(self.entries):
			self.selected = int(index)
			self._changed()
