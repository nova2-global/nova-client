"""NOVA-127: the empire-colored select and target rings and the monster ring.

- playersettingmodule registers OLD's ring effects (OLD playerSettingModule.py:
  293-302) at the chrmgr ids the client picks from (InstanceBase.h, OLD
  InstanceBase.cpp:631-776), and keeps the generic rings the client falls
  back to;
- the client ships each ring and every file it names: tools/old_art.py took
  them from OLD's client (`rings`), with their rows in tools/fixtures/
  old_art.tsv. The check reads git's tree, so it holds in a sparse worktree.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import old_art  # noqa: E402

RINGS = {
	"EFFECT_SELECT": "d:/ymir work/effect/etc/click/click_select.mse",
	"EFFECT_TARGET": "d:/ymir work/effect/etc/click/click_glow_select.mse",
	"EFFECT_SHINSOO": "d:/ymir work/effect/world/shinsoo_select.mse",
	"EFFECT_TARGET_SHINSOO": "d:/ymir work/effect/world/shinsoo_glow_select.mse",
	"EFFECT_CHUNJO": "d:/ymir work/effect/world/chunjo_select.mse",
	"EFFECT_TARGET_CHUNJO": "d:/ymir work/effect/world/chunjo_glow_select.mse",
	"EFFECT_JINNOS": "d:/ymir work/effect/world/jinnos_select.mse",
	"EFFECT_TARGET_JINNOS": "d:/ymir work/effect/world/jinnos_glow_select.mse",
	"EFFECT_MONSTER": "d:/ymir work/effect/world/mob_select.mse",
	"EFFECT_TARGET_MONSTER": "d:/ymir work/effect/world/mob_glow_select.mse",
}


class Registrations(unittest.TestCase):
	"""What INIT and EFFECT register, read as the client runs them."""

	def setUp(self):
		patcher = mock.patch.dict(sys.modules)
		patcher.start()
		self.addCleanup(patcher.stop)
		modules = dict((name, lf.Numbered(name)) for name in lf.RaceMotions.C_MODULES)
		chrmgr = modules["chrmgr"]
		# Ids clear of the stand-in's small numbers and their sums.
		for offset, name in enumerate(sorted(RINGS)):
			setattr(chrmgr, name, 900000 + offset)
		self.effects = {}

		def register(index, bone, path, *rest):
			self.effects.setdefault(index, []).append((bone, path))

		chrmgr.RegisterCacheEffect = chrmgr.RegisterEffect = register
		sys.modules.update(modules)
		self.chrmgr = chrmgr
		namespace = {"__name__": "playerSettingModule"}
		path = os.path.join(lf.ROOT, "playersettingmodule.py")
		exec(compile(lf.read(path), path, "exec"), namespace)
		with lf.quiet():
			for name in ("INIT", "EFFECT"):
				namespace["LoadGameData"](name)

	def test_each_ring_is_olds_file_once_on_no_bone(self):
		for name, path in sorted(RINGS.items()):
			with self.subTest(name=name):
				self.assertEqual(self.effects.get(getattr(self.chrmgr, name)), [("", path)])


class ShippedArt(unittest.TestCase):
	"""Each ring and the files it names are in git's tree of the groups."""

	@classmethod
	def setUpClass(cls):
		groups = old_art._groups()
		cls.paths = old_art.tree_files()
		cls.files = old_art.tree_published(cls.paths, groups)
		cls.where = {}
		for path in cls.paths:
			found = old_art._tree_store(path, groups)
			if found:
				cls.where.setdefault(found[1], path)

	def test_every_ring_is_published(self):
		self.assertEqual([path for path in RINGS.values() if path not in self.files], [])

	def test_every_file_a_ring_names_is_published(self):
		missing = []
		for path in sorted(set(RINGS.values())):
			tree_path = self.where.get(path)
			if not tree_path:
				continue  # test_every_ring_is_published names it
			data = old_art.git_blob(tree_path)
			for name in old_art.references(data, path):
				if name not in self.files:
					missing.append("%s <- %s" % (name, path))
		self.assertEqual(missing, [])

	def test_each_ring_taken_from_old_has_its_manifest_row(self):
		with open(old_art.MANIFEST, encoding="utf-8") as handle:
			rows = dict((row[0], row) for row in (line.rstrip("\n").split("\t") for line in handle if not line.startswith("#")))
		for path in old_art.RINGS:
			with self.subTest(path=path):
				self.assertIn(path, rows)
				self.assertEqual("assets/" + rows[path][1], self.where.get(path))


if __name__ == "__main__":
	unittest.main()
