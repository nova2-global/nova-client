#!/usr/bin/env python3
"""Checks or regenerates the NovaUI snapshot goldens in docs/ui/snapshots/.

    python3 tools/check_nui_snapshots.py            # compare every golden (exit 1 on any mismatch)
    python3 tools/check_nui_snapshots.py --write    # regenerate every golden
    python3 tools/check_nui_snapshots.py --only login --tolerance 0

Run it from anywhere; it works in the asset repository root and passes
nuitool relative paths, so a Windows nuitool.exe started from WSL works too.
nuitool comes from --nuitool, else the NUITOOL environment variable, else
PATH. The case table below is the single list of goldens: their page,
theme, scale, frame size, fixture and motion setting (docs/ui/snapshots/
README.md explains why each is what it is).

A check runs every case, even after a mismatch, lists every mismatch with
nuitool's own report, and leaves the snapshots and diff images of the
mismatches in a folder it names. RmlUi warnings (nuitool's "rmlui:" lines)
are listed too; a regeneration should print none.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOTS = os.path.join("docs", "ui", "snapshots")
ROOTS = ["--root", "assets/nui", "--root", "assets/icon", "--locale", "assets/locale/locale/en"]

# (golden name, document, fixture or None, theme, --scale, --size, reduced motion)
PAGES = [
    ("gallery", "nui/windows/gallery/gallery.rml", "assets/nui/nui/windows/gallery/gallery.fixture.json",
     [("100", "1", "1920x1080"), ("150", "1.5", "2880x1620"), ("200", "2", "3840x2160")]),
    ("render-test", "nui/windows/render-test/render-test.rml", None,
     [("100", "1", "1280x720"), ("150", "1.5", "1920x1080"), ("200", "2", "2560x1440")]),
    ("login", "nui/windows/login/login.rml", "assets/nui/nui/windows/login/login.fixture.json",
     [("100", "1", "1920x1080"), ("150", "1.5", "2880x1620"), ("200", "2", "3840x2160")]),
]


def cases():
    for page, document, fixture, scales in PAGES:
        for theme in ("dark", "light"):
            for percent, scale, size in scales:
                yield (f"{page}-{theme}-{percent}", document, fixture, theme, scale, size, False)
    # Reduced motion renders the resting state, which at the default --time 1
    # is the settled frame: the board's open animation has finished.
    yield ("login-dark-100-reduced-motion", "nui/windows/login/login.rml", "assets/nui/nui/windows/login/login.fixture.json",
           "dark", "1", "1920x1080", True)


def command(nuitool, case, out, compare=None, tolerance=None):
    name, document, fixture, theme, scale, size, reduced = case
    cmd = [nuitool, "snap"] + ROOTS + ["--doc", document, "--theme", theme, "--scale", scale, "--size", size, "--out", out]
    if fixture:
        cmd += ["--fixture", fixture]
    if reduced:
        cmd.append("--reduced-motion")
    if compare:
        cmd += ["--compare", compare, "--tolerance", str(tolerance)]
    return cmd


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="regenerate the goldens instead of comparing")
    parser.add_argument("--nuitool", default=os.environ.get("NUITOOL", "nuitool"), help="nuitool to run (default: $NUITOOL or nuitool on PATH)")
    parser.add_argument("--tolerance", type=int, default=1,
                        help="allowed difference per channel when comparing (default 1: builds for other platforms differ by 1 in a few pixels)")
    parser.add_argument("--only", default="", help="only the goldens whose name contains this text")
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    if shutil.which(args.nuitool) is None and not os.path.isfile(args.nuitool):
        print(f"check_nui_snapshots: nuitool not found: {args.nuitool} (pass --nuitool or set NUITOOL)", file=sys.stderr)
        return 2
    selected = [c for c in cases() if args.only in c[0]]
    if not selected:
        print(f"check_nui_snapshots: no golden matches '{args.only}'", file=sys.stderr)
        return 2

    work = None if args.write else os.path.relpath(tempfile.mkdtemp(prefix=".snapshot-check-", dir=ROOT), ROOT)
    failed, warned = [], []
    for case in selected:
        name = case[0]
        golden = os.path.join(SNAPSHOTS, name + ".png")
        if args.write:
            cmd = command(args.nuitool, case, golden)
        else:
            cmd = command(args.nuitool, case, os.path.join(work, name + ".png"), golden, args.tolerance)
        result = subprocess.run(cmd, capture_output=True, text=True)
        warnings = [line for line in result.stderr.splitlines() if line.startswith("rmlui:")]
        if warnings:
            warned.append((name, warnings))
        if result.returncode == 0:
            print(f"ok    {name}")
            continue
        failed.append(name)
        print(f"FAIL  {name}")
        for line in (result.stdout + result.stderr).splitlines():
            if line.startswith("nuitool"):
                print(f"      {line}")

    for name, warnings in warned:
        print(f"RmlUi reported problems for {name}:")
        for line in warnings:
            print(f"      {line}")
    if work and not failed:
        shutil.rmtree(work, ignore_errors=True)
    action = "written" if args.write else f"matching within {args.tolerance}"
    print(f"{len(selected) - len(failed)} of {len(selected)} goldens {action}" + (f"; snapshots and diffs in {work}" if work and failed else ""))
    return 1 if failed or (args.write and warned) else 0


if __name__ == "__main__":
    sys.exit(main())
