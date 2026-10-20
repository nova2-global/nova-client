"""The guild war declare dialog (nui/windows/guild-war-declare/
guild-war-declare.rml; P16 spec 5.10): its board and its facade.

While the guild-war-dialogs flag is on, the guild window's declare button
(uiGuild.GuildWindow.__OnClickDeclareWarButton) makes DeclareGuildWarDialog
below through nui_windows.make() instead of uiGuild.DeclareGuildWarDialog:
a subclass of the legacy class whose loader (__CreateDialog) puts proxies
where the uiscript's widgets were, so Open (the field focused), the type
buttons, OK and Enter (an empty name does nothing; else the chat command
"/war <name> <type>" and Close), Cancel, Escape and the close button are
legacy's code. Legacy's type tooltips (uiToolTip windows) become each type
button's hint in the document, from the same strings
(localeInfo.GUILDWAR_*_TITLE and _DESCLIST).

A modal (D12) above the legacy UI layer that the scrim centers
(nui_facade.DialogFacade). The field's limit is GUILD_NAME_MAX_LEN (the
uiscript's 12 today, 24 at the foundation); its text never enters the model.

The guild window makes a new dialog at each press of its declare button, so
the dialog cannot keep its board; its board waits instead, hidden, for the
next dialog (P18: WAVE4.md measured 17 to 17.5 ms of UI work at its first
open, a 60 fps frame): nui_hud.PooledBoard over POOL, one board, its type
buttons gone (types_on), its field empty and no dialog behind it
(nui_hud.Pooled). The next dialog takes it with no load and writes the
field from its own proxy."""

import constInfo
import localeInfo
import ui
import uiGuild
import uiScriptLocale

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/guild-war-declare/guild-war-declare.rml"
FIELD = "guild-war-name"
# The three battle types in the type buttons' order: the button's label
# (the uiscript's), the hint's title and description lines (localeInfo).
TYPES = (("GUILD_WAR_NORMAL", "GUILDWAR_NORMAL_TITLE", "GUILDWAR_NORMAL_DESCLIST"),
         ("GUILD_WAR_WARP", "GUILDWAR_WARP_TITLE", "GUILDWAR_WARP_DESCLIST"),
         ("GUILD_WAR_CTF", "GUILDWAR_CTF_TITLE", "GUILDWAR_CTF_DESCLIST"))
# P18: the board that waits for the next declare dialog. One: one dialog
# shows at a time (the next press's dialog takes over the last one).
POOL = nui_hud.BoardPool("guild-war-declare", 1)


def type_hints():
	"""The type buttons' labels and hints, as legacy's tooltips hold them
	(__CreateGameTypeToolTip: the title, then each description line)."""
	hints = []
	for label, title, lines in TYPES:
		hints.append({"label": nui.plain_text(getattr(uiScriptLocale, label, "")),
		              "title": nui.plain_text(getattr(localeInfo, title, "")),
		              "lines": [nui.plain_text(line) for line in getattr(localeInfo, lines, ())]})
	return hints


class TypeButtonProxy(nui_proxies.ButtonProxy):
	"""A battle type's radio button: SAFE_SetEvent holds the event as
	legacy's (ui.__mem_func__), SetToolTipWindow keeps the tooltip legacy
	built (the document shows the hint from the same strings)."""

	def SAFE_SetEvent(self, event, *args):
		self.SetEvent(ui.__mem_func__(event), *args)

	def SetToolTipWindow(self, toolTip):
		self.tooltip_window = toolTip


class TitledBoardProxy(nui_proxies.BoardProxy):
	"""ui.BoardWithTitleBar: SetTitleName hands the title to the window."""

	def __init__(self, width, height, on_title=None):
		nui_proxies.BoardProxy.__init__(self, width, height)
		self._on_title = on_title

	def SetTitleName(self, name):
		nui_proxies.BoardProxy.SetTitleName(self, name)
		if self._on_title is not None:
			self._on_title(self.title)


class WarDialogBoard(nui_hud.RaisesOnPress, nui.Window):
	"""A guild war dialog's document; its events go to its facade. FIELD_ID
	names its field (None for the accept dialog, which has none)."""

	MODAL = True
	FIELD_ID = None

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc and self.FIELD_ID:
			# A focused field stops every key but Tab: the field hears its own.
			self.element_on("", "keydown", self._on_key)
			self.element_on(self.FIELD_ID, "keydown", self._on_key)

	def initial_model(self):
		return dict(self._initial)

	def _on_key(self, event):
		"""Legacy's edit line: Enter is its OnIMEReturn (the accept event),
		Escape its OnPressEscapeKey (the cancel event)."""
		if not self.is_visible():
			return None
		field = getattr(self._owner, "inputValue", None)
		if field is None:
			return None
		key = event.get("key_identifier")
		if key in (nui.KEY_RETURN, nui.KEY_NUMPADENTER):
			field.fire_return()
			return True
		if key == nui.KEY_ESCAPE:
			field.fire_escape()
			return True
		return None

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("type_press")
	def on_type_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_type(int(index))

	@nui.on("accept_press")
	def on_accept_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.acceptButton.click()

	@nui.on("cancel_press")
	def on_cancel_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.cancelButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()


class _DeclareBoard(nui_hud.Pooled, WarDialogBoard):
	DOCUMENT = DOCUMENT
	MODEL = "guild_war_declare"
	FIELD_ID = FIELD
	# nui_hud.Pooled: emptied before the board waits in POOL.
	FIELDS = (FIELD,)


class WarDialogMixin(object):
	"""What both war dialogs' facades share: the type buttons as legacy's
	radio buttons, the type and the type row's state in the model."""

	def _make_type_buttons(self):
		buttons = [TypeButtonProxy(self._on_types) for _ in TYPES]
		return buttons

	def _on_types(self, button=None):
		buttons = getattr(self, "typeButtonList", ())
		selected = [i for i, entry in enumerate(buttons) if entry.down]
		self.nui_set(type=selected[0] if selected else 0)

	def _on_game_type(self, shown):
		self.nui_set(type_select=bool(shown))

	def _press_type(self, index):
		"""A press on a type button as CRadioButton takes it: nothing while it
		is down, else its event (the legacy handler sets the buttons'
		states)."""
		buttons = getattr(self, "typeButtonList", None) or ()
		if 0 <= index < len(buttons) and not buttons[index].down:
			buttons[index].click()

	def SetSize(self, width, height):
		"""Nothing: legacy's SetBoardWidth sizes the window itself; the legacy
		window stays 0 x 0 and the document lays itself out."""

	def _game_type(self):
		gameType = nui_proxies.BoardProxy(on_show=self._on_game_type)
		if constInfo.GUILD_WAR_TYPE_SELECT_ENABLE == 0:
			gameType.Hide()
		return gameType


class DeclareGuildWarDialog(WarDialogMixin, nui_facade.DialogFacade, uiGuild.DeclareGuildWarDialog):
	"""uiGuild.DeclareGuildWarDialog on NovaUI (GuildWindow.inputDialog)."""

	KEY = "guild-war-declare"
	BOARD = _DeclareBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiGuild.DeclareGuildWarDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		# types_on (P18): the type buttons, a list of one entry while the
		# board shows, none while it waits in POOL.
		return {"type": 0, "type_select": constInfo.GUILD_WAR_TYPE_SELECT_ENABLE != 0, "hints": type_hints(),
		        "max": self._limits.GUILD_NAME_MAX_LEN, "types_on": [1]}

	def nui_demand(self):
		"""P18: the board comes from POOL and goes back to it."""
		return nui_hud.PooledBoard(POOL, self._make_board, self._restore_board, self._keep_board,
		                           self._empty_board, self._adopt_board)

	def _adopt_board(self, board):
		board.adopt(self)

	def _empty_board(self, board):
		board.set(types_on=[])

	def Show(self):
		"""DialogFacade's, then the field written even when it is empty: a
		board from POOL shows no earlier dialog's name (P18)."""
		nui_facade.DialogFacade.Show(self)
		board = self.nui_board()
		if board is None:
			return
		for field in self._fields():
			if not field.text:
				board.set_value(field.field_id, "", caret="end", even_hidden=True)

	def _fields(self):
		field = getattr(self, "inputValue", None)
		return (field,) if field is not None else ()

	# --- the loader (uiguild.py:74-118, on proxies) ---------------------------------------

	def _DeclareGuildWarDialog__CreateDialog(self):
		# The uiscript's style (declareguildwardialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")

		self.board = TitledBoardProxy(230, 130)
		self.typeButtonList = self._make_type_buttons()
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.inputSlot = nui_proxies.BoardProxy(130, 18)
		self.inputValue = self._field(FIELD, self._limits.GUILD_NAME_MAX_LEN, "max")

		gameType = self._game_type()

		self.typeButtonList[0].SAFE_SetEvent(self._DeclareGuildWarDialog__OnClickTypeButtonNormal)
		self.typeButtonList[1].SAFE_SetEvent(self._DeclareGuildWarDialog__OnClickTypeButtonWarp)
		self.typeButtonList[2].SAFE_SetEvent(self._DeclareGuildWarDialog__OnClickTypeButtonCTF)

		self._DeclareGuildWarDialog__ClickRadioButton(self.typeButtonList, 0)

		self.SetAcceptEvent(ui.__mem_func__(self._DeclareGuildWarDialog__OnOK))
		self.SetCancelEvent(ui.__mem_func__(self._DeclareGuildWarDialog__OnCancel))
