"""NovaUI locale flag strip (nui/windows/locale-strip/locale-strip.rml).

While the "locale-strip" window flag is on (nui_windows), the name
uilocaleselector.LocaleSelector makes the LocaleStrip facade below instead of
the legacy strip: the same names and meanings (Create, SetLocaleChangedEvent,
Destroy, the flag click with its confirm question), drawn by a document.

- The flags are uilocaleselector.AVAILABLE_LOCALES with their legacy flag
  art; the flag of the locale in use (config/locale.cfg) is selected.
- A flag acts on a left mousedown: the document never takes the focus, so a
  login field keeps its caret.
- The confirm is uiCommon.QuestionDialog(), the dialog kit's question when
  its flag is on, else the legacy one.
- Right-to-left: a confirm to ae closes and re-opens the login window, whose
  new strip is the legacy one (nui.enabled_for_locale), and a change back
  makes this one again.
"""

import weakref

import localeInfo
import ui
import uiCommon
import uilocaleselector

import nui

DOCUMENT = "nui/windows/locale-strip/locale-strip.rml"
LOCALE_CONFIG = "config/locale.cfg"
DEFAULT_LOCALE = "en"


def current_locale():
	"""The locale code intrologin.py saved in config/locale.cfg, "en" when
	there is none."""
	try:
		with open(LOCALE_CONFIG, "r") as file:
			code = file.read().strip().lower()
	except (IOError, OSError):
		return DEFAULT_LOCALE
	return code or DEFAULT_LOCALE


def flags():
	return [{"code": locale["code"], "name": nui.plain_text(locale["name"]),
		"image": uilocaleselector.FLAG_IMAGE_PATH % locale["flag"]}
		for locale in uilocaleselector.AVAILABLE_LOCALES]


class LocaleStripWindow(nui.Window):
	"""The strip's document. It reports flag presses to its owner, the
	LocaleStrip facade."""

	DOCUMENT = DOCUMENT
	MODEL = "locale_strip"

	def __init__(self, owner):
		self._owner = weakref.proxy(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"flags": flags(), "current": current_locale()}

	@nui.on("pick")
	def on_pick(self, code, button):
		if button != 0:
			return
		self._owner._OnClickFlag(code)


class LocaleStrip(object):
	"""uilocaleselector.LocaleSelector (uilocaleselector.py:54-192) on NovaUI."""

	def __init__(self):
		self.parent = None
		self.confirmDialog = None
		self.selectedLocaleCode = None
		self.eventLocaleChanged = None
		self._nui_discarded = False
		# Loaded here, hidden, so nui_windows.make() can test it.
		self.nui_window = LocaleStripWindow(self)

	# --- the nui_windows.make() protocol ------------------------------------------

	def nui_ready(self):
		return self.nui_window is not None and bool(self.nui_window._doc)

	def __del__(self):
		# A strip dropped without Destroy takes its document along.
		try:
			if self.nui_window is not None:
				self.nui_window.destroy()
		except Exception:
			pass

	def nui_discard(self):
		window, self.nui_window = self.nui_window, None
		if window is not None:
			window.destroy()
		self._nui_discarded = True

	# --- the legacy surface -----------------------------------------------------------

	def Create(self, parent):
		"""Shows the strip. The parent is kept weakly; nothing is parented."""
		self.parent = weakref.proxy(parent) if parent is not None else None
		if self.nui_window is not None:
			self.nui_window.show()

	def _CreateFlagButtons(self):
		pass  # the document makes the flags

	def Destroy(self):
		self.eventLocaleChanged = None
		self.selectedLocaleCode = None
		if self.confirmDialog:
			self.confirmDialog.Close()
			self.confirmDialog = None
		window, self.nui_window = self.nui_window, None
		if window is not None:
			window.destroy()

	def SetLocaleChangedEvent(self, event):
		self.eventLocaleChanged = event

	def _OnClickFlag(self, localeCode):
		self.selectedLocaleCode = localeCode
		localeName = "Unknown"
		for locale in uilocaleselector.AVAILABLE_LOCALES:
			if locale["code"] == localeCode:
				localeName = locale["name"]
				break
		if not self.confirmDialog:
			self.confirmDialog = uiCommon.QuestionDialog()
		self.confirmDialog.SetText(localeInfo.LOCALE_CHANGE_CONFIRM % localeName)
		self.confirmDialog.SetAcceptEvent(ui.__mem_func__(self._OnConfirmLocaleChange))
		self.confirmDialog.SetCancelEvent(ui.__mem_func__(self._OnCancelLocaleChange))
		self.confirmDialog.Open()

	def _OnConfirmLocaleChange(self):
		if self.confirmDialog:
			self.confirmDialog.Close()
		if not self.selectedLocaleCode:
			return
		if self.eventLocaleChanged:
			self.eventLocaleChanged(self.selectedLocaleCode)

	def _OnCancelLocaleChange(self):
		if self.confirmDialog:
			self.confirmDialog.Close()
		self.selectedLocaleCode = None

	# --- ui.Window shims intrologin.py uses ---------------------------------------------

	def Show(self):
		if self.nui_window is not None:
			self.nui_window.show()

	def Hide(self):
		if self.nui_window is not None:
			self.nui_window.hide()

	def IsShow(self):
		return self.nui_window is not None and self.nui_window.is_visible()

	def SetTop(self):
		if self.nui_window is not None:
			self.nui_window.bring_to_front()
