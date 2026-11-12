"""Tests of the client's persistent answer cache (assets/root/datacache.py):
python3 -B -m unittest datacache_test (from tools/).

The dungeon drops (uiTimerWindow.DUNGEON_DROP), the chest contents
(constInfo.CHESTS_PREVIEW) and the wiki pages (nui_wiki.ANSWERS) are tables
of one shared module that keeps them in memory and on disk, under config/,
keyed by the server address and the server's data version
(GC::DATA_VERSION). The server computes the version over every table these
answers come from, so the rule players see is:

- a relog to a server whose data did not change asks the server nothing it
  already answered;
- a relog after the data changed asks again;
- a reload the server pushes while playing drops the old answers at once.

Until a version is known (an older server, or before the packet arrives) the
answers stay in memory only."""

import ast
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_game_support as support  # noqa: E402
import nui_test_support as base  # noqa: E402

ROOT = support.ROOT
SERVER = "192.168.0.10"
V1, V2 = 0x1111222233334444, 0xAAAABBBBCCCCDDDD


def fresh_module():
    """datacache as a new client process starts it."""
    return base.load_module("datacache", os.path.join(ROOT, "datacache.py"))


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="datacache_test_")
        self.addCleanup(shutil.rmtree, self.folder, True)

    def module(self):
        module = fresh_module()
        module.FOLDER = os.path.join(self.folder, "config", "datacache")
        self.addCleanup(module.begin_session)  # closes its file
        return module

    def files(self):
        path = os.path.join(self.folder, "config", "datacache")
        return sorted(os.listdir(path)) if os.path.isdir(path) else []


# --- the module on its own ------------------------------------------------------------

class MemoryOnly(TempFolder):
    def test_with_no_version_known_answers_stay_in_memory(self):
        cache = self.module()
        table = cache.Table("chest_drop")
        table[50011] = [(27992, 5, 30)]
        self.assertEqual(table[50011], [(27992, 5, 30)])
        self.assertEqual(self.files(), [], "nothing is written before the server names its version")

    def test_answers_from_before_the_version_are_dropped_when_it_arrives(self):
        cache = self.module()
        table = cache.Table("chest_drop")
        table[50011] = [(27992, 5, 30)]
        cache.set_version(SERVER, V1)
        self.assertNotIn(50011, table, "an answer of unknown data is not kept under a version")


class Persistence(TempFolder):
    def test_an_answer_is_written_through_and_a_new_process_reads_it(self):
        cache = self.module()
        cache.set_version(SERVER, V1)
        table = cache.Table("chest_drop")
        table[50011] = [(27992, 5, 30), (1, 100000, 15)]
        self.assertEqual(len(self.files()), 1)

        again = self.module()
        again.begin_session()
        later = again.Table("chest_drop")
        again.set_version(SERVER, V1)
        self.assertEqual(later[50011], [(27992, 5, 30), (1, 100000, 15)])

    def test_a_table_made_after_the_version_still_gets_its_answers(self):
        cache = self.module()
        cache.set_version(SERVER, V1)
        cache.Table("wiki")[(0, 11000)] = {"flags": 0, "origins": [(3, 9001)]}

        again = self.module()
        again.set_version(SERVER, V1)
        self.assertEqual(again.Table("wiki")[(0, 11000)], {"flags": 0, "origins": [(3, 9001)]})

    def test_appended_rows_are_folded_again_when_read(self):
        def fold(table, key, row):
            table.setdefault(key, []).append(row)

        cache = self.module()
        cache.set_version(SERVER, V1)
        table = cache.Table("dungeon_drop", fold=fold)
        table.append(0, (2598, 1, 27001, 3, 800000))
        table.append(0, (2598, 1, 27002, 1, 500000))
        self.assertEqual(table[0], [(2598, 1, 27001, 3, 800000), (2598, 1, 27002, 1, 500000)])

        again = self.module()
        again.set_version(SERVER, V1)
        self.assertEqual(again.Table("dungeon_drop", fold=fold)[0],
                         [(2598, 1, 27001, 3, 800000), (2598, 1, 27002, 1, 500000)])

    def test_clear_empties_memory_only(self):
        cache = self.module()
        cache.set_version(SERVER, V1)
        table = cache.Table("chest_drop")
        table[50011] = [(27992, 5, 30)]
        table.clear()
        self.assertEqual(dict(table), {})
        cache.begin_session()
        cache.set_version(SERVER, V1)
        self.assertEqual(table[50011], [(27992, 5, 30)])

    def test_a_damaged_file_loses_only_what_it_damaged(self):
        cache = self.module()
        cache.set_version(SERVER, V1)
        table = cache.Table("chest_drop")
        table[1] = [(1, 1, 1)]
        table[2] = [(2, 2, 2)]
        path = os.path.join(cache.FOLDER, self.files()[0])
        with open(path, "ab") as handle:
            handle.write(b"0000ffff\x00\x01garbage")
        again = self.module()
        again.set_version(SERVER, V1)
        self.assertEqual(dict(again.Table("chest_drop")), {1: [(1, 1, 1)], 2: [(2, 2, 2)]})

    def test_a_file_that_is_no_cache_is_ignored(self):
        cache = self.module()
        os.makedirs(cache.FOLDER)
        name = cache.file_name(SERVER, V1)
        with open(os.path.join(cache.FOLDER, name), "wb") as handle:
            handle.write(b"not a cache at all")
        cache.set_version(SERVER, V1)
        table = cache.Table("chest_drop")
        self.assertEqual(dict(table), {})
        table[1] = [(1, 1, 1)]
        again = self.module()
        again.set_version(SERVER, V1)
        self.assertEqual(dict(again.Table("chest_drop")), {1: [(1, 1, 1)]})


class Versions(TempFolder):
    def test_another_version_of_the_same_server_is_deleted(self):
        cache = self.module()
        table = cache.Table("chest_drop")
        cache.set_version(SERVER, V1)
        table[1] = [(1, 1, 1)]
        cache.set_version(SERVER, V2)
        table[2] = [(2, 2, 2)]
        self.assertEqual(self.files(), [cache.file_name(SERVER, V2)])

    def test_another_server_keeps_its_own_file(self):
        cache = self.module()
        table = cache.Table("chest_drop")
        cache.set_version(SERVER, V1)
        table[1] = [(1, 1, 1)]
        cache.set_version("10.0.0.7", V2)
        self.assertEqual(dict(table), {})
        table[2] = [(2, 2, 2)]
        self.assertEqual(self.files(), sorted([cache.file_name(SERVER, V1), cache.file_name("10.0.0.7", V2)]))
        cache.set_version(SERVER, V1)
        self.assertEqual(dict(table), {1: [(1, 1, 1)]})

    def test_the_file_name_holds_the_server_and_the_version(self):
        cache = self.module()
        name = cache.file_name("my.server:13000/x", V1)
        self.assertIn("%016x" % V1, name)
        self.assertNotIn("/", name)
        self.assertNotIn(":", name)
        self.assertNotEqual(cache.file_name("a", V1), cache.file_name("b", V1))

    def test_a_live_push_drops_the_answers_and_the_asked_marks(self):
        cache = self.module()
        cache.set_version(SERVER, V1)
        table = cache.Table("chest_drop")
        table[1] = [(1, 1, 1)]
        asked = cache.asked_set()
        asked.add(1)
        cache.set_version(SERVER, V2)
        self.assertEqual(dict(table), {})
        self.assertEqual(set(asked), set(), "a request made for old data may be made again")

    def test_the_same_version_again_keeps_the_answers(self):
        cache = self.module()
        cache.set_version(SERVER, V1)
        table = cache.Table("chest_drop")
        table[1] = [(1, 1, 1)]
        cache.set_version(SERVER, V1)
        self.assertEqual(dict(table), {1: [(1, 1, 1)]})

    def test_the_number_of_servers_kept_is_capped(self):
        cache = self.module()
        table = cache.Table("chest_drop")
        for n in range(cache.MAX_SERVERS + 3):
            cache.set_version("10.0.0.%d" % n, V1)
            table[n] = [(n, 1, 1)]
        self.assertEqual(len(self.files()), cache.MAX_SERVERS)
        self.assertIn(cache.file_name("10.0.0.%d" % (cache.MAX_SERVERS + 2), V1), self.files())


class SizeCap(TempFolder):
    def test_the_file_never_grows_past_the_cap_and_the_oldest_answers_go_first(self):
        cache = self.module()
        cache.MAX_FILE_BYTES = 4096
        cache.set_version(SERVER, V1)
        table = cache.Table("wiki")
        for n in range(200):
            table[(0, n)] = {"drops": [(n, 1)] * 4}
        path = os.path.join(cache.FOLDER, cache.file_name(SERVER, V1))
        self.assertLessEqual(os.path.getsize(path), cache.MAX_FILE_BYTES)
        self.assertIn((0, 199), table, "the newest answer stays")
        self.assertNotIn((0, 0), table, "the oldest answer went")
        again = self.module()
        again.MAX_FILE_BYTES = 4096
        again.set_version(SERVER, V1)
        self.assertEqual(dict(again.Table("wiki")), dict(table), "disk and memory hold the same answers")

    def test_an_answer_larger_than_the_cap_stays_in_memory_only(self):
        cache = self.module()
        cache.MAX_FILE_BYTES = 1024
        cache.set_version(SERVER, V1)
        table = cache.Table("wiki")
        table[(0, 1)] = {"drops": [(1, 1)] * 1000}
        self.assertIn((0, 1), table)
        again = self.module()
        again.set_version(SERVER, V1)
        self.assertNotIn((0, 1), again.Table("wiki"))


# --- the game's handler ---------------------------------------------------------------

class GameHandler(TempFolder):
    """game.BINARY_DataVersion keys the cache by the address the player
    connected to; GameWindow.__init__ starts a session before anything."""

    def compiled(self, name, scope):
        source = open(os.path.join(ROOT, "game.py"), encoding="utf-8").read()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                exec(compile(ast.Module(body=[node], type_ignores=[]), "game.py", "exec"), scope)
                return scope[name]
        self.fail("game.py has no %s" % name)

    def test_the_handler_sets_the_version_for_the_connected_server(self):
        cache = self.module()
        handler = self.compiled("BINARY_DataVersion", {"datacache": cache})
        game = types.SimpleNamespace(stream=types.SimpleNamespace(GetConnectAddr=lambda: SERVER))
        handler(game, V1)
        self.assertEqual(cache.current(), (cache.server_key(SERVER), V1))

    def test_the_game_window_starts_a_session_first(self):
        source = open(os.path.join(ROOT, "game.py"), encoding="utf-8").read()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ClassDef) and node.name == "GameWindow":
                init = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"][0]
                first = ast.unparse(init.body[0])
                self.assertEqual(first, "datacache.begin_session()")
                return
        self.fail("game.py has no GameWindow")


# --- Eddy's rule, end to end through the three consumers ------------------------------

class Relog(TempFolder):
    """A client process per session: each world loads every module afresh, as
    a client started again would (the strongest case; a relog in the same
    process keeps the module but starts a session the same way)."""

    def session(self, make_world, version):
        world = make_world()
        cache = world.m("datacache")
        cache.FOLDER = os.path.join(self.folder, "config", "datacache")
        self.addCleanup(cache.begin_session)  # closes its file
        cache.begin_session()
        cache.set_version(SERVER, version)
        return world


class DungeonDrops(Relog):
    def world(self):
        import dungeon_timer_support as dts
        world = dts.World(True)
        world.game.state.now = 100.0
        return world

    def open_timer(self, world):
        import nui_w4_world as w4
        window = world.timer()
        with world.game, w4.quiet():
            window.Open()
        return window

    def answer(self, world):
        import nui_w4_world as w4
        with world.game, w4.quiet():
            world.timer_module.add_drop(0, 2598, 1, 27001, 3, 800000)
            world.timer_module.add_drop(0, 2598, 1, 27002, 1, 500000)

    def test_the_same_version_at_relog_asks_nothing(self):
        world = self.session(self.world, V1)
        self.open_timer(world)
        self.assertIn((0,), world.drop_requests())
        self.answer(world)

        world = self.session(self.world, V1)
        window = self.open_timer(world)
        self.assertEqual(world.drop_requests(), [], "the drops are known: no request")
        self.assertEqual(world.timer_module.DUNGEON_DROP[0][2598]["items"], [(27001, 3, 800000), (27002, 1, 500000)])
        import nui_w4_world as w4
        self.assertEqual(w4.board(window).model["drops_state"], "ready")

    def test_a_changed_version_at_relog_asks_again(self):
        world = self.session(self.world, V1)
        self.open_timer(world)
        self.answer(world)

        world = self.session(self.world, V2)
        self.open_timer(world)
        self.assertIn((0,), world.drop_requests())

    def test_a_live_push_drops_the_rows_and_the_next_look_asks_again(self):
        import nui_w4_world as w4
        world = self.session(self.world, V1)
        window = self.open_timer(world)
        self.answer(world)
        asked = len(world.drop_requests())

        world.m("datacache").set_version(SERVER, V2)
        self.assertEqual(dict(world.timer_module.DUNGEON_DROP), {})
        world.game.state.now = 200.0
        with world.game, w4.quiet():
            w4.press(window, "arrow_press", "next", 0)
            world.game.state.now = 300.0
            w4.press(window, "arrow_press", "prev", 0)
        self.assertEqual(world.drop_requests()[asked:].count((0,)), 1, "dungeon 0 is asked again")


class ChestContents(Relog):
    CHEST = 50011
    ROWS = [(27992, 5, 30), (1, 100000, 15)]

    def world(self):
        import nui_chest_drop_test as chest
        import nui_w4_world as w4
        world = w4.World(True, windows="+trade,+chest-drop", setup=chest.items)
        with world.game, w4.quiet():
            world.game.modules["ui"].ScrollWindow = chest._ScrollWindow
            world.game.load("uiChestDrop", "uichestdrop.py")
        return world

    def ask(self, world):
        import nui_w4_world as w4
        mark = len(world.game.log)
        with world.game, w4.quiet():
            world.m("uiChestDrop").request(self.CHEST)
        return [args for name, args in world.calls_since(mark, "net.") if name == "net.SendChestDropInfo"]

    def answer(self, world):
        """game.BINARY_SetChestDropInfo, compiled from game.py over this world's constInfo."""
        source = open(os.path.join(ROOT, "game.py"), encoding="utf-8").read()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef) and node.name == "BINARY_SetChestDropInfo":
                scope = {"constInfo": world.m("constInfo")}
                exec(compile(ast.Module(body=[node], type_ignores=[]), "game.py", "exec"), scope)
                scope["BINARY_SetChestDropInfo"](types.SimpleNamespace(interface=None), self.CHEST, tuple(self.ROWS))
                return
        self.fail("game.py has no BINARY_SetChestDropInfo")

    def test_the_same_version_at_relog_asks_nothing(self):
        world = self.session(self.world, V1)
        self.assertEqual(self.ask(world), [(self.CHEST,)])
        self.answer(world)

        world = self.session(self.world, V1)
        self.assertEqual(self.ask(world), [], "the chest is known: no request")
        self.assertEqual(world.m("constInfo").CHESTS_PREVIEW[self.CHEST], self.ROWS)

    def test_a_changed_version_at_relog_asks_again(self):
        world = self.session(self.world, V1)
        self.ask(world)
        self.answer(world)

        world = self.session(self.world, V2)
        self.assertEqual(self.ask(world), [(self.CHEST,)])

    def test_a_live_push_drops_the_contents(self):
        world = self.session(self.world, V1)
        self.ask(world)
        self.answer(world)
        self.assertEqual(self.ask(world), [])
        world.m("datacache").set_version(SERVER, V2)
        self.assertEqual(self.ask(world), [(self.CHEST,)])


class WikiPages(Relog):
    def world(self):
        import nui_wiki_test as wiki
        import nui_w4_world as w4
        world = w4.World(True, windows="+items,+wiki", setup=wiki.setup)
        with world.game, w4.quiet():
            world.game.load("nui_wiki_data", "nui_wiki_data.py")
            world.game.load("nui_wiki", "nui_wiki.py")
        with world.game, w4.quiet():
            window = world.nui_windows.make("wiki", type("Unused", (), {}), "nui_wiki.WikiWindow")
            window.Open()
        world.wiki = window
        return world

    def ask(self, world):
        import nui_w4_world as w4
        mark = len(world.game.log)
        with world.game, w4.quiet():
            world.wiki.OpenMob(8002)
        return [args for name, args in world.calls_since(mark, "net.") if name == "net.SendWikiRequest"]

    def answer(self, world):
        import nui_w4_world as w4
        with world.game, w4.quiet():
            world.wiki.WikiAnswer(1, 0, 8002, 0, (), (), (), ((27001, 2),))

    def test_the_same_version_at_relog_asks_nothing(self):
        world = self.session(self.world, V1)
        self.assertEqual(self.ask(world), [(1, 8002)])
        self.answer(world)

        world = self.session(self.world, V1)
        self.assertEqual(self.ask(world), [], "the page is known: no request")
        import nui_w4_world as w4
        self.assertEqual(w4.board(world.wiki).model["page_state"], "ready")

    def test_a_changed_version_at_relog_asks_again(self):
        world = self.session(self.world, V1)
        self.ask(world)
        self.answer(world)

        world = self.session(self.world, V2)
        self.assertEqual(self.ask(world), [(1, 8002)])

    def test_a_busy_answer_is_never_kept(self):
        world = self.session(self.world, V1)
        self.ask(world)
        import nui_w4_world as w4
        with world.game, w4.quiet():
            world.wiki.WikiAnswer(1, 1, 8002, 0, (), (), (), ())
        world = self.session(self.world, V1)
        self.assertEqual(self.ask(world), [(1, 8002)])

    def test_a_live_push_drops_the_pages(self):
        world = self.session(self.world, V1)
        self.ask(world)
        self.answer(world)
        world.m("datacache").set_version(SERVER, V2)
        self.assertEqual(dict(world.m("nui_wiki").ANSWERS), {})
        self.assertEqual(self.ask(world), [(1, 8002)])


if __name__ == "__main__":
    unittest.main()
