"""NovaUI dungeon manager, direction D "Bestiary" (nui/windows/dungeon-timer/dungeon-timer.rml;
NOVA-25, the Claude Design D-bestiary board).

While the dungeon-timer flag is on, Interface.__MakeDungeonWindows makes TimerWindow below
through nui_windows.make() instead of uiTimerWindow.TimerWindow: a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the widgets were, so the hidden-dungeon rule
(HIDDEN_DUNGEONS: session and level), the chosen dungeon, the ticket's tooltip (legacy's over-in
handler, through nui_slots.LegacySlotEvents), the teleport and the ranking commands are legacy's
code.

The board is a deck of boss cards: every dungeon has a card with its boss (one named model
preview per dungeon, "dungeon_boss_<idx>", view "model-dungeon-boss-<idx>", shown only for the
visible cards; the front card's boss turns, the side cards' are still pictures; a card shows its
monogram until its boss is made, which a background preview does over the steps after it is
asked, NOVA-256), a badge (Ready,
the live countdown, or Hidden), and a place in the deck (a slot class; the sheet transitions
left, top, width, height and opacity over 0.3 s). Below it the front dungeon's details, its
drops merged across all its mobs in one grid (merged_drops) with filter chips, and Run or
Practice.

No Python runs per frame. A card's clock is a nui-countdown (M:SS) to the dungeon's re-entry
time: its end raises card_ready and the card turns ready. The notice of a checked dungeon is
nui_dungeon_notice's: legacy's per-frame UpdateTime does nothing here. While a shown card's boss
loads, a hidden nui-countdown (previews_check) asks every PREVIEW_POLL seconds whether it is made.

What an open costs (NOVA-256; r46: the session's first open made the five bosses in one frame,
242 ms of GR2 parses): the previews are background previews (modelpreview.SetBackground), so a
Select makes no model; the client reads each boss's files on its loader thread and parses them one
a step, front card first. A close hides the previews and keeps them, models and pictures, for the
next open (Destroy, at the phase's end, clears them), and the board is kept loaded and hidden from
the window's making on (KEEP_BOARD_FROM_PROBE), so an open loads no document."""

import app
import item
import net
import ui
import uiScriptLocale
import uiTimerWindow

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots
import nui_dungeon_notice

DOCUMENT = "nui/windows/dungeon-timer/dungeon-timer.rml"
KEY = "dungeon-timer"
BUTTONS = {"time": "btnTimeRank", "overall": "btnOverAllRank", "damage": "btnDamageRank"}
BANDS = {1: "rare", 2: "common", 3: "guaranteed"}
FILTERS = ("guaranteed", "common", "rare")
# The server answers one drops request a second (CHARACTER::SendDungeonDrops) and
# sends nothing for a dungeon it knows no drops of, so a request inside that
# second is sent again, and the drops pane reads empty after a wait.
DROPS_REQUEST_GAP = 1.1
DROPS_ANSWER_WAIT = 3.0
# The deck: a card's offset from the front one is its slot (the sheet's classes).
SLOTS = {0: "c", 1: "r1", 2: "r2", 3: "r3", -1: "l1", -2: "l2", -3: "l3"}
# The slots that show a card: the outermost ones sit behind the deck, hidden.
SHOWN_SLOTS = ("c", "r1", "r2", "l1", "l2")
FRONT_SLOT = "c"
PREVIEW_PREFIX = "dungeon_boss_"
# NOVA-256: the previews' bosses load off the frame (modelpreview.SetBackground), in this order of
# their cards' slots: the front card first, then the nearest.
BACKGROUND_PREVIEWS = True
PREVIEW_ORDER = ("c", "r1", "l1", "r2", "l2")
# Seconds between two looks at a boss that is still loading (the hidden previews_check clock).
PREVIEW_POLL = 0.2
# NOVA-256: the board the window's making loads (nui_end's probe) stays, hidden and emptied, so even
# the session's first open loads no document (default, Eddy to confirm: a hidden document for the
# phase, the inventory's kept-board pattern from the making on instead of from the first open).
KEEP_BOARD_FROM_PROBE = True


def monogram(title):
	"""Two letters for a card without a boss model: the first letters of the first two
	words, or the first two letters of a one-word name."""
	words = [word for word in title.split() if word]
	if not words:
		return ""
	if len(words) >= 2:
		return "".join(word[0] for word in words[:2]).upper()
	return words[0][:2].upper()


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

	@nui.on("card_press")
	def on_card_press(self, idx, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_card(int(idx))

	@nui.on("arrow_press")
	def on_arrow_press(self, direction, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_arrow(direction)

	@nui.on("hide_press")
	def on_hide_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_hide()

	@nui.on("chip_press")
	def on_chip_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_chip()

	@nui.on("card_ready")
	def on_card_ready(self, idx):
		self._owner.publish_cards()

	@nui.on("button_press")
	def on_button_press(self, name, button):
		self.raise_for(button)
		if button == 0 and name in BUTTONS:
			getattr(self._owner, BUTTONS[name]).click()

	@nui.on("go_press")
	def on_go_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_go()

	@nui.on("seg_press")
	def on_seg_press(self, mode, button):
		self.raise_for(button)
		if button == 0:
			self._owner.set_mode(mode)

	@nui.on("filter_press")
	def on_filter_press(self, band, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_filter(band)

	@nui.on("wiki_press")
	def on_wiki_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_wiki()

	@nui.on("notice_press")
	def on_notice_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.noticeBtn.OnMouseLeftButtonUp()

	@nui.on("drop_over")
	def on_drop_over(self, index):
		self._owner.over_drop(int(index))

	@nui.on("drop_out")
	def on_drop_out(self):
		self._owner.out_drop()

	@nui.on("drops_retry")
	def on_drops_retry(self):
		self._owner.retry_drops()

	@nui.on("drops_timeout")
	def on_drops_timeout(self):
		self._owner.drops_timed_out()

	@nui.on("previews_ready")
	def on_previews_ready(self):
		self._owner.check_previews()

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
	"""uiTimerWindow.TimerWindow on NovaUI (Interface.wndTimer), as direction D."""

	KEY = KEY
	BOARD = _TimerBoard
	PLACE = "center"
	OnUpdate = None

	# Class-level defaults: ui.Window.__init__ calls Hide before __init__ below has set
	# anything on the instance.
	_preview_models = None
	_preview_waiting = None
	_show_hidden = False
	_filter = ""
	_mode = "run"
	_keep_description = False

	def __init__(self):
		self._drops_asked = uiTimerWindow.asked_set()
		self._drops_empty = uiTimerWindow.asked_set()
		self._drops_next_ask = 0.0
		self._drop_items = []
		# idx -> (the race its preview was asked for, whether it has a model), from the first show
		# of its card until Destroy; the ones whose boss still loads (a background preview).
		self._preview_models = {}
		self._preview_waiting = set()
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
			"cards": [],
			"selected": -1,
			"chip": "",
			"chip_on": False,
			"hero_hidden": False,
			"hide_locked": False,
			"empty": "",
			"name": "",
			"boss": "",
			"level": "",
			"group": "",
			"cooldown": "",
			"ticket": nui_slots.empty_cell(0),
			"ticket_none": True,
			# P15 F-2 (nui_slots.ATTACH_RIGHT; the ticket cell's nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			"wiki_on": False,
			"notice": False,
			"mode": "run",
			# The Run/Practice button: its text, the live clock's end (0: none) and whether it is locked.
			"go_label": "",
			"go_end": 0.0,
			"go_locked": False,
			# The drops: "loading", "empty" or "ready", the cells shown, the heading's count, the
			# filter chips, and the two clocks that retry a request and give up on an answer.
			"drops_state": "",
			"drops_items": [],
			"drops_count": "0",
			"filter_chips": [],
			"drops_retry": 0.0,
			"drops_timeout": 0.0,
			# NOVA-256: the clock that looks again at the bosses still loading (0: none loads).
			"previews_check": 0.0,
		}

	def nui_demand(self):
		"""NOVA-256: the board is kept, hidden and emptied, between opens (P18's kept boards), from
		the window's making on (KEEP_BOARD_FROM_PROBE) or from its first open."""
		return nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board,
		                         keep_probe=KEEP_BOARD_FROM_PROBE)

	def _empty_board(self, board):
		"""The kept hidden board holds no card, drop or chip and runs no clock (RmlUi updates every
		element of a loaded document each frame); _restore_board sets them again at the next show."""
		board.set(cards=[], drops_items=[], filter_chips=[], go_end=0.0, drops_retry=0.0, drops_timeout=0.0,
		          previews_check=0.0)

	# --- the loader (uitimerwindow.py __LoadWindow, on proxies) ------------------------

	def _TimerWindow__LoadWindow(self):
		# The uiscript's style (timerwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.board = nui_proxies.BoardProxy(820, 540)
		self.itemSlot = nui_slots.SlotWindowProxy([0], self._on_ticket)
		self.teleport = nui_proxies.ButtonProxy()
		self.btnDungeonDrops = nui_proxies.ButtonProxy()
		self.btnTimeRank = nui_proxies.ButtonProxy()
		self.btnOverAllRank = nui_proxies.ButtonProxy()
		self.btnDamageRank = nui_proxies.ButtonProxy()
		self.info_bg = _AreaProxy()
		# The details are read from the data at each SetDescription (the texts legacy
		# writes are its one-line forms): these only take what legacy tells them.
		self.BossName = nui_proxies.TextProxy()
		self.text1 = nui_proxies.TextProxy()
		self.text2 = nui_proxies.TextProxy()
		self.text3 = nui_proxies.TextProxy()
		self.text4 = nui_proxies.TextProxy()
		self.dungeonsWindow = nui_proxies.WindowProxy()
		self.showHiddenBtn = nui_proxies.ButtonProxy()
		self.boardScrollableWindow = _ScrollProxy()
		self.descWindow = nui_proxies.WindowProxy()
		self.descScrollableWindow = _ScrollProxy()
		self.textLine = _NameProxy(lambda value: self.nui_set(name=nui.plain_text(value)))
		self.emptyLabel = nui_proxies.TextProxy(lambda value: self._publish_empty())
		self.emptyLabel.on_show = lambda shown: self._publish_empty()
		self.emptyLabel.shown = False
		self.noticeBtn = _CheckBoxProxy(lambda checked: self.nui_set(notice=bool(checked)))
		self.ticket_events = self.nui_events(nui_slots.LegacySlotEvents(self.itemSlot))
		self.bossView = None

	def _TimerWindow__MakeBossView(self):
		return None

	def _TimerWindow__MakeBoard(self, idx):
		return _RowProxy(self, idx)

	def _TimerWindow__MakeDescLine(self):
		return _DescProxy()

	def _TimerWindow__ShowBossModel(self, race):
		"""The cards' previews replace legacy's single one."""

	def _TimerWindow__HideBossModel(self):
		"""Legacy's Hide: the cards' previews hide and keep their bosses for the next show (legacy's
		Hide runs in ui.Window.__init__ before the window has any: _hide_previews survives that)."""
		self._hide_previews()

	# --- the deck ----------------------------------------------------------------------

	def _deck(self):
		"""The dungeons with a card in the deck, in the deck's order: the visible ones, and the
		player's hidden ones while the chip shows them."""
		deck = []
		for idx in uiTimerWindow.iter_indices_sorted():
			if not uiTimerWindow.is_hidden_for_current_view(idx):
				deck.append(idx)
			elif self._show_hidden and uiTimerWindow.is_user_hidden(idx):
				deck.append(idx)
		return deck

	def _hidden_count(self):
		return sum(1 for idx in uiTimerWindow.DESCRIPTION if uiTimerWindow.is_user_hidden(idx))

	def _slot_of(self, deck, front, idx):
		if idx not in deck:
			return "out"
		size = len(deck)
		offset = (deck.index(idx) - deck.index(front)) % size
		if offset > size / 2.0:
			offset -= size
		return SLOTS[max(-3, min(3, offset))]

	def nui_race(self, idx):
		return int(uiTimerWindow.DESCRIPTION[idx][0][0])

	def publish_cards(self):
		"""The deck and everything that follows its front card."""
		if self.__dict__.get("_state") is None or "boards" not in self.__dict__:
			return
		deck = self._deck()
		front = self.index if self.index in deck else (deck[0] if deck else None)
		now = nui.now()
		indices = list(uiTimerWindow.iter_indices_sorted())
		slots = dict((idx, "out" if front is None else self._slot_of(deck, front, idx)) for idx in indices)
		# The previews in the order their bosses should load: the front card's first.
		views = {}
		for idx in self._preview_order(slots):
			views[idx] = self._sync_preview(idx, slots[idx])
		cards = []
		for idx in indices:
			slot = slots[idx]
			left = self._left(idx)
			hidden = uiTimerWindow.is_user_hidden(idx)
			title = nui.plain_text(uiTimerWindow.get_title(idx))
			cards.append({
				"idx": int(idx), "title": title, "mono": monogram(title), "level": self._level_text(idx),
				"slot": slot, "hidden": hidden, "view": views[idx],
				"state": "hidden" if hidden else ("cd" if left > 0 else "ready"),
				"end": now + left if left > 0 and not hidden else 0.0,
			})
		count = self._hidden_count()
		left = self._left(self.index) if front is not None else 0
		hero_hidden = front is not None and uiTimerWindow.is_user_hidden(front)
		loading = self.IsShow() and any(idx in self._preview_waiting for idx in indices if slots[idx] in SHOWN_SLOTS)
		self.nui_set(cards=cards, selected=int(front) if front is not None else -1,
		             chip=self._chip_text(count), chip_on=self._show_hidden, hero_hidden=hero_hidden,
		             hide_locked=not hero_hidden and len(self.visible_indices) <= 1,
		             previews_check=now + PREVIEW_POLL if loading else 0.0,
		             **self._go_state(front, left, now))

	def _chip_text(self, count):
		if self._show_hidden:
			return uiScriptLocale.DUNGEON_MANAGER_DONE
		return uiScriptLocale.DUNGEON_MANAGER_N_HIDDEN % count if count else ""

	def _go_state(self, front, left, now):
		if front is None:
			return {"go_label": "", "go_end": 0.0, "go_locked": True}
		if self._mode == "practice":
			return {"go_label": uiScriptLocale.DUNGEON_MANAGER_START_PRACTICE, "go_end": 0.0, "go_locked": False}
		if left > 0:
			return {"go_label": uiScriptLocale.DUNGEON_MANAGER_READY_IN, "go_end": now + left, "go_locked": True}
		return {"go_label": uiScriptLocale.DUNGEON_MANAGER_TELEPORT, "go_end": 0.0, "go_locked": False}

	def _level_text(self, idx):
		data = uiTimerWindow.DESCRIPTION[idx]
		return uiScriptLocale.DUNGEON_MANAGER_LEVEL_RANGE % (int(data[1]), int(data[2]))

	def _left(self, idx):
		"""Seconds left on a dungeon's clock (0 before QuestTimeReady, as legacy)."""
		if not uiTimerWindow.TIMER_STATE["loaded"]:
			return 0
		return max(0, self.GetEndTime(idx) - app.GetGlobalTimeStamp())

	# --- the previews (one per dungeon, only for the cards that show) ------------------

	def _preview_order(self, slots):
		"""The dungeons in the order their previews are asked for: by their card's slot in
		PREVIEW_ORDER (the front card first), then the rest (a background preview's boss loads in the
		order asked)."""
		rank = dict((slot, i) for i, slot in enumerate(PREVIEW_ORDER))
		return sorted(slots, key=lambda idx: (rank.get(slots[idx], len(rank)), idx))

	def _sync_preview(self, idx, slot):
		"""Shows or hides dungeon idx's preview and answers whether its card shows it: a shown card
		whose boss is made (a background preview's boss loads over the steps after it is asked; the
		card shows its monogram until then, and never another dungeon's boss)."""
		name = PREVIEW_PREFIX + str(int(idx))
		preview = uiTimerWindow.model_preview()
		if preview is None or self._preview_models is None:
			return False
		shown = slot in SHOWN_SLOTS and self.IsShow()
		if not shown:
			if idx in self._preview_models:
				preview.Show(name, False)
			return False
		# 0 is no boss here; the client takes race 0 for the warrior (r39).
		race = self.nui_race(idx)
		asked = self._preview_models.get(idx)
		if asked is None or asked[0] != race:
			self._select_preview(preview, name, idx, race)
		if not self._preview_models[idx][1]:
			return False
		preview.Show(name, True)
		# Only the front card turns; a side card is drawn once and keeps its picture (r38: five
		# bosses turning every frame cost the frame rate). A client without SetStill turns them all.
		set_still = getattr(preview, "SetStill", None)
		if set_still is not None:
			set_still(name, slot != FRONT_SLOT)
		return self._preview_ready(preview, name, idx, race)

	def _select_preview(self, preview, name, idx, race):
		"""Asks dungeon idx's preview for its boss; a background preview (a client with
		SetBackground) answers at once and makes the model over the next steps."""
		self._preview_waiting.discard(idx)
		if not race:
			self._preview_models[idx] = (race, False)
			return
		set_background = getattr(preview, "SetBackground", None) if BACKGROUND_PREVIEWS else None
		if set_background is not None:
			set_background(name, True)
		ok = bool(preview.Select(name, race))
		self._preview_models[idx] = (race, ok)
		if ok and set_background is not None:
			self._preview_waiting.add(idx)

	def _preview_ready(self, preview, name, idx, race):
		"""Whether dungeon idx's boss is made: at once without a background preview, else once the
		client's request no longer waits, and only with a model of the card's own race."""
		if idx not in self._preview_waiting:
			return True
		get_state = getattr(preview, "GetState", None)
		state = get_state(name) if get_state is not None else None
		if state is None:
			self._preview_waiting.discard(idx)
			return True
		if state.get("pending"):
			return False
		self._preview_waiting.discard(idx)
		if not state.get("has_model") or int(state.get("race", -1)) != int(race):
			# It made no model: the monogram stays (the same race is not asked again).
			self._preview_models[idx] = (race, False)
			return False
		return True

	def check_previews(self):
		"""The previews_check clock's end: the cards whose boss is made show it, and the clock runs
		again while one still loads."""
		self.nui_set(previews_check=0.0)
		if self.IsShow():
			self.publish_cards()

	def _hide_previews(self):
		"""Every preview the cards have hides, keeping its model and picture for the next show."""
		models = self._preview_models
		if not models:
			return
		preview = uiTimerWindow.model_preview()
		if preview is None:
			return
		for idx in models:
			preview.Show(PREVIEW_PREFIX + str(int(idx)), False)

	def _clear_previews(self):
		"""Every preview the cards have goes (Destroy: the phase's end)."""
		models = self._preview_models
		if self._preview_waiting:
			self._preview_waiting.clear()
		if not models:
			return
		preview = uiTimerWindow.model_preview()
		if preview is not None:
			for idx in models:
				preview.Clear(PREVIEW_PREFIX + str(int(idx)))
		models.clear()

	# --- the board's presses ------------------------------------------------------------

	def press_card(self, idx):
		if idx in self._deck() and idx != self.index:
			self.SetDescription(idx)

	def press_arrow(self, direction):
		deck = self._deck()
		if self.index not in deck:
			return
		step = 1 if direction == "next" else -1
		self.SetDescription(deck[(deck.index(self.index) + step) % len(deck)])

	def press_hide(self):
		idx = self.index
		if idx not in uiTimerWindow.DESCRIPTION:
			return
		if uiTimerWindow.is_user_hidden(idx):
			uiTimerWindow.HIDDEN_DUNGEONS[idx] = 0
			uiTimerWindow.SESSION_HIDDEN[idx] = 0
			self.RebuildBoards()
			self.SetDescription(idx)
			return
		if len(self.visible_indices) <= 1:
			return  # the button is locked; a stale press hides nothing
		deck = self._deck()
		if self._show_hidden:
			uiTimerWindow.TimerWindow.HideDungeon(self, idx)
			self.publish_cards()
			return
		self.index = deck[(deck.index(idx) + 1) % len(deck)]
		uiTimerWindow.TimerWindow.HideDungeon(self, idx)
		self.SetDescription(self.index)

	def press_chip(self):
		if not self._show_hidden and not self._hidden_count():
			return
		self._show_hidden = not self._show_hidden
		deck = self._deck()
		if deck and self.index not in deck:
			self.SetDescription(deck[0])
		self.publish_cards()

	def press_go(self):
		if self.index not in uiTimerWindow.DESCRIPTION:
			return
		if self._mode == "practice":
			net.SendChatPacket("/practice_dungeon %d" % self.index)
			self.Close()
			return
		if self._left(self.index) > 0:
			return  # the button is locked; a stale press sends nothing
		self.teleport.click()

	def set_mode(self, mode):
		if mode in ("run", "practice") and mode != self._mode:
			self._mode = mode
			self.nui_set(mode=mode)
			self.publish_cards()
			self._publish_drops()

	def press_filter(self, band):
		if band in FILTERS:
			self._filter = "" if self._filter == band else band
			self._publish_drops()

	def _wiki(self):
		"""The Interface's OpenWikiMob (nui_wiki's OpenMob, NOVA-42), or None without the wiki."""
		interface = self.interface
		if interface is None or getattr(interface, "wndWiki", None) is None:
			return None
		opener = getattr(interface, "OpenWikiMob", None)
		return opener if callable(opener) else None

	def press_wiki(self):
		opener = self._wiki()
		if opener is not None and self.index in uiTimerWindow.DESCRIPTION:
			opener(self.nui_race(self.index))

	# --- what NovaUI changes -----------------------------------------------------------

	def Open(self):
		self._mode = "run"
		self._show_hidden = False
		self._filter = ""
		self.nui_set(mode="run")
		uiTimerWindow.TimerWindow.Open(self)

	def Show(self):
		nui_facade.Facade.Show(self)
		self.publish_cards()

	def RebuildBoards(self):
		self._keep_description = self._show_hidden and self.index in uiTimerWindow.DESCRIPTION
		try:
			uiTimerWindow.TimerWindow.RebuildBoards(self)
		finally:
			self._keep_description = False
		self.publish_cards()

	def SetDescription(self, index):
		if self._keep_description:
			return
		uiTimerWindow.TimerWindow.SetDescription(self, index)
		if index in uiTimerWindow.DESCRIPTION:
			self._publish_details(index)
			self.publish_cards()
			self._ask_drops()

	def _publish_details(self, index):
		data = uiTimerWindow.DESCRIPTION[index]
		self.nui_set(boss=uiScriptLocale.DUNGEON_MANAGER_BOSS_LINE % nui.plain_text(self._boss_name(index)),
		             level=self._level_text(index),
		             group=nui.plain_text(uiTimerWindow.group_text(data[3])),
		             cooldown=nui.plain_text(uiTimerWindow._fmt_mins_label(uiTimerWindow._mins_ceil(int(data[4])))),
		             ticket_none=int(data[5]) == 0,
		             wiki_on=self._wiki() is not None)

	def _boss_name(self, index):
		import nonplayer
		return nonplayer.GetMonsterName(self.nui_race(index))

	def refreshMobList(self):
		uiTimerWindow.TimerWindow.refreshMobList(self)
		self._publish_drops()

	def SetTimeLeft(self, index, time_):
		uiTimerWindow.TimerWindow.SetTimeLeft(self, index, time_)
		self.publish_cards()
		self._watch_notices()

	def QuestTimeReady(self):
		uiTimerWindow.TimerWindow.QuestTimeReady(self)
		self.publish_cards()
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
		self._clear_previews()

	# --- the drops ---------------------------------------------------------------------

	def _ask_drops(self):
		"""Asks the server for the chosen dungeon's drops, unless they are known or
		asked; a request inside the server's second is sent again by drops_retry."""
		index = self.index
		if index not in uiTimerWindow.DUNGEON_DROP and index not in self._drops_asked:
			now = nui.now()
			if now < self._drops_next_ask:
				self.nui_set(drops_retry=self._drops_next_ask)
			else:
				self._send_drops_request(index)
		self._publish_drops()

	def _send_drops_request(self, index):
		if index in uiTimerWindow.DUNGEON_DROP or index in self._drops_asked:
			return
		self._drops_asked.add(index)
		self._drops_next_ask = nui.now() + DROPS_REQUEST_GAP
		net.RequestDungeonDrop(index)
		self.nui_set(drops_retry=0.0, drops_timeout=nui.now() + DROPS_ANSWER_WAIT)

	def retry_drops(self):
		self.nui_set(drops_retry=0.0)
		self._ask_drops()

	def drops_timed_out(self):
		self.nui_set(drops_timeout=0.0)
		if self.index not in uiTimerWindow.DUNGEON_DROP:
			self._drops_empty.add(self.index)
			self._publish_drops()

	def _publish_drops(self):
		if self.__dict__.get("_state") is None or "boards" not in self.__dict__:
			return
		rows = uiTimerWindow.merged_drops(self.index)
		labels = {"guaranteed": uiScriptLocale.DUNGEON_MANAGER_FILTER_GUARANTEED,
		          "common": uiScriptLocale.DUNGEON_MANAGER_FILTER_COMMON,
		          "rare": uiScriptLocale.DUNGEON_MANAGER_FILTER_RARE}
		counts = dict((band, sum(1 for row in rows if BANDS[row[2]] == band)) for band in FILTERS)
		chosen = self._filter if self._mode == "run" else ""
		chips = [{"band": band, "label": labels[band], "n": counts[band], "on": band == chosen} for band in FILTERS]
		self._drop_items = []
		items = []
		for vnum, count, band in rows:
			if chosen and BANDS[band] != chosen:
				continue
			item.SelectItem(vnum)
			self._drop_items.append(vnum)
			items.append({"i": len(items), "vnum": int(vnum), "icon": nui_slots.icon_source(item.GetIconImageFileName()),
			              "count": str(int(count)) if int(count) > 1 else "", "band": BANDS[band]})
		if not rows and self.index not in uiTimerWindow.DUNGEON_DROP:
			state = "empty" if self.index in self._drops_empty else "loading"
		else:
			state = "ready" if rows else "empty"
		total = len(rows)
		count = uiScriptLocale.DUNGEON_MANAGER_N_OF_M % (len(items), total) if chosen else str(total)
		self.nui_set(drops_state=state, drops_items=items, drops_count=count, filter_chips=chips)

	def over_drop(self, index):
		if self.tooltip and 0 <= index < len(self._drop_items):
			self.tooltip.SetItemToolTip(int(self._drop_items[index]))

	def out_drop(self):
		if self.tooltip:
			self.tooltip.HideToolTip()

	def _publish_empty(self):
		if self.__dict__.get("_state") is None:
			return
		label = self.emptyLabel
		self.nui_set(empty=nui.plain_text(label.text) if label.IsShow() else "")

	def _on_ticket(self, cells):
		self.nui_set(ticket=cells[0])

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
