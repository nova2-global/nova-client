"""NovaUI dungeon manager (nui/windows/dungeon-timer/dungeon-timer.rml; NOVA-25).

While the dungeon-timer flag is on, Interface.__MakeDungeonWindows makes
TimerWindow below through nui_windows.make() instead of
uiTimerWindow.TimerWindow: a subclass of the legacy class (nui_facade.Facade)
whose loader puts proxies where the widgets were (the board, the entry ticket's
cell, the buttons, the texts of the chosen dungeon, the "Show Hidden" button,
the notice box, the empty line) and whose makers give a proxy for each
dungeon's row and description line, so the list and its order, hiding and
showing, the chosen dungeon's texts, the ticket's tooltip (legacy's over-in
handler, through nui_slots.LegacySlotEvents), the teleport, the ranking
buttons and the drops panel are legacy's code.

No Python runs per frame. A row's clock is a nui-countdown (M:SS) to the
dungeon's re-entry time, which legacy counts in rounded-up minutes every frame
(TimerBoard.UpdateTime): its end raises row_ready and the row turns ready.
The notice of a checked dungeon is nui_dungeon_notice's: legacy's per-frame
UpdateTime does nothing here."""

import app
import ui
import uiTimerWindow

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots
import nui_dungeon_notice

DOCUMENT = "nui/windows/dungeon-timer/dungeon-timer.rml"
KEY = "dungeon-timer"
TONES = dict((color, name) for name, color in (
	("heading", uiTimerWindow.DESC_COLORS["#"]), ("note", uiTimerWindow.DESC_COLORS["$"]),
	("hint", uiTimerWindow.DESC_COLORS["%"])))
BUTTONS = {"teleport": "teleport", "drops": "btnDungeonDrops", "time": "btnTimeRank", "overall": "btnOverAllRank",
           "damage": "btnDamageRank", "show_hidden": "showHiddenBtn"}


class _TimerBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The manager's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "dungeon_timer"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()

	@nui.on("row_press")
	def on_row_press(self, idx, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_row(int(idx))

	@nui.on("hide_press")
	def on_hide_press(self, idx, button):
		self.raise_for(button)
		if button == 0:
			self._owner.HideDungeon(int(idx))

	@nui.on("row_ready")
	def on_row_ready(self, idx):
		self._owner.publish_rows()

	@nui.on("button_press")
	def on_button_press(self, name, button):
		self.raise_for(button)
		if button == 0 and name in BUTTONS:
			getattr(self._owner, BUTTONS[name]).click()

	@nui.on("notice_press")
	def on_notice_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.noticeBtn.OnMouseLeftButtonUp()

	@nui.on("ticket_press")
	def on_ticket_press(self, button):
		self._owner.ticket_events.press(0, int(button))

	@nui.on("ticket_over")
	def on_ticket_over(self):
		self._owner.ticket_events.over(0)

	@nui.on("ticket_out")
	def on_ticket_out(self):
		self._owner.ticket_events.out(0)


class _RowProxy(nui_proxies._Shown):
	"""uitimerwindow.TimerBoard: a dungeon's row; the board draws it from the
	window's state (title, clock), so it only records its place."""

	def __init__(self, owner, index):
		self.owner = owner
		self.index = index
		self.position = (0, 0)

	def SetPosition(self, x, y):
		self.position = (int(x), int(y))

	def UpdateTime(self, now):
		pass

	def OnMouseLeftButtonDown(self):
		self.owner.SetDescription(self.index)

	def Destroy(self):
		self.owner = None


class _DescProxy(nui_proxies.TextProxy):
	"""A description line (ui.TextLine): its text and its tone (OLD's color by
	the line's first character)."""

	def __init__(self):
		nui_proxies.TextProxy.__init__(self)
		self.font = None

	def SetFontName(self, font):
		self.font = font


class _NameProxy(nui_proxies.TextProxy):
	def SetFontName(self, font):
		pass


class _CheckBoxProxy(nui_proxies._Shown):
	"""ui.CheckBox: SetCheckStatus, GetCheckStatus, SetEvent(func, kind) and a
	left release that flips it and calls its ON_CHECK or ON_UNCHECK event."""

	def __init__(self, on_change):
		self.checked = False
		self.text = ""
		self.events = {"ON_CHECK": None, "ON_UNCHECK": None}
		self.on_change = on_change

	def SetTextInfo(self, text):
		self.text = str(text)

	def SetCheckStatus(self, flag):
		self.checked = bool(flag)
		self.on_change(self.checked)

	def GetCheckStatus(self):
		return self.checked

	def SetEvent(self, func, kind):
		if kind in self.events:
			self.events[kind] = func

	def OnMouseLeftButtonUp(self):
		self.SetCheckStatus(not self.checked)
		event = self.events["ON_CHECK" if self.checked else "ON_UNCHECK"]
		if event:
			event()
		return True


class _ScrollProxy(nui_proxies._Shown):
	"""ui.ScrollWindow: the document scrolls by itself."""

	def SetContentWindow(self, window):
		pass

	def FitWidth(self, width):
		pass

	def OnContentWindowSizeChange(self):
		pass

	def ScrollToStart(self):
		pass

	def OnRunMouseWheel(self, length):
		return False


class _AreaProxy(nui_proxies.WindowProxy):
	def IsIn(self):
		return False


class TimerWindow(nui_facade.Facade, uiTimerWindow.TimerWindow):
	"""uiTimerWindow.TimerWindow on NovaUI (Interface.wndTimer)."""

	KEY = KEY
	BOARD = _TimerBoard
	PLACE = "center"
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiTimerWindow.TimerWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise
		self.nui_notices = nui_dungeon_notice.Notices(self._announce)

	def nui_model(self):
		return {
			"rows": [],
			"selected": -1,
			"show_hidden": False,
			"empty": "",
			"name": "",
			"boss": "",
			"ticket_label": "",
			"level": "",
			"group": "",
			"cooldown": "",
			"ticket": nui_slots.empty_cell(0),
			# P15 F-2 (nui_slots.ATTACH_RIGHT; the ticket cell's nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			"desc": [],
			"notice": False,
			"notice_label": "",
		}

	# --- the loader (uitimerwindow.py __LoadWindow, on proxies) ------------------------

	def _TimerWindow__LoadWindow(self):
		# The uiscript's style (timerwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		text = lambda key: nui_proxies.TextProxy(lambda value, key=key: self.nui_set(**{key: nui.plain_text(value)}))
		self.board = nui_proxies.BoardProxy(618, 472)
		self.itemSlot = nui_slots.SlotWindowProxy([0], self._on_ticket)
		self.teleport = nui_proxies.ButtonProxy()
		self.btnDungeonDrops = nui_proxies.ButtonProxy()
		self.btnTimeRank = nui_proxies.ButtonProxy()
		self.btnOverAllRank = nui_proxies.ButtonProxy()
		self.btnDamageRank = nui_proxies.ButtonProxy()
		self.info_bg = _AreaProxy()
		self.BossName = text("boss")
		self.text1 = text("level")
		self.text2 = text("group")
		self.text3 = text("cooldown")
		self.text4 = text("ticket_label")
		self.dungeonsWindow = nui_proxies.WindowProxy()
		self.showHiddenBtn = nui_proxies.ButtonProxy(lambda button: self.nui_set(show_hidden=button.IsShow()))
		self.boardScrollableWindow = _ScrollProxy()
		self.descWindow = nui_proxies.WindowProxy()
		self.descScrollableWindow = _ScrollProxy()
		self.textLine = _NameProxy(lambda value: self.nui_set(name=nui.plain_text(value)))
		self.emptyLabel = nui_proxies.TextProxy(lambda value: self._publish_empty())
		self.emptyLabel.on_show = lambda shown: self._publish_empty()
		self.emptyLabel.shown = False
		self.noticeBtn = _CheckBoxProxy(lambda checked: self.nui_set(notice=bool(checked)))
		self.ticket_events = self.nui_events(nui_slots.LegacySlotEvents(self.itemSlot))

	def _TimerWindow__MakeBoard(self, idx):
		return _RowProxy(self, idx)

	def _TimerWindow__MakeDescLine(self):
		return _DescProxy()

	# --- what NovaUI changes -----------------------------------------------------------

	def press_row(self, idx):
		for row in self.boards:
			if row.index == idx:
				row.OnMouseLeftButtonDown()
				return

	def RebuildBoards(self):
		uiTimerWindow.TimerWindow.RebuildBoards(self)
		self.publish_rows()

	def SetDescription(self, index):
		uiTimerWindow.TimerWindow.SetDescription(self, index)
		if index in uiTimerWindow.DESCRIPTION:
			self.nui_set(selected=int(index), desc=[self._desc(line) for line in self.descLines])

	def SetTimeLeft(self, index, time_):
		uiTimerWindow.TimerWindow.SetTimeLeft(self, index, time_)
		self.publish_rows()
		self._watch_notices()

	def QuestTimeReady(self):
		uiTimerWindow.TimerWindow.QuestTimeReady(self)
		self.publish_rows()
		self._watch_notices()

	def ToogleNotice(self, arg):
		uiTimerWindow.TimerWindow.ToogleNotice(self, arg)
		self._watch_notices()

	def UpdateTime(self):
		"""Nothing per frame: the board's countdowns count, and the notices are
		nui_dungeon_notice's timers."""

	def Destroy(self):
		if getattr(self, "nui_notices", None) is not None:
			self.nui_notices.discard()
		self.nui_discard()
		uiTimerWindow.TimerWindow.Destroy(self)

	# --- the board's model -------------------------------------------------------------

	def _left(self, idx):
		"""Seconds left on a dungeon's clock (0 before QuestTimeReady, as legacy)."""
		if not uiTimerWindow.TIMER_STATE["loaded"]:
			return 0
		return max(0, self.GetEndTime(idx) - app.GetGlobalTimeStamp())

	def publish_rows(self):
		if self.__dict__.get("_state") is None:
			return
		now = nui.now()
		rows = []
		for row in self.boards:
			left = self._left(row.index)
			rows.append({"idx": int(row.index), "title": nui.plain_text(uiTimerWindow.get_title(row.index)),
			             "end": now + left if left > 0 else 0.0, "event": uiTimerWindow.is_event_index(row.index)})
		self.nui_set(rows=rows)

	def _publish_empty(self):
		if self.__dict__.get("_state") is None:
			return
		label = self.emptyLabel
		self.nui_set(empty=nui.plain_text(label.text) if label.IsShow() else "")

	def _on_ticket(self, cells):
		self.nui_set(ticket=cells[0])

	@staticmethod
	def _desc(line):
		return {"text": nui.plain_text(line.text), "tone": TONES.get(line.color, "")}

	def _watch_notices(self):
		"""The clocks of the checked dungeons still running and not announced."""
		notices = getattr(self, "nui_notices", None)
		if notices is None:
			return
		clocks = {}
		for idx in self.endTimes:
			left = self._left(idx)
			if left > 0 and uiTimerWindow.ALLOW_NOTICE.get(idx, 0) and not self.announced.get(idx, False):
				clocks[idx] = left
		notices.watch(clocks)

	def _announce(self, idx):
		"""A watched clock ended: legacy's announce (once per clock), and the
		box's title while the dungeon's notice is still checked."""
		if self.announced.get(idx, True):
			return None
		self.announced[idx] = True
		if not uiTimerWindow.ALLOW_NOTICE.get(idx, 0):
			return None
		return uiTimerWindow.get_title(idx)
