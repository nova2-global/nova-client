"""NovaUI empire select (nui/windows/empire/empire.rml).

While the "empire" window flag is on, networkModule.MainStream's empire
setters make SelectEmpireWindow and ReselectEmpireWindow below through
nui_windows.make() instead of the introEmpire classes. They subclass the
legacy classes, which stay the phase window C++ talks to and keep the
packets and the phase changes: ClickLeftButton, ClickRightButton,
ClickSelectButton (SendSelectEmpirePacket, then the next phase),
ClickExitButton and OnPressEscapeKey are inherited. The screen moves to the
document: no uiscript, and no per-frame Python (the areas fade with a CSS
transition, and OnUpdate does nothing). The description is plain
paragraphs (nui_desc_text, the G15 subset), so the Prev and Next pages are
gone.

The document loads hidden in __init__ (nui_ready, nui_discard and __del__
follow nui_windows.make()'s protocol, as nui_loading does)."""

import weakref

import app
import event
import net
import ui
import uiScriptLocale
import wndMgr

import introEmpire
import nui
import nui_desc_text

DOCUMENT = "nui/windows/empire/empire.rml"

FLAG_IMAGE = "d:/ymir work/ui/intro/empire/empireflag_%s.sub"
LETTERS = {net.EMPIRE_A: "a", net.EMPIRE_B: "b", net.EMPIRE_C: "c"}


def _keep(owner):
	"""The owner as a weak proxy; an object that takes no weak reference (a
	plain object() from a fixture check) is kept as it is. The board never
	calls it while it is being made."""
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def empire_model(empire_id):
	"""The model keys of one empire: its number, name key, flag and
	description paragraphs (read now, from the current locale)."""
	letter = LETTERS.get(empire_id)
	if letter is None:
		return {"empire": int(empire_id), "name": "", "flag_image": "", "paragraphs": []}
	path = getattr(uiScriptLocale, "EMPIREDESC_" + letter.upper(), "")
	return {"empire": int(empire_id), "name": "@game.EMPIRE_" + letter.upper(),
		"flag_image": FLAG_IMAGE % letter, "paragraphs": nui_desc_text.load(path) if path else []}


class EmpireBoard(nui.Window):
	"""The empire screen's document, model and handlers; it reports to its
	owner, the phase window."""

	DOCUMENT = DOCUMENT
	MODEL = "empire"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"empire": 1, "hover": 0, "name": "", "flag_image": "", "paragraphs": [], "title_image": ""}

	@nui.on("pick")
	def on_pick(self, empire_id):
		# The legacy area button: a press on another empire selects it.
		if self._owner.empireID != empire_id:
			self._owner.OnSelectEmpire(empire_id)

	@nui.on("hover")
	def on_hover(self, empire_id):
		self._owner.OnOverInEmpire(empire_id)

	@nui.on("unhover")
	def on_unhover(self, empire_id):
		self._owner.OnOverOutEmpire(empire_id)

	@nui.on("left")
	def on_left(self):
		self._owner.ClickLeftButton()

	@nui.on("right")
	def on_right(self):
		self._owner.ClickRightButton()

	@nui.on("choose")
	def on_choose(self):
		self._owner.ClickSelectButton()

	@nui.on("leave")
	def on_leave(self):
		self._owner.ClickExitButton()


class SelectEmpireWindow(introEmpire.SelectEmpireWindow):
	"""introEmpire.SelectEmpireWindow with its screen on NovaUI."""

	def __init__(self, stream):
		introEmpire.SelectEmpireWindow.__init__(self, stream)
		self._nui_discarded = False
		self.board = None
		try:
			self.board = EmpireBoard(self)
		except Exception:
			self.nui_discard()
			raise

	def __del__(self):
		self._destroy_board()
		if getattr(self, "_nui_discarded", False):
			ui.ScriptWindow.__del__(self)
			return
		introEmpire.SelectEmpireWindow.__del__(self)

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
		self.SetSize(wndMgr.GetScreenWidth(), wndMgr.GetScreenHeight())
		self.SetWindowName("SelectEmpireWindow")
		self.Show()

		self._set(title_image=uiScriptLocale.EMPIRE_PATH + "title.sub")
		self.OnSelectEmpire(self.empireID)
		if self.board is not None:
			self.board.show()
		app.ShowCursor()

	def Close(self):
		self._destroy_board()
		self.KillFocus()
		self.Hide()

		app.HideCursor()
		event.Destroy()

	def OnSelectEmpire(self, arg):
		self.empireID = arg
		self._set(**empire_model(arg))

	def OnOverInEmpire(self, arg):
		self._set(hover=arg)

	def OnOverOutEmpire(self, arg):
		# Only the area the pointer left; the next one may have lit already.
		if self.board is not None and self.board.get("hover") == arg:
			self.board.set(hover=0)

	def PrevDescriptionPage(self):
		pass  # the description scrolls; it has no pages (G15 subset)

	def NextDescriptionPage(self):
		pass

	def OnUpdate(self):
		pass  # the fades are CSS transitions


class ReselectEmpireWindow(SelectEmpireWindow):
	"""introEmpire.ReselectEmpireWindow: Choose goes on to the create phase
	and Exit back to the select phase."""

	def ClickSelectButton(self):
		net.SendSelectEmpirePacket(self.empireID)
		self.stream.SetCreateCharacterPhase()

	def ClickExitButton(self):
		self.stream.SetSelectCharacterPhase()
