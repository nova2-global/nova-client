import ui
import uiScriptLocale
import wndMgr
import player
import miniMap
import localeInfo
import net
import app
import colorInfo
import constInfo
import background
import player_options

# NOVA-129: the boss and metin stone marks' hover lines, from the locale.
# miniMap.SetAtlasMarkTexts takes them once per atlas window (this one and
# nui_atlas.AtlasWindow); an exe without it (before protocol 10) is skipped.
def AtlasMarkTexts():
	return {
		"boss": localeInfo.ATLAS_MARK_BOSS,
		"king": localeInfo.ATLAS_MARK_KING,
		"stone": localeInfo.ATLAS_MARK_STONE,
		"level": localeInfo.BOSS_INFO_LEVEL,
		"alive": localeInfo.BOSS_INFO_ALIVE,
		"dead": localeInfo.BOSS_INFO_DEAD,
		"respawn_in": localeInfo.BOSS_INFO_RESPAWN,
		"period": localeInfo.ATLAS_MARK_RESPAWN_TIME,
		# NOVA-206: the press hint, which C++ appends as the last line once
		# its HoverDetail reads this key (an older exe ignores it).
		"wiki": localeInfo.ATLAS_MARK_WIKI_HINT,
	}

def SetAtlasMarkTexts():
	setter = getattr(miniMap, "SetAtlasMarkTexts", None)
	if setter:
		setter(AtlasMarkTexts())

# The lines a boss or stone mark the last GetAtlasInfo hit adds under its
# name line ("" for anything else, or an exe without marks).
def AtlasMarkHover():
	getter = getattr(miniMap, "GetAtlasMarkHover", None)
	if not getter:
		return ""
	return getter()

# NOVA-206 (OLD uiMiniMap.py:167-205): the vnum of the boss or metin stone
# mark at an atlas point, 0 for anything else. GetAtlasInfo hits the mark (and
# sets the one GetAtlasMarkHover answers for); its place, divided by 100 as
# GetAtlasInfo hands it over, finds the mark in miniMap.GetAtlasMarks.
# OLD looked the vnum up by the mob's name; the place is the mark's own.
def AtlasMarkVnumAt(x, y):
	getMarks = getattr(miniMap, "GetAtlasMarks", None)
	if not getMarks:
		return 0
	info = miniMap.GetAtlasInfo(x, y)
	if not info[0] or not AtlasMarkHover():
		return 0
	(cellX, cellY) = (info[2], info[3])
	for mark in getMarks():
		(vnum, markX, markY) = (mark[5], mark[6], mark[7])
		if int(markX) // 100 == cellX and int(markY) // 100 == cellY:
			return vnum
	return 0

# The hover's last line on a mark while a press opens its page: legacy's
# own, unless C++ already ended the mark's lines with it.
def WithWikiHint(detail):
	hint = localeInfo.ATLAS_MARK_WIKI_HINT
	if not detail or detail.split("\n")[-1] == hint:
		return detail
	return detail + "\n" + hint

class MapTextToolTip(ui.Window):
	# NOVA-129: a boss or stone mark's hover has several lines ("\n"), each
	# a text line of its own LINE_HEIGHT below the one before.
	LINE_HEIGHT = 16

	def __init__(self):
		ui.Window.__init__(self)

		self.textLine = self.__MakeLine()
		self.extraLines = []
		self.lineCount = 1

	def __del__(self):
		ui.Window.__del__(self)

	def __MakeLine(self):
		textLine = ui.TextLine()
		textLine.SetParent(self)
		textLine.SetHorizontalAlignCenter()
		textLine.SetOutline()
		textLine.SetHorizontalAlignRight()
		textLine.Show()
		return textLine

	def __Lines(self):
		return [self.textLine] + self.extraLines[:self.lineCount - 1]

	def SetText(self, text):
		lines = text.split("\n")
		self.textLine.SetText(lines[0])
		while len(self.extraLines) < len(lines) - 1:
			self.extraLines.append(self.__MakeLine())
		for i, line in enumerate(self.extraLines):
			if i + 1 < len(lines):
				line.SetText(lines[i + 1])
				line.Show()
			else:
				line.Hide()
		self.lineCount = len(lines)

	def SetTooltipPosition(self, PosX, PosY):
		for i, line in enumerate(self.__Lines()):
			y = PosY + i * self.LINE_HEIGHT
			if app.IsRTL():
				w, h = line.GetTextSize()
				line.SetPosition(PosX - w - 5, y)
			else:
				line.SetPosition(PosX - 5, y)

	def SetTextColor(self, TextColor):
		for line in [self.textLine] + self.extraLines:
			line.SetPackedFontColor(TextColor)

	def GetTextSize(self):
		return self.textLine.GetTextSize()

class AtlasWindow(ui.ScriptWindow):

	class AtlasRenderer(ui.Window):
		def __init__(self):
			ui.Window.__init__(self)
			self.AddFlag("not_pick")

		def OnUpdate(self):
			miniMap.UpdateAtlas()

		def OnRender(self):
			(x, y) = self.GetGlobalPosition()
			fx = float(x)
			fy = float(y)
			miniMap.RenderAtlas(fx, fy)

		def HideAtlas(self):
			miniMap.HideAtlas()

		def ShowAtlas(self):
			miniMap.ShowAtlas()

	def __init__(self):
		self.tooltipInfo = MapTextToolTip()
		self.tooltipInfo.Hide()
		self.infoGuildMark = ui.MarkBox()
		self.infoGuildMark.Hide()
		self.AtlasMainWindow = None
		self.mapName = ""
		self.board = 0
		self.openWikiMobEvent = None

		ui.ScriptWindow.__init__(self)

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def SetMapName(self, mapName):
		# A map the dict has no name for keeps the title it has, as OLD's
		# try/except did, so that MiniMap.SetMapName still shows or hides
		# the minimap.
		mapTitle = localeInfo.MINIMAP_ZONE_NAME_DICT.get(mapName)
		if mapTitle is not None:
			self.board.SetTitleName(mapTitle)

	def LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/AtlasWindow.py")
		except:
			import exception
			exception.Abort("AtlasWindow.LoadWindow.LoadScript")

		try:
			self.board = self.GetChild("board")

		except:
			import exception
			exception.Abort("AtlasWindow.LoadWindow.BindObject")

		self.AtlasMainWindow = self.AtlasRenderer()
		self.board.SetCloseEvent(self.Hide)
		# NOVA-206: a left click on a boss or stone mark opens its wiki page
		# (the release, as legacy's buttons click).
		self.board.SetOnMouseLeftButtonUpEvent(ui.__mem_func__(self.OnAtlasPress))
		self.AtlasMainWindow.SetParent(self.board)
		self.AtlasMainWindow.SetPosition(7, 30)
		self.tooltipInfo.SetParent(self.board)
		self.infoGuildMark.SetParent(self.board)
		self.SetPosition(wndMgr.GetScreenWidth() - 136 - 256 - 10, 0)
		self.Hide()

		miniMap.RegisterAtlasWindow(self)
		SetAtlasMarkTexts()

	def Destroy(self):
		miniMap.UnregisterAtlasWindow()
		self.ClearDictionary()
		self.AtlasMainWindow = None
		self.tooltipAtlasClose = 0
		self.tooltipInfo = None
		self.infoGuildMark = None
		self.board = None
		self.openWikiMobEvent = None

	def OnUpdate(self):

		if not self.tooltipInfo:
			return

		if not self.infoGuildMark:
			return

		self.infoGuildMark.Hide()
		self.tooltipInfo.Hide()

		if False == self.board.IsIn():
			return

		(mouseX, mouseY) = wndMgr.GetMousePosition()
		(bFind, sName, iPosX, iPosY, dwTextColor, dwGuildID) = miniMap.GetAtlasInfo(mouseX, mouseY)

		if False == bFind:
			return

		if "empty_guild_area" == sName:
			sName = localeInfo.GUILD_EMPTY_AREA

		if app.IsRTL() and sName[-1].isalnum():
			text = "(%s)%d, %d" % (sName, iPosX, iPosY)
		else:
			text = "%s(%d, %d)" % (sName, iPosX, iPosY)
		# NOVA-129: a boss or stone mark's kind and level, state and respawn
		# time, under the name line.
		detail = AtlasMarkHover()
		if detail and self.openWikiMobEvent:
			detail = WithWikiHint(detail)
		if detail:
			text += "\n" + detail
		self.tooltipInfo.SetText(text)

		(x, y) = self.GetGlobalPosition()
		self.tooltipInfo.SetTooltipPosition(mouseX - x, mouseY - y)
		self.tooltipInfo.SetTextColor(dwTextColor)
		self.tooltipInfo.Show()
		self.tooltipInfo.SetTop()

		if 0 != dwGuildID:
			textWidth, textHeight = self.tooltipInfo.GetTextSize()
			self.infoGuildMark.SetIndex(dwGuildID)
			self.infoGuildMark.SetPosition(mouseX - x - textWidth - 18 - 5, mouseY - y)
			self.infoGuildMark.Show()

	## NOVA-206: the Interface's OpenWikiMob, through the minimap.
	def SetOpenWikiMobEvent(self, event):
		self.openWikiMobEvent = event

	def OnAtlasPress(self):
		if not self.openWikiMobEvent:
			return
		(mouseX, mouseY) = wndMgr.GetMousePosition()
		vnum = AtlasMarkVnumAt(mouseX, mouseY)
		if vnum:
			self.openWikiMobEvent(vnum)

	def Hide(self):
		if self.AtlasMainWindow:
			self.AtlasMainWindow.HideAtlas()
			self.AtlasMainWindow.Hide()
		ui.ScriptWindow.Hide(self)

	def Show(self):
		if self.AtlasMainWindow:
			(bGet, iSizeX, iSizeY) = miniMap.GetAtlasSize()
			if bGet:
				self.SetSize(iSizeX + 15, iSizeY + 38)

				if app.IsRTL():
					self.board.SetPosition(iSizeX+15, 0)

				self.board.SetSize(iSizeX + 15, iSizeY + 38)
				#self.AtlasMainWindow.SetSize(iSizeX, iSizeY)
				self.AtlasMainWindow.ShowAtlas()
				self.AtlasMainWindow.Show()
		ui.ScriptWindow.Show(self)

	def SetCenterPositionAdjust(self, x, y):
		self.SetPosition((wndMgr.GetScreenWidth() - self.GetWidth()) // 2 + x, (wndMgr.GetScreenHeight() - self.GetHeight()) // 2 + y)

	def OnPressEscapeKey(self):
		self.Hide()
		return True

def __RegisterMiniMapColor(type, rgb):
	miniMap.RegisterColor(type, rgb[0], rgb[1], rgb[2])

class MiniMap(ui.ScriptWindow):

	CANNOT_SEE_INFO_MAP_DICT = {
		"metin2_map_monkeydungeon" : False,
		"metin2_map_monkeydungeon_02" : False,
		"metin2_map_monkeydungeon_03" : False,
		"metin2_map_devilsCatacomb" : False,
	}

	# The FPS readout (NOVA-118): an outlined line centered at the hidden
	# position line's place (uiscript minimap.py), on the minimap itself so it
	# stays while the map is closed; OLD put it at W - 70, 164 (game.py:2384).
	FPS_LINE_POSITION = (70, 160)

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self.__Initialize()

		miniMap.Create()
		miniMap.SetScale(2.0)

		self.AtlasWindow = AtlasWindow()
		self.AtlasWindow.LoadWindow()
		self.AtlasWindow.Hide()

		self.tooltipMiniMapOpen = MapTextToolTip()
		self.tooltipMiniMapOpen.SetText(localeInfo.MINIMAP)
		self.tooltipMiniMapOpen.Show()
		self.tooltipMiniMapClose = MapTextToolTip()
		self.tooltipMiniMapClose.SetText(localeInfo.UI_CLOSE)
		self.tooltipMiniMapClose.Show()
		self.tooltipScaleUp = MapTextToolTip()
		self.tooltipScaleUp.SetText(localeInfo.MINIMAP_INC_SCALE)
		self.tooltipScaleUp.Show()
		self.tooltipScaleDown = MapTextToolTip()
		self.tooltipScaleDown.SetText(localeInfo.MINIMAP_DEC_SCALE)
		self.tooltipScaleDown.Show()
		self.tooltipAtlasOpen = MapTextToolTip()
		self.tooltipAtlasOpen.SetText(localeInfo.MINIMAP_SHOW_AREAMAP)
		self.tooltipAtlasOpen.Show()
		self.tooltipInfo = MapTextToolTip()
		self.tooltipInfo.Show()

		if miniMap.IsAtlas():
			self.tooltipAtlasOpen.SetText(localeInfo.MINIMAP_SHOW_AREAMAP)
		else:
			self.tooltipAtlasOpen.SetText(localeInfo.MINIMAP_CAN_NOT_SHOW_AREAMAP)

		self.tooltipInfo = MapTextToolTip()
		self.tooltipInfo.Show()

		self.mapName = ""

		self.isLoaded = 0
		self.canSeeInfo = True
		
		# AUTOBAN
		self.imprisonmentDuration = 0
		self.imprisonmentEndTime = 0
		self.imprisonmentEndTimeText = ""
		# END_OF_AUTOBAN

		player_options.listen(self)

	def __del__(self):
		miniMap.Destroy()
		ui.ScriptWindow.__del__(self)

	def __Initialize(self):
		self.positionInfo = 0
		self.observerCount = 0

		self.OpenWindow = 0
		self.CloseWindow = 0
		self.ScaleUpButton = 0
		self.ScaleDownButton = 0
		self.MiniMapHideButton = 0
		self.MiniMapShowButton = 0
		self.AtlasShowButton = 0

		self.tooltipMiniMapOpen = 0
		self.tooltipMiniMapClose = 0
		self.tooltipScaleUp = 0
		self.tooltipScaleDown = 0
		self.tooltipAtlasOpen = 0
		self.tooltipInfo = None
		self.serverInfo = None
		self.fpsLine = None
		self.fpsShown = False
		self.fpsNext = 0.0

	def SetMapName(self, mapName):
		self.mapName=mapName
		self.AtlasWindow.SetMapName(mapName)

		if mapName in self.CANNOT_SEE_INFO_MAP_DICT:
			self.canSeeInfo = False
			self.HideMiniMap()
			self.tooltipMiniMapOpen.SetText(localeInfo.MINIMAP_CANNOT_SEE)
		else:
			self.canSeeInfo = True
			self.ShowMiniMap()
			self.tooltipMiniMapOpen.SetText(localeInfo.MINIMAP)
			
	# AUTOBAN
	def SetImprisonmentDuration(self, duration):
		self.imprisonmentDuration = duration
		self.imprisonmentEndTime = app.GetGlobalTimeStamp() + duration				
		
		self.__UpdateImprisonmentDurationText()
		
	def __UpdateImprisonmentDurationText(self):
		restTime = max(self.imprisonmentEndTime - app.GetGlobalTimeStamp(), 0)
		
		imprisonmentEndTimeText = localeInfo.SecondToDHM(restTime)
		if imprisonmentEndTimeText != self.imprisonmentEndTimeText:
			self.imprisonmentEndTimeText = imprisonmentEndTimeText
			self.serverInfo.SetText("%s: %s" % (uiScriptLocale.AUTOBAN_QUIZ_REST_TIME, self.imprisonmentEndTimeText))
	# END_OF_AUTOBAN	

	def Show(self):
		self.__LoadWindow()

		ui.ScriptWindow.Show(self)

	def __LoadWindow(self):
		if self.isLoaded == 1:
			return

		self.isLoaded = 1

		try:
			pyScrLoader = ui.PythonScriptLoader()
			if app.IsRTL():
				pyScrLoader.LoadScriptFile(self, uiScriptLocale.LOCALE_UISCRIPT_PATH + "Minimap.py")
			else:
				pyScrLoader.LoadScriptFile(self, "UIScript/MiniMap.py")
		except:
			import exception
			exception.Abort("MiniMap.LoadWindow.LoadScript")

		try:
			self.OpenWindow = self.GetChild("OpenWindow")
			self.MiniMapWindow = self.GetChild("MiniMapWindow")
			self.ScaleUpButton = self.GetChild("ScaleUpButton")
			self.ScaleDownButton = self.GetChild("ScaleDownButton")
			self.MiniMapHideButton = self.GetChild("MiniMapHideButton")
			self.AtlasShowButton = self.GetChild("AtlasShowButton")
			self.CloseWindow = self.GetChild("CloseWindow")
			self.MiniMapShowButton = self.GetChild("MiniMapShowButton")
			self.positionInfo = self.GetChild("PositionInfo")
			self.observerCount = self.GetChild("ObserverCount")
			self.serverInfo = self.GetChild("ServerInfo")
		except:
			import exception
			exception.Abort("MiniMap.LoadWindow.Bind")

		if constInfo.MINIMAP_POSITIONINFO_ENABLE==0:
			self.positionInfo.Hide()

		self.serverInfo.SetText(net.GetServerInfo())
		self.ScaleUpButton.SetEvent(ui.__mem_func__(self.ScaleUp))
		self.ScaleDownButton.SetEvent(ui.__mem_func__(self.ScaleDown))
		self.MiniMapHideButton.SetEvent(ui.__mem_func__(self.HideMiniMap))
		self.MiniMapShowButton.SetEvent(ui.__mem_func__(self.ShowMiniMap))

		if miniMap.IsAtlas():
			self.AtlasShowButton.SetEvent(ui.__mem_func__(self.ShowAtlas))

		(ButtonPosX, ButtonPosY) = self.MiniMapShowButton.GetGlobalPosition()
		self.tooltipMiniMapOpen.SetTooltipPosition(ButtonPosX, ButtonPosY)

		(ButtonPosX, ButtonPosY) = self.MiniMapHideButton.GetGlobalPosition()
		self.tooltipMiniMapClose.SetTooltipPosition(ButtonPosX, ButtonPosY)

		(ButtonPosX, ButtonPosY) = self.ScaleUpButton.GetGlobalPosition()
		self.tooltipScaleUp.SetTooltipPosition(ButtonPosX, ButtonPosY)

		(ButtonPosX, ButtonPosY) = self.ScaleDownButton.GetGlobalPosition()
		self.tooltipScaleDown.SetTooltipPosition(ButtonPosX, ButtonPosY)

		(ButtonPosX, ButtonPosY) = self.AtlasShowButton.GetGlobalPosition()
		self.tooltipAtlasOpen.SetTooltipPosition(ButtonPosX, ButtonPosY)

		self.fpsLine = ui.TextLine()
		self.fpsLine.SetParent(self)
		self.fpsLine.SetPosition(*self.FPS_LINE_POSITION)
		self.fpsLine.SetHorizontalAlignCenter()
		self.fpsLine.SetOutline()
		self.__ShowFps(player_options.is_on(player_options.FPS_COUNTER))

		self.ShowMiniMap()

	def Destroy(self):
		self.HideMiniMap()

		self.AtlasWindow.Destroy()
		self.AtlasWindow = None

		self.ClearDictionary()

		self.__Initialize()

	def UpdateObserverCount(self, observerCount):
		if observerCount>0:
			self.observerCount.Show()
		elif observerCount<=0:
			self.observerCount.Hide()

		self.observerCount.SetText(localeInfo.MINIMAP_OBSERVER_COUNT % observerCount)

	# The server line again from net.GetServerInfo(): game.py calls it when a
	# channel change renamed the channel there (NOVA-49). Before the first
	# Show the line is not loaded yet, and that Show reads the text itself.
	def RefreshServerInfo(self):
		if self.serverInfo:
			self.serverInfo.SetText(net.GetServerInfo())

	# The FPS readout: shown or hidden by the option, its text read again
	# once a second (the client counts the render FPS once a second).
	def __ShowFps(self, show):
		self.fpsShown = bool(show)
		if not self.fpsLine:
			return
		if self.fpsShown:
			self.__RefreshFps(True)
			self.fpsLine.Show()
		else:
			self.fpsLine.Hide()

	def __RefreshFps(self, force=False):
		now = app.GetTime()
		if force or now >= self.fpsNext:
			self.fpsLine.SetText(player_options.fps_text(app.GetRenderFPS()))
			self.fpsNext = now + player_options.FPS_INTERVAL

	def OnPlayerOptionChanged(self, name):
		if name == player_options.FPS_COUNTER:
			self.__ShowFps(player_options.is_on(player_options.FPS_COUNTER))

	def OnUpdate(self):
		if self.fpsShown and self.fpsLine:
			self.__RefreshFps()

		(x, y, z) = player.GetMainCharacterPosition()
		miniMap.Update(x, y)

		self.positionInfo.SetText("(%.0f, %.0f)" % (x // 100, y // 100))

		if self.tooltipInfo:
			if True == self.MiniMapWindow.IsIn():
				(mouseX, mouseY) = wndMgr.GetMousePosition()
				(bFind, sName, iPosX, iPosY, dwTextColor) = miniMap.GetInfo(mouseX, mouseY)

				if bFind == 0:
					self.tooltipInfo.Hide()
				elif not self.canSeeInfo:
					self.tooltipInfo.SetText("%s (%s)" % (sName, localeInfo.UI_POS_UNKNOWN))
					self.tooltipInfo.SetTooltipPosition(mouseX - 5, mouseY)
					self.tooltipInfo.SetTextColor(dwTextColor)
					self.tooltipInfo.Show()
				else:
					if app.IsRTL() and sName[-1].isalnum():
						self.tooltipInfo.SetText("(%s) %d, %d" % (sName, iPosX, iPosY))
					else:
						self.tooltipInfo.SetText("%s (%d, %d)" % (sName, iPosX, iPosY))

					self.tooltipInfo.SetTooltipPosition(mouseX - 5, mouseY)
					self.tooltipInfo.SetTextColor(dwTextColor)
					self.tooltipInfo.Show()
			else:
				self.tooltipInfo.Hide()
			
			# AUTOBAN
			if self.imprisonmentDuration:
				self.__UpdateImprisonmentDurationText()
			# END_OF_AUTOBAN

		if True == self.MiniMapShowButton.IsIn():
			self.tooltipMiniMapOpen.Show()
		else:
			self.tooltipMiniMapOpen.Hide()

		if True == self.MiniMapHideButton.IsIn():
			self.tooltipMiniMapClose.Show()
		else:
			self.tooltipMiniMapClose.Hide()

		if True == self.ScaleUpButton.IsIn():
			self.tooltipScaleUp.Show()
		else:
			self.tooltipScaleUp.Hide()

		if True == self.ScaleDownButton.IsIn():
			self.tooltipScaleDown.Show()
		else:
			self.tooltipScaleDown.Hide()

		if True == self.AtlasShowButton.IsIn():
			self.tooltipAtlasOpen.Show()
		else:
			self.tooltipAtlasOpen.Hide()

	def OnRender(self):
		(x, y) = self.GetGlobalPosition()
		fx = float(x)
		fy = float(y)
		miniMap.Render(fx + 4.0, fy + 5.0)

	def Close(self):
		self.HideMiniMap()

	def HideMiniMap(self):
		miniMap.Hide()
		self.OpenWindow.Hide()
		self.CloseWindow.Show()

	def ShowMiniMap(self):
		if not self.canSeeInfo:
			return

		miniMap.Show()
		self.OpenWindow.Show()
		self.CloseWindow.Hide()

	def isShowMiniMap(self):
		return miniMap.isShow()

	def ScaleUp(self):
		miniMap.ScaleUp()

	def ScaleDown(self):
		miniMap.ScaleDown()

	def ShowAtlas(self):
		if not miniMap.IsAtlas():
			return
		if not self.AtlasWindow.IsShow():
			self.AtlasWindow.Show()

	# NOVA-206: the event a press on an atlas mark calls with its vnum.
	def SetOpenWikiMobEvent(self, event):
		self.AtlasWindow.SetOpenWikiMobEvent(event)

	def ToggleAtlasWindow(self):
		if not miniMap.IsAtlas():
			return
		if self.AtlasWindow.IsShow():
			self.AtlasWindow.Hide()
		else:
			self.AtlasWindow.Show()
