"""NovaUI party boards and menu (nui/windows/party/party.rml).

While the "party" window flag is on, Interface.__MakeParty makes PartyWindow
below through nui_windows.make() instead of uiParty.PartyWindow: the facade
of the legacy class, which the Interface and the C++ callbacks behind it
(AddPartyMember, UpdatePartyMemberInfo, RemovePartyMember, the links,
ChangePartyParameter) call as they call the legacy one. Its document is
PartyBoard: one board per member (the state button, the name, the HP gauge
and the nine party affect images with their tooltips), the role buttons a
leader opens beside a member's board, and the menu (heal, break up or
leave, and the EXP distribution).

The logic is uiparty.py's: the offline name, the player's own board ending
the party, the roles by the leadership skill, OnSelectState's packets, the
expel, a press on a member's board (target, character menu, and an
exchange when an item is attached), heal, break up, leave and the
distribution modes. The art names, the affect texts and the role names
are read from the legacy classes. Legacy places the menu and the role
buttons as windows of their own; here they are in the same document, so
they hide with the window."""

import weakref

import localeInfo
import mouseModule
import net
import player

import nui
import nui_hud
import uiParty

DOCUMENT = "nui/windows/party/party.rml"
AFFECT_COUNT = 9

_Board = uiParty.PartyMemberInfoBoard
_ART = _Board.MEMBER_BUTTON_IMAGE_FILE_NAME_DICT

_live = weakref.WeakSet()  # the facades a locale change refreshes


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def _text(value):
	return nui.plain_text(value) if value else ""


def _on_locale_reload():
	"""The affect and role texts in the new locale; uiParty rebuilt its
	tables first (its callback was registered when it was imported)."""
	for facade in list(_live):
		facade._sync()


class PartyBoard(nui.Window):
	"""The party's document, model and handlers."""

	DOCUMENT = DOCUMENT
	MODEL = "party"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"members": [], "menu_open": False, "is_leader": False, "has_role": False,
		        "heal_ready": False, "distribution": 0}

	@nui.on("member_press")
	def on_member_press(self, pid, button):
		self._owner.nui_member_press(pid, button)

	@nui.on("member_release")
	def on_member_release(self, pid, button):
		if button == 0:
			self._owner.nui_member_release(pid)

	@nui.on("member_drop")
	def on_member_drop(self, pid):
		self._owner.nui_member_release(pid)

	@nui.on("state_pick")
	def on_state_pick(self, pid, state, button):
		if button == 0:
			self._owner.nui_state_pick(pid, state)

	@nui.on("expel")
	def on_expel(self, pid, button):
		if button == 0:
			self._owner.nui_expel(pid)

	@nui.on("toggle_menu")
	def on_toggle_menu(self, button):
		if button == 0:
			self._owner.OnTogglePartyMenu()

	@nui.on("heal")
	def on_heal(self, button):
		if button == 0:
			self._owner.nui_heal()

	@nui.on("break_up")
	def on_break_up(self, button):
		if button == 0:
			net.SendPartyExitPacket()

	@nui.on("leave")
	def on_leave(self, button):
		if button == 0:
			net.SendPartyExitPacket()

	@nui.on("mode")
	def on_mode(self, mode, button):
		if button == 0:
			self._owner.nui_mode(mode)


class _Member(object):
	"""One member's board: PartyMemberInfoBoard's state."""

	def __init__(self, pid):
		self.pid = pid
		self.vid = None
		self.name = ""
		self.linked = False
		self.hp = 0.0
		self.state = -1
		self.affects = [False] * AFFECT_COUNT
		self.affectValueDict = {}
		self.isShowStateButton = False
		self.stateButtons = []   # the roles shown beside the board, in order


class PartyWindow(object):
	"""uiParty.PartyWindow on NovaUI (Interface.wndParty)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over("party", self)
		self._nui_discarded = False
		self.board = None
		self.members = []
		self.menuOpen = False
		self.isLeader = False
		self.hasRole = False
		self.healReady = False
		self.distributionMode = 0
		self.shownMode = 0
		if not nui_hud.has_engine():
			return
		try:
			self.board = PartyBoard(self)
		except Exception:
			self.nui_discard()
			raise
		_live.add(self)
		self.ChangePartyParameter(self.distributionMode)

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		_live.discard(self)
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("party", self)

	# --- the window ---------------------------------------------------------------

	def Destroy(self):
		self.DestroyPartyMemberInfoBoard()
		self.nui_discard()

	def DestroyPartyMemberInfoBoard(self):
		self.members = []
		self._sync()

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

	# --- the callbacks -----------------------------------------------------------

	def AddPartyMember(self, pid, name):
		member = self.__FindByPID(pid)
		if member is None:
			member = _Member(pid)
			self.members.append(member)
		if not name:
			name = localeInfo.PARTY_MEMBER_OFFLINE
		member.name = name
		self.__Unlink(member)
		self._sync()
		self.Show()

	def RemovePartyMember(self, pid):
		member = self.__FindByPID(pid)
		if member is None:
			return
		vid = member.vid
		if None != vid and player.IsMainCharacterIndex(vid):
			self.ExitParty()
			player.ExitParty()
		else:
			player.RemovePartyMember(pid)
			self.members.remove(member)
			self._sync()

	def UpdatePartyMemberInfo(self, pid):
		member = self.__FindByPID(pid)
		if member is None:
			return
		state = player.GetPartyMemberState(pid)
		hpPercentage = player.GetPartyMemberHPPercentage(pid)
		affectsList = player.GetPartyMemberAffects(pid)
		member.state = state
		member.hp = min(1.0, max(0, hpPercentage) / 100.0)
		for i in range(len(affectsList)):
			if i >= AFFECT_COUNT:
				continue
			member.affects[i] = affectsList[i] > 0
			member.affectValueDict[i] = affectsList[i]
		vid = member.vid
		if None != vid and player.IsMainCharacterIndex(vid):
			self.hasRole = True
			self.isLeader = player.PARTY_STATE_LEADER == player.GetPartyMemberState(pid)
		self._sync()

	def LinkPartyMember(self, pid, vid):
		member = self.__FindByPID(pid)
		if member is None:
			return
		member.linked = True
		member.vid = vid
		self._sync()

	def UnlinkPartyMember(self, pid):
		member = self.__FindByPID(pid)
		if member is None:
			return
		self.__Unlink(member)
		self._sync()

	def UnlinkAllPartyMember(self):
		for member in self.members:
			self.__Unlink(member)
		self._sync()

	def ExitParty(self):
		self.menuOpen = False
		self.members = []
		self._sync()
		self.Hide()

	def PartyHealReady(self):
		self.healReady = True
		self._sync()

	def ChangePartyParameter(self, distributionMode):
		# PartyMenu.__SetModeButton: every mode button up, the mode's down;
		# an unknown mode leaves them all up and the mode as it was.
		if distributionMode in (player.PARTY_EXP_NON_DISTRIBUTION, player.PARTY_EXP_DISTRIBUTION_PARITY):
			self.distributionMode = distributionMode
			self.shownMode = distributionMode
		else:
			self.shownMode = -1
		self._sync()

	def OnTogglePartyMenu(self):
		self.menuOpen = not self.menuOpen
		self._sync()

	# --- PartyMemberInfoBoard ------------------------------------------------------

	def __FindByPID(self, pid):
		for member in self.members:
			if pid == member.pid:
				return member
		return None

	def __Unlink(self, member):
		member.vid = None
		member.linked = False
		member.affects = [False] * AFFECT_COUNT

	def __GetPartySkillLevel(self):
		slotIndex = player.GetSkillSlotIndex(player.SKILL_INDEX_TONGSOL)
		skillGrade = player.GetSkillGrade(slotIndex)
		skillLevel = player.GetSkillLevel(slotIndex)
		return skillLevel + skillGrade * 20

	def __ShowStateButton(self, member):
		member.isShowStateButton = True
		skillLevel = self.__GetPartySkillLevel()
		roles = []
		for minimum, state in ((10, player.PARTY_STATE_ATTACKER), (20, player.PARTY_STATE_BERSERKER),
		                       (20, player.PARTY_STATE_TANKER), (25, player.PARTY_STATE_BUFFER),
		                       (35, player.PARTY_STATE_SKILL_MASTER), (40, player.PARTY_STATE_DEFENDER)):
			if skillLevel >= minimum:
				# The member's own role is the "withdraw" button in its place.
				roles.append(-1 if state == member.state else state)
		member.stateButtons = roles

	def __HideStateButton(self, member):
		member.isShowStateButton = False
		member.stateButtons = []

	def nui_member_press(self, pid, button):
		"""OnMouseLeftButtonDown, and the right button, which legacy maps to it."""
		member = self.__FindByPID(pid)
		if member is None or button not in (0, 1):
			return
		if member.vid:
			player.SetTarget(member.vid)
			player.OpenCharacterMenu(member.vid)
			if mouseModule.mouseController.isAttached():
				attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
				net.SendExchangeStartPacket(member.vid)
				net.SendExchangeItemAddPacket(attachedSlotPos, 0)
				mouseModule.mouseController.DeattachObject()
				return
		if player.IsPartyLeader(player.GetMainCharacterIndex()):
			if player.PARTY_STATE_LEADER != member.state:
				if member.isShowStateButton:
					self.__HideStateButton(member)
				else:
					self.__ShowStateButton(member)
				self._sync()

	def nui_member_release(self, pid):
		"""OnMouseLeftButtonUp: a release (or a drop from the legacy UI) on a
		member's board with an item attached starts an exchange."""
		member = self.__FindByPID(pid)
		if member is None:
			return
		if member.vid:
			player.SetTarget(member.vid)
			player.OpenCharacterMenu(member.vid)
			if mouseModule.mouseController.isAttached():
				attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
				net.SendExchangeStartPacket(member.vid)
				net.SendExchangeItemAddPacket(attachedSlotPos, 0)
				mouseModule.mouseController.DeattachObject()

	def nui_state_pick(self, pid, state):
		"""OnSelectState: -1 withdraws the member's role."""
		member = self.__FindByPID(pid)
		if member is None or state not in member.stateButtons:
			return
		self.__HideStateButton(member)
		if state <= 0:
			net.SendPartySetStatePacket(member.pid, member.state, False)
		else:
			if member.state <= 0:
				net.SendPartySetStatePacket(member.pid, state, True)
			else:
				net.SendPartySetStatePacket(member.pid, member.state, False)
				net.SendPartySetStatePacket(member.pid, state, True)
		self._sync()

	def nui_expel(self, pid):
		member = self.__FindByPID(pid)
		if member is None or not member.isShowStateButton:
			return
		self.__HideStateButton(member)
		self._sync()
		if not member.pid:
			return
		net.SendPartyRemovePacket(member.pid)

	# --- PartyMenu ---------------------------------------------------------------------

	def nui_heal(self):
		if not self.healReady:
			return
		net.SendPartyUseSkillPacket(_Board.PARTY_SKILL_HEAL, 0)
		self.healReady = False
		self._sync()

	def nui_mode(self, mode):
		"""OnClickEXPLevel and OnClickEXPDistributeParity: the buttons show
		the mode in force again; a leader asks for the new one."""
		self.ChangePartyParameter(self.distributionMode)
		if self.isLeader and mode in (player.PARTY_EXP_NON_DISTRIBUTION, player.PARTY_EXP_DISTRIBUTION_PARITY):
			net.SendPartyParameterPacket(mode)

	# --- the model ---------------------------------------------------------------------

	def _state_art(self, state):
		return _ART.get(state, _ART[_Board.MEMBER_BUTTON_NORMAL])

	def _role_button(self, state):
		if state == -1:
			return {"state": -1, "art": _ART[_Board.MEMBER_BUTTON_NORMAL],
			        "tip": nui_hud.locale_text("PARTY_SET_NORMAL")}
		return {"state": state, "art": _ART[state], "tip": _text(_Board.STATE_NAME_DICT.get(state, ""))}

	def _affect_tip(self, member, index):
		text_for = _Board.AFFECT_STRING_DICT.get(index)
		if text_for is None or index not in member.affectValueDict:
			return ""
		try:
			return _text(text_for(member.affectValueDict[index]))
		except Exception:
			return ""

	def _sync(self):
		if self.board is None:
			return
		members = []
		for member in self.members:
			members.append({
				"pid": member.pid, "vid": member.vid or 0, "name": _text(member.name), "linked": member.linked,
				"hp": member.hp, "state": member.state, "state_art": self._state_art(member.state),
				"affects": list(member.affects),
				"affect_tips": [self._affect_tip(member, i) for i in range(AFFECT_COUNT)],
				"show_states": member.isShowStateButton,
				"state_buttons": [self._role_button(state) for state in member.stateButtons],
			})
		self.board.set(members=members, menu_open=self.menuOpen, is_leader=self.isLeader, has_role=self.hasRole,
		               heal_ready=self.healReady, distribution=self.shownMode)


localeInfo.RegisterReloadCallback(_on_locale_reload)
