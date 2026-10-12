"""NovaUI web window (nui/windows/web/web.rml).

While the "web" window flag is on, Interface.__MakeWebWindow makes WebWindow
below through nui_windows.make() instead of uiWeb.WebWindow: the facade of
the legacy window, with its name, constructor and methods. The server's
mall command opens it (Interface.OpenWebWindow, game.py __InGameShop_Show)
with the item mall's address.

The page is the client's WebView2 page (app.ShowWebPage), a native child
window that draws over every layer and takes the pointer inside its
rectangle. The NovaUI window is the frame and title bar around it: Open()
shows the page on the frame's page area (the element web-page) and has the
client keep it there, and its zoom at the UI scale, from C++
(nuigame.WebPageFollow): when the window moves, the scale changes or the
page appears later (the client makes it asynchronously). So there is no
OnUpdate, where legacy moves the page every frame (uiweb.py:72-82).
Close() stops the follow and hides the page.

The document exists only while the window shows (nui_hud.OnDemand). Its body
and close button take no focus (the button acts on a left mousedown);
Escape closes it in its legacy place, the TOP_MOST layer
(nui_hud.EscapeProxy). It needs the Wave 5a engine
(nui_hud.has_engine_5a)."""

import sys

import app
import wndMgr

import nui
import nui_hud

DOCUMENT = "nui/windows/web/web.rml"
PAGE = "web-page"

# Legacy's frame (uiscript webwindow.py): 740 x 550 of page, 10 to the left,
# right and bottom of it and 30 above it.
WEB_WIDTH = 740
WEB_HEIGHT = 550


def _nuigame():
	return sys.modules.get("nuigame")


class WebBoard(nui.Window):
	"""The window's document; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "web"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {}

	@nui.on("act")
	def on_act(self, what, button):
		if button == 0 and what == "close":
			self._owner.Close()


class WebWindow(nui_hud.LayoutCalls):
	"""uiWeb.WebWindow on NovaUI (Interface.wndWeb)."""

	NUI_FACADE = True
	KEY = "web"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.oldPos = None
		self.following = False
		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		if not nui_hud.has_engine_5a():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.Close, layer="TOP_MOST")
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_5a()

	def nui_discard(self):
		self._nui_discarded = True
		self._follow(False)
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	def _make_board(self):
		return WebBoard(self)

	def _board(self):
		return self.demand.board() if self.demand is not None else None

	def _follow(self, on):
		"""nuigame.WebPageFollow on the page area, or off."""
		nuigame = _nuigame()
		follow = getattr(nuigame, "WebPageFollow", None)
		if on:
			if follow is not None:
				follow(DOCUMENT, PAGE)
				self.following = True
		elif self.following:
			self.following = False
			if follow is not None:
				follow("", "")

	def page_rect(self):
		"""(left, top, right, bottom) in screen pixels of the page area: its
		box when the board has laid one out, else legacy's page rectangle of a
		centered frame at the scale in use (the follow corrects it once the
		board is laid out)."""
		board = self._board()
		box = board.element_box(PAGE) if board is not None else None
		if box and box[2] > 0 and box[3] > 0:
			x, y, width, height = box
			return (int(round(x)), int(round(y)), int(round(x + width)), int(round(y + height)))
		s = nui.get_scale() or 1.0
		screen_width, screen_height = wndMgr.GetScreenWidth(), wndMgr.GetScreenHeight()
		width = min((WEB_WIDTH + 20) * s, screen_width)
		height = min((WEB_HEIGHT + 40) * s, screen_height)
		x = (screen_width - width) / 2.0
		y = (screen_height - height) / 2.0
		return (int(x + 10 * s), int(y + 30 * s), int(x + width - 10 * s), int(y + height - 10 * s))

	# --- the Interface's calls (uiweb.py:9-82) -------------------------------------------

	def LoadWindow(self):
		"""The document loaded with the facade."""
		return None

	def Destroy(self):
		app.HideWebPage()
		self.nui_discard()

	def Open(self, url):
		self.Refresh()
		self.Show()
		board = self._board()
		if board is not None:
			board.center()
			board.bring_to_front()
		app.ShowWebPage(url, self.page_rect())
		self._follow(True)

	def Close(self):
		self._follow(False)
		app.HideWebPage()
		self.Hide()

	def Clear(self):
		self.Refresh()

	def Refresh(self):
		pass

	def Show(self):
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()

	def Hide(self):
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return self.demand is not None and self.demand.is_shown()

	def SetTop(self):
		board = self._board()
		if board is not None:
			board.bring_to_front()
		if self.escapeProxy is not None and self.escapeProxy.is_shown():
			self.escapeProxy.show()

	def OnPressEscapeKey(self):
		self.Close()
		return True
