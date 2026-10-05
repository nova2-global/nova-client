# NovaUI snapshot goldens

Reference images of the NovaUI pages that cover the components, the renderer, the first converted window and the player themes, written by `nuitool snap`:

| Page | Document | Themes | Frame sizes (scale 1.0, 1.5, 2.0) |
|---|---|---|---|
| Gallery, every component in every state it styles | `nui/windows/gallery/gallery.rml` with `gallery.fixture.json` | dark, light, classic | 1920x1080, 2880x1620, 3840x2160 |
| Render test, every renderer feature | `nui/windows/render-test/render-test.rml` | dark, light | 1280x720, 1920x1080, 2560x1440 |
| Login board, its error state | `nui/windows/login/login.rml` with `login.fixture.json` | dark, light, classic | 1920x1080, 2880x1620, 3840x2160 |
| Theme picker | `nui/windows/theme-picker/theme-picker.rml` with `theme-picker.fixture.json` | dark, light, classic | 640x360 (1.0 only) |
| Skin proof, the classic frame pieces at legacy sizes | `nui/windows/skin-proof/skin-proof.rml` | classic | 640x360, 960x540, 1280x720 |

The scales are the client's automatic scale for 1080, 1620 and 2160 lines. A file is `<page>-<theme>-<percent>.png`, for example `gallery-light-150.png`, where the theme is the short name: `dark`, `light` and `classic` stand for the theme ids `modern-dark`, `modern-light` and `classic` of `nui/theme/themes.json`, which the checker passes to `--theme`. The login board also has `login-dark-100-reduced-motion.png`. `tools/check_nui_snapshots.py` holds the table of all 31 (page, theme, scale, frame size, fixture, motion setting); it is the one place to add a golden. It needs a `nuitool` that takes theme ids (`--theme modern-dark`).

All of them use the English strings (`--locale assets/locale/locale/en`) and the default `--time 1`, which lets the window-open motion and the component transitions finish and puts the render test's two endless animations at a fixed phase.

The snapshots come from `SoftRenderInterface`, the CPU renderer. It follows the Direct3D 9 renderer's rules (premultiplied filtering, per-axis wrap, `.sub` regions, the color key; see `src/NovaUI/README.md` in `nova-client-src`), but it is not the client: compare the client against these by eye, not pixel for pixel.

## Where they come from

- The render-test images were written by a Linux (GCC) build of `nuitool` at `nova-client-src` commit a8ce386.
- The gallery and login images were written again when the text inputs lost their rounded corners (`input.rcss`: RmlUi makes every text input clip its content, and an element that clips with a border-radius needs the stencil clip mask on every frame). That is the only change in them: the four corners of each input, at most 2x2 px each at 1.0, 4x4 at 1.5 and 6x6 at 2.0. The window that opens with a rise and no fade (`window-frame.rcss`) and the list that scrolls in a square viewport inside its rounded frame (`list.rcss`) changed no pixel of these settled frames.
- A Linux build of `nova-client-src` commit f9539ec matches all 19 at tolerance 0, so it writes these images. A Windows (MSVC) build of the same commit matches the 13 gallery and login images at tolerance 0; in four render-test images one or two pixels differ by 1, all inside the rotated text of the clip-mask cell.

- The 12 goldens of the player themes (every `-classic-` image and the three theme-picker images) were written by a Linux build of `nova-client-src` branch `nui-themes`, the first `nuitool` that takes theme ids and draws the `nui-repeat-box` decorator. A Linux build of its commit 46d4630 matches all 31 at tolerance 0, so it writes these images. The 19 older images did not change with the themes: that build matches them at tolerance 0, and so does a Linux build of `8c39bd3`, which still takes `--theme dark` and `light`.
- Seven classic images were written again on 2026-10-05, by a Linux build of `nova-client-src` `nui-themes` at fc98e03: `gallery-classic-150`, `-200`, `skin-proof-classic-150`, `-200` and `login-classic-100`, `-150`, `-200`. In the 2x art the stone board and the leather title bar have their grain back (detail 1.25), and the thin board and the login field are the legacy pixels doubled (`nearest`); the classic login board has the legacy row offsets and an error line that takes space only while there is an error. The other 24 images did not change, and that build matches all 31 and the five switched snapshots at tolerance 0.

So the check allows a difference of 1 per channel, and a build for either platform passes it. To catch a change of 1 anywhere, check at `--tolerance 0` with a Linux build, the platform that wrote the goldens: `nova-client-src/tools/linux-nui` builds `nuitool` on Linux or WSL (see "Tools" in `docs/ui/AUTHORING.md`).

## Check

From the asset repository root:

```bash
python3 tools/check_nui_snapshots.py --nuitool <path to nuitool>
```

- `--nuitool` defaults to the `NUITOOL` environment variable, then to `nuitool` on `PATH`. A Windows `nuitool.exe` started from WSL works, since the script passes relative paths.
- It runs every case, lists every mismatch with nuitool's report, and exits 1 if any failed. The snapshots and diff images (magenta where pixels differ) of the mismatches stay in the `.snapshot-check-*` folder it names; delete it when done. With no mismatch it deletes the folder itself.
- `--tolerance 0` checks exactly; `--only <text>` checks the goldens whose name contains the text (`--only login`).
- The render test's scroll container holds more than it shows on purpose, so nuitool prints a `scrolls; the snapshot shows ...` note for it; that note is not a failure.

## Regenerate

Regenerate after a change to anything the pages draw: the files under `assets/nui/nui/` they use, the two fixtures, the English strings they show, or `nuitool` itself (the soft renderer, the runtime, RmlUi or FreeType):

```bash
python3 tools/check_nui_snapshots.py --write --nuitool <path to nuitool>
```

`--only` works here too. Look at every changed image before committing it, and say in the commit message what changed on screen and why. RmlUi warnings (`rmlui: ...` lines) are listed at the end, and a regeneration that prints one exits 1: it should print none. When the images change because `nuitool` changed, update "Where they come from" with the `nova-client-src` commit that wrote them.

## Switched snapshots

A player switches themes at run time, so a switched window must look exactly like one opened in the new theme. The check also runs five snapshots made after a switch (`nuitool snap --switch-from <id>`: the page settles in that theme, then switches to the golden's theme with one update at the same time) and compares each with the golden of the theme it switched to; they have no files of their own. The table is `SWITCHED` in `tools/check_nui_snapshots.py`:

| Snapshot | Golden | What it covers |
|---|---|---|
| `login-classic-100-from-dark` | `login-classic-100` | a skin switch onto classic over the login board's transitioning buttons and fields |
| `login-dark-150-from-classic` | `login-dark-150` | a skin switch away from classic |
| `skin-proof-classic-200-from-light` | `skin-proof-classic-200` | the 2x classic art after a switch |
| `gallery-light-100-from-classic` | `gallery-light-100` | every component switched from classic, the slider's thumb and track included |
| `gallery-dark-100-from-light` | `gallery-dark-100` | a palette-only switch |

A mismatch means a switch left part of the old theme behind, or started a transition or an animation: snap does not move the clock after the switch, so either shows. `--write` writes the goldens, then checks these.

## Login board

- The fixture is the error state: a filled ID, the ID field focused (autofocus), the password field marked invalid and its error line. In classic the error line takes space only while there is an error, so the classic board is one line taller in these images than at rest.
- The sizes are the client's full-screen backbuffers at those scales: the board sits relative to the bottom center of the frame (horizontally centered, 72dp above the bottom edge).
- The reduced-motion frame matches the settled one at tolerance 0: reduced motion stops the window-open animation, and at the default `--time 1` it has finished.
- `--time 0.05` gives a frame that does not match: the board rises 4dp each time it is shown, and at 0.05 s it is 2 px low at scale 1.0. A reduced-motion frame at `--time 0.05` differs only by the ID field's caret, which RmlUi blinks on its own clock (visible at 0.05 s, hidden at 1 s).
- nuitool prints no `rmlui:` warning and no note about the frame for these cases.

## Classic pages

- The classic images use Noto Sans for the classic font family (`Nova Classic`): `nuitool` gives that family Noto Sans unless `--font` hands it another file, so the goldens do not depend on the fonts of the machine. The client draws Tahoma there.
- At 1.0 the classic art is the 1x sheet, the legacy pixels; at 1.5 and 2.0 it is the 2x sheet (`nui/skins/classic/classic-sprites.rcss`). A change to the sheets (`tools/nui_classic_art.py build`) changes every classic image.
- The skin-proof page is a 280x160 legacy board with a title bar, a close button, a field and two large buttons, one of them in its over art (`is-hover`). At 1.0 its frame, title bar, close button and buttons match a drawing of the same window from the original legacy files (`tools/nui_classic_art.py legacy-ref`) to the pixel.
- The theme picker's fixture has `modern-dark` selected, so its selected button has the primary look in the modern themes and the legacy down art in classic.
