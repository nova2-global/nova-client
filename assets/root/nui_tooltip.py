"""The NovaUI tooltip recorder (P14 spec 5): the item, skill and link
tooltips keep one rule engine, the legacy uitooltip.py, and NovaUI records
what its rules build.

Once this module is imported (only when a Wave 3b flag uses it), uiToolTip's
module global `ui` is a proxy module whose TextLine, ImageBox and Line are
the real legacy widgets with bookkeeping (what each was told: text, color,
alignment, outline, shown state, owner, the order it was made in); every
other name is the real ui's. No line of uitooltip.py changes, so whatever
the rules append, now or after the foundation wave's C2, is recorded.

A facade (nui_item_tooltip.ItemToolTip, nui_skill_tooltip.SkillToolTip,
nui_link_tooltip.HyperlinkItemToolTip, EmbeddedItemToolTip below) is a
subclass of the legacy class with Facade first: every legacy rule runs on
it, its legacy board stays hidden (never drawn), and when a public call
ends with the tooltip shown and changed, the recorded widgets become one
model (build_model: lines of runs with roles, images, sockets, countdowns)
that a NovaUI document renders. The model is built once per hover, and the
documents need no per-frame Python: placement is the runtime's
(follow_pointer), remaining times are nui-countdown runs.

The three tooltip documents are loaded at their first show in a phase and
then kept, hidden and empty, until the phase ends (end_phase(), spec D8)."""

import sys
import time
import types
import weakref

import app
import dbg
import grp
import localeInfo
import uiToolTip

import nui
import nui_hud
import nui_text

# The legacy taskbar's height at the screen's bottom (uiscript/taskbar.py).
LEGACY_TASKBAR_HEIGHT = 37


def bottom_reserve_dp():
	"""The dp a tooltip keeps clear of at the screen's bottom (P14 spec
	5.5.7): the legacy taskbar's while it is the one in use, since it is a
	TOP_MOST window and the tooltips draw below that layer; none with the
	NovaUI taskbar, which draws below them."""
	if nui_hud.current("taskbar") is not None:
		return 0
	return LEGACY_TASKBAR_HEIGHT / (nui.get_scale() or 1.0)


# --- the role table (spec 5.3) -------------------------------------------------------------

# uitooltip.ToolTip's color constants, in this order; a value already in the
# table keeps its first role.
ROLE_ORDER = (
	("TITLE_COLOR", "title"), ("SPECIAL_TITLE_COLOR", "special"), ("NORMAL_COLOR", "normal"),
	("FONT_COLOR", "normal"), ("ENABLE_COLOR", "normal"), ("PRICE_COLOR", "price"),
	("HIGH_PRICE_COLOR", "special"), ("MIDDLE_PRICE_COLOR", "price-middle"), ("LOW_PRICE_COLOR", "price-low"),
	("DISABLE_COLOR", "negative"), ("NEGATIVE_COLOR", "negative"), ("CANNOT_LEVEL_UP_COLOR", "negative"),
	("POSITIVE_COLOR", "positive"), ("SPECIAL_POSITIVE_COLOR", "positive-special"),
	("SPECIAL_POSITIVE_COLOR2", "positive-rare"), ("CONDITION_COLOR", "condition"),
	("CAN_LEVEL_UP_COLOR", "level-up"), ("NEED_SKILL_POINT_COLOR", "skill-point"))
ROLES = ("title", "special", "normal", "price", "price-middle", "price-low", "negative", "positive",
         "positive-special", "positive-rare", "condition", "level-up", "skill-point", "custom")


def _packed(value):
	"""A legacy color as an unsigned 0xAARRGGBB: grp.GenerateColor answers a
	signed C long, the hex literals are positive (spec D7)."""
	return int(value) & 0xFFFFFFFF


def role_table(cls=None):
	"""({packed color: role}, {role: packed color}, [unmapped constant
	names]) from the legacy ToolTip's constants. A constant the table names
	but the class lacks is skipped; a *_COLOR constant it does not name is
	listed as unmapped (its lines are custom runs, with their color)."""
	cls = cls if cls is not None else uiToolTip.ToolTip
	by_color, by_role = {}, {}
	for name, role in ROLE_ORDER:
		value = getattr(cls, name, None)
		if not isinstance(value, int) or isinstance(value, bool):
			continue
		color = _packed(value)
		by_color.setdefault(color, role)
		by_role.setdefault(role, color)
	known = set(name for name, _ in ROLE_ORDER)
	unmapped = set()
	for klass in (cls, getattr(uiToolTip, "ItemToolTip", None), getattr(uiToolTip, "SkillToolTip", None)):
		for name, value in vars(klass).items() if klass is not None else ():
			if name.endswith("_COLOR") and name not in known and isinstance(value, int):
				unmapped.add(name)
	return by_color, by_role, sorted(unmapped)


ROLE_OF_COLOR, COLOR_OF_ROLE, UNMAPPED_COLORS = role_table()


def color_text(color):
	"""#rrggbbaa of a packed 0xAARRGGBB."""
	color = _packed(color)
	return "#%02x%02x%02x%02x" % ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF, (color >> 24) & 0xFF)


# --- what the recorder counts (read by the kit, spec 5.2.7) ---------------------------------

STATS = {"builds": 0, "publishes": 0, "build_ms_max": 0.0, "build_ms_sum": 0.0, "lines_max": 0, "errors": 0,
         "unrecorded": 0}
# Gap values the build saw that are not 0 to 40 in steps of 5: {value: count}.
GAP_VALUES = {}

# --- the recording widgets (spec 5.2.1) -----------------------------------------------------

_seq = [0]       # the creation order of recording widgets
_group = [None]  # the socket group open now (the marker, spec 5.2.3)
_group_seq = [0]
_auto = [False]  # inside AutoAppendTextLine: its lines are as tall as their text plus 5


class _Record(object):
	"""The bookkeeping of a recording widget. Each setter keeps what it was
	told and tells the owner (the SetParent argument) that it changed; the
	geometry, measurement and drawing are the legacy widget's."""

	def _rec_init(self):
		_seq[0] += 1
		self._rec_seq = _seq[0]
		self._rec_owner = None
		self._rec_shown = False
		self._rec_group = _group[0]
		self._rec_auto = _auto[0]

	def _rec_parent(self):
		ref = self._rec_owner
		return ref() if ref is not None else None

	def _rec_touch(self):
		owner = self._rec_parent()
		if owner is not None and getattr(owner, "_NUI_RECORDS", False):
			owner._rec_version += 1

	def _rec_set(self, name, value):
		if getattr(self, name, None) != value:
			setattr(self, name, value)
			self._rec_touch()


def _recording_classes(real):
	"""TextLine, ImageBox and Line: subclasses of `real`'s (the real ui
	module) that record. Each keeps its legacy class name, since the rules
	compare it (AlignTextLineHorizonalCenter: type(child).__name__ ==
	"TextLine", MR-10)."""
	def common(base):
		class Recording(_Record, base):
			def __init__(self, *args, **kwargs):
				self._rec_init()
				base.__init__(self, *args, **kwargs)

			def SetParent(self, parent):
				try:
					self._rec_owner = weakref.ref(parent)
				except TypeError:
					self._rec_owner = None
				base.SetParent(self, parent)
				self._rec_touch()

			def Show(self):
				base.Show(self)
				self._rec_set("_rec_shown", True)

			def Hide(self):
				base.Hide(self)
				self._rec_set("_rec_shown", False)

			def SetPosition(self, x, y):
				base.SetPosition(self, x, y)
				self._rec_touch()
		return Recording

	text_base = common(real.TextLine)

	class TextLine(text_base):
		_rec_text = ""
		_rec_color = 0xFFFFFFFF
		_rec_outline = False
		_rec_feather = True
		_rec_align = "left"

		def SetText(self, text):
			text_base.SetText(self, text)
			self._rec_set("_rec_text", text if text else "")

		def SetPackedFontColor(self, color):
			text_base.SetPackedFontColor(self, color)
			self._rec_set("_rec_color", _packed(color))

		def SetFontColor(self, red, green, blue):
			text_base.SetFontColor(self, red, green, blue)
			self._rec_set("_rec_color", _packed(grp.GenerateColor(red, green, blue, 1.0)))

		def SetOutline(self, value=True):
			text_base.SetOutline(self, value)
			self._rec_set("_rec_outline", bool(value))

		def SetFeather(self, value=True):
			text_base.SetFeather(self, value)
			self._rec_set("_rec_feather", bool(value))

		def SetHorizontalAlignCenter(self):
			text_base.SetHorizontalAlignCenter(self)
			self._rec_set("_rec_align", "center")

		def SetHorizontalAlignRight(self):
			text_base.SetHorizontalAlignRight(self)
			self._rec_set("_rec_align", "right")

		def SetHorizontalAlignLeft(self):
			text_base.SetHorizontalAlignLeft(self)
			self._rec_set("_rec_align", "left")

		def SetWindowHorizontalAlignCenter(self):
			text_base.SetWindowHorizontalAlignCenter(self)
			self._rec_set("_rec_align", "center")

	image_base = common(real.ImageBox)

	class ImageBox(image_base):
		_rec_image = ""

		def LoadImage(self, path):
			image_base.LoadImage(self, path)
			self._rec_set("_rec_image", path if path else "")

	line_base = common(real.Line)

	class Line(line_base):
		_rec_color = 0xFFFFFFFF

		def SetColor(self, color):
			line_base.SetColor(self, color)
			self._rec_set("_rec_color", _packed(color))

	for cls, name in ((TextLine, "TextLine"), (ImageBox, "ImageBox"), (Line, "Line")):
		cls.__name__ = cls.__qualname__ = name
		cls.__module__ = __name__
		cls._rec_kind = name
	return {"TextLine": TextLine, "ImageBox": ImageBox, "Line": Line}


class _UiProxy(types.ModuleType):
	"""The ui module the rules see: the recording widgets, and every other
	name the real module's."""

	def __init__(self, real, classes):
		types.ModuleType.__init__(self, getattr(real, "__name__", "ui"))
		self.__dict__["_nui_real"] = real
		self.__dict__.update(classes)

	def __getattr__(self, name):
		return getattr(self.__dict__["_nui_real"], name)


_installed = []  # [the rules' globals, the real ui] while installed


def _rules_globals():
	"""The globals dict the legacy rules read (spec 5.2.2: a rule method's
	__globals__, which a logging wrapper keeps)."""
	method = vars(uiToolTip.ToolTip).get("AppendTextLine")
	found = getattr(method, "__globals__", None)
	return found if found is not None else vars(uiToolTip)


def install():
	"""Puts the recording proxy in place of the rules' `ui` (once); returns it."""
	rules = _rules_globals()
	current = rules.get("ui")
	if isinstance(current, _UiProxy):
		return current
	proxy = _UiProxy(current, _recording_classes(current))
	rules["ui"] = proxy
	_installed[:] = [rules, current]
	return proxy


def uninstall():
	"""Puts the real ui back (tests)."""
	if _installed:
		rules, real = _installed
		rules["ui"] = real
		del _installed[:]


def is_recording(widget):
	return isinstance(widget, _Record)


# --- the model (spec 5.4, 5.2.6) --------------------------------------------------------------

TEXT_LINE_HEIGHT = 17          # ToolTip.TEXT_LINE_HEIGHT
DIVIDER_ABOVE, DIVIDER_HEIGHT = 3, 11  # AppendHorizontalLine: its lines at +3 and +4, then 11
SOCKET_HEIGHT, SOCKET_EXTRA = 35, 18   # __AppendMetinSlotInfo_AppendMetinSocketData
SOCKET_FRAMES = {"metin_slot_silver.sub": "silver", "metin_slot_gold.sub": "gold"}
GAP_STEP, GAP_MAX = 5, 40


def _entry(kind, **values):
	"""A model entry with every key the documents read (an entry of another
	kind still has them, since a hidden element's views read them too)."""
	entry = {"t": kind, "gap": 0, "rule": False, "align": "center", "outline": True, "runs": [], "src": "", "ih": 0,
	         "frame": "", "icon": "", "sub": []}
	entry.update(values)
	return entry


def _run(kind, text, role, color, end=0.0):
	return {"k": kind, "text": text, "role": role, "color": color, "end": float(end)}


def role_of(color):
	"""(role, "#rrggbbaa" for a custom run, else "")."""
	role = ROLE_OF_COLOR.get(_packed(color))
	if role is None:
		return "custom", color_text(color)
	return role, ""


def _has_tags(text):
	"""Whether legacy draws `text` as anything but its own characters in the
	line's color (a color tag, a link, an escaped |): nui_text's runs."""
	if "|" not in text:
		return False
	runs = nui_text.parse_runs(text)
	return not (len(runs) == 1 and runs[0][0] == text and runs[0][1] == -1 and not runs[0][2])


def text_runs(text, color):
	"""The runs of one legacy text line: one tags run (nui-text) for text with
	legacy tags, else one text run (plain_text); the line's role and color."""
	role, custom = role_of(color)
	if _has_tags(text):
		return [_run("tags", text, role, custom)]
	return [_run("text", nui.plain_text(text), role, custom)]


def _time_runs(text, color, info):
	"""A timeInfoList line (a remaining time legacy rewrites every frame) as a
	text run and a countdown run, when its text ends with the remaining time;
	None otherwise (a shop item's empty line, a text the rules changed)."""
	if not text:
		return None
	value = info.get("value") if isinstance(info, dict) else None
	if value is None:
		return None
	left = max(0, int(value) - int(app.GetGlobalTimeStamp()))
	# The text was written when the line was made or by the last OnUpdate:
	# within the same second, or the one before or after.
	for seconds in (left, left + 1, left - 1):
		if seconds < 0:
			continue
		suffix = localeInfo.RTSecondToDHMS(seconds)
		if text.endswith(suffix):
			break
	else:
		return None
	role, custom = role_of(color)
	prefix = text[:len(text) - len(suffix)] if suffix else text
	return [_run("text", nui.plain_text(prefix), role, custom), _run("count", "", role, custom, nui.now() + left)]


def _source(path):
	"""An image as <img src> takes it: a store path rooted with /, a d:/ path
	as legacy writes it."""
	path = (path or "").replace("\\", "/")
	if not path or path.startswith("/") or (len(path) > 1 and path[1] == ":"):
		return path
	return "/" + path


def _frame_of(path):
	name = (path or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
	return SOCKET_FRAMES.get(name, "")


def _gap(value):
	"""A gap in legacy px as one of 0, 5, ..., 40; another value is noted."""
	value = int(value)
	if value % GAP_STEP or value < 0 or value > GAP_MAX:
		if value not in GAP_VALUES:
			dbg.Tracen("nui_tooltip: a gap of %d px, drawn as %d" % (value, min(max(value, 0), GAP_MAX)))
		GAP_VALUES[value] = GAP_VALUES.get(value, 0) + 1
	value = min(max(value, 0), GAP_MAX)
	return (value + GAP_STEP // 2) // GAP_STEP * GAP_STEP


def _widgets(tip):
	"""The shown recording widgets of childrenList, then the lines of
	timeInfoList not already there (by identity), and {id: time info}."""
	seen = set()
	found = []
	times = {}
	for widget in list(getattr(tip, "childrenList", None) or ()):
		if id(widget) not in seen:
			seen.add(id(widget))
			found.append(widget)
	for info in list(getattr(tip, "timeInfoList", None) or ()):
		line = info.get("line") if isinstance(info, dict) else None
		if not line:
			continue
		times[id(line)] = info
		if id(line) not in seen:
			seen.add(id(line))
			found.append(line)
	shown = []
	for widget in found:
		if not is_recording(widget):
			STATS["unrecorded"] += 1
			continue
		if not widget._rec_shown:
			continue
		x, y = widget.GetLocalPosition()
		shown.append((int(y), widget._rec_seq, int(x), widget))
	shown.sort(key=lambda item: (item[0], item[1]))
	return shown, times


def _line_height(widget):
	if widget._rec_auto:
		return int(widget.GetTextSize()[1]) + 5
	return TEXT_LINE_HEIGHT


def _line_entry(widget, times):
	text = widget._rec_text
	runs = None
	info = times.get(id(widget))
	if info is not None:
		runs = _time_runs(text, widget._rec_color, info)
	if runs is None:
		runs = text_runs(text, widget._rec_color)
	return _entry("line", align=widget._rec_align, outline=widget._rec_outline, runs=runs)


def _positional_groups(items):
	"""{seq of a widget: group id} by position (spec 5.2.3's fallback): a
	socket frame image opens a row that takes every later widget (in
	creation order) lying within it: from the frame's y to its y + 1 + 35,
	and 18 more for each text line at the row's text column below that."""
	groups = {}
	by_seq = sorted(items, key=lambda item: item[1])
	for index, (y, seq, x, widget) in enumerate(by_seq):
		if widget._rec_kind != "ImageBox" or not _frame_of(widget._rec_image) or seq in groups:
			continue
		groups[seq] = seq
		end = y + 1 + SOCKET_HEIGHT
		column = None
		for other_y, other_seq, other_x, other in by_seq[index + 1:]:
			if other._rec_kind == "ImageBox" and _frame_of(other._rec_image):
				break
			if other._rec_kind == "ImageBox" and not other._rec_image:
				groups[other_seq] = seq  # an empty socket's stone image: never placed, draws nothing
				continue
			if other_y >= y and other_y < end:
				groups[other_seq] = seq
				if other._rec_kind == "TextLine" and column is None:
					column = other_x
				continue
			if other._rec_kind == "TextLine" and other_x == column and end <= other_y < end + SOCKET_EXTRA + 1:
				groups[other_seq] = seq
				end += SOCKET_EXTRA
				continue
			break
	return groups


def build_model(tip, positional=False):
	"""The model of a tooltip's recorded widgets (spec 5.2.6): {"lines":
	[entry], "min_w": toolTipWidth}. Socket rows are grouped by the marker
	the facade opens around each legacy socket call, or, with `positional`
	(or for widgets made outside a marker), by position."""
	items, times = _widgets(tip)
	marker = {}
	if not positional:
		for y, seq, x, widget in items:
			if widget._rec_group is not None:
				marker[seq] = ("m", widget._rec_group)
	position = dict((seq, ("p", group)) for seq, group in _positional_groups(items).items() if seq not in marker)
	groups = dict(position)
	groups.update(marker)

	members = {}
	for item in items:
		group = groups.get(item[1])
		if group is not None:
			members.setdefault(group, []).append(item)

	lines = []
	bottom = None       # the previous entry's bottom, legacy px
	rule = None         # (top, bottom) of a divider waiting for its entry
	done = set()
	for y, seq, x, widget in items:
		if widget._rec_kind == "ImageBox" and not widget._rec_image:
			continue  # an image that loaded nothing draws nothing (an empty socket's stone: never placed)
		group = groups.get(seq)
		if group is not None:
			if group in done:
				continue
			done.add(group)
			entry, top, entry_bottom = _socket_entry(members[group], times)
		elif widget._rec_kind == "Line":
			top = y - DIVIDER_ABOVE
			if rule is None:
				rule = (top, top + DIVIDER_HEIGHT)
			continue
		elif widget._rec_kind == "ImageBox":
			if not widget._rec_image:
				continue  # an image that loaded nothing draws nothing
			height = int(widget.GetHeight())
			entry, top, entry_bottom = _entry("image", src=_source(widget._rec_image), ih=height), y, y + height
		else:
			entry, top, entry_bottom = _line_entry(widget, times), y, y + _line_height(widget)
		gap = 0
		if rule is not None:
			entry["rule"] = True
			gap = (rule[0] - bottom if bottom is not None else 0) + (top - rule[1])
			rule = None
		elif bottom is not None:
			gap = top - bottom
		entry["gap"] = _gap(gap) if lines else 0
		lines.append(entry)
		bottom = entry_bottom
	return {"lines": lines, "min_w": int(getattr(tip, "toolTipWidth", 0) or 0)}


def _socket_entry(group, times):
	"""(entry, top, bottom) of one socket row: its frame, its stone's icon and
	its text lines in y order."""
	frame, icon, top = "", "", None
	subs = []
	for y, seq, x, widget in sorted(group, key=lambda item: (item[0], item[1])):
		if widget._rec_kind == "ImageBox":
			kind = _frame_of(widget._rec_image)
			if kind and not frame:
				frame, top = kind, y
			elif widget._rec_image and not icon:
				icon = _source(widget._rec_image)
		elif widget._rec_kind == "TextLine":
			sub = _line_entry(widget, times)
			sub["align"] = "left"
			subs.append(sub)
	if top is None:
		top = min(item[0] for item in group) - 1
	height = SOCKET_HEIGHT + SOCKET_EXTRA * max(0, len(subs) - 2)
	entry = _entry("socket", frame=frame or "silver", icon=icon, sub=subs, align="left")
	return entry, top + 1, top + 1 + height


# --- the facades (spec 5.2.4, 5.2.5) -----------------------------------------------------------

# The tooltip documents by kind, loaded at their first show and kept,
# hidden and empty, until end_phase() (spec D8); and the facade that shows
# in each (a weak reference).
_boards = {}
_owners = {}


def board(kind):
	"""The kind's board while loaded, else None."""
	found = _boards.get(kind)
	return found if found is not None and found._doc else None


def _owner(kind):
	ref = _owners.get(kind)
	return ref() if ref is not None else None


def end_phase():
	"""nui_windows.end_phase(): the tooltip documents go with the phase.
	Returns how many were loaded."""
	count = 0
	for kind, found in list(_boards.items()):
		if found._doc:
			count += 1
		found.destroy()
	_boards.clear()
	_owners.clear()
	return count


def _transactional(fn):
	"""A public method of a facade: the outermost call ends the transaction
	(builds and publishes once when the tooltip shows and changed). A rule
	that raises still ends it, as legacy's board shows what the rules built
	before the raise; the exception goes on."""
	def call(self, *args, **kwargs):
		self._tx_depth += 1
		try:
			return fn(self, *args, **kwargs)
		finally:
			self._tx_depth -= 1
			if self._tx_depth == 0:
				self._tx_end()

	call.__name__ = getattr(fn, "__name__", "call")
	call.__doc__ = getattr(fn, "__doc__", None)
	call.__wrapped__ = fn
	call._nui_tx = True
	return call


def transactional(cls):
	"""Class decorator of a facade: every public method of the legacy tooltip
	classes and of the facade runs in a transaction (spec 5.2.5)."""
	names = set()
	for klass in cls.__mro__:
		if klass is Facade or issubclass(klass, uiToolTip.ToolTip):
			for name, attr in vars(klass).items():
				if not name.startswith("_") and isinstance(attr, types.FunctionType):
					names.add(name)
	for name in sorted(names):
		method = getattr(cls, name)
		function = getattr(method, "__func__", method)
		if getattr(function, "_nui_tx", False) or not isinstance(function, types.FunctionType):
			continue
		setattr(cls, name, _transactional(function))
	return cls


class Facade(object):
	"""What every NovaUI tooltip facade shares; it precedes the legacy class in
	the bases (class ItemToolTip(Facade, uiToolTip.ItemToolTip)).

	LEGACY is the legacy class, KIND the board's kind ("item", "skill",
	"link"; None for an embedded tooltip), FOLLOW_ONCE whether the board is
	placed at the pointer once and held (the link tooltip)."""

	NUI_FACADE = True
	_NUI_RECORDS = True
	LEGACY = None
	KIND = None
	FOLLOW_ONCE = False

	def __init__(self, *args, **kwargs):
		install()
		self._rec_version = 0
		self._built_version = None
		self._tx_depth = 0
		self._want_show = False
		self._shown = False
		self._fixed = None
		self._model = {"lines": [], "min_w": 0}
		self._nui_discarded = False
		self.LEGACY.__init__(self, *args, **kwargs)

	# --- make()'s protocol --------------------------------------------------------------

	def nui_ready(self):
		"""The Wave 3b engine and a document that loads (made, then unloaded
		again until the first show, D8)."""
		if not nui_hud.has_engine_3b():
			return False
		if self.KIND is None:
			return True
		if board(self.KIND) is not None:
			return True
		probe = self._make_board()
		loaded = bool(probe is not None and probe._doc)
		if probe is not None:
			probe.destroy()
		return loaded

	def nui_discard(self):
		self._nui_discarded = True
		self._release_board(destroy=True)

	# --- the board ------------------------------------------------------------------

	def _make_board(self):
		"""A new board of this kind (a nui.Window); the facade modules say."""
		return None

	def _board(self, make=False):
		kind = self.KIND
		if kind is None:
			return None
		found = board(kind)
		if found is None and make and not self._nui_discarded:
			found = self._make_board()
			if found is None or not found._doc:
				if found is not None:
					found.destroy()
				STATS["errors"] += 1
				return None
			_boards[kind] = found
		return found

	def _owns_board(self):
		return self.KIND is not None and _owner(self.KIND) is self

	def _release_board(self, destroy=False):
		"""Hides the board (empty) when this facade shows in it; with
		`destroy`, unloads it."""
		if self.KIND is None:
			return
		found = board(self.KIND)
		if found is None or not self._owns_board():
			return
		found.hide()
		found.set(lines=[])
		if destroy:
			found.destroy()
			_boards.pop(self.KIND, None)
			_owners.pop(self.KIND, None)

	# --- the transaction ------------------------------------------------------------

	def _tx_end(self):
		try:
			if self._want_show:
				self._want_show = False
				self._show_now()
			elif self._shown and self._rec_version != self._built_version:
				if self.KIND is None or self._owns_board():
					self._publish(self._build())
				else:
					self._shown = False  # another facade of this kind shows now
		except Exception as error:
			STATS["errors"] += 1
			dbg.TraceError("nui_tooltip: %s: %s (%s)" % (type(self).__name__, type(error).__name__, error))

	def _build(self):
		started = time.perf_counter()
		model = build_model(self)
		elapsed = (time.perf_counter() - started) * 1000.0
		self._built_version = self._rec_version
		STATS["builds"] += 1
		STATS["build_ms_sum"] += elapsed
		STATS["build_ms_max"] = max(STATS["build_ms_max"], elapsed)
		STATS["lines_max"] = max(STATS["lines_max"], len(model["lines"]))
		self._model = model
		return model

	def _publish(self, model):
		found = self._board(make=True)
		if found is None:
			return
		_owners[self.KIND] = weakref.ref(self)
		found.set(lines=model["lines"], min_w=model["min_w"])
		STATS["publishes"] += 1

	def _legacy_on_update(self):
		"""The legacy class's own OnUpdate, as legacy's ShowToolTip runs it once
		(the time texts; the link's is a no-op)."""
		self.LEGACY.OnUpdate(self)

	def _show_now(self):
		self._legacy_on_update()
		if self._rec_version != self._built_version or self._built_version is None:
			model = self._build()
		else:
			model = self._model
		self._shown = True
		self._publish(model)
		found = self._board()
		if found is None or not self._owns_board():
			return
		found.show()
		found.bring_to_front()
		self._place(found)

	def _place(self, found):
		if self._fixed is not None:
			scale = nui.get_scale() or 1.0
			x, y = self._fixed
			found.set_position(x / scale, y / scale + 10, origin=(0.5, 1.0))
		elif self.followFlag:
			found.follow_pointer(once=self.FOLLOW_ONCE, bottom_reserve_dp=bottom_reserve_dp())

	def model(self):
		"""The last model built: {"lines", "min_w"}."""
		return self._model

	# --- the overrides (spec 5.2.4) ---------------------------------------------------

	def Show(self):
		"""The document shows; the legacy board never does."""
		self._want_show = True

	def Hide(self):
		"""Hides the document and empties it; the legacy board stays hidden."""
		self.LEGACY.Hide(self)
		self._want_show = False
		was_shown, self._shown = self._shown, False
		self._built_version = None
		if was_shown or self._owns_board():
			self._release_board()

	def IsShow(self):
		"""The document's state: shown, with this facade's content."""
		if self.KIND is None:
			return self._shown
		found = board(self.KIND)
		return bool(self._shown and found is not None and self._owns_board() and found.is_visible())

	def SetTop(self):
		if self._owns_board():
			found = board(self.KIND)
			if found is not None:
				found.bring_to_front()

	def ShowToolTip(self):
		"""Asks for the show: the transaction's end shows the document once."""
		self._want_show = True

	def HideToolTip(self):
		self.Hide()

	def ClearToolTip(self):
		super(Facade, self).ClearToolTip()
		self._rec_version += 1

	def SetToolTipPosition(self, x=-1, y=-1):
		super(Facade, self).SetToolTipPosition(x, y)
		self._fixed = None if (x == -1 and y == -1) else (float(x), float(y))
		if self.IsShow():
			self._place(board(self.KIND))

	def SetFollow(self, flag):
		super(Facade, self).SetFollow(flag)
		found = board(self.KIND) if self.KIND is not None else None
		if not flag and found is not None and self._owns_board() and self._fixed is None:
			box = found.element_box("")
			if box:
				scale = nui.get_scale() or 1.0
				found.set_position(box[0] / scale, box[1] / scale)

	def Destroy(self):
		self._release_board(destroy=True)
		destroy = getattr(self.LEGACY, "Destroy", None)
		if destroy is not None:
			destroy(self)

	def OnUpdate(self):
		"""Nothing: no per-frame Python. A rule that calls ItemToolTip.OnUpdate
		by name (SetHyperlinkItem) reaches legacy's."""

	def AutoAppendTextLine(self, *args, **kwargs):
		_auto[0] = True
		try:
			return super(Facade, self).AutoAppendTextLine(*args, **kwargs)
		finally:
			_auto[0] = False

	def _ItemToolTip__AppendMetinSlotInfo_AppendMetinSocketData(self, *args, **kwargs):
		"""The socket group marker (spec 5.2.3): the widgets of one legacy
		socket row are one model entry."""
		_group_seq[0] += 1
		_group[0] = _group_seq[0]
		try:
			return super(Facade, self)._ItemToolTip__AppendMetinSlotInfo_AppendMetinSocketData(*args, **kwargs)
		finally:
			_group[0] = None


@transactional
class EmbeddedItemToolTip(Facade, uiToolTip.ItemToolTip):
	"""An item tooltip inside a NovaUI dialog (the refine dialogs, attach
	metin stone): no document of its own; the dialog shows model() in its
	own document. `on_model(model)` runs after each build."""

	LEGACY = uiToolTip.ItemToolTip
	KIND = None

	def __init__(self, *args, **kwargs):
		self.on_model = None
		Facade.__init__(self, *args, **kwargs)

	def _publish(self, model):
		callback = self.on_model
		if callback is not None:
			callback(model)

	def _show_now(self):
		self._legacy_on_update()
		if self._rec_version != self._built_version or self._built_version is None:
			model = self._build()
		else:
			model = self._model
		self._shown = True
		self._publish(model)

	def Hide(self):
		self.LEGACY.Hide(self)
		self._want_show = False
		self._shown = False

	def IsShow(self):
		return self._shown

	def SetTop(self):
		pass


# --- the parity test's flattening (spec 5.8; the kit's TP and TT use it in the client) ---------

DIVIDER_COLORS = (0xFF555555, 0xFF000000)   # uitooltip.py AppendHorizontalLine
FRAME_PATHS = {"silver": "d:/ymir work/ui/game/windows/metin_slot_silver.sub",
               "gold": "d:/ymir work/ui/game/windows/metin_slot_gold.sub"}


def _norm(path):
	return (path or "").replace("\\", "/").lstrip("/").lower()


def _plain(text):
	return (text or "").replace("\u2060", "")


def legacy_rows(tip):
	"""Spec 5.8 A: a legacy tooltip's shown widgets in (y, x) order, its
	time lines as their text: ("text", text, color, align, outline),
	("image", path), ("line", color). Needs recording widgets (a legacy
	tooltip made while the recorder is installed has them)."""
	items, times = _widgets(tip)
	rows = []
	for y, seq, x, widget in sorted(items, key=lambda item: (item[0], item[2], item[1])):
		kind = widget._rec_kind
		if kind == "TextLine":
			rows.append(("text", widget._rec_text, widget._rec_color, widget._rec_align, widget._rec_outline))
		elif kind == "ImageBox":
			if widget._rec_image:
				rows.append(("image", _norm(widget._rec_image)))
		elif kind == "Line":
			rows.append(("line", widget._rec_color))
	return rows


def model_rows(model, now=None):
	"""Spec 5.8 B: a published model flattened in order: each line's runs
	joined (a countdown run as RTSecondToDHMS of its time left at `now`,
	nui.now() by default), the role mapped back to its color (custom: its
	own), the alignment and outline; images; sockets as their frame, icon
	and lines; a divider as its two line colors."""
	now = nui.now() if now is None else now

	def line_row(entry):
		text = ""
		color = None
		for run in entry.get("runs") or ():
			if color is None:
				color = _color_of_run(run)
			if run.get("k") == "count":
				text += localeInfo.RTSecondToDHMS(max(0, int(round(float(run.get("end", 0.0)) - now))))
			else:
				text += _plain(run.get("text", ""))
		if color is None:
			color = COLOR_OF_ROLE.get("normal")
		return ("text", text, color, entry.get("align", "center"), bool(entry.get("outline")))

	rows = []
	for entry in (model or {}).get("lines") or ():
		if entry.get("rule"):
			rows += [("line", DIVIDER_COLORS[0]), ("line", DIVIDER_COLORS[1])]
		kind = entry.get("t")
		if kind == "line":
			rows.append(line_row(entry))
		elif kind == "image":
			if entry.get("src"):
				rows.append(("image", _norm(entry["src"])))
		elif kind == "socket":
			rows.append(("image", _norm(FRAME_PATHS.get(entry.get("frame"), ""))))
			if entry.get("icon"):
				rows.append(("image", _norm(entry["icon"])))
			for sub in entry.get("sub") or ():
				rows.append(line_row(sub))
	return rows


def _color_of_run(run):
	if run.get("role") == "custom":
		text = str(run.get("color") or "").lstrip("#")
		if len(text) == 8:
			r, g, b, a = (int(text[i:i + 2], 16) for i in (0, 2, 4, 6))
			return (a << 24) | (r << 16) | (g << 8) | b
		return None
	return COLOR_OF_ROLE.get(run.get("role"))


install()
