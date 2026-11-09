##
## Interface
##
import sys

import constInfo
import systemSetting
import wndMgr
import chat
import app
import player
import uiTaskBar
import uiCharacter
import uiInventory
import uiExtraInventory
import uiDragonSoul
import uiChat
import uiMessenger
import guild

import ui
import uiHelp
import uiWhisper
import uiPointReset
import uiShop
import uiExchange
import uiSystem
import uiRestart
import uiToolTip
import uiMiniMap
import uiParty
import uiSafebox
import uiGuild
import uiQuest
import uiPrivateShopBuilder
import uiCommon
import uiRefine
import uiEquipmentDialog
import uiGameButton
import uiTip
import uiCubeRenewal
import miniMap
# ACCESSORY_REFINE_ADD_METIN_STONE
import uiselectitem
# END_OF_ACCESSORY_REFINE_ADD_METIN_STONE
# The gaya market (NOVA-10; OLD interfaceModule.py:112-114).
import uiGemShop
import uiChestDrop
import uiSash
## The advanced pet's windows (NOVA-24).
import uiPet
# The offline shop's search, log and decoration windows (NOVA-9, chunk Y2's).
import uiSearchShop
import uiOfflineShopLog
import uiKillRank
import uiMyShopDecoration
import uiSelectSkill
# The switchbot (NOVA-43; OLD interfaceModule.py:90, 417).
import uiSwitchbot
# The dungeon manager and the dungeon ranking (NOVA-25).
import uiTimerWindow
import uiDungeonRank
# The boss info panel and the damage count window (NOVA-27).
import uiBossInfo
import uiDamageCount
import uiScriptLocale

import event
import localeInfo
import nui_windows

IsQBHide = 0
# nova-protocol offline_shop_packets.h EOfflineShopCG: the builder's CREATE;
# every other op's RESULT is the shop window's (NOVA-9).
OFFLINE_SHOP_OP_CREATE = 0
ItemMallTraced = False  # OpenItemMall writes its log line once per session
class Interface(object):
	CHARACTER_STATUS_TAB = 1
	CHARACTER_SKILL_TAB = 2
	
	def __init__(self):
		systemSetting.SetInterfaceHandler(self)
		self.windowOpenPosition = 0
		# The trade window on top (the tradable icon, NOVA-13).
		self.onTopWindow = player.ON_TOP_WND_NONE
		self.dlgWhisperWithoutTarget = None
		self.inputDialog = None
		self.tipBoard = None
		self.bigBoard = None
		# MR-11: Suppress quest button when quest dialog is open to prevent quest button flashing
		self.questButtonSuppressed = False
		# MR-11: -- END OF -- Suppress quest button when quest dialog is open to prevent quest button flashing

		self.wndWeb = None
		self.wndCubeRenewal = None
		self.wndTaskBar = None
		self.wndCharacter = None
		self.wndInventory = None
		self.wndExtraInventory = None
		self.wndExpandedTaskBar = None
		self.wndDragonSoul = None
		self.wndDragonSoulRefine = None
		self.wndChat = None
		self.wndMessenger = None
		self.wndMiniMap = None
		self.wndGuild = None
		self.wndGuildBuilding = None
		self.wndGemShop = None
		self.wndChestDrop = None
		self.wndSashCombine = None
		self.wndSashAbsorption = None
		## The advanced pet's windows (NOVA-24; OLD interfaceModule.py:392-398).
		self.wndPetEggHatch = None
		self.wndPetRefineWindow = None
		self.wndPetEvolutionWindow = None
		self.wndPetInterfaceWindow = None
		self.wndPetWindow = None
		self.wndPetPreviewWindow = None
		self.wndSearchShop = None
		self.wndOfflineShopLog = None
		self.wndMyShopDeco = None
		self.wndSelectSkill = None
		self.wndSwitchbot = None
		# NOVA-29: the kill ranking and the guild war top killers.
		self.wndKillRank = None
		self.wndTopKillers = None
		self.wndTimer = None
		self.wndDungeonRank = None
		self.wndBossInfo = None
		self.wndDamageCount = None

		self.listGMName = {}
		self.wndQuestWindow = {}
		self.wndQuestWindowNewKey = 0
		self.privateShopAdvertisementBoardDict = {}
		self.guildScoreBoardDict = {}
		self.equipmentDialogDict = {}
		event.SetInterfaceWindow(self)

	def __del__(self):
		systemSetting.DestroyInterfaceHandler()
		event.SetInterfaceWindow(None)

	################################
	## Make Windows & Dialogs
	def __MakeUICurtain(self):
		wndUICurtain = ui.Bar("TOP_MOST")
		wndUICurtain.SetSize(wndMgr.GetScreenWidth(), wndMgr.GetScreenHeight())
		wndUICurtain.SetColor(0x77000000)
		wndUICurtain.Hide()
		self.wndUICurtain = wndUICurtain

	def __MakeMessengerWindow(self):
		self.wndMessenger = nui_windows.make("messenger", uiMessenger.MessengerWindow, "nui_messenger.MessengerWindow")

		from _weakref import proxy
		self.wndMessenger.SetWhisperButtonEvent(lambda n,i=proxy(self):i.OpenWhisperDialog(n))
		self.wndMessenger.SetGuildButtonEvent(ui.__mem_func__(self.ToggleGuildWindow))

	def __MakeGuildWindow(self):
		self.wndGuild = nui_windows.make("guild", uiGuild.GuildWindow, "nui_guild.GuildWindow")

	def __MakeChatWindow(self):
		wndChat = nui_windows.make("chat", uiChat.ChatWindow, "nui_chat.ChatWindow")
		
		wndChat.SetSize(wndChat.CHAT_WINDOW_WIDTH, 0)
		wndChat.SetPosition(wndMgr.GetScreenWidth() // 2 - wndChat.CHAT_WINDOW_WIDTH // 2, wndMgr.GetScreenHeight() - wndChat.EDIT_LINE_HEIGHT - 37)
		wndChat.SetHeight(200)
		wndChat.Refresh()
		wndChat.Show()

		self.wndChat = wndChat
		self.wndChat.BindInterface(self)
		self.wndChat.SetSendWhisperEvent(ui.__mem_func__(self.OpenWhisperDialogWithoutTarget))
		self.wndChat.SetOpenChatLogEvent(ui.__mem_func__(self.ToggleChatLogWindow))

	def __PlaceChatAboveTaskBar(self):
		wndChat = getattr(self, "wndChat", None)
		if wndChat is None:
			return
		height = self.wndTaskBar.GetBarHeight()
		wndChat.SetPosition(wndMgr.GetScreenWidth() // 2 - wndChat.CHAT_WINDOW_WIDTH // 2, wndMgr.GetScreenHeight() - wndChat.EDIT_LINE_HEIGHT - height)
		wndChat.Refresh()

	def __MakeTaskBar(self):
		wndTaskBar = nui_windows.make("taskbar", uiTaskBar.TaskBar, "nui_taskbar.TaskBar")
		wndTaskBar.LoadWindow()
		# The NovaUI gift box needs the NovaUI taskbar, which makes it (spec D17).
		if not getattr(wndTaskBar, "NUI_FACADE", False) and nui_windows.is_on("gift-box"):
			nui_windows.refuse("gift-box", "needs the NovaUI taskbar")
		self.wndTaskBar = wndTaskBar
		# The NovaUI bar is not legacy's 37 px: the legacy chat stays above it, also after a theme or scale change.
		if getattr(wndTaskBar, "NUI_FACADE", False) and hasattr(wndTaskBar, "SetBarHeightEvent"):
			wndTaskBar.SetBarHeightEvent(ui.__mem_func__(self.__PlaceChatAboveTaskBar))
			self.__PlaceChatAboveTaskBar()
		self.wndTaskBar.SetToggleButtonEvent(uiTaskBar.TaskBar.BUTTON_CHARACTER, ui.__mem_func__(self.ToggleCharacterWindowStatusPage))
		self.wndTaskBar.SetToggleButtonEvent(uiTaskBar.TaskBar.BUTTON_INVENTORY, ui.__mem_func__(self.ToggleInventoryWindow))
		self.wndTaskBar.SetToggleButtonEvent(uiTaskBar.TaskBar.BUTTON_MESSENGER, ui.__mem_func__(self.ToggleMessenger))
		self.wndTaskBar.SetToggleButtonEvent(uiTaskBar.TaskBar.BUTTON_SYSTEM, ui.__mem_func__(self.ToggleSystemDialog))
		if uiTaskBar.TaskBar.IS_EXPANDED:
			self.wndTaskBar.SetToggleButtonEvent(uiTaskBar.TaskBar.BUTTON_EXPAND, ui.__mem_func__(self.ToggleExpandedButton))
			self.wndExpandedTaskBar = nui_windows.make("expanded-taskbar", uiTaskBar.ExpandedTaskBar, "nui_expanded_taskbar.ExpandedTaskBar")
			self.wndExpandedTaskBar.LoadWindow()
			self.wndExpandedTaskBar.SetToggleButtonEvent(uiTaskBar.ExpandedTaskBar.BUTTON_DRAGON_SOUL, ui.__mem_func__(self.ToggleDragonSoulWindow))

		else:
			self.wndTaskBar.SetToggleButtonEvent(uiTaskBar.TaskBar.BUTTON_CHAT, ui.__mem_func__(self.ToggleChat))
		
		self.wndEnergyBar = None
		import app
		if app.ENABLE_ENERGY_SYSTEM:
			wndEnergyBar = nui_windows.make("energy-bar", uiTaskBar.EnergyBar, "nui_energy_bar.EnergyBar")
			wndEnergyBar.LoadWindow()
			self.wndEnergyBar = wndEnergyBar	

	def __MakeParty(self):
		wndParty = nui_windows.make("party", uiParty.PartyWindow, "nui_party.PartyWindow")
		wndParty.Hide()
		self.wndParty = wndParty

	def __MakeGameButtonWindow(self):
		wndGameButton = nui_windows.make("game-buttons", uiGameButton.GameButtonWindow, "nui_game_buttons.GameButtonWindow")
		wndGameButton.SetTop()
		wndGameButton.Show()
		wndGameButton.SetButtonEvent("STATUS", ui.__mem_func__(self.__OnClickStatusPlusButton))
		wndGameButton.SetButtonEvent("SKILL", ui.__mem_func__(self.__OnClickSkillPlusButton))
		wndGameButton.SetButtonEvent("QUEST", ui.__mem_func__(self.__OnClickQuestButton))
		wndGameButton.SetButtonEvent("HELP", ui.__mem_func__(self.__OnClickHelpButton))
		wndGameButton.SetButtonEvent("BUILD", ui.__mem_func__(self.__OnClickBuildButton))

		self.wndGameButton = wndGameButton

	def __IsChatOpen(self):
		return True
		
	def __MakeWindows(self):
		wndCharacter = nui_windows.make("character", uiCharacter.CharacterWindow, "nui_character.CharacterWindow")
		wndInventory = nui_windows.make("inventory", uiInventory.InventoryWindow, "nui_inventory.InventoryWindow")
		wndInventory.BindInterfaceClass(self)
		# The special inventory (NOVA-16).
		wndExtraInventory = nui_windows.make("extra-inventory", uiExtraInventory.ExtraInventoryWindow, "nui_extra_inventory.ExtraInventoryWindow")
		wndExtraInventory.BindInterfaceClass(self)
		wndExtraInventory.Hide()
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			wndDragonSoul = nui_windows.make("dragon-soul", uiDragonSoul.DragonSoulWindow, "nui_dragon_soul.DragonSoulWindow")	
			wndDragonSoul.BindInterfaceClass(self)
			wndDragonSoulRefine = nui_windows.make("dragon-soul-refine", uiDragonSoul.DragonSoulRefineWindow, "nui_dragon_soul_refine.DragonSoulRefineWindow")
		else:
			wndDragonSoul = None
			wndDragonSoulRefine = None
 
		wndMiniMap = nui_windows.make("minimap", uiMiniMap.MiniMap, "nui_minimap.MiniMap")
		# The NovaUI atlas needs the NovaUI minimap, which makes it (P10 spec D16).
		if not getattr(wndMiniMap, "NUI_FACADE", False) and nui_windows.is_on("atlas"):
			nui_windows.refuse("atlas", "needs the NovaUI minimap")
		wndSafebox = nui_windows.make("safebox", uiSafebox.SafeboxWindow, "nui_safebox.SafeboxWindow")
		
		# ITEM_MALL
		wndMall = nui_windows.make("mall", uiSafebox.MallWindow, "nui_mall.MallWindow")
		self.wndMall = wndMall
		# END_OF_ITEM_MALL

		wndChatLog = nui_windows.make("chat-log", uiChat.ChatLogWindow, "nui_chat_log.ChatLogWindow")
		wndChatLog.BindInterface(self)
		
		self.wndCharacter = wndCharacter
		self.wndInventory = wndInventory
		self.wndExtraInventory = wndExtraInventory
		self.wndDragonSoul = wndDragonSoul
		self.wndDragonSoulRefine = wndDragonSoulRefine
		self.wndMiniMap = wndMiniMap
		self.wndSafebox = wndSafebox
		self.wndChatLog = wndChatLog
		
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.SetDragonSoulRefineWindow(self.wndDragonSoulRefine)
			self.wndDragonSoulRefine.SetInventoryWindows(self.wndInventory, self.wndDragonSoul)
			self.wndInventory.SetDragonSoulRefineWindow(self.wndDragonSoulRefine)
			self.wndExtraInventory.SetDragonSoulRefineWindow(self.wndDragonSoulRefine)

		# The gaya market (NOVA-10), made plainly: the UI session wraps it in
		# nui_windows.make later (spec 4.8).
		self.wndGemShop = nui_windows.make("gem-shop", uiGemShop.GemShopWindow, "nui_gem_shop.GemShopWindow")
		self.wndGemShop.Hide()

		# The chest-drop preview (NOVA-18; OLD interfaceModule.py:758-760).
		self.wndChestDrop = nui_windows.make("chest-drop", uiChestDrop.ChestDropWindow, "nui_chest_drop.ChestDropWindow")
		self.wndChestDrop.Hide()

		# The offline shop's search, log and decoration windows (NOVA-9) are the
		# legacy controllers on NovaUI proxies.
		self.wndSearchShop = nui_windows.make("shop-search", uiSearchShop.SearchShopWindow, "nui_shop_search.SearchShopWindow")
		self.wndSearchShop.BindInterface(self)
		self.wndOfflineShopLog = nui_windows.make("offline-shop-log", uiOfflineShopLog.OfflineShopLogWindow,
		                                          "nui_offline_shop_log.OfflineShopLogWindow")
		self.wndOfflineShopLog.BindInterface(self)
		self.wndMyShopDeco = nui_windows.make("shop-deco", uiMyShopDecoration.MyShopDecorationWindow,
		                                      "nui_shop_deco.MyShopDecorationWindow")
		self.wndMyShopDeco.BindInterface(self)
		# NOVA-37 (OLD interfaceModule.py:752-754).
		self.wndSelectSkill = nui_windows.make("select-skill", uiSelectSkill.SelectSkillWindow, "nui_select_skill.SelectSkillWindow")
		self.wndSelectSkill.LoadWindow()

		# The switchbot (NOVA-43; OLD interfaceModule.py:417): the legacy
		# controller, on NovaUI proxies while the switchbot flag is on.
		self.wndSwitchbot = nui_windows.make("switchbot", uiSwitchbot.SwitchbotWindow, "nui_switchbot.SwitchbotWindow")
		self.wndSwitchbot.Hide()

		# The kill ranking (NOVA-29, OLD interfaceModule.py:780-782) and the guild
		# war top killers (OLD :279-280).
		self.wndKillRank = nui_windows.make("kill-rank", uiKillRank.KillRankWindow, "nui_kill_rank.KillRankWindow")
		self.wndKillRank.LoadWindow()
		self.wndTopKillers = nui_windows.make("guild-war-top", uiGuild.TopWarPlayersDialog,
		                                      "nui_guild_war_top.TopWarPlayersDialog")

	def __MakeDialogs(self):
		self.dlgExchange = nui_windows.make("exchange", uiExchange.ExchangeDialog, "nui_exchange.ExchangeDialog")
		self.dlgExchange.LoadDialog()
		self.dlgExchange.SetCenterPosition()
		self.dlgExchange.Hide()

		# The NovaUI point reset is the dialog kit's question: without the kit
		# it is refused (P11 spec 4.2).
		if nui_windows.is_on("point-reset") and not nui_windows.use("dialogs")[0]:
			nui_windows.refuse("point-reset", "needs the NovaUI dialog kit")
			self.dlgPointReset = uiPointReset.PointResetDialog()
		else:
			self.dlgPointReset = nui_windows.make("point-reset", uiPointReset.PointResetDialog, "nui_point_reset.PointResetDialog")
		self.dlgPointReset.LoadDialog()
		self.dlgPointReset.Hide()

		self.dlgShop = nui_windows.make("shop", uiShop.ShopDialog, "nui_shop.ShopDialog")
		self.dlgShop.LoadDialog()
		self.dlgShop.Hide()

		self.dlgRestart = nui_windows.make("restart", uiRestart.RestartDialog, "nui_restart.RestartDialog")
		self.dlgRestart.LoadDialog()
		self.dlgRestart.Hide()

		self.dlgSystem = nui_windows.make("system-menu", uiSystem.SystemDialog, "nui_system_menu.SystemDialog")
		self.dlgSystem.LoadDialog()
		self.dlgSystem.SetOpenHelpWindowEvent(ui.__mem_func__(self.OpenHelpWindow))
		self.dlgSystem.SetOpenKillRankEvent(ui.__mem_func__(self.OpenKillRank))

		self.dlgSystem.Hide()

		self.dlgPassword = nui_windows.make("safebox", uiSafebox.PasswordDialog, "nui_safebox.PasswordDialog")
		self.dlgPassword.Hide()

		self.hyperlinkItemTooltip = nui_windows.make("tooltips", uiToolTip.HyperlinkItemToolTip, "nui_link_tooltip.HyperlinkItemToolTip")
		self.hyperlinkItemTooltip.Hide()

		self.tooltipItem = nui_windows.make("tooltips", uiToolTip.ItemToolTip, "nui_item_tooltip.ItemToolTip")
		self.tooltipItem.Hide()

		self.tooltipSkill = nui_windows.make("tooltips", uiToolTip.SkillToolTip, "nui_skill_tooltip.SkillToolTip")
		self.tooltipSkill.Hide()

		self.privateShopBuilder = nui_windows.make("private-shop", uiPrivateShopBuilder.PrivateShopBuilder, "nui_private_shop.PrivateShopBuilder")
		self.privateShopBuilder.Hide()

		self.dlgRefineNew = nui_windows.make("refine", uiRefine.RefineDialogNew, "nui_refine.RefineDialogNew")
		self.dlgRefineNew.Hide()

	def __BindTradableWindows(self):
		"""The tradable icon (NOVA-13; OLD interfaceModule.py:362-368,
		438-460, 494-526): the windows that hold inventory items lock their
		cells in both inventories, and the trade windows say which is on
		top, so the inventories mark the items it refuses."""
		for wnd in (self.dlgExchange, self.dlgShop, self.wndSafebox, self.privateShopBuilder):
			wnd.BindInterface(self)

		for wnd in (self.dlgExchange, self.privateShopBuilder, self.dlgRefineNew,
				getattr(self.wndInventory, "attachMetinDialog", None)):
			if not wnd:
				continue
			wnd.SetInven(self.wndInventory, self.wndExtraInventory)
			self.wndInventory.BindWindow(wnd)
			self.wndExtraInventory.BindWindow(wnd)

	def SetOnTopWindow(self, onTopWnd):
		self.onTopWindow = onTopWnd

	def GetOnTopWindow(self):
		return self.onTopWindow

	def RefreshMarkInventoryBag(self):
		for wnd in (self.wndInventory, self.wndExtraInventory):
			if wnd:
				wnd.RefreshMarkSlots()

	def CantTradableItemExchange(self, dstSlotIndex, srcSlotIndex, srcWindow=player.INVENTORY):
		self.dlgExchange.CantTradableItem(dstSlotIndex, srcSlotIndex, srcWindow)

	def ReleaseTradableItemExchange(self, dstSlotIndex):
		self.dlgExchange.ReleaseTradableItem(dstSlotIndex)

	def __MakeHelpWindow(self):
		self.wndHelp = nui_windows.make("help", uiHelp.HelpWindow, "nui_help.HelpWindow")
		self.wndHelp.LoadDialog()
		self.wndHelp.SetCloseEvent(ui.__mem_func__(self.CloseHelpWindow))
		self.wndHelp.Hide()

	def __MakeTipBoard(self):
		self.tipBoard = nui_windows.make("tip-board", uiTip.TipBoard, "nui_tip_board.TipBoard")
		self.tipBoard.Hide()

		self.bigBoard = nui_windows.make("big-board", uiTip.BigBoard, "nui_big_board.BigBoard")
		self.bigBoard.Hide()

	def __MakeWebWindow(self):
		import uiWeb
		self.wndWeb = nui_windows.make("web", uiWeb.WebWindow, "nui_web.WebWindow")
		self.wndWeb.LoadWindow()
		self.wndWeb.Hide()

	def __MakeCubeRenewalWindow(self):
		self.wndCubeRenewal = uiCubeRenewal.CubeRenewalWindow()
		self.wndCubeRenewal.LoadWindow()
		self.wndCubeRenewal.Hide()

	# ACCESSORY_REFINE_ADD_METIN_STONE
	def __MakeItemSelectWindow(self):
		self.wndItemSelect = nui_windows.make("select-item", uiselectitem.SelectItemWindow, "nui_select_item.SelectItemWindow")
		self.wndItemSelect.Hide()
	# END_OF_ACCESSORY_REFINE_ADD_METIN_STONE
				
	## The sash windows (NOVA-20; OLD interfaceModule.py:656-665), made
	## plainly, as the other wave windows: the UI session wraps them.
	def __MakeSashWindow(self):
		self.wndSashCombine = nui_windows.make("sash", uiSash.CombineWindow, "nui_sash.CombineWindow")
		self.wndSashCombine.Hide()

		self.wndSashAbsorption = nui_windows.make("sash", uiSash.AbsorbWindow, "nui_sash.AbsorbWindow")
		self.wndSashAbsorption.LoadWindow()
		self.wndSashAbsorption.Hide()

		if self.wndInventory:
			self.wndInventory.SetSashWindow(self.wndSashCombine, self.wndSashAbsorption)
		## The tradable icon (NOVA-13): their items' cells take no mouse event.
		for wnd in (self.wndSashCombine, self.wndSashAbsorption):
			self.__BindItemHolder(wnd)

	def __BindItemHolder(self, wnd):
		wnd.SetInven(self.wndInventory, self.wndExtraInventory)
		for inventory in (self.wndInventory, self.wndExtraInventory):
			if inventory:
				inventory.BindWindow(wnd)

	## The advanced pet's windows (NOVA-24; OLD interfaceModule.py:392-398),
	## each through the factory with contract 8's id and controller; the
	## preview is a second "pet" window.
	def __MakePetWindows(self):
		self.wndPetEggHatch = nui_windows.make("pet-hatch", uiPet.PetHatchEggWindow, "nui_pet_hatch.PetHatchEggWindow")
		self.wndPetRefineWindow = nui_windows.make("pet-attr-refine", uiPet.PetAttrRefineWindow, "nui_pet_attr_refine.PetAttrRefineWindow")
		self.wndPetEvolutionWindow = nui_windows.make("pet-evolution", uiPet.PetEvolutionWindow, "nui_pet_evolution.PetEvolutionWindow")
		self.wndPetInterfaceWindow = nui_windows.make("pet-mini", uiPet.PetInterfaceWindow, "nui_pet_mini.PetInterfaceWindow")
		self.wndPetWindow = nui_windows.make("pet", uiPet.PetWindow, "nui_pet.PetWindow")
		self.wndPetPreviewWindow = nui_windows.make("pet", uiPet.PetWindow, "nui_pet.PetWindow")

	## The aura level window (NOVA-23), which the game window makes at the
	## server's first GC::AURA (OLD game.py:1224-1230).
	def BindAuraWindow(self, wndAura):
		wndAura.SetItemToolTip(self.tooltipItem)
		self.__BindItemHolder(wndAura)
		if self.wndInventory:
			self.wndInventory.SetAuraWindow(wndAura)
		if self.wndExtraInventory:
			self.wndExtraInventory.SetAuraWindow(wndAura)

	## The boss info panel and the damage count window (NOVA-27; OLD
	## interfaceModule.py:399-400, 503-506). The panel waits hidden for the
	## server's boss list; the damage count opens at its first row.
	def __MakeBossWindows(self):
		self.wndBossInfo = nui_windows.make("boss-info", uiBossInfo.BossInfoWindow, "nui_boss_info.BossInfoWindow")
		self.wndDamageCount = nui_windows.make("damage-count", uiDamageCount.DamageCountWindow, "nui_damage_count.DamageCountWindow")
		self.wndDamageCount.LoadWindow()
		self.wndDamageCount.Hide()

	def ClearBossInfo(self):
		if self.wndBossInfo:
			self.wndBossInfo.ClearBossInfo()

	def AddBossInfo(self, bossVnum, isAlive, timeUntilRespawn):
		if self.wndBossInfo:
			self.wndBossInfo.AddBossInfo(bossVnum, isAlive, timeUntilRespawn)

	def BossInfoLoadComplete(self):
		if self.wndBossInfo:
			self.wndBossInfo.BossInfoLoadComplete()

	## The dungeon manager and the dungeon ranking (NOVA-25; OLD
	## interfaceModule.py:753-757, 785-787, 4199-4209, 4248-4253). The
	## manager's drops panel is made by the manager (uitimerwindow).
	def __MakeDungeonWindows(self):
		uiTimerWindow.reset_session()
		self.wndTimer = nui_windows.make("dungeon-timer", uiTimerWindow.TimerWindow, "nui_dungeon_timer.TimerWindow")
		self.wndTimer.BindInterface(self)
		self.wndTimer.LoadWindow()
		self.wndTimer.Hide()
		self.wndDungeonRank = nui_windows.make("dungeon-rank", uiDungeonRank.DungeonRankWindow, "nui_dungeon_rank.DungeonRankWindow")
		self.wndDungeonRank.LoadWindow()
		self.wndDungeonRank.Hide()

	def OpenTimerWindow(self):
		if self.wndTimer.IsShow():
			self.wndTimer.Close()
		else:
			self.wndTimer.Open()

	def UpdateTimer(self):
		if self.wndTimer:
			self.wndTimer.UpdateTime()

	def SetQuestTime(self, index, time):
		if self.wndTimer:
			self.wndTimer.SetTimeLeft(index, time)

	def QuestTimeReady(self):
		if self.wndTimer:
			self.wndTimer.QuestTimeReady()

	def RefreshDungeonDrops(self):
		if self.wndTimer:
			self.wndTimer.refreshMobList()

	def OpenDungeonRank(self):
		self.wndDungeonRank.Open(-1, -1)

	def RefreshDungeonRank(self, type, dungeonIndex):
		self.wndDungeonRank.RefreshDungeonRank(type, dungeonIndex)

	def SetPersonalDungeonRank(self, rank, name, count, type):
		self.wndDungeonRank.SetPersonalDungeonRank(rank, name, count, type)

	def MakeInterface(self):
		self.__MakeMessengerWindow()
		self.__MakeGuildWindow()
		self.__MakeChatWindow()
		self.__MakeParty()
		self.__MakeWindows()
		self.__MakeSashWindow()
		self.__MakePetWindows()
		self.__MakeDialogs()
		self.__BindTradableWindows()

		self.__MakeUICurtain()
		self.__MakeTaskBar()
		self.__MakeGameButtonWindow()
		self.__MakeHelpWindow()
		self.__MakeTipBoard()
		self.__MakeWebWindow()
		self.__MakeCubeRenewalWindow()
		
		
		# ACCESSORY_REFINE_ADD_METIN_STONE
		self.__MakeItemSelectWindow()
		# END_OF_ACCESSORY_REFINE_ADD_METIN_STONE
		self.__MakeDungeonWindows()
		self.__MakeBossWindows()

		self.questButtonList = []
		self.whisperButtonList = []
		self.whisperUnread = set()
		self.whisperDialogDict = {}
		self.privateShopAdvertisementBoardDict = {}

		self.wndMessenger.InitializeHandler()

		self.wndInventory.SetItemToolTip(self.tooltipItem)
		self.wndExtraInventory.SetItemToolTip(self.tooltipItem)

		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.SetItemToolTip(self.tooltipItem)
			self.wndDragonSoulRefine.SetItemToolTip(self.tooltipItem)

		self.wndSafebox.SetItemToolTip(self.tooltipItem)
		self.wndCubeRenewal.SetItemToolTip(self.tooltipItem)

		# ITEM_MALL
		self.wndMall.SetItemToolTip(self.tooltipItem)
		# END_OF_ITEM_MALL

		self.wndCharacter.SetSkillToolTip(self.tooltipSkill)
		self.wndSelectSkill.SetSkillToolTip(self.tooltipSkill)
		self.wndTaskBar.SetItemToolTip(self.tooltipItem)
		self.wndTaskBar.SetSkillToolTip(self.tooltipSkill)
		self.wndGuild.SetSkillToolTip(self.tooltipSkill)

		# ACCESSORY_REFINE_ADD_METIN_STONE
		self.wndItemSelect.SetItemToolTip(self.tooltipItem)
		# END_OF_ACCESSORY_REFINE_ADD_METIN_STONE

		self.dlgShop.SetItemToolTip(self.tooltipItem)
		self.dlgExchange.SetItemToolTip(self.tooltipItem)
		self.privateShopBuilder.SetItemToolTip(self.tooltipItem)
		self.wndGemShop.SetItemToolTip(self.tooltipItem)
		self.wndSwitchbot.SetItemToolTip(self.tooltipItem)
		self.wndSashCombine.SetItemToolTip(self.tooltipItem)
		self.wndSashAbsorption.SetItemToolTip(self.tooltipItem)
		self.wndTimer.SetToolTip(self.tooltipItem)

		self.__InitWhisper()
		self.DRAGON_SOUL_IS_QUALIFIED = False

	def MakeHyperlinkTooltip(self, hyperlink):
		tokens = hyperlink.split(":")
		if tokens and len(tokens):
			type = tokens[0]
			if "item" == type:
				self.hyperlinkItemTooltip.SetHyperlinkItem(tokens)

	## Make Windows & Dialogs
	################################

	def Close(self):
		if self.dlgWhisperWithoutTarget:
			self.dlgWhisperWithoutTarget.Destroy()
			del self.dlgWhisperWithoutTarget

		if "QuestCurtain" in uiQuest.QuestDialog.__dict__:
			uiQuest.QuestDialog.QuestCurtain.Close()

		if self.wndQuestWindow:
			for key, eachQuestWindow in list(self.wndQuestWindow.items()):
				eachQuestWindow.nextCurtainMode = -1
				eachQuestWindow.CloseSelf()
				eachQuestWindow = None
		self.wndQuestWindow = {}

		if self.wndChat:
			self.wndChat.Destroy()

		if self.wndTaskBar:
			self.wndTaskBar.Destroy()
		
		if self.wndExpandedTaskBar:
			self.wndExpandedTaskBar.Destroy()
			
		if self.wndEnergyBar:
			self.wndEnergyBar.Destroy()

		if self.wndCharacter:
			self.wndCharacter.Destroy()

		if self.wndInventory:
			self.wndInventory.Destroy()

		if self.wndExtraInventory:
			self.wndExtraInventory.Destroy()
			
		if self.wndDragonSoul:
			self.wndDragonSoul.Destroy()

		if self.wndDragonSoulRefine:
			self.wndDragonSoulRefine.Destroy()

		if self.dlgExchange:
			self.dlgExchange.Destroy()

		if self.dlgPointReset:
			self.dlgPointReset.Destroy()

		if self.dlgShop:
			self.dlgShop.Destroy()

		if self.dlgRestart:
			self.dlgRestart.Destroy()

		if self.dlgSystem:
			self.dlgSystem.Destroy()

		if self.dlgPassword:
			self.dlgPassword.Destroy()

		if self.wndMiniMap:
			self.wndMiniMap.Destroy()

		if self.wndSafebox:
			self.wndSafebox.Destroy()
		# A phase that ends with the safebox open gets no CloseSafebox command,
		# and the tooltip module lives on into the next phase (NOVA-16).
		uiToolTip.SetSafeboxOpen(False)

		if self.wndWeb:
			self.wndWeb.Destroy()
			self.wndWeb = None

		if self.wndMall:
			self.wndMall.Destroy()

		if self.wndParty:
			self.wndParty.Destroy()

		if self.wndHelp:
			self.wndHelp.Destroy()

		if self.wndCubeRenewal:
			self.wndCubeRenewal.Destroy()

		if self.wndMessenger:
			self.wndMessenger.Destroy()

		if self.wndGuild:
			self.wndGuild.Destroy()

		if self.privateShopBuilder:
			self.privateShopBuilder.Destroy()

		if self.dlgRefineNew:
			self.dlgRefineNew.Destroy()

		if self.wndGuildBuilding:
			self.wndGuildBuilding.Destroy()

		if self.wndGameButton:
			self.wndGameButton.Destroy()

		# ACCESSORY_REFINE_ADD_METIN_STONE
		if self.wndItemSelect:
			self.wndItemSelect.Destroy()
		# END_OF_ACCESSORY_REFINE_ADD_METIN_STONE

		if self.wndGemShop:
			self.wndGemShop.Destroy()
			self.wndGemShop = None

		if self.wndChestDrop:
			self.wndChestDrop.Destroy()
			self.wndChestDrop = None

		if self.wndSashCombine:
			self.wndSashCombine.Destroy()
			self.wndSashCombine = None

		if self.wndSashAbsorption:
			self.wndSashAbsorption.Destroy()
			self.wndSashAbsorption = None

		## OLD interfaceModule.py:1654-1660, 1685-1691.
		if self.wndPetEggHatch:
			self.wndPetEggHatch.Destroy()
			self.wndPetEggHatch = None
		if self.wndPetRefineWindow:
			self.wndPetRefineWindow.Destroy()
			self.wndPetRefineWindow = None
		if self.wndPetEvolutionWindow:
			self.wndPetEvolutionWindow.Destroy()
			self.wndPetEvolutionWindow = None
		if self.wndPetInterfaceWindow:
			self.wndPetInterfaceWindow.Destroy()
			self.wndPetInterfaceWindow = None
		if self.wndPetWindow:
			self.wndPetWindow.Destroy()
			self.wndPetWindow = None
		if self.wndPetPreviewWindow:
			self.wndPetPreviewWindow.Destroy()
			self.wndPetPreviewWindow = None

		if self.wndSearchShop:
			self.wndSearchShop.Destroy()
			self.wndSearchShop = None

		if self.wndSwitchbot:
			self.wndSwitchbot.Destroy()
			self.wndSwitchbot = None

		if self.wndOfflineShopLog:
			self.wndOfflineShopLog.Destroy()
			self.wndOfflineShopLog = None

		if self.wndKillRank:
			self.wndKillRank.Destroy()
			self.wndKillRank = None

		if self.wndTopKillers:
			self.wndTopKillers.Destroy()
			self.wndTopKillers = None

		if self.wndMyShopDeco:
			self.wndMyShopDeco.Destroy()
			self.wndMyShopDeco = None

		# NOVA-37 (OLD interfaceModule.py:1580).
		if self.wndSelectSkill:
			self.wndSelectSkill.Destroy()
			self.wndSelectSkill = None

		# NOVA-27 (OLD interfaceModule.py:1489-1491, 1661-1662).
		if self.wndBossInfo:
			self.wndBossInfo.Destroy()
			self.wndBossInfo = None

		if self.wndDamageCount:
			self.wndDamageCount.Destroy()
			self.wndDamageCount = None

		# NOVA-25 (OLD interfaceModule.py:1600-1601, 1624-1625).
		if self.wndTimer:
			self.wndTimer.Destroy()
			self.wndTimer = None

		if self.wndDungeonRank:
			self.wndDungeonRank.Destroy()
			self.wndDungeonRank = None

		self.wndChatLog.Destroy()
		for btn in self.questButtonList:
			btn.SetEvent(0)
		for btn in self.whisperButtonList:
			btn.SetEvent(0)
		for dlg in list(self.whisperDialogDict.values()):
			dlg.Destroy()
		for brd in list(self.guildScoreBoardDict.values()):
			brd.Destroy()
		for dlg in list(self.equipmentDialogDict.values()):
			dlg.Destroy()

		del self.wndGuild
		del self.wndMessenger
		del self.wndUICurtain
		del self.wndChat
		del self.wndTaskBar
		if self.wndExpandedTaskBar:
			del self.wndExpandedTaskBar
		del self.wndEnergyBar
		del self.wndCharacter
		del self.wndInventory
		del self.wndExtraInventory
		if self.wndDragonSoul:
			del self.wndDragonSoul
		if self.wndDragonSoulRefine:
			del self.wndDragonSoulRefine
		del self.dlgExchange
		del self.dlgPointReset
		del self.dlgShop
		del self.dlgRestart
		del self.dlgSystem
		del self.dlgPassword
		del self.hyperlinkItemTooltip
		del self.tooltipItem
		del self.tooltipSkill
		del self.wndMiniMap
		del self.wndSafebox
		del self.wndMall
		del self.wndParty
		del self.wndHelp
		del self.wndCubeRenewal
		del self.privateShopBuilder
		del self.inputDialog
		del self.wndChatLog
		del self.dlgRefineNew
		del self.wndGuildBuilding
		del self.wndGameButton
		# The NovaUI boards' documents go with them (spec D26); legacy only drops the reference.
		for board in (self.tipBoard, self.bigBoard):
			if getattr(board, "NUI_FACADE", False):
				board.Destroy()
		del self.tipBoard
		del self.bigBoard
		del self.wndItemSelect

		self.questButtonList = []
		edge = sys.modules.get("nui_edge_buttons")
		if edge is not None:
			edge.close_all()
		self.whisperButtonList = []
		self.whisperUnread = set()
		self.__RefreshWhisperBadge()
		self.whisperDialogDict = {}
		# The NovaUI shop signs share one document, which goes with the last sign.
		signs = sys.modules.get("nui_shop_signs")
		if signs is not None:
			signs.close_all()
		self.privateShopAdvertisementBoardDict = {}
		self.guildScoreBoardDict = {}
		self.equipmentDialogDict = {}

		uiChat.DestroyChatInputSetWindow()

	## Skill
	def OnUseSkill(self, slotIndex, coolTime):
		self.wndCharacter.OnUseSkill(slotIndex, coolTime)
		self.wndTaskBar.OnUseSkill(slotIndex, coolTime)
		self.wndGuild.OnUseSkill(slotIndex, coolTime)

	def OnActivateSkill(self, slotIndex):
		self.wndCharacter.OnActivateSkill(slotIndex)
		self.wndTaskBar.OnActivateSkill(slotIndex)

	def OnDeactivateSkill(self, slotIndex):
		self.wndCharacter.OnDeactivateSkill(slotIndex)
		self.wndTaskBar.OnDeactivateSkill(slotIndex)

	def OnChangeCurrentSkill(self, skillSlotNumber):
		self.wndTaskBar.OnChangeCurrentSkill(skillSlotNumber)

	def	SkillClearCoolTime(self, slotIndex):
		self.wndCharacter.SkillClearCoolTime(slotIndex)
		self.wndTaskBar.SkillClearCoolTime(slotIndex)

	def SelectMouseButtonEvent(self, dir, event):
		self.wndTaskBar.SelectMouseButtonEvent(dir, event)

	## Refresh
	def RefreshAlignment(self):
		self.wndCharacter.RefreshAlignment()

	def RefreshStatus(self):
		self.wndTaskBar.RefreshStatus()
		self.wndCharacter.RefreshStatus()
		self.wndInventory.RefreshStatus()
		if self.wndEnergyBar:
			self.wndEnergyBar.RefreshStatus()
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.RefreshStatus()
		if self.wndCubeRenewal:
			self.wndCubeRenewal.RefreshCost()

	def RefreshStamina(self):
		self.wndTaskBar.RefreshStamina()

	def RefreshSkill(self):
		self.wndCharacter.RefreshSkill()
		self.wndTaskBar.RefreshSkill()

	def RefreshInventory(self):
		self.wndTaskBar.RefreshQuickSlot()
		self.wndInventory.RefreshItemSlot()
		self.wndExtraInventory.RefreshItemSlot()
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.RefreshItemSlot()
		if self.wndCubeRenewal:
			self.wndCubeRenewal.Refresh()

	def RefreshCharacter(self): ## Refresh character face in Character page, full body in Inventory page, etc.
		self.wndCharacter.RefreshCharacter()
		self.wndTaskBar.RefreshQuickSlot()

	def RefreshQuest(self):
		self.wndCharacter.RefreshQuest()

	def RefreshSafebox(self):
		self.wndSafebox.RefreshSafebox()

	# ITEM_MALL
	def RefreshMall(self):
		self.wndMall.RefreshMall()

	def OpenItemMall(self):
		# The item_mall server command opens the item mall's web page, as the
		# system menu's Mall button does (the server answers with its mall
		# command). Legacy's mall page dialog (uishop.py) loaded a uiscript
		# that does not exist, and the load failure exited the client.
		global ItemMallTraced
		if not ItemMallTraced:
			ItemMallTraced = True
			import dbg
			dbg.Tracen("item_mall: opening the mall web page through /in_game_mall")
		import net
		net.SendChatPacket("/in_game_mall")
	# END_OF_ITEM_MALL

	def RefreshMessenger(self):
		self.wndMessenger.RefreshMessenger()

	def RefreshGuildInfoPage(self):
		self.wndGuild.RefreshGuildInfoPage()

	def RefreshGuildBoardPage(self):
		self.wndGuild.RefreshGuildBoardPage()

	def RefreshGuildMemberPage(self):
		self.wndGuild.RefreshGuildMemberPage()

	def RefreshGuildMemberPageGradeComboBox(self):
		self.wndGuild.RefreshGuildMemberPageGradeComboBox()

	def RefreshGuildSkillPage(self):
		self.wndGuild.RefreshGuildSkillPage()

	def RefreshGuildGradePage(self):
		self.wndGuild.RefreshGuildGradePage()

	def DeleteGuild(self):
		self.wndMessenger.ClearGuildMember()
		self.wndGuild.DeleteGuild()

	def OnBlockMode(self, mode):
		self.dlgSystem.OnBlockMode(mode)

	## Calling Functions
	# PointReset
	def OpenPointResetDialog(self):
		self.dlgPointReset.Show()
		self.dlgPointReset.SetTop()

	def ClosePointResetDialog(self):
		self.dlgPointReset.Close()

	# Shop
	def OpenShopDialog(self, vid):
		self.wndInventory.Show()
		self.wndInventory.SetTop()
		self.dlgShop.Open(vid)
		self.dlgShop.SetTop()

	def CloseShopDialog(self):
		self.dlgShop.Close()

	def RefreshShopDialog(self):
		self.dlgShop.Refresh()

	## Offline shop (NOVA-9): the glue between C's callbacks (game.py) and
	## chunk Y2's windows, as the Y1/Y2 contract names them.
	# A visitor's view of an offline shop (GC VIEW): every page.
	def OpenOfflineShopDialog(self, vid):
		self.wndInventory.Show()
		self.wndInventory.SetTop()
		self.dlgShop.Open(vid, multiPage=True)
		self.dlgShop.SetTop()

	# The owner's panel (GC MANAGE): open 1 opens it, 0 refreshes a shown one.
	def OpenOfflineShop(self, open):
		self.dlgShop.OpenOfflineShop(open)

	def UpdateShopLock(self, locked):
		self.dlgShop.UpdateLock(locked)

	def UpdateShopTime(self, secondsLeft):
		self.dlgShop.UpdateTime(secondsLeft)

	def UpdateShopSign(self, sign):
		self.dlgShop.UpdateSign(sign)

	def UpdateShopGold(self, gold):
		self.dlgShop.UpdateGold(gold)

	def OnOfflineShopResult(self, op, code, arg):
		if OFFLINE_SHOP_OP_CREATE == op:
			self.privateShopBuilder.OnOfflineShopResult(op, code, arg)
		else:
			self.dlgShop.OnOfflineShopResult(op, code, arg)

	def OpenOfflineShopLog(self):
		self.wndOfflineShopLog.Open()
		self.wndOfflineShopLog.SetTop()

	def OfflineShopLog(self, rows, page, last):
		self.wndOfflineShopLog.SetData(rows, page, last)

	# The kill ranking (NOVA-29, OLD interfaceModule.py:4239-4246): the system
	# menu's button toggles it (the temporary entry, PRODUCT-DECISIONS NOVA-29
	# Q3, until the extra inventory's button of OLD); the answer refreshes it.
	def OpenKillRank(self):
		if not self.wndKillRank:
			return
		if self.wndKillRank.IsShow():
			self.wndKillRank.Close()
		else:
			self.wndKillRank.Open(-1)

	def RefreshKillRank(self, type):
		if self.wndKillRank:
			self.wndKillRank.RefreshKillRank(type)

	def SetPersonalKillRank(self, rank, name, guildName, count):
		if self.wndKillRank:
			self.wndKillRank.SetPersonalKillRank(rank, name, guildName, count)

	# The guild war top killers (NOVA-29): shown while TAB is held during a war
	# (OLD toggled at the press and at the release, interfaceModule.py:4313).
	def OpenTopKillers(self):
		if self.wndTopKillers and not self.wndTopKillers.IsShow():
			self.wndTopKillers.Open()

	def CloseTopKillers(self):
		if self.wndTopKillers and self.wndTopKillers.IsShow():
			self.wndTopKillers.Close()

	def UpdateTopKillers(self, guildId, name, race, totalDamage, kills, deaths, ping):
		if self.wndTopKillers:
			self.wndTopKillers.Update(guildId, name, race, totalDamage, kills, deaths, ping)

	# The search: the inventory's button toggles it (vnum 0), Ctrl + click on
	# an item opens it on that item (OLD uiInventory.py:1172-1173, 1758-1761).
	def OpenSearchShop(self, vnum=0):
		if not vnum and self.wndSearchShop.IsShow():
			self.wndSearchShop.Close()
			return

		self.wndSearchShop.Open(vnum)
		self.wndSearchShop.SetTop()

	def RefreshSearchShop(self):
		self.wndSearchShop.RefreshItems()

	def OnSearchShopBuyResult(self, code, ownerPid, slot):
		self.wndSearchShop.OnBuyResult(code, ownerPid, slot)

	def OpenSelectSkillWindow(self):
		"""NOVA-37: the letter's button (server command OpenSelectSkillWindow)."""
		self.wndSelectSkill.Open()

	def OpenMyShopDecoWnd(self):
		self.wndMyShopDeco.Open()
		self.wndMyShopDeco.SetTop()

	# GC CONFIG: the inventory's shop and search entries show only while the
	# server's offline shop is on (shop.GetConfig(), C's copy of CONFIG).
	def OnOfflineShopConfig(self):
		import shop
		config = shop.GetConfig()
		self.wndInventory.ShowOfflineShopButtons(isinstance(config, dict) and bool(config.get("enabled")))

	# GC HIDE_SHOPS: the game options show the server's state (M5); a window
	# made later reads it when it is made.
	def OnOfflineShopHideShops(self, hidden):
		gameOptionDlg = getattr(self.dlgSystem, "gameOptionDlg", None)
		refreshHideShops = getattr(gameOptionDlg, "RefreshHideShops", None)
		if refreshHideShops:
			refreshHideShops()

	# GC::BUFFI_HIDE (NOVA-38): the game options show the server's /hide_buffi
	# state (player.IsHideBuffi); a window made later reads it when it is made.
	def OnBuffiHide(self, hidden):
		gameOptionDlg = getattr(self.dlgSystem, "gameOptionDlg", None)
		refreshHideBuffi = getattr(gameOptionDlg, "RefreshHideBuffi", None)
		if refreshHideBuffi:
			refreshHideBuffi()

	## Quest
	def OpenCharacterWindowQuestPage(self):
		self.wndCharacter.Show()
		self.wndCharacter.SetState("QUEST")

	def OpenQuestWindow(self, skin, idx):

		wnds = ()

		q = nui_windows.make("quest", uiQuest.QuestDialog, "nui_quest.QuestDialog", skin, idx)
		q.SetWindowName("QuestWindow" + str(idx))
		q.Show()
		if skin:
			q.Lock()
			wnds = self.__HideWindows()

			# UNKNOWN_UPDATE
			q.AddOnDoneEvent(lambda tmp_self, args=wnds: self.__ShowWindows(args))
			# END_OF_UNKNOWN_UPDATE

		if skin:
			q.AddOnCloseEvent(q.Unlock)
		q.AddOnCloseEvent(lambda key = self.wndQuestWindowNewKey:ui.__mem_func__(self.RemoveQuestDialog)(key))
		self.wndQuestWindow[self.wndQuestWindowNewKey] = q

		self.wndQuestWindowNewKey = self.wndQuestWindowNewKey + 1

		# END_OF_UNKNOWN_UPDATE
		
	def RemoveQuestDialog(self, key):
		del self.wndQuestWindow[key]

	## Exchange
	def StartExchange(self):
		self.dlgExchange.OpenDialog()
		self.dlgExchange.Refresh()

	def EndExchange(self):
		self.dlgExchange.CloseDialog()
		# Completed or canceled, the trade's source cells take the mouse again
		# and nothing is on top (the legacy CloseDialog does both; a NovaUI
		# exchange's may not).
		self.dlgExchange.ReleaseLockedItems()
		if self.onTopWindow == player.ON_TOP_WND_EXCHANGE:
			self.SetOnTopWindow(player.ON_TOP_WND_NONE)
			self.RefreshMarkInventoryBag()

	def RefreshExchange(self):
		self.dlgExchange.Refresh()

	## Party
	def AddPartyMember(self, pid, name):
		self.wndParty.AddPartyMember(pid, name)

		self.__ArrangeQuestButton()

	def UpdatePartyMemberInfo(self, pid):
		self.wndParty.UpdatePartyMemberInfo(pid)

	def RemovePartyMember(self, pid):
		self.wndParty.RemovePartyMember(pid)

		## Quest position adjustment
		self.__ArrangeQuestButton()

	def LinkPartyMember(self, pid, vid):
		self.wndParty.LinkPartyMember(pid, vid)

	def UnlinkPartyMember(self, pid):
		self.wndParty.UnlinkPartyMember(pid)

	def UnlinkAllPartyMember(self):
		self.wndParty.UnlinkAllPartyMember()

	def ExitParty(self):
		self.wndParty.ExitParty()

		## Quest position adjustment
		self.__ArrangeQuestButton()

	def PartyHealReady(self):
		self.wndParty.PartyHealReady()

	def ChangePartyParameter(self, distributionMode):
		self.wndParty.ChangePartyParameter(distributionMode)

	## Safebox
	def AskSafeboxPassword(self):
		if self.wndSafebox.IsShow():
			return

		# SAFEBOX_PASSWORD
		self.dlgPassword.SetTitle(localeInfo.PASSWORD_TITLE)
		self.dlgPassword.SetSendMessage("/safebox_password ")
		# END_OF_SAFEBOX_PASSWORD

		self.dlgPassword.ShowDialog()

	def OpenSafeboxWindow(self, size):
		self.dlgPassword.CloseDialog()
		self.wndSafebox.ShowWindow(size)
		uiToolTip.SetSafeboxOpen(True)

	def RefreshSafeboxMoney(self):
		self.wndSafebox.RefreshSafeboxMoney()

	def CommandCloseSafebox(self):
		self.wndSafebox.CommandCloseSafebox()
		uiToolTip.SetSafeboxOpen(False)

	def IsSafeboxOpen(self):
		"""Whether the safebox window shows (NEW's safebox module has no
		IsOpen, OLD's did): the item windows' Shift + right-click."""
		return bool(self.wndSafebox and self.wndSafebox.IsShow())

	# ITEM_MALL
	def AskMallPassword(self):
		if self.wndMall.IsShow():
			return
		self.dlgPassword.SetTitle(localeInfo.MALL_PASSWORD_TITLE)
		self.dlgPassword.SetSendMessage("/mall_password ")
		self.dlgPassword.ShowDialog()

	def OpenMallWindow(self, size):
		self.dlgPassword.CloseDialog()
		self.wndMall.ShowWindow(size)

	def CommandCloseMall(self):
		self.wndMall.CommandCloseMall()
	# END_OF_ITEM_MALL

	## Guild
	def OnStartGuildWar(self, guildSelf, guildOpp):
		self.wndGuild.OnStartGuildWar(guildSelf, guildOpp)

		guildWarScoreBoard = nui_windows.make("guild-war", uiGuild.GuildWarScoreBoard, "nui_guild_war.GuildWarScoreBoard")
		guildWarScoreBoard.Open(guildSelf, guildOpp)
		guildWarScoreBoard.Show()
		self.guildScoreBoardDict[uiGuild.GetGVGKey(guildSelf, guildOpp)] = guildWarScoreBoard
		if getattr(self, "wndTopKillers", None):
			self.wndTopKillers.BeginWar(guildSelf, guildOpp)

	def OnEndGuildWar(self, guildSelf, guildOpp):
		self.wndGuild.OnEndGuildWar(guildSelf, guildOpp)

		key = uiGuild.GetGVGKey(guildSelf, guildOpp)

		if key not in self.guildScoreBoardDict:
			return

		self.guildScoreBoardDict[key].Destroy()
		del self.guildScoreBoardDict[key]
		if getattr(self, "wndTopKillers", None):
			self.wndTopKillers.EndWar()

	# GUILDWAR_MEMBER_COUNT
	def UpdateMemberCount(self, gulidID1, memberCount1, guildID2, memberCount2):
		key = uiGuild.GetGVGKey(gulidID1, guildID2)

		if key not in self.guildScoreBoardDict:
			return

		self.guildScoreBoardDict[key].UpdateMemberCount(gulidID1, memberCount1, guildID2, memberCount2)
	# END_OF_GUILDWAR_MEMBER_COUNT

	def OnRecvGuildWarPoint(self, gainGuildID, opponentGuildID, point):
		key = uiGuild.GetGVGKey(gainGuildID, opponentGuildID)
		if key not in self.guildScoreBoardDict:
			return

		guildBoard = self.guildScoreBoardDict[key]
		guildBoard.SetScore(gainGuildID, opponentGuildID, point)
		if getattr(self, "wndTopKillers", None):
			self.wndTopKillers.SetScore(gainGuildID, point)

	## PK Mode
	def OnChangePKMode(self):
		self.wndCharacter.RefreshAlignment()
		self.dlgSystem.OnChangePKMode()

	## Refine
	def OpenRefineDialog(self, targetItemPos, nextGradeItemVnum, cost, prob, type):
		self.dlgRefineNew.Open(targetItemPos, nextGradeItemVnum, cost, prob, type)

	def AppendMaterialToRefineDialog(self, vnum, count):
		self.dlgRefineNew.AppendMaterial(vnum, count)

	## Show & Hide
	def ShowDefaultWindows(self):
		self.wndTaskBar.Show()
		self.wndMiniMap.Show()
		self.wndMiniMap.ShowMiniMap()
		if self.wndEnergyBar:
			self.wndEnergyBar.Show()

	def ShowAllWindows(self):
		self.wndTaskBar.Show()
		self.wndCharacter.Show()
		self.wndInventory.Show()
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.Show()
			self.wndDragonSoulRefine.Show()
		self.wndChat.Show()
		self.wndMiniMap.Show()
		if self.wndEnergyBar:
			self.wndEnergyBar.Show()
		if self.wndExpandedTaskBar:
			self.wndExpandedTaskBar.Show()
			self.wndExpandedTaskBar.SetTop()
		# NOVA-27 (OLD interfaceModule.py:2664-2665), only with a boss list:
		# OLD showed the empty panel on a map without bosses.
		wndBossInfo = getattr(self, "wndBossInfo", None)
		if wndBossInfo and wndBossInfo.HasBossInfo():
			wndBossInfo.Show()

	def HideAllWindows(self):
		if self.wndTaskBar:
			self.wndTaskBar.Hide()

		# NOVA-27 (OLD interfaceModule.py:2743-2744).
		if getattr(self, "wndBossInfo", None):
			self.wndBossInfo.Hide()

		if self.wndEnergyBar:
			self.wndEnergyBar.Hide()

		if self.wndCharacter:
			self.wndCharacter.Hide()

		if self.wndInventory:
			self.wndInventory.Hide()

		if self.wndExtraInventory:
			self.wndExtraInventory.Hide()
			
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.Hide()
			self.wndDragonSoulRefine.Hide()

		if self.wndChat:
			self.wndChat.Hide()

		if self.wndMiniMap:
			self.wndMiniMap.Hide()

		if self.wndMessenger:
			self.wndMessenger.Hide()

		if self.wndGuild:
			self.wndGuild.Hide()
			
		if self.wndExpandedTaskBar:
			self.wndExpandedTaskBar.Hide()

		## OLD interfaceModule.py:2761-2762 (NOVA-9).
		if self.wndMyShopDeco:
			self.wndMyShopDeco.Hide()

		## NOVA-37: the select skill window goes with the others.
		if getattr(self, "wndSelectSkill", None):
			self.wndSelectSkill.Hide()

		## The advanced pet's windows (NOVA-24; OLD interfaceModule.py:2735-2741).
		for name in ("wndPetEggHatch", "wndPetRefineWindow", "wndPetEvolutionWindow", "wndPetInterfaceWindow",
					 "wndPetWindow", "wndPetPreviewWindow"):
			wnd = getattr(self, name, None)
			if wnd:
				wnd.Hide()
 

	def ShowMouseImage(self):
		self.wndTaskBar.ShowMouseImage()

	def HideMouseImage(self):
		self.wndTaskBar.HideMouseImage()

	def ToggleChat(self):
		if True == self.wndChat.IsEditMode():
			self.wndChat.CloseChat()
		else:
			# Chat input disabled when webpage is open
			if self.wndWeb and self.wndWeb.IsShow():
				pass
			else:
				self.wndChat.OpenChat()

	def IsOpenChat(self):
		return self.wndChat.IsEditMode()

	def SetChatFocus(self):
		self.wndChat.SetChatFocus()

	def OpenRestartDialog(self):
		self.dlgRestart.OpenDialog()
		self.dlgRestart.SetTop()

	def CloseRestartDialog(self):
		self.dlgRestart.Close()

	def ToggleSystemDialog(self):
		if False == self.dlgSystem.IsShow():
			self.dlgSystem.OpenDialog()
			self.dlgSystem.SetTop()
		else:
			self.dlgSystem.Close()

	def OpenSystemDialog(self):
		self.dlgSystem.OpenDialog()
		self.dlgSystem.SetTop()

	def ToggleMessenger(self):
		if self.wndMessenger.IsShow():
			self.wndMessenger.Hide()
		else:
			self.wndMessenger.SetTop()
			self.wndMessenger.Show()

	def ToggleMiniMap(self):
		if app.IsPressed(app.DIK_LSHIFT) or app.IsPressed(app.DIK_RSHIFT):
			if False == self.wndMiniMap.isShowMiniMap():
				self.wndMiniMap.ShowMiniMap()
				self.wndMiniMap.SetTop()
			else:
				self.wndMiniMap.HideMiniMap()

		else:
			self.wndMiniMap.ToggleAtlasWindow()

	def PressMKey(self):
		if app.IsPressed(app.DIK_LALT) or app.IsPressed(app.DIK_RALT):
			self.ToggleMessenger()

		else:
			self.ToggleMiniMap()

	def SetMapName(self, mapName):
		self.wndMiniMap.SetMapName(mapName)

	def MiniMapScaleUp(self):
		self.wndMiniMap.ScaleUp()

	def MiniMapScaleDown(self):
		self.wndMiniMap.ScaleDown()

	def ToggleCharacterWindow(self, state):
		if False == player.IsObserverMode():
			if False == self.wndCharacter.IsShow():
				self.OpenCharacterWindowWithState(state)
			else:
				if state == self.wndCharacter.GetState():
					self.wndCharacter.OverOutItem()
					self.wndCharacter.Hide()
				else:
					self.wndCharacter.SetState(state)

	def OpenCharacterWindowWithState(self, state):
		if False == player.IsObserverMode():
			self.wndCharacter.SetState(state)
			self.wndCharacter.Show()
			self.wndCharacter.SetTop()

	def ToggleCharacterWindowStatusPage(self):
		self.ToggleCharacterWindow("STATUS")

	def ToggleInventoryWindow(self):
		if False == player.IsObserverMode():
			if False == self.wndInventory.IsShow():
				self.wndInventory.Show()
				self.wndInventory.SetTop()
			else:
				self.wndInventory.OverOutItem()
				self.wndInventory.Close()
				# The special inventory goes with the inventory (NOVA-16).
				if self.wndExtraInventory and self.wndExtraInventory.IsShow():
					self.wndExtraInventory.OverOutItem()
					self.wndExtraInventory.Close()

	## Key P (NOVA-24; OLD interfaceModule.py:4419-4424).
	def TogglePetWindow(self):
		if self.wndPetWindow.IsShow():
			self.wndPetWindow.Close()
		else:
			self.wndPetWindow.Open()

	## Key Tab (NOVA-24): OLD's exe asked the shown windows, topmost first,
	## until one's OnPressTabKey answered True (CWindowManager::RunPressTabKey);
	## NEW's exe has no such walk, so the game window asks these. Only the
	## window whose item the pointer is over answers.
	def PressTabKey(self):
		for name in ("wndInventory", "wndExtraInventory", "dlgExchange", "dlgShop", "wndSearchShop"):
			wnd = getattr(self, name, None)
			if wnd and wnd.IsShow() and getattr(wnd, "OnPressTabKey", None) and wnd.OnPressTabKey():
				return True
		return False

	def ToggleExtraInventoryWindow(self):
		"""Key U and the inventory's button (NOVA-16)."""
		if False == player.IsObserverMode():
			if False == self.wndExtraInventory.IsShow():
				self.wndExtraInventory.Open()
			else:
				self.wndExtraInventory.OverOutItem()
				self.wndExtraInventory.Close()
	
	def ToggleExpandedButton(self):
		if False == player.IsObserverMode():
			if False == self.wndExpandedTaskBar.IsShow():
				self.wndExpandedTaskBar.Show()
				self.wndExpandedTaskBar.SetTop()
			else:
				self.wndExpandedTaskBar.Close()
	
	# Dragon soul
	def DragonSoulActivate(self, deck):
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.ActivateDragonSoulByExtern(deck)

	def DragonSoulDeactivate(self):
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoul.DeactivateDragonSoul()

	def Highligt_Item(self, inven_type, inven_pos):
		if player.DRAGON_SOUL_INVENTORY == inven_type:
			if app.ENABLE_DRAGON_SOUL_SYSTEM:
				self.wndDragonSoul.HighlightSlot(inven_pos)

	def DragonSoulGiveQuilification(self):
		self.DRAGON_SOUL_IS_QUALIFIED = True
		self.wndExpandedTaskBar.SetToolTipText(uiTaskBar.ExpandedTaskBar.BUTTON_DRAGON_SOUL, uiScriptLocale.TASKBAR_DRAGON_SOUL)

	def ToggleDragonSoulWindow(self):
		if False == player.IsObserverMode():
			if app.ENABLE_DRAGON_SOUL_SYSTEM:
				if False == self.wndDragonSoul.IsShow():
					if self.DRAGON_SOUL_IS_QUALIFIED:
						self.wndDragonSoul.Show()
					else:
						try:
							self.wndPopupDialog.SetText(localeInfo.DRAGON_SOUL_UNQUALIFIED)
							self.wndPopupDialog.Open()
						except:
							self.wndPopupDialog = uiCommon.PopupDialog()
							self.wndPopupDialog.SetText(localeInfo.DRAGON_SOUL_UNQUALIFIED)
							self.wndPopupDialog.Open()
				else:
					self.wndDragonSoul.Close()
		
	def ToggleDragonSoulWindowWithNoInfo(self):
		if False == player.IsObserverMode():
			if app.ENABLE_DRAGON_SOUL_SYSTEM:
				if False == self.wndDragonSoul.IsShow():
					if self.DRAGON_SOUL_IS_QUALIFIED:
						self.wndDragonSoul.Show()
				else:
					self.wndDragonSoul.Close()
				
	def FailDragonSoulRefine(self, reason, inven_type, inven_pos):
		if False == player.IsObserverMode():
			if app.ENABLE_DRAGON_SOUL_SYSTEM:
				if True == self.wndDragonSoulRefine.IsShow():
					self.wndDragonSoulRefine.RefineFail(reason, inven_type, inven_pos)
 
	def SucceedDragonSoulRefine(self, inven_type, inven_pos):
		if False == player.IsObserverMode():
			if app.ENABLE_DRAGON_SOUL_SYSTEM:
				if True == self.wndDragonSoulRefine.IsShow():
					self.wndDragonSoulRefine.RefineSucceed(inven_type, inven_pos)
 
	def OpenDragonSoulRefineWindow(self):
		if False == player.IsObserverMode():
			if app.ENABLE_DRAGON_SOUL_SYSTEM:
				if False == self.wndDragonSoulRefine.IsShow():
					self.wndDragonSoulRefine.Show()
					if None != self.wndDragonSoul:
						if False == self.wndDragonSoul.IsShow():
							self.wndDragonSoul.Show()

	def CloseDragonSoulRefineWindow(self):
		if False == player.IsObserverMode():
			if app.ENABLE_DRAGON_SOUL_SYSTEM:
				if True == self.wndDragonSoulRefine.IsShow():
					self.wndDragonSoulRefine.Close()

	# Dragon soul end
	
	def ToggleGuildWindow(self):
		if not self.wndGuild.IsShow():
			if self.wndGuild.CanOpen():
				self.wndGuild.Open()
			else:
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.GUILD_YOU_DO_NOT_JOIN)
		else:
			self.wndGuild.OverOutItem()
			self.wndGuild.Hide()

	def ToggleChatLogWindow(self):
		if self.wndChatLog.IsShow():
			self.wndChatLog.Hide()
		else:
			self.wndChatLog.Show()

	def CheckGameButton(self):
		if self.wndGameButton:
			self.wndGameButton.CheckGameButton()

	def __OnClickStatusPlusButton(self):
		self.ToggleCharacterWindow("STATUS")

	def __OnClickSkillPlusButton(self):
		self.ToggleCharacterWindow("SKILL")

	def __OnClickQuestButton(self):
		self.ToggleCharacterWindow("QUEST")

	def __OnClickHelpButton(self):
		player.SetPlayTime(1)
		self.CheckGameButton()
		self.OpenHelpWindow()

	def __OnClickBuildButton(self):
		self.BUILD_OpenWindow()

	def OpenHelpWindow(self):
		# The NovaUI help's scrim is its curtain: a TOP_MOST bar would draw
		# above every NovaUI document.
		if not getattr(self.wndHelp, "NUI_FACADE", False):
			self.wndUICurtain.Show()
		self.wndHelp.Open()

	def CloseHelpWindow(self):
		if not getattr(self.wndHelp, "NUI_FACADE", False):
			self.wndUICurtain.Hide()
		self.wndHelp.Close()

	def OpenWebWindow(self, url):
		self.wndWeb.Open(url)

		# Close chat when opening webpage
		self.wndChat.CloseChat()

	# show GIFT
	def ShowGift(self):
		self.wndTaskBar.ShowGift()
	    	
	def CloseWbWindow(self):
		self.wndWeb.Close()

	# The server sent the cube's recipes (the window has them already) or closed the cube.
	def BINARY_CUBE_RENEWAL_OPEN(self):
		if self.wndCubeRenewal:
			self.wndCubeRenewal.Open()

	def BINARY_CUBE_RENEWAL_CLOSE(self):
		if self.wndCubeRenewal:
			self.wndCubeRenewal.BINARY_CUBE_RENEWAL_CLOSE()

	def __HideWindows(self):
		hideWindows = self.wndTaskBar,\
						self.wndCharacter,\
						self.wndInventory,\
						self.wndMiniMap,\
						self.wndGuild,\
						self.wndMessenger,\
						self.wndChat,\
						self.wndParty,\
						self.wndGameButton,

		if self.wndEnergyBar:
			hideWindows += self.wndEnergyBar,
 			
		if self.wndExpandedTaskBar:
			hideWindows += self.wndExpandedTaskBar,
 			
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			hideWindows += self.wndDragonSoul,\
						self.wndDragonSoulRefine,

		## OLD interfaceModule.py:3369-3370 (NOVA-9). getattr: nui_quest_test
		## and nui_guild_building_test run this method over an Interface
		## stand-in that has only the HUD windows.
		if getattr(self, "wndMyShopDeco", None):
			hideWindows += self.wndMyShopDeco,
		## NOVA-37 (OLD interfaceModule.py:1594).
		if getattr(self, "wndSelectSkill", None):
			hideWindows += self.wndSelectSkill,
		## OLD interfaceModule.py:3381-3382 (NOVA-18).
		if getattr(self, "wndChestDrop", None):
			hideWindows += self.wndChestDrop,

		## The switchbot (NOVA-43; OLD interfaceModule.py:3384-3385).
		if getattr(self, "wndSwitchbot", None):
			hideWindows += self.wndSwitchbot,

		## The advanced pet's windows (NOVA-24; OLD interfaceModule.py:3358-3364).
		if getattr(self, "wndPetWindow", None):
			hideWindows += self.wndPetEggHatch,
			hideWindows += self.wndPetRefineWindow,
			hideWindows += self.wndPetEvolutionWindow,
			hideWindows += self.wndPetInterfaceWindow,
			hideWindows += self.wndPetWindow,
			hideWindows += self.wndPetPreviewWindow,

		## NOVA-25 (OLD interfaceModule.py:3378-3379).
		if getattr(self, "wndTimer", None):
			hideWindows += self.wndTimer,

		## NOVA-27 (OLD interfaceModule.py:3366-3367).
		if getattr(self, "wndBossInfo", None):
			hideWindows += self.wndBossInfo,

		hideWindows = [x for x in hideWindows if x.IsShow()]

		list([x.Hide() for x in hideWindows])

		import sys

		# MR-11: Suppress quest button when quest dialog is open to prevent quest button flashing
		self.questButtonSuppressed = True
		# MR-11: -- END OF -- Suppress quest button when quest dialog is open to prevent quest button flashing

		self.HideAllQuestButton()
		self.HideAllWhisperButton()

		if self.wndChat.IsEditMode():
			self.wndChat.CloseChat()

		return hideWindows

	def __ShowWindows(self, wnds):
		import sys

		list([x.Show() for x in wnds])

		# MR-11: Suppress quest button when quest dialog is open to prevent quest button flashing
		self.questButtonSuppressed = False
		# MR-11: -- END OF -- Suppress quest button when quest dialog is open to prevent quest button flashing

		global IsQBHide

		if not IsQBHide:
			self.ShowAllQuestButton()
		else:
			self.HideAllQuestButton()

		self.ShowAllWhisperButton()

	def BINARY_OpenAtlasWindow(self):
		if self.wndMiniMap:
			self.wndMiniMap.ShowAtlas()

	def BINARY_SetObserverMode(self, flag):
		self.wndGameButton.SetObserverMode(flag)

	# ACCESSORY_REFINE_ADD_METIN_STONE
	def BINARY_OpenSelectItemWindow(self):
		self.wndItemSelect.Open()
	# END_OF_ACCESSORY_REFINE_ADD_METIN_STONE

	## The gaya cut's stone picker (NOVA-10): C's [SELECT_ITEM_EX max_grade;n]
	## (OLD's uiSelectItemEx: stones up to the server's grade, open between
	## cuts). The alchemist's picker, with two more arguments.
	def BINARY_OpenSelectItemWindowEx(self, maxGrade):
		self.wndItemSelect.Open(maxGrade=maxGrade, stayOpen=True)

	#####################################################################################
	### Sash (NOVA-20; OLD interfaceModule.py:3270-3303) ###

	def ActSash(self, iAct, bWindow):
		if bWindow:
			wndSash = self.wndSashCombine
		else:
			wndSash = self.wndSashAbsorption

		if iAct == 1:
			if not wndSash.IsOpened():
				wndSash.Open()

			if not self.wndInventory.IsShow():
				self.wndInventory.Show()
		elif iAct == 2:
			if wndSash.IsOpened():
				wndSash.Close()
		elif iAct == 3 or iAct == 4:
			if wndSash.IsOpened():
				wndSash.Refresh(iAct)
		else:
			return

		self.wndInventory.RefreshBagSlotWindow()

	#####################################################################################
	### Gaya market (NOVA-10; OLD interfaceModule.py:2026-2033) ###

	def OpenGemShop(self):
		self.wndGemShop.Open()

	def RefreshGemShop(self):
		self.wndGemShop.RefreshGemShop()

	def CloseGemShop(self):
		self.wndGemShop.Close()

	#####################################################################################
	### Chest-drop preview (NOVA-18; OLD uiInventory.py:1201-1208, game.py:1173-1179) ###

	def OpenChestDrop(self, vnum):
		"""Asks the server for a chest's rows once a session, then opens the
		window on what is known (OLD's Shift press). False: no chest."""
		if not self.wndChestDrop or not uiChestDrop.request(vnum):
			return False
		self.wndChestDrop.Open(vnum)
		return True

	def OpenHoveredChestDrop(self):
		"""The Shift press: the chest under the pointer in the inventory, the
		special inventory or a shop (OLD's OnPressLeftShiftKey of each)."""
		return self.OpenChestDrop(uiChestDrop.hovered_vnum())

	def RefreshChestDrop(self, vnum):
		"""The server's answer (OLD's BINARY_RefreshChestDropInfo)."""
		if self.wndChestDrop:
			self.wndChestDrop.Refresh(vnum)

	#####################################################################################
	### Switchbot (NOVA-43; OLD interfaceModule.py:3099-3111) ###

	def ToggleSwitchbotWindow(self):
		if not self.wndSwitchbot:
			return
		if self.wndSwitchbot.IsShow():
			self.wndSwitchbot.Close()
		else:
			self.wndSwitchbot.Open()

	def RefreshSwitchbotWindow(self):
		if self.wndSwitchbot and self.wndSwitchbot.IsShow():
			self.wndSwitchbot.RefreshSwitchbotWindow()

	def RefreshSwitchbotItem(self, slot):
		if self.wndSwitchbot and self.wndSwitchbot.IsShow():
			self.wndSwitchbot.RefreshSwitchbotItem(slot)

	#####################################################################################
	### Private Shop ###

	## The offline shop's builder (NOVA-9: GC MANAGE without a shop, through
	## game.BINARY_OfflineShopBuilderOpen, or the OpenPrivateShop command).
	## A new shop starts with the default decoration (OLD interfaceModule.py:
	## 3494-3495), and Y2's deco button opens the decoration window.
	def OpenPrivateShopInputNameDialog(self):
		#if player.IsInSafeArea():
		#	chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.CANNOT_OPEN_PRIVATE_SHOP_IN_SAFE_AREA)
		#	return

		uiPrivateShopBuilder.SHOP_DECO = 0
		uiPrivateShopBuilder.SHOP_STYLE = 0

		inputDialog = uiCommon.InputDialog()
		inputDialog.SetTitle(localeInfo.PRIVATE_SHOP_INPUT_NAME_DIALOG_TITLE)
		inputDialog.SetMaxLength(32)
		inputDialog.SetAcceptEvent(ui.__mem_func__(self.OpenPrivateShopBuilder))
		inputDialog.SetCancelEvent(ui.__mem_func__(self.CancelPrivateShopInputNameDialog))
		decoButton = getattr(inputDialog, "decoButton", None)
		if decoButton:
			decoButton.SetEvent(ui.__mem_func__(self.OpenMyShopDecoWnd))
			decoButton.Show()
		inputDialog.Open()
		self.inputDialog = inputDialog

	def ClosePrivateShopInputNameDialog(self):
		self.inputDialog = None
		return True

	## Closing the name dialog ends the server's builder session (LEAVE,
	## spec 3.4.2), which MANAGE without a shop opened.
	def CancelPrivateShopInputNameDialog(self):
		import net
		net.SendOfflineShopLeavePacket()
		return self.ClosePrivateShopInputNameDialog()

	def OpenPrivateShopBuilder(self):

		if not self.inputDialog:
			return True

		if not len(self.inputDialog.GetText()):
			return True

		self.privateShopBuilder.Open(self.inputDialog.GetText())
		self.ClosePrivateShopInputNameDialog()
		return True

	## style (NOVA-9): the sign's decoration; 0 is today's board, a decorated
	## one Y2's title bar. A sign shown again takes its new title where the
	## board's class has UpdateTitle (NovaUI's ShopSign has none yet: it is
	## made again, as today).
	def AppearPrivateShop(self, vid, text, style=0):
		board = self.privateShopAdvertisementBoardDict.get(vid)
		if board and getattr(type(board), "UpdateTitle", None):
			board.UpdateTitle(text)
			return

		if style > 0:
			board = nui_windows.make("shop-signs", uiPrivateShopBuilder.PrivateShopTitleBar, "nui_shop_signs.ShopSign", style)
		else:
			board = nui_windows.make("shop-signs", uiPrivateShopBuilder.PrivateShopAdvertisementBoard, "nui_shop_signs.ShopSign")
		board.Open(vid, text)

		self.privateShopAdvertisementBoardDict[vid] = board

	def DisappearPrivateShop(self, vid):

		if vid not in self.privateShopAdvertisementBoardDict:
			return

		del self.privateShopAdvertisementBoardDict[vid]
		uiPrivateShopBuilder.DeleteADBoard(vid)

	#####################################################################################
	### Equipment ###

	def OpenEquipmentDialog(self, vid):
		dlg = nui_windows.make("equipment-view", uiEquipmentDialog.EquipmentDialog, "nui_equipment_view.EquipmentDialog")
		dlg.SetItemToolTip(self.tooltipItem)
		dlg.SetCloseEvent(ui.__mem_func__(self.CloseEquipmentDialog))
		dlg.Open(vid)

		self.equipmentDialogDict[vid] = dlg

	def SetEquipmentDialogItem(self, vid, slotIndex, vnum, count):
		if not vid in self.equipmentDialogDict:
			return
		self.equipmentDialogDict[vid].SetEquipmentDialogItem(slotIndex, vnum, count)

	def SetEquipmentDialogSocket(self, vid, slotIndex, socketIndex, value):
		if not vid in self.equipmentDialogDict:
			return
		self.equipmentDialogDict[vid].SetEquipmentDialogSocket(slotIndex, socketIndex, value)

	def SetEquipmentDialogAttr(self, vid, slotIndex, attrIndex, type, value):
		if not vid in self.equipmentDialogDict:
			return
		self.equipmentDialogDict[vid].SetEquipmentDialogAttr(slotIndex, attrIndex, type, value)

	def CloseEquipmentDialog(self, vid):
		if not vid in self.equipmentDialogDict:
			return
		del self.equipmentDialogDict[vid]

	#####################################################################################

	#####################################################################################
	### Quest ###	
	def BINARY_ClearQuest(self, index):
		btn = self.__FindQuestButton(index)

		if 0 != btn:
			self.__DestroyQuestButton(btn)		
	
	def RecvQuest(self, index, name):
		# QUEST_LETTER_IMAGE
		self.BINARY_RecvQuest(index, name, "file", localeInfo.GetLetterImageName())
		# END_OF_QUEST_LETTER_IMAGE

	def BINARY_RecvQuest(self, index, name, iconType, iconName):

		btn = self.__FindQuestButton(index)
		if 0 != btn:
			self.__DestroyQuestButton(btn)

		btn = uiWhisper.WhisperButton()

		# QUEST_LETTER_IMAGE
		## Quest image replacement
		import item

		# MR-7: Fix quest letter icon flashing
		if "item" == iconType:
			item.SelectItem(int(iconName))
			buttonImageFileName = item.GetIconImageFileName()
		else:
			buttonImageFileName = iconName

		if "highlight" == iconType:
			btn.SetUpVisual("locale/ymir_ui/highlighted_quest.tga")
			btn.SetOverVisual("locale/ymir_ui/highlighted_quest_r.tga")
			btn.SetDownVisual("locale/ymir_ui/highlighted_quest_r.tga")
		else:
			btn.SetUpVisual(localeInfo.GetLetterCloseImageName())
			btn.SetOverVisual(localeInfo.GetLetterOpenImageName())
			btn.SetDownVisual(localeInfo.GetLetterOpenImageName())

			btn.Flash()
		# MR-7: -- END OF -- Fix quest letter icon flashing
		# END_OF_QUEST_LETTER_IMAGE

		if app.IsRTL():
			btn.SetToolTipText(name, 0, 35)
			btn.ToolTipText.SetHorizontalAlignCenter()
		else:
			btn.SetToolTipText(name, -20, 35)
			btn.ToolTipText.SetHorizontalAlignLeft()

		btn.SetEvent(ui.__mem_func__(self.__StartQuest), btn)

		# MR-1: Hide quest button when quest dialog is open to prevent quest button flashing
		if IsQBHide or self.questButtonSuppressed:
			btn.Hide()
		else:
			btn.Show()
		# MR-1: -- END OF -- Hide quest button when quest dialog is open to prevent quest button flashing

		btn.index = index
		btn.name = name

		self.questButtonList.insert(0, btn)
		self.__ArrangeQuestButton()

		#chat.AppendChat(chat.CHAT_TYPE_NOTICE, localeInfo.QUEST_APPEND)

	def __ArrangeQuestButton(self):
		screenWidth = wndMgr.GetScreenWidth()
		screenHeight = wndMgr.GetScreenHeight()

		## Quest position adjustment
		if self.wndParty.IsShow():
			xPos = 100 + 30
		else:
			xPos = 20

		if app.IsRTL():
			xPos = xPos + 15

		yPos = 170 * screenHeight // 600
		yCount = (screenHeight - 330) // 63
		count = 0

		for btn in self.questButtonList:
			btn.SetPosition(xPos + (int(count // yCount) * 100), yPos + (count % yCount * 63))
	
			count += 1

			global IsQBHide

			# MR-1: Hide quest button when quest dialog is open to prevent quest button flashing
			if IsQBHide or self.questButtonSuppressed:
				btn.Hide()
			else:
				btn.Show()
			# MR-1: -- END OF -- Hide quest button when quest dialog is open to prevent quest button flashing

	def __StartQuest(self, btn):
		event.QuestButtonClick(btn.index)
		self.__DestroyQuestButton(btn)

	def __FindQuestButton(self, index):
		for btn in self.questButtonList:
			if btn.index == index:
				return btn

		return 0

	def __DestroyQuestButton(self, btn):
		btn.SetEvent(0)
		self.questButtonList.remove(btn)
		self.__ArrangeQuestButton()

	def HideAllQuestButton(self):
		for btn in self.questButtonList:
			btn.Hide()

	def ShowAllQuestButton(self):
		for btn in self.questButtonList:
			btn.Show()
	#####################################################################################

	#####################################################################################
	### Whisper ###

	def __InitWhisper(self):
		chat.InitWhisper(self)

	## Opens unnamed whisper dialog when "Send Message" is clicked in chat window
	## Managed separately from WhisperDialogDict because it has no name
	def OpenWhisperDialogWithoutTarget(self):
		if not self.dlgWhisperWithoutTarget:
			dlgWhisper = nui_windows.make("whisper", uiWhisper.WhisperDialog, "nui_whisper.WhisperDialog", self.MinimizeWhisperDialog, self.CloseWhisperDialog)
			dlgWhisper.BindInterface(self)
			dlgWhisper.LoadDialog()
			dlgWhisper.OpenWithoutTarget(self.RegisterTemporaryWhisperDialog)
			dlgWhisper.SetPosition(self.windowOpenPosition*30,self.windowOpenPosition*30)
			dlgWhisper.Show()
			self.dlgWhisperWithoutTarget = dlgWhisper

			self.windowOpenPosition = (self.windowOpenPosition+1) % 5

		else:
			self.dlgWhisperWithoutTarget.SetTop()
			self.dlgWhisperWithoutTarget.OpenWithoutTarget(self.RegisterTemporaryWhisperDialog)

	## Adds window to WhisperDialogDict when name is determined in unnamed dialog
	def RegisterTemporaryWhisperDialog(self, name):
		if not self.dlgWhisperWithoutTarget:
			return

		btn = self.__FindWhisperButton(name)
		if 0 != btn:
			self.__DestroyWhisperButton(btn)

		elif name in self.whisperDialogDict:
			oldDialog = self.whisperDialogDict[name]
			oldDialog.Destroy()
			del self.whisperDialogDict[name]

		self.whisperDialogDict[name] = self.dlgWhisperWithoutTarget
		self.dlgWhisperWithoutTarget.OpenWithTarget(name)
		self.dlgWhisperWithoutTarget = None
		self.__CheckGameMaster(name)

	## Opens whisper window directly with name when "1:1 Chat" is clicked in character menu
	def OpenWhisperDialog(self, name):
		if name not in self.whisperDialogDict:
			dlg = self.__MakeWhisperDialog(name)
			dlg.OpenWithTarget(name)
			dlg.chatLine.SetFocus()
			dlg.Show()

			self.__CheckGameMaster(name)
			btn = self.__FindWhisperButton(name)
			if 0 != btn:
				self.__DestroyWhisperButton(btn)

	## Shows button when receiving message from another character
	def RecvWhisper(self, name):
		if name not in self.whisperDialogDict:
			btn = self.__FindWhisperButton(name)
			if 0 == btn:
				btn = self.__MakeWhisperButton(name)
				btn.Flash()

				chat.AppendChat(chat.CHAT_TYPE_NOTICE, localeInfo.RECEIVE_MESSAGE % (name))

			else:
				btn.Flash()
			self.whisperUnread.add(name)
			self.__RefreshWhisperBadge()
		elif self.IsGameMasterName(name):
			dlg = self.whisperDialogDict[name]
			dlg.SetGameMasterLook()

	def MakeWhisperButton(self, name):
		self.__MakeWhisperButton(name)

	## Opens window when button is clicked
	def ShowWhisperDialog(self, btn):
		try:
			self.__MakeWhisperDialog(btn.name)
			dlgWhisper = self.whisperDialogDict[btn.name]
			dlgWhisper.OpenWithTarget(btn.name)
			dlgWhisper.Show()
			self.__CheckGameMaster(btn.name)
		except:
			import dbg
			dbg.TraceError("interface.ShowWhisperDialog - Failed to find key")

		## Reset button
		self.__DestroyWhisperButton(btn)

	## Called when minimize command is executed in WhisperDialog window
	## Minimizes the window
	def MinimizeWhisperDialog(self, name):

		if 0 != name:
			self.__MakeWhisperButton(name)

		self.CloseWhisperDialog(name)

	## Called when close command is executed in WhisperDialog window
	## Destroys the window
	def CloseWhisperDialog(self, name):

		if 0 == name:

			if self.dlgWhisperWithoutTarget:
				self.dlgWhisperWithoutTarget.Destroy()
				self.dlgWhisperWithoutTarget = None

			return

		try:
			dlgWhisper = self.whisperDialogDict[name]
			dlgWhisper.Destroy()
			del self.whisperDialogDict[name]
		except:
			import dbg
			dbg.TraceError("interface.CloseWhisperDialog - Failed to find key")

	## Rearranges buttons when button count changes
	def __ArrangeWhisperButton(self):
		screenWidth = wndMgr.GetScreenWidth()
		screenHeight = wndMgr.GetScreenHeight()
	
		xPos = screenWidth - 70
		yPos = 170 * screenHeight // 600
		yCount = (screenHeight - 330) // 63
		#yCount = (screenHeight - 285) // 63

		count = 0

		for button in self.whisperButtonList:
			button.SetPosition(xPos + (int(count // yCount) * -50), yPos + (count % yCount * 63))

			count += 1

	## Finds and returns Whisper button by name
	## Buttons are not stored in dictionary because sorting would lose order
	## This prevents tooltips from being covered by other buttons
	def __FindWhisperButton(self, name):
		for button in self.whisperButtonList:
			if button.name == name:
				return button

		return 0

	## Creates window
	def __MakeWhisperDialog(self, name):
		dlgWhisper = nui_windows.make("whisper", uiWhisper.WhisperDialog, "nui_whisper.WhisperDialog", self.MinimizeWhisperDialog, self.CloseWhisperDialog)
		dlgWhisper.BindInterface(self)
		dlgWhisper.LoadDialog()
		dlgWhisper.SetPosition(self.windowOpenPosition*30,self.windowOpenPosition*30)
		self.whisperDialogDict[name] = dlgWhisper

		self.windowOpenPosition = (self.windowOpenPosition+1) % 5

		return dlgWhisper

	## Creates button
	def __MakeWhisperButton(self, name):
		whisperButton = uiWhisper.WhisperButton()
		whisperButton.SetUpVisual("d:/ymir work/ui/game/windows/btn_mail_up.sub")
		whisperButton.SetOverVisual("d:/ymir work/ui/game/windows/btn_mail_up.sub")
		whisperButton.SetDownVisual("d:/ymir work/ui/game/windows/btn_mail_up.sub")
		if self.IsGameMasterName(name):
			whisperButton.SetToolTipTextWithColor(name, 0xffffa200)
		else:
			whisperButton.SetToolTipText(name)
		whisperButton.ToolTipText.SetHorizontalAlignCenter()
		whisperButton.SetEvent(ui.__mem_func__(self.ShowWhisperDialog), whisperButton)
		whisperButton.Show()
		whisperButton.name = name

		self.whisperButtonList.insert(0, whisperButton)
		self.__ArrangeWhisperButton()

		return whisperButton

	def __DestroyWhisperButton(self, button):
		button.SetEvent(0)
		self.whisperButtonList.remove(button)
		self.__ArrangeWhisperButton()
		self.whisperUnread.discard(button.name)
		self.__RefreshWhisperBadge()

	## NovaUI taskbar only: its Messenger button's badge counts the pending
	## whisper buttons that hold a message the player has not opened (a
	## minimized dialog's button holds none until a message arrives). The legacy
	## taskbar has no such method.
	def __RefreshWhisperBadge(self):
		setter = getattr(getattr(self, "wndTaskBar", None), "nui_set_unread_whispers", None)
		if setter is not None:
			setter(len([btn for btn in self.whisperButtonList if btn.name in self.whisperUnread]))

	def HideAllWhisperButton(self):
		for btn in self.whisperButtonList:
			btn.Hide()

	def ShowAllWhisperButton(self):
		for btn in self.whisperButtonList:
			btn.Show()

	def __CheckGameMaster(self, name):
		if name not in self.listGMName:
			return
		if name in self.whisperDialogDict:
			dlg = self.whisperDialogDict[name]
			dlg.SetGameMasterLook()

	def RegisterGameMasterName(self, name):
		if name in self.listGMName:
			return
		self.listGMName[name] = "GM"

	def IsGameMasterName(self, name):
		if name in self.listGMName:
			return True
		else:
			return False

	#####################################################################################

	#####################################################################################
	### Guild Building ###

	def BUILD_OpenWindow(self):
		self.wndGuildBuilding = nui_windows.make("guild-building", uiGuild.BuildGuildBuildingWindow,
		                                         "nui_guild_building.BuildGuildBuildingWindow")
		self.wndGuildBuilding.Open()
		self.wndGuildBuilding.wnds = self.__HideWindows()
		self.wndGuildBuilding.SetCloseEvent(ui.__mem_func__(self.BUILD_CloseWindow))

	def BUILD_CloseWindow(self):
		self.__ShowWindows(self.wndGuildBuilding.wnds)
		self.wndGuildBuilding = None

	def BUILD_OnUpdate(self):
		if not self.wndGuildBuilding:
			return

		if self.wndGuildBuilding.IsPositioningMode():
			import background
			x, y, z = background.GetPickingPoint()
			self.wndGuildBuilding.SetBuildingPosition(x, y, z)

	def BUILD_OnMouseLeftButtonDown(self):
		if not self.wndGuildBuilding:
			return

		# GUILD_BUILDING
		if self.wndGuildBuilding.IsPositioningMode():
			self.wndGuildBuilding.SettleCurrentPosition()
			return True
		elif self.wndGuildBuilding.IsPreviewMode():
			pass
		else:
			return True
		# END_OF_GUILD_BUILDING
		return False

	def BUILD_OnMouseLeftButtonUp(self):
		if not self.wndGuildBuilding:
			return

		if not self.wndGuildBuilding.IsPreviewMode():
			return True

		return False

	def BULID_EnterGuildArea(self, areaID):
		# GUILD_BUILDING
		mainCharacterName = player.GetMainCharacterName()
		masterName = guild.GetGuildMasterName()

		if mainCharacterName != masterName:
			return

		if areaID != player.GetGuildID():
			return
		# END_OF_GUILD_BUILDING

		self.wndGameButton.ShowBuildButton()

	def BULID_ExitGuildArea(self, areaID):
		self.wndGameButton.HideBuildButton()

	#####################################################################################

	def IsEditLineFocus(self):
		if self.ChatWindow.chatLine.IsFocus():
			return 1

		if self.ChatWindow.chatToLine.IsFocus():
			return 1

		return 0

	def EmptyFunction(self):
		pass

	def UseDSSButtonEffect(self, enable):
		if self.wndInventory:
			self.wndInventory.UseDSSButtonEffect(enable)

if __name__ == "__main__":

	import app
	import wndMgr
	import systemSetting
	import mouseModule
	import grp
	import ui
	import localeInfo

	app.SetMouseHandler(mouseModule.mouseController)
	app.SetHairColorEnable(True)
	wndMgr.SetMouseHandler(mouseModule.mouseController)
	wndMgr.SetScreenSize(systemSetting.GetWidth(), systemSetting.GetHeight())
	app.Create(localeInfo.APP_TITLE, systemSetting.GetWidth(), systemSetting.GetHeight(), 1)
	mouseModule.mouseController.Create()

	class TestGame(ui.Window):
		def __init__(self):
			ui.Window.__init__(self)

			localeInfo.LoadLocaleData()
			player.SetItemData(0, 27001, 10)
			player.SetItemData(1, 27004, 10)

			self.interface = Interface()
			self.interface.MakeInterface()
			self.interface.ShowDefaultWindows()
			self.interface.RefreshInventory()

		def __del__(self):
			ui.Window.__del__(self)

		def OnUpdate(self):
			app.UpdateGame()

		def OnRender(self):
			app.RenderGame()
			grp.PopState()
			grp.SetInterfaceRenderState()

	game = TestGame()
	game.SetSize(systemSetting.GetWidth(), systemSetting.GetHeight())
	game.Show()

	app.Loop()
