"""NovaUI select skill window (nui/windows/select-skill/select-skill.rml; NOVA-37).

While the select-skill flag is on, Interface.__MakeWindows makes SelectSkillWindow below
through nui_windows.make() instead of uiSelectSkill.SelectSkillWindow: a subclass of the legacy
class (nui_facade.Facade) whose loader (_LoadScript) puts proxies where the widgets were (the
two buttons, the two rows of skill slots), so the job's skills, their tooltips, the preview's
model and motion, and the /select_skill it sends are legacy's code. The preview is the nui-view
"model-select-skill" (legacy's render target of the same model); a client without render targets
shows a mark. The board exists only while the window shows.

The layout is Eddy's direction D, "Orbit" (.nui-work/design/select-skill/pulled/D-orbit.dc.html):
each group's side panel (its name, a "plays like" line, its skills by name, its Choose button)
on either side of a ring of the skills around the round preview. Only the skills that exist are
listed (the warrior's and the assassin's 6, 21, 36 and 51 do not). Hovering a side makes its group
active and dims the other; hovering a skill, on the ring or in a list, lights it in both, names it
under the ring and casts it on the preview (legacy's OverInItem). The skill stays until another
is hovered or the pointer leaves the content area, which resets all of it and returns the preview
to its idle casting."""

import player
import skill
import uiScriptLocale
import uiSelectSkill

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/select-skill/select-skill.rml"
KEY = "select-skill"
# NOVA-263 (r48: showing the window and its preview took one 33 ms frame, of which 11.2 ms made the
# model and 6.0 ms loaded the document):
# - the preview's model is made off the frame (modelpreview.SetBackground; every motion, since it
#   casts skills): the view stays clear (a plain ring), then the model fades in, as the wiki's do;
#   a hidden nui-countdown (preview_check_at) looks again every PREVIEW_POLL seconds while it loads;
# - for a character that has not chosen its skill group yet (the only one the server opens the
#   window for), the board the window's making loads is kept, hidden and emptied, so the open
#   loads no document. KEEP_BOARD_UNTIL_CHOSEN False loads it at each open, as before.
BACKGROUND_PREVIEW = True
KEEP_BOARD_UNTIL_CHOSEN = True
PREVIEW_POLL = 0.1
CONTENT = "select-skill-content"
# The idle state: no side active, no skill hovered.
IDLE = {"active_group": 0, "hover_group": 0, "hover_slot": -1, "caption_name": "", "caption_tag": ""}
JOB_NAMES = {0: "WARRIOR", 1: "ASSASSIN", 2: "SURA", 3: "SHAMAN"}


def _text(name, fallback=""):
	return getattr(uiScriptLocale, name, fallback)


def skill_text(vnum):
	"""(name, tag) of a skill as skilldesc.txt has them: its name and its first condition line
	(the design's tag, "Frontal Slash Attack 3 times"); ("", "") for one the client lacks."""
	try:
		name = skill.GetSkillName(vnum)
	except Exception:
		return ("", "")
	try:
		tag = skill.GetSkillConditionDescription(vnum, 0) or ""
	except Exception:
		tag = ""
	return (str(name).strip(), str(tag).strip())


def skill_group():
	"""The character's skill group (net.GetMainActorSkillGroup, known from the loading screen on;
	0: not chosen), None when the client cannot say."""
	try:
		import net
		return int(net.GetMainActorSkillGroup())
	except Exception:
		return None


def _preview_pending():
	"""The preview's request still waits for its model (GetState's pending)."""
	preview = uiSelectSkill.model_preview()
	get_state = getattr(preview, "GetState", None) if preview is not None else None
	if get_state is None:
		return False
	try:
		state = get_state(uiSelectSkill.PREVIEW)
	except Exception:
		return False
	return bool(state.get("pending")) if isinstance(state, dict) else False


def plays_like(job, group):
	"""The group's "plays like" line (SELECT_SKILL_PLAYS_<JOB>_<group>, draft copy)."""
	return _text("SELECT_SKILL_PLAYS_%s_%d" % (JOB_NAMES.get(job, ""), group))


class _SelectSkillBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The window's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "select_skill"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		self.element_on(CONTENT, "mouseout", self.nui_content_out)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.Close()

	@nui.on("pick_press")
	def on_pick_press(self, group, button):
		self.raise_for(button)
		if button == 0:
			self._owner.nui_pick(int(group))

	@nui.on("cell_press")
	def on_cell_press(self, group, index, button):
		self.raise_for(button)
		self._owner.nui_cell_events(int(group)).press(int(index), button)

	@nui.on("cell_over")
	def on_cell_over(self, group, index):
		self._owner.nui_cell_events(int(group)).over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, group, index):
		self._owner.nui_cell_events(int(group)).out(int(index))

	@nui.on("side_over")
	def on_side_over(self, group):
		self._owner.nui_side(int(group))

	# NOVA-263: the preview's model, made over the client's next steps.
	@nui.on("preview_check")
	def on_preview_check(self):
		self._owner.preview_check()

	def nui_content_out(self, event):
		"""RmlUi has no mouseleave: the content element's own mouseout (a child's bubbles here too,
		with the child as its target) is the pointer leaving the content area."""
		if event.get("target_id") == CONTENT:
			self._owner.nui_leave()


class _PreviewView(object):
	"""The render target's place on the board: the nui-view, shown while legacy shows it."""

	def __init__(self, owner):
		self.owner = owner

	def Show(self):
		self.owner.nui_set(model_view=True)

	def Hide(self):
		self.owner.nui_set(model_view=False)


class SelectSkillWindow(nui_facade.Facade, uiSelectSkill.SelectSkillWindow):
	"""uiSelectSkill.SelectSkillWindow on NovaUI (Interface.wndSelectSkill)."""

	KEY = KEY
	BOARD = _SelectSkillBoard
	PLACE = "center"
	BACKGROUND_PREVIEW = BACKGROUND_PREVIEW

	# ui.Window.__init__ calls Hide before these exist.
	_group_events = None

	def __init__(self):
		self.nui_begin()
		try:
			uiSelectSkill.SelectSkillWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		model = {
			"groups": [self._group(1), self._group(2)],
			"model_view": False,
			# NOVA-263: the model is still being made (the view clear), and the clock that looks
			# again at it.
			"preview_loading": False,
			"preview_check_at": 0.0,
			# P15 F-2: nui_slots.ATTACH_RIGHT (the ring's nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
		}
		model.update(IDLE)
		return model

	def _group(self, group):
		return {"group": group, "name": "", "plays": "", "choose": "", "cells": []}

	def nui_demand(self):
		"""NOVA-263: a character without a skill group keeps the board the window's making loads,
		hidden and emptied (KEEP_BOARD_UNTIL_CHOSEN), so the open loads no document; any other
		loads it at an open, as before (the server opens the window for the first only)."""
		keep = KEEP_BOARD_UNTIL_CHOSEN and skill_group() == 0
		return nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board,
		                         keep_probe=keep)

	def _empty_board(self, board):
		"""A kept hidden board holds no skill and no view and runs no clock (RmlUi updates every
		loaded document each frame); _restore_board sets them again at the next show."""
		board.set(groups=[self._group(1), self._group(2)], model_view=False, preview_loading=False,
		          preview_check_at=0.0)

	# --- the preview's model, made off the frame (NOVA-263) -----------------------------

	def _PreviewAsked(self):
		"""After every Select, motion and show: while the request waits, the view is clear and the
		clock looks again."""
		self._watch_preview(_preview_pending())

	def _watch_preview(self, loading):
		armed = self._state.get("preview_check_at", 0.0) > 0
		values = {}
		if bool(self._state.get("preview_loading")) != loading:
			values["preview_loading"] = loading
		if loading and not armed:
			values["preview_check_at"] = nui.now() + PREVIEW_POLL
		elif not loading and armed:
			values["preview_check_at"] = 0.0
		if values:
			self.nui_set(**values)

	def preview_check(self):
		"""The preview_check_at clock's end: a model still being made keeps the view clear and the
		clock running; a made one gets its camera and hovered skill back and fades in."""
		if _preview_pending():
			self.nui_set(preview_check_at=nui.now() + PREVIEW_POLL)
			return
		self._PreviewMade()
		self.nui_set(preview_loading=False, preview_check_at=0.0)

	def _set_group(self, group, **values):
		groups = [dict(entry) for entry in self._state["groups"]]
		groups[group - 1].update(values)
		self.nui_set(groups=groups)

	def _on_cells(self, group, cells):
		"""The skills that exist (a skill the client lacks is an empty cell), in slot order, each
		with its name and tag; a cell's index stays its legacy slot."""
		job = player.GetJob()
		vnums = uiSelectSkill.SKILL_INDEX_DICT.get(job, uiSelectSkill.SKILL_INDEX_DICT[0])[group]
		shown = []
		for cell in cells:
			if cell.get("kind") == "" or cell.get("icon") == "":
				continue
			name, tag = skill_text(vnums[cell["index"]])
			shown.append(dict(cell, name=name, tag=tag))
		self._set_group(group, cells=shown, plays=plays_like(job, group))

	def _caption(self, group, slot):
		for cell in self._state["groups"][group - 1]["cells"]:
			if cell["index"] == slot:
				return (cell["name"], cell["tag"])
		return ("", "")

	# --- the orbit's hover --------------------------------------------------------------

	def nui_side(self, group):
		"""The pointer over a side panel: its group is active, the other side dims."""
		if self._state["active_group"] != group:
			self.nui_set(active_group=group)

	def nui_hover(self, group, slot):
		"""A skill hovered, on the ring or in its side's list: lit in both, named under the ring."""
		name, tag = self._caption(group, slot)
		self.nui_set(active_group=group, hover_group=group, hover_slot=slot, caption_name=name, caption_tag=tag)

	def nui_leave(self):
		"""The pointer left the content area: idle again, and a preview that cast a hovered skill
		back to its cycle (one that never left it keeps its cast)."""
		hovered = self._state["hover_group"] != 0
		self.nui_set(**IDLE)
		if hovered:
			self._SelectSkillWindow__ApplyPreview()

	def OverInItem1(self, slotNumber):
		self.nui_hover(1, slotNumber)
		uiSelectSkill.SelectSkillWindow.OverInItem1(self, slotNumber)

	def OverInItem2(self, slotNumber):
		self.nui_hover(2, slotNumber)
		uiSelectSkill.SelectSkillWindow.OverInItem2(self, slotNumber)

	def OverOutItem(self):
		"""Leaving a skill hides its tooltip; the skill stays lit and cast until another skill is
		hovered or the pointer leaves the content area (nui_leave)."""
		if self.toolTipSkill:
			self.toolTipSkill.HideToolTip()

	# --- the loader (uiselectskill.py _LoadScript, on proxies) ----------------------------

	def _LoadScript(self):
		# The uiscript's style (selectskillwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		count = uiSelectSkill.MAX_SKILL_NUM
		self.Button1 = self._group_button(1)
		self.Button2 = self._group_button(2)
		self.SkillGroup1 = nui_slots.SlotWindowProxy(range(count), lambda cells: self._on_cells(1, cells), cols=count, rows=1)
		self.SkillGroup2 = nui_slots.SlotWindowProxy(range(count), lambda cells: self._on_cells(2, cells), cols=count, rows=1)
		self._group_events = {
			1: self.nui_events(nui_slots.LegacySlotEvents(self.SkillGroup1)),
			2: self.nui_events(nui_slots.LegacySlotEvents(self.SkillGroup2)),
		}
		self.previewView = _PreviewView(self) if uiSelectSkill.model_preview() is not None else None

	def _group_button(self, group):
		def name_changed(button):
			name = nui.plain_text(button.text)
			self._set_group(group, name=name, choose=_text("SELECT_SKILL_CHOOSE", "%s") % name)
		return nui_proxies.ButtonProxy(on_change=name_changed)

	def nui_cell_events(self, group):
		return self._group_events[group]

	def nui_pick(self, group):
		(self.Button1 if group == 1 else self.Button2).click()

	# --- what NovaUI changes -----------------------------------------------------------

	def nui_on_hide(self):
		"""The board goes: the next open starts idle."""
		nui_facade.Facade.nui_on_hide(self)
		self._state.update(IDLE)

	def Hide(self):
		"""Every way the window goes (Close, the Interface's hide) stops the preview."""
		nui_facade.Facade.Hide(self)
		if self._group_events is not None:
			self._SelectSkillWindow__StopPreview()
