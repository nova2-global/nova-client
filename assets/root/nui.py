"""Python side of the NovaUI (RmlUi) windows.

OWNER: P2.

A window is one RmlUi document (.rml + .rcss) plus an optional data model and
a controller class in root/nui_<name>.py:

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
  * A window lives until destroy(): the runtime holds its handlers, so
    dropping the last reference does not close it. Only one window per MODEL
    name can exist at a time.
  * destroy() inside one of the window's own handlers (a close button) hides
    it at once; the document and model go by the end of the frame.

The C++ module `_nui` (src/NovaUI/Python) is the only thing this file calls;
when it is missing or has no runtime (headless tests) is_available() is False
and every Window method is a no-op that returns a falsy value.
"""

try:
	import _nui
except ImportError:  # pragma: no cover - client builds always have it
	_nui = None


_THEMES = ("dark", "light")
_SCALE_MIN_PERCENT = 75
_SCALE_MAX_PERCENT = 200

# Open windows by document id, so a re-load reaches the right on_reload().
_windows = {}


def is_available():
	"""True when the `_nui` module is present and the client created a runtime."""
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


def on(event_name):
	"""Method decorator: the method handles data-event `event_name` of the
	window's model and is called with the evaluated arguments.

	One method may carry several @on decorators. A subclass that overrides a
	decorated method without repeating the decorator still receives the
	event; a subclass method decorated for the same event name wins over the
	base class one."""
	if not isinstance(event_name, str) or not event_name:
		raise TypeError("nui.on() takes the data-event name as a non-empty str")

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
		handlers but no MODEL (checked only while NovaUI is available). When
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

		_prepare_runtime()
		if self.MODEL:
			model = _nui.CreateModel(self.MODEL, self.initial_model())
			if not model:
				return
			self._model = model
			# Before the load, which already raises events.
			for event_name, method_name in handlers.items():
				_nui.ModelOn(model, event_name, getattr(self, method_name))

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
		"""Top-level model keys and their initial values."""
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

	def set(self, **values):
		"""Replace model keys; only the views that use them update.

		True if every key was accepted. An unknown key or a kind that differs
		from initial_model() is refused and logged; a value that is not an
		int, float, str, bool, None, list, tuple or dict (with str keys)
		raises TypeError."""
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
		"mouse_y", the modifier keys, "key_identifier" for key events).
		An empty element_id means the document itself. A second call for the
		same element and event replaces fn; fn=None removes it. True if the
		handler was registered (or removed). Events of the copy a re-load
		replaced (its unload, blur, mouseout) do not reach fn."""
		if not self._doc:
			return False
		return bool(_nui.On(self._doc, element_id, event, fn))

	def on_reload(self):
		"""Hook: the document was re-loaded in place (hot reload, locale)."""
		pass

	def destroy(self):
		"""Close the document, drop the model and every handler. Inside one
		of the window's handlers the document hides at once, and it goes
		with the model by the end of the frame."""
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
# systemSetting (UI_THEME, UI_SCALE, UI_REDUCED_MOTION): it stores the value
# and saves the file. Without NovaUI running only the saved value changes.

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


def set_theme(name):
	""""dark" or "light" (any case); anything else raises ValueError."""
	if not isinstance(name, str) or name.lower() not in _THEMES:
		raise ValueError('nui.set_theme() takes "dark" or "light", not %r' % (name,))
	theme = name.lower()
	if is_available():
		_nui.SetTheme(theme)
	setting = _system_setting()
	if setting is not None:
		setting.SetUITheme(theme)
		_save(setting)


def get_theme():
	"""The theme in use ("dark" or "light"); the saved one without NovaUI."""
	if is_available():
		theme = _nui.GetTheme()
		if theme:
			return theme
	setting = _system_setting()
	if setting is not None:
		return setting.GetUITheme()
	return "dark"


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
	means automatic, as the config file reads them."""
	percent = _clamp_scale_percent(percent)
	if is_available():
		_nui.SetScalePercent(percent)
	setting = _system_setting()
	if setting is not None:
		setting.SetUIScalePercent(percent)
		_save(setting)


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
