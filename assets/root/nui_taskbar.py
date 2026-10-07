"""NovaUI taskbar (nui/windows/taskbar/taskbar.rml).

While the "taskbar" window flag is on, Interface.__MakeTaskBar makes TaskBar
below through nui_windows.make() instead of uiTaskBar.TaskBar. TaskBar is a
facade: a plain class with the legacy class's name, constants and methods,
which the Interface and the C++ callbacks (through the Interface) call as
they call the legacy one. Its document is TaskBarBoard.

What moves to C++ (the feeds of NuiGameFeeds, bound in FEEDS): the gauges,
the EXP orbs, the quick page and the eight quickslots of the page, so the
legacy 500 ms poll and the per-frame IsIn() hover checks are gone; a facade
method that legacy answers by refreshing the quickslots asks C++ to rebuild
them (nuigame.RefreshQuickSlots). What stays in Python, run on events only:
the drags (nui_slots.SlotDrag through mouseModule.mouseController), the item
and skill tooltips (nui_slots.TooltipBridge), the mouse-button modes and
their menus, the skill picker, the window buttons and the item mall button.

The document loads hidden in __init__ (nui_ready and nui_discard follow
nui_windows.make()'s protocol); the board keeps a weak proxy to its facade."""

import math
import weakref

import constInfo
import item
import mouseModule
import net
import player
import skill
import wndMgr

import nui
import nui_hud
import nui_slots
import nui_windows
import uiTaskBar

try:
	import nuigame
except ImportError:  # an exe without the Wave 2a engine: nui_hud.has_engine() is False
	nuigame = None

DOCUMENT = "nui/windows/taskbar/taskbar.rml"
QUICK_SLOTS = 8
SKILL_PAGE = 6               # skills per picker row (OpenSelectSkill's PAGE_SLOT_COUNT)
SKILL_CATEGORIES = (1, 21, 41)  # ACTIVE_1, ACTIVE_2, ACTIVE_3: their first skill slot

_BUTTON_NAMES = {0: "character", 1: "inventory", 2: "messenger", 3: "system", 4: "expand"}

# The bar's height above the screen's bottom in dp, its top border included:
# taskbar.rcss .taskbar-bar (48dp and a 1dp border) and the classic skin's
# (37dp, legacy's bar, no border). Below 1060dp the modern document shrinks
# about its bottom-left corner (taskbar.rcss @media max-width): the widest
# screen in dp of each step, and its factor. nui_hud_core_test checks both
# against the sheets.
BAR_HEIGHT_DP = 49
CLASSIC_BAR_HEIGHT_DP = 37
NARROW_STEPS = ((688, 0.6), (741, 0.65), (794, 0.7), (847, 0.75), (900, 0.8), (953, 0.85), (1006, 0.9), (1059, 0.95))


def _keep(owner):
	"""The owner as a weak proxy; an object that takes no weak reference is
	kept as it is. The board never calls it while it is being made."""
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def _refresh_quick_slots():
	"""Asks C++ to rebuild the quickslot feed at its next tick."""
	if nuigame is not None:
		nuigame.RefreshQuickSlots()


class TaskBarBoard(nui.Window):
	"""The taskbar's document, model and handlers; it reports to its owner,
	the facade."""

	DOCUMENT = DOCUMENT
	MODEL = "taskbar"
	FEEDS = {
		"hp": "player.hp", "hp_max": "player.hp_max", "hp_ratio": "player.hp_ratio",
		"hp_recovery_ratio": "player.hp_recovery_ratio",
		"sp": "player.sp", "sp_max": "player.sp_max", "sp_ratio": "player.sp_ratio",
		"sp_recovery_ratio": "player.sp_recovery_ratio",
		"stamina": "player.stamina", "stamina_max": "player.stamina_max", "stamina_ratio": "player.stamina_ratio",
		"exp_percent": "player.exp_percent", "exp_orbs": "player.exp_orbs",
		"quick_page": "quickslot.page", "quick_slots": "quickslot.slots",
	}

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {
			"hp": 0, "hp_max": 0, "hp_ratio": 0.0, "hp_recovery_ratio": 0.0,
			"sp": 0, "sp_max": 0, "sp_ratio": 0.0, "sp_recovery_ratio": 0.0,
			"stamina": 0, "stamina_max": 0, "stamina_ratio": 0.0,
			"exp_percent": 0.0, "exp_orbs": [0.0, 0.0, 0.0, 0.0],
			"quick_page": 0, "quick_slots": [nui_slots.empty_slot(i) for i in range(QUICK_SLOTS)],
			"quick_picked": -1, "quick_selected": -1,
			"left_mode": "move", "right_mode": "move", "left_tip": "", "right_tip": "",
			"left_open": False, "right_open": False,
			"right_skill": [nui_slots.empty_slot(0)], "right_skill_shown": False,
			"skill_rows": [],
			"mouse_image": False,
			"expandable": True,
		}

	def on_theme_changed(self, theme_id):
		self._owner.nui_bar_height_changed()

	def on_scale_changed(self, scale):
		self._owner.nui_bar_height_changed()

	@nui.on("slot_press")
	def on_slot_press(self, grid, index, button):
		self._owner.nui_slot_press(grid, index, button)

	@nui.on("slot_release")
	def on_slot_release(self, grid, index, button):
		self._owner.nui_slot_release(grid, index, button)

	@nui.on("slot_over")
	def on_slot_over(self, grid, index):
		self._owner.nui_slot_over(grid, index)

	@nui.on("slot_out")
	def on_slot_out(self, grid, index):
		self._owner.nui_slot_out(grid, index)

	@nui.on("slot_drop")
	def on_slot_drop(self, grid, index):
		self._owner.nui_slot_drop(grid, index)

	@nui.on("page_up")
	def on_page_up(self, button):
		if button == 0:
			self._owner.nui_page(-1)

	@nui.on("page_down")
	def on_page_down(self, button):
		if button == 0:
			self._owner.nui_page(1)

	@nui.on("toggle_mouse")
	def on_toggle_mouse(self, direction, button):
		if button == 0:
			self._owner.nui_toggle_mouse(direction)

	@nui.on("pick_mode")
	def on_pick_mode(self, direction, event, button):
		if button == 0:
			self._owner.SelectMouseButtonEvent(direction, event)

	@nui.on("pick_skill")
	def on_pick_skill(self, skill_slot, button):
		if button == 0:
			self._owner.CloseSelectSkill(skill_slot + 1)

	@nui.on("pick_over")
	def on_pick_over(self, skill_slot):
		self._owner.nui_pick_over(skill_slot)

	@nui.on("pick_out")
	def on_pick_out(self):
		self._owner.tooltips.hide()

	@nui.on("button")
	def on_button(self, name, button):
		if button == 0:
			self._owner.nui_button(name)

	@nui.on("mall_click")
	def on_mall_click(self, button):
		if button == 0:
			self._owner.nui_mall_click()


class TaskBar(object):
	"""uiTaskBar.TaskBar on NovaUI (the wndTaskBar facade)."""

	NUI_FACADE = True

	BUTTON_CHARACTER = 0
	BUTTON_INVENTORY = 1
	BUTTON_MESSENGER = 2
	BUTTON_SYSTEM = 3
	BUTTON_CHAT = 4
	BUTTON_EXPAND = 4
	IS_EXPANDED = False

	MOUSE_BUTTON_LEFT = 0
	MOUSE_BUTTON_RIGHT = 1
	NONE = 255

	EVENT_MOVE = 0
	EVENT_ATTACK = 1
	EVENT_MOVE_AND_ATTACK = 2
	EVENT_CAMERA = 3
	EVENT_SKILL = 4
	EVENT_AUTO = 5

	GAUGE_WIDTH = 95
	GAUGE_HEIGHT = 13

	QUICKPAGE_NUMBER_FILENAME = [
		"d:/ymir work/ui/game/taskbar/1.sub",
		"d:/ymir work/ui/game/taskbar/2.sub",
		"d:/ymir work/ui/game/taskbar/3.sub",
		"d:/ymir work/ui/game/taskbar/4.sub",
	]

	# The legacy mode menus' buttons, (direction, event) -> the art the mode
	# button then shows. Another pair is a child the legacy menu does not
	# have: legacy GetChild raises KeyError there, and so does this facade.
	_MENU_ART = {
		(0, EVENT_MOVE_AND_ATTACK): "attack", (0, EVENT_AUTO): "auto", (0, EVENT_CAMERA): "camera",
		(1, EVENT_MOVE_AND_ATTACK): "attack", (1, EVENT_CAMERA): "camera", (1, EVENT_SKILL): "skill",
	}
	_MISSING_BUTTON = {EVENT_MOVE: "button_move", EVENT_ATTACK: "button_attack",
	                   EVENT_AUTO: "button_auto_attack", EVENT_SKILL: "button_skill"}

	def __init__(self):
		nui_hud.take_over("taskbar", self)
		self._nui_discarded = False
		self.board = None
		self.tooltips = nui_slots.TooltipBridge()
		self.toggleButtonEvents = {}
		self.barHeightEvent = None
		self.wndGiftBox = None
		self._right_slot = 0       # the right skill's skill slot (curSkillButton.slotIndex)
		self._right_index = 0      # its skill index (curSkillButton.skillIndex)
		self.drag_quick = nui_slots.SlotDrag(pick=self._pick_quick, drop=self.AddQuickSlot, use=self._use_quick,
			on_pick=self._on_pick, owner=self)
		self.drag_right = nui_slots.SlotDrag(pick=lambda index: None, drop=lambda index: None, owner=self)
		if not nui_hud.has_engine():
			return
		try:
			self.board = TaskBarBoard(self)
		except Exception:
			self.nui_discard()
			raise

	# --- the nui_windows.make() protocol ------------------------------------------

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		self._destroy_board()
		nui_hud.forget("taskbar", self)

	def _destroy_board(self):
		board, self.board = self.board, None
		if board is not None:
			board.destroy()

	def _set(self, **values):
		if self.board is not None:
			self.board.set(**values)

	def _get(self, key):
		return self.board.get(key) if self.board is not None else None

	# --- the window -------------------------------------------------------------------

	def LoadWindow(self):
		"""What legacy LoadWindow does after loading its uiscripts: the NovaUI
		bar has the expand button (taskbar.py's ExpandButton), the mouse
		settings load and apply, the gift box is made, and the quickslots
		refresh."""
		uiTaskBar.TaskBar.IS_EXPANDED = True
		TaskBar.IS_EXPANDED = True
		self.wndGiftBox = nui_windows.make("gift-box", uiTaskBar.GiftBox, "nui_gift_box.GiftBox")
		self.wndGiftBox.LoadWindow()
		self.__LoadMouseSettings()
		self.RefreshStatus()
		self.RefreshQuickSlot()

	def __LoadMouseSettings(self):
		try:
			uiTaskBar.LoadMouseButtonSettings()
			(left, right) = uiTaskBar.GetMouseButtonSettings()
			if not self.__IsInSafeMouseButtonSettingRange(left) or not self.__IsInSafeMouseButtonSettingRange(right):
				raise RuntimeError("INVALID_MOUSE_BUTTON_SETTINGS")
		except Exception:
			uiTaskBar.InitMouseButtonSettings(self.EVENT_MOVE_AND_ATTACK, self.EVENT_CAMERA)
			(left, right) = uiTaskBar.GetMouseButtonSettings()

		try:
			self.SelectMouseButtonEvent(self.MOUSE_BUTTON_LEFT, left)
			self.SelectMouseButtonEvent(self.MOUSE_BUTTON_RIGHT, right)
		except Exception:
			uiTaskBar.InitMouseButtonSettings(self.EVENT_MOVE_AND_ATTACK, self.EVENT_CAMERA)
			(left, right) = uiTaskBar.GetMouseButtonSettings()
			self.SelectMouseButtonEvent(self.MOUSE_BUTTON_LEFT, left)
			self.SelectMouseButtonEvent(self.MOUSE_BUTTON_RIGHT, right)

	def __IsInSafeMouseButtonSettingRange(self, arg):
		return arg >= self.EVENT_MOVE and arg <= self.EVENT_AUTO

	def Destroy(self):
		uiTaskBar.SaveMouseButtonSettings()
		gift, self.wndGiftBox = self.wndGiftBox, None
		if gift is not None:
			gift.Destroy()
		self.tooltips = nui_slots.TooltipBridge()
		self._destroy_board()
		nui_hud.forget("taskbar", self)

	def Show(self):
		if self.board is not None:
			self.board.show()

	def Hide(self):
		"""Hides the bar, its menus and the skill picker, and the tooltips."""
		self._set(left_open=False, right_open=False, skill_rows=[])
		self.tooltips.hide()
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	def SetTop(self):
		if self.board is not None:
			self.board.bring_to_front()

	def SetToggleButtonEvent(self, eButton, kEventFunc):
		self.toggleButtonEvents[eButton] = kEventFunc

	## The bar's height (NovaUI only: the legacy bar is always 37 px)
	def GetBarHeight(self):
		"""The bar's height in screen pixels above the bottom edge, as drawn
		now: 49dp modern (shrunk with the document on a narrow screen) or
		37dp classic, at the scale in use. The Interface keeps the legacy
		chat above it."""
		scale = nui.get_scale()
		if self.board is not None and self.board.has_class("skin-classic"):
			return int(math.ceil(CLASSIC_BAR_HEIGHT_DP * scale - 0.001))
		width_dp = wndMgr.GetScreenWidth() / scale if scale > 0 else 0
		factor = 1.0
		for widest, step in NARROW_STEPS:
			if width_dp <= widest:
				factor = step
				break
		return int(math.ceil(BAR_HEIGHT_DP * scale * factor - 0.001))

	def SetBarHeightEvent(self, event):
		"""`event()` runs after a theme or scale change, when GetBarHeight()
		may answer differently."""
		self.barHeightEvent = event

	def nui_bar_height_changed(self):
		if self.barHeightEvent is not None:
			self.barHeightEvent()

	def SetItemToolTip(self, tooltipItem):
		self.tooltips.set_item_tooltip(tooltipItem)

	def SetSkillToolTip(self, tooltipSkill):
		self.tooltips.set_skill_tooltip(tooltipSkill)

	## Gift
	def ShowGift(self):
		if self.wndGiftBox is not None:
			self.wndGiftBox.Show()

	def HideGift(self):
		if self.wndGiftBox is not None:
			self.wndGiftBox.Hide()

	## Mouse Image
	def ShowMouseImage(self):
		self._set(mouse_image=True)

	def HideMouseImage(self):
		player.SetQuickCameraMode(False)
		self._set(mouse_image=False)

	## Gauge: fed from C++ (player.* feeds).
	def RefreshStatus(self):
		pass

	def RefreshStamina(self):
		pass

	## Skill
	def RefreshSkill(self):
		_refresh_quick_slots()
		if self._right_slot:
			self.__SetRightSkill(self._right_slot)
		if self._get("right_open"):
			self._set(skill_rows=self.__SkillRows())

	def SkillClearCoolTime(self, usedSlotIndex):
		_refresh_quick_slots()
		if usedSlotIndex == self._right_slot:
			self.__UpdateRightSkill(cd_start=0.0, cd_end=0.0)

	def OnUseSkill(self, usedSlotIndex, coolTime):
		if usedSlotIndex == self._right_slot:
			start, end = nui_slots.cooldown_span(coolTime)
			values = {"cd_start": start, "cd_end": end}
			if skill.IsToggleSkill(self._right_index):
				values["active"] = True
			self.__UpdateRightSkill(**values)
		_refresh_quick_slots()

	def OnActivateSkill(self, usedSlotIndex):
		# Legacy deactivates the right skill here too (uitaskbar.py OnActivateSkill).
		if usedSlotIndex == self._right_slot:
			self.__DeactivateRightSkill()
		_refresh_quick_slots()

	def OnDeactivateSkill(self, usedSlotIndex):
		if usedSlotIndex == self._right_slot:
			self.__DeactivateRightSkill()
		_refresh_quick_slots()

	def OnChangeCurrentSkill(self, skillSlotNumber):
		self.__SetRightSkill(skillSlotNumber)
		self._set(right_skill_shown=True)

	def __SetRightSkill(self, skillSlotNumber):
		"""SkillButton.SetSkill: a skill index of 0 clears the cell and keeps
		the slot number."""
		slot = nui_slots.skill_slot(0, skillSlotNumber)
		self._right_index = player.GetSkillIndex(skillSlotNumber)
		if self._right_index:
			self._right_slot = skillSlotNumber
		self._set(right_skill=[slot])

	def __UpdateRightSkill(self, **values):
		right = self._get("right_skill")
		if not right:
			return
		cell = dict(right[0])
		cell.update(values)
		self._set(right_skill=[cell])

	def __DeactivateRightSkill(self):
		if skill.IsToggleSkill(self._right_index):
			self.__UpdateRightSkill(active=False)

	## QuickSlot: fed from C++ (quickslot.* feeds).
	def RefreshQuickSlot(self):
		_refresh_quick_slots()

	def canAddQuickSlot(self, Type, slotNumber):
		if player.SLOT_TYPE_INVENTORY == Type:
			itemIndex = player.GetItemIndex(slotNumber)
			return item.CanAddToQuickSlotItem(itemIndex)
		return True

	def AddQuickSlot(self, localSlotIndex):
		"""uiTaskBar.TaskBar.AddQuickSlot, the MR-3 swap included."""
		controller = mouseModule.mouseController
		AttachedSlotType = controller.GetAttachedType()
		AttachedSlotNumber = controller.GetAttachedSlotNumber()
		AttachedItemIndex = controller.GetAttachedItemIndex()

		# MR-3: swap when the dragged item, skill or emotion is in the quickslots already.
		if AttachedSlotType != player.SLOT_TYPE_QUICK_SLOT:
			for slotIdx in range(constInfo.QUICKSLOT_MAX_NUM):
				(Type, Position) = player.GetLocalQuickSlot(slotIdx)
				if Type == AttachedSlotType and Position == AttachedSlotNumber:
					player.RequestMoveGlobalQuickSlotToLocalQuickSlot(slotIdx, localSlotIndex)
					controller.DeattachObject()
					self.RefreshQuickSlot()
					return

		if player.SLOT_TYPE_QUICK_SLOT == AttachedSlotType:
			player.RequestMoveGlobalQuickSlotToLocalQuickSlot(AttachedSlotNumber, localSlotIndex)
		elif player.SLOT_TYPE_EMOTION == AttachedSlotType:
			player.RequestAddLocalQuickSlot(localSlotIndex, AttachedSlotType, AttachedItemIndex)
		elif True == self.canAddQuickSlot(AttachedSlotType, AttachedSlotNumber):
			player.RequestAddLocalQuickSlot(localSlotIndex, AttachedSlotType, AttachedSlotNumber)

		controller.DeattachObject()
		self.RefreshQuickSlot()

	def _quick_filled(self, index):
		"""Whether the cell shows something (CSlotWindow's isItem)."""
		slots = self._get("quick_slots") or []
		return 0 <= index < len(slots) and slots[index].get("kind", "") != ""

	def _pick_quick(self, index):
		"""SelectItemQuickSlot's attach, for a cell that holds something."""
		if not self._quick_filled(index):
			return None
		globalQuickSlotIndex = player.LocalQuickSlotIndexToGlobalQuickSlotIndex(index)
		return (player.SLOT_TYPE_QUICK_SLOT, globalQuickSlotIndex, globalQuickSlotIndex, 0)

	def _use_quick(self, index):
		"""UnselectItemQuickSlot with nothing attached."""
		if self._quick_filled(index):
			player.RequestUseLocalQuickSlot(index)

	def _on_pick(self, index):
		self.tooltips.hide()

	## ToolTip
	def OverInItem(self, slotNumber):
		if mouseModule.mouseController.isAttached():
			return

		(Type, Position) = player.GetLocalQuickSlot(slotNumber)

		if player.SLOT_TYPE_INVENTORY == Type:
			self.tooltips.show_inventory_item(Position)

		elif player.SLOT_TYPE_SKILL == Type:
			skillIndex = player.GetSkillIndex(Position)
			if skill.SKILL_TYPE_GUILD == skill.GetSkillType(skillIndex):
				import guild
				skillGrade = 0
				skillLevel = guild.GetSkillLevel(Position)
			else:
				skillGrade = player.GetSkillGrade(Position)
				skillLevel = player.GetSkillLevel(Position)
			self.tooltips.show_skill(Position, skillIndex, skillGrade, skillLevel)

	def OverOutItem(self):
		self.tooltips.hide()

	## Mouse buttons
	def ToggleLeftMouseButtonModeWindow(self):
		self._set(left_open=not self._get("left_open"))

	def ToggleRightMouseButtonModeWindow(self):
		if self._get("right_open"):
			self.CloseSelectSkill()
		else:
			self._set(right_open=True)
			self.OpenSelectSkill()

	def OpenSelectSkill(self):
		self._set(skill_rows=self.__SkillRows())

	def __SkillRows(self):
		"""The picker's rows, as OpenSelectSkill lays them out: per category
		its active skills (no empty slot, no level 0, no standing skill),
		right to left from the right mode button, a row per category that
		has any."""
		rows = []
		for start in SKILL_CATEGORIES:
			slots = []
			for i in range(SKILL_PAGE):
				number = start + i
				skillIndex = player.GetSkillIndex(number)
				if 0 == skillIndex:
					continue
				if 0 == player.GetSkillLevel(number):
					continue
				if skill.IsStandingSkill(skillIndex):
					continue
				slots.append(nui_slots.skill_slot(len(slots), number))
			if slots:
				rows.append({"slots": slots})
		return rows

	def CloseSelectSkill(self, slotIndex=-1):
		had_rows = bool(self._get("skill_rows"))
		self._set(right_open=False, skill_rows=[])
		if had_rows:
			self.tooltips.hide()
		if -1 != slotIndex:
			self._set(right_skill_shown=True)
			player.SetMouseFunc(player.MBT_RIGHT, player.MBF_SKILL)
			player.ChangeCurrentSkillNumberOnly(slotIndex - 1)
		else:
			self._set(right_skill_shown=False)

	def SelectMouseButtonEvent(self, dir, event):
		uiTaskBar.SetMouseButtonSetting(dir, event)

		self.CloseSelectSkill()
		if dir == self.MOUSE_BUTTON_LEFT:
			self._set(left_open=False)
		elif dir == self.MOUSE_BUTTON_RIGHT:
			self._set(right_open=False)

		type = self.NONE
		func = self.NONE
		if self.MOUSE_BUTTON_LEFT == dir:
			type = player.MBT_LEFT
		elif self.MOUSE_BUTTON_RIGHT == dir:
			type = player.MBT_RIGHT

		art = self._MENU_ART.get((dir, event))
		if art is None and event in self._MISSING_BUTTON:
			raise KeyError(self._MISSING_BUTTON[event])

		if self.EVENT_AUTO == event:
			func, tooltip_text = player.MBF_AUTO, "TASKBAR_AUTO"
		elif self.EVENT_MOVE_AND_ATTACK == event:
			func, tooltip_text = player.MBF_SMART, "TASKBAR_ATTACK"
		elif self.EVENT_CAMERA == event:
			func, tooltip_text = player.MBF_CAMERA, "TASKBAR_CAMERA"
		elif self.EVENT_SKILL == event:
			func, tooltip_text = player.MBF_SKILL, "TASKBAR_SKILL"
		else:
			tooltip_text = None

		if art is not None and tooltip_text is not None:
			tip = nui_hud.locale_text(tooltip_text)
			if dir == self.MOUSE_BUTTON_LEFT:
				self._set(left_mode=art, left_tip=tip)
			else:
				self._set(right_mode=art, right_tip=tip)

		player.SetMouseFunc(type, func)

	# --- the board's events -------------------------------------------------------------

	def nui_slot_press(self, grid, index, button):
		if grid == "quick":
			self.drag_quick.press(index, button)
		elif grid == "right" and button == 0:
			right = self._get("right_skill") or []
			if right and right[0].get("kind", "") != "":
				self.ToggleRightMouseButtonModeWindow()

	def nui_slot_release(self, grid, index, button):
		if grid == "quick":
			self.drag_quick.release(index, button)
		elif grid == "right":
			self.drag_right.release(index, button)

	def nui_slot_drop(self, grid, index):
		if grid == "quick":
			self.drag_quick.legacy_drop(index)

	def nui_slot_over(self, grid, index):
		if grid == "quick":
			self.OverInItem(index)
		elif grid == "right" and self._right_index:
			self.tooltips.show_skill_index(self._right_index)

	def nui_slot_out(self, grid, index):
		self.OverOutItem()

	def nui_page(self, step):
		player.SetQuickPage(player.GetQuickPage() + step)

	def nui_toggle_mouse(self, direction):
		if direction == self.MOUSE_BUTTON_LEFT:
			self.ToggleLeftMouseButtonModeWindow()
		elif direction == self.MOUSE_BUTTON_RIGHT:
			self.ToggleRightMouseButtonModeWindow()

	def nui_pick_over(self, skill_slot):
		self.tooltips.show_skill_index(player.GetSkillIndex(skill_slot))

	def nui_button(self, name):
		for eButton, button_name in _BUTTON_NAMES.items():
			if button_name == name:
				event = self.toggleButtonEvents.get(eButton)
				if event:
					event()
				return

	def nui_mall_click(self):
		net.SendChatPacket("/in_game_mall")
		self.HideGift()

