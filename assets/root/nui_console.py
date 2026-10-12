"""NovaUI developer console (nui/windows/console/console.rml).

While the "console" window flag is on, the game window makes ConsoleWindow
below through nui_windows.make() instead of consoleModule.ConsoleWindow:
the facade of the legacy window, with its name, constructor, methods and
constants. It opens exactly where legacy's does: game.ShowConsole (the ","
key) in debug mode or after the server's ConsoleEnable.

The command set is legacy's by construction: the facade holds legacy's
command object (consoleModule.Console, whose output is this facade) and
fills its command table with legacy's own ConsoleWindow.InitFunction, so
every command does what it does in legacy and prints through Print().
ProcessCommand is legacy's with one fix: `help`, `help <name>` and `?`
print the command list and a command's help, where legacy raises
UnboundLocalError under Python 3 (it assigns the name `list` locally, and
reads `__func__` of a plain function). game.py reads Console.collision
every frame, an attribute read.

The board is a band at the top of the screen, as wide as the screen: the
last 50 lines in nui-text (the output is file names and game data, shown as
written, tags included), the newest at the bottom, a field for the command
and a resize handle for the height. Enter with text runs the command and
empties the field; Enter on an empty field and Escape close the console
(the lines stay). The document exists only while the console shows
(nui_hud.OnDemand); there is no OnRender."""

import consoleModule
import net
import wndMgr

import nui
import nui_hud

DOCUMENT = "nui/windows/console/console.rml"
FIELD = "console-field"
DEFAULT_HEIGHT = 200


class ConsoleBoard(nui.Window):
	"""The console's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "console"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		model = getattr(self._owner, "nui_model", None)
		if model is not None:
			return model()
		return {"lines": [], "width": "0.00", "height": "%.2f" % DEFAULT_HEIGHT}

	def on_scale_changed(self, scale):
		self._owner.nui_scale_changed()

	# The field's keydown (element_on), through the board, so the runtime
	# that holds it keeps no facade alive.
	def nui_key(self, event):
		return self._owner.nui_key(event)

	@nui.on("submit")
	def on_submit(self, value, linebreak):
		self._owner.nui_submit(value, linebreak)

	@nui.on("resized")
	def on_resized(self, width, height):
		self._owner.nui_resized(width, height)


class ConsoleWindow(nui_hud.LayoutCalls):
	"""consoleModule.ConsoleWindow on NovaUI (GameWindow.console)."""

	NUI_FACADE = True
	KEY = "console"

	BACK_GROUND_COLOR = consoleModule.ConsoleWindow.BACK_GROUND_COLOR
	EDIT_LINE_COLOR = consoleModule.ConsoleWindow.EDIT_LINE_COLOR
	BUTTON_COLOR = consoleModule.ConsoleWindow.BUTTON_COLOR
	HEIGHT = 200
	LINE_STEP = 15
	MAX_LINE_COUNT = 50

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.TextList = []
		self.lineIds = []
		self.nextLineId = 1
		self.game = 0
		self.size = (wndMgr.GetScreenWidth(), DEFAULT_HEIGHT)   # SetConsoleSize's (pixels, legacy height)
		self.heightDp = None    # the height a resize left, in dp
		self.Console = consoleModule.Console(self)
		self.functionDict = {}
		consoleModule.ConsoleWindow.InitFunction(self)

		self.demand = None
		self.loaded = False
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board)
			self.loaded = self.demand.probe()
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	# --- the model ----------------------------------------------------------------

	def _lines(self):
		return [{"id": line_id, "text": str(text)} for line_id, text in zip(self.lineIds, self.TextList)]

	def _size_dp(self):
		"""(width, height) in dp: the screen's width (SetConsoleSize's pixels
		at the scale in use) and the height (legacy's 200, kept in dp so the
		band holds the same lines at every scale, or what a resize left)."""
		s = nui.get_scale() or 1.0
		width = self.size[0] / s
		height = self.heightDp if self.heightDp is not None else float(self.size[1])
		return width, height

	def nui_model(self):
		width, height = self._size_dp()
		return {"lines": self._lines(), "width": "%.2f" % width, "height": "%.2f" % height}

	def _board(self):
		return self.demand.board() if self.demand is not None else None

	def _make_board(self):
		return ConsoleBoard(self)

	def _restore_board(self, board):
		board.set(**self.nui_model())
		board.element_on(FIELD, "keydown", board.nui_key)

	# --- the game window's calls (consolemodule.py:591-905) -------------------------------

	def BindGameClass(self, game):
		self.Console.BindGameClass(game)

	def Close(self):
		self.Console.Close()
		self.nui_discard()

	def SetConsoleSize(self, width, height):
		self.size = (width, height)
		board = self._board()
		if board is not None:
			board.set(**self.nui_model())

	def UpdatePosition(self):
		"""CSS lays the console out."""
		pass

	def Show(self):
		if self.demand is not None:
			self.demand.show()

	def Hide(self):
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return self.demand is not None and self.demand.is_shown()

	def SetTop(self):
		board = self._board()
		if board is not None:
			board.bring_to_front()

	def OpenWindow(self):
		self.Show()
		board = self._board()
		if board is not None:
			board.focus(FIELD)
		self.Console.RefreshPath()

	def CloseWindow(self):
		self.Hide()

	def ProcessCommand(self, text):
		"""Legacy's (consolemodule.py:746-800); `help`, `help <name>` and `?`
		print what legacy meant them to print."""
		if '/' == text[0]:
			net.SendChatPacket(text)
			return

		Console = self.Console
		Console.Print(">> " + text)

		lstsArg = text.split()
		if len(lstsArg) == 0:
			return

		sCmd = lstsArg[0]

		if sCmd in self.functionDict:
			try:
				self.functionDict[sCmd](self.Console, *lstsArg[1:])
			except Exception as e:
				Console.Print(str(e))
		elif sCmd == 'help' or sCmd == 'h':
			name = lstsArg[1] if len(lstsArg) > 1 else None
			if name in self.functionDict:
				self.__PrintHelp(name, self.functionDict[name], True)
			else:
				for k, v in list(self.functionDict.items()):
					self.__PrintHelp(k, v, False)
				Console.Print("? : All commands list")
				Console.Print("h : Help for all commands")
				Console.Print("h blah : Help for blah")
			Console.Print("")
		elif sCmd == '?':
			names = sorted(self.functionDict.keys())
			Console.ShowNameList(names)

	def __PrintHelp(self, name, func, withArgs):
		"""One command's help line, as legacy formats it: its argument count
		without self (plus one for *args) and its docstring."""
		code = getattr(func, "__code__", None)
		if code is None:
			code = func.__func__.__code__
		argcount = code.co_argcount - 1
		if code.co_flags & 4:
			argcount += 1
		if argcount:
			self.Console.Print("%s(%s) : %s" % (name, argcount, func.__doc__))
			if withArgs:
				self.Console.Print("   arg : %s" % (code.co_varnames[1:argcount + 1],))
		else:
			self.Console.Print("%s : %s" % (name, func.__doc__))

	def InitFunction(self):
		consoleModule.ConsoleWindow.InitFunction(self)

	def AddFunction(self, cmd, func):
		self.functionDict[cmd] = func

	def Print(self, text):
		self.TextList.append(text)
		self.lineIds.append(self.nextLineId)
		self.nextLineId += 1

		count = len(self.TextList)
		if count > self.MAX_LINE_COUNT:
			del self.TextList[:count - self.MAX_LINE_COUNT]
			del self.lineIds[:count - self.MAX_LINE_COUNT]

		board = self._board()
		if board is not None:
			board.set(lines=self._lines())

	# --- the board's events -------------------------------------------------------------

	def nui_submit(self, value, linebreak):
		"""Enter in the field (consolemodule.py ConsoleEditLine.OnIMEReturn):
		a command runs, an empty line closes the console; the field empties."""
		if not linebreak:
			return
		text = value if isinstance(value, str) else ""
		if len(text) > 0:
			self.ProcessCommand(text)
		else:
			self.CloseWindow()
		board = self._board()
		if board is not None:
			board.set_value(FIELD, "")

	def nui_key(self, event):
		"""Escape in the field: emptied, and the console closes
		(ConsoleEditLine.OnPressEscapeKey). Every other key goes on."""
		if event.get("key_identifier") != nui.KEY_ESCAPE:
			return None
		board = self._board()
		if board is not None:
			board.set_value(FIELD, "")
		self.CloseWindow()
		return True

	def nui_resized(self, width, height):
		try:
			self.heightDp = float(height)
		except (TypeError, ValueError):
			return
		board = self._board()
		if board is not None:
			board.set(height="%.2f" % self.heightDp)

	def nui_scale_changed(self):
		"""The width follows the screen at the new scale."""
		board = self._board()
		if board is not None:
			board.set(width=self.nui_model()["width"])
