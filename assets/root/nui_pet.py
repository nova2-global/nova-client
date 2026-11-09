"""NovaUI pet window (nui/windows/pet/pet.rml; NOVA-24).

While the "pet" window is on, the Interface makes PetWindow below through
nui_windows.make() instead of uiPet.PetWindow, twice: the own pet's window
(key P, wndPetWindow) and the preview window (wndPetPreviewWindow, Open(True)
from BINARY_PetPreview). It is a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the uiscript's widgets
were (petwindow.py): the portrait, the name, level and grade lines, the exp
gauge, the evolve button, the three bonus rows (name, level, plus button),
the 13 skill cells and their disabled overlays, the close button. Open,
Refresh, RefreshStatus, RefreshSkillSlot, the evolve gate, the bonus and skill
tooltips, the refine and evolution requests and the revert drop
(pet.UseResetSkill) are legacy's code.

Two windows at once: KEY is None (no instance takes the other over) and the
board is INSTANCED (each binds its own model, "pet_<n>").

What legacy did every frame happens without Python: legacy's OnUpdate re-ran
the shown text tooltip's update (the exp and bonus lines) each frame; the
legacy RefreshStatus now re-runs it, and BINARY_PetRefreshStatus calls it on
every change. The text tooltip (legacy's TextToolTip, a TOP_MOST window that
follows the pointer in OnRender) is the board's hint line under the gauge.

Proxies shared with the other pet windows (nui_pet_mini, nui_pet_hatch,
nui_pet_evolution, nui_pet_attr_refine) live here."""

import pet
import ui
import uiPet
import uiToolTip

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots
import nui_text

DOCUMENT = "nui/windows/pet/pet.rml"
SKILL_SLOTS = tuple(range(13))
ATTR_COUNT = 3
# OLD's label color (uipet.LABEL_COLOR), the grade line's before legacy sets its own.
GRADE_COLOR = "#fee3ae"


def color_of(packed):
	"""A legacy packed ARGB font color as "#rrggbb" ("" for none)."""
	if packed is None:
		return ""
	return "#%06x" % (int(packed) & 0xFFFFFF)


def line_text(text):
	"""Legacy's line without its color tags (uipet.LabelText's gold label):
	the sheets color the lines, so they read in every theme."""
	return nui.plain_text(nui_text.visible_text(text or ""))


def skill_icon(path):
	"""The icon of a pet skill as <img src> takes it. OLD's art is GIF, which
	NEW's client loads nowhere (ScriptLib/Resource.cpp; NovaUI's NuiPaths.h):
	the art ships as PNG beside the name C's module builds."""
	path = str(path or "")
	if path.lower().endswith(".gif"):
		path = path[:-4] + ".png"
	return nui_slots.icon_source(path)


def make_tooltip(legacy_class, controller):
	"""A tooltip as the Interface makes its own: through the factory under
	"tooltips" (the NovaUI facade while that window is on)."""
	import nui_windows
	return nui_windows.make("tooltips", legacy_class, controller)


class ButtonProxy(nui_proxies.ButtonProxy):
	"""ui.Button as the pet windows use it: SAFE_SetEvent (the event held
	as ui.__mem_func__ holds it), Flash (the evolve button at a gate; the
	board blinks it until Disable), SetText."""

	def __init__(self, on_change=None):
		nui_proxies.ButtonProxy.__init__(self, on_change)
		self.flash = False

	def SAFE_SetEvent(self, func, *args):
		self.SetEvent(nui_proxies._weak_method(func), *args)

	def Flash(self):
		self.flash = True
		self._changed()

	def Disable(self):
		self.flash = False
		nui_proxies.ButtonProxy.Disable(self)


class ColorTextProxy(nui_proxies.TextProxy):
	"""ui.TextLine whose color the board shows: SetPackedFontColor runs
	on_text again (legacy sets the grade's color after its text)."""

	def SetPackedFontColor(self, color):
		nui_proxies.TextProxy.SetPackedFontColor(self, color)
		nui_proxies._call(self.on_text, self.text)


class ImageProxy(nui_proxies.ImageProxy):
	"""ui.ImageBox and ExpandedImageBox as the pet windows use them: the image
	(on_image), Show and Hide (on_show), the gauge's SetPercentage (on_fill,
	the fraction), and the handlers uipet.SetStringEvent sets on the
	instance (OnMouseOverIn, OnMouseOverOut, OnMouseLeftButtonDown), which the
	board's events call."""

	def __init__(self, on_image=None, on_show=None, on_fill=None):
		nui_proxies.ImageProxy.__init__(self, on_image)
		self.on_show = on_show
		self.on_fill = on_fill
		self.fraction = 0.0
		self.position = (0, 0)

	def SetPercentage(self, curValue, maxValue):
		self.fraction = min(1.0, max(0.0, float(curValue) / float(maxValue))) if maxValue else 0.0
		nui_proxies._call(self.on_fill, self.fraction)

	def SetPosition(self, x, y):
		self.position = (int(x), int(y))

	def GetLocalPosition(self):
		return self.position

	def fire(self, name):
		"""One of the handlers legacy set (nothing when none is set)."""
		handler = self.__dict__.get(name)
		if handler is not None:
			handler()


class TextToolTipProxy(nui_proxies._Shown):
	"""uiPet.TextToolTip: SetText, Show, Hide, IsShow and the updateFunc
	legacy keeps on it; the board shows the text as its hint line."""

	def __init__(self, on_change):
		self.shown = False
		self.text = ""
		self.updateFunc = None
		self.on_change = on_change

	def SetText(self, text):
		self.text = "" if text is None else str(text)
		nui_proxies._call(self.on_change, self)

	def Show(self):
		self.shown = True
		nui_proxies._call(self.on_change, self)

	def Hide(self):
		self.shown = False
		nui_proxies._call(self.on_change, self)


class SkillSlotProxy(nui_slots.SlotWindowProxy):
	"""The skill cells (ui.SlotWindow) with ui.py's SetPetSkillSlot: the
	skill's icon (pet.GetSkillProtoIconPath) and its level as the count; OLD's
	scale is the document's cell size."""

	def SetPetSkillSlot(self, slot, vnum, skillLevel, scalex=1.0, scaley=1.0):
		if not self._holds(slot):
			return
		icon = skill_icon(pet.GetSkillProtoIconPath(vnum))
		if not icon:
			self.ClearSlot(slot)
			return
		record = self._record(int(slot))
		record.update({"kind": "skill", "vnum": int(vnum), "icon": icon, "w": 1, "h": 1,
		               "count": str(int(skillLevel)) if skillLevel and int(skillLevel) > 0 else ""})
		record.update(nui_slots.CLEARED_STATES)


def skill_events(owner, slot, on_states):
	"""The skill cells' legacy events (a select runs legacy's revert drop,
	a hover its skill tooltip)."""
	return owner.nui_events(nui_slots.LegacySlotEvents(slot, on_states=on_states))


class SlotBoardMixin(object):
	"""The cell events every pet board with cells shares."""

	@nui.on("cell_press")
	def on_cell_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_events.press(int(index), button)

	@nui.on("cell_release")
	def on_cell_release(self, index, button):
		self._owner._cell_events.release(int(index), button)

	@nui.on("cell_use")
	def on_cell_use(self, index):
		self._owner._cell_events.use(int(index))

	@nui.on("cell_drop")
	def on_cell_drop(self, index):
		self._owner._cell_events.drop(int(index))

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._cell_events.out(int(index))


class _PetBoard(SlotBoardMixin, nui_hud.RaisesOnPress, nui.Window):
	"""The pet window's document (one per window: own and preview)."""

	DOCUMENT = DOCUMENT
	MODEL = "pet"
	INSTANCED = True

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
			self._owner.closeButton.click()

	@nui.on("evolve_press")
	def on_evolve_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["evolution_upgrade"].click()

	@nui.on("plus_press")
	def on_plus_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["bonus"][int(index)]["plus"].click()

	@nui.on("level_press")
	def on_level_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["bg"][int(index)]["level"].fire("OnMouseLeftButtonDown")

	@nui.on("bonus_over")
	def on_bonus_over(self, index):
		self._owner.main["bg"][int(index)]["level"].fire("OnMouseOverIn")

	@nui.on("bonus_out")
	def on_bonus_out(self, index):
		self._owner.main["bg"][int(index)]["level"].fire("OnMouseOverOut")

	@nui.on("exp_over")
	def on_exp_over(self):
		self._owner.main["PetExpBar"].fire("OnMouseOverIn")

	@nui.on("exp_out")
	def on_exp_out(self):
		self._owner.main["PetExpBar"].fire("OnMouseOverOut")


def empty_model():
	return {
		"preview": False,
		# The name, level and grade lines: legacy's texts with its color tags.
		"name": "",
		"level": "",
		"evolution": "",
		"evolution_color": GRADE_COLOR,
		"portrait": "",
		"exp": 0.0,
		"evolve_shown": False,
		"evolve_enabled": False,
		"evolve_flash": False,
		"bonuses": [{"name": "", "level": "", "plus": False} for _ in range(ATTR_COUNT)],
		"cells": [nui_slots.empty_cell(i) for i in range(len(SKILL_SLOTS))],
		"disabled": [True] * len(SKILL_SLOTS),
		"hint": "",
		"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
	}


class PetWindow(nui_facade.Facade, uiPet.PetWindow):
	"""uiPet.PetWindow on NovaUI (Interface.wndPetWindow and
	wndPetPreviewWindow)."""

	KEY = None
	BOARD = _PetBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiPet.PetWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return empty_model()

	# --- the proxies' callbacks -----------------------------------------------------------

	def _on_text(self, key):
		return lambda text: self.nui_set(**{key: line_text(text)})

	def _on_evolution(self, text):
		main = getattr(self, "main", None)
		proxy = main["PetEvolution"] if main else None
		self.nui_set(evolution=line_text(text), evolution_color=color_of(proxy.color if proxy is not None else None) or GRADE_COLOR)

	def _on_portrait(self, path):
		self.nui_set(portrait=nui_slots.icon_source(path))

	def _on_background(self, path):
		self.nui_set(preview=path.endswith("bg-preview.png"))

	def _on_exp(self, fraction):
		self.nui_set(exp=fraction)

	def _on_evolve(self, button):
		self.nui_set(evolve_shown=bool(button.shown), evolve_enabled=bool(button.enabled),
		             evolve_flash=bool(button.flash and button.enabled))

	def _on_bonus(self, *args):
		main = getattr(self, "main", None)
		if not main:
			return
		self.nui_set(bonuses=[{"name": nui.plain_text(row["name"].text), "level": nui.plain_text(row["level"].text),
		                       "plus": bool(row["plus"].shown)} for row in main["bonus"]])

	def _on_disabled(self, *args):
		main = getattr(self, "main", None)
		if main:
			self.nui_set(disabled=[bool(proxy.shown) for proxy in main["skill_disabled"]])

	def _on_hint(self, tip):
		self.nui_set(hint=nui.plain_text(tip.text) if tip.shown else "")

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.main["skill"].cells(), states, picked))

	# --- the loader (uipet.py PetWindow.__LoadWindow, on proxies) ----------------------------

	def _PetWindow__LoadWindow(self):
		"""Legacy's __LoadWindow (uipet.py) with proxies where the uiscript's
		widgets were (petwindow.py); the bindings are legacy's, one for one."""
		self.AddFlag("movable")
		self.AddFlag("float")
		on_disabled = self._on_disabled
		self.main = {
			"Background": ImageProxy(self._on_background),
			"PetImage": ImageProxy(self._on_portrait),
			"PetName": nui_proxies.TextProxy(self._on_text("name")),
			"PetLevel": nui_proxies.TextProxy(self._on_text("level")),
			"PetEvolution": ColorTextProxy(self._on_evolution),
			"PetExpBar": ImageProxy(on_fill=self._on_exp),
			"evolution_upgrade": ButtonProxy(self._on_evolve),
			"bonus": [{
				"name": nui_proxies.TextProxy(self._on_bonus),
				"level": nui_proxies.TextProxy(self._on_bonus),
				"plus": ButtonProxy(self._on_bonus),
			} for i in range(pet.ATTR_MAX_NUM)],
			"bg": [{
				"name": ImageProxy(),
				"level": ImageProxy(),
			} for i in range(pet.ATTR_MAX_NUM)],
			"skill": SkillSlotProxy(SKILL_SLOTS, self._on_cells),
			"skill_disabled": [nui_proxies.WindowProxy(on_disabled) for i in range(pet.SKILL_MAX_NUM)],
		}
		self.closeButton = ButtonProxy()
		self.closeButton.SetEvent(ui.__mem_func__(self.Close))

		self.itemToolTip = make_tooltip(uiToolTip.ItemToolTip, "nui_item_tooltip.ItemToolTip")
		self.itemToolTip.HideToolTip()

		self.skillToolTip = make_tooltip(uiToolTip.PetSkillToolTip, "nui_pet_skill_tooltip.PetSkillToolTip")
		self.skillToolTip.HideToolTip()

		self.textToolTip = TextToolTipProxy(self._on_hint)
		self.textToolTip.Hide()

		self.main["evolution_upgrade"].SetEvent(pet.RequestEvolutionInfo)

		uiPet.SetStringEvent(self.main["PetExpBar"], "MOUSE_OVER_IN", lambda func=self._PetWindow__OverInExp: self._PetWindow__ShowTextToolTip(func))
		uiPet.SetStringEvent(self.main["PetExpBar"], "MOUSE_OVER_OUT", lambda: self.textToolTip.Hide())

		for i in range(pet.ATTR_MAX_NUM):
			tmpfunc0 = lambda arg=i: self._PetWindow__ClickAttr(arg)
			uiPet.SetStringEvent(self.main["bg"][i]["level"], "MOUSE_LEFT_DOWN", lambda func=tmpfunc0: self._PetWindow__OnClickAttr(func))
			self.main["bonus"][i]["plus"].SetEvent(lambda arg=i: self._PetWindow__ClickAttr(arg))
			tmpfunc = lambda arg=i: self._PetWindow__OverInBonus(arg)
			uiPet.SetStringEvent(self.main["bg"][i]["level"], "MOUSE_OVER_IN", lambda func=tmpfunc: self._PetWindow__ShowTextToolTip(func))
			uiPet.SetStringEvent(self.main["bg"][i]["level"], "MOUSE_OVER_OUT", lambda: self.textToolTip.Hide())

		self.main["skill"].SetOverInItemEvent(self._PetWindow__OverInSkillSlot)
		self.main["skill"].SetOverOutItemEvent(self._PetWindow__OverOutSkillSlot)
		self.main["skill"].SetSelectItemSlotEvent(self._PetWindow__ClickSkillSlot)
		self._cell_events = skill_events(self, self.main["skill"], self._on_states)

		self.Refresh()

	def RefreshSkillSlot(self):
		"""Legacy's, then the cells to the board."""
		uiPet.PetWindow.RefreshSkillSlot(self)
		self._on_disabled()
