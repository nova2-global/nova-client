"""NovaUI aura level window (nui/windows/aura/aura.rml; Wave 6, NOVA-23).

While the aura flag is on, game.BINARY_AuraPacket makes AuraWindow below
through nui_windows.make() instead of uiAura.AuraWindow, at the server's
first GC::AURA: a subclass of the legacy class (nui_facade.Facade) whose
loader puts proxies where the uiscript's widgets were: the two cells (a
SlotWindowProxy over slots 0 and 1, item.AURA_SLOT_MAIN and
AURA_SLOT_MATERIAL), the level, percentage and experience lines, the
experience gauge's background and fill, the title bar and the two buttons.
So the cells, the material's count, the level and experience texts, the
gauge's width, the cell locks in both inventories (SetCantMouseEventCell),
the tooltips (SetInventoryItem with the item's window) and the
"/aura add|remove|leveling|close" chat commands are legacy's code.

The loader: legacy's LoadWindow (uiaura.py:76-113) is public and mixes the
uiscript load with the bindings, so this module replicates it on proxies
(the isLoaded guard, the uiscript's "movable" and "float" style, the same
eight bindings, the closing Hide) instead of adding a seam to uiaura.py;
tools/nui_aura_test.py's LoaderBindsAsLegacy compares every binding with
legacy's.

The gauge: legacy sizes ExpGaugeFill to `width` of EXP_GAUGE_MAX_WIDTH (188)
pixels (uiaura.py:167-178) and hides it and its background while no aura is
in (:146-157). The board shows the fill as the fraction width / 188 on a
code-drawn nui-gauge, and the track only while legacy shows the background.

What legacy did every frame happens without Python: the walk-away rule of
OnUpdate (uiaura.py:281-286: 1000 units or more from the open position on
either axis runs OnClose once) is a nuigame.WatchLeaveRange watch, armed by
Open and stopped by Hide, whose callback is legacy's OnClose. The watch
fires past `range` (|d| > range) where legacy fires at |d| >= 1000, so the
range is the double just under LIMIT_RANGE (math.nextafter): the engine takes
it as a double, and |d| > that is |d| >= 1000. The board exists only while
the window shows."""

import math

import nuigame
import ui
import uiAura

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/aura/aura.rml"
KEY = "aura"
# Legacy's LIMIT_RANGE (uiaura.py:19), less one ulp: see the module docstring
# for > and >=.
LEAVE_RANGE = math.nextafter(float(getattr(uiAura, "LIMIT_RANGE", 1000)), 0.0)
# Legacy's EXP_GAUGE_MAX_WIDTH (uiaura.py:20): the fill's full width.
GAUGE_WIDTH = getattr(uiAura, "EXP_GAUGE_MAX_WIDTH", 188)
# The uiscript's bar height (aura_levelupwindow.py: ExpGaugeBG, ExpGaugeFill).
GAUGE_HEIGHT = 12
# The slot window's two slots (item.AURA_SLOT_MAIN 0, AURA_SLOT_MATERIAL 1).
SLOTS = (0, 1)


class BarProxy(nui_proxies.WindowProxy):
	"""ui.Bar (the uiscript's "bar": ExpGaugeBG and ExpGaugeFill): Show, Hide
	and SetSize recorded (the uiscript's size first), GetWidth and GetHeight
	answering the last size; on_change(proxy) runs after each change."""

	def __init__(self, width, height, on_change=None):
		nui_proxies.WindowProxy.__init__(self)
		self.size = (int(width), int(height))
		self.on_change = on_change

	def _changed(self):
		if self.on_change is not None:
			self.on_change(self)

	def Show(self):
		self.shown = True
		self._changed()

	def Hide(self):
		self.shown = False
		self._changed()

	def SetSize(self, width, height):
		self.size = (int(width), int(height))
		self._changed()

	def GetWidth(self):
		return self.size[0]

	def GetHeight(self):
		return self.size[1]


class _AuraBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The aura window's document; its events go to its window. A press on
	it raises the window, as legacy's window manager does ("float")."""

	DOCUMENT = DOCUMENT
	MODEL = "aura"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

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

	@nui.on("accept_press")
	def on_accept_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnAccept.click()

	@nui.on("cancel_press")
	def on_cancel_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnCancel.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()


class AuraWindow(nui_facade.Facade, uiAura.AuraWindow):
	"""uiAura.AuraWindow on NovaUI (GameWindow.auraWindow)."""

	KEY = KEY
	LEAVE_RANGE = True
	BOARD = _AuraBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiAura.AuraWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"cells": [nui_slots.empty_cell(i) for i in range(len(SLOTS))],
			# LevelText, ExpPercentText and ExpText: legacy's texts.
			"level": "",
			"percent": "",
			"exp": "",
			# ExpGaugeBG shown (the track), and the fill as width / 188.
			"gauge": True,
			"fill": 0.0,
			# P15 F-2: nui_slots.ATTACH_RIGHT (the cells' nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.auraSlot.cells(), states, picked))

	def _on_level(self, text):
		self.nui_set(level=nui.plain_text(text))

	def _on_percent(self, text):
		self.nui_set(percent=nui.plain_text(text))

	def _on_exp(self, text):
		self.nui_set(exp=nui.plain_text(text))

	def _on_gauge(self, bar):
		self.nui_set(gauge=bool(bar.shown))

	def _on_fill(self, bar):
		"""Legacy's fill width as the fraction of its full width (0 while the
		fill is hidden), clamped to the track."""
		fraction = float(bar.size[0]) / float(GAUGE_WIDTH) if bar.shown and GAUGE_WIDTH else 0.0
		self.nui_set(fill=min(1.0, max(0.0, fraction)))

	# --- the loader (uiaura.py LoadWindow, on proxies) -----------------------------------

	def LoadWindow(self):
		"""Legacy's LoadWindow (uiaura.py:76-113) with proxies where the
		uiscript's widgets were (aura_levelupwindow.py); the bindings are
		legacy's, one for one."""
		if self.isLoaded:
			return

		self.isLoaded = 1

		# The uiscript's style ("movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.titleBar = nui_proxies.BoardProxy(235, 23)
		self.titleName = nui_proxies.TextProxy()
		self.btnAccept = nui_proxies.ButtonProxy()
		self.btnCancel = nui_proxies.ButtonProxy()
		self.auraSlot = nui_slots.SlotWindowProxy(SLOTS, self._on_cells)
		self.levelText = nui_proxies.TextProxy(self._on_level)
		self.expGaugeBG = BarProxy(GAUGE_WIDTH, GAUGE_HEIGHT, self._on_gauge)
		self.expGaugeFill = BarProxy(0, GAUGE_HEIGHT, self._on_fill)
		self.expPercentText = nui_proxies.TextProxy(self._on_percent)
		self.expText = nui_proxies.TextProxy(self._on_exp)

		self.auraSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.OnSelectEmptySlot))
		self.auraSlot.SetUnselectItemSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.auraSlot.SetUseSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.auraSlot.SetOverInItemEvent(ui.__mem_func__(self.OnOverInItem))
		self.auraSlot.SetOverOutItemEvent(ui.__mem_func__(self.OnOverOutItem))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnClose))
		self.btnCancel.SetEvent(ui.__mem_func__(self.OnClose))
		self.btnAccept.SetEvent(ui.__mem_func__(self.OnAccept))

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(self.auraSlot, on_states=self._on_states))

		self.Hide()

	# --- what NovaUI changes -----------------------------------------------------------

	def Open(self):
		"""Legacy's, then the walk-away watch (legacy's OnUpdate rule), whose
		callback is legacy's OnClose."""
		uiAura.AuraWindow.Open(self)
		nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self.OnClose), False)

	def Hide(self):
		"""The facade's, then the watch stops (an exe without the Wave 4
		engine has no watch; make() keeps the legacy window there)."""
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			stop = getattr(nuigame, "StopLeaveRange", None)
			if stop is not None:
				stop(KEY)
