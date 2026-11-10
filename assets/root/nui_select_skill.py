"""NovaUI select skill window (nui/windows/select-skill/select-skill.rml; NOVA-37).

While the select-skill flag is on, Interface.__MakeWindows makes SelectSkillWindow below
through nui_windows.make() instead of uiSelectSkill.SelectSkillWindow: a subclass of the legacy
class (nui_facade.Facade) whose loader (_LoadScript) puts proxies where the widgets were (the
two buttons, the two rows of skill slots), so the job's skills, their tooltips, the preview's
model and motion, and the /select_skill it sends are legacy's code. The preview is the nui-view
"model-select-skill" (legacy's render target of the same model); a client without render targets
shows a mark. The board exists only while the window shows."""

import uiSelectSkill

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/select-skill/select-skill.rml"
KEY = "select-skill"


class _SelectSkillBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The window's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "select_skill"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

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
		return {
			"groups": [self._group(1), self._group(2)],
			"model_view": False,
			# P15 F-2: nui_slots.ATTACH_RIGHT (the rows' nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
		}

	def _group(self, group):
		return {"group": group, "name": "", "cells": [nui_slots.empty_cell(i) for i in range(uiSelectSkill.MAX_SKILL_NUM)]}

	def _set_group(self, group, **values):
		groups = [dict(entry) for entry in self._state["groups"]]
		groups[group - 1].update(values)
		self.nui_set(groups=groups)

	def _on_cells(self, group, cells):
		self._set_group(group, cells=cells)

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
			self._set_group(group, name=nui.plain_text(button.text))
		return nui_proxies.ButtonProxy(on_change=name_changed)

	def nui_cell_events(self, group):
		return self._group_events[group]

	def nui_pick(self, group):
		(self.Button1 if group == 1 else self.Button2).click()

	# --- what NovaUI changes -----------------------------------------------------------

	def Hide(self):
		"""Every way the window goes (Close, the Interface's hide) stops the preview."""
		nui_facade.Facade.Hide(self)
		if self._group_events is not None:
			self._SelectSkillWindow__StopPreview()
