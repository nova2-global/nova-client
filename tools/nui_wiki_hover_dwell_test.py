"""The wiki's hover preview and a list scrolled under a still pointer (r39:
the frame rate fell to near 0 over the Weapon Costumes list). Every row the
pointer met made a model, up to 323 ms each. The hover preview now asks the
client to wait until the pointer has rested on a row (modelpreview.SetDwell,
PythonModelPreview.h); the page's own preview keeps showing at once. A client
without SetDwell hovers as before."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_test as base  # noqa: E402

WOLF = 8002


class HoverDwell(base.WikiTest):
    def hovered(self, dwell=True):
        world, window = self.world()
        previews = world.game.modules["modelpreview"]
        if dwell:
            previews.SetDwell = lambda name, ms: previews.calls.append(("SetDwell", name, ms))
        elif hasattr(previews, "SetDwell"):
            del previews.SetDwell
        with world.game, w4.quiet():
            window.Open()
            window.search("wolf")
        del previews.calls[:]
        return world, window, previews.calls

    def test_the_hover_preview_waits_for_the_pointer_to_rest(self):
        world, window, calls = self.hovered()
        with world.game, w4.quiet():
            window.over_row(0)
        names = [c[0] for c in calls if c[1] == "wiki_hover"]
        self.assertIn("SetDwell", names)
        self.assertLess(names.index("SetDwell"), names.index("Select"), "the dwell is set before the request")
        dwell = [c[2] for c in calls if c[0] == "SetDwell"][0]
        self.assertTrue(150 <= dwell <= 200, dwell)
        self.assertTrue(w4.board(window).model["hover_view"], "the box shows (empty) while the client waits")

    def test_the_pages_own_preview_does_not_wait(self):
        world, window, calls = self.hovered()
        with world.game, w4.quiet():
            window.OpenMob(WOLF)
        self.assertIn(("Select", "wiki", WOLF), calls)
        self.assertFalse([c for c in calls if c[0] == "SetDwell" and c[1] == "wiki"])

    def test_a_client_without_dwell_still_hovers(self):
        world, window, calls = self.hovered(dwell=False)
        with world.game, w4.quiet():
            window.over_row(0)
        self.assertIn(("Select", "wiki_hover", WOLF), calls)
        self.assertTrue(w4.board(window).model["hover_view"])


if __name__ == "__main__":
    unittest.main()
