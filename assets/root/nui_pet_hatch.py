"""NovaUI pet hatch window (nui/windows/pet-hatch/pet-hatch.rml; NOVA-24).

While the "pet-hatch" window is on, the Interface makes PetHatchEggWindow
below through nui_windows.make() instead of uiPet.PetHatchEggWindow: a
subclass of the legacy class (nui_facade.DialogFacade) whose loader puts
proxies where the uiscript's widgets were (pethatcheggwindow.py): the title,
the egg's and the pet's cells, the name field, the price line and the hatch
button. Open (the egg's or, in rename mode, the seal's), the wait refusal of
decision Q2, the name check and its popup, pet.UseEgg and pet.ChangeName are
legacy's code.

The name field takes the keyboard, so the window is a modal (MODAL, on a
scrim, D12): Enter in the field is legacy's return event (the hatch), Escape
its escape event (Close). The field's text never enters the model: the
facade reads it when legacy's hatch reads it."""

import uiPet

import nui
import nui_facade
import nui_hud
import nui_pet
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/pet-hatch/pet-hatch.rml"
KEY = "pet-hatch"
FIELD = "pet-hatch-field"
# The uiscript's edit line (pet_name, input_limit 20).
NAME_MAX = 20
SLOTS = (0, 1)


class _PetHatchBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The hatch window's document; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "pet_hatch"
	MODAL = True

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc:
			self.element_on("", "keydown", self._on_key)
			self.element_on(FIELD, "keydown", self._on_key)

	def initial_model(self):
		return dict(self._initial)

	def _on_key(self, event):
		"""Legacy's edit line: Enter is its return event (the hatch), Escape
		its escape event (Close)."""
		if not self.is_visible():
			return None
		key = event.get("key_identifier")
		field = self._owner.main["name"]
		if key in (nui.KEY_RETURN, nui.KEY_NUMPADENTER):
			field.fire_return()
			return True
		if key == nui.KEY_ESCAPE:
			field.fire_escape()
			return True
		return None

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("hatch_press")
	def on_hatch_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["hatch"].click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["title"].close()


class PetHatchEggWindow(nui_facade.DialogFacade, uiPet.PetHatchEggWindow):
	"""uiPet.PetHatchEggWindow on NovaUI (Interface.wndPetEggHatch)."""

	KEY = KEY
	BOARD = _PetHatchBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiPet.PetHatchEggWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"title": "",
			"button": "",
			"price": "",
			"price_shown": True,
			"cells": [nui_slots.empty_cell(i) for i in range(len(SLOTS))],
			"max": NAME_MAX,
		}

	def _fields(self):
		main = getattr(self, "main", None)
		return (main["name"],) if main else ()

	# --- the proxies' callbacks ---------------------------------------------------------------

	def _on_title(self, text):
		self.nui_set(title=nui.plain_text(text))

	def _on_button(self, button):
		self.nui_set(button=nui.plain_text(button.text))

	def _on_price(self, text):
		self.nui_set(price=nui.plain_text(text))

	def _on_price_shown(self, shown):
		self.nui_set(price_shown=bool(shown))

	def _on_cells(self, cells):
		self.nui_set(cells=cells)

	# --- the loader (uipet.py PetHatchEggWindow.__LoadWindow, on proxies) -----------------------

	def _PetHatchEggWindow__LoadWindow(self):
		"""Legacy's __LoadWindow with proxies where the uiscript's widgets
		were (pethatcheggwindow.py); the bindings are legacy's."""
		import ui
		import wndMgr
		self.AddFlag("movable")
		self.AddFlag("float")
		name = self._field(FIELD, NAME_MAX, "max")
		name.SAFE_SetReturnEvent = lambda event: name.SetReturnEvent(nui_proxies._weak_method(event))
		price = nui_proxies.TextProxy(self._on_price)
		price.on_show = self._on_price_shown
		self.main = {
			"title": nui_proxies.BoardProxy(176, 184),
			"titleName": nui_proxies.TextProxy(self._on_title),
			"item": nui_slots.SlotWindowProxy(SLOTS, self._on_cells),
			"name": name,
			"price": price,
			"hatch": nui_pet.ButtonProxy(self._on_button),
		}

		self.main["title"].SetCloseEvent(ui.__mem_func__(self.Close))

		self.main["item"].SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.main["item"].SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.main["item"].SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		self.main["name"].SAFE_SetReturnEvent(self._PetHatchEggWindow__OnClickHatch)
		self.main["name"].SetEscapeEvent(ui.__mem_func__(self.Close))

		self.main["hatch"].SAFE_SetEvent(self._PetHatchEggWindow__OnClickHatch)
