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

A modal (D12) above the legacy UI layer, at legacy's place (D21, spec
5.9.5): Open's SetPosition (the pointer's x less half the uiscript's
width, 50 px below the pointer) becomes the dialog's place in dp, while the
scrim still dims the rest; a SetCenterPosition centers it again. Enter in
the field, or on the dialog, is the field's OnIMEReturn and Escape its
OnPressEscapeKey; both keep the key. The buttons act on a left mousedown.
The field's text never enters the model: the facade reads it at the accept."""

import uiGuild
import wndMgr

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/guild-grade-name/guild-grade-name.rml"
FIELD = "guild-grade-name-field"
# The uiscript's board (changegradenamedialog.py), 170 x 90: legacy's Open
# centers that width under the pointer, and its window has that size.
WIDTH, HEIGHT = 170, 90


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
		return {"max": self._limits.GUILD_GRADE_NAME_MAX_LEN, "placed": False, "x": 0.0, "y": 0.0}

	# --- the place (D21) ----------------------------------------------------------------

	def GetWidth(self):
		"""The uiscript's width, which legacy's Open centers under the
		pointer (the legacy window stays 0 x 0)."""
		return WIDTH

	def GetHeight(self):
		return HEIGHT

	def SetPosition(self, x, y):
		"""Legacy's pixels as the dialog's place in dp; the scrim still dims
		the rest. Kept on the screen with the uiscript's size (legacy's own
		window could leave it, but a modal off the screen would hold every
		key and press)."""
		try:
			width, height = int(wndMgr.GetScreenWidth()), int(wndMgr.GetScreenHeight())
		except Exception:
			width = height = 0
		x, y = int(x), int(y)
		if width > WIDTH and height > HEIGHT:
			x = min(max(x, 0), width - WIDTH)
			y = min(max(y, 0), height - HEIGHT)
		scale = nui.get_scale() or 1.0
		self.nui_set(placed=True, x=x / scale, y=y / scale)

	def SetCenterPosition(self, x=0, y=0):
		"""Legacy's centering: the scrim centers the dialog."""
		self.nui_set(placed=False)

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
