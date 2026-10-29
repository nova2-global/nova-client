# The cyberpunk skin

Cyberpunk x Metin2, after the reviewed skins mockup of stage 2 (the
`.skin-cyberpunk` rules and the `.nui.theme-cyberpunk` palette of
`nova-skins.css`; the gallery's design is `skins-stage2/ref/Kit-cyberpunk.png`):
deep violet-black panels cut at the top right and bottom left, thin neon
cyan lines, a magenta second accent and an acid third, a faint holographic
sheen with fine scan lines, a neon tab that runs along the frames' top
edges and corner brackets that pulse. Body class `skin-cyberpunk`, theme
`cyberpunk` (`nui/theme/themes.json`, last in menu order), palette
`cyberpunk`. Every ported window shows it on its modern layout; the
overlays below change the layout only where the mockup does. Item icons,
skill icons and every other content image keep their pixels: nothing here
tints content.

| File | What |
|---|---|
| `tokens.json` | The palette `cyberpunk`, the skin's own tokens (`cyberpunk-...`) and shared overrides, the five color slots, five extra contrast pairs and the theme |
| `cyberpunk-tokens.rcss`, `colors.json` | Generated from `tokens.json` by `python tools/nui_tokens.py`, which checks every contrast pair; do not edit |
| `art.json` | The art manifest: the eleven sprites below, by numbers |
| `cyberpunk-1x.png`, `cyberpunk-2x.png`, `cyberpunk-sprites.rcss` | Generated from `art.json` by `python3 tools/nui_skin_art.py build` (`check` verifies them); do not edit |
| `cyberpunk.rcss` | The component rules, every selector under `.skin-cyberpunk` |
| `windows/<window>.rcss` | The overlays: a window's own cyberpunk rules, applied after its sheets |
| `snapshots.json` | The skin's own golden cases (reduced motion, reduced effects, effects off, player colors, a live switch, the modal dialogs over the synthetic world, translucent panels) |

## The look

- **Palette** (the mockup's): panels `#0a0816`, raised `#161230`, wells
  `#05040d`; text `#ebe7ff`, muted `#a39dca`; the lines are the cyan at 20%
  (`border`), 45% (`cyberpunk-edge-dim`) and 70% (`cyberpunk-edge`); cyan
  `#23e5ff` (`accent`), magenta `#ff2bd1` (`cyberpunk-edge-alt`), acid
  `#e9ff3b` (`cyberpunk-acid`, also `focus-ring`); danger `#ff3d71`, HP
  `#ff2e6a`, SP `#2e9bff`, ok `#3bffb0`, warn `#ffd23b`. Tooltip plates
  (`tip-bg`, `tooltip-bg`) are the shared 51% black of every theme.
- **Frames** (`nui-window`): the panel sprite (12dp cuts at the top right
  and bottom left) as a ninepatch over the border box, tinted with
  `surface`, so the player's panel color and opacity reach it. The modern
  1dp border stays, transparent, and the modern title bar and body padding
  stay, so every window keeps its modern layout to the pixel. Title in
  `cyberpunk-title`, 12dp (a size below modern's, so tracked 0.5dp it takes
  the modern width: a long German title still fits), with a faint glow (a
  font effect);
  the title bar's line the 20% cyan, no line above the footer; the close
  button the modern ghost, its cross muted, magenta under the pointer.
- **Boards** (`nui-board`, the HUD's framed parts): the board fill (6dp cuts
  at the top left and bottom right) with the board's 1dp edge in
  `cyberpunk-edge-dim`. A board that is a document's `<body>` (the theme
  picker, the belt) is drawn as a frame. **Tooltip boards** (the item, skill
  and link tooltips, the refine and attach dialogs' item boards, the target
  board) take the frame's cut shape on `tip-bg` with the frame's outline and
  an acid bar down the top of the left edge; an inset one is on `scene`.
  **Tiles** square, raised, with the 20% line; **panels** square: raised
  with the 45% line, sunken in the well, flat with a magenta line.
- **Buttons**: chips cut 7dp at the bottom right, labels tracked 0.5dp
  (1dp ran long translations past the system options' fixed-width choice
  rows). The
  chip's fill (baked at 20%) and its edge share one tint: at rest the 45%
  line, hovered the 70% line with a white label, pressed the full accent;
  keyboard focus the acid edge alone; a selected choice (`is-selected`) acid
  fill, edge and label. Primary the solid cyan chip (its focus an acid notch
  in the cut, the button's background, which only the cut uncovers: a
  dialog's default button has the focus when it opens); danger the magenta
  chip; ghost no chip until hovered; icon buttons square boxes with the
  glyph in the accent. Disabled at 35%.
- **Tabs**: tracked labels over the row's 20% line, on the modern 32dp (a
  5dp gap above 26dp tabs); the selected tab lit, a soft cyan rising from
  the line (a vertex gradient) and a magenta underline; the modern
  indicator, hidden in modern, is shown as that 2dp underline and slides
  with the modern motion.
- **Fields**: the well with the 20% line and a 70% underline, the 45% line
  hovered and focused (the underline in the accent focused), danger when
  invalid; labels and errors tracked 1dp. **Toggles**: the mockup's slanted
  32 x 14dp track and 10 x 8dp knob (sprites), the dim line off, the
  accent's soft fill and line on. **Sliders**: a 3dp track in the soft cyan,
  a magenta-to-cyan fill (a vertex gradient), a white 6 x 16dp bar thumb in
  a 2dp halo, acid while pressed. **Gauges**: square, the fill lit from the
  top by a white sheen (a vertex gradient) under dark segment gaps every
  8dp; HP pink-red, SP blue, stamina and EXP acid.
- **Lists**: square rows, hovered in the cyan-tinted hover, the selected one
  white on the soft cyan with a magenta left edge. **Badges**: acid tags (a
  10% fill, a 45% edge), the variant in the label's color. **Slots**: square
  cells with the faint cyan fill (`cyberpunk-cell`) and the 20% line;
  hovered the soft cyan and the accent edge, selected magenta, an active
  item's edge acid; counts acid. **Hint tooltips**: the overlay black with
  the 70% line. **Scroll bars**: a 4dp thumb in the 45% cyan. **Glyphs** in
  `accent`.
- **Modal scrims** blur the world behind a dialog (`backdrop-filter`), except
  the quest's, which keeps the world sharp as legacy does.

## Chrome hooks

The theme asks for `outline`, `corner-tl`, `corner-br`, `edge-top`, `scan`
(frames and boards) and `accent` (title bars); the runtime puts them in
(`docs/ui/AUTHORING.md` "Chrome").

| Hook | On frames | On boards |
|---|---|---|
| `outline` | The panel's edge in `cyberpunk-edge` with a soft glow baked in, 6dp outside the frame, under the content (`z-index: -1`) | The board's 1dp edge; on tooltip boards the frame's (the target's the board's, red); the minimap ring's halo (a gradient); none on the taskbar's band or the skill picker (below) |
| `corner-tl`, `corner-br` | A 14dp bracket 3dp outside each square corner, magenta at the top left and in the accent at the bottom right, pulsing from full to 0.55 opacity over 2.4s, the second half a cycle later | Hidden unless an overlay shows them (the loading panel's, pulsing as a frame's); none on tooltips |
| `edge-top` | A 44dp neon tab on the top edge, 18dp from its left end, that every 6s runs toward the right end, shrinking to nothing (transform only: an opacity fade would regenerate its gradient every frame), and grows back in place; it rests in place | Hidden unless an overlay shows it (the loading panel's tab, running as a frame's; the taskbar's a still faint magenta line under its top line; the target's a still red line along its top); on tooltip boards a still 3 x 36dp acid bar down the left edge |
| `scan` | Scan lines over a faint sheen, cyan in the top left corner and magenta in the bottom right one, clear between them (so the cut corners stay clear), under the content | Where an overlay shows it: the tip, the big notice, the loading panel and the taskbar (its scan lines alone) |
| `accent` | A short magenta bar on the title bar's line, its glow a gradient | |

Three hooks move per frame, `transform` and `opacity` only, with the values
written out; a frame without its hooks' motion (reduced motion) shows the
brackets whole and the tab in place. Board hooks other than the outline are
hidden by default: boards are always loaded. The motion rules name the
window frame (`.nui-window > .nui-chrome--corner-tl.nui-anim`), and an
overlay that shows a board's moving hooks moves that board's alone, since
RmlUi advances an animation on every update even while its element is hidden:
the first cut moved the hidden hooks of every HUD board on every frame (the
P13 review). Each hook is one element per frame; the shown ones draw one
decorator each (the scan two gradients).

A board's hooks are placed against the nearest positioned ancestor, so a
board must be positioned to hold them. Every window positions its boards
but the inset tooltip boards, which this sheet makes `position: relative`;
the component cannot do so for every board, since that would outweigh the
windows' own `position: absolute` (the gallery's sample boards are static:
their outlines frame the gallery window until the gallery's overlay
positions them).

**Reduced effects** (the player's setting, and every device without
effects): no scan layer, the edge tab a plain resting bar, no minimap halo,
rim, radar rings or ticks, no spark on an active quickslot and no empire
grid (without effects a gradient draws one flat color over its whole box),
the title accent a plain bar, the chat's sizing line plain; the
scrim's blur goes (`base.rcss`). The slider and gauge vertex gradients stay;
the gauges' segment gaps go (a repeating gradient whose first and last
stops are clear draws nothing there).

## Art

Eleven white sprites with alpha, drawn from numbers by
`tools/nui_skin_art.py` (`art.json`), at 1x and 2x (the 2x sprites drawn
from the doubled numbers, never upscaled), each in a gutter of its own edge
texels, tinted by `image-color` from tokens. Everything else is code.

| Sprite | 1x, 2x | Bytes alone (1x, 2x) | Drawn as | Why it is art |
|---|---|---|---|---|
| `panel` | 48, 96 px; 12px cuts at the top right and bottom left | 219, 327 | frame and tooltip fills (ninepatch), tinted `surface` or `tip-bg` | RCSS rounds corners only; a 45-degree cut on a box of any size would take two nested `mask-image` layers per element per frame |
| `panel-edge` | 64, 128 px; a 1px line, 6px glow at 0.3 | 1,036, 2,082 | the frame and tooltip outline hook, tinted `cyberpunk-edge` | the same cut, and a glow that follows it; a `box-shadow` is a rectangle and a texture made at first show |
| `chip-solid` | 24, 48 px; a 7px cut at the bottom right | 119, 176 | primary, pressed danger and pressed close buttons | the cut at button size |
| `chip` | 24, 48 px; the same, alpha 0.2 | 125, 179 | every other button's fill, under `chip-edge` | one element has one `image-color`, so the fill's alpha is baked and shares the edge's tint |
| `chip-edge` | 24, 48 px; a 1px line | 153, 218 | button and chip edges | the cut's outline |
| `board` | 24, 48 px; 6px cuts at the top left and bottom right | 132, 215 | HUD board fills, tinted `surface` or `notice-bar` | the board's cut |
| `board-edge` | 24, 48 px; a 1px line | 189, 272 | the board outline hook | the cut's outline |
| `skew` | 16, 32 px; 4px cuts at the top left and bottom right, alpha 0.15 | 119, 164 | the checked toggle track's fill | the mockup's slanted track; a skew transform draws stair-stepped edges |
| `skew-edge` | 16, 32 px; a 1px line | 157, 205 | the toggle track's edge | its outline |
| `knob` | 12, 24 px; 3px cuts | 107, 132 | the toggle's knob | the slanted knob |
| `ring` | 40, 80 px; a 3px line, 2px glow at 0.5 | 813, 2,313 | the taskbar's HP ring (`fill-image`), tinted `cyberpunk-hp`; unused since stage 2 (the ring is hidden) | a circular `<progress>` draws its fill from an image only, cut by its value |

The sheets: `cyberpunk-1x.png` 256 x 112 px, 2,857 bytes; `cyberpunk-2x.png`
512 x 224 px, 6,843 bytes. The art is white, so no texel is the client's
`#FF00FF` color key.

## Overlays

| Window | What changes |
|---|---|
| `taskbar` | The modern layout (the reviewed mockup has no HP ring, so the optional HP ring and values of P13 D21 stay hidden): the bar a band lit from the top under a cyan top line and a faint magenta one, with scan lines; the mall button a magenta ring with the shop glyph in pink; the gauges square, segmented, on the dark well, the HP chip white; the EXP orbs four acid cells filled from the bottom under dark hatching, the percent in acid; the middle well and the quickslots cut (the board and chip outlines), a slot lit in the accent under the pointer, acid while active, magenta selected, the grade tags dark and edged in their grade's color; the mouse modes magenta chips; the pager and window buttons bare, a window button a soft cyan with a magenta underline under the pointer |
| `minimap` | The steel bezel a dark band between a 1dp neon ring on the map's edge and a faint outer ring, cyan ticks every 10 degrees on it and a soft halo outside it; faint radar rings and the map's rim faded into the band, both drawn by a gradient the frame draws over the map (not a mask: a mask took two layers on every idle frame); the north mark magenta; square dark buttons, the close one magenta; the place line and observers on dark plates with a magenta left edge, in `accent` |
| `chat` | The open history square with a magenta left edge, its sizing bar a neon line fading at both ends; the input row square; the mode a magenta tag with a pink label, the send, whisper and log buttons square boxes with a dim edge; item links square acid tags |
| `chat-view` | Item links the chat's square acid tags |
| `chat-log` | The chat chip a square neon box; the filters a strip of plain tracked labels over one dim line (the modern letter spacing: 1dp more ran the long locales' labels into each other), a filter that is on lit in `accent` over a magenta underline (a gradient in its content box; its bottom border under reduced effects); the lines' well square with a magenta left edge; the mode button a magenta chip, send a cyan outline chip; a thin neon scroll bar |
| `target` | The board's cut (top left, bottom right) on `tip-bg` with a thin red edge and a red top line; the name lit with a red glow; the level a slanted red tag (the toggle track's sprites); the percent red; the bar square on the dark well, its chip white |
| `party` | Each member's board cut (the row draws the dark fill, the tile the dim neon edge, `accent` under the pointer); the role tile square, acid for the leader and magenta for an attacker, the pictograms in `accent`; the HP bar square on the dark well; the menu toggle a dark cut tile with a dashed neon rule; the role and menu buttons square dark chips |
| `affects` | Each icon in a thin square neon frame (acid on a timed affect); the time left in acid on a square tag |
| `tip-board`, `big-board` | The notice boards with a neon edge and the scan layer, the tip's line 9dp in, clear of the cut; the big notice's text glows |
| `gift-box` | The frame's dark cut panel around a neon chip, the present in neon lines of `accent` with a magenta ribbon |
| `expanded-taskbar`, `game-buttons`, `edge-buttons`, `energy-bar` | Chips and neon plates; the game buttons square dark chips with the plus in `accent` |
| `shop-signs` | Each sign a violet-edged plate, the shop's name in `cyberpunk-name` |
| `inventory` | The paper doll's well square on fine cyan scan lines and a holographic lattice, a magenta glow behind the figure (none without effects), magenta corner brackets, the rune circle in neon with a magenta glow ring; the wear cells dark plates cut at the bottom right (the place draws the `cooldown-shade` fill, the cell the cut edge: one element has one `image-color`), the line dim when empty and `accent` under the pointer; the costume, dragon soul and item shop buttons dark plates with the board's magenta cut outline (acid while the dragon soul's effect is on); the stats square plates with magenta icons; the page tabs the skin's underlined tabs on the modern 32dp; the coin and the amount acid over the field's neon underline; the rail's grip magenta |
| `costume`, `equipment-view` | The stage as the inventory's doll (square, scan lines, lattice, magenta glow; none without effects), the wear cells its dark cut plates; the costume's rune magenta with an acid glow ring, its two empty frames the same plates (the fill rounded inside the cut, the cut's line over it); the equipment view's code-drawn figure a faint cyan hologram, its cells acid under the pointer |
| `belt-inventory` | The fold bar a square well on the 45% line, its chevron in `accent`; the cells beyond the belt's grade hatched faintly (clear first and last stops, so a device without effects shows the plain dim cell) |
| `item-tooltip`, `link-tooltip` | The socket frames square on a dark well with a 1dp line (the modern 36dp box), silver or acid; the dividers dashed (whole without effects); the name lit with a glow of its color |
| `skill-tooltip` | The name tracked 1dp and lit; the divider a neon line from magenta to cyan fading at both ends (one flat line without effects) |
| `character` | Status: the face's ring acid with an acid glow, the level an acid tag, the name tracked and lit, the class an acid tag, the EXP well with an acid left edge, the headings in `accent`, tracked, the points an acid tag, the stat cards square wells (base and vital with a brighter top line, extra with a cyan left line). Skills: the group choices underlined tabs, the active grid's well with a magenta left edge, a magenta split, the reached steps and the plus buttons acid. Emotions: the headings magenta bars with a magenta left edge. Quests: muted chevrons, a square neon rail with a cyan-to-magenta thumb. The page tabs the skin's underlined tabs, tracked 0.5dp (the Greek four fit the 316dp) |
| `dragon-soul` | The altar square under a magenta glow; the sigil's rings and hexagram in neon cyan, its middle ring dashed magenta (a repeating conic gradient under a disc of the altar's color that leaves its rim, so it turns with the sigil; a plain magenta ring without effects), the core magenta; the worn cells dark plates in the board's cut with a 70% line, acid while active; the deck choices square boxes, the chosen acid; the kind tabs square, the shown one with a magenta underline; the kind's name in `cyberpunk-name`; the grades underlined tabs |
| `dragon-soul-refine` | The cells' well square, a closed cell faintly hatched with a muted lock; the arrow magenta; the modes underlined tabs; the fee a square well with an acid left edge and an acid coin |
| `refine`, `attach-metin` | The inset item boards the mockup's wells: square, opaque on `scene`, the dim line with a 2dp magenta left edge, without the floating tooltip's outline and acid bar; their socket frames and dividers as the item tooltip's. The refine's item cell square on the 45% line, its materials square wells with an `accent` left edge, the cost on an acid tag's fill and line; the attach's arrow magenta, the stone square with an acid line |
| `dragon-soul`, `dragon-soul-refine`, `refine`, `attach-metin`, `select-item`, `equipment-view` | The title's icon chip a square on the 45% line over the holographic cyan; select item's grid well square |
| `exchange`, `shop`, `private-shop`, `safebox`, `safebox-password`, `mall`, `pick-money`, `guild`, `guild-mark`, `guild-building` | The title's emblem in a cut chip (the button chip's fill and edge, tinted the dim neon line), one part of its pictogram magenta |
| `exchange` | The amounts in square wells with a neon underline, the coin in the warning gold; the lamps cut chips on the faint line with a neon ring; the rule between the columns magenta fading into cyan |
| `shop`, `safebox` | The shop's tabs and the safebox's pages as the skin's underlined tabs (muted labels over the row's dim line, the shown one lit on a soft cyan over a magenta underline) instead of the modern segmented well, the row keeping its 32dp |
| `private-shop` | The shop's name in a square well with the focused field's look (the 45% line, the `accent` underline) |
| `guild` | Square cards on the cell fill under title bars lit cyan to magenta, their titles in `accent`, tracked, their rules fading out; square wells (the values' underline magenta); the table heads in `accent` (the buildings' muted); square rows on the cell fill; square checks with an acid mark; the board's notices acid (edge, a film fading out, the "!"), its delete buttons magenta wells; the mark in the board sprite's cut frame with a magenta inner ring; the enemies behind magenta diamonds; the skill covers the board's cut outline; the "+" acid; the points an acid tag; the key cap magenta; a square `accent` scroll thumb; the tabs underlined as the skin's tabs |
| `guild-mark`, `guild-building` | The lists square wells on the cell fill, the selected row lit from cyan inside the 70% line with the magenta left edge; the building's headings in `accent`, tracked, its values square; the mark list's thumb square in `accent` |
| `guild-war` | Each board cut as the HUD boards (the slot draws the board fill, the board its edge), the rows square wells, the first with a magenta left edge, the marks framed in the dim neon line |
| `guild-war-accept` | The declaring guild in a square well with a neon underline, its crest a magenta diamond in a magenta halo |
| `loading` | The gauge panel (a board) drawn as a window frame: the cut-corner panel, its glowing outline, the corner brackets and edge tab (moved by the overlay, the screen's one board) and the scan layer; the spinner as a neon sweep (a conic gradient); the bar the skin's segmented gauge in acid in a square dark track |
| `empire` | The scene's bands in the holographic cyan and a faint grid between them, lit by a cyan glow behind the atlas and a magenta haze below it (none under reduced effects); the flag and description in square wells, the description with a magenta left edge; the arrows boxes cut at the top left and bottom right (the board's edge sprite), `accent` under the pointer |
| `quest` | No blur behind the quest; the corner brackets magenta L's without ticks, the top sheen a magenta haze from the top left (none under reduced effects or on the scroll skin); the speaker's title run in acid, tracked and lit; Next tracked; solid choices on the scroll skin's paper |
| `quest-curtain` | The black letterbox bars with the dim neon line on their inner edges |
| `atlas`, `web` | The title chip a square neon box; the atlas's map rim in `accent`, square, under a faint magenta haze (the map keeps its pixels) |
| `music-list` | The music chip square; the rows muted between faint cyan hairlines, the selected one white and lit on a soft cyan fading out with the magenta edge; square scroll arrows with `accent` wedges, a thin cyan track and an `accent` thumb; a dim line over the buttons |
| `login`, `server-board`, `virtual-keyboard`, `locale-strip` | The login card's look: the server row a square status well with an acid left edge, the pictograms muted; the server board's title lit and tracked, its lists in square wells; Enter the solid `accent` chip and the special keys muted (acid while on); the flag strip's bottom edge the dim neon line, the selected flag's chip square with a magenta underline |
| `select`, `create` | Square wells (the description with a magenta left edge); the slots dark cells on a faint cyan line, the chosen one on the soft fill in the dim neon line with the magenta left edge; the chosen gender and shape solid `accent` chips; the rotate arrows the modern blades on a neon edge (`accent` under the pointer), with no box or label |
| `theme-picker` | The heading in `accent`, tracked; the themes plain labels, a dim chip under the pointer, the theme in use the solid `accent` chip |
| `system-options`, `theme-picker` | A block layout instead of the modern flex one (below) |
| `system-options` | The title's tile square with the dim neon line; the sound and music rows open; the labels a size smaller, tracked 0.5dp; the legacy rows' choices with 7dp sides (more room for long locales); the section headings in `accent` over a rule fading out; square swatches; the overlay opacity row a square magenta box |
| `messenger` | The rows in a square well; a group row an `accent` heading, tracked, over a faint line; a member's person in `accent` with a magenta presence dot (a plain square without effects); the selected row a soft cyan fading out with a magenta edge; a cyan-to-magenta scroll thumb; the four actions as chips, their plus and minus badges magenta; the grip a dashed neon line |
| `whisper` | The lines on `tip-bg` in a square well; a magenta-to-cyan scroll thumb; the compose row open but for a line along its top; minimize muted as the close; the corner grip in `accent` |
| `system-menu`, `restart` | Glyphs in `accent`, labels tracked 1dp; the mall and restart here the acid chip with an acid label, the exit glyph magenta |
| `game-options` | The title's tile square; every other row open but for an `accent` line down its left edge and a soft cyan fading out; the labels a size smaller, tracked |
| `help` | The heading lit and tracked as a frame's title, its tile square; each line open but for a neon line down its left edge and a soft cyan fading out, its bullet magenta; the guide's cards square on the cell fill |
| `change-password`, `dialog-input`, `dialog-money` | The title's tile a square with the dim neon line on the cell fill (modern's selection fill read as a teal block), as in the system and game options and the help; the change password's labels a size smaller, tracked |
| `dialog-question` | The outline hook in magenta (the board's runs from magenta into cyan; one ninepatch takes one tint, and the accent bracket keeps the cyan end) |
| `console` | The resize grip a square corner bracket in `accent` |

## Player colors

The theme offers five slots (`nui.get_color_slots()`, the Interface
section): `accent` also sets the lines (`border`, `cyberpunk-edge-dim`,
`cyberpunk-edge`, `tip-divider`), the glow, the holographic cyan and the
cell fill (each the color at its own alpha), so a player's accent recolors
the neon; `panel` the surfaces; `opacity` makes the panels translucent with
no backdrop blur (a backdrop blur clips to the border box, which a
cut-corner fill does not fill); `overlay` the alpha of `tip-bg` and
`tooltip-bg` (30 to 100, 51 by default, as the modern palettes); `highlight`
also sets `cyberpunk-name` and `tip-special`. The `colors` golden cases
show a violet accent and a cyan highlight.

## Limits found

- **No `text-transform`.** RmlUi 6.3 upper-cases ASCII letters only
  (`ElementText.cpp`), so the mockup's upper-case titles, labels and buttons
  would mix cases in most locales; they keep their case and take letter
  spacing. The mockup's fonts (Oxanium, Share Tech Mono) need an exe change;
  the skin keeps Noto Sans.
- **No `box-shadow`.** Each shadow is a render target texture made the first
  time its element shows (about 8 ms on the device in the P13 effects bench,
  so a hover glow would hitch), and a device without effects drops the
  element's background and border with it. Glows are baked into the outline
  art, drawn as gradients or as a translucent border (the slider thumb's
  halo); the mockup's glows on buttons, slots and gauges are left out.
- **No gradient along an outline.** The mockup's frame outline runs from
  cyan to magenta; a ninepatch takes one `image-color`, and a gradient
  through a mask would cost two layers per window per frame. The outline is
  the cyan at 70%, with the magenta in the top left bracket, the title's
  accent and the sheen's bottom right corner.
- **Two inks on one chip.** A chip's fill and edge share one tint, so the
  mockup's cyan button with an acid focus line is the acid edge alone, and
  the solid primary shows its focus as an acid notch in its cut.
- **Gradient stops at one position.** RmlUi does not keep the order of two
  color stops at the same position, so a hard edge is written as a 1dp (or
  0.1dp) ramp.
- **Auto-height flex frames.** RmlUi 6.3 sizes an absolute child by its top
  and bottom against an auto-height flex container's unsized box
  (`FlexFormattingContext.cpp` keeps the box it started from), so a hook in
  such a frame ends at its top. The system options and the theme picker are
  blocks in this skin; the skill picker draws a plain neon border.
- **The HP ring's sprite and a live scale switch.** A `<progress>` loads its
  `fill-image` when the property changes, not when the 2x sprite sheet's
  media query does, so after a live scale switch across 1.125 the ring may
  keep the other sheet's sprite until the theme changes (inferred from
  `ElementProgress.cpp`, not seen live). Since stage 2 the taskbar hides the
  ring (the reviewed mockup has none), so no rule draws the `ring` sprite.

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
| `--surface` | `#0a0816` |
| `--surface-raised` | `#161230` |
| `--surface-sunken` | `#05040d` |
| `--surface-hover` | `#0c1c2b` |
| `--surface-band` | `#0a0816e6` |
| `--scene` | `#04030a` |
| `--scene-band` | `#0a0816` |
| `--border` | `#23e5ff33` |
| `--text` | `#ebe7ff` |
| `--text-muted` | `#a39dca` |
| `--text-inverse` | `#ebe7ff` |
| `--accent` | `#23e5ff` |
| `--accent-hover` | `#8af2ff` |
| `--accent-text` | `#00141a` |
| `--danger` | `#ff3d71` |
| `--danger-hover` | `#ff7096` |
| `--warning` | `#ffd23b` |
| `--success` | `#3bffb0` |
| `--focus-ring` | `#e9ff3b` |
| `--selection` | `#0d2534` |
| `--overlay-scrim` | `#020108cc` |
| `--tooltip-bg` | `#00000082` |
| `--ember` | `#ffb24ff2` |
| `--ember-hot` | `#fff3cff7` |
| `--ember-glow` | `#ff9e3a47` |
| `--sheen` | `#ffffff73` |
| `--sheen-clear` | `#ffffff00` |
| `--sweep` | `#fff6dc8c` |
| `--sweep-clear` | `#fff4d600` |
| `--gauge-track` | `#ffffff0d` |
| `--gauge-red` | `#ff2e6a` |
| `--gauge-pink` | `#e9ff3b` |
| `--gauge-purple` | `#e9ff3b` |
| `--gauge-blue` | `#2e9bff` |
| `--cooldown-shade` | `#020108a6` |
| `--slot-disabled` | `#ff3d7159` |
| `--slot-locked` | `#0000008c` |
| `--slot-picked` | `#23e5ff59` |
| `--notice-bar` | `#00000080` |
| `--notice-text-big` | `#8af2ff` |
| `--edge-gm` | `#ffb347` |
| `--party-link` | `#ebe7ff` |
| `--party-unlink` | `#6b6493` |
| `--hp-recovery` | `#ff2e6a4d` |
| `--sp-recovery` | `#2e9bff4d` |
| `--chat-talking` | `#ebe7ff` |
| `--chat-info` | `#ff9fc4` |
| `--chat-notice` | `#ffd23b` |
| `--chat-party` | `#23e5ff` |
| `--chat-guild` | `#e9ff3b` |
| `--chat-command` | `#9fe6c3` |
| `--chat-shout` | `#3bffb0` |
| `--chat-whisper` | `#6dffb0` |
| `--chat-big-notice` | `#ffd23b` |
| `--chat-view-shade-top` | `#05040d00` |
| `--chat-view-shade-bottom` | `#05040dcc` |
| `--chat-edit-shade` | `#0a0816d9` |
| `--chat-mark` | `#ffd23b` |
| `--text-outline` | `#000000` |
| `--quest-text` | `#ebe7ff` |
| `--quest-body` | `#c2bde0` |
| `--quest-title` | `#ffd23b` |
| `--highlight` | `#ffd23b` |
| `--quest-reward` | `#ff9fc4` |
| `--quest-item` | `#ff6b8a` |
| `--quest-scrim` | `#00000000` |
| `--letterbox` | `#000000` |
| `--fade-black` | `#000000` |
| `--fade-white` | `#ffffff` |
| `--console-bg` | `#0a0816e6` |
| `--console-field` | `#05040d` |
| `--console-text` | `#ebe7ff` |
| `--console-grip` | `#23e5ff4d` |
| `--web-page` | `#05040d` |
| `--slot-target` | `#23e5ff4d` |
| `--slot-blocked` | `#ff3d7159` |
| `--slot-usable` | `#ffd23b59` |
| `--slot-unusable` | `#ff3d7159` |
| `--slot-unavailable` | `#000000a6` |
| `--accent-glow` | `#23e5ff66` |
| `--tip-bg` | `#00000082` |
| `--tip-title` | `#e9ff3b` |
| `--tip-special` | `#23e5ff` |
| `--tip-normal` | `#c2bde0` |
| `--tip-price` | `#ffd23b` |
| `--tip-price-middle` | `#d8d4ee` |
| `--tip-price-low` | `#a39dca` |
| `--tip-negative` | `#ff3d71` |
| `--tip-positive` | `#3bffb0` |
| `--tip-positive-special` | `#23e5ff` |
| `--tip-positive-rare` | `#c6fbff` |
| `--tip-condition` | `#e9ff3b` |
| `--tip-level-up` | `#3bffb0` |
| `--tip-skill-point` | `#ff8ae6` |
| `--tip-divider` | `#23e5ff33` |
| `--tip-divider-shadow` | `#000000` |
| `--tip-socket-silver` | `#c2c8d6` |
| `--tip-socket-gold` | `#e9ff3b` |

| Skin token | Value |
|---|---|
| `--radius-sm` | `1dp` |
| `--radius-md` | `2dp` |
| `--radius-lg` | `2dp` |
| `--cyberpunk-edge` | `#23e5ffb3` |
| `--cyberpunk-edge-dim` | `#23e5ff73` |
| `--cyberpunk-edge-alt` | `#ff2bd1` |
| `--cyberpunk-glow` | `#23e5ff59` |
| `--cyberpunk-glow-alt` | `#ff2bd180` |
| `--cyberpunk-holo-a` | `#23e5ff21` |
| `--cyberpunk-holo-b` | `#ff2bd126` |
| `--cyberpunk-scan` | `#ffffff08` |
| `--cyberpunk-hp` | `#ff2e6a` |
| `--cyberpunk-sp` | `#2e9bff` |
| `--cyberpunk-title` | `#f2fdff` |
| `--cyberpunk-name` | `#e9ff3b` |
| `--cyberpunk-link` | `#e9ff3b` |
| `--cyberpunk-acid` | `#e9ff3b` |
| `--cyberpunk-acid-soft` | `#e9ff3b1a` |
| `--cyberpunk-acid-line` | `#e9ff3b73` |
| `--cyberpunk-cell` | `#23e5ff0a` |

<!-- skin-tokens:end -->
