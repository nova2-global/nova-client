# NovaUI snapshot goldens

Reference images of the NovaUI pages that cover the components, the renderer, the first converted window and the player themes, written by `nuitool snap`:

| Page | Document | Themes | Frame sizes (scale 1.0, 1.5, 2.0) |
|---|---|---|---|
| Gallery, every component in every state it styles | `nui/windows/gallery/gallery.rml` with `gallery.fixture.json` | dark, light, classic | 1920x1080, 2880x1620, 3840x2160 |
| Render test, every renderer feature | `nui/windows/render-test/render-test.rml` | dark, light | 1280x720, 1920x1080, 2560x1440 |
| Login board, its error state | `nui/windows/login/login.rml` with `login.fixture.json` | dark, light, classic | 1920x1080, 2880x1620, 3840x2160 |
| Theme picker | `nui/windows/theme-picker/theme-picker.rml` with `theme-picker.fixture.json` | dark, light, classic | 640x360 (1.0 only) |
| Skin proof, the classic frame pieces at legacy sizes | `nui/windows/skin-proof/skin-proof.rml` | classic | 640x360, 960x540, 1280x720 |
| The dialog kit: `dialog-message`, `dialog-question`, `dialog-input`, `dialog-money`, `pick-money` | `nui/windows/<name>/<name>.rml` with its fixture | dark, light, classic | 640x360, 960x540, 1280x720 |
| Server and channel board | `nui/windows/server-board/server-board.rml` with its fixture | dark, light, classic | 1280x720, 1920x1080, 2560x1440 |
| Virtual keyboard | `nui/windows/virtual-keyboard/virtual-keyboard.rml` with its fixture (root `assets/ETC`) | dark, light, classic | 1280x720, 1920x1080, 2560x1440 |
| Locale flag strip | `nui/windows/locale-strip/locale-strip.rml` with its fixture (root `assets/ETC`) | dark, light, classic | 1280x120, 1920x180, 2560x240 |
| Loading screen | `nui/windows/loading/loading.rml` with its fixture (roots `assets/ETC`, `assets/uiloading`), at `--time 0.1` | dark, light, classic | 1280x720, 1920x1080, 2560x1440 |
| Empire select, character select, character create | `nui/windows/<name>/<name>.rml` (`empire`, `select`, `create`) with its fixture (roots `assets/ETC`, `assets/locale`) | dark, light, classic | 1280x720, 1920x1080, 2560x1440 |
| Character select and create while a start or a creation is under way (`select-busy`, `create-busy`): every button disabled | the same documents with `<name>.busy.fixture.json` | classic | 1280x720 (1.0 only) |

The scales are the client's automatic scale for 1080, 1620 and 2160 lines. A file is `<page>-<theme>-<percent>.png`, for example `gallery-light-150.png`, where the theme is the short name: `golden-themes.json` here maps `dark`, `light` and `classic` to the theme ids `modern-dark`, `modern-light` and `classic` of `nui/theme/themes.json`, which the checker passes to `--theme`. It also sets the golden policy: a case whose themes are `"all"` covers every shipped theme, and a theme marked experimental gets only the gallery and the pages it names ("Adding a theme" in `docs/ui/AUTHORING.md`). Every theme of `themes.json` needs an entry there; the checker stops without one. The login board also has `login-dark-100-reduced-motion.png`. The pages that predate Wave 1 are the table `PAGES` in `tools/check_nui_snapshots.py`; every other window declares its goldens in its own `assets/nui/nui/windows/<name>/<name>.snapshots.json`, which the checker discovers (see "Golden case files" in `docs/ui/AUTHORING.md`), so a new window adds its goldens there. A case may name a `variant`, a second fixture of the same window (`<name>.<variant>.fixture.json`), whose goldens are `<page>-<variant>-<theme>-<percent>.png`. `cases()` lists all of them: 141 goldens today. It needs a `nuitool` that takes theme ids (`--theme modern-dark`), and the cases with the `assets/ETC` root need one that decodes DDS (the locale flags) and knows `nui-frames` (the loading screen).

All of them use the English strings (`--locale assets/locale/locale/en`) and, except the loading screen, the default `--time 1`, which lets the window-open motion and the component transitions finish and puts the render test's two endless animations at a fixed phase.

The snapshots come from `SoftRenderInterface`, the CPU renderer. It follows the Direct3D 9 renderer's rules (premultiplied filtering, per-axis wrap, `.sub` regions, the color key; see `src/NovaUI/README.md` in `nova-client-src`), but it is not the client: compare the client against these by eye, not pixel for pixel.

## Where they come from

- The render-test images were written by a Linux (GCC) build of `nuitool` at `nova-client-src` commit a8ce386.
- The gallery and login images were written again when the text inputs lost their rounded corners (`input.rcss`: RmlUi makes every text input clip its content, and an element that clips with a border-radius needs the stencil clip mask on every frame). That is the only change in them: the four corners of each input, at most 2x2 px each at 1.0, 4x4 at 1.5 and 6x6 at 2.0. The window that opens with a rise and no fade (`window-frame.rcss`) and the list that scrolls in a square viewport inside its rounded frame (`list.rcss`) changed no pixel of these settled frames.
- A Linux build of `nova-client-src` commit f9539ec matches all 19 at tolerance 0, so it writes these images. A Windows (MSVC) build of the same commit matches the 13 gallery and login images at tolerance 0; in four render-test images one or two pixels differ by 1, all inside the rotated text of the clip-mask cell.

- The 12 goldens of the player themes (every `-classic-` image and the three theme-picker images) were written by a Linux build of `nova-client-src` branch `nui-themes`, the first `nuitool` that takes theme ids and draws the `nui-repeat-box` decorator. A Linux build of its commit 46d4630 matches all 31 at tolerance 0, so it writes these images. The 19 older images did not change with the themes: that build matches them at tolerance 0, and so does a Linux build of `8c39bd3`, which still takes `--theme dark` and `light`.
- Seven classic images were written again on 2026-10-05, by a Linux build of `nova-client-src` `nui-themes` at fc98e03: `gallery-classic-150`, `-200`, `skin-proof-classic-150`, `-200` and `login-classic-100`, `-150`, `-200`. In the 2x art the stone board and the leather title bar have their grain back (detail 1.25), and the thin board and the login field are the legacy pixels doubled (`nearest`); the classic login board has the legacy row offsets and an error line that takes space only while there is an error. The other 24 images did not change, and that build matches all 31 and the five switched snapshots at tolerance 0.

- **Wave 1, 2026-10-05:** a Linux build of `nova-client-src` `nui-wave1` at 7458d97 (the first `nuitool` that decodes DDS and knows `nui-frames`) wrote the 72 goldens of the dialog kit, the server board, the virtual keyboard and the locale strip, and the 9 gallery goldens again, all with `--write --optimize`. The gallery now shows the medium buttons, a disabled button of each size, the classic disabled look (the default art tinted gray, at full opacity, where it was the art at 0.45 opacity) and the gauge in its four colors; its goldens take the `assets/ETC` root for the classic gauge art. That build matches the other 22 goldens and the five switched snapshots at tolerance 0.
- **Wave 1 phase windows, 2026-10-05:** a Linux build of `nova-client-src` `nui-wave1` at e3906b7 wrote the 36 goldens of the loading screen, empire select, character select and character create, with `--write --optimize`; that build matches all 139 goldens and the five switched snapshots at tolerance 0. The nine loading goldens take 26 MB of the 34 MB these 36 add, because the fixture stretches the legacy loading photo over the whole frame, which lossless PNG compresses poorly.
- **Wave 1 integration, 2026-10-05:** the `nui-frames` sheet (`components/frames.rcss`) became `display: inline-flex; vertical-align: top` with block frames, the engine's contract; no golden changed, since the loading screen, the only page with the element, already styled it so. A Linux build of `nova-client-src` `nui-wave1` at 73675c3 (the integration's fix, whose `nuitool` is byte-identical to e3906b7's) matches all 139 goldens and the five switched snapshots at tolerance 0.

- **Wave 1 fix stage, 2026-10-05:** the same Linux `nuitool` (`nova-client-src` `nui-wave1` at 73675c3; the fix stage changed only lint in `nuitool`) wrote seven goldens again and two new ones, with `--write --optimize`. `theme-picker-classic-100`: the classic picker buttons have 9dp of padding, so "Modern light" no longer touches the caps. `select-classic-100`, `-150`, `-200`: the empire name is whole ("Chunjo Kingdom", where it was "Chunjo Kingd..."), as legacy draws it. `server-board-classic-100`, `-150`, `-200`: the channel states are plain list text after the name ("CH1 ...."), as legacy writes them, where they were colored pills. New: `select-busy-classic-100` and `create-busy-classic-100`, the classic disabled look on every button while a start or a creation is under way, Start, Create and the selected choices included. The input dialog's two fields (one per type) and the locale strip's flags as buttons changed no pixel. That build matches all 141 goldens and the five switched snapshots at tolerance 0.

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

`--only` works here too, and `--optimize` re-saves each written image with Pillow's optimizer (smaller files, the same pixels). Look at every changed image before committing it, and say in the commit message what changed on screen and why. RmlUi warnings (`rmlui: ...` lines) are listed at the end, and a regeneration that prints one exits 1: it should print none. When the images change because `nuitool` changed, update "Where they come from" with the `nova-client-src` commit that wrote them.

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

## Wave 1 windows

- **The dialogs** are modal: their snapshots show the scrim over the empty frame. The fixtures are the error popup (two lines), a two-line question, the private-code input (secret, 7 characters), the price input and pick money with a maximum of 250. A shown dialog focuses its default button, so in classic the accept and OK buttons show their over art, as a focused classic button does.
- **The server board** fixture has two servers and four channels, one in each state (none yet, normal, busy, full). The classic board is exactly the legacy 375x400 at 100%, 72dp above the bottom edge.
- **The virtual keyboard** fixture is the unshuffled lower case set. At these frame sizes (720dp tall) its 680dp media query shows it.
- **The locale strip** shows the 17 flags from the DDS atlas `severflags_01.dds`; an older `nuitool` draws them transparent.
- **The phase windows** (loading, empire, select, create) are full-screen boards in a 1280x720dp frame. The loading goldens are taken at `--time 0.1`, so the emblem (`nui-frames`, 24 frames of 1/60 s) shows frame 5 (`floor(0.1 / 0.0167) mod 24`). Select and create are overlays: the 3D scene that the client draws under them is not part of the snapshot.
