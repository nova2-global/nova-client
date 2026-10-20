"""NovaUI target board (nui/windows/target/target.rml).

While the "target" window flag is on, GameWindow.__init__ makes TargetBoard
below through nui_windows.make() instead of uiTarget.TargetBoard: the facade
of the legacy class, which game.py and the C++ callbacks behind it
(SetPCTargetBoard, RefreshTargetBoardByVID and ByName, SetHPTargetBoard,
CloseTargetBoard and CloseTargetBoardIfDifferent) call as they call the
legacy one. Its document is TargetBoardBoard.

The logic is uitarget.py's: the other-empire rule, the main character's
menu (dismount, the end of the observer mode), buildings hidden, the level
and grade in front of a monster's name, RefreshButton's rules for the
relation buttons and each button's packet. The button ids, their locale
entries and the grade names are read from the legacy class. The legacy
board measured the distance to its target every frame to show the exchange
button within EXCHANGE_LIMIT_RANGE; here C++ watches it
(nuigame.WatchTargetRange, the target.in_range feed) and the button shows
by that key, so no Python runs per frame. Escape closes the board in its
legacy place in the Escape chain (nui_hud.EscapeProxy, shown with it)."""

import weakref

import chr
import constInfo
import guild
import localeInfo
import messenger
import net
import nonplayer
import player

import nui
import nui_hud
import ui
import uiCommon
import uiTarget

try:
	import nuigame
except ImportError:  # an exe without the Wave 2a engine: nui_hud.has_engine() is False
	nuigame = None

DOCUMENT = "nui/windows/target/target.rml"

_Legacy = uiTarget.TargetBoard


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def _watch(vid, distance):
	if nuigame is not None:
		nuigame.WatchTargetRange(vid, distance)


class TargetBoardBoard(nui.Window):
	"""The target board's document, model and handlers."""

	DOCUMENT = DOCUMENT
	MODEL = "target"
	FEEDS = {"in_range": "target.in_range"}

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"name": "", "hp": 0.0, "show_hp": False, "buttons": [], "exchange_at": -1, "in_range": False}

	@nui.on("press")
	def on_press(self, button_id, button):
		if button == 0:
			self._owner.nui_press(button_id)

	@nui.on("close")
	def on_close(self, button):
		if button == 0:
			self._owner.OnPressedCloseButton()


class TargetBoard(object):
	"""uiTarget.TargetBoard on NovaUI (GameWindow.targetBoard)."""

	NUI_FACADE = True

	BTN_WHISPER = _Legacy.BTN_WHISPER
	BTN_EXCHANGE = _Legacy.BTN_EXCHANGE
	BTN_FIGHT = _Legacy.BTN_FIGHT
	BTN_ACCEPT_FIGHT = _Legacy.BTN_ACCEPT_FIGHT
	BTN_AVENGE = _Legacy.BTN_AVENGE
	BTN_FRIEND = _Legacy.BTN_FRIEND
	BTN_INVITE_PARTY = _Legacy.BTN_INVITE_PARTY
	BTN_LEAVE_PARTY = _Legacy.BTN_LEAVE_PARTY
	BTN_EXCLUDE = _Legacy.BTN_EXCLUDE
	BTN_INVITE_GUILD = _Legacy.BTN_INVITE_GUILD
	BTN_REMOVE_GUILD = _Legacy.BTN_REMOVE_GUILD
	BTN_DISMOUNT = _Legacy.BTN_DISMOUNT
	BTN_EXIT_OBSERVER = _Legacy.BTN_EXIT_OBSERVER
	BTN_VIEW_EQUIPMENT = _Legacy.BTN_VIEW_EQUIPMENT
	BTN_REQUEST_ENTER_PARTY = _Legacy.BTN_REQUEST_ENTER_PARTY
	BTN_BUILDING_DESTROY = _Legacy.BTN_BUILDING_DESTROY
	BTN_EMOTION_ALLOW = _Legacy.BTN_EMOTION_ALLOW
	BTN_VOTE_BLOCK_CHAT = _Legacy.BTN_VOTE_BLOCK_CHAT
	BUTTON_CONFIG = _Legacy.BUTTON_CONFIG
	EXCHANGE_LIMIT_RANGE = _Legacy.EXCHANGE_LIMIT_RANGE

	def __init__(self):
		nui_hud.take_over("target", self)
		self._nui_discarded = False
		self.board = None
		self.escape = None
		self.eventWhisper = None
		self.questionDialog = None
		# The labels, resolved at construction as legacy resolves them.
		self.buttonLabels = dict((button_id, nui_hud.locale_text(attribute) or attribute)
		                         for button_id, attribute in self.BUTTON_CONFIG)
		self.buttonEvents = {
			self.BTN_WHISPER: self.OnWhisper,
			self.BTN_EXCHANGE: self.OnExchange,
			self.BTN_FIGHT: self.OnPVP,
			self.BTN_ACCEPT_FIGHT: self.OnPVP,
			self.BTN_AVENGE: self.OnPVP,
			self.BTN_FRIEND: self.OnAppendToMessenger,
			self.BTN_INVITE_PARTY: self.OnPartyInvite,
			self.BTN_LEAVE_PARTY: self.OnPartyExit,
			self.BTN_EXCLUDE: self.OnPartyRemove,
			self.BTN_INVITE_GUILD: self.__OnGuildAddMember,
			self.BTN_REMOVE_GUILD: self.__OnGuildRemoveMember,
			self.BTN_DISMOUNT: self.__OnDismount,
			self.BTN_EXIT_OBSERVER: self.__OnExitObserver,
			self.BTN_VIEW_EQUIPMENT: self.__OnViewEquipment,
			self.BTN_REQUEST_ENTER_PARTY: self.__OnRequestParty,
			self.BTN_BUILDING_DESTROY: self.__OnDestroyBuilding,
			self.BTN_EMOTION_ALLOW: self.__OnEmotionAllow,
			self.BTN_VOTE_BLOCK_CHAT: self.__OnVoteBlockChat,
		}
		# Legacy keeps every button in its showing list after construction
		# and hides them all; a later ShowDefaultButton shows that list.
		self.showingButtonList = [button_id for button_id, attribute in self.BUTTON_CONFIG]
		self.shownButtons = set()
		self.nameString = ""
		self.nameLength = 0
		self.vid = 0
		self.isShowButton = False
		self.hpShown = False
		self.hp = 0.0
		if not nui_hud.has_engine():
			return
		try:
			self.board = TargetBoardBoard(self)
			self.escape = nui_hud.EscapeProxy(self.OnPressedCloseButton)
		except Exception:
			self.nui_discard()
			raise
		self.__Initialize()
		self.ResetTargetBoard()

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		escape, self.escape = self.escape, None
		if escape is not None:
			escape.destroy()
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("target", self)

	def __Initialize(self):
		self.nameString = ""
		self.nameLength = 0
		self.vid = 0
		self.isShowButton = False

	# --- the window ---------------------------------------------------------------

	def Destroy(self):
		if self.vid:
			_watch(0, 0)
		self.eventWhisper = None
		self.__Initialize()
		self.nui_discard()

	def Show(self):
		if self.board is not None:
			self.board.show()
		if self.escape is not None:
			self.escape.show()

	def Hide(self):
		if self.board is not None:
			self.board.hide()
		if self.escape is not None:
			self.escape.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	def SetTop(self):
		if self.board is not None:
			self.board.bring_to_front()

	def UpdatePosition(self):
		"""The board keeps itself at the top center (its sheet)."""
		pass

	def OnPressEscapeKey(self):
		self.OnPressedCloseButton()
		return True

	def OnPressedCloseButton(self):
		player.ClearTarget()
		self.Close()

	def Close(self):
		_watch(0, 0)
		self.__Initialize()
		self.Hide()

	def Open(self, vid, name):
		if vid:
			if not constInfo.GET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD():
				if not player.IsSameEmpire(vid):
					self.Hide()
					return

			if vid != self.GetTargetVID():
				self.ResetTargetBoard()
				self.SetTargetVID(vid)
				self.SetTargetName(name)

			if player.IsMainCharacterIndex(vid):
				self.__ShowMainCharacterMenu()
			elif chr.INSTANCE_TYPE_BUILDING == chr.GetInstanceType(self.vid):
				self.Hide()
			else:
				self.RefreshButton()
				self.Show()
		else:
			self.HideAllButton()
			self.__ShowButton(self.BTN_WHISPER)
			self.__ShowButton(self.BTN_VOTE_BLOCK_CHAT)
			self.__ArrangeButtonPosition()
			self.SetTargetName(name)
			self.Show()

	def Refresh(self):
		if self.IsShow():
			if self.IsShowButton():
				self.RefreshButton()

	def RefreshByVID(self, vid):
		if vid == self.GetTargetVID():
			self.Refresh()

	def RefreshByName(self, name):
		if name == self.GetTargetName():
			self.Refresh()

	def __ShowMainCharacterMenu(self):
		canShow = 0
		self.HideAllButton()
		if player.IsMountingHorse():
			self.__ShowButton(self.BTN_DISMOUNT)
			canShow = 1
		if player.IsObserverMode():
			self.__ShowButton(self.BTN_EXIT_OBSERVER)
			canShow = 1
		if canShow:
			self.__ArrangeButtonPosition()
			self.Show()
		else:
			self.Hide()

	def SetWhisperEvent(self, event):
		self.eventWhisper = event

	def ResetTargetBoard(self):
		_watch(0, 0)
		self.shownButtons = set()
		self.__Initialize()
		self.hpShown = False
		self._sync()

	def SetTargetVID(self, vid):
		self.vid = vid

	def SetEnemyVID(self, vid):
		self.SetTargetVID(vid)
		name = chr.GetNameByVID(vid)
		level = nonplayer.GetLevelByVID(vid)
		grade = nonplayer.GetGradeByVID(vid)
		nameFront = ""
		if -1 != level:
			nameFront += "Lv." + str(level) + " "
		if grade in _Legacy.GRADE_NAME:
			nameFront += "(" + _Legacy.GRADE_NAME[grade] + ") "
		self.SetTargetName(nameFront + name)

	def GetTargetVID(self):
		return self.vid

	def GetTargetName(self):
		return self.nameString

	def SetTargetName(self, name):
		self.nameString = name
		self.nameLength = len(name)
		self._sync()

	def SetHP(self, hpPercentage):
		self.hpShown = True
		self.hp = min(1.0, max(0.0, float(hpPercentage) / 100.0))
		self._sync()

	def ShowDefaultButton(self):
		self.isShowButton = True
		self.showingButtonList.append(self.BTN_WHISPER)
		self.showingButtonList.append(self.BTN_EXCHANGE)
		self.showingButtonList.append(self.BTN_FIGHT)
		self.showingButtonList.append(self.BTN_EMOTION_ALLOW)
		self.shownButtons.update(self.showingButtonList)
		self._sync()

	def HideAllButton(self):
		self.isShowButton = False
		self.shownButtons.difference_update(self.showingButtonList)
		self.showingButtonList = []
		self._sync()

	def __ShowButton(self, name):
		if name not in self.buttonEvents:
			return
		self.shownButtons.add(name)
		self.showingButtonList.append(name)

	def __HideButton(self, name):
		if name not in self.buttonEvents:
			return
		self.shownButtons.discard(name)
		if name in self.showingButtonList:
			self.showingButtonList.remove(name)

	def IsShowButton(self):
		return self.isShowButton

	def RefreshButton(self):
		self.HideAllButton()

		if chr.INSTANCE_TYPE_BUILDING == chr.GetInstanceType(self.vid):
			return

		if player.IsPVPInstance(self.vid) or player.IsObserverMode():
			return

		self.ShowDefaultButton()

		def isGuildMaster(name):
			return guild.GetGuildMasterName() == name

		def isGuildMember(name, vid):
			return guild.IsMemberByName(name) and chr.GetGuildID(vid) != 0

		def isNotGuildMember(name, vid):
			return not guild.IsMemberByName(name) and chr.GetGuildID(vid) == 0

		guildAuthorityButtons = {
			guild.AUTH_ADD_MEMBER: {
				"btn": self.BTN_INVITE_GUILD,
				"condition": lambda: isNotGuildMember(self.nameString, self.vid),
			},
			guild.AUTH_REMOVE_MEMBER: {
				"btn": self.BTN_REMOVE_GUILD,
				"condition": lambda: isGuildMember(self.nameString, self.vid) and not isGuildMaster(self.nameString),
			},
		}
		for guildAuthority, guildButton in guildAuthorityButtons.items():
			hasAuthority = guild.MainPlayerHasAuthority(guildAuthority)
			satisfiesCondition = guildButton["condition"]()
			if hasAuthority and satisfiesCondition:
				self.__ShowButton(guildButton["btn"])

		if not messenger.IsFriendByName(self.nameString):
			self.__ShowButton(self.BTN_FRIEND)

		if player.IsPartyMember(self.vid):
			self.__HideButton(self.BTN_FIGHT)
			if player.IsPartyLeader(self.vid):
				self.__ShowButton(self.BTN_LEAVE_PARTY)
			elif player.IsPartyLeader(player.GetMainCharacterIndex()):
				self.__ShowButton(self.BTN_EXCLUDE)
		else:
			if player.IsPartyMember(player.GetMainCharacterIndex()):
				if player.IsPartyLeader(player.GetMainCharacterIndex()):
					self.__ShowButton(self.BTN_INVITE_PARTY)
			else:
				if chr.IsPartyMember(self.vid):
					self.__ShowButton(self.BTN_REQUEST_ENTER_PARTY)
				else:
					self.__ShowButton(self.BTN_INVITE_PARTY)

			if player.IsRevengeInstance(self.vid):
				self.__HideButton(self.BTN_FIGHT)
				self.__ShowButton(self.BTN_AVENGE)
			elif player.IsChallengeInstance(self.vid):
				self.__HideButton(self.BTN_FIGHT)
				self.__ShowButton(self.BTN_ACCEPT_FIGHT)
			elif player.IsCantFightInstance(self.vid):
				self.__HideButton(self.BTN_FIGHT)

			if not player.IsSameEmpire(self.vid):
				self.__HideButton(self.BTN_INVITE_PARTY)
				self.__HideButton(self.BTN_FRIEND)
				self.__HideButton(self.BTN_FIGHT)

		# The exchange button shows within EXCHANGE_LIMIT_RANGE, as legacy
		# measured it here and then every frame; from now on C++ watches the
		# distance (target.in_range).
		distance = player.GetCharacterDistance(self.vid)
		if self.board is not None:
			self.board.set(in_range=not (distance > self.EXCHANGE_LIMIT_RANGE))
		_watch(self.vid, self.EXCHANGE_LIMIT_RANGE)
		self.__ArrangeButtonPosition()

	def __ArrangeButtonPosition(self):
		self._sync()

	# --- the buttons ----------------------------------------------------------------

	def nui_press(self, button_id):
		if button_id not in self.shownButtons:
			return
		event = self.buttonEvents.get(button_id)
		if event:
			event()

	def OnWhisper(self):
		if None != self.eventWhisper:
			self.eventWhisper(self.nameString)

	def OnExchange(self):
		net.SendExchangeStartPacket(self.vid)

	def OnPVP(self):
		net.SendChatPacket("/pvp %d" % (self.vid))

	def OnAppendToMessenger(self):
		net.SendMessengerAddByVIDPacket(self.vid)

	def OnPartyInvite(self):
		net.SendPartyInvitePacket(self.vid)

	def OnPartyExit(self):
		net.SendPartyExitPacket()

	def OnPartyRemove(self):
		net.SendPartyRemovePacket(self.vid)

	def __OnGuildAddMember(self):
		net.SendGuildAddMemberPacket(self.vid)

	def __OnGuildRemoveMember(self):
		self.questionDialog = uiCommon.QuestionDialog()
		self.questionDialog.SetText(localeInfo.GUILD_REMOVE_MEMBER_QUESTION)
		self.questionDialog.SetAcceptEvent(ui.__mem_func__(self.__OnGuildRemoveMemberAccept))
		self.questionDialog.SetCancelEvent(ui.__mem_func__(self.__OnGuildRemoveMemberClose))
		self.questionDialog.Open()

	def __OnGuildRemoveMemberAccept(self):
		net.SendGuildRemoveMemberPacket(self.nameString)
		self.__OnGuildRemoveMemberClose()

	def __OnGuildRemoveMemberClose(self):
		if self.questionDialog is not None:
			self.questionDialog.Close()
		self.questionDialog = None
		return True

	def __OnDismount(self):
		net.SendChatPacket("/unmount")

	def __OnExitObserver(self):
		net.SendChatPacket("/observer_exit")

	def __OnViewEquipment(self):
		net.SendChatPacket("/view_equip " + str(self.vid))

	def __OnRequestParty(self):
		net.SendChatPacket("/party_request " + str(self.vid))

	def __OnDestroyBuilding(self):
		net.SendChatPacket("/build d %d" % (self.vid))

	def __OnEmotionAllow(self):
		net.SendChatPacket("/emotion_allow %d" % (self.vid))

	def __OnVoteBlockChat(self):
		cmd = "/vote_block_chat %s" % (self.nameString)
		net.SendChatPacket(cmd)

	# --- the model ---------------------------------------------------------------------

	def _sync(self):
		if self.board is None:
			return
		buttons = []
		seen = set()
		# The exchange button's index: the markup hides that slot out of range.
		exchange_at = -1
		for button_id in self.showingButtonList:
			if button_id in self.shownButtons and button_id not in seen:
				seen.add(button_id)
				if button_id == self.BTN_EXCHANGE:
					exchange_at = len(buttons)
				buttons.append({"id": button_id, "label": self.buttonLabels.get(button_id, "")})
		self.board.set(name=nui.plain_text(self.nameString), hp=self.hp, show_hp=self.hpShown, buttons=buttons,
		               exchange_at=exchange_at)
