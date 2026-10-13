"""Python side of the NovaUI (RmlUi) windows.

A window is one RmlUi document (.rml + .rcss) plus an optional data model and
a controller class in root/nui_<name>.py, with each hyphen in the window name
written as an underscore (window item-shop: root/nui_item_shop.py, imported
as nui_item_shop):

    import nui

    class InventoryWindow(nui.Window):
        DOCUMENT = "nui/windows/inventory/inventory.rml"
        MODEL = "inventory"          # data-model="inventory" in the document

        def initial_model(self):     # every top-level key, with its first value
            return {"slots": [], "money": 0}

        @nui.on("use")               # data-event-click="use(slot.index)"
        def on_use(self, index):
            net.SendItemUsePacket(index)

        def refresh(self):
            self.set(slots=[{"index": i, "icon": "..."} for i in range(90)])

Rules (docs/ui/AUTHORING.md has the full list):
  * Python runs only on events and when you call set(); never per frame.
  * The kind of each model key (scalar, list, map) is fixed by
    initial_model(); set() with a different kind fails and logs. Writes
    from the document (data-value, data-checked, an assignment in a
    data-event) keep a scalar key's type: an int key stays an int (a
    fraction is cut toward zero), and text that does not read as a number
    of that type leaves the key as it was. A None key takes the first type
    written to it. A text field bound to a number key shows the number as
    RmlUi prints it after each accepted keystroke; bind free-form text to a
    str key and convert in Python.
  * Handlers get the evaluated data-event arguments as Python scalars: int,
    float, str, bool or None. A whole number arrives as an int, including
    literals and arithmetic (use(3) and use(slot.index + 1) pass an int);
    other numbers arrive as float. A list or map argument arrives as its
    length or member count, with no warning, so pass its members:
    use(slot.index), not use(slot). Event parameters that are not scalars
    (ev.drag_element) arrive as None.
  * Handlers also run for changes the model causes, not only for input: a
    bound checkbox, radio, select or slider sends change when set() or a
    (re-)load moves it. On the first load that happens inside __init__
    (see there). Apply ev.checked or ev.value idempotently; do not toggle,
    resend a packet or open a window from such a handler.
  * After a hot reload or a locale change the document is re-loaded in place:
    element handlers registered with element_on() are re-attached for you,
    the @nui.on handlers get the new document's own events (its load, change
    from bindings), then on_reload() runs. The replaced document's events
    (its unload, a mouseout as it leaves) reach none of your handlers.
  * Model keys (initial_model()) and event names (@on) are letters, digits
    and _, start with a letter, and are none of it, it_index, ev, true,
    false, size and literal, in any case. RmlUi refuses the rest: a refused
    key leaves the whole window unavailable (syserr names the key), and on()
    raises ValueError for such an event name. Nested list and map members
    are not restricted.
  * Model strings shown with {{ }} are translated like markup text, so an
    @ui.KEY or @game.KEY inside one is replaced. Never bind text another
    player wrote (chat, names, shop signs, mail) through {{ }} as it is.
    Model strings are always text, never markup: the runtime refuses
    data-rml.
  * A key the class names in FEEDS follows a C++ feed (nui.feed): the game
    publishes the value (player.hp, quickslot.slots) and the key takes it
    once per frame, with no Python. Times that nui-frames, nui-cooldown and
    nui-countdown read are seconds of nui.now().
  * Text with the legacy color and link tags (|c, |r, |H ... |h ... |h)
    that players or game data wrote goes into a <nui-text> element's value
    (or reaches a chat lines element through its feed): it is shown as
    written, never translated or parsed. A press on a link sends "nuilink"
    with ev.link (data-event-nuilink).
  * A window lives until destroy(): the runtime holds its handlers, so
    dropping the last reference does not close it. Only one window per MODEL
    name can exist at a time.
  * destroy() inside one of the window's own handlers (a close button) hides
    it at once; the document and model go by the end of the frame. From
    destroy() on, the document's own events (a mouseout as it hides, its
    unload) reach none of its handlers, so a window made again in its own
    handler keeps the model.
  * Keys: a NovaUI window gets keys only while one of its text fields has
    the focus, while a modal (MODAL = True) is shown, or while the focus is
    on a control the player reached with Tab; Escape reaches the focused
    window first in any case. An element_on("", "keydown", fn) handler that
    returns exactly True keeps the key: an Escape then does not also reach
    the legacy UI. KEY_ESCAPE, KEY_RETURN, KEY_NUMPADENTER, KEY_TAB and
    KEY_SPACE are the key_identifier values.

The C++ module `_nui` (src/NovaUI/Python) is the only thing this file calls;
when it is missing (plain Python outside the client) or no runtime is active
(NovaUI failed to start or has shut down, or a test started none)
is_available() is False and every Window method is a no-op that returns a
falsy value. A headless runtime (NOVA_UI_HEADLESS, or a test's null
renderer) is active, so there is_available() is True and windows work.
"""

try:
	import _nui
except ImportError:  # pragma: no cover - client builds always have it
	_nui = None


# Theme ids are lowercase letters, digits and '-', at most 31 characters
# (UI_THEME). The first theme of nui/theme/themes.json is the default.
_THEME_DEFAULT = "modern-dark"
_THEME_LEGACY = {"dark": "modern-dark", "light": "modern-light"}
_THEME_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_THEME_ID_MAX = 31
_SCALE_MIN_PERCENT = 75
_SCALE_MAX_PERCENT = 200
_RESERVED_NAMES = ("it", "it_index", "ev", "true", "false", "size", "literal")
_SIDES = ("left", "right", "above", "below")
_CARETS = ("end", "start", "keep")
_WORD_JOINER = "\u2060"

# RmlUi's key identifiers, as ev["key_identifier"] of a key event carries
# them. `_nui` exports RmlUi's own values; the numbers here are the same, for
# Python run without the client.
KEY_ESCAPE = getattr(_nui, "KEY_ESCAPE", 81)
KEY_RETURN = getattr(_nui, "KEY_RETURN", 72)
KEY_NUMPADENTER = getattr(_nui, "KEY_NUMPADENTER", 61)
KEY_TAB = getattr(_nui, "KEY_TAB", 70)
KEY_SPACE = getattr(_nui, "KEY_SPACE", 1)

# Open windows by document id, so a re-load reaches the right on_reload().
_windows = {}


def is_available():
	"""True when the `_nui` module is present and a runtime is active (the
	client's, headless or not)."""
	return _nui is not None and bool(_nui.IsAvailable())


def enabled_for_locale():
	"""False for locales NovaUI cannot render yet (right-to-left scripts), so
	callers keep the legacy window there."""
	try:
		import app
	except ImportError:
		return True
	is_rtl = getattr(app, "IsRTL", None)
	return not (is_rtl is not None and is_rtl())


def any_window_shown():
	"""True while a window made through Window is shown. The legacy common
	dialogs ask this when they open (nui_windows.legacy_dialog_layer)."""
	return any(window.is_visible() for window in list(_windows.values()))


def plain_text(text):
	"""`text` safe to show with {{ }}: a U+2060 WORD JOINER (zero width) after
	every "@", so text from game data or another player can never name a
	locale key (@ui.KEY, @game.KEY). It looks the same. None reads as ""."""
	if text is None:
		return ""
	if not isinstance(text, str):
		text = str(text)
	return text.replace("@", "@" + _WORD_JOINER)


def now():
	"""The NovaUI clock in seconds, the one nui-frames, nui-cooldown and
	nui-countdown read: a time written into a model for them (a cooldown's
	start and end, an affect's end) is now() plus seconds. 0.0 without a
	runtime."""
	if not is_available():
		return 0.0
	return float(_nui.Now())


def feed(name):
	"""The value C++ published last under this feed name ("player.hp"; the
	list is in src/UserInterface/NuiGameFeeds.h), or None."""
	if _nui is None:
		return None
	return _nui.FeedGet(name)


def _is_legal_name(name):
	"""RmlUi's rule for model keys and data-event names."""
	if not name or not ("a" <= name[0].lower() <= "z"):
		return False
	for c in name.lower():
		if not (c == "_" or "a" <= c <= "z" or "0" <= c <= "9"):
			return False
	return name.lower() not in _RESERVED_NAMES


def on(event_name):
	"""Method decorator: the method handles data-event `event_name` of the
	window's model and is called with the evaluated arguments.

	One method may carry several @on decorators. A subclass that overrides a
	decorated method without repeating the decorator still receives the
	event; a subclass method decorated for the same event name wins over the
	base class one.

	The name follows RmlUi's rule (letters, digits and _, starting with a
	letter; not it, it_index, ev, true, false, size or literal, in any case);
	another one raises ValueError. A data-event handler cannot stop an event;
	to keep a key, use element_on() and return True."""
	if not isinstance(event_name, str) or not event_name:
		raise TypeError("nui.on() takes the data-event name as a non-empty str")
	if not _is_legal_name(event_name):
		raise ValueError("nui.on(%r): a data-event name is letters, digits and _, starts with a letter, "
			"and is not one of %s" % (event_name, ", ".join(_RESERVED_NAMES)))

	def mark(method):
		method._nui_events = getattr(method, "_nui_events", ()) + (event_name,)
		return method

	return mark


def _event_methods(cls):
	"""{event name: method name} over cls and its bases, subclasses last so
	they win."""
	found = {}
	for klass in reversed(cls.__mro__):
		for name, attr in vars(klass).items():
			for event_name in getattr(attr, "_nui_events", ()):
				found[event_name] = name
	return found


def _on_document_reloaded(doc):
	window = _windows.get(doc)
	if window is not None:
		window.on_reload()


def _prepare_runtime():
	"""Before a window loads: the reload hook, and the string tables once per
	runtime so @ui.KEY / @game.KEY resolve in its first document."""
	_nui.SetReloadHandler(_on_document_reloaded)
	if not _nui.HasStrings():
		refresh_strings()


class Window(object):
	"""One document plus its data model and handlers. Subclass per window."""

	DOCUMENT = None   # asset path of the .rml (required)
	MODEL = None      # data model name the document binds to, or None
	MODAL = False     # show() as a modal document
	FEEDS = {}        # model key -> C++ feed name the key follows (see nui.feed)

	_doc = 0          # document id, 0 when there is none
	_model = 0        # model id, 0 when there is none

	def __init__(self):
		"""Creates the model (if MODEL) from initial_model(), binds the @on
		handlers, then loads DOCUMENT. The document starts hidden.

		Events the document raises while it loads (data-event-load on
		<body>, change from bindings such as data-attrif-checked) reach the
		handlers before __init__ returns, while self._doc is still 0: show(),
		hide(), is_visible() and element_on() do nothing then, and set() and
		get() work. A handler that calls destroy() then leaves the window
		unavailable.

		Raises ValueError when DOCUMENT is not set, or when the class has @on
		handlers or FEEDS but no MODEL (checked only while NovaUI is available). When
		the model or the document cannot be made (the runtime logs why), the
		window stays unavailable and its methods do nothing."""
		self._doc = 0
		self._model = 0
		if not is_available():
			return

		cls = type(self)
		if not self.DOCUMENT:
			raise ValueError("%s.DOCUMENT is not set" % cls.__name__)
		handlers = _event_methods(cls)
		if handlers and not self.MODEL:
			raise ValueError("%s has @nui.on handlers but no MODEL" % cls.__name__)
		if self.FEEDS and not self.MODEL:
			raise ValueError("%s has FEEDS but no MODEL" % cls.__name__)

		_prepare_runtime()
		if self.MODEL:
			model = _nui.CreateModel(self.MODEL, self.initial_model())
			if not model:
				return
			self._model = model
			# Before the load, which already raises events.
			for event_name, method_name in handlers.items():
				_nui.ModelOn(model, event_name, getattr(self, method_name))
			for key, feed_name in self.FEEDS.items():
				_nui.BindFeed(model, key, feed_name)

		doc = _nui.LoadDocument(self.DOCUMENT)
		if not doc:
			self._drop_model()
			return
		if self.MODEL and not self._model:
			_nui.Close(doc)  # a handler destroyed the window while it loaded
			return
		self._doc = doc
		_windows[doc] = self

	def initial_model(self):
		"""Top-level model keys and their initial values.

		Keys follow RmlUi's rule (letters, digits and _, starting with a
		letter; not it, it_index, ev, true, false, size or literal, in any
		case). One other key makes RmlUi refuse the whole model, and the
		window stays unavailable (syserr names the key). Members of nested
		lists and maps may have any name."""
		return {}

	def show(self):
		"""Shows the document (modal if MODAL). True if it was shown."""
		if not self._doc:
			return False
		return bool(_nui.Show(self._doc, bool(self.MODAL)))

	def hide(self):
		"""Hides the document. True if it was hidden."""
		if not self._doc:
			return False
		return bool(_nui.Hide(self._doc))

	def is_visible(self):
		if not self._doc:
			return False
		return bool(_nui.IsVisible(self._doc))

	def focus(self, element_id):
		"""Gives the keyboard focus to the element with this id (a text field
		gets the caret); "" means the document itself. False when the window
		or the element is hidden, the id is unknown or the element cannot take
		focus (focus: none, a modal elsewhere). Works inside handlers.

		hide() moves the focus off a field, and show() puts it back where
		hide() left it, so focus the field again after show()."""
		if not self._doc:
			return False
		return bool(_nui.Focus(self._doc, element_id))

	# --- placement --------------------------------------------------------------
	# Places the window's <body> on the screen in dp, so a placement follows
	# the UI scale. A placement holds until the next one or clear_placement():
	# after a layout in which the window's size, the screen size, the scale or
	# the other window changed, the runtime places the window again, and it
	# keeps the window on the screen. A body that fills the screen (an overlay
	# or a scrim) is not moved. None of these take the focus or show the window.

	def set_position(self, x_dp, y_dp, origin=(0.0, 0.0)):
		"""Puts the point `origin` of the window's border box ((0, 0) its top
		left, (1, 1) its bottom right, (0.5, 1) the middle of its bottom edge)
		at (x_dp, y_dp) of the screen. True if the placement was stored."""
		if not self._doc:
			return False
		origin_x, origin_y = origin
		return bool(_nui.SetPosition(self._doc, float(x_dp), float(y_dp), float(origin_x), float(origin_y)))

	def center(self):
		"""Keeps the window in the middle of the screen."""
		if not self._doc:
			return False
		return bool(_nui.Center(self._doc))

	def place_next_to(self, other, side, gap_dp=0, element_id=""):
		"""Keeps the window beside `other` (a Window), or beside the element of
		`other` with this id: on `side` ("left", "right", "above" or "below"),
		`gap_dp` apart, its top edge (left, right) or left edge (above, below)
		in line with the other's. Where that side has no room the opposite side
		is used. ValueError for another side."""
		if side not in _SIDES:
			raise ValueError("nui.Window.place_next_to(): side is one of %s, not %r" % (", ".join(_SIDES), side))
		other_doc = getattr(other, "_doc", 0)
		if not self._doc or not other_doc:
			return False
		return bool(_nui.PlaceNextTo(self._doc, other_doc, side, float(gap_dp), element_id))

	def clear_placement(self):
		"""Hands the window's position back to its style sheet."""
		if not self._doc:
			return False
		return bool(_nui.ClearPlacement(self._doc))

	def bring_to_front(self):
		"""Draws the window above the other NovaUI windows without giving it
		the focus. A later show() or focus() of another window raises that one."""
		if not self._doc:
			return False
		return bool(_nui.BringToFront(self._doc))

	def follow_pointer(self, below_dp=40, above_dp=20, flip_dp=300, once=False):
		"""Keeps the window at the pointer, by legacy's tooltip rule
		(uitooltip.py ToolTip.OnUpdate), in every update after layout and with
		no Python: with the pointer at (mx, my) dp, the screen W x H dp and the
		window's border box w x h dp, y = my + below_dp while my < H - flip_dp,
		else my - h - above_dp; x = mx - w / 2; then the box is kept on the
		screen. The pointer is the host's, which keeps moving over the legacy
		UI. `once`: placed in the first update after the call, then held. The
		placement replaces any other and holds until clear_placement() or
		another placement call. True when stored; False without a document or
		with an exe whose _nui has no FollowPointer."""
		follow = getattr(_nui, "FollowPointer", None) if _nui is not None else None
		if not self._doc or follow is None:
			return False
		return bool(follow(self._doc, float(below_dp), float(above_dp), float(flip_dp), bool(once)))

	def keep_clear_of(self, *targets):
		"""While the window overlaps one of `targets` that is shown, the runtime
		puts the class nui-overlapping on its <body>, so its sheet can hide it
		(opacity: 0 and pointer-events: none; not display, whose zero size
		would end the overlap). A target is a Window or a (Window, element id)
		pair; keep_clear_of() with none clears the list."""
		if not self._doc:
			return False
		pairs = []
		for target in targets:
			window, element_id = target if isinstance(target, tuple) else (target, "")
			doc = getattr(window, "_doc", 0)
			if doc:
				pairs.append((doc, element_id))
		return bool(_nui.SetKeepClear(self._doc, pairs))

	# --- text fields ------------------------------------------------------------

	def set_value(self, element_id, text, caret="end"):
		"""Replaces the text of the text field with this id (an input that takes
		text, or a textarea), cut to its maxlength, and sends one change event
		(linebreak False) when the text changed, as typing would. `caret`
		("end", "start", "keep" or a character index) places the caret, with no
		selection, when the field has the focus; a field without the focus
		keeps its own caret. False for an unknown or hidden element, or one
		that takes no text."""
		if not isinstance(text, str):
			raise TypeError("nui.Window.set_value() takes str text, not %s" % type(text).__name__)
		if not (caret in _CARETS or (isinstance(caret, int) and not isinstance(caret, bool) and caret >= 0)):
			raise ValueError("nui.Window.set_value(): caret is one of %s or an index >= 0, not %r" % (", ".join(_CARETS), caret))
		if not self._doc:
			return False
		return bool(_nui.SetValue(self._doc, element_id, text, caret))

	def insert_text(self, element_id, text):
		"""Types `text` into the text field with this id at its caret, replacing
		the selection, as key presses would: the field takes the focus first,
		maxlength applies, and one change event follows. "\\b" is Backspace;
		"\\n" in a single-line field is Enter (change with linebreak True).
		False when nothing could be typed there."""
		if not isinstance(text, str):
			raise TypeError("nui.Window.insert_text() takes str text, not %s" % type(text).__name__)
		if not self._doc:
			return False
		return bool(_nui.InsertText(self._doc, element_id, text))

	def get_value(self, element_id):
		"""The text of the text field with this id, or None."""
		if not self._doc:
			return None
		return _nui.GetValue(self._doc, element_id)

	def set(self, **values):
		"""Replace model keys; only the views that use them update.

		True if every key was accepted. An unknown key or a kind that differs
		from initial_model() is refused and logged; a value that is not an
		int, float, str, bool, None, list, tuple or dict (with str keys)
		raises TypeError.

		A string shown with {{ }} is translated: an @ui.KEY or @game.KEY in
		it is replaced, so do not set text another player wrote into a key
		that {{ }} shows. Strings are text, never markup."""
		if not self._model:
			return False
		accepted = True
		for key, value in values.items():
			if not _nui.ModelSet(self._model, key, value):
				accepted = False
		return accepted

	def get(self, key):
		"""Current value of a model key (a copy), or None if unknown."""
		if not self._model:
			return None
		return _nui.ModelGet(self._model, key)

	def element_on(self, element_id, event, fn):
		"""Plain DOM event on the element with this id ("click", "dragstart",
		"keydown", ...); fn receives a dict with "type", "target_id" and, for
		mouse events, "button".

		The dict also carries the event's other parameters ("mouse_x",
		"mouse_y", the modifier keys, "key_identifier" for key events,
		compared with KEY_ESCAPE and the other KEY_ constants).
		An empty element_id means the document itself. A second call for the
		same element and event replaces fn; fn=None removes it. True if the
		handler was registered (or removed). Events of the copy a re-load
		replaced (its unload, blur, mouseout) do not reach fn.

		For "keydown", fn returning exactly True keeps the key: it stops
		there, so ancestor handlers and RmlUi's own Tab, arrow and Enter/Space
		handling do not run, and an Escape does not also reach the legacy UI
		(which would close a legacy window or open the system menu). Return
		True only when the handler acted on the key, and only while the
		window is shown; any other return value lets the key go on. Note that
		a lambda returns its expression, and show(), hide() and set() return
		True. A focused text field stops every key but Tab itself, so a
		document-level handler sees no Escape typed in a field: register the
		same handler on the field too."""
		if not self._doc:
			return False
		return bool(_nui.On(self._doc, element_id, event, fn))

	def on_reload(self):
		"""Hook: the document was re-loaded in place (hot reload, locale)."""
		pass

	def on_theme_changed(self, theme_id):
		"""Hook: nui.set_theme() applied `theme_id`. The documents carry the
		new theme's classes already; override this to update model values
		that name the theme (a picker's selection)."""
		pass

	def on_scale_changed(self, scale):
		"""Hook: nui.set_scale_percent() applied a new choice; `scale` is the
		factor in use now (get_scale()). Override this to move what follows
		the window's size in pixels (a legacy window kept clear of it)."""
		pass

	def on_colors_changed(self, slot):
		"""Hook: nui.set_color() set color slot `slot`, or nui.reset_colors()
		reset them (`slot` None). The documents show the new colors already;
		override this to refill model values that show the colors (the
		Interface section's swatches)."""
		pass

	def has_class(self, name, element_id=""):
		"""True when the element with this id ("" is the <body>) has the class
		`name` now. The theme's classes (skin-classic, theme-dark, ...) are on
		the <body> as soon as nui.set_theme() returns, before the restyle.
		False without a document, and with an exe whose _nui has no
		HasClass."""
		has = getattr(_nui, "HasClass", None) if _nui is not None else None
		if not self._doc or has is None:
			return False
		return bool(has(self._doc, element_id, name))

	def element_box(self, element_id):
		"""(x, y, width, height) of the element's border box in screen pixels
		("" is the <body>), as the last frame laid it out; None for an unknown
		element, one not laid out (it or an element above it has display:
		none, such as a data-if that is off; a hidden document keeps its
		boxes), without a document, or with an exe whose _nui has no
		GetElementBox."""
		get = getattr(_nui, "GetElementBox", None) if _nui is not None else None
		if not self._doc or get is None:
			return None
		box = get(self._doc, element_id)
		return tuple(box) if box is not None else None

	def destroy(self):
		"""Close the document, drop the model and every handler. Inside one
		of the window's handlers the document hides at once, and it goes
		with the model by the end of the frame. From here on its document's
		events reach none of the handlers, its unload included."""
		doc = self._doc
		self._doc = 0
		if doc:
			_windows.pop(doc, None)
			if _nui is not None:
				_nui.Close(doc)
		self._drop_model()

	def _drop_model(self):
		model = self._model
		self._model = 0
		if model and _nui is not None:
			_nui.DestroyModel(model)


# --- appearance -------------------------------------------------------------
# Each setter applies immediately and persists to config/metin2.cfg through
# systemSetting (UI_THEME, UI_SCALE, UI_REDUCED_MOTION, UI_REDUCED_EFFECTS,
# UI_COLORS): it stores the value and saves the file. Without NovaUI running
# only the saved value changes (the colors need the runtime to apply).

def _system_setting():
	try:
		import systemSetting
	except ImportError:
		return None
	return systemSetting


def _save(setting):
	save = getattr(setting, "SaveConfig", None)
	if save is not None:
		save()


def _theme_id(name):
	"""The theme id `name` stands for: stripped and lowercased, "dark" and
	"light" mapped to their ids. ValueError when that is not an id."""
	if not isinstance(name, str):
		raise ValueError("nui.set_theme() takes a theme id, not %r" % (name,))
	theme = name.strip().lower()
	theme = _THEME_LEGACY.get(theme, theme)
	if not 1 <= len(theme) <= _THEME_ID_MAX or not _THEME_ID_CHARS.issuperset(theme):
		raise ValueError("nui.set_theme(): %r is not a theme id (lowercase letters, digits and '-', at most %d)"
			% (name, _THEME_ID_MAX))
	return theme


def set_theme(name):
	"""Applies a theme at once and saves it (UI_THEME). Returns its id.

	`name` is an id from get_themes(), in any case. "dark" and "light", the
	values older config files and callers use, mean "modern-dark" and
	"modern-light". With NovaUI running, an id the runtime's table
	(nui/theme/themes.json) does not hold raises ValueError and nothing is
	saved; without it only the form of the id is checked. Then every open
	window's on_theme_changed() runs. No document re-loads: open windows keep
	their focus, typed text and models."""
	theme = _theme_id(name)
	if is_available() and not _nui.SetTheme(theme):
		known = ", ".join(theme_id for theme_id, _ in get_themes())
		raise ValueError("nui.set_theme(): no theme %r (themes: %s)" % (theme, known or "none"))
	setting = _system_setting()
	if setting is not None:
		setting.SetUITheme(theme)
		_save(setting)
	for window in list(_windows.values()):
		window.on_theme_changed(theme)
	return theme


def get_theme():
	"""The id of the theme in use. Without NovaUI, the saved one ("dark" and
	"light" from an older client read as their ids), else the default,
	"modern-dark"."""
	if is_available():
		theme = _nui.GetTheme()
		if theme:
			return theme
	setting = _system_setting()
	if setting is not None:
		theme = setting.GetUITheme()
		if theme:
			theme = theme.lower()
			return _THEME_LEGACY.get(theme, theme)
	return _THEME_DEFAULT


def get_themes():
	"""The player themes as (id, label) pairs in menu order; the first is the
	default. Labels are plain English for now. [] without NovaUI, or with a
	client whose _nui has no GetThemes."""
	if not is_available():
		return []
	themes = getattr(_nui, "GetThemes", None)
	if themes is None:
		return []
	return [(str(theme_id), str(label)) for theme_id, label in themes()]


def _clamp_scale_percent(percent):
	if isinstance(percent, bool) or not isinstance(percent, (int, float)):
		raise TypeError("nui.set_scale_percent() takes a number, not %s" % type(percent).__name__)
	percent = int(round(percent))
	if percent <= 0:
		return 0
	return min(max(percent, _SCALE_MIN_PERCENT), _SCALE_MAX_PERCENT)


def set_scale_percent(percent):
	"""0 = automatic (from the resolution), else 75..200.

	Values in between are clamped to that range, and anything at or below 0
	means automatic, as the config file reads them. Then every open window's
	on_scale_changed() runs with the factor in use."""
	percent = _clamp_scale_percent(percent)
	if is_available():
		_nui.SetScalePercent(percent)
	setting = _system_setting()
	if setting is not None:
		setting.SetUIScalePercent(percent)
		_save(setting)
	scale = get_scale()
	for window in list(_windows.values()):
		window.on_scale_changed(scale)


def get_scale_percent():
	"""The saved choice: 0 for automatic."""
	setting = _system_setting()
	if setting is not None:
		return int(setting.GetUIScalePercent())
	if is_available():
		return int(_nui.GetScalePercent())
	return 0


def get_scale():
	"""The scale factor in use now (1.0 = 100%)."""
	if is_available():
		return float(_nui.GetScale())
	return 1.0


def get_auto_scale():
	"""The factor automatic mode would pick for the current resolution."""
	if is_available():
		return float(_nui.GetAutoScale())
	return 1.0


def set_reduced_motion(on):
	on = bool(on)
	if is_available():
		_nui.SetReducedMotion(on)
	setting = _system_setting()
	if setting is not None:
		setting.SetUIReducedMotion(1 if on else 0)
		_save(setting)


def is_reduced_motion():
	"""Whether reduced motion is on now; the saved choice without NovaUI."""
	if is_available():
		return bool(_nui.GetReducedMotion())
	setting = _system_setting()
	if setting is not None:
		return bool(setting.IsUIReducedMotion())
	return False


def _nui_call(name):
	"""The _nui function `name` while NovaUI runs, else None (also with an
	older exe that has no such function)."""
	return getattr(_nui, name, None) if is_available() else None


def set_reduced_effects(on):
	"""Reduced effects on or off at once (the reduced-effects media theme:
	no filters, backdrop filters or masks; shadows and gradients stay), and
	saved (UI_REDUCED_EFFECTS). A device without effects keeps them reduced
	whatever this says (effects_available())."""
	on = bool(on)
	setter = _nui_call("SetReducedEffects")
	if setter is not None:
		setter(on)
	setting = _system_setting()
	if setting is not None and getattr(setting, "SetUIReducedEffects", None) is not None:
		setting.SetUIReducedEffects(1 if on else 0)
		_save(setting)


def is_reduced_effects():
	"""Whether effects are reduced now: the player's setting, or True when the
	device draws no effects. The saved choice without NovaUI."""
	getter = _nui_call("GetReducedEffects")
	if getter is not None:
		return bool(getter())
	setting = _system_setting()
	if setting is not None and getattr(setting, "IsUIReducedEffects", None) is not None:
		return bool(setting.IsUIReducedEffects())
	return False


def effects_available():
	"""Whether the renderer draws effects (filters, layers, shaders) on this
	device; False without NovaUI, or with an exe that has none."""
	available = _nui_call("EffectsAvailable")
	return bool(available()) if available is not None else False


# --- player colors (docs/ui/AUTHORING.md "Player colors") --------------------

def get_color_slots():
	"""The color slots the theme in use offers, in order: dicts {"slot",
	"kind" ("color" or "percent"), "label" (a locale key, @ui.), "default",
	"value" (the one in use), "swatches", "min", "max", "step"}. [] when the
	theme offers none (classic), without NovaUI, or with an exe that has no
	player colors."""
	get = _nui_call("GetColorSlots")
	if get is None:
		return []
	return [dict(slot) for slot in get()]


def get_colors():
	"""The theme in use's player colors: {slot: value} for every slot not at
	its default; {} when none is set."""
	return {slot["slot"]: str(slot["value"]) for slot in get_color_slots() if str(slot["value"]) != str(slot["default"])}


def _save_colors():
	overrides = _nui_call("GetColorOverrides")
	setting = _system_setting()
	if overrides is None or setting is None or getattr(setting, "SetUIColors", None) is None:
		return
	setting.SetUIColors(overrides())
	_save(setting)


def save_colors():
	"""Writes every theme's player colors (UI_COLORS) to the config now: after
	a run of set_color(..., save=False), such as a slider's drag. Nothing
	without NovaUI or with an exe that has no player colors."""
	_save_colors()


def set_color(slot, value, save=True):
	"""Sets one color slot of the theme in use for every open window at once,
	saves every theme's colors (UI_COLORS; with save=False it does not, for a
	live preview that calls save_colors() once it ends, as a slider's drag
	does: each save rewrites the config file), then runs every open window's
	on_colors_changed(slot). Returns the resolve's result: {"ok": True,
	"value", "adjusted": {token: value} (the colors it changed to keep text
	readable; "opacity" when it raised the panel opacity), "failed": [[fg,
	bg], ...], "opacity"}.

	`value` is "#rrggbb" for a color slot or a whole percent for a percent
	slot ("opacity", 50 to 100 in steps of 5, as an int or a string); the
	slot's default removes the override. ValueError for a slot the theme does
	not offer or a malformed value. Without NovaUI nothing applies and the
	result has "ok": False."""
	if not isinstance(slot, str) or isinstance(value, bool) or not isinstance(value, (str, int)):
		raise ValueError("nui.set_color() takes a slot name and a #rrggbb color or a whole percent, not %r, %r" % (slot, value))
	setter = _nui_call("SetColor")
	if setter is None:
		return {"ok": False, "value": str(value), "adjusted": {}, "failed": [], "opacity": 100}
	result = dict(setter(slot, str(value)))
	if save:
		_save_colors()
	for window in list(_windows.values()):
		window.on_colors_changed(slot)
	return result


def reset_colors(all_themes=False):
	"""Removes the player colors of the theme in use (every theme's with
	all_themes), applies and saves at once, then runs every open window's
	on_colors_changed(None)."""
	reset = _nui_call("ResetColors")
	if reset is None:
		return
	reset("*" if all_themes else "")
	_save_colors()
	for window in list(_windows.values()):
		window.on_colors_changed(None)


# --- engine features ------------------------------------------------------------

def has_decorator(name):
	"""Whether the runtime registered the decorator `name` (nui-cells, the
	lean slot grids' cell bases, P14 spec 4.9); False without NovaUI or with
	an exe whose _nui has no HasDecorator."""
	query = _nui_call("HasDecorator")
	return bool(query(str(name))) if query is not None else False


# --- first opens --------------------------------------------------------------

def prewarm(paths):
	"""Asks the runtime to parse the style sheets of these documents ahead of
	their first open, one document per calm frame (P13 spec 8.2 F-H1), so the
	first open of an on-demand window costs what a second one does. `paths`
	are store paths of documents (nui/windows/<w>/<w>.rml). True when the
	runtime took the list; False without NovaUI or with an exe that has no
	prewarm."""
	queue = _nui_call("Prewarm")
	if queue is None:
		return False
	queue([str(path) for path in paths])
	return True


# --- strings ----------------------------------------------------------------

def _string_table(module_name):
	"""The str globals of a locale module (names not starting with "_"), or
	None when the module cannot be imported here. The values stay plain
	text: the runtime escapes them where they land in RML."""
	try:
		module = __import__(module_name)
	except Exception:
		return None
	return {key: value for key, value in vars(module).items()
		if not key.startswith("_") and isinstance(value, str)}


def refresh_strings():
	"""Push uiScriptLocale ("ui") and localeInfo ("game") to the runtime so
	@ui.KEY / @game.KEY resolve; re-loads open documents.

	Called for you before the first window loads and after every locale
	reload (it registers itself with localeInfo.RegisterReloadCallback).
	A locale module that cannot be imported keeps its previous table. True
	if a table was pushed."""
	if not is_available():
		return False
	ui = _string_table("uiScriptLocale")
	game = _string_table("localeInfo")
	if game is not None:
		import localeInfo
		register = getattr(localeInfo, "RegisterReloadCallback", None)
		if register is not None:
			register(refresh_strings)
	if ui is not None:
		# One re-load for both tables: only the last push re-loads.
		_nui.SetStrings("ui", ui, game is None)
	if game is not None:
		_nui.SetStrings("game", game, True)
	return ui is not None or game is not None
