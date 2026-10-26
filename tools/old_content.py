"""OLD's client text for the items and mobs of the foundation cut (NOVA-98).

The cut's item_proto and mob_proto are OLD's, so the client needs OLD's
lines for the vnums NEW's text files lack. This module reads those files the
way NEW's client does and adds OLD's lines. It changes none of NEW's, except
the name of a mob the cut brings that NEW named for another model
(merge_npclist). Each file's test (tools/<file>_test.py) checks the result
against tools/fixtures/old_content.json.

	python3 tools/old_content.py item_list OLD_ITEM_LIST CUT_ITEM_PROTO
	python3 tools/old_content.py npclist OLD_NPCLIST_PY CUT_MOB_PROTO PRE_CUT_MOB_PROTO
	python3 tools/old_content.py itemdesc OLD_LOCALE_ROOT CUT_ITEM_PROTO

OLD_ITEM_LIST is old/client_pack/source/locale/common/item_list.txt and
CUT_ITEM_PROTO int-rt's share/conf/item_proto.txt; OLD_NPCLIST_PY is
old/client_pack/source/root/NpcList.py, CUT_MOB_PROTO int-rt's
share/conf/mob_proto.txt and PRE_CUT_MOB_PROTO the same file at a6d52a5^;
OLD_LOCALE_ROOT is old/client_pack/source/locale.
Each command rewrites its files (from NEW's own
lines, also on a second run) and sets the file's fixture entry.
"""
import hashlib
import json
import os
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ASSETS = os.path.join(REPO, "assets")
ITEM_LIST = os.path.join(ASSETS, "locale", "locale", "common", "item_list.txt")
FIXTURE = os.path.join(REPO, "tools", "fixtures", "old_content.json")


def split_tab(line):
	"""CMemoryTextFileLoader::SplitLine(line, "\\t") (src/EterBase/FileLoader.cpp):
	tokens between tab runs, a token starting with a quote running to the next
	quote; None for a blank line or an open quote."""
	tokens = []
	base, size = 0, len(line)
	while True:
		begin = base
		while begin < size and line[begin] == "\t":
			begin += 1
		if begin >= size:
			return tokens or None
		if line[begin] == '"':
			begin += 1
			end = line.find('"', begin)
			if end < 0:
				return None
			tokens.append(line[begin:end])
			base = end + 1
		else:
			end = line.find("\t", begin)
			end = size if end < 0 else end
			tokens.append(line[begin:end])
			base = end
		rest = base
		while rest < size and line[rest] == "\t":
			rest += 1
		if rest >= size:
			return tokens


def atoi(text):
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
	return sign * int(digits or "0")


def lines_of(data):
	"""A text file's lines as CMemoryTextFileLoader::Bind makes them for an
	ASCII file: a break is CR or LF, and the CR or LF right after it belongs
	to it."""
	text = data.decode("latin-1")
	lines, line, i = [], [], 0
	while i < len(text):
		ch = text[i]
		i += 1
		if ch in "\r\n":
			if i < len(text) and text[i] in "\r\n":
				i += 1
			lines.append("".join(line))
			line = []
		else:
			line.append(ch)
	lines.append("".join(line))
	return lines


def item_list_lines(data):
	"""CItemManager::LoadItemList (src/GameLib/ItemManager.cpp): {vnum: line}
	for the lines it takes (3 or 4 tab columns; a later line for a vnum
	replaces an earlier one) and the lines it logs as StrangeLine."""
	taken, strange = {}, []
	for line in lines_of(data):
		tokens = split_tab(line)
		if tokens is None:
			continue
		if len(tokens) not in (3, 4):
			strange.append(line)
			continue
		taken[atoi(tokens[0])] = line
	return taken, strange


def published_files():
	"""Every store path the client can open: the files of the groups in
	assets/groups.txt, named as AssetLib's PublishedName names them."""
	names = set()
	with open(os.path.join(ASSETS, "groups.txt"), encoding="utf-8") as handle:
		groups = [line.split("#")[0].strip() for line in handle]
	for group in filter(None, groups):
		top = os.path.join(ASSETS, group)
		for folder, _, files in os.walk(top):
			for name in files:
				relative = os.path.relpath(os.path.join(folder, name), top).replace("\\", "/").lower()
				if relative.startswith("ymir work/"):
					relative = "d:/" + relative
				names.add(relative)
	return names


def store_name(path):
	"""NormalizeLookupPath: slashes forward, ASCII lowercase."""
	return path.replace("\\", "/").lower()


def cut_item_vnums(text):
	"""The vnums of an item_proto.txt, its ranges (110000~110099) spread."""
	vnums = set()
	for row in text.split("\n")[1:]:
		cells = row.split("\t")
		if len(cells) < 3 or not cells[0].strip():
			continue
		if "~" in cells[0]:
			first, last = cells[0].split("~")
			vnums.update(range(int(first), int(last) + 1))
		else:
			vnums.add(int(cells[0]))
	return vnums


def old_item_line(line):
	"""OLD's line as NEW's loader takes it. OLD's loader reads a fifth column
	only on an AURA line (its aura and wing effects, ENABLE_AURA_SYSTEM) and
	then sets the icon alone, so that line keeps its first three columns;
	NEW has no aura part."""
	tokens = split_tab(line)
	if len(tokens) == 5:
		if tokens[1] != "AURA":
			raise ValueError("a five-column line that is not an aura: %r" % line)
		return "\t".join(tokens[:3])
	return line


def merge_item_list(new_data, old_data, cut_vnums, files):
	"""NEW's item_list with OLD's line appended for each vnum of the cut's
	item_proto that NEW's list lacks, in vnum order, when the client has the
	files the line names.

	A line whose icon the client lacks is left out: with a line, the slot
	shows no icon (CItemData::__SetIconImage), where without one the item
	falls back to icon/item/<vnum>.tga, the icon of the first item of its
	name, vnum - vnum % 10 and then the empty bowl (LoadItemTable). A model
	the client lacks would likewise hide the dropped item, which is the bag
	today. Returns (bytes, report)."""
	new, strange = item_list_lines(new_data)
	if strange:
		raise ValueError("NEW's list has lines its loader refuses: %r" % strange[:3])
	old = {}
	for line in lines_of(old_data):
		tokens = split_tab(line)
		if tokens is None or len(tokens) not in (3, 4, 5):
			continue
		old[atoi(tokens[0])] = line
	added, withheld, differ = [], [], []
	for vnum in sorted(old):
		if vnum in new:
			if split_tab(new[vnum]) != split_tab(old[vnum]):
				differ.append(vnum)
			continue
		if vnum not in cut_vnums:
			continue
		line = old_item_line(old[vnum])
		tokens = split_tab(line)
		if all(store_name(path) in files for path in tokens[2:]):
			added.append((vnum, line))
		else:
			withheld.append(vnum)
	text = new_data.decode("ascii")
	if text and not text.endswith("\n"):
		text += "\n"
	body = text + "".join(line + "\n" for _, line in added)
	report = {
		"new_lines": len(text.splitlines()),
		"new_sha1": hashlib.sha1(text.encode("ascii")).hexdigest(),
		"added": [vnum for vnum, _ in added],
		"withheld": len(withheld),
		"differ": differ,
	}
	return body.encode("ascii"), report


NPCLIST = os.path.join(ASSETS, "root", "npclist.txt")


def npclist_entries(text):
	"""playersettingmodule.__LoadGameNPC: ({vnum: name}, {name: folder}), the
	first line for a vnum or a name winning as chrmgr's map inserts do. A
	line it would abort on raises ValueError."""
	names, folders = {}, {}
	if text and not text.endswith("\n"):
		raise ValueError("the last line has no line break, and line[:-1] would cut its last letter")
	for number, line in enumerate(text.split("\n")[:-1], 1):
		tokens = line.split("\t")
		if not tokens[0]:
			continue
		vnum = int(tokens[0])
		if vnum:
			if len(tokens) < 2:
				raise ValueError("line %d: a name line without a name" % number)
			names.setdefault(vnum, tokens[1].strip())
		else:
			if len(tokens) < 3:
				raise ValueError("line %d: a folder line without a folder" % number)
			folders.setdefault(tokens[1].strip(), tokens[2].strip())
	return names, folders


def old_npclist(text):
	"""OLD's NpcList.py, which OLD's live client runs (playerSettingModule,
	outside a test server): its chrmgr.RegisterRaceName and
	RegisterRaceSrcName calls, the first one for a vnum or name winning.
	Returns (names, folders, folder names in file order). Some folders hold
	a single backslash (plechito_halloween2020\\...), which Python keeps as
	it is; a string an escape would change raises ValueError."""
	import re
	names, folders, order = {}, {}, []

	def literal(raw):
		if "\\" in raw and re.search(r"\\[\\'\"abfnrtv0-7xNuU\n]", raw):
			raise ValueError("an escape in NpcList.py: %r" % raw)
		return raw

	for line in text.split("\n"):
		match = re.match(r"\s*chrmgr\.RegisterRaceSrcName\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)\s*$", line)
		if match:
			name = literal(match.group(1))
			folders.setdefault(name, literal(match.group(2)))
			order.append(name)
			continue
		match = re.match(r"\s*chrmgr\.RegisterRaceName\(\s*(\d+)\s*,\s*'([^']*)'\s*\)\s*$", line)
		if match:
			names.setdefault(int(match.group(1)), literal(match.group(2)))
			continue
		if line.strip() and line.strip() != "import chrmgr":
			raise ValueError("a line of NpcList.py this reader does not know: %r" % line)
	return names, folders, order


def race_paths(race):
	"""CRaceManager's __GetRaceResourcePathes (src/GameLib/RaceManager.cpp):
	the folders a mob's model is looked for in, in order."""
	monster = ["d:/ymir work/monster/", "d:/ymir work/monster2/"]
	npc = ["d:/ymir work/npc/", "d:/ymir work/npc2/"]
	guild = ["d:/ymir work/guild/"]
	if 14000 <= race < 15000 or race == 20043:
		return guild + npc + monster
	if race > 9000:
		return (npc[::-1] if race >= 30000 else npc) + monster + guild
	if race in (8507, 8510) or (2000 < race <= 8000) or 1400 <= race <= 1700:
		return monster[::-1] + npc + guild
	return monster + npc + guild


def mob_shows(vnum, names, folders, files):
	"""Whether CRaceManager::__LoadRaceData finds the mob's .msm:
	<path><folder>/<name>.msm, the folder being the name's folder line or the
	name itself; for a name starting with '#' (LOAD_LOCAL_RESOURCE), the rest
	of the name is a path and the file <path>shape.msm."""
	name = names.get(vnum)
	if not name:
		return False
	if name.startswith("#"):
		return store_name(name[1:] + "shape.msm") in files
	folder = folders.get(name, name)
	return any(store_name("%s%s/%s.msm" % (path, folder, name)) in files for path in race_paths(vnum))


def cut_mob_vnums(text):
	return set(int(row.split("\t")[0]) for row in text.split("\n")[1:] if row.split("\t")[0].strip().isdigit())


def _first_rows(rows):
	"""{vnum: index of its first name line}: the line chrmgr keeps."""
	first = {}
	for number, row in enumerate(rows):
		head = row.split("\t")[0]
		if head and int(head) and int(head) not in first:
			first[int(head)] = number
	return first


def _rename(rows, vnum, was, name):
	"""The vnum's first name line with ``name`` for ``was``, the rest of the
	line (NEW's trailing tab or none) kept."""
	number = _first_rows(rows)[vnum]
	tokens = rows[number].split("\t")
	if tokens[1].strip() != was:
		raise ValueError("line %d names %r, not %r" % (number + 1, tokens[1], was))
	tokens[1] = name
	rows[number] = "\t".join(tokens)


def npclist_news(text, entry):
	"""NEW's own npclist from a merged one: its first ``new_lines`` lines, with
	NEW's name put back where OLD's replaced it (``renamed``)."""
	rows = text.split("\n")[:entry["new_lines"]]
	for vnum, new_name, old_name in entry.get("renamed", []):
		_rename(rows, vnum, old_name, new_name)
	return "".join(row + "\n" for row in rows)


def merge_npclist(new_data, old_text, mob_vnums, files, pre_vnums):
	"""NEW's npclist with, after its last line, OLD's folder lines for the
	names OLD's added or renamed mobs use that NEW has no folder for (in
	OLD's order) and OLD's name lines for the cut's mobs NEW names none for
	(in vnum order). A name with no model in the store costs CRaceManager
	five failed lookups and syserr lines per spawn, and the mob stays unseen
	as today, so those lines are added too.

	A mob the cut brings (in ``mob_vnums``, not in ``pre_vnums``, NEW's
	pre-cut mob_proto) that NEW's list names otherwise than OLD's takes OLD's
	name on NEW's line when the store has the model OLD's name finds: NEW
	named those vnums for mobs its proto never had, and the cut's mob there
	is OLD's. Where the store lacks OLD's model, NEW's name stays, so a mob
	that shows keeps showing; a rerun after an import switches it. Returns
	(bytes, report)."""
	text = new_data.decode("ascii")
	new_names, new_folders = npclist_entries(text)
	old_names, old_folders, folder_order = old_npclist(old_text)
	added_names = [vnum for vnum in sorted(old_names) if vnum in mob_vnums and vnum not in new_names]
	candidates = [vnum for vnum in sorted(new_names) if vnum in mob_vnums and vnum not in pre_vnums
		and vnum in old_names and old_names[vnum] != new_names[vnum]]

	def folder_lines(vnums):
		used = set(old_names[vnum] for vnum in vnums)
		out = []
		for name in folder_order:
			if name in used and name not in new_folders and name not in out:
				out.append(name)
		return out

	folders = dict(new_folders)
	folders.update((name, old_folders[name]) for name in folder_lines(added_names + candidates))
	renamed = [vnum for vnum in candidates if mob_shows(vnum, {vnum: old_names[vnum]}, folders, files)]
	added_folders = folder_lines(added_names + renamed)
	rows = text.split("\n")
	for vnum in renamed:
		_rename(rows, vnum, new_names[vnum], old_names[vnum])
	lines = ["0\t%s\t%s\n" % (name, old_folders[name]) for name in added_folders]
	lines += ["%d\t%s\t\n" % (vnum, old_names[vnum]) for vnum in added_names]
	body = "\n".join(rows) + "".join(lines)
	names, folders = npclist_entries(body)
	new_mobs = sorted(set(mob_vnums) - set(pre_vnums))
	report = {
		"new_lines": len(text.splitlines()),
		"new_sha1": hashlib.sha1(text.encode("ascii")).hexdigest(),
		"names": ranges(added_names),
		"folders": added_folders,
		"shown": sum(1 for vnum in added_names if mob_shows(vnum, names, folders, files)),
		"renamed": [[vnum, new_names[vnum], old_names[vnum]] for vnum in renamed],
		"cut_new_mobs": ranges(new_mobs),
		"cut_new_mobs_shown": sum(1 for vnum in new_mobs if mob_shows(vnum, names, folders, files)),
	}
	return body.encode("ascii"), report


LOCALES = os.path.join(ASSETS, "locale", "locale")
# The OLD locale each of NEW's locales takes its itemdesc lines from: OLD has
# no br, and NEW's br is its pt with its own spellings.
ITEMDESC_SOURCE = {"br": "pt"}


def itemdesc_path(locale):
	return os.path.join(LOCALES, locale, "itemdesc.txt")


def itemdesc_locales():
	return sorted(name for name in os.listdir(LOCALES) if os.path.isfile(itemdesc_path(name)))


def bind_lines(data):
	"""CMemoryTextFileLoader::Bind on bytes, its DBCS rule included: a byte
	of 0x80 or more takes the next byte with it, even a line break."""
	sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
	import race_msm
	return race_msm.split_lines(data)


def itemdesc_lines(data):
	"""CItemManager::LoadItemDesc: {vnum: line} (SplitLineByTab, atoi of the
	first column, a later line for a vnum replacing an earlier one)."""
	lines = {}
	for line in bind_lines(data):
		if line:
			lines[atoi(line.split(b"\t")[0].decode("latin-1"))] = line
	return lines


def merge_itemdesc(new_data, old_data, cut_vnums):
	"""NEW's itemdesc with, after its last line and in vnum order, OLD's
	line (its last for the vnum, as the loader keeps) for each vnum of the
	cut's item_proto NEW's file has no line for. Lines for other vnums would
	be skipped by the loader (it only describes items it knows). Returns
	(bytes, report)."""
	if new_data and not new_data.endswith(b"\n"):
		raise ValueError("NEW's file does not end with a line break")
	# Every vnum NEW's file has a line for, also one the loader cannot see
	# because the line before it swallows its break (ru 41349 and 41350).
	new = set(atoi(line.split(b"\t")[0].decode("latin-1")) for line in new_data.split(b"\n") if line.strip())
	old = {}
	for line in old_data.split(b"\n"):
		if line.strip():
			old[atoi(line.split(b"\t")[0].decode("latin-1"))] = line.rstrip(b"\r")
	added = [vnum for vnum in sorted(old) if vnum in cut_vnums and vnum not in new]
	block = b"".join(old[vnum] + b"\n" for vnum in added)
	block.decode("utf-8")
	body = new_data + block
	if bind_lines(body) != bind_lines(new_data)[:-1] + [old[vnum] for vnum in added] + [b""]:
		raise ValueError("the loader would not read the added lines one by one")
	report = {
		"new_lines": new_data.count(b"\n"),
		"new_sha1": hashlib.sha1(new_data).hexdigest(),
		"added": ranges(added),
	}
	return body, report


def ranges(vnums):
	"""1, 2, 3, 7 -> "1-3, 7"."""
	out, run = [], []
	for vnum in sorted(vnums):
		if run and vnum == run[-1] + 1:
			run.append(vnum)
			continue
		if run:
			out.append(str(run[0]) if len(run) == 1 else "%d-%d" % (run[0], run[-1]))
		run = [vnum]
	if run:
		out.append(str(run[0]) if len(run) == 1 else "%d-%d" % (run[0], run[-1]))
	return ", ".join(out)


def parse_ranges(text):
	""""1-3, 7" -> [1, 2, 3, 7]."""
	vnums = []
	for part in filter(None, (piece.strip() for piece in text.split(","))):
		first, _, last = part.partition("-")
		vnums.extend(range(int(first), int(last or first) + 1))
	return vnums


def load_fixture():
	with open(FIXTURE, encoding="utf-8") as handle:
		return json.load(handle)


def save_fixture(name, entry):
	"""Sets one file's entry of tools/fixtures/old_content.json."""
	fixture = load_fixture() if os.path.exists(FIXTURE) else {}
	fixture[name] = entry
	with open(FIXTURE, "w", encoding="utf-8") as handle:
		handle.write(json.dumps(fixture, indent="\t", sort_keys=True) + "\n")


def news_part(data, name):
	"""NEW's own lines of a file this module has merged before (the first
	``new_lines`` of its fixture entry, when they still hash the same), else
	the whole file: so a second run, after OLD's icons land for instance,
	starts again from NEW's lines."""
	if not os.path.exists(FIXTURE):
		return data
	entry = load_fixture().get(name)
	if not entry:
		return data
	text = data.decode("ascii")
	if name == "npclist":
		try:
			head = npclist_news(text, entry)
		except (KeyError, ValueError):
			return data
	else:
		head = "".join(line + "\n" for line in text.split("\n")[:entry["new_lines"]])
	if hashlib.sha1(head.encode("ascii")).hexdigest() == entry["new_sha1"]:
		return head.encode("ascii")
	return data


def _main(argv):
	if len(argv) == 3 and argv[0] == "item_list":
		with open(argv[1], "rb") as handle:
			old_data = handle.read()
		with open(argv[2], encoding="utf-8", errors="replace") as handle:
			cut_vnums = cut_item_vnums(handle.read())
		with open(ITEM_LIST, "rb") as handle:
			new_data = news_part(handle.read(), "item_list")
		data, report = merge_item_list(new_data, old_data, cut_vnums, published_files())
		with open(ITEM_LIST, "wb") as handle:
			handle.write(data)
		differ = report.pop("differ")
		withheld = report.pop("withheld")
		save_fixture("item_list", report)
		print("added %d, withheld %d, NEW's line kept for %d vnums whose lines differ: %s" % (
			len(report["added"]), withheld, len(differ), ranges(differ)))
		return 0
	if len(argv) == 4 and argv[0] == "npclist":
		with open(argv[1], encoding="ascii") as handle:
			old_text = handle.read()
		with open(argv[2], encoding="utf-8", errors="replace") as handle:
			mob_vnums = cut_mob_vnums(handle.read())
		with open(argv[3], encoding="utf-8", errors="replace") as handle:
			pre_vnums = cut_mob_vnums(handle.read())
		with open(NPCLIST, "rb") as handle:
			new_data = news_part(handle.read(), "npclist")
		data, report = merge_npclist(new_data, old_text, mob_vnums, published_files(), pre_vnums)
		with open(NPCLIST, "wb") as handle:
			handle.write(data)
		save_fixture("npclist", report)
		print("added %d name lines and %d folder lines; %d of the added mobs have a model the store has; "
			"OLD's name replaces NEW's for %d; %d of the cut's %d new mobs show" % (
				len(parse_ranges(report["names"])), len(report["folders"]), report["shown"], len(report["renamed"]),
				report["cut_new_mobs_shown"], len(parse_ranges(report["cut_new_mobs"]))))
		return 0
	if len(argv) == 3 and argv[0] == "itemdesc":
		old_root, cut_proto = argv[1:]
		with open(cut_proto, encoding="utf-8", errors="replace") as handle:
			cut_vnums = cut_item_vnums(handle.read())
		entry = {}
		for locale in itemdesc_locales():
			source = ITEMDESC_SOURCE.get(locale, locale)
			with open(os.path.join(old_root, source, "itemdesc.txt"), "rb") as handle:
				old_data = handle.read()
			with open(itemdesc_path(locale), "rb") as handle:
				new_data = handle.read()
			previous = load_fixture().get("itemdesc", {}).get(locale) if os.path.exists(FIXTURE) else None
			if previous:
				head = b"".join(line + b"\n" for line in new_data.split(b"\n")[:previous["new_lines"]])
				if hashlib.sha1(head).hexdigest() == previous["new_sha1"]:
					new_data = head
			data, report = merge_itemdesc(new_data, old_data, cut_vnums)
			with open(itemdesc_path(locale), "wb") as handle:
				handle.write(data)
			entry[locale] = report
			print("%s (from OLD's %s): added %d" % (locale, source, len(parse_ranges(report["added"]))))
		save_fixture("itemdesc", entry)
		return 0
	sys.stderr.write(__doc__)
	return 2


if __name__ == "__main__":
	sys.exit(_main(sys.argv[1:]))
