"""NovaUI private shop signs (nui/windows/shop-signs/shop-signs.rml).

While the "shop-signs" window flag is on, Interface.AppearPrivateShop makes
ShopSign below through nui_windows.make() instead of
uiPrivateShopBuilder.PrivateShopAdvertisementBoard: the facade of one
legacy sign, with its name, constructor and methods. Every sign is an entry
of one document (P10 spec D18), made with the first sign and destroyed by
close_all() (Interface.Close) or when the last sign goes, since one document
per sign would multiply the per-document update cost in a market.

Each sign registers itself in uiPrivateShopBuilder's dict, as legacy's does,
so the builder module's UpdateADBoard (the game options) reaches it. The
Interface keeps it in its own dict; when the shop disappears
(Interface.DisappearPrivateShop) both drop it, and its entry leaves the
document when it is collected (weakref.finalize). A sign opened again for
the same character replaces the entry.

What legacy did from Python every frame is the engine's: each entry's
nui-anchor places the sign every frame at the owner's position raised 220
units and projected (chr.GetProjectPosition), and the game option that hides
the other players' signs (systemSetting.IsShowSalesText) reaches the
document through the system.show_sales_text feed, so the player's own sign
stays and the others hide, as legacy's OnUpdate does. A release of the left
button on a sign sends net.SendOnClickPacket. The names are shown as written
(nui-text): their color tags are drawn, their links are not."""

import weakref

import net
import player
import uiPrivateShopBuilder

import nui
import nui_hud

DOCUMENT = "nui/windows/shop-signs/shop-signs.rml"

_board = None
_entries = {}                              # vid -> {"vid", "text", "own", "shown", "serial"}, in the order opened
_facades = weakref.WeakValueDictionary()   # vid -> the ShopSign that owns the entry
_next_serial = [1]


class ShopSignBoard(nui.Window):
	"""The signs' one document and model."""

	DOCUMENT = DOCUMENT
	MODEL = "shop_signs"
	FEEDS = {"show_all": "system.show_sales_text"}

	def initial_model(self):
		return {"show_all": True, "signs": []}

	@nui.on("open")
	def on_open(self, vid, button):
		if button != 0:
			return
		facade = _facades.get(vid)
		if facade is not None:
			facade.OnMouseLeftButtonUp()


def _get_board():
	"""The shared document, made with the first sign; None when it cannot
	load or the exe lacks the Wave 2b engine."""
	global _board
	if _board is not None and _board._doc:
		return _board
	if not nui_hud.has_engine_2b():
		return None
	_board = ShopSignBoard()
	if not _board._doc:
		_board = None
		return None
	_board.show()
	return _board


def _sync():
	"""Writes every entry into the model; the document goes with the last."""
	global _board
	if _board is None:
		return
	if not _entries:
		board, _board = _board, None
		board.destroy()
		return
	_board.set(signs=[{"vid": entry["vid"], "text": entry["text"], "own": entry["own"], "shown": entry["shown"],
	                   "legacy_width": legacy_width(entry["text"])}
	                  for entry in _entries.values()])


def legacy_width(text):
	"""The legacy board's width for `text`, in dp: len(text) * 6 + 20
	(uiprivateshopbuilder.py:86), tags counted as legacy counts them, at
	least ThinBoard's 32 (ui.py:2003-2007). The classic skin sizes the sign
	by it (--legacy-width); the modern ones follow the drawn text."""
	return "%ddp" % max(32, len(text) * 6 + 20)


def _forget(vid, serial):
	"""A sign went: its entry leaves, unless a newer sign took the vid."""
	entry = _entries.get(vid)
	if entry is not None and entry["serial"] == serial:
		del _entries[vid]
		_sync()


def close_all():
	"""Every entry removed and the document destroyed (Interface.Close)."""
	global _board
	_entries.clear()
	_facades.clear()
	board, _board = _board, None
	if board is not None:
		board.destroy()


def _show_all():
	value = nui.feed("system.show_sales_text")
	return True if value is None else bool(value)


class ShopSign(object):
	"""uiPrivateShopBuilder.PrivateShopAdvertisementBoard on NovaUI."""

	NUI_FACADE = True

	def __init__(self):
		self._nui_discarded = False
		self._serial = _next_serial[0]
		_next_serial[0] += 1
		self.vid = None
		self.board = _get_board()

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine_2b()

	def nui_discard(self):
		self._nui_discarded = True
		if self.vid is not None:
			_forget(self.vid, self._serial)
		elif not _entries:
			_sync()

	def _entry(self):
		entry = _entries.get(self.vid) if self.vid is not None else None
		return entry if entry is not None and entry["serial"] == self._serial else None

	# --- the Interface's and the builder module's calls -------------------------------------

	def Open(self, vid, text):
		"""As uiprivateshopbuilder.py:81-89: the entry added and shown, and the
		sign registered in the builder module's dict."""
		self.vid = vid
		if self.board is not None and not self._nui_discarded:
			if _board is None:
				self.board = _get_board()
			_entries.pop(vid, None)
			_entries[vid] = {"vid": int(vid), "text": text if isinstance(text, str) else str(text),
			                 "own": vid == player.GetMainCharacterIndex(), "shown": True, "serial": self._serial}
			_facades[vid] = self
			weakref.finalize(self, _forget, vid, self._serial)
			_sync()
		uiPrivateShopBuilder.g_privateShopAdvertisementBoardDict[vid] = self

	def Show(self):
		self._set_shown(True)

	def Hide(self):
		self._set_shown(False)

	def IsShow(self):
		entry = self._entry()
		return bool(entry is not None and entry["shown"] and (_show_all() or entry["own"]))

	def OnMouseLeftButtonUp(self):
		"""As uiprivateshopbuilder.py:91-96."""
		if not self.vid:
			return
		net.SendOnClickPacket(self.vid)
		return True

	def Destroy(self):
		if self.vid is not None:
			_forget(self.vid, self._serial)

	def _set_shown(self, shown):
		entry = self._entry()
		if entry is None or entry["shown"] == shown:
			return
		entry["shown"] = shown
		_sync()
