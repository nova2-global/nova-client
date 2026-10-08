"""NovaUI guild war score boards (nui/windows/guild-war/guild-war.rml).

While the "guild-war" window flag is on, Interface.OnStartGuildWar makes
GuildWarScoreBoard below through nui_windows.make() instead of
uiGuild.GuildWarScoreBoard: the facade of one war's board, with its name,
constructor and the methods the Interface calls (Open, Show, SetScore,
UpdateMemberCount, Destroy). Every war is an entry of one document, made with
the first war and destroyed with the last (Destroy, from OnEndGuildWar and
Interface.Close). Legacy puts every board at (10, H - 100), so a second war
hid the first; here the boards stack upward 4dp apart, the first war at the
legacy place (P10 spec D19).

The texts are legacy's __RefreshName (uiguild.py:456-468): "name score"
until the server sends both member counts, then "name(count) score". A
guild's mark is a 16 x 12 region of the mark atlas the client downloads
(mark_source, spec D20); a guild without a mark shows none. A board's width
follows its text, where legacy computes it from the name's length."""

import guild

import nui
import nui_hud

DOCUMENT = "nui/windows/guild-war/guild-war.rml"
MARK_COLUMNS = 32     # marks per row of a 512 x 512 atlas (src/UserInterface/MarkImage.h)
MARK_WIDTH = 16
MARK_HEIGHT = 12

_board = None
_wars = []            # the open boards' facades, in the order opened
_next_key = [1]


def mark_source(guild_id):
	"""(src, rect) of the guild's mark for an <img>: the downloaded atlas as a
	rooted store path and the mark's region, as legacy's MarkBox draws it
	(GrpMarkInstance.cpp:56-68); ("", "") for a guild without a mark
	(GuildIDToMarkID answers -1)."""
	mark_id = guild.GuildIDToMarkID(guild_id)
	if mark_id is None or mark_id < 0:
		return ("", "")
	path = guild.GetMarkImageFilenameByMarkID(mark_id)
	if not path:
		return ("", "")
	index = guild.GetMarkIndexByMarkID(mark_id)
	rect = "%d %d %d %d" % ((index % MARK_COLUMNS) * MARK_WIDTH, (index // MARK_COLUMNS) * MARK_HEIGHT, MARK_WIDTH, MARK_HEIGHT)
	return ("/" + path.lstrip("/"), rect)


class GuildWarBoard(nui.Window):
	"""The war boards' one document and model."""

	DOCUMENT = DOCUMENT
	MODEL = "guild_war"

	def initial_model(self):
		return {"boards": []}


def _get_board():
	"""The shared document, made with the first war; None when it cannot load
	or the exe lacks the Wave 2b engine."""
	global _board
	if _board is not None and _board._doc:
		return _board
	if not nui_hud.has_engine_2b():
		return None
	_board = GuildWarBoard()
	if not _board._doc:
		_board = None
		return None
	_board.show()
	return _board


def _sync():
	"""Writes the shown boards, the newest first (the column's top); the
	document goes with the last war."""
	global _board
	if _board is None:
		return
	if not _wars:
		board, _board = _board, None
		board.destroy()
		return
	boards = [war._entry() for war in reversed(_wars) if war._shown and war._opened]
	_board.set(boards=boards)


def _drop(war):
	if war in _wars:
		_wars.remove(war)
		_sync()


class GuildWarScoreBoard(object):
	"""uiGuild.GuildWarScoreBoard on NovaUI (Interface.guildScoreBoardDict)."""

	NUI_FACADE = True

	def __init__(self):
		self._nui_discarded = False
		self._key = _next_key[0]
		_next_key[0] += 1
		self._shown = False
		self._opened = False
		self.board = _get_board()
		if self.board is not None:
			_wars.append(self)
		self.Initialize()

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine_2b()

	def nui_discard(self):
		self._nui_discarded = True
		if self in _wars:
			_drop(self)
		elif not _wars:
			_sync()

	# --- legacy's methods --------------------------------------------------------------

	def Initialize(self):
		"""As uiguild.py:384-388."""
		self.allyGuildID = 0
		self.enemyGuildID = 0
		self.allyDataDict = {}
		self.enemyDataDict = {}

	def Open(self, allyGuildID, enemyGuildID):
		"""As uiguild.py:390-430: the two guilds' names and marks, scores 0,
		member counts unknown (-1); then shown."""
		self.allyGuildID = allyGuildID
		self.enemyGuildID = enemyGuildID
		self.allyDataDict = self._data(allyGuildID)
		self.enemyDataDict = self._data(enemyGuildID)
		self._opened = True
		self.__RefreshName()
		self.Show()

	@staticmethod
	def _data(guild_id):
		return {"NAME": guild.GetGuildName(guild_id), "SCORE": 0, "MEMBER_COUNT": -1, "MARK": mark_source(guild_id),
		        "TEXT": ""}

	def __GetDataDict(self, ID):
		if self.allyGuildID == ID:
			return self.allyDataDict
		if self.enemyGuildID == ID:
			return self.enemyDataDict
		return None

	def SetScore(self, gainGuildID, opponetGuildID, point):
		"""As uiguild.py:440-445."""
		dataDict = self.__GetDataDict(gainGuildID)
		if not dataDict:
			return
		dataDict["SCORE"] = point
		self.__RefreshName()

	def UpdateMemberCount(self, guildID1, memberCount1, guildID2, memberCount2):
		"""As uiguild.py:447-454."""
		dataDict1 = self.__GetDataDict(guildID1)
		dataDict2 = self.__GetDataDict(guildID2)
		if dataDict1:
			dataDict1["MEMBER_COUNT"] = memberCount1
		if dataDict2:
			dataDict2["MEMBER_COUNT"] = memberCount2
		self.__RefreshName()

	def __RefreshName(self):
		"""Legacy's texts (uiguild.py:456-468); the width follows them."""
		ally, enemy = self.allyDataDict, self.enemyDataDict
		if -1 == ally["MEMBER_COUNT"] or -1 == enemy["MEMBER_COUNT"]:
			ally["TEXT"] = "%s %d" % (ally["NAME"], ally["SCORE"])
			enemy["TEXT"] = "%s %d" % (enemy["NAME"], enemy["SCORE"])
		else:
			ally["TEXT"] = "%s(%d) %d" % (ally["NAME"], ally["MEMBER_COUNT"], ally["SCORE"])
			enemy["TEXT"] = "%s(%d) %d" % (enemy["NAME"], enemy["MEMBER_COUNT"], enemy["SCORE"])
		self._changed()

	def Show(self):
		if not self._shown:
			self._shown = True
			self._changed()

	def Hide(self):
		if self._shown:
			self._shown = False
			self._changed()

	def IsShow(self):
		return self._shown

	def Destroy(self):
		"""The entry leaves; the document goes with the last war."""
		self._shown = False
		self._opened = False
		_drop(self)

	def _entry(self):
		rows = []
		for data in (self.allyDataDict, self.enemyDataDict):
			src, rect = data["MARK"]
			rows.append({"src": src, "rect": rect, "text": nui.plain_text(data["TEXT"])})
		return {"key": self._key, "rows": rows}

	def _changed(self):
		if self in _wars and self._opened:
			_sync()
