"""NovaUI pet bonus refine window (nui/windows/pet-attr-refine/
pet-attr-refine.rml; NOVA-24).

While the "pet-attr-refine" window is on, the Interface makes
PetAttrRefineWindow below through nui_windows.make() instead of
uiPet.PetAttrRefineWindow: a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the uiscript's widgets
were (petrefineattrwindow.py): the bonus, its current and next level and
value, the materials, the cost, Upgrade and Cancel. Open
(BINARY_PetAttrRefineInfo, also after each upgrade), Refresh (which closes
the window at the top level), the money and material checks with their
popups and pet.RefineAttr are legacy's code. The materials are
nui_pet_evolution's MaterialProxys, as there."""

import pet
import ui
import uiPet
import uiToolTip

import nui
import nui_facade
import nui_hud
import nui_pet
import nui_pet_evolution
import nui_proxies

DOCUMENT = "nui/windows/pet-attr-refine/pet-attr-refine.rml"
KEY = "pet-attr-refine"


class _PetAttrRefineBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The refine window's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "pet_attr_refine"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("upgrade_press")
	def on_upgrade_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["upgrade"].click()

	@nui.on("cancel_press")
	def on_cancel_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["cancel"].click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["title"].close()

	@nui.on("material_over")
	def on_material_over(self, index):
		nui_pet_evolution.material_event(self._owner, index, "OnMouseOverIn")

	@nui.on("material_out")
	def on_material_out(self, index):
		nui_pet_evolution.material_event(self._owner, index, "OnMouseOverOut")


class PetAttrRefineWindow(nui_facade.Facade, uiPet.PetAttrRefineWindow):
	"""uiPet.PetAttrRefineWindow on NovaUI (Interface.wndPetRefineWindow)."""

	KEY = KEY
	BOARD = _PetAttrRefineBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiPet.PetAttrRefineWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"attribute": "",
			"current_level": "",
			"current_value": "",
			"next_level": "",
			"next_value": "",
			"materials": [],
			"cost": "",
		}

	def _on_text(self, key):
		return lambda text: self.nui_set(**{key: nui.plain_text(text)})

	# --- the loader (uipet.py PetAttrRefineWindow.__LoadWindow, on proxies) --------------------

	def _PetAttrRefineWindow__LoadWindow(self):
		"""Legacy's __LoadWindow with proxies where the uiscript's widgets
		were (petrefineattrwindow.py); the bindings are legacy's."""
		self.AddFlag("movable")
		self.AddFlag("float")
		self.main = {
			"title": nui_proxies.BoardProxy(260, 330),
			"attribute": nui_proxies.TextProxy(self._on_text("attribute")),
			"current": {
				"value": nui_proxies.TextProxy(self._on_text("current_value")),
				"level": nui_proxies.TextProxy(self._on_text("current_level")),
			},
			"next": {
				"value": nui_proxies.TextProxy(self._on_text("next_value")),
				"level": nui_proxies.TextProxy(self._on_text("next_level")),
			},
			"material": nui_proxies.BoardProxy(nui_pet_evolution.MATERIAL_WIDTH, 72),
			"cost": nui_proxies.TextProxy(self._on_text("cost")),
			"upgrade": nui_pet.ButtonProxy(),
			"cancel": nui_pet.ButtonProxy(),
		}

		self._itemToolTip = nui_pet.make_tooltip(uiToolTip.ItemToolTip, "nui_item_tooltip.ItemToolTip")
		self._itemToolTip.HideToolTip()

		self.main["title"].SetCloseEvent(ui.__mem_func__(self.Close))

		self.main["upgrade"].SAFE_SetEvent(self._PetAttrRefineWindow__OnClickUpgrade)
		self.main["cancel"].SAFE_SetEvent(self.Close)

	def _PetAttrRefineWindow__MakeMaterial(self, index):
		return nui_pet_evolution.make_material(self, pet.GetAttrRefineMaterial, index)

	def RefreshRequirements(self):
		"""Legacy's, then the materials to the board."""
		uiPet.PetAttrRefineWindow.RefreshRequirements(self)
		self.nui_set(materials=[mat.model() for mat in (self._materials or [])])
