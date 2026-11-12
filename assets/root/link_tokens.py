"""Link tokens in the chat and whisper inputs (NOVA-42 round 3, Eddy
2026-11-10, option c: no engine change).

A link pasted into a chat or whisper input shows as its short text, for
example [Blazefury Blade Skin], since NovaUI's text fields show what they
hold. The input keeps a map from each token to the raw
|c...|H...|h[...]|h|r form it stands for, and its send swaps each intact
token back before the packet goes out. A token the player edited no longer
matches and goes out as the plain text it is. The map is cleared when the
input is sent or cleared. Legacy's chat and whisper windows do the same, so
the two look and send alike.

An input takes part by registering itself (register) and answering
link_focused() and link_tokens(). paste() puts a link into the registered
input that has the focus, else (another field, such as a search box) pastes
the raw link as before."""

import re
import weakref

# A link as the chat writes it: an optional color, |H<data>|h, a text
# without "|", |h, an optional |r. The text is the token.
_LINK = re.compile(r"(?:\|c[0-9a-fA-F]{8})?\|H[^|]*\|h([^|]+)\|h(?:\|r)?\Z")

_inputs = []   # weak references to the registered inputs


def short_text(raw):
	"""The visible text of a link (its token), or None for anything else."""
	match = _LINK.match(raw or "")
	return match.group(1) if match else None


class LinkTokens(object):
	"""One input's tokens, in paste order. Two links with one name are two
	entries: the first occurrence in the text takes the first link."""

	def __init__(self):
		self._links = []   # (token, raw)

	def add(self, raw):
		"""Records a link; returns its token, or None when it is not a link."""
		token = short_text(raw)
		if token is not None:
			self._links.append((token, raw))
		return token

	def expand(self, text):
		"""The text with each intact token, left to right, swapped for its raw
		link. An occurrence with no link left stays plain."""
		if not self._links or not text:
			return text
		queues = {}
		for token, raw in self._links:
			queues.setdefault(token, []).append(raw)
		pattern = re.compile("|".join(re.escape(t) for t in sorted(queues, key=len, reverse=True)))

		def swap(match):
			queue = queues[match.group(0)]
			return queue.pop(0) if queue else match.group(0)
		return pattern.sub(swap, text)

	def clear(self):
		self._links = []

	def snapshot(self):
		return list(self._links)

	def restore(self, links):
		self._links = list(links or ())

	def __len__(self):
		return len(self._links)


def register(owner):
	"""An input that pastes tokens: it answers link_focused() and
	link_tokens(). Held weakly."""
	_prune()
	if all(ref() is not owner for ref in _inputs):
		_inputs.append(weakref.ref(owner))


def unregister(owner):
	_inputs[:] = [ref for ref in _inputs if ref() is not None and ref() is not owner]


def _prune():
	_inputs[:] = [ref for ref in _inputs if ref() is not None]


def focused_input():
	"""The registered input that has the focus, or None."""
	_prune()
	for ref in _inputs:
		owner = ref()
		try:
			if owner is not None and owner.link_focused():
				return owner
		except ReferenceError:
			continue
	return None


def paste(raw, target=None, paste=None):
	"""Pastes a link where the player types: into `target`, or the focused
	registered input, as its token; anywhere else as the raw link. `paste`
	is the paste call (ime.PasteString by default)."""
	if paste is None:
		import ime
		paste = ime.PasteString
	owner = target if target is not None else focused_input()
	token = owner.link_tokens().add(raw) if owner is not None else None
	paste(token if token is not None else raw)
	return token is not None
