"""The wiki's text page format (NOVA-139): front matter and a Markdown subset,
parsed into plain data that the wiki window turns into its model
(nui_wiki_pages.py). docs/wiki/WRITING.md is the author's guide; this module
is the rule.

A page is UTF-8 text:

    ---
    title: Demon Tower
    category: dungeons
    order: 10                                (optional)
    decor: top-right = icon/item/30304.tga   (optional, once per corner)
    ---
    # Heading, ## and ### too
    Text with **bold**, *italic*, [[item:19]], [[mob:101|Wild Dog]],
    [[page:dungeons/demon_tower]], and an item with its icon and its
    tooltip, ![[item:30304]] (r4: OLD's [IMG=icon/item/N.tga; ITEM_TOOLTIP=N]).
    - bullets, 1. numbers, | tables |, ![alt](pack/path.png){float=right width=180},
    ---, --- {style=ornate}, :::note, :::warning, :::columns with +++ breaks, :::

Nothing in a page is markup: every word reaches the window as model text,
never RML. Image paths are store paths in the pack, of a fixed character set
and extension; page paths are [a-z0-9_/-]. A problem never raises: it
becomes an error block where it happened (and an entry in problems, which
tools/nui_wiki_pages_tool.py check reports), and a page whose front matter
is unusable is one error block. There are no pixel positions, by design:
OLD's .txt pages placed lines and images by pixel and broke with every font
and scale.

This module imports nothing from the client, so tools and tests use it as
it is."""

SIZE_MAX = 64 * 1024
BLOCKS_MAX = 400
TITLE_MAX = 80
PATH_MAX = 64
IMAGE_PATH_MAX = 128
TABLE_COLUMNS_MAX = 8
COLUMNS_MAX = 3
LIST_DEPTH_MAX = 2
VNUM_MAX = 4294967295
IMAGE_WIDTH_MIN, IMAGE_WIDTH_MAX = 8, 640

# The separator styles a page may name with --- {style=<name>}. Each has a
# rule .wp__hr--<name> in nui/windows/wiki/wiki-pages.rcss (docs/wiki/WRITING.md,
# "Adding a separator style"); nui_wiki_pages_test checks both ways.
SEPARATOR_STYLES = ("ornate",)
CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")
LINK_KINDS = ("item", "mob", "page")
IMAGE_EXTENSIONS = (".png", ".tga", ".dds", ".jpg", ".sub")
LEGACY_DRIVE = "d:/ymir work/"
META_KEYS = ("title", "category", "order", "decor")

BLOCK_KINDS = ("h1", "h2", "h3", "p", "ul", "ol", "table", "img", "hr", "note", "warn", "cols", "error")
CONTAINERS = {"note": "note", "warning": "warn", "columns": "cols"}

_PATH_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-/")
_IMAGE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-/.")
_CATEGORY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")
# A backslash before any ASCII punctuation shows it as it is.
_ESCAPABLE = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


class Page(object):
	"""A parsed page: meta (title, category, order, decor), blocks, problems
	[(line, message)], fatal (the front matter was unusable: blocks is one
	error block) and search_text (the title and every word, lowercase)."""

	def __init__(self):
		self.meta = {"title": "", "category": "", "order": 0, "decor": []}
		self.blocks = []
		self.problems = []
		self.fatal = False
		self.search_text = ""


def empty_block(kind):
	"""Every block has every key, at every level, so a document that binds
	them never reads a missing one."""
	return {"k": kind, "runs": [], "items": [], "rows": [], "src": "", "alt": "", "fl": "", "al": "",
	        "w": "auto", "style": "", "cols": [], "text": ""}


def walk(blocks):
	"""Every block, those inside notes and columns too."""
	out = []
	for block in blocks:
		out.append(block)
		for column in block["cols"]:
			out.extend(walk(column["blocks"]))
	return out


def _run(text, bold=False, italic=False, link=None, error=False, embed=False):
	"""A piece of text: bold, italic, a link (kind, ident, text or None), an
	error, or an embed (a link shown with the item's icon, ![[item:N]])."""
	return {"t": text, "b": bold, "i": italic, "link": link, "e": error, "embed": embed}


# --- paths ------------------------------------------------------------------------------

def valid_page_path(path):
	"""A page's path: [a-z0-9_/-], at most PATH_MAX characters, no leading or
	trailing slash, no empty part. The chat link (|Hsyswiki:page:<path>|h)
	carries the same rule."""
	if not isinstance(path, str) or not path or len(path) > PATH_MAX:
		return False
	if any(c not in _PATH_CHARS for c in path) or path.startswith("/") or path.endswith("/"):
		return False
	return all(part and part != ".." for part in path.split("/"))


def valid_image_path(path):
	"""A store path in the pack: lowercase [a-z0-9_./-] parts with one of
	IMAGE_EXTENSIONS, or the same after legacy's "d:/ymir work/" drive. No
	"..", no empty part, no leading slash, no other drive, no scheme."""
	if not isinstance(path, str) or not path or len(path) > IMAGE_PATH_MAX:
		return False
	rest = path[len(LEGACY_DRIVE):] if path.startswith(LEGACY_DRIVE) else path
	if not rest or any(c not in _IMAGE_CHARS for c in rest):
		return False
	parts = rest.split("/")
	if any(not part or part in (".", "..") for part in parts):
		return False
	return parts[-1].endswith(IMAGE_EXTENSIONS) and not parts[-1].startswith(".")


def image_source(path):
	"""The <img src> of a valid image path: store paths from the store root."""
	return path if path.startswith(LEGACY_DRIVE) else "/" + path


def _valid_vnum(text):
	return text.isdigit() and text[0] != "0" and int(text) <= VNUM_MAX


# --- text --------------------------------------------------------------------------------

def _clean(text):
	"""Tabs to spaces, control characters out (newlines stay)."""
	text = text.replace("\t", "    ")
	return "".join(c for c in text if c == "\n" or (ord(c) >= 32 and ord(c) != 127))


def _decode(data):
	if isinstance(data, bytes):
		try:
			data = data.decode("utf-8")
		except UnicodeDecodeError:
			return None
	if not isinstance(data, str):
		return None
	if data.startswith("\ufeff"):
		data = data[1:]
	return data.replace("\r\n", "\n").replace("\r", "\n")


class _Parser(object):
	def __init__(self, result):
		self.result = result
		self.line = 0
		self.pending = []
		self.inline_problems = []

	def problem(self, message, line=None):
		"""Records a problem; returns its error block."""
		self.result.problems.append((self.line if line is None else line, message))
		block = empty_block("error")
		block["text"] = message
		return block

	# --- inline --------------------------------------------------------------------------

	def _link(self, body, raw, embed=False):
		"""[[kind:ident]] or [[kind:ident|text]]: the run, or an error run.
		With embed (a ! before it), only an item: an embed shows the item's
		icon and tooltip, which a mob or a page does not have (OLD's pages
		embedded items only)."""
		target, bar, label = body.partition("|")
		kind, colon, ident = target.partition(":")
		kind, ident = kind.strip(), ident.strip()
		reason = None
		if not colon or kind not in LINK_KINDS:
			reason = "a link is [[item:<vnum>]], [[mob:<vnum>]] or [[page:<path>]]: %s" % raw
		elif kind in ("item", "mob") and not _valid_vnum(ident):
			reason = "%s links take a number from 1 to %d: %s" % (kind, VNUM_MAX, raw)
		elif kind == "page" and not valid_page_path(ident):
			reason = "a page path is [a-z0-9_/-], at most %d characters: %s" % (PATH_MAX, raw)
		elif bar and not label.strip():
			reason = "a link's text after | is empty: %s" % raw
		elif embed and kind != "item":
			reason = "only items embed, as ![[item:<vnum>]]; write a %s as a link, [[%s:...]]: %s" % (kind, kind, raw)
		if reason:
			self.inline_problems.append(reason)
			return _run(raw, error=True)
		return _run("", link=(kind, ident, label.strip() if bar else None), embed=embed)

	def tokens(self, text):
		"""Text, star and link tokens; escapes resolved into text."""
		out, buf, i, n = [], [], 0, len(text)

		def flush():
			if buf:
				out.append(("text", "".join(buf)))
				del buf[:]
		while i < n:
			c = text[i]
			if c == "\\" and i + 1 < n and text[i + 1] in _ESCAPABLE:
				buf.append(text[i + 1])
				i += 2
			elif c == "*":
				j = i
				while j < n and text[j] == "*":
					j += 1
				flush()
				count = j - i
				if count > 3:
					out.append(("text", "*" * (count - 3)))
					count = 3
				out.append(("star", count))
				i = j
			elif text.startswith("[[", i) or text.startswith("![[", i):
				embed = c == "!"
				start = i + 1 if embed else i
				end = text.find("]]", start + 2)
				if end < 0 or "[[" in text[start + 2:end]:
					buf.append(text[i:start + 2])
					i = start + 2
					continue
				flush()
				out.append(("link", self._link(text[start + 2:end], text[i:end + 2], embed)))
				i = end + 2
			else:
				buf.append(c)
				i += 1
		flush()
		return out

	def inline(self, text):
		tokens = self.tokens(text)
		# A star run opens only where a later run of the same length closes it.
		paired, open_at = set(), {}
		for index, (kind, value) in enumerate(tokens):
			if kind != "star":
				continue
			if value in open_at:
				paired.add(open_at.pop(value))
				paired.add(index)
			else:
				open_at[value] = index
		runs, bold, italic = [], False, False
		for index, (kind, value) in enumerate(tokens):
			if kind == "star":
				if index in paired:
					if value & 2:
						bold = not bold
					if value & 1:
						italic = not italic
				else:
					self._text(runs, "*" * value, bold, italic)
			elif kind == "text":
				self._text(runs, value, bold, italic)
			else:
				value["b"], value["i"] = bold, italic
				runs.append(value)
		return runs

	@staticmethod
	def _text(runs, text, bold, italic):
		last = runs[-1] if runs else None
		if last is not None and not last["link"] and not last["e"] and last["b"] == bold and last["i"] == italic:
			last["t"] += text
		else:
			runs.append(_run(text, bold, italic))

	def runs(self, text):
		"""The runs of a piece of text; its link problems wait in pending
		until the block is placed, and go after it."""
		self.inline_problems = []
		runs = self.inline(text.strip())
		for reason in self.inline_problems:
			self.pending.append(self.problem(reason))
		return runs

	# --- blocks ----------------------------------------------------------------------------

	def emit(self, block):
		"""A block, then the problems its text had."""
		self.target.append(block)
		self.flush()

	def flush(self):
		self.target.extend(self.pending)
		del self.pending[:]

	def parse_body(self, lines, first_line):
		self.blocks = []            # the page's blocks
		self.target = self.blocks   # where blocks go: the page, or a column
		self.container = None       # the open :::block: (block, word, line)
		state = {"para": [], "list": None, "table": None}

		def end_para():
			if state["para"]:
				block = empty_block("p")
				block["runs"] = self.runs(" ".join(state["para"]))
				self.emit(block)
				state["para"] = []

		def end_all():
			end_para()
			state["list"] = None
			state["table"] = None

		for index, raw in enumerate(lines):
			self.line = first_line + index
			stripped = raw.strip()
			indent = len(raw) - len(raw.lstrip(" "))
			if not stripped:
				end_all()
				continue
			listing = state["list"]
			# A list item's continuation: indented under it, not a new item.
			if listing is not None and indent >= 2 and self._item(stripped) is None:
				entry = listing[1]["items"][-1]
				entry["_text"] += " " + stripped
				entry["runs"] = self.runs(entry["_text"])
				self.flush()
				continue
			if stripped.startswith(":::"):
				end_all()
				self.fence(stripped[3:].strip())
				continue
			if stripped == "+++":
				end_all()
				self.column_break()
				continue
			if stripped == "---" or (stripped.startswith("--- ") and stripped[4:].strip().startswith("{")):
				end_all()
				self.separator(stripped[3:].strip())
				continue
			if stripped.startswith("#"):
				hashes = len(stripped) - len(stripped.lstrip("#"))
				if stripped[hashes:hashes + 1] == " " and stripped[hashes:].strip():
					end_all()
					block = empty_block("h%d" % min(hashes, 3))
					block["runs"] = self.runs(stripped[hashes:])
					if hashes > 3:
						self.pending.append(self.problem("headings go down to ### (three levels)"))
					self.emit(block)
					continue
			if self._image_parts(stripped) is not None:
				end_all()
				self.image_line(stripped)
				continue
			item = self._item(stripped)
			if item is not None:
				end_para()
				state["table"] = None
				self.list_item(state, item, indent)
				continue
			if stripped.startswith("|"):
				end_para()
				state["list"] = None
				state["table"] = self.table_row(stripped, state["table"])
				continue
			if state["list"] is not None or state["table"] is not None:
				end_all()
			state["para"].append(stripped)
		end_all()
		if self.container is not None:
			self.blocks.append(self.problem("a :::%s block is never closed with :::" % self.container[1],
			                                self.container[2]))
		for block in walk(self.blocks):
			for entry in block["items"]:
				entry.pop("_text", None)
			block.pop("_ruled", None)
			block.pop("_width", None)
		return self.blocks

	@staticmethod
	def _item(stripped):
		if stripped[:2] in ("- ", "* ") and stripped[2:].strip():
			return ("ul", 0, stripped[2:])
		digits = 0
		while digits < len(stripped) and stripped[digits].isdigit():
			digits += 1
		if 0 < digits <= 6 and stripped[digits:digits + 2] == ". " and stripped[digits + 2:].strip():
			return ("ol", int(stripped[:digits]), stripped[digits + 2:])
		return None

	def list_item(self, state, item, indent):
		kind, number, rest = item
		depth = min(indent // 2, LIST_DEPTH_MAX)
		listing = state["list"]
		if listing is None or (listing[0] != kind and depth == 0):
			block = empty_block(kind)
			listing = state["list"] = (kind, block, {})
			self.target.append(block)
		counts = listing[2]
		for deeper in [d for d in counts if d > depth]:
			del counts[deeper]
		marker = ""
		if kind == "ol":
			counts[depth] = counts[depth] + 1 if depth in counts else number
			marker = "%d." % counts[depth]
		entry = {"n": marker, "d": depth, "runs": self.runs(rest), "_text": rest}
		listing[1]["items"].append(entry)
		self.flush()

	def fence(self, word):
		if not word:
			if self.container is None:
				self.emit(self.problem("::: closes a block, but none is open"))
				return
			self.target = self.blocks
			self.container = None
			return
		kind = CONTAINERS.get(word)
		if kind is None:
			self.emit(self.problem("a block is :::note, :::warning or :::columns, not :::%s" % word))
			return
		if self.container is not None:
			self.emit(self.problem("a :::%s block cannot hold another block (:::%s)" % (self.container[1], word)))
			return
		block = empty_block(kind)
		block["cols"].append({"blocks": []})
		self.blocks.append(block)
		self.container = (block, word, self.line)
		self.target = block["cols"][0]["blocks"]

	def column_break(self):
		if self.container is None or self.container[0]["k"] != "cols":
			self.emit(self.problem("+++ breaks columns only inside :::columns"))
			return
		cols = self.container[0]["cols"]
		if len(cols) >= COLUMNS_MAX:
			self.emit(self.problem("a :::columns block has at most %d columns" % COLUMNS_MAX))
			return
		cols.append({"blocks": []})
		self.target = cols[-1]["blocks"]

	@staticmethod
	def attributes(text):
		"""{a=b c=d}: a dict, or None."""
		if not (text.startswith("{") and text.endswith("}")):
			return None
		out = {}
		for part in text[1:-1].split():
			key, eq, value = part.partition("=")
			if not eq or not key or not value:
				return None
			out[key] = value
		return out

	def separator(self, rest):
		block = empty_block("hr")
		if rest:
			attrs = self.attributes(rest)
			style = (attrs or {}).get("style")
			if attrs is None or set(attrs) != {"style"}:
				self.pending.append(self.problem("a separator is --- or --- {style=<name>}"))
			elif style not in SEPARATOR_STYLES:
				self.pending.append(self.problem("no separator style '%s' (there are: %s)"
				                                 % (style, ", ".join(SEPARATOR_STYLES))))
			else:
				block["style"] = style
		self.emit(block)

	@staticmethod
	def _image_parts(stripped):
		"""(alt, path, options) of a line ![alt](path){options}, else None
		(the line is text)."""
		if not stripped.startswith("!["):
			return None
		close = stripped.find("](")
		end = stripped.find(")", close + 2) if close > 0 else -1
		if close < 0 or end < 0:
			return None
		return stripped[2:close], stripped[close + 2:end].strip(), stripped[end + 1:].strip()

	def image_line(self, stripped):
		"""![alt](path){attrs} on a line of its own."""
		alt, path, rest = self._image_parts(stripped)
		if not valid_image_path(path):
			self.emit(self.problem("an image path is a lowercase pack path ending in %s, with no '..': %s"
			                       % (", ".join(IMAGE_EXTENSIONS), path)))
			return
		block = empty_block("img")
		block["src"] = image_source(path)
		block["alt"] = alt.strip()
		reason = self.image_options(block, rest) if rest else None
		self.emit(self.problem(reason) if reason else block)

	def image_options(self, block, rest):
		attrs = self.attributes(rest)
		if attrs is None:
			return "image options are {float=left|right align=left|center|right width=<dp>|<percent>%}"
		for key, value in attrs.items():
			if key == "float" and value in ("left", "right"):
				block["fl"] = value
			elif key == "align" and value in ("left", "center", "right"):
				block["al"] = value
			elif key == "width" and value.endswith("%") and value[:-1].isdigit() and 1 <= int(value[:-1]) <= 100:
				block["w"] = "%d%%" % int(value[:-1])
			elif key == "width" and value.isdigit() and IMAGE_WIDTH_MIN <= int(value) <= IMAGE_WIDTH_MAX:
				block["w"] = "%ddp" % int(value)
			else:
				return ("the image option %s=%s is not one of float=left|right, align=left|center|right, "
				        "width=%d to %d or 1%% to 100%%" % (key, value, IMAGE_WIDTH_MIN, IMAGE_WIDTH_MAX))
		if block["fl"] and block["al"]:
			return "an image floats or aligns, not both"
		return None

	@staticmethod
	def _cells(line):
		"""A row's cells, split on | outside [[links]] and escapes."""
		body = line.strip()[1:]
		if body.endswith("|") and not body.endswith("\\|"):
			body = body[:-1]
		cells, buf, i, depth = [], [], 0, 0
		while i < len(body):
			if body[i] == "\\" and i + 1 < len(body):
				buf.append(body[i:i + 2])
				i += 2
				continue
			if body.startswith("[[", i):
				depth += 1
			elif body.startswith("]]", i) and depth:
				depth -= 1
			if body[i] == "|" and not depth:
				cells.append("".join(buf))
				buf = []
			else:
				buf.append(body[i])
			i += 1
		cells.append("".join(buf))
		return [c.strip() for c in cells]

	def table_row(self, stripped, table):
		cells = self._cells(stripped)
		is_rule = all(c and set(c) <= set("-: ") and "-" in c for c in cells)
		if table is not None and is_rule and len(table["rows"]) == 1 and not table["_ruled"]:
			table["rows"][0]["head"] = True
			table["_ruled"] = True
			return table
		if table is None:
			table = empty_block("table")
			table["_ruled"] = False
			table["_width"] = min(len(cells), TABLE_COLUMNS_MAX)
			self.target.append(table)
			if len(cells) > TABLE_COLUMNS_MAX:
				self.target.append(self.problem("a table has at most %d columns" % TABLE_COLUMNS_MAX))
		width = table["_width"]
		if len(cells) > width:
			self.target.append(self.problem("this table row has %d cells, the table %d" % (len(cells), width)))
			cells = cells[:width]
		cells += [""] * (width - len(cells))
		row = {"head": False, "cells": []}
		for cell in cells:
			row["cells"].append({"runs": self.runs(cell)})
		table["rows"].append(row)
		self.flush()
		return table


def _front_matter(lines, result, parser):
	"""(line index of the closing ---, error blocks), or (None, [block]) when
	the page cannot show."""
	if not lines or lines[0].strip() != "---":
		return None, [parser.problem("a page starts with a line '---', its front matter (title, category) and '---'", 1)]
	close = None
	for i in range(1, min(len(lines), 40)):
		if lines[i].strip() == "---":
			close = i
			break
	if close is None:
		return None, [parser.problem("the front matter is never closed with '---'", 1)]
	meta, corners, errors = result.meta, set(), []
	for i in range(1, close):
		parser.line = i + 1
		line = lines[i].strip()
		if not line or line.startswith("#"):
			continue
		key, colon, value = line.partition(":")
		key, value = key.strip().lower(), value.strip()
		if not colon or key not in META_KEYS:
			errors.append(parser.problem("the front matter takes %s, not '%s'" % (", ".join(META_KEYS), line)))
		elif key == "title":
			meta["title"] = value[:TITLE_MAX]
		elif key == "category":
			meta["category"] = value
		elif key == "order":
			if value.lstrip("-").isdigit() and len(value) < 7:
				meta["order"] = int(value)
			else:
				errors.append(parser.problem("order is a whole number"))
		else:
			corner, eq, path = value.partition("=")
			corner, path = corner.strip(), path.strip()
			if not eq or corner not in CORNERS:
				errors.append(parser.problem("decor is <corner> = <image path>, the corner one of %s" % ", ".join(CORNERS)))
			elif corner in corners:
				errors.append(parser.problem("decor names %s twice" % corner))
			elif not valid_image_path(path):
				errors.append(parser.problem("a decor image is a lowercase pack path ending in %s, with no '..': %s"
				                             % (", ".join(IMAGE_EXTENSIONS), path)))
			else:
				corners.add(corner)
				meta["decor"].append((corner, path))
	if not meta["title"].strip():
		return None, [parser.problem("the front matter has no title", 1)]
	category = meta["category"]
	if not category or len(category) > 32 or any(c not in _CATEGORY_CHARS for c in category):
		return None, [parser.problem("the category is lowercase [a-z0-9_-], for example 'dungeons'", 1)]
	return close, errors


def _plain(blocks):
	words = []
	for block in walk(blocks):
		pieces = [block["runs"]] + [entry["runs"] for entry in block["items"]]
		pieces += [cell["runs"] for row in block["rows"] for cell in row["cells"]]
		if block["alt"]:
			words.append(block["alt"])
		for runs in pieces:
			for run in runs:
				link = run["link"]
				words.append(link[2] if link and link[2] else run["t"])
	return " ".join(w for w in words if w)


def parse(data):
	"""A page from its file's text (str or UTF-8 bytes). Never raises."""
	result = Page()
	parser = _Parser(result)
	text = _decode(data)
	if text is None:
		blocks, fatal = [parser.problem("the page is not UTF-8 text", 1)], True
	elif len(text) > SIZE_MAX:
		blocks, fatal = [parser.problem("the page is longer than %d characters" % SIZE_MAX, 1)], True
	else:
		lines = _clean(text).split("\n")
		close, errors = _front_matter(lines, result, parser)
		if close is None:
			blocks, fatal = errors, True
		else:
			blocks, fatal = errors + parser.parse_body(lines[close + 1:], close + 2), False
			if len(blocks) > BLOCKS_MAX:
				blocks = blocks[:BLOCKS_MAX]
				blocks.append(parser.problem("the page has more than %d blocks: the rest is cut" % BLOCKS_MAX))
	result.blocks, result.fatal = blocks, fatal
	result.search_text = (result.meta["title"] + " " + _plain(result.blocks)).lower()
	return result
