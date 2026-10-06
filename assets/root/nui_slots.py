"""Slot models, the drag bridge and the tooltip bridge of the NovaUI slot
windows (docs/ui/AUTHORING.md "Slot grids"). Pure Python over the game
modules; it never runs per frame.

The slot model is one dict per cell with the keys of SLOT_KEYS, the same
whether this module or the C++ quickslot feed (NuiGameFeeds::BuildQuickSlots)
makes it. A window binds a list of them in nui/components/slot-grid.rcss's
markup and passes the cells' data events to a SlotDrag (pick and place
through mouseModule.mouseController, the one drag state of both UIs) and
to a TooltipBridge (the legacy item and skill tooltips)."""

import app
import constInfo
import grpImage
import item
import mouseModule
import player
import skill

import nui

try:
	import wndMgr
except ImportError:  # plain Python outside the client
	wndMgr = None

SLOT_KEYS = ("index", "kind", "type", "ref", "icon", "count", "w", "h",
             "cd_start", "cd_end", "active", "cover", "disabled", "locked")

_GUILD_SKILL = getattr(skill, "SKILL_TYPE_GUILD", 5)


def empty_slot(index):
	"""Every key at its empty value."""
	return {"index": int(index), "kind": "", "type": 0, "ref": 0, "icon": "", "count": "", "w": 1, "h": 1,
		"cd_start": 0.0, "cd_end": 0.0, "active": False, "cover": False, "disabled": False, "locked": False}


def icon_source(path):
	"""An image source as <img src> takes it: a store path gets a leading "/"
	("icon/item/27001.tga" -> "/icon/item/27001.tga"), a drive path
	("d:/ymir work/...") and a "/" path stay as they are, "" stays ""."""
	if not path:
		return ""
	path = str(path).replace("\\", "/")
	if path.startswith("/") or path[1:3] == ":/":
		return path
	return "/" + path


def count_label(grade, level):
	"""The label CSlotWindow::SetSlotCountNew draws for a skill: "" for a level
	of 0 or less, else "%d", "m%d", "g%d" or "p" for the grades 0 to 3 (and ""
	for another grade, for which legacy formats nothing)."""
	level = int(level)
	if level <= 0:
		return ""
	return {0: "%d" % level, 1: "m%d" % level, 2: "g%d" % level, 3: "p"}.get(int(grade), "")


def cooldown_span(cool_time, elapsed=0.0):
	"""(start, end) of a cooldown of `cool_time` seconds of which `elapsed`
	have passed, in nui.now() seconds, for nui-cooldown; (0.0, 0.0) for none."""
	cool_time = float(cool_time)
	if cool_time <= 0:
		return (0.0, 0.0)
	start = nui.now() - float(elapsed)
	return (start, start + cool_time)


def _exists(path):
	"""False for an icon file the client does not have, so the cell shows no
	image instead of RmlUi's solid box (docs/ui/AUTHORING.md)."""
	exists = getattr(app, "IsExistFile", None)
	return exists is None or bool(exists(path))


def item_slot(index, inventory_pos, window=None):
	"""The cell of the item at an inventory position (or at (window,
	position) for another inventory window), as RefreshQuickSlot shows it:
	the icon, the count above 1, the item's size and the active state of an
	auto potion that is on. An empty cell for vnum 0 (the item went)."""
	slot = empty_slot(index)
	at = (inventory_pos,) if window is None else (window, inventory_pos)
	vnum = player.GetItemIndex(*at)
	if not vnum:
		return slot
	count = player.GetItemCount(*at)
	item.SelectItem(vnum)
	icon = item.GetIconImageFileName()
	width, height = item.GetItemSize()
	dragon_soul = window is not None and window == getattr(player, "DRAGON_SOUL_INVENTORY", None)
	slot.update({
		"kind": "item",
		"type": player.SLOT_TYPE_DRAGON_SOUL_INVENTORY if dragon_soul else player.SLOT_TYPE_INVENTORY,
		"ref": int(inventory_pos),
		"icon": icon_source(icon) if icon and _exists(icon) else "",
		"count": str(count) if count > 1 else "",
		"w": int(width),
		"h": int(height),
	})
	if constInfo.IS_AUTO_POTION(vnum):
		slot["active"] = 0 != int(player.GetItemMetinSocket(*(at + (0,))))
	return slot


def skill_slot(index, skill_slot_number):
	"""The cell of the skill in a skill slot, as RefreshQuickSlot shows it: the
	grade's icon, the level label, the cover, a running cooldown and the
	active state. A guild skill has grade 0 and the guild's level. An empty
	cell for skill index 0."""
	slot = empty_slot(index)
	skill_index = player.GetSkillIndex(skill_slot_number)
	if not skill_index:
		return slot
	if skill.GetSkillType(skill_index) == _GUILD_SKILL:
		import guild
		grade, level = 0, guild.GetSkillLevel(skill_slot_number)
	else:
		grade, level = player.GetSkillGrade(skill_slot_number), player.GetSkillLevel(skill_slot_number)
	get_icon = getattr(skill, "GetIconImageFileNameNew", None)
	icon = get_icon(skill_index, grade) if get_icon is not None else ""
	slot.update({
		"kind": "skill",
		"type": player.SLOT_TYPE_SKILL,
		"ref": int(skill_slot_number),
		"icon": icon_source(icon),
		"count": count_label(grade, level),
		"cover": True,
		"active": bool(player.IsSkillActive(skill_slot_number)),
	})
	if level > 0 and player.IsSkillCoolTime(skill_slot_number):
		cool_time, elapsed = player.GetSkillCoolTime(skill_slot_number)
		slot["cd_start"], slot["cd_end"] = cooldown_span(cool_time, elapsed)
	return slot


def emotion_slot(index, emotion_index):
	"""The cell of an emotion: its registered icon and the cover."""
	slot = empty_slot(index)
	get_icon = getattr(player, "GetEmotionIconFileName", None)
	icon = get_icon(emotion_index) if get_icon is not None else ""
	slot.update({"kind": "emotion", "type": player.SLOT_TYPE_EMOTION, "ref": int(emotion_index),
		"icon": icon_source(icon), "cover": True})
	return slot


def item_layer(items, cols, rows):
	"""The item layer of a layered grid (multi-cell icons): one entry per
	(cell, slot) pair in `items` whose w x h fits the grid from that cell,
	with the slot's keys plus "c" and "r", the cell's column and row."""
	layer = []
	for cell, slot in items:
		c, r = cell % cols, cell // cols
		w, h = int(slot.get("w", 1)), int(slot.get("h", 1))
		if 0 <= cell and r < rows and c + w <= cols and r + h <= rows:
			entry = dict(slot)
			entry["c"], entry["r"] = c, r
			layer.append(entry)
	return layer


def owner_of_cells(items, cols, rows):
	"""Per cell of a cols x rows grid, the position in `items` of the
	(cell, slot) pair whose item covers it, or -1, for hit testing a layered
	grid."""
	owners = [-1] * (cols * rows)
	for position, (cell, slot) in enumerate(items):
		c, r = cell % cols, cell // cols
		for dy in range(int(slot.get("h", 1))):
			for dx in range(int(slot.get("w", 1))):
				x, y = c + dx, r + dy
				if 0 <= x < cols and 0 <= y < rows:
					owners[y * cols + x] = position
	return owners


def footprint(cell, w, h, cols, rows):
	"""The cells a w x h item covers when it is dropped from the hovered
	`cell`, as CGridSlotWindow::GetPickedSlotList works them out: a 2-tall
	item covers the hovered row and the one below, a 3-tall one the rows
	around it, and an area that leaves the grid is moved back into it. []
	when the cell is outside the grid or the item is larger than it. Widths
	follow the same rule as heights (legacy items are one column wide)."""
	if not (0 <= cell < cols * rows) or not (1 <= w <= cols) or not (1 <= h <= rows):
		return []
	ix, iy = cell % cols, cell // cols

	def span(at, size, count):
		start = at - 1 if size == 3 else at
		end = start + size - 1
		if start < 0:
			start, end = 0, end - start
		if end >= count:
			start, end = start - (end - count + 1), count - 1
		return start, end

	x0, x1 = span(ix, w, cols)
	y0, y1 = span(iy, h, rows)
	return [y * cols + x for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


# --- the drag bridge ------------------------------------------------------------

# The left press that picked an item in a NovaUI grid: (SlotDrag, cell), in
# any grid, so a press in one NovaUI grid and its release over another drop
# there. Every left press and release, and the end of an attach made here,
# forget it.
_press = None


def _forget_press():
	global _press
	_press = None


def _free_icon(handle, kind):
	"""Frees an icon instance of the kind AttachObject made it for."""
	if not handle:
		return
	if kind == player.SLOT_TYPE_SKILL:
		skill.DeleteIconInstance(handle)
	elif kind == player.SLOT_TYPE_EMOTION:
		grpImage.Delete(handle)
	else:
		item.DeleteIconInstance(handle)


def _leaked_kind(slot_type, slot_number):
	"""The kind of icon instance mouseModule's DeattachObject leaves behind
	for an attach of this type (it frees only inventory, shop, safebox, mall,
	skill and emotion icons), or None when it frees it."""
	if slot_type == player.SLOT_TYPE_QUICK_SLOT:
		return player.GetGlobalQuickSlot(slot_number)[0]
	if slot_type == getattr(player, "SLOT_TYPE_DRAGON_SOUL_INVENTORY", None):
		return player.SLOT_TYPE_INVENTORY
	return None


def attach(owner, slot_type, slot_number, item_index, count=0, on_end=None):
	"""Attaches through mouseModule.mouseController.AttachObject, after
	detaching what it held. For this attach only, it shadows DeattachObject
	on the controller instance: the shadow calls the class method, frees
	the icon instance the class method leaves (quick slot: by the quick
	slot's content; dragon soul: item.DeleteIconInstance), calls on_end()
	(the owner clears its pick highlight), and removes itself. A legacy
	attach never sees it. True when something is attached."""
	controller = mouseModule.mouseController
	if controller.isAttached():
		controller.DeattachObject()
	leaked = _leaked_kind(slot_type, slot_number)
	controller.AttachObject(owner, slot_type, slot_number, item_index, count)
	if not controller.isAttached():
		return False
	handle = getattr(controller, "AttachedIconHandle", 0)
	deattach_class = type(controller).DeattachObject

	def deattach():
		current = getattr(controller, "AttachedIconHandle", 0)
		# First, so a nested call (C++ DeattachIcon from inside) reaches the class method.
		controller.__dict__.pop("DeattachObject", None)
		_forget_press()
		deattach_class(controller)
		if current != handle:
			# A later AttachObject replaced this one without a detach: its
			# icon was never freed, whatever its type.
			_free_icon(handle, leaked if leaked is not None else slot_type)
		elif leaked is not None:
			_free_icon(handle, leaked)
		if on_end is not None:
			on_end()

	controller.DeattachObject = deattach
	return True


def attached():
	"""Whether the legacy mouse controller holds something."""
	return bool(mouseModule.mouseController.isAttached())


def _dragging():
	"""wndMgr.IsDragging(): 10 px or more from the last left press; true with
	an exe that has no such binding."""
	is_dragging = getattr(wndMgr, "IsDragging", None)
	return True if is_dragging is None else bool(is_dragging())


class SlotDrag(object):
	"""Pick-and-place for one NovaUI grid (D4, D5). The window passes its
	data events here; `pick(index)` answers (slot_type, slot_number,
	item_index, count) or None for a cell that cannot be picked (empty,
	locked); `drop(index)` places what is attached; `use(index)` is the
	right button with nothing attached. `on_pick(index)` runs after a pick
	attached something (the window hides its tooltips), `on_end()` when that
	attach ends. `owner` is what AttachObject records as the owner (the
	window; by default this object)."""

	def __init__(self, pick, drop, use=None, on_pick=None, on_end=None, owner=None):
		self.pick = pick
		self.drop = drop
		self.use = use
		self.on_pick = on_pick
		self.on_end = on_end
		self.owner = owner

	def press(self, index, button):
		"""A mousedown on a cell. Left: with something attached, drop it here;
		else pick the cell up and remember the press. Right: with nothing
		attached, use the cell; with something attached, nothing (the host
		cancelled the attach and kept the press, NuiHost.h)."""
		global _press
		if button == 0:
			_press = None
			if attached():
				self.drop(index)
				return
			picked = self.pick(index)
			if not picked:
				return
			slot_type, slot_number, item_index, count = picked
			if attach(self if self.owner is None else self.owner, slot_type, slot_number, item_index, count,
					on_end=self.on_end):
				_press = (self, index)
				if self.on_pick is not None:
					self.on_pick(index)
		elif button == 1:
			if not attached() and self.use is not None:
				self.use(index)

	def release(self, index, button):
		"""A mouseup on a cell: after a pick on another cell (of any NovaUI
		grid) and a drag of 10 px or more, drop what is attached here. A
		release on the cell it was picked from keeps the item attached
		(pick-and-place)."""
		global _press
		if button != 0:
			return
		pressed, _press = _press, None
		if pressed is None or (pressed[0] is self and pressed[1] == index):
			return
		if attached() and _dragging():
			self.drop(index)

	def legacy_drop(self, index):
		"""nuidrop: a press in the legacy UI dragged and released over the
		cell drops what is attached."""
		if attached():
			self.drop(index)


# --- the tooltip bridge -----------------------------------------------------------

def _usable(tooltip):
	return tooltip is not None and not (isinstance(tooltip, int) and tooltip == 0)


class TooltipBridge(object):
	"""Shows the legacy item and skill tooltips (uitooltip.ItemToolTip,
	SkillToolTip: TOP_MOST, not pickable, following the mouse in their own
	OnUpdate, assets/root/uitooltip.py:110-117, :316-359) for NovaUI cells,
	as the legacy windows do through SetItemToolTip and SetSkillToolTip.
	Nothing shows while an item is attached, and a tooltip not set yet (0)
	is skipped."""

	def __init__(self):
		self.item = 0
		self.skill = 0

	def set_item_tooltip(self, tooltip):
		self.item = tooltip

	def set_skill_tooltip(self, tooltip):
		self.skill = tooltip

	def show_inventory_item(self, inventory_pos):
		if attached():
			return
		if _usable(self.item):
			self.item.SetInventoryItem(inventory_pos)
		if _usable(self.skill):
			self.skill.HideToolTip()

	def show_skill(self, skill_slot, skill_index, grade, level):
		if attached():
			return
		if _usable(self.skill):
			self.skill.SetSkillNew(skill_slot, skill_index, grade, level)
		if _usable(self.item):
			self.item.HideToolTip()

	def show_skill_index(self, skill_index):
		"""The skill pickers' tooltip (SkillButton.OnOverInItem)."""
		if attached():
			return
		if _usable(self.skill):
			self.skill.SetSkill(skill_index)
		if _usable(self.item):
			self.item.HideToolTip()

	def hide(self):
		if _usable(self.item):
			self.item.HideToolTip()
		if _usable(self.skill):
			self.skill.HideToolTip()
