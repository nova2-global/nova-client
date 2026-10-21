"""What the NovaUI HUD facades share (docs/ui/AUTHORING.md "HUD windows").

A HUD facade is a plain class with the legacy class's name, constructor and
methods (nui_taskbar.TaskBar for uiTaskBar.TaskBar), made by
nui_windows.make() where the Interface and the game window make the legacy
one. Its document is a nui.Window board that loads hidden in the facade's
constructor; the facade answers nui_ready() and nui_discard() for make(),
and carries NUI_FACADE = True, which the Interface and game.py wiring use to
touch only NovaUI objects. No facade runs Python per frame: it acts on the
Interface's calls, the C++ callbacks that reach it and its document's
events, and fed model keys (nui.Window.FEEDS) carry what changes in between."""

import sys
import weakref

import ui

import nui

_facades = {}  # key -> the facade made last under it


def has_engine():
	"""True when the exe has the Wave 2a engine: the nuigame module and
	_nui.BindFeed. A facade's nui_ready() is False without it, so make()
	keeps the legacy window on an older exe."""
	if sys.modules.get("nuigame") is None:
		try:
			import nuigame  # noqa: F401
		except ImportError:
			return False
	return getattr(getattr(nui, "_nui", None), "BindFeed", None) is not None


def has_engine_2b():
	"""True when the exe has the Wave 2b engine as well: nuigame's chat,
	view and anchor functions. A Wave 2b facade's nui_ready() is False
	without it, so make() keeps the legacy window on an older exe."""
	if not has_engine():
		return False
	nuigame = sys.modules.get("nuigame")
	return all(getattr(nuigame, name, None) is not None for name in ("ChatAttach", "ViewState", "AnchorState"))


def has_engine_3a():
	"""True when the exe has the Wave 3a engine as well: nuigame.NuiStats.
	Only the chat's closed view needs it (nui-chat-lines mode="off"); the
	Wave 3a windows need has_engine() alone."""
	if not has_engine_2b():
		return False
	return getattr(sys.modules.get("nuigame"), "NuiStats", None) is not None


def has_engine_5a():
	"""True when the exe has the Wave 5a engine as well: nuigame.QuestAttach,
	QuestState and WebPageFollow (P12 spec 3.4, 6.4). The quest dialog and the
	web window need it; the guild building window and the console need
	has_engine() alone."""
	if not has_engine_3a():
		return False
	nuigame = sys.modules.get("nuigame")
	return all(getattr(nuigame, name, None) is not None for name in ("QuestAttach", "QuestState", "WebPageFollow"))


def has_engine_3b():
	"""True when the exe has the Wave 3b engine as well (P14 spec 4.9.4):
	_nui.FollowPointer (pointer placement, the marker) and the nui-cells
	decorator (nui.has_decorator). Every Wave 3b facade's nui_ready() needs
	it, so make() keeps the legacy window on an older exe."""
	if not has_engine():
		return False
	if getattr(getattr(nui, "_nui", None), "FollowPointer", None) is None:
		return False
	has = getattr(nui, "has_decorator", None)
	return has is not None and bool(has("nui-cells"))


def has_engine_4():
	"""True when the exe has the Wave 4 engine as well (P16 spec 4.3, 7.5):
	nuigame.WatchLeaveRange (the trade windows' distance rule),
	nuigame.WhisperAttach (the whisper lines) and _nui.LoadDocumentAs (the
	instanced documents). Every Wave 4 facade's nui_ready() needs it, so
	make() keeps the legacy window on an older exe."""
	if not has_engine_3b():
		return False
	nuigame = sys.modules.get("nuigame")
	if any(getattr(nuigame, name, None) is None for name in ("WatchLeaveRange", "WhisperAttach")):
		return False
	return getattr(getattr(nui, "_nui", None), "LoadDocumentAs", None) is not None


def take_over(key, facade):
	"""Destroys the NovaUI parts of the previous facade registered under `key`
	if they are still alive (a phase that ended without Destroy, D26), then
	records `facade`. Each module calls it first in its constructor."""
	previous = _facades.get(key)
	if previous is not None and previous is not facade:
		discard = getattr(previous, "nui_discard", None)
		if discard is not None:
			discard()
	_facades[key] = facade


def forget(key, facade):
	"""Destroy() and nui_discard() call it: drops the record when it is this
	facade's."""
	if _facades.get(key) is facade:
		del _facades[key]


def current(key):
	"""The facade registered under `key`, or None."""
	return _facades.get(key)


class _EscapeWindow(ui.Window):
	"""The legacy window behind an EscapeProxy: 0 x 0, so never picked."""

	def __init__(self, action, layer="UI", exit_action=None):
		ui.Window.__init__(self, layer)
		self.SetWindowName("NuiEscapeProxy")
		self._action = action
		self._exit_action = exit_action

	def __del__(self):
		ui.Window.__del__(self)

	def OnPressEscapeKey(self):
		action = self._action
		if action is not None:
			action()
		return True

	def OnPressExitKey(self):
		action = self._exit_action
		if action is None:
			return False
		action()
		return True


def _mem_func(action):
	"""A bound method as a weak ui.__mem_func__, so a proxy keeps no facade
	alive; anything else as given."""
	mem_func = getattr(ui, "__mem_func__", None)
	if mem_func is not None and hasattr(action, "__self__"):
		return mem_func(action)
	return action


class EscapeProxy(object):
	"""A 0 x 0 legacy ui.Window, shown while its NovaUI window is shown, whose
	OnPressEscapeKey runs `action` (None: nothing) and returns True. It keeps
	the window's place in the legacy Escape chain
	(CWindow::RunPressEscapeKeyEvent, PythonWindow.cpp:643-659), so Escape
	acts in the legacy order whatever NovaUI document has the focus. It is
	never picked (no area).

	`layer` is the proxy's legacy layer, "UI" (the default) or "TOP_MOST":
	the chain walks each layer's children last first, and the TOP_MOST
	layer before the UI layer, so a TOP_MOST proxy comes before every
	UI-layer window, as a legacy TOP_MOST window would. `exit_action`, when
	given, is run by the proxy's OnPressExitKey, which then returns True
	(the window's close button and WM_CLOSE reach it through
	CWindowManager::RunPressExitKey, PythonWindowManager.cpp:1486-1500);
	without it the proxy returns False there and the exit key goes on.
	`action` and `exit_action` are held as weak methods (ui.__mem_func__)
	when they are bound methods."""

	def __init__(self, action, layer="UI", exit_action=None):
		self._window = _EscapeWindow(_mem_func(action), layer, _mem_func(exit_action))
		self._window.SetSize(0, 0)
		self._window.Hide()

	def show(self):
		if self._window is not None:
			self._window.Show()
			self._window.SetTop()

	def hide(self):
		if self._window is not None:
			self._window.Hide()

	def is_shown(self):
		return self._window is not None and bool(self._window.IsShow())

	def destroy(self):
		window, self._window = self._window, None
		if window is not None:
			window.Hide()
			window._action = None
			window._exit_action = None
			window.Destroy()


class RaisesOnPress(object):
	"""For the board (a nui.Window) of a legacy window whose uiscript makes it
	"float": legacy's window manager raises the UI-layer window under the
	pointer on every left and right press, before the press reaches it
	(CWindowManager::RunMouseLeftButtonDown and RunMouseRightButtonDown call
	SetTopUIWindow, PythonWindowManager.cpp:704-719). The raise puts the window
	first in the Escape chain and above the windows it overlaps, and runs its
	OnTop. A NovaUI board takes the press, so it raises its window itself:
	every mousedown handler of the board calls raise_for(button) before it
	acts, and the body's own mousedown (board_press, which RmlUi runs last as
	the press bubbles; each board's @nui.on("board_press") calls
	body_pressed(button)) raises only when no handler did, so a press that
	opens a dialog leaves that dialog above. The board's `_owner` is the
	window, whose SetTop raises the board and the legacy window (the window
	adds the "float" flag its uiscript gave legacy's, P14 V-1)."""

	_raised = False

	def raise_for(self, button):
		if button not in (0, 1) or self._raised:
			return
		self._raised = True
		self._owner.SetTop()

	def body_pressed(self, button):
		if self._raised:
			self._raised = False
			return
		if button in (0, 1):
			self._owner.SetTop()


def _weak(method):
	"""A bound method held weakly (its object may go first), else as given."""
	if method is None or not hasattr(method, "__self__"):
		return method
	ref = weakref.WeakMethod(method)

	def call():
		target = ref()
		if target is not None:
			target()
	return call


def _weak_fn(fn):
	"""A bound method held weakly, returning its result (None once its
	object went); anything else as given."""
	if fn is None or not hasattr(fn, "__self__"):
		return fn
	ref = weakref.WeakMethod(fn)

	def call(*args):
		target = ref()
		if target is None:
			return None
		return target(*args)
	return call


class OnDemand(object):
	"""A board (a nui.Window) that exists only while its window is shown:
	made at show(), destroyed at hide(), because RmlUi updates every loaded
	document each frame, shown or not. make() makes a new board; restore(board)
	runs after each make, to set the board's model and place from the
	facade's state; keep(board) runs before each destroy, to read back what
	the document holds (a moved window's place: element_box of its body).
	All three are held weakly when they are bound methods (the facade owns
	the OnDemand)."""

	def __init__(self, make, restore=None, keep=None):
		self._make = _weak_fn(make)
		self._restore = _weak_fn(restore)
		self._keep = _weak_fn(keep)
		self._board = None

	def _new(self):
		make = self._make
		if make is None:
			return None
		return make()

	def probe(self):
		"""Makes one board and destroys it: True when its document loaded. A
		board that is shown now answers for itself and stays."""
		if self._board is not None:
			return bool(self._board._doc)
		board = self._new()
		if board is None:
			return False
		loaded = bool(board._doc)
		board.destroy()
		return loaded

	def board(self):
		"""The board while shown, else None."""
		return self._board

	def show(self):
		"""Makes the board if there is none (then restore(board)), then shows
		it. True when it is shown; a board whose document did not load is
		destroyed again, and nothing shows."""
		board = self._board
		if board is None:
			board = self._new()
			if board is None:
				return False
			if not board._doc:
				board.destroy()
				return False
			self._board = board
			if self._restore is not None:
				self._restore(board)
			if self._board is not board:
				# restore() hid it again (a caller's Hide inside it).
				return False
		return bool(board.show())

	def hide(self):
		"""keep(board), then destroys it; nothing when there is none."""
		board = self._board
		if board is None:
			return
		self._board = None
		if self._keep is not None:
			self._keep(board)
		board.destroy()

	def is_shown(self):
		return self._board is not None and bool(self._board.is_visible())

	def destroy(self):
		"""hide() and forgets the callbacks."""
		self.hide()
		self._make = self._restore = self._keep = None


class LayoutCalls(object):
	"""The ui.ScriptWindow layout calls callers make on a Wave 3a facade
	(P11 spec 6.0.2): CSS places the window, so SetCenterPosition, Lock and
	Unlock do nothing (a modal replaces the lock), and GetWidth and GetHeight
	answer the shown board's box in pixels (0 while hidden). A facade keeps
	its OnDemand in `demand`."""

	demand = None

	def _box(self):
		board = self.demand.board() if self.demand is not None else None
		box = board.element_box("") if board is not None and board.is_visible() else None
		return box or (0, 0, 0, 0)

	def SetCenterPosition(self, x=0, y=0):
		pass

	def Lock(self):
		pass

	def Unlock(self):
		pass

	def GetWidth(self):
		return int(round(self._box()[2]))

	def GetHeight(self):
		return int(round(self._box()[3]))


def moved_place(board):
	"""The board's top left in dp when the player moved it away from the
	place the runtime centers it at (a handle drag), else None: a window
	that was centered is centered again at its next show. For OnDemand's
	keep(). The centered place is the runtime's (NuiRuntime's Center
	placement): a board wider or taller than the screen sits at 0 on that
	axis, so a board too tall for the screen at a large scale still counts
	as centered."""
	box = board.element_box("")
	if not box:
		return None
	import wndMgr
	x, y, width, height = box
	screen_width = wndMgr.GetScreenWidth()
	screen_height = wndMgr.GetScreenHeight()
	center_x = 0.0 if width > screen_width else (screen_width - width) / 2.0
	center_y = 0.0 if height > screen_height else (screen_height - height) / 2.0
	if abs(x - center_x) <= 2 and abs(y - center_y) <= 2:
		return None
	s = nui.get_scale() or 1.0
	return (x / s, y / s)


def keep_weakly(owner):
	"""A weak proxy to a board's facade (the owner rule: a board never keeps
	its facade alive); an object that takes no weak reference as it is."""
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def _call(method):
	"""A weak method whose owner is gone does nothing."""
	if method is None:
		return
	try:
		method()
	except ReferenceError:
		pass


# FocusProxy.take() calls in progress. While another proxy takes wndMgr's
# focus, NovaUI's focus already sits on that proxy's field (RmlUi keeps one
# focus), so the proxy that loses wndMgr's focus must not move NovaUI's.
_taking = [0]


class _FocusWindow(ui.Window):
	"""The legacy window behind a FocusProxy: 0 x 0, so never picked. wndMgr
	calls OnKillFocus when another window takes its focus
	(CWindowManager::ActivateWindow) and OnSetFocus when it gives it back
	(DeactivateWindow); OnKeyDown passes every key on to the root window,
	as a legacy edit line passes the game keys it does not keep. A
	FocusProxy.take() of another proxy runs no `on_lost` here."""

	def __init__(self, on_lost, on_gained):
		ui.Window.__init__(self, "UI")
		self.SetWindowName("NuiFocusProxy")
		self._on_lost = on_lost
		self._on_gained = on_gained
		self._quiet = False

	def __del__(self):
		ui.Window.__del__(self)

	def OnKillFocus(self):
		if not self._quiet and not _taking[0]:
			_call(self._on_lost)

	def OnSetFocus(self):
		if not self._quiet:
			_call(self._on_gained)

	def OnKeyDown(self, key):
		return False


class FocusProxy(object):
	"""A 0 x 0 legacy ui.Window in the UI layer that holds wndMgr's focus
	while a NovaUI text field has NovaUI's, as a focused legacy edit line
	would hold it (ui.EditLine.SetFocus). Legacy code that asks whether the
	game window has the focus (game.py CheckFocus, :1112-1117) then answers
	as it would with the legacy chat: a world press closes the chat. When a
	legacy edit line takes wndMgr's focus, the proxy's OnKillFocus runs
	`on_lost` (the facade moves NovaUI's focus off its field); when wndMgr
	gives the focus back (the window that took it closed,
	PythonWindowManager.cpp:670-689), its OnSetFocus runs `on_gained` (the
	facade focuses its field again). Its OnKeyDown returns False, so the
	keys the host lets through while typing (F1 to F4, left Alt, Print
	Screen, left Ctrl) reach the game window as through a legacy edit line.
	Never picked (no area); `on_lost` and
	`on_gained` are held as weak methods; neither runs for take() and
	release() themselves, and `on_lost` does not run when another proxy
	takes the focus: its field already has NovaUI's (the chat window and
	the chat log each own one)."""

	def __init__(self, on_lost, on_gained):
		self._window = _FocusWindow(_weak(on_lost), _weak(on_gained))
		self._window.SetSize(0, 0)
		self._window.Show()

	def _quietly(self, call):
		window = self._window
		window._quiet = True
		try:
			call()
		finally:
			window._quiet = False

	def take(self):
		"""wndMgr.SetFocus on the proxy, unless it has it."""
		window = self._window
		if window is None or window.IsFocus():
			return
		_taking[0] += 1
		try:
			self._quietly(window.SetFocus)
		finally:
			_taking[0] -= 1

	def release(self):
		"""wndMgr.KillFocus on the proxy, when it has it; on_lost does not run."""
		window = self._window
		if window is None or not window.IsFocus():
			return
		self._quietly(window.KillFocus)

	def has_focus(self):
		return self._window is not None and bool(self._window.IsFocus())

	def destroy(self):
		self.release()
		window, self._window = self._window, None
		if window is not None:
			window._on_lost = None
			window._on_gained = None
			window.Hide()
			window.Destroy()


def locale_text(name, *args):
	"""localeInfo.<name>, called with args when it is a function (an SA or
	SNA entry; with no args it gets 0, which an SNA entry ignores), then
	nui.plain_text(); "" for a missing entry or one that does not format."""
	try:
		import localeInfo
	except ImportError:
		return ""
	value = getattr(localeInfo, name, None)
	if value is None:
		return ""
	if callable(value):
		try:
			value = value(*args) if args else value(0)
		except Exception:
			return ""
	return nui.plain_text(value)


# --- Wave 3c (P15) ---

def has_engine_3c():
	"""True when the exe has the Wave 3c engine as well (P15 spec 11.2 E2):
	nuigame.QuestIconFileName, the quest icon's file, which the character
	window's quest rows need. Every Wave 3c window's nui_ready() needs it,
	so make() keeps the legacy window on an older exe."""
	if not has_engine_3b():
		return False
	return getattr(sys.modules.get("nuigame"), "QuestIconFileName", None) is not None


class KeptBoard(OnDemand):
	"""OnDemand whose board is kept, hidden, after its first show (P15 V-2,
	spec 8.1): a window opened often (the inventory, with its costume and
	belt) then loads its document once, not at every open. The first show()
	makes the board (as OnDemand), runs restore(board) and shows it; hide()
	runs keep(board), then empty(board), which empties the document's lists
	so the hidden document holds only its frame (RmlUi updates every loaded
	document each frame), then hides it; a later show() runs restore(board),
	which sets the lists again, and shows it, with no load. board() answers
	the board only while it shows, so a window's model writes while hidden
	stay in its state and restore() sets them at the next show, as with
	OnDemand. probe() makes and destroys a board, as OnDemand's: nothing is
	loaded before the first open. destroy() (the window's Destroy, at the
	phase's end) unloads it. The callbacks are held weakly when they are
	bound methods."""

	def __init__(self, make, restore=None, keep=None, empty=None):
		OnDemand.__init__(self, make, restore, keep)
		self._empty = _weak_fn(empty)
		self._kept = None

	def loaded(self):
		"""True while the board exists, shown or kept hidden."""
		return self._board is not None or self._kept is not None

	def kept(self):
		"""The board while it is kept hidden, else None (tests, benches)."""
		return self._kept

	def probe(self):
		board = self._board or self._kept
		if board is not None:
			return bool(board._doc)
		return OnDemand.probe(self)

	def show(self):
		board = self._kept
		if board is None:
			return OnDemand.show(self)
		self._kept = None
		self._board = board
		if self._restore is not None:
			self._restore(board)
		if self._board is not board:
			# restore() hid it again (a caller's Hide inside it).
			return False
		return bool(board.show())

	def hide(self):
		board = self._board
		if board is None:
			return
		self._board = None
		if self._keep is not None:
			self._keep(board)
		if self._empty is not None:
			self._empty(board)
		board.hide()
		self._kept = board

	def destroy(self):
		"""Unloads the board, shown or kept, and forgets the callbacks."""
		shown, board = self._board, self._board or self._kept
		self._board = self._kept = None
		if board is not None:
			# A kept board's place was read at its hide.
			if shown is not None and self._keep is not None:
				self._keep(board)
			board.destroy()
		self._make = self._restore = self._keep = self._empty = None


class _NoOwner(object):
	"""The owner of a board that waits in a BoardPool (P18): every attribute
	is itself and every call does nothing, so an event that still reaches a
	waiting board (a binding's change as it is emptied) acts on no window."""

	def __getattr__(self, name):
		return self

	def __call__(self, *args, **kwargs):
		return None

	def __bool__(self):
		return False


NO_OWNER = _NoOwner()


class Pooled(object):
	"""For a board a PooledBoard holds (P18), with RaisesOnPress's `_owner`:
	adopt(owner) gives a waiting board its new window; release() takes the
	window away (NO_OWNER), empties its text fields (FIELDS, hidden ones too:
	set_value's even_hidden) and, while the board still shows, parks the
	focus on PARK (a control that takes no keys), so a board that waits keeps
	nothing a player typed, and the next show gives no field the focus legacy
	did not ask for."""

	FIELDS = ()
	PARK = None

	def adopt(self, owner):
		self._owner = keep_weakly(owner)
		self._raised = False

	def release(self):
		self._owner = NO_OWNER
		self._raised = False
		for field in self.FIELDS:
			self.set_value(field, "", even_hidden=True)
		if self.PARK and self.is_visible():
			self.focus(self.PARK)


# The pools by name, for pool_stats() and drain_pools().
_pools = {}


class BoardPool(object):
	"""Hidden boards of one board class that wait for the next window of that
	class (P18): a window made again at each open (the war declare dialog),
	or one of several at once (the whisper dialogs, the equipment views),
	takes a waiting board instead of loading its document. At most `bound`
	boards wait; a board put back while the pool is full is destroyed.
	drain() destroys the waiting boards (the phase's end, drain_pools())."""

	def __init__(self, name, bound):
		self.name = str(name)
		self.bound = max(0, int(bound))
		self._boards = []
		self.loads = 0       # documents loaded for the pool's windows
		self.reuses = 0      # shows that took a waiting board
		self.most = 0        # the most boards that ever waited at once
		_pools[self.name] = self

	def __len__(self):
		return len(self._boards)

	def boards(self):
		return list(self._boards)

	def take(self):
		"""The board that waited last, or None."""
		while self._boards:
			board = self._boards.pop()
			if board._doc:
				self.reuses += 1
				return board
		return None

	def put(self, board):
		"""True when the board waits; one over the bound is destroyed."""
		if board is None:
			return False
		if any(waiting is board for waiting in self._boards):
			return True
		if not board._doc or len(self._boards) >= self.bound:
			board.destroy()
			return False
		self._boards.append(board)
		self.most = max(self.most, len(self._boards))
		return True

	def drain(self):
		"""Destroys every waiting board; how many there were."""
		boards, self._boards = self._boards, []
		for board in boards:
			board.destroy()
		return len(boards)


def drain_pools():
	"""Every pool's waiting boards go (nui_facade.end_phase(), at each phase
	change: RmlUi updates every loaded document each frame). How many."""
	return sum(pool.drain() for pool in list(_pools.values()))


def pool_stats():
	"""{name: {"waiting", "bound", "most", "loads", "reuses"}} of every pool
	(dev tools, the kit's memory runs, tests)."""
	return dict((name, {"waiting": len(pool), "bound": pool.bound, "most": pool.most,
	                    "loads": pool.loads, "reuses": pool.reuses})
	            for name, pool in _pools.items())


class PooledBoard(OnDemand):
	"""OnDemand whose boards come from a BoardPool and go back to it (P18):
	show() takes a waiting board (adopt(board), the window's, then
	restore(board)) or makes one; hide() runs keep(board), empty(board)
	(the window's lists, as KeptBoard's) and the board's own release(), hides
	it and puts it back in the pool, where it waits for the next window of
	its class. A hidden window holds no board, so the pool's bound counts
	every hidden one. probe() makes no board while one waits, and a board it
	makes waits in the pool for the show that follows, so a first open loads
	the document once. destroy() (the window's Destroy, a facade collected)
	is hide() for good. The callbacks are held weakly when they are bound
	methods."""

	def __init__(self, pool, make, restore=None, keep=None, empty=None, adopt=None):
		OnDemand.__init__(self, make, restore, keep)
		self._pool = pool
		self._empty = _weak_fn(empty)
		self._adopt = _weak_fn(adopt)

	def pool(self):
		return self._pool

	def _new(self):
		if self._make is None:
			# Destroyed: the waiting boards are the next window's.
			return None
		board = self._pool.take()
		if board is not None:
			if self._adopt is not None:
				self._adopt(board)
			return board
		board = OnDemand._new(self)
		if board is not None and board._doc:
			self._pool.loads += 1
		return board

	def probe(self):
		if self._board is not None:
			return bool(self._board._doc)
		if self._make is None:
			return False
		if len(self._pool):
			return True
		board = OnDemand._new(self)
		if board is None:
			return False
		if not board._doc:
			board.destroy()
			return False
		self._pool.loads += 1
		self._wait(board)
		return True

	def _wait(self, board):
		release = getattr(board, "release", None)
		if release is not None:
			release()
		board.hide()
		self._pool.put(board)

	def hide(self):
		board = self._board
		if board is None:
			return
		self._board = None
		if self._keep is not None:
			self._keep(board)
		if self._empty is not None:
			self._empty(board)
		self._wait(board)

	def destroy(self):
		OnDemand.destroy(self)
		self._empty = self._adopt = None


# P15 fix stage (VF-1): the order of the boards below the legacy UI band.
# Legacy's window manager keeps one order in the UI layer: SetTop moves a
# window to the top, and Show only shows it where it stands
# (CWindow::Show). A NovaUI board loaded or shown at a Show draws above every
# other document instead, so a window shown by a press on another (the
# inventory's dragon soul button: the press raised the inventory first,
# SetTopUIWindow) covered the window the press had just raised.
_raises = weakref.WeakKeyDictionary()   # window -> the number of its last SetTop
_raise_count = [0]


def note_raise(window):
	"""A board's window was raised (its SetTop): remembered, so a board that
	shows later without a raise of its own stays below it (keep_order)."""
	_raise_count[0] += 1
	_raises[window] = _raise_count[0]


def keep_order(window):
	"""After `window`'s board loads or shows at a Show that raises nothing,
	brings back above it, oldest first, the shown boards of every window
	raised since `window`'s own last SetTop: the windows legacy's UI layer
	keeps above it. A window that was never raised counts as raised before
	every other. Returns how many boards it raised."""
	mine = _raises.get(window, 0)
	later = sorted((seq, index, other) for index, (other, seq) in enumerate(list(_raises.items()))
	               if other is not window and seq > mine)
	raised = 0
	for _, _, other in later:
		demand = getattr(other, "demand", None)
		board = demand.board() if demand is not None and other.IsShow() else None
		if board is not None and board.bring_to_front():
			raised += 1
	return raised
