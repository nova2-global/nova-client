# NovaUI snapshot goldens

Reference images of the two NovaUI pages that cover the components and the renderer, written by `nuitool snap`:

| Page | Document | Frame sizes (scale 1.0, 1.5, 2.0) |
|---|---|---|
| Gallery, every component in every state it styles | `nui/windows/gallery/gallery.rml` with `gallery.fixture.json` | 1920x1080, 2880x1620, 3840x2160 |
| Render test, every renderer feature | `nui/windows/render-test/render-test.rml` | 1280x720, 1920x1080, 2560x1440 |

Each page is stored in both themes at scales 1.0, 1.5 and 2.0, the client's automatic scale for 1080, 1620 and 2160 lines: `<page>-<theme>-<percent>.png`, for example `gallery-light-150.png`. The gallery frames are the client's own sizes at those scales, because the gallery body's height follows the frame (`max-height: 80vh`). The render test's layout does not depend on the frame, so its frames only need to hold it.

All of them use the English strings (`--locale assets/locale/locale/en`) and the default `--time 1`, which lets the window-open fade and the component transitions finish and puts the render test's two endless animations at a fixed phase.

The snapshots come from `SoftRenderInterface`, the CPU renderer. It follows the Direct3D 9 renderer's rules (premultiplied filtering, per-axis wrap, `.sub` regions, the color key; see `src/NovaUI/README.md` in `nova-client-src`), but it is not the client: compare the client against these by eye, not pixel for pixel.

They were written by a Linux (GCC) build of `nuitool` from `nova-client-src` branch `nui-int-c` (a8ce386). A Linux build of `nui-foundation` d0d0a8f matches every image at tolerance 0. A Windows (MSVC) build of the same commit matches the six gallery images at tolerance 0; in four render-test images one or two pixels differ by 1, all inside the rotated text of the clip-mask cell. So the check below allows a difference of 1 per channel, and a build for either platform passes it.

## Check

From the asset repository root, with `nuitool` on `PATH`. Every run exits 0 when its image matches within 1 per channel; a mismatch exits 1 and writes a diff image (magenta where pixels differ) next to the output. A change of 1 per channel anywhere passes too; to catch those, drop `--tolerance 1` and check with a Linux build, the platform that wrote the goldens.

```bash
out=$(mktemp -d)
for theme in dark light; do
  for spec in "1 100 1920x1080 1280x720" "1.5 150 2880x1620 1920x1080" "2 200 3840x2160 2560x1440"; do
    set -- $spec
    nuitool snap --root assets/nui --root assets/icon --locale assets/locale/locale/en \
      --doc nui/windows/gallery/gallery.rml --fixture assets/nui/nui/windows/gallery/gallery.fixture.json \
      --theme $theme --scale $1 --size $3 --out $out/gallery-$theme-$2.png \
      --compare docs/ui/snapshots/gallery-$theme-$2.png --tolerance 1
    nuitool snap --root assets/nui --root assets/icon --locale assets/locale/locale/en \
      --doc nui/windows/render-test/render-test.rml \
      --theme $theme --scale $1 --size $4 --out $out/render-test-$theme-$2.png \
      --compare docs/ui/snapshots/render-test-$theme-$2.png --tolerance 1
  done
done
```

The render test's scroll container holds more than it shows on purpose, so snap prints a `scrolls; the snapshot shows ...` note for it on every run; that note does not change the exit code.

## Regenerate

Regenerate after a change to anything the two pages draw: the files under `assets/nui/nui/` they use, `gallery.fixture.json`, the English strings they show, or `nuitool` itself (the soft renderer, the runtime, RmlUi or FreeType). The same loop, writing into this folder:

```bash
for theme in dark light; do
  for spec in "1 100 1920x1080 1280x720" "1.5 150 2880x1620 1920x1080" "2 200 3840x2160 2560x1440"; do
    set -- $spec
    nuitool snap --root assets/nui --root assets/icon --locale assets/locale/locale/en \
      --doc nui/windows/gallery/gallery.rml --fixture assets/nui/nui/windows/gallery/gallery.fixture.json \
      --theme $theme --scale $1 --size $3 --out docs/ui/snapshots/gallery-$theme-$2.png
    nuitool snap --root assets/nui --root assets/icon --locale assets/locale/locale/en \
      --doc nui/windows/render-test/render-test.rml \
      --theme $theme --scale $1 --size $4 --out docs/ui/snapshots/render-test-$theme-$2.png
  done
done
```

Look at every changed image before committing it, and say in the commit message what changed on screen and why. Snap prints RmlUi warnings as `rmlui: ...` on standard error; a regeneration should print none.
