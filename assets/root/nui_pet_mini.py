"""NovaUI pet mini window (nui/windows/pet-mini/pet-mini.rml; NOVA-24).

While the "pet-mini" window is on, the Interface makes PetInterfaceWindow
below through nui_windows.make() instead of uiPet.PetInterfaceWindow: a
subclass of the legacy class (nui_facade.Facade) whose loader puts proxies
where the uiscript's widgets were (petinterfacewindow.py): the pet's icon,
the name and level line, the grade line, the exp gauge, the 13 small skill
cells and their disabled overlays. Open (BINARY_PetSummon), Close
(BINARY_PetUnsummon), Refresh, RefreshStatus, RefreshSkillSlot, the skill
tooltip and the revert drop are legacy's code.

Folding and opening: legacy animates the board's size and the icon's place
every frame (OnUpdate, __TickAnimation) and folds 30 seconds after an open.
Here the fold is the board's class (open), which the sheets animate with a
transition (none under reduced motion), and the 30 seconds are a
nui-countdown whose countdownend calls legacy's __StartMinimize: no Python
runs while it counts. A CSS transition delay with transitionend would not
do, since reduced motion turns transitions off and its end would never come.
So legacy's __OnImageClick, __StartMinimize and the two layouts are
overridden with the class change; legacy's timing constants stay
(_EXPAND_SECS). Legacy's OnUpdate also re-ran the shown text tooltip; the
hint follows legacy's RefreshStatus instead (the exp tooltip writes the
board's hint while the pointer is over the gauge)."""

import app
import pet
import uiPet
import uiToolTip

import nui
import nui_facade
import nui_hud
import nui_pet
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/pet-mini/pet-mini.rml"
KEY = "pet-mini"
SKILL_SLOTS = tuple(range(13))


class _PetMiniBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The mini window's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "pet_mini"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("image_press")
	def on_image_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["image"].fire("OnMouseLeftButtonDown")

	@nui.on("exp_over")
	def on_exp_over(self):
		self._owner.main["ExpBar"].fire("OnMouseOverIn")

	@nui.on("exp_out")
	def on_exp_out(self):
		self._owner.main["ExpBar"].fire("OnMouseOverOut")

	@nui.on("fold_due")
	def on_fold_due(self):
		self._owner.fold_due()

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


class PetInterfaceWindow(nui_facade.Facade, uiPet.PetInterfaceWindow):
	"""uiPet.PetInterfaceWindow on NovaUI (Interface.wndPetInterfaceWindow)."""

	KEY = KEY
	BOARD = _PetMiniBoard
	PLACE = None

	def __init__(self):
		self.nui_begin()
		try:
			uiPet.PetInterfaceWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"open": False,
			# The clock (nui.now() seconds) the open board folds at; 0 folded.
			"fold_at": 0.0,
			"icon": "",
			"title": "",
			"evolution": "",
			"evolution_color": nui_pet.GRADE_COLOR,
			"exp": 0.0,
			"cells": [nui_slots.empty_cell(i) for i in range(len(SKILL_SLOTS))],
			"disabled": [True] * len(SKILL_SLOTS),
			"hint": "",
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
		}

	# --- the proxies' callbacks ---------------------------------------------------------------

	def _on_title(self, text):
		self.nui_set(title=nui.plain_text(text))

	def _on_evolution(self, text):
		main = getattr(self, "main", None)
		proxy = main["evo"] if main else None
		self.nui_set(evolution=nui_pet.line_text(text),
		             evolution_color=nui_pet.color_of(proxy.color if proxy is not None else None) or nui_pet.GRADE_COLOR)

	def _on_icon(self, path):
		self.nui_set(icon=nui_slots.icon_source(path))

	def _on_exp(self, fraction):
		self.nui_set(exp=fraction)

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

	# --- the loader (uipet.py PetInterfaceWindow.__LoadWindow, on proxies) ---------------------

	def _PetInterfaceWindow__LoadWindow(self):
		"""Legacy's __LoadWindow with proxies where the uiscript's widgets
		were (petinterfacewindow.py); the bindings are legacy's."""
		self.AddFlag("movable")
		self.AddFlag("float")
		on_disabled = self._on_disabled
		self.main = {
			"title": nui_proxies.TextProxy(self._on_title),
			"evo": nui_pet.ColorTextProxy(self._on_evolution),
			"image": nui_pet.ImageProxy(self._on_icon),
			"ExpBar": nui_pet.ImageProxy(on_fill=self._on_exp),
			"skill": nui_pet.SkillSlotProxy(SKILL_SLOTS, self._on_cells),
			"skill_disabled": [nui_proxies.WindowProxy(on_disabled) for i in range(pet.SKILL_MAX_NUM)],
		}
		self.board = nui_proxies.BoardProxy(self._DEFAULT_W, self._DEFAULT_H)
		self.expBarBG = nui_proxies.WindowProxy()
		self.mainSlotImg = nui_proxies.WindowProxy()
		self.slotEffect = nui_proxies.WindowProxy()
		self._extras = [self.main["title"], self.main["evo"], self.expBarBG, self.main["skill"]]
		self._PetInterfaceWindow__CacheIconBasePositions()

		self.itemToolTip = nui_pet.make_tooltip(uiToolTip.ItemToolTip, "nui_item_tooltip.ItemToolTip")
		self.itemToolTip.HideToolTip()

		self.skillToolTip = nui_pet.make_tooltip(uiToolTip.PetSkillToolTip, "nui_pet_skill_tooltip.PetSkillToolTip")
		self.skillToolTip.HideToolTip()

		self.textToolTip = nui_pet.TextToolTipProxy(self._on_hint)
		self.textToolTip.Hide()

		uiPet.SetStringEvent(self.main["image"], "MOUSE_LEFT_DOWN", self._PetInterfaceWindow__OnImageClick)
		uiPet.SetStringEvent(self.main["ExpBar"], "MOUSE_OVER_IN", lambda func=self._PetInterfaceWindow__OverInExp: self._PetInterfaceWindow__ShowTextToolTip(func))
		uiPet.SetStringEvent(self.main["ExpBar"], "MOUSE_OVER_OUT", lambda: self.textToolTip.Hide())

		self.main["skill"].SetOverInItemEvent(self._PetInterfaceWindow__OverInSkillSlot)
		self.main["skill"].SetOverOutItemEvent(self._PetInterfaceWindow__OverOutSkillSlot)
		self.main["skill"].SetSelectItemSlotEvent(self._PetInterfaceWindow__ClickSkillSlot)
		self._cell_events = nui_pet.skill_events(self, self.main["skill"], self._on_states)

		self._PetInterfaceWindow__ApplyMinimizedLayout()

	# --- the fold: a class change and a countdown (module docstring) --------------------------

	def _set_open(self, flag):
		self._animActive = False
		self._isMinimized = not flag
		self._expandUntil = (app.GetTime() + float(self._EXPAND_SECS)) if flag else 0.0
		self.nui_set(open=bool(flag), fold_at=(nui.now() + float(self._EXPAND_SECS)) if flag else 0.0)

	def _PetInterfaceWindow__ApplyMinimizedLayout(self):
		self._set_open(False)

	def _PetInterfaceWindow__ApplyExpandedLayout(self):
		self._set_open(True)

	def _PetInterfaceWindow__OnImageClick(self):
		"""Legacy's toggle: a folded window opens for 30 seconds, an open one
		folds."""
		if self._isMinimized:
			self._set_open(True)
		else:
			self._PetInterfaceWindow__StartMinimize()

	def _PetInterfaceWindow__StartMinimize(self):
		"""Legacy's: the tooltips go and the window folds (the sheets animate
		it)."""
		self.skillToolTip.Hide()
		self.itemToolTip.Hide()
		self.textToolTip.Hide()
		self._set_open(False)

	def fold_due(self):
		"""The board's countdown ended: legacy's fold, once the 30 seconds of
		the last open are up."""
		if not self._isMinimized:
			self._PetInterfaceWindow__StartMinimize()

	def RefreshSkillSlot(self):
		uiPet.PetInterfaceWindow.RefreshSkillSlot(self)
		self._on_disabled()
