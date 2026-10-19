"""NovaUI dragon soul inventory (nui/windows/dragon-soul/dragon-soul.rml; P15
spec 5).

While the dragon-soul flag is on, Interface.__MakeWindows makes
DragonSoulWindow below through nui_windows.make() instead of
uiDragonSoul.DragonSoulWindow. It is a subclass of the legacy class (P15 spec
D1): its constructor is legacy's, whose uiscript loader it replaces with
proxies standing where the legacy widgets were (nui_slots.FullSlotWindowProxy
for the bag page and the deck's six equipment slots; nui_proxies for the
kind tabs, the grade buttons, the deck and activate toggles, the kind's
title and the title bar), bound to the legacy handlers as legacy's loader
bound its widgets. So every flow, packet, question, popup and rule (pick and
place, equip and unequip, the deck switch, activation, item on item, sell,
the links, the highlights, the refine window's auto set) is the legacy
class's own code; the proxies record what it tells them and the board shows
it. Legacy's ScriptWindow stays underneath, a 0 x 0 window in the UI layer,
so IsShow, the Escape chain and SetTop are legacy's.

No Python runs per frame: legacy's window has no OnUpdate either. The board
loads at the window's first show and is kept, hidden, after it, its lists
emptied (nui_hud.KeptBoard, P15 V-2b); a refresh while hidden runs
legacy's refresh on the proxies and the board takes their last state at its
next show. Legacy activates and deactivates slots without
RefreshSlot (the highlights, the active deck), which CSlotWindow draws at
once, so every legacy entry point and board event ends with a flush of the
slot proxies it changed. Every count comes from nui_limits.current()."""

import player
import ui
import uiCommon
import uiDragonSoul

import nui
import nui_hud
import nui_limits
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/dragon-soul/dragon-soul.rml"
KEY = "dragon-soul"


def flushes(method):
	"""A legacy entry point of the window (an Interface or C++ callback, a
	key, Escape): its outermost call ends with the window's _flush(). Only
	for methods legacy never binds through ui.__mem_func__ with arguments:
	the wrapper takes *args, so __mem_func__ would call it with none."""
	def call(self, *args, **kwargs):
		depth = getattr(self, "_flush_depth", None)
		if depth is None:
			return method(self, *args, **kwargs)
		self._flush_depth = depth + 1
		try:
			return method(self, *args, **kwargs)
		finally:
			self._flush_depth -= 1
			if self._flush_depth == 0:
				self._flush()
	call.__name__ = method.__name__
	call.__doc__ = method.__doc__
	call.__wrapped__ = method
	return call


def flushes_owner(method):
	"""A board event: the owner's flush after it."""
	def call(self, *args):
		try:
			return method(self, *args)
		finally:
			try:
				self._owner._flush()
			except ReferenceError:
				pass
	call.__name__ = method.__name__
	call._nui_events = method._nui_events
	return call


def flush_board_events(board_class):
	"""Wraps every @nui.on handler of a board class with flushes_owner."""
	for name, method in list(vars(board_class).items()):
		if getattr(method, "_nui_events", None):
			setattr(board_class, name, flushes_owner(method))


class _DragonSoulBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The dragon soul window's document; its events go to its window. A
	press on it raises the window, as legacy's window manager does
	(RaisesOnPress); buttons act on a left mousedown."""

	DOCUMENT = DOCUMENT
	MODEL = "dragon_soul"

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
			self._owner._close()

	@nui.on("kind_press")
	def on_kind_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_kind(int(index))

	@nui.on("grade_press")
	def on_grade_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_grade(int(index))

	@nui.on("deck_press")
	def on_deck_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_deck(int(index))

	@nui.on("activate_press")
	def on_activate_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_activate()

	# --- the bag and the equipment: the legacy slot windows' events -------------------

	@nui.on("bag_press")
	def on_bag_press(self, index, button):
		self.raise_for(button)
		self._owner._bag_events.press(int(index), button)
		# P15 spec 7: legacy's SelectItemSlot attaches a dragon soul, whose
		# icon its DeattachObject leaves unless the legacy fix is in.
		nui_slots.adopt_attach()

	@nui.on("bag_release")
	def on_bag_release(self, index, button):
		self._owner._bag_events.release(int(index), button)

	@nui.on("bag_use")
	def on_bag_use(self, index):
		self._owner._bag_events.use(int(index))

	@nui.on("bag_over")
	def on_bag_over(self, index):
		self._owner._bag_events.over(int(index))

	@nui.on("bag_out")
	def on_bag_out(self, index):
		self._owner._bag_events.out(int(index))

	@nui.on("bag_drop")
	def on_bag_drop(self, index):
		self._owner._bag_events.drop(int(index))

	@nui.on("equip_press")
	def on_equip_press(self, index, button):
		self.raise_for(button)
		self._owner._equip_events.press(int(index), button)
		nui_slots.adopt_attach()

	@nui.on("equip_release")
	def on_equip_release(self, index, button):
		self._owner._equip_events.release(int(index), button)

	@nui.on("equip_use")
	def on_equip_use(self, index):
		self._owner._equip_events.use(int(index))

	@nui.on("equip_over")
	def on_equip_over(self, index):
		self._owner._equip_events.over(int(index))

	@nui.on("equip_out")
	def on_equip_out(self, index):
		self._owner._equip_events.out(int(index))

	@nui.on("equip_drop")
	def on_equip_drop(self, index):
		self._owner._equip_events.drop(int(index))


flush_board_events(_DragonSoulBoard)


class DragonSoulWindow(uiDragonSoul.DragonSoulWindow):
	"""uiDragonSoul.DragonSoulWindow on NovaUI (Interface.wndDragonSoul)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._flush_depth = 0
		self._flushing = False
		self._bag_events = None
		self._equip_events = None
		self._state = self._empty_state()
		self._place = None
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_3c():
			# V-2b (P15 spec 8.1, D9): the board is kept, hidden, after its first open.
			self.demand = nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board)
		try:
			uiDragonSoul.DragonSoulWindow.__init__(self)
			if self.demand is not None:
				self.loaded = self.demand.probe()
		except Exception:
			self.nui_discard()
			raise

	# --- make()'s protocol ------------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_3c()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(KEY, self)

	# --- the model ------------------------------------------------------------------

	def _bag_slots(self):
		return list(range(self._limits.DRAGON_SOUL_PAGE_SIZE))

	def _equip_slots(self):
		start = self._limits.DRAGON_SOUL_EQUIPMENT_SLOT_START
		return [start + i for i in range(self._limits.DRAGON_SOUL_EQUIPMENT_FIRST_SIZE)]

	def _empty_state(self):
		limits = self._limits
		return {
			"placed": False,
			# P15 F-2: the grids take a right press while something is attached.
			"attach_right": bool(nui_slots.ATTACH_RIGHT),
			"kinds": [{"index": i, "label": "@ui.DRAGONSOUL_TAP_TITLE_%d" % (i + 1), "down": i == 0}
			          for i in range(limits.DRAGON_SOUL_KIND_COUNT)],
			"kind": 0,
			"kind_title": "",
			"grades": [{"index": i, "label": "@ui.DRAGONSOUL_PAGE_BUTTON_%d" % (i + 1), "down": i == 0}
			           for i in range(limits.DRAGON_SOUL_PAGE_COUNT)],
			"grade": 0,
			"decks": [{"index": i, "label": nui_limits.ROMAN[i] if i < len(nui_limits.ROMAN) else str(i + 1),
			           "down": i == 0} for i in range(limits.DRAGON_SOUL_EQUIPMENT_PAGE_COUNT)],
			"deck": 0,
			"activated": False,
			"bag": [nui_slots.empty_cell(i) for i in range(limits.DRAGON_SOUL_PAGE_SIZE)],
			"bag_cols": limits.DRAGON_SOUL_COLUMNS,
			"equip": [dict(nui_slots.empty_cell(i), sub=i) for i in range(limits.DRAGON_SOUL_EQUIPMENT_FIRST_SIZE)],
			# V-2b: the deck, the kinds, the grades and the bag, each a list of
			# one entry while the board shows and none while it is kept hidden.
			"deck_on": [1], "kinds_on": [1], "grades_on": [1], "bag_on": [1],
		}

	def _set(self, **values):
		"""The changed keys into the state and the shown board (a hover, a
		refresh of the same page: often nothing changed)."""
		changed = dict((key, value) for key, value in values.items() if self._state.get(key) != value)
		if not changed:
			return
		self._state.update(changed)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**changed)

	def _make_board(self):
		return _DragonSoulBoard(self, self._state)

	def _restore_board(self, board):
		self._flush()
		board.set(**self._state)
		if self._place is not None:
			self._state["placed"] = True
			board.set(placed=True)
			board.set_position(self._place[0], self._place[1])

	def _empty_board(self, board):
		"""V-2b: the hidden kept board holds no deck, kind, grade or bag cell
		(RmlUi updates every element of a loaded document each frame);
		_restore_board sets them again at the next show."""
		board.set(deck_on=[], kinds_on=[], grades_on=[], bag_on=[])

	def _keep_board(self, board):
		"""Legacy's window keeps the place it was dragged to (D10): the board's
		top left in dp, read before it goes."""
		box = board.element_box("")
		if box:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def board(self):
		return self.demand.board() if self.demand is not None else None

	# --- the proxies' callbacks -------------------------------------------------------

	def _bag_position(self, local):
		return self._DragonSoulWindow__InventoryLocalSlotPosToGlobalSlotPos(player.DRAGON_SOUL_INVENTORY, local)

	def _equip_position(self, slot):
		return self._DragonSoulWindow__InventoryLocalSlotPosToGlobalSlotPos(player.INVENTORY, slot)

	def _with_states(self, events, cells):
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		return nui_slots.with_states(cells, states, picked)

	def _on_bag(self, cells):
		self._set(bag=self._with_states(self._bag_events, cells))

	def _on_bag_states(self, states, picked):
		self._set(bag=nui_slots.with_states(self.wndItem.cells(), states, picked))

	def _equip_cells(self, cells, states=None, picked=-1):
		marked = nui_slots.with_states(cells, states or {}, picked)
		for sub, cell in enumerate(marked):
			cell["sub"] = sub
		return marked

	def _on_equip(self, cells):
		events = self._equip_events
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self._set(equip=self._equip_cells(cells, states, picked))

	def _on_equip_states(self, states, picked):
		self._set(equip=self._equip_cells(self.wndEquip.cells(), states, picked))

	def _on_kinds(self, *ignored):
		"""The kind strip as legacy draws it: the shown tab image (Tab_0n) is
		the selected kind; the radio buttons over it have no art."""
		tabs = getattr(self, "tabDict", None)
		if not tabs:
			return
		kinds = [{"index": i, "label": "@ui.DRAGONSOUL_TAP_TITLE_%d" % (i + 1), "down": bool(tabs[i].IsShow())}
		         for i in sorted(tabs)]
		self._set(kinds=kinds, kind=int(self.DSKindIndex))

	def _on_kind_title(self, text):
		self._set(kind_title=nui.plain_text(text), kind=int(self.DSKindIndex))

	def _on_grades(self, *ignored):
		tabs = getattr(self, "inventoryTab", None)
		if not tabs:
			return
		grades = [{"index": i, "label": "@ui.DRAGONSOUL_PAGE_BUTTON_%d" % (i + 1), "down": bool(tab.IsDown())}
		          for i, tab in enumerate(tabs)]
		self._set(grades=grades, grade=int(self.inventoryPageIndex))

	def _on_decks(self, *ignored):
		tabs = getattr(self, "deckTab", None)
		if not tabs:
			return
		decks = [{"index": i, "label": nui_limits.ROMAN[i] if i < len(nui_limits.ROMAN) else str(i + 1),
		          "down": bool(tab.IsDown())} for i, tab in enumerate(tabs)]
		self._set(decks=decks, deck=int(self.deckPageIndex))

	def _on_activate(self, proxy):
		self._set(activated=bool(proxy.IsDown()))

	# --- the loader (uidragonsoul.py:54-176, on proxies) ---------------------------------

	def _DragonSoulWindow__LoadWindow(self):
		"""Legacy's, on proxies (P15 spec 5.4): without its right-to-left
		mirroring (NovaUI never runs in such a locale) and without
		exception.Abort (make() falls back to the legacy window when this
		raises); every attribute legacy reads, the same events bound to the
		same legacy handlers, the same refreshes at the end."""
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		# The uiscript's style (dragonsoulwindow.py: "movable", "float"): a
		# float window is the one SetTop raises (CWindow::SetTop).
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits

		wndItem = nui_slots.FullSlotWindowProxy(
			self._bag_slots(), self._on_bag, cols=limits.DRAGON_SOUL_COLUMNS, rows=limits.DRAGON_SOUL_ROWS,
			positions=self._bag_position, window=player.DRAGON_SOUL_INVENTORY, limits=limits)
		wndEquip = nui_slots.FullSlotWindowProxy(self._equip_slots(), self._on_equip, positions=self._equip_position,
		                                         limits=limits)
		self.activateButton = nui_proxies.ToggleButtonProxy(self._on_activate)
		self.deckTab = [nui_proxies.ToggleButtonProxy(self._on_decks)
		                for _ in range(limits.DRAGON_SOUL_EQUIPMENT_PAGE_COUNT)]
		self._title_bar = nui_proxies.BoardProxy()
		self._title_bar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.inventoryTab = [nui_proxies.ButtonProxy(self._on_grades) for _ in range(limits.DRAGON_SOUL_PAGE_COUNT)]
		kinds = range(limits.DRAGON_SOUL_KIND_COUNT)
		self.tabDict = dict((i, nui_proxies.ImageProxy()) for i in kinds)
		for image in self.tabDict.values():
			image.on_show = self._on_kinds
		self.tabButtonDict = dict((i, nui_proxies.ButtonProxy()) for i in kinds)
		self.tabText = nui_proxies.TextProxy(self._on_kind_title)

		## DragonSoul Kind Tap
		for (tabKey, tabButton) in list(self.tabButtonDict.items()):
			tabButton.SetEvent(ui.__mem_func__(self.SetDSKindIndex), tabKey)
		## Item
		wndItem.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndItem.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		wndItem.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndItem.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndItem.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))

		## Equipment
		wndEquip.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptyEquipSlot))
		wndEquip.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectEquipItemSlot))
		wndEquip.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseEquipItemSlot))
		wndEquip.SetUseSlotEvent(ui.__mem_func__(self.UseEquipItemSlot))
		wndEquip.SetOverInItemEvent(ui.__mem_func__(self.OverInEquipItem))
		wndEquip.SetOverOutItemEvent(ui.__mem_func__(self.OverOutEquipItem))

		## Deck (legacy's literal two decks, its own lambdas)
		for deck, tab in enumerate(self.deckTab):
			tab.SetToggleDownEvent(lambda arg=deck: self.SetDeckPage(arg))
			tab.SetToggleUpEvent(lambda arg=deck: self._DragonSoulWindow__DeckButtonDown(arg))
		self.deckTab[0].Down()
		## Grade button
		for page, tab in enumerate(self.inventoryTab):
			tab.SetEvent(lambda arg=page: self.SetInventoryPage(arg))
		self.inventoryTab[0].Down()
		## Etc
		self.wndItem = wndItem
		self.wndEquip = wndEquip
		self._bag_events = nui_slots.LegacySlotEvents(wndItem, on_states=self._on_bag_states)
		self._equip_events = nui_slots.LegacySlotEvents(wndEquip, on_states=self._on_equip_states)

		self.dlgQuestion = uiCommon.QuestionDialog2()
		self.dlgQuestion.Close()

		self.activateButton.SetToggleDownEvent(ui.__mem_func__(self.ActivateButtonClick))
		self.activateButton.SetToggleUpEvent(ui.__mem_func__(self.ActivateButtonClick))
		self.wndPopupDialog = uiCommon.PopupDialog()

		##
		self.listHighlightedSlot = []

		## Refresh
		self.SetInventoryPage(0)
		self.RefreshItemSlot()
		self.RefreshEquipSlotWindow()
		self.RefreshBagSlotWindow()
		self.SetDSKindIndex(0)
		self.activateButton.Enable()
		self.deckTab[self.deckPageIndex].Down()
		self.activateButton.SetUp()

	# --- the board's presses -----------------------------------------------------------

	def _close(self):
		self._title_bar.close()

	def _press_radio(self, button):
		"""A radio button (a kind tab, a grade button): a press on the one
		that is down does nothing (CRadioButton::OnMouseLeftButtonDown);
		else it goes down and calls its event."""
		if button is None or button.IsDown():
			return
		button.Down()
		button.click()

	def _press_kind(self, index):
		self._press_radio(self.tabButtonDict.get(index) if self.tabButtonDict else None)

	def _press_grade(self, index):
		if 0 <= index < len(self.inventoryTab):
			self._press_radio(self.inventoryTab[index])

	def _press_deck(self, index):
		"""A deck toggle (CToggleButton): the other deck's goes down and runs
		SetDeckPage; the shown deck's goes up and its up event presses it
		down again."""
		if 0 <= index < len(self.deckTab):
			self.deckTab[index].click()

	def _press_activate(self):
		self.activateButton.click()

	# --- the flush ------------------------------------------------------------------

	def _flush(self):
		"""What legacy changed without RefreshSlot during the call that ends
		now (FullSlotWindowProxy's dirty flag; CSlotWindow draws a change at
		once) and the page, kind and deck reach the model."""
		if self._flushing:
			return
		self._flushing = True
		try:
			for events in (self._bag_events, self._equip_events):
				if events is not None and events.proxy.dirty:
					events.proxy.push()
			# The page, kind and deck legacy keeps in attributes, with their
			# buttons (each write is skipped when nothing changed).
			self._on_kinds()
			self._on_grades()
			self._on_decks()
			if getattr(self, "activateButton", None):
				self._on_activate(self.activateButton)
		finally:
			self._flushing = False

	# --- what NovaUI changes (P15 spec 5.4's table) ------------------------------------

	def Show(self):
		# The board first, so a refresh legacy's Show runs reaches it.
		if self.demand is not None:
			self.demand.show()
			# Legacy's Show raises nothing: the boards raised since stay above (VF-1).
			nui_hud.keep_order(self)
		uiDragonSoul.DragonSoulWindow.Show(self)

	def Hide(self):
		uiDragonSoul.DragonSoulWindow.Hide(self)
		# The board's cells hear no mouseout as it goes (nui_slots.LegacySlotEvents.reset).
		for events in (self._bag_events, self._equip_events):
			if events is not None:
				events.reset()
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.board()
		if board is not None:
			board.bring_to_front()
		nui_hud.note_raise(self)
		uiDragonSoul.DragonSoulWindow.SetTop(self)

	def Destroy(self):
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		uiDragonSoul.DragonSoulWindow.Destroy(self)
		nui_hud.forget(KEY, self)


# The facade (P15 spec 5.4: what the Interface, game.py, the item tooltip and
# the C++ callbacks call) and the legacy methods that change the slots or the
# chrome. None of them is bound through ui.__mem_func__ with an argument
# (Close and ActivateButtonClick are bound, and called with none), so the
# wrapper's signature is safe; SetDSKindIndex is bound with its kind, so it
# stays unwrapped (its RefreshBagSlotWindow flushes).
FLUSHED = ("ActivateButtonClick", "ActivateDragonSoulByExtern", "Close", "DeactivateDragonSoul", "Hide", "HighlightSlot",
           "OnPressEscapeKey", "RefreshBagSlotWindow", "RefreshEquipSlotWindow", "RefreshItemSlot", "RefreshStatus",
           "SetDeckPage", "SetInventoryPage", "Show")
for _name in FLUSHED:
	setattr(DragonSoulWindow, _name, flushes(getattr(DragonSoulWindow, _name)))
del _name
