"""Python side of the NovaUI (RmlUi) windows.

OWNER: P2 (contract from the shared base; the bodies below are stubs).

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
    initial_model(); set() with a different kind fails and logs.
  * Handlers get the evaluated data-event arguments as plain Python values
    (int, float, str, bool, list, dict, None).
  * After a hot reload or a locale change the document is re-loaded in place:
    element handlers registered with element_on() are re-attached for you,
    then on_reload() runs.

The C++ module `_nui` (src/NovaUI/Python) is the only thing this file calls;
when it is missing or has no runtime (headless tests) is_available() is False
and every Window method is a no-op that returns a falsy value.
"""

try:
	import _nui
except ImportError:  # pragma: no cover - client builds always have it
	_nui = None


def is_available():
	"""True when the `_nui` module is present and the client created a runtime."""
	raise NotImplementedError


def enabled_for_locale():
	"""False for locales NovaUI cannot render yet (right-to-left scripts), so
	callers keep the legacy window there."""
	raise NotImplementedError


def on(event_name):
	"""Method decorator: the method handles data-event `event_name` of the
	window's model and is called with the evaluated arguments."""
	raise NotImplementedError


class Window(object):
	"""One document plus its data model and handlers. Subclass per window."""

	DOCUMENT = None   # asset path of the .rml (required)
	MODEL = None      # data model name the document binds to, or None
	MODAL = False     # show() as a modal document

	def __init__(self):
		"""Creates the model (if MODEL) from initial_model(), loads DOCUMENT,
		binds @on handlers. The document starts hidden."""
		raise NotImplementedError

	def initial_model(self):
		"""Top-level model keys and their initial values."""
		return {}

	def show(self):
		raise NotImplementedError

	def hide(self):
		raise NotImplementedError

	def is_visible(self):
		raise NotImplementedError

	def set(self, **values):
		"""Replace model keys; only the views that use them update."""
		raise NotImplementedError

	def get(self, key):
		"""Current value of a model key (a copy), or None if unknown."""
		raise NotImplementedError

	def element_on(self, element_id, event, fn):
		"""Plain DOM event on the element with this id ("click", "dragstart",
		"keydown", ...); fn receives a dict with "type", "target_id" and, for
		mouse events, "button"."""
		raise NotImplementedError

	def on_reload(self):
		"""Hook: the document was re-loaded in place (hot reload, locale)."""
		pass

	def destroy(self):
		"""Close the document, drop the model and every handler."""
		raise NotImplementedError


# --- appearance -------------------------------------------------------------
# Each setter applies immediately and persists to config/metin2.cfg through
# systemSetting (UI_THEME, UI_SCALE, UI_REDUCED_MOTION).

def set_theme(name):
	""""dark" or "light"."""
	raise NotImplementedError


def get_theme():
	raise NotImplementedError


def set_scale_percent(percent):
	"""0 = automatic (from the resolution), else 75..200."""
	raise NotImplementedError


def get_scale_percent():
	"""The saved choice: 0 for automatic."""
	raise NotImplementedError


def get_scale():
	"""The scale factor in use now (1.0 = 100%)."""
	raise NotImplementedError


def get_auto_scale():
	"""The factor automatic mode would pick for the current resolution."""
	raise NotImplementedError


def set_reduced_motion(on):
	raise NotImplementedError


def is_reduced_motion():
	raise NotImplementedError


def refresh_strings():
	"""Push uiScriptLocale ("ui") and localeInfo ("game") to the runtime so
	@ui.KEY / @game.KEY resolve; re-loads open documents."""
	raise NotImplementedError
