"""NovaUI loading screen (nui/windows/loading/loading.rml).

While the "loading" window flag is on, networkModule.MainStream's loading
setters make LoadingWindow below through nui_windows.make() instead of
introLoading.LoadingWindow. It subclasses the legacy class, which stays the
phase window C++ talks to: LoadData (PythonNetworkStreamPhaseLoading.cpp),
DEBUG_LoadData, OnUpdate (the load steps), OnPressEscapeKey (back to the
login), every __Load* and __Register* step and __StartGame are inherited
unchanged. Only the screen moves to the document: no uiscript is loaded;
the background, the emblem animation (nui-frames) and the gauge come from
the model, and the gauge shows the progress at once. The modern looks add
"Preparing <name>" (the chosen slot's character) and a badge of the empire
and the channel over the gauge, both set once at Open.

The document loads hidden in __init__, so nui_windows.make() can test it
(nui_ready); a window whose document did not load is discarded
(nui_discard) and then skips the legacy net.SetPhaseWindow(..., 0) when it
is collected, so it cannot clear the slot of the legacy window made in its
place."""

import weakref

import app
import net
import ui
import uiScriptLocale

import introLoading
import nui

DOCUMENT = "nui/windows/loading/loading.rml"

# introloading.py:81-110, in its order; Open picks one with app.GetRandom.
BACKGROUNDS = (
	# Base
	"d:/ymir work/uiloading/base/background_loading_warrior.sub",
	"d:/ymir work/uiloading/base/background_loading_shaman.sub",
	"d:/ymir work/uiloading/base/background_loading_sura.sub",
	"d:/ymir work/uiloading/base/background_loading_assassin.sub",
	"d:/ymir work/uiloading/base/background_loading_assassin2.sub",
	"d:/ymir work/uiloading/base/background_loading_assassin3.sub",
	"d:/ymir work/uiloading/base/background_loading_sura2.sub",
	"d:/ymir work/uiloading/base/background_loading_assassin3.sub",
	# Grotto
	"d:/ymir work/uiloading/grotto/background_loading_samahi1.sub",
	"d:/ymir work/uiloading/grotto/background_loading_warrior5.sub",
	"d:/ymir work/uiloading/grotto/background_loading_warriorghist1.sub",
	# Catacomb
	"d:/ymir work/uiloading/catacomb/loading0.sub",
	"d:/ymir work/uiloading/catacomb/loading1.sub",
	"d:/ymir work/uiloading/catacomb/loading2.sub",
	"d:/ymir work/uiloading/catacomb/loading3.sub",
	# Dark Dragons
	"d:/ymir work/uiloading/dark_dragons/loading0.sub",
	"d:/ymir work/uiloading/dark_dragons/loading1.sub",
	"d:/ymir work/uiloading/dark_dragons/loading2.sub",
	"d:/ymir work/uiloading/dark_dragons/loading3.sub",
	# Purgatory
	"d:/ymir work/uiloading/purgatory/loading0.sub",
	"d:/ymir work/uiloading/purgatory/loading1.sub",
	"d:/ymir work/uiloading/purgatory/loading2.sub",
	"d:/ymir work/uiloading/purgatory/loading3.sub",
)


EMPIRE_LETTERS = {net.EMPIRE_A: "a", net.EMPIRE_B: "b", net.EMPIRE_C: "c"}


def preparing_text(name):
	"""NUI_LOADING_PREPARING with the character's name ("Preparing %s"),
	through plain_text; "" without a name."""
	if not isinstance(name, str) or not name:
		return ""
	text = getattr(uiScriptLocale, "NUI_LOADING_PREPARING", "%s")
	if not isinstance(text, str) or "%s" not in text:
		text = "%s"
	return nui.plain_text(text.replace("%s", name, 1))


def badge_text(empire_id, server_info):
	"""The empire's name as its locale key and the channel from the server
	info text intrologin sets ("<server>, <channel>"), joined by a middle
	dot; either alone when the other is missing (a login by address has no
	channel part), "" without both."""
	parts = []
	letter = EMPIRE_LETTERS.get(empire_id)
	if letter:
		parts.append("@game.EMPIRE_" + letter.upper())
	text = server_info.strip() if isinstance(server_info, str) else ""
	if ", " in text:
		channel = text.rsplit(", ", 1)[1].strip()
		if channel:
			parts.append(nui.plain_text(channel))
	return " · ".join(parts)


def _keep(owner):
	"""The owner as a weak proxy; an object that takes no weak reference (a
	plain object() from a fixture check) is kept as it is. The board never
	calls it while it is being made."""
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def progress_value(percent):
	"""The gauge value for a load step's percent, as legacy SetPercentage
	shows it: 2 + 98 * p / 100 out of 100."""
	return 2.0 + 98.0 * percent / 100.0


class LoadingBoard(nui.Window):
	"""The loading screen's document and model. It has no data events."""

	DOCUMENT = DOCUMENT
	MODEL = "loading"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"background": "", "progress": progress_value(0), "error": False, "preparing": "", "badge": ""}


class ErrorLine(object):
	"""errMsg: the legacy error text line. The inherited OnUpdate calls
	Show() when a load step fails; here that shows the board's error line."""

	def __init__(self, board):
		self._board = board

	def Show(self):
		if self._board is not None:
			self._board.set(error=True)

	def Hide(self):
		if self._board is not None:
			self._board.set(error=False)

	def IsShow(self):
		return bool(self._board is not None and self._board.get("error"))


class LoadingWindow(introLoading.LoadingWindow):
	"""introLoading.LoadingWindow with its screen on NovaUI."""

	def __init__(self, stream):
		introLoading.LoadingWindow.__init__(self, stream)
		self._nui_discarded = False
		self.board = None
		try:
			self.board = LoadingBoard(self)
		except Exception:
			self.nui_discard()
			raise

	def __del__(self):
		self._destroy_board()
		if getattr(self, "_nui_discarded", False):
			ui.Window.__del__(self)
			return
		introLoading.LoadingWindow.__del__(self)

	# --- the nui_windows.make() protocol ------------------------------------------

	def nui_ready(self):
		return getattr(self, "board", None) is not None and bool(self.board._doc)

	def nui_discard(self):
		self._nui_discarded = True
		self._destroy_board()

	def _destroy_board(self):
		board = getattr(self, "board", None)
		self.board = None
		if board is not None:
			board.destroy()

	def _set(self, **values):
		if self.board is not None:
			self.board.set(**values)

	# --- the legacy surface -------------------------------------------------------

	def Open(self):
		self.errMsg = ErrorLine(self.board)
		background = BACKGROUNDS[app.GetRandom(0, len(BACKGROUNDS) - 1)]
		self._set(background=background, progress=progress_value(0), error=False)
		if self.board is not None:
			self.board.show()
		self.Show()

		chrSlot = self.stream.GetCharacterSlot()
		name = net.GetAccountCharacterSlotDataString(chrSlot, net.ACCOUNT_CHARACTER_SLOT_NAME)
		self._set(preparing=preparing_text(name), badge=badge_text(net.GetEmpireID(), net.GetServerInfo()))
		net.SendSelectCharacterPacket(chrSlot)

		app.SetFrameSkip(0)

	def Close(self):
		app.SetFrameSkip(1)

		self.loadStepList = []
		self.errMsg = 0
		self._destroy_board()
		self.Hide()

	def __SetProgress(self, p):
		self._set(progress=progress_value(p))
