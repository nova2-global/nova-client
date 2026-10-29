"""NovaUI minimap (nui/windows/minimap/minimap.rml).

While the "minimap" window flag is on, Interface.__MakeWindows makes MiniMap
below through nui_windows.make() instead of uiMiniMap.MiniMap: the facade
of the legacy window, with its name, constructor and the methods the
Interface and game.py call. CPythonMiniMap stays the map's renderer and data
owner (P10 spec D3): the facade makes legacy's state calls (Create, the
scale, Show and Hide, the zoom), and the client renders the legacy minimap
into the document's nui-view ("minimap") each frame the view shows, with
the main character's position, where legacy called miniMap.Update and
Render from Python every frame. The view's own label shows what lies under
the pointer (legacy polled miniMap.GetInfo every frame), in the format the
facade sets once (nuigame.SetViewHoverFormat). So no Python runs per frame.

The minimap makes the atlas, as legacy does: the NovaUI atlas
(nui_atlas.AtlasWindow) while the "atlas" flag is on, else the legacy one;
either way it keeps the legacy attribute name, AtlasWindow.

Where it differs from legacy: the position line is not made (legacy hides
it, constInfo.MINIMAP_POSITIONINFO_ENABLE); SetImprisonmentDuration, which
nothing calls, sets the text once and counts nothing down; the hints open on
hover."""

import weakref

import localeInfo
import miniMap
import net
import uiMiniMap
import uiScriptLocale

try:
	import nuigame
except ImportError:  # an exe without the Wave 2b engine: nui_ready() is False
	nuigame = None

import nui
import nui_hud
import nui_windows

DOCUMENT = "nui/windows/minimap/minimap.rml"
VIEW = "minimap"
HOVER_FORMAT = "{name} ({x}, {y})"   # uiminimap.py:406


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


class MiniMapBoard(nui.Window):
	"""The minimap's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "minimap"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"shown": False, "open": False, "can_see": True, "has_atlas": False, "server_info": "",
		        "observers": 0, "observer_text": ""}

	@nui.on("scale_up")
	def on_scale_up(self, button):
		if button == 0:
			self._owner.ScaleUp()

	@nui.on("scale_down")
	def on_scale_down(self, button):
		if button == 0:
			self._owner.ScaleDown()

	@nui.on("hide_map")
	def on_hide_map(self, button):
		if button == 0:
			self._owner.HideMiniMap()

	@nui.on("show_map")
	def on_show_map(self, button):
		if button == 0:
			self._owner.ShowMiniMap()

	@nui.on("atlas")
	def on_atlas(self, button):
		if button == 0:
			self._owner.nui_atlas_button()


class MiniMap(object):
	"""uiMiniMap.MiniMap on NovaUI (Interface.wndMiniMap)."""

	NUI_FACADE = True
	KEY = "minimap"

	CANNOT_SEE_INFO_MAP_DICT = uiMiniMap.MiniMap.CANNOT_SEE_INFO_MAP_DICT

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self._created = False
		self.board = None
		self.AtlasWindow = None
		self.mapName = ""
		self.isLoaded = 0
		self.canSeeInfo = True
		self.atlasButton = False     # legacy binds the atlas button at its first load, when the map has an atlas
		self.imprisonmentDuration = 0
		self.state = {"shown": False, "open": False, "can_see": True, "has_atlas": False, "server_info": "",
		              "observers": 0, "observer_text": ""}
		# The engine first: an older exe keeps the legacy minimap, and this
		# facade then makes no call and no atlas.
		if not nui_hud.has_engine_2b():
			return
		try:
			# Legacy's calls (uiminimap.py:198-245).
			miniMap.Create()
			miniMap.SetScale(2.0)
			self._created = True
			self.AtlasWindow = nui_windows.make("atlas", uiMiniMap.AtlasWindow, "nui_atlas.AtlasWindow")
			self.AtlasWindow.LoadWindow()
			self.AtlasWindow.Hide()
			self.state["has_atlas"] = bool(miniMap.IsAtlas())
			self.board = MiniMapBoard(self)
			if self.board._doc:
				self.board.set(**self.state)
			self._hover_format()
		except Exception:
			self.nui_discard()
			raise

	def __del__(self):
		# As legacy (uiminimap.py:247-249); a discarded facade leaves the map
		# to the legacy minimap made in its place.
		if getattr(self, "_created", False) and not getattr(self, "_nui_discarded", True):
			miniMap.Destroy()

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine_2b()

	def nui_discard(self):
		self._nui_discarded = True
		atlas, self.AtlasWindow = self.AtlasWindow, None
		if atlas is not None:
			atlas.Destroy()
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget(self.KEY, self)

	def Destroy(self):
		"""As uiminimap.py:366-374: the map hides, the atlas goes, then the
		document."""
		self.HideMiniMap()
		atlas, self.AtlasWindow = self.AtlasWindow, None
		if atlas is not None:
			atlas.Destroy()
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget(self.KEY, self)

	# --- the Interface's calls -------------------------------------------------------

	def Show(self):
		self.__LoadWindow()
		self._set(shown=True)
		if self.board is not None:
			self.board.show()

	def Hide(self):
		self._set(shown=False)
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.state["shown"] and self.board is not None and self.board.is_visible()

	def __LoadWindow(self):
		"""The part of legacy's first Show that is not layout
		(uiminimap.py:305-364): the server line, the atlas button's event, and
		the map shown."""
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		self._set(server_info=nui.plain_text(net.GetServerInfo()))
		self.atlasButton = bool(miniMap.IsAtlas())
		self.ShowMiniMap()

	def ShowMiniMap(self):
		if not self.canSeeInfo:
			return
		miniMap.Show()
		self._set(open=True)

	def HideMiniMap(self):
		miniMap.Hide()
		self._set(open=False)

	def isShowMiniMap(self):
		return miniMap.isShow()

	def Close(self):
		self.HideMiniMap()

	def SetTop(self):
		if self.board is not None:
			self.board.bring_to_front()

	def ScaleUp(self):
		miniMap.ScaleUp()

	def ScaleDown(self):
		miniMap.ScaleDown()

	def SetMapName(self, mapName):
		"""As uiminimap.py:271-282; the hover label says the place is unknown
		where the map cannot be seen (:397-398)."""
		self.mapName = mapName
		if self.AtlasWindow is not None:
			self.AtlasWindow.SetMapName(mapName)
		if mapName in self.CANNOT_SEE_INFO_MAP_DICT:
			self.canSeeInfo = False
			self.HideMiniMap()
			self._set(can_see=False)
		else:
			self.canSeeInfo = True
			self.ShowMiniMap()
			self._set(can_see=True)
		self._hover_format()

	def RefreshServerInfo(self):
		"""The server line again from net.GetServerInfo() (uiminimap.py
		RefreshServerInfo): game.py calls it when a channel change renamed
		the channel there (NOVA-49). Before the first Show the line is not
		loaded yet, and that Show reads the text itself."""
		if self.isLoaded == 1:
			self._set(server_info=nui.plain_text(net.GetServerInfo()))

	def ShowAtlas(self):
		if not miniMap.IsAtlas():
			return
		if self.AtlasWindow is not None and not self.AtlasWindow.IsShow():
			self.AtlasWindow.Show()

	def ToggleAtlasWindow(self):
		if not miniMap.IsAtlas():
			return
		if self.AtlasWindow is None:
			return
		if self.AtlasWindow.IsShow():
			self.AtlasWindow.Hide()
		else:
			self.AtlasWindow.Show()

	def UpdateObserverCount(self, observerCount):
		"""As uiminimap.py:376-382: the line shows while the count is above 0."""
		self._set(observers=int(observerCount), observer_text=nui.plain_text(localeInfo.MINIMAP_OBSERVER_COUNT % observerCount))

	def SetImprisonmentDuration(self, duration):
		"""The text legacy's first call shows (uiminimap.py:285-297); nothing
		calls it, and nothing counts it down."""
		self.imprisonmentDuration = duration
		rest = max(int(duration), 0)
		label = getattr(uiScriptLocale, "AUTOBAN_QUIZ_REST_TIME", "")
		self._set(server_info=nui.plain_text("%s: %s" % (label, localeInfo.SecondToDHM(rest))))

	# --- the document's events -------------------------------------------------------

	def nui_atlas_button(self):
		"""The atlas button: legacy binds its event only when the map had an
		atlas at the window's first load; else it does nothing."""
		if self.atlasButton:
			self.ShowAtlas()

	def _hover_format(self):
		if nuigame is None:
			return
		if self.canSeeInfo:
			nuigame.SetViewHoverFormat(VIEW, HOVER_FORMAT)
		else:
			nuigame.SetViewHoverFormat(VIEW, "{name} (" + nui.plain_text(localeInfo.UI_POS_UNKNOWN) + ")")

	def _set(self, **values):
		self.state.update(values)
		if self.board is not None:
			self.board.set(**values)
