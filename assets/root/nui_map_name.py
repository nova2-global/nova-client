"""NovaUI map name splash (nui/windows/map-name/map-name.rml).

While the "map-name" window flag is on, GameWindow.__init__ makes
MapNameShower below through nui_windows.make() instead of
uiMapNameShower.MapNameShower: the facade of the legacy splash, which the
C++ callback ShowMapName (game.py) calls on a warp and at login.

The art, its table and its locale path are the legacy module's
(_MAP_NAME_SUFFIXES, LOCALE_PATH), and so are the Demon Tower and Devil's
Catacomb floors. Legacy faded the splash from its per-frame Update(), which
game.py called every frame; game.py skips that call for this facade
(NUI_FACADE), and the fade is a keyframe animation instead (a second's
wait, the fade in, five seconds of hold, the fade out), with a format="none"
nui-countdown that hides the window when it is over. Each ShowMapName
starts it again: the body alternates between two animation classes, which
restarts the animation."""

import weakref

import app

import nui
import nui_hud
import nui_slots
import uiMapNameShower

DOCUMENT = "nui/windows/map-name/map-name.rml"
SHOW_TIME = 6.6   # the legacy one second wait, the fade in, the five second hold and the fade out


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def _exists(path):
	"""Whether the store has the image; legacy LoadImage raised for a missing
	one. Without app.IsExistFile every image counts as there."""
	is_exist = getattr(app, "IsExistFile", None)
	return True if is_exist is None else bool(is_exist(path))


class MapNameBoard(nui.Window):
	"""The splash's document and model."""

	DOCUMENT = DOCUMENT
	MODEL = "map_name"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"image": "", "floor_image": "", "offset": "none", "hide_at": 0.0, "run": ""}

	@nui.on("done")
	def on_done(self):
		self._owner.nui_done()


class MapNameShower(object):
	"""uiMapNameShower.MapNameShower on NovaUI (GameWindow.mapNameShower)."""

	NUI_FACADE = True

	STATE_HIDE = 0
	STATE_FADE_IN = 1
	STATE_SHOW = 2
	STATE_FADE_OUT = 3

	def __init__(self):
		nui_hud.take_over("map-name", self)
		self._nui_discarded = False
		self.board = None
		self.state = self.STATE_HIDE
		self.run = ""
		if not nui_hud.has_engine():
			return
		try:
			self.board = MapNameBoard(self)
		except Exception:
			self.nui_discard()
			raise

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("map-name", self)

	def Destroy(self):
		self.nui_discard()

	def Show(self):
		if self.board is not None:
			self.board.show()

	def Hide(self):
		self.state = self.STATE_HIDE
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	def Update(self):
		"""Legacy's per-frame fade; the animation and the timer do it here
		(game.py does not call it for a facade)."""
		pass

	def __GetDevilTowerFloor(self, x, y):
		return uiMapNameShower.MapNameShower._MapNameShower__GetDevilTowerFloor(self, x, y)

	def __GetDevilBase(self, x, y):
		return uiMapNameShower.MapNameShower._MapNameShower__GetDevilBase(self, x, y)

	def ShowMapName(self, mapName, x, y):
		suffixes = uiMapNameShower._MAP_NAME_SUFFIXES
		if mapName not in suffixes:
			print((" [ERROR] - There is no map name image", mapName))
			return
		path = uiMapNameShower.LOCALE_PATH
		image = path + suffixes[mapName]
		if not _exists(image):
			return

		offset = "none"
		floor_image = ""
		if mapName in ("metin2_map_deviltower1", "metin2_map_devilsCatacomb"):
			if mapName == "metin2_map_deviltower1":
				floor = self.__GetDevilTowerFloor(x, y)
			else:
				floor = self.__GetDevilBase(x, y)
			floor_path = path + "devil1_%df.tga" % floor
			if _exists(floor_path):
				offset = "tower" if mapName == "metin2_map_deviltower1" else "catacomb"
				floor_image = nui_slots.icon_source(floor_path)

		self.state = self.STATE_FADE_IN
		self.run = "b" if self.run == "a" else "a"
		if self.board is not None:
			self.board.set(image=nui_slots.icon_source(image), floor_image=floor_image, offset=offset,
			               hide_at=nui.now() + SHOW_TIME, run=self.run)
		self.Show()

	def nui_done(self):
		"""The splash faded out."""
		self.Hide()
		if self.board is not None:
			self.board.set(hide_at=0.0)
