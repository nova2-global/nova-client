import ui
import localeInfo
import chr
import item
import app
import skill
import player
import net
import uiToolTip
import math
import dbg
import weakref

# WEDDING
class LovePointImage(ui.ExpandedImageBox):

	FILE_PATH = "d:/ymir work/ui/pattern/LovePoint/"
	FILE_DICT = {
		0 : FILE_PATH + "01.dds",
		1 : FILE_PATH + "02.dds",
		2 : FILE_PATH + "02.dds",
		3 : FILE_PATH + "03.dds",
		4 : FILE_PATH + "04.dds",
		5 : FILE_PATH + "05.dds",
	}

	def __init__(self):
		ui.ExpandedImageBox.__init__(self)

		self.loverName = ""
		self.lovePoint = 0

		self.toolTip = uiToolTip.ToolTip(100)
		self.toolTip.HideToolTip()

	def __del__(self):
		ui.ExpandedImageBox.__del__(self)

	def SetLoverInfo(self, name, lovePoint):
		self.loverName = name
		self.lovePoint = lovePoint
		self.__Refresh()

	def OnUpdateLovePoint(self, lovePoint):
		self.lovePoint = lovePoint
		self.__Refresh()

	def __Refresh(self):
		self.lovePoint = max(0, self.lovePoint)
		self.lovePoint = min(100, self.lovePoint)

		if 0 == self.lovePoint:
			loveGrade = 0
		else:
			loveGrade = self.lovePoint / 25 + 1
		fileName = self.FILE_DICT.get(loveGrade, self.FILE_PATH+"00.dds")

		try:
			self.LoadImage(fileName)
		except:
			import dbg
			dbg.TraceError("LovePointImage.SetLoverInfo(lovePoint=%d) - LoadError %s" % (self.lovePoint, fileName))

		self.SetScale(0.7, 0.7)

		self.toolTip.ClearToolTip()
		self.toolTip.SetTitle(self.loverName)
		self.toolTip.AppendTextLine(localeInfo.AFF_LOVE_POINT % (self.lovePoint))
		self.toolTip.ResizeToolTip()

	def OnMouseOverIn(self):
		self.toolTip.ShowToolTip()

	def OnMouseOverOut(self):
		self.toolTip.HideToolTip()
# END_OF_WEDDING


class HorseImage(ui.ExpandedImageBox):

	FILE_PATH = "d:/ymir work/ui/pattern/HorseState/"

	FILE_DICT = {
		00 : FILE_PATH + "00.dds",
		0o1 : FILE_PATH + "00.dds",
		0o2 : FILE_PATH + "00.dds",
		0o3 : FILE_PATH + "00.dds",
		10 : FILE_PATH + "10.dds",
		11 : FILE_PATH + "11.dds",
		12 : FILE_PATH + "12.dds",
		13 : FILE_PATH + "13.dds",
		20 : FILE_PATH + "20.dds",
		21 : FILE_PATH + "21.dds",
		22 : FILE_PATH + "22.dds",
		23 : FILE_PATH + "23.dds",
		30 : FILE_PATH + "30.dds",
		31 : FILE_PATH + "31.dds",
		32 : FILE_PATH + "32.dds",
		33 : FILE_PATH + "33.dds",
	}

	def __init__(self):
		ui.ExpandedImageBox.__init__(self)

		#self.textLineList = []
		self.toolTip = uiToolTip.ToolTip(100)
		self.toolTip.HideToolTip()

	def __GetHorseGrade(self, level):
		if 0 == level:
			return 0

		return (level-1)/10 + 1

	def SetState(self, level, health, battery):
		#self.textLineList=[]
		self.toolTip.ClearToolTip()

		if level > 0:
			try:
				grade = self.__GetHorseGrade(level)
				self.__AppendText(localeInfo.LEVEL_LIST[int(grade)])
			except IndexError:
				print(("HorseImage.SetState(level=%d, health=%d, battery=%d) - Unknown Index" % (level, health, battery)))
				return

			try:
				healthName = localeInfo.HEALTH_LIST[health]
				if len(healthName) > 0:
					self.__AppendText(healthName)
			except IndexError:
				print(("HorseImage.SetState(level=%d, health=%d, battery=%d) - Unknown Index" % (level, health, battery)))
				return

			if health > 0:
				if battery == 0:
					self.__AppendText(localeInfo.NEEFD_REST)

			try:
				fileName = self.FILE_DICT[health*10 + battery]
			except KeyError:
				print(("HorseImage.SetState(level=%d, health=%d, battery=%d) - KeyError" % (level, health, battery)))

			try:
				self.LoadImage(fileName)
			except:
				print(("HorseImage.SetState(level=%d, health=%d, battery=%d) - LoadError %s" % (level, health, battery, fileName)))

		self.SetScale(0.7, 0.7)

	def __AppendText(self, text):

		self.toolTip.AppendTextLine(text)
		self.toolTip.ResizeToolTip()

		#x=self.GetWidth()/2
		#textLine = ui.TextLine()
		#textLine.SetParent(self)
		#textLine.SetSize(0, 0)
		#textLine.SetOutline()
		#textLine.Hide()
		#textLine.SetPosition(x, 40+len(self.textLineList)*16)
		#textLine.SetText(text)
		#self.textLineList.append(textLine)

	def OnMouseOverIn(self):
		#for textLine in self.textLineList:
		#	textLine.Show()

		self.toolTip.ShowToolTip()

	def OnMouseOverOut(self):
		#for textLine in self.textLineList:
		#	textLine.Hide()

		self.toolTip.HideToolTip()


# AUTO_POTION
class AutoPotionImage(ui.ExpandedImageBox):

	FILE_PATH_HP = "d:/ymir work/ui/pattern/auto_hpgauge/"
	FILE_PATH_SP = "d:/ymir work/ui/pattern/auto_spgauge/"

	def __init__(self):
		ui.ExpandedImageBox.__init__(self)

		self.loverName = ""
		self.lovePoint = 0
		self.potionType = player.AUTO_POTION_TYPE_HP
		self.filePath = ""

		self.toolTip = uiToolTip.ToolTip(100)
		self.toolTip.HideToolTip()

	def __del__(self):
		ui.ExpandedImageBox.__del__(self)

	def SetPotionType(self, type):
		self.potionType = type
		
		if player.AUTO_POTION_TYPE_HP == type:
			self.filePath = self.FILE_PATH_HP
		elif player.AUTO_POTION_TYPE_SP == type:
			self.filePath = self.FILE_PATH_SP
			

	def OnUpdateAutoPotionImage(self):
		self.__Refresh()

	def __Refresh(self):
		print("__Refresh")
	
		isActivated, currentAmount, totalAmount, slotIndex = player.GetAutoPotionInfo(self.potionType)
		
		amountPercent = (float(currentAmount) / totalAmount) * 100.0
		grade = math.ceil(amountPercent / 20)
		
		if 5.0 > amountPercent:
			grade = 0
			
		if 80.0 < amountPercent:
			grade = 4
			if 90.0 < amountPercent:
				grade = 5			

		fmt = self.filePath + "%.2d.dds"
		fileName = fmt % grade
		
		print((self.potionType, amountPercent, fileName))

		try:
			self.LoadImage(fileName)
		except:
			import dbg
			dbg.TraceError("AutoPotionImage.__Refresh(potionType = %d) - LoadError %s" % (self.potionType, fileName))

		self.SetScale(0.7, 0.7)

		self.toolTip.ClearToolTip()

		# MR-10: Add toolTip support and real-time countdown for affects
		itemName = None

		if slotIndex >= 0:
			itemVnum = player.GetItemIndex(slotIndex)

			if itemVnum:
				item.SelectItem(itemVnum)
				itemName = item.GetItemName()

		if itemName:
			self.toolTip.SetTitle(itemName)
		elif player.AUTO_POTION_TYPE_HP == self.potionType:
			self.toolTip.SetTitle(localeInfo.TOOLTIP_AUTO_POTION_HP)
		else:
			self.toolTip.SetTitle(localeInfo.TOOLTIP_AUTO_POTION_SP)

		self.toolTip.AppendTextLine(localeInfo.TOOLTIP_AUTO_POTION_REST % (amountPercent))
		self.toolTip.ResizeToolTip()
		# MR-10: -- END OF -- Add toolTip support and real-time countdown for affects

	def OnMouseOverIn(self):
		self.toolTip.ShowToolTip()

	def OnMouseOverOut(self):
		self.toolTip.HideToolTip()
# END_OF_AUTO_POTION


class AffectImage(ui.ExpandedImageBox):

	# MR-16: Canonical item vnum for each infinite-duration affect (proto lookup, no inventory)
	INFINITE_AFFECT_ITEM_VNUM = {
		chr.NEW_AFFECT_NO_DEATH_PENALTY    : 71004,
		chr.NEW_AFFECT_SKILL_BOOK_BONUS    : 71094,
		chr.NEW_AFFECT_SKILL_BOOK_NO_DELAY : 71001,
	}
	# MR-16: -- END OF -- Canonical item vnum for each infinite-duration affect

	def __init__(self):
		ui.ExpandedImageBox.__init__(self)

		self.toolTipText = None
		# MR-10: Add toolTip support and real-time countdown for affects
		self.toolTip = None
		self.dsTimeCache = {}
		self.isHover = False
		# MR-10: -- END OF -- Add toolTip support and real-time countdown for affects
		self.isSkillAffect = True
		self.description = None
		self.endTime = 0
		self.affect = None
		self.isClocked = True
		self.autoPotionToolTipTitle = None
		self.autoPotionToolTipLine = None
		self.pressEvent = None
		self.pressEventArgs = ()

	def SetAffect(self, affect):
		self.affect = affect

	def GetAffect(self):
		return self.affect

	def SetToolTipText(self, text, x = 0, y = -19):

		if not self.toolTipText:
			textLine = ui.TextLine()

			textLine.SetParent(self)
			textLine.SetSize(0, 0)
			textLine.SetOutline()
			textLine.Hide()

			self.toolTipText = textLine
			
		self.toolTipText.SetText(text)
		w, h = self.toolTipText.GetTextSize()
		self.toolTipText.SetPosition(max(0, x + self.GetWidth()/2 - w/2), y)

	def SetDescription(self, description):
		self.description = description

	def SetDuration(self, duration):
		self.endTime = 0

		# MR-10: Add toolTip support and real-time countdown for affects
		if duration > 0:
			self.endTime = app.GetGlobalTimeStamp() + duration
		# MR-10: -- END OF -- Add toolTip support and real-time countdown for affects

	def UpdateAutoPotionDescription(self):		
		
		potionType = 0

		if self.affect == chr.NEW_AFFECT_AUTO_HP_RECOVERY:
			potionType = player.AUTO_POTION_TYPE_HP
		else:
			potionType = player.AUTO_POTION_TYPE_SP	
		
		isActivated, currentAmount, totalAmount, slotIndex = player.GetAutoPotionInfo(potionType)
		
		#print "UpdateAutoPotionDescription ", isActivated, currentAmount, totalAmount, slotIndex
		
		amountPercent = 0.0
		
		try:
			amountPercent = (float(currentAmount) / totalAmount) * 100.0		
		except:
			amountPercent = 100.0
		
		# MR-10: Add toolTip support and real-time countdown for affects
		if not self.isHover:
			return

		self.__EnsureToolTip()

		itemName = None

		if slotIndex >= 0:
			itemVnum = player.GetItemIndex(slotIndex)

			if itemVnum:
				item.SelectItem(itemVnum)
				itemName = item.GetItemName()

		if itemName:
			title = itemName
		elif player.AUTO_POTION_TYPE_HP == potionType:
			title = localeInfo.TOOLTIP_AUTO_POTION_HP
		else:
			title = localeInfo.TOOLTIP_AUTO_POTION_SP

		line = self.description % amountPercent

		if self.autoPotionToolTipTitle == title and self.autoPotionToolTipLine == line:
			return

		self.toolTip.ClearToolTip()
		self.toolTip.SetTitle(title)
		self.toolTip.AppendTextLine(line)
		self.toolTip.ResizeToolTip()
		self.autoPotionToolTipTitle = title
		self.autoPotionToolTipLine = line
		# MR-10: -- END OF -- Add toolTip support and real-time countdown for affects
		
	def SetClock(self, isClocked):
		self.isClocked = isClocked
		
	# MR-10: Add toolTip support and real-time countdown for affects
	def UpdateDescription(self):
		# MR-12: Fix realtime countdown auto-start
		if self.__IsDragonSoulAffect():
			minRemain = self.__GetDragonSoulMinRemainSec()

			if self.isHover:
				self.__UpdateDragonSoulDescription(minRemain)
		# MR-12: -- END OF -- Fix realtime countdown auto-start

				if self.toolTip:
					self.toolTip.ShowToolTip()
			return

		if not self.isClocked:
			self.__UpdateDescription2()
			return

		if not self.description:
			return

		if self.__ShouldShowTimedToolTip():
			if self.isHover:
				remainSec = max(0, self.endTime - app.GetGlobalTimeStamp())
				self.__UpdateTimedDescription(remainSec)

				if self.toolTip:
					self.toolTip.ShowToolTip()
			return

		# MR-16: Classic affect duration countdown
		if self.__ShouldShowInfiniteToolTip():
			return
		# MR-16: -- END OF -- Classic affect duration countdown

		self.SetToolTipText(self.description, 0, 40)
		
	# Used to suppress the time countdown display (German version)
	def __UpdateDescription2(self):
		if not self.description:
			return

		toolTip = self.description
		self.SetToolTipText(toolTip, 0, 40)

	def __EnsureToolTip(self):
		if not self.toolTip:
			self.toolTip = uiToolTip.ToolTip(100)
			self.toolTip.HideToolTip()

	def __IsAutoPotionAffect(self):
		return self.affect in (chr.NEW_AFFECT_AUTO_HP_RECOVERY, chr.NEW_AFFECT_AUTO_SP_RECOVERY)

	def __ShouldShowTimedToolTip(self):
		return self.isClocked and self.endTime > 0 and not self.__IsAutoPotionAffect()

	# MR-16: Classic affect duration countdown
	def __ShouldShowInfiniteToolTip(self):
		return (self.isClocked and self.description and self.endTime == 0
			and not self.__IsAutoPotionAffect() and not self.__IsDragonSoulAffect())
	# MR-16: -- END OF -- Classic affect duration countdown

	def __UpdateTimedDescription(self, remainSec):
		if not self.description:
			return

		self.__EnsureToolTip()

		self.toolTip.ClearToolTip()
		self.toolTip.SetTitle(self.description)
		self.toolTip.AppendTextLine("(%s : %s)" % (localeInfo.LEFT_TIME, localeInfo.RTSecondToDHMS(remainSec)))
		self.toolTip.ResizeToolTip()

	# MR-16: Classic affect duration countdown
	def __GetInfiniteAffectItemName(self):
		vnum = self.INFINITE_AFFECT_ITEM_VNUM.get(self.affect)

		if not vnum:
			return None

		item.SelectItem(vnum)

		return item.GetItemName()

	def __UpdateInfiniteDescription(self):
		if not self.description:
			return

		self.__EnsureToolTip()

		self.toolTip.ClearToolTip()

		itemName = self.__GetInfiniteAffectItemName()

		if itemName:
			self.toolTip.SetTitle(itemName)

		self.toolTip.AppendTextLine(self.description)
		self.toolTip.ResizeToolTip()
	# MR-16: -- END OF -- Classic affect duration countdown

	def __IsDragonSoulAffect(self):
		return self.affect in (chr.NEW_AFFECT_DRAGON_SOUL_DECK1, chr.NEW_AFFECT_DRAGON_SOUL_DECK2)

	def __GetDragonSoulMinRemainSec(self):
		deckIndex = 0 if self.affect == chr.NEW_AFFECT_DRAGON_SOUL_DECK1 else 1
		now = app.GetGlobalTimeStamp()
		minRemain = None

		for i in range(6):
			slotNumber = deckIndex * player.DRAGON_SOUL_EQUIPMENT_FIRST_SIZE + (player.DRAGON_SOUL_EQUIPMENT_SLOT_START + i)
			itemVnum = player.GetItemIndex(slotNumber)

			if itemVnum == 0:
				continue

			item.SelectItem(itemVnum)
			remainSec = None

			for j in range(item.LIMIT_MAX_NUM):
				(limitType, limitValue) = item.GetLimit(j)

				if item.LIMIT_REAL_TIME == limitType or item.LIMIT_REAL_TIME_START_FIRST_USE == limitType:
					endTime = player.GetItemMetinSocket(player.INVENTORY, slotNumber, 0)
					remainSec = endTime - now
					break

				if item.LIMIT_TIMER_BASED_ON_WEAR == limitType:
					rawRemain = player.GetItemMetinSocket(player.INVENTORY, slotNumber, 0)
					cacheKey = (slotNumber, itemVnum)
					cache = self.dsTimeCache.get(cacheKey)

					if cache and cache["remainSec"] == rawRemain:
						remainSec = cache["endTime"] - now
					else:
						endTime = now + rawRemain
						self.dsTimeCache[cacheKey] = {"remainSec": rawRemain, "endTime": endTime}
						remainSec = endTime - now
					break

			if remainSec is None or remainSec <= 0:
				continue

			if minRemain is None or remainSec < minRemain:
				minRemain = remainSec

		return minRemain

	# MR-12: Fix realtime countdown auto-start
	def __UpdateDragonSoulDescription(self, minRemain = None):
		if not self.description:
			return

		if minRemain is None:
			minRemain = self.__GetDragonSoulMinRemainSec()

		self.__EnsureToolTip()
		self.toolTip.ClearToolTip()
		self.toolTip.SetTitle(self.description)

		if minRemain is not None:
			self.toolTip.AppendTextLine("(%s : %s)" % (localeInfo.LEFT_TIME, localeInfo.RTSecondToDHMS(minRemain)))

		self.toolTip.ResizeToolTip()
	# MR-12: -- END OF -- Fix realtime countdown auto-start

	def SetSkillAffectFlag(self, flag):
		self.isSkillAffect = flag

	def IsSkillAffect(self):
		return self.isSkillAffect

	## NOVA-197: what a left press does (a support buff's removal question); none by default.
	def SetPressEvent(self, event, *args):
		self.pressEvent = event
		self.pressEventArgs = args

	def OnMouseLeftButtonDown(self):
		if self.pressEvent:
			self.pressEvent(*self.pressEventArgs)

	def OnMouseOverIn(self):
		# MR-10: Add toolTip support and real-time countdown for affects
		self.isHover = True

		if self.__IsAutoPotionAffect():
			self.UpdateAutoPotionDescription()

			if self.toolTip:
				self.toolTip.ShowToolTip()
			return

		if self.__IsDragonSoulAffect():
			self.__UpdateDragonSoulDescription()

			if self.toolTip:
				self.toolTip.ShowToolTip()
			return

		if self.__ShouldShowTimedToolTip():
			remainSec = max(0, self.endTime - app.GetGlobalTimeStamp())
			self.__UpdateTimedDescription(remainSec)

			if self.toolTip:
				self.toolTip.ShowToolTip()
			return

		# MR-16: Classic affect duration countdown
		if self.__ShouldShowInfiniteToolTip():
			self.__UpdateInfiniteDescription()

			if self.toolTip:
				self.toolTip.ShowToolTip()
			return
		# MR-16: -- END OF -- Classic affect duration countdown

		if self.toolTipText:
			self.toolTipText.Show()

	def OnMouseOverOut(self):
		self.isHover = False

		if self.toolTip:
			self.toolTip.HideToolTip()

		if self.toolTipText:
			self.toolTipText.Hide()
		# MR-10: -- END OF -- Add toolTip support and real-time countdown for affects

## NOVA-11 (OLD uiAffectShower.py:453-516, 898-916): the premium tier's icon,
## first in the row. Its tooltip names the tier and the time left; a press
## asks whether to turn the premium time back into a scroll.
class PremiumImage(ui.ExpandedImageBox):

	## Spec Q9: OLD's art (d:/ymir work/ui/pattern/premium/01-03.dds) is a
	## later asset task. NEW's stock premium affect art stands in, Gold's for
	## Platinum. A tier with no entry shows nothing (PB-C7).
	IMAGE_DICT = {
		1 : "d:/ymir work/ui/skill/common/affect/silver_premium.sub",
		2 : "d:/ymir work/ui/skill/common/affect/premium_gold.sub",
		3 : "d:/ymir work/ui/skill/common/affect/premium_gold.sub",
	}
	## The tooltip is rebuilt at most once a second (spec 5.6; OLD tore it
	## down and rebuilt it every 500 ms, PB-C12).
	REFRESH_SECONDS = 1

	def __init__(self):
		ui.ExpandedImageBox.__init__(self)
		self.tier = 0
		self.endTime = 0
		self.nextRefreshTime = 0
		self.questionDialog = None

		self.toolTip = uiToolTip.ToolTip(150)
		self.toolTip.HideToolTip()

	def __del__(self):
		ui.ExpandedImageBox.__del__(self)

	def SetPremiumStatus(self, tier, secondsLeft):
		self.tier = tier
		self.LoadImage(self.IMAGE_DICT[tier])
		self.SetScale(0.7, 0.7)

		self.endTime = app.GetGlobalTimeStamp() + max(0, secondsLeft)
		self.nextRefreshTime = 0
		self.UpdateTime()

	def UpdateTime(self):
		now = app.GetGlobalTimeStamp()
		if now < self.nextRefreshTime:
			return

		self.nextRefreshTime = now + self.REFRESH_SECONDS
		self.toolTip.ClearToolTip()
		self.toolTip.SetTitle(localeInfo.PREMIUM_TITLE)
		self.toolTip.AppendTextLine(getattr(localeInfo, "PREMIUM_TIER_%d" % self.tier))
		self.toolTip.AppendTextLine(localeInfo.SecondToDHM(max(0, self.endTime - now)))
		self.toolTip.ResizeToolTip()

	def OnMouseLeftButtonDown(self):
		import uiCommon
		self.OnCloseQuestionDialog()

		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText(localeInfo.PREMIUM_DEACTIVATE_QUESTION)
		questionDialog.SetWidth(350)
		questionDialog.SetAcceptEvent(ui.__mem_func__(self.OnAcceptQuestionDialog))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		questionDialog.Open()
		self.questionDialog = questionDialog

	def OnAcceptQuestionDialog(self):
		## Once per question: the dialog goes before the command is sent.
		if not self.questionDialog:
			return

		self.OnCloseQuestionDialog()
		net.SendChatPacket("/deactivate_premium")

	def OnCloseQuestionDialog(self):
		if self.questionDialog:
			self.questionDialog.Close()

		self.questionDialog = None

	def OnMouseOverIn(self):
		self.toolTip.ShowToolTip()

	def OnMouseOverOut(self):
		self.toolTip.HideToolTip()

## NOVA-197 (OLD uiAffectShower.py:46-61, 415-448): the skill vnums of the
## support buffs a left press on their icon offers to remove (HOSIN, BOHO,
## GICHEON, KWAESOK, JEUNGRYEOK). Keep it equal to the server's
## REMOVABLE_SKILL_BUFFS, which refuses /remove_skill_affect for any other.
REMOVABLE_SKILL_BUFFS = (94, 95, 96, 110, 111)

## NOVA-218 (OLD uiAffectShower.py __ArrangeImageList): the icons in two
## rows, each sorted by affect so an icon never moves when another starts,
## ends or is renewed. The first row holds the status icons (premium, heart,
## horse) and the skill affects (the classic affect bits: buffs and debuffs);
## the second the potions and item bonuses: every affect the server sends as
## a NEW_AFFECT (the mall bonuses, EXP and drop bonuses, the auto potions, the
## dragon soul decks, ...) and the classic bits a potion or an item gives.
## Default, Eddy to confirm.
AFFECT_ROW_SKILLS = 0
AFFECT_ROW_ITEMS = 1
ITEM_AFFECT_BITS = (chr.AFFECT_ATT_SPEED_POTION, chr.AFFECT_MOV_SPEED_POTION, chr.AFFECT_FISH_MIND,
	chr.AFFECT_CHINA_FIREWORK)

def AffectRow(affect, isSkillAffect):
	"""The row of an affect's icon: a classic affect bit (SetAffect) is a
	skill unless a potion or an item gives it; the rest are items."""
	if isSkillAffect and affect not in ITEM_AFFECT_BITS:
		return AFFECT_ROW_SKILLS
	return AFFECT_ROW_ITEMS

def BuffiNameAffect():
	"""The buffi name scroll's affect (NOVA-38): chr.AFFECT_BUFFI_NAME, the
	server's AFFECT_BUFFI_NAME 553 on an exe without the name."""
	value = getattr(chr, "AFFECT_BUFFI_NAME", None)
	return value if isinstance(value, int) else 553


class AffectShower(ui.Window):

	MALL_DESC_IDX_START = 1000
	IMAGE_STEP = 25
	AFFECT_MAX_NUM = 32

	INFINITE_AFFECT_DURATION = 0x1FFFFFFF
	_liveInstances = weakref.WeakSet()
	
	# Maps affect key -> (localeInfo attribute name, image path).
	# AFFECT_DATA_DICT is built from this by _RebuildLocaleStrings().
	_AFFECT_TEMPLATE = {
		chr.AFFECT_POISON : ("SKILL_TOXICDIE", "d:/ymir work/ui/skill/common/affect/poison.sub"),
		chr.AFFECT_SLOW : ("SKILL_SLOW", "d:/ymir work/ui/skill/common/affect/slow.sub"),
		chr.AFFECT_STUN : ("SKILL_STUN", "d:/ymir work/ui/skill/common/affect/stun.sub"),
		chr.AFFECT_ATT_SPEED_POTION : ("SKILL_INC_ATKSPD", "d:/ymir work/ui/skill/common/affect/Increase_Attack_Speed.sub"),
		chr.AFFECT_MOV_SPEED_POTION : ("SKILL_INC_MOVSPD", "d:/ymir work/ui/skill/common/affect/Increase_Move_Speed.sub"),
		chr.AFFECT_FISH_MIND : ("SKILL_FISHMIND", "d:/ymir work/ui/skill/common/affect/fishmind.sub"),
		chr.AFFECT_JEONGWI : ("SKILL_JEONGWI", "d:/ymir work/ui/skill/warrior/jeongwi_03.sub"),
		chr.AFFECT_GEOMGYEONG : ("SKILL_GEOMGYEONG", "d:/ymir work/ui/skill/warrior/geomgyeong_03.sub"),
		chr.AFFECT_CHEONGEUN : ("SKILL_CHEONGEUN", "d:/ymir work/ui/skill/warrior/cheongeun_03.sub"),
		chr.AFFECT_GYEONGGONG : ("SKILL_GYEONGGONG", "d:/ymir work/ui/skill/assassin/gyeonggong_03.sub"),
		chr.AFFECT_EUNHYEONG : ("SKILL_EUNHYEONG", "d:/ymir work/ui/skill/assassin/eunhyeong_03.sub"),
		chr.AFFECT_GWIGEOM : ("SKILL_GWIGEOM", "d:/ymir work/ui/skill/sura/gwigeom_03.sub"),
		chr.AFFECT_GONGPO : ("SKILL_GONGPO", "d:/ymir work/ui/skill/sura/gongpo_03.sub"),
		chr.AFFECT_JUMAGAP : ("SKILL_JUMAGAP", "d:/ymir work/ui/skill/sura/jumagap_03.sub"),
		chr.AFFECT_HOSIN : ("SKILL_HOSIN", "d:/ymir work/ui/skill/shaman/hosin_03.sub"),
		chr.AFFECT_BOHO : ("SKILL_BOHO", "d:/ymir work/ui/skill/shaman/boho_03.sub"),
		chr.AFFECT_KWAESOK : ("SKILL_KWAESOK", "d:/ymir work/ui/skill/shaman/kwaesok_03.sub"),
		chr.AFFECT_HEUKSIN : ("SKILL_HEUKSIN", "d:/ymir work/ui/skill/sura/heuksin_03.sub"),
		chr.AFFECT_MUYEONG : ("SKILL_MUYEONG", "d:/ymir work/ui/skill/sura/muyeong_03.sub"),
		chr.AFFECT_GICHEON : ("SKILL_GICHEON", "d:/ymir work/ui/skill/shaman/gicheon_03.sub"),
		chr.AFFECT_JEUNGRYEOK : ("SKILL_JEUNGRYEOK", "d:/ymir work/ui/skill/shaman/jeungryeok_03.sub"),
		chr.AFFECT_PABEOP : ("SKILL_PABEOP", "d:/ymir work/ui/skill/sura/pabeop_03.sub"),
		chr.AFFECT_FALLEN_CHEONGEUN : ("SKILL_CHEONGEUN", "d:/ymir work/ui/skill/warrior/cheongeun_03.sub"),
		# MR-16: Added AFFECT_FIRE to Affects Shower
		chr.AFFECT_FIRE : ("SKILL_FIRE", "d:/ymir work/ui/skill/sura/hwayeom_03.sub"),
		# MR-16: -- END OF -- Added AFFECT_FIRE to Affects Shower
		chr.AFFECT_CHINA_FIREWORK : ("SKILL_POWERFUL_STRIKE", "d:/ymir work/ui/skill/common/affect/powerfulstrike.sub"),
		chr.NEW_AFFECT_EXP_BONUS : ("TOOLTIP_MALL_EXPBONUS_STATIC", "d:/ymir work/ui/skill/common/affect/exp_bonus.sub"),
		chr.NEW_AFFECT_ITEM_BONUS : ("TOOLTIP_MALL_ITEMBONUS_STATIC", "d:/ymir work/ui/skill/common/affect/item_bonus.sub"),
		chr.NEW_AFFECT_SAFEBOX : ("TOOLTIP_MALL_SAFEBOX", "d:/ymir work/ui/skill/common/affect/safebox.sub"),
		chr.NEW_AFFECT_AUTOLOOT : ("TOOLTIP_MALL_AUTOLOOT", "d:/ymir work/ui/skill/common/affect/autoloot.sub"),
		chr.NEW_AFFECT_FISH_MIND : ("TOOLTIP_MALL_FISH_MIND", "d:/ymir work/ui/skill/common/affect/fishmind.sub"),
		chr.NEW_AFFECT_MARRIAGE_FAST : ("TOOLTIP_MALL_MARRIAGE_FAST", "d:/ymir work/ui/skill/common/affect/marriage_fast.sub"),
		chr.NEW_AFFECT_GOLD_BONUS : ("TOOLTIP_MALL_GOLDBONUS_STATIC", "d:/ymir work/ui/skill/common/affect/gold_bonus.sub"),
		chr.NEW_AFFECT_NO_DEATH_PENALTY : ("TOOLTIP_APPLY_NO_DEATH_PENALTY", "d:/ymir work/ui/skill/common/affect/gold_premium.sub"),
		chr.NEW_AFFECT_SKILL_BOOK_BONUS : ("TOOLTIP_APPLY_SKILL_BOOK_BONUS", "d:/ymir work/ui/skill/common/affect/gold_premium.sub"),
		chr.NEW_AFFECT_SKILL_BOOK_NO_DELAY : ("TOOLTIP_APPLY_SKILL_BOOK_NO_DELAY", "d:/ymir work/ui/skill/common/affect/gold_premium.sub"),
		chr.NEW_AFFECT_AUTO_HP_RECOVERY : ("TOOLTIP_AUTO_POTION_REST", "d:/ymir work/ui/pattern/auto_hpgauge/05.dds"),
		chr.NEW_AFFECT_AUTO_SP_RECOVERY : ("TOOLTIP_AUTO_POTION_REST", "d:/ymir work/ui/pattern/auto_spgauge/05.dds"),
		# Mall point affects
		MALL_DESC_IDX_START + player.POINT_MALL_ATTBONUS : ("TOOLTIP_MALL_ATTBONUS_STATIC", "d:/ymir work/ui/skill/common/affect/att_bonus.sub"),
		MALL_DESC_IDX_START + player.POINT_MALL_DEFBONUS : ("TOOLTIP_MALL_DEFBONUS_STATIC", "d:/ymir work/ui/skill/common/affect/def_bonus.sub"),
		MALL_DESC_IDX_START + player.POINT_MALL_EXPBONUS : ("TOOLTIP_MALL_EXPBONUS", "d:/ymir work/ui/skill/common/affect/exp_bonus.sub"),
		MALL_DESC_IDX_START + player.POINT_MALL_ITEMBONUS : ("TOOLTIP_MALL_ITEMBONUS", "d:/ymir work/ui/skill/common/affect/item_bonus.sub"),
		MALL_DESC_IDX_START + player.POINT_MALL_GOLDBONUS : ("TOOLTIP_MALL_GOLDBONUS", "d:/ymir work/ui/skill/common/affect/gold_bonus.sub"),
		MALL_DESC_IDX_START + player.POINT_CRITICAL_PCT : ("TOOLTIP_APPLY_CRITICAL_PCT", "d:/ymir work/ui/skill/common/affect/critical.sub"),
		MALL_DESC_IDX_START + player.POINT_PENETRATE_PCT : ("TOOLTIP_APPLY_PENETRATE_PCT", "d:/ymir work/ui/skill/common/affect/gold_premium.sub"),
		MALL_DESC_IDX_START + player.POINT_MAX_HP_PCT : ("TOOLTIP_MAX_HP_PCT", "d:/ymir work/ui/skill/common/affect/gold_premium.sub"),
		MALL_DESC_IDX_START + player.POINT_MAX_SP_PCT : ("TOOLTIP_MAX_SP_PCT", "d:/ymir work/ui/skill/common/affect/gold_premium.sub"),
		MALL_DESC_IDX_START + player.POINT_PC_BANG_EXP_BONUS : ("TOOLTIP_MALL_EXPBONUS_P_STATIC", "d:/ymir work/ui/skill/common/affect/EXP_Bonus_p_on.sub"),
		MALL_DESC_IDX_START + player.POINT_PC_BANG_DROP_BONUS : ("TOOLTIP_MALL_ITEMBONUS_P_STATIC", "d:/ymir work/ui/skill/common/affect/Item_Bonus_p_on.sub"),
		# MR-12: Add Mall Attack speed affect
		MALL_DESC_IDX_START + player.POINT_ATT_SPEED : ("TOOLTIP_MALL_ATT_SPEED", "d:/ymir work/ui/skill/common/affect/Increase_Attack_Speed.sub"),
		# MR-12: -- END OF -- Add Mall Attack speed affect
	}

	if app.ENABLE_DRAGON_SOUL_SYSTEM:
		_AFFECT_TEMPLATE[chr.NEW_AFFECT_DRAGON_SOUL_DECK1] = ("TOOLTIP_DRAGON_SOUL_DECK1", "d:/ymir work/ui/dragonsoul/buff_ds_sky1.tga")
		_AFFECT_TEMPLATE[chr.NEW_AFFECT_DRAGON_SOUL_DECK2] = ("TOOLTIP_DRAGON_SOUL_DECK2", "d:/ymir work/ui/dragonsoul/buff_ds_land1.tga")

	## The buffi's name scroll (NOVA-38; OLD uiAffectShower.py:664): its +5%
	## against monsters, the affect's value. OLD showed the scroll's icon
	## (icon/item/91035.tga), which NEW's packs do not ship: the mall's attack
	## bonus icon instead.
	_AFFECT_TEMPLATE[BuffiNameAffect()] = ("TOOLTIP_APPLY_ATTBONUS_MONSTER", "d:/ymir work/ui/skill/common/affect/att_bonus.sub")

	AFFECT_DATA_DICT = {}  # populated by _RebuildLocaleStrings()

	@staticmethod
	def _RebuildLocaleStrings():
		d = {}
		for key, (attrName, path) in AffectShower._AFFECT_TEMPLATE.items():
			d[key] = (getattr(localeInfo, attrName), path)
		AffectShower.AFFECT_DATA_DICT = d
		for inst in AffectShower._liveInstances:
			inst.RefreshLocale()

	def RefreshLocale(self):
		for affect, image in list(self.affectImageDict.items()):
			if affect not in self.AFFECT_DATA_DICT:
				continue
			name = self.AFFECT_DATA_DICT[affect][0]
			skillIndex = player.AffectIndexToSkillIndex(affect)
			if 0 != skillIndex:
				name = skill.GetSkillName(skillIndex)
			if image.IsSkillAffect():
				image.SetToolTipText(name, 0, 40)
			else:
				image.SetDescription(name)
				image.UpdateDescription()

	def __init__(self):
		ui.Window.__init__(self)
		AffectShower._liveInstances.add(self)

		self.serverPlayTime = 0
		self.clientPlayTime = 0

		self.lastUpdateTime = 0
		self.affectImageDict = {}
		self.horseImage = None
		self.lovePointImage = None
		self.premiumImage = None
		self.removeQuestion = None
		self.removeQuestionAffect = None
		self.removeQuestionSkill = 0
		self.autoPotionImageHP = AutoPotionImage()
		self.autoPotionImageSP = AutoPotionImage()
		# MR-16: Classic affect duration countdown
		self.pendingClassicDurations = {}
		# MR-16: -- END OF -- Classic affect duration countdown

		self.SetPosition(10, 10)
		self.Show()

	def ClearAllAffects(self):
		self.horseImage = None
		self.lovePointImage = None
		self.affectImageDict = {}
		self.__CloseRemoveQuestion()
		# MR-16: Classic affect duration countdown
		self.pendingClassicDurations = {}
		# MR-16: -- END OF -- Classic affect duration countdown

		self.__ArrangeImageList()

	def ClearAffects(self): ## Clears skill affects on death; MALL (non-skill) affects survive.
		self.living_affectImageDict = {}

		for key, image in list(self.affectImageDict.items()):
			if not image.IsSkillAffect():
				self.living_affectImageDict[key] = image

		self.affectImageDict = self.living_affectImageDict
		if self.removeQuestionAffect not in self.affectImageDict:
			self.__CloseRemoveQuestion()
		# MR-16: Classic affect duration countdown
		self.pendingClassicDurations = {}
		# MR-16: -- END OF -- Classic affect duration countdown

		self.__ArrangeImageList()

	def BINARY_NEW_AddAffect(self, type, pointIdx, value, duration, affFlag = 0):
		print(("BINARY_NEW_AddAffect", type, pointIdx, value, duration, affFlag))

		if type < 500:
			# MR-16: Classic affect duration countdown
			# affFlag is the server-side AFF_* enum value (1-based).
			# The client's chr.AFFECT_* enum is 0-based, so affBit = affFlag - 1.
			# This covers all classic affects without any static mapping.
			if 0 < duration <= self.INFINITE_AFFECT_DURATION and affFlag > 0:
				affBit = affFlag - 1

				if affBit in self.AFFECT_DATA_DICT:
					if affBit in self.affectImageDict:
						# Icon already exists (CHARACTER_UPDATE arrived first) - update directly
						self.__ApplyClassicDuration(affBit, duration)
					else:
						# Icon not yet created - store for when __AppendAffect fires
						self.pendingClassicDurations[affBit] = duration
			# MR-16: -- END OF -- Classic affect duration countdown

			return

		if type == chr.NEW_AFFECT_MALL:
			affect = self.MALL_DESC_IDX_START + pointIdx
		else:
			affect = type

		if affect in self.affectImageDict:
			return

		if affect not in self.AFFECT_DATA_DICT:
			return

		## As an exception, the following affects have their Duration forced to 0.
		if affect == chr.NEW_AFFECT_NO_DEATH_PENALTY or\
		   affect == chr.NEW_AFFECT_SKILL_BOOK_BONUS or\
		   affect == chr.NEW_AFFECT_AUTO_SP_RECOVERY or\
		   affect == chr.NEW_AFFECT_AUTO_HP_RECOVERY or\
		   affect == chr.NEW_AFFECT_SKILL_BOOK_NO_DELAY:
			duration = 0

		affectData = self.AFFECT_DATA_DICT[affect]
		description = affectData[0]
		filename = affectData[1]

		if pointIdx == player.POINT_MALL_ITEMBONUS or\
		   pointIdx == player.POINT_MALL_GOLDBONUS:
			value = 1 + float(value) / 100.0

		trashValue = 123

		#if affect == chr.NEW_AFFECT_AUTO_SP_RECOVERY or affect == chr.NEW_AFFECT_AUTO_HP_RECOVERY:
		if trashValue == 1:
			try:
				#image = AutoPotionImage()
				#image.SetParent(self)
				image = None
				
				if affect == chr.NEW_AFFECT_AUTO_SP_RECOVERY:
					image.SetPotionType(player.AUTO_POTION_TYPE_SP)
					image = self.autoPotionImageSP
					#self.autoPotionImageSP = image;
				else:
					image.SetPotionType(player.AUTO_POTION_TYPE_HP)
					image = self.autoPotionImageHP
					#self.autoPotionImageHP = image;
				
				image.SetParent(self)
				image.Show()
				image.OnUpdateAutoPotionImage()
				
				self.affectImageDict[affect] = image

				self.__ArrangeImageList()
			except Exception as e:
				print(("except Aff auto potion affect ", e))
				pass
		else:
			if affect != chr.NEW_AFFECT_AUTO_SP_RECOVERY and affect != chr.NEW_AFFECT_AUTO_HP_RECOVERY:
				description = description(float(value))

			try:
				print(("Add affect %s" % affect))

				image = AffectImage()

				image.SetParent(self)
				image.LoadImage(filename)
				image.SetDescription(description)
				image.SetDuration(duration)
				image.SetAffect(affect)

				if affect == chr.NEW_AFFECT_EXP_BONUS_EURO_FREE or\
					affect == chr.NEW_AFFECT_EXP_BONUS_EURO_FREE_UNDER_15 or\
					self.INFINITE_AFFECT_DURATION < duration:
					image.SetClock(False)
					image.UpdateDescription()
				elif affect == chr.NEW_AFFECT_AUTO_SP_RECOVERY or affect == chr.NEW_AFFECT_AUTO_HP_RECOVERY:
					image.UpdateAutoPotionDescription()
				else:
					image.UpdateDescription()
					
				if affect == chr.NEW_AFFECT_DRAGON_SOUL_DECK1 or affect == chr.NEW_AFFECT_DRAGON_SOUL_DECK2:
					image.SetScale(1, 1)
				else:
					image.SetScale(0.7, 0.7)

				image.SetSkillAffectFlag(False)
				image.Show()
				self.affectImageDict[affect] = image
				self.__ArrangeImageList()
			except Exception as e:
				print(("except Aff affect ", e))
				pass

	def BINARY_NEW_RemoveAffect(self, type, pointIdx):
		if type == chr.NEW_AFFECT_MALL:
			affect = self.MALL_DESC_IDX_START + pointIdx
		else:
			affect = type
	
		print(("Remove Affect %s %s" % ( type , pointIdx )))
		self.__RemoveAffect(affect)
		self.__ArrangeImageList()

	def SetAffect(self, affect):
		self.__AppendAffect(affect)
		self.__ArrangeImageList()

	def ResetAffect(self, affect):
		self.__RemoveAffect(affect)
		self.__ArrangeImageList()

	def SetLoverInfo(self, name, lovePoint):
		image = LovePointImage()
		image.SetParent(self)
		image.SetLoverInfo(name, lovePoint)
		self.lovePointImage = image
		self.__ArrangeImageList()

	def ShowLoverState(self):
		if self.lovePointImage:
			self.lovePointImage.Show()
			self.__ArrangeImageList()

	def HideLoverState(self):
		if self.lovePointImage:
			self.lovePointImage.Hide()
			self.__ArrangeImageList()

	def ClearLoverState(self):
		self.lovePointImage = None
		self.__ArrangeImageList()

	def OnUpdateLovePoint(self, lovePoint):
		if self.lovePointImage:
			self.lovePointImage.OnUpdateLovePoint(lovePoint)

	def SetHorseState(self, level, health, battery):
		if level == 0:
			self.horseImage=None
		else:
			image = HorseImage()
			image.SetParent(self)
			image.SetState(level, health, battery)
			image.Show()

			self.horseImage = image

		# MR-17: Fix icons not re-arranging after horse state changes
		self.__ArrangeImageList()
		# MR-17: -- END OF -- Fix icons not re-arranging after horse state changes

	## NOVA-11 (OLD uiAffectShower.py:898-907): the tier C keeps from
	## GC::PREMIUM_STATUS, through game.BINARY_SetPremiumStatus. Tier 0 removes
	## the icon, and so does a tier with no icon (PB-C7: OLD raised KeyError).
	def SetPremiumStatus(self, tier, secondsLeft):
		if tier in PremiumImage.IMAGE_DICT:
			image = PremiumImage()
			image.SetParent(self)
			image.SetPremiumStatus(tier, secondsLeft)
			image.Show()
			self.premiumImage = image
		else:
			self.premiumImage = None

		self.__ArrangeImageList()

	def SetPlayTime(self, playTime):
		self.serverPlayTime = playTime
		self.clientPlayTime = app.GetTime()

	## NOVA-197 (OLD uiAffectShower.py:415-448): a left press on a support
	## buff's icon asks whether to remove it; Yes sends /remove_skill_affect
	## with the skill's vnum, which the server checks against its own list.
	## One question at a time; it closes when its affect ends.
	def __AskRemoveSkillAffect(self, affect, skillIndex):
		import uiCommon
		self.__CloseRemoveQuestion()

		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText(localeInfo.REMOVE_AFFECT_QUESTION % skill.GetSkillName(skillIndex))
		questionDialog.SetWidth(350)
		questionDialog.SetAcceptEvent(ui.__mem_func__(self.__AcceptRemoveQuestion))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.__CloseRemoveQuestion))
		questionDialog.Open()
		self.removeQuestion = questionDialog
		self.removeQuestionAffect = affect
		self.removeQuestionSkill = skillIndex

	def __AcceptRemoveQuestion(self):
		## Once per question: the dialog goes before the command is sent.
		if not self.removeQuestion:
			return

		skillIndex = self.removeQuestionSkill
		self.__CloseRemoveQuestion()
		net.SendChatPacket("/remove_skill_affect %d" % skillIndex)

	def __CloseRemoveQuestion(self):
		if self.removeQuestion:
			self.removeQuestion.Close()

		self.removeQuestion = None
		self.removeQuestionAffect = None
		self.removeQuestionSkill = 0

	def __AppendAffect(self, affect):

		if affect in self.affectImageDict:
			return

		try:
			affectData = self.AFFECT_DATA_DICT[affect]
		except KeyError:
			return

		name = affectData[0]
		filename = affectData[1]

		skillIndex = player.AffectIndexToSkillIndex(affect)

		if 0 != skillIndex:
			name = skill.GetSkillName(skillIndex)

		image = AffectImage()
		image.SetParent(self)
		image.SetSkillAffectFlag(True)

		try:
			image.LoadImage(filename)
		except:
			pass

		image.SetToolTipText(name, 0, 40)
		image.SetScale(0.7, 0.7)
		if skillIndex in REMOVABLE_SKILL_BUFFS:
			image.SetPressEvent(ui.__mem_func__(self.__AskRemoveSkillAffect), affect, skillIndex)
		image.Show()
		self.affectImageDict[affect] = image

		# MR-16: Classic affect duration countdown
		# Apply pending duration if AFFECT_ADD arrived before CHARACTER_UPDATE
		if affect in self.pendingClassicDurations:
			duration = self.pendingClassicDurations.pop(affect)
			self.__ApplyClassicDuration(affect, duration)
		# MR-16: -- END OF -- Classic affect duration countdown

	# MR-16: Classic affect duration countdown
	def __ApplyClassicDuration(self, affBit, duration):
		image = self.affectImageDict.get(affBit)
		if not image:
			return

		affectData = self.AFFECT_DATA_DICT.get(affBit)
		if not affectData:
			return

		name = affectData[0]
		skillIndex = player.AffectIndexToSkillIndex(affBit)
		if 0 != skillIndex:
			name = skill.GetSkillName(skillIndex)

		image.SetDescription(name)
		image.SetDuration(duration)
	# MR-16: -- END OF -- Classic affect duration countdown

	def __RemoveAffect(self, affect):
		"""
		if affect == chr.NEW_AFFECT_AUTO_SP_RECOVERY:
			self.autoPotionImageSP.Hide()

		if affect == chr.NEW_AFFECT_AUTO_HP_RECOVERY:
			self.autoPotionImageHP.Hide()
		"""
			
		if affect not in self.affectImageDict:
			print(("__RemoveAffect %s ( No Affect )" % affect))
			return

		print(("__RemoveAffect %s ( Affect )" % affect))
		del self.affectImageDict[affect]
		if affect == self.removeQuestionAffect:
			self.__CloseRemoveQuestion()
		
		self.__ArrangeImageList()

	## NOVA-218: two rows (AffectRow), the second only when it has icons, at
	## the top when the first is empty; each sorted by affect.
	ROW_STEP = 25

	def __ArrangeImageList(self):
		rows = ([], [])

		## The premium icon first (OLD uiAffectShower.py:982-987).
		if self.premiumImage:
			rows[AFFECT_ROW_SKILLS].append(self.premiumImage)

		if self.lovePointImage:
			if self.lovePointImage.IsShow():
				rows[AFFECT_ROW_SKILLS].append(self.lovePointImage)

		if self.horseImage:
			rows[AFFECT_ROW_SKILLS].append(self.horseImage)

		for affect in sorted(self.affectImageDict):
			image = self.affectImageDict[affect]
			rows[AffectRow(affect, image.IsSkillAffect())].append(image)

		width = 0
		yPos = 0
		for row in rows:
			if not row:
				continue

			for (index, image) in enumerate(row):
				image.SetPosition(index * self.IMAGE_STEP, yPos)

			width = max(width, len(row) * self.IMAGE_STEP)
			yPos += self.ROW_STEP

		self.SetSize(width, 26 + max(0, yPos - self.ROW_STEP))

	# MR-12: Fix realtime countdown auto-start
	def OnUpdate(self):
		try:
			if self.premiumImage:
				self.premiumImage.UpdateTime()

			for image in list(self.affectImageDict.values()):
				if image.GetAffect() == chr.NEW_AFFECT_AUTO_HP_RECOVERY or image.GetAffect() == chr.NEW_AFFECT_AUTO_SP_RECOVERY:
					image.UpdateAutoPotionDescription()
					continue

				# MR-16: Classic affect duration countdown
				if not image.IsSkillAffect():
					image.UpdateDescription()
					continue

				# Classic (skill) affects also need UpdateDescription when they
				# carry a timed duration captured from the AFFECT_ADD packet.
				if image.endTime > 0:
					image.UpdateDescription()
				# MR-16: -- END OF -- Classic affect duration countdown
		except Exception as e:
			print(("AffectShower::OnUpdate error : ", e))
	# MR-12: -- END OF -- Fix realtime countdown auto-start

AffectShower._RebuildLocaleStrings()
localeInfo.RegisterReloadCallback(AffectShower._RebuildLocaleStrings)
