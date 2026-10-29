"""The guild war accept dialog (nui/windows/guild-war-accept/
guild-war-accept.rml; P16 spec 5.10): its board and its facade.

While the guild-war-dialogs flag is on, the game window
(game.GameWindow.__GuildWar_OpenAskDialog, when the guild master receives a
declaration) makes AcceptGuildWarDialog below through nui_windows.make()
instead of uiGuild.AcceptGuildWarDialog: a subclass of the legacy class
whose loader (__CreateDialog) puts proxies where the uiscript's widgets
were, so Open (the declaring guild's name and type, and its member cap and
end score, NOVA-90: each line shown only when the server sent a value, the
cap as each guild's half), the type buttons (which choose the declared type
again, as legacy's), OK (the game window's "/war <name>") and Cancel or the
close button ("/nowar <name>") are legacy's code. The type hints are the
declare dialog's (nui_guild_war_declare).

A modal (D12) above the legacy UI layer that the scrim centers
(nui_facade.DialogFacade). It has no field, and legacy's dialog handles no
key, so no key is kept."""

import constInfo
import uiGuild

import nui
import nui_facade
import nui_guild_war_declare as declare
import nui_proxies

DOCUMENT = "nui/windows/guild-war-accept/guild-war-accept.rml"


class _AcceptBoard(declare.WarDialogBoard):
	"""The accept dialog's document: the declare board's handlers, named
	here so lint (NUI006) finds them in this module."""

	DOCUMENT = DOCUMENT
	MODEL = "guild_war_accept"

	@nui.on("board_press")
	def on_board_press(self, button):
		declare.WarDialogBoard.on_board_press(self, button)

	@nui.on("type_press")
	def on_type_press(self, index, button):
		declare.WarDialogBoard.on_type_press(self, index, button)

	@nui.on("accept_press")
	def on_accept_press(self, button):
		declare.WarDialogBoard.on_accept_press(self, button)

	@nui.on("cancel_press")
	def on_cancel_press(self, button):
		declare.WarDialogBoard.on_cancel_press(self, button)

	@nui.on("close_press")
	def on_close_press(self, button):
		declare.WarDialogBoard.on_close_press(self, button)


class AcceptGuildWarDialog(declare.WarDialogMixin, nui_facade.DialogFacade, uiGuild.AcceptGuildWarDialog):
	"""uiGuild.AcceptGuildWarDialog on NovaUI (game.GameWindow.guildWarQuestionDialog)."""

	KEY = "guild-war-accept"
	BOARD = _AcceptBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiGuild.AcceptGuildWarDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		# members and score (NOVA-90): the war's limit lines legacy's Open
		# writes, each with its shown state.
		return {"type": 0, "type_select": constInfo.GUILD_WAR_TYPE_SELECT_ENABLE != 0, "hints": declare.type_hints(),
		        "name": "", "members": "", "members_shown": False, "score": "", "score_shown": False}

	def _on_name(self, text):
		self.nui_set(name=text or "")

	def _limit_line(self, key):
		"""A limit's text line (uiscript MembersCount, EndScore): its text and
		its shown state reach the model keys `key` and `key`_shown."""
		line = nui_proxies.TextProxy(lambda text: self.nui_set(**{key: nui.plain_text(text or "")}))
		line.on_show = lambda shown: self.nui_set(**{key + "_shown": bool(shown)})
		return line

	# --- the loader (uiguild.py AcceptGuildWarDialog.__CreateDialog, on proxies) -----------

	def _AcceptGuildWarDialog__CreateDialog(self):
		# The uiscript's style (acceptguildwardialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")

		self.board = declare.TitledBoardProxy(230, 175)
		self.typeButtonList = self._make_type_buttons()
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.inputSlot = nui_proxies.BoardProxy(130, 18)
		self.inputValue = nui_proxies.TextProxy(self._on_name)
		self.membersCountText = self._limit_line("members")
		self.endScoreText = self._limit_line("score")

		gameType = self._game_type()

		self.typeButtonList[0].SAFE_SetEvent(self._AcceptGuildWarDialog__OnClickTypeButtonNormal)
		self.typeButtonList[1].SAFE_SetEvent(self._AcceptGuildWarDialog__OnClickTypeButtonWarp)
		self.typeButtonList[2].SAFE_SetEvent(self._AcceptGuildWarDialog__OnClickTypeButtonCTF)

		self._AcceptGuildWarDialog__ClickRadioButton(self.typeButtonList, 0)
