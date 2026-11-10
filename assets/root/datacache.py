"""The client's persistent cache of the server's lookups.

The answers that depend only on the server's data are kept here, in memory
and on disk: the dungeon drops (uiTimerWindow.DUNGEON_DROP), the chest
contents (constInfo.CHESTS_PREVIEW) and the wiki pages (nui_wiki.ANSWERS).
The mob info board (constInfo.MONSTER_INFO_DATA) is not: its answer depends
on the player's level and map.

Every answer is keyed by the server's address and its data version
(GC::DATA_VERSION, sent at every login and again when a GM reload changes
it). The server computes the version over every table these answers come
from, so:
- a relog to the same data reads the answers from disk and asks nothing;
- a relog after the data changed finds no file for the new version and asks
  again (the files of the other versions of that server are deleted);
- a reload pushed while playing drops every answer at once, and the sets made
  by asked_set() (the "already asked" marks) are emptied with them.
Until a version is known (an older server, or before the packet) the answers
stay in memory only, and begin_session() (each new game phase) drops them.

The tables are dicts (Table): a consumer reads them as before, and a write
(table[key] = value) goes to the file at once. A table of rows that arrive one
packet at a time (the dungeon drops) takes append(key, row): its fold function
puts the row in memory, and the file keeps the row, so reading the file folds
the rows again. clear() and del empty memory only.

The files are config/datacache/<server>-<version as 16 hex digits>.dc: a
header line, then records, each eight hex digits of length and a marshal of
(op, table, key, value). A damaged record ends the reading and the file is
written again from what came before it. A file stays under MAX_FILE_BYTES:
when the next record would pass it, the oldest answers go (from memory too)
until the rest fills three quarters of the cap, and the file is written again
from memory; an answer larger than the cap stays in memory only. At most
MAX_SERVERS files are kept, the most recently used.

Only os and marshal are used: the client's embedded Python has no json."""

import marshal
import os

FOLDER = "config/datacache"
FORMAT = 1
MAGIC = b"NOVA-DATACACHE %d\n" % FORMAT
SUFFIX = ".dc"
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_SERVERS = 8

_tables = {}		# name -> Table
_pending = {}		# name -> [record] read from disk for a table not made yet
_sets = []			# the sets asked_set() made this session
_order = {}			# (table, key) -> bytes of its records, oldest answer first
_state = {"server": None, "version": None, "handle": None, "bytes": 0}


def disk_open(path, mode):
	"""The file on disk itself (the client's open() reads the asset store)."""
	import builtins
	return getattr(builtins, "old_open", open)(path, mode)


def server_key(server):
	"""A server address as a file name part: letters, digits, dot and hyphen."""
	text = "".join(c if (c.isalnum() and ord(c) < 128) or c in ".-" else "_" for c in str(server))
	return text[:64] or "_"


def file_name(server, version):
	return "%s-%016x%s" % (server_key(server), int(version) & 0xFFFFFFFFFFFFFFFF, SUFFIX)


def current():
	"""(server key, version) the answers are kept under, or (None, None)."""
	return (_state["server"], _state["version"])


class Table(dict):
	"""One kind of answer: a dict whose writes go to disk (module docstring)."""

	def __init__(self, name, fold=None):
		dict.__init__(self)
		self.name = name
		self.fold = fold
		self.rows = {}		# key -> [row] appended (fold tables)
		_tables[name] = self
		for record in _pending.pop(name, []):
			_apply(record)

	def __setitem__(self, key, value):
		dict.__setitem__(self, key, value)
		_write(("p", self.name, key, value))

	def append(self, key, row):
		self.fold(self, key, row)
		self.rows.setdefault(key, []).append(row)
		_write(("a", self.name, key, row))

	def clear(self):
		dict.clear(self)
		self.rows.clear()

	def __delitem__(self, key):
		dict.__delitem__(self, key)
		self.rows.pop(key, None)

	def forget(self, key):
		dict.pop(self, key, None)
		self.rows.pop(key, None)


def asked_set():
	"""A set emptied with the answers when the data version changes."""
	marks = set()
	_sets.append(marks)
	return marks


def begin_session():
	"""A new game phase: nothing is known about the server's data until its
	version arrives, so the answers of the last session leave memory."""
	_close()
	_state["server"] = None
	_state["version"] = None
	_state["bytes"] = 0
	_forget_all()
	del _sets[:]


def set_version(server, version):
	"""GC::DATA_VERSION: keep the answers of (server, version). Another pair
	than the current one drops what memory holds and reads that pair's file;
	the same pair again changes nothing. True when the pair changed."""
	key = server_key(server)
	version = int(version) & 0xFFFFFFFFFFFFFFFF
	if (key, version) == current():
		return False
	_close()
	_forget_all()
	for marks in _sets:
		marks.clear()
	_state["server"] = key
	_state["version"] = version
	_read()
	_prune()
	return True


# --- memory ---------------------------------------------------------------------------

def _forget_all():
	for table in _tables.values():
		table.clear()
	_pending.clear()
	_order.clear()


def _apply(record):
	op, name, key, value = record
	table = _tables.get(name)
	if table is None:
		_pending.setdefault(name, []).append(record)
		return
	if op == "p":
		dict.__setitem__(table, key, value)
	elif table.fold is not None:
		table.fold(table, key, value)
		table.rows.setdefault(key, []).append(value)


def _note(name, key, size, replace):
	"""Counts a record of (name, key) as the newest answer; a put replaces
	what the key held, a row adds to it."""
	slot = (name, key)
	held = 0 if replace else _order.get(slot, 0)
	_order.pop(slot, None)
	_order[slot] = held + size


def _live_records():
	"""Every answer memory holds, as the records that write it, oldest first."""
	out = []
	for (name, key) in list(_order):
		table = _tables.get(name)
		if table is None or key not in table:
			_order.pop((name, key), None)
			continue
		if table.fold is not None:
			for row in table.rows.get(key, []):
				out.append(((name, key), ("a", name, key, row)))
		else:
			out.append(((name, key), ("p", name, key, dict.__getitem__(table, key))))
	return out


def _evict_oldest():
	(name, key) = next(iter(_order))
	_order.pop((name, key))
	table = _tables.get(name)
	if table is not None:
		table.forget(key)


# --- disk -----------------------------------------------------------------------------

def _path():
	return os.path.join(FOLDER, "%s-%016x%s" % (_state["server"], _state["version"], SUFFIX))


def _encode(record):
	try:
		data = marshal.dumps(record)
	except ValueError:
		return None
	return b"%08x" % len(data) + data


def _close():
	handle = _state["handle"]
	_state["handle"] = None
	if handle is not None:
		try:
			handle.close()
		except (IOError, OSError):
			pass


def _open(mode):
	"""The current pair's file for appending ("ab") or new ("wb", with its
	header); None when it cannot be opened."""
	try:
		if not os.path.isdir(FOLDER):
			os.makedirs(FOLDER)
		handle = disk_open(_path(), mode)
		if mode == "wb":
			handle.write(MAGIC)
			_state["bytes"] = len(MAGIC)
		_state["handle"] = handle
		return handle
	except (IOError, OSError):
		_state["handle"] = None
		return None


def _write(record):
	"""Write-through of one record; memory only while no version is known."""
	data = _encode(record)
	if data is None:
		return
	op, name, key = record[0], record[1], record[2]
	_note(name, key, len(data), op == "p")
	if _state["version"] is None:
		return
	if len(MAGIC) + _order[(name, key)] > MAX_FILE_BYTES:
		# Larger than the cap: memory only, and the file drops its older copy.
		size = _order.pop((name, key))
		_rewrite()
		_order[(name, key)] = size
		return
	if _state["bytes"] + len(data) > MAX_FILE_BYTES:
		_compact()
		return
	handle = _state["handle"]
	if handle is None:
		handle = _open("ab" if _state["bytes"] else "wb")
		if handle is None:
			return
	try:
		handle.write(data)
		handle.flush()
		_state["bytes"] += len(data)
	except (IOError, OSError):
		_close()


def _compact():
	"""Evicts the oldest answers until the rest fills three quarters of the
	cap, then writes the file again from memory. The newest answer (the one
	being written) stays."""
	target = MAX_FILE_BYTES * 3 // 4
	total = len(MAGIC) + sum(_order.values())
	while len(_order) > 1 and total > target:
		total -= _order[next(iter(_order))]
		_evict_oldest()
	_rewrite()


def _rewrite():
	"""Writes the file again from memory, skipping what would pass the cap."""
	_close()
	handle = _open("wb")
	if handle is None:
		return
	total = len(MAGIC)
	try:
		for slot, record in _live_records():
			data = _encode(record)
			if data is None or total + len(data) > MAX_FILE_BYTES:
				continue
			handle.write(data)
			total += len(data)
		handle.flush()
	except (IOError, OSError):
		_close()
	_state["bytes"] = total


def _read():
	"""Reads the current pair's file into memory. A damaged record ends the
	reading, and the file is written again from what came before it."""
	_state["bytes"] = 0
	try:
		with disk_open(_path(), "rb") as handle:
			data = handle.read()
	except (IOError, OSError):
		return
	if not data.startswith(MAGIC):
		_rewrite()
		return
	at = len(MAGIC)
	damaged = False
	while at < len(data):
		try:
			size = int(data[at:at + 8], 16)
			if size <= 0 or at + 8 + size > len(data):
				raise ValueError("short record")
			record = marshal.loads(data[at + 8:at + 8 + size])
			op, name, key, value = record
			if op not in ("p", "a") or not isinstance(name, str):
				raise ValueError("unknown record")
			hash(key)
		except Exception:
			damaged = True
			break
		_apply(record)
		_note(name, key, 8 + size, op == "p")
		at += 8 + size
	_state["bytes"] = at
	if damaged or at > MAX_FILE_BYTES:
		_rewrite()
	else:
		try:
			os.utime(_path(), None)
		except (IOError, OSError):
			pass


def _prune():
	"""Deletes the other versions of this server, and the least recently used
	servers past MAX_SERVERS."""
	try:
		names = [n for n in os.listdir(FOLDER) if n.endswith(SUFFIX)]
	except (IOError, OSError):
		return
	mine = os.path.basename(_path())
	prefix = _state["server"] + "-"
	others = []
	for name in names:
		if name == mine:
			continue
		path = os.path.join(FOLDER, name)
		if name.startswith(prefix) and len(name) == len(mine):
			_remove(path)
			continue
		try:
			others.append((os.path.getmtime(path), name))
		except (IOError, OSError):
			pass
	others.sort()
	while len(others) > MAX_SERVERS - 1:
		_remove(os.path.join(FOLDER, others.pop(0)[1]))


def _remove(path):
	try:
		os.remove(path)
	except (IOError, OSError):
		pass
