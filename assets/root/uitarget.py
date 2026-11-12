import app
import ui
import player
import net
import wndMgr
import messenger
import guild
import chr
import chrmgr
import item
import nonplayer
import localeInfo
import constInfo
import uiCommon
import uiTargetInfo
import uiToolTip
import nui_windows
import nui_numbers

# OLD uiTarget.py ELEMENT_IMAGE_DIC (char.cpp:7450-7470), drawn as a colored
# name because OLD's 12zi element art is not in NEW's packs.
ELEMENT_NAME_KEY = {1: "TARGET_INFO_RACE_ELEC", 2: "TARGET_INFO_RACE_FIRE", 3: "TARGET_INFO_RACE_ICE",
                    4: "TARGET_INFO_RACE_WIND", 5: "TARGET_INFO_RACE_EARTH", 6: "TARGET_INFO_RACE_DARK"}
ELEMENT_COLOR = {1: 0xffcdb3ff, 2: 0xffff8a4a, 3: 0xff7ec9ff, 4: 0xff9fffa6, 5: 0xffd6b16e, 6: 0xffc17bff}

# NOVA-208 (OLD uiTarget.py:780-830, 1166-1173, 1595-1640): the HP gauge's
# bar art by the target's state, and the orange damage trail that stays at
# the HP before a hit and drains to the new HP in TRAIL_SECONDS. The green,
# yellow and orange bars are the red one turned on the hue wheel, as the
# legacy blue, pink and purple are.
GAUGE_ART = "d:/ymir work/ui/pattern/gauge_%s.tga"
GAUGE_RED = "red"
GAUGE_POISONED = "green"
GAUGE_BURNING = "yellow"
GAUGE_TRAIL = "orange"
TRAIL_SECONDS = 0.75


def TrailPercent(start, end, startTime, now):
	"""The trail's HP percent at `now`: from `start` (the HP before the hit)
	to `end` (the HP after it), linearly over TRAIL_SECONDS from startTime."""
	if end >= start:
		return end
	left = 1.0 - (now - startTime) / TRAIL_SECONDS
	if left <= 0.0:
		return end
	return end + (start - end) * min(1.0, left)


def GaugeColorOf(vid):
	"""The bar's color for the target's affects: green while it is poisoned
	(also while it burns too), yellow while it burns, red otherwise. An exe
	without chrmgr.HasAffectByVID keeps red."""
	hasAffect = getattr(chrmgr, "HasAffectByVID", None)
	if not vid or hasAffect is None:
		return GAUGE_RED
	if hasAffect(vid, chr.AFFECT_POISON):
		return GAUGE_POISONED
	if hasAffect(vid, chr.AFFECT_FIRE):
		return GAUGE_BURNING
	return GAUGE_RED


# NOVA-209 (OLD uiTarget.py:48-147): the bonus a bow's arrow gets at the
# target's distance, as "+N% arrow damage" in the tooltip's positive color,
# "0%" in its normal color, "-N%" in its negative color.
ARROW_UP = "up"
ARROW_EVEN = "even"
ARROW_DOWN = "down"
# uitooltip.ToolTip's POSITIVE_COLOR, NORMAL_COLOR and NEGATIVE_COLOR.
ARROW_COLOR = {ARROW_UP: 0xff8ab98e, ARROW_EVEN: 0xffc2c2c2, ARROW_DOWN: 0xffe57976}


def ArrowDamageText(percent):
	"""(text, ARROW_UP / ARROW_EVEN / ARROW_DOWN) for an arrow damage percent."""
	if percent > 100:
		amount, role = "+%d%%" % (percent - 100), ARROW_UP
	elif percent < 100:
		amount, role = "-%d%%" % (100 - percent), ARROW_DOWN
	else:
		amount, role = "0%", ARROW_EVEN
	text = getattr(localeInfo, "TARGET_ARROW_DAMAGE", "%s")
	try:
		return text % amount, role
	except (TypeError, ValueError):
		return amount, role


def ArrowPercentOf(vid):
	"""The arrow damage percent at the distance to `vid` while the main
	character holds a bow (player.GetArrowDistancePercent, the shared rule
	of bow_distance.h), else 0. An exe without the rule answers 0."""
	rule = getattr(player, "GetArrowDistancePercent", None)
	if not vid or rule is None or player.IsMainCharacterIndex(vid):
		return 0
	vnum = player.GetItemIndex(item.EQUIPMENT_WEAPON)
	if not vnum:
		return 0
	item.SelectItem(vnum)
	if item.GetItemType() != item.ITEM_TYPE_WEAPON or item.GetItemSubType() != item.WEAPON_BOW:
		return 0
	distance = player.GetCharacterDistance(vid)
	if distance < 0:
		return 0
	return int(rule(distance))


def MetinQueueHint(vnum):
	"""NOVA-216 (OLD uiTarget.py:840): the attack queue hint for a metin
	stone's race, "" for anything else or an exe without IsMonsterStone."""
	isStone = getattr(nonplayer, "IsMonsterStone", None)
	if not vnum or isStone is None or not isStone(vnum):
		return ""
	return getattr(localeInfo, "TARGET_METIN_QUEUE_HINT", "")


class TargetHPGauge(ui.Gauge):
	"""The legacy gauge (ui.Gauge) with the target's colors and the damage
	trail: an orange bar from the HP to the trail, over the empty slot, which
	stays at the HP before a drop and drains to the new HP (OnUpdate). A rise
	or a new target moves it at once."""

	# ui.Gauge's GAUGE_TEMPORARY_PLACE and GAUGE_WIDTH: the bar starts 12 px
	# in from both ends and its art is 16 px wide.
	BAR_INSET = 12
	ART_WIDTH = 16

	def __init__(self):
		ui.Gauge.__init__(self)
		self.trail = None
		self.color = GAUGE_RED
		self.gaugeWidth = 0
		self.hpPercent = 0.0
		self.trailStart = 0.0
		self.trailEnd = 0.0
		self.trailTime = 0.0

	def MakeGauge(self, width, color):
		ui.Gauge.MakeGauge(self, width, color)
		self.gaugeWidth = max(48, width)
		self.color = color
		trail = ui.ExpandedImageBox()
		trail.SetParent(self)
		trail.LoadImage(GAUGE_ART % GAUGE_TRAIL)
		trail.Hide()
		self.trail = trail

	def SetColor(self, color):
		"""The bar's art; loaded only when it changes."""
		if color == self.color:
			return
		self.color = color
		self.imgGauge.LoadImage(GAUGE_ART % color)
		ui.Gauge.SetPercentage(self, self.hpPercent, 100.0)

	def ResetTrail(self):
		"""A new target: the next HP sets the trail at once."""
		self.hpPercent = 0.0
		self.trailStart = self.trailEnd = 0.0
		self.trailTime = 0.0
		if self.trail:
			self.trail.Hide()

	def SetPercentage(self, curValue, maxValue):
		ui.Gauge.SetPercentage(self, curValue, maxValue)
		percent = min(100.0, max(0.0, 100.0 * float(curValue) / float(maxValue))) if maxValue > 0 else 0.0
		if percent < self.hpPercent:
			self.trailStart = self.hpPercent
			self.trailTime = app.GetTime()
		else:
			self.trailStart = percent
		self.trailEnd = percent
		self.hpPercent = percent
		self.__DrawTrail()

	def GetTrailPercent(self):
		return TrailPercent(self.trailStart, self.trailEnd, self.trailTime, app.GetTime())

	def __DrawTrail(self):
		if not self.trail:
			return
		span = self.gaugeWidth - self.BAR_INSET * 2
		left = int(span * self.hpPercent / 100.0)
		width = int(span * self.GetTrailPercent() / 100.0) - left
		if width <= 0:
			self.trail.Hide()
			return
		self.trail.SetPosition(self.BAR_INSET + left, 0)
		self.trail.SetRenderingRect(0.0, 0.0, float(width) / self.ART_WIDTH - 1.0, 0.0)
		self.trail.Show()

	def OnUpdate(self):
		self.__DrawTrail()


class ArcherGauge(ui.Window):
	"""NOVA-209 (OLD uiTarget.py:48-147): the archer distance gauge below the
	target board, shown while the main character holds a bow. Its fill is
	empty at LOW and full at HIGH percent arrow damage, with a mark at 100;
	the tooltip says the bonus. OLD's art (archergauge/*.png) is not in
	NEW's packs: code-drawn in the legacy gauge's colors."""

	WIDTH = 14
	HEIGHT = 84
	LOW = 80
	HIGH = 120
	EDGE_COLOR = 0xff4c4c4c
	TRACK_COLOR = 0xff0a0a0a
	FILL_COLOR = 0xffd18047
	MARK_COLOR = 0xffc7c7c7

	# ui.Window.__init__ calls Hide before this class's __init__ runs.
	toolTip = None
	tipShown = False

	def __init__(self):
		ui.Window.__init__(self)
		self.percent = 0
		self.toolTip = None
		self.tipShown = False
		self.SetSize(self.WIDTH, self.HEIGHT)
		self.edge = self.__MakeBar(0, 0, self.WIDTH, self.HEIGHT, self.EDGE_COLOR)
		self.track = self.__MakeBar(2, 2, self.WIDTH - 4, self.HEIGHT - 4, self.TRACK_COLOR)
		self.fill = self.__MakeBar(2, self.HEIGHT - 2, self.WIDTH - 4, 0, self.FILL_COLOR)
		self.mark = self.__MakeBar(1, self.HEIGHT // 2, self.WIDTH - 2, 1, self.MARK_COLOR)

	def __MakeBar(self, x, y, width, height, color):
		bar = ui.Bar()
		bar.SetParent(self)
		bar.AddFlag("not_pick")
		bar.SetPosition(x, y)
		bar.SetSize(width, height)
		bar.SetColor(color)
		bar.Show()
		return bar

	def Destroy(self):
		self.OnMouseOverOut()
		self.toolTip = None
		self.edge = self.track = self.fill = self.mark = None

	def GetFill(self):
		return min(1.0, max(0.0, float(self.percent - self.LOW) / (self.HIGH - self.LOW)))

	def SetPercent(self, percent):
		if percent == self.percent:
			return
		self.percent = percent
		inner = self.HEIGHT - 4
		height = int(round(inner * self.GetFill()))
		self.fill.SetPosition(2, 2 + inner - height)
		self.fill.SetSize(self.WIDTH - 4, height)
		if self.tipShown:
			self.__ShowToolTip()

	def __ShowToolTip(self):
		text, role = ArrowDamageText(self.percent)
		self.toolTip.ClearToolTip()
		self.toolTip.AppendTextLine(text, ARROW_COLOR[role])
		self.toolTip.ResizeToolTip()
		self.toolTip.ShowToolTip()
		self.tipShown = True

	def OnMouseOverIn(self):
		if not self.toolTip:
			self.toolTip = uiToolTip.ToolTip()
		self.__ShowToolTip()

	def OnMouseOverOut(self):
		self.tipShown = False
		if self.toolTip:
			self.toolTip.HideToolTip()

	def Hide(self):
		ui.Window.Hide(self)
		self.OnMouseOverOut()


class TargetBoard(ui.ThinBoard):

	# Locale-independent button identifiers (never use translated strings as dict keys)
	BTN_WHISPER = 0
	BTN_EXCHANGE = 1
	BTN_FIGHT = 2
	BTN_ACCEPT_FIGHT = 3
	BTN_AVENGE = 4
	BTN_FRIEND = 5
	BTN_INVITE_PARTY = 6
	BTN_LEAVE_PARTY = 7
	BTN_EXCLUDE = 8
	BTN_INVITE_GUILD = 9
	BTN_REMOVE_GUILD = 10
	BTN_DISMOUNT = 11
	BTN_EXIT_OBSERVER = 12
	BTN_VIEW_EQUIPMENT = 13
	BTN_REQUEST_ENTER_PARTY = 14
	BTN_BUILDING_DESTROY = 15
	BTN_EMOTION_ALLOW = 16
	BTN_VOTE_BLOCK_CHAT = 17
	# The block list (NOVA-47): one of the two shows for another player.
	BTN_BLOCK = 18
	BTN_UNBLOCK = 19
	# The duel rules (NOVA-28, OLD uiTarget.py:737-738): refuse a challenge,
	# pardon a revenge ("/cancel_pvp").
	BTN_DENY_FIGHT = 20
	BTN_CANCEL_AVENGE = 21

	# (buttonId, localeInfo attribute name) — text resolved at __init__ time
	BUTTON_CONFIG = (
		(BTN_WHISPER, "TARGET_BUTTON_WHISPER"),
		(BTN_EXCHANGE, "TARGET_BUTTON_EXCHANGE"),
		(BTN_FIGHT, "TARGET_BUTTON_FIGHT"),
		(BTN_ACCEPT_FIGHT, "TARGET_BUTTON_ACCEPT_FIGHT"),
		(BTN_AVENGE, "TARGET_BUTTON_AVENGE"),
		(BTN_FRIEND, "TARGET_BUTTON_FRIEND"),
		(BTN_INVITE_PARTY, "TARGET_BUTTON_INVITE_PARTY"),
		(BTN_LEAVE_PARTY, "TARGET_BUTTON_LEAVE_PARTY"),
		(BTN_EXCLUDE, "TARGET_BUTTON_EXCLUDE"),
		(BTN_INVITE_GUILD, "TARGET_BUTTON_INVITE_GUILD"),
		(BTN_REMOVE_GUILD, "TARGET_BUTTON_REMOVE_GUILD"),
		(BTN_DISMOUNT, "TARGET_BUTTON_DISMOUNT"),
		(BTN_EXIT_OBSERVER, "TARGET_BUTTON_EXIT_OBSERVER"),
		(BTN_VIEW_EQUIPMENT, "TARGET_BUTTON_VIEW_EQUIPMENT"),
		(BTN_REQUEST_ENTER_PARTY, "TARGET_BUTTON_REQUEST_ENTER_PARTY"),
		(BTN_BUILDING_DESTROY, "TARGET_BUTTON_BUILDING_DESTROY"),
		(BTN_EMOTION_ALLOW, "TARGET_BUTTON_EMOTION_ALLOW"),
		(BTN_VOTE_BLOCK_CHAT, "VOTE_BLOCK_CHAT"),
		(BTN_BLOCK, "TARGET_BUTTON_BLOCK"),
		(BTN_UNBLOCK, "TARGET_BUTTON_UNBLOCK"),
		(BTN_DENY_FIGHT, "TARGET_BUTTON_DENY_FIGHT"),
		(BTN_CANCEL_AVENGE, "TARGET_BUTTON_CANCEL_AVENGE"),
	)

	GRADE_NAME = {}
	EXCHANGE_LIMIT_RANGE = 3000
	# NOVA-216: a metin stone's board is this tall, its queue hint under the gauge.
	HINT_BOARD_HEIGHT = 54

	# ui.ThinBoard.__init__ calls Hide before this class's __init__ runs.
	archerGauge = None

	@staticmethod
	def _RebuildLocaleStrings():
		TargetBoard.GRADE_NAME = {
			nonplayer.PAWN : localeInfo.TARGET_LEVEL_PAWN,
			nonplayer.S_PAWN : localeInfo.TARGET_LEVEL_S_PAWN,
			nonplayer.KNIGHT : localeInfo.TARGET_LEVEL_KNIGHT,
			nonplayer.S_KNIGHT : localeInfo.TARGET_LEVEL_S_KNIGHT,
			nonplayer.BOSS : localeInfo.TARGET_LEVEL_BOSS,
			nonplayer.KING : localeInfo.TARGET_LEVEL_KING,
		}

	def __init__(self):
		ui.ThinBoard.__init__(self)

		name = ui.TextLine()
		name.SetParent(self)
		name.SetDefaultFontName()
		name.SetOutline()
		name.Show()

		# NOVA-208: the gauge tinted by the target's poison and fire, with the
		# damage trail (TargetHPGauge).
		hpGauge = TargetHPGauge()
		hpGauge.SetParent(self)
		hpGauge.MakeGauge(130, GAUGE_RED)
		hpGauge.Hide()

		# NOVA-216 (OLD uiTarget.py:840): the attack queue hint of a metin stone.
		metinHint = ui.TextLine()
		metinHint.SetParent(self)
		metinHint.SetOutline()
		metinHint.SetWindowHorizontalAlignCenter()
		metinHint.SetHorizontalAlignCenter()
		metinHint.SetPosition(0, 33)
		metinHint.Hide()

		# NOVA-40 (OLD uiTarget.py:862, 1330-1391): the percent beside the gauge,
		# the exact numbers over it, the element and the info button of a mob.
		hpPercent = ui.TextLine()
		hpPercent.SetParent(self)
		hpPercent.SetOutline()
		hpPercent.SetWindowHorizontalAlignRight()
		hpPercent.SetHorizontalAlignRight()
		hpPercent.Hide()

		hpValues = ui.TextLine()
		hpValues.SetParent(self)
		hpValues.SetOutline()
		hpValues.SetWindowHorizontalAlignRight()
		hpValues.SetHorizontalAlignCenter()
		hpValues.Hide()

		elementText = ui.TextLine()
		elementText.SetParent(self)
		elementText.SetOutline()
		elementText.Hide()

		infoButton = ui.Button()
		infoButton.SetParent(self)
		infoButton.SetUpVisual("d:/ymir work/ui/public/xsmall_button_01.sub")
		infoButton.SetOverVisual("d:/ymir work/ui/public/xsmall_button_02.sub")
		infoButton.SetDownVisual("d:/ymir work/ui/public/xsmall_button_03.sub")
		infoButton.SetText("?")
		infoButton.SetEvent(ui.__mem_func__(self.OnPressedInfoButton))
		infoButton.Hide()

		closeButton = ui.Button()
		closeButton.SetParent(self)
		closeButton.SetUpVisual("d:/ymir work/ui/public/close_button_01.sub")
		closeButton.SetOverVisual("d:/ymir work/ui/public/close_button_02.sub")
		closeButton.SetDownVisual("d:/ymir work/ui/public/close_button_03.sub")
		closeButton.SetPosition(30, 13)

		if app.IsRTL():
			hpGauge.SetPosition(55, 17)
			hpGauge.SetWindowHorizontalAlignLeft()
			closeButton.SetWindowHorizontalAlignLeft()
		else:
			hpGauge.SetPosition(175, 17)
			hpGauge.SetWindowHorizontalAlignRight()
			closeButton.SetWindowHorizontalAlignRight()

		closeButton.SetEvent(ui.__mem_func__(self.OnPressedCloseButton))
		closeButton.Show()

		self.buttonDict = {}
		self.showingButtonList = []

		for btnId, localeAttr in self.BUTTON_CONFIG:
			button = ui.Button()
			button.SetParent(self)

			if app.IsRTL():
				button.SetUpVisual("d:/ymir work/ui/public/Small_Button_01.sub")
				button.SetOverVisual("d:/ymir work/ui/public/Small_Button_02.sub")
				button.SetDownVisual("d:/ymir work/ui/public/Small_Button_03.sub")
			else:
				button.SetUpVisual("d:/ymir work/ui/public/small_thin_button_01.sub")
				button.SetOverVisual("d:/ymir work/ui/public/small_thin_button_02.sub")
				button.SetDownVisual("d:/ymir work/ui/public/small_thin_button_03.sub")

			button.SetWindowHorizontalAlignCenter()
			button.SetText(getattr(localeInfo, localeAttr, localeAttr))
			button.Hide()
			self.buttonDict[btnId] = button
			self.showingButtonList.append(button)

		self.buttonDict[self.BTN_WHISPER].SetEvent(ui.__mem_func__(self.OnWhisper))
		self.buttonDict[self.BTN_EXCHANGE].SetEvent(ui.__mem_func__(self.OnExchange))
		# Fight opens the duel rules (NOVA-28, OLD uiTarget.py:983); accepting a
		# challenge or a revenge sends the bare "/pvp <vid>", as OLD.
		self.buttonDict[self.BTN_FIGHT].SetEvent(ui.__mem_func__(self.OnAdvancedPVP))
		self.buttonDict[self.BTN_ACCEPT_FIGHT].SetEvent(ui.__mem_func__(self.OnPVP))
		self.buttonDict[self.BTN_AVENGE].SetEvent(ui.__mem_func__(self.OnPVP))
		self.buttonDict[self.BTN_DENY_FIGHT].SetEvent(ui.__mem_func__(self.OnCancelDuel))
		self.buttonDict[self.BTN_CANCEL_AVENGE].SetEvent(ui.__mem_func__(self.OnCancelDuel))
		self.buttonDict[self.BTN_FRIEND].SetEvent(ui.__mem_func__(self.OnAppendToMessenger))
		self.buttonDict[self.BTN_INVITE_PARTY].SetEvent(ui.__mem_func__(self.OnPartyInvite))
		self.buttonDict[self.BTN_LEAVE_PARTY].SetEvent(ui.__mem_func__(self.OnPartyExit))
		self.buttonDict[self.BTN_EXCLUDE].SetEvent(ui.__mem_func__(self.OnPartyRemove))

		self.buttonDict[self.BTN_INVITE_GUILD].SAFE_SetEvent(self.__OnGuildAddMember)
		self.buttonDict[self.BTN_REMOVE_GUILD].SAFE_SetEvent(self.__OnGuildRemoveMember)
		self.buttonDict[self.BTN_DISMOUNT].SAFE_SetEvent(self.__OnDismount)
		self.buttonDict[self.BTN_EXIT_OBSERVER].SAFE_SetEvent(self.__OnExitObserver)
		self.buttonDict[self.BTN_VIEW_EQUIPMENT].SAFE_SetEvent(self.__OnViewEquipment)
		self.buttonDict[self.BTN_REQUEST_ENTER_PARTY].SAFE_SetEvent(self.__OnRequestParty)
		self.buttonDict[self.BTN_BUILDING_DESTROY].SAFE_SetEvent(self.__OnDestroyBuilding)
		self.buttonDict[self.BTN_EMOTION_ALLOW].SAFE_SetEvent(self.__OnEmotionAllow)

		self.buttonDict[self.BTN_VOTE_BLOCK_CHAT].SetEvent(ui.__mem_func__(self.__OnVoteBlockChat))
		self.buttonDict[self.BTN_BLOCK].SetEvent(ui.__mem_func__(self.OnBlockPlayer))
		self.buttonDict[self.BTN_UNBLOCK].SetEvent(ui.__mem_func__(self.OnUnblockPlayer))

		self.name = name
		self.hpGauge = hpGauge
		self.metinHint = metinHint
		# NOVA-209: the archer distance gauge, a window of its own below the board.
		self.archerGauge = ArcherGauge()
		self.hpPercent = hpPercent
		self.hpValues = hpValues
		self.elementText = elementText
		self.infoButton = infoButton
		self.element = 0
		self.vnum = 0
		self.closeButton = closeButton
		self.nameString = 0
		self.nameLength = 0
		self.vid = 0
		self.eventWhisper = None
		self.isShowButton = False
		# The duel rules board (NOVA-28), made at the first Fight.
		self.duelRulesDialog = None

		self.__Initialize()
		self.infoBoard = nui_windows.make("target-info", uiTargetInfo.InfoBoard, "nui_target_info.InfoBoard")
		self.ResetTargetBoard()

	def __del__(self):
		ui.ThinBoard.__del__(self)

		print("===================================================== DESTROYED TARGET BOARD")

	def __Initialize(self):
		self.nameString = ""
		self.nameLength = 0
		self.vid = 0
		self.isShowButton = False

	def Destroy(self):
		if self.duelRulesDialog:
			self.duelRulesDialog.Destroy()
			self.duelRulesDialog = None
		self.eventWhisper = None
		self.closeButton = None
		self.showingButtonList = None
		self.buttonDict = None
		self.name = None
		self.hpGauge = None
		self.metinHint = None
		if self.archerGauge:
			self.archerGauge.Hide()
			self.archerGauge.Destroy()
			self.archerGauge = None
		self.hpPercent = None
		self.hpValues = None
		self.elementText = None
		self.infoButton = None
		if self.infoBoard:
			self.infoBoard.Destroy()
			self.infoBoard = None
		self.__Initialize()

	def OnPressedCloseButton(self):
		player.ClearTarget()
		self.Close()

	def Close(self):
		self.__Initialize()
		self.CloseDuelRules()
		if self.infoBoard:
			self.infoBoard.Close()
		self.Hide()

	def CloseDuelRules(self):
		if self.duelRulesDialog:
			self.duelRulesDialog.Close()

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
		canShow=0

		self.HideAllButton()

		if player.IsMountingHorse():
			self.__ShowButton(self.BTN_DISMOUNT)
			canShow=1

		if player.IsObserverMode():
			self.__ShowButton(self.BTN_EXIT_OBSERVER)
			canShow=1

		if canShow:
			self.__ArrangeButtonPosition()
			self.Show()
		else:
			self.Hide()
			
	def __ShowNameOnlyMenu(self):
		self.HideAllButton()

	def SetWhisperEvent(self, event):
		self.eventWhisper = event

	def SetWikiItemEvent(self, event):
		"""Interface.OpenWikiItem, for the info board's drop rows."""
		if self.infoBoard:
			self.infoBoard.SetWikiItemEvent(event)

	def UpdatePosition(self):
		self.SetPosition(wndMgr.GetScreenWidth() // 2 - self.GetWidth() // 2, 10)

	def ResetTargetBoard(self):

		for btn in list(self.buttonDict.values()):
			btn.Hide()

		self.__Initialize()

		self.name.SetPosition(0, 13)
		self.name.SetHorizontalAlignCenter()
		self.name.SetWindowHorizontalAlignCenter()
		self.hpGauge.Hide()
		self.hpGauge.ResetTrail()
		self.hpGauge.SetColor(GAUGE_RED)
		self.metinHint.Hide()
		if self.archerGauge:
			self.archerGauge.Hide()
		self.hpPercent.Hide()
		self.hpValues.Hide()
		self.elementText.Hide()
		self.infoButton.Hide()
		self.element = 0
		self.vnum = 0
		if self.infoBoard:
			self.infoBoard.Close()
		self.SetSize(250, 40)

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
		if grade in self.GRADE_NAME:
			nameFront += "(" + self.GRADE_NAME[grade] + ") "

		self.SetTargetName(nameFront + name)

		# NOVA-40 (OLD uiTarget.py:1079-1086): the info button of a monster.
		self.vnum = uiTargetInfo.race_of_vid(vid)
		if self.vnum:
			self.infoButton.SetPosition(self.name.GetTextSize()[0] + 32, 13)
			self.infoButton.SetWindowHorizontalAlignLeft()
			self.infoButton.Show()

		# NOVA-216: a metin stone's board says how to queue it.
		hint = MetinQueueHint(self.vnum)
		if hint:
			self.metinHint.SetText(hint)
			self.metinHint.Show()
			self.SetSize(self.GetWidth(), self.HINT_BOARD_HEIGHT)
		else:
			self.metinHint.Hide()

	def GetTargetVID(self):
		return self.vid

	def GetTargetName(self):
		return self.nameString

	def SetTargetName(self, name):
		self.nameString = name
		self.nameLength = len(name)
		self.name.SetText(name)

	def SetHP(self, hpPercentage, actualHP=0, maxHP=0):
		if not self.hpGauge.IsShow():

			# OLD's 250 (uiTarget.py:1340): room for the percent beside the name.
			self.SetSize(250 + 7 * self.nameLength, self.GetHeight())

			if app.IsRTL():
				self.name.SetPosition( self.GetWidth()-23, 13)
			else:
				self.name.SetPosition(23, 13)

			self.name.SetWindowHorizontalAlignLeft()
			self.name.SetHorizontalAlignLeft()
			self.hpGauge.ResetTrail()
			self.hpGauge.Show()
			self.UpdatePosition()

		self.hpGauge.SetPercentage(hpPercentage, 100)
		self.__ShowHPText(hpPercentage, actualHP, maxHP)

	def __ShowHPText(self, hpPercentage, actualHP, maxHP):
		self.hpPercent.SetPosition(180, 13)
		self.hpPercent.SetText("%d%%" % (hpPercentage))
		self.hpPercent.Show()
		if maxHP > 0:
			self.hpValues.SetPosition(110, 4)
			self.hpValues.SetText(nui_numbers.group(int(max(actualHP, 0))) + " / " + nui_numbers.group(int(maxHP)))
			self.hpValues.Show()
		else:
			self.hpValues.Hide()

	def SetPCHP(self, hpPercentage):
		"""A player target's bar and percent (OLD uiTarget.py:1126-1178): the
		same gauge at the right, the board's size and buttons untouched."""
		if not self.hpGauge.IsShow():
			self.name.SetPosition(23, 13)
			self.name.SetWindowHorizontalAlignLeft()
			self.name.SetHorizontalAlignLeft()
			self.hpGauge.ResetTrail()
			self.hpGauge.Show()
		self.hpGauge.SetPercentage(hpPercentage, 100)
		self.__ShowHPText(hpPercentage, 0, 0)

	def SetElement(self, elementId):
		"""Set when the element changes; OLD made a new image per packet."""
		if elementId == self.element:
			return
		self.element = elementId
		if elementId in ELEMENT_NAME_KEY:
			self.elementText.SetText(getattr(localeInfo, ELEMENT_NAME_KEY[elementId], ""))
			self.elementText.SetPackedFontColor(ELEMENT_COLOR[elementId])
			self.elementText.SetPosition(23, 0)
			self.elementText.Show()
		else:
			self.elementText.Hide()

	def SetAttackers(self, count):
		if self.vnum and uiTargetInfo.set_attackers(self.vnum, count):
			self.infoBoard.RefreshAttackerInfo()

	def RefreshInfoBoard(self, race):
		if self.vnum == race and self.infoBoard.IsShow():
			self.infoBoard.Refresh()

	def OnPressedInfoButton(self):
		if self.infoBoard.IsShow():
			self.infoBoard.Close()
		elif self.vnum:
			self.infoBoard.Open(self, self.vnum, self.GetTargetVID())
		self.SetTop()

	def ShowDefaultButton(self):

		self.isShowButton = True
		self.showingButtonList.append(self.buttonDict[self.BTN_WHISPER])
		self.showingButtonList.append(self.buttonDict[self.BTN_EXCHANGE])
		self.showingButtonList.append(self.buttonDict[self.BTN_FIGHT])
		self.showingButtonList.append(self.buttonDict[self.BTN_EMOTION_ALLOW])
		for button in self.showingButtonList:
			button.Show()

	def HideAllButton(self):
		self.isShowButton = False
		for button in self.showingButtonList:
			button.Hide()
		self.showingButtonList = []

	def __ShowButton(self, name):

		if name not in self.buttonDict:
			return

		self.buttonDict[name].Show()
		self.showingButtonList.append(self.buttonDict[name])

	def __HideButton(self, name):

		if name not in self.buttonDict:
			return

		button = self.buttonDict[name]
		button.Hide()

		for btnInList in self.showingButtonList:
			if btnInList == button:
				self.showingButtonList.remove(button)
				break

	def OnWhisper(self):
		if None != self.eventWhisper:
			self.eventWhisper(self.nameString)

	def OnExchange(self):
		net.SendExchangeStartPacket(self.vid)

	def OnPVP(self):
		net.SendChatPacket("/pvp %d" % (self.vid))

	# The duel rules (NOVA-28, OLD uiTarget.py:1438-1445): Fight opens the
	# rules board for the target; Deny and Pardon send "/cancel_pvp <vid>".
	def OnAdvancedPVP(self):
		if not self.duelRulesDialog:
			import uiDuel
			self.duelRulesDialog = nui_windows.make("duel-rules", uiDuel.DuelRulesDialog, "nui_duel_rules.DuelRulesDialog")
		self.duelRulesDialog.Open(self.vid)

	def OnCancelDuel(self):
		net.SendChatPacket("/cancel_pvp %d" % (self.vid))

	def OnAppendToMessenger(self):
		net.SendMessengerAddByVIDPacket(self.vid)

	# The block list (NOVA-47, OLD uiTarget.py:1450-1464): the change is sent
	# and the other button shows at once.
	def OnBlockPlayer(self):
		net.SendBlockAddPacket(self.nameString)

		self.__HideButton(self.BTN_BLOCK)
		self.__ShowButton(self.BTN_UNBLOCK)
		self.__ArrangeButtonPosition()

	def OnUnblockPlayer(self):
		net.SendBlockRemovePacket(self.nameString)

		self.__HideButton(self.BTN_UNBLOCK)
		self.__ShowButton(self.BTN_BLOCK)
		self.__ArrangeButtonPosition()

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

	def OnPressEscapeKey(self):
		self.OnPressedCloseButton()
		return True

	def IsShowButton(self):
		return self.isShowButton

	def RefreshButton(self):
		self.HideAllButton()

		if chr.INSTANCE_TYPE_BUILDING == chr.GetInstanceType(self.vid):
			#self.__ShowButton(self.BTN_BUILDING_DESTROY)
			#self.__ArrangeButtonPosition()
			return
		
		if player.IsPVPInstance(self.vid) or player.IsObserverMode():
			# PVP_INFO_SIZE_BUG_FIX
			self.SetSize(200 + 7 * self.nameLength, 40)
			self.UpdatePosition()
			# END_OF_PVP_INFO_SIZE_BUG_FIX			
			return	

		self.ShowDefaultButton()

		def isGuildMaster(name):
			guildMasterName = guild.GetGuildMasterName()
			return guildMasterName == name

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
				self.__ShowButton(self.BTN_CANCEL_AVENGE)
			elif player.IsChallengeInstance(self.vid):
				self.__HideButton(self.BTN_FIGHT)
				self.__ShowButton(self.BTN_ACCEPT_FIGHT)
				self.__ShowButton(self.BTN_DENY_FIGHT)
			elif player.IsCantFightInstance(self.vid):
				self.__HideButton(self.BTN_FIGHT)

			if not player.IsSameEmpire(self.vid):
				self.__HideButton(self.BTN_INVITE_PARTY)
				self.__HideButton(self.BTN_FRIEND)
				self.__HideButton(self.BTN_FIGHT)

		# Block or Unblock for another player, never for staff ("[GM]..."), as
		# OLD (uiTarget.py:1569-1575).
		if self.nameString and not str(self.nameString).startswith("["):
			if messenger.IsBlocked(self.nameString):
				self.__ShowButton(self.BTN_UNBLOCK)
			else:
				self.__ShowButton(self.BTN_BLOCK)

		distance = player.GetCharacterDistance(self.vid)
		if distance > self.EXCHANGE_LIMIT_RANGE:
			self.__HideButton(self.BTN_EXCHANGE)
			self.__ArrangeButtonPosition()

		self.__ArrangeButtonPosition()

	def __ArrangeButtonPosition(self):
		showingButtonCount = len(self.showingButtonList)

		pos = -(showingButtonCount // 2) * 68

		if 0 == showingButtonCount % 2:
			pos += 34

		for button in self.showingButtonList:
			button.SetPosition(pos, 33)
			pos += 68

		self.SetSize(max(150, showingButtonCount * 75), 65)
		self.UpdatePosition()

	def Hide(self):
		ui.ThinBoard.Hide(self)
		if self.archerGauge:
			self.archerGauge.Hide()

	def __UpdateCombat(self):
		"""NOVA-208: the gauge's color by the target's poison and fire;
		NOVA-209: the archer gauge below the board while a bow is held."""
		if self.hpGauge and self.hpGauge.IsShow():
			self.hpGauge.SetColor(GaugeColorOf(self.vid))
		if not self.archerGauge:
			return
		percent = ArrowPercentOf(self.vid)
		if percent <= 0:
			self.archerGauge.Hide()
			return
		self.archerGauge.SetPercent(percent)
		x, y = self.GetGlobalPosition()
		self.archerGauge.SetPosition(x + (self.GetWidth() - self.archerGauge.WIDTH) // 2, y + self.GetHeight() + 4)
		if not self.archerGauge.IsShow():
			self.archerGauge.Show()
			self.archerGauge.SetTop()

	def OnUpdate(self):
		self.__UpdateCombat()

		if self.isShowButton:

			exchangeButton = self.buttonDict[self.BTN_EXCHANGE]
			distance = player.GetCharacterDistance(self.vid)

			if distance < 0:
				return

			if exchangeButton.IsShow():
				if distance > self.EXCHANGE_LIMIT_RANGE:
					self.RefreshButton()

			else:
				if distance < self.EXCHANGE_LIMIT_RANGE:
					self.RefreshButton()

TargetBoard._RebuildLocaleStrings()
localeInfo.RegisterReloadCallback(TargetBoard._RebuildLocaleStrings)
