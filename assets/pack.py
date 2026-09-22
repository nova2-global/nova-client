#!/usr/bin/env python3
"""Build and publish content releases with novapack.

    python pack.py status                 what each channel points at, what would ship next
    python pack.py build [--optional]     next release id, configured staging + key
    python pack.py publish [--dry-run]    two-phase rsync to the configured server
    python pack.py release [--optional]   build, then publish
    python pack.py pull-pointers          copy the server's channel pointers into staging (fresh machines, CI)
    python pack.py keygen                 create the signing key at the configured path
    python pack.py verify | inspect | gc  passed through to novapack (staging by default)

Defaults live in pack.cfg (committed) and pack.local.cfg (git-ignored, per
machine: key, staging, server). Any option still overrides them:
    --out <staging>  --key <file>  --channel <name>  --release-id <id>  --target <rsync target>

Release ids are <prefix><number> (pack.cfg [release] prefix, "r" by default):
`build` reads the channel's current release from staging and takes the next
number, so you never have to remember it. `status` shows it before you build.

`--optional` publishes a nice-to-have patch: clients that start pick it up,
but the login gate keeps accepting the previously required release, so nobody
in game or at the login window is forced out. A plain build makes the new
release mandatory again.

Group order comes from groups.txt; loose files from _loose/ (see
LOOSE-FILES.md; keep documentation out of that folder, everything in it is
published).
"""
import configparser
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILES = ("pack.cfg", "pack.local.cfg")


class PackError(SystemExit):
    pass


# --- configuration ---------------------------------------------------------

def load_config(here=HERE):
    """pack.cfg, then pack.local.cfg on top; relative paths resolve against `here`."""
    parser = configparser.ConfigParser()
    parser.read([os.path.join(here, name) for name in CONFIG_FILES], encoding="utf-8")
    cfg = {
        "staging": parser.get("paths", "staging", fallback="../staging"),
        "key": parser.get("paths", "key", fallback=""),
        "novapack": parser.get("paths", "novapack", fallback=""),
        "channel": parser.get("release", "channel", fallback="live"),
        "prefix": parser.get("release", "prefix", fallback="r"),
        "target": parser.get("publish", "target", fallback=""),
    }
    for name in ("staging", "key", "novapack"):
        if cfg[name]:
            cfg[name] = os.path.normpath(os.path.join(here, os.path.expanduser(cfg[name])))
    return cfg


def take_option(args, name, default=None):
    """Removes `name <value>` from args and returns the value (or default)."""
    if name in args:
        i = args.index(name)
        if i + 1 >= len(args):
            raise PackError(f"{name} needs a value")
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return default


def take_flag(args, name):
    if name in args:
        args.remove(name)
        return True
    return False


# --- release ids -----------------------------------------------------------

def read_pointer(staging, channel):
    """The channel pointer as a dict, or None when the channel does not exist yet."""
    path = os.path.join(staging, "channels", channel + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            pointer = json.load(handle)
        pointer["release"]
        return pointer
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise PackError(f"cannot read the channel pointer {path}: {error}")


def next_release_id(current, prefix):
    """r4 -> r5; nothing yet -> r1. Ids that do not follow the scheme need --release-id."""
    if current is None:
        return f"{prefix}1"
    match = re.fullmatch(re.escape(prefix) + r"(\d+)", current)
    if not match:
        raise PackError(f"current release {current!r} does not look like {prefix}<number>; pass --release-id")
    return f"{prefix}{int(match.group(1)) + 1}"


def required_for_optional(pointer, channel):
    """The release the login gate must keep accepting after an optional patch:
    the channel's current "required" id, or its "release" when every earlier
    patch was mandatory."""
    if pointer is None:
        raise PackError(f"--optional needs an existing channel {channel!r}: the first release is always mandatory")
    return pointer.get("required") or pointer["release"]


# --- commands --------------------------------------------------------------

def find_novapack(cfg):
    candidates = [cfg["novapack"]] if cfg["novapack"] else []
    candidates += [os.path.join(HERE, "novapack.exe"), os.path.join(HERE, "novapack")]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    for name in ("novapack.exe", "novapack"):
        found = shutil.which(name)
        if found:
            return found
    raise PackError("novapack not found: build nova-client-src and put novapack(.exe) on PATH, next to pack.py, "
                    "or set [paths] novapack in pack.local.cfg")


def build_args(cfg, args, exe):
    """The novapack command line for `build`, plus the ids it settles on."""
    args = list(args)
    staging = take_option(args, "--out", cfg["staging"])
    key = take_option(args, "--key", cfg["key"])
    channel = take_option(args, "--channel", cfg["channel"])
    optional = take_flag(args, "--optional")
    pointer = read_pointer(staging, channel)
    release_id = take_option(args, "--release-id") or next_release_id(pointer["release"] if pointer else None,
                                                                       cfg["prefix"])
    if not key:
        raise PackError("no signing key configured: set [paths] key in pack.local.cfg or pass --key")
    if not os.path.exists(key):
        raise PackError(f"signing key not found: {key} (run `pack.py keygen` once, then keep it out of git)")
    cmd = [exe, "build", "--groups", os.path.join(HERE, "groups.txt"), "--assets", HERE, "--out", staging,
           "--key", key, "--channel", channel, "--release-id", release_id]
    loose = os.path.join(HERE, "_loose")
    if os.path.isdir(loose):
        cmd += ["--loose", loose]
    required = required_for_optional(pointer, channel) if optional else None
    if required is not None:
        cmd += ["--required-release", required]
    cmd += args  # anything else goes straight to novapack (e.g. --bundle-max-mib)
    return cmd, {"staging": staging, "channel": channel, "release": release_id, "required": required,
                 "previous": pointer["release"] if pointer else None}


def publish(staging, target, extra, run=subprocess.call):
    """Two-phase rsync so a client never sees a channel pointer before its objects:
    1. releases/ and bundles/ (immutable, content-addressed: idempotent, unchanged
       bundles are skipped by size+checksum), 2. channels/ last."""
    staging = os.path.abspath(staging)
    if not os.path.isdir(os.path.join(staging, "channels")):
        raise PackError(f"{staging} does not look like a novapack staging directory (no channels/)")
    if not target:
        raise PackError("no publish target configured: set [publish] target in pack.local.cfg or pass --target")
    if not shutil.which("rsync"):
        raise PackError("rsync not found on PATH")
    base = ["rsync", "-a", "--checksum"] + extra
    target = target.rstrip("/") + "/"
    steps = [
        base + [os.path.join(staging, "releases") + "/", target + "releases/"],
        base + [os.path.join(staging, "bundles") + "/", target + "bundles/"],
        base + [os.path.join(staging, "channels") + "/", target + "channels/"],
    ]
    for cmd in steps:
        print(" ".join(cmd))
        rc = run(cmd)
        if rc != 0:
            if cmd is not steps[-1]:
                raise PackError(f"rsync failed with exit code {rc}; the channel pointer was NOT updated")
            raise PackError(rc)
    return 0


def pull_pointers(staging, target, extra, run=subprocess.call):
    """Brings the server's channels/ into staging so `build` numbers the next
    release from what is actually live. A fresh checkout (a CI runner) has no
    staging history; the bundles themselves need not be pulled because the
    builder is deterministic and the publish rsync skips what the server has."""
    if not target:
        raise PackError("no publish target configured: set [publish] target in pack.local.cfg or pass --target")
    if not shutil.which("rsync"):
        raise PackError("rsync not found on PATH")
    channels = os.path.join(os.path.abspath(staging), "channels")
    os.makedirs(channels, exist_ok=True)
    cmd = ["rsync", "-a"] + extra + [target.rstrip("/") + "/channels/", channels + "/"]
    print(" ".join(cmd))
    rc = run(cmd)
    if rc != 0:
        raise PackError(f"rsync failed with exit code {rc}")
    return 0


def status(cfg, args):
    args = list(args)
    staging = take_option(args, "--out", cfg["staging"])
    print(f"staging:  {staging}")
    print(f"key:      {cfg['key'] or '(not configured)'}" + ("" if os.path.exists(cfg["key"]) else "  [missing]"))
    print(f"publish:  {cfg['target'] or '(not configured)'}")
    channels_dir = os.path.join(staging, "channels")
    names = sorted(n[:-5] for n in os.listdir(channels_dir) if n.endswith(".json")) if os.path.isdir(channels_dir) else []
    if not names:
        print(f"channels: none yet; `pack.py build` creates {cfg['channel']} as {cfg['prefix']}1")
        return 0
    for name in names:
        pointer = read_pointer(staging, name)
        required = pointer.get("required") or pointer["release"]
        kind = "optional patches allowed down to " + required if required != pointer["release"] else "mandatory"
        marker = "  <- default" if name == cfg["channel"] else ""
        print(f"channel {name}: release {pointer['release']} ({kind}){marker}")
    try:
        nxt = next_release_id(read_pointer(staging, cfg["channel"])["release"], cfg["prefix"]) \
            if cfg["channel"] in names else f"{cfg['prefix']}1"
        print(f"next:     {nxt} on {cfg['channel']}")
    except PackError as error:
        print(f"next:     {error}")
    releases_dir = os.path.join(staging, "releases")
    if os.path.isdir(releases_dir):
        print("releases: " + ", ".join(sorted(n[:-4] for n in os.listdir(releases_dir) if n.endswith(".nvm"))))
    return 0


def main(argv, cfg=None, run=subprocess.call):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cfg = cfg or load_config()
    cmd, rest = argv[0], list(argv[1:])
    if cmd == "status":
        return status(cfg, rest)
    if cmd in ("publish", "pull-pointers"):
        target = take_option(rest, "--target", cfg["target"])
        staging = take_option(rest, "--out", cfg["staging"])
        if cmd == "publish":
            return publish(staging, target, rest, run)
        return pull_pointers(staging, target, rest, run)
    exe = find_novapack(cfg)
    if cmd in ("build", "release"):
        dry = take_flag(rest, "--dry-run")
        target = take_option(rest, "--target", cfg["target"])
        args, info = build_args(cfg, rest, exe)
        previous = info["previous"] or "nothing"
        kind = f"optional, login gate keeps accepting {info['required']}" if info["required"] else "mandatory"
        print(f"{info['channel']}: {previous} -> {info['release']} ({kind})")
        print(" ".join(args))
        if dry:
            return 0
        rc = run(args)
        if rc != 0 or cmd == "build":
            return rc
        return publish(info["staging"], target, [], run)
    if cmd == "keygen":
        if "--out" not in rest:
            if not cfg["key"]:
                raise PackError("no key path configured: set [paths] key or pass --out")
            rest += ["--out", cfg["key"][:-4] if cfg["key"].endswith(".key") else cfg["key"]]
        args = [exe, "keygen"] + rest
    elif cmd in ("verify", "inspect"):
        args = [exe, cmd] + (rest or [cfg["staging"]])
    elif cmd == "gc":
        if "--root" not in rest:
            rest = ["--root", cfg["staging"]] + rest
        args = [exe, "gc"] + rest
    else:
        raise PackError(f"unknown command {cmd!r}; see --help")
    print(" ".join(args))
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
