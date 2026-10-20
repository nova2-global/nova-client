"""The board of the NovaUI music list (nui/windows/music-list/music-list.rml).

The music list's facade is nui_system_options.FileListDialog, which the
NovaUI system options make; this module holds its document's nui.Window,
whose events go to that facade."""

import nui
import nui_hud

DOCUMENT = "nui/windows/music-list/music-list.rml"


class MusicListBoard(nui.Window):
	"""The music list's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "music_list"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"files": [], "selected": -1}

	@nui.on("pick")
	def on_pick(self, index, button):
		if button == 0:
			self._owner.nui_pick(index)

	@nui.on("act")
	def on_act(self, what, button):
		if button == 0:
			self._owner.nui_act(what)
