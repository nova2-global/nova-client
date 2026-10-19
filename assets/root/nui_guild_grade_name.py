"""The guild's grade name dialog (nui/windows/guild-grade-name/
guild-grade-name.rml; P16 spec 5.9.5): its board and its facade.

While the guild flag is on, the NovaUI guild window (nui_guild.GuildWindow)
makes ChangeGradeNameDialog below in place of uiGuild.ChangeGradeNameDialog:
a subclass of the legacy class whose widgets are proxies, handed out by
GetChild under the uiscript's names, so the guild window binds them as
legacy's loader did (uiguild.py:881-886): OK and Enter the window's
OnChangeGradeName, Cancel and the close button the dialog's Hide, Escape
its Close. Open (the field cleared and focused, the place under the mouse),
Close, the grade number and the name are legacy's code.

A modal (D12) above the legacy UI layer: the scrim centers it, so legacy's
place 50 px under the mouse moves nothing (nui_facade.DialogFacade). Enter
in the field, or on the dialog, is the field's OnIMEReturn and Escape its
OnPressEscapeKey; both keep the key. The buttons act on a left mousedown.
The field's text never enters the model: the facade reads it at the accept."""

import uiGuild

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/guild-grade-name/guild-grade-name.rml"
FIELD = "guild-grade-name-field"


class GuildGradeNameBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The grade name dialog's document; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "guild_grade_name"
	MODAL = True

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc:
			# A focused field stops every key but Tab: the field hears its own.
			self.element_on("", "keydown", self._on_key)
			self.element_on(FIELD, "keydown", self._on_key)

	def initial_model(self):
		return dict(self._initial)

	def _on_key(self, event):
		"""Legacy's edit line: Enter is its OnIMEReturn, Escape its
		OnPressEscapeKey (the guild window's OnChangeGradeName, the dialog's
		Close)."""
		if not self.is_visible():
			return None
		key = event.get("key_identifier")
		field = self._owner.gradeNameSlot
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
			self._owner.titleBar.close()


class ChangeGradeNameDialog(nui_facade.DialogFacade, uiGuild.ChangeGradeNameDialog):
	"""uiGuild.ChangeGradeNameDialog on NovaUI (GuildWindow.changeGradeNameDialog)."""

	KEY = "guild-grade-name"
	BOARD = GuildGradeNameBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiGuild.ChangeGradeNameDialog.__init__(self)
			self._make_proxies()
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"max": self._limits.GUILD_GRADE_NAME_MAX_LEN}

	def _fields(self):
		field = getattr(self, "gradeNameSlot", None)
		return (field,) if field is not None else ()

	def _make_proxies(self):
		"""The uiscript's widgets (changegradenamedialog.py) as proxies, and
		its style ("movable", "float")."""
		self.AddFlag("movable")
		self.AddFlag("float")
		self.titleBar = nui_proxies.BoardProxy(170, 90)
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.gradeNameSlot = self._field(FIELD, self._limits.GUILD_GRADE_NAME_MAX_LEN, "max")
		self._children = {"Board": self.titleBar, "AcceptButton": self.acceptButton, "CancelButton": self.cancelButton,
		                  "GradeNameValue": self.gradeNameSlot}

	def GetChild(self, name):
		"""The proxies by the uiscript's names, as the guild window binds them."""
		return self._children[name]

	def ClearDictionary(self):
		"""Legacy's Destroy of the guild window clears the dialog's children;
		the proxies stay (nothing holds the window)."""
