"""Tests for the NovaUI virtual keyboard (assets/root/nui_virtual_keyboard.py):
python3 -B -m unittest nui_virtual_keyboard_test (from tools/).

Plain CPython over the stand-ins of nui_test_support. The legacy keyboard
code (intrologin.Suffle and LoginWindow's __VirtualKeyboard_* methods) is
compiled from intrologin.py itself, so the key labels are compared with
what the legacy keyboard shows."""
import ast
import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402
import nui_login_test  # noqa: E402

INTROLOGIN = os.path.join(support.ROOT, "intrologin.py")
LOCALE = nui_login_test.keyboard_locale()


class Recorder(object):
    """app.GetRandom with a recorded, repeatable sequence."""

    def __init__(self, seed=3):
        self.seed = seed
        self.calls = []

    def __call__(self, low, high):
        self.calls.append((low, high))
        self.seed = (self.seed * 1103515245 + 12345) % 2147483648
        return low + self.seed % (high - low + 1)


def compile_legacy(app):
    """intrologin.Suffle and a LegacyKeys class with the __VirtualKeyboard_*
    methods, over stand-in key windows."""
    with open(INTROLOGIN, encoding="utf-8") as file:
        source = file.read()
    tree = ast.parse(source)
    lines = source.splitlines()
    suffle = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "Suffle")
    window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LoginWindow")
    methods = [node for node in window.body if isinstance(node, ast.FunctionDef) and node.name.startswith("__VirtualKeyboard_")]
    body = []
    for node in methods:
        body.extend(lines[node.lineno - 1:node.end_lineno])
        body.append("")

    class Key(object):
        def __init__(self):
            self.text = None
            self.ButtonText = support.Widget()

        def SetEvent(self, *args):
            pass

        def SetText(self, text):
            self.text = text

    class KeysBase(object):
        def __init__(self):
            self.keys = {"key_%d" % index: Key() for index in range(1, 47)}
            self.virtualKeyboardMode = "ALPHABET"
            self.virtualKeyboardIsUpper = False

        def GetChild2(self, name):
            return self.keys.get(name)

        def labels(self):
            return [self.keys["key_%d" % index].text for index in range(1, 47)]

    namespace = {"app": app, "localeInfo": LOCALE, "ime": support.stub_module("ime"),
                 "VIRTUAL_KEYBOARD_RAND_KEY": True, "VIRTUAL_KEYBOARD_NUM_KEYS": 46, "KeysBase": KeysBase}
    LOCALE.UI_DEF_FONT = "font"
    LOCALE.UI_DEF_FONT_LARGE = "large"
    code = "\n".join(lines[suffle.lineno - 1:suffle.end_lineno]) + "\n\nclass LoginWindow(KeysBase):\n" + "\n".join(body) + "\n"
    exec(compile(code, INTROLOGIN, "exec"), namespace)
    return namespace["Suffle"], namespace["LoginWindow"]


def raw_labels(keyboard):
    """The characters the 46 keys type, as the legacy keys show them."""
    return [keyboard._keys[i] if i < len(keyboard._keys) else " " for i in range(46)]


class Board(object):
    """The login board as the keyboard sees it: type_text."""

    def __init__(self, typed=True):
        self.typed = []
        self.answer = typed

    def type_text(self, text):
        self.typed.append(text)
        return self.answer


class KeyboardTest(unittest.TestCase):
    def setUp(self):
        self.state = support.NuiState()
        self.random = Recorder()
        self.sounds = []
        self.app = support.stub_module("app", GetRandom=self.random)
        self.modules = support.Modules(
            nui=support.make_nui(self.state), app=self.app, localeInfo=LOCALE,
            snd=support.stub_module("snd", PlaySound=self.sounds.append))
        self.addCleanup(self.modules.restore)
        self.m = self.modules.load("nui_virtual_keyboard")
        self.board = Board()

    def make(self):
        return self.m.VirtualKeyboard(self.board)

    def legacy(self):
        """The legacy keyboard after the same shuffles: a fresh random
        sequence with the same seed, in the legacy order."""
        legacy_random = Recorder()
        suffle, keys = compile_legacy(support.stub_module("app", GetRandom=legacy_random))
        window = keys()
        window.VIRTUAL_KEY_ALPHABET_UPPERS = suffle(LOCALE.VIRTUAL_KEY_ALPHABET_UPPERS)
        window.VIRTUAL_KEY_ALPHABET_LOWERS = "".join([LOCALE.VIRTUAL_KEY_ALPHABET_LOWERS[LOCALE.VIRTUAL_KEY_ALPHABET_UPPERS.index(e)]
                                                      for e in window.VIRTUAL_KEY_ALPHABET_UPPERS])
        window.VIRTUAL_KEY_SYMBOLS = suffle(LOCALE.VIRTUAL_KEY_SYMBOLS)
        window.VIRTUAL_KEY_NUMBERS = suffle(LOCALE.VIRTUAL_KEY_NUMBERS)
        window._LoginWindow__VirtualKeyboard_SetAlphabetMode()
        return window, legacy_random


class Shuffle(KeyboardTest):
    def test_the_shuffle_calls_get_random_exactly_as_suffle_does(self):
        suffle, _ = compile_legacy(support.stub_module("app", GetRandom=Recorder()))
        legacy_random = Recorder()
        suffle, _ = compile_legacy(support.stub_module("app", GetRandom=legacy_random))
        for text in (LOCALE.VIRTUAL_KEY_ALPHABET_UPPERS, LOCALE.VIRTUAL_KEY_SYMBOLS, "ab"):
            ours = self.m.shuffle(text)
            theirs = suffle(text)
            self.assertEqual(ours, theirs)
        self.assertEqual(self.random.calls, legacy_random.calls)

    def test_a_keyboard_shuffles_like_the_legacy_window_and_lower_case_follows_upper_case(self):
        keyboard = self.make()
        legacy, legacy_random = self.legacy()
        self.assertEqual(self.random.calls, legacy_random.calls, "the same GetRandom calls, in order")
        self.assertEqual(raw_labels(keyboard), legacy.labels())
        uppers = keyboard._uppers
        for upper, lower in zip(uppers, keyboard._lowers):
            self.assertEqual(LOCALE.VIRTUAL_KEY_ALPHABET_LOWERS[LOCALE.VIRTUAL_KEY_ALPHABET_UPPERS.index(upper)], lower)

    def test_the_rows_hold_12_12_11_and_11_keys_numbered_1_to_46(self):
        rows = self.make().model["rows"]
        self.assertEqual([len(row) for row in rows], [12, 12, 11, 11])
        self.assertEqual([key["index"] for row in rows for key in row], list(range(1, 47)))


class Modes(KeyboardTest):
    def test_every_sequence_of_shift_and_symbol_presses_shows_the_legacy_labels(self):
        toggles = {"shift": ("_LoginWindow__VirtualKeyboard_SetUpperMode", "_LoginWindow__VirtualKeyboard_SetLowerMode"),
                   "symbols": ("_LoginWindow__VirtualKeyboard_SetSymbolMode", "_LoginWindow__VirtualKeyboard_SetAlphabetMode")}
        checked = 0
        for length in range(1, 5):
            for sequence in itertools.product(("shift", "symbols"), repeat=length):
                self.random.seed = 3
                keyboard = self.make()
                legacy, _ = self.legacy()
                down = {"shift": False, "symbols": False}
                for name in sequence:
                    keyboard.fire("special", name, 0)
                    down[name] = not down[name]
                    getattr(legacy, toggles[name][0 if down[name] else 1])()
                    self.assertEqual(raw_labels(keyboard), legacy.labels(), sequence)
                    self.assertEqual(keyboard.labels(), [support.make_nui(self.state).plain_text(c) for c in legacy.labels()])
                self.assertEqual(keyboard.model["upper"], down["shift"], sequence)
                self.assertEqual(keyboard.model["mode"], "symbol" if down["symbols"] else "alphabet", sequence)
                checked += 1
        self.assertEqual(checked, 2 + 4 + 8 + 16)

    def test_unused_keys_show_a_space(self):
        keyboard = self.make()
        keyboard.fire("special", "symbols", 0)
        labels = keyboard.labels()
        self.assertEqual(labels[len(LOCALE.VIRTUAL_KEY_SYMBOLS):], [" "] * (46 - len(LOCALE.VIRTUAL_KEY_SYMBOLS)))

    def test_labels_are_plain_text(self):
        keyboard = self.make()
        keyboard.fire("special", "symbols", 0)
        labels = keyboard.labels()
        self.assertIn("@\u2060", labels, "the @ key cannot start a locale key")


class Typing(KeyboardTest):
    def test_a_press_types_its_label_through_the_board_then_plays_type(self):
        keyboard = self.make()
        label = keyboard._keys[4]
        keyboard.fire("press", 5, 0)
        self.assertEqual(self.board.typed, [label])
        self.assertEqual(self.sounds, ["sound/ui/type.wav"])

    def test_an_unused_key_types_a_space(self):
        keyboard = self.make()
        keyboard.fire("special", "symbols", 0)
        keyboard.fire("press", 46, 0)
        self.assertEqual(self.board.typed, [" "])

    def test_the_right_button_does_nothing(self):
        keyboard = self.make()
        keyboard.fire("press", 5, 1)
        keyboard.fire("special", "shift", 2)
        self.assertEqual(self.board.typed, [])
        self.assertIs(keyboard.model["upper"], False)
        self.assertEqual(self.sounds, [])

    def test_space_enter_and_backspace_type_their_keys(self):
        keyboard = self.make()
        for name in ("space", "enter", "backspace"):
            keyboard.fire("special", name, 0)
        self.assertEqual(self.board.typed, [" ", "\n", "\b"])
        self.assertEqual(self.sounds, ["sound/ui/type.wav", "sound/ui/click.wav", "sound/ui/type.wav"])

    def test_nothing_typed_plays_nothing(self):
        self.board.answer = False
        keyboard = self.make()
        keyboard.fire("press", 1, 0)
        self.assertEqual(self.sounds, [])

    def test_the_fixture_shows_with_any_owner(self):
        import json
        path = os.path.join(support.ROOT, "..", "nui", "nui", "windows", "virtual-keyboard", "virtual-keyboard.fixture.json")
        with open(path, encoding="utf-8") as file:
            fixture = json.load(file)["virtual_keyboard"]
        keyboard = self.m.VirtualKeyboard(Board())
        self.assertEqual(set(keyboard.model), set(fixture))
        self.assertTrue(keyboard.set(**fixture))
        self.assertEqual([key["label"] for row in fixture["rows"] for key in row], list(LOCALE.VIRTUAL_KEY_ALPHABET_LOWERS),
                         "the fixture is the unshuffled lower case set")


if __name__ == "__main__":
    unittest.main()
