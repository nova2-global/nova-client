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
uiscript's 12 today, 24 at the foundation); its text never enters the model."""

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


class _DeclareBoard(WarDialogBoard):
	DOCUMENT = DOCUMENT
	MODEL = "guild_war_declare"
	FIELD_ID = FIELD


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
		return {"type": 0, "type_select": constInfo.GUILD_WAR_TYPE_SELECT_ENABLE != 0, "hints": type_hints(),
		        "max": self._limits.GUILD_NAME_MAX_LEN}

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
