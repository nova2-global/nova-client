"""NovaUI tip board (nui/windows/tip-board/tip-board.rml).

While the "tip-board" window flag is on, Interface.__MakeTipBoard makes
TipBoard below through nui_windows.make() instead of uiTip.TipBoard: the
facade of the legacy board, which the C++ callback BINARY_SetTipMessage
(game.py) feeds with SetTip. The big notice board (nui_big_board.py) shares
the logic here with its own numbers.

The legacy board scrolled its text one pixel per frame (uitip.py OnUpdate);
this one shows one tip at a time and advances on a timer: a format="none"
nui-countdown whose countdownend calls advance(), with the end written once
per step (nui.now() plus the wait), so no Python runs between steps. The
timing is legacy's: a hidden board shows and its first tip comes in a
second after SetTip; each step brings in the next tip, SCROLL_WAIT_TIME
apart; the step after the last tip moves it out, and the next one wraps,
dropping the tips older than TIP_DURATION (the board hides when none are
left) before it starts again from the first. Each step slides the incoming
line in from below and the outgoing one up (two line elements, a and b,
which swap at each step)."""

import weakref

import app

import nui
import nui_hud

DOCUMENT = "nui/windows/tip-board/tip-board.rml"


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


class NoticeBoard(nui.Window):
	"""A notice board's document and model; advance() reports to its owner."""

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"shown": False, "line_a": "", "line_b": "", "front": "a", "next_at": 0.0}

	@nui.on("advance")
	def on_advance(self):
		self._owner.nui_advance()


class TipBoardBoard(NoticeBoard):
	DOCUMENT = DOCUMENT
	MODEL = "tip_board"


class NoticeFacade(object):
	"""What the tip and the big board share: the tip list and the steps."""

	NUI_FACADE = True
	KEY = None
	BOARD = None
	SCROLL_WAIT_TIME = 3.0
	TIP_DURATION = 5.0
	FIRST_WAIT = 1.0
	OUT_STEP = True         # a step that moves the last tip out before the wrap

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.board = None
		self.tipList = []
		self.pos = -1           # the tip shown, -1 before the first, len(tipList) after the last
		self.lines = {"a": "", "b": ""}
		self.front = "a"
		self.nextAt = 0.0
		self.shown = False
		if not nui_hud.has_engine():
			return
		try:
			self.board = self.BOARD(self)
		except Exception:
			self.nui_discard()
			raise

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget(self.KEY, self)

	def Destroy(self):
		self.tipList = []
		self.nui_discard()

	def Show(self):
		self.shown = True
		if self.board is not None:
			self.board.show()
		self._sync()

	def Hide(self):
		self.shown = False
		if self.board is not None:
			self.board.hide()
		self._sync()

	def IsShow(self):
		return self.shown and self.board is not None and self.board.is_visible()

	def SetTip(self, text):
		if not app.IsVisibleNotice():
			return
		self._append(app.GetTime(), text)
		self.nextAt = nui.now() + self.FIRST_WAIT
		if not self.IsShow():
			self.pos = -1
			self.lines = {"a": "", "b": ""}
			self.front = "a"
			self.Show()
		elif self.pos >= 0 and self.pos < len(self.tipList) and self.lines[self.front] == "":
			# The board was past its last tip: legacy draws the new one in
			# the line already in view, at once.
			self.lines[self.front] = self.tipList[self.pos][1]
		self._sync()

	def _append(self, made, text):
		self.tipList.append((made, text))

	def _keep_tip(self, made, now):
		"""TipBoard.__CleanOldTip: a tip stays while it is younger than
		TIP_DURATION."""
		return not (now - made > self.TIP_DURATION)

	def _slide_in(self, text):
		back = "b" if self.front == "a" else "a"
		self.lines[back] = text
		self.front = back

	def nui_advance(self):
		"""One step, SCROLL_WAIT_TIME after the last."""
		if not self.IsShow():
			return
		if not self.tipList:
			self.Hide()
			return
		self.nextAt = nui.now() + self.SCROLL_WAIT_TIME
		self.pos += 1
		if self.pos < len(self.tipList):
			self._slide_in(self.tipList[self.pos][1])
		elif self.pos == len(self.tipList) and self.OUT_STEP:
			self._slide_in("")
		else:
			self._wrap()
			if not self.IsShow():
				return
		self._sync()

	def _wrap(self):
		now = app.GetTime()
		self.tipList = [tip for tip in self.tipList if self._keep_tip(tip[0], now)]
		self.pos = -1
		if not self.tipList:
			self.lines = {"a": "", "b": ""}
			self.Hide()

	def _sync(self):
		if self.board is None:
			return
		self.board.set(shown=self.shown, line_a=nui.plain_text(self.lines["a"]), line_b=nui.plain_text(self.lines["b"]),
		               front=self.front, next_at=self.nextAt if self.shown else 0.0)


class TipBoard(NoticeFacade):
	"""uiTip.TipBoard on NovaUI (Interface.tipBoard)."""

	KEY = "tip-board"
	BOARD = TipBoardBoard
	SCROLL_WAIT_TIME = 3.0
	TIP_DURATION = 5.0
	STEP_HEIGHT = 17
