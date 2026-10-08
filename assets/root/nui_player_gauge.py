"""NovaUI player gauge, the HP gauge over the player's head
(nui/windows/player-gauge/player-gauge.rml).

While the "player-gauge" window flag is on, GameWindow.__init__ makes
PlayerGauge below through nui_windows.make() instead of
uiPlayerGauge.PlayerGauge: the facade of the legacy gauge, with its name,
constructor and the methods the game window calls (Hide, RefreshGauge from
RefreshStatus, EnableShowAlways and DisableShowAlways from the left Alt
key). Its show rules are legacy's exactly (uiplayergauge.py:33-59): always
shown while the names show, else a shown gauge hides above half HP and a
hidden one shows below half.

What legacy did from Python every frame is the engine's: the document's
nui-anchor places the gauge each frame under the main character's name tail
(textTail.GetPosition, 17dp lower while a chat bubble shows), and its value
follows the player.hp_ratio feed (FEEDS). So no Python runs per frame. The
board stays shown; the gauge shows while the model's `shown` is True."""

import player

import nui
import nui_hud

DOCUMENT = "nui/windows/player-gauge/player-gauge.rml"


class PlayerGaugeBoard(nui.Window):
	"""The gauge's document and model."""

	DOCUMENT = DOCUMENT
	MODEL = "player_gauge"
	FEEDS = {"hp_ratio": "player.hp_ratio"}

	def initial_model(self):
		return {"shown": False, "vid": 0, "hp_ratio": 0.0}


class PlayerGauge(object):
	"""uiPlayerGauge.PlayerGauge on NovaUI (GameWindow.playerGauge)."""

	NUI_FACADE = True
	KEY = "player-gauge"

	def __init__(self, parent):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.board = None
		self.curHP = 0
		self.maxHP = 0
		self.showAlways = False
		self.shown = False
		if not nui_hud.has_engine_2b():
			return
		try:
			self.board = PlayerGaugeBoard()
			if self.board._doc:
				self.board.set(shown=False, vid=int(player.GetMainCharacterIndex()))
				self.board.show()
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine_2b()

	def nui_discard(self):
		self._nui_discarded = True
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget(self.KEY, self)

	def Destroy(self):
		self.nui_discard()

	# --- the game window's calls -----------------------------------------------------

	def Show(self):
		self.shown = True
		self._set(shown=True)

	def Hide(self):
		self.shown = False
		self._set(shown=False)

	def IsShow(self):
		return self.shown

	def RefreshGauge(self):
		"""Exactly uiplayergauge.py:33-51; the value is the feed's, and the
		anchor follows the main character the game window names now."""
		self.curHP = player.GetStatus(player.HP)
		self.maxHP = player.GetStatus(player.MAX_HP)
		self._set(vid=int(player.GetMainCharacterIndex()))
		if self.showAlways:
			self.Show()
		elif self.IsShow():
			if self.curHP > self.maxHP // 2:
				self.Hide()
		elif self.curHP < self.maxHP // 2:
			self.Show()

	def EnableShowAlways(self):
		self.showAlways = True
		self.RefreshGauge()

	def DisableShowAlways(self):
		self.showAlways = False
		self.RefreshGauge()

	def _set(self, **values):
		if self.board is not None:
			self.board.set(**values)
