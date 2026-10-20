"""The legacy color and link tags (|cAARRGGBB, |r, ||, |H<link>|h<text>|h)
in plain Python, as the client's Core/TextTags.h reads them (P10 spec 2.2).
The two pass the same cases (tools/fixtures/text_tags_cases.json).

parse_runs follows the legacy render path (src/EterLib/GrpTextInstance.cpp),
which is what players see: |c needs 8 more characters, else its | is plain
text, and a color whose 8 digits are not all hex draws white (htoi's -1);
|c and |r flush the pending text in the current color, |H does not; the
first |h after |H flushes the pending text and starts the link's text, the
second draws that text (when not empty) as the link followed by one space;
text still pending at the end is plain, and unclosed metadata is dropped.
visible_text and visible_length are the edit line's rules
(src/EterLib/TextTag.cpp GetTextTagOutputString and GetTextTagOutputLen).
Pure Python: no game module."""

_PLAIN, _COLOR, _TAG, _RESTORE, _LINK_START, _LINK_END = range(6)
_HEX = frozenset("0123456789abcdefABCDEF")
_WHITE = 0xFFFFFFFF


def _tag(text, i):
	"""(kind, length, digits) of the tag at text[i], as GetTextTag reads it."""
	rest = len(text) - i
	if rest < 2 or text[i] != "|":
		return _PLAIN, 1, ""
	mark = text[i + 1]
	if mark == "c":
		if rest < 10:
			return _PLAIN, 1, ""
		return _COLOR, 10, text[i + 2:i + 10]
	if mark == "|":
		return _TAG, 2, ""
	if mark == "r":
		return _RESTORE, 2, ""
	if mark == "H":
		return _LINK_START, 2, ""
	if mark == "h":
		return _LINK_END, 2, ""
	return _PLAIN, 1, ""


def _color(digits):
	"""htoi of the 8 digits as 0xAARRGGBB; any other character is htoi's -1,
	which draws white. (int() alone would accept "_" and spaces.)"""
	if len(digits) != 8 or not _HEX.issuperset(digits):
		return _WHITE
	return int(digits, 16)


def _append(runs, text, color, link):
	if not text:
		return
	if runs and not link and not runs[-1][2] and runs[-1][1] == color:
		runs[-1] = (runs[-1][0] + text, color, "")
	else:
		runs.append((text, color, link))


def parse_runs(text):
	"""[(text, color, link)]: the runs legacy draws for `text`, color -1 for
	the line's own color, link "" for none; adjacent plain runs of one color
	merged."""
	text = text or ""
	runs = []
	color = -1
	step = 0                 # 0 text, 1 the link's metadata, 2 the link's text
	link = ""
	metadata = []
	segment = []

	def flush():
		_append(runs, "".join(segment), color, "")
		del segment[:]

	i = 0
	while i < len(text):
		kind, length, digits = _tag(text, i)
		if kind == _COLOR:
			flush()
			color = _color(digits)
		elif kind == _RESTORE:
			flush()
			color = -1
		elif kind == _LINK_START:
			step = 1
			metadata = []
		elif kind == _LINK_END:
			if step == 1:
				flush()
				step = 2
				link = "".join(metadata)
			elif step == 2:
				if segment:
					_append(runs, "".join(segment) + " ", color, link)
				del segment[:]
				step = 0
		elif step == 1:
			metadata.append(text[i])
		else:
			segment.append(text[i])
		i += length
	flush()
	return runs


def visible_text(text):
	"""The text legacy's edit line shows and counts (GetTextTagOutputString):
	the tags gone, a link's text kept, no space added after a link."""
	text = text or ""
	out = []
	step = 0
	i = 0
	while i < len(text):
		kind, length, _ = _tag(text, i)
		if kind in (_PLAIN, _TAG):
			if step in (0, 2):
				out.append(text[i])
		elif kind == _LINK_START:
			step = 1
		elif kind == _LINK_END:
			if step == 1:
				step = 2
			elif step == 2:
				step = 0
		i += length
	return "".join(out)


def visible_length(text):
	"""GetTextTagOutputLen in code points: the characters outside a link's
	metadata (the length the chat fields limit, P10 spec D26)."""
	text = text or ""
	count = 0
	step = 0
	i = 0
	while i < len(text):
		kind, length, _ = _tag(text, i)
		if kind in (_PLAIN, _TAG):
			if step == 0:
				count += 1
		elif kind == _LINK_START:
			step = 1
		elif kind == _LINK_END:
			step = 0
		i += length
	return count


def link_tokens(link):
	"""The link's fields, split at ":" as Interface.MakeHyperlinkTooltip
	splits it ("item:4e21:0:0:0:0" gives ["item", "4e21", "0", "0", "0", "0"])."""
	return (link or "").split(":")
