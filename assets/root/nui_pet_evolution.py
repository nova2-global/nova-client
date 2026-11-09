"""NovaUI pet evolution window (nui/windows/pet-evolution/pet-evolution.rml;
NOVA-24).

While the "pet-evolution" window is on, the Interface makes
PetEvolutionWindow below through nui_windows.make() instead of
uiPet.PetEvolutionWindow: a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the uiscript's widgets
were (petevolutionwindow.py): the seal's icon, the pet's name, the current
and next grade with their skill counts, the materials, the cost, Evolve and
Cancel. Open (BINARY_PetEvolutionInfo), Refresh, the money and material
checks with their popups, pet.Evolve and the result texts
(BINARY_PetEvolveResult) are legacy's code.

The materials: legacy makes an image box and a number line per material in
its material window (__MakeMaterial, which parents real legacy widgets);
here __MakeMaterial makes a MaterialProxy (the vnum, the count, the icon and
the hover's item tooltip, as legacy's image box binds it), and the board
shows the list. The item tooltip is the Interface's kind (the factory's
"tooltips")."""

import item
import pet
import ui
import uiPet
import uiToolTip

import nui
import nui_facade
import nui_hud
import nui_pet
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/pet-evolution/pet-evolution.rml"
KEY = "pet-evolution"
# The uiscript's material window (material_window, 230 x 72).
MATERIAL_WIDTH = 230


class MaterialProxy(nui_pet.ImageProxy):
	"""One of legacy's material image boxes (__MakeMaterial): its item and
	count, and the hover handlers legacy set (the item tooltip)."""

	def __init__(self, vnum, count):
		item.SelectItem(vnum)
		nui_pet.ImageProxy.__init__(self)
		self.vnum = int(vnum)
		self.count_value = int(count)
		self.LoadImage(item.GetIconImageFileName())

	def model(self):
		return {"icon": nui_slots.icon_source(self.image), "count": str(self.count_value)}


def make_material(owner, getter, index):
	"""Legacy's __MakeMaterial (uipet.py) on a proxy: the material at
	`index` (pet.GetEvolveMaterial or GetAttrRefineMaterial), its tooltip on
	hover."""
	mat_vnum, mat_count = getter(index)
	mat_item = MaterialProxy(mat_vnum, mat_count)
	uiPet.SetStringEvent(mat_item, "MOUSE_OVER_IN", lambda arg=mat_vnum: owner._itemToolTip.SetItemToolTip(arg))
	uiPet.SetStringEvent(mat_item, "MOUSE_OVER_OUT", lambda: owner._itemToolTip.HideToolTip())
	mat_item.Show()
	return mat_item


def material_event(owner, index, handler):
	"""A hover of the board's material `index`: the handler legacy set on
	its image box (the item tooltip)."""
	materials = owner._materials or []
	if 0 <= int(index) < len(materials):
		materials[int(index)].fire(handler)


class _PetEvolutionBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The evolution window's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "pet_evolution"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("evolve_press")
	def on_evolve_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.main["evolve"].click()

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
		material_event(self._owner, index, "OnMouseOverIn")

	@nui.on("material_out")
	def on_material_out(self, index):
		material_event(self._owner, index, "OnMouseOverOut")

	@nui.on("item_over")
	def on_item_over(self):
		self._owner.main["item"].fire("OnMouseOverIn")

	@nui.on("item_out")
	def on_item_out(self):
		self._owner.main["item"].fire("OnMouseOverOut")


def grade_model():
	return {"title": "", "color": nui_pet.GRADE_COLOR, "active": "", "passive": ""}


class PetEvolutionWindow(nui_facade.Facade, uiPet.PetEvolutionWindow):
	"""uiPet.PetEvolutionWindow on NovaUI (Interface.wndPetEvolutionWindow)."""

	KEY = KEY
	BOARD = _PetEvolutionBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiPet.PetEvolutionWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"icon": "",
			"name": "",
			"current": grade_model(),
			"next": grade_model(),
			"materials": [],
			"cost": "",
		}

	# --- the proxies' callbacks ---------------------------------------------------------------

	def _on_grade(self, key):
		def changed(text):
			main = getattr(self, "main", None)
			if not main:
				return
			part = main[key]
			self.nui_set(**{key: {"title": nui.plain_text(part["title"].text),
			                      "color": nui_pet.color_of(part["title"].color) or nui_pet.GRADE_COLOR,
			                      "active": nui.plain_text(part["active_skill"].text),
			                      "passive": nui.plain_text(part["passive_skill"].text)}})
		return changed

	def _on_icon(self, path):
		self.nui_set(icon=nui_slots.icon_source(path))

	def _on_name(self, text):
		self.nui_set(name=nui.plain_text(text))

	def _on_cost(self, text):
		self.nui_set(cost=nui.plain_text(text))

	# --- the loader (uipet.py PetEvolutionWindow.__LoadWindow, on proxies) ---------------------

	def _PetEvolutionWindow__LoadWindow(self):
		"""Legacy's __LoadWindow with proxies where the uiscript's widgets
		were (petevolutionwindow.py); the bindings are legacy's."""
		self.AddFlag("movable")
		self.AddFlag("float")
		on_current, on_next = self._on_grade("current"), self._on_grade("next")
		material = nui_proxies.BoardProxy(MATERIAL_WIDTH, 72)
		self.main = {
			"title": nui_proxies.BoardProxy(260, 330),
			"item": nui_pet.ImageProxy(self._on_icon),
			"pet_name": nui_proxies.TextProxy(self._on_name),
			"current": {
				"title": nui_pet.ColorTextProxy(on_current),
				"active_skill": nui_proxies.TextProxy(on_current),
				"passive_skill": nui_proxies.TextProxy(on_current),
			},
			"next": {
				"title": nui_pet.ColorTextProxy(on_next),
				"active_skill": nui_proxies.TextProxy(on_next),
				"passive_skill": nui_proxies.TextProxy(on_next),
			},
			"material": material,
			"cost": nui_proxies.TextProxy(self._on_cost),
			"evolve": nui_pet.ButtonProxy(),
			"cancel": nui_pet.ButtonProxy(),
		}

		self._itemToolTip = nui_pet.make_tooltip(uiToolTip.ItemToolTip, "nui_item_tooltip.ItemToolTip")
		self._itemToolTip.HideToolTip()

		self.main["title"].SetCloseEvent(ui.__mem_func__(self.Close))

		self.main["evolve"].SAFE_SetEvent(self._PetEvolutionWindow__OnClickEvolve)
		self.main["cancel"].SAFE_SetEvent(self.Close)

		uiPet.SetStringEvent(self.main["item"], "MOUSE_OVER_IN", lambda: self._itemToolTip.SetItemToolTip(pet.GetItemVnum()))
		uiPet.SetStringEvent(self.main["item"], "MOUSE_OVER_OUT", lambda: self._itemToolTip.HideToolTip())

	def _PetEvolutionWindow__MakeMaterial(self, index):
		return make_material(self, pet.GetEvolveMaterial, index)

	def RefreshRequirements(self):
		"""Legacy's, then the materials to the board."""
		uiPet.PetEvolutionWindow.RefreshRequirements(self)
		self.nui_set(materials=[mat.model() for mat in (self._materials or [])])
