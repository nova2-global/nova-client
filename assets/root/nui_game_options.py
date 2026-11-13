"""NovaUI game options (nui/windows/game-options/game-options.rml).

While the "game-options" window flag is on, uiGameOption.OptionDialog (a
factory, nui_windows.factory) makes OptionDialog below instead of the legacy
class, for whichever system menu runs (P11 spec D7). It is the facade of the
legacy window with its name, constructor and methods; C++ reaches it through
the system menu (OnBlockMode, OnChangePKMode). Its document exists only
while it shows (nui_hud.OnDemand), and each show fills the model.

Every choice makes legacy's call, in legacy's order (uigameoption.py): the
name color and the target board option set constInfo's module state; the
PvP choices send /pkmode (unless the level is protected, or a guild mode
without a guild, or PvP mode is off: an info line instead), and show the
server's mode until its answer reaches OnChangePKMode; a block toggle sends
/setblockmode with that bit flipped and shows the server's mask until its
setblockmode command reaches OnBlockMode; the four flags call systemSetting
(saved at exit), the shop names also uiPrivateShopBuilder.UpdateADBoard
when turned on; a pickup filter toggle (NOVA-50: equipment, special,
potions, others; what Z and ` pick up) flips its category through
systemSetting.SetPickupFilter, which the client saves with the settings; the
sash row (SHOW_ACCE, NOVA-20) calls systemSetting.SetShowAcceFlag, saved at
exit with the other flags. The hide-buffi row (NOVA-38) sends /hide_buffi and
shows the server's state. uiGameOption.blockMode and viewChatMode stay the shared
state: this module reads and writes them, never a copy. Escape closes the
window in its legacy place (nui_hud.EscapeProxy); a window the player moved
keeps its place across a hide, as legacy's one window does.

The Keyboard row (NOVA-121) opens the document's second page, the key
bindings (`page` "keys"): keybindings.Page's rows, notice and capture, which
the legacy key bindings dialog (uikeybindings.py) shares, so both show one
table. A left press on a key cell waits for the next key the game window gets
(game.py gives keybindings' capture every key first); Escape ends a waiting
cell before it closes the window, and a hide ends it too. The page stays
across a hide, as the place does. The window listens to the table, so a
change made in the legacy dialog shows here."""

import chat
import constInfo
import keybindings
import localeInfo
import net
import player
import shop
import systemSetting
import uiGameOption
import uiPrivateShopBuilder
import item_glow

import nui
import nui_hud

DOCUMENT = "nui/windows/game-options/game-options.rml"
BLOCK_COUNT = 6
# The pickup filter's categories, in systemSetting.PICKUP_FILTER_*'s order
# (uigameoption.py pickupFilterButtonList): equipment, special, potions, others.
PICKUP_COUNT = 4


def _block_bits():
	"""The six toggles' bits in legacy's order (uigameoption.py:184-207)."""
	return (player.BLOCK_EXCHANGE, player.BLOCK_PARTY, player.BLOCK_GUILD, player.BLOCK_WHISPER,
	        player.BLOCK_FRIEND, player.BLOCK_PARTY_REQUEST)


def _hide_shops():
	"""Whether the offline shops are hidden (an exe without the offline shop:
	shown)."""
	return bool(getattr(shop, "IsHideShops", lambda: False)())


def _show_sash():
	"""Whether the client draws the sashes (systemSetting.IsShowAcce,
	SHOW_ACCE; uigameoption.py RefreshShowSash)."""
	return bool(systemSetting.IsShowAcce())


def _hide_buffi():
	"""Whether the buffi are hidden (NOVA-38: uiGameOption.IsHideBuffi, the
	server's GC::BUFFI_HIDE state; an exe without it: shown)."""
	return bool(uiGameOption.IsHideBuffi())


class GameOptionsBoard(nui.Window):
	"""The game options' document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "game_options"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		model = getattr(self._owner, "nui_model", None)
		if model is not None:
			return model()
		return {"name_color": 0, "target_board": 0, "pk_mode": 0, "block": 0, "blocked": [False] * BLOCK_COUNT,
		        "view_chat": True, "always_show_name": True, "show_damage": True, "sales_text": True,
		        "pickup": [True] * PICKUP_COUNT, "hide_shops": False, "show_sash": True, "hide_buffi": False,
		        "mob_level": True, "mob_ai": True, "new_item_glow": True, "page": "main", "key_rows": [], "notice": ""}

	@nui.on("choose")
	def on_choose(self, what, value, button):
		if button == 0:
			self._owner.nui_choose(what, value)

	@nui.on("block")
	def on_block(self, index, button):
		if button == 0:
			self._owner.nui_block(index)

	@nui.on("pickup")
	def on_pickup(self, index, button):
		if button == 0:
			self._owner.nui_pickup(index)

	@nui.on("keypage")
	def on_keypage(self, what, button):
		if button == 0:
			self._owner.nui_keypage(what)

	@nui.on("bind")
	def on_bind(self, action, column, button):
		if button == 0:
			self._owner.nui_bind(action, column)

	@nui.on("reset_keys")
	def on_reset_keys(self, button):
		if button == 0:
			self._owner.nui_reset_keys()

	@nui.on("close")
	def on_close(self, button):
		if button == 0:
			self._owner.Close()


class OptionDialog(nui_hud.LayoutCalls):
	"""uiGameOption.OptionDialog on NovaUI (SystemDialog.gameOptionDlg)."""

	NUI_FACADE = True
	KEY = "game-options"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		# The PvP mode legacy shows at load (__SetPeacePKMode, :136).
		self.pkMode = player.PK_MODE_PEACE
		self.place = None
		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		# NOVA-121: the keys page and the table it shows.
		self.page = "main"
		self.keyPage = keybindings.Page(self.RefreshKeys)
		keybindings.current().listen(self)
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.OnPressEscapeKey)
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		keyPage = getattr(self, "keyPage", None)
		if keyPage is not None:
			keyPage.cancel()
			keybindings.current().forget(self)
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	# --- the model ----------------------------------------------------------------

	@staticmethod
	def blocked(mask):
		return [bool(mask & (1 << i)) for i in range(BLOCK_COUNT)]

	@staticmethod
	def pickup():
		"""Each category's toggle: down while the filter picks it up."""
		return [bool(systemSetting.GetPickupFilter(i)) for i in range(PICKUP_COUNT)]

	def nui_model(self):
		mask = uiGameOption.blockMode
		return {"name_color": constInfo.GET_CHRNAME_COLOR_INDEX(),
		        "target_board": constInfo.GET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD(),
		        "pk_mode": self.pkMode, "block": mask, "blocked": self.blocked(mask),
		        "view_chat": bool(systemSetting.IsViewChat()), "always_show_name": bool(systemSetting.IsAlwaysShowName()),
		        "show_damage": bool(systemSetting.IsShowDamage()), "sales_text": bool(systemSetting.IsShowSalesText()),
		        "pickup": self.pickup(), "hide_shops": _hide_shops(), "show_sash": _show_sash(), "hide_buffi": _hide_buffi(),
		        "mob_level": bool(systemSetting.IsShowMobLevel()), "mob_ai": bool(systemSetting.IsShowMobAIFlag()),
		        "new_item_glow": item_glow.enabled(),
		        "page": self.page, "key_rows": self.key_rows(), "notice": nui.plain_text(self.keyPage.notice_text())}

	def key_rows(self):
		"""keybindings.Page's rows, their texts plain (they come from the
		locale files and the key names, never a locale key)."""
		rows = []
		for row in self.keyPage.rows():
			row = dict(row)
			for key in ("label", "k1", "k2"):
				row[key] = nui.plain_text(row[key])
			rows.append(row)
		return rows

	def _board(self):
		return self.demand.board() if self.demand is not None else None

	def _set(self, **values):
		board = self._board()
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return GameOptionsBoard(self)

	def _restore_board(self, board):
		board.set(**self.nui_model())
		if self.place is not None:
			board.set_position(*self.place)
		else:
			board.center()

	def _keep_board(self, board):
		self.place = nui_hud.moved_place(board)

	# --- the system menu's and C++'s calls ----------------------------------------------

	def Destroy(self):
		self.nui_discard()

	def Show(self):
		"""uigameoption.py:365-367: the block toggles from the shared mask."""
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()

	def Hide(self):
		# A capture never outlives the page that waits (NOVA-121).
		keyPage = getattr(self, "keyPage", None)
		if keyPage is not None:
			keyPage.cancel()
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

	def Close(self):
		self.Hide()

	def OnPressEscapeKey(self):
		# A key cell that waits ends first; the next Escape closes (NOVA-121).
		if self.keyPage.cancel():
			return True
		self.Close()
		return True

	def OnBlockMode(self, mode):
		"""The server's setblockmode command (uigameoption.py:360-363)."""
		uiGameOption.blockMode = mode
		self.RefreshBlock()

	def OnChangePKMode(self):
		"""The server's answer to /pkmode (uigameoption.py:313-314)."""
		self.pkMode = player.GetPKMode()
		self._set(pk_mode=self.pkMode)

	def RefreshBlock(self):
		mask = uiGameOption.blockMode
		self._set(block=mask, blocked=self.blocked(mask))

	def RefreshViewChat(self):
		self._set(view_chat=bool(systemSetting.IsViewChat()))

	def RefreshAlwaysShowName(self):
		self._set(always_show_name=bool(systemSetting.IsAlwaysShowName()))

	def RefreshShowDamage(self):
		self._set(show_damage=bool(systemSetting.IsShowDamage()))

	def RefreshShowSalesText(self):
		self._set(sales_text=bool(systemSetting.IsShowSalesText()))

	def RefreshHideShops(self):
		"""Wave 5 (NOVA-9): the offline shops shown or hidden, the server's
		state (shop.IsHideShops; Interface.OnOfflineShopHideShops calls this
		on GC HIDE_SHOPS), never a local guess (M5)."""
		self._set(hide_shops=_hide_shops())

	def RefreshShowSash(self):
		"""SHOW_ACCE (NOVA-20): the sashes drawn or not, the client's flag
		(uigameoption.py RefreshShowSash)."""
		self._set(show_sash=_show_sash())

	def RefreshHideBuffi(self):
		"""NOVA-38: the buffi shown or hidden, the server's state
		(player.IsHideBuffi; Interface.OnBuffiHide calls this on
		GC::BUFFI_HIDE), never a local guess."""
		self._set(hide_buffi=_hide_buffi())

	def RefreshKeys(self):
		"""The keys page's rows and notice (NOVA-121): after a key bound, a
		wait begun or ended, a reset, or a change from the legacy dialog."""
		self._set(key_rows=self.key_rows(), notice=nui.plain_text(self.keyPage.notice_text()))

	def OnKeyBindingsChanged(self):
		self.RefreshKeys()

	def nui_keypage(self, what):
		"""The Keyboard row's button ("open") and the keys page's Back."""
		if what == "open":
			self.page = "keys"
		elif what == "back":
			self.keyPage.cancel()
			self.page = "main"
		else:
			return
		self._set(page=self.page)
		self.RefreshKeys()

	def nui_bind(self, action, column):
		"""A left press on a key cell: it waits for the next key."""
		if action not in keybindings.ACTION or column not in (0, 1):
			return
		self.keyPage.press(action, int(column))

	def nui_reset_keys(self):
		self.keyPage.reset()

	def RefreshPickupFilter(self):
		"""A category's toggle is down while the filter picks it up
		(uigameoption.py RefreshPickupFilter)."""
		self._set(pickup=self.pickup())

	# --- the board's events (uigameoption.py:149-311) -----------------------------------

	def _in_effect(self, what):
		"""The choice the row shows selected, as nui_model fills it; None for
		a row of no choices."""
		if what == "name_color":
			return constInfo.GET_CHRNAME_COLOR_INDEX()
		if what == "target_board":
			return constInfo.GET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD()
		if what == "pk":
			return self.pkMode
		if what == "view_chat":
			return int(bool(systemSetting.IsViewChat()))
		if what == "always_show_name":
			return int(bool(systemSetting.IsAlwaysShowName()))
		if what == "show_damage":
			return int(bool(systemSetting.IsShowDamage()))
		if what == "sales_text":
			return int(bool(systemSetting.IsShowSalesText()))
		if what == "hide_shops":
			return int(_hide_shops())
		if what == "show_sash":
			return int(_show_sash())
		if what == "hide_buffi":
			return int(_hide_buffi())
		if what == "mob_level":
			return int(bool(systemSetting.IsShowMobLevel()))
		if what == "mob_ai":
			return int(bool(systemSetting.IsShowMobAIFlag()))
		if what == "new_item_glow":
			return int(item_glow.enabled())
		return None

	def nui_choose(self, what, value):
		# Legacy's radio buttons ignore a press on the one that is down
		# (CRadioButton::OnMouseLeftButtonDown): no call, and no /pkmode again.
		if value == self._in_effect(what):
			return
		if what == "name_color" and value in (0, 1):
			constInfo.SET_CHRNAME_COLOR_INDEX(value)
			self._set(name_color=value)
		elif what == "target_board" and value in (0, 1):
			constInfo.SET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD(value)
			self._set(target_board=value)
		elif what == "pk" and value in (player.PK_MODE_PEACE, player.PK_MODE_REVENGE, player.PK_MODE_GUILD,
		                               player.PK_MODE_FREE):
			self.__ChoosePKMode(value)
		elif what == "view_chat" and value in (0, 1):
			uiGameOption.viewChatMode = value
			systemSetting.SetViewChatFlag(value)
			self.RefreshViewChat()
		elif what == "always_show_name" and value in (0, 1):
			systemSetting.SetAlwaysShowNameFlag(bool(value))
			self.RefreshAlwaysShowName()
		elif what == "show_damage" and value in (0, 1):
			systemSetting.SetShowDamageFlag(bool(value))
			self.RefreshShowDamage()
		elif what == "sales_text" and value in (0, 1):
			systemSetting.SetShowSalesTextFlag(bool(value))
			self.RefreshShowSalesText()
			if value:
				uiPrivateShopBuilder.UpdateADBoard()
		elif what == "hide_shops" and value in (0, 1):
			# Legacy's row (uiGameOption.__OnClickHideShopsButton): 0 shows the
			# shops, 1 hides them; the server answers with HIDE_SHOPS.
			net.SendChatPacket("/hide_shops %d" % value)
			self.RefreshHideShops()
		elif what == "show_sash" and value in (0, 1):
			# Legacy's row (uiGameOption.__OnClickShowSashButton): 1 draws the
			# sashes, 0 hides them.
			systemSetting.SetShowAcceFlag(bool(value))
			self.RefreshShowSash()
		elif what == "mob_level" and value in (0, 1):
			# NOVA-40 (legacy's row: uiGameOption.__OnClickMobLevelButton).
			systemSetting.SetShowMobLevel(value)
			self._set(mob_level=bool(systemSetting.IsShowMobLevel()))
		elif what == "mob_ai" and value in (0, 1):
			systemSetting.SetShowMobAIFlag(value)
			self._set(mob_ai=bool(systemSetting.IsShowMobAIFlag()))
		elif what == "new_item_glow" and value in (0, 1) and hasattr(systemSetting, "SetShowNewItemHighlight"):
			# NOVA-188 (legacy's row: uiGameOption.__OnClickNewItemButton).
			systemSetting.SetShowNewItemHighlight(value)
			if not value:
				item_glow.forget_all()
			self._set(new_item_glow=item_glow.enabled())
		elif what == "hide_buffi" and value in (0, 1):
			# Legacy's row (uiGameOption.__OnClickHideBuffiButton): 0 shows the
			# buffi, 1 hides them; the server answers with GC::BUFFI_HIDE.
			net.SendChatPacket("/hide_buffi %d" % value)
			self.RefreshHideBuffi()

	def __CheckPvPProtectedLevelPlayer(self):
		if player.GetStatus(player.LEVEL) < constInfo.PVPMODE_PROTECTED_LEVEL:
			self.pkMode = player.PK_MODE_PEACE
			self._set(pk_mode=self.pkMode)
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.OPTION_PVPMODE_PROTECT % (constInfo.PVPMODE_PROTECTED_LEVEL))
			return 1
		return 0

	def __ChoosePKMode(self, mode):
		"""A PvP choice: the shown mode stays the server's until it answers."""
		if self.__CheckPvPProtectedLevelPlayer():
			return
		self.pkMode = player.GetPKMode()
		self._set(pk_mode=self.pkMode)
		if mode == player.PK_MODE_GUILD and 0 == player.GetGuildID():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.OPTION_PVPMODE_CANNOT_SET_GUILD_MODE)
			return
		if constInfo.PVPMODE_ENABLE:
			net.SendChatPacket("/pkmode %d" % mode, chat.CHAT_TYPE_TALKING)
		else:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.OPTION_PVPMODE_NOT_SUPPORT)

	def nui_pickup(self, index):
		"""A pickup filter toggle (NOVA-50): its category flipped, as legacy's
		toggle up and down events both do (__TogglePickupFilter)."""
		if not 0 <= index < PICKUP_COUNT:
			return
		systemSetting.SetPickupFilter(index, not systemSetting.GetPickupFilter(index))
		self.RefreshPickupFilter()

	def nui_block(self, index):
		"""A block toggle: the toggles show the server's mask, and the command
		asks for that bit flipped."""
		if not 0 <= index < BLOCK_COUNT:
			return
		self.RefreshBlock()
		net.SendChatPacket("/setblockmode " + str(uiGameOption.blockMode ^ _block_bits()[index]))
