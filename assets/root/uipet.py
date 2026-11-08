## The advanced pet's windows (NOVA-24; OLD root/uiPet.py, ENABLE_PET_ADVANCED).
##
## The pet lives on the server; chunk C's client keeps what GC::PET_ADVANCED
## sent in the `pet` module (contract 6) and calls the game window's
## BINARY_Pet* callbacks, which reach these windows through the Interface.
## The windows send the pet module's requests and show what it holds:
## - PetHatchEggWindow: an egg's hatch (pet.UseEgg) and the Pet Name
##   Changer's rename (pet.ChangeName), with OLD's uiscript;
## - PetEvolutionWindow: the evolution recipe (pet.Evolve);
## - PetInterfaceWindow: the mini window while a pet is out, folded after
##   30 seconds;
## - PetWindow: the pet window (key P), and a second instance for the
##   previews of another item (isPreview, pet.ReqPetPreview);
## - PetAttrRefineWindow: a bonus's upgrade (pet.RefineAttr).
## NovaUI subclasses each class (nui_pet*.py), so OLD's class, method and
## child names stay. OLD's bugs fixed here say "OLD bug" where they are.
import app
import player
import item
import chat
import wndMgr
import pet
import ui
import uiToolTip
import uiCommon
import localeInfo
import mouseModule
import uiScriptLocale


def GetEvolveLevelIndex(skip_level = -1, isPreview = False):
	"""The index of the evolution row the pet has reached: a row whose level
	the pet has reached counts once it has exp at that level (OLD: a pet at
	a gate with 0 exp has not evolved yet). -1 before the first row."""
	i = 0
	while True:
		now_level = pet.GetEvolveProtoLevel(i)
		if now_level == -1:
			break

		if skip_level != now_level:
			if now_level > pet.GetLevel(isPreview):
				break

			if now_level == pet.GetLevel(isPreview):
				if pet.GetExp(isPreview) == 0:
					break

		i += 1

	return i - 1

def GetEvolveLevel(skip_level = -1, isPreview = False):
	idx = GetEvolveLevelIndex(skip_level, isPreview)
	if idx == -1:
		return 0

	return pet.GetEvolveProtoLevel(idx)

def GetEvolveLocaleName(evolve_name):
	## OLD bug 8: OLD's data named the seventh grade "Mythic " (a trailing
	## space), so its key was not found; the name is stripped. OLD used eval.
	key = "PET_EVOLVE_GRADE_" + evolve_name.strip().upper().replace(" ", "")
	name = getattr(localeInfo, key, None)
	if not isinstance(name, str):
		return "[unknown: %s]" % evolve_name
	return name

def GetEvolveColor(index):
	## OLD read EVOLUTION_COLOR[index] unguarded in the mini window, which
	## raised for a pet before its first row (index -1).
	return EVOLUTION_COLOR.get(index, EVOLUTION_COLOR[0])

def GetAffectText(applyType, value):
	"""The bonus line of an APPLY_* at a value: the item tooltip's rule
	(OLD read localeInfo.AFFECT_DICT; NEW's table is the tooltip's)."""
	affect = uiToolTip.ItemToolTip.AFFECT_DICT.get(applyType)
	if affect is None:
		return "UNKNOWN_TYPE[%s] %s" % (applyType, value)
	return affect(value)

def GetAffectName(applyType):
	"""The bonus's name without its value, and whether it is a percentage
	(OLD's strip of the affect text at 0)."""
	attrName = GetAffectText(applyType, 0)
	percentBonus = '%' in attrName
	attrName = attrName.replace("+", "").replace("%%", "").replace("%d", "").replace("%f", "").replace("%s", "").replace("%", "").replace("0", "")
	return attrName.strip(), percentBonus

def SetStringEvent(window, event, func):
	"""OLD ui.py's ImageBox.SetStringEvent: NEW's ImageBox has no left press
	event and keeps its hover events in a dict of bound methods; the
	window's own handler is set instead (the window manager calls it)."""
	name = {"MOUSE_OVER_IN": "OnMouseOverIn", "MOUSE_OVER_OUT": "OnMouseOverOut",
			"MOUSE_LEFT_DOWN": "OnMouseLeftButtonDown"}[event]
	setattr(window, name, func)


EVOLUTION_COLOR = {
	0 : 0xFFFFD74C,  # Junior
	1 : 0xFFFFC542,  # Apprentice
	2 : 0xFFC427EB,  # Scout
	3 : 0xFF9A1FC6,  # Elite
	4 : 0xFF31D32A,  # Champion
	5 : 0xFF1F9E16,  # Veteran
	6 : 0xFFB9F2FF,  # Mythic
	7 : 0xFF89D3F9,  # Heroic
	8 : 0xFF55B5F6,  # Heroic Plus
	9 : 0xFF2A7BE4,  # Heroic Ascended
}

## OLD's labels were English in the code ("|~ffFEE3AEName:|h|r {}", a tag
## NEW's text engine does not read): locale keys in OLD's label color.
LABEL_COLOR = "|cffFEE3AE"

def LabelText(label, value):
	return "%s%s|r %s" % (LABEL_COLOR, label, value)

## A bonus stops at this level (OLD's literal 20, uiPet.py:1295; OLD bug 9).
PET_ATTR_MAX_LEVEL = 20
## The name the hatch window asks for at least (OLD's 3, uiPet.py:209).
PET_NAME_MIN_LEN = 3


class TextToolTip(ui.Window):
	"""A one-line tooltip over the pointer (the exp gauge and the bonuses)."""

	def __init__(self):
		ui.Window.__init__(self, "TOP_MOST")
		## OLD bug 9: OLD gave this window the gift box's name.
		self.SetWindowName("PetTextToolTip")
		textLine = ui.TextLine()
		textLine.SetParent(self)
		textLine.SetHorizontalAlignCenter()
		textLine.SetOutline()
		textLine.Show()
		self.textLine = textLine
		self.updateFunc = None

	def __del__(self):
		ui.Window.__del__(self)

	def SetText(self, text):
		self.textLine.SetText(text)

	def OnRender(self):
		(mouseX, mouseY) = wndMgr.GetMousePosition()
		self.textLine.SetPosition(mouseX, mouseY - 15)


class PetHatchEggWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self._window = -1
		self._egg_cell = -1
		self.changingName = False

		self.popupDlg = uiCommon.PopupDialog()
		self.popupDlg.Close()

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			ui.PythonScriptLoader().LoadScriptFile(self, "UIScript/PetHatchEggWindow.py")
		except:
			import exception
			exception.Abort("PetWindow.LoadScript")

		try:
			self.main = {
				"title" : self.GetChild("PetHatching_TitleBar"),
				"titleName" : self.GetChild("TitleName"),
				"item" : self.GetChild("HatchingItemSlot"),
				"name" : self.GetChild("pet_name"),
				"price" : self.GetChild("HatchingMoney"),
				"hatch" : self.GetChild("HatchingButton"),
			}

		except:
			import exception
			exception.Abort("PetWindow.BindObject")

		self.main["title"].SetCloseEvent(ui.__mem_func__(self.Close))

		self.main["item"].SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.main["item"].SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.main["item"].SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		self.main["name"].SAFE_SetReturnEvent(self.__OnClickHatch)
		self.main["name"].SetEscapeEvent(ui.__mem_func__(self.Close))

		self.main["hatch"].SAFE_SetEvent(self.__OnClickHatch)

	def Destroy(self):
		self.Close()

		self.main = None
		self.popupDlg = None

		ui.ScriptWindow.Destroy(self)

	def Open(self, egg_cell, window = player.INVENTORY, isRename = False):
		## Decision Q2 (NOVA-24): an egg made while PET_EGG_HATCH_SECONDS was
		## above 0 holds the time it can hatch in its socket 1. OLD's own check
		## (commented out at uiPet.py:155-157, socket 0, which the egg's expiry
		## overwrote), now with the time left (OLD bug 6).
		if not isRename:
			leftSec = player.GetItemMetinSocket(window, egg_cell, pet.EGG_HATCH_SOCKET) - app.GetGlobalTimeStamp()
			if leftSec > 0:
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.PET_HATCH_NEED_WAIT % localeInfo.SecondToDHM(leftSec))
				return

		self.changingName = isRename
		self._window = window
		self._egg_cell = egg_cell

		item_vnum = player.GetItemIndex(window, egg_cell)
		item.SelectItem(item_vnum)
		price = item.GetValue(2)
		pet_item_vnum = item.GetValue(1)

		item.SelectItem(pet_item_vnum)
		self.main["item"].SetItemSlot(0, item_vnum)
		if not self.changingName:
			self.main["item"].SetItemSlot(1, pet_item_vnum)
		else:
			## OLD bug 11: a rename after a hatch kept the last egg's pet in
			## slot 1, drawn over the seal.
			self.main["item"].ClearSlot(1)
		self.main["item"].RefreshSlot()

		self.main["name"].SetText("")

		if isRename:
			self.main["titleName"].SetText(localeInfo.PET_HATCH_RENAME_TITLE)
			self.main["hatch"].SetText(localeInfo.PET_HATCH_RENAME_BUTTON)
			self.main["price"].Hide()
		else:
			self.main["titleName"].SetText(uiScriptLocale.PET_HATCHING_WINDOW_TITLE)
			self.main["hatch"].SetText(uiScriptLocale.PET_HATCHING_BUTTON)
			self.main["price"].Show()

		if price > 0:
			self.main["price"].SetText(localeInfo.TOOLTIP_SELLPRICE % localeInfo.NumberToMoneyString(price))

		self.main["name"].SetFocus()

		self.SetTop()
		self.Show()

	def Close(self):
		self.main["name"].KillFocus()
		self.Hide()

		self.popupDlg.Close()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def __ShowPopup(self, text):
		self.popupDlg.SetText(text)
		self.popupDlg.Open()

	def __OnClickHatch(self):
		name = self.main["name"].GetText()
		if len(name) < PET_NAME_MIN_LEN:
			## OLD bug 1: OLD called the dialog object and formatted a text
			## that has no %d.
			self.__ShowPopup(localeInfo.PET_HATCH_NAME_TOO_SHORT)
			return

		if self.changingName:
			pet.ChangeName(self._window, self._egg_cell, name)
		else:
			pet.UseEgg(self._window, self._egg_cell, name)
		self.Close()

	def OverInItem(self, slotIndex):
		return

	def OverOutItem(self):
		return


class PetEvolutionWindow(ui.ScriptWindow):

	MATERIAL_SIZE = 36
	MATERIAL_SPACE = 7

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self._popupDlg = uiCommon.PopupDialog()
		self._popupDlg.Close()

		self._materials = []

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			ui.PythonScriptLoader().LoadScriptFile(self, "UIScript/PetEvolutionWindow.py")
		except:
			import exception
			exception.Abort("PetWindow.LoadScript")

		try:
			self.main = {
				"title" : self.GetChild("TitleBar"),
				"item" : self.GetChild("item"),
				"pet_name" : self.GetChild("pet_name"),
				"current" : {
					"title" : self.GetChild("evolve_current"),
					"active_skill" : self.GetChild("active_skill_count_current"),
					"passive_skill" : self.GetChild("passive_skill_count_current"),
				},
				"next" : {
					"title" : self.GetChild("evolve_next"),
					"active_skill" : self.GetChild("active_skill_count_next"),
					"passive_skill" : self.GetChild("passive_skill_count_next"),
				},
				"material" : self.GetChild("material_window"),
				"cost" : self.GetChild("cost"),
				"evolve" : self.GetChild("evolve"),
				"cancel" : self.GetChild("cancel"),
			}

		except:
			import exception
			exception.Abort("PetWindow.BindObject")

		itemToolTip = uiToolTip.ItemToolTip()
		itemToolTip.HideToolTip()
		self._itemToolTip = itemToolTip

		self.main["title"].SetCloseEvent(ui.__mem_func__(self.Close))

		self.main["evolve"].SAFE_SetEvent(self.__OnClickEvolve)
		self.main["cancel"].SAFE_SetEvent(self.Close)

		SetStringEvent(self.main["item"], "MOUSE_OVER_IN", lambda: self._itemToolTip.SetItemToolTip(pet.GetItemVnum()))
		SetStringEvent(self.main["item"], "MOUSE_OVER_OUT", lambda: self._itemToolTip.HideToolTip())

	def Destroy(self):
		self.Close()

		self.main = None
		self._popupDlg = None
		self._itemToolTip = None
		self._materials = None

		ui.ScriptWindow.Destroy(self)

	def Open(self):
		self.Refresh()
		if not self.IsShow():
			self.SetCenterPosition()
			self.SetTop()
			self.Show()

	def Close(self):
		self.Hide()

		self._popupDlg.Close()
		self._itemToolTip.HideToolTip()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def __MakeMaterial(self, index):
		mat_vnum, mat_count = pet.GetEvolveMaterial(index)
		item.SelectItem(mat_vnum)

		mat_item = ui.ImageBox()
		mat_item.SetParent(self.main["material"])
		mat_item.LoadImage(item.GetIconImageFileName())
		SetStringEvent(mat_item, "MOUSE_OVER_IN", lambda arg=mat_vnum: self._itemToolTip.SetItemToolTip(arg))
		SetStringEvent(mat_item, "MOUSE_OVER_OUT", lambda: self._itemToolTip.HideToolTip())
		mat_item.Show()

		mat_xcount = ui.NumberLine()
		mat_xcount.SetParent(mat_item)
		mat_xcount.SetPosition(3, 9)
		mat_xcount.SetHorizontalAlignRight()
		mat_xcount.SetWindowHorizontalAlignRight()
		mat_xcount.SetWindowVerticalAlignBottom()
		mat_xcount.SetNumber(str(mat_count))
		mat_xcount.Show()

		mat_item.count = mat_xcount

		return mat_item

	def RefreshProto(self):
		evolve_level = GetEvolveLevel()
		next_evolve_level = pet.GetEvolveProtoLevel(GetEvolveLevelIndex() + 1)
		item_vnum = pet.GetItemVnum()
		item.SelectItem(item_vnum)

		self.main["item"].LoadImage(item.GetIconImageFileName())
		self.main["pet_name"].SetText(pet.GetName())

		kv_level = {
			"current" : (evolve_level, GetEvolveLevelIndex()),
			"next" : (next_evolve_level, GetEvolveLevelIndex() + 1),
		}
		for key in ("current", "next"):
			obj = self.main[key]
			lvl, lvl_idx = kv_level[key]

			obj["title"].SetText(GetEvolveLocaleName(pet.GetEvolveProtoName(lvl)))
			obj["title"].SetPackedFontColor(GetEvolveColor(lvl_idx))
			obj["active_skill"].SetText(localeInfo.PET_EVOLVE_ACTIVE_SKILL_COUNT % str(pet.GetEvolveProtoNormalSkillCount(lvl)))
			obj["passive_skill"].SetText(localeInfo.PET_EVOLVE_PASSIVE_SKILL_COUNT % str(pet.GetHeroicProtoPassiveSkillCount(lvl)))

	def RefreshRequirements(self):
		self._materials = []

		matCount = pet.GetEvolveMaterialCount()
		matWidth = self.MATERIAL_SIZE * matCount + self.MATERIAL_SPACE * (matCount - 1)
		xpos = (self.main["material"].GetWidth() - matWidth) // 2

		for i in range(matCount):
			mat = self.__MakeMaterial(pet.GetEvolveMaterialCount() - 1 - i)
			self._materials.append(mat)

			mat.SetPosition(xpos, 12)
			xpos += self.MATERIAL_SIZE + self.MATERIAL_SPACE

		## OLD added a gold emoji ("|E~/gold.png|e"), which NEW's text engine
		## does not draw: the money string names the unit.
		self.main["cost"].SetText(localeInfo.PET_EVOLVE_PRICE % localeInfo.NumberToMoneyString(pet.GetEvolveCost()))

	def Refresh(self):
		self.RefreshProto()
		self.RefreshRequirements()

	def __ShowPopup(self, text):
		self._popupDlg.SetText(text)
		self._popupDlg.Open()

	def __OnClickEvolve(self):
		if player.GetMoney() < pet.GetEvolveCost():
			self.__ShowPopup(localeInfo.PET_EVOLVE_ERROR_NOT_ENOUGH_GOLD)
			return

		for i in range(pet.GetEvolveMaterialCount()):
			mat_vnum, mat_count = pet.GetEvolveMaterial(i)
			inven_count = player.GetItemCountByVnum(mat_vnum)
			if inven_count < mat_count:
				item.SelectItem(mat_vnum)
				self.__ShowPopup(localeInfo.PET_EVOLVE_ERROR_NOT_ENOUGH_ITEM % (mat_count - inven_count, item.GetItemName()))
				return

		pet.Evolve()

	def OnEvolveFailure(self):
		self.__ShowPopup(localeInfo.PET_EVOLVE_FAILURE)

	def OnEvolveSuccess(self):
		self.Close()
		self.__ShowPopup(localeInfo.PET_EVOLVE_SUCCESS)


class PetInterfaceWindow(ui.ScriptWindow):
	"""The mini window while a pet is out: the pet's icon, name, level,
	grade, exp and skills, folded to the icon (75 x 75) after 30 seconds
	open. A click on the icon opens or folds it, animated."""

	# --- Sizes & timings ---
	_DEFAULT_W = 245
	_DEFAULT_H = 135
	_MIN_W = 75
	_MIN_H = 75
	_EXPAND_SECS = 30.0
	_ANIM_EXPAND = 0.22
	_ANIM_MINIMIZE = 0.18
	_SHOW_EXTRAS_AT = 0.60  # show extras during expand once 60% done

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		# State
		self._isMinimized = True
		self._expandUntil = 0.0

		# Animation state
		self._animActive = False
		self._animStartTime = 0.0
		self._animDuration = 0.0
		self._animStartW = self._MIN_W
		self._animStartH = self._MIN_H
		self._animTargetW = self._DEFAULT_W
		self._animTargetH = self._DEFAULT_H
		self._animKind = None  # "expand" | "minimize"
		self._extrasShown = True  # synced by the Apply*Layout calls

		# Icon position shifting (px)
		self._iconShift = 12
		self._imgBasePos = self._imgMinPos = None
		self._effectBasePos = self._effectMinPos = None
		self._slotImgBasePos = self._slotImgMinPos = None

		# Per-anim position lerp (start -> target)
		self._imgStartPos = self._imgTargetPos = None
		self._effectStartPos = self._effectTargetPos = None
		self._slotImgStartPos = self._slotImgTargetPos = None

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			ui.PythonScriptLoader().LoadScriptFile(self, "UIScript/PetInterfaceWindow.py")
		except:
			import exception
			exception.Abort("PetWindow.LoadScript")

		try:
			self.main = {
				"title": self.GetChild("title"),
				"evo": self.GetChild("evo"),
				"image": self.GetChild("image"),
				"ExpBar": self.GetChild("ExpBar"),
				"skill": self.GetChild("skill_slot"),
				"skill_disabled": [self.GetChild("skill_slot%d_disabled" % (i + 1)) for i in range(pet.SKILL_MAX_NUM)],
			}

			# Nodes
			self.board = self.GetChild("board")
			self.expBarBG = self.GetChild("expBar_bg")
			self.mainSlotImg = self.GetChild("main_slot_img")            # always visible + nudged
			self.slotEffect = self.GetChild("pet_icon_slot_ani_img")     # always visible + nudged

			# Extras to hide/show (not mainSlotImg, which always shows)
			self._extras = [
				self.main["title"],
				self.main["evo"],
				self.expBarBG,
				self.main["skill"],
			]

			self.__CacheIconBasePositions()

		except:
			import exception
			exception.Abort("PetWindow.BindObject")

		self.itemToolTip = uiToolTip.ItemToolTip()
		self.itemToolTip.HideToolTip()

		self.skillToolTip = uiToolTip.PetSkillToolTip()
		self.skillToolTip.HideToolTip()

		self.textToolTip = TextToolTip()
		self.textToolTip.Hide()

		# Events
		SetStringEvent(self.main["image"], "MOUSE_LEFT_DOWN", ui.__mem_func__(self.__OnImageClick))
		SetStringEvent(self.main["ExpBar"], "MOUSE_OVER_IN", lambda func=self.__OverInExp: self.__ShowTextToolTip(func))
		SetStringEvent(self.main["ExpBar"], "MOUSE_OVER_OUT", lambda: self.textToolTip.Hide())

		self.main["skill"].SetOverInItemEvent(self.__OverInSkillSlot)
		self.main["skill"].SetOverOutItemEvent(self.__OverOutSkillSlot)
		self.main["skill"].SetSelectItemSlotEvent(self.__ClickSkillSlot)

		# Start minimized
		self.__ApplyMinimizedLayout()

	def Destroy(self):
		self.Close()

		self.main = None
		self.skillToolTip = None
		self.itemToolTip = None
		self.textToolTip = None

		ui.ScriptWindow.Destroy(self)

	## OLD bug 2: OLD's toggle here called an Interface method that does
	## not exist; nothing called it. Removed:
	## the Interface's TogglePetWindow is the pet window's toggle.

	def Open(self):
		self.Refresh()
		self.SetTop()
		self.__ApplyMinimizedLayout()
		self.Show()

	def Close(self):
		self.Hide()
		self.skillToolTip.Hide()
		self.itemToolTip.Hide()
		self.textToolTip.Hide()

	# -----------------------------
	# Animation helpers
	# -----------------------------
	def __time_now(self):
		return app.GetTime()

	def __ease_out_cubic(self, t):
		if t <= 0.0: return 0.0
		if t >= 1.0: return 1.0
		u = 1.0 - t
		return 1.0 - u * u * u

	def __ease_in_cubic(self, t):
		if t <= 0.0: return 0.0
		if t >= 1.0: return 1.0
		return t * t * t

	def __setWindowSize(self, w, h):
		w = int(round(w)); h = int(round(h))
		if self.board:
			self.board.SetSize(w, h)
		self.SetSize(w, h)

	def __setExtrasVisible(self, show):
		if self._extrasShown == show:
			return
		for w in self._extras:
			if not w: continue
			(w.Show if show else w.Hide)()
		self._extrasShown = show

	def __getLocalPosSafe(self, wnd):
		try:
			return wnd.GetLocalPosition()
		except:
			return (0, 0)

	def __setPosSafe(self, wnd, x, y):
		try:
			wnd.SetPosition(x, y)
		except:
			pass

	def __CacheIconBasePositions(self):
		ix, iy = self.__getLocalPosSafe(self.main["image"])
		self._imgBasePos = (ix, iy)
		self._imgMinPos = (ix + self._iconShift, iy)

		ex, ey = self.__getLocalPosSafe(self.slotEffect)
		self._effectBasePos = (ex, ey)
		self._effectMinPos = (ex + self._iconShift, ey)

		sx, sy = self.__getLocalPosSafe(self.mainSlotImg)
		self._slotImgBasePos = (sx, sy)
		self._slotImgMinPos = (sx + self._iconShift, sy)

		self._imgStartPos = self._imgTargetPos = self._imgBasePos
		self._effectStartPos = self._effectTargetPos = self._effectBasePos
		self._slotImgStartPos = self._slotImgTargetPos = self._slotImgBasePos

	def __ApplyIconPosForState(self, minimized):
		img = self._imgMinPos if minimized else self._imgBasePos
		eff = self._effectMinPos if minimized else self._effectBasePos
		slt = self._slotImgMinPos if minimized else self._slotImgBasePos

		self.__setPosSafe(self.main["image"], img[0], img[1])
		self.__setPosSafe(self.slotEffect, eff[0], eff[1])
		self.__setPosSafe(self.mainSlotImg, slt[0], slt[1])

	def __ApplyMinimizedLayout(self):
		self._animActive = False
		self.__setWindowSize(self._MIN_W, self._MIN_H)
		self.__setExtrasVisible(False)
		self.main["image"].Show()
		self.mainSlotImg.Show()
		self.slotEffect.Show()
		self.__ApplyIconPosForState(True)   # shift right when minimized
		self._isMinimized = True

	def __ApplyExpandedLayout(self):
		self._animActive = False
		self.__setWindowSize(self._DEFAULT_W, self._DEFAULT_H)
		self.__setExtrasVisible(True)
		self.main["image"].Show()
		self.mainSlotImg.Show()
		self.slotEffect.Show()
		self.__ApplyIconPosForState(False)
		self._isMinimized = False

	def __StartAnimTo(self, target_w, target_h, duration, kind):
		self._animStartW = self.GetWidth()
		self._animStartH = self.GetHeight()
		self._animTargetW = target_w
		self._animTargetH = target_h
		self._animDuration = max(0.01, float(duration))
		self._animStartTime = self.__time_now()
		self._animKind = kind
		self._animActive = True

		self._imgStartPos = self.__getLocalPosSafe(self.main["image"])
		self._effectStartPos = self.__getLocalPosSafe(self.slotEffect)
		self._slotImgStartPos = self.__getLocalPosSafe(self.mainSlotImg)

		if kind == "minimize":
			self._imgTargetPos = self._imgMinPos
			self._effectTargetPos = self._effectMinPos
			self._slotImgTargetPos = self._slotImgMinPos
		else:
			self._imgTargetPos = self._imgBasePos
			self._effectTargetPos = self._effectBasePos
			self._slotImgTargetPos = self._slotImgBasePos
		self.__setExtrasVisible(False)  # hidden at the start of either; an expand shows them part-way

	def __Lerp2(self, a, b, p):
		return (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)

	def __TickAnimation(self):
		if not self._animActive:
			return

		now = self.__time_now()
		t = (now - self._animStartTime) / self._animDuration

		if t >= 1.0:
			self.__setWindowSize(self._animTargetW, self._animTargetH)
			self._animActive = False
			if self._animKind == "expand":
				self.__setExtrasVisible(True)
				self.__ApplyIconPosForState(False)
				self._isMinimized = False
			else:
				self.__setExtrasVisible(False)
				self.__ApplyIconPosForState(True)
				self._isMinimized = True
			return

		if self._animKind == "expand":
			p = self.__ease_out_cubic(t)
			if not self._extrasShown and t >= self._SHOW_EXTRAS_AT:
				self.__setExtrasVisible(True)
		else:
			p = self.__ease_in_cubic(t)

		cw = self._animStartW + (self._animTargetW - self._animStartW) * p
		ch = self._animStartH + (self._animTargetH - self._animStartH) * p
		self.__setWindowSize(cw, ch)

		ip = self.__Lerp2(self._imgStartPos, self._imgTargetPos, p)
		ep = self.__Lerp2(self._effectStartPos, self._effectTargetPos, p)
		sp = self.__Lerp2(self._slotImgStartPos, self._slotImgTargetPos, p)

		self.__setPosSafe(self.main["image"], int(round(ip[0])), int(round(ip[1])))
		self.__setPosSafe(self.slotEffect, int(round(ep[0])), int(round(ep[1])))
		self.__setPosSafe(self.mainSlotImg, int(round(sp[0])), int(round(sp[1])))

	# -----------------------------
	# Public / events
	# -----------------------------
	def __OnImageClick(self):
		now = self.__time_now()

		# If mid-animation, reverse direction
		if self._animActive:
			if self._animKind == "expand":
				self._expandUntil = 0.0
				self.__StartMinimize()
			else:
				self.__StartAnimTo(self._DEFAULT_W, self._DEFAULT_H, self._ANIM_EXPAND, "expand")
				self._expandUntil = now + float(self._EXPAND_SECS)
			return

		if self._isMinimized:
			self.__StartAnimTo(self._DEFAULT_W, self._DEFAULT_H, self._ANIM_EXPAND, "expand")
			self._expandUntil = now + float(self._EXPAND_SECS)
		else:
			self._expandUntil = 0.0
			self.__StartMinimize()

	def __StartMinimize(self):
		# Hide any active tooltips when collapsing
		self.skillToolTip.Hide()
		self.itemToolTip.Hide()
		self.textToolTip.Hide()
		self.__StartAnimTo(self._MIN_W, self._MIN_H, self._ANIM_MINIMIZE, "minimize")

	def OnUpdate(self):
		if self.textToolTip.IsShow() and self.textToolTip.updateFunc:
			self.textToolTip.updateFunc()

		self.__TickAnimation()

		# Fold after the 30 seconds (an animation runs to its end first)
		if (not self._isMinimized) and (not self._animActive):
			if self.__time_now() >= self._expandUntil:
				self.__StartMinimize()

	def Refresh(self):
		self.RefreshStatus()
		self.RefreshSkillSlot()

	def RefreshStatus(self):
		item.SelectItem(pet.GetItemVnum())
		self.main["title"].SetText(pet.GetName() + " [Lv. " + str(pet.GetLevel()) + "]")
		self.main["evo"].SetPackedFontColor(GetEvolveColor(GetEvolveLevelIndex()))
		self.main["evo"].SetText(LabelText(localeInfo.PET_INFO_EVOLUTION, GetEvolveLocaleName(pet.GetEvolveProtoName(GetEvolveLevel()))))

		self.main["image"].LoadImage(item.GetIconImageFileName())
		self.RefreshExp(pet.GetExp(), pet.GetNextExp())

	def RefreshExp(self, curPoint, maxPoint):
		curPoint = min(curPoint, maxPoint)
		curPoint = max(curPoint, 0)
		maxPoint = max(maxPoint, 0)

		if int(maxPoint) == 0:
			self.main["ExpBar"].SetPercentage(0.0, 1.0)
			return

		self.main["ExpBar"].SetPercentage(min(float(curPoint), float(maxPoint)), float(maxPoint))

	def RefreshDisabledSkillSlot(self, start_idx, end_idx, enabled_count):
		for i in range(start_idx, end_idx):
			idx = i - start_idx
			if idx < enabled_count:
				self.main["skill_disabled"][i].Hide()
			else:
				self.main["skill_disabled"][i].Show()

	def RefreshSkillSlot(self):
		self.RefreshDisabledSkillSlot(pet.SKILL_NORMAL_START, pet.SKILL_HEROIC_START, pet.GetEvolveProtoNormalSkillCount(GetEvolveLevel()))
		self.RefreshDisabledSkillSlot(pet.SKILL_HEROIC_START, pet.SKILL_MAX_NUM, pet.GetHeroicProtoPassiveSkillCount(GetEvolveLevel()))

		for i in range(pet.SKILL_MAX_NUM):
			vnum = pet.GetSkillID(i)
			if vnum == 0:
				self.main["skill"].ClearSlot(i)
				continue

			self.main["skill"].SetPetSkillSlot(i, vnum, 0, 0.55, 0.55)

		self.main["skill"].RefreshSlot()

	def __ShowTextToolTip(self, func):
		func()
		self.textToolTip.updateFunc = func
		self.textToolTip.Show()

	def __OverInExp(self):
		exp = pet.GetExp()
		max_exp = pet.GetNextExp()
		if max_exp == 0:
			max_exp = 1
		pct = exp * 100.0 / max_exp
		if pct > 100.0:
			pct = 100.0

		self.textToolTip.SetText(localeInfo.TARGET_INFO_EXP % ("%.2f%%" % pct))

	## OLD bug 3: OLD's stamina tooltip read a pet stamina getter and a
	## locale text that no module has; nothing called it. Removed.

	def __OverInSkillSlot(self, slotIndex):
		self.skillToolTip.SetSkill(pet.GetSkillID(slotIndex), pet.GetSkillLevel(slotIndex))

	def __OverOutSkillSlot(self):
		self.skillToolTip.HideToolTip()

	def __ClickSkillSlot(self, slotIndex):
		ClickSkillSlot(slotIndex)


def ClickSkillSlot(slotIndex):
	"""A SKILL_REVERT item dropped on a skill cell resets that skill (OLD's
	__ClickSkillSlot of both windows, uiPet.py:871-882 and 1132-1143)."""
	if mouseModule.mouseController.isAttached():
		attachedSlotType = mouseModule.mouseController.GetAttachedType()
		attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
		attachedItemIndex = mouseModule.mouseController.GetAttachedItemIndex()

		item.SelectItem(attachedItemIndex)
		if player.SLOT_TYPE_INVENTORY == attachedSlotType:
			if item.GetItemType() == item.ITEM_TYPE_PET_ADVANCED and item.GetItemSubType() == item.PET_SKILL_REVERT:
				pet.UseResetSkill(player.INVENTORY, attachedSlotPos, slotIndex)

	mouseModule.mouseController.DeattachObject()


class PetWindow(ui.ScriptWindow):
	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.isPreview = False

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			ui.PythonScriptLoader().LoadScriptFile(self, "UIScript/PetWindow.py")
		except:
			import exception
			exception.Abort("PetWindow.LoadScript")

		try:
			GetObject = self.GetChild
			self.main = {
				"Background" : GetObject("bg"),
				"PetImage" : GetObject("PetImage"),
				"PetName" : GetObject("PetName"),
				"PetLevel" : GetObject("PetLevel"),
				"PetEvolution" : GetObject("PetEvolution"),

				"PetExpBar" : GetObject("ExpBar"),

				"evolution_upgrade" : GetObject("evolution_upgrade"),
				"bonus" : [{
					"name" : GetObject("bonus%d_name" % (i + 1)),
					"level" : GetObject("bonus%d_level" % (i + 1)),
					"plus" : GetObject("bonus%d_plus_btn" % (i + 1)),
				} for i in range(pet.ATTR_MAX_NUM)],
				"bg" : [{
					"name" : GetObject("bonus%d_name_bg" % (i + 1)),
					"level" : GetObject("bonus%d_level_bg" % (i + 1)),
				} for i in range(pet.ATTR_MAX_NUM)],
				"skill" : GetObject("skill_slot"),
				"skill_disabled" : [GetObject("skill_slot%d_disabled" % (i + 1)) for i in range(pet.SKILL_MAX_NUM)],
			}

			GetObject("CloseBtn").SetEvent(ui.__mem_func__(self.Close))

		except:
			import exception
			exception.Abort("PetWindow.BindObject")

		self.itemToolTip = uiToolTip.ItemToolTip()
		self.itemToolTip.HideToolTip()

		self.skillToolTip = uiToolTip.PetSkillToolTip()
		self.skillToolTip.HideToolTip()

		self.textToolTip = TextToolTip()
		self.textToolTip.Hide()

		self.main["evolution_upgrade"].SetEvent(pet.RequestEvolutionInfo)

		SetStringEvent(self.main["PetExpBar"], "MOUSE_OVER_IN", lambda func=self.__OverInExp: self.__ShowTextToolTip(func))
		SetStringEvent(self.main["PetExpBar"], "MOUSE_OVER_OUT", lambda: self.textToolTip.Hide())

		for i in range(pet.ATTR_MAX_NUM):
			tmpfunc0 = lambda arg=i: self.__ClickAttr(arg)
			SetStringEvent(self.main["bg"][i]["level"], "MOUSE_LEFT_DOWN", lambda func=tmpfunc0: self.__OnClickAttr(func))
			self.main["bonus"][i]["plus"].SetEvent(lambda arg=i: self.__ClickAttr(arg))
			tmpfunc = lambda arg=i: self.__OverInBonus(arg)
			SetStringEvent(self.main["bg"][i]["level"], "MOUSE_OVER_IN", lambda func=tmpfunc: self.__ShowTextToolTip(func))
			SetStringEvent(self.main["bg"][i]["level"], "MOUSE_OVER_OUT", lambda: self.textToolTip.Hide())

		self.main["skill"].SetOverInItemEvent(self.__OverInSkillSlot)
		self.main["skill"].SetOverOutItemEvent(self.__OverOutSkillSlot)
		self.main["skill"].SetSelectItemSlotEvent(self.__ClickSkillSlot)

		self.Refresh()

	def Destroy(self):
		self.Close()

		self.main = None
		self.itemToolTip = None
		self.skillToolTip = None
		self.textToolTip = None

		ui.ScriptWindow.Destroy(self)

	def Open(self, isPreview = False):
		if not isPreview and not pet.IsSummoned():
			return

		if isPreview:
			self.main["Background"].LoadImage("d:/ymir work/ui/pet/bg-preview.png")

		self.isPreview = isPreview
		self.SetTop()
		self.Show()
		self.Refresh()

	def Close(self):
		self.Hide()

		self.skillToolTip.Hide()
		self.itemToolTip.Hide()
		self.textToolTip.Hide()

	def OnUpdate(self):
		if self.textToolTip.IsShow() and self.textToolTip.updateFunc:
			self.textToolTip.updateFunc()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	## OLD bug 4: OLD passed the preview flag as GetEvolveLevelIndex's
	## skip_level, and compared with the own pet's level.
	def __CanEvolve(self):
		idx = GetEvolveLevelIndex(-1, self.isPreview)
		return pet.GetEvolveProtoLevel(idx + 1) == pet.GetLevel(self.isPreview)

	def __HasNextEvolve(self):
		idx = GetEvolveLevelIndex(-1, self.isPreview)
		return pet.GetEvolveProtoLevel(idx + 1) != -1

	def Refresh(self):
		self.RefreshStatus()
		self.RefreshSkillSlot()

	def RefreshStatus(self):
		if not self.isPreview and not pet.IsSummoned():
			return

		## OLD's portraits are animated GIFs; NEW's client loads no GIF
		## (ScriptLib/Resource.cpp: sub, dds, jpg, tga, bmp, png), so they
		## ship as PNGs of their first frame.
		ROOT_PATH = "d:/ymir work/ui/pet/panel_info/icon_pets/{}.png"

		self.main["PetName"].SetText(LabelText(localeInfo.PET_INFO_NAME, pet.GetName(self.isPreview)))

		self.main["PetImage"].LoadImage(ROOT_PATH.format(pet.GetItemVnum(self.isPreview)))

		self.main["PetLevel"].SetText(LabelText(localeInfo.PET_INFO_LEVEL, "(%d)" % pet.GetLevel(self.isPreview)))

		self.main["PetEvolution"].SetText(LabelText(localeInfo.PET_INFO_EVOLUTION, GetEvolveLocaleName(pet.GetEvolveProtoName(GetEvolveLevel(-1, self.isPreview)))))
		self.main["PetEvolution"].SetPackedFontColor(GetEvolveColor(GetEvolveLevelIndex(-1, self.isPreview)))

		for i in range(pet.ATTR_MAX_NUM):
			if pet.GetAttrType(i, self.isPreview) != 0:
				attrName, percentBonus = GetAffectName(pet.GetAttrType(i, self.isPreview))
				self.main["bonus"][i]["name"].SetText(attrName)
				self.main["bonus"][i]["level"].SetText("Lv." + str(pet.GetAttrLevel(i, self.isPreview)) + " - " + str(pet.GetAttrValue(i, self.isPreview)) + ("%" if percentBonus else ""))
			if pet.GetAttrCanUpgrade(i, self.isPreview):
				self.main["bonus"][i]["plus"].Show()
			else:
				self.main["bonus"][i]["plus"].Hide()

		self.RefreshExp(pet.GetExp(self.isPreview), pet.GetNextExp(self.isPreview))

		if not self.__HasNextEvolve():
			self.main["evolution_upgrade"].Hide()
		else:
			self.main["evolution_upgrade"].Show()
			if self.__CanEvolve():
				self.main["evolution_upgrade"].Enable()
				self.main["evolution_upgrade"].Flash()
			else:
				self.main["evolution_upgrade"].Disable()

		## The shown text tooltip follows a change at once (OLD re-ran it
		## every frame in OnUpdate).
		if self.textToolTip.IsShow() and self.textToolTip.updateFunc:
			self.textToolTip.updateFunc()

	def RefreshExp(self, curPoint, maxPoint):
		curPoint = min(curPoint, maxPoint)
		curPoint = max(curPoint, 0)
		maxPoint = max(maxPoint, 0)

		if int(maxPoint) == 0:
			self.main["PetExpBar"].SetPercentage(0.0, 1.0)
			return

		self.main["PetExpBar"].SetPercentage(min(float(curPoint), float(maxPoint)), float(maxPoint))

	def RefreshDisabledSkillSlot(self, start_idx, end_idx, enabled_count):
		for i in range(start_idx, end_idx):
			idx = i - start_idx
			if idx < enabled_count:
				self.main["skill_disabled"][i].Hide()
			else:
				self.main["skill_disabled"][i].Show()

	def RefreshSkillSlot(self):
		self.RefreshDisabledSkillSlot(pet.SKILL_NORMAL_START, pet.SKILL_HEROIC_START, pet.GetEvolveProtoNormalSkillCount(GetEvolveLevel(-1, self.isPreview)))
		self.RefreshDisabledSkillSlot(pet.SKILL_HEROIC_START, pet.SKILL_MAX_NUM, pet.GetHeroicProtoPassiveSkillCount(GetEvolveLevel(-1, self.isPreview)))

		for i in range(pet.SKILL_MAX_NUM):
			vnum = pet.GetSkillID(i, self.isPreview)
			level = pet.GetSkillLevel(i, self.isPreview)
			if vnum == 0:
				self.main["skill"].ClearSlot(i)
				continue

			self.main["skill"].SetPetSkillSlot(i, vnum, level)

		self.main["skill"].RefreshSlot()

	def __OnClickAttr(self, func):
		func()

	def __ShowTextToolTip(self, func):
		func()
		self.textToolTip.updateFunc = func
		self.textToolTip.Show()

	def __OverInExp(self):
		## OLD bug 4: OLD read the own pet's exp in the preview window too.
		exp = pet.GetExp(self.isPreview)
		max_exp = pet.GetNextExp(self.isPreview)
		if max_exp == 0:
			max_exp = 1
		pct = exp * 100.0 / max_exp
		if pct > 100.0:
			pct = 100.0

		self.textToolTip.SetText(localeInfo.TARGET_INFO_EXP % ("%.2f%%" % pct))

	def __ClickAttr(self, bonus_index):
		pet.RequestAttrRefineInfo(bonus_index)

	def __OverInBonus(self, bonus_index):
		attr_type = pet.GetAttrType(bonus_index, self.isPreview)
		attr_value = pet.GetAttrValue(bonus_index, self.isPreview)
		attr_level = pet.GetAttrLevel(bonus_index, self.isPreview)

		if attr_type == 0 or attr_value == 0:
			return

		self.textToolTip.SetText(localeInfo.TOOLTIP_PET_ATTR_INFO % (attr_level, GetAffectText(attr_type, attr_value)))

	def __OverInSkillSlot(self, slotIndex):
		self.skillToolTip.SetSkill(pet.GetSkillID(slotIndex, self.isPreview), pet.GetSkillLevel(slotIndex, self.isPreview), self.isPreview)

	def __OverOutSkillSlot(self):
		self.skillToolTip.HideToolTip()

	def __ClickSkillSlot(self, slotIndex):
		ClickSkillSlot(slotIndex)

	## OLD bug 3: OLD's skill use called a cooldown getter and a use call
	## that no module has; nothing called it. Removed.


class PetAttrRefineWindow(ui.ScriptWindow):

	MATERIAL_SIZE = 36
	MATERIAL_SPACE = 7

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self._popupDlg = uiCommon.PopupDialog()
		self._popupDlg.Close()

		self._materials = []
		self.index = 0
		self.nextValue = 0

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			ui.PythonScriptLoader().LoadScriptFile(self, "UIScript/PetRefineAttrWindow.py")
		except:
			import exception
			exception.Abort("PetWindow.LoadScript")

		try:
			self.main = {
				"title" : self.GetChild("TitleBar"),
				"attribute" : self.GetChild("attr_txt"),
				"current" : {
					"value" : self.GetChild("attr_bonus_current"),
					"level" : self.GetChild("level_current"),
				},
				"next" : {
					"value" : self.GetChild("attr_bonus_next"),
					"level" : self.GetChild("level_next"),
				},
				"material" : self.GetChild("material_window"),
				"cost" : self.GetChild("cost"),
				"upgrade" : self.GetChild("upgrade"),
				"cancel" : self.GetChild("cancel"),
			}

		except:
			import exception
			exception.Abort("PetWindow.BindObject")

		itemToolTip = uiToolTip.ItemToolTip()
		itemToolTip.HideToolTip()
		self._itemToolTip = itemToolTip

		self.main["title"].SetCloseEvent(ui.__mem_func__(self.Close))

		self.main["upgrade"].SAFE_SetEvent(self.__OnClickUpgrade)
		self.main["cancel"].SAFE_SetEvent(self.Close)

	def Destroy(self):
		self.Close()

		self.main = None
		self._popupDlg = None
		self._itemToolTip = None
		self._materials = None

		ui.ScriptWindow.Destroy(self)

	def Open(self, index, nextValue):
		self.index = index
		self.nextValue = nextValue
		self.Refresh()
		if not self.IsShow():
			self.SetCenterPosition()
			self.SetTop()
			self.Show()

	def Close(self):
		self.Hide()

		self._popupDlg.Close()
		self._itemToolTip.HideToolTip()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def __MakeMaterial(self, index):
		mat_vnum, mat_count = pet.GetAttrRefineMaterial(index)
		item.SelectItem(mat_vnum)

		mat_item = ui.ImageBox()
		mat_item.SetParent(self.main["material"])
		mat_item.LoadImage(item.GetIconImageFileName())
		SetStringEvent(mat_item, "MOUSE_OVER_IN", lambda arg=mat_vnum: self._itemToolTip.SetItemToolTip(arg))
		SetStringEvent(mat_item, "MOUSE_OVER_OUT", lambda: self._itemToolTip.HideToolTip())
		mat_item.Show()

		mat_xcount = ui.NumberLine()
		mat_xcount.SetParent(mat_item)
		mat_xcount.SetPosition(3, 9)
		mat_xcount.SetHorizontalAlignRight()
		mat_xcount.SetWindowHorizontalAlignRight()
		mat_xcount.SetWindowVerticalAlignBottom()
		mat_xcount.SetNumber(str(mat_count))
		mat_xcount.Show()

		mat_item.count = mat_xcount

		return mat_item

	def RefreshProto(self):
		attrName, percentBonus = GetAffectName(pet.GetAttrType(self.index))
		self.main["attribute"].SetText(attrName)

		self.main["current"]["level"].SetText("Lv. " + str(pet.GetAttrLevel(self.index)))
		self.main["current"]["value"].SetText(str(pet.GetAttrValue(self.index)) + ("%" if percentBonus else ""))

		self.main["next"]["level"].SetText("Lv. " + str(pet.GetAttrLevel(self.index) + 1))
		self.main["next"]["value"].SetText(str(self.nextValue) + ("%" if percentBonus else ""))

	def RefreshRequirements(self):
		self._materials = []

		matCount = pet.GetAttrRefineMaterialCount()
		matWidth = self.MATERIAL_SIZE * matCount + self.MATERIAL_SPACE * (matCount - 1)
		xpos = (self.main["material"].GetWidth() - matWidth) // 2

		for i in range(matCount):
			mat = self.__MakeMaterial(pet.GetAttrRefineMaterialCount() - 1 - i)
			self._materials.append(mat)

			mat.SetPosition(xpos, 12)
			xpos += self.MATERIAL_SIZE + self.MATERIAL_SPACE

		self.main["cost"].SetText(localeInfo.PET_EVOLVE_PRICE % localeInfo.NumberToMoneyString(pet.GetAttrRefineCost()))

	def Refresh(self):
		if self.IsShow() and pet.GetAttrLevel(self.index) >= PET_ATTR_MAX_LEVEL:
			self.Close()
			return
		self.RefreshProto()
		self.RefreshRequirements()

	def __ShowPopup(self, text):
		self._popupDlg.SetText(text)
		self._popupDlg.Open()

	def __OnClickUpgrade(self):
		if player.GetMoney() < pet.GetAttrRefineCost():
			self.__ShowPopup(localeInfo.PET_EVOLVE_ERROR_NOT_ENOUGH_GOLD)
			return

		for i in range(pet.GetAttrRefineMaterialCount()):
			mat_vnum, mat_count = pet.GetAttrRefineMaterial(i)
			inven_count = player.GetItemCountByVnum(mat_vnum)
			if inven_count < mat_count:
				item.SelectItem(mat_vnum)
				self.__ShowPopup(localeInfo.PET_EVOLVE_ERROR_NOT_ENOUGH_ITEM % (mat_count - inven_count, item.GetItemName()))
				return

		pet.RefineAttr(self.index)

	## OLD's refine result texts: nothing calls these in OLD either (the
	## server answers an upgrade with a new ATTR_REFINE_INFO, which refreshes
	## this window, or closes it at the top level). Kept for the NovaUI side.
	def OnRefineAttrFailure(self):
		self.__ShowPopup(localeInfo.PET_ATTR_REFINE_FAILURE)

	def OnEvolveSuccess(self):
		self.Close()
		self.__ShowPopup(localeInfo.PET_ATTR_REFINE_SUCCESS)
