import app
import net
import player
import item
import ui
import uiToolTip
import mouseModule
import localeInfo
import uiCommon
import constInfo

## NOVA-198, fast upgrade (OLD uiRefine.py:262-277, 636-675, game.py:3315-3321):
## a refine from +8 makes +9 and ends the chain (the grade is the vnum's last
## digit: the client's Python reads no refine level or next grade).
FAST_REFINE_STOP_GRADE = 9
## The refine types the server opens the dialog with when the item was given
## to a blacksmith (REFINE_TYPE_NORMAL, REFINE_TYPE_MONEY_ONLY); a scroll
## opens it with any other.
FAST_REFINE_NPC_TYPES = (0, 4)

class FastRefine(object):
	"""The fast upgrade box's state (kept for the session) and the request
	that opened the refine dialog, to send again after a success.

	The request is a scroll used on the item (uiinventory.RefineItem records
	it with itself as the sender, so its private shop guard and CanRefine
	still apply) or the item given to a blacksmith (game.py). The server's
	answer opens the dialog (OnOpen); Accept sends the refine packet as
	always (OnAccept); on RefineSuceeded with the box checked the request
	goes again (SendAgain) and the server answers with the next step, which
	needs its own Accept. Anything else forgets the request: a failure, +9, a
	scroll gone, a cancel or close, a dialog opened for another item."""

	SCROLL = "scroll"
	NPC = "npc"

	## The request's state: sent, waiting for the dialog; the dialog shows
	## it; accepted, waiting for the result.
	REQUESTED, OPEN, AWAITING = list(range(3))

	def __init__(self):
		self.enabled = False
		self.Forget()

	def Forget(self):
		self.kind = None
		self.state = None
		self.target = -1
		self.targetVnum = 0
		self.scroll = None	# (cell, vnum)
		self.npc = None		# (vid, window, cell, count)
		self.send = None

	def RecordScroll(self, scrollPos, scrollVnum, targetPos, send):
		self.Forget()
		self.kind = self.SCROLL
		self.scroll = (scrollPos, scrollVnum)
		self.target = targetPos
		self.send = send
		self.state = self.REQUESTED

	def RecordNpc(self, vid, window, cell, count):
		self.Forget()
		## Only an inventory item refines (the server's RefineInformation).
		if window != player.INVENTORY:
			return

		self.kind = self.NPC
		self.npc = (vid, window, cell, count)
		self.target = cell
		self.state = self.REQUESTED

	def OnOpen(self, targetPos, type):
		viaNpc = type in FAST_REFINE_NPC_TYPES
		if self.state != self.REQUESTED or targetPos != self.target or viaNpc != (self.kind == self.NPC):
			self.Forget()
			return

		self.state = self.OPEN
		self.targetVnum = player.GetItemIndex(targetPos)

	def OnAccept(self):
		if self.state == self.OPEN:
			self.state = self.AWAITING

	def IsAwaiting(self):
		return self.state == self.AWAITING

	def CanGoOn(self):
		## RefineSuceeded comes before the item's cell is replaced: the cell
		## still holds the refined item, its old vnum.
		if player.GetItemIndex(self.target) != self.targetVnum:
			return False

		if self.targetVnum % 10 + 1 >= FAST_REFINE_STOP_GRADE:
			return False

		if self.kind == self.SCROLL:
			(scrollPos, scrollVnum) = self.scroll
			## The scroll's count is already lowered: the last one leaves the cell empty.
			if player.GetItemIndex(scrollPos) != scrollVnum or player.GetItemCount(scrollPos) <= 0:
				return False

		return True

	def SendAgain(self):
		kind, scroll, npc, target, send = self.kind, self.scroll, self.npc, self.target, self.send
		self.state = self.REQUESTED
		if kind == self.SCROLL:
			send(scroll[0], target)
		elif kind == self.NPC:
			net.SendGiveItemPacket(*npc)

FAST_REFINE = FastRefine()

class RefineDialog(ui.ScriptWindow):
	makeSocketSuccessPercentage = ( 100, 33, 20, 15, 10, 5, 0 )
	upgradeStoneSuccessPercentage = ( 30, 29, 28, 27, 26, 25, 24, 23, 22 )
	upgradeArmorSuccessPercentage = ( 99, 66, 33, 33, 33, 33, 33, 33, 33 )
	upgradeAccessorySuccessPercentage = ( 99, 88, 77, 66, 33, 33, 33, 33, 33 )
	upgradeSuccessPercentage = ( 99, 66, 33, 33, 33, 33, 33, 33, 33 )

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.__LoadScript()

		self.scrollItemPos = 0
		self.targetItemPos = 0

	def __LoadScript(self):

		self.__LoadQuestionDialog()

		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "uiscript/refinedialog.py")

		except:
			import exception
			exception.Abort("RefineDialog.__LoadScript.LoadObject")

		try:
			self.board = self.GetChild("Board")
			self.titleBar = self.GetChild("TitleBar")
			self.successPercentage = self.GetChild("SuccessPercentage")
			self.GetChild("AcceptButton").SetEvent(self.OpenQuestionDialog)
			self.GetChild("CancelButton").SetEvent(self.Close)
		except:
			import exception
			exception.Abort("RefineDialog.__LoadScript.BindObject")

		self.successPercentage.Hide()

		toolTip = uiToolTip.ItemToolTip()
		toolTip.SetParent(self)
		toolTip.SetPosition(15, 38)
		toolTip.SetFollow(False)
		toolTip.Show()
		self.toolTip = toolTip

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadQuestionDialog(self):
		self.dlgQuestion = ui.ScriptWindow()

		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self.dlgQuestion, "uiscript/questiondialog2.py")
		except:
			import exception
			exception.Abort("RefineDialog.__LoadQuestionDialog.LoadScript")

		try:
			GetObject=self.dlgQuestion.GetChild
			GetObject("message1").SetText(localeInfo.REFINE_DESTROY_WARNING)
			GetObject("message2").SetText(localeInfo.REFINE_WARNING2)
			GetObject("accept").SetEvent(ui.__mem_func__(self.Accept))
			GetObject("cancel").SetEvent(ui.__mem_func__(self.dlgQuestion.Hide))
		except:
			import exception
			exception.Abort("SelectCharacterWindow.__LoadQuestionDialog.BindObject")

	def Destroy(self):
		self.ClearDictionary()
		self.board = 0
		self.successPercentage = 0
		self.titleBar = 0
		self.toolTip = 0
		self.dlgQuestion = 0

	def GetRefineSuccessPercentage(self, scrollSlotIndex, itemSlotIndex):
		if -1 != scrollSlotIndex:
			if player.IsRefineGradeScroll(scrollSlotIndex):
				curGrade = player.GetItemGrade(itemSlotIndex)
				itemIndex = player.GetItemIndex(itemSlotIndex)

				item.SelectItem(itemIndex)

				itemType = item.GetItemType()
				itemSubType = item.GetItemSubType()

				if item.ITEM_TYPE_METIN == itemType:
					if curGrade >= len(self.upgradeStoneSuccessPercentage):
						return 0
					return self.upgradeStoneSuccessPercentage[curGrade]
				elif item.ITEM_TYPE_ARMOR == itemType:
					if item.ARMOR_BODY == itemSubType:
						if curGrade >= len(self.upgradeArmorSuccessPercentage):
							return 0
						return self.upgradeArmorSuccessPercentage[curGrade]
					else:
						if curGrade >= len(self.upgradeAccessorySuccessPercentage):
							return 0
						return self.upgradeAccessorySuccessPercentage[curGrade]
				else:
					if curGrade >= len(self.upgradeSuccessPercentage):
						return 0

					return self.upgradeSuccessPercentage[curGrade]

		for i in range(player.METIN_SOCKET_MAX_NUM+1):
			if 0 == player.GetItemMetinSocket(itemSlotIndex, i):
				break

		return self.makeSocketSuccessPercentage[i]

	def Open(self, scrollItemPos, targetItemPos):
		self.scrollItemPos = scrollItemPos
		self.targetItemPos = targetItemPos

		percentage = self.GetRefineSuccessPercentage(scrollItemPos, targetItemPos)

		if 0 == percentage:
			return

		self.successPercentage.SetText(localeInfo.REFINE_SUCCESS_PROBALITY % (percentage))

		itemIndex = player.GetItemIndex(targetItemPos)
		self.toolTip.ClearToolTip()
		metinSlot = []

		for i in range(player.METIN_SOCKET_MAX_NUM):
			metinSlot.append(player.GetItemMetinSocket(targetItemPos, i))

		self.toolTip.AddItemData(itemIndex, metinSlot)

		self.UpdateDialog()
		self.SetTop()
		self.Show()

	def UpdateDialog(self):
		newWidth = self.toolTip.GetWidth() + 30
		# MR-15: Adjust button padding for refine window
		newHeight = self.toolTip.GetHeight() + 108
		# MR-15: -- END OF -- Adjust button padding for refine window

		self.board.SetSize(newWidth, newHeight)
		# MR-15: Adjust button padding for refine window
		self.titleBar.SetWidth(newWidth - 15)
		# MR-15: -- END OF -- Adjust button padding for refine window
		self.SetSize(newWidth, newHeight)

		(x, y) = self.GetLocalPosition()

		self.SetPosition(x, y)

	def OpenQuestionDialog(self):
		percentage = self.GetRefineSuccessPercentage(-1, self.targetItemPos)

		if 100 == percentage:
			self.Accept()

			return

		self.dlgQuestion.SetTop()
		self.dlgQuestion.Show()

	def Accept(self):
		net.SendItemUseToItemPacket(self.scrollItemPos, self.targetItemPos)
		self.Close()

	def Close(self):
		self.dlgQuestion.Hide()
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

class RefineDialogNew(ui.ScriptWindow):

	## NOVA-198: the fast upgrade box's row, between the materials and the
	## cost (whose bottom-aligned y is 64): the board grows by it.
	FAST_REFINE_ROW = 20
	FAST_REFINE_Y = 84

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.__Initialize()
		self.isLoaded = False
		self.wndInventory = None
		self.wndExtraInventory = None
		# [(window, cell)]: the refined item's cell while the dialog shows.
		self.lockedItems = []

	def __Initialize(self):
		self.dlgQuestion = None
		self.children = []
		self.vnum = 0
		self.targetItemPos = 0
		self.dialogHeight = 0
		self.cost = 0
		self.percentage = 0
		self.type = 0

	def __LoadScript(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "uiscript/refinedialog.py")
		except:
			import exception
			exception.Abort("RefineDialog.__LoadScript.LoadObject")

		try:
			self.board = self.GetChild("Board")
			self.titleBar = self.GetChild("TitleBar")
			self.probText = self.GetChild("SuccessPercentage")
			self.costText = self.GetChild("Cost")
			self.successPercentage = self.GetChild("SuccessPercentage")
			self.GetChild("AcceptButton").SetEvent(self.OpenQuestionDialog)
			self.GetChild("CancelButton").SetEvent(self.CancelRefine)
		except:
			import exception
			exception.Abort("RefineDialog.__LoadScript.BindObject")

		self.successPercentage.Hide()

		toolTip = uiToolTip.ItemToolTip()
		toolTip.SetParent(self)
		toolTip.SetFollow(False)
		toolTip.SetPosition(15, 38)
		toolTip.Show()
		self.toolTip = toolTip

		self.slotList = []

		for i in range(3):
			slot = self.__MakeSlot()

			slot.SetParent(toolTip)
			slot.SetWindowVerticalAlignCenter()
			self.slotList.append(slot)

		itemImage = self.__MakeItemImage()
		itemImage.SetParent(toolTip)
		itemImage.SetWindowVerticalAlignCenter()
		itemImage.SetPosition(-35, 0)
		self.itemImage = itemImage

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.CancelRefine))

		## NOVA-198: the fast upgrade box, centered above the cost (OLD put it
		## at the bottom; UpdateDialog makes its row).
		checkBox = ui.CheckBox()
		checkBox.SetParent(self)
		checkBox.SetTextInfo(localeInfo.REFINE_FAST_UPGRADE)
		checkBox.SetPosition(0, self.FAST_REFINE_Y)
		checkBox.SetWindowHorizontalAlignCenter()
		checkBox.SetWindowVerticalAlignBottom()
		checkBox.SetEvent(ui.__mem_func__(self.OnToggleFastRefine), "ON_CHECK")
		checkBox.SetEvent(ui.__mem_func__(self.OnToggleFastRefine), "ON_UNCHECK")
		checkBox.Show()
		self.fastRefineCheck = checkBox

		self.isLoaded = True

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __MakeSlot(self):
		slot = ui.ImageBox()

		slot.LoadImage("d:/ymir work/ui/public/slot_base.sub")
		slot.Show()
		self.children.append(slot)

		return slot

	def __MakeItemImage(self):
		itemImage = ui.ImageBox()

		itemImage.Show()
		self.children.append(itemImage)

		return itemImage

	def __MakeThinBoard(self):
		thinBoard = ui.ThinBoard()

		thinBoard.SetParent(self)
		thinBoard.Show()
		self.children.append(thinBoard)

		return thinBoard

	def Destroy(self):
		self.ClearDictionary()

		self.dlgQuestion = None
		self.board = 0
		self.probText = 0
		self.costText = 0
		self.titleBar = 0
		self.toolTip = 0
		self.successPercentage = None
		self.slotList = []
		self.children = []
		self.fastRefineCheck = None
		FAST_REFINE.Forget()

	def Open(self, targetItemPos, nextGradeItemVnum, cost, prob, type):
		if False == self.isLoaded:
			self.__LoadScript()

		self.__Initialize()

		self.targetItemPos = targetItemPos
		self.vnum = nextGradeItemVnum
		self.cost = cost
		self.percentage = prob
		self.type = type

		self.probText.SetText(localeInfo.REFINE_SUCCESS_PROBALITY % (self.percentage))
		self.costText.SetText(localeInfo.REFINE_COST % (self.cost))

		self.toolTip.ClearToolTip()
		metinSlot = []

		for i in range(player.METIN_SOCKET_MAX_NUM):
			metinSlot.append(player.GetItemMetinSocket(targetItemPos, i))

		attrSlot = []

		for i in range(player.ATTRIBUTE_SLOT_MAX_NUM):
			attrSlot.append(player.GetItemAttribute(targetItemPos, i))

		self.toolTip.AddRefineItemData(nextGradeItemVnum, metinSlot, attrSlot)

		item.SelectItem(nextGradeItemVnum)
		self.itemImage.LoadImage(item.GetIconImageFileName())
		xSlotCount, ySlotCount = item.GetItemSize()

		for slot in self.slotList:
			slot.Hide()

		for i in range(min(3, ySlotCount)):
			self.slotList[i].SetPosition(-35, i * 32 - (ySlotCount - 1) * 16)
			self.slotList[i].Show()

		self.dialogHeight = self.toolTip.GetHeight() + 46
		self.UpdateDialog()

		FAST_REFINE.OnOpen(targetItemPos, type)
		self.fastRefineCheck.SetCheckStatus(FAST_REFINE.enabled)

		self.SetTop()
		self.Show()

		self.__LockCells((player.INVENTORY, targetItemPos))

	def Close(self):
		# MR-15: Multiline dialog messages
		if self.dlgQuestion:
			self.dlgQuestion.Hide()
		# MR-15: -- END OF -- Multiline dialog messages

		self.dlgQuestion = None
		self.Hide()

		self.__ReleaseCells()

		## An accepted step keeps its request for the result; any other close forgets it.
		if not FAST_REFINE.IsAwaiting():
			FAST_REFINE.Forget()

	## NOVA-198: the fast upgrade box's state, kept for the session.
	def OnToggleFastRefine(self):
		FAST_REFINE.enabled = self.fastRefineCheck.GetCheckStatus()

	## NOVA-198: RefineSuceeded or RefineFailed (game.py, through the
	## Interface). Without an accepted fast upgrade step it does nothing, as
	## before; with one, a success with the box checked sends the request
	## again, and anything else ends the chain.
	def OnRefineResult(self, succeeded):
		if not FAST_REFINE.IsAwaiting():
			return

		if succeeded and FAST_REFINE.enabled and FAST_REFINE.CanGoOn():
			FAST_REFINE.SendAgain()
			return

		FAST_REFINE.Forget()
		if self.IsShow():
			self.Close()

	## The tradable icon (NOVA-13; OLD uiRefine.py:437-438, 556-558, 679-705): the cells of the items the
	## dialog works on take no mouse event while it shows.
	def SetInven(self, wndInventory, wndExtraInventory=None):
		self.wndInventory = wndInventory
		self.wndExtraInventory = wndExtraInventory

	def __InventoryWindowOf(self, window):
		if window == player.INVENTORY:
			return self.wndInventory
		if window == player.EXTRA_INVENTORY:
			return self.wndExtraInventory
		return None

	def __LockCells(self, *cells):
		self.__ReleaseCells()
		self.lockedItems = list(cells)
		self.RefreshLockedSlot()

	def __ReleaseCells(self):
		cells, self.lockedItems = self.lockedItems, []
		for (window, cell) in cells:
			wnd = self.__InventoryWindowOf(window)
			if wnd:
				wnd.SetCanMouseEventCell(cell)

	def RefreshLockedSlot(self):
		for (window, cell) in self.lockedItems:
			wnd = self.__InventoryWindowOf(window)
			if wnd:
				wnd.SetCantMouseEventCell(cell)

	def AppendMaterial(self, vnum, count):
		slot = self.__MakeSlot()

		slot.SetParent(self)
		slot.SetPosition(15, self.dialogHeight)

		itemImage = self.__MakeItemImage()

		itemImage.SetParent(slot)
		item.SelectItem(vnum)
		itemImage.LoadImage(item.GetIconImageFileName())

		thinBoard = self.__MakeThinBoard()

		thinBoard.SetPosition(50, self.dialogHeight)
		thinBoard.SetSize(self.toolTip.GetWidth(), 20)

		textLine = ui.TextLine()

		textLine.SetParent(thinBoard)
		textLine.SetFontName(localeInfo.UI_DEF_FONT)
		textLine.SetPackedFontColor(0xffdddddd)
		textLine.SetText("%s x %02d" % (item.GetItemName(), count))
		textLine.SetOutline()
		textLine.SetFeather(False)
		textLine.SetWindowVerticalAlignCenter()
		textLine.SetVerticalAlignCenter()

		if app.IsRTL():
			(x,y) = textLine.GetTextSize()
			textLine.SetPosition(x, 0)
		else:
			textLine.SetPosition(15, 0)

		textLine.Show()
		self.children.append(textLine)

		self.dialogHeight += 34
		self.UpdateDialog()

	def UpdateDialog(self):
		newWidth = self.toolTip.GetWidth() + 60
		# MR-15: Adjust button padding for refine window
		newHeight = self.dialogHeight + 79
		# MR-15: -- END OF -- Adjust button padding for refine window

		newHeight -= 8
		newHeight += self.FAST_REFINE_ROW

		if app.IsRTL():
			self.board.SetPosition(newWidth, 0)

			(x, y) = self.titleBar.GetLocalPosition()
			self.titleBar.SetPosition(newWidth - 15, y)

		self.board.SetSize(newWidth, newHeight)
		self.toolTip.SetPosition(15 + 35, 38)
		self.titleBar.SetWidth(newWidth - 15)
		self.SetSize(newWidth, newHeight)

		(x, y) = self.GetLocalPosition()
		self.SetPosition(x, y)

	def OpenQuestionDialog(self):

		if 100 == self.percentage:
			self.Accept()
			return

		if 5 == self.type: ## ������ �ູ��
			self.Accept()
			return

		dlgQuestion = uiCommon.QuestionDialog2()
		dlgQuestion.SetText2(localeInfo.REFINE_WARNING2)
		dlgQuestion.SetAcceptEvent(ui.__mem_func__(self.Accept))
		dlgQuestion.SetCancelEvent(ui.__mem_func__(dlgQuestion.Close))

		if 3 == self.type: ## ��ö
			dlgQuestion.SetText1(localeInfo.REFINE_DESTROY_WARNING_WITH_BONUS_PERCENT_1)
			# MR-15: Update refining messages
			dlgQuestion.SetText2(localeInfo.REFINE_POPUP_NO_DOWNGRADE_MESSAGE)
			# MR-15: -- END OF -- Update refining messages
		elif 2 == self.type: ## �ູ��
			dlgQuestion.SetText1(localeInfo.REFINE_DOWN_GRADE_WARNING)
		else:
			dlgQuestion.SetText1(localeInfo.REFINE_DESTROY_WARNING)

		dlgQuestion.Open()
		self.dlgQuestion = dlgQuestion

	def Accept(self):
		net.SendRefinePacket(self.targetItemPos, self.type)
		FAST_REFINE.OnAccept()
		self.Close()

	def CancelRefine(self):
		net.SendRefinePacket(255, 255)
		self.Close()

	def OnPressEscapeKey(self):
		self.CancelRefine()
		return True
