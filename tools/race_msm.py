"""Read a race .msm (assets/root/msm/<race>.msm) the way NEW's client does.

The client loads the eight race files with chrmgr.LoadLocalRaceData
(assets/root/playersettingmodule.py), which runs CRaceData::LoadRaceData
(nova-client-src src/GameLib/RaceDataFile.cpp) over CTextFileLoader
(src/EterLib/TextFileLoader.cpp) and CMemoryTextFileLoader
(src/EterBase/FileLoader.cpp). This module repeats that reader rule for rule,
including its quirks, so a test can tell what a file gives the game:

- Lines break at CR or LF, and a CR or LF right after a break is part of
  it (CR LF is one break; so is LF LF, which drops an empty line). A byte of
  0x80 or more takes the next byte with it, so an odd run of such bytes at
  the end of a line swallows the line break (the DBCS rule).
- Tokens split at spaces and tabs; a token starting with a quote runs to the
  next quote. A key is case-insensitive and keeps its first value in a group.
- A key line with no value inside a group, or a stray '}' at the top,
  fails the whole load.
- ``ShapeDataCount`` and ``HairDataCount`` bound the ``ShapeDataNN`` and
  ``HairDataNN`` children read (``%02u``; the first child of a name wins).
- ``SpecialPath`` replaces the path for that entry and every later one.
- An entry without its index (or a shape without Model and Local_Model) is
  skipped without leaving it, so every later entry and the hair after the
  shapes are lost: the reader's own ``continue`` before ``SetParentNode``.
- A shape takes Model, then Local_SourceSkin/Local_TargetSkin,
  SourceSkin/TargetSkin and SourceSkin2/TargetSkin2 as skins (appended, so a
  repeated index adds skins and its last Model wins). A hair needs Model,
  SourceSkin and TargetSkin together.

Keys the reader does not know (OLD's CommonTargetSkin*, SourceSkin3-8,
CustomSpecular*, CustomOpacity*, CustomSpecularMask*, SpecularMask,
SourceFace/TargetFace, FacialData, WingData) are kept as tokens and ignored.

As a script it merges OLD's race files into NEW's (``merge``) and writes the
table tools/race_msm_test.py checks (``build_fixture``):

	python3 tools/race_msm.py merge OLD_ROOT NEW_MSM_DIR OUT_DIR
	python3 tools/race_msm.py fixture PRE_CUT_ITEM_PROTO CUT_ITEM_PROTO NEW_MSM_DIR OLD_ROOT MERGED_DIR OUT_JSON

OLD_ROOT is old/client_pack/source/root, the item protos are int-rt's
share/conf/item_proto.txt at a6d52a5^ and at the cut, and NEW_MSM_DIR holds
NEW's race files from before the merge.
"""
import os
import sys

RACES = ("warrior_m", "assassin_w", "sura_m", "shaman_w", "warrior_w", "assassin_m", "sura_w", "shaman_m")
_DELIMS = b" \t"


def split_lines(data, starts=None):
	"""CMemoryTextFileLoader::Bind. ``starts``, when given, gets the byte
	offset each line starts at."""
	lines = []
	line = bytearray()
	pos, size = 0, len(data)
	start = 0
	while pos < size:
		c = data[pos]
		pos += 1
		if c in (10, 13):
			if pos < size and data[pos] in (10, 13):
				pos += 1
			lines.append(bytes(line))
			if starts is not None:
				starts.append(start)
			line = bytearray()
			start = pos
		elif c >= 0x80:
			line += data[pos - 1:pos + 1]
			pos += 1
		else:
			line.append(c)
	lines.append(bytes(line))
	if starts is not None:
		starts.append(start)
	return lines


def _first_not_of(line, start):
	for i in range(start, len(line)):
		if line[i] not in _DELIMS:
			return i
	return -1


def _first_of(line, chars, start):
	for i in range(start, len(line)):
		if line[i] in chars:
			return i
	return -1


def split_tokens(line):
	"""CMemoryTextFileLoader::SplitLine2: (0, tokens), (-1, []) for a blank
	line, (-2, []) for an open quote."""
	tokens = []
	base = 0
	while True:
		begin = _first_not_of(line, base)
		if begin < 0:
			return -1, []
		if line[begin] == 0x22:
			begin += 1
			end = _first_of(line, b'"', begin)
			if end < 0:
				return -2, []
			base = end + 1
		else:
			end = _first_of(line, _DELIMS, begin)
			base = end if end >= 0 else len(line)
		tokens.append(line[begin:end] if end >= 0 else line[begin:])
		if _first_not_of(line, base) < 0:
			break
		if base >= len(line):
			break
	return 0, tokens


class Node(object):
	"""A CTextFileLoader group: lowercased name, tokens (first value of a key
	wins) and children in file order. ``first`` and ``last`` are the line
	indexes of its ``Group`` line and closing brace, for the merge."""

	def __init__(self, name, parent=None, first=None):
		self.name = name
		self.parent = parent
		self.tokens = {}
		self.children = []
		self.first = first
		self.last = None

	def child(self, name):
		for node in self.children:
			if node.name == name:
				return node
		return None

	def string(self, key):
		values = self.tokens.get(key)
		if not values:
			return None
		return values[0].decode("latin-1")

	def integer(self, key):
		"""GetTokenDoubleWord: atoi of the first value as a DWORD."""
		text = self.string(key)
		if text is None:
			return None
		text = text.lstrip(" \t\n\v\f\r")
		sign = 1
		if text[:1] in ("+", "-"):
			sign = -1 if text[0] == "-" else 1
			text = text[1:]
		digits = ""
		for ch in text:
			if not ch.isdigit():
				break
			digits += ch
		return (sign * int(digits or "0")) & 0xFFFFFFFF


def parse(data, old_reader=False):
	"""CTextFileLoader::Load: (ok, global node, lines). ``old_reader`` splits
	lines as OLD's client does (storm::Tokenize at CR and LF, no DBCS rule)."""
	starts = []
	if old_reader:
		lines = [line for line in data.replace(b"\r", b"\n").split(b"\n") if line]
	else:
		lines = split_lines(data, starts)
	top = Node("global")
	state = {"index": 0}

	def load_group(node):
		depth = 0
		while state["index"] < len(lines):
			ret, tokens = split_tokens(lines[state["index"]])
			if ret != 0:
				state["index"] += 1
				continue
			head = tokens[0].lower()
			if head[:1] == b"{":
				depth += 1
				state["index"] += 1
				continue
			if head[:1] == b"}":
				depth -= 1
				node.last = state["index"]
				break
			if head == b"group":
				if len(tokens) != 2:
					state["index"] += 1
					continue
				sub = Node(tokens[1].lower().decode("latin-1"), node, state["index"])
				node.children.append(sub)
				state["index"] += 1
				if not load_group(sub):
					return False
			elif head == b"list":
				if len(tokens) != 2:
					state["index"] += 1
					continue
				key = tokens[1].lower().decode("latin-1")
				values = []
				state["index"] += 1
				while state["index"] < len(lines):
					ret, sub_tokens = split_tokens(lines[state["index"]])
					if ret == 0:
						if sub_tokens[0][:1] == b"}":
							break
						if sub_tokens[0][:1] != b"{":
							values.extend(sub_tokens)
					state["index"] += 1
				node.tokens.setdefault(key, values)
			else:
				if len(tokens) == 1:
					break
				node.tokens.setdefault(head.decode("latin-1"), tokens[1:])
			state["index"] += 1
		return depth == 0

	ok = load_group(top)
	top.starts = starts
	return ok, top, lines


class RaceData(object):
	"""What CRaceData holds after LoadRaceData: shapes and hairs by index,
	each a model path and a list of (source, target) skins."""

	def __init__(self):
		self.loaded = False
		self.base_model = None
		self.shapes = {}
		self.hairs = {}
		# (kind, index) -> the entry nodes and the paths they were read with,
		# and per kind every entry read, in the reader's order: for the merge.
		self.entries = {}
		self.order = {"shapedata": [], "hairdata": []}


def _common_skins(entry, count):
	"""OLD's COMMON_PATH skins: SourceSkinN with CommonTargetSkinN, both
	without the path (N = 1 is written SourceSkin and CommonTargetSkin)."""
	skins = []
	for n in range(1, count + 1):
		suffix = "" if n == 1 else str(n)
		src, dst = entry.string("sourceskin" + suffix), entry.string("commontargetskin" + suffix)
		if src is not None and dst is not None:
			skins.append((src, dst))
	return skins


def _read_entries(race, node, kind, old_reader=False):
	"""The ShapeData or HairData block of LoadRaceData, from the node the
	reader is on. Returns the node it is left on: the parent of the group,
	or the group itself when an entry left it stuck."""
	group = node.child(kind)
	if group is None:
		return node
	cur = group
	path = group.string("pathname")
	count = group.integer(kind + "count")
	if path is None or count is None:
		return group.parent
	store = race.shapes if kind == "shapedata" else race.hairs
	for i in range(count):
		entry = cur.child("%s%02d" % (kind, i))
		if entry is None:
			continue
		cur = entry
		special = entry.string("specialpath")
		if special is not None:
			path = special
		index = entry.integer("shapeindex" if kind == "shapedata" else "hairindex")
		if index is None:
			continue
		if kind == "shapedata":
			model = entry.string("model")
			if model is not None:
				model = path + model
			else:
				model = entry.string("local_model")
				if model is None:
					continue
			item = store.setdefault(index, [None, []])
			item[0] = model
			local = (entry.string("local_sourceskin"), entry.string("local_targetskin"))
			if None not in local:
				item[1].append(local)
			for source, target in (("sourceskin", "targetskin"), ("sourceskin2", "targetskin2")):
				src, dst = entry.string(source), entry.string(target)
				if src is not None and dst is not None:
					item[1].append((path + src, path + dst))
			if old_reader:
				item[1].extend(_common_skins(entry, 8))
				src, dst = entry.string("sourceface"), entry.string("targetface")
				if src is not None and dst is not None:
					item[1].append((path + src, path + dst))
		elif old_reader:
			# OLD's hair: the model alone registers it (SetHairSource), and
			# each skin pair, its own and the common ones, is added.
			item = store.setdefault(index, [None, []])
			model = entry.string("model")
			if model is not None:
				item[0] = path + model
			for source, target in (("sourceskin", "targetskin"), ("sourceskin2", "targetskin2")):
				src, dst = entry.string(source), entry.string(target)
				if src is not None and dst is not None:
					item[1].append((path + src, path + dst))
			item[1].extend(_common_skins(entry, 5))
		else:
			model, src, dst = entry.string("model"), entry.string("sourceskin"), entry.string("targetskin")
			if model is not None and src is not None and dst is not None:
				item = store.setdefault(index, [None, []])
				item[0] = path + model
				item[1].append((path + src, path + dst))
		race.entries.setdefault((kind, index), []).append((entry, path))
		race.order[kind].append((index, entry, path))
		cur = entry.parent
	return cur.parent if cur.parent is not None else cur


def load(data, old_reader=False):
	"""CRaceData::LoadRaceData over the bytes of a race file; with
	``old_reader``, OLD's (old/client_source GameLib/RaceDataFile.cpp), which
	also reads the COMMON_PATH skins and SourceFace/TargetFace and registers
	a hair by its model alone."""
	race = RaceData()
	ok, top, lines = parse(data, old_reader)
	race.lines = lines
	race.top = top
	if not ok:
		return race
	race.loaded = True
	race.base_model = top.string("basemodelfilename")
	cur = _read_entries(race, top, "shapedata", old_reader)
	_read_entries(race, cur, "hairdata", old_reader)
	return race


def load_file(path, old_reader=False):
	with open(path, "rb") as handle:
		return load(handle.read(), old_reader)


def norm(path):
	"""The resource manager's view of a path: case and slashes do not count."""
	return path.replace("\\", "/").lower() if path is not None else None


def look(item):
	"""A shape or hair as the files it shows: (model, ((source, target), ...)).
	A skin given twice is listed once: the second SetMaterialImagePointer of
	the same pair changes nothing."""
	if item is None:
		return None
	skins = []
	for src, dst in item[1]:
		pair = (norm(src), norm(dst))
		if pair not in skins:
			skins.append(pair)
	return (norm(item[0]), tuple(skins))


# The item rows whose value3 is a race file index: CInstanceBase::SetArmor
# looks an armour or costume body's value3 up as a shape, and the server
# sends a costume hair's value3 as the hair (game/item.cpp).
ITEM_KINDS = {
	("ITEM_ARMOR", "ARMOR_BODY"): "shapedata",
	("ITEM_COSTUME", "COSTUME_BODY"): "shapedata",
	("ITEM_COSTUME", "COSTUME_HAIR"): "hairdata",
}
_JOB_FLAGS = {"warrior": "ANTI_MUSA", "assassin": "ANTI_ASSASSIN", "sura": "ANTI_SURA", "shaman": "ANTI_MUDANG"}
_SEX_FLAGS = {"m": "ANTI_MALE", "w": "ANTI_FEMALE"}


def read_item_proto(text):
	"""The body and hair rows of an item_proto.txt: {vnum: (kind, value3,
	races that can wear it)}. Rows split only at LF (OLD's names hold a
	0x1C byte)."""
	rows = text.split("\n")
	header = rows[0].rstrip("\r").split("\t")
	value3 = header.index("VALUE3")
	items = {}
	for row in rows[1:]:
		cells = row.rstrip("\r").split("\t")
		if len(cells) <= value3 or "~" in cells[0]:
			continue
		kind = ITEM_KINDS.get((cells[2], cells[3]))
		if kind is None:
			continue
		flags = set(flag.strip() for flag in cells[5].split("|"))
		races = tuple(race for race in RACES
			if _JOB_FLAGS[race.split("_")[0]] not in flags and _SEX_FLAGS[race.split("_")[1]] not in flags)
		items[int(cells[0])] = (kind, int(cells[value3]), races)
	return items


def resolve(race, kind, index):
	"""The look an item of ``kind`` with this value3 gets from a loaded race."""
	return look((race.shapes if kind == "shapedata" else race.hairs).get(index))


# Indexes both files have where the merge keeps NEW's entry, with the reason.
# Every other index OLD has takes OLD's entries: the cut's item_proto carries
# OLD's value3, so OLD's entry is the look OLD's item had.
KEEP_NEW = {
	("warrior_w", "shapedata", 40062): "OLD's Salsa Dress names its LOD 3 model (warrior_salsa1_lod_03.GR2) as "
		"the body, where OLD's other seven races and NEW name the full model",
}


def clean_old(data):
	"""OLD's female files have twelve HairIndex lines whose comment is
	mojibake (U+FFFD runs). NEW's DBCS rule pairs those bytes, so the comment
	goes: the value before it stays as it was."""
	out = []
	for line in data.split(b"\n"):
		if any(b >= 0x80 for b in line):
			cut = line.find(b"#")
			if cut < 0:
				raise ValueError("a line with bytes of 0x80 or more outside a comment: %r" % line)
			line = line[:cut].rstrip(b" \t")
		out.append(line)
	return b"\n".join(out)


def _raw(data, top, lines, node):
	"""The bytes of a group from its Group line to its closing brace."""
	starts = top.starts
	return data[starts[node.first]:starts[node.last] + len(lines[node.last])]


def _entry_text(raw, name, path, current):
	"""An entry renamed to ``name``; a SpecialPath line goes in when the path
	the reader would carry into it (``current``) is not the one it was read
	with, so the entry reads the same wherever it stands."""
	rows = raw.split(b"\n")
	head = rows[0]
	indent = head[:len(head) - len(head.lstrip(b" \t"))]
	rows[0] = indent + b"Group " + name.encode("ascii")
	_, node, _ = parse(raw)
	entry = node.children[0]
	if entry.string("specialpath") is None and path != current:
		for i, row in enumerate(rows):
			if row.strip().startswith(b"{"):
				rows.insert(i + 1, indent + b"\tSpecialPath\t\t\t\"" + path.encode("latin-1") + b"\"")
				break
	return b"\n".join(rows)


def merge(race_name, old_data, new_data, keep_new=None):
	"""OLD's race file with NEW's entries for the indexes OLD lacks.

	OLD's ShapeData and HairData entries come first, in the order OLD's
	reader reads them (an entry it never reads, such as a misnamed group, is
	left out), then NEW's entries for the indexes OLD has no entry for and
	those ``keep_new`` names. Entries are renumbered from 00 and each count
	is the number of entries. OLD's FacialData and WingData stay as they are
	(NEW reads neither); AttachingData is NEW's (OLD's adds two copies of
	the first body sphere). Returns (bytes, report)."""
	keep_new = KEEP_NEW if keep_new is None else keep_new
	old_data = clean_old(old_data)
	old = load(old_data)
	new = load(new_data)
	if not old.loaded or not new.loaded:
		raise ValueError("%s: a source file does not load" % race_name)
	if norm(old.base_model) != norm(new.base_model):
		raise ValueError("%s: the base models differ" % race_name)
	report = {"old": {}, "new": {}, "kept_new": [], "dropped": {}}
	out = [b"ScriptType            RaceDataScript", b"",
		b"BaseModelFileName     \"" + old.base_model.encode("latin-1") + b"\"", b""]
	for kind, title in (("hairdata", b"HairData"), ("shapedata", b"ShapeData")):
		old_group, new_group = old.top.child(kind), new.top.child(kind)
		path = old_group.string("pathname")
		if path != new_group.string("pathname"):
			raise ValueError("%s: the %s paths differ" % (race_name, kind))
		old_indexes = set(index for index, _, _ in old.order[kind])
		chosen = []
		for index, entry, entry_path in old.order[kind]:
			if (race_name, kind, index) not in keep_new:
				chosen.append((old_data, old, entry, entry_path))
		for index, entry, entry_path in new.order[kind]:
			if index not in old_indexes or (race_name, kind, index) in keep_new:
				chosen.append((new_data, new, entry, entry_path))
				if index in old_indexes:
					report["kept_new"].append((kind, index))
		report["old"][kind] = sum(1 for c in chosen if c[1] is old)
		report["new"][kind] = sum(1 for c in chosen if c[1] is new)
		report["dropped"][kind] = len(old_group.children) - len(old.order[kind])
		out += [b"Group " + title, b"{", b"\tPathName\t\"" + path.encode("latin-1") + b"\"", b"",
			b"\t" + title + b"Count\t\t\t" + str(len(chosen)).encode("ascii")]
		current = path
		for number, (data, race, entry, entry_path) in enumerate(chosen):
			raw = _raw(data, race.top, race.lines, entry)
			out.append(_entry_text(raw, "%s%02d" % (title.decode("ascii"), number), entry_path, current))
			current = entry_path
		out += [b"}", b""]
	for kind in ("facialdata", "wingdata"):
		node = old.top.child(kind)
		if node is not None:
			out += [_raw(old_data, old.top, old.lines, node), b""]
	node = new.top.child("attachingdata")
	out += [_raw(new_data, new.top, new.lines, node), b""]
	return b"\n".join(out), report


# Why a pre-cut item's look changes with the merged files: (race, kind,
# index after the cut) -> reason. build_fixture refuses a change not listed.
LOOK_CHANGES = {}
for _index in (3, 4, 5):
	LOOK_CHANGES[("sura_w", "shapedata", _index)] = (
		"OLD's entry adds SourceSkin2/TargetSkin2 sura_jinhon_cloak.dds onto itself; the female model names "
		"that texture already, so it looks the same")
LOOK_CHANGES[("assassin_w", "shapedata", 40061)] = (
	"both entries name a target skin with an extension the resource manager does not load (NEW "
	"assassin_tailcoat1.ddsS, OLD .ddds), so neither applies and the model keeps its own texture")
for _race in ("assassin_w", "sura_w", "shaman_w"):
	for _index in (151, 152, 153, 154, 171, 172, 173, 174):
		LOOK_CHANGES[(_race, "hairdata", _index)] = (
			"NEW's file gave this race's TUR, GER, BRA and Olympic hairs one another's colours; NEW's "
			"warrior_w and OLD's four female files give hair 15N and 17N the texture hair_15_N and "
			"hair_17_N (TUR 1, GER 2, BRA 3, Olympic 4), which OLD's value3 and entry restore")

PREFIX = "d:/ymir work/"
SHORT = {"shapedata": "shape", "hairdata": "hair"}


def look_json(item):
	"""A look as the fixture writes it, without the d:/ymir work/ every path
	starts with."""
	def cut(path):
		return path[len(PREFIX):] if path.startswith(PREFIX) else path
	return None if item is None else [cut(item[0]), [[cut(src), cut(dst)] for src, dst in item[1]]]


def old_digest(looks):
	"""One digest over {"shape:N" or "hair:N": look_json} for a race."""
	import hashlib
	import json
	text = json.dumps(sorted(looks.items()), separators=(",", ":"))
	return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def build_fixture(pre_items, cut_items, new_races, old_races, merged_races):
	"""The table tools/race_msm_test.py checks the race files against.

	``items``: every body and hair row of the cut's item_proto as [vnum,
	"shape" or "hair", value3, races that can wear it as a bit mask in RACES
	order, and for a pre-cut item its pre-cut value3 and races, else null and
	0]. ``before``: what each pre-cut item showed before the cut, by race and
	NEW's index (NEW's race files with NEW's pre-cut item_proto); an index
	that showed nothing is left out. ``changes``: the pre-cut items that look
	otherwise with the merged files, each with its LOOK_CHANGES reason.
	``old``: per race, the indexes OLD-only items use that OLD's file has,
	and a digest of what NEW's reader makes of OLD's entries for them.
	``old_only``: how many OLD-only items and item-race pairs NEW's reader
	shows (and how many such items there are)."""
	items, before, changes = [], {}, []
	old = dict((race, {"shape": set(), "hair": set(), "looks": {}}) for race in RACES)
	vnums, shown_vnums, pairs, shown_pairs = 0, 0, 0, 0
	for vnum in sorted(cut_items):
		kind, value3, races = cut_items[vnum]
		pre = pre_items.get(vnum)
		mask = sum(1 << RACES.index(race) for race in races)
		pre_mask = 0 if pre is None or pre[0] != kind else sum(1 << RACES.index(race) for race in pre[2])
		items.append([vnum, SHORT[kind], value3, mask, None if pre is None else pre[1], pre_mask])
		if pre is None:
			vnums += 1
			shows = False
			for race in races:
				pairs += 1
				now = resolve(merged_races[race], kind, value3)
				if now is not None:
					shown_pairs += 1
					shows = True
				if (kind, value3) in old_races[race].entries:
					old[race][SHORT[kind]].add(value3)
					old[race]["looks"]["%s:%d" % (SHORT[kind], value3)] = look_json(resolve(old_races[race], kind, value3))
			shown_vnums += shows
			continue
		for race in races:
			if race not in pre[2] or pre[0] != kind:
				continue
			was = resolve(new_races[race], kind, pre[1])
			if was is None:
				continue
			before.setdefault(race, {})["%s:%d" % (SHORT[kind], pre[1])] = look_json(was)
			now = resolve(merged_races[race], kind, value3)
			if now != was:
				why = LOOK_CHANGES.get((race, kind, value3))
				if why is None:
					raise ValueError("%d on %s changes look with no reason given" % (vnum, race))
				changes.append([vnum, race, look_json(now), why])
	for race in RACES:
		looks = old[race].pop("looks")
		old[race]["digest"] = old_digest(looks)
		old[race]["shape"] = sorted(old[race]["shape"])
		old[race]["hair"] = sorted(old[race]["hair"])
	return {
		"about": "Generated by tools/race_msm.py fixture from int-rt's item_proto.txt at a6d52a5^ (pre-cut) "
			"and at the cut, NEW's race files before the merge and OLD's eight (old/client_pack/source/root).",
		"races": list(RACES),
		"items": items,
		"before": before,
		"changes": changes,
		"old": old,
		"old_only": {"vnums": vnums, "vnums_shown": shown_vnums, "pairs": pairs, "pairs_shown": shown_pairs},
	}


def dump_fixture(fixture):
	"""JSON with one item, look or change per line, so a diff reads."""
	import json

	def one(value):
		return json.dumps(value, separators=(",", ":"), sort_keys=True)

	def block(rows, indent):
		pad = "\t" * indent
		return "[\n" + ",\n".join(pad + one(row) for row in rows) + "\n" + "\t" * (indent - 1) + "]"

	def table(mapping, indent):
		pad = "\t" * indent
		return "{\n" + ",\n".join(pad + json.dumps(key) + ":" + one(mapping[key]) for key in sorted(mapping)) + \
			"\n" + "\t" * (indent - 1) + "}"

	parts = [
		'\t"about":' + json.dumps(fixture["about"]),
		'\t"races":' + one(fixture["races"]),
		'\t"items":' + block(fixture["items"], 2),
		'\t"before":{\n' + ",\n".join('\t\t%s:%s' % (json.dumps(race), table(fixture["before"][race], 3))
			for race in sorted(fixture["before"])) + "\n\t}",
		'\t"changes":' + block(fixture["changes"], 2),
		'\t"old":' + table(fixture["old"], 2),
		'\t"old_only":' + one(fixture["old_only"]),
	]
	return "{\n" + ",\n".join(parts) + "\n}\n"


def _main(argv):
	if len(argv) >= 2 and argv[0] == "dump":
		race = load_file(argv[1])
		print("loaded", race.loaded, "shapes", len(race.shapes), "hairs", len(race.hairs))
		return 0
	if len(argv) == 4 and argv[0] == "merge":
		old_root, new_dir, out_dir = argv[1:]
		for name in RACES:
			with open(os.path.join(old_root, name + ".msm"), "rb") as handle:
				old_data = handle.read()
			with open(os.path.join(new_dir, name + ".msm"), "rb") as handle:
				new_data = handle.read()
			data, report = merge(name, old_data, new_data)
			with open(os.path.join(out_dir, name + ".msm"), "wb") as handle:
				handle.write(data)
			print(name, report)
		return 0
	if len(argv) == 7 and argv[0] == "fixture":
		import json
		pre_proto, cut_proto, new_dir, old_root, merged_dir, out = argv[1:]
		with open(pre_proto, encoding="utf-8", errors="replace") as handle:
			pre_items = read_item_proto(handle.read())
		with open(cut_proto, encoding="utf-8", errors="replace") as handle:
			cut_items = read_item_proto(handle.read())
		new_races = dict((name, load_file(os.path.join(new_dir, name + ".msm"))) for name in RACES)
		merged_races = dict((name, load_file(os.path.join(merged_dir, name + ".msm"))) for name in RACES)
		old_races = {}
		for name in RACES:
			with open(os.path.join(old_root, name + ".msm"), "rb") as handle:
				old_races[name] = load(clean_old(handle.read()))
		fixture = build_fixture(pre_items, cut_items, new_races, old_races, merged_races)
		with open(out, "w", encoding="utf-8") as handle:
			handle.write(dump_fixture(fixture))
		print("items", len(fixture["items"]), "changes", len(fixture["changes"]), "old_only", fixture["old_only"])
		return 0
	sys.stderr.write(__doc__)
	return 2


if __name__ == "__main__":
	sys.exit(_main(sys.argv[1:]))
