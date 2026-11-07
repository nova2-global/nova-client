"""NovaUI private and offline shop signs (nui/windows/shop-signs/shop-signs.rml).

While the "shop-signs" window flag is on, Interface.AppearPrivateShop makes
ShopSign below through nui_windows.make() instead of
uiPrivateShopBuilder.PrivateShopAdvertisementBoard (a plain sign, style 0)
or PrivateShopTitleBar(style) (a decorated offline shop's sign, styles 1 to
5): the facade of one legacy sign, with its constructor's arguments and its
methods. Every sign is an entry of one document (P10 spec D18), made with the
first sign and destroyed by close_all() (Interface.Close) or when the last
sign goes, since one document per sign would multiply the per-document
update cost in a market.

Each sign registers itself in uiPrivateShopBuilder's dict, as legacy's does,
so the builder module's UpdateADBoard (the game options) reaches it, and the
shop window reads its title and marks it seen (MarkSeen) when the player
opens its shop. The Interface keeps it in its own dict; when the shop
disappears (Interface.DisappearPrivateShop) both drop it, and its entry
leaves the document when it is collected (weakref.finalize). A sign opened
again for the same character replaces the entry; the Interface gives a
shown sign its new title with UpdateTitle.

Which signs show is Wave 5's rule (uiprivateshopbuilder.IsBoardShown, o-cli
bugs 12 and 23), the same for every style: the player's own (the stall and
the offline shop), the target and the hovered character's always; with the
sales texts on (the system.show_sales_text feed, the game option), also the
SIGN_DISPLAY_COUNT nearest within SIGN_RANGE (offlineshopconst). Legacy
works the rule out at most once a second and at once when a sign comes or
goes; here a nui-countdown timer runs it once a second while signs exist (no
Python per frame), so the target and the hovered sign show within a second.
A host without offlineshopconst keeps the rule before Wave 5: the own sign,
and the others with the sales texts on. A visited shop's plain sign turns
purple for SIGN_SEEN_MINUTES (MarkSeen, MarkUnseen).

What legacy did from Python every frame is the engine's: each entry's
nui-anchor places the sign every frame at the owner's position raised 220
units and projected (chr.GetProjectPosition). A release of the left button
on a sign sends net.SendOnClickPacket. The names are shown as written
(nui-text): their color tags are drawn, their links are not."""

import weakref

import app
import chr
import net
import player
import uiPrivateShopBuilder

import nui
import nui_hud

DOCUMENT = "nui/windows/shop-signs/shop-signs.rml"
# The styles the sheets draw (shop-sign--style-1 to 5); another is drawn as 0.
STYLE_CLASSES = 5
# Legacy's refresh when offlineshopconst is not there (its SIGN_REFRESH_SEC).
REFRESH_SEC = 1.0

_board = None
_entries = {}                              # vid -> entry, in the order opened
_facades = weakref.WeakValueDictionary()   # vid -> the ShopSign that owns the entry
_next_serial = [1]


def _const():
	"""offlineshopconst, or None on a host without it (uiprivateshopbuilder's
	own rule: the module is optional)."""
	return getattr(uiPrivateShopBuilder, "offlineshopconst", None)


def _style(style):
	"""The style a sign draws: offlineshopconst.clamp_style's (a style the
	client has no art for is 0), and 0 past the styles the sheets draw."""
	const = _const()
	try:
		style = int(const.clamp_style(style) if const is not None else style)
	except (TypeError, ValueError):
		return 0
	return style if 1 <= style <= STYLE_CLASSES else 0


class ShopSignBoard(nui.Window):
	"""The signs' one document and model."""

	DOCUMENT = DOCUMENT
	MODEL = "shop_signs"
	FEEDS = {"show_all": "system.show_sales_text"}

	def initial_model(self):
		return {"show_all": True, "signs": [], "tick_end": 0.0}

	@nui.on("open")
	def on_open(self, vid, button):
		if button != 0:
			return
		facade = _facades.get(vid)
		if facade is not None:
			facade.OnMouseLeftButtonUp()

	@nui.on("tick")
	def on_tick(self):
		refresh()


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
	                   "style": entry["style"], "seen": entry["seen"], "always": entry["always"],
	                   "near": entry["near"], "legacy_width": legacy_width(entry["text"], entry["style"])}
	                  for entry in _entries.values()])


def legacy_width(text, style=0):
	"""The legacy sign's width for `text`, in dp, tags counted as legacy
	counts them: a plain board len(text) * 6 + 20 (uiprivateshopbuilder.py's
	Open), at least ThinBoard's 32 (ui.py:2003-2007); a decorated one
	len(text) * 6 + 40, at least 32 (PrivateShopTitleBar.__Resize). The
	classic skin sizes the sign by it (--legacy-width); the modern ones
	follow the drawn text."""
	pad = 40 if style else 20
	return "%ddp" % max(32, len(text) * 6 + pad)


def _always_vids():
	"""The player's own sign (the stall's character and the offline shop's),
	the target's and the hovered character's: these show whatever the rule
	(uiprivateshopbuilder.IsBoardShown)."""
	vids = [player.GetMainCharacterIndex()]
	for getter in (getattr(player, "GetOwnOfflineShopVID", None), getattr(player, "GetTargetVID", None),
	               getattr(chr, "Pick", None)):
		if callable(getter):
			vids.append(getter())
	return [vid for vid in vids if vid]


def _update(entry, **values):
	"""Writes `values` into `entry`; True when one of them changed."""
	changed = any(entry[key] != value for key, value in values.items())
	entry.update(values)
	return changed


def refresh():
	"""Wave 5's sign rule over every entry (uiprivateshopbuilder.
	RefreshShopBoards): which signs always show and which are among the
	nearest, and a visited sign's own color back after SIGN_SEEN_MINUTES;
	then the timer's next turn. The signs are written only when one changed:
	the runtime updates every view of a key it is given, equal or not."""
	if _board is None or not _entries:
		return
	const = _const()
	now = app.GetTime()
	changed = False
	if const is None:
		own = player.GetMainCharacterIndex()
		for vid, entry in _entries.items():
			changed = _update(entry, always=vid == own, near=True) or changed
	else:
		always = set(_always_vids())
		vids = list(_entries.keys())
		near = set(const.nearest_signs(vids, player.GetCharacterDistance, const.sign_display_count()))
		for vid, entry in _entries.items():
			changed = _update(entry, always=vid in always, near=vid in near) or changed
			facade = _facades.get(vid)
			if facade is not None and facade.lastSeen and not const.is_seen(vid, now):
				facade.MarkUnseen()
	if changed:
		_sync()
	_board.set(tick_end=nui.now() + (getattr(const, "SIGN_REFRESH_SEC", REFRESH_SEC) if const is not None else REFRESH_SEC))


def _forget(vid, serial):
	"""A sign went: its entry leaves, unless a newer sign took the vid."""
	entry = _entries.get(vid)
	if entry is not None and entry["serial"] == serial:
		del _entries[vid]
		_sync()
		refresh()


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
	"""uiPrivateShopBuilder.PrivateShopAdvertisementBoard, or
	PrivateShopTitleBar(style), on NovaUI."""

	NUI_FACADE = True

	def __init__(self, style=0):
		self._nui_discarded = False
		self._serial = _next_serial[0]
		_next_serial[0] += 1
		self.vid = None
		self.title = ""
		self.lastSeen = 0
		self.style = _style(style)
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

	# --- the Interface's, the shop window's and the builder module's calls ----------------

	def Open(self, vid, text):
		"""As uiprivateshopbuilder.py's Open: the entry added and shown, the
		sign registered in the builder module's dict, a shop visited within
		SIGN_SEEN_MINUTES marked seen, and the rule run at once."""
		self.vid = vid
		self.title = text if isinstance(text, str) else str(text)
		if self.board is not None and not self._nui_discarded:
			if _board is None:
				self.board = _get_board()
			_entries.pop(vid, None)
			_entries[vid] = {"vid": int(vid), "text": self.title, "own": vid == player.GetMainCharacterIndex(),
			                 "shown": True, "serial": self._serial, "style": self.style, "seen": False,
			                 "always": vid == player.GetMainCharacterIndex(), "near": True}
			_facades[vid] = self
			weakref.finalize(self, _forget, vid, self._serial)
			_sync()
		uiPrivateShopBuilder.g_privateShopAdvertisementBoardDict[vid] = self
		const = _const()
		if const is not None and const.is_seen(vid, app.GetTime()):
			self.MarkSeen(const.seen_at(vid))
		refresh()

	def UpdateTitle(self, text):
		"""A new sign for a sign already shown (GC SHOP_SIGN again)."""
		self.title = text if isinstance(text, str) else str(text)
		entry = self._entry()
		if entry is not None and entry["text"] != self.title:
			entry["text"] = self.title
			_sync()

	def MarkSeen(self, when=None):
		"""The player opened this shop: a plain sign turns purple for a while
		(a decorated one keeps its style, as legacy's title bar)."""
		self.lastSeen = app.GetTime() if when is None else when
		const = _const()
		if const is not None:
			const.mark_seen(self.vid, self.lastSeen)
		self._set_seen(True)

	def MarkUnseen(self):
		self.lastSeen = 0
		self._set_seen(False)

	def Show(self):
		self._set_shown(True)

	def Hide(self):
		self._set_shown(False)

	def IsShow(self):
		entry = self._entry()
		return bool(entry is not None and entry["shown"] and (entry["always"] or (_show_all() and entry["near"])))

	def OnMouseLeftButtonUp(self):
		"""As uiprivateshopbuilder.py's."""
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

	def _set_seen(self, seen):
		entry = self._entry()
		seen = bool(seen and self.style == 0)
		if entry is None or entry["seen"] == seen:
			return
		entry["seen"] = seen
		_sync()
