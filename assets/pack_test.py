"""Unit tests for pack.py (no novapack or rsync needed): python -m unittest pack_test"""
import json
import os
import tempfile
import unittest

import pack


class TempAssets(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        self.staging = os.path.join(self.root, "staging")
        os.makedirs(os.path.join(self.staging, "channels"))
        os.makedirs(os.path.join(self.staging, "releases"))
        self.key = os.path.join(self.root, "nova.key")
        with open(self.key, "w") as handle:
            handle.write("00")
        self.novapack = os.path.join(self.root, "novapack")  # a stand-in; nothing is executed
        open(self.novapack, "w").close()
        self.cfg = {"staging": self.staging, "key": self.key, "novapack": self.novapack, "channel": "live",
                    "prefix": "r", "target": "host:/srv/patch"}
        self.calls = []

    def tearDown(self):
        self.dir.cleanup()

    def pointer(self, channel, **fields):
        with open(os.path.join(self.staging, "channels", channel + ".json"), "w") as handle:
            json.dump(fields, handle)

    def run_(self, cmd):
        self.calls.append(cmd)
        return 0

    def build(self, *args):
        cmd, info = pack.build_args(self.cfg, list(args), "novapack")
        return cmd, info

    def opt(self, cmd, name):
        return cmd[cmd.index(name) + 1]


class NextReleaseId(unittest.TestCase):
    def test_counts_up_from_the_current_release(self):
        self.assertEqual(pack.next_release_id("r4", "r"), "r5")
        self.assertEqual(pack.next_release_id("r99", "r"), "r100")
        self.assertEqual(pack.next_release_id("live-7", "live-"), "live-8")

    def test_first_release_is_number_one(self):
        self.assertEqual(pack.next_release_id(None, "r"), "r1")

    def test_foreign_ids_need_an_explicit_release_id(self):
        with self.assertRaises(SystemExit):
            pack.next_release_id("20260921T1500-abcd", "r")


class ConfigLayering(unittest.TestCase):
    def test_local_file_overrides_the_committed_one_and_paths_resolve_relative_to_the_folder(self):
        with tempfile.TemporaryDirectory() as here:
            with open(os.path.join(here, "pack.cfg"), "w") as handle:
                handle.write("[paths]\nstaging = ../staging\nkey = ../keys/nova.key\n[publish]\ntarget = a:/x\n")
            with open(os.path.join(here, "pack.local.cfg"), "w") as handle:
                handle.write("[paths]\nkey = /secret/nova.key\n[publish]\ntarget = b:/y\n")
            cfg = pack.load_config(here)
            self.assertEqual(cfg["staging"], os.path.normpath(os.path.join(here, "../staging")))
            self.assertEqual(cfg["key"], os.path.normpath("/secret/nova.key"))
            self.assertEqual(cfg["target"], "b:/y")
            self.assertEqual(cfg["channel"], "live")
            self.assertEqual(cfg["prefix"], "r")

    def test_missing_files_give_plain_defaults(self):
        with tempfile.TemporaryDirectory() as here:
            cfg = pack.load_config(here)
            self.assertEqual(cfg["key"], "")
            self.assertEqual(cfg["target"], "")


class BuildArguments(TempAssets):
    def test_first_build_is_r1_mandatory_with_configured_paths(self):
        cmd, info = self.build()
        self.assertEqual(info, {"staging": self.staging, "channel": "live", "release": "r1", "required": None,
                                "previous": None})
        self.assertEqual(self.opt(cmd, "--out"), self.staging)
        self.assertEqual(self.opt(cmd, "--key"), self.key)
        self.assertEqual(self.opt(cmd, "--release-id"), "r1")
        self.assertNotIn("--required-release", cmd)

    def test_next_build_counts_up_and_optional_keeps_the_required_release(self):
        self.pointer("live", release="r4")
        cmd, info = self.build("--optional")
        self.assertEqual(info["release"], "r5")
        self.assertEqual(info["previous"], "r4")
        self.assertEqual(self.opt(cmd, "--required-release"), "r4")
        # a second optional patch keeps the same floor
        self.pointer("live", release="r5", required="r4")
        cmd, info = self.build("--optional")
        self.assertEqual(info["release"], "r6")
        self.assertEqual(self.opt(cmd, "--required-release"), "r4")
        # a mandatory build drops it
        cmd, info = self.build()
        self.assertEqual(info["required"], None)
        self.assertNotIn("--required-release", cmd)

    def test_overrides_win_and_unknown_options_pass_through(self):
        self.pointer("beta", release="r2")
        other_key = os.path.join(self.root, "other.key")
        open(other_key, "w").close()
        cmd, info = self.build("--channel", "beta", "--release-id", "hotfix-1", "--key", other_key,
                               "--bundle-max-mib", "64")
        self.assertEqual(info["channel"], "beta")
        self.assertEqual(info["release"], "hotfix-1")
        self.assertEqual(self.opt(cmd, "--key"), other_key)
        self.assertEqual(self.opt(cmd, "--bundle-max-mib"), "64")

    def test_optional_needs_an_existing_channel_and_the_key_must_exist(self):
        with self.assertRaises(SystemExit):
            self.build("--optional")
        self.cfg["key"] = os.path.join(self.root, "missing.key")
        with self.assertRaises(SystemExit):
            self.build()


class Commands(TempAssets):
    def test_release_builds_then_publishes_in_two_phases_with_the_pointer_last(self):
        self.pointer("live", release="r4")
        pack.main(["release", "--optional"], self.cfg, self.run_)
        self.assertEqual(self.calls[0][1], "build")
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(self.calls[1][-1].endswith("releases/"))
        self.assertTrue(self.calls[2][-1].endswith("bundles/"))
        self.assertTrue(self.calls[3][-1].endswith("channels/"))
        self.assertTrue(self.calls[3][-1].startswith("host:/srv/patch/"))

    def test_dry_run_prints_but_does_not_build(self):
        pack.main(["build", "--dry-run"], self.cfg, self.run_)
        self.assertEqual(self.calls, [])

    def test_a_failed_bundle_sync_never_touches_the_channel_pointer(self):
        def failing(cmd):
            self.calls.append(cmd)
            return 23 if cmd[-1].endswith("bundles/") else 0
        with self.assertRaises(SystemExit):
            pack.publish(self.staging, "host:/srv/patch", [], failing)
        self.assertEqual(len(self.calls), 2)

    def test_publish_without_a_target_is_refused(self):
        self.cfg["target"] = ""
        with self.assertRaises(SystemExit):
            pack.main(["publish"], self.cfg, self.run_)

    def test_passthrough_commands_default_to_the_staging_dir_and_key(self):
        pack.main(["verify"], self.cfg, self.run_)
        pack.main(["gc", "--keep", "3"], self.cfg, self.run_)
        pack.main(["keygen"], self.cfg, self.run_)
        self.assertEqual(self.calls[0][1:], ["verify", self.staging])
        self.assertEqual(self.calls[1][1:], ["gc", "--root", self.staging, "--keep", "3"])
        self.assertEqual(self.calls[2][1:], ["keygen", "--out", self.key[:-4]])


if __name__ == "__main__":
    unittest.main()
