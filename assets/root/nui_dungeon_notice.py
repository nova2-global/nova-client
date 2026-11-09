"""NovaUI dungeon ready notice (nui/windows/dungeon-notice/dungeon-notice.rml;
NOVA-25).

Legacy's notice (uitimerwindow.TimerNotice) is a box near the top of the screen
that a dungeon's row opens when its re-entry clock ends, if the player checked
"Notify me when ready" for that dungeon, and that hides itself after three
seconds; legacy finds both moments every frame (game.OnUpdate through
TimerWindow.UpdateTime and TimerNotice.OnUpdate). Here no Python runs per
frame: the NovaUI dungeon manager (nui_dungeon_timer.TimerWindow) hands
Notices the clocks to watch, and the document's hidden nui-countdown timers
raise `timer_end` at a clock's end and `toast_end` three seconds after a box
shows. The document is loaded only while a clock is watched or a box shows,
and goes when neither is left. It takes no presses (body.nui-overlay)."""

import nui
import nui_hud

DOCUMENT = "nui/windows/dungeon-notice/dungeon-notice.rml"
NOTICE_SECONDS = 3


class _NoticeBoard(nui.Window):
	DOCUMENT = DOCUMENT
	MODEL = "dungeon_notice"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("timer_end")
	def on_timer_end(self, idx):
		self._owner.timer_ended(int(idx))

	@nui.on("toast_end")
	def on_toast_end(self, key):
		self._owner.toast_ended(int(key))


class Notices(object):
	"""The clocks the manager watches and the boxes that show (legacy's
	OPEN_NOTICE_COUNT stacking: each new box under the ones still shown).
	on_end(idx) runs when a watched clock ends; it answers the box's title,
	or None for no box."""

	def __init__(self, on_end):
		self.on_end = on_end
		self.timers = []     # [{"idx", "end"}]
		self.toasts = []     # [{"key", "title", "end"}]
		self.serial = 0
		self.board = None

	def model(self):
		return {"timers": [dict(t) for t in self.timers], "toasts": [dict(t) for t in self.toasts]}

	def watch(self, clocks):
		"""The clocks to watch, {idx: seconds left}, replacing the earlier ones."""
		now = nui.now()
		self.timers = [{"idx": int(idx), "end": now + float(left)} for idx, left in sorted(clocks.items()) if left > 0]
		self._publish()

	def timer_ended(self, idx):
		self.timers = [t for t in self.timers if t["idx"] != idx]
		title = self.on_end(idx)
		if title is not None:
			self.serial += 1
			self.toasts.append({"key": self.serial, "title": nui.plain_text(title), "end": nui.now() + NOTICE_SECONDS})
		self._publish()

	def toast_ended(self, key):
		self.toasts = [t for t in self.toasts if t["key"] != key]
		self._publish()

	def _publish(self):
		if not self.timers and not self.toasts:
			self.discard()
			return
		if self.board is None:
			self.board = _NoticeBoard(self, self.model())
			self.board.show()
		else:
			self.board.set(**self.model())

	def discard(self):
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
