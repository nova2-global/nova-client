"""NovaUI game buttons (nui/windows/game-buttons/game-buttons.rml).

While the "game-buttons" window flag is on, Interface.__MakeGameButtonWindow
makes GameButtonWindow below through nui_windows.make() instead of
uiGameButton.GameButtonWindow: the facade of the legacy class, with its six
buttons (stats, skills, tasks, help, guild building, the end of the observer
mode). As legacy: every button starts hidden and the observer button
follows player.IsObserverMode(); CheckGameButton, while the window shows,
shows the stat button with stat points, the skill button with skill points
and the help button at play time 0; the task button never shows again; the
observer button sends /observer_exit unless the Interface gives it another
event."""

import weakref

import app
import net
import player

import nui
import nui_hud

DOCUMENT = "nui/windows/game-buttons/game-buttons.rml"
BUTTONS = ("STATUS", "SKILL", "QUEST", "HELP", "BUILD", "EXIT_OBSERVER")
_MODEL_KEYS = {"STATUS": "show_status", "SKILL": "show_skill", "QUEST": "show_quest", "HELP": "show_help",
               "BUILD": "show_build", "EXIT_OBSERVER": "show_observer"}


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


class GameButtonBoard(nui.Window):
	DOCUMENT = DOCUMENT
	MODEL = "game_buttons"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return dict((key, False) for key in _MODEL_KEYS.values())

	@nui.on("press")
	def on_press(self, name, button):
		if button == 0:
			self._owner.nui_press(name)


class GameButtonWindow(object):
	"""uiGameButton.GameButtonWindow on NovaUI (the wndGameButton facade)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over("game-buttons", self)
		self._nui_discarded = False
		self.board = None
		self.gameButtonEvents = dict((name, 0) for name in BUTTONS)
		self.gameButtonEvents["EXIT_OBSERVER"] = self.__OnClickExitObserver
		if not nui_hud.has_engine():
			return
		try:
			self.board = GameButtonBoard(self)
		except Exception:
			self.nui_discard()
			raise
		self.SetObserverMode(player.IsObserverMode())

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("game-buttons", self)

	def _show_button(self, name, shown):
		if self.board is not None:
			self.board.set(**{_MODEL_KEYS[name]: bool(shown)})

	def Destroy(self):
		self.gameButtonEvents = {}
		self.nui_discard()

	def Show(self):
		if self.board is not None:
			self.board.show()

	def Hide(self):
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	def SetTop(self):
		if self.board is not None:
			self.board.bring_to_front()

	def SetButtonEvent(self, name, event):
		if name not in self.gameButtonEvents:
			print("GameButtonWindow.LoadScript - %s" % name)
			app.Abort()
			return
		self.gameButtonEvents[name] = event

	def ShowBuildButton(self):
		self._show_button("BUILD", True)

	def HideBuildButton(self):
		self._show_button("BUILD", False)

	def CheckGameButton(self):
		if not self.IsShow():
			return
		self._show_button("STATUS", player.GetStatus(player.STAT) > 0)
		self._show_button("SKILL", player.GetStatus(player.SKILL_ACTIVE) > 0)
		self._show_button("HELP", 0 == player.GetPlayTime())

	def SetObserverMode(self, isEnable):
		self._show_button("EXIT_OBSERVER", isEnable)

	def __OnClickExitObserver(self):
		net.SendChatPacket("/observer_exit")

	def nui_press(self, name):
		event = self.gameButtonEvents.get(name)
		if event:
			event()
