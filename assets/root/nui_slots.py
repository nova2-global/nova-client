"""Slot models, the drag bridge and the tooltip bridge of the NovaUI slot
windows (docs/ui/AUTHORING.md "Slot grids"). Pure Python over the game
modules; it never runs per frame.

The slot model is one dict per cell with the keys of SLOT_KEYS, the same
whether this module or the C++ quickslot feed (NuiGameFeeds::BuildQuickSlots)
makes it. A window binds a list of them in nui/components/slot-grid.rcss's
markup and passes the cells' data events to a SlotDrag (pick and place
through mouseModule.mouseController, the one drag state of both UIs) and
to a TooltipBridge (the legacy item and skill tooltips).

Slot grid v2 (P14 spec 4.8, 6.0) adds the item grids' cells (CELL_KEYS: an
item's anchor cell and the cells it covers, the drop footprint's states),
CGridSlotWindow's footprint, drop target and use-mode rules on cell events
(footprint_states, drop_target), and the pieces a NovaUI window uses when it
subclasses a legacy window: SlotWindowProxy stands where the legacy
ui.SlotWindow or ui.GridSlotWindow was and turns what the legacy controller
tells it into cells, and LegacySlotEvents turns the cells' events into the
legacy slot window's events, so every flow stays the legacy controller's."""

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


def owner_of_cells(items, cols, rows):
	"""Per cell of a cols x rows grid, the position in `items` of the
	(cell, slot) pair whose item covers it, or -1."""
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


# --- item grids (slot grid v2, P14 spec 4.2 to 4.4) -----------------------------------

# The keys of an item grid's cell: the slot model plus the grid's own.
# covered: a cell an item larger than one cell covers (its anchor holds the
# item; the covered cell stays a hit target, mapped to the anchor); target:
# the drop footprint's state ("", "move", "blocked", "usable", "unusable");
# picked: the cell the attached item came from; unavailable: the belt's
# cells beyond the belt's grade (legacy DisableCoverButton).
CELL_KEYS = SLOT_KEYS + ("covered", "target", "picked", "unavailable")
TARGET_STATES = ("move", "blocked", "usable", "unusable")


def empty_cell(index):
	"""empty_slot(index) plus covered False, target "", picked False,
	unavailable False."""
	cell = empty_slot(index)
	cell.update({"covered": False, "target": "", "picked": False, "unavailable": False})
	return cell


def as_cell(slot):
	"""A slot model dict with the grid keys added at their empty values (a
	copy; the slot's own keys win)."""
	cell = empty_cell(slot.get("index", 0))
	cell.update(slot)
	return cell


def mark_covered(cells, cols, rows):
	"""Marks, in place, every cell that an anchor's w x h covers inside the
	cols x rows grid: kind, icon and count emptied, w and h 1, the states
	off, covered True, type and ref kept as the owner's. An item that leaves
	the grid covers only its cells inside it, as legacy draws it clipped.
	An anchor is never covered. Returns {covered index: anchor index}."""
	owners = {}
	for anchor, cell in enumerate(cells):
		if not cell.get("kind") or cell.get("covered"):
			continue
		c, r = anchor % cols, anchor // cols
		for dy in range(int(cell.get("h", 1))):
			for dx in range(int(cell.get("w", 1))):
				if not (dx or dy):
					continue
				x, y = c + dx, r + dy
				if not (0 <= x < cols and 0 <= y < rows):
					continue
				index = y * cols + x
				if index >= len(cells) or (cells[index].get("kind") and not cells[index].get("covered")):
					continue
				covered = empty_cell(index)
				covered.update({"type": cell.get("type", 0), "ref": cell.get("ref", 0), "covered": True,
				                "unavailable": cells[index].get("unavailable", False)})
				cells[index] = covered
				owners[index] = anchor
	return owners


def item_cells(positions, cols, rows, window=None):
	"""The cells of a fixed grid whose cell i shows inventory position
	positions[i] (None for a cell with no position): item_slot() at each
	anchor, then every cell an anchor's w x h covers inside the grid marked
	covered (kind, icon and count emptied, ref kept as the owner's
	position). Raises nothing for an item that leaves the grid: its cells
	outside are dropped, as legacy draws them clipped."""
	cells = []
	for index, position in enumerate(positions):
		if position is None:
			cells.append(empty_cell(index))
		else:
			cells.append(as_cell(item_slot(index, position, window)))
	mark_covered(cells, cols, rows)
	return cells


def owner_index(cells, index, cols, rows):
	"""The index of the anchor whose item covers cell `index` (the cell
	itself when it holds the item or is empty), as CGridSlotWindow's center
	slot (dwCenterSlotNumber)."""
	cell = cells[index]
	if not cell.get("covered"):
		return index
	for anchor in range(index - 1, -1, -1):
		other = cells[anchor]
		if not other.get("kind") or other.get("covered"):
			continue
		c, r = anchor % cols, anchor // cols
		x, y = index % cols, index // cols
		if c <= x < c + int(other.get("w", 1)) and r <= y < r + int(other.get("h", 1)):
			return anchor
	return index


def _picked_list(cells, hovered, w, h, cols, rows, use_mode):
	"""CGridSlotWindow::GetPickedSlotList for an attached w x h icon over cell
	`hovered`, in legacy's order (columns outside, rows inside: the order
	the drop target's tie rule depends on): the footprint, and in use mode
	with a single cell, every other cell of the same owner, in index order."""
	if not (0 <= hovered < cols * rows):
		return []
	ix, iy = hovered % cols, hovered // cols
	half = w // 2
	x0, x1 = ix - (half - half % 2), ix + half
	if h == 2:
		y0, y1 = iy, iy + 1
	elif h == 3:
		y0, y1 = iy - 1, iy + 1
	else:
		y0, y1 = iy, iy
	if x0 < 0:
		x0, x1 = 0, x1 - x0
	if y0 < 0:
		y0, y1 = 0, y1 - y0
	if x1 >= cols:
		x0, x1 = x0 - (x1 - cols + 1), cols - 1
	if y1 >= rows:
		y0, y1 = y0 - (y1 - rows + 1), rows - 1
	found = [y * cols + x for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
	         if 0 <= x < cols and 0 <= y < rows and y * cols + x < len(cells)]
	if use_mode and len(found) == 1:
		main = owner_index(cells, found[0], cols, rows)
		for index in range(len(cells)):
			if index not in found and owner_index(cells, index, cols, rows) == main:
				found.append(index)
	return found


def _is_item(cell):
	return bool(cell.get("kind")) and not cell.get("covered")


def _vnum_of(cells, index, cols, rows, vnums):
	"""CGridSlotWindow's dwItemIndex of a cell after OnRefreshSlot: the vnum
	of the item at its owner (from `vnums`, anchor index -> vnum, else
	player.GetItemIndex of the owner's position), 0 for an empty cell."""
	owner = owner_index(cells, index, cols, rows)
	if not _is_item(cells[owner]):
		return 0
	if vnums is not None:
		return int(vnums.get(owner, 0))
	return int(player.GetItemIndex(cells[owner].get("ref", 0)))


def drop_target(cells, hovered, attached, cols, rows, use_mode=False, slot_numbers=None):
	"""The cell CGridSlotWindow::GetPickedSlotPointer answers while
	`attached` (attached_info()) is over cell `hovered`: of the picked list,
	the cell with the lowest number (an item cell over an empty one that
	comes later), then its owner, unless that owner is the cell the attached
	item came from (`slot_numbers[i]` is cell i's legacy slot number; None:
	the index). None when nothing is picked."""
	if attached is None:
		return None
	_, slot_number, _, _, w, h = attached
	found = _picked_list(cells, hovered, w, h, cols, rows, use_mode)
	if not found:
		return None
	number = (lambda i: slot_numbers[i]) if slot_numbers is not None else (lambda i: i)
	lowest = None
	for index in found:
		if lowest is None:
			lowest = index
		elif number(index) < number(lowest):
			lowest = index
		elif not _is_item(cells[lowest]) and _is_item(cells[index]):
			lowest = index
	center = owner_index(cells, lowest, cols, rows)
	if slot_number == number(center):
		return lowest
	return center


def attached_info():
	"""(slot_type, slot_number, vnum, count, w, h) of what
	mouseModule.mouseController holds (item.GetItemSize() of the vnum; 1, 1
	for money, skills and emotions; a quick slot's item its size), as
	AttachObject tells wndMgr.AttachIcon, or None. vnum is the attached
	index, which CGridSlotWindow compares with its cells' items."""
	controller = mouseModule.mouseController
	if not controller.isAttached():
		return None
	slot_type = controller.GetAttachedType()
	slot_number = controller.GetAttachedSlotNumber()
	vnum = controller.GetAttachedItemIndex()
	count = controller.GetAttachedItemCount()
	w = h = 1
	item_types = (player.SLOT_TYPE_INVENTORY, getattr(player, "SLOT_TYPE_PRIVATE_SHOP", -2),
	              getattr(player, "SLOT_TYPE_SHOP", -3), getattr(player, "SLOT_TYPE_SAFEBOX", -4),
	              getattr(player, "SLOT_TYPE_MALL", -5), getattr(player, "SLOT_TYPE_DRAGON_SOUL_INVENTORY", -6))
	if vnum != getattr(player, "ITEM_MONEY", -1):
		if slot_type in item_types:
			item.SelectItem(vnum)
			w, h = item.GetItemSize()
		elif slot_type == getattr(player, "SLOT_TYPE_QUICK_SLOT", -7):
			quick_type, position = player.GetGlobalQuickSlot(slot_number)
			if quick_type == player.SLOT_TYPE_INVENTORY:
				item.SelectItem(player.GetItemIndex(position))
				w, h = item.GetItemSize()
	return (slot_type, slot_number, vnum, count, int(w), int(h))


def footprint_states(cells, hovered, attached, cols, rows, use_mode, usable, pick_up=True, slot_numbers=None, vnums=None):
	"""{cell index: "move" | "blocked" | "usable" | "unusable"} as
	CGridSlotWindow::OnRenderPickingSlot draws them for `attached`
	(attached_info()) over cell `hovered`: in use mode with an item at the
	owner of the footprint's first cell, that item's cells, "usable" or
	"unusable" by `usable` (the window's SetUsableItem); else the footprint,
	"move" when CheckMoving holds (every cell empty, or holding the attached
	item's vnum, or the attached item's own cells: `vnums` maps an anchor
	index to its vnum), else "blocked". pick_up False (SLOT_STYLE_NONE): {},
	since CSlotWindow::OnRender draws the picking slots only for
	SLOT_STYLE_PICK_UP. {} when nothing fits or nothing is attached."""
	if attached is None or not pick_up:
		return {}
	_, _, _, _, w, h = attached
	found = _picked_list(cells, hovered, w, h, cols, rows, use_mode)
	if not found:
		return {}
	if use_mode:
		center = owner_index(cells, found[0], cols, rows)
		if _is_item(cells[center]):
			state = "usable" if usable else "unusable"
			anchor = cells[center]
			c, r = center % cols, center // cols
			marked = {}
			for dy in range(int(anchor.get("h", 1))):
				for dx in range(int(anchor.get("w", 1))):
					x, y = c + dx, r + dy
					if 0 <= x < cols and 0 <= y < rows and y * cols + x < len(cells):
						marked[y * cols + x] = state
			return marked
	state = "move" if _check_moving(cells, found, attached, cols, rows, slot_numbers, vnums) else "blocked"
	return dict((index, state) for index in found)


def _check_moving(cells, found, attached, cols, rows, slot_numbers=None, vnums=None):
	"""CGridSlotWindow::CheckMoving over the picked cells `found`: every cell
	whose owner is not the attached item's own cell is empty or holds the
	attached vnum."""
	_, slot_number, vnum, _, _, _ = attached
	number = (lambda i: slot_numbers[i]) if slot_numbers is not None else (lambda i: i)
	for index in found:
		center = owner_index(cells, index, cols, rows)
		if slot_number == number(center):
			continue
		held = _vnum_of(cells, index, cols, rows, vnums)
		if (held != 0 or center != index) and vnum != held:
			return False
	return True


def with_states(cells, states, picked=-1):
	"""A new list: each cell's target from states ("" elsewhere), picked True
	for the cell index `picked`."""
	result = []
	for index, cell in enumerate(cells):
		cell = dict(cell)
		cell["target"] = states.get(index, "")
		cell["picked"] = index == picked
		result.append(cell)
	return result


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
	"""Shows the Interface's item and skill tooltips (uitooltip.ItemToolTip,
	SkillToolTip, or their NovaUI facades while the tooltips flag is on) for
	NovaUI cells, as the legacy windows do through SetItemToolTip and
	SetSkillToolTip. Nothing shows while an item is attached, unless
	`while_attached` (the inventory windows show the hovered item's tooltip
	then, as legacy's OverInItem does, P14 spec D19), and a tooltip not set
	yet (0) is skipped."""

	def __init__(self, while_attached=False):
		self.item = 0
		self.skill = 0
		self.while_attached = bool(while_attached)

	def set_item_tooltip(self, tooltip):
		self.item = tooltip

	def set_skill_tooltip(self, tooltip):
		self.skill = tooltip

	def _blocked(self):
		return attached() and not self.while_attached

	def show_inventory_item(self, inventory_pos, window=None):
		"""SetInventoryItem(pos), or SetInventoryItem(pos, window) for another
		inventory window (the dragon soul inventory, uitooltip.py:657)."""
		if self._blocked():
			return
		if _usable(self.item):
			if window is None:
				self.item.SetInventoryItem(inventory_pos)
			else:
				self.item.SetInventoryItem(inventory_pos, window)
		if _usable(self.skill):
			self.skill.HideToolTip()

	def show_skill(self, skill_slot, skill_index, grade, level):
		if self._blocked():
			return
		if _usable(self.skill):
			self.skill.SetSkillNew(skill_slot, skill_index, grade, level)
		if _usable(self.item):
			self.item.HideToolTip()

	def show_skill_index(self, skill_index):
		"""The skill pickers' tooltip (SkillButton.OnOverInItem)."""
		if self._blocked():
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


# --- legacy slot windows inside NovaUI windows (P14 spec 6.0) -------------------------

def _mem_func(fn):
	"""fn as the legacy slot window stores an event (ui.__mem_func__: a weak
	method that drops the argument of a method taking only self); fn itself
	outside the client."""
	try:
		import ui
	except ImportError:
		return fn
	mem_func = getattr(ui, "__mem_func__", None)
	if mem_func is None or not hasattr(fn, "__self__"):
		return fn
	return mem_func(fn)


_EVENT_NAMES = ("select_empty", "select_item", "unselect_empty", "unselect_item", "use", "over_in", "over_out",
                "pressed_button")
_DEFAULT_COVER = "d:/ymir work/ui/public/slot_cover_button_01.sub"


def _pick_up_style():
	return getattr(wndMgr, "SLOT_STYLE_PICK_UP", 1)


class SlotWindowProxy(object):
	"""Stands for a legacy ui.SlotWindow or ui.GridSlotWindow inside a NovaUI
	window (P14 spec 6.0): it records what the legacy controller tells the
	widget and turns it into cells (CELL_KEYS) at RefreshSlot(), handing them to
	on_refresh(cells). slot_numbers: the legacy slot numbers in cell order (a
	grid page's local 0..n-1, a wear group's cell numbers); cols and rows for a
	grid (multi-cell, the footprint), None for single slots. positions maps a
	slot number to the inventory position its cell shows (a callable, or None:
	the slot number itself); window is the inventory window of the cells'
	items (None: the inventory).

	Only the legacy methods below exist, so a legacy call this proxy does not
	know raises AttributeError (the tests see it). A slot number the window
	does not hold is ignored, as CSlotWindow's GetSlotPointer ignores it."""

	def __init__(self, slot_numbers, on_refresh, cols=None, rows=None, positions=None, window=None):
		self.on_refresh = on_refresh
		self.positions = positions
		self.window = window
		self.use_mode = False
		self.usable = False
		self.pick_up = True
		self.shown = True
		self.events = None          # the LegacySlotEvents bound to it
		self._events = dict.fromkeys(_EVENT_NAMES)
		self._arrange(slot_numbers, cols, rows)

	def _arrange(self, slot_numbers, cols, rows):
		self.slot_numbers = [int(n) for n in slot_numbers]
		self.cols = cols
		self.rows = rows
		self._index = dict((n, i) for i, n in enumerate(self.slot_numbers))
		self._slots = {}
		self._owners = {}
		self._cells = [empty_cell(i) for i in range(len(self.slot_numbers))]

	def _record(self, slot):
		record = self._slots.get(slot)
		if record is None:
			record = self._slots[slot] = {"kind": "", "vnum": 0, "count": "", "icon": "", "w": 1, "h": 1,
			                              "active": False, "locked": False, "disabled": False, "cd": (0.0, 0.0),
			                              "cover_art": "", "unavailable": False, "always_cover": False}
		return record

	def _holds(self, slot):
		return int(slot) in self._index

	def _clear(self, record):
		record.update({"kind": "", "vnum": 0, "count": "", "icon": "", "w": 1, "h": 1, "active": False,
		               "locked": False, "disabled": False, "cd": (0.0, 0.0)})

	# --- what legacy calls -----------------------------------------------------------

	def SetItemSlot(self, slot, vnum, count=0, color=None):
		"""Legacy's SetItemSlot: vnum 0 clears the slot; the count shows when
		it is above 0 (CSlotWindow::SetSlotCount), so the legacy windows pass
		0 for a single item. The same vnum again keeps the active state."""
		if not self._holds(slot):
			return
		if not vnum:
			self.ClearSlot(slot)
			return
		record = self._record(int(slot))
		same = record["kind"] == "item" and record["vnum"] == vnum
		item.SelectItem(vnum)
		icon = item.GetIconImageFileName()
		width, height = item.GetItemSize()
		record.update({"kind": "item", "vnum": int(vnum), "icon": icon_source(icon) if icon and _exists(icon) else "",
		               "w": int(width), "h": int(height), "locked": False, "disabled": False,
		               "count": str(int(count)) if count and int(count) > 0 else ""})
		if not same:
			record.update({"active": False, "cd": (0.0, 0.0)})

	def SetSkillSlotNew(self, slot, skill_index, grade, level):
		if not self._holds(slot):
			return
		get_icon = getattr(skill, "GetIconImageFileNameNew", None)
		icon = get_icon(skill_index, grade) if get_icon is not None else ""
		if not icon:
			self.ClearSlot(slot)
			return
		record = self._record(int(slot))
		record.update({"kind": "skill", "vnum": int(skill_index), "icon": icon_source(icon), "w": 1, "h": 1,
		               "locked": False, "disabled": False})

	def SetEmotionSlot(self, slot, emotion_index):
		if not self._holds(slot):
			return
		get_icon = getattr(player, "GetEmotionIconFileName", None)
		icon = get_icon(emotion_index) if get_icon is not None else ""
		record = self._record(int(slot))
		record.update({"kind": "emotion", "vnum": int(emotion_index), "icon": icon_source(icon), "w": 1, "h": 1,
		               "locked": False, "disabled": False})

	def SetSlotCount(self, slot, count):
		if self._holds(slot):
			self._record(int(slot))["count"] = str(int(count)) if count and int(count) > 0 else ""

	def SetSlotCountNew(self, slot, grade, level):
		if self._holds(slot):
			self._record(int(slot))["count"] = count_label(grade, level)

	def SetSlotCoolTime(self, slot, cool_time, elapsed=0.0):
		if self._holds(slot):
			self._record(int(slot))["cd"] = cooldown_span(cool_time, elapsed)

	def ClearSlotCoolTime(self, slot):
		if self._holds(slot):
			self._record(int(slot))["cd"] = (0.0, 0.0)

	def ClearSlot(self, slot):
		if self._holds(slot):
			self._clear(self._record(int(slot)))

	def ClearAllSlot(self):
		for record in self._slots.values():
			self._clear(record)

	def ActivateSlot(self, slot):
		if self._holds(slot):
			self._record(int(slot))["active"] = True

	def DeactivateSlot(self, slot):
		if self._holds(slot):
			self._record(int(slot))["active"] = False

	def SetUseMode(self, flag):
		self.use_mode = bool(flag)

	def SetUsableItem(self, flag):
		self.usable = bool(flag)

	def SetCoverButton(self, slot, up=_DEFAULT_COVER, over="", down="", disable="", left=False, right=True):
		"""The cover art: the skill and emotion cover (slot_cover_button_*)
		draws as the cell's cover part; other art (the belt's, which does not
		exist, P14 spec 2.1) draws none."""
		if self._holds(slot):
			self._record(int(slot))["cover_art"] = str(up or "")

	def EnableCoverButton(self, slot):
		if self._holds(slot):
			self._record(int(slot))["unavailable"] = False

	def DisableCoverButton(self, slot):
		if self._holds(slot):
			self._record(int(slot))["unavailable"] = True

	def SetAlwaysRenderCoverButton(self, slot, flag=True):
		if self._holds(slot):
			self._record(int(slot))["always_cover"] = bool(flag)

	def LockSlot(self, slot):
		if self._holds(slot):
			self._record(int(slot))["locked"] = True

	def UnlockSlot(self, slot):
		if self._holds(slot):
			self._record(int(slot))["locked"] = False

	def EnableSlot(self, slot):
		if self._holds(slot):
			self._record(int(slot))["disabled"] = False

	def DisableSlot(self, slot):
		if self._holds(slot):
			self._record(int(slot))["disabled"] = True

	def SetSlotStyle(self, style):
		"""wndMgr.SLOT_STYLE_PICK_UP draws the drop footprint; any other style
		draws none."""
		self.pick_up = style == _pick_up_style()

	def ArrangeSlot(self, start, cols, rows, w=32, h=32, xstep=0, ystep=0):
		"""A grid of cols x rows slots numbered from `start` (select item sets
		its rows this way); the slots are made again, empty."""
		self._arrange(range(int(start), int(start) + int(cols) * int(rows)), int(cols), int(rows))

	def AppendSlot(self, slot, x=0, y=0, w=32, h=32):
		if self._holds(slot):
			return
		self.slot_numbers.append(int(slot))
		self._index[int(slot)] = len(self.slot_numbers) - 1
		self._cells.append(empty_cell(len(self.slot_numbers) - 1))

	def SetSlotBaseImage(self, path, r=1.0, g=1.0, b=1.0, a=1.0):
		"""Nothing: the skin draws the cells' base."""

	def RefreshSlot(self):
		"""Builds the cells from what legacy set, hands them to on_refresh, and
		shows the hovered cell's tooltip again (CSlotWindow::RefreshSlot)."""
		self._cells = self._build()
		if self.on_refresh is not None:
			self.on_refresh(self.cells())
		if self.events is not None:
			self.events.refresh_hover()

	def GetSlotCount(self):
		return len(self.slot_numbers)

	def HasSlot(self, slot):
		return self._holds(slot)

	def GetStartIndex(self):
		return self.slot_numbers[0] if self.cols is not None and self.slot_numbers else 0

	def Show(self):
		self.shown = True

	def Hide(self):
		self.shown = False

	def IsShow(self):
		return self.shown

	def __set_event(name):
		def set_event(self, event):
			self._events[name] = event
		set_event.__name__ = "Set%sEvent" % name.title().replace("_", "")
		return set_event

	SetSelectEmptySlotEvent = __set_event("select_empty")
	SetSelectItemSlotEvent = __set_event("select_item")
	SetUnselectEmptySlotEvent = __set_event("unselect_empty")
	SetUnselectItemSlotEvent = __set_event("unselect_item")
	SetUseSlotEvent = __set_event("use")
	SetOverInItemEvent = __set_event("over_in")
	SetOverOutItemEvent = __set_event("over_out")
	SetPressedSlotButtonEvent = __set_event("pressed_button")
	del __set_event

	def SAFE_SetButtonEvent(self, button, state, event):
		"""As ui.SlotWindow.SAFE_SetButtonEvent: LEFT or RIGHT, EMPTY, EXIST or
		ALWAYS, the event held as a ui.__mem_func__."""
		event = _mem_func(event)
		names = {"LEFT": ("select_empty", "select_item"), "RIGHT": ("unselect_empty", "unselect_item")}.get(button)
		if names is None:
			return
		if state in ("EMPTY", "ALWAYS"):
			self._events[names[0]] = event
		if state in ("EXIST", "ALWAYS"):
			self._events[names[1]] = event

	# --- what the NovaUI window calls -----------------------------------------------

	def _position(self, slot):
		if self.positions is None:
			return slot
		return self.positions(slot)

	def _slot_type(self):
		dragon_soul = getattr(player, "DRAGON_SOUL_INVENTORY", None)
		if self.window is not None and self.window == dragon_soul:
			return getattr(player, "SLOT_TYPE_DRAGON_SOUL_INVENTORY", player.SLOT_TYPE_INVENTORY)
		return player.SLOT_TYPE_INVENTORY

	def _build(self):
		cells = []
		for index, slot in enumerate(self.slot_numbers):
			cell = empty_cell(index)
			record = self._slots.get(slot)
			if record is not None:
				kind = record["kind"]
				if kind:
					cell.update({"kind": kind, "icon": record["icon"], "count": record["count"],
					             "w": record["w"], "h": record["h"], "active": record["active"],
					             "locked": record["locked"], "disabled": record["disabled"]})
					cell["cd_start"], cell["cd_end"] = record["cd"]
					if kind == "item":
						cell["type"] = self._slot_type()
						cell["ref"] = int(self._position(slot))
					else:
						cell["type"] = player.SLOT_TYPE_SKILL if kind == "skill" else player.SLOT_TYPE_EMOTION
						cell["ref"] = int(slot)
				shows_cover = bool(kind) or record["always_cover"]
				cell["cover"] = shows_cover and "slot_cover_button" in record["cover_art"].lower()
				cell["unavailable"] = shows_cover and record["unavailable"]
			cells.append(cell)
		self._owners = mark_covered(cells, self.cols, self.rows) if self.cols is not None else {}
		return cells

	def cells(self):
		"""The cells of the last RefreshSlot (copies)."""
		return [dict(cell) for cell in self._cells]

	def handlers(self):
		"""The legacy events bound to the window, by name."""
		return dict(self._events)

	def slot_number(self, index):
		return self.slot_numbers[index]

	def index_of(self, slot):
		"""The cell index of a legacy slot number, or None."""
		return self._index.get(int(slot))

	def owner(self, index):
		"""The anchor index of the item that covers cell `index` (the cell
		itself otherwise)."""
		return self._owners.get(index, index)

	def is_item(self, index):
		return 0 <= index < len(self._cells) and _is_item(self._cells[index])

	def is_locked(self, index):
		return 0 <= index < len(self._cells) and bool(self._cells[index].get("locked"))

	def vnums(self):
		"""{anchor index: vnum} of the item cells (CGridSlotWindow's dwItemIndex)."""
		found = {}
		for index, slot in enumerate(self.slot_numbers):
			record = self._slots.get(slot)
			if record is not None and record["kind"] == "item":
				found[index] = record["vnum"]
		return found


# The LegacySlotEvents that show footprint states now; the end of an attach
# clears them (watch_attach).
_with_states = set()


def _end_of_attach():
	for events in list(_with_states):
		events.clear_states()


def watch_attach():
	"""Has the end of the current attach clear every NovaUI grid's footprint
	states: shadows DeattachObject on the controller instance once, as
	attach() does, calling what was there (the class method, or attach()'s
	own shadow) and then clearing. True when something is attached."""
	controller = mouseModule.mouseController
	if not controller.isAttached():
		return False
	current = controller.__dict__.get("DeattachObject")
	if getattr(current, "_nui_watch", False):
		return True

	def deattach():
		if current is None:
			controller.__dict__.pop("DeattachObject", None)
		else:
			controller.DeattachObject = current
		try:
			if current is not None:
				current()
			else:
				type(controller).DeattachObject(controller)
		finally:
			_end_of_attach()

	deattach._nui_watch = True
	controller.DeattachObject = deattach
	return True


class LegacySlotEvents(object):
	"""The cell events of one NovaUI grid (or group of single slots), turned
	into the events legacy's C++ slot window sends its Python handlers, with
	CSlotWindow's and CGridSlotWindow's rules (P14 spec 6.0, D2):

	- press(index, 0): the select-item event of the cell's item (a cell an
	  item covers stands for its anchor; a locked item counts as empty), else
	  the select-empty event; while something is attached in a grid, the cell
	  CGridSlotWindow's drop target answers (drop_target). A press that
	  attached something is remembered, as SlotDrag's press is.
	- release(index, 0): after a press on another cell of any NovaUI grid
	  and a drag of 10 px or more (wndMgr.IsDragging), the same on the
	  release cell (no lock check, as OnMouseLeftButtonUp).
	- drop(index) (nuidrop: a legacy press released here): the same.
	- press(index, 1) with nothing attached: the unselect-item or
	  unselect-empty event; with something attached nothing (the host
	  cancelled the attach and kept the press).
	- use(index) (dblclick): the use event of an item.
	- over(index), out(index): the over-in event once per item, the over-out
	  event once, as CSlotWindow keeps m_dwToolTipSlotNumber; and while
	  something is attached, the drop footprint's states, handed to
	  on_states(states, picked) (footprint_states; a single slot: "move" on
	  the hovered cell).

	The proxy's RefreshSlot calls refresh_hover(): the hovered item's over-in
	again, as CSlotWindow::RefreshSlot does."""

	def __init__(self, proxy, owner_of=None, on_states=None):
		self.proxy = proxy
		proxy.events = self
		self.owner_of = owner_of
		self.on_states = on_states
		self.hovered = None
		self.tooltip = None
		self.states = {}
		self.picked = -1

	def _grid(self):
		return self.proxy.cols is not None

	def _owner(self, index):
		if self.owner_of is not None:
			return self.owner_of(index)
		return self.proxy.owner(index)

	def _target(self, index):
		if not (0 <= index < len(self.proxy.slot_numbers)):
			return None
		if self._grid() and attached():
			proxy = self.proxy
			return drop_target(proxy.cells(), index, attached_info(), proxy.cols, proxy.rows, proxy.use_mode,
			                   proxy.slot_numbers)
		return self._owner(index)

	def _call(self, name, *args):
		event = self.proxy._events.get(name)
		if event:
			event(*args)

	def _select(self, index, check_lock):
		target = self._target(index)
		if target is None:
			return
		number = self.proxy.slot_number(target)
		if self.proxy.is_item(target) and not (check_lock and self.proxy.is_locked(target)):
			self._call("select_item", number)
			if attached():
				self._over_out()
		else:
			self._call("select_empty", number)

	def _over_out(self):
		if self.tooltip is None:
			return
		self.tooltip = None
		self._call("over_out")

	def press(self, index, button):
		global _press
		self.hovered = index
		if button == 0:
			_press = None
			before = attached()
			self._select(index, True)
			if not before and attached():
				_press = (self, index)
				watch_attach()
			self.refresh_states()
		elif button == 1:
			if attached():
				return
			target = self._owner(index)
			if target is None or not (0 <= target < len(self.proxy.slot_numbers)):
				return
			number = self.proxy.slot_number(target)
			self._call("unselect_item" if self.proxy.is_item(target) else "unselect_empty", number)

	def release(self, index, button):
		global _press
		if button != 0:
			return
		self.hovered = index
		pressed, _press = _press, None
		if pressed is None or (pressed[0] is self and pressed[1] == index):
			return
		if attached() and _dragging():
			self._select(index, False)
			self.refresh_states()

	def drop(self, index):
		self.hovered = index
		if attached():
			self._select(index, False)
			self.refresh_states()

	def use(self, index):
		target = self._target(index)
		if target is not None and self.proxy.is_item(target):
			self._call("use", self.proxy.slot_number(target))

	def over(self, index):
		self.hovered = index
		self._over_in(index)
		self.refresh_states()

	def _over_in(self, index):
		target = self._target(index)
		if target is not None and self.proxy.is_item(target):
			number = self.proxy.slot_number(target)
			if self.tooltip != number:
				self.tooltip = number
				self._call("over_in", number)
		else:
			self._over_out()

	def out(self, index):
		if self.hovered == index:
			self.hovered = None
		self._over_out()
		self.clear_states()

	def refresh_hover(self):
		if self.hovered is None:
			return
		self._over_out()
		self._over_in(self.hovered)
		self.refresh_states()

	def _picked_index(self):
		info = attached_info()
		if info is None:
			return -1
		slot_type, slot_number = info[0], info[1]
		for index, cell in enumerate(self.proxy._cells):
			if _is_item(cell) and cell.get("type") == slot_type and cell.get("ref") == slot_number:
				return index
		return -1

	def refresh_states(self):
		"""The footprint's states over the hovered cell while something is
		attached ({} otherwise), handed to on_states when they changed."""
		index = self.hovered
		if index is None or not attached():
			self._set_states({}, -1)
			return
		proxy = self.proxy
		if self._grid():
			states = footprint_states(proxy.cells(), index, attached_info(), proxy.cols, proxy.rows, proxy.use_mode,
			                          proxy.usable, proxy.pick_up, proxy.slot_numbers, proxy.vnums())
		else:
			states = {index: "move"} if proxy.pick_up else {}
		self._set_states(states, self._picked_index())

	def clear_states(self):
		self._set_states({}, -1 if not attached() else self._picked_index())

	def _set_states(self, states, picked):
		if states == self.states and picked == self.picked:
			return
		self.states = states
		self.picked = picked
		if states or picked >= 0:
			_with_states.add(self)
		else:
			_with_states.discard(self)
		if self.on_states is not None:
			self.on_states(dict(states), picked)
