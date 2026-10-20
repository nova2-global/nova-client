"""NovaUI guild building placement (nui/windows/guild-building/guild-building.rml).

While the "guild-building" window flag is on, Interface.BUILD_OpenWindow
makes BuildGuildBuildingWindow below through nui_windows.make() instead of
uiGuild.BuildGuildBuildingWindow, once per open: the facade of the legacy
window, with its name, constructor, methods and class constants. It makes
legacy's state and world calls in legacy's order (uiguild.py:1959-2555):
the preview instances (chr), the camera (app.SetCameraSetting and
SetDefaultCamera), the guild area view (background), the PC blocker, the
money and material checks with app.IsEnableTestServerFlag, the popups
(uiCommon.PopupDialog, the dialog kit's facade while "dialogs" is on) and
/build. The list rows keep legacy's list box rule (a selection fires only
when it changes, ui.py ListBox.SelectItem) and the sliders legacy's slider
rule (a position the window sets fires nothing; a slider's change event
that brings back the model's own value is that echo, not a move).

game.py calls IsPositioningMode() every frame while the window exists and,
while positioning, SetBuildingPosition() with the picking point
(Interface.BUILD_OnUpdate), as it calls legacy's: both answer from
attributes and touch no model, since the board does not exist while the
window hides to position. These are the only per-frame calls; there is no
OnUpdate or OnRender. The document exists only while the window shows
(nui_hud.OnDemand); its controls take no focus and act on a left mousedown,
the sliders on their change events. Escape closes the window in its legacy
place, the UI layer (nui_hud.EscapeProxy).

The building names come from guildbuildinglist.txt and go through
nui.plain_text; the category labels and the counts are localeInfo's."""

import app
import background
import chr
import grp
import localeInfo
import miniMap
import net
import player
import uiCommon
import uiGuild
import wndMgr

import nui
import nui_hud

DOCUMENT = "nui/windows/guild-building/guild-building.rml"
AXES = ("x", "y", "z")


class GuildBuildingBoard(nui.Window):
	"""The window's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "guild_building"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		model = getattr(self._owner, "nui_model", None)
		if model is not None:
			return model()
		return BuildGuildBuildingWindow.empty_model()

	@nui.on("act")
	def on_act(self, what, button):
		if button == 0:
			self._owner.nui_act(what)

	@nui.on("pick_category")
	def on_pick_category(self, index, button):
		if button == 0:
			self._owner.nui_pick_category(index)

	@nui.on("pick_building")
	def on_pick_building(self, index, button):
		if button == 0:
			self._owner.nui_pick_building(index)

	@nui.on("rotate")
	def on_rotate(self, axis, value):
		self._owner.nui_rotate(axis, value)


class BuildGuildBuildingWindow(nui_hud.LayoutCalls):
	"""uiGuild.BuildGuildBuildingWindow on NovaUI (Interface.wndGuildBuilding)."""

	NUI_FACADE = True
	KEY = "guild-building"

	GUILD_CATEGORY_LIST = (
		("HEADQUARTER", localeInfo.GUILD_HEADQUARTER),
		("FACILITY", localeInfo.GUILD_FACILITY),
		("OBJECT", localeInfo.GUILD_OBJECT),
	)
	# The labels of the list above, for the model (nui_hud.locale_text).
	CATEGORY_LABELS = ("GUILD_HEADQUARTER", "GUILD_FACILITY", "GUILD_OBJECT")

	MODE_VIEW = 0
	MODE_POSITIONING = 1
	MODE_PREVIEW = 2

	BUILDING_ALPHA = 0.55

	ENABLE_COLOR = grp.GenerateColor(0.7607, 0.7607, 0.7607, 1.0)
	DISABLE_COLOR = grp.GenerateColor(0.9, 0.4745, 0.4627, 1.0)

	START_INSTANCE_INDEX = 123450

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.closeEvent = None
		self.popup = None
		self.mode = self.MODE_VIEW
		self.race = 0
		self.type = None
		self.x = 0
		self.y = 0
		self.z = 0
		self.rot_x = 0
		self.rot_y = 0
		self.rot_z = 0
		self.rot_x_limit = 0
		self.rot_y_limit = 0
		self.rot_z_limit = 0
		self.needMoney = 0
		self.needStoneCount = 0
		self.needLogCount = 0
		self.needPlywoodCount = 0

		self.indexList = []
		self.raceList = []
		self.posList = []
		self.rotList = []

		# Legacy's widgets as state: the two list boxes (rows of (number,
		# text) and the selected line, -1 for none), the three sliders' places
		# (0 to 1; legacy's cursor starts at 1.0) and whether each can move,
		# and the texts the value lines show.
		self.categoryRows = [(index, category[1]) for index, category in enumerate(self.GUILD_CATEGORY_LIST)]
		self.categoryLine = -1
		self.buildingRows = []
		self.buildingLine = -1
		self.sliderPos = {"x": 1.0, "y": 1.0, "z": 1.0}
		self.sliderOn = {"x": True, "y": True, "z": True}
		self.texts = {"price": "", "stone": "", "log": "", "plywood": "", "pos_x": "999", "pos_y": "999"}
		self.short = {"price": False, "stone": False, "log": False, "plywood": False}
		self.place = None

		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.Close)
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	# --- the model ----------------------------------------------------------------

	@staticmethod
	def empty_model():
		return {"categories": [], "category": -1, "buildings": [], "building": -1,
		        "price": "", "stone": "", "log": "", "plywood": "",
		        "price_short": False, "stone_short": False, "log_short": False, "plywood_short": False,
		        "pos_x": "", "pos_y": "", "rot_x": 100, "rot_y": 100, "rot_z": 100,
		        "rot_x_on": True, "rot_y_on": True, "rot_z_on": True, "positioning": False, "preview": False}

	def nui_model(self):
		"""Every key from the facade's state, as legacy's widgets show it."""
		model = {"categories": [{"label": nui_hud.locale_text(name)} for name in self.CATEGORY_LABELS],
		         "category": self.categoryLine,
		         "buildings": [{"label": nui.plain_text(text)} for _, text in self.buildingRows],
		         "building": self.buildingLine,
		         "positioning": self.mode == self.MODE_POSITIONING, "preview": self.mode == self.MODE_PREVIEW}
		for key in ("price", "stone", "log", "plywood"):
			model[key] = nui.plain_text(self.texts[key])
			model[key + "_short"] = self.short[key]
		for key in ("pos_x", "pos_y"):
			model[key] = nui.plain_text(self.texts[key])
		for axis in AXES:
			model["rot_" + axis] = int(round(self.sliderPos[axis] * 100))
			model["rot_%s_on" % axis] = self.sliderOn[axis]
		return model

	def _board(self):
		return self.demand.board() if self.demand is not None else None

	def _set(self, **values):
		board = self._board()
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return GuildBuildingBoard(self)

	def _restore_board(self, board):
		board.set(**self.nui_model())
		if self.place is not None:
			board.set_position(*self.place)

	def _keep_board(self, board):
		"""The place the player dragged the window to, in dp; None while it is
		where the sheet puts it (10dp from the left, its bottom 50dp above the
		screen's)."""
		box = board.element_box("")
		if not box:
			return
		x, y, width, height = box
		s = nui.get_scale() or 1.0
		if abs(x - 10 * s) <= 2 and abs(y + height - (wndMgr.GetScreenHeight() - 50 * s)) <= 2:
			self.place = None
		else:
			self.place = (x / s, y / s)

	# --- legacy's widgets ---------------------------------------------------------------

	def _select_category(self, line):
		"""categoryList.SelectItem(line) (ui.py ListBox.SelectItem)."""
		if not 0 <= line < len(self.categoryRows) or line == self.categoryLine:
			return
		self.categoryLine = line
		self._set(category=line)
		self.__OnSelectCategory()

	def _category_index(self):
		"""categoryList.GetSelectedItem()."""
		if 0 <= self.categoryLine < len(self.categoryRows):
			return self.categoryRows[self.categoryLine][0]
		return 0

	def _select_building(self, line):
		"""buildingList.SelectItem(line)."""
		if not 0 <= line < len(self.buildingRows) or line == self.buildingLine:
			return
		self.buildingLine = line
		self._set(building=line)
		self.__OnSelectBuilding()

	def _building_index(self):
		"""buildingList.GetSelectedItem()."""
		if 0 <= self.buildingLine < len(self.buildingRows):
			return self.buildingRows[self.buildingLine][0]
		return 0

	def _set_slider_pos(self, axis, pos):
		"""ctrlRotation<axis>.SetSliderPos(pos): fires nothing."""
		self.sliderPos[axis] = pos
		self._set(**{"rot_" + axis: int(round(pos * 100))})

	def _set_slider_on(self, axis, on):
		"""ctrlRotation<axis>.Enable() and Disable()."""
		self.sliderOn[axis] = on
		self._set(**{"rot_%s_on" % axis: on})

	def _set_text(self, key, text):
		self.texts[key] = text
		self._set(**{key: nui.plain_text(text)})

	def _set_short(self, key, short):
		self.short[key] = short
		self._set(**{key + "_short": short})

	# --- the instances (uiguild.py:2064-2202) -------------------------------------------

	def __CreateWallBlock(self, race, x, y, rot=0.0):
		idx = self.START_INSTANCE_INDEX + len(self.indexList)
		self.indexList.append(idx)
		self.raceList.append(race)
		self.posList.append((x, y))
		self.rotList.append(rot)
		chr.CreateInstance(idx)
		chr.SelectInstance(idx)
		chr.SetVirtualID(idx)
		chr.SetInstanceType(chr.INSTANCE_TYPE_OBJECT)

		chr.SetRace(race)
		chr.SetArmor(0)
		chr.Refresh()
		chr.SetLoopMotion(chr.MOTION_WAIT)
		chr.SetBlendRenderMode(idx, self.BUILDING_ALPHA)
		chr.SetRotationAll(0.0, 0.0, rot)

		for axis in AXES:
			self._set_slider_pos(axis, 0.5)

	def __GetObjectSize(self, race):
		idx = self.START_INSTANCE_INDEX + 1000
		chr.CreateInstance(idx)
		chr.SelectInstance(idx)
		chr.SetVirtualID(idx)
		chr.SetInstanceType(chr.INSTANCE_TYPE_OBJECT)

		chr.SetRace(race)
		chr.SetArmor(0)
		chr.Refresh()
		chr.SetLoopMotion(chr.MOTION_WAIT)
		sx, sy, ex, ey = chr.GetBoundBoxOnlyXY(idx)
		chr.DeleteInstance(idx)
		return sx, sy, ex, ey

	def __GetBuildInPosition(self):
		zList = []
		zList.append(background.GetHeight(self.x + self.sxPos, self.y + self.syPos))
		zList.append(background.GetHeight(self.x + self.sxPos, self.y + self.eyPos))
		zList.append(background.GetHeight(self.x + self.exPos, self.y + self.syPos))
		zList.append(background.GetHeight(self.x + self.exPos, self.y + self.eyPos))
		zList.append(background.GetHeight(self.x + (self.exPos + self.sxPos) / 2, self.y + (self.eyPos + self.syPos) / 2))
		zList.sort()
		return zList[3]

	def __CreateBuildInInstance(self, race):
		"""Legacy's walled building, kept as legacy has it: no category has the
		type BUILDIN (GUILD_CATEGORY_LIST), so nothing reaches it. Legacy's
		range(X_SIZE_STEP / 2) (a float under Python 3) is the integer
		division its Python 2 meant."""
		self.__DeleteInstance()

		object_base = race - race % 10

		door_minX, door_minY, door_maxX, door_maxY = self.__GetObjectSize(object_base + 4)
		corner_minX, corner_minY, corner_maxX, corner_maxY = self.__GetObjectSize(object_base + 1)
		line_minX, line_minY, line_maxX, line_maxY = self.__GetObjectSize(object_base + 2)
		line_width = line_maxX - line_minX
		line_width_half = line_width / 2

		X_SIZE_STEP = 2 * 2
		Y_SIZE_STEP = 8
		sxPos = door_maxX - corner_minX + (line_width_half * X_SIZE_STEP)
		exPos = -sxPos
		syPos = 0
		eyPos = -(corner_maxY * 2 + line_width * Y_SIZE_STEP)

		self.sxPos = sxPos
		self.syPos = syPos
		self.exPos = exPos
		self.eyPos = eyPos

		z = self.__GetBuildInPosition()  # noqa: F841 (legacy's unused height)

		self.__CreateWallBlock(object_base + 4, 0.0, syPos)

		self.__CreateWallBlock(object_base + 1, sxPos, syPos)
		self.__CreateWallBlock(object_base + 1, exPos, syPos, 270.0)
		self.__CreateWallBlock(object_base + 1, sxPos, eyPos, 90.0)
		self.__CreateWallBlock(object_base + 1, exPos, eyPos, 180.0)

		lineBlock = object_base + 2
		line_startX = -door_maxX - line_minX - (line_width_half * X_SIZE_STEP)
		self.__CreateWallBlock(lineBlock, line_startX, eyPos)
		self.__CreateWallBlock(lineBlock, line_startX + line_width * 1, eyPos)
		self.__CreateWallBlock(lineBlock, line_startX + line_width * 2, eyPos)
		self.__CreateWallBlock(lineBlock, line_startX + line_width * 3, eyPos)
		for i in range(X_SIZE_STEP):
			self.__CreateWallBlock(lineBlock, line_startX + line_width * (3 + i + 1), eyPos)
		for i in range(X_SIZE_STEP // 2):
			self.__CreateWallBlock(lineBlock, door_minX - line_maxX - line_width * i, syPos)
			self.__CreateWallBlock(lineBlock, door_maxX - line_minX + line_width * i, syPos)
		for i in range(Y_SIZE_STEP):
			self.__CreateWallBlock(lineBlock, sxPos, line_minX + corner_minX - line_width * i, 90.0)
			self.__CreateWallBlock(lineBlock, exPos, line_minX + corner_minX - line_width * i, 90.0)

		self.SetBuildingPosition(int(self.x), int(self.y), self.__GetBuildInPosition())

	def __DeleteInstance(self):
		if not self.indexList:
			return

		for index in self.indexList:
			chr.DeleteInstance(index)

		self.indexList = []
		self.raceList = []
		self.posList = []
		self.rotList = []

	def __CreateInstance(self, race):
		self.__DeleteInstance()

		self.race = race

		idx = self.START_INSTANCE_INDEX
		self.indexList.append(idx)
		self.posList.append((0, 0))
		self.rotList.append(0)

		chr.CreateInstance(idx)
		chr.SelectInstance(idx)
		chr.SetVirtualID(idx)
		chr.SetInstanceType(chr.INSTANCE_TYPE_OBJECT)

		chr.SetRace(race)
		chr.SetArmor(0)
		chr.Refresh()
		chr.SetLoopMotion(chr.MOTION_WAIT)
		chr.SetBlendRenderMode(idx, self.BUILDING_ALPHA)

		self.SetBuildingPosition(int(self.x), int(self.y), 0)
		for axis in AXES:
			self._set_slider_pos(axis, 0.5)

	# --- the Interface's and game.py's calls --------------------------------------------

	def Build(self):
		"""uiguild.py:2204-2230."""
		if not self.__IsEnoughMoney():
			self.__PopupDialog(localeInfo.GUILD_NOT_ENOUGH_MONEY)
			return
		if not self.__IsEnoughMaterialStone():
			self.__PopupDialog(localeInfo.GUILD_NOT_ENOUGH_MATERIAL)
			return
		if not self.__IsEnoughMaterialLog():
			self.__PopupDialog(localeInfo.GUILD_NOT_ENOUGH_MATERIAL)
			return
		if not self.__IsEnoughMaterialPlywood():
			self.__PopupDialog(localeInfo.GUILD_NOT_ENOUGH_MATERIAL)
			return

		## /build c vnum x y x_rot y_rot z_rot
		if "BUILDIN" == self.type:
			for i in range(len(self.raceList)):
				race = self.raceList[i]
				xPos, yPos = self.posList[i]
				rot = self.rotList[i]
				net.SendChatPacket("/build c %d %d %d %d %d %d" % (race, int(self.x + xPos), int(self.y + yPos), self.rot_x, self.rot_y, rot))
		else:
			net.SendChatPacket("/build c %d %d %d %d %d %d" % (self.race, int(self.x), int(self.y), self.rot_x, self.rot_y, self.rot_z))

		self.Close()

	def Open(self):
		"""uiguild.py:2232-2250."""
		x, y, z = player.GetMainCharacterPosition()
		app.SetCameraSetting(int(x), int(-y), int(z), 3000, 0, 30)

		background.VisibleGuildArea()

		self.x = x
		self.y = y
		self.z = z
		self._select_category(0)
		self._select_building(0)
		self.Show()
		self.SetTop()
		self.__DisablePCBlocker()

		import debugInfo
		if debugInfo.IsDebugMode():
			self._select_category(2)
			self._select_building(0)

	def Close(self):
		"""uiguild.py:2252-2263."""
		self.__DeleteInstance()

		background.DisableGuildArea()

		self.Hide()
		self.__OnClosePopupDialog()
		self.__EnablePCBlocker()
		self.__UnlockCameraMoving()
		if self.closeEvent:
			self.closeEvent()

	def Destroy(self):
		"""Legacy's inherited ui.Window.Destroy (the Interface's Close): its
		own Destory is never called, so the instances and the guild area view
		stay as they are (P12 spec 2.7); the NovaUI parts go."""
		self.nui_discard()

	def Destory(self):
		"""uiguild.py:2265-2284 (no caller)."""
		self.Close()
		self.closeEvent = None
		self.nui_discard()

	def SetCloseEvent(self, event):
		self.closeEvent = event

	def Show(self):
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()

	def Hide(self):
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return self.demand is not None and self.demand.is_shown()

	def SetTop(self):
		board = self._board()
		if board is not None:
			board.bring_to_front()
		if self.escapeProxy is not None and self.escapeProxy.is_shown():
			self.escapeProxy.show()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def __PopupDialog(self, text):
		popup = uiCommon.PopupDialog()
		popup.SetText(text)
		popup.SetAcceptEvent(self.__OnClosePopupDialog)
		popup.Open()
		self.popup = popup

	def __OnClosePopupDialog(self):
		self.popup = None

	def __EnablePCBlocker(self):
		chr.SetInstanceType(chr.INSTANCE_TYPE_BUILDING)

		for idx in self.indexList:
			chr.SetBlendRenderMode(idx, 1.0)

	def __DisablePCBlocker(self):
		chr.SetInstanceType(chr.INSTANCE_TYPE_OBJECT)

		for idx in self.indexList:
			chr.SetBlendRenderMode(idx, self.BUILDING_ALPHA)

	def __OnSelectPositioningMode(self):
		# The radio button pops up again in preview mode (positionButton.SetUp).
		if self.MODE_PREVIEW == self.mode:
			return

		self.mode = self.MODE_POSITIONING
		self._set(positioning=True)
		self.Hide()

	def __OnEnterPreviewMode(self):
		if self.MODE_POSITIONING == self.mode:
			return

		self.mode = self.MODE_PREVIEW
		self._set(preview=True, positioning=False)
		self.__UnlockCameraMoving()
		self.__EnablePCBlocker()

	def __OnLeavePreviewMode(self):
		self.__RestoreViewMode()

	def __RestoreViewMode(self):
		self.__DisablePCBlocker()
		self.__LockCameraMoving()
		self.mode = self.MODE_VIEW
		self._set(positioning=False, preview=False)

	def __IsEnoughMoney(self):
		if app.IsEnableTestServerFlag():
			return True

		curMoney = player.GetMoney()
		if curMoney < self.needMoney:
			return False
		return True

	def __IsEnoughMaterialStone(self):
		if app.IsEnableTestServerFlag():
			return True

		curStoneCount = player.GetItemCountByVnum(uiGuild.MATERIAL_STONE_ID)
		if curStoneCount < self.needStoneCount:
			return False
		return True

	def __IsEnoughMaterialLog(self):
		if app.IsEnableTestServerFlag():
			return True

		curLogCount = player.GetItemCountByVnum(uiGuild.MATERIAL_LOG_ID)
		if curLogCount < self.needLogCount:
			return False
		return True

	def __IsEnoughMaterialPlywood(self):
		if app.IsEnableTestServerFlag():
			return True

		curPlywoodCount = player.GetItemCountByVnum(uiGuild.MATERIAL_PLYWOOD_ID)
		if curPlywoodCount < self.needPlywoodCount:
			return False
		return True

	def __OnSelectCategory(self):
		# listScrollBar.SetPos(0.0): the NovaUI list is a new one.
		self.__RefreshItem()

	def __SetBuildingData(self, data):
		self._set_text("price", uiGuild.NumberToMoneyString(int(data["PRICE"])))

		self.needMoney = int(data["PRICE"])

		materialList = data["MATERIAL"]
		self.needStoneCount = int(materialList[uiGuild.MATERIAL_STONE_INDEX])
		self.needLogCount = int(materialList[uiGuild.MATERIAL_LOG_INDEX])
		self.needPlywoodCount = int(materialList[uiGuild.MATERIAL_PLYWOOD_INDEX])

		self._set_text("stone", materialList[uiGuild.MATERIAL_STONE_INDEX] + localeInfo.THING_COUNT)
		self._set_text("log", materialList[uiGuild.MATERIAL_LOG_INDEX] + localeInfo.THING_COUNT)
		self._set_text("plywood", materialList[uiGuild.MATERIAL_PLYWOOD_INDEX] + localeInfo.THING_COUNT)

		self._set_short("price", not self.__IsEnoughMoney())
		self._set_short("stone", not self.__IsEnoughMaterialStone())
		self._set_short("log", not self.__IsEnoughMaterialLog())
		self._set_short("plywood", not self.__IsEnoughMaterialPlywood())

		self.rot_x_limit = data["X_ROT_LIMIT"]
		self.rot_y_limit = data["Y_ROT_LIMIT"]
		self.rot_z_limit = data["Z_ROT_LIMIT"]
		self._set_slider_on("x", 0 != self.rot_x_limit)
		self._set_slider_on("y", 0 != self.rot_y_limit)
		self._set_slider_on("z", 0 != self.rot_z_limit)

	def __OnSelectBuilding(self):
		buildingIndex = self._building_index()
		if buildingIndex >= len(uiGuild.BUILDING_DATA_LIST):
			return

		categoryIndex = self._category_index()
		if categoryIndex >= len(self.GUILD_CATEGORY_LIST):
			return
		selectedType = self.GUILD_CATEGORY_LIST[categoryIndex][0]

		index = 0
		for data in uiGuild.BUILDING_DATA_LIST:
			type = data["TYPE"]
			vnum = data["VNUM"]
			if selectedType != type:
				continue

			if index == buildingIndex:
				self.type = type
				if "BUILDIN" == self.type:
					self.__CreateBuildInInstance(vnum)
				else:
					self.__CreateInstance(vnum)

				self.__SetBuildingData(data)

			index += 1

	def __OnChangeRotation(self):
		self.rot_x = self.sliderPos["x"] * self.rot_x_limit - self.rot_x_limit / 2
		self.rot_y = self.sliderPos["y"] * self.rot_y_limit - self.rot_y_limit / 2
		self.rot_z = (self.sliderPos["z"] * 360 + 180) % 360
		chr.SetRotationAll(self.rot_x, self.rot_y, self.rot_z)

	def __LockCameraMoving(self):
		app.SetCameraSetting(int(self.x), int(-self.y), int(self.z), 3000, 0, 30)

	def __UnlockCameraMoving(self):
		app.SetDefaultCamera()

	def __RefreshItem(self):
		self.buildingRows = []
		self.buildingLine = -1

		categoryIndex = self._category_index()
		if categoryIndex < len(self.GUILD_CATEGORY_LIST):
			selectedType = self.GUILD_CATEGORY_LIST[categoryIndex][0]

			index = 0
			for data in uiGuild.BUILDING_DATA_LIST:
				if selectedType != data["TYPE"]:
					continue

				if data["SHOW"]:
					self.buildingRows.append((index, data["LOCAL_NAME"]))

				index += 1

		self._set(buildings=[{"label": nui.plain_text(text)} for _, text in self.buildingRows], building=-1)
		if categoryIndex < len(self.GUILD_CATEGORY_LIST):
			self._select_building(0)

	def SettleCurrentPosition(self):
		"""uiguild.py:2512-2524: a world press while positioning."""
		guildID = miniMap.GetGuildAreaID(self.x, self.y)

		import debugInfo
		if debugInfo.IsDebugMode():
			guildID = player.GetGuildID()

		if guildID != player.GetGuildID():
			return

		self.__RestoreViewMode()
		self.__LockCameraMoving()
		self.Show()

	def SetBuildingPosition(self, x, y, z):
		"""uiguild.py:2526-2541; every frame while positioning, when the board
		does not exist."""
		self.x = x
		self.y = y
		self.texts["pos_x"] = str(int(x))
		self.texts["pos_y"] = str(int(y))
		self._set(pos_x=self.texts["pos_x"], pos_y=self.texts["pos_y"])

		for i in range(len(self.indexList)):
			idx = self.indexList[i]
			xPos, yPos = self.posList[i]

			chr.SelectInstance(idx)
			if 0 != z:
				self.z = z
				chr.SetPixelPosition(int(x + xPos), int(y + yPos), int(z))
			else:
				chr.SetPixelPosition(int(x + xPos), int(y + yPos))

	def IsPositioningMode(self):
		if self.MODE_POSITIONING == self.mode:
			return True
		return False

	def IsPreviewMode(self):
		if self.MODE_PREVIEW == self.mode:
			return True
		return False

	# --- the board's events ---------------------------------------------------------------

	def nui_act(self, what):
		if what in ("close", "cancel"):
			self.Close()
		elif what == "accept":
			self.Build()
		elif what == "position":
			# Legacy's radio button calls nothing for a press while it is down.
			if self.mode != self.MODE_POSITIONING:
				self.__OnSelectPositioningMode()
		elif what == "preview":
			# Legacy's toggle button: down enters preview, up leaves it.
			if self.mode == self.MODE_PREVIEW:
				self.__OnLeavePreviewMode()
			else:
				self.__OnEnterPreviewMode()

	def nui_pick_category(self, index):
		self._select_category(int(index))

	def nui_pick_building(self, index):
		self._select_building(int(index))

	def nui_rotate(self, axis, value):
		"""A slider moved: its place (0 to 1) and legacy's rotation event. The
		model's own value coming back (each show and each SetSliderPos moves the
		slider) is not a move, nor is a slider legacy keeps still (Disable)."""
		if axis not in AXES:
			return
		try:
			percent = float(value)
		except (TypeError, ValueError):
			return
		board = self._board()
		if board is None or not self.sliderOn[axis]:
			return
		if abs(percent - float(board.get("rot_" + axis) or 0)) < 0.5:
			return
		self.sliderPos[axis] = percent / 100.0
		board.set(**{"rot_" + axis: int(round(percent))})
		self.__OnChangeRotation()
