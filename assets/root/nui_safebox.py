"""NovaUI safebox and its password dialogs (nui/windows/safebox/safebox.rml,
safebox-password, change-password; P16 spec 5.4).

While the safebox flag is on, Interface.__MakeDialogs makes SafeboxWindow
and PasswordDialog below through nui_windows.make() instead of
uiSafebox.SafeboxWindow and uiSafebox.PasswordDialog (the password dialog
the Interface shares with the mall), and the NovaUI safebox makes the
NovaUI ChangePasswordDialog. Each is a subclass of its legacy class whose
uiscript loader puts proxies where the widgets were (nui_facade.Facade),
so every flow is legacy's code:
- the safebox: storing an item (an active auto potion used first, the
  check-in packet, a move inside the safebox), taking one (the attach, the
  inventory's check-out), money attached and dropped (legacy's save money
  call), the pages (legacy's rule of "I", "II", "III", one more "I" a page;
  their count from nui_limits.SAFEBOX_PAGE_COUNT_MAX), the close command;
- the password dialog: the title and the chat command the Interface sets,
  the secret field, OK and Enter send the command with the password, Cancel
  and Escape close it;
- the change-password dialog: three secret fields, Tab and Enter move the
  focus old, new, check, old; Enter in the check field or OK compares the
  new fields: a mismatch shows the dialog kit's message (D13), its OK clears
  the new fields; a match sends legacy's change command.

A password never enters a model: the fields' proxies read the document's
field at the accept (nui.Window.get_value). Legacy's per-frame distance rule
is nuigame.WatchLeaveRange's watch, armed in ShowWindow and stopped in Hide;
it sends the close command once where legacy sends it every frame until the
server answers (spec 2.1). The boards exist only while their windows show;
the dialogs are modal and draw above the legacy UI layer (D12), the safebox
below it, as legacy's window lived in it (D3)."""

import localeInfo
import net
import nuigame
import player
import safebox
import ui
import uiPickMoney
import uiSafebox
import uiScriptLocale

import nui
import nui_change_password
import nui_facade
import nui_form_proxies
import nui_hud
import nui_limits
import nui_proxies
import nui_safebox_password
import nui_slots
import nui_windows

DOCUMENT = "nui/windows/safebox/safebox.rml"
KEY = "safebox"
# Legacy's USE_SAFEBOX_LIMIT_RANGE (uisafebox.py:514).
LEAVE_RANGE = 1000
# The uiscript's place (safeboxwindow.py: 100, 20), in dp.
PLACE_LEFT, PLACE_TOP = 100, 20


class _SafeboxBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The safebox's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "safebox"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("cell_press")
	def on_cell_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_events.press(int(index), button)

	@nui.on("cell_release")
	def on_cell_release(self, index, button):
		self._owner._cell_events.release(int(index), button)

	@nui.on("cell_drop")
	def on_cell_drop(self, index):
		self._owner._cell_events.drop(int(index))

	@nui.on("cell_use")
	def on_cell_use(self, index):
		self._owner._cell_events.use(int(index))

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._cell_events.out(int(index))

	@nui.on("page_press")
	def on_page_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_page(int(index))

	@nui.on("change_password_press")
	def on_change_password_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.changePasswordButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.exitButton.click()


class SafeboxWindow(nui_facade.Facade, uiSafebox.SafeboxWindow):
	"""uiSafebox.SafeboxWindow on NovaUI (Interface.wndSafebox)."""

	KEY = KEY
	BOARD = _SafeboxBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiSafebox.SafeboxWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def PLACE(self):
		"""Legacy's place, (100, 20) in dp."""
		return (PLACE_LEFT, PLACE_TOP)

	def nui_model(self):
		limits = self._limits
		return {
			"cells": [nui_slots.empty_cell(i) for i in range(limits.SAFEBOX_PAGE_SIZE)],
			"cols": limits.SAFEBOX_COLUMNS,
			# The loader's SetTableSize(3): one page until the server's size.
			"pages": nui_limits.safebox_pages(3, limits),
			"page_count": 1,
			"page": 0,
			# P14b: the grid's is-attaching (nui_slots.LegacySlotEvents).
			"attaching": False,
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _global(self, slot):
		"""A cell's global safebox position (legacy's __LocalPosToGlobalPos)."""
		return self._SafeboxWindow__LocalPosToGlobalPos(slot)

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.wndItem.cells(), states, picked))

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	def _on_pages(self, button=None):
		"""The page buttons: their labels (legacy's texts) and the one down."""
		buttons = getattr(self, "pageButtonList", [])
		page = 0
		for index, entry in enumerate(buttons):
			if getattr(entry, "down", False):
				page = index
				break
		self.nui_set(pages=[{"index": i, "label": nui.plain_text(entry.GetText())} for i, entry in enumerate(buttons)],
		             page_count=len(buttons), page=page)

	def _press_page(self, index):
		"""A press on a page button as CRadioButton takes it: the button that is
		down ignores it; another goes down and calls its event (SelectPage)."""
		buttons = getattr(self, "pageButtonList", [])
		if not (0 <= index < len(buttons)):
			return
		button = buttons[index]
		if button.down or not button.enabled:
			return
		button.Down()
		button.click()

	# --- the loader (uisafebox.py:238-288, on proxies) -------------------------------------

	def _SafeboxWindow__LoadWindow(self):
		if self.isLoaded == 1:
			return

		self.isLoaded = 1

		# The uiscript's style (safeboxwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits

		## Item
		wndItem = nui_form_proxies.TypedSlotWindowProxy(
			range(limits.SAFEBOX_PAGE_SIZE), self._on_cells, cols=limits.SAFEBOX_COLUMNS, rows=limits.SAFEBOX_PAGE_ROWS,
			positions=self._global, slot_type=player.SLOT_TYPE_SAFEBOX)
		wndItem.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndItem.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndItem.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndItem.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		wndItem.Show()

		## PickMoneyDialog (the dialog kit's facade while the dialogs flag is on)
		dlgPickMoney = uiPickMoney.PickMoneyDialog()
		dlgPickMoney.LoadDialog()
		dlgPickMoney.SetAcceptEvent(ui.__mem_func__(self.OnPickMoney))
		dlgPickMoney.Hide()

		## ChangePasswrod: the NovaUI dialog, or legacy's where it cannot load
		dlgChangePassword = nui_windows.make(KEY, uiSafebox.ChangePasswordDialog, ChangePasswordDialog)
		dlgChangePassword.LoadDialog()
		dlgChangePassword.Hide()

		## Close Button
		self.titleBar = nui_proxies.BoardProxy(161, 23)
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.changePasswordButton = nui_proxies.ButtonProxy()
		self.changePasswordButton.SetEvent(ui.__mem_func__(self.OnChangePassword))
		self.exitButton = nui_proxies.ButtonProxy()
		self.exitButton.SetEvent(ui.__mem_func__(self.Close))

		self.wndItem = wndItem
		self.dlgPickMoney = dlgPickMoney
		self.dlgChangePassword = dlgChangePassword
		self.wndBoard = nui_proxies.BoardProxy(self.BOX_WIDTH, 250)

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(
			wndItem, on_states=self._on_states, on_attaching=self._on_attaching))

		## Initialize
		self.SetTableSize(3)
		self.RefreshSafeboxMoney()

	def _SafeboxWindow__MakePageButton(self, pageCount):
		"""Legacy's page buttons as ButtonProxys: "I", "II", ... (one more "I"
		each), page 0 down; the board lays them out."""
		self.curPageIndex = 0
		self.pageButtonList = []

		text = "I"
		for i in range(pageCount):
			button = nui_proxies.ButtonProxy(self._on_pages)
			button.SetText(text)
			button.SetEvent(lambda arg=i: self.SelectPage(arg))
			button.Show()

			self.pageButtonList.append(button)

			text += "I"

		self.pageButtonList[0].Down()

	# --- what NovaUI changes (P16 spec 5.4.3) -----------------------------------------

	def SetTableSize(self, size):
		"""Legacy's, with the page count from the limits module (legacy's
		min(3, ...); OLD's 5 at the foundation) and no window size: the board
		lays itself out, the legacy window stays 0 x 0."""
		limits = self._limits
		pageCount = len(nui_limits.safebox_pages(size, limits))
		rows = limits.SAFEBOX_PAGE_ROWS

		self._SafeboxWindow__MakePageButton(pageCount)

		self.wndItem.ArrangeSlot(0, limits.SAFEBOX_COLUMNS, rows, 32, 32, 0, 0)
		self.wndItem.RefreshSlot()
		self.wndItem.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)

		self.wndBoard.SetSize(self.BOX_WIDTH, 130 + 32 * rows)
		self._on_pages()

	def SelectPage(self, index):
		uiSafebox.SafeboxWindow.SelectPage(self, index)
		self._on_pages()

	def ShowWindow(self, size):
		uiSafebox.SafeboxWindow.ShowWindow(self, size)
		nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self.Close), False)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			nuigame.StopLeaveRange(KEY)


# --- the password dialogs ------------------------------------------------------------------------

class _DialogFacade(nui_facade.Facade):
	"""What the two password dialogs add to the facade: their boards are
	modals (the scrim centers them, as legacy's ShowDialog and Open center
	the window); their fields are FieldProxys whose text, focus and limit
	reach the document, and whose GetText reads the document's field."""

	def _value(self, field_id):
		board = self.board()
		return board.get_value(field_id) if board is not None else None

	def _field(self, field_id, maximum):
		field = nui_form_proxies.FieldProxy(field_id, self._on_field)
		field.reader = lambda: self._value(field_id)
		field.SetMax(maximum)
		return field

	def _fields(self):
		return ()

	def _on_field(self, field, what):
		board = self.board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			board.set_value(field.field_id, field.text, caret="end")
		elif what == "focus":
			board.focus(field.field_id)

	def _keep_board(self, board):
		"""Nothing to keep: the scrim centers the dialog at each show."""

	def Show(self):
		nui_facade.Facade.Show(self)
		board = self.board()
		if board is None:
			return
		# The fields as legacy left them (a text set while hidden), and the
		# focus legacy gave before the show (ShowDialog, Open).
		for field in self._fields():
			if field.text:
				board.set_value(field.field_id, field.text, caret="end")
		for field in self._fields():
			if field.focused:
				board.focus(field.field_id)
				break


class PasswordDialog(_DialogFacade, uiSafebox.PasswordDialog):
	"""uiSafebox.PasswordDialog on NovaUI (Interface.dlgPassword: the
	safebox's and the mall's password)."""

	KEY = "safebox-password"
	BOARD = nui_safebox_password.SafeboxPasswordBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiSafebox.PasswordDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"title": nui.plain_text(uiScriptLocale.PASSWORD_TITLE),
		        "max": self._limits.SAFEBOX_PASSWORD_MAX_LEN}

	def _fields(self):
		field = getattr(self, "passwordValue", None)
		return (field,) if field is not None else ()

	def _on_title(self, text):
		self.nui_set(title=nui.plain_text(text))

	# --- the loader (uisafebox.py:22-45, on proxies) -----------------------------------------

	def _PasswordDialog__LoadDialog(self):
		# The uiscript's style (passworddialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.passwordValue = self._field(nui_safebox_password.FIELD, self._limits.SAFEBOX_PASSWORD_MAX_LEN)
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.titleName = nui_proxies.TextProxy(self._on_title, uiScriptLocale.PASSWORD_TITLE)
		self.titleBar = nui_proxies.BoardProxy(234, 23)
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.CloseDialog))

		self.passwordValue.OnIMEReturn = self.OnAccept
		self.passwordValue.OnPressEscapeKey = self.OnCancel
		self.acceptButton.SetEvent(ui.__mem_func__(self.OnAccept))
		self.cancelButton.SetEvent(ui.__mem_func__(self.OnCancel))
		# MR-17: Set secret mode for password input
		self.passwordValue.SetSecretMode(1)
		# MR-17: -- END OF -- Set secret mode for password input


class ChangePasswordDialog(_DialogFacade, uiSafebox.ChangePasswordDialog):
	"""uiSafebox.ChangePasswordDialog on NovaUI (SafeboxWindow.dlgChangePassword)."""

	KEY = "change-password"
	BOARD = nui_change_password.ChangePasswordBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiSafebox.ChangePasswordDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"max": self._limits.SAFEBOX_PASSWORD_MAX_LEN}

	def _fields(self):
		return tuple(field for field in (getattr(self, name, None) for name in ("oldPassword", "newPassword",
		                                                                         "newPasswordCheck"))
		             if field is not None)

	# --- the loaders (uisafebox.py:87-133, on proxies) ---------------------------------------

	def _ChangePasswordDialog__LoadDialog(self):
		"""The mismatch message: the dialog kit's message (popupdialog.py on
		uiCommon.PopupDialog, D13)."""
		self.dlgMessage = nui_form_proxies.MessageWindowProxy()
		self.dlgMessage.GetChild("message").SetText(localeInfo.SAFEBOX_WRONG_PASSWORD)
		self.dlgMessage.GetChild("accept").SetEvent(ui.__mem_func__(self.OnCloseMessageDialog))

	def LoadDialog(self):
		# The uiscript's style (changepassworddialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		maximum = self._limits.SAFEBOX_PASSWORD_MAX_LEN
		self.acceptButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.titleBar = nui_proxies.BoardProxy(204, 23)
		self.acceptButton.SetEvent(ui.__mem_func__(self.OnAccept))
		self.cancelButton.SetEvent(ui.__mem_func__(self.OnCancel))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnCancel))
		oldPassword = self._field(nui_change_password.OLD, maximum)
		newPassword = self._field(nui_change_password.NEW, maximum)
		newPasswordCheck = self._field(nui_change_password.CHECK, maximum)

		oldPassword.SetTabEvent(lambda arg=1: self.OnNextFocus(arg))
		newPassword.SetTabEvent(lambda arg=2: self.OnNextFocus(arg))
		newPasswordCheck.SetTabEvent(lambda arg=3: self.OnNextFocus(arg))
		oldPassword.SetReturnEvent(lambda arg=1: self.OnNextFocus(arg))
		newPassword.SetReturnEvent(lambda arg=2: self.OnNextFocus(arg))
		newPasswordCheck.SetReturnEvent(ui.__mem_func__(self.OnAccept))
		oldPassword.OnPressEscapeKey = self.OnCancel
		newPassword.OnPressEscapeKey = self.OnCancel
		newPasswordCheck.OnPressEscapeKey = self.OnCancel

		# MR-17: Set secret mode for password input
		oldPassword.SetSecretMode(1)
		newPassword.SetSecretMode(1)
		newPasswordCheck.SetSecretMode(1)
		# MR-17: -- END OF -- Set secret mode for password input

		self.oldPassword = oldPassword
		self.newPassword = newPassword
		self.newPasswordCheck = newPasswordCheck
