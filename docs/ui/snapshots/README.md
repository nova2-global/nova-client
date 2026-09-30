# NovaUI snapshot goldens

Each golden is a `nuitool snap` frame of one document. Rerun the command with `--compare <golden> --out <scratch file>` to check a change: a frame matches its golden at tolerance 0 when it was written with the same `--size`, `--scale`, `--theme`, `--time` and `--locale`. Run the commands from the root of this repository. `nuitool` is built from `nova-client-src` (target `nuitool`); the goldens come from its CPU renderer, which is the same in the Linux and the MSVC build.

## Login board (`nui/windows/login`)

Written by the `nuitool` of `nova-client-src` branch `nui-p4-login`, whose snap runs the clock in steps of 0.1 s and reads `--locale` (the same code as `nui-int-c` 09871ee and a8ce386). The fixture is the error state: a filled ID, the ID field focused (autofocus), the password field marked invalid and its error line.

```
N=nuitool
F=assets/nui/nui/windows/login/login.fixture.json
L=assets/locale/locale/en
S=docs/ui/snapshots
D="--root assets/nui --root assets/icon --doc nui/windows/login/login.rml --fixture $F --locale $L"
for t in dark light; do
  $N snap $D --theme $t --scale 1   --size 1920x1080 --out $S/login-$t-100.png
  $N snap $D --theme $t --scale 1.5 --size 2880x1620 --out $S/login-$t-150.png
  $N snap $D --theme $t --scale 2   --size 3840x2160 --out $S/login-$t-200.png
done
$N snap $D --theme dark --scale 1 --size 1920x1080 --reduced-motion \
  --out $S/login-dark-100-reduced-motion.png --compare $S/login-dark-100.png
```

- The sizes are the client's full-screen backbuffers at those scales: the board sits relative to the bottom center of the frame (horizontally centered, 72dp above the bottom edge).
- The reduced-motion frame matches the settled one at tolerance 0: reduced motion stops the window-open animation, and at the default `--time 1` it has finished.
- `--time 0.05` gives a frame that does not match: the board fades in each time it is shown.
- Snap prints no `rmlui:` warning and no note about the frame for these commands.
