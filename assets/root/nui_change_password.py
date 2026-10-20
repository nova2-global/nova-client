"""The safebox's change-password dialog's board (nui/windows/change-password/
change-password.rml; P16 spec 5.4.2). Its facade is
nui_safebox.ChangePasswordDialog, a subclass of uiSafebox.ChangePasswordDialog
that the NovaUI safebox makes.

A modal (D12). Each field hears its own keys, as legacy's edit lines: Tab is
its OnIMETab (the tab event: OnNextFocus, old to new to check to old),
Enter its OnIMEReturn (OnNextFocus, or OnAccept in the check field), Escape
its OnPressEscapeKey (OnCancel); each keeps the key, so RmlUi moves no focus
of its own. Escape on the dialog outside the fields cancels as well. The
buttons act on a left mousedown. No field's text enters the model: the
facade reads the fields at the accept."""

import nui
import nui_hud

DOCUMENT = "nui/windows/change-password/change-password.rml"
OLD = "change-password-old"
NEW = "change-password-new"
CHECK = "change-password-check"
# The facade's attribute of each field (legacy's names).
FIELDS = ((OLD, "oldPassword"), (NEW, "newPassword"), (CHECK, "newPasswordCheck"))


class ChangePasswordBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The change-password dialog's document; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "change_password"
	MODAL = True

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc:
			self.element_on("", "keydown", self._on_body_key)
			for field_id, name in FIELDS:
				self.element_on(field_id, "keydown", lambda event, name=name: self._on_field_key(name, event))

	def initial_model(self):
		return dict(self._initial)

	def _on_field_key(self, name, event):
		if not self.is_visible():
			return None
		field = getattr(self._owner, name)
		key = event.get("key_identifier")
		if key == nui.KEY_TAB:
			field.fire_tab()
			return True
		if key in (nui.KEY_RETURN, nui.KEY_NUMPADENTER):
			field.fire_return()
			return True
		if key == nui.KEY_ESCAPE:
			field.fire_escape()
			return True
		return None

	def _on_body_key(self, event):
		"""Escape outside the fields: the fields' escape (OnCancel)."""
		if not self.is_visible() or event.get("key_identifier") != nui.KEY_ESCAPE:
			return None
		self._owner.oldPassword.fire_escape()
		return True

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
