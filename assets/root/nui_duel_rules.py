"""NovaUI duel rules (nui/windows/duel-rules/duel-rules.rml; NOVA-28).

While the duel-rules flag is on, the target board's Fight button (legacy
uitarget.py and nui_target.py OnAdvancedPVP) makes DuelRulesDialog below
through nui_windows.make() instead of uiDuel.DuelRulesDialog: a subclass of
the legacy class (nui_facade.Facade) whose loader puts proxies where the
widgets were (the title bar, the nine rules' check boxes, Fight and Cancel).
So the rules offered, their order, the ticked rules kept between opens and
"/pvp <vid> <rules>" are legacy's code (OLD uiTarget.py AdvancedDuel).

The board shows the rules as check rows: a press on a row is the check box's
click (it flips, as ui.CheckBox's release). It sits under the target board, at
legacy's place (centered, 80 down), exists only while it shows and runs no
Python per frame."""

import ui
import uiDuel
import wndMgr

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/duel-rules/duel-rules.rml"
KEY = "duel-rules"
WIDTH = 355      # legacy's uiscript width
TOP = 80         # legacy's y


class CheckBoxProxy(nui_proxies._Shown):
	"""ui.CheckBox: its text and state; click() is its left release (the state
	flips, then ON_CHECK or ON_UNCHECK runs); on_change(proxy) after each change."""

	def __init__(self, on_change=None):
		self.text = ""
		self.checked = False
		self.eventFunc = {"ON_CHECK": None, "ON_UNCHECK": None}
		self.on_change = on_change

	def _changed(self):
		if self.on_change:
			self.on_change(self)

	def SetParent(self, parent):
		pass

	def SetPosition(self, x, y):
		pass

	def SetTextInfo(self, info):
		self.text = "" if info is None else str(info)
		self._changed()

	def SetCheckStatus(self, flag):
		self.checked = bool(flag)
		self._changed()

	def GetCheckStatus(self):
		return self.checked

	def SetEvent(self, func, kind):
		if kind in self.eventFunc:
			self.eventFunc[kind] = func

	def click(self):
		self.SetCheckStatus(not self.checked)
		event = self.eventFunc["ON_CHECK" if self.checked else "ON_UNCHECK"]
		if event:
			event()


class _DuelRulesBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The duel rules' document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "duel_rules"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()

	@nui.on("rule_press")
	def on_rule_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.nui_rule_press(int(index))

	@nui.on("button_press")
	def on_button_press(self, name, button):
		self.raise_for(button)
		if button != 0:
			return
		widget = {"accept": "acceptButton", "cancel": "cancelButton"}.get(name)
		if widget:
			getattr(self._owner, widget).click()


def _legacy_place():
	"""Legacy's place in dp: centered across the screen, TOP down."""
	scale = nui.get_scale() or 1.0
	return ((wndMgr.GetScreenWidth() / scale - WIDTH) / 2.0, TOP)


class DuelRulesDialog(nui_facade.Facade, uiDuel.DuelRulesDialog):
	"""uiDuel.DuelRulesDialog on NovaUI (TargetBoard.duelRulesDialog)."""

	KEY = KEY
	BOARD = _DuelRulesBoard
	PLACE = staticmethod(_legacy_place)
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiDuel.DuelRulesDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"rules": []}

	def _DuelRulesDialog__LoadWindow(self):
		self.AddFlag("movable")
		self.AddFlag("float")
		self.titleBar = nui_proxies.BoardProxy(340, 21)
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnCancelDuel))
		self.acceptButton.SetEvent(ui.__mem_func__(self.OnPressAcceptDuel))
		self.cancelButton.SetEvent(ui.__mem_func__(self.OnCancelDuel))

		self.checkBoxList = []
		for index, (bit, key) in enumerate(uiDuel.DUEL_FLAGS):
			checkBox = CheckBoxProxy(self._publish_rules)
			checkBox.SetPosition(*uiDuel.RULE_POSITION(index))
			checkBox.SetTextInfo(uiDuel.rule_text(key))
			checkBox.Show()
			self.checkBoxList.append(checkBox)
		self._publish_rules()

	def _publish_rules(self, changed=None):
		boxes = getattr(self, "checkBoxList", None) or []
		self.nui_set(rules=[{"label": nui.plain_text(box.text), "checked": box.checked} for box in boxes])

	def nui_rule_press(self, index):
		if 0 <= index < len(self.checkBoxList):
			self.checkBoxList[index].click()
