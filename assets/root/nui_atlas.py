"""NovaUI atlas, the large map (nui/windows/atlas/atlas.rml).

While the "atlas" window flag is on, the NovaUI minimap (nui_minimap.MiniMap)
makes AtlasWindow below through nui_windows.make() instead of
uiMiniMap.AtlasWindow; the Interface reaches it only through the minimap
(ShowAtlas, ToggleAtlasWindow), and C++ through the handler the facade
registers (miniMap.RegisterAtlasWindow): CPythonMiniMap::OpenAtlasWindow
calls its Show and SetAtlasCenterPosition its SetCenterPositionAdjust. With
the legacy minimap the flag is refused (nui_windows.refuse, the Interface's
wiring), since the legacy minimap makes the legacy atlas.

CPythonMiniMap renders the atlas (P10 spec D3): the facade makes legacy's
state calls (ShowAtlas, HideAtlas), and the client renders the legacy atlas,
its marks and guild areas into the document's nui-view ("atlas") at the
atlas image's size each frame the view shows, where legacy called
miniMap.UpdateAtlas and RenderAtlas from Python every frame. The view's own
label shows what lies under the pointer (legacy polled miniMap.GetAtlasInfo
every frame), with the guild's mark over a guild area, in the format the
facade sets once. Escape closes the atlas in its legacy place in the Escape
chain (nui_hud.EscapeProxy).

The document exists only while the atlas shows (nui_hud.OnDemand, P11 spec
D5): RmlUi updates every loaded document each frame, shown or not. The
constructor loads it once to answer nui_ready(); the title and the place C++
asked for (SetCenterPositionAdjust, also before the first show) live on the
facade and go into each new board.

Where it differs from legacy: the window shows only when the atlas has a
size (miniMap.GetAtlasSize), where legacy showed its frame without an image
too; the title is empty, and the markup shows the default title, for a map
localeInfo.MINIMAP_ZONE_NAME_DICT lacks, where legacy raised."""

import weakref

import localeInfo
import miniMap
import wndMgr

try:
	import nuigame
except ImportError:  # an exe without the Wave 2b engine: nui_ready() is False
	nuigame = None

import nui
import nui_hud

DOCUMENT = "nui/windows/atlas/atlas.rml"
VIEW = "atlas"
HOVER_FORMAT = "{name}({x}, {y})"   # uiminimap.py:144


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


class AtlasBoard(nui.Window):
	"""The atlas's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "atlas"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"shown": False, "title": ""}

	@nui.on("close")
	def on_close(self, button):
		if button == 0:
			self._owner.Hide()


class AtlasWindow(object):
	"""uiMiniMap.AtlasWindow on NovaUI (MiniMap.AtlasWindow)."""

	NUI_FACADE = True
	KEY = "atlas"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.demand = None
		self.loaded = False
		self.escapeProxy = None
		self.registered = False
		self.shown = False
		self.mapName = ""
		self.title = ""
		self.centerAdjust = None    # the offset C++ asked for, in screen pixels
		if not nui_hud.has_engine_2b():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.Hide)
			nuigame.SetViewHoverFormat(VIEW, HOVER_FORMAT,
			                           {"empty_guild_area": nui.plain_text(localeInfo.GUILD_EMPTY_AREA)})
		except Exception:
			self.nui_discard()
			raise

	@property
	def board(self):
		"""The atlas's board while it shows, else None."""
		return self.demand.board() if self.demand is not None else None

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_2b()

	def nui_discard(self):
		self._nui_discarded = True
		if self.registered:
			self.registered = False
			miniMap.UnregisterAtlasWindow()
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	def _make_board(self):
		return AtlasBoard(self)

	def _restore_board(self, board):
		board.set(shown=True, title=self.title)
		self._place(board)

	def _place(self, board):
		if self.centerAdjust is None:
			return
		x, y = self.centerAdjust
		s = nui.get_scale() or 1.0
		board.set_position((wndMgr.GetScreenWidth() / 2.0 + x) / s, (wndMgr.GetScreenHeight() / 2.0 + y) / s,
		                   origin=(0.5, 0.5))

	def Destroy(self):
		"""As uiminimap.py:109-116: C++ lets go of the handler, then the
		document goes."""
		miniMap.UnregisterAtlasWindow()
		self.registered = False
		self.nui_discard()

	# --- the minimap's and C++'s calls --------------------------------------------------

	def LoadWindow(self):
		"""As uiminimap.py:83-107 without the layout: hidden, and registered as
		C++'s atlas handler (CPythonMiniMap keeps a borrowed reference until
		Destroy, so the minimap facade keeps the atlas alive)."""
		self.Hide()
		miniMap.RegisterAtlasWindow(self)
		self.registered = True

	def Show(self):
		"""As uiminimap.py:164-177: with an atlas size, the atlas shows."""
		ok, width, height = miniMap.GetAtlasSize()
		if not ok:
			return
		miniMap.ShowAtlas()
		self.shown = True
		if self.demand is not None:
			self.demand.show()
		if self.escapeProxy is not None:
			self.escapeProxy.show()

	def Hide(self):
		"""As uiminimap.py:158-162."""
		miniMap.HideAtlas()
		self.shown = False
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return self.shown and self.board is not None and self.board.is_visible()

	def SetMapName(self, mapName):
		self.mapName = mapName
		names = getattr(localeInfo, "MINIMAP_ZONE_NAME_DICT", {}) or {}
		title = names.get(mapName)
		self.title = nui.plain_text(title) if title is not None else ""
		if self.board is not None:
			self.board.set(title=self.title)

	def SetCenterPositionAdjust(self, x, y):
		"""As uiminimap.py:179-180: the window centered on the screen, moved
		by (x, y) pixels; kept for the next board while the atlas is hidden."""
		self.centerAdjust = (x, y)
		board = self.board
		if board is not None:
			self._place(board)

	def OnPressEscapeKey(self):
		self.Hide()
		return True
