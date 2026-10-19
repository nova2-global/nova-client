"""The pattern every Wave 4 window follows (P16 spec 4.1, D1): a subclass of
the legacy class whose uiscript loader puts proxies (nui_form_proxies,
nui_proxies, nui_slots) where the widgets were, so every flow, packet,
question and rule stays the legacy class's own code; the NovaUI board shows
what the proxies were told. Wave 3b's item windows wrote this pattern out per
window; the Wave 4 windows share it here.

Facade goes first among the bases: class ExchangeDialog(nui_facade.Facade,
uiExchange.ExchangeDialog). The subclass's constructor calls
self.nui_begin(), then the legacy constructor (whose loader call reaches the
subclass's override), then self.nui_end(). Facade gives the window:
- make()'s protocol: nui_ready() (the document loaded and the exe has the
  Wave 4 engine, nui_hud.has_engine_4()), nui_discard();
- the board on demand (nui_hud.OnDemand): made at Show, destroyed at Hide,
  every model key set from the facade's state at each make (_restore_board),
  so a refresh while hidden costs only the proxies' bookkeeping (D4);
- the place: PLACE None (the window sheet's place), "center", or a callable
  answering (x, y) in dp, at the first show; then where the player moved it
  (a centered window that was not moved is centered again, nui_hud.moved_place);
- Show (the board, then legacy's), Hide (legacy's, then the slot events'
  reset, then the board goes), SetTop (bring_to_front, then legacy's),
  Destroy (nui_discard, then legacy's), SetCenterPosition and SetPosition
  (the board's place, never the 0 x 0 legacy window's; legacy's
  SetCenterPosition forgets a place the player dragged it to, as legacy's
  centers the window again);
- OnUpdate = None and OnRender = None: the legacy window underneath stays
  shown while the board shows, and the C++ calls any callable OnUpdate or
  OnRender every frame (CWindow::OnUpdate); the per-frame distance rule is
  nuigame.WatchLeaveRange's (D5).

A board is a nui.Window with nui_hud.RaisesOnPress, defined in the window's
own controller module (lint NUI006 finds its @nui.on handlers there)."""

import nui
import nui_hud
import nui_limits


class Facade(object):
	"""The NovaUI half of a Wave 4 window (module docstring)."""

	NUI_FACADE = True
	# nui_hud.take_over's key: the window id. None for a window the Interface
	# makes several of at once (the equipment view, one per viewed player),
	# which no later instance takes over.
	KEY = None
	BOARD = None         # the board class (a nui.Window), made with (facade, model)
	PLACE = None         # None, "center", or a callable(facade) -> (x_dp, y_dp)

	OnUpdate = None
	OnRender = None

	# --- the lifecycle ------------------------------------------------------------------

	def nui_begin(self):
		"""First in the subclass's constructor, before the legacy one."""
		if self.KEY is not None:
			nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._state = self.nui_model()
		self._slot_events = []
		self._place = None
		self._centered = False
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_4():
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)

	def nui_end(self):
		"""Last in the subclass's constructor: whether a board loads."""
		if self.demand is not None:
			self.loaded = self.demand.probe()

	def nui_model(self):
		"""Every model key the board binds, with its first value."""
		return {}

	def nui_ready(self):
		return bool(self.loaded) and self.demand is not None and nui_hud.has_engine_4()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		if self.KEY is not None:
			nui_hud.forget(self.KEY, self)

	# --- the board ------------------------------------------------------------------------

	def nui_board(self):
		"""The board while shown, else None."""
		return self.demand.board() if self.demand is not None else None

	def nui_set(self, **values):
		"""Model keys: kept in the state, and set on the board when it shows."""
		self._state.update(values)
		board = self.nui_board()
		if board is not None:
			board.set(**values)

	def nui_events(self, events):
		"""Registers a nui_slots.LegacySlotEvents the window resets as its
		board goes (a board that goes sends its cells no mouseout)."""
		self._slot_events.append(events)
		return events

	def _make_board(self):
		return self.BOARD(self, self._state)

	def _restore_board(self, board):
		board.set(**self._state)
		if self._place is not None:
			board.set_position(self._place[0], self._place[1])
			return
		place = self.PLACE
		if place == "center":
			board.center()
		elif callable(place):
			x, y = place()
			board.set_position(x, y)

	def _keep_board(self, board):
		if self.PLACE == "center":
			self._place = nui_hud.moved_place(board)
			return
		box = board.element_box("")
		if box and box[2] > 0 and box[3] > 0:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def nui_on_hide(self):
		"""Before the board goes: the slot events forget the pointer."""
		for events in self._slot_events:
			events.reset()

	# --- the legacy window's calls -----------------------------------------------------

	def Show(self):
		if self.demand is not None:
			self.demand.show()
		super(Facade, self).Show()

	def Hide(self):
		super(Facade, self).Hide()
		if self.IsShow():
			return
		self.nui_on_hide()
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.nui_board()
		if board is not None:
			board.bring_to_front()
		super(Facade, self).SetTop()

	def Destroy(self):
		self.nui_discard()
		super(Facade, self).Destroy()

	def SetCenterPosition(self, x=0, y=0):
		"""Legacy's centering, on the board: the kept place is forgotten and a
		shown board is centered (a hidden one is at its next show, through
		PLACE); the 0 x 0 legacy window stays put."""
		self._place = None
		board = self.nui_board()
		if board is not None:
			board.center()

	def SetPosition(self, x, y):
		"""Legacy's pixels as the board's place in dp."""
		scale = nui.get_scale() or 1.0
		self._place = (x / scale, y / scale)
		board = self.nui_board()
		if board is not None:
			board.set_position(self._place[0], self._place[1])


class DialogFacade(Facade):
	"""A Wave 4 modal input dialog (D12: the guild's grade name dialog, the
	war declare and accept dialogs): the scrim centers its board at each show
	(legacy's own place, a SetPosition or SetCenterPosition, moves nothing),
	and its fields are nui_form_proxies.FieldProxys whose text, focus and limit
	reach the document and whose GetText reads the document's field. The
	window lists its fields in _fields(); a field's limit goes to the model
	key that _field() was given."""

	def _value(self, field_id):
		board = self.nui_board()
		return board.get_value(field_id) if board is not None and board.is_visible() else None

	def _field(self, field_id, maximum, max_key=None):
		import nui_form_proxies
		field = nui_form_proxies.FieldProxy(field_id, self._on_field)
		field.max_key = max_key
		field.reader = lambda: self._value(field_id)
		field.SetMax(maximum)
		return field

	def _fields(self):
		return ()

	def _on_field(self, field, what):
		if what == "max":
			if getattr(field, "max_key", None):
				self.nui_set(**{field.max_key: int(field.max)})
			return
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			board.set_value(field.field_id, field.text, caret="end")
		elif what == "focus":
			board.focus(field.field_id)

	def _keep_board(self, board):
		"""Before the board goes: each field's text (legacy's edit line keeps
		its text while hidden, and legacy reads it after its Hide, as the
		guild's OnChangeGradeName does). No place: the scrim centers the
		dialog at each show."""
		for field in self._fields():
			value = board.get_value(field.field_id)
			if isinstance(value, str):
				field.text = value

	def SetPosition(self, x, y):
		"""Nothing: the scrim centers the dialog."""

	def SetCenterPosition(self, x=0, y=0):
		"""Nothing: the scrim centers the dialog."""

	def Show(self):
		Facade.Show(self)
		board = self.nui_board()
		if board is None:
			return
		# The fields as legacy left them (a text set while hidden), and the
		# focus legacy gave before the show (Open).
		for field in self._fields():
			if field.text:
				board.set_value(field.field_id, field.text, caret="end")
		for field in self._fields():
			if field.focused:
				board.focus(field.field_id)
				break
