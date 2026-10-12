"""NovaUI quest dialog (nui/windows/quest/quest.rml) and the quest curtain.

While the "quest" window flag is on, Interface.OpenQuestWindow makes
QuestDialog below through nui_windows.make() instead of uiQuest.QuestDialog,
one per script packet: the facade of the legacy dialog, with its name,
constructor, methods, class constants and the attributes callers touch. The
C++ quest interpreter (CPythonEventManager) stays the only parser, timer and
caller of the dialog's callbacks; its sink publishes the text and the page
of each event set as two feeds, quest.<index>.lines (read by the element
nui-quest-text) and quest.<index>.page (the board's "page" key), and
nuigame.QuestAttach has C++ drive the set once per frame (P12 spec 3). So no
Python runs while a dialog types: the facade acts on the interpreter's
callbacks, its document's events and the player's keys.

A dialog with a skin is a modal board (MODAL, body.nui-scrim) above every
NovaUI HUD window: it takes every key and click, as legacy's lock window
did. Its keys follow legacy's rules exactly (OnKeyDown, OnPressEscapeKey,
OnIMEReturn): no click skips the typing and none continues outside the
buttons. A skin-0 dialog has no board, only its place in the legacy Escape
chain. A skinned dialog made while another NovaUI quest board exists routes
every call to a legacy uiQuest.QuestDialog made in its place (RmlUi allows
one model per name).

The curtain: QuestCurtain below is uiQuest.QuestDialog.QuestCurtain while
the flag is on, the one object every dialog writes (CurtainMode, BarHeight,
Close, the class list uiQuest.QuestCurtain.OnDoneEventList), so a legacy
dialog made in a fallback uses it too. It draws the letterbox bars and the
black and white fades of quest scripts in one on-demand document
(nui_quest_curtain.QuestCurtainBoard), ended by a timer on the NovaUI
clock. The Interface's HUD hiding (__HideWindows, __ShowWindows) works
unchanged through the HUD facades and the curtain's done events.

The quest text and choices are data from the server: the text reaches the
document only through nui-quest-text, the choices through nui-text, so
neither is ever translated or parsed as markup."""

import functools
import sys
import weakref

import app
import event
import net
import snd
import wndMgr

import nui
import nui_hud
import uiQuest

DOCUMENT = "nui/windows/quest/quest.rml"

# RmlUi's key identifiers for the arrows (Include/RmlUi/Core/Input.h).
KEY_UP = 91
KEY_DOWN = 93

QUEST_BUTTON_MAX_NUM = 8
SELECT_NEXT = 254          # the answer the Next button and Escape send (uiquest.py:469-473)

# The curtain's slide (legacy moves the bars 200 px a second) and fades.
SLIDE_TIME = 0.4
DEFAULT_FADE_SPEED = 0.035  # uiquest.py EventCurtain.DEFAULT_FADE_SPEED
# Legacy steps a fade by `speed` a frame (1 / speed frames); at 60 frames a
# second that is t = 1 / (speed * 60) seconds. Each class: (t up to, name,
# the seconds it is drawn in).
FADE_CLASSES = ((0.35, "fast", 0.25), (0.75, "normal", 0.5), (1.5, "slow", 1.0), (None, "slower", 2.0))
FADE_KINDS = {"fade_out": ("black", "out"), "fade_in": ("black", "in"),
              "white_out": ("white", "out"), "white_in": ("white", "in")}
_EPSILON = 0.002


def empty_page(skin=0):
	"""quest.<index>.page before the interpreter made anything (P12 spec 3.2)."""
	return {"skin": int(skin), "choices": [], "pages": 0, "button": "", "input": False,
	        "images": {"left": "", "top": "", "background": "", "title": "", "title_serial": 0},
	        "free_images": [], "size": {"width": 0, "height": 0},
	        "fade": {"kind": "", "speed": 0.0, "serial": 0}, "delay": 10,
	        "waiting": False, "locked": False, "ended": False, "done": False}


def fade_class(speed):
	"""(class name, seconds) of a fade at legacy's per-frame `speed` (0 and
	less: legacy's default, uiquest.py:164-166)."""
	if not speed or speed <= 0:
		speed = DEFAULT_FADE_SPEED
	seconds = 1.0 / (float(speed) * 60.0)
	for limit, name, duration in FADE_CLASSES:
		if limit is None or seconds <= limit:
			return name, duration
	return FADE_CLASSES[-1][1], FADE_CLASSES[-1][2]


def _nuigame():
	return sys.modules.get("nuigame")


# --- the curtain ------------------------------------------------------------------------

class QuestCurtain(object):
	"""uiQuest.QuestCurtain and the fades of uiQuest.EventCurtain on NovaUI.

	CurtainMode keeps legacy's meaning: 1 slides the bars in, -1 slides them
	out and then runs Close() (the done events), 0 holds (a slide under way
	finishes). BarHeight is legacy's class attribute, which every dialog
	sets; at 0 (a 16:9 screen) the bars change state at once and no board is
	made for them. fade() is the dialogs' FadeOut and the rest; its end calls
	event.EndEventProcess for the dialog's set, as legacy's EventCurtain does.
	The board exists only while bars or a fade show."""

	CURTAIN_TIME = 0.25
	CURTAIN_SPEED = 200

	def __init__(self):
		self._mode = 0
		self._bars = "out"        # "out", "sliding_in", "in" or "sliding_out"
		self._slide_at = 0.0
		self._slide_end = 0.0
		self._fade = None         # the fade shown: {"color", "dir", "class", "index", "end", "running"}
		self._board = None
		self._shown = False
		self._held = 0            # hold() depth: board updates wait while it is above 0
		self._dirty = False

	# Legacy's class attributes, which every dialog writes on uiQuest.QuestCurtain.
	@property
	def BarHeight(self):
		return uiQuest.QuestCurtain.BarHeight

	@BarHeight.setter
	def BarHeight(self, value):
		uiQuest.QuestCurtain.BarHeight = value
		self._sync_board()

	@property
	def OnDoneEventList(self):
		return uiQuest.QuestCurtain.OnDoneEventList

	@OnDoneEventList.setter
	def OnDoneEventList(self, value):
		uiQuest.QuestCurtain.OnDoneEventList = value

	@property
	def CurtainMode(self):
		return self._mode

	@CurtainMode.setter
	def CurtainMode(self, mode):
		self._set_mode(mode)

	def Show(self):
		self._shown = True

	def Hide(self):
		self._shown = False

	def IsShow(self):
		return self._shown

	def Close(self):
		"""As legacy (uiquest.py:81-87): the bars out at once, every done event
		run with the curtain as its argument, the class list emptied."""
		self._mode = 0
		self._bars = "out"
		for done in uiQuest.QuestCurtain.OnDoneEventList:
			done(*(self,))
		uiQuest.QuestCurtain.OnDoneEventList = []
		self._arm()
		self._sync_board()

	# --- the bars --------------------------------------------------------------------

	def bars(self):
		"""The bars' state: "out", "sliding_in", "in" or "sliding_out"."""
		return self._bars

	def _bar_height(self):
		try:
			return max(0, int(uiQuest.QuestCurtain.BarHeight))
		except (TypeError, ValueError):
			return 0

	def _bar_dp(self):
		scale = nui.get_scale() or 1.0
		return "%.2f" % (self._bar_height() / float(scale))

	def _set_mode(self, mode):
		self._mode = mode
		now = nui.now()
		if mode > 0:
			if self._bars == "in":
				self._mode = 0
			elif self._bars != "sliding_in":
				self._slide("sliding_in", now)
		elif mode < 0:
			if self._bars == "out" or (self._bars == "sliding_in" and abs(self._slide_at - now) <= _EPSILON):
				# Out already, or a slide that began this instant (a skin-0 dialog
				# sets 1, then -1): legacy closes at its next update.
				self._bars = "out"
				self.Close()
			elif self._bars != "sliding_out":
				self._slide("sliding_out", now)

	def _slide(self, state, now):
		self._bars = state
		self._slide_at = now
		self._slide_end = now + SLIDE_TIME
		if self._bar_height() <= 0 or nui.is_reduced_motion():
			self._finish_slide()
			return
		self._arm()
		self._sync_board()

	def _finish_slide(self):
		if self._bars == "sliding_in":
			self._bars = "in"
			self._mode = 0
			self._arm()
			self._sync_board()
		elif self._bars == "sliding_out":
			self._bars = "out"
			self.Close()

	# --- the fades -------------------------------------------------------------------

	def fade(self, kind, speed, index):
		"""A fade of a quest script (kind "fade_out", "fade_in", "white_out" or
		"white_in") for the event set `index`. A fade that replaces another
		dialog's running one still ends that one's wait
		(event.EndEventProcess): legacy gives each dialog a fade of its own.
		Within one set the new fade replaces the old, as legacy's does."""
		color, direction = FADE_KINDS[kind]
		name, duration = fade_class(speed)
		previous = self._fade
		self._fade = {"color": color, "dir": direction, "class": name, "index": index,
		              "end": nui.now() + duration, "running": True}
		if previous is not None and previous["running"] and previous["index"] != index:
			event.EndEventProcess(previous["index"])
		if nui.is_reduced_motion():
			self._finish_fade()
			return
		self._arm()
		self._sync_board()

	def fading(self):
		"""The fade shown, a copy, or None."""
		return dict(self._fade) if self._fade is not None else None

	def _finish_fade(self):
		fade = self._fade
		if fade is None:
			return
		fade["running"] = False
		if fade["dir"] == "in":
			self._fade = None
		self._arm()
		self._sync_board()
		event.EndEventProcess(fade["index"])

	def end_fades_of(self, index):
		"""A dialog closed: its fade layer goes with it, as legacy's EventCurtain
		goes with its dialog."""
		if self._fade is not None and self._fade["index"] == index:
			self._fade = None
			self._arm()
			self._sync_board()

	# --- the board and its timer -----------------------------------------------------

	def board(self):
		return self._board

	def hold(self):
		"""Board updates wait until the matching release(): a dialog writes its
		modes in a row (a skin-0 dialog sets 1, then -1), and only the state
		at the end needs a document."""
		self._held += 1

	def release(self):
		self._held = max(0, self._held - 1)
		if not self._held and self._dirty:
			self._dirty = False
			self._arm()
			self._sync_board()

	def _deadline(self):
		ends = []
		if self._bars in ("sliding_in", "sliding_out"):
			ends.append(self._slide_end)
		if self._fade is not None and self._fade["running"]:
			ends.append(self._fade["end"])
		return min(ends) if ends else None

	def _arm(self):
		if self._held:
			self._dirty = True
			return
		board = self._board
		if board is None:
			return
		end = self._deadline()
		board.set(timer_on=end is not None, timer_end_at=float(end) if end is not None else 0.0)

	def _sync_board(self):
		"""Makes, updates or drops the board for what shows now."""
		if self._held:
			self._dirty = True
			return
		bars = self._bar_height() > 0 and self._bars != "out"
		fade = self._fade
		if not bars and fade is None:
			self._drop_board()
			return
		board = self._board
		if board is None:
			import nui_quest_curtain
			board = nui_quest_curtain.QuestCurtainBoard(self)
			if not board._doc:
				board.destroy()
				return
			self._board = board
			board.show()
		end = self._deadline()
		board.set(bars="in" if self._bars in ("in", "sliding_in") else "out", bar_dp=self._bar_dp(),
		          fade=fade["color"] if fade is not None else "",
		          fade_dir=fade["dir"] if fade is not None else "out",
		          fade_class=fade["class"] if fade is not None else "normal",
		          timer_on=end is not None, timer_end_at=float(end) if end is not None else 0.0)
		if fade is not None:
			board.bring_to_front()
		else:
			_front_quest_boards()

	def _drop_board(self):
		board, self._board = self._board, None
		if board is not None:
			board.destroy()

	def nui_timer_end(self):
		now = nui.now()
		if self._bars in ("sliding_in", "sliding_out") and now + _EPSILON >= self._slide_end:
			self._finish_slide()
		if self._fade is not None and self._fade["running"] and now + _EPSILON >= self._fade["end"]:
			self._finish_fade()
		self._arm()

	def nui_scale_changed(self):
		self._sync_board()

	def end_phase(self):
		"""The phase ended: every state back to rest, the board gone. 1 when a
		board went, else 0."""
		had = 1 if self._board is not None else 0
		self._mode = 0
		self._bars = "out"
		self._fade = None
		self._held = 0
		self._dirty = False
		self._drop_board()
		return had


_curtain = [None]


def curtain():
	"""The NovaUI curtain, made once."""
	if _curtain[0] is None:
		_curtain[0] = QuestCurtain()
	return _curtain[0]


def install_curtain():
	"""Makes the NovaUI curtain uiQuest.QuestDialog.QuestCurtain unless a curtain
	is there already (a NovaUI one, or a legacy one a fallback dialog made
	first), and returns the one installed."""
	if "QuestCurtain" not in uiQuest.QuestDialog.__dict__:
		uiQuest.QuestDialog.QuestCurtain = curtain()
	return uiQuest.QuestDialog.QuestCurtain


# --- the dialogs ----------------------------------------------------------------------------

_live = []   # weak references to the NovaUI dialogs alive, oldest first


def _dialogs():
	alive = [ref() for ref in _live]
	_live[:] = [weakref.ref(dialog) for dialog in alive if dialog is not None]
	return [dialog for dialog in alive if dialog is not None]


def _board_busy():
	"""True while a NovaUI quest board exists (one model per name)."""
	return any(dialog._board() is not None for dialog in _dialogs())


def _front_quest_boards():
	for dialog in _dialogs():
		board = dialog._board()
		if board is not None:
			board.bring_to_front()


def end_phase():
	"""nui_windows.end_phase(): the curtain's board and any quest board left go
	(none should: the Interface closes every dialog). Returns their count."""
	count = 0
	for dialog in _dialogs():
		if dialog._board() is not None:
			count += 1
		dialog.nui_discard()
	if _curtain[0] is not None:
		count += _curtain[0].end_phase()
	return count


class QuestBoard(nui.Window):
	"""A skinned dialog's document; its events and keys go to its facade. The
	page key follows the set's page feed, bound per instance."""

	DOCUMENT = DOCUMENT
	MODEL = "quest"
	MODAL = True

	def __init__(self, owner, index, skin):
		self._owner = nui_hud.keep_weakly(owner)
		self._index = int(index)
		self._skin = int(skin)
		self.FEEDS = {"page": "quest.%d.page" % self._index}
		nui.Window.__init__(self)

	def initial_model(self):
		return {"set_index": self._index, "skin": self._skin, "page": empty_page(self._skin),
		        "choice_page": 0, "focus_index": -1, "next_hover": False, "title_on": False}

	def nui_key(self, event_args):
		return self._call("nui_key", event_args)

	def nui_field_key(self, event_args):
		return self._call("nui_field_key", event_args)

	def _call(self, name, *args):
		try:
			return getattr(self._owner, name)(*args)
		except ReferenceError:
			return None

	@nui.on("choose")
	def on_choose(self, index, button):
		if button == 0:
			self._call("nui_choose", index)

	@nui.on("pager")
	def on_pager(self, step, button):
		if button == 0:
			self._call("nui_pager", step)

	@nui.on("next")
	def on_next(self, button):
		if button == 0:
			self._call("nui_next")

	@nui.on("next_out")
	def on_next_out(self):
		self._call("nui_next_out")

	@nui.on("field")
	def on_field(self, value, linebreak):
		self._call("nui_field", value, linebreak)

	@nui.on("title_end")
	def on_title_end(self):
		self._call("nui_title_end")


def _routed(method):
	"""A facade method that a busy fallback (QuestDialog._legacy) answers."""
	@functools.wraps(method)
	def call(self, *args, **kwargs):
		legacy = self.__dict__.get("_legacy")
		if legacy is not None:
			return getattr(legacy, method.__name__)(*args, **kwargs)
		return method(self, *args, **kwargs)
	return call


def _nothing():
	"""The exit key's action while a board shows: none, as under legacy's lock."""
	return None


class QuestDialog(nui_hud.LayoutCalls):
	"""uiQuest.QuestDialog on NovaUI (Interface.wndQuestWindow[key])."""

	NUI_FACADE = True

	TITLE_STATE_NONE = 0
	TITLE_STATE_APPEAR = 1
	TITLE_STATE_SHOW = 2
	TITLE_STATE_DISAPPEAR = 3

	SKIN_NONE = 0
	SKIN_CINEMA = 5

	QUEST_BUTTON_MAX_NUM = QUEST_BUTTON_MAX_NUM

	def __init__(self, skin, idx):
		self._legacy = None
		self._index = idx
		self._key = "quest-%d" % idx
		nui_hud.take_over(self._key, self)
		self._nui_discarded = False
		self._ready = False
		self._attached = False
		self._shown = False
		self._has_field = False
		self._field_text = ""
		self._choice_page = 0
		self._focus_index = -1
		self._next_hover = False
		self._title_on = False
		self._window_name = ""
		self.demand = None
		self.escapeProxy = None
		if not nui_hud.has_engine_5a():
			return
		if skin and _board_busy():
			# One board at a time: this dialog is legacy's, made in its place.
			self._legacy = uiQuest.QuestDialog(skin, idx)
			self._ready = True
			return

		# Legacy's attributes, with legacy's names and meanings.
		self.skin = skin
		self.descIndex = idx
		self.focusIndex = 0
		self.sx = 0
		self.sy = 0
		self.nextCurtainMode = 0
		self.nextButtonType = None
		self.needInputString = False
		self.bCancelled = False
		self.OnCloseEvent = None
		self.btnAnswer = None      # the answer count once a question was made
		self.btnNext = None        # True once a Next button was made

		if not _nuigame().QuestAttach(idx, skin):
			return
		self._attached = True
		_live.append(weakref.ref(self))

		event.SetRestrictedCount(idx, 36 if skin == 3 else 60)
		height = (wndMgr.GetScreenHeight() - wndMgr.GetScreenWidth() * 9 // 16) // 2
		uiQuest.QuestCurtain.BarHeight = height if height >= 0 else 50
		curtain_now = install_curtain()
		held = getattr(curtain_now, "hold", None) is not None
		if held:
			curtain_now.hold()
		try:
			curtain_now.CurtainMode = 1
			self.nextCurtainMode = 0
			if self.skin:
				curtain_now.CurtainMode = 1
				self.nextCurtainMode = 0
			else:
				curtain_now.CurtainMode = -1
				self.nextCurtainMode = -1
		finally:
			if held:
				curtain_now.release()
		event.SetEventHandler(idx, self)

		if skin:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board)
			self.escapeProxy = nui_hud.EscapeProxy(self.OnPressEscapeKey, layer="TOP_MOST", exit_action=_nothing)
			if not self.demand.show():
				return
			self._shown = True
			self._board().bring_to_front()
			self.escapeProxy.show()
		else:
			# A shown skin-0 dialog sits in the UI layer's Escape chain.
			self.escapeProxy = nui_hud.EscapeProxy(self.OnPressEscapeKey, layer="UI")
			self.escapeProxy.show()
		self._ready = True

	def __getattr__(self, name):
		legacy = self.__dict__.get("_legacy")
		if legacy is None or name.startswith("__"):
			raise AttributeError(name)
		return getattr(legacy, name)

	def __setattr__(self, name, value):
		legacy = self.__dict__.get("_legacy")
		if legacy is not None and not name.startswith("_"):
			setattr(legacy, name, value)
		else:
			object.__setattr__(self, name, value)

	# --- make()'s protocol --------------------------------------------------------------

	def nui_ready(self):
		if self._legacy is not None:
			return True
		return self._ready and nui_hud.has_engine_5a()

	def nui_discard(self):
		"""The sink detached and the NovaUI parts destroyed; the event set stays
		(the legacy dialog made in this one's place takes it)."""
		self._nui_discarded = True
		self._detach()
		self._teardown()

	def _detach(self):
		if self._attached:
			self._attached = False
			nuigame = _nuigame()
			if nuigame is not None:
				nuigame.QuestDetach(self._index)

	def _teardown(self):
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		if _curtain[0] is not None:
			_curtain[0].end_fades_of(self._index)
		_live[:] = [ref for ref in _live if ref() is not None and ref() is not self]
		nui_hud.forget(self._key, self)

	def _board(self):
		return self.demand.board() if self.demand is not None else None

	def _make_board(self):
		return QuestBoard(self, self._index, self.skin)

	def _restore_board(self, board):
		board.set(choice_page=self._choice_page, focus_index=self._focus_index,
		          next_hover=self._next_hover, title_on=self._title_on)
		board.element_on("", "keydown", board.nui_key)
		board.element_on("quest-input", "keydown", board.nui_field_key)

	def _set(self, **values):
		board = self._board()
		if board is not None:
			board.set(**values)

	# --- the ui.ScriptWindow calls the Interface makes ---------------------------------

	@_routed
	def Show(self):
		self._shown = True
		if self.skin:
			if self.demand is not None and self.demand.show():
				self._board().bring_to_front()
				if self.escapeProxy is not None:
					self.escapeProxy.show()
		elif self.escapeProxy is not None:
			self.escapeProxy.show()

	@_routed
	def Hide(self):
		self._shown = False
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	@_routed
	def IsShow(self):
		if self.skin:
			return self.demand is not None and self.demand.is_shown()
		return self._shown

	@_routed
	def SetTop(self):
		board = self._board()
		if board is not None:
			board.bring_to_front()

	@_routed
	def SetWindowName(self, name):
		self._window_name = name

	@_routed
	def SetCenterPosition(self, x=0, y=0):
		pass

	@_routed
	def Lock(self):
		"""A modal replaces legacy's lock window."""
		pass

	@_routed
	def Unlock(self):
		pass

	@_routed
	def GetWidth(self):
		return nui_hud.LayoutCalls.GetWidth(self)

	@_routed
	def GetHeight(self):
		return nui_hud.LayoutCalls.GetHeight(self)

	# --- legacy's methods ----------------------------------------------------------------

	@_routed
	def LoadDialog(self, skin):
		"""The board is made with the facade; nothing is left to load."""
		pass

	@_routed
	def OnCancel(self):
		self.bCancelled = True
		self.nextCurtainMode = -1
		self.CloseSelf()

	@_routed
	def CloseSelf(self):
		"""As legacy (uiquest.py:342-356): the cancel packet, the curtain's next
		mode, Destroy() (the close events and the input string), the event set
		cleared. Legacy clears only a set whose index is not 0; the sink is
		detached in any case, so C++ stops driving it."""
		if self.bCancelled:
			net.SendQuestCancelPacket()
			self.bCancelled = False

		uiQuest.QuestDialog.QuestCurtain.CurtainMode = self.nextCurtainMode
		self.btnNext = None
		self.btnAnswer = None
		self.Destroy()
		if self.descIndex:
			event.ClearEventSet(self.descIndex)  # detaches the sink as well
			self.descIndex = None
			self._attached = False
		self._detach()
		self.focusIndex = 0

	@_routed
	def Destroy(self):
		"""The close events (the Interface's RemoveQuestDialog and Unlock), then
		with an input the field's text as legacy sends it, read before the
		board goes; then the board and the proxy."""
		if self.OnCloseEvent:
			self.OnCloseEvent()
			self.OnCloseEvent = None
			if self.needInputString and self._has_field:
				net.SendQuestInputStringPacket(self._input_text())
		self._teardown()

	def _input_text(self):
		board = self._board()
		if board is not None:
			value = board.get_value("quest-input")
			if value is not None:
				return value
		return self._field_text

	@_routed
	def AddOnCloseEvent(self, f):
		if self.OnCloseEvent:
			old = self.OnCloseEvent

			def combined(*args, **kwargs):
				err = None
				try:
					old(*args, **kwargs)
				except Exception as e:
					err = e
				f(*args, **kwargs)
				if err:
					raise err

			self.OnCloseEvent = combined
		else:
			self.OnCloseEvent = f

	@_routed
	def AddOnDoneEvent(self, f):
		uiQuest.QuestCurtain.OnDoneEventList.append(f)

	@_routed
	def SetOnCloseEvent(self, f):
		self.OnCloseEvent = f

	@_routed
	def SetEventSetPosition(self, x, y):
		self.sx = x
		self.sy = y

	@_routed
	def AdjustEventSetPosition(self, x, y):
		self.sx += x
		self.sy += y

	@_routed
	def MakeNextButton(self, button_type):
		if self.SKIN_NONE == self.skin:
			return
		self.nextButtonType = button_type
		self.btnNext = True
		self._next_hover = False
		self._set(next_hover=False)

	@_routed
	def MakeQuestion(self, n):
		"""The module globals as legacy keeps them (uiquest.py:481-505); the
		choices themselves come from the page feed."""
		uiQuest.entire_questpage_number = ((n - 2) // 7) + 1
		uiQuest.entire_questbutton_number = n
		if not self.skin:
			return
		self.btnAnswer = n
		self._choice_page = 0
		self._focus_index = -1
		self._set(choice_page=0, focus_index=-1)
		if uiQuest.cur_questpage_number != 1:
			uiQuest.cur_questpage_number = 1

	@_routed
	def MakeEachButton(self, i):
		"""Legacy's widget maker; the board draws the choices."""
		return None

	@_routed
	def MakeNextPrevPageButton(self):
		return None

	@_routed
	def RefreshQuestPage(self, n):
		self._choice_page = max(0, uiQuest.cur_questpage_number - 1)
		self._set(choice_page=self._choice_page)

	@_routed
	def NextQuestPageEvent(self, one, n):
		uiQuest.cur_questpage_number = uiQuest.cur_questpage_number + one
		self.RefreshQuestPage(n)

	@_routed
	def PrevQuestPageEvent(self, one, n):
		uiQuest.cur_questpage_number = uiQuest.cur_questpage_number - one
		self.RefreshQuestPage(n)

	@_routed
	def ClickAnswerEvent(self, ai):
		event.SelectAnswer(self.descIndex, ai)
		self.CloseSelf()

	@_routed
	def AppendQuestion(self, name, idx):
		"""The page feed carries the text; nothing to do."""
		pass

	@_routed
	def FadeOut(self, speed):
		curtain().fade("fade_out", speed, self.descIndex)

	@_routed
	def FadeIn(self, speed):
		curtain().fade("fade_in", speed, self.descIndex)

	@_routed
	def WhiteOut(self, speed):
		curtain().fade("white_out", speed, self.descIndex)

	@_routed
	def WhiteIn(self, speed):
		curtain().fade("white_in", speed, self.descIndex)

	@_routed
	def DoneEvent(self):
		self.nextCurtainMode = -1
		if self.SKIN_NONE == self.skin or self.SKIN_CINEMA == self.skin:
			self.CloseSelf()

	@_routed
	def OnKeyDown(self, key):
		"""Legacy's keys (uiquest.py:617-660), app.DIK_* codes; the board maps
		Enter and the arrows onto them."""
		if self.btnAnswer is None:
			if self.btnNext is not None:
				if app.DIK_RETURN == key:
					self.OnPressEscapeKey()
				if app.DIK_UP == key or app.DIK_DOWN == key:
					self._next_hover = True
					self._set(next_hover=True)
			return True

		focus = self.focusIndex
		last = focus
		count = self.btnAnswer
		if app.DIK_DOWN == key:
			focus += 1
		if app.DIK_UP == key:
			focus -= 1
		if focus < 0:
			focus = count - 1
		if focus >= count:
			focus = 0
		self.focusIndex = focus
		if focus != last:
			self._focus_index = focus
			self._set(focus_index=focus)
		if app.DIK_RETURN == key:
			# Legacy presses the focused answer's button (BarButton.CallEvent).
			snd.PlaySound("sound/ui/click.wav")
			self.ClickAnswerEvent(focus)
		return True

	@_routed
	def OnPressEscapeKey(self):
		"""As legacy (uiquest.py:662-684): with a Next button its action, else
		the last answer of the last question any dialog made, then a cancel."""
		if self.btnNext is not None:
			if event.BUTTON_TYPE_CANCEL == self.nextButtonType:
				self.bCancelled = True
				event.SelectAnswer(self.descIndex, SELECT_NEXT)
				self.CloseSelf()
			elif event.BUTTON_TYPE_DONE == self.nextButtonType:
				self.CloseSelf()
			elif event.BUTTON_TYPE_NEXT == self.nextButtonType:
				event.SelectAnswer(self.descIndex, SELECT_NEXT)
				self.CloseSelf()
		else:
			event.SelectAnswer(self.descIndex, uiQuest.entire_questbutton_number - 1)
			self.OnCancel()
		return True

	@_routed
	def OnIMEReturn(self):
		if self.needInputString:
			self.CloseSelf()
			return True

	@_routed
	def OnIMEUpdate(self):
		pass

	@_routed
	def OnInput(self):
		"""Input mode: legacy's done button, and the field takes the focus now
		(it is laid out while idle; its class follows the page feed)."""
		self.needInputString = True
		self.MakeNextButton(event.BUTTON_TYPE_DONE)
		board = self._board()
		if board is not None:
			self._has_field = True
			board.focus("quest-input")

	@_routed
	def OnImage(self, x, y, filename, desc=""):
		"""The page feed carries the image (with legacy's board folder rule)."""
		pass

	@_routed
	def OnInsertItemIcon(self, type, idx, title, desc, index=0, total=1):
		"""The lines feed carries the icon row, captions and tooltips."""
		pass

	@_routed
	def OnInsertImage(self, filename, underTitle, title, desc, index=0, total=1):
		pass

	@_routed
	def OnSize(self, width, height):
		pass

	@_routed
	def OnTitleImage(self, filename):
		self._title_on = True
		self._set(title_on=True)

	@_routed
	def OnLeftImage(self, imgfile):
		pass

	@_routed
	def OnTopImage(self, imgfile):
		pass

	@_routed
	def OnBackgroundImage(self, imgfile):
		pass

	# --- the board's events and keys -------------------------------------------------

	def nui_key(self, event_args):
		"""Every key while the board shows is the dialog's (the modal keeps them
		all, as legacy's lock did): Escape, Enter and the arrows as legacy's."""
		board = self._board()
		if board is None or not board.is_visible():
			return None
		key = event_args.get("key_identifier")
		if key == nui.KEY_ESCAPE:
			self.OnPressEscapeKey()
			return True
		dik = {nui.KEY_RETURN: app.DIK_RETURN, KEY_UP: app.DIK_UP, KEY_DOWN: app.DIK_DOWN}.get(key)
		if dik is not None:
			self.OnKeyDown(dik)
		return True

	def nui_field_key(self, event_args):
		"""Escape in the field (a focused field stops every key but Tab); Enter
		arrives as the field's change event."""
		if event_args.get("key_identifier") != nui.KEY_ESCAPE or self._board() is None:
			return None
		self.OnPressEscapeKey()
		return True

	def nui_choose(self, index):
		if self.btnAnswer is None or not 0 <= index < self.btnAnswer:
			return
		self.ClickAnswerEvent(index)

	def nui_pager(self, step):
		count = self.btnAnswer or 0
		pages = (count + QUEST_BUTTON_MAX_NUM - 1) // QUEST_BUTTON_MAX_NUM
		if step > 0 and self._choice_page < pages - 1:
			self.NextQuestPageEvent(1, count)
		elif step < 0 and self._choice_page > 0:
			self.PrevQuestPageEvent(1, count)

	def nui_next(self):
		"""The Next button's press (uiquest.py:466-474)."""
		if self.btnNext is None:
			return
		if event.BUTTON_TYPE_CANCEL == self.nextButtonType:
			self.bCancelled = True
			event.SelectAnswer(self.descIndex, SELECT_NEXT)
			self.OnCancel()
		elif event.BUTTON_TYPE_DONE == self.nextButtonType:
			self.CloseSelf()
		elif event.BUTTON_TYPE_NEXT == self.nextButtonType:
			event.SelectAnswer(self.descIndex, SELECT_NEXT)
			self.CloseSelf()

	def nui_next_out(self):
		if self._next_hover:
			self._next_hover = False
			self._set(next_hover=False)

	def nui_field(self, value, linebreak):
		self._field_text = value if isinstance(value, str) else ""
		if linebreak:
			self.OnIMEReturn()

	def nui_title_end(self):
		self._title_on = False
		self._set(title_on=False)
