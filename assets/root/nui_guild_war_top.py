"""NovaUI guild war top killers (nui/windows/guild-war-top/guild-war-top.rml;
NOVA-29).

While the guild-war-top flag is on, Interface.__MakeWindows makes
TopWarPlayersDialog below through nui_windows.make() instead of
uiGuild.TopWarPlayersDialog: a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the widgets were (each
side's name with its score, its MVP line and its ten rows). So BeginWar,
EndWar, SetScore, each fighter's line (Update, from game.py BINARY_WarTop),
the order (OLD's: kills, then deaths, then damage, highest first) and the
texts are legacy's code (OLD uiGuild.py TopWarPlayersDialog).

TAB held shows it during a war (Interface.OpenTopKillers at the press,
CloseTopKillers at the release). The board exists only while it shows; each
row also carries the fighter's race, which the modern looks draw as the
portrait the target board uses (FACES)."""

import uiGuild

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/guild-war-top/guild-war-top.rml"
KEY = "guild-war-top"
# The portrait of each race, rooted (nui_target.FACES, uicharacter.py
# FACE_IMAGE_DICT's icons).
FACES = {0: "/icon/face/warrior_m.tga", 1: "/icon/face/assassin_w.tga", 2: "/icon/face/sura_m.tga",
         3: "/icon/face/shaman_w.tga", 4: "/icon/face/warrior_w.tga", 5: "/icon/face/assassin_m.tga",
         6: "/icon/face/sura_w.tga", 7: "/icon/face/shaman_m.tga"}


class _RowTextProxy(nui_proxies.TextProxy):
	"""One cell of a side's row: its text, published with the side."""

	def __init__(self, owner):
		nui_proxies.TextProxy.__init__(self, lambda text: owner._publish())

	def SetParent(self, parent):
		pass

	def SetPosition(self, x, y):
		pass


class _TopBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The top killers' document."""

	DOCUMENT = DOCUMENT
	MODEL = "guild_war_top"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)


class TopWarPlayersDialog(nui_facade.Facade, uiGuild.TopWarPlayersDialog):
	"""uiGuild.TopWarPlayersDialog on NovaUI (Interface.wndTopKillers)."""

	KEY = KEY
	BOARD = _TopBoard
	PLACE = "center"
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiGuild.TopWarPlayersDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		side = {"name": "", "mvp": "", "rows": []}
		return {"left": dict(side), "right": dict(side)}

	def _TopWarPlayersDialog__CreateDialog(self):
		self.AddFlag("float")
		self.board = nui_proxies.BoardProxy(720, 340)
		if not hasattr(self, "ElementDictionary"):
			self.ElementDictionary = {}
		for side in (1, 2):
			self.ElementDictionary["guild%d_name" % side] = _RowTextProxy(self)
			self.ElementDictionary["guild%d_mvp" % side] = _RowTextProxy(self)
		self.rows = {}
		for side in (1, 2):
			self.rows[side] = [[_RowTextProxy(self) for _ in uiGuild.TOP_WAR_COLUMNS] for _ in range(uiGuild.TOP_WAR_ROWS)]
		self._publish()

	def _race_of(self, side, name):
		for guildId, entry in getattr(self, "guildNumber", {}).items():
			if entry.get("side") == side:
				data = getattr(self, "DATA", {}).get(guildId, {}).get(name)
				if data:
					return data[3]
		return -1

	def _publish(self):
		rows = getattr(self, "rows", None)
		if not rows or not getattr(self, "ElementDictionary", None):
			return
		model = {}
		for side, key in ((1, "left"), (2, "right")):
			shown = []
			for texts in rows.get(side, []):
				values = [text.GetText() for text in texts]
				if not values[0]:
					continue
				race = self._race_of(side, values[0])
				shown.append({"name": nui.plain_text(values[0]), "kills": values[1], "deaths": values[2],
				              "damage": values[3], "ping": values[4], "portrait": FACES.get(race, "")})
			model[key] = {"name": nui.plain_text(self.GetChild("guild%d_name" % side).GetText()),
			              "mvp": nui.plain_text(self.GetChild("guild%d_mvp" % side).GetText()), "rows": shown}
		self.nui_set(**model)
