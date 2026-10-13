# The cyberpunk skin

Cyberpunk x Metin2, the third column of the skins mockup
(`.nui-work/refs/skins-mockup-2026-10-12.png`): deep navy panels with cut
corners, neon cyan edges with a glow, violet accents, a holographic sheen
with fine scan lines, a light that runs along the frames' top edges and
corner cuts that pulse. Body class `skin-cyberpunk`, theme `cyberpunk`
(`nui/theme/themes.json`, last in menu order), palette `cyberpunk`. Every
ported window shows it on its modern layout; the overlays below change the
layout only where the mockup does. Item icons, skill icons and every other
content image keep their pixels: nothing here tints content.

| File | What |
|---|---|
| `tokens.json` | The palette `cyberpunk`, the skin's own tokens (`cyberpunk-...`) and shared overrides, the four color slots, four extra contrast pairs and the theme |
| `cyberpunk-tokens.rcss`, `colors.json` | Generated from `tokens.json` by `python tools/nui_tokens.py`, which checks every contrast pair; do not edit |
| `art.json` | The art manifest: the six sprites below, by numbers |
| `cyberpunk-1x.png`, `cyberpunk-2x.png`, `cyberpunk-sprites.rcss` | Generated from `art.json` by `python3 tools/nui_skin_art.py build` (`check` verifies them); do not edit |
| `cyberpunk.rcss` | The component rules, every selector under `.skin-cyberpunk` |
| `windows/<window>.rcss` | The overlays: a window's own cyberpunk rules, applied after its sheets |
| `snapshots.json` | The skin's own golden cases (reduced motion, reduced effects, effects off, player colors, a live switch, the modal dialogs over the synthetic world, translucent panels) |

## The look

- **Frames** (`nui-window`): the panel sprite as a ninepatch over the border
  box, tinted with `surface`, so the player's panel color and opacity reach
  it. The modern 1dp border stays, transparent, so every window keeps its
  modern layout to the pixel. Title in `cyberpunk-title`, 1dp letter spacing
  and a faint glow (a font effect); the title bar's and the footer's lines in
  `cyberpunk-edge-dim`; the close button a small neon chip.
- **Boards** (`nui-board`, the HUD's framed parts): the chip fill (5dp cuts)
  with the chip's 1dp edge; tiles and panels square, with a dim neon border.
- **Buttons and tabs**: chips. At rest the 1dp edge in `cyberpunk-edge-dim`;
  hovered or focused, the 30% fill under a full edge in `accent` (focus in
  `focus-ring`); pressed, selected tabs and the chat log's active filters, the
  solid fill with `accent-text` labels. Primary and danger buttons keep the
  30% fill at rest.
- **Fields** sunken with a dim neon border, `accent` on hover and focus;
  **toggles** a square track with a diamond knob, the checked track a
  gradient from `accent` to `cyberpunk-edge-alt`; **sliders** a 2dp track, the
  same gradient, a diamond thumb; **gauges** square, their fills brighter
  toward the end (vertex gradients, which every device draws); **slots** a dim
  neon edge, hover the accent edge and a holographic glow under the icon;
  **tooltips** the dark plate with an `accent` edge; **scroll bars** a 4dp
  neon thumb; **glyphs** in `accent`.
- **Modal scrims** blur the world behind a dialog (`backdrop-filter`), except
  the quest's, which keeps the world sharp as legacy does.

## Chrome hooks

The theme asks for `outline`, `corner-tl`, `corner-br`, `edge-top`, `scan`
(frames and boards) and `accent` (title bars); the runtime puts them in
(`docs/ui/AUTHORING.md` "Chrome").

| Hook | On frames | On boards |
|---|---|---|
| `outline` | The panel's edge with its glow baked in, 6dp outside the frame, under the content (`z-index: -1`) | The chip's 1dp edge; the minimap ring's halo (a gradient); none on the skill picker (below) |
| `corner-tl`, `corner-br` | A violet 16dp bar along each cut, pulsing from full to 0.55 opacity over 2.4s, the second half a cycle later | The taskbar's `corner-tl` only |
| `edge-top` | A neon streak running along the top edge every 6s, growing from no width and shrinking to none at its ends (transform only: an opacity fade would regenerate its gradient every frame), resting at no width | The taskbar only |
| `scan` | Scan lines over a cyan to violet sheen across the diagonal, under the content, fading out toward the cuts | The tip and the big notice only |
| `accent` | A short violet bar on the title bar's line, its glow a gradient | |

Three hooks move per frame, `transform` and `opacity` only, with the values
written out; a frame without its hooks' motion (reduced motion) shows the
pulses whole and the streak out. Board hooks other than the outline are
hidden by default: boards are always loaded. The motion rules name the
window frame (`.nui-window > .nui-chrome--corner-tl.nui-anim`), and the
taskbar's overlay moves its bar's two shown hooks itself, since RmlUi
advances an animation on every update even while its element is hidden:
the first cut moved the hidden hooks of every HUD board on every frame (the
P13 review). Each hook is one element per frame; the shown ones draw one
decorator each (the scan two gradients).

**Reduced effects** (the player's setting, and every device without
effects): no scan layer, no edge streak, no minimap halo or rim, no HP ring
track and no empire grid (without effects a gradient draws one flat color
over its whole box), the title accent a plain bar; the scrim's blur goes
(`base.rcss`). Toggle, slider and slot gradients stay: their flat color is
under their parts.

## Art

Six white sprites with alpha, drawn from numbers by `tools/nui_skin_art.py`
(`art.json`), at 1x and 2x (the 2x sprites drawn from the doubled numbers,
never upscaled), each in a gutter of its own edge texels, tinted by
`image-color` from tokens. Everything else is code.

| Sprite | 1x, 2x | Bytes alone (1x, 2x) | Drawn as | Why it is art |
|---|---|---|---|---|
| `panel` | 48, 96 px; 10px cuts at the top left and bottom right | 201, 306 | the frame fill (ninepatch), tinted `surface` | RCSS rounds corners only; a 45-degree cut on a box of any size would take two nested `mask-image` layers per element per frame |
| `panel-edge` | 64, 128 px; a 1px line, 6px glow at 0.45 | 1,058, 2,320 | the frame outline hook, tinted `cyberpunk-edge` | the same cut, and a glow that follows it; a `box-shadow` is a rectangle and a texture made at first show |
| `chip-solid` | 24, 48 px; 5px cuts | 126, 201 | board fills, pressed and selected chips | the cut at chip size |
| `chip` | 24, 48 px; 5px cuts, alpha 0.3 | 139, 202 | hovered chips, under `chip-edge` | one element has one `image-color`, so the 30% fill is baked into its alpha and shares the edge's tint |
| `chip-edge` | 24, 48 px; a 1px line | 181, 259 | chip and board edges | the cut's outline |
| `ring` | 40, 80 px; a 3px line, 2px glow at 0.5 | 813, 2,313 | the taskbar's HP ring (`fill-image`), tinted `cyberpunk-hp` | a circular `<progress>` draws its fill from an image only, cut by its value |

The sheets: `cyberpunk-1x.png` 256 x 68 px, 2,674 bytes; `cyberpunk-2x.png`
512 x 136 px, 6,435 bytes. The art is white, so no texel is the client's
`#FF00FF` color key.

## Overlays

| Window | What changes |
|---|---|
| `taskbar` | The bar as the cut-corner panel with the glowing outline, the edge streak and the violet cut; the HP ring (P13 D21) at its left with the HP value inside (9dp, so five digits stay off the ring's stroke), the SP value right of the right mode button; the mall button right of the ring and the HP, SP and stamina bars 106dp wide, so the left group still ends at 268dp; every button a chip; the EXP orbs filled violet to cyan |
| `minimap` | A 1dp neon ring with a halo, a ring of ticks between the map and the ring, the map's rim faded into the disc by a gradient ring the frame draws over it (not a mask: a mask took two layers on every idle frame), violet round buttons, the place line on a neon plate |
| `chat` | The open chat framed by one dim neon edge; the mode, send, whisper and log buttons as chips |
| `chat-log` | The filters as a strip of neon tabs, the active ones filled, with the modern letter spacing (1dp more ran the long locales' labels past their chips); the mode button a chip; a thin neon scroll bar |
| `target` | The name in `cyberpunk-title` with a glow |
| `party` | The role and menu buttons as neon chips |
| `affects` | Each icon in a dim neon chip; the time left in `accent` |
| `tip-board`, `big-board` | The notice boards with a neon edge and the scan layer; the big notice's text glows |
| `gift-box`, `expanded-taskbar`, `game-buttons`, `edge-buttons`, `energy-bar`, `map-name` | Chips, neon plates and glowing standalone text |
| `shop-signs` | Each sign a violet-edged plate, the shop's name in `cyberpunk-name` |
| `loading` | The spinner as a neon sweep (a conic gradient), the bar as a neon gauge |
| `empire` | The scene's bands in the holographic cyan and a faint grid between them |
| `quest` | No blur behind the quest; solid choices on the scroll skin's paper |
| `system-options`, `theme-picker` | A block layout instead of the modern flex one (below) |

## Player colors

The theme offers the four slots (`nui.get_color_slots()`, the Interface
section): `accent` also sets `cyberpunk-edge`, its glow, the holographic cyan
and the dim edge, so a player's accent recolors the neon; `panel` the
surfaces; `opacity` makes the panels translucent with no backdrop blur (a
backdrop blur clips to the border box, which a cut-corner fill does not
fill); `highlight` also sets `cyberpunk-name`. The `colors` golden cases show
a violet accent and a cyan highlight.

## Limits found

- **No `text-transform`.** RmlUi 6.3 upper-cases ASCII letters only
  (`ElementText.cpp`), so the mockup's upper-case titles would mix cases in
  most locales; titles and tabs keep their case and take letter spacing.
- **No `box-shadow`.** Each shadow is a render target texture made the first
  time its element shows (about 8 ms on the device in the P13 effects bench,
  so a hover glow would hitch), and a device without effects drops the
  element's background and border with it. Glows are baked into the outline
  art or drawn as gradients.
- **Auto-height flex frames.** RmlUi 6.3 sizes an absolute child by its top
  and bottom against an auto-height flex container's unsized box
  (`FlexFormattingContext.cpp` keeps the box it started from), so a hook in
  such a frame ends at its top. The system options and the theme picker are
  blocks in this skin; the skill picker draws a plain neon border.
- **The HP ring's sprite and a live scale switch.** A `<progress>` loads its
  `fill-image` when the property changes, not when the 2x sprite sheet's
  media query does, so after a live scale switch across 1.125 the ring may
  keep the other sheet's sprite until the theme changes (inferred from
  `ElementProgress.cpp`, not seen live).

## What the skin cost outside this folder

The proof of P13 item 6 (spec 7.9): writing the skin touched **no content
file** outside this folder (nothing under `nui/windows/`, `nui/components/`,
`nui/theme/`, `assets/root/`, nor `base.rcss` or `nui.rtpl`).

- **Support files:** `tools/nui_skin_art.py` and `tools/nui_skin_art_test.py`
  (generic: any skin can draw its art with them), and the skin's goldens
  under `docs/ui/snapshots/` (`*-cyber-*.png`: the full matrix of 212 and the
  38 cases of `snapshots.json`).
- **Registration,** the cost of any new skin, made before the skin was
  written: the `themes.json` entry with its `chrome` list, the
  `golden-themes.json` entry, three `nui.rtpl` links, `THEME_CYBERPUNK` in the
  17 `locale_interface.txt` files and two rows of `tools/nui_button_fit.py`.
- **The chrome hooks and the taskbar's optional parts** (P13 items 3 and D21)
  belong to the shared chrome and the design-rule pass.

## Tokens

The palette (every color of the `dark` palette's keys) and the skin's own tokens, generated from `tokens.json`:

<!-- skin-tokens:begin (generated by tools/nui_tokens.py; do not edit by hand) -->

| Token | cyberpunk |
|---|---|
| `--surface` | `#0b1322` |
| `--surface-raised` | `#101c30` |
| `--surface-sunken` | `#060c17` |
| `--surface-hover` | `#16283f` |
| `--surface-band` | `#060c17e0` |
| `--scene` | `#050a14` |
| `--scene-band` | `#0b1322` |
| `--border` | `#1e4f73` |
| `--text` | `#e6f6ff` |
| `--text-muted` | `#9cb8cc` |
| `--text-inverse` | `#e6f6ff` |
| `--accent` | `#2fd4ff` |
| `--accent-hover` | `#85e6ff` |
| `--accent-text` | `#03131f` |
| `--danger` | `#ff5c8a` |
| `--danger-hover` | `#ff8cab` |
| `--warning` | `#ffc857` |
| `--success` | `#4dffb5` |
| `--focus-ring` | `#c77dff` |
| `--selection` | `#123955` |
| `--overlay-scrim` | `#02050acc` |
| `--tooltip-bg` | `#08111e` |
| `--ember` | `#ffb24ff2` |
| `--ember-hot` | `#fff3cff7` |
| `--ember-glow` | `#ff9e3a47` |
| `--sheen` | `#ffffff73` |
| `--sheen-clear` | `#ffffff00` |
| `--sweep` | `#fff6dc8c` |
| `--sweep-clear` | `#fff4d600` |
| `--gauge-track` | `#060c17` |
| `--gauge-red` | `#ff4d7a` |
| `--gauge-pink` | `#ff6fb5` |
| `--gauge-purple` | `#b06bff` |
| `--gauge-blue` | `#36a8ff` |
| `--cooldown-shade` | `#00000080` |
| `--slot-disabled` | `#ff5c8a59` |
| `--slot-locked` | `#0000008c` |
| `--slot-picked` | `#2fd4ff59` |
| `--notice-bar` | `#02050ab3` |
| `--notice-text-big` | `#9fefff` |
| `--edge-gm` | `#ffb347` |
| `--party-link` | `#e6f6ff` |
| `--party-unlink` | `#6f8799` |
| `--hp-recovery` | `#ff4d7a55` |
| `--sp-recovery` | `#36a8ff55` |
| `--chat-talking` | `#e6f6ff` |
| `--chat-info` | `#ffb4b4` |
| `--chat-notice` | `#ffd166` |
| `--chat-party` | `#5ff0e0` |
| `--chat-guild` | `#e2f36b` |
| `--chat-command` | `#9fe6c3` |
| `--chat-shout` | `#9fe6c3` |
| `--chat-whisper` | `#6dffb0` |
| `--chat-big-notice` | `#ffd166` |
| `--chat-view-shade-top` | `#060c1700` |
| `--chat-view-shade-bottom` | `#060c17cc` |
| `--chat-edit-shade` | `#0b1322d9` |
| `--chat-mark` | `#ffc857` |
| `--text-outline` | `#000000` |
| `--quest-text` | `#e6f6ff` |
| `--quest-body` | `#b9cde0` |
| `--quest-title` | `#ffd166` |
| `--highlight` | `#ffd166` |
| `--quest-reward` | `#ff9fbf` |
| `--quest-item` | `#ff6b8a` |
| `--quest-scrim` | `#00000000` |
| `--letterbox` | `#000000` |
| `--fade-black` | `#000000` |
| `--fade-white` | `#ffffff` |
| `--console-bg` | `#060c17e0` |
| `--console-field` | `#060c17` |
| `--console-text` | `#e6f6ff` |
| `--console-grip` | `#1e4f73` |
| `--web-page` | `#060c17` |

| Skin token | Value |
|---|---|
| `--radius-sm` | `1dp` |
| `--radius-md` | `2dp` |
| `--radius-lg` | `2dp` |
| `--cyberpunk-edge` | `#2fd4ff` |
| `--cyberpunk-edge-dim` | `#1a6f99` |
| `--cyberpunk-edge-alt` | `#c06bff` |
| `--cyberpunk-glow` | `#2fd4ff59` |
| `--cyberpunk-glow-alt` | `#c06bff4d` |
| `--cyberpunk-holo-a` | `#2fd4ff1f` |
| `--cyberpunk-holo-b` | `#c06bff17` |
| `--cyberpunk-scan` | `#ffffff0a` |
| `--cyberpunk-hp` | `#ff4d7a` |
| `--cyberpunk-sp` | `#36a8ff` |
| `--cyberpunk-title` | `#c9f3ff` |
| `--cyberpunk-name` | `#ffd166` |
| `--cyberpunk-link` | `#ff9f43` |

<!-- skin-tokens:end -->
