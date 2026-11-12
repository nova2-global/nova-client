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
			# P15 F-2: nui_slots.ATTACH_RIGHT (the ring's nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
		}
		model.update(IDLE)
		return model

	def _group(self, group):
		return {"group": group, "name": "", "plays": "", "choose": "", "cells": []}

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
