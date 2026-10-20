"""The safebox password dialog's board (nui/windows/safebox-password/
safebox-password.rml; P16 spec 5.4.2). Its facade is
nui_safebox.PasswordDialog (Interface.dlgPassword, shared by the safebox and
the mall), a subclass of uiSafebox.PasswordDialog.

A modal (D12): it takes every key and click while it shows. Enter in the
field, or on the dialog, is legacy's OnIMEReturn of the field (OnAccept);
Escape is its OnPressEscapeKey (OnCancel); both keep the key. The buttons act
on a left mousedown. The field is a password input whose text never enters
the model: the facade reads it at the accept."""

import nui
import nui_hud

DOCUMENT = "nui/windows/safebox-password/safebox-password.rml"
FIELD = "safebox-password-field"


class SafeboxPasswordBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The password dialog's document; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "safebox_password"
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
		OnPressEscapeKey (the facade's OnAccept and OnCancel)."""
		if not self.is_visible():
			return None
		key = event.get("key_identifier")
		field = self._owner.passwordValue
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
