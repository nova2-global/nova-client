"""Stand-ins shared by the NovaUI controller tests in tools/ (plain CPython,
no client): a recording `nui` module, `dbg`, `systemSetting`, `wndMgr`,
`snd`, `app`, and a loader that imports a root module over them.

The `nui` stand-in follows assets/root/nui.py's contract as far as the
controllers see it. A window keeps its model in a dict and records every
call. Focus follows NuiRuntime: the first show() gives the window's
autofocus element (NuiState.autofocus) the focus, hide() takes it off, and a
later show() leaves it off. Text fields hold their text: set_value() and
insert_text() change it and, when the text changed, call the window's
change handler as RmlUi's change event would (NuiState.field_events names
the data event a field's data-event-change calls). Each field has a caret,
as RmlUi's text widget does: a new field has it at 0, the focus leaves it
where it is, set_value() places it only in the focused field (another
field's caret is cut to its new text, as the next layout does), and
insert_text() types and erases at it. show() records whether it showed the
window as a modal (Window.modal). Feeds follow nui.py's FEEDS: a window
binds each key it names when it is made (the key takes the feed's value
then, if NuiState.feeds holds one), NuiState.publish() changes a feed and
every bound key, as the runtime's next frame would, and nui.now() and
nui.feed() answer NuiState.now and NuiState.feeds. The appearance calls
(set_theme, set_scale_percent, set_reduced_motion and their getters,
get_auto_scale) follow NuiState.theme, .scale_percent, .auto_scale and
.reduced_motion, and each setter is recorded in NuiState.appearance."""
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "assets", "root"))
sys.path.insert(0, HERE)
import nui_palette  # noqa: E402

_PALETTE_DATA = []


def palette_data():
    """The shipped player color data (nui/theme/colors.json and the skins'),
    read once."""
    if not _PALETTE_DATA:
        _PALETTE_DATA.append(nui_palette.load())
    return _PALETTE_DATA[0]

THEMES = [("modern-dark", "Modern dark"), ("modern-light", "Modern light"), ("classic", "Classic")]
# Each theme's <body> classes (nui/theme/themes.json).
THEME_CLASSES = {"modern-dark": ("skin-modern", "theme-dark"), "modern-light": ("skin-modern", "theme-light"),
                 "classic": ("skin-classic", "theme-classic")}

MISSING = object()

KEY_ESCAPE, KEY_RETURN, KEY_NUMPADENTER, KEY_TAB, KEY_SPACE = 81, 72, 61, 70, 1


class NuiState(object):
    """What the stand-in nui module answers, and what it saw."""

    def __init__(self):
        self.available = True
        self.rtl = False
        self.loads = True
        self.failing = set()     # documents that do not load
        self.raising = set()     # documents whose window raises while it is made
        self.next_doc = 1
        self.themes = list(THEMES)
        self.theme = "modern-dark"
        self.scale = 1.0
        self.shows = []          # (class name, document) of every show(), in order
        self.windows = []        # every window made, for on_theme_changed and any_window_shown
        self.autofocus = {}      # document -> the element id its autofocus names
        self.field_events = {}   # (document, field id) -> data-event name of its change
        self.boxes = {}          # (document, element id) -> (x, y, w, h) in pixels
        self.maxlength = {}      # (document, field id) -> maxlength
        self.now = 0.0           # nui.now()
        self.feeds = {}          # feed name -> the value C++ published last (nui.feed)
        self.binds = []          # (window class name, model key, feed name) of every bind, in order
        self.text_fields = set()  # (document, element id) of the text fields (ime.PasteString reaches them)
        self.scale_percent = 0   # nui.get_scale_percent(): the saved choice, 0 for automatic
        self.auto_scale = 0.875  # nui.get_auto_scale(): 900 lines in 1/8 steps
        self.reduced_motion = False
        self.reduced_effects = False   # the player's setting (nui.set_reduced_effects)
        self.effects_available = True  # nui.effects_available(): False for a device without effects
        self.colors = {}         # theme id -> {slot: value}, the player colors set (nui.set_color)
        self.decorators = set()  # nui.has_decorator(): the decorators the runtime registered (Wave 3b: nui-cells)
        self.fronts = []         # every window bring_to_front() raised, in order
        self.appearance = []     # ("set_theme", id), ("set_scale_percent", p), ("set_reduced_motion", on),
                                 # ("set_reduced_effects", on), ("set_color", slot, value[, "unsaved"]), ("save_colors",), ("reset_colors", all), in order

    def publish(self, name, value):
        """A feed changes: every live window's key bound to it takes the value,
        as the runtime applies feeds before its next update."""
        self.feeds[name] = value
        for window in self.windows:
            if not window._model:
                continue
            for key, feed_name in window.FEEDS.items():
                if feed_name == name:
                    window.model[key] = value


def make_nui(state):
    """A stand-in for assets/root/nui.py over `state`."""
    nui = types.ModuleType("nui")

    def on(event_name):
        def mark(method):
            method._nui_events = getattr(method, "_nui_events", ()) + (event_name,)
            return method
        return mark

    def event_methods(cls):
        found = {}
        for klass in reversed(cls.__mro__):
            for name, attr in vars(klass).items():
                for event_name in getattr(attr, "_nui_events", ()):
                    found[event_name] = name
        return found

    class Window(object):
        DOCUMENT = None
        MODEL = None
        MODAL = False
        FEEDS = {}
        _doc = 0
        _model = 0

        def __init__(self):
            self._doc = 0
            self._model = 0
            self.calls = []
            self.model = {}
            self.visible = False
            self.focused = None
            self.modal = False
            self.fields = {}
            self.carets = {}         # field id -> caret index
            self.handlers = {}       # (element id, event) -> fn
            self.placement = None
            self.keep_clear = []
            self.front = 0
            self._shown_before = False
            if not state.available:
                return
            if self.DOCUMENT in state.raising:
                raise RuntimeError("stand-in: %s raises" % self.DOCUMENT)
            if self.FEEDS and not self.MODEL:
                raise ValueError("%s has FEEDS but no MODEL" % type(self).__name__)
            self.model = dict(self.initial_model())
            self._model = 1
            for key, feed_name in self.FEEDS.items():
                state.binds.append((type(self).__name__, key, feed_name))
                if feed_name in state.feeds:
                    self.model[key] = state.feeds[feed_name]
            if not state.loads or self.DOCUMENT in state.failing:
                self._model = 0
                return
            self._doc = state.next_doc
            state.next_doc += 1
            state.windows.append(self)

        def initial_model(self):
            return {}

        # --- visibility and focus -------------------------------------------------

        def show(self):
            if not self._doc:
                return False
            self.calls.append(("show",))
            state.shows.append((type(self).__name__, self.DOCUMENT))
            self.visible = True
            self.modal = bool(self.MODAL)
            if not self._shown_before:
                self._shown_before = True
                element = state.autofocus.get(self.DOCUMENT)
                if element:
                    self._take_focus(element)
            return True

        def hide(self):
            if not self._doc:
                return False
            self.calls.append(("hide",))
            self.visible = False
            self.focused = None
            return True

        def is_visible(self):
            return bool(self._doc) and self.visible

        def _take_focus(self, element_id):
            self.focused = element_id
            handler = self.handlers.get((element_id, "focus"))
            if handler is not None:
                handler({"type": "focus", "target_id": element_id})

        def focus(self, element_id):
            self.calls.append(("focus", element_id))
            if not self._doc or not self.visible:
                return False
            self._take_focus(element_id)
            return True

        # --- model and events -----------------------------------------------------

        def set(self, **values):
            if not self._model:
                return False
            self.calls.append(("set", dict(values)))
            self.model.update(values)
            return True

        def get(self, key):
            if not self._model:
                return None
            return self.model.get(key)

        def element_on(self, element_id, event, fn):
            if not self._doc:
                return False
            self.calls.append(("element_on", element_id, event))
            if fn is None:
                self.handlers.pop((element_id, event), None)
            else:
                self.handlers[(element_id, event)] = fn
            return True

        def key(self, element_id, key_identifier):
            """A keydown the stand-in runtime delivers: the field's handler,
            then the document's, until one returns exactly True. True when one
            kept the key."""
            for target in ([element_id, ""] if element_id else [""]):
                handler = self.handlers.get((target, "keydown"))
                if handler is None:
                    continue
                if handler({"type": "keydown", "target_id": element_id, "key_identifier": key_identifier}) is True:
                    return True
            return False

        def click(self, element_id, event_name=None, *args):
            """A mouse click as RmlUi delivers it: the press focuses the
            clicked element, the element's data event (if named) runs, then
            the click bubbles to the element's handler and the document's."""
            if self._doc and self.visible:
                self._take_focus(element_id)
            if event_name is not None:
                self.fire(event_name, *args)
            for target in ([element_id, ""] if element_id else [""]):
                handler = self.handlers.get((target, "click"))
                if handler is not None:
                    handler({"type": "click", "target_id": element_id})

        def fire(self, event_name, *args):
            """A data event from the document: its @nui.on handler, if any."""
            method = event_methods(type(self)).get(event_name)
            if method is None:
                raise AssertionError("%s has no handler for %s" % (type(self).__name__, event_name))
            return getattr(self, method)(*args)

        def on_reload(self):
            pass

        def on_theme_changed(self, theme_id):
            pass

        def on_colors_changed(self, slot):
            pass

        def on_scale_changed(self, scale):
            pass

        def element_box(self, element_id):
            """NuiState.boxes, while the window is shown (nui.py element_box)."""
            if not self._doc:
                return None
            return _box(state, self._doc, element_id)

        def has_class(self, name, element_id=""):
            """The theme's classes on the <body> (element "")."""
            if not self._doc or element_id:
                return False
            return name in THEME_CLASSES.get(state.theme, ())

        def destroy(self):
            self.calls.append(("destroy",))
            self._doc = 0
            self._model = 0
            self.visible = False
            self.focused = None

        # --- placement ------------------------------------------------------------

        def set_position(self, x_dp, y_dp, origin=(0.0, 0.0)):
            if not self._doc:
                return False
            self.calls.append(("set_position", x_dp, y_dp, tuple(origin)))
            self.placement = ("position", x_dp, y_dp, tuple(origin))
            return True

        def center(self):
            if not self._doc:
                return False
            self.calls.append(("center",))
            self.placement = ("center",)
            return True

        def place_next_to(self, other, side, gap_dp=0, element_id=""):
            if side not in ("left", "right", "above", "below"):
                raise ValueError(side)
            if not self._doc or not getattr(other, "_doc", 0):
                return False
            self.calls.append(("place_next_to", other, side, gap_dp, element_id))
            self.placement = ("next_to", other, side, gap_dp, element_id)
            return True

        def clear_placement(self):
            if not self._doc:
                return False
            self.placement = None
            return True

        def bring_to_front(self):
            if not self._doc:
                return False
            self.calls.append(("bring_to_front",))
            self.front += 1
            state.fronts.append(self)
            return True

        def follow_pointer(self, below_dp=40, above_dp=20, flip_dp=300, once=False, bottom_reserve_dp=0):
            """nui.py follow_pointer: recorded as the placement, when the
            stand-in _nui has FollowPointer (the Wave 3b engine)."""
            if not self._doc or getattr(nui._nui, "FollowPointer", None) is None:
                return False
            self.calls.append(("follow_pointer", below_dp, above_dp, flip_dp, bool(once), bottom_reserve_dp))
            self.placement = ("pointer", below_dp, above_dp, flip_dp, bool(once), bottom_reserve_dp)
            return True

        def keep_clear_of(self, *targets):
            if not self._doc:
                return False
            self.calls.append(("keep_clear_of",) + targets)
            self.keep_clear = [t for t in targets if getattr(t[0] if isinstance(t, tuple) else t, "_doc", 0)]
            return True

        # --- text fields ----------------------------------------------------------

        def _change(self, element_id, linebreak):
            event = state.field_events.get((self.DOCUMENT, element_id))
            if event:
                self.fire(event, self.fields.get(element_id, ""), linebreak)

        def set_value(self, element_id, text, caret="end"):
            if not isinstance(text, str):
                raise TypeError(type(text).__name__)
            if not self._doc or not self.visible:
                return False
            self.calls.append(("set_value", element_id, text, caret))
            limit = state.maxlength.get((self.DOCUMENT, element_id))
            if limit is not None:
                text = text[:limit]
            text = text.replace("\r", "").replace("\n", "").replace("\t", "")
            focused = self.focused == element_id
            kept = self.carets.get(element_id, 0)
            if self.fields.get(element_id, "") != text:
                self.fields[element_id] = text
                self.carets[element_id] = min(kept, len(text))
                self._change(element_id, False)
            # Only into a field that had the focus and still has it.
            if focused and self.focused == element_id:
                if caret == "keep":
                    at = kept
                elif caret == "start":
                    at = 0
                elif caret == "end":
                    at = len(text)
                else:
                    at = caret
                self.carets[element_id] = max(0, min(at, len(text)))
            return True

        def insert_text(self, element_id, text):
            if not isinstance(text, str):
                raise TypeError(type(text).__name__)
            if not self._doc or not self.visible:
                return False
            self.calls.append(("insert_text", element_id, text))
            if self.focused != element_id:
                self._take_focus(element_id)
            current = self.fields.get(element_id, "")
            at = max(0, min(self.carets.get(element_id, 0), len(current)))
            if text == "\b":
                if at == 0:
                    return False
                self.fields[element_id] = current[:at - 1] + current[at:]
                self.carets[element_id] = at - 1
                self._change(element_id, False)
                return True
            if text == "\n":
                self._change(element_id, True)
                return True
            limit = state.maxlength.get((self.DOCUMENT, element_id))
            if limit is not None:
                text = text[:max(0, limit - len(current))]
            if not text:
                return False
            self.fields[element_id] = current[:at] + text + current[at:]
            self.carets[element_id] = at + len(text)
            self._change(element_id, False)
            return True

        def get_value(self, element_id):
            if not self._doc:
                return None
            return self.fields.get(element_id, "")

    def set_theme(name):
        if name not in [theme_id for theme_id, _ in state.themes]:
            raise ValueError("no theme %r" % (name,))
        state.appearance.append(("set_theme", name))
        state.theme = name
        for window in list(state.windows):
            if window._doc:
                window.on_theme_changed(name)
        return name

    def set_scale_percent(percent):
        """nui.py's clamp: 0 or less is automatic, else 75..200."""
        percent = int(round(percent))
        percent = 0 if percent <= 0 else min(max(percent, 75), 200)
        state.appearance.append(("set_scale_percent", percent))
        state.scale_percent = percent
        state.scale = percent / 100.0 if percent > 0 else state.auto_scale
        for window in list(state.windows):
            if window._doc:
                window.on_scale_changed(state.scale)

    def set_reduced_motion(on):
        state.appearance.append(("set_reduced_motion", bool(on)))
        state.reduced_motion = bool(on)

    def set_reduced_effects(on):
        state.appearance.append(("set_reduced_effects", bool(on)))
        state.reduced_effects = bool(on)

    # The player colors, over the shipped palette data and the reference
    # resolve (tools/nui_palette.py), as the runtime answers them.
    def color_slots():
        if not state.available:
            return []
        values = state.colors.get(state.theme, {})
        return [{"slot": s["slot"], "kind": s["kind"], "label": s["label"], "default": s["default"],
                 "value": values.get(s["slot"], s["default"]), "swatches": list(s["swatches"]),
                 "min": s["min"], "max": s["max"], "step": s["step"]} for s in nui_palette.slots_of_theme(palette_data(), state.theme)]

    def set_color(slot, value, save=True):
        state.appearance.append(("set_color", slot, str(value)) if save else ("set_color", slot, str(value), "unsaved"))
        if not state.available:
            return {"ok": False, "value": str(value), "adjusted": {}, "failed": [], "opacity": 100}
        spec = next((s for s in nui_palette.slots_of_theme(palette_data(), state.theme) if s["slot"] == slot), None)
        normal = nui_palette.normalize_slot_value(spec, str(value)) if spec else None
        if normal is None:
            raise ValueError("nui.set_color(): no slot %r or a malformed value %r" % (slot, value))
        values = state.colors.setdefault(state.theme, {})
        if normal == spec["default"]:
            values.pop(slot, None)
        else:
            values[slot] = normal
        result = nui_palette.resolve(palette_data(), state.theme, values)
        for window in list(state.windows):
            if window._doc:
                window.on_colors_changed(slot)
        return {"ok": True, "value": normal, "adjusted": result["adjusted"], "failed": result["failed"],
                "opacity": result["opacity"]}

    def save_colors():
        state.appearance.append(("save_colors",))

    def reset_colors(all_themes=False):
        state.appearance.append(("reset_colors", bool(all_themes)))
        if all_themes:
            state.colors.clear()
        else:
            state.colors.pop(state.theme, None)
        for window in list(state.windows):
            if window._doc:
                window.on_colors_changed(None)

    def any_window_shown():
        return any(window.is_visible() for window in state.windows)

    def plain_text(text):
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)
        return text.replace("@", "@\u2060")

    nui.Window = Window
    nui.on = on
    nui.is_available = lambda: state.available
    nui.enabled_for_locale = lambda: not state.rtl
    nui.get_themes = lambda: list(state.themes) if state.available else []
    nui.get_theme = lambda: state.theme
    nui.set_theme = set_theme
    nui.get_scale = lambda: state.scale
    nui.set_scale_percent = set_scale_percent
    nui.get_scale_percent = lambda: state.scale_percent
    nui.get_auto_scale = lambda: state.auto_scale if state.available else 1.0
    nui.set_reduced_motion = set_reduced_motion
    nui.is_reduced_motion = lambda: state.reduced_motion
    nui.set_reduced_effects = set_reduced_effects
    nui.is_reduced_effects = lambda: state.reduced_effects or not state.effects_available
    nui.effects_available = lambda: bool(state.effects_available) if state.available else False
    nui.get_color_slots = color_slots
    nui.set_color = set_color
    nui.reset_colors = reset_colors
    nui.save_colors = save_colors
    nui.get_colors = lambda: dict(state.colors.get(state.theme, {}))
    nui.any_window_shown = any_window_shown
    nui.plain_text = plain_text
    nui.now = lambda: float(state.now) if state.available else 0.0
    nui.feed = lambda name: state.feeds.get(name)
    nui.KEY_ESCAPE = KEY_ESCAPE
    nui.KEY_RETURN = KEY_RETURN
    nui.KEY_NUMPADENTER = KEY_NUMPADENTER
    nui.KEY_TAB = KEY_TAB
    nui.KEY_SPACE = KEY_SPACE
    nui._nui = types.SimpleNamespace(GetElementBox=lambda doc, element_id: _box(state, doc, element_id))
    nui.has_decorator = lambda name: state.available and name in state.decorators
    return nui


def _box(state, doc, element_id):
    for window in state.windows:
        if window._doc == doc:
            if not window.visible:
                return None
            return state.boxes.get((window.DOCUMENT, element_id))
    return None


def make_dbg():
    dbg = types.ModuleType("dbg")
    dbg.errors = []
    dbg.lines = []
    dbg.TraceError = dbg.errors.append
    dbg.Tracen = dbg.lines.append
    return dbg


def make_setting(flag=1, has_binding=True, windows=None):
    """systemSetting with UI_NUI_LOGIN `flag`; `windows` is the UI_NUI_WINDOWS
    string, or None for an exe without its binding."""
    setting = types.ModuleType("systemSetting")
    setting.saved = 0
    if has_binding:
        setting.IsUINuiLogin = lambda: flag
    if windows is not None:
        setting.windows = windows
        setting.GetUINuiWindows = lambda: setting.windows

        def set_windows(value):
            setting.windows = value
            return True

        setting.SetUINuiWindows = set_windows

    def save():
        setting.saved += 1

    setting.SaveConfig = save
    return setting


def make_wndmgr(with_layers=True, mouse=(0, 0), screen=(1600, 900)):
    wndmgr = types.ModuleType("wndMgr")
    wndmgr.layers = {}
    wndmgr.layer_calls = []
    if with_layers:
        def set_layer(handle, layer):
            wndmgr.layer_calls.append((handle, layer))
            wndmgr.layers[handle] = layer
            return True

        wndmgr.SetWindowLayer = set_layer
        wndmgr.GetWindowLayer = lambda handle: wndmgr.layers.get(handle, "UI")
    wndmgr.mouse = mouse
    wndmgr.GetMousePosition = lambda: wndmgr.mouse
    wndmgr.GetScreenWidth = lambda: screen[0]
    wndmgr.GetScreenHeight = lambda: screen[1]
    return wndmgr


def stub_module(name, **members):
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Modules(object):
    """Puts stand-ins into sys.modules for the duration of a test and takes
    them out again; load() imports a root module over them (fresh each
    time), so the module under test and its own imports see the stand-ins."""

    def __init__(self, **modules):
        self.saved = {}
        self.names = []
        for name, module in modules.items():
            self.put(name, module)

    def put(self, name, module):
        if name not in self.saved:
            self.saved[name] = sys.modules.get(name, MISSING)
        if module is None:
            sys.modules.pop(name, None)
            # A blocked import: `import name` raises ImportError.
            sys.modules[name] = None
        else:
            sys.modules[name] = module

    def load(self, name, file_name=None):
        path = os.path.join(ROOT, file_name or (name.lower() + ".py"))
        self.put(name, None)
        module = load_module(name, path)
        sys.modules[name] = module
        return module

    def restore(self):
        for name, value in self.saved.items():
            if value is MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        self.saved = {}


# --- a stand-in for the legacy ui module -------------------------------------------

class Widget(object):
    """A legacy child window: records every call, keeps a text, a shown
    state, events and the edit line attributes the dialogs touch."""

    def __init__(self, name=""):
        self.name = name
        self.calls = []
        self.text = ""
        self.shown = True
        self.focused = False
        self.extraLines = []
        self.event = None
        self.eventArgs = ()

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)

        def record(*args):
            self.calls.append((attr,) + args)
            return None
        return record

    def SetText(self, text):
        self.calls.append(("SetText", text))
        self.text = text

    def GetText(self):
        return self.text

    def SetEvent(self, event, *args):
        self.calls.append(("SetEvent", event) + args)
        self.event = event
        self.eventArgs = args

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def IsShow(self):
        return self.shown

    def SetFocus(self):
        self.focused = True

    def KillFocus(self):
        self.focused = False

    def IsFocus(self):
        return self.focused

    def GetLocalPosition(self):
        return (0, 0)

    def GetWidth(self):
        return 0

    def GetHeight(self):
        return 0

    def Click(self):
        """The legacy button's CallEvent."""
        if self.event:
            self.event(*self.eventArgs)


def make_legacy_ui():
    """A stand-in ui.py: ScriptWindow, Window, Bar, ThinBoard, Button,
    PythonScriptLoader and __mem_func__, enough for the legacy classes of
    uicommon.py, uipickmoney.py, networkmodule.py and uilocaleselector.py."""
    ui = types.ModuleType("ui")
    ui.handles = [0]

    class Window(object):
        def __init__(self, layer="UI"):
            ui.handles[0] += 1
            self.hWnd = ui.handles[0]
            self.layer = layer
            self.shown = False
            self.calls = []
            self.Children = []
            self.ElementDictionary = {}

        def __del__(self):
            pass

        def Show(self):
            self.shown = True

        def Hide(self):
            self.shown = False

        def IsShow(self):
            return self.shown

        def SetTop(self):
            self.calls.append(("SetTop",))

        def SetCenterPosition(self, x=0, y=0):
            self.calls.append(("SetCenterPosition",))

        def SetPosition(self, x, y):
            self.calls.append(("SetPosition", x, y))

        def GetGlobalPosition(self):
            return (0, 0)

        def SetSize(self, width, height):
            self.calls.append(("SetSize", width, height))

        def UpdateRect(self):
            pass

        def Lock(self):
            self.calls.append(("Lock",))

        def Unlock(self):
            self.calls.append(("Unlock",))

        def GetWidth(self):
            return 280

        def GetHeight(self):
            return 105

        def KillFocus(self):
            pass

        def SetParent(self, parent):
            pass

        def SetWindowName(self, name):
            pass

        def AddFlag(self, flag):
            pass

        def IsRTL(self):
            return False

        def Destroy(self):
            pass

    class ScriptWindow(Window):
        def ClearDictionary(self):
            self.Children = []
            self.ElementDictionary = {}

        def GetChild(self, name):
            child = self.ElementDictionary.get(name)
            if child is None:
                child = self.ElementDictionary[name] = Widget(name)
            return child

        def GetChild2(self, name):
            return self.GetChild(name)

    class PythonScriptLoader(object):
        loaded = []

        def LoadScriptFile(self, window, path):
            PythonScriptLoader.loaded.append(path)

    class mem_func(object):
        """Legacy's rule (ui.py:58-84): a bound method that takes only self
        is called with no argument, whatever the caller passes (a list box
        passes the row's number and text)."""

        def __init__(self, fn):
            self.fn = fn
            code = getattr(getattr(fn, "__func__", None), "__code__", None)
            self.drops_args = code is not None and code.co_argcount <= 1

        def __call__(self, *args):
            if self.drops_args:
                return self.fn()
            return self.fn(*args)

    class Button(Widget):
        def __init__(self):
            Widget.__init__(self, "button")

    class ThinBoard(Widget):
        def __init__(self):
            Widget.__init__(self, "thinboard")

    ui.Window = Window
    ui.ScriptWindow = ScriptWindow
    ui.Bar = Window
    ui.ThinBoard = ThinBoard
    ui.Button = Button
    ui.PythonScriptLoader = PythonScriptLoader
    setattr(ui, "__mem_func__", mem_func)
    ui.EditLine = types.SimpleNamespace(OnIMEUpdate=lambda line: None)
    return ui


class LocaleInfo(types.ModuleType):
    """localeInfo: every unknown name is its own name, so tests compare keys."""

    def __init__(self, **values):
        types.ModuleType.__init__(self, "localeInfo")
        self.__dict__.update(values)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return name


def number_to_money(n):
    return "%s Yang" % "{:,}".format(int(n))
