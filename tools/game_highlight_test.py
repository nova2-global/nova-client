"""Tests for game.GameWindow.BINARY_Highlight_Item (assets/root/game.py,
NOVA-160): python3 -B -m unittest game_highlight_test (from tools/).

The client's RecvItemSetPacket calls it on the game phase window when the
server marks an item set to be highlighted (NEW's server does so for a dragon
soul stone). GameWindow.Close() drops the Interface (self.interface=None),
but the closed window stays the C++ phase window until GameWindow.__del__
runs net.ClearPhaseWindow, so an item set arriving in between (a relog, the
character select, a warp) reached a missing Interface and raised
AttributeError. OLD guards the call (old/client_pack/source/root/game.py
2775-2777); so does NEW now.

The method is compiled from game.py's own source (the compiled() pattern of
nui_dragon_soul_test) over no game modules, since it reaches none."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402


def compiled(file_name, class_name, names, namespace=None):
    """A class with the methods `names` of a root module's class, compiled
    from its own source (the legacy code, unchanged) over `namespace`."""
    source = support.source_of(file_name, names, inside=class_name)
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(namespace or {})
    exec(compile("class %s(object):\n%s\n" % (class_name, body), file_name, "exec"), namespace)
    return namespace[class_name]


class HighlightItem(unittest.TestCase):
    def window(self, interface):
        window = compiled("game.py", "GameWindow", ("BINARY_Highlight_Item",))()
        window.interface = interface
        return window

    def test_a_closed_game_window_drops_the_highlight(self):
        window = self.window(None)
        self.assertIsNone(window.BINARY_Highlight_Item(1, 5))

    def test_an_open_game_window_hands_it_to_the_interface(self):
        calls = []
        interface = types.SimpleNamespace(Highligt_Item=lambda *args: calls.append(args))
        self.window(interface).BINARY_Highlight_Item(1, 5)
        self.assertEqual(calls, [(1, 5)])

    def test_close_is_what_drops_the_interface(self):
        """The guard is for the state Close() leaves: no Interface, the
        window itself still alive."""
        close = support.source_of("game.py", ("Close",), inside="GameWindow")
        self.assertRegex(close, r"self\.interface\s*=\s*None")


if __name__ == "__main__":
    unittest.main()
