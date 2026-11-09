"""NovaUI mob info board (nui/windows/target-info/target-info.rml; NOVA-40).

While the target-info flag is on, the target board (legacy uitarget.py and
nui_target.TargetBoard) makes InfoBoard below through nui_windows.make() instead
of uiTargetInfo.InfoBoard: a subclass of the legacy class (nui_facade.Facade)
whose board calls (AppendTextLine, AppendSeperator, MakeDropList, FinishLoad)
fill a model instead of making widgets, so the stats, the race lines, the
resists, the drop rows and their texts, the cache and the retry are legacy's
code. The plain window it stands on is NOT ui.ThinBoard (its corners would
show at the screen's top left).

What NovaUI changes: the board sits under the target board at its sheet's
place (legacy's position is the target board's); the drop list scrolls in
RmlUi; the retry is a nui-countdown (legacy's OnUpdate waits for a time). No
Python runs per frame. OLD cycled the icon of a metin stone row and a valentine
letter row every couple of seconds; neither this board nor legacy's does."""

import ui
import uiTargetInfo

import nui
import nui_facade
import nui_hud
import nui_slots

DOCUMENT = "nui/windows/target-info/target-info.rml"
KEY = "target-info"


class _Board(nui.Window):
	"""The board's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "target_info"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("row_over")
	def on_row_over(self, index):
		self._owner.row_over(int(index))

	@nui.on("row_out")
	def on_row_out(self):
		self._owner.row_out()

	@nui.on("retry_done")
	def on_retry_done(self):
		self._owner.nui_retry()


class InfoBoard(nui_facade.Facade, uiTargetInfo.InfoBoard):
	"""uiTargetInfo.InfoBoard on NovaUI."""

	KEY = KEY
	BOARD = _Board
	PLACE = None
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			self._lines = []
			self._rows = []
			uiTargetInfo.InfoBoard.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"lines": [], "rows": [], "retry": 0.0}

	# --- the legacy window underneath: no art of its own --------------------------------

	def _InitBoard(self):
		"""A plain window, not ui.ThinBoard: its corners and edges are made and
		shown at once, at the screen's top left."""
		ui.Window.__init__(self)

	def SetSize(self, width, height):
		"""Nothing: the legacy window stays 0 x 0 under the board."""

	def AddFlag(self, flag):
		pass

	def _InfoBoard__PlaceUnder(self, targetBoard):
		"""The sheet places the board."""

	def _InfoBoard__Load(self, race):
		self._lines = []
		self._rows = []
		uiTargetInfo.InfoBoard._InfoBoard__Load(self, race)

	def AppendTextLine(self, text):
		self._lines.append({"text": nui.plain_text(text), "sep": False})

	def AppendSeperator(self):
		self._lines.append({"text": "", "sep": True})

	def MakeDropList(self, rows):
		self._rows = [{"icon": nui_slots.icon_source(icon), "text": nui.plain_text(text),
		               "lines": [nui.plain_text(line) for line in lines], "vnum": int(vnum)}
		              for vnum, icon, text, lines in rows]

	def FinishLoad(self):
		self.nui_set(lines=self._lines, rows=[{"icon": row["icon"], "text": row["text"], "lines": row["lines"]}
		                                      for row in self._rows])

	# --- the tooltip ---------------------------------------------------------------------

	def row_over(self, index):
		if 0 <= index < len(self._rows):
			self.OnShowItemTooltip(self._rows[index]["vnum"])

	def row_out(self):
		self.OnShowItemTooltip(0)

	# --- the retry (legacy's OnUpdate waits for a time) ------------------------------

	def ScheduleRetry(self):
		self.nui_set(retry=nui.now() + uiTargetInfo.RETRY_DELAY)

	def nui_retry(self):
		self.nui_set(retry=0.0)
		self.RetryRequest()

	def Close(self):
		self.nui_set(retry=0.0)
		uiTargetInfo.InfoBoard.Close(self)

	def Destroy(self):
		self.nui_discard()
		uiTargetInfo.InfoBoard.Destroy(self)
