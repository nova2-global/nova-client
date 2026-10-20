"""The board of the NovaUI quest curtain (nui/windows/quest-curtain/quest-curtain.rml).

nui_quest.QuestCurtain owns it: the letterbox bars and the black and white
fades of quest scripts (uiquest.py QuestCurtain and EventCurtain), one
document every quest dialog shares. It exists only while the bars are in
or sliding, or a fade shows (P12 spec D21). One format="none"
nui-countdown ends both the slides and the fades on the NovaUI clock, so no
Python runs while they move. Lint wants the controller of a document named
after it, so the board lives here and its owner in nui_quest.py."""

import nui
import nui_hud

DOCUMENT = "nui/windows/quest-curtain/quest-curtain.rml"


def empty_model():
	"""The model of a curtain with its bars out and no fade."""
	return {"bars": "out", "bar_dp": "0.00", "fade": "", "fade_dir": "out", "fade_class": "normal",
	        "timer_on": False, "timer_end_at": 0.0}


class QuestCurtainBoard(nui.Window):
	"""The curtain's document; its timer and scale changes go to its owner."""

	DOCUMENT = DOCUMENT
	MODEL = "quest_curtain"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return empty_model()

	@nui.on("timer_end")
	def on_timer_end(self):
		try:
			self._owner.nui_timer_end()
		except ReferenceError:
			pass

	def on_scale_changed(self, scale):
		try:
			self._owner.nui_scale_changed()
		except ReferenceError:
			pass
