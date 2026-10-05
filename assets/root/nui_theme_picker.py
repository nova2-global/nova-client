"""The intro theme picker (nui/windows/theme-picker/theme-picker.rml): one
button per player theme, under the legacy flag strip. nui_login.py opens it
with the login board, hides it while a legacy popup is open and destroys it
with the board.

A left press applies the theme at once and saves it (nui.set_theme), so the
next start opens in it. Every open window, this one included, then gets
on_theme_changed, which moves the selection here.

The document never takes the focus, so the board keeps its caret and typed
text; RmlUi sends no click there, so the buttons act on mousedown.
"""
import dbg
import nui


class ThemePicker(nui.Window):
	DOCUMENT = "nui/windows/theme-picker/theme-picker.rml"
	MODEL = "theme_picker"

	def initial_model(self):
		return {"themes": [{"id": theme_id, "label": label} for theme_id, label in nui.get_themes()],
			"current": nui.get_theme()}

	@nui.on("pick")
	def on_pick(self, theme_id, button):
		# Left press only; nui.set_theme applies, saves and calls on_theme_changed.
		if button != 0:
			return
		try:
			nui.set_theme(theme_id)
		except ValueError as error:
			dbg.TraceError("nui_theme_picker: %s" % error)

	def on_theme_changed(self, theme_id):
		self.set(current=theme_id)
