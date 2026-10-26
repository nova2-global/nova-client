"""OLD's client text for the items and mobs of the foundation cut (NOVA-98).

The cut's item_proto and mob_proto are OLD's, so the client needs OLD's
lines for the vnums NEW's text files lack. This module reads those files the
way NEW's client does, adds OLD's lines and never changes one of NEW's; each
file's test (tools/<file>_test.py) checks the result against
tools/fixtures/old_content.json.

	python3 tools/old_content.py item_list OLD_ITEM_LIST CUT_ITEM_PROTO

OLD_ITEM_LIST is old/client_pack/source/locale/common/item_list.txt and
CUT_ITEM_PROTO int-rt's share/conf/item_proto.txt. The command rewrites
assets/locale/locale/common/item_list.txt (from NEW's own lines, also on a
second run) and sets the file's fixture entry.
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
	head = "".join(line + "\n" for line in data.decode("ascii").split("\n")[:entry["new_lines"]])
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
	sys.stderr.write(__doc__)
	return 2


if __name__ == "__main__":
	sys.exit(_main(sys.argv[1:]))
