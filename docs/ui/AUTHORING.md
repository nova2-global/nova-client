# NovaUI authoring guide

NovaUI is the RmlUi 6.3 layer that new client windows are written in: RML markup, RCSS style sheets, data bindings, and a Python controller that runs only on events. The legacy `wndMgr` UI keeps running next to it, and windows move over one at a time.

This guide is for people and AI agents writing windows. It is a reference: every rule below is either enforced by `nuitool lint` or explained by an RmlUi 6.3 behavior that was checked in the vendored source (`nova-client-src/vendor/RmlUi-6.3`). Where the RmlUi documentation and this guide disagree, this guide describes what the vendored version does.

Status: the runtime, the Direct3D 9 renderer, the CPU renderer behind `nuitool snap`, the client host, the `_nui` Python module and this content are integrated and covered by unit and integration tests. They have not been checked in the running client yet. [Status and known gaps](#status-and-known-gaps) lists what is missing.

## Contents

- [New window checklist](#new-window-checklist)
- [File layout and store paths](#file-layout-and-store-paths)
- [A complete window](#a-complete-window)
- [Components](#components)
- [Gauges](#gauges)
- [Frame animations](#frame-animations)
- [Slot grids](#slot-grids)
- [Clock elements](#clock-elements)
- [Digit art](#digit-art)
- [Additive images](#additive-images)
- [Nearest images](#nearest-images)
- [Text with tags and links](#text-with-tags-and-links)
- [Chat lines](#chat-lines)
- [Views](#views)
- [World anchors](#world-anchors)
- [Resize handles](#resize-handles)
- [Tokens](#tokens)
- [Data binding cheatsheet](#data-binding-cheatsheet)
- [Text from game data and players](#text-from-game-data-and-players)
- [Python controller API](#python-controller-api)
- [Feeds](#feeds)
- [Placement](#placement)
- [Text fields](#text-fields)
- [Keyboard and modals](#keyboard-and-modals)
- [UI sounds](#ui-sounds)
- [The dialog kit](#the-dialog-kit)
- [The drag bridge](#the-drag-bridge)
- [HUD windows](#hud-windows)
- [System windows](#system-windows)
- [Window flags and the factory](#window-flags-and-the-factory)
- [Rules](#rules)
- [What the renderer draws](#what-the-renderer-draws)
- [Motion and reduced motion](#motion-and-reduced-motion)
- [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)
- [Localization](#localization)
- [Scale and themes](#scale-and-themes)
- [Themes](#themes)
- [Skins](#skins)
- [Classic skin](#classic-skin)
- [Adding a theme](#adding-a-theme)
- [Tools](#tools)
- [Golden case files](#golden-case-files)
- [Hot reload and debugging](#hot-reload-and-debugging)
- [Status and known gaps](#status-and-known-gaps)

## New window checklist

1. Pick a name of lowercase letters, digits and hyphens that starts with a letter, for example `settings` or `item-shop`. Create `assets/nui/nui/windows/settings/`.
2. Write `settings.rml` from the skeleton in [A complete window](#a-complete-window): link `../../nui.rtpl`, put `template="nui"` and `class="nui-window nui-anim"` on `<body>`. A dialog that must take the keyboard is a modal instead: `<body class="nui-scrim">` with a `div.nui-window` inside, and `MODAL = True` in step 5 (see [Keyboard and modals](#keyboard-and-modals)).
3. Write `settings.rcss` for the window's size and position and anything the components do not cover. Use tokens for every color and `dp` for every length.
4. Write `settings.fixture.json` with every key of every data model the document binds. `nuitool lint` checks its JSON (NUI001) and loads the document with it; pass it to `nuitool snap` with `--fixture`.
5. Write the controller `assets/root/nui_settings.py`: subclass `nui.Window`, set `DOCUMENT` and `MODEL` (and `MODAL = True` for a dialog), return every model key from `initial_model()`, and add one `@nui.on("name")` method for every `data-event-*="name(...)"` in the document. The controller's name writes each hyphen of the window name as an underscore: window `item-shop` has `assets/root/nui_item_shop.py`, imported as `nui_item_shop`. Model keys and event names follow RmlUi's name rule (see [Data binding cheatsheet](#data-binding-cheatsheet)).
6. Use `@ui.KEY` (from `locale_interface.txt`) or `@game.KEY` (from `locale_game.txt`) for every visible string. The key must exist in every locale, and a `@game.KEY` must be a plain string, not one of the typed entries localeInfo makes functions of (see [Localization](#localization), which also says how to add a key).
7. If you touched `tokens.json`, run `python tools/nui_tokens.py` (it rewrites `tokens.rcss` and the token table below, and prints the contrast ratios). `python tools/nui_tokens.py --check` verifies without writing and exits 1 while an output is stale. Then run `nuitool lint` (with the nine roots of [Tools](#tools)) until it exits 0. Findings are the only thing on standard output; the `N findings in M files` summary and any note about a skipped check always go to standard error. Exit 2 (a missing root, a mistyped path) also leaves standard output empty, so go by the exit code.
8. Run `nuitool snap` with `--locale assets/locale/locale/en` in every theme (`--theme modern-dark`, `modern-light` and `classic`, the ids in `nui/theme/themes.json`) at scale 1.0, 1.5 and 2.0, and once with `--reduced-motion`. The components follow every theme by themselves; when the window's own sheet draws something the classic look needs to change, write those rules in the window's classic overlay, `nui/skins/classic/windows/<name>.rcss`, never in the window's sheet (see [Skins](#skins)). `--size` is in pixels: give it the scale times the dp area the window needs, for a full-screen window 1920x1080 at 1.0, 2880x1620 at 1.5 and 3840x2160 at 2.0 (the client's own sizes at those scales). Snap does not scroll, so a scroll container shows only its first screen. Look at the images. Declare the window's goldens in `<name>.snapshots.json` (see [Golden case files](#golden-case-files)) and write them with `python3 tools/check_nui_snapshots.py --write --optimize --only <name>`.
9. Check the window with the German locale (`--locale assets/locale/locale/de`; strings run about a third longer than English) and at 75% scale.
10. Open the window from game code only through its controller. Never call RmlUi or `_nui` directly.

## File layout and store paths

NovaPack publishes a file at `assets/<group>/<path>` under the store path `<path>`, lowercased (`src/AssetLib/PathNorm.h`). The `nui` group in `assets/groups.txt` therefore holds a second `nui/` folder, the same pattern as `assets/icon/icon/` and `assets/locale/locale/`:

| In the repository | Store path | What |
|---|---|---|
| `assets/nui/nui/nui.rtpl` | `nui/nui.rtpl` | template that links every shared style sheet |
| `assets/nui/nui/base.rcss` | `nui/base.rcss` | element defaults, typography, focus, scrollbars, reduced motion |
| `assets/nui/nui/theme/tokens.json` | `nui/theme/tokens.json` | design tokens, the source of truth |
| `assets/nui/nui/theme/tokens.rcss` | `nui/theme/tokens.rcss` | generated from `tokens.json`, never edit by hand |
| `assets/nui/nui/theme/themes.json` | `nui/theme/themes.json` | the player themes and the `<body>` classes each one sets (see [Themes](#themes)) |
| `assets/nui/nui/components/*.rcss` | `nui/components/*.rcss` | one style sheet per component |
| `assets/nui/nui/skins/<skin>/` | `nui/skins/<skin>/...` | everything a skin adds: its component sheet, its art and its window overlays, every rule scoped under `.skin-<skin>` (see [Skins](#skins)) |
| `assets/nui/nui/skins/<skin>/windows/<name>.rcss` | same folder | the skin's overlay of window `<name>`: its rules for that window, applied after the window's own sheets |
| `assets/nui/nui/fonts/NotoSans-{Regular,Bold,Italic}.ttf` | `nui/fonts/...` | Noto Sans 2.015 (OFL, see `OFL.txt` next to them) |
| `assets/nui/nui/windows/<name>/<name>.rml` | `nui/windows/<name>/<name>.rml` | the window document |
| `assets/nui/nui/windows/<name>/<name>.rcss` | same folder | the window's own rules |
| `assets/nui/nui/windows/<name>/<name>.fixture.json` | same folder | sample model data for lint and snapshots |
| `assets/nui/nui/windows/<name>/<name>.snapshots.json` | same folder | the window's golden cases (see [Golden case files](#golden-case-files)); not used by the client |
| `assets/root/nui_<module>.py` | `nui_<module>.py` | the controller, imported as `nui_<module>`: the window name with each hyphen as an underscore (`item-shop`: `nui_item_shop`) |
| `assets/nui/nui/windows/gallery/` | | every component in `nui/components/` in every state it styles |
| `assets/nui/nui/windows/render-test/` | | every renderer feature on one page |
| `assets/nui/nui/windows/theme-picker/` | | the intro theme picker, one button per theme (controller `nui_theme_picker.py`) |
| `assets/nui/nui/windows/skin-proof/` | | a dev page with a skin's frame pieces at legacy sizes, for the sharpness and fidelity checks; nothing in the game opens it |
| `assets/nui/nui/windows/dialog-*/`, `pick-money/` | | the dialog kit's documents (see [The dialog kit](#the-dialog-kit)) |
| `assets/nui/nui/windows/server-board/`, `virtual-keyboard/`, `locale-strip/` | | the login screen's server and channel board, virtual keyboard and locale flag strip |
| `assets/root/nui_windows.py` | `nui_windows.py` | the window flags and the factory that picks the NovaUI or the legacy class (see [Window flags and the factory](#window-flags-and-the-factory)) |
| `assets/root/nui_dialog_kit.py` | `nui_dialog_kit.py` | what the dialog kit's windows share |
| `assets/root/nui_slots.py` | `nui_slots.py` | the slot model, the drag bridge and the tooltip bridge of every slot window (see [Slot grids](#slot-grids)) |
| `assets/root/nui_hud.py` | `nui_hud.py` | what the HUD facades share (see [HUD windows](#hud-windows)) |
| `assets/nui/nui/windows/taskbar/`, `expanded-taskbar/`, `energy-bar/`, `gift-box/`, `game-buttons/` and the other Wave 2a windows | | the HUD (see [HUD windows](#hud-windows)) |

The client loads the fonts (`kDefaultFonts`, which `nuitool lint` and `snap` also use) and the render test (`kRenderTestDocument`, Ctrl+Shift+U in a dev build) by the constants in `nova-client-src/src/NovaUI/Core/NuiPaths.h`. The gallery has no client constant: its controller, `assets/root/nui_gallery.py`, names the document in `DOCUMENT` and opens it with `import nui_gallery; nui_gallery.open_gallery()`.

Paths inside documents and style sheets:

- A relative path resolves against the file that contains it: `href` and `src` in an `.rml` against the document, `image(...)` in an `.rcss` against that style sheet. `..` segments are normalized.
- A path that starts with `/` is a store path from the store root and resolves the same from any file: `/nui/theme/tokens.rcss`, `/icon/item/27001.tga`. `_nui.LoadDocument` takes one too.
- Templates are the exception to the first rule. `href` in a template's `<head>` resolves against the template file, but the template's body is copied into each document that uses it, so a relative `<img src>` or inline-style image path there resolves against that document (RmlUi joins them with the owner document's path). Put images in a template's body through an image decorator in a linked `.rcss`, a sprite, a `/` store path or a `d:/` path; lint reports a relative one as NUI007.
- Name files in lowercase with hyphens. A window's folder and document use its window name (lowercase letters, digits and hyphens, starting with a letter); only its controller module writes the hyphens as underscores, because an import statement cannot name a hyphen. Underscores are not used in window names, so `item-shop` and `item_shop` can never share a controller. The store and `nuitool` look paths up without regard to case, so a reference in the wrong case still resolves; write the exact case anyway, because git and Linux file systems are case-sensitive. The three font files are the only mixed-case names (fixed by `NuiPaths.h`).
- Legacy assets outside `nui/` are reached from the store root: `/icon/item/27001.tga`, or by climbing to it (three levels from `nui/windows/<name>/`: `../../../icon/item/27001.tga`). Model values from Python are store paths (`item.GetIconImageFileName()` style), so root them in the binding: `data-attr-src="'/' + slot.icon"`; Python may also pass `/icon/...` values itself.
- Legacy `d:/ymir work/...` paths work as written; the runtime treats the drive prefix as absolute.
- In a release the client reads store paths only: a path that climbs above the store root (`nui/../../x.rml`) or names another drive (`c:/x.png`, also what `'/' + slot.icon` gives for a model value of `c:/x.png`) reads as missing, for documents and images alike. `d:/ymir work/...` is the one drive path.
- A path from a binding or from Python stays under 260 characters, the client's limit for image names; a longer one draws nothing. Static references are checked by lint (NUI007).

## A complete window

A small settings window with one toggle and one slider. The same pattern scales to any window.

`assets/nui/nui/windows/settings/settings.rml`:

```xml
<rml>
<head>
	<title>@ui.SYSTEMOPTION_TITLE</title>
	<link type="text/template" href="../../nui.rtpl"/>
	<link type="text/rcss" href="settings.rcss"/>
</head>
<body template="nui" class="nui-window nui-anim" data-model="settings">
	<div class="nui-window__titlebar">
		<handle class="nui-window__handle" move_target="#document">
			<span class="nui-window__title">@ui.SYSTEMOPTION_TITLE</span>
		</handle>
		<button class="nui-button nui-button--ghost nui-button--icon nui-window__close nui-anim"
			data-event-click="close()">&#215;</button>
	</div>
	<div class="nui-window__body nui-stack">
		<label class="nui-toggle">
			<input type="checkbox" class="nui-toggle__input"
				data-attrif-checked="music" data-event-change="set_music(ev.checked)"/>
			<span class="nui-toggle__track nui-anim"><span class="nui-toggle__knob nui-anim"></span></span>
			<span class="nui-toggle__label">@ui.OPTION_MUSIC</span>
		</label>
		<input type="range" class="nui-slider" min="0" max="100" step="5"
			data-attr-value="volume" data-event-change="set_volume(ev.value)"/>
	</div>
	<div class="nui-window__footer">
		<button class="nui-button nui-button--primary nui-anim" data-event-click="close()">@ui.OK</button>
	</div>
</body>
</rml>
```

`settings.rcss` holds only what belongs to this window:

```css
body.nui-window
{
	left: 120dp;
	top: 120dp;
	width: 360dp;
}
```

`settings.fixture.json` has one object per data model, holding every key:

```json
{
	"settings": {
		"music": true,
		"volume": 60
	}
}
```

`assets/root/nui_settings.py`:

```python
import nui

class SettingsWindow(nui.Window):
	DOCUMENT = "nui/windows/settings/settings.rml"
	MODEL = "settings"

	def initial_model(self):
		return {"music": True, "volume": 60}

	@nui.on("set_music")
	def on_set_music(self, checked):
		self.set(music=bool(checked))

	@nui.on("set_volume")
	def on_set_volume(self, value):
		self.set(volume=int(round(value)))

	@nui.on("close")
	def on_close(self):
		self.hide()
```

What the example relies on:

- `template="nui"` pulls in the tokens, `base.rcss` and every component sheet, so the document links only its own sheet.
- `data-model` goes on `<body>`. The model must exist before the document loads; `nui.Window.__init__` creates it first.
- The toggle and the slider use one-way bindings (`data-attrif-checked`, `data-attr-value`) and report changes through `data-event-change`. The controller calls `set()`, which updates the view. `ev.checked` and `ev.value` are parameters of RmlUi's change event.
- Handler arguments are Python scalars. A range input's `ev.value` arrives as an int while the value is a whole number and as a float otherwise, so the handler rounds before storing an int.
- `on_set_music` and `on_set_volume` also run when nothing was clicked: the bindings send `change` whenever the view moves the control, after `set()`, on every re-load, and on the first load inside `__init__`. Both handlers only store the value they are given, so running them again changes nothing.
- The window is not modal, so the mouse works the toggle and the slider. The keyboard reaches them only where NovaUI has the keyboard (see [Keyboard and modals](#keyboard-and-modals)).

## Components

All class names start with `nui-`. Modifiers use `--`, parts use `__`, states use `is-*`. The gallery (`nui/windows/gallery/gallery.rml`) shows every component in every state it styles; the body-level layers (`nui-overlay`, `nui-scrim`) and the layout helpers other than `nui-row` are not on it. Copy markup from there.

| Component | Markup | Variants and states |
|---|---|---|
| Window frame | `<body class="nui-window nui-anim">` with `nui-window__titlebar`, `nui-window__handle` (a `<handle move_target="#document">`), `nui-window__title`, `nui-window__close`, `nui-window__body`, `nui-window__footer` | Rises 4dp each time the window is shown. For a modal dialog, use `<body class="nui-scrim">` with a `div.nui-window` inside, set `MODAL = True` in the controller, and point the handle at the div's id: `move_target="my-dialog"` (a plain id, no `#`). The modal takes the keyboard and every click beside the dialog; the scrim draws the backdrop. A scrim without `MODAL` blocks clicks but gets no keys; `MODAL` on a plain `body.nui-window` blocks the world with nothing on screen to show it. The scrim centers the div, and the component makes it `position: relative` so the drag can offset it; the dialog's sheet sets only its width and height, never `position`, `left` or `top`. |
| Button | `<button class="nui-button nui-button--primary nui-anim">` | `--primary`, `--secondary` (the default look), `--ghost`, `--danger`; sizes `--small`, `--medium` (the dialogs' size: a minimum width, the legacy middle art in classic), `--icon`. A new window never puts a text label on `--small`: the classic small art fits only short labels (`tools/nui_button_fit.py` reports it); a window that needs legacy's small art for a choice sets it in its classic overlay. `:hover`, `:active`, `:focus-visible`; `is-selected` for a choice that is on, a radio choice or a toggle legacy draws as a button held down (`data-class-is-selected`): the selection color and an accent border in modern, the down art of the small, middle and large buttons in classic, under the pointer too. Enter and Space press a focused button where NovaUI has the keyboard ([Keyboard and modals](#keyboard-and-modals)). The `disabled` attribute takes the button out of pointer hit testing, the tab order and Enter/Space (see [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)). |
| Panel | `<div class="nui-panel">` with an optional `nui-panel__title` | `--sunken`, `--flat`. `nui-divider` is a 1dp rule. |
| Tabs | native `<tabset class="nui-tabs nui-tabs--3">` with `<tab>` and `<panel>` pairs and a last `<tab class="nui-tabs__indicator nui-anim">` | `nui-tabs--2` to `--6` must match the number of real tabs. Tabs switch without Python; the selected tab and panel get `:selected`. Tabs are in the tab order: where NovaUI has the keyboard, Tab moves between them, Enter or Space selects one, and `:focus-visible` rings the focused tab. |
| List | `<div class="nui-list">` around a `<div class="nui-list__viewport">` that holds the rows `<div class="nui-list__item nui-anim">`, parts `nui-list__label`, `nui-list__meta` | `is-selected`, `:hover`, `:focus-visible` (a ring on every edge; a selected row keeps its accent stripe). Enter or Space selects the focused row where NovaUI has the keyboard. The `disabled` attribute takes a row out of hit testing, the tab order and Enter/Space. Give the viewport a height in the window sheet to scroll (`.my-list .nui-list__viewport { height: 200dp; }`): the rounded frame does not clip, the square viewport does, so the list clips with the scissor alone (see [What the renderer draws](#what-the-renderer-draws)). |
| Slot grid | `<div class="nui-slot-grid">` with `<div class="nui-slot nui-anim">` cells and their parts `__icon`, `__cover`, `__tint`, `__cooldown`, `__active`, `__finish`, `__count`, `__digits`, `__key` | 40dp cells for 32dp icons (the legacy 32dp pitch in classic). `--cols-1` to `--cols-10`, `--pick`, `--layered`; `is-empty`, `is-disabled`, `is-locked`, `is-picked`, `is-selected`, `is-target`, `:hover`, `is-hover`. See [Slot grids](#slot-grids). |
| Slider | `<input type="range" class="nui-slider" min max step value>` | `:hover` and `:active` on the thumb, `:focus-visible`; `disabled` attribute. The arrow keys move a focused slider where NovaUI has the keyboard. RmlUi builds the track, fill and thumb; the component centers them in the 20dp input, so give `.nui-slider` no padding or border. |
| Toggle | `<label class="nui-toggle">` around `<input type="checkbox" class="nui-toggle__input">`, `nui-toggle__track`, `nui-toggle__knob`, `nui-toggle__label` | `checked` and `disabled` attributes. The label forwards clicks to the hidden checkbox, in a document that takes focus: a document whose body has `focus: none` gets no click at all, so such a window flips the toggle on a left `mousedown` on the label ([RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter); the system options' reduced motion). The checkbox stays in the tab order: where NovaUI has the keyboard, Tab reaches the toggle, Space flips it, and `:focus-visible` rings the track. |
| Text input | `<input type="text" class="nui-input">` (also `type="password"`), inside `div.nui-field` with `label.nui-field__label` and `span.nui-field__error` | `--invalid`, `disabled` attribute, `:focus`, `:placeholder-shown`. The corners are square on purpose: RmlUi makes every text input clip, and square clipping needs no stencil mask. `nui-escape-keeps-focus` on `<body>`: Escape in a field of this document does not leave the field (the login board). |
| Tooltip | `<span class="nui-has-tooltip">` host with `<span class="nui-tooltip nui-anim">` inside | One line by default; `--wrap` wraps at 240dp. `is-open` shows it without hover. The host is laid out as `inline-block` (one box that does not wrap with the text around it), because RmlUi never places an absolute child against an inline box. Use a span or a component element as the host; a bare `div` or `p` becomes inline-block too. Item tooltips stay on the legacy `uitooltip` windows. |
| Badge | `<span class="nui-badge">` | `--accent`, `--danger`, `--warning`, `--success`. |
| Gauge | `<progress class="nui-gauge nui-gauge--red" direction="right" data-attr-value="hp"/>` | `--red` (default), `--pink`, `--purple`, `--blue`. See [Gauges](#gauges). |
| Frame animation | `<nui-frames frames="a.sub, b.sub" delay="0.1"/>` | `start`, `after="none"`. See [Frame animations](#frame-animations). |
| Countdown | `<nui-countdown format="dhms" data-attr-end="icon.end"/>` | The time left as text, or a timer (`format="none"`). See [Clock elements](#clock-elements). |
| Cooldown sweep | `<nui-cooldown data-attr-start="slot.cd_start" data-attr-end="slot.cd_end"/>` | Over its positioned parent. See [Clock elements](#clock-elements). |
| Digit art | `<nui-number value="m1"/>` | The legacy number glyphs. See [Digit art](#digit-art). |
| Tagged text | `<nui-text data-attr-value="sign.text"/>` | `links="off"`; link runs are `span.nui-link` (underlined on hover in the modern skins). See [Text with tags and links](#text-with-tags-and-links). |
| Chat lines | `<nui-chat-lines view="window" step="15" data-attr-mode="..."/>` | `view`, `edit`, `log` modes; lines `div.nui-chat__line--t<type>`, `is-fading`, `is-edge-0`, `is-edge-1`. See [Chat lines](#chat-lines). |
| View | `<nui-view name="minimap" class="nui-interactive"/>` | `hover="none"`; its label `div.nui-view__label` and mark `img.nui-view__mark`. See [Views](#views). |
| World anchor | `<nui-anchor mode="project" height="220" data-attr-vid="sign.vid"/>` | `mode="tail"`, `align-x`, `align-y`, `offset-x`, `offset-y`, `chat-offset-y`, `snap`. See [World anchors](#world-anchors). |
| Resize handle | `<nui-resize class="nui-resize--top" edge="top" target="id"/>` | `edge="bottom-right"` with `nui-resize--bottom-right`; `resized` at the end of a drag. See [Resize handles](#resize-handles). |
| Dialog | `div.nui-window.nui-dialog` inside `body.nui-scrim`, with `nui-dialog__text`, `nui-dialog__field` and a `nui-window__footer nui-dialog__footer` | The dialog kit's look (`components/dialog.rcss`): 280dp to 420dp wide, centered text that wraps, a centered 160dp field, centered buttons. See [The dialog kit](#the-dialog-kit). |
| Layout helpers | `nui-row` (flex row, `--wrap`, `--end`, `--between`), `nui-stack` (flex column, `--loose`), `nui-grow`, `nui-muted`, `nui-small` | Use these instead of inline styles. |
| Full-screen layers | `<body class="nui-overlay">` for HUD layers that never take the mouse; `nui-interactive` on children that should | `nui-center-max` caps content at 1600dp; `nui-safe-16x9` limits a HUD anchor area to 16:9 of the screen height on ultrawide screens. |

The gallery shows every component but the body-level layers, the dialog look (the `dialog-*` windows have goldens of their own), `nui-frames` outside the slot effects (the loading window shows it), `nui-countdown` (the HUD windows show it) and most layout helpers.

`is-hover`, `is-active` and `is-focus` force the look of `:hover`, `:active` and `:focus-visible` where a component styles that state: buttons and sliders take all three, inputs, list rows, tabs and toggles take `is-hover` and `is-focus`, and slots take `is-hover`. Use them only where no pointer or keyboard is behind the state: gallery snapshots, or a highlight driven by data (`data-class-is-hover="slot.target"`).

## Gauges

`<progress class="nui-gauge nui-gauge--blue" direction="right" data-attr-value="sp"/>`, with a value from 0 to 1 (`max` defaults to 1). RmlUi sizes the inner `<fill>` from the value; bind it with `data-attr-value`, since an inline style is NUI009.

- **Modern:** a 6dp track in `--gauge-track` with a fill in `--gauge-red`, `--gauge-pink`, `--gauge-purple` or `--gauge-blue` (every palette defines the five).
- **Classic:** the legacy gauge (`ui.Gauge`): the slot art with its two caps, 8dp tall, and the colored bar inset 12dp from both ends. The art comes from the legacy pattern folder (`d:/ymir work/ui/pattern/gauge_*.tga`) and is 1x only: it is not in the classic sprite sheets, so it is filtered above 100%. Its rules and decorators are in `skins/classic/classic.rcss`. Lint and snapshots of a document with a gauge need the `assets/ETC` root.
- **No easing:** a gauge shows a new value at once. The legacy gauges eased toward it every frame, which is per-frame Python.

## Frame animations

`nui-frames` is an element the NovaUI runtime registers (`nova-client-src/src/NovaUI/Core/ElementFrames.h`). It plays a legacy `ani_image` sequence: it makes one `<img class="nui-frames__frame">` per frame, stacked, and shows one at a time from the clock. A frame switch changes two visibility properties and rebuilds no mesh; each frame's quad is built the first time it is drawn.

```xml
<nui-frames pattern="d:/ymir work/ui/intro/loading/%02d.sub" count="24" delay="0.05"/>
<nui-frames frames="a.sub, b.sub, c.sub" delay="0.1" loop="false" data-event-framesend="done()"/>
```

| Attribute | Meaning |
|---|---|
| `frames` | The frame sources, separated by commas; each is trimmed at its ends, so legacy paths with spaces work. A source is what `<img src>` takes. |
| `pattern`, `count`, `first` | Used without `frames`: `pattern` holds one `%d` or `%0Nd`, and `count` (1 to 256) frames are made from `first` (default 0). |
| `delay` | Seconds per frame, above 0 (default 0.1). |
| `loop` | `"false"` stops on the last frame and sends `framesend` once (not bubbling); anything else loops. |
| `rest` | The frame shown under reduced motion, and while paused before the first update (default 0). |
| `paused` | Present: hold the current frame. |
| `start` | Clock time in seconds the sequence starts (a slot's cooldown end, written from `nui.now()`): the frame counts from then, and before it no frame shows. A change (a bound `data-attr-start`) re-bases the clock, arms `framesend` again and rebuilds nothing. |
| `after` | `last` (default): a non-looping sequence keeps its last frame. `none`: it shows nothing once its last frame has shown for one `delay`, so an effect plays once and goes. |

- The first frame stays in the flow and sizes the element; the others are placed over it. `components/frames.rcss` gives the element `display: inline-flex; position: relative; vertical-align: top` and the frames `display: block`, which makes the box exactly frame 0's size, on the line's top. RmlUi 6.3 sizes an `inline-block` around a block image to 0 wide, and adds the line's descent below an inline one. A sheet that overrides `display` keeps the frames as blocks.
- Changing `frames`, `pattern`, `count` or `first` (in markup or through `data-attr-*`) rebuilds the frames; `delay`, `loop`, `rest` and `paused` do not.
- Reduced motion shows the `rest` frame and holds it.
- `nuitool snap --time S` shows frame `floor(S / delay) mod count`.
- Lint checks every source of a literal `frames` or `pattern` as it checks `<img src>` (NUI007); a bound `data-attr-frames` is not checked. A bad `delay`, a bad pattern or no frames is one warning per element (`nui-frames: <reason>`).

## Slot grids

Item, skill and emotion cells are `nui/components/slot-grid.rcss` (slot grid v2). Every slot window shares one Python helper, `assets/root/nui_slots.py`, for the model, the drags and the tooltips.

**The slot model.** One dict per cell, with the same keys whether `nui_slots` or C++ (the quickslot feed, `NuiGameFeeds::BuildQuickSlots`) makes it:

| Key | Type | Empty | Meaning |
|---|---|---|---|
| `index` | int | the cell | the cell's index in its grid, 0-based |
| `kind` | str | `""` | `"item"`, `"skill"`, `"emotion"` or `""` |
| `type` | int | 0 | the content's legacy slot type (`player.SLOT_TYPE_*`), for tooltips and drags |
| `ref` | int | 0 | what the cell holds: an inventory position, a skill slot, an emotion index |
| `icon` | str | `""` | an image source as `<img src>` takes it: `/icon/item/27001.tga`, `d:/ymir work/ui/skill/...` |
| `count` | str | `""` | the label at the bottom right: an item count above 1, a skill level label (`"20"`, `"m1"`, `"g2"`, `"p"`) |
| `w`, `h` | int | 1, 1 | the cells the icon spans (an item's `item.GetItemSize()`, 1 to 3) |
| `cd_start`, `cd_end` | float | 0.0, 0.0 | the cooldown's span in `nui.now()` seconds; 0 and 0 for none |
| `active` | bool | false | the 13-frame "active" effect (a toggle skill, an auto potion that is on) |
| `cover` | bool | false | the cover art over skills and emotions |
| `disabled` | bool | false | the legacy red tint |
| `locked` | bool | false | the legacy black tint; the window refuses a pick |

`nui_slots.SLOT_KEYS` lists the keys, and `empty_slot(index)`, `item_slot(index, inventory_pos, window=None)`, `skill_slot(index, skill_slot_number)` and `emotion_slot(index, emotion_index)` build cells as the legacy `RefreshQuickSlot` shows them (a vnum or a skill index of 0 is an empty cell; a guild skill has grade 0 and the guild's level). `icon_source(path)` puts a `/` in front of a store path and keeps a `d:/` path; `count_label(grade, level)` is `CSlotWindow::SetSlotCountNew`'s label; `cooldown_span(cool_time, elapsed=0.0)` is the `(start, end)` of a cooldown in `nui.now()` seconds. Selection and the pick highlight are window state, not cell state: a window keeps `<grid>_picked` and `<grid>_selected` keys (int, -1 for none) and compares them with `slot.index`.

**Markup.** The component's comment holds a cell with every part; copy it. In short:

```xml
<div class="nui-slot-grid nui-slot-grid--cols-4" id="quick-slots">
	<div class="nui-slot nui-anim" data-for="slot : quick_slots"
	     data-class-is-empty="slot.kind == ''" data-class-is-locked="slot.locked"
	     data-event-mousedown="slot_press('quick', slot.index, ev.button)"
	     data-event-mouseup="slot_release('quick', slot.index, ev.button)"
	     data-event-mouseover="slot_over('quick', slot.index)"
	     data-event-mouseout="slot_out('quick', slot.index)"
	     data-event-nuidrop="slot_drop('quick', slot.index)">
		<img class="nui-slot__icon" data-if="slot.icon != ''" data-attr-src="slot.icon"/>
		<div class="nui-slot__cover" data-if="slot.cover"></div>
		<div class="nui-slot__tint"></div>
		<nui-cooldown class="nui-slot__cooldown" data-if="slot.cd_end > 0" data-attr-start="slot.cd_start" data-attr-end="slot.cd_end"/>
		<nui-frames class="nui-slot__active" data-if="slot.active"
			pattern="d:/ymir work/ui/public/slotactiveeffect/%02d.sub#nui-additive" count="13" delay="0.0667"/>
		<nui-frames class="nui-slot__finish" data-if="slot.cd_end > 0"
			pattern="d:/ymir work/ui/public/slotfinishcooltimeeffect/%02d.sub#nui-additive" count="11"
			delay="0.0333" loop="false" after="none" data-attr-start="slot.cd_end"/>
		<span class="nui-slot__count" data-if="slot.count != ''">{{ slot.count }}</span>
		<nui-number class="nui-slot__digits" data-if="slot.count != ''" data-attr-value="slot.count"/>
	</div>
</div>
```

- **The event names** are the window's own, each with the grid's name first, so one window with several grids has one handler per kind.
- **Every part ignores the pointer**, so the cell is always the event target and moving over its icon sends no `mouseout`.
- **The parts draw in the legacy order** (`CSlotWindow::OnRender`): the pick and selection tint under the icon, then the icon, the disabled tint, the sweep, the cover, the count, the finish effect, the active effect and the locked tint on top. The cell is a stacking context (`z-index: 0`), so the negative z-index of the pick tint draws above its background and under the icon.
- **The pick highlight** draws only in a grid with `nui-slot-grid--pick` (legacy `SLOT_STYLE_PICK_UP`); the quickslots have none. A disabled or locked cell keeps its pointer events, as legacy cells take clicks.
- **Reduced motion** hides the finish effect and holds the active effect on its rest frame.
- **The effects are additive art** (`#nui-additive`, see [Additive images](#additive-images)): on a light surface (the modern light theme) they wash a cell out toward white.

**Pick and place, never RmlUi drag-and-drop.** `mouseModule.mouseController` stays the one drag state of the client while both UIs live, so NovaUI and legacy windows trade items through it, and the legacy dragged icon draws above both UIs. A window hands its cells' events to a `nui_slots.SlotDrag(pick, drop, use=None, on_pick=None, on_end=None, owner=None)`:

- `press(index, button)` (`mousedown`): with the left button and something attached, `drop(index)`; else `pick(index)` answers `(slot_type, slot_number, item_index, count)` or `None` (an empty or locked cell), and the cell is attached. The right button with nothing attached is `use(index)`; with something attached it does nothing, because the host already cancelled the attach (see [The drag bridge](#the-drag-bridge)).
- `release(index, button)` (`mouseup`): after a pick on another cell, of any NovaUI grid, and a drag of 10 px or more (`wndMgr.IsDragging()`), `drop(index)`. A release on the cell the item came from keeps it attached: the next press places it.
- `legacy_drop(index)` (`nuidrop`): a press in the legacy UI dragged and released over the cell drops what is attached.
- `nui_slots.attach(owner, slot_type, slot_number, item_index, count=0, on_end=None)` attaches after detaching what the controller held. For that attach only it shadows `DeattachObject` on the controller instance, to free the icon instance the legacy method leaves behind (quick slots and dragon soul items) and to call `on_end()`; a legacy attach never sees it. `nui_slots.attached()` asks the controller.
- What a drop does is the window's: the taskbar's is the legacy `AddQuickSlot`, MR-3 swap included.
- A release over the same NovaUI grid outside every cell keeps the item attached, where legacy cancels the drag.

**Tooltips.** Item and skill tooltips stay the legacy `uitooltip` windows, drawn above NovaUI in the legacy top layer. A window passes the tooltips the Interface hands it (`SetItemToolTip`, `SetSkillToolTip`) to a `nui_slots.TooltipBridge` and calls `show_inventory_item(pos)`, `show_skill(skill_slot, skill_index, grade, level)` or `show_skill_index(skill_index)` from `slot_over`, and `hide()` from `slot_out`, from its `Hide()` and when an attach starts. Nothing shows while an item is attached, and a tooltip not set yet (0) is skipped.

**Multi-cell items.** A grid that holds items larger than one cell (the inventory) draws their icons in a layer over the cells, which stay the hit targets:

```xml
<div class="nui-slot-grid nui-slot-grid--cols-5 nui-slot-grid--layered">
	<div class="nui-slot nui-anim" data-for="cell : bag_cells" data-class-is-target="cell.target">
		<div class="nui-slot__tint"></div>
	</div>
	<div class="nui-slot-grid__items">
		<div class="nui-slot-item" data-for="item : bag_items"
		     data-class-is-disabled="item.disabled" data-class-is-locked="item.locked"
		     data-class-nui-slot-item--c1="item.c == 1" data-class-nui-slot-item--r2="item.r == 2"
		     data-class-nui-slot-item--w2="item.w == 2" data-class-nui-slot-item--h3="item.h == 3">
			<img class="nui-slot__icon" data-attr-src="item.icon"/>
			<div class="nui-slot__cover" data-if="item.cover"></div>
			<div class="nui-slot__tint"></div>
			<nui-cooldown class="nui-slot__cooldown" data-if="item.cd_end > 0"
				data-attr-start="item.cd_start" data-attr-end="item.cd_end"/>
			<nui-frames class="nui-slot__active" data-if="item.active"
				pattern="d:/ymir work/ui/public/slotactiveeffect/%02d.sub#nui-additive" count="13" delay="0.0667"/>
			<nui-frames class="nui-slot__finish" data-if="item.cd_end > 0"
				pattern="d:/ymir work/ui/public/slotfinishcooltimeeffect/%02d.sub#nui-additive" count="11"
				delay="0.0333" loop="false" after="none" data-attr-start="item.cd_end"/>
			<span class="nui-slot__count" data-if="item.count != ''">{{ item.count }}</span>
			<nui-number class="nui-slot__digits" data-if="item.count != ''" data-attr-value="item.count"/>
		</div>
	</div>
</div>
```

- **What goes where.** The item layer draws above every cell, so everything legacy draws over an icon belongs to the item entry: `is-disabled` and `is-locked` on it, and its own `__tint`, `__cover`, `__cooldown`, `__active` and `__finish`. Those 32dp parts sit on the item's anchor cell, as `CSlotWindow` draws them at the slot with its cell size; the tint covers the whole item in the modern skins and only the anchor cell in classic. The cells keep what legacy draws under the icon: `is-picked`, `is-selected` and the footprint's `is-target`, each through the cell's `__tint`. A state put on a cell of a layered grid draws under the item's icon.

- `nui-slot-item--c0` to `--c9` and `--r0` to `--r9` place an item at its cell, `--w1` to `--w3` and `--h1` to `--h3` size it (44dp steps in the modern skins, 32dp in classic); bind one class per value, since an inline style is NUI009. In a layered grid the cells show no icon or count of their own.
- `nui_slots.item_layer(items, cols, rows)` makes the layer's entries (the slot keys plus `c` and `r`) from `(cell, slot)` pairs, `owner_of_cells(items, cols, rows)` maps every covered cell to its item for hit testing, and `footprint(cell, w, h, cols, rows)` gives the cells an attached item would cover from the hovered cell, as `CGridSlotWindow` works them out (an area that leaves the grid moves back into it; `[]` for an item larger than the grid). The window sets `target` on those cells on `slot_over` while something is attached and clears it on `slot_out`; give the cells a `__tint`, which shows the state (classic: the legacy white over the slot base).
- The gallery shows a 5 x 3 layered grid with a 1x2 item, a locked 1x2 item, a 2x3 item, an active 1x1 item and a two-cell footprint.

**Classic.** `skins/classic/classic.rcss` gives slots the legacy 32dp pitch: no gap, the `slot_base.sub` art, the icon at 0,0, the cover button art (`slot_cover_button_01` to `_03`), the legacy tints (the `--slot-*` tokens hold the legacy colors in the classic palette), the legacy digits right-aligned 4dp in from the item's right edge with their top 10dp above its bottom, and no hover look. Window overlays add the placement.

## Clock elements

Three elements read the NovaUI clock (`nui.now()`): `nui-countdown`, `nui-cooldown` and `nui-frames` with `start`. A time a controller writes into a model for them is `nui.now()` plus seconds, so no Python runs while they count; `nuitool snap --time S` shows them at time S, and fixture times are seconds of that clock (the default `--time 1`).

**`nui-countdown`**: the time left until `end`, as text that changes at most once a second.

| Attribute | Meaning |
|---|---|
| `end` | Clock time in seconds the countdown ends. Absent, or 0 or less: nothing shows and nothing is sent. |
| `format` | `dhms` (default, `localeInfo.RTSecondToDHMS`: "1 Days, 2 Hours, 3 Minutes, 4 Sec", zero parts left out), `dhm` (`localeInfo.SecondToDHM`), `hms` ("H:MM:SS"), `ms` ("M:SS"), `s` (whole seconds), or `none`: no text, a timer. |
| `day`, `hour`, `minute`, `second` | The unit words, plain attributes: `day="@game.DAY"`. Defaults `d`, `h`, `m`, `s`. |

- The element owns its one text child; markup gives it none. `countdownend` (not bubbling, `data-event-countdownend`) is sent once at `end`, again for a new `end`, at once for an `end` already past. Reduced motion changes nothing.
- Hidden (inside a closed tooltip, a hidden document), it keeps its text and formats nothing, so its document is not laid out again every second; it shows the current time at its first visible update, one update after it shows, which a tooltip's fade-in covers. `countdownend` comes as when shown.
- `components/clock.rcss` makes it inline.

**`nui-cooldown`**: a cooldown sweep, a `<progress>` whose value is the remaining fraction of `[start, end)`, counter-clockwise from the top as the legacy box sweeps it, in `steps` values (default 64), so one cooldown compiles at most 64 meshes whatever the frame rate. Outside its span it is hidden. `components/clock.rcss` lays it over its positioned parent and draws it as a white texel tinted with `--cooldown-shade` (the legacy black at 50%). RmlUi resolves a progress element's `fill-image` against its document, not the sheet that names it, so a sheet names one from the store root (`/nui/components/img/solid.tga`) or a `d:/` path. RmlUi projects the sweep's angle onto the square, where the legacy box moves along each edge: a few pixels apart mid-octant.

**`nui-frames` `start` and `after`**: see [Frame animations](#frame-animations). The slot grid's finish effect plays once from the cooldown's end: `loop="false" after="none" data-attr-start="slot.cd_end"`.

**`nui-blink`**: with `period` seconds (0 or none: still) the element has the class `nui-blink-off` in the second half of each period, on the clock every `nui-blink` shares, so they blink together, as the legacy flashing buttons do. The sheet says what the class hides; the edge buttons bind `data-attr-period="e.flashing ? 1 : 0"` and hide the art with `.edge__blink.nui-blink-off { visibility: hidden; }`. Use it instead of an infinite RCSS animation for anything that only toggles: RmlUi sets an animated property, and restyles its element, on every frame, which for 14 flashing quest letters cost about 11 µs of every frame's update; `nui-blink` touches its element twice a second. It does nothing while an ancestor is hidden, and stays on under reduced motion (give that state another look under `@media (theme: reduced-motion)`).

## Digit art

`<nui-number value="200"/>` draws the legacy digit art as `CNumberLine` draws quickslot counts and skill levels: one `<img class="nui-number__glyph">` per character, from `path` (default `d:/ymir work/ui/game/taskbar/`), for the digits, `:`, `?`, `/`, `%`, `+`, `m`, `g` and `p`; other characters are skipped, as legacy skips them. `components/number.rcss` lays the glyphs out in a row with no gaps. The art is 1x only (legacy `.sub` regions, the `assets/ETC` root for lint and snapshots). The slot grid shows it in classic (`__digits`) and the count badge in the modern skins (`__count`). Lint checks a literal `value`'s glyphs (NUI007).

## Additive images

A `#nui-additive` suffix on an image source draws the image additively: its color is added to what is under it and its alpha is ignored, so black texels show nothing. Legacy effects such as the slot effects were made for a screen blend, and the finish effect's frames are opaque black where they are dark; drawn normally they would be black squares.

```xml
<nui-frames pattern="d:/ymir work/ui/public/slotactiveeffect/%02d.sub#nui-additive" count="13" delay="0.0667"/>
```

- It works wherever a source does: `<img src>`, `decorator: image(...)`, a `@spritesheet`'s `src`, a progress `fill-image`, the frames of `nui-frames`. The flagged and the plain source are two textures.
- Additive and screen differ only where both colors are bright, which the dark slot art rarely is; over a light surface additive art washes out toward white.
- Lint resolves the path part; a suffix that is not a flag is NUI007 ("unknown image flag").

## Nearest images

A `#nui-nearest` suffix samples the image at the texel under each pixel's center, with no filtering, as the legacy UI draws every image (`D3DTEXF_NONE`). Drawn 1:1 it changes nothing; scaled, it shows legacy's texels where the filtered image is softer. The classic affect icons, drawn at legacy's 70%, use it at 100% and below: the window has a second, nearest copy of each icon (`affect__image--nearest`, `display: none`) that the classic overlay shows under `@media (max-resolution: 1x)`. To pick legacy's texels the scaled image must cover legacy's 22.4 px, not a whole number: RmlUi lays out a 22.4dp box at 22 px, a step of 32 / 22 that shows other texels, so the overlay draws the copy at 32dp and scales it by `transform: scale(0.7)` from its top left corner, which is not snapped (pixel k then shows texel floor((k + 0.5) / 0.7), as legacy's quad does; `nui_hud_test.ClassicAffectIcons` checks the golden against the atlas). Above 100% there is no legacy picture to match, and the filtered copy shows. The flagged and the plain source are two textures; it works wherever a source does, as `#nui-additive` does, and the two do not combine.

## Text with tags and links

Text that players or game data wrote may carry the legacy color and link tags: `|cAARRGGBB` sets a color, `|r` restores the line's own, `||` is one `|`, and `|H<link>|h<text>|h` is a link (`item:4e21:0:0:0:0`, the item tooltip's fields). `nui-text` shows such text as legacy draws it, and never as markup:

```xml
<nui-text data-attr-value="sign.text"/>            <!-- link runs clickable -->
<nui-text links="off" data-attr-value="name"/>    <!-- link runs shown as plain runs -->
```

- The runtime registers the element (`nova-client-src/src/NovaUI/Core/ElementText.h`). It builds one `span.nui-text__run` per run through RmlUi's DOM calls, its text in a text node, so the text is never parsed, translated (`@ui.KEY`) or data-bound (`{{ }}`). A run with a color tag gets an inline color; a link run is also `nui-link` with `data-link`. Bind `value` with `data-attr-value` (a literal `value` would be translated as an attribute). Markup gives the element no children; `components/text.rcss` makes it inline.
- **The run rules** follow the legacy render path (`GrpTextInstance.cpp`), which is what players see: `|c` needs 8 more characters, else its `|` is plain text, and 8 that are not all hex draw white; `|c` and `|r` end the run before them, `|H` does not; the link's text is drawn with one space after it; a color tag inside a link's text leaves the part before it plain; text after an unclosed `|H` is dropped, and an unclosed link's text is plain.
- **A press on a link**: a left press on an element with `data-link` (or inside one) sends `nuilink` to it, which bubbles; bind it anywhere above, `data-event-nuilink="link(ev.link)"`. The press itself goes on. The chat windows open the legacy item tooltip (`Interface.MakeHyperlinkTooltip`) with it, or with the left Alt key down paste the link (`ime.PasteString(chat.GetLinkFromHyperlink(link))`); the facades read the key from `app.IsPressed(app.DIK_LALT)`.
- **`assets/root/nui_text.py`** reads the tags in plain Python: `parse_runs(text)` (the runs, as `(text, color, link)`), `visible_text(text)` and `visible_length(text)` (the legacy edit line's text and length, which leave the link's metadata out) and `link_tokens(link)`. It passes the same cases as the client's `Core/TextTags.h` (`tools/fixtures/text_tags_cases.json`, byte-identical to the client's `tests/fixtures/nui/text-tags/cases.json`).
- **Which helper where:** a model string shown with `{{ }}` goes through `nui.plain_text()` ([Text from game data and players](#text-from-game-data-and-players)); text with tags goes into a `nui-text` value, or reaches the chat lines through their C++ feed ([Chat lines](#chat-lines)); RML built in C++ uses `RunsToRml` or `EscapeRmlText`.
- The gallery's typography section shows a tagged line on the chat's backdrop.

## Chat lines

The chat's lines stay in the C++ line store (`CPythonChat`, 300 lines). C++ publishes the lines a view shows, and `nui-chat-lines` makes one element per line, keyed by the line's serial, so an append builds and lays out one line and no Python runs per frame.

```xml
<nui-chat-lines id="chat-lines" view="window" step="15" data-attr-mode="open ? 'edit' : 'view'"/>
<nui-chat-lines id="chat-log-lines" view="log" mode="log" step="15"/>
```

| Attribute | Meaning |
|---|---|
| `view` | `window` reads the feed `chat.window.lines` (chat set 0), `log` reads `chat.log.lines` (chat set 1). |
| `mode` | `view` (the chat closed), `edit` (open) or `log`; bind it with `data-attr-mode`. |
| `step` | The line pitch in dp (15). |
| `max-view`, `fade-after`, `fade-time`, `fade-steps`, `view-pad`, `edge-lines` | View mode: at most 4 lines (legacy keeps five and fades the fifth newest at once), each for 5 s, then a 0.36 s fade in 3 opacity steps; the element's height is its lines times the step plus 20dp. Edit mode: the top 2 lines take the edge classes. |

- **A line map** (the feed's list, oldest first): `id` (the line's serial), `type` (`CHAT_TYPE_*`: 0 talking, 1 info, 2 notice, 3 party, 4 guild, 5 command, 6 shout, 7 whisper, 8 big notice), `t` (`nui.now()` when it was appended) and `runs` (the tag runs as maps of `text`, `color`, `link`).
- **A line** is `div.nui-chat__line.nui-anim.nui-chat__line--t<type>` with the id `<element id>-line-<line id>`, placed by its `bottom` offset (the newest at 0); its runs are those of [Text with tags and links](#text-with-tags-and-links), and its link spans have the ids `<element id>-link-<line id>-<run>`. A run without a color tag takes the line's color: the chat type's token (`--chat-talking` to `--chat-big-notice`, `components/chat.rcss`).
- **View mode** shows the newest 4 lines younger than 5 s; a line that stops showing gets `is-fading` and goes when its fade ends, at once under reduced motion. The element fades it by stepping the line's inline opacity (`fade-steps`, 3), because each opacity change rebuilds the line's meshes: do not put a transition on `is-fading`. The element sets its own height then and has `has-lines` while it shows any (the chat's view shade).
- **Edit and log modes** show as many lines as the element's height holds, `floor(height / step)` rows (1 to 64), and report the rows to C++ (`nuigame.ChatState(view)["rows"]`), which publishes that many lines ending at the chat set's end position. In edit mode, when the history is full, the top line has `is-edge-0` (clear) and the next `is-edge-1` (half), legacy's ramp. The height comes from the sheet.
- Lines are single and not wrapped, as legacy draws them.
- **`nuigame`:** `ChatAttach()` and `ChatDetach()` start and stop the feeds (the chat facades share one attach), `ChatState(view)` answers `rows`, `total`, `end`, `at_end`, `board_state`, `end_pos`, `mask` and `attached`.
- `nuitool snap --feed chat.window.lines=<json>` publishes a fixture's lines; a golden case names them in `feeds` ([Golden case files](#golden-case-files)). Fixture times are seconds of the snap clock, so a line's `t` lies within the 4 s before `--time`.
- **The closed chat's own document** (Wave 3a): RmlUi lays a whole document out again when an element is added or removed, so with an exe that has the Wave 3a engine (`nui_hud.has_engine_3a()`) the closed chat's lines show in a small document of their own, `nui/windows/chat-view/chat-view.rml` (`nui_chat_view.ChatViewBoard`), which the chat facade shows while the chat is closed and shown and places where it places the chat. The chat document binds its lines element's mode to `lines_mode`: `edit` while open and `off` while closed, so it builds no line then; with an older exe there is no view board and `lines_mode` is `view` while closed, as before. `chat-view.rcss` repeats the closed-line rules of `chat.rcss`, which keeps them for that older exe.

## Views

`nui-view` draws, as one textured quad, what a C++ view provider renders into its own render target: the legacy minimap and atlas, drawn by `CPythonMiniMap` unchanged. The element is transformed, faded, clipped and stacked like any image.

```xml
<nui-view id="minimap-view" name="minimap" class="nui-interactive"/>
```

- `name` is the provider's name (`minimap`, `atlas`). Without a size in the sheet the element takes the provider's natural size (the atlas image's); with one (the minimap's 128dp) that wins. A view that is not shown is not rendered.
- `hover="label"` (the default) shows the provider's hover text in the element's own `div.nui-view__label`, right-aligned 5dp left of the pointer, in the color the provider gives, after a guild mark (`img.nui-view__mark`) when it has one. The text is shown as written. `hover="none"` shows none. The element needs pointer events (`nui-interactive`) for the label.
- The facades set the label's format once: `nuigame.SetViewHoverFormat(name, "{name} ({x}, {y})", names)`; `nuigame.ViewState(name)` answers what the provider was asked for.
- `nuitool snap --view minimap=<png>` stands a PNG in for a provider (its pixel size is the natural size in dp); a golden case names it in `views`. Without one a view draws nothing; lint does not report that.

## World anchors

`nui-anchor` places itself each frame on a character's point on the screen, by its `left` and `top` offset, which moves it without a layout or a new mesh. The player gauge and the private shop signs use it.

```xml
<body template="nui" class="nui-overlay ...">
	<nui-anchor mode="project" height="220" data-attr-vid="s.vid">...</nui-anchor>
</body>
```

| Attribute | Meaning |
|---|---|
| `vid` | The character (bound with `data-attr-vid`); 0 hides the anchor. |
| `mode` | `project` (default): the character's position raised by `height` world units, projected, as `chr.GetProjectPosition`. `tail`: its name tail, as `textTail.GetPosition`. |
| `align-x`, `align-y` | The point of the anchor's own box that sits on the character's point, as fractions (0.5, 0.5: its center). |
| `offset-x`, `offset-y`, `chat-offset-y` | dp added; `chat-offset-y` only while the character shows a chat bubble. |
| `snap` | `floor` (default) rounds the point down, as the text tails do; `none`. |

- The anchor stays hidden while the character is not on the screen, behind the camera, or while its own box is not laid out yet. Its px are screen px, so put it in a `body.nui-overlay`.
- `nuitool snap --anchor 1=160,120` stands character 1 at (160, 120) dp; a golden case names its characters in `anchors`.

## Resize handles

`nui-resize` resizes another element of its document by a drag, in dp, so the size follows a scale change; no Python runs during the drag.

```xml
<nui-resize class="nui-resize--top" edge="top" target="chat-history" min-height="25"
	data-attr-height="history_height" data-event-resized="resized(ev.height)"/>
```

- `edge="top"` grows the target upward (place the target by its bottom edge); `edge="bottom-right"` grows its width and height with the drag. `min-width`, `max-width`, `min-height` and `max-height` are dp limits (the maxima also capped by the screen).
- `width` and `height` (bound with `data-attr-*`) apply to the target as inline dp at load and whenever they change, so the model keeps the size and a re-load restores it. The handle sends `resized` once at the drag's end, with `ev.width` and `ev.height` in dp; store them in the model.
- `components/resize.rcss` makes it draggable; give it a size (`nui-resize--top`, `nui-resize--bottom-right`) and `nui-interactive` in a document without pointer events. The host shows no resize cursor over it.

## Tokens

`assets/nui/nui/theme/tokens.json` is the source of truth. It has three kinds of sections:

- `shared`: lengths, font sizes, the font family, durations and easings that every theme starts from.
- Palettes: every other top-level key except `skins` is a palette of colors, named by the `theme-<palette>` class a theme in `nui/theme/themes.json` sets (`dark`, `light`, `classic`). Every palette defines the same colors, and a palette holds colors only.
- `skins` (optional): per skin, tokens that override a shared one (the classic skin's font family and sizes) or tokens of its own, named `<skin>-...` and holding a color or a `dp` length (`--classic-slot-dark`).

`tools/nui_tokens.py` turns it into `nui/theme/tokens.rcss`: the `shared` values go into `body { ... }`, each palette's colors into `body.theme-<palette> { ... }` in the order the themes first name them, and each skin's tokens into `body.skin-<skin> { ... }`. The palette of the first theme doubles as the default for a `<body>` without a theme class. The script also reads `themes.json` and fails when a theme does not set exactly one `skin-*` and one `theme-*` class, when a theme names a palette `tokens.json` lacks, or when a palette or skin is named by no theme. Change a token by editing the JSON and running, from the repository root:

```
python tools/nui_tokens.py           # writes tokens.rcss and the table below, prints contrast ratios
python tools/nui_tokens.py --check   # writes nothing; exit 1 when an output is stale or a ratio fails
```

The script checks WCAG 2.x contrast in every palette for every text color a component draws on each background it uses, at 4.5:1 (body text, muted text on panels, hovered and selected rows, labels on accent and status fills, tooltip text, status text), and for the focus ring and the accent fill of the slider and the checked toggle at 3:1. It fails when any pair is below its minimum; the pairs are listed in `CONTRAST_PAIRS` in `tools/nui_tokens.py`. `--border` is deliberately subtle in the modern palettes (1.4 to 1.8:1 on the surfaces) and is not checked, both as a border and as the scrollbar thumb; controls are recognizable by their fill.

What the color roles mean:

- `--surface` is the window background, `--surface-raised` panels and secondary buttons, `--surface-sunken` inputs, slots and tracks, `--surface-hover` hovered rows and buttons, `--selection` selected rows and selected text.
- `--text` is body text, `--text-muted` secondary text and placeholders. `--text-inverse` is text on `--tooltip-bg`, the inverse surface used by tooltips and slot counts (light in the dark theme, dark in the light theme; classic keeps the legacy dark tooltip with light text).
- `--accent` fills primary buttons, the checked toggle, the slider fill and the tab indicator, and colors the selected tab label. `--accent-text` is text on `--accent`, `--accent-hover`, `--danger`, `--danger-hover`, `--success` and `--warning` fills.
- `--danger`, `--warning` and `--success` work both as text on surfaces and as fills.
- `--focus-ring` is the keyboard focus border. `--overlay-scrim` is the translucent modal backdrop.

<!-- tokens:begin (generated by tools/nui_tokens.py; do not edit by hand) -->

| Token | Dark | Light | Classic |
|---|---|---|---|
| `--surface` | `#1a1d23` | `#f3f4f6` | `#1b1918` |
| `--surface-raised` | `#232830` | `#ffffff` | `#23201e` |
| `--surface-sunken` | `#121418` | `#e7e9ed` | `#000000` |
| `--surface-hover` | `#2c323c` | `#e3e6eb` | `#494746` |
| `--border` | `#3b424e` | `#c3c8d1` | `#777777` |
| `--text` | `#e7eaf0` | `#1a1d23` | `#dadada` |
| `--text-muted` | `#a4acba` | `#525a67` | `#c2c2c2` |
| `--text-inverse` | `#16191e` | `#f3f4f6` | `#dadada` |
| `--accent` | `#8ab4f8` | `#1a5fc4` | `#ffc800` |
| `--accent-hover` | `#a8c7fa` | `#154ea3` | `#ffd84d` |
| `--accent-text` | `#0c1a30` | `#ffffff` | `#000000` |
| `--danger` | `#f28b82` | `#b3261e` | `#ff4d4d` |
| `--danger-hover` | `#f6aea9` | `#8c1d18` | `#ff7a7a` |
| `--warning` | `#f6c75a` | `#8a5300` | `#ffb96d` |
| `--success` | `#7fd29a` | `#1e7a3c` | `#8ab98e` |
| `--focus-ring` | `#f2f5f9` | `#111317` | `#f2e7c1` |
| `--selection` | `#2a3a55` | `#d6e4fb` | `#131237` |
| `--overlay-scrim` | `#000000a6` | `#0000007a` | `#00000080` |
| `--tooltip-bg` | `#e7eaf0` | `#2a2f37` | `#0d0c0b` |
| `--ember` | `#ffb24ff2` | `#ffb24ff2` | `#ffb24ff2` |
| `--ember-hot` | `#fff3cff7` | `#fff3cff7` | `#fff3cff7` |
| `--ember-glow` | `#ff9e3a47` | `#ff9e3a47` | `#ff9e3a47` |
| `--sheen` | `#ffffff73` | `#ffffff73` | `#ffffff73` |
| `--sheen-clear` | `#ffffff00` | `#ffffff00` | `#ffffff00` |
| `--sweep` | `#fff6dc8c` | `#fff6dc8c` | `#fff6dc8c` |
| `--sweep-clear` | `#fff4d600` | `#fff4d600` | `#fff4d600` |
| `--gauge-track` | `#121418` | `#d5d9e0` | `#242424` |
| `--gauge-red` | `#f28b82` | `#b3261e` | `#bc5353` |
| `--gauge-pink` | `#f48fb1` | `#b0306f` | `#bc5296` |
| `--gauge-purple` | `#c58af9` | `#7438c4` | `#8052bc` |
| `--gauge-blue` | `#8ab4f8` | `#1a5fc4` | `#5283bc` |
| `--cooldown-shade` | `#00000080` | `#00000080` | `#00000080` |
| `--slot-disabled` | `#f28b8259` | `#b3261e47` | `#ff00004d` |
| `--slot-locked` | `#0000008c` | `#1a1d2366` | `#00000080` |
| `--slot-picked` | `#8ab4f859` | `#1a5fc440` | `#ffffff80` |
| `--notice-bar` | `#00000080` | `#00000080` | `#00000080` |
| `--notice-text-big` | `#f2e7c1` | `#f2e7c1` | `#f2e7c1` |
| `--edge-gm` | `#9a5a00` | `#ffb547` | `#ffa200` |
| `--party-link` | `#e7eaf0` | `#1a1d23` | `#c2c2c2` |
| `--party-unlink` | `#7f8794` | `#7a828f` | `#808080` |
| `--hp-recovery` | `#f28b8255` | `#b3261e40` | `#ff000055` |
| `--sp-recovery` | `#8ab4f855` | `#1a5fc440` | `#0000ff55` |
| `--chat-talking` | `#e7eaf0` | `#e7eaf0` | `#ffffff` |
| `--chat-info` | `#ffb4b4` | `#ffb4b4` | `#ffc8c8` |
| `--chat-notice` | `#f6d79a` | `#f6d79a` | `#ffe6ba` |
| `--chat-party` | `#5fe3d4` | `#5fe3d4` | `#00ffe4` |
| `--chat-guild` | `#e6ea7a` | `#e6ea7a` | `#fdff7c` |
| `--chat-command` | `#9fe6c3` | `#9fe6c3` | `#a7ffd4` |
| `--chat-shout` | `#9fe6c3` | `#9fe6c3` | `#a7ffd4` |
| `--chat-whisper` | `#7fd29a` | `#7fd29a` | `#4ae14a` |
| `--chat-big-notice` | `#f6d79a` | `#f6d79a` | `#ffe6ba` |
| `--chat-view-shade-top` | `#12141800` | `#12141800` | `#00000000` |
| `--chat-view-shade-bottom` | `#121418cc` | `#121418cc` | `#000000cc` |
| `--chat-edit-shade` | `#1a1d23d9` | `#1a1d23d9` | `#00000080` |
| `--chat-mark` | `#f6c75a` | `#8a5300` | `#ffff00` |
| `--text-outline` | `#000000` | `#000000` | `#000000` |

| Token | Shared value |
|---|---|
| `--font-family` | `Noto Sans` |
| `--space-1` | `4dp` |
| `--space-2` | `8dp` |
| `--space-3` | `12dp` |
| `--space-4` | `16dp` |
| `--space-5` | `24dp` |
| `--space-6` | `32dp` |
| `--radius-sm` | `2dp` |
| `--radius-md` | `4dp` |
| `--radius-lg` | `8dp` |
| `--font-xs` | `11dp` |
| `--font-sm` | `12dp` |
| `--font-md` | `14dp` |
| `--font-lg` | `16dp` |
| `--font-xl` | `20dp` |
| `--dur-fast` | `0.1s` |
| `--dur-med` | `0.2s` |
| `--dur-slow` | `0.3s` |
| `--ease-out` | `cubic-out` |
| `--ease-in-out` | `cubic-in-out` |
| `--legacy-strip-bottom` | `60px` |
| `--font-notice-big` | `18dp` |

| Token | Skin | Value |
|---|---|---|
| `--font-family` | classic | `Nova Classic` |
| `--font-xs` | classic | `11dp` |
| `--font-sm` | classic | `12dp` |
| `--font-md` | classic | `12dp` |
| `--font-lg` | classic | `14dp` |
| `--font-xl` | classic | `14dp` |
| `--classic-slot-fill` | classic | `#000000` |
| `--classic-slot-dark` | classic | `#333333` |
| `--classic-slot-light` | classic | `#b3b3b3` |
| `--classic-edit-text` | classic | `#ffffff` |
| `--classic-button-text` | classic | `#c7c7c7` |
| `--classic-tooltip-text` | classic | `#c2c2c2` |
| `--classic-hover-white` | classic | `#ffffff33` |
| `--classic-press-white` | classic | `#ffffff80` |
| `--classic-select` | classic | `#0000804d` |
| `--classic-separator` | classic | `#777777` |
| `--classic-separator-shadow` | classic | `#111111` |
| `--classic-text-outline` | classic | `#000000` |
| `--classic-disabled-tint` | classic | `#8c8c8cff` |
| `--classic-disabled-text` | classic | `#6e6e6e` |
| `--classic-key-text` | classic | `#000000` |
| `--classic-label-white` | classic | `#ffffff` |
| `--classic-chat-press` | classic | `#ffffff4d` |
| `--classic-chat-log-fill` | classic | `#00000077` |
| `--classic-chat-grip` | classic | `#989898` |
| `--classic-warning-text` | classic | `#ff4c4c` |
| `--classic-mall-text` | classic | `#f8bf24` |
| `--classic-help-curtain` | classic | `#00000077` |
| `--classic-list-ex-select` | classic | `#0000b3b3` |

<!-- tokens:end -->

Durations and easings are listed for reference: RCSS cannot read them through `var()` in transitions, so motion values are written out (see [Motion and reduced motion](#motion-and-reduced-motion)).

## Data binding cheatsheet

A document binds one data model by name; the controller owns it. Expressions use model keys, literals and a few operators.

Names: a top-level model key and a data-event name are letters, digits and `_`, start with a letter, and are none of `it`, `it_index`, `ev`, `true`, `false`, `size` and `literal`, in any case (RmlUi's rule; `nova-client-src/src/NovaUI/Core/DataNames.h`). Members of nested lists and maps may have any name. RmlUi refuses a whole model for one other key: the window stays unavailable, every method does nothing, and `syserr.txt` names the key; lint reports it on the fixture (NUI001). `@nui.on()` raises `ValueError` for another event name.

| Attribute | Example | Effect |
|---|---|---|
| `data-model` | `<body data-model="inventory">` | Binds the element and its descendants to the model. The model must exist before the document loads, or RmlUi logs an error and nothing binds. |
| `{{ expr }}` | `{{ gold }} / {{ slot.count }}` | Text only. The result is translated like other text, so `@ui.KEY` inside a model string also resolves. So never bind text another player wrote (chat, whispers, names, shop signs, guild notices, mail) through `{{ }}` as it is: `x@game.SOME_KEY` would show that locale string. In an attribute the braces stay literal (`src="{{ icon }}"` loads a file of that name); bind attributes with `data-attr-NAME`. |
| `data-for` | `data-for="slot : slots"`, `data-for="slot, i : slots"` | Repeats the element per list entry. Without names the item is `it` and the index `it_index`. Over a list that can shrink, the repeated element's own views (`data-if`, `data-class-*`, `data-attr-*` and the like on the same tag) may read only the index and top-level keys: RmlUi 6.3 updates them in the same pass as the `data-for` that removes the element, in no fixed order, so they can read the entry that is gone (`list index N is out of range` and `Could not get value from data variable` in `syserr.txt`). Bind the item on a child, as the target board, the affect icons and the edge buttons do with a bare slot element; `data-event-*` is safe. `nui_hud_test.RepeatedElements` checks the HUD windows. |
| `data-if` | `data-if="slot.count > 1"` | Removes the element from layout when false (`display: none`). |
| `data-visible` | `data-visible="loading"` | Hides with `visibility`, keeping the space. |
| `data-class-NAME` | `data-class-is-selected="row.id == selected"` | Adds class NAME while true. |
| `data-attr-NAME` | `data-attr-src="'/' + slot.icon"` | Sets attribute NAME to the result. |
| `data-attrif-NAME` | `data-attrif-disabled="!can_buy"` | Sets attribute NAME (empty value) while true, removes it while false. |
| `data-event-TYPE` | `data-event-click="use(slot.index)"` | Calls the controller handler `@nui.on("use")` with the evaluated arguments. `TYPE` is any RmlUi event: `click`, `dblclick`, `mousedown`, `change`, `keydown`, `dragstart`, ... |
| `data-alias-NAME` | `data-alias-item="slots[3]"` | A local name for an address, for templates. |

Model strings are always text, never markup. RmlUi's `data-rml` (and `data-rml-*`) would set a string as markup whose `data-event` attributes call the window's handlers, so the runtime removes the attribute with an error, refuses a document whose `<body>` has one, and lint reports it as NUI012. For mixed styling, use fixed markup with `data-class-*`, or `data-for` over segments.

Expressions:

- Operators: `+ - * /`, `! && ||`, `== != < <= > >=`, `cond ? a : b`, parentheses. `+` joins strings when either side is a string.
- Strings use single quotes inside the double-quoted attribute: `data-if="mode == 'buy'"`.
- Addresses: `slot.icon`, `slots[3].icon`, `slots[i].count` inside a `data-for` with an index name.
- List size: `size(slots)`, as specified by `nova-client-src/src/NovaUI/Core/DynamicModel.h`.
- Formatting: `{{ price | format(2) }}` (two decimals), `format(value, 2, true)` drops trailing zeros, `| round`, `| to_upper`, `| to_lower`.
- Event parameters: `ev.NAME` reads a parameter of the current event, for example `ev.value` and `ev.checked` on `change`, `ev.button` on mouse events, `ev.tab_index` on the tabset's `tabchange`.
- Several actions in one event: `data-event-click="select(slot.index); open_menu()"`.

Keep bindings one-way: write model values from Python with `set()`. A binding that sets `checked` or `value` makes the control send `change`, so a `change` handler runs for input and also after `set()` moves the control, on every re-load, and on the first load, inside `__init__`. Apply `ev.checked` or `ev.value` idempotently: never toggle, resend a packet or open a window from such a handler. RmlUi can also write into a model from the document (`data-value`, `data-checked`, and assignments such as `data-event-click="tab = 2"`). `nui.py` specifies that such a write keeps a scalar key's type: an int key stays an int (a fraction is cut toward zero), text that does not read as a number of that type leaves the key as it was, and a `None` key takes the first type written. A text field bound to a number key shows the number as RmlUi prints it after each accepted keystroke, so bind free-form text to a string key and convert in Python.

## Text from game data and players

`{{ }}` translates `@ui.KEY` and `@game.KEY` inside model strings, so text that does not come from the locale files must not reach a model key as it is: a name another player chose, a message from game code, a file's text. `nui.plain_text(text)` puts a zero-width WORD JOINER (U+2060) after every `@`, so such text can never name a locale key and still looks the same:

```python
self.set(lines=[nui.plain_text(line) for line in text.split("\n")], title=nui.plain_text(title))
```

- Pass every string from callers, game data, files or players through it before it reaches a key shown with `{{ }}`. Fixed strings stay `@ui.KEY` or `@game.KEY`, which do translate.
- `None` reads as `""`, and other values as their `str()`.
- It relies on U+2060 being zero width in Noto Sans, the fallback face for every family (Tahoma included).

## Python controller API

From `assets/root/nui.py` (its docstrings are the specification).

A window is one document plus an optional model and a controller class:

| Member | Meaning |
|---|---|
| `DOCUMENT` | Store path of the `.rml` (required). |
| `MODEL` | Name the document uses in `data-model`, or `None`. |
| `MODAL` | `True` to show the window as a modal document: it takes every key and every click that the legacy lock window and the legacy top layer leave, also beside the window. Pair it with `body.nui-scrim` (see [Keyboard and modals](#keyboard-and-modals)). |
| `FEEDS` | `{model key: feed name}`: keys that follow values the game publishes from C++, with no Python (see [Feeds](#feeds)). Needs `MODEL`. |
| `initial_model()` | Returns every top-level model key with its first value. Each key's kind (scalar, list, map) is fixed from then on. Keys follow the name rule in the [Data binding cheatsheet](#data-binding-cheatsheet); one other key leaves the window unavailable. |
| `@nui.on("name")` | Marks a method as the handler for `data-event-*="name(...)"`. It receives the evaluated arguments as Python scalars: `int`, `float`, `str`, `bool` or `None`. A whole number arrives as an `int`, literals and arithmetic included (`use(3)` and `use(slot.index + 1)` pass an `int`); other numbers arrive as `float`. A list or map argument arrives as its length or member count, with no warning, so pass its members: `use(slot.index)`, not `use(slot)`. Event parameters that are not scalars (`ev.drag_element`) arrive as `None`. The name follows the name rule in the [Data binding cheatsheet](#data-binding-cheatsheet); another one raises `ValueError`. A data-event handler cannot stop an event. |
| `__init__()` | Creates the model, binds the handlers, then loads the document hidden. Events the document raises while it loads (`data-event-load` on `<body>`, `change` from bindings such as `data-attrif-checked`) reach the handlers before `__init__` returns; until then `show()`, `hide()`, `is_visible()` and `element_on()` do nothing, while `set()` and `get()` work. |
| `show()`, `hide()`, `is_visible()` | Visibility. |
| `focus(element_id)` | Gives the element with that id the keyboard focus (a text field gets the caret); `False` while the window or the element is hidden. `hide()` takes the focus off the window's fields and a later `show()` does not put it back, so focus the field again after `show()`. Works inside handlers. |
| `set_position(x_dp, y_dp, origin=(0, 0))`, `center()`, `place_next_to(other, side, gap_dp=0, element_id="")`, `clear_placement()`, `bring_to_front()`, `keep_clear_of(*targets)` | Placement in dp; see [Placement](#placement). |
| `set_value(element_id, text, caret="end")`, `insert_text(element_id, text)`, `get_value(element_id)` | A text field's text; see [Text fields](#text-fields). |
| `set(**values)` | Replaces model keys; only views that use them update. An unknown key or a value of a different kind is refused and logged; a value that is not an `int`, `float`, `str`, `bool`, `None`, `list`, `tuple` or `dict` with `str` keys raises `TypeError`. Inside a handler the values wait until the event is over (`get()` sees them at once), so a list the clicked element lives in is not rebuilt under it. |
| `get(key)` | A copy of the current value, or `None`. |
| `element_on(element_id, event, fn)` | A plain DOM event on the element with that id; `fn` gets a dict with `type`, `target_id` and, for mouse events, `button`, plus the event's other parameters (`key_identifier` for key events). Re-attached after reloads. For `"keydown"`, `fn` returning exactly `True` keeps the key (see [Keyboard and modals](#keyboard-and-modals)); any other value lets it go on, and nothing else stops an event. |
| `on_reload()` | Hook: the document was re-loaded in place (hot reload, locale change). By then the `element_on()` handlers are attached again and the new document's own events (its load, `change` from bindings) have reached the `@nui.on` handlers. The replaced document's events (its unload, a `mouseout` as it leaves) reach no handler. |
| `on_theme_changed(theme_id)` | Hook: `nui.set_theme()` applied a theme. The window's documents already carry the new theme's classes, and the components restyle by themselves; override it only to update model values that name the theme (the picker's selection). |
| `on_scale_changed(scale)` | Hook: `nui.set_scale_percent()` applied a new choice; `scale` is the factor in use. Override it to move what follows the window's size in pixels (the taskbar tells the Interface, which keeps the legacy chat above it). An automatic scale that changes with the window size calls nothing. |
| `has_class(name, element_id="")` | Whether the element (`""` the `<body>`) has the class now. The theme's classes (`skin-classic`, `theme-dark`) are on the body as soon as `nui.set_theme()` returns, before the restyle, so a facade reads its skin with `has_class("skin-classic")`. `False` without a document or with an older exe. |
| `destroy()` | Closes the document and drops the model and every handler. Inside one of the window's own handlers (a close button) the document hides at once, and it goes with the model by the end of the frame. From `destroy()` on, the document's own events (a `mouseout` as it hides, its unload) reach none of the window's handlers, so a window made again in its own handler (a reset button, a wizard step) keeps the model; a close by C++ or RmlUi still delivers the unload. |

Module functions: `nui.is_available()` (false without the `_nui` module or an active runtime, for example when NovaUI failed to start or a test started no runtime; every `Window` method is then a no-op. A headless runtime, under `NOVA_UI_HEADLESS` or a test's null renderer, is available), `nui.enabled_for_locale()` (false for right-to-left locales), `nui.set_theme(theme_id)`, `nui.get_theme()`, `nui.get_themes()` (see [Themes](#themes)), `nui.set_scale_percent(p)` (0 = automatic, else 75..200), `nui.get_scale_percent()`, `nui.get_scale()`, `nui.get_auto_scale()`, `nui.set_reduced_motion(on)`, `nui.is_reduced_motion()`, `nui.refresh_strings()`, `nui.any_window_shown()` (true while a window made through `Window` is shown; the legacy common dialogs ask it, see [The dialog kit](#the-dialog-kit)) `nui.plain_text(text)` (see [Text from game data and players](#text-from-game-data-and-players)), and `nui.now()` and `nui.feed(name)` (see [Feeds](#feeds)). The appearance setters apply at once and persist to `config/metin2.cfg` (`UI_THEME`, `UI_SCALE`, `UI_REDUCED_MOTION`). The constants `nui.KEY_ESCAPE`, `nui.KEY_RETURN`, `nui.KEY_NUMPADENTER`, `nui.KEY_TAB` and `nui.KEY_SPACE` are the `key_identifier` values of those keys (RmlUi's own numbers).

A window lives until `destroy()`: the runtime holds its handlers, so dropping the last reference does not close it. Only one window per `MODEL` name can exist at a time.

Python never runs per frame. It runs when a handler fires or when game code calls a controller method that calls `set()`.

## Feeds

The game publishes some values from C++ under feed names (`player.hp`, `quickslot.slots`), and a model key can follow one: the value reaches the document once per frame, before the runtime's update, and no Python runs. This replaces per-frame Python for values that change without an event the window hears (gauges, quickslots, a distance).

```python
class TaskBarBoard(nui.Window):
	DOCUMENT = "nui/windows/taskbar/taskbar.rml"
	MODEL = "taskbar"
	FEEDS = {"hp": "player.hp", "hp_max": "player.hp_max", "quick_slots": "quickslot.slots"}

	def initial_model(self):
		return {"hp": 0, "hp_max": 0, "quick_slots": [nui_slots.empty_slot(i) for i in range(8)]}
```

- `nui.Window` binds each key before the document loads (`_nui.BindFeed`); a value published before (the status packets at game entry) applies at once. `FEEDS` without `MODEL` raises `ValueError`.
- `initial_model()` gives each fed key its empty value of the feed's shape (an int, a float, a list); a value of another shape is refused with one warning, and the key keeps its value.
- A `set()` on a fed key lasts until the feed changes. A value published and changed again within one frame shows only the last.
- `nui.feed(name)` is the value published last, or `None`; `nui.now()` is the NovaUI clock in seconds (0.0 without a runtime), the clock of the [Clock elements](#clock-elements).
- Content asks whether the exe has the feeds before it relies on them: `nui_hud.has_engine()` (the `nuigame` module and `_nui.BindFeed`).

The game's feeds (`nova-client-src/src/UserInterface/NuiGameFeeds.h`):

| Feed | Value |
|---|---|
| `player.hp`, `player.hp_max`, `player.sp`, `player.sp_max`, `player.stamina`, `player.stamina_max`, `player.hp_recovery`, `player.sp_recovery`, `player.level` | int |
| `player.exp`, `player.exp_next` | int (the unsigned 32-bit value) |
| `player.hp_ratio`, `player.sp_ratio`, `player.stamina_ratio` | float 0..1, as the legacy gauges cut them |
| `player.hp_recovery_ratio`, `player.sp_recovery_ratio` | float 0..1: what the regeneration will reach, 0 without one |
| `player.exp_orbs` | four floats 0..1, the taskbar's EXP quarters |
| `player.exp_percent` | float |
| `quickslot.page` | int 0..3 |
| `quickslot.slots` | the current page's eight cells in the slot model ([Slot grids](#slot-grids)), rebuilt at most once a frame when a quickslot packet, a page change or `nuigame.RefreshQuickSlots()` marks it |
| `target.in_range` | bool: whether the character `nuigame.WatchTargetRange(vid, range)` watches is in range |

## Placement

A window's `<body>` can be placed from Python, in dp, so a placement follows the UI scale:

| Call | Effect |
|---|---|
| `set_position(x_dp, y_dp, origin=(0, 0))` | Puts the point `origin` of the border box (`(0, 0)` its top left, `(1, 1)` its bottom right, `(0.5, 1)` the middle of its bottom edge) at that screen point. Pick money: `set_position(mouse_x / s, mouse_y / s - 20, origin=(0.5, 1.0))`. |
| `center()` | Keeps the window in the middle of the screen. |
| `place_next_to(other, side, gap_dp=0, element_id="")` | Keeps it beside another window, or beside the element of that window with this id: `"left"`, `"right"`, `"above"` or `"below"`, `gap_dp` apart, aligned with the other's top edge (left, right) or left edge (above, below). Where that side has no room, the opposite one is used. Another side raises `ValueError`. |
| `clear_placement()` | Hands `left` and `top` back to the style sheet. |
| `bring_to_front()` | Draws it above the other NovaUI windows, without the focus. |
| `keep_clear_of(*targets)` | While the window overlaps a shown target (a `Window`, or a `(Window, element id)` pair), its `<body>` carries `nui-overlapping`, so its sheet can hide it: `body.x.nui-overlapping { opacity: 0; pointer-events: none; }`. Not `display: none`, whose zero size would end the overlap and bring it back on the next update. No argument clears the list. |

- The runtime resolves a placement after the layout of the next update, keeps the border box on the screen, and places the window again when its size, the screen size, the scale or the other window changes. A position change rebuilds no geometry.
- A body that fills the screen (an overlay, a scrim) is not moved; the scrim centers a modal dialog by itself.
- A placement holds until the next placement call, `clear_placement()` or the window's close, across re-loads. None of these calls changes the focus or the visibility.
- A window placed in a frame shows there from that frame's render on. A drag with a `<handle>` holds only until the next size, scale or screen change places the window again.
- The intro theme picker sits below the NovaUI locale strip (`place_next_to(strip, "below", 4)`) and keeps clear of the login board, the server board and the virtual keyboard.

## Text fields

A text field is an `<input>` whose type takes text (every type but radio, checkbox, range, submit and button) or a `<textarea>`. Python reaches its text through RmlUi's own input element, so the caret, the selection and the IME stay right:

| Call | Effect |
|---|---|
| `set_value(element_id, text, caret="end")` | Replaces the text, cut to `maxlength`, without line breaks in a single-line field, and sends one `change` event (`linebreak` false) when it changed, as typing does. When the field has the focus, `caret` (`"end"`, `"start"`, `"keep"` or a character index) places the caret with no selection; a field without the focus keeps its own caret. |
| `insert_text(element_id, text)` | Types `text` at the caret, replacing the selection, as key presses would: the field takes the focus first, `maxlength` applies, and one `change` follows. `"\b"` is Backspace; `"\n"` in a single-line field is Enter (`change` with `linebreak` true). The virtual keyboard types this way. |
| `get_value(element_id)` | The text, or `None`. A password field answers its real text. |

- All three return `False` (or `None`) for an unknown or hidden element and for one that takes no text. `set_value` with a caret other than those raises `ValueError`, and text that is not a `str` raises `TypeError`.
- They work inside handlers. The `change` handlers they cause wait until the handler that called them ends, as every handler does.
- A field's text never needs to enter a model: read it from `change` (`ev.value`) or with `get_value`. The dialog kit's number fields put their digits back with `set_value(..., caret="end")`.

## Keyboard and modals

The legacy UI and the game keep the keyboard unless NovaUI has a reason to take it (`nova-client-src/src/NovaUI/Core/InputArbiter.h`, `src/UserInterface/NuiHost.h`):

- NovaUI has the keyboard while one of its text fields has the focus (any input but checkbox, radio, range, submit and button; textarea; select), while a NovaUI modal (`MODAL = True`) is shown, and while the focus sits on a control the player moved it to with Tab or an arrow key that reached NovaUI (Tab out of a field, or inside a modal). Every other key goes to the legacy UI and the game hotkeys: Space attacks, Enter opens the chat.
- So in a window that is not modal, the keyboard works its buttons, tabs, toggles, sliders and list rows only after a Tab out of one of its text fields: then Enter and Space press the focused control and Tab moves on. A click, a press that goes to the legacy UI, Escape, or another non-modal window shown meanwhile (it takes the focus from the control) ends it, and the next keys are the game's again. A window without text fields cannot be worked with the keyboard unless it is modal.
- Keep a control out of the tab order when it should not be reached that way: `tab-index: none` on buttons, tabs, list rows and `.nui-focusable`; `focus: none` on form controls (the toggle's checkbox, the slider, input buttons), whose inline `tab-index: auto` outranks a style sheet. The login board takes its buttons out, so Tab moves only between its two fields.
- While a legacy modal (a lock window: the connect-failure popup, a quest dialog) is open, NovaUI gets neither the pointer (except the release of its own press) nor keys, also from a field that keeps its focus behind it, or from a NovaUI modal. Do not open a NovaUI modal from a locked legacy dialog.
- The middle button turns the game camera: it starts no autoscroll in NovaUI.
- **Typing like a legacy edit line** (the chat and the chat log): `nui-field-passes-hotkeys` on `<body>` lets F1 to F4, left Alt, Print Screen and left Ctrl reach the game while one of the document's text fields has the focus, as a legacy edit line lets them through (`ui.py` `EditLine.OnKeyDown`); every other key stays the field's. `nui-field-keeps-focus` keeps the field's focus when the player presses a legacy UI window (not the world), as a legacy edit line keeps it. The chat facades also hold wndMgr's focus away from the game window while their field has NovaUI's (`nui_hud.FocusProxy`), so `game.py`'s `CheckFocus` closes the chat on a world press, as with the legacy chat, and a legacy edit line that takes wndMgr's focus (a whisper dialog) gets the keys while the chat stays open.
- `ime.PasteString` (the legacy inventory's Alt+click on an item) types into the NovaUI text field that has the focus, at its caret; with none it reaches the legacy IME as before.

Escape:

- Escape reaches the focused NovaUI window first, also when NovaUI does not have the keyboard, and it reaches only the focused document (the last one shown or clicked; it keeps the focus after a world click). A hidden window gets none.
- A Python `element_on("", "keydown", fn)` handler that returns exactly `True` keeps it: the legacy Escape chain does not run (it would close the topmost legacy window or open the system menu). Return `True` only when the handler acted, and only while the window is shown. A data-event handler (`@nui.on`) cannot keep a key.
- Nobody keeps it: the legacy UI gets it as well. In a text field it also leaves the field (not in a modal, and not in a document whose `<body>` has `nui-escape-keeps-focus`), so the next Escape is the legacy UI's alone.
- A document that stands for a legacy dialog without a text field can keep Escape and still let the legacy key handlers see it, as the legacy dialog did: `nui-escape-passes-key-down` on `<body>`. Then the legacy Escape chain does not run (no system menu), but wndMgr's key-down does: the game window ends its item drop question and the inventory lock there. The kit's question has it; a dialog with a field must not (a legacy edit line keeps the key).
- A focused text field stops every key but Tab itself, so a document-level handler sees no Escape typed in a field. Register the same handler on each text field as well; handlers on the field itself still run.

Dialogs: a dialog that takes the keyboard is a modal. `MODAL = True` takes every key and every click beside the dialog (the legacy lock window and the legacy top layer still come first); `body.nui-scrim` draws the backdrop that shows why. A scrim without `MODAL` blocks clicks but gets no keys; `MODAL` on a plain `body.nui-window` blocks the world with nothing on screen to show it.

A confirm dialog that closes on Escape and confirms on Enter:

```xml
<body template="nui" class="nui-scrim" data-model="confirm">
	<div class="nui-window nui-anim" id="confirm-dialog">
		<div class="nui-window__titlebar">
			<handle class="nui-window__handle" move_target="confirm-dialog">
				<span class="nui-window__title">@ui.MESSAGE</span>
			</handle>
		</div>
		<div class="nui-window__body"><p>{{ text }}</p></div>
		<div class="nui-window__footer">
			<button class="nui-button nui-anim" data-event-click="cancel()">@ui.CANCEL</button>
			<button class="nui-button nui-button--primary nui-anim" autofocus="autofocus" data-event-click="accept()">@ui.OK</button>
		</div>
	</div>
</body>
```

```python
class ConfirmDialog(nui.Window):
	DOCUMENT = "nui/windows/confirm/confirm.rml"
	MODEL = "confirm"
	MODAL = True

	def initial_model(self):
		return {"text": ""}

	def open(self, text):
		self.set(text=text)
		self.show()
		self.element_on("", "keydown", self.on_key)

	def on_key(self, ev):
		if ev["key_identifier"] != nui.KEY_ESCAPE or not self.is_visible():
			return None
		self.hide()
		return True

	@nui.on("accept")
	def on_accept(self):
		self.hide()

	@nui.on("cancel")
	def on_cancel(self):
		self.hide()
```

- Enter needs no handler: `autofocus` puts the focus on the default button when the dialog is shown, and RmlUi clicks a focused element whose `tab-index` is `auto` on Enter, keypad Enter or Space. For a destructive confirm, put `autofocus` on Cancel. Do not also treat Enter as accept in the keydown handler, or it runs twice.
- A dialog with a text field: give the field the same `keydown` handler (`self.element_on("name-field", "keydown", self.on_key)`), and submit from the field with `data-event-change="submit(ev.value, ev.linebreak)"`, acting only when `linebreak` is true.
- `autofocus` acts on the first show of a document only: a show after a hide keeps the focus where the hide left it (the document). A dialog shown again focuses its default button itself, as the dialog kit does with `focus()` after each `show()`.

## UI sounds

The client host plays the legacy UI sounds for NovaUI input, the way the legacy widgets did (`ui.Button.CallEvent`, `ui.EditLine`): `sound/ui/click.wav` for a click on a button (and a left press on a button that takes no focus, which gets no click), a checkbox or radio change and a tab change; `sound/ui/type.wav` for typed text and Backspace or Delete in a field; the click for Enter in a single-line field.

- One listener on the context hears each input event once, before any handler can stop it, and plays at most one sound per event. It plays only for input: a change the model or Python makes (a bound checkbox moved by `set()`, `set_value`, `insert_text`) is silent.
- `nui-silent` on the target or an ancestor silences it.
- Controllers play no sound themselves. The one exception is the virtual keyboard, which plays the typing sound after each key, as the legacy edit line did for pasted keys.

## The dialog kit

The legacy common dialogs run on NovaUI while the `dialogs` window flag is on (see [Window flags and the factory](#window-flags-and-the-factory)). Callers do not change: at the end of `uicommon.py`, `uipickmoney.py` and `networkmodule.py` each class name is rebound to a factory, which makes the NovaUI facade with the flag on and the legacy class (`uiCommon.LegacyQuestionDialog` and so on) with it off.

| Window | Facades | Stands for |
|---|---|---|
| `dialog-message` | `nui_dialog_message.PopupDialog`, `PhasePopupDialog` | `uiCommon.PopupDialog`, `networkModule.PopupDialog` (the phase popup: connecting, login failures) |
| `dialog-question` | `nui_dialog_question.QuestionDialog`, `QuestionDialog2` | `uiCommon.QuestionDialog`, `QuestionDialog2` |
| `dialog-input` | `nui_dialog_input.InputDialog`, `InputDialogWithDescription`, `InputDialogWithDescription2` | the three `uiCommon` input dialogs |
| `dialog-money` | `nui_dialog_money.MoneyInputDialog` | `uiCommon.MoneyInputDialog` |
| `pick-money` | `nui_pick_money.PickMoneyDialog` | `uiPickMoney.PickMoneyDialog` |

- **The facades** keep the legacy constructors, method names and meanings, the `ui.ScriptWindow` calls callers make (`Show`, `Hide`, `IsShow`, `SetTop`, `GetWidth` and the rest; the layout calls such as `SetWidth`, `SetBoardWidth`, `SetSize` and `Lock` do nothing, since widths come from CSS and a modal replaces the lock), and any attribute a caller stores on them. Events are whatever the caller passed (a function, a `ui.__mem_func__`, `0`), called with no arguments; a falsy one is skipped. Every caller string goes through `nui.plain_text`.
- **One document per kind,** made with the kind's first facade and kept hidden between uses (RmlUi allows one model per name). A facade claims its kind's window to show it. While the window is shown for another facade, the second one makes the legacy dialog, replays its state into it, and routes every call to it until it closes: two invites at once still work.
- **Gone at each phase end:** RmlUi updates every loaded document each frame, shown or not, so when a phase window closes, `nui_windows.end_phase()` destroys every kind's window (`nui_dialog_kit.end_phase`): document, model and handlers. A window shown at that moment (a popup the stream opened for the next phase) goes when it hides. Facades keep their state in attributes, so a facade made before the phase end (the game window's are made while the loading phase still runs) loads its kind again at its next show. A kind whose document failed stays legacy and is not tried again.
- **Modal:** every kind but pick money (`MODAL = True`, `body.nui-scrim`). Pick money is a plain window placed above the mouse, as in legacy, so the inventory under it stays usable.
- **Enter and Escape** follow each legacy class:

| Kind | Enter | Escape |
|---|---|---|
| message | presses the button (it has the focus): `Close()` and the event | `Close()` and the event |
| question | presses the accept button (it has the focus): the accept event. New: legacy Enter did nothing here | `Close()` only, no event |
| input, money | in the field: the accept event | in the field: the cancel event |
| pick money | in the field: accept (the amount, capped at the maximum, goes to the event), then close | in the field: close |

- The buttons call their events and leave a question or input dialog open, as the legacy buttons do: callers close it themselves. A caller that replaces `OnPressEscapeKey` on a message or question dialog (the friend request does) gets its own.
- **Fields:** a field gets its text after the focus, so the caret lands at the end (RmlUi moves the caret only in a focused field, and a focus leaves it where it was). The input dialog has a text field and a password field (`dialog-input-field`, `dialog-input-secret`), and its secret mode picks one: a field never changes its `type`, since RmlUi then gives it a new widget without the old maxlength, caret and IME (lint NUI013). The other field is idle, collapsed rather than hidden, so the facade can fill and focus the field in use in the same call that set `secret`.
- **A warning line:** `QuestionDialog2.SetWarningLine(index)` marks the text of `SetText1` (0) or `SetText2` (1) as a warning, `-1` none (the default): the model's `warn_line` is that text's first row, and its paragraph gets `nui-dialog__text--warning` (`--danger` in modern, legacy's `(1.0, 0.3, 0.3)` red in classic). Every other facade of the kind shows none when it claims the window; the busy fallback colors the legacy text line (`SetFontColor`). The point reset's confirmation uses it.
- **Not ported:** `uiCommon.QuestionDialogWithTimeLimit` stays legacy until a timer exists.
- **The legacy dialogs above NovaUI (G5):** the legacy dialogs are in the UI layer, which draws under NovaUI. `nui_windows.legacy_dialog_layer(self)`, the first statement of each legacy common dialog's `Open`, moves the dialog to the `TOP_MOST` layer while a NovaUI window is shown (`nui.any_window_shown()`), which draws above NovaUI and takes the pointer first, and back to `UI` otherwise. A session without NovaUI windows is unchanged. It decides at each `Open` only. A legacy dialog that goes to `TOP_MOST` also covers the kit (`nui_dialog_kit.cover`): until it hides, every kit dialog steps aside (it stops being modal and gives up the focus), so the keys reach the legacy dialog the player sees, and Enter cannot press the default button of a kit dialog under it; then the kit dialog is modal again and takes its focus back. That is the busy fallback's second dialog and the time-limited question. Outside the kit it does not move the keyboard: a legacy input dialog opened while a NovaUI field of another window (the login board) has the focus types into that field until the player clicks the dialog.

## The drag bridge

While both UIs live, a drag is the legacy mouse controller's (`mouseModule.mouseController`), whichever UI started it, and the client host routes the pointer and Escape around it (`nova-client-src/src/UserInterface/NuiHost.h`, the arbiter's `RouteDragPointer` and `RouteDragEscape`):

- **A right press over NovaUI while something is attached** cancels the attach, as the legacy right release does; neither the press nor its release reach either UI, so it uses no quickslot. An element whose right press acts on the attach, as the legacy party member board's starts a trade, takes the class `nui-attach-right` (on it or an ancestor): its right press then reaches it, and its release cancels an attach the handler left, as the legacy right release would.
- **Escape while something is attached** cancels the attach when a shown NovaUI document holds the focus, and then reaches neither UI. Otherwise it goes on as before, and the game window's Escape cancels it. The HUD documents never take the focus.
- **A legacy press dragged 10 px or more and released over NovaUI** reaches the legacy UI as before, then the hovered NovaUI element gets `nuidrop` (it bubbles, carries `mouse_x`, `mouse_y` and `button`; bind it as `data-event-nuidrop`). A NovaUI press on a slot cell (class `nui-slot`) dragged off NovaUI and released reaches RmlUi and then the legacy UI, whose slot windows or game window drop it. A press on anything else keeps its release, as a legacy button does (only a legacy slot window passes a release on), so a slipped click on a NovaUI button with an item on the cursor drops nothing. A left press NovaUI takes starts wndMgr's 10 px from there.
- Without the drag distance an item stays attached on both sides: pick and place.

The slot grid's `SlotDrag` is the content side of it ([Slot grids](#slot-grids)).

## HUD windows

The HUD windows of Wave 2a (the taskbar and its pieces, the affects, the target board, the party, the edge buttons, the notice boards and the map name) replace legacy windows that the Interface and the game window hold and call by method name, and that the C++ callbacks reach through them. Each is a **facade**: a plain class with the legacy class's name, constructor and methods (`nui_taskbar.TaskBar` for `uiTaskBar.TaskBar`), made by `nui_windows.make()` where the legacy one is made, and a `nui.Window` board for its document.

- **The protocol of `make()`:** the document loads hidden in the constructor; `nui_ready()` answers whether it loaded and whether the exe has the Wave 2a engine (`nui_hud.has_engine()`), so an older exe keeps the legacy window; `nui_discard()` destroys the NovaUI parts. A `LoadWindow()` the Interface calls does only what legacy did after loading its uiscript.
- **`NUI_FACADE = True`** marks every facade class. The wiring in `interfacemodule.py` and `game.py` uses it to touch only NovaUI objects: their `Close` methods destroy a facade where legacy only drops the reference, and `game.py` skips the per-frame `Update()` of a NovaUI map name splash.
- **The owner rule:** a board keeps a weak proxy to its facade and never calls it while it is being made.
- **No per-frame Python:** a facade has no `OnUpdate` or `OnRender`; it acts on the Interface's calls, the C++ callbacks and its document's events. Fed keys carry what changes in between; hints open on `:hover`.
- **Strings:** fixed text is `@ui.KEY` or `@game.KEY` in markup; a `localeInfo` entry that is a function, and every name and message, goes through `nui_hud.locale_text(name, *args)` or `nui.plain_text()`.
- **Escape:** a legacy window with an Escape action keeps its place in the legacy Escape chain through a `nui_hud.EscapeProxy(action, layer="UI", exit_action=None)`: a 0 x 0 legacy window, shown while the NovaUI window shows, whose `OnPressEscapeKey` runs the action (none for `None`) and returns `True`. The expanded taskbar and the target board use one, and no NovaUI keydown handler, so Escape acts in the legacy order whatever NovaUI document has the focus. `layer="TOP_MOST"` puts the proxy before every UI-layer window in the chain, as a legacy `TOP_MOST` window is (the help). `exit_action`, when given, runs on the exit key (the window's close button, `WM_CLOSE`: `OnPressExitKey`), which the proxy then keeps; without it the exit key goes on, as before.
- **One facade per window:** `nui_hud.take_over(key, facade)` (first in each constructor) destroys the NovaUI parts of a previous facade still alive, a phase that ended without `Destroy`; `Destroy()` calls `nui_hud.forget(key, facade)`.
- **Layout and layers:** every HUD document is `body.nui-overlay` (full screen, no pointer events) with `nui-interactive` on its clickable parts and `focus: none` on the body, so a press never takes the focus from a field and buttons act on `mousedown` (RmlUi then sends no `click`). None is modal, none has a text field. The classic overlays put the legacy art at the legacy positions at 100% (1dp to the legacy pixel), anchored as legacy anchors them: from the screen's left, its center (`left: 50%` plus a margin) or its right, and from its bottom. The client draws NovaUI in two bands, which keep the legacy layers: a document whose `<body>` has the class **`nui-below-legacy-ui`** draws below the legacy UI layer, so a legacy window of that layer opened over it (a whisper dialog, the inventory) covers it and gets the pointer there, as legacy draws a later window on top; every other document draws above the UI layer and below the legacy top layer. A HUD window takes the band of its legacy window: the expanded taskbar, the energy bar, the gift icon, the game buttons, the affects, the target board, the party and the notice boards lived in the UI layer and have the class; the taskbar, the edge buttons and the map name splash were `TOP_MOST` windows and do not, so the legacy tooltips and a `TOP_MOST` dialog still draw above them, and a legacy window of the UI layer below them. `nui_hud_test.Layers` checks each window against its legacy class. Lint and snap draw every document in one pass.
- **The chat** sits on the taskbar's top edge: the Interface places it above the NovaUI taskbar's height (`TaskBar.GetBarHeight()`: 49dp modern, shrunk with the document on a narrow screen, 37dp classic, at the scale in use) and again after a theme or scale change (`SetBarHeightEvent`). The NovaUI chat (`nui_chat.ChatWindow`) takes the same `SetPosition` and puts its body's bottom center there.
- **Wave 2b** (the chat window and its input, the chat log; the minimap, the atlas, the player gauge, the shop signs and the guild war boards follow the same rules): every document is `nui-below-legacy-ui` (their legacy windows live in the GAME, UI_BOTTOM or UI layer), its `<body>` takes no focus but its text fields, and a facade's `nui_ready()` needs the Wave 2b engine as well (`nui_hud.has_engine_2b()`: `nuigame.ChatAttach`, `ViewState` and `AnchorState`). The chat's body is its 600dp block, as tall as its content; the chat log is a movable window. The chat's input (`nui_chat.ChatInput`, shared with the log) is legacy's `ChatLine` on a NovaUI field: the modes and their `#`, `%` and `!` prefixes with the mark over the field's first character, the 33-line history on Up and Down, Enter (send and stay open), Escape (clear and close), Tab (nothing), the shout limit, the insult check, and the field's length limit counted without a link's metadata (`nui_text.visible_length`). A mode change reaches every chat input (`uiChat.RefreshChatMode`), a hidden one's on its next show. The log's filters keep legacy's bit logic (command, whisper and big notice are never filtered). New: the wheel scrolls the open chat (legacy never shows its scroll bar).
- **Tests:** `tools/nui_game_support.py` holds recording stand-ins of the game modules (and the real `mousemodule.py` and `constinfo.py`); `tools/nui_hud_core_test.py` and `tools/nui_hud_test.py` check every facade's methods and constants against the legacy class, compare the legacy and NovaUI windows' `player`, `net`, `app` and mouse controller calls flow by flow, check the fixtures against the models, and check that no HUD module defines `OnUpdate` or `OnRender`.

## System windows

The Wave 3a windows (the system menu, the system options with the music list and the Interface section, the game options, the restart dialog, the help and the point reset) are facades as the HUD windows are ([HUD windows](#hud-windows)): the legacy class's name, constructor and methods, `NUI_FACADE = True`, made by `nui_windows.make()` or a factory. They differ in these rules:

- **On demand:** a system window's document exists only while it shows, because RmlUi updates every loaded document each frame, shown or not, and these windows show rarely. `nui_hud.OnDemand(make, restore, keep)` holds the board: `show()` makes it and runs `restore(board)` (the model from the facade's state, the place), `hide()` runs `keep(board)` (what the document holds, such as a moved window's place) and destroys it. The constructor runs `probe()` once, which makes and destroys one board, to answer `nui_ready()`. A facade keeps every state its window shows in attributes and fills the model at each show; a slider's or a toggle's change event that brings back the model's own value is not a move (each show moves the controls), so opening a window writes no setting. A first open after a start loads its document cold (6.7 to 9.9 ms for this size, measured offline), later opens 1.5 to 3.3 ms. Since Wave 3a the chat log and the atlas follow the same rule, keeping what legacy's one window keeps across a hide (filters, size, place, draft, title).
- **Factories:** the system menu makes the two option windows through `uiSystemOption.OptionDialog` and `uiGameOption.OptionDialog`, which are factories (`nui_windows.factory`) at the end of their modules, so the legacy and the NovaUI menu each make the window its own flag asks for. The music list belongs to the system options (`nui_system_options.FileListDialog`, its board in `nui_music_list.py`, as lint wants a controller named after the document).
- **Bands:** none has `nui-below-legacy-ui`: they draw above the legacy UI layer, since the player opens them over other windows. The help is a modal (`MODAL = True`, `body.nui-scrim`) whose scrim is the curtain: the Interface shows its legacy `TOP_MOST` curtain for the legacy help only, as that bar would draw above every NovaUI document.
- **No keyboard:** their bodies and controls take no focus (`focus: none`; form controls need it, since their inline `tab-index: auto` outranks a style sheet), buttons act on a left `mousedown`, choices are buttons with `is-selected`, and the sliders act on `change`. The toggle acts on a left `mousedown` on its label too: RmlUi makes no click in a document that takes no focus, so the label cannot flip its checkbox; the checkbox follows the model, and its `change` event is the echo. The help's body is the exception: a modal's body takes the focus when it shows (RmlUi's automatic focus needs a focusable element), so its keydown handler hears Escape and H; its button takes none.
- **Escape and the exit key** keep each legacy window's place in the legacy chains through `nui_hud.EscapeProxy`: the help's in `TOP_MOST` with an exit action, the restart dialog's keeping both keys with no action, as legacy's.
- **Places:** the classic overlays put legacy's art at legacy's places at 100% (1dp to the legacy pixel), a legacy button's label centered over its fixed art and overflowing it where it is wider, as legacy's text line does (a `<span>` label placed absolutely across the button, with `pointer-events: none`: legacy's text line takes no pointer, and a label that overflows its button would take the presses on the neighbor it covers, so GPU acted as Apply in the Wave 3a validation); modern windows are centered where legacy centers. A modern window that can be taller than the screen at 200% keeps to it and scrolls (`max-height` in `vh` on a flex column, the rows `overflow-y: auto`): the system options and the help. The two option windows keep a place the player moved them to across a hide (`nui_hud.moved_place` in `keep`), and a scale change centers them again.
- **The Interface section** of the system options has no legacy original: the theme, one choice per entry of `nui.get_themes()` (`nui.set_theme`); the UI scale as a row of choices, Auto (with its percent) and 75 to 200 percent, plus a saved percent outside them (a hand-edited 110) as one more (`nui.set_scale_percent`; not a slider, which would rescale the window under the drag); and reduced motion (`nui.set_reduced_motion`). Each applies at once and `nui.py` saves it (`UI_THEME`, `UI_SCALE`, `UI_REDUCED_MOTION`); `on_theme_changed` and `on_scale_changed` refresh the choices, and a scale change centers the window again.
- **The point reset** has no document of its own: it is two `uiCommon.QuestionDialog2` facades of the dialog kit, shown one at a time, the confirmation's first line a warning line ([The dialog kit](#the-dialog-kit)). It needs the kit (`dialogs`); without it the Interface refuses it and keeps the legacy one.
- **Choices:** a press on the choice in effect does nothing, as legacy's radio buttons ignore a press on the one that is down (`CRadioButton::OnMouseLeftButtonDown`): no setting is written again and no `/pkmode` is sent again.
- **Tests:** `tools/nui_hit_test.py` asks RmlUi's own hit test (`nuitool snap --hits`) about a grid of points on every control with an id in every golden case and fails when another element takes one; `tools/nui_sys_test.py`: each facade against its legacy class, the differential flows (the legacy windows made from their real uiscripts and pressed as a player presses them, against the boards' data events: the same `net`, `systemSetting`, `snd`, `background`, `app`, `chrmgr`, `musicInfo`, `chat` and `uiPrivateShopBuilder` calls in order, slider values within 0.01), the fixtures, the on-demand rule and the wiring.

## Window flags and the factory

`assets/root/nui_windows.py` decides which windows run on NovaUI. Each window has an id and a default; `config/metin2.cfg` overrides the defaults with `UI_NUI_WINDOWS`, comma-separated `+id` (on) and `-id` (off) tokens, which `systemSetting.GetUINuiWindows()` reads and the client keeps when it saves the file. `UI_NUI_LOGIN 1` means `+login` unless the string names `login` itself.

| Id | Window | Default |
|---|---|---|
| `login` | the login board | off |
| `dialogs` | the dialog kit | off |
| `server-board` | the server and channel board | off |
| `virtual-keyboard` | the virtual keyboard (needs the NovaUI login board) | off |
| `locale-strip` | the locale flag strip | off |
| `loading`, `empire`, `select`, `create` | the phase windows | off |
| `taskbar` | the taskbar: gauges, quickslots, the mouse-button pickers | off |
| `expanded-taskbar` | the expanded taskbar (the dragon soul button) | off |
| `energy-bar` | the energy bar | off |
| `gift-box` | the gift icon (needs the NovaUI taskbar, which makes it) | off |
| `game-buttons` | the stat, skill, help, quest, build and observer buttons | off |
| `affects` | the affect icons | off |
| `target` | the target board | off |
| `party` | the party boards and menu | off |
| `edge-buttons` | the quest and whisper edge buttons | off |
| `tip-board`, `big-board` | the tip and big notice boards | off |
| `map-name` | the map name splash | off |
| `chat` | the chat window and its input | off |
| `chat-log` | the chat log | off |
| `minimap` | the minimap: frame, controls and the map view | off |
| `atlas` | the atlas (needs the NovaUI minimap, which makes it) | off |
| `player-gauge` | the HP gauge over the player's head | off |
| `shop-signs` | the private shop signs | off |
| `guild-war` | the guild war score boards | off |
| `system-menu` | the system menu (Escape in game) | off |
| `system-options` | the system options, the music list and the Interface section | off |
| `game-options` | the game options | off |
| `restart` | the restart dialog after a death | off |
| `help` | the help window | off |
| `point-reset` | the point reset questions (needs the NovaUI dialog kit) | off |

**Groups:** a group id in `UI_NUI_WINDOWS` stands for each of its windows, in its place among the tokens: `wave1` for every Wave 1 window but `login` (`dialogs`, `server-board`, `virtual-keyboard`, `locale-strip`, `loading`, `empire`, `select`, `create`), `hud` for the twelve Wave 2a windows above (`taskbar` to `map-name`), `hud2` for the seven Wave 2b ones (`chat` to `guild-war`), and `sys` for the six Wave 3a ones (`system-menu` to `point-reset`). A later token wins per id: `+hud,-target` is every HUD window but the target board, `-target,+hud` has it on. A group id is not a window (`use("hud")` answers `(False, "flag off")`), and `set_override()` refuses one (`ValueError`). The demo configuration is `UI_NUI_WINDOWS +wave1,+hud,+hud2,+sys` (22 of its 200 characters).

- **`use(window_id)`** returns `(True, "")` or `(False, reason)` with the first check that failed: `"flag off"`, `"NovaUI unavailable"`, `"right-to-left locale"` (`nui.enabled_for_locale()`). It records the decision in `nui_windows.DECISIONS` (`"nui"` or `"legacy: <reason>"`) and writes it to `log.txt` when it changed.
- **`make(window_id, legacy, novaui, *args)`** makes the NovaUI class (a class or a `"module.Class"` string, imported only then) when `use()` allows it, else the legacy one with the same arguments. A NovaUI constructor that raises, or one whose module cannot be imported, falls back to legacy, and so does an instance whose `nui_ready()` answers `False` (its document did not load): `make()` calls its `nui_discard()` and drops it before it makes the legacy one. Each such fallback is written once to `syserr.txt` as `nui_windows: <id>: <reason>; using the legacy window` (`note_failure`).
- **`factory(window_id, legacy, novaui)`** is a function named like the legacy class that calls `make()`: the class-level wiring (`PopupDialog = nui_windows.factory("dialogs", LegacyPopupDialog, "nui_dialog_message.PopupDialog")`). A legacy class in the same module that calls its base by name must name the `Legacy` alias, since the plain name is a function after the rebinding (`uicommon.py` does).
- **The protocol of what `make()` builds:** load the document in `__init__` (hidden), not in `Open()`; `nui_ready()` says whether it loaded; `nui_discard()` destroys the NovaUI parts and sets `self._nui_discarded`. A phase window's NovaUI subclass skips the legacy `net.SetPhaseWindow(<phase>, 0)` in `__del__` once discarded, so a late collection does not clear the slot of the legacy window made in its place.
- **Phases:** a phase window's NovaUI documents go with its `Close()` (the login board and its parts, the server board, the locale strip, the phase windows' boards; the HUD with `Interface.Close` and the game window's `Close`), and come back when the phase is built again. `networkModule.MainStream` calls **`end_phase()`** after the old phase window's `Close()` and before the new one's `Open()`; it unloads the documents no phase window owns, those of the modules in `PHASE_SCOPED` (the dialog kit), and writes `nui_windows: phase ended, <n> document(s) unloaded` to `log.txt`. A document shared between windows needs such an `end_phase()`, and its module goes into `PHASE_SCOPED`: a hidden document that outlives its phase costs its update in every frame of the next.
- **`refuse(window_id, reason)`** records a refusal `use()` does not know (the virtual keyboard without the NovaUI login board, the gift box without the NovaUI taskbar, the atlas without the NovaUI minimap, the point reset without the dialog kit); `set_override(window_id, on)` writes one override and saves the config, for a settings window and tests.
- **Adding a window:** give it an id (lowercase letters, digits and `-`), add `(id, False)` to `WINDOWS`, and make it through `make()` or a factory. It stays off until its default turns on.

## Rules

`nuitool lint` enforces the ones marked with a code.

1. **Lengths in `dp`** (NUI002). `px` is allowed only for hairlines that stay one physical pixel at every scale (`1px`, `-1px`, `0px`), in `@spritesheet` rectangles (texture pixels) and under `nui/theme/`. Unitless `0`, `%`, `em`, `vw` and `vh` are fine.
2. **Colors from tokens** (NUI003, NUI004). No `#hex`, `rgb()`, `rgba()`, `hsl()` or named colors outside `nui/theme/`; `transparent` is allowed. Every `var(--x)` must be a token or a custom property declared in the same file.
3. **No inline styles** (NUI009): no `style="..."`, no `data-style-*` and no `data-attr-style`. Put rules in the window's `.rcss` and switch them with `data-class-*`. One exception: `data-style---<name>` sets the custom property `--<name>` from data, a value a skin may read with `var()` and the others ignore (the classic shop signs and guild war boards take legacy's text-length widths this way); the skin file that reads it declares a fallback.
4. **Strings from the locale files** (NUI005): every `@ui.KEY` and `@game.KEY` must exist, a `@game.KEY` must be a plain string (not an entry typed `SA`, `SNA`, `SAA` or `SAN`), the locale files end with a newline, and no key may sit in a `data-attr-*` or `data-value` binding, which is never translated (see [Localization](#localization)).
5. **Every data event has a handler** (NUI006): `data-event-*="name(...)"` in `nui/windows/<name>/<name>.rml` needs `@nui.on("name")` in the controller, `assets/root/nui_<name>.py` with each hyphen of `<name>` written as an underscore. A window name outside lowercase letters, digits and hyphens is reported too.
6. **Every reference resolves** (NUI007): `<link>` targets, templates, `<img>` sources and sprites, and image paths in style sheets.
7. **Documents load cleanly** (NUI001 parse, NUI008 load): no RmlUi warnings or errors with the fixture, and the fixture itself is valid JSON holding one object per model, whose top-level keys follow the name rule. For template files NUI001 also runs RmlUi's template reader (see [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)). Lint runs no controller, so it gives every data event a handler that does nothing: events raised while loading (`data-event-load`, `change` from bindings) are not findings, and rule 5 is the handler check.
8. **No per-frame Python.** No polling from `OnUpdate`; drive views with `set()` from game events.
9. **Overlays do not take the mouse.** A full-screen document that is not a modal dialog uses `body.nui-overlay` (`pointer-events: none`). The input arbiter only routes clicks to NovaUI while the pointer is over an element that accepts pointer events, unless a NovaUI modal is shown, which takes every click; so a full-screen body without it would swallow every world click.
10. **Only features the renderer draws** (NUI010, see the next section).
11. **Motion only in `.component.nui-anim` rules**, with values written out, and on selectors lighter than the reduced-motion rule (NUI011, see [Motion and reduced motion](#motion-and-reduced-motion)).
12. **No fixed widths on text.** Give buttons, tabs and labels room (`min-width`, wrapping rows) instead of `width`; translations are longer than English.
13. **Model strings are text** (NUI012): no `data-rml` or `data-rml-*`; the runtime removes them (see [Data binding cheatsheet](#data-binding-cheatsheet)).
14. **Literal values a NovaUI element takes** (NUI015): `nui-view` `name` and `hover`, `nui-chat-lines` `view`, `mode` and its numbers, `nui-anchor` `mode`, `snap` and its numbers, `nui-resize` `edge` and its numbers, `nui-text` `links`. A bound value (`data-attr-*`) is checked by the element when it arrives (one warning).

## What the renderer draws

The Direct3D 9 renderer implements geometry, textures, scissor clipping, transforms and the stencil clip mask. It does not implement render layers, filters or shaders, the same as the CPU renderer used by `nuitool snap`. The list at the top of `nova-client-src/src/NovaUI/D3D9/NuiRenderInterfaceD3D9.h` is the source of truth; this table follows it. These RCSS features need what is missing and must not be used; `nuitool lint` reports each as NUI010:

| Do not use | What happens |
|---|---|
| `box-shadow` | It needs a render layer saved as a texture. Without one RmlUi draws the element's background near the screen origin on every frame. Never use it. |
| `filter`, `backdrop-filter` (blur, drop-shadow, brightness, contrast, grayscale, hue-rotate, invert, opacity, saturate, sepia) | They need render layers and compiled filters. The content renders unfiltered and RmlUi logs "Could not compile filter on element". `filter: opacity()` stays opaque: use the `opacity` property. |
| `mask-image` | It needs render layers. The mask image is drawn as visible content. |
| `decorator: linear-gradient(...)`, `repeating-linear-gradient`, `radial-gradient`, `repeating-radial-gradient`, `conic-gradient`, `repeating-conic-gradient`, `shader(...)` | They need compiled shaders (`RenderInterface::CompileShader`). Nothing is drawn, and RmlUi logs "Could not generate decorator element data". |

More rules for art, from the client's image loader (`GrpImageTexture.cpp`):

- Use `.png`, `.tga`, `.jpg`, `.bmp` and `.dds` files, and legacy `.sub` regions: the types the client's resource manager has loaders for. A `.jpeg`, `.svg`, `.gif` or `.webp` file draws nothing in the client; rename a JPEG `.jpg`, convert the rest. Lint reports a reference to another type as NUI007, and snapshots draw nothing for it either.
- Avoid pure `#FF00FF` in PNG, TGA, JPEG and BMP art. On the client's Direct3D 9Ex device those files load through D3DX with a color key that turns every opaque `#FF00FF` texel transparent. `nuitool lint` reports an image with such texels as NUI010, and snapshots show them transparent, as the client does. DDS files load without the key.
- On a device the client counts as low on texture memory, PNG, TGA, JPEG and BMP images are stored in 16 bits per texel (`A4R4G4B4`, or `A1R5G5B5` without alpha) and may be halved in size. Smooth color and alpha ramps band there; DDS files keep their format.
- A missing or unreadable image file draws nothing, lays out at 0x0 when the element has no size of its own, and logs one warning that names the file. It stays missing until the client restarts: RmlUi does not ask for that path again, for that document or any other. Hot reload does not retry it (see [Hot reload and debugging](#hot-reload-and-debugging)).
- An `<img>` with an empty or absent `src`, or an unknown sprite, is different: RmlUi draws it as a solid box in its `image-color` (white by default) at its CSS size, without any image. Guard bound sources with `data-if`, as the slot grid does (`data-if="slot.icon != ''"`). Lint checks static paths only (NUI007), so a controller that binds paths at run time (slot icons) passes `''` for a file that does not exist (`app.IsExistFile`), as the legacy item data does, and the `data-if` hides the `<img>`.
- A legacy `.sub` image (a region of an atlas) never shows its atlas neighbors: filtering and clamping stop at the region's own edges, and a repeat fit tiles the region alone. On a device without pixel shader 2.0 the Direct3D 9 renderer falls back to point sampling, and a `.sub` region then clamps at the atlas's edges and cannot tile.

Safe to use: solid backgrounds, borders (all sides solid), `border-radius`, `opacity` (but do not animate it on a container, see [Motion and reduced motion](#motion-and-reduced-motion)), `transform` (translate, rotate, scale, skew, matrix, perspective), `overflow` clipping, `image`, `tiled-horizontal`, `tiled-vertical`, `tiled-box` (their tiles stretch) and `ninepatch` decorators, NovaUI's `nui-repeat-box` decorator (nine tiles whose edges and center repeat 1:1, sprites included; see [Classic skin](#classic-skin)), `<img>`, sprite sheets (`@spritesheet`, with a gutter, see below), `image-color` tints, `font-effect` (outline, shadow, glow, blur; the font engine draws those into glyph textures on the CPU), and:

- Two-color gradients: `decorator: horizontal-gradient(var(--accent) var(--danger))` and `vertical-gradient(...)`. RmlUi colors the background mesh's vertices, so no shader is involved, and the gradient follows `border-radius`. The older form `gradient(horizontal ...)` draws the same but RmlUi 6.3 logs it as deprecated, which lint reports as NUI008.
- Image fits `repeat`, `repeat-x` and `repeat-y`. Both renderers wrap along an axis whose texture coordinates leave the image (by more than 1/4096) and clamp along the other, so `repeat-x` tiles across without bleeding the top and bottom rows into each other. RmlUi refuses these fits for `@spritesheet` sprites; `nui-repeat-box` repeats sprites instead, one quad per copy.

Sprite sheets need a gutter. RmlUi addresses a sprite on its whole sheet and passes only texture coordinates, so neither renderer knows the sprite's rectangle: drawn larger than the sheet's resolution, at any UI scale above it (the automatic scale on 1440 and 2160 lines), the sprite's edge pixels filter in up to half a texel of the neighboring sprite. A `.sub` region does not have this problem. Keep at least 1 px of transparent gutter between sprites; for art whose edges must stay opaque (button-state strips, frames), repeat each sprite's edge texels into a 1 px ring around it, which means 2 px between two such sprites. The sheet's outer border needs nothing. One image per icon, or a sheet drawn at twice the size and declared `resolution: 2x`, avoids the question. The classic skin's sheets (`tools/nui_classic_art.py`) give every sprite a 2 px ring of its own texels at 1x and 4 px at 2x, wrapped around on the axes the skin repeats the sprite on and extruded on the others, so a repeated copy filters into the next copy and nothing else.

Clipping cost: an overflow element with `border-radius` always uses the stencil clip mask, on every frame, so put the radius on a wrapper that does not clip and clip with a square element inside it, as the list component does (and RmlUi makes every text input clip, so the input component has square corners). An overflow element that has a transform, or sits inside a transformed element (RmlUi applies ancestor transforms to descendants), uses the mask when its content overflows, and never the scissor, because its box can be projected anywhere. Other rectangular overflow uses the cheaper scissor. The client creates a D24S8 depth-stencil surface, so the mask is available. If the bound depth-stencil surface had no stencil bits, the Direct3D 9 renderer would skip the mask and log a warning once: rounded overflow would then clip to a rectangle, and the overflow of a transformed element would not be clipped by that element at all.

## Motion and reduced motion

Stock motion: button, list, slot, input, toggle and tooltip state changes take 0.1s, the tab indicator slides in 0.2s, and the window rises 4dp over 0.2s each time it is shown. All of it uses `cubic-out`.

How to add motion, with reasons from RmlUi 6.3. `nuitool lint` reports a break of the first four points as NUI011:

- Declare `transition` and `animation` only in a rule of the form `.your-class.nui-anim { ... }`, and put `nui-anim` on the element. Motion is then opt-in, and the reduced-motion rule in `base.rcss` can stop it. That rule is `.nui-anim.nui-anim.nui-anim.nui-anim` (four classes, weight 400,000, because RCSS has no `!important`), and every component and window sheet is linked after `base.rcss`, so a motion rule of equal or greater weight wins the tie and keeps moving. A motion rule's whole selector, ancestors and `:not()` included, may therefore hold `nui-anim`, at most two other classes, attributes or pseudo-classes, and tags, but no id: `.shop-row.nui-anim`, `.shop .shop-row.nui-anim` and `li.shop-row.is-open.nui-anim` work; `.shop .shop-row.is-open.nui-anim` and `#buy.nui-anim` do not. Lint measures each motion selector against the rule in `base.rcss` and reports one that ties or outranks it. Declare `transition` on the resting rule, not on `:hover`, `:active` or another state rule: the pseudo-class adds weight, and the transition should run in both directions anyway.
- Write durations and easings out, matching the tokens (`--dur-fast` 0.1s, `--dur-med` 0.2s, `--dur-slow` 0.3s, `--ease-out` cubic-out). RmlUi ignores a `transition` that contains `var()`, without any warning: the property jumps to its end value. An `animation` with `var()` does run, but restarts every time the theme changes.
- Durations are seconds only: `0.12s`. RmlUi does not read `ms`: `120ms` is a syntax error, logged as a warning, and the whole declaration is dropped.
- Easing names are RmlUi tweens, `family-mode`: families `back`, `bounce`, `circular`, `cubic`, `elastic`, `exponential`, `linear`, `quadratic`, `quartic`, `quintic`, `sine`; modes `in`, `out`, `in-out`. CSS names such as `ease` and `ease-in-out` do not exist.
- `transition` lists property names, then the duration, an optional delay and the tween: `transition: background-color border-color 0.1s cubic-out;`. Shorthands such as `border-color` expand to their parts.
- Design keyframes so that the last frame equals the element's normal style. When reduced motion removes an animation, the element shows that style.
- Animate `transform` to move or scale a container: it rebuilds nothing. Animating or transitioning `opacity` or `color` rebuilds meshes on every frame of the motion, because RmlUi 6.3 bakes both into vertex colors and both are inherited: on an element with descendants every background, border, decorator, image and text run under it is rebuilt (for `color`, every text run that inherits it), and the Direct3D 9 renderer makes two buffers for each rebuilt mesh. A fade of the whole group (`filter: opacity()`) needs render layers, which the renderers do not have. Keep opacity and color motion on small parts, as the stock button and tooltip transitions do. A child that sets its own `opacity` does not follow a parent's fade: opacity is inherited, not multiplied (an open tooltip stays opaque while its window would fade).
- The window-open animation plays each time the window is shown. The runtime puts the class `nui-shown` on the `<body>` in `show()` and takes it off in `hide()`, and `window-frame.rcss` keys the animation on it: `.nui-window.nui-shown.nui-anim`, plus `.nui-shown .nui-window.nui-anim` for the dialog div inside a scrim. A re-load (hot reload, locale change) keeps the class, so a visible window plays the animation again. Key a window's own opening motion on `nui-shown` the same way.

Reduced motion is the RmlUi media theme `reduced-motion`. `nui.set_reduced_motion(True)` (or `UI_REDUCED_MOTION 1` in `metin2.cfg`) activates it, and `base.rcss` then sets `transition: none; animation: none` on every `nui-anim` element. A window that follows the opt-in rule needs nothing else. To change other properties under reduced motion (for example to hide a decorative element), add a block to the window's sheet:

```css
@media (theme: reduced-motion)
{
	.shop-sparkles { display: none; }
}
```

A theme switch holds transitions off for one update. From `nui.set_theme()` to the end of the next update the runtime activates the media theme `theme-switch`, and `base.rcss` sets `transition: none` on every `nui-anim` element under it, with the reduced-motion rule's weight. So no color fades from the old theme to the new one, and every element shows the new theme in the next frame. Animations are not stopped: a skin that declared other `animation` values would restart them on a switch, so skins declare none (the classic skin changes how things look, not how they move).

## RCSS and RML differences that matter

RCSS looks like CSS but is not a browser. Each item below was checked in the vendored RmlUi 6.3 source.

Layout and styling:

- Every element is `display: inline` unless a style sheet says otherwise. `base.rcss` makes the usual block elements block; give new elements a `display`.
- There is no `outline`, no `border-style` (every border is solid), no `background-image` (use `decorator`), and `background` only sets `background-color`.
- There is no `@import`. Documents get shared sheets from the `nui` template.
- There is no `!important`. Specificity: an id counts 1,000,000, a class, attribute or pseudo-class 100,000, a tag 10,000; later sheets win ties.
- `display` supports `none`, `block`, `inline`, `inline-block`, `flow-root`, `flex`, `inline-flex` and the table values. There is no grid.
- `opacity` is inherited but not multiplied: each element uses its own value, so a child that sets `opacity` replaces its parent's.
- An auto-width inline-block or absolutely positioned box is never wider than the space available to it, and flex items shrink below their content (`min-width` defaults to 0, there is no `min-width: auto`). When a row is too narrow, a button is squeezed and its label spills out; CSS would widen the box instead. Tables do not shrink to fit; they take the full width.
- `translate()` needs two values; use `translateX()` or `translateY()` for one. Translate percentages are of the element's own size.
- An inline element is never the containing block of an absolutely positioned child, even with `position: relative`: only container boxes can be, that is block, inline-block, flow-root, flex and table boxes (`Layout/ContainerBox.cpp`). The child is placed against the nearest positioned block ancestor, often the window body. Give the parent `display: inline-block` (as the tooltip host has) or put the child in a block.
- `font-family` takes one family name. Loaded faces: Noto Sans regular, bold and italic.
- Unitless `0` is accepted for lengths.
- Intrinsic image sizes are in `dp`: an `<img>` without a width, or a decorator image with fit `scale-none`, shows a 32 px icon at 32dp.

Markup:

- A text run made only of whitespace between two tags is dropped: `<b>A</b> <i>B</i>` renders "AB". Keep the space inside a text run: `<b>A</b> and <i>B</i>`, or use `&#160;`.
- Only `&lt; &gt; &amp; &quot;` are decoded as named entities; use numeric ones for anything else, such as `&#215;` for × and `&#160;` for a non-breaking space.
- `<button>` is a plain element: the `disabled` attribute does nothing by itself. `:disabled`, and the blur and `focus: none` RmlUi applies to a disabled control, exist only for `<input>`, `<select>` and `<textarea>`. The button and list-row components therefore style `[disabled]` with `pointer-events: none` (no hit testing), `focus: none` (out of the tab order, `Focus()` refused) and `tab-index: none` (Enter and Space no longer click it; RmlUi synthesizes that click only on a focused element whose `tab-index` is `auto`, whatever its `pointer-events`). `.nui-focusable[disabled]` gets the same. What is left:
  - A control disabled while it has focus keeps the focus, and its ring.
  - `data-attrif-disabled` takes effect at the next context update, so events handled earlier in the same frame, or while the model still says enabled (for example while waiting for a server reply), still reach the handler. A handler for an action that can be disabled re-checks the model first, for example `if not self.get("can_buy"): return`.
  - `element_on()` listeners and data events other than `click` are not blocked.
  - A `<label>` that wraps or targets a `<button>` still clicks it (`ElementLabel.cpp`); do not put buttons in labels.
- RmlUi makes a `click` only on a focusable element: on a left button release it clicks the element the press went to, and a press in a document whose body has `focus: none` goes to none (`FindFocusElement` and `ProcessMouseButtonUp` in `Context.cpp`). In such a document (the HUD and system windows) no element gets `click`, so `data-event-click` never fires and a `<label>` never forwards a click to its checkbox; act on `mousedown` instead. `mousedown`, `mouseup`, the drag events and the slider (it works on `mousedown` and drag) are not affected.
- `<input>` gets its type as a class (`input.text`, `input.checkbox`, `input.range`).
- `<handle move_target="#document">` drags the whole document; `#self`, `#parent` and plain ids also work. The handle moves its target by writing `left` and `top`, so a target other than `#document` must be `position: relative` or `absolute`; a static element ignores them. `#document` always works, because the document places itself from `left` and `top`.
- RmlUi does not parse a template file as XML: it searches the text for `<head>`, `</head>`, `<body>`, `</body>` and `<template`. Once that search has passed a `/` in front of the word it looks for, it no longer matches an opening tag, so text such as `/template` before the `<template>` tag, `/head` before `<head>` or `/body` between `</head>` and `<body>` (even inside a comment) makes the template fail to load. Start the file with its `<template name="...">` tag; lint reports this as NUI001.
- A document needs its data model when it loads (see the cheatsheet), which is why every window with a model has a fixture.

Events:

- RmlUi has no drag cancel. When a drag-and-drop ends (`drag: drag-drop` or `drag: clone`), RmlUi sends `dragdrop` to the element under the pointer, if there is one, and then `dragend` to the dragged element. When the client cancels a drag, for example because the window loses activation, it ends the drag with the pointer outside every element, so only `dragend` arrives; a release outside NovaUI looks the same. Treat a `dragend` without a `dragdrop` as a cancelled drag and undo what the drag started (a lifted item, a highlighted slot). A cancelled handle or slider drag stops where it is.

## Localization

- `@ui.KEY` resolves from `locale_interface.txt` (the `uiScriptLocale` module) and `@game.KEY` from `locale_game.txt` (`localeInfo`), for the client's current locale.
- A `locale_game.txt` line whose third field is `SA`, `SNA`, `SAA` or `SAN` is not a string: `localeInfo` makes a function of it (122 such keys, the same in every locale), which never reaches NovaUI's table, so `@game.KEY` would show as written. Lint reports it (NUI005). Format it in the controller and bind the result as a model string, and set it again in `on_reload()`: an `SNA` entry ignores its argument (`localeInfo.KEY(0)`), an `SA` entry formats with `%` (`localeInfo.KEY(value)`), an `SAA` entry takes a tuple (`localeInfo.ITEM_GET_FROM_PARTY((item, name))`). Two plain entries, `REFINE_FAILURE_CAN_NOT_ATTACH` and `REFINE_FAILURE_NO_GOLD_SOCKET`, are functions too, because `localeinfo.py` defines functions of those names after it reads the file; do not use them as `@game.KEY` either.
- What is translated:
  - Text content, `{{ }}` output and the document `<title>` (RmlUi's text path).
  - Attribute values written in markup, such as `placeholder="@ui.KEY"` or `title="@ui.KEY"`: the runtime translates every attribute except `id`, `class`, `style` and `data-*` when the element is created, in documents, templates and `data-for` items alike. The `<body>` attributes are translated once the document has loaded.
  - Not values set later: see the next point.
- Values set after the element exists are not translated: a `data-attr-*` or `data-value` binding, or an attribute set from code, shows `@ui.KEY` as written, and lint reports a key there as NUI005. Bind such an attribute to a model string that the controller fills from `uiScriptLocale` (`data-attr-placeholder="hint"`).
- A missing key stays visible as `@ui.KEY` and is logged once, in text and in attributes alike.
- String tables are plain text. Some shipped strings contain `<` or `&` (key hints such as `<CTRL> + Q`: 31 in `locale_interface.txt`, 4 in `locale_game.txt` across all locales). RmlUi parses translated text again as RML and looks for `{{ }}` bindings in it, so the runtime escapes `&`, `<`, `>`, `{` and `}` in each entry there, and puts entries into attributes as they are: `<CTRL> + Q` shows as written in both. Two places show such an entry with its entities (`&lt;CTRL&gt;`, `&#123;`): `<textarea>` content and `{{ }}` output of a model string that holds a key. Keep those keys out of them, or put the translated text into the model from Python. A text node that holds its own `{{ }}` binding reads an entry's braces as brackets (RmlUi decodes the node before its view parses it), so put such a key in an element of its own: `<span>@ui.KEY</span> {{ gold }}`.
- A model string shown with `{{ }}` is translated too (see the cheatsheet), so never bind text another player wrote through `{{ }}` as it is.
- Dynamic text (names, numbers, counts) comes from the model.
- After a locale change, `nui.refresh_strings()` pushes the tables again and re-loads open documents; controllers re-apply state in `on_reload()`.

Adding a string:

- The files are UTF-8, one `KEY<TAB>value` entry per line, with LF line endings. A third tab field is used only in `locale_game.txt`, where `SA`, `SNA`, `SAA` and `SAN` make the entry a function (above); give a new display string none.
- Add the key to every locale folder: `ae br cz de dk en es fr gr hu it nl pl pt ro ru tr` under `assets/locale/locale/` (`common/` holds no locale files).
- Every file must end with a newline. Both client loaders cut the last character off every line, which is its newline, so a last line without one loses a real character in the client, and a plain append glues the new key onto that line. Lint reports a file without a final newline (NUI005). Append safely:

```bash
for l in ae br cz de dk en es fr gr hu it nl pl pt ro ru tr; do
  f=assets/locale/locale/$l/locale_interface.txt
  [ -n "$(tail -c1 "$f")" ] && printf '\n' >> "$f"
  printf 'MY_NEW_KEY\t%s\n' "English text" >> "$f"
done
```

- Then lint once per locale:

```bash
for l in ae br cz de dk en es fr gr hu it nl pl pt ro ru tr; do
  echo "== $l"; nuitool lint --root assets/nui --root assets/icon --root assets/ETC --root assets/locale --root assets/uiloading --root assets/season1 --root assets/metin2_patch_eu4 --root assets/metin2_patch_etc --root assets/metin2_patch_ds --locale assets/locale/locale/$l
done
```
- Noto Sans covers Latin, Greek and Cyrillic, which includes every non-right-to-left locale the client ships. It has no Arabic, Hebrew, CJK or Thai glyphs.
- Right-to-left text is not supported yet: RmlUi's FreeType engine does no shaping or bidirectional layout. For those locales `nui.enabled_for_locale()` is false and callers keep the legacy window.

## Scale and themes

- One `dp` is one pixel at scale 1.0. The runtime sets the ratio from the backbuffer height (1080 lines = 1.0, in steps of 0.125, between 0.75 and 2.0), or from the player's override (75 to 200 percent, `UI_SCALE`). Glyphs are rasterized at the scaled size, so text stays sharp.
- Test at 0.75, 1.0, 1.5 and 2.0. `nuitool snap --scale` takes a factor in whole percents (`1.25`, not `1.125`, which is a usage error); `--scale auto` with a `--size` gives the client's automatic scale for that height, including its 1/8 steps (0.875 at 900 lines).
- Every document's `<body>` carries the classes of the player's theme, for example `skin-modern theme-dark`; the runtime sets them and swaps them on `nui.set_theme()` (see [Themes](#themes)). Components never mention the theme: they read tokens, which change with the `theme-*` palette class and the `skin-*` class, and a skin's own rules apply under its `skin-*` class.
- The classic skin's art has a 1x sheet with the legacy pixels and a 2x sheet that takes over from a scale of 1.125, so frames and buttons stay sharp up to 200% (see [Classic skin](#classic-skin)).

## Themes

Players pick a theme, and the change applies at once, with no reload and no restart. A theme is data: a list of `<body>` classes. The runtime knows no theme by name.

**The registry.** `nui/theme/themes.json` lists the player themes in menu order; the first one is the default:

```json
{
	"$comment": "...",
	"themes": [
		{"id": "modern-dark", "label": "Modern dark", "body": ["skin-modern", "theme-dark"]},
		{"id": "modern-light", "label": "Modern light", "body": ["skin-modern", "theme-light"]},
		{"id": "classic", "label": "Classic", "body": ["skin-classic", "theme-classic"]}
	]
}
```

- `id`: 1 to 31 characters of lowercase letters, digits and `-`, unique. This is what `UI_THEME` stores.
- `label`: plain text for menus, 1 to 64 bytes of UTF-8, the fallback when the locale has no key for the theme: menus show `@ui.THEME_<ID>` (the id in upper case, `-` as `_`; `THEME_MODERN_DARK`), which every locale defines for the three themes.
- `body`: 1 to 8 class names, each `[a-z][a-z0-9-]*` and not `nui-shown`. By convention exactly one `skin-<skin>` class (the component rules: `modern` is the stock components, `classic` the legacy look) and exactly one `theme-<palette>` class (the colors in `tokens.json`); `tools/nui_tokens.py` and lint check it.
- The first theme must be `modern-dark`: the client never writes the default to `UI_THEME`.
- The runtime reads the file at start, and so do `nuitool lint` and `snap`. It ignores unknown keys, so newer content still loads on an older client; lint reports them (NUI001). Without the file, documents get no theme class. Python cannot read the file (the pack API serves no `.json`), so it asks the runtime: `nui.get_themes()`.

**How a theme applies.** The runtime puts the theme's classes on the `<body>` of every NovaUI document and takes every other theme's classes off. It swaps the union of all themes' classes, so a class two themes share stays set: going from `modern-dark` to `modern-light` changes only `theme-dark` to `theme-light`. A switch reaches the open documents, the ones loaded later and the copies a reload makes; nothing re-loads, so windows keep their focus, typed text and models. The next update restyles, without transitions (see [Motion and reduced motion](#motion-and-reduced-motion)). Never write a theme class in markup: the runtime replaces it.

**Palettes and skins.** A theme's colors come from its palette, its other tokens from `shared` and its skin's tokens (see [Tokens](#tokens)). Its component rules come from the stock components plus, for a skin other than `modern`, the skin's folder `nui/skins/<skin>/`: a component sheet that `nui.rtpl` links into every document and an overlay per window that the runtime applies after the window's sheets, every rule scoped under `.skin-<skin>` (see [Skins](#skins)). A modern theme matches no classic rule, so the classic art is never loaded there.

**Python** (`assets/root/nui.py`):

- `nui.set_theme(theme_id)` applies a theme at once, saves it (`UI_THEME` in `config/metin2.cfg`) and returns its id. The id is matched without regard to case; `"dark"` and `"light"`, from older configs and callers, mean `modern-dark` and `modern-light`. With NovaUI running, an id `themes.json` does not hold raises `ValueError` and nothing is saved. Then every open window's `on_theme_changed(theme_id)` runs.
- `nui.get_theme()` is the id in use (the saved one without NovaUI, else `modern-dark`). `nui.get_themes()` is the list of `(id, label)` pairs in menu order, `[]` without NovaUI.
- The config holds an id only when it is not the default: choosing `modern-dark` removes the `UI_THEME` line. A well-formed id the table does not know (content from a newer release) stays in the file and shows the default theme; a malformed value reads as the default.

**The theme picker.** `nui/windows/theme-picker` (controller `assets/root/nui_theme_picker.py`) shows one button per theme at the top left of the login screen, under the flag strip: placed below the NovaUI strip, or where its sheet puts it under the legacy one. Its heading is `@ui.THEME_TITLE` and its labels `@ui.THEME_*`. It keeps clear of the login board, the server board and the keyboard: while it overlaps one of them, it hides (`nui-overlapping`). `nui_login.py` opens it with the NovaUI login board (`win.nuiPicker`), hides it while a legacy popup is open and destroys it with the board. Its `<body>` has `focus: none`, so a press never takes the focus from the board's fields; RmlUi then sends no `click` there, so the buttons act on `mousedown` (`pick(theme.id, ev.button)`, left button only). The gallery's Theme button cycles through `nui.get_themes()`.

**Adding a theme.** `tools/nui_new_theme.py` scaffolds one; see [Adding a theme](#adding-a-theme).

## Skins

A skin is one folder, `nui/skins/<skin>/`, plus the body class `skin-<skin>`, which every theme of `themes.json` that uses the skin puts on every document. `modern`, the stock components, has no folder. Adding or removing a skin touches no window or component file, and a window with no rules for a skin shows that skin's components on its modern layout.

| File | What |
|---|---|
| `nui/skins/<skin>/<skin>.rcss` | The component rules, linked at the end of `nui/nui.rtpl` |
| `nui/skins/<skin>/windows/<window>.rcss` | The skin's overlay of one window: its rules for that window. `<window>` is the folder name of the document `nui/windows/<window>/<window>.rml`. |
| `nui/skins/<skin>/...` | The skin's art and generated sheets (classic: `classic-sprites.rcss`, `classic-1x.png`, `classic-2x.png`) |

**Overlays.** When the runtime loads a window document, it also applies, after the document's own sheets, the overlay of every skin named in `themes.json` that has a file for that window; `nuitool lint` and `snap` apply them through the same code. Each overlay keeps its `.skin-<skin>` prefixes, so every skin's overlay is in place at once, and a theme switch stays a change of body classes: no reload and no sheet swap. Editing an overlay reloads like editing the window's own sheet. A document that is not `nui/windows/<window>/<window>.rml` gets no overlay. In a release, an overlay comes from where its window comes from: a window the release packs takes only the overlays the release packs, so a loose file in the client folder cannot restyle it, and a window staged as loose files (a dev client on top of a release) takes its loose overlays.

**Rules.**

- Every selector in a skin's sheets starts with `.skin-<skin>`, or `body.skin-<skin>` with the window's body class after it (`body.skin-classic.login`). The selector scheme of [Classic skin](#classic-skin) holds for every skin, with its own class.
- Only the theme folders name theme classes: lint reports a `.skin-*` or `.theme-*` class in a selector of any sheet or `<style>` under `nui/` outside `nui/skins/` and `nui/theme/` (NUI014), so a window cannot get a skin's rules through a sheet of its own elsewhere either. Such rules belong in a skin folder or in `nui/theme/`. Class names that start with `skin-` or `theme-` are therefore for theme classes only, a window's block class included; the theme picker's own classes are `picker`, `picker__label` and `picker__button`.
- Lint also reports a selector in a skin's folder that does not start with its skin's class (it would apply in every theme), and a `<link>` from a window document into `nui/skins/` (the runtime links the overlays and `nui.rtpl` the component sheets; a direct link ties the window to the skin).
- An overlay rule outweighs the window rule it changes by its skin class, and the overlay comes after the window's sheets and after the skin's component sheet, so it also wins ties against both.
- RmlUi 6.3 refuses a style sheet without a rule (`StyleSheetParser::Parse` returns false and the document logs `Failed to load style sheet`), so every sheet keeps at least one rule; a stub holds an empty `.skin-<skin> { }`. A window whose whole look comes from the components links no sheet of its own (the message and question dialogs).

**The fallback guarantee.** `tools/fixtures/skin-bare/theme.json` is a test-only theme, `bare`: the skin `skin-bare`, which has no folder and no rule at all, with its own palette (the dark one with a mint accent, so a snapshot shows the palette applied). It is never in the shipped `themes.json`.

- `python3 tools/nui_skin_bare.py --out DIR` writes a scratch copy of `assets/nui/nui` with the bare theme added and prints the nuitool roots to use with it; `--snap` also snaps the gallery, the login board, character select and the question dialog in it into `DIR/snaps/`, to look at.
- `nui_skin_bare_test.py` lints every window in every theme with `bare` added, and snaps every golden page in `bare` with no RmlUi warning (with `NUITOOL` set; it skips without).
- `nui_skins_test.py` checks the layout without nuitool: no theme class in a window or component selector or in window markup, every skin selector under its skin's class, every overlay named after a window and owned by a skin in use, and a rule in every sheet. Lint's NUI014 checks the selectors too, and is the check to run while writing; window markup is the test's alone.

## Classic skin

The classic theme (`skin-classic theme-classic`) draws NovaUI windows in the legacy Metin2 look: the stone board and its title bar, the thin translucent board, the legacy buttons, fields and scrollbar, the legacy colors and Tahoma at the legacy sizes. Its art is the legacy pixels at 1x, plus 2x art made with an AI upscaler, so it stays sharp when the UI scales.

| File | What |
|---|---|
| `nui/skins/classic/classic.rcss` | The component rules, all under `.skin-classic`, and the named frame and gauge decorators |
| `nui/skins/classic/classic-sprites.rcss` | Generated by `tools/nui_classic_art.py`: the 1x and 2x sprite sheets. Do not edit. |
| `nui/skins/classic/classic-1x.png`, `classic-2x.png` | Generated: the sheets |
| `tools/classic_art/manifest.json` | The legacy pieces the sheets hold, and how each one is cut and upscaled |
| `tools/classic_art/record.json` | Generated: the method that made each 2x piece, the hashes `check` compares, and every review note |
| `nui/theme/tokens.json` | The `classic` palette and the `skins.classic` tokens |
| `nui/skins/classic/windows/<window>.rcss` | A window's classic overlay: its own classic rules (see [Skins](#skins)) |

**Selector scheme.** Classic rules must win against the modern component rules by weight, never by sheet order. RmlUi weighs an id 1,000,000, a class, attribute or pseudo-class 100,000 and a tag 10,000.

1. Every classic rule starts with `.skin-classic`.
2. A classic rule takes the exact modern selector it overrides and puts `.skin-classic` in front, which makes it heavier by exactly 100,000: modern `.nui-button:hover` (200,000) becomes classic `.skin-classic .nui-button:hover` (300,000).
3. A component that can be the `<body>` itself lists both forms: `.skin-classic.nui-window, .skin-classic .nui-window`.
4. Every modern state rule (`:hover`, `.is-hover`, `:active`, `:focus-visible`, the variants' states) has a classic rule at least one class heavier that sets everything the classic look needs, resets included (`background-color: transparent`, `border-width: 0`, `border-radius: 0`, `transform: none`).
5. A window's classic rules go into its classic overlay, `nui/skins/classic/windows/<window>.rcss`, with the same prefix: `body.skin-classic.login` (210,000) outweighs `body.login` (110,000). The overlay comes after the window's sheet and after `classic.rcss`, so it also wins ties against both.
6. No `transition` and no `animation` in classic rules, so the reduced-motion and theme-switch rules act on classic as on modern. No ids.
7. Colors from tokens, lengths in `dp`, as everywhere (NUI002, NUI003).

A window's classic overlay, from `skins/classic/windows/login.rcss`:

```css
body.skin-classic.login
{
	width: 208dp;
	margin-left: -104dp;
	decorator: classic-thinboard;
}
.skin-classic input.login-input
{
	decorator: image(classic-login-field);
	width: 120dp;
	height: 18dp;
	border-width: 0;
	background-color: transparent;
}
```

**What the components look like.** The window frame is the stone board (`ui.Board`) with the legacy title bar and close button; panels and tooltips are the thin board (`ui.ThinBoard`); buttons use the legacy large art (`--small` and `--icon` the small art, `--medium` the middle art, 61dp) with the over art on hover and focus and the down art on press; text inputs, toggle tracks, slider tracks and the scrollbar track are the legacy slot bar; slots are the legacy slot base art at the legacy 32dp pitch, with the legacy cover art, tints and digits ([Slot grids](#slot-grids)) (black, a dark top and left line, a light bottom and right line); a checked toggle shows the legacy check mark; the vertical scrollbar has the legacy arrows and ribbed thumb. Lists use the legacy highlights (white at 0.2 on hover, the translucent navy selection); sliders get a slot-bar track and a small button as the thumb. Tabs, badges and horizontal scrollbars keep their modern shapes in the classic colors. Labels are the legacy gray (`#dadada`), button labels a darker gray, `--primary` labels gold and `--danger` labels red. Buttons do not lift or dip: the art swap is the feedback. A disabled button shows its default art tinted gray (`image-color: var(--classic-disabled-tint)`) with a dimmed label (`--classic-disabled-text`), at full opacity: the legacy buttons have no disabled art, and a lower opacity let the background show through the bevel. Dialog buttons keep the legacy gray label, the primary one too.

**Sprites.** Every piece is the sprite `classic-<id>` in both sheets. A piece with slices also has `classic-<id>-l`, `-c` and `-r` (the buttons: 6dp caps and a center), which `tiled-horizontal` draws: the caps keep their width and the center stretches, which at the legacy widths (43, 61 and 88dp) draws the art 1:1. The names: `classic-board-{tl,t,tr,l,c,r,bl,b,br}`, `classic-thin-...` (the same nine), `classic-title-{l,c,r}`, `classic-close-0{1,2,3}`, `classic-button-{small,middle,large}-0{1,2,3}` with their slices, `classic-login-field`, `classic-check`, `classic-scroll-{up,down}-0{1,2,3}` and `classic-thumb-{t,c,b}`. `01` is the default art, `02` over and `03` down.

The frames repeat their edges and center 1:1, as the legacy UI draws them, through the `nui-repeat-box` decorator. It takes the nine property names of `tiled-box` (`top-left-image` to `bottom-right-image`), each a sprite or an image; `auto` leaves a tile out, so three tiles make a bar. Corners keep their size, edges repeat between them from their leading edge, the center repeats on both axes, and the last copy is clipped. `classic.rcss` names four of them:

| Decorator | Use |
|---|---|
| `classic-board` | the stone board of a window |
| `classic-thinboard` | the thin translucent board: panels, tooltips, the login board, the picker |
| `classic-titlebar` | the title bar (left, center, right) |
| `classic-thumb` | the scrollbar thumb (top, center, bottom) |

The 1x sheet holds the exact legacy pixels, so at 100% the frame and button art of a classic window is the legacy art (on the skin-proof page, `nuitool snap` matches a legacy-rule drawing of the same window to the pixel). The 2x sheet replaces it from a scale of 1.125 up (`@media (min-resolution: 1.125x)` in `classic-sprites.rcss`; `min-resolution` compares the context's dp ratio, which is the UI scale). Below 1.125 the 1x art is drawn, minified at 0.75 and 0.875.

**The art tool.** `tools/nui_classic_art.py` (Python 3 with Pillow) reads `tools/classic_art/manifest.json`:

```
python3 tools/nui_classic_art.py build [--no-ai] [--work DIR]   # decode, upscale, pack, write the sheets, the RCSS and the record
python3 tools/nui_classic_art.py build --replay DIR             # the same, from an earlier run's network output (DIR/out)
python3 tools/nui_classic_art.py check                          # write nothing; exit 1 when an output is stale
python3 tools/nui_classic_art.py rcss [--threshold X] [--force-1x] [--out FILE]
python3 tools/nui_classic_art.py legacy-ref --out DIR           # the legacy references the validation compares with
python3 tools/nui_classic_art.py sheets --out DIR               # review sheets from the committed sheets
```

- A piece is a TGA, DDS or PNG file, a `.sub` atlas region (parsed from the `.sub`, version 1.0 or 2.0) or a generated fill, with an optional crop, the axes the skin repeats it on (`tile`), optional slices, and optionally a forced method (`lanczos` or `nearest`, with a `why`), its own `detail` (0 to 2) or a review `note`.
- A repeated piece is cut from a context composite that lays it out between copies of itself, as the legacy UI draws it, so the upscaler sees its real neighbors and its copies join without seams. The tool checks the composite holds those copies.
- `build` runs Real-ESRGAN ncnn-vulkan once, on the GPU (`realesr-animevideov3` at x2, from `E:\nova-build\tools\realesrgan`), over the RGB of every composite and standalone piece; alpha never goes through the network. Each 2x piece is the network's luma plus a share of the Lanczos detail (the high-pass of the Lanczos luma), with Lanczos chroma and alpha ("av3cd"). The share is the recipe's `detail`, 0.5, or a piece's own: the stone board and the leather title bar use 1.25, because the network removes their fine grain and 0.5 left them smoother than the 1x art scaled up (the validation's sharpness check). Give every piece of one context the same `detail`: the tool recombines a context once per value, and two values would meet at a join. Every input side must be 11 to 512 px: one smaller input turns the whole run into noise, so the tool refuses to start the upscaler then.
- Lanczos replaces the AI piece where the upscaler fails, where a piece differs from the Lanczos one by more than the manifest's `garbage_mad` (a backstop, not proof), with `--no-ai`, and where the manifest forces it. The record names the method of every piece and why it is not `av3cd`.
- Look at every review sheet `build` writes (`<work>/review/`, on E:): each piece at 1x, Lanczos 2x, AI 2x and final 2x on a checkerboard, then the 1x and the final 2x on the login backdrop's pink (where a pale fringe in a cut-out shows), zoomed so a 16 px piece shows its texels, and the two assembled layouts. The build summary and the last cell of each row count two things to look at: 2x texels more than 40 levels brighter than the brightest opaque texel around them at 1x, and 2x texels that cover a clear 1x texel. Sharpened bevels and highlights count too, so a count is a place to look, not a verdict; the MAD guard misses both. A visibly broken AI piece (a mangled ornament, an invented crack, a color cast) gets `"method": "lanczos"` and a `why` in the manifest and a line in the commit message; never hide one. Today the close buttons use Lanczos (the AI lifted the X to white, so the pressed state read like the default) and the check mark does (the garbage guard). The thin board and the login field use `nearest`: they are 1 px pixel art, where the AI moved the thin board's outlines half a legacy pixel into their cut-outs and brightened them, and lifted one bevel of the field; nearest is the legacy pixels, exact at 200%.
- The sheets are packed in shelves, 512 px wide at 1x, each sprite in a gutter of its own texels (2 px at 1x, 4 px at 2x). An opaque `#FF00FF` texel becomes `#FE00FF`, since the client's color key would make it transparent.
- `check` rebuilds the 1x sheet and the RCSS and compares them, and checks the 2x sheet against the record (the upscaler's output depends on the GPU, so `check` never re-runs it). To change a piece's method or `detail` without a new network run, `build --replay <work folder>` reuses that run's `out/`; the other pieces stay byte-identical, and the record keeps that run's upscaler fields and names the folder (`replayed_from`). `python3 -B -m unittest nui_classic_art_test` in `tools/` tests the tool without a GPU.
- The work folder, the review sheets and the legacy references stay on E: and are never committed; neither is a `--force-1x` RCSS, which is for validation runs only.
- The tool is driven by its manifest: the manifest's `name` prefixes the sprites (`<name>-<piece>`) and the files (`<name>-1x.png`, `<name>-2x.png`, `<name>-sprites.rcss`), and its `out_dir` is where they go. Every command takes `--manifest FILE` for another skin's art: its record is `record.json` next to that manifest and its work folders go to `E:\nova-build\<name>-art\work`. Without it, the commands above work on the classic manifest as before. `legacy-ref` draws the classic references only (the skin-proof window and the login board).

**The font.** The classic skin's tokens set `--font-family: Nova Classic` and the legacy sizes: 12dp for body text and buttons, 14dp for large text, 11dp for the smallest (`UI_DEF_FONT Tahoma:12` and `Tahoma:14` in every locale; 12dp at 100% is the legacy 12 px em). In the client, Nova Classic is the player's installed Tahoma: the client reads `tahoma.ttf` and `tahomabd.ttf` from the Windows font folder at start and hands both to the runtime, or neither. Without them, and in `nuitool lint` and `snap`, Nova Classic is Noto Sans, so the goldens are deterministic; `nuitool snap --font "Nova Classic=<path to tahoma.ttf>"` previews Tahoma. Italic is always Noto Sans Italic. Tahoma is never shipped or copied. RmlUi draws grayscale antialiased text, where the legacy UI draws LCD subpixel text, so classic text has the legacy metrics but not its exact pixels.

**Art and CSS.** Art: the frames, the title bar and close button, the buttons (small, middle, large), the login field, the check mark and the vertical scrollbar. CSS only, in the legacy colors: text inputs other than the login field (the legacy slot bar), lists, tabs, sliders, badges and horizontal scrollbars. Slots use legacy art files directly (`slot_base.sub`, the cover buttons, the digits; 1x only, not in the sheets), as the HUD windows' overlays do for their art. The legacy buttons have no disabled art, so a disabled classic button is its default art tinted gray, at full opacity. The gauge and the virtual keyboard's keys use legacy art files directly (1x only, not in the sheets). To give another component art, add its legacy pieces to the manifest, run `build`, review the sheets, and write the rules.

**The login board.** The legacy login draws two boards (the connect board and the login window art); the NovaUI board is one document, so classic draws one thin board, 208dp wide, with the server row, the painted login fields, and Exit and Connect at the legacy button sizes. Its rows sit at the legacy offsets, measured from the top of the connect board: the fields at +56 and +91 and the buttons at +114, so the board is 142dp tall at rest, the legacy pair's height. The legacy UI shows login errors in popups, so the classic board keeps no empty line for one: the error line, centered and outlined, takes space only while there is an error, and the board grows upward by one line then. It keeps the NovaUI button order (Exit, Connect; the legacy order is Connect, Exit) and its place 72dp above the bottom edge.

**Tool licenses.** The 2x art is made with Real-ESRGAN ncnn-vulkan (MIT) and the `realesr-animevideov3` model (BSD-3-Clause, from Real-ESRGAN). Both are run on a developer machine, never shipped. Tahoma is read from the player's Windows and never shipped.

## Adding a theme

There are three kinds of theme. `tools/nui_new_theme.py` scaffolds each of them, and none needs a change to a window or component file.

```
python3 tools/nui_new_theme.py <id> --base <palette> [--label TEXT] [--palette NAME] [--skin NAME]
                               [--window NAME ...] [--name SHORT] [--shipped | --pages PAGE,...] [--dry-run]
```

- `<id>` is the theme id (`UI_THEME`), `--base` the palette its new palette copies (`dark`, `light`, `classic`). The palette is named after the id unless `--palette` names it; the label comes from the id unless `--label` gives it; the golden short name is the id without hyphens unless `--name` gives it.
- `--dry-run` lists the files and writes nothing. It refuses an id, palette or short name already in use, a base or a window that does not exist, and overlays for `modern`.
- `python3 -B -m unittest nui_new_theme_test` in `tools/` tests it.

| Kind | Example | The scaffold writes | Then you write |
|---|---|---|---|
| A palette only, on an existing skin | `nui_new_theme.py ember --base dark` (skin `modern`), or `--skin classic` for a classic palette | `theme/tokens.json` (palette `ember`, a copy of `dark`, after the others), `theme/themes.json` (the theme, last in menu order, `["skin-modern", "theme-ember"]`), `theme/tokens.rcss` and the token table in this guide (regenerated as `nui_tokens.py` does), and its entry in `docs/ui/snapshots/golden-themes.json`: 5 files | the palette's colors in `tokens.json`, then `python tools/nui_tokens.py`, which checks the contrast |
| A component skin on the modern layout | `nui_new_theme.py stone --base classic --skin stone` | the same 5, plus `skins/stone/README.md`, `skins/stone/stone.rcss` (a stub) and its link at the end of `nui.rtpl`: 8 files | the component rules in `stone.rcss`, skin tokens (`skins.stone` in `tokens.json`) and art, if the skin has any |
| A skin with layout overrides per window | the same with `--window login --window select` | the same 8, plus one overlay stub `skins/stone/windows/<window>.rcss` per window | the overlay rules |

Then, for every kind:

1. Write the skin's rules by the scheme of [Skins](#skins) and [Classic skin](#classic-skin): every selector under `.skin-<skin>`, the exact modern selector behind it, no motion, tokens and `dp`. `classic.rcss` and `skins/classic/windows/` are the worked example. Start without overlays: every window already shows the skin's components on its modern layout (the bare skin proves it), so add an overlay only where a window needs a different layout.
2. Art: a skin made from legacy art writes its own manifest, `tools/<skin>_art/manifest.json` with `"name": "<skin>"` and `"out_dir": "assets/nui/nui/skins/<skin>"`, runs `python3 tools/nui_classic_art.py build --manifest tools/<skin>_art/manifest.json`, reviews the sheets as for classic, and links `skins/<skin>/<skin>-sprites.rcss` in `nui.rtpl` before the skin's sheet. Other art goes in the skin folder and is named by `image()` paths relative to the sheet.
3. Labels: the picker and the system options' Interface section show `@ui.THEME_<ID>` (the id in upper case, `-` as `_`) when the locale has it, else the label. A translated label is optional: it adds the key to all 17 `locale_interface.txt` files (see [Localization](#localization)) and to the theme picker and system options rows of `tools/nui_button_fit.py`, 18 more files.
4. Lint loads every window in every theme of `themes.json`, so run it as in [Tools](#tools) and fix what it reports.
5. Write the goldens: `python3 tools/check_nui_snapshots.py --write --optimize --only=-<name>-`, and look at every one. Keep the `=`: the text starts with `-`, and argparse reads a separate `-<name>-` as an option and stops.
6. Run the asset tests (`python3 -B -m unittest` over `tools/*_test.py`). None of them names the shipped themes, so none needs an edit for a new theme. They do check that every golden case has its image and every image is a case, so they pass once step 5 is done.

**The golden policy.** `docs/ui/snapshots/golden-themes.json` maps every theme of `themes.json` to its short name for golden file names; the checker stops with exit 2 when a theme is missing there, or when it names one `themes.json` does not hold.

- A shipped theme gets the full matrix: every golden case whose `themes` is `"all"` (the gallery, the login board, the theme picker and every Wave 1 window, at each of their scales), 43 goldens today.
- A theme marked `"experimental": true` gets the gallery and the pages its `pages` names, at each of their scales: the scaffold's default is the login board, character select and the question dialog, 12 goldens with the gallery.
- The scaffold writes an experimental entry; `--shipped` writes a shipped one. To ship an experimental theme, delete `experimental` and `pages` from its entry and write its new goldens. The mark is for the goldens only: an experimental theme is still in the picker, so keep it out of a release until it is shipped.

```json
{"name": "ember", "id": "ember", "experimental": true, "pages": ["login", "select", "dialog-question"]}
```

**Removing a theme** is the same files in reverse: its entries in `themes.json` and `golden-themes.json`, its palette in `tokens.json` (then `nui_tokens.py`), its skin folder and `nui.rtpl` link if no other theme uses the skin, and its goldens.

## Tools

The Python tools run from the asset repository root. `nuitool` is built from `nova-client-src`; the commands assume it is on `PATH` and run from the asset repository root, with the relative paths shown. Two ways to get it:

- On Linux or WSL, with the portable harness in `nova-client-src` (no `protocol/` submodule, no GPU), the platform the snapshot goldens were written on:

```bash
cmake -S nova-client-src/tools/linux-nui -B build-nui -G "Unix Makefiles"
cmake --build build-nui -j 6 --target nuitool
ln -sf "$PWD/build-nui/bin/nuitool" ~/.local/bin/nuitool
```

- On Windows, the MSVC build of `nova-client-src` (target `nuitool`, which needs the `protocol/` submodule) writes `build/bin/<config>/nuitool.exe`. From WSL, build it with the recipe in `nova-client-src/tests/README.md` ("Driving the Windows toolchain from WSL") and link it under a name without `.exe`, since WSL does not add the extension (no `PATHEXT`): `ln -s <build>/bin/RelWithDebInfo/nuitool.exe ~/.local/bin/nuitool`. Run it from the asset repository root with relative paths: a Windows executable started from a `/mnt/<drive>` directory does not translate an absolute Linux path such as a `mktemp` directory under `/tmp` (keep `--out` relative, or pass it through `wslpath -w`). A Windows build can differ from the goldens by 1 in a few pixels (see the snapshot README).

Tokens: `python tools/nui_tokens.py`, see [Tokens](#tokens). Classic art: `python3 tools/nui_classic_art.py`, see [Classic skin](#classic-skin).

Lint, from the asset repository root:

```
nuitool lint --root assets/nui --root assets/icon --root assets/ETC --root assets/locale --root assets/uiloading --root assets/season1 --root assets/metin2_patch_eu4 --root assets/metin2_patch_etc --root assets/metin2_patch_ds --locale assets/locale/locale/en
```

All nine roots: the gauge component, the slot grid, the login screen's windows and the HUD name legacy art under `d:/ymir work/` (`assets/ETC`), the phase windows name locale and loading art, the big notice board names `season1/interface/...` (`assets/season1`), and the HUD names art that only patch groups hold under `d:/ymir work/`: the energy bar (`assets/metin2_patch_eu4`), the gift icon (`assets/metin2_patch_etc`) and the dragon soul button (`assets/metin2_patch_ds`). The client finds all of them in its packs; lint and snapshots find them only through these roots.

- `--root` is a folder that contains store paths. The first one holds the documents: `assets/nui` holds `nui/...`. Repeat it for the groups that images come from: `assets/icon` for `icon/...`, and a group with a `ymir work/` folder, such as `assets/ETC`, for `d:/ymir work/...`.
- `--locale` points at one locale folder with `locale_interface.txt` and `locale_game.txt`. Without it, NUI005 is skipped. Run lint once per shipped locale when you add keys.
- `--scripts` points at the controllers. The default tries `<root>/root`, then `<root>/../root`, which finds `assets/root`.
- Lint loads every document through the runtime, with its fixture, for NUI008, in every theme of `nui/theme/themes.json` (under the first root) at 100% and again at 200%. A problem that shows only after the first pass (the first theme at 100%) is prefixed with its pass, for example `[classic 200%] `, and a message already reported for the document is not repeated. When the runtime cannot start (for example a font that fails to load), that is itself an NUI008 finding and the exit code is 1. `--no-load` skips the loads and runs the static checks only; fixture syntax and model key names (NUI001) are checked either way.
- Lint and snap run no controller, so they give every data-event name a document calls a handler that does nothing, before the document raises its first event: the events a load raises (`data-event-load`, `change` from a binding that moves a toggle or a slider) are not findings. NUI006 is the handler check, and it checks only `nui/windows/<w>/<w>.rml` against `nui_<w>.py` (hyphens as underscores); other documents get no handler check.
- Paths after the options limit the run to those files or folders, relative to the first root: `nuitool lint --root assets/nui --root assets/icon nui/windows/settings`.
- Findings go to standard output as `path:line: NUIxxx: message`, one per line. Notes about skipped checks and the summary line go to standard error. The exit code is 0 when clean, 1 with findings and 2 for a usage error.

| Code | Finding |
|---|---|
| NUI001 | `nui/theme/themes.json` breaks a rule of [Themes](#themes) (a JSON error, an id, label or class out of form, an unknown key, a first theme other than `modern-dark`, a theme without exactly one `skin-*` and one `theme-*` class); a document, template or style sheet does not parse, RmlUi's template reader cannot find the parts of a template file, or a `.fixture.json` is not valid JSON holding one object per model, or has a top-level model key RmlUi refuses (reported on the fixture, at the JSON line; a key name at line 1). |
| NUI002 | A `px` length other than a hairline (`1px`, `-1px`, `0px`), outside `nui/theme/` and sprite rectangles. |
| NUI003 | A raw color outside `nui/theme/`. |
| NUI004 | `var(--x)` that is neither a token nor declared in the same file. |
| NUI005 | `@ui.KEY` or `@game.KEY` missing from the locale files; a `@game.KEY` typed `SA`, `SNA`, `SAA` or `SAN` in `locale_game.txt`, which `localeInfo` makes a function; any such key in a `data-attr-*` or `data-value` binding, which is never translated; or a locale file whose last line has no newline (reported at that line). |
| NUI006 | A `data-event-*` without a matching `@nui.on` handler in the controller (`nui_<window>.py`, each hyphen as an underscore), or a window name outside lowercase letters, digits and hyphens. |
| NUI007 | A link, template, image or sprite that does not resolve (a `/` path resolves from the store root), a sprite that only a `@spritesheet` inside `@media` defines (outside that media query it does not exist), an image of a type the client has no loader for (only `.png`, `.tga`, `.jpg`, `.bmp`, `.dds` and `.sub` load), a path that holds `{{ }}`, and a relative image path in a template's body. |
| NUI008 | RmlUi warnings or errors while loading the document with its fixture, in any theme at 100% or 200%, one finding per report; or the runtime did not start while loading was on. RmlUi's binding reports carry no line, so lint reports them at the line of the binding whose expression or name they quote, and a report that only follows another one (a view that could not be added) at that one's line; line 1 when nothing matches, as for a binding from a linked template. A key NUI005 already reported is not reported again. |
| NUI009 | An inline style: `style="..."`, `data-style-*` (but not `data-style---<name>`, a custom property) or `data-attr-style`. |
| NUI010 | A feature the renderers do not draw, or an image with opaque `#FF00FF` texels, which the client's color key draws transparent (see [What the renderer draws](#what-the-renderer-draws)). |
| NUI011 | Motion that RmlUi drops or that reduced motion cannot stop, including a motion selector that ties or outranks the reduced-motion rule (see [Motion and reduced motion](#motion-and-reduced-motion)). |
| NUI012 | `data-rml` or `data-rml-*` in markup: model strings are text, never markup (the runtime removes the attribute). |
| NUI013 | `data-attr-type` or `data-attrif-type` on an `<input>`: RmlUi gives the field a new widget on each type change, which drops its maxlength, caret and IME; use one input per type. |
| NUI014 | A theme class outside the theme folders: a `.skin-*` or `.theme-*` class in a selector (`:not()` included) of a style sheet or `<style>` block anywhere under `nui/` except `nui/skins/` and `nui/theme/` (a skin's rules go in its folder, `nui/skins/<skin>/`, a window's in the skin's overlay of it, `nui/skins/<skin>/windows/<window>.rcss`, and the palettes in `nui/theme/`; a window's block class gets no exemption, so a window named `theme-*` takes another block name); a selector under `nui/skins/<skin>/` that does not start with `.skin-<skin>`, after an optional element name, since it would apply in every theme; and a `<link>` from a document under `nui/windows/` into `nui/skins/` (see [Skins](#skins)). |
| NUI015 | A literal attribute value a NovaUI element refuses: `<tag>: bad <attribute> '<value>'` (rule 14). |

Snapshots:

```
nuitool snap --root assets/nui --root assets/icon --locale assets/locale/locale/en \
	--doc nui/windows/gallery/gallery.rml --fixture assets/nui/nui/windows/gallery/gallery.fixture.json \
	--theme modern-dark --scale 1.5 --size 2880x1620 --out gallery-dark-150.png
```

- `--doc` is a store path, or a file path under the first root.
- `--fixture` is not picked up automatically; pass the window's `<name>.fixture.json`.
- `--locale` points at one locale folder, as for lint, and fills the string tables before the document loads. Without it every `@ui.KEY` and `@game.KEY` shows as written, and RmlUi warns once for each.
- `--size WxH` is the backbuffer in pixels (default 1280x720). `--scale` is 0.75 to 2 in whole percents (`1.125` is a usage error, since the runtime takes a whole percent), or `auto` for the client's height-based scale, which includes the 1/8 steps (default 1). `--theme` is a theme id from `nui/theme/themes.json` under the first root (default: its first theme, `modern-dark`); an id the table does not hold is a usage error that lists the ids.
- Snap does not scroll and does not move the window, so the frame has to hold the window: `--size` at least the scale times the window's right and bottom edges in dp. A scroll container shows only its first screen. The gallery is sized for a 1920x1080 dp area: `--size 1920x1080 --scale 1`, `--size 2880x1620 --scale 1.5` and `--size 3840x2160 --scale 2` show all of it. The 1280x720 default is a smaller dp area than the client uses at any automatic scale. Snap notes on standard error when the window reaches past the frame, or when a scroll container (`overflow: auto` or `scroll`) holds more than it shows; neither changes the exit code.
- `--switch-from <id>` snaps after a run-time theme switch: the window settles in that theme, then switches to `--theme` with one update at the same time, as a player's switch restyles the next frame. It must match the snapshot made in `--theme` from the start; the snapshot check compares five such switches with their goldens (a mismatch means a switch left something of the old theme, or started a transition or an animation).
- `--time` is how many seconds of animation run before the frame is taken (default 1, which lets the window-open motion and every stock transition finish). RmlUi moves an animation at most 0.1 s per update, so snap advances the clock in steps of at most 0.1 s; long times cost one update per 0.1 s. An endless animation is caught at the phase `--time` gives it. `--reduced-motion` renders the resting state.
- `--compare golden.png [--tolerance N] [--diff diff.png]` compares with a stored image, channel by channel (N is 0 to 255, default 0), and exits 1 on a mismatch. The diff image goes to `--diff`, by default the output name with `.png` replaced by `.diff.png`. A snapshot matches the golden it was saved as at tolerance 0, as long as the golden was written by `nuitool snap` with the same `--size`, `--scale`, `--theme` and `--time`, by a build for the same platform. Windows and Linux builds can differ by 1 in a few pixels of rotated content, so compare across platforms with `--tolerance 1`. `--compare` may not name the `--out` or the diff file, since snap writes those.
- RmlUi warnings and errors during a snapshot print as `rmlui: ...` on standard error and do not change the exit code; lint reports them as NUI008. Like lint, snap gives every data event a handler that does nothing, so the guide's own windows snap without warnings.
- `--font "<family>[:bold][:italic]=<file>"` loads a local font file under a family before the runtime's own fonts, once per face: `--font "Nova Classic=/mnt/c/Windows/Fonts/tahoma.ttf" --font "Nova Classic:bold=/mnt/c/Windows/Fonts/tahomabd.ttf"` shows the classic skin in Tahoma, as the client does. Quote it: the family name has a space.
- `--boxes <json>` writes the border box `[x, y, width, height]`, in frame pixels, of the `<body>` (key `""`) and of every element with an id.
- `--hits <json>` writes where presses on each control land, as RmlUi's hit test answers (`pointer-events` included): for every visible element with an id that takes presses (a button or form control, or one with a `data-event-mouse*`, `data-event-click` or `on*` mouse attribute), nine points on a 3 x 3 grid of its border box inside the frame, counted as `own` (the control or a child), `under` (an ancestor), `none`, `clipped` (cut off by a scroll container, such as a list row scrolled out of view) and `taken`, the ids of the elements that took the rest. `tools/nui_hit_test.py` runs it on every golden case and wants `taken` empty.
- `--feed NAME=JSON`, `--view NAME=PNG` and `--anchor VID=X,Y` (each repeatable) stand in for the engine's C++ side: a feed's value published before the first update (the chat lines), a view provider's image, a character's point in dp. The files are files on disk or store paths in the roots. See [Chat lines](#chat-lines), [Views](#views) and [World anchors](#world-anchors).
- Snapshots decode DDS files and the `.sub` images of DDS atlases (most legacy `.sub` files): DXT1 (with its 1-bit alpha), DXT3, DXT5 and the uncompressed formats (A8R8G8B8, X8R8G8B8, A8B8G8R8, R8G8B8, A1R5G5B5, X1R5G5B5, R5G6B5, A4R4G4B4, 8-bit luminance), the top mip level only, with no color key, as the client loads DDS. DXT2, DXT4, a DX10 header, a cube map or a volume is refused: that image stays transparent at its own size, so the layout matches the client, and snap prints a warning naming the file (`rmlui: SoftRenderInterface: ... is not decoded`).
- The CPU renderer follows the Direct3D 9 renderer's rules: premultiplied texels filtered, clamp addressing that wraps per axis for repeat fits, `.sub` regions clamped at their own edges, the color key and the same unsupported features. Colors, borders, text and images should therefore agree within a small tolerance, but a snapshot is not a screenshot of the client.
- `docs/ui/snapshots/` holds goldens of the gallery, the login board, the Wave 1 windows (the dialogs, the server board, the virtual keyboard, the locale strip and the phase windows) and the Wave 2a windows (the taskbar and its pieces, then the rest of the HUD) in all three themes, the render test in the two modern ones, at scales 1.0, 1.5 and 2.0, and of the theme picker and the classic skin-proof page. A golden's name holds the theme's short name (`dark`, `light`, `classic`). `python3 tools/check_nui_snapshots.py` checks all of them and `--write --optimize` regenerates them (see [Golden case files](#golden-case-files) and the README there). Regenerate them in the same change as anything they show.

`nuitool help` prints the current options.

## Golden case files

A window declares its goldens in `assets/nui/nui/windows/<name>/<name>.snapshots.json`; `tools/check_nui_snapshots.py` finds every such file, so a new window adds its goldens without editing the checker:

```json
{
	"$comment": "Golden cases of this window (tools/check_nui_snapshots.py).",
	"cases": [
		{"page": "dialog-question", "themes": "all",
		 "scales": [["100", "1", "640x360"], ["150", "1.5", "960x540"], ["200", "2", "1280x720"]],
		 "fixture": true, "roots": [], "time": null}
	]
}
```

- `page` is the folder name and the golden name's prefix: `dialog-question-classic-150.png`. `themes` is `"all"`, every shipped theme of `docs/ui/snapshots/golden-themes.json` (the full matrix, so a new theme needs no edit here), or a list of short names (`dark`, `light`, `classic`) for a case that covers only some (`"variant": "busy"` is classic only). An experimental theme is added to the gallery and the pages it names (see [Adding a theme](#adding-a-theme)). Each `scales` row is the percent in the file name, `--scale` and `--size`.
- `fixture: true` passes `<name>.fixture.json`. A case with `"variant": "busy"` passes `<name>.busy.fixture.json` instead, for a state of the window the main fixture does not show, and its goldens are `<name>-busy-<theme>-<percent>.png` (select and create have a classic busy case, for the disabled buttons). `roots` are extra `--root` values after `assets/nui` and `assets/icon`, among `assets/ETC` (art under `d:/ymir work/`), `assets/locale`, `assets/uiloading`, `assets/icon`, `assets/season1` and the HUD's patch groups `assets/metin2_patch_eu4`, `assets/metin2_patch_etc` and `assets/metin2_patch_ds`. `time` is `--time` in seconds, or `null` for the default.
- The frame sizes: dialogs 640x360, 960x540 and 1280x720; the locale strip 1280x120, 1920x180 and 2560x240; the server board, the keyboard and the phase windows (a 1280x720dp design frame) 1280x720, 1920x1080 and 2560x1440.
- `feeds` (feed name to a JSON file), `views` (view name to a PNG) and `anchors` (a vid, as a string, to `[x, y]` dp) stand in for the engine's C++ side; the checker passes them as `--feed`, `--view` and `--anchor`. Paths are store paths under `assets/nui` (as `--doc` takes them): `"feeds": {"chat.window.lines": "nui/windows/chat/chat.chat.window.lines.json"}`. A feed or view file of a window sits in its folder as `<name>[.<variant>].<feed>.json` or `<name>.view.png`; the client never loads them.
- `python3 tools/check_nui_snapshots.py --write --optimize --only <name>` writes a window's goldens and re-saves them with Pillow's optimizer; the check compares pixels, so an optimized file matches the same. A case file that breaks these rules stops the checker with exit 2.

## Hot reload and debugging

Hot reload and the two hotkeys below are dev tools. They are compiled into every client build except a distribution one (the CMake option `NOVA_DISTRIBUTION` sets the define `NOVA_UI_DEV_TOOLS` to 0), in every configuration. They switch on only in a build that does not enforce the safe gate (`NOVA_SAFEGATE=OFF`, the dev and test builds), started with the environment variable `NOVA_UI_DEV` set to anything but `0`; a build that enforces the gate, as every player build does, never reads the variable (`nova-client-src/src/UserInterface/NuiHost.h`).

Hot reload also needs the asset store in file-load mode (dev runs without an installed release, `--no-patch`): every asset lookup then reads the file under the client's working directory, and a `HotReloader` watches the `nui/` folder there. One way to edit in place is to make `<client>/nui` a directory junction to `nova-client/assets/nui/nui`.

- Saving an `.rcss`, a skin's overlay of a window included, re-applies style sheets to open documents.
- Saving an `.rml` or `.rtpl`, or adding or removing any `.rml`, `.rtpl` or `.rcss` file, re-loads open documents in place. Element handlers from `element_on()` are re-attached, the new document's own events (its load, `change` from bindings) reach the `@nui.on` handlers, then `on_reload()` runs; the replaced document's events reach no handler. Models are kept. A removal counts one poll (0.5 s by default) late, so an editor that saves by replacing the file causes one reload of the kind of file it saved, not two.
- A reload does not retry an image that was missing: add the file, then restart the client (see [What the renderer draws](#what-the-renderer-draws)).
- Ctrl+Shift+D toggles the RmlUi debugger (element tree, computed styles, events).
- Ctrl+Shift+U toggles the render test page. It is loaded afresh on each toggle with RmlUi's style sheet and template caches cleared, so edits to the page, its sheets and `nui.rtpl` show without hot reload.
- The gallery has no hotkey: open it from the client's Python console or a debug script with `import nui_gallery; nui_gallery.open_gallery()`.

## Status and known gaps

- Nothing here has been checked in the running client yet; the unit and integration tests and the snapshots are the evidence so far. That includes the gallery controller, `assets/root/nui_gallery.py`, which binds the theme and close buttons with `element_on()`, and the keyboard rules of [Keyboard and modals](#keyboard-and-modals).
- A data-event handler (`@nui.on`) cannot stop an event; only an `element_on` keydown handler can keep a key (by returning `True`).
- `nui.plain_text()` keeps text from players and game data from naming a locale key (see [Text from game data and players](#text-from-game-data-and-players)); it relies on U+2060 being zero width in Noto Sans.
- Attribute values set after the element exists (`data-attr-*`, `data-value`, code) are not translated (see [Localization](#localization)).
- Right-to-left scripts are not supported. NovaUI text fields show the IME composition, underlined, inside the field; like the legacy edit line, they show no candidate list.
- RmlUi has no drag cancel event (see [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)).
- Snapshots refuse DXT2, DXT4, DX10 headers, cube maps and volumes; those images stay transparent. Other DDS files and `.sub` regions of DDS atlases are drawn.
- A missing image is not retried until the client restarts, hot reload included (see [What the renderer draws](#what-the-renderer-draws)).
- Themes and the classic skin are covered by unit tests, lint in every theme and the snapshots; their checks in the running client (the scaling matrix, switching on the go, persistence) come separately.
- Classic text is antialiased in grayscale, the legacy text in LCD subpixels, and the outline the legacy tooltips draw around their text is not reproduced.
- The legacy buttons have no disabled art: a disabled classic button is its default art tinted gray.
- The dialog kit: one shown dialog per kind (a second one at the same time is the legacy dialog); `QuestionDialogWithTimeLimit` stays legacy until a timer exists; Enter on a question presses its default button (new); widths come from CSS, so `SetWidth`, `SetBoardWidth` and `SetSlotWidth` do nothing, and the dialogs are wider than the fixed legacy boards. Classic shows the focused default button in its over art.
- The G5 stopgap decides a legacy dialog's layer at each `Open` only. It takes the keys from the dialog kit while a legacy dialog covers it, but not from a NovaUI field of another window. A legacy dialog shown again with `Show()` rather than `Open()` does not cover the kit again.
- The virtual keyboard shows only on a screen at least 680dp tall (below that the board and the keyboard do not fit together). It plays the typing sound from Python after each key. Its classic key art and the classic gauge art are 1x only.
- Every Wave 1, 2a, 2b and 3a window is off by default (`nui_windows.WINDOWS`) until its flows have run against a game server.
- **Slot grids and the drag bridge:** a release over a NovaUI grid outside every cell keeps the item attached, where legacy cancels the drag; with a legacy window open and a NovaUI document focused, Escape cancels a drag before it closes that window. The cooldown sweep follows RmlUi's angle projection, a few pixels from the legacy edge interpolation mid-octant, in 64 steps. The slot effects are additive, not screen: brighter than legacy where effect and background are both bright, and washed toward white on the modern light theme's slots.
- **Feeds** apply once per frame; a value published and changed again within one frame shows only the last, and a `set()` on a fed key lasts until the feed changes.
- **Tooltips:** item and skill tooltips stay the legacy windows (the tooltip bridge), drawn above NovaUI.
- **The taskbar:** the classic gauges show the first of the legacy seven fill frames, still: RmlUi 6.3 does not animate `fill-image`, the property that cuts the art at the value. The right mode menu shows attack and camera, as legacy does (its skill button is hidden there; skills are picked in the picker). The gauge and digit art is 1x only. The modern bar needs 1060dp; on a narrower screen (1280 wide at 150%, 1024 at 100%) its document shrinks about the bottom-left corner in steps of 5% down to 60%, which fits from 636dp; below that its parts touch, and text in a shrunk bar is filtered. Classic fits from 800dp and never shrinks.
- **The energy bar** changes state only on a status refresh or a hover, as legacy. **The gift icon** stays legacy while the taskbar is legacy (the NovaUI taskbar makes it).
- **The other HUD windows**, where they differ from legacy on purpose:
  - Affects: the auto potion and dragon soul values are read once per hover, where legacy reads them every frame; the love point heart uses the grade legacy meant (its `/` looks up a fraction and falls back to a missing `00.dds`); a mall affect's text is formatted again on a locale change. The auto potion art is only in the `patch2` group, which the golden checker does not take as a root, so no golden shows it.
  - Target board: the classic board is as wide as its content (legacy computes 200 plus 7 per letter, or 75dp per button), and a label wider than its 60dp button overflows both sides, as legacy's centered text does.
  - Party: a former leader sees Leave alone (legacy also keeps Break up); the menu and role buttons hide with the party window, where legacy makes them separate windows.
  - Edge buttons: in classic a stack's column height stands for the legacy row count with `bottom: 75dp`, exact at 900 lines (at 720 lines it holds 7 rows where legacy has 6). In modern the columns end 120dp above the bottom, clear of the game buttons and the gift icon (8 rows at 900 lines where legacy has 9), and while the party shows the quest column starts at 190dp, right of the wider modern party menu (legacy and classic: 130dp). A flashing button blinks through `nui-blink` on the shared clock.
  - Game buttons: in modern the label pill sits beside its button (right of a left button, left of a right one), not under it, where it would cover the taskbar's gauge and button hints; classic keeps the legacy labels under the buttons.
  - Layers: a `nui-below-legacy-ui` window stays under every legacy window of the UI layer, also one opened before it, where legacy's `SetTop` raises the window shown last (the expanded taskbar over an inventory that overlaps it, rare at the legacy places). A legacy window that opens under a pointer that does not move leaves the NovaUI hover where it was until the next move.
  - The classic gauge and EXP hints sit where legacy's would for a pointer in the middle of their board; legacy's follow the pointer.
  - Affects: classic draws the icons nearest-sampled at 100% and below (`#nui-nearest`), as legacy does.
  - Notice boards: one line at a time, advanced by a `nui-countdown` timer and slid by `transform`, where legacy scrolls a pixel per frame; the big board shows a batch once through and hides, as legacy's inverted cleanup does, and a long notice wraps where legacy splits it in two.
  - Map name splash: a keyframe fade hidden by a timer; `game.py` skips its per-frame `Update()` for the facade.
- **The chat and the chat log** (Wave 2b), where they differ from legacy:
  - The field shows a pasted link as its raw tags: an RmlUi input cannot style parts of its text.
  - The field's length limit counts characters (code points) without a link's metadata, as the shared tag cases fix it; legacy's IME counts the UTF-8 bytes of the visible text (`IME.cpp:1445-1460`), so a line in Cyrillic or Greek holds about twice as many characters as in legacy.
  - The closed chat's lines fade as whole lines (an opacity transition), where legacy fades their color per frame; a tagged run keeps its own color until the line goes in both.
  - New: the wheel scrolls the open chat, and a press on the open history does nothing (legacy's history is not a window, so a press there reached the world, which closed the chat).
  - Tab in the field does nothing; legacy's `ChatLine.OnIMETab` answers False, so wndMgr gave its focus to the oldest window of its focus list (inferred from `PythonWindowManager.cpp:1276-1296`, not run).
  - No resize cursor over the sizing bar and the log's grip (the host sets no cursor), and no candidate list for an IME (as the legacy edit line).
  - Classic: the log's body has no darker edge (legacy draws two 1 px boxes at 47%), and the filter labels overflow the 38dp xsmall art in several locales, as legacy's do on the same art.
  - The modern chat keeps a dark backdrop and dark-backdrop line colors in the light theme too: the colors of tags (item links, notices) come from game data made for a dark backdrop.
- **The system windows** (Wave 3a), where they differ from legacy:
  - The point reset shows one question at a time and localized texts (`POINT_RESET_*`), where legacy shows the confirmation over the question and hard-codes Korean in every locale. No path reaches it on this client and server: `SendPointResetPacket` has no caller and the server has no `pointreset` command.
  - The modern help is a centered card without the taskbar pointers, which aim at the legacy taskbar's places. With the legacy taskbar (`hud` off) the taskbar's `TOP_MOST` buttons stay above the help's scrim and take the pointer first.
  - The camera distance, the name color and the target board option are not saved across a restart, as in legacy (module state in `constinfo.py`). The music list's empty-list popup cannot show, as in legacy: the default entry is always there.
  - The mall button sends `/in_game_mall` as legacy does; the web window it opens is not ported. The portal variant of the system menu (`SYSTEM_MENU_FOR_PORTAL`, off) is not ported.
  - The classic Interface section has no legacy original: its layout is new, on legacy art, and the board grows under legacy's 255 px by its height.
  - The music list's popups are `uiCommon.PopupDialog` (the kit's facade with `dialogs` on), not legacy's private copy.
- `UI_NUI_WINDOWS` holds at most 200 characters, and an older client drops it when it saves the config.
- Gauges show their value at once, with no easing.
- A placement is resolved after layout: a window placed in a frame shows there from that frame's render on, and a handle drag holds until the next size, scale or screen change.
- UI sounds play for input only: changes Python or the model make are silent, by design.
- `nui-frames` builds each frame's mesh the first time it is drawn; a bound `data-attr-frames` is not linted.
- Classic art covers the frames, the title bar and close button, the buttons, the login field, the check mark and the vertical scrollbar; slots, the gauges and the HUD use legacy art files directly (1x only); other inputs, lists, tabs, sliders, badges and horizontal scrollbars are CSS in the legacy colors (see [Classic skin](#classic-skin)).
- The classic login board is one thin board where the legacy UI draws two, and keeps the NovaUI button order (Exit, Connect).
- Every document parses the classic sheets and holds the classic sprites in its sprite namespace; the sheet textures load only when a classic rule matches.
- A client without the `nui-repeat-box` decorator (an exe older than this content) logs two parse warnings for each named decorator of the classic sheet (the four frame and the five gauge decorators): `Invalid decorator type 'nui-repeat-box'` and then `Invalid character '}'`. It has no theme table either: `nui.get_themes()` is empty, so the login board opens without the picker, and only dark and light exist. An exe without skin overlays applies no `nui/skins/<skin>/windows/` sheet, so its classic windows show the classic components on their modern layout. The exe and the `nui` group ship together.
- If FreeType refuses one of the two Tahoma faces the client hands over, classic text can mix Tahoma and Noto Sans; the runtime logs it.
- A well-formed `UI_THEME` id the table does not hold stays in the config and shows the default theme; an older client reads a new id as the default and drops it when it saves the config.
- Below a scale of 1.125 the 1x classic art is drawn, minified at 0.75 and 0.875.

### Future work

- **Loading only the active skin's sheets.** Every document links every skin's component sheet (through `nui.rtpl`) and gets every skin's overlay of it, whatever theme is in use; that is what keeps a theme switch to a change of body classes, with no reload and no sheet swap. With a handful of skins it is cheap. Measured in the client runtime on 2026-10-05 (`NuiLoadBench`, MSVC RelWithDebInfo, the 18 window documents, theme classic, the sum of the per-window medians of 50 rounds; method and table in `nova-client-src/src/NovaUI/README.md`, Skin overlays): opening every window again (RmlUi's sheet cache kept) took 42.7 ms with the classic rules inside the window sheets, 42.7 ms with them in classic's overlays, and 58.0 ms with three more full copies of classic as fake skins; the first load of a session, which parses every shared sheet once, took 135.6, 145.5 and 243.5 ms. Each further full skin adds about 0.3 ms to a window's load and first frame when opened again: the login board takes 2.41 ms with one skin and 3.31 ms with four. As whole processes, measured with `nuitool snap` on Linux, the overlays linked after each window's sheet, at a 160x90 frame so that loading dominates (each run starts the runtime, loads the fonts and the document; median of 15 runs, which spread by about 50 ms): with classic alone and with three more copies of classic as fake skins, the login board took 710 and 783 ms, character select 820 and 914 ms and the gallery 949 and 962 ms; without classic at all, 685, 770 and 930 ms. A full `nuitool lint` run, which also reads every sheet, took 5.4 s with classic alone and 7.7 s with the three copies (median of 7). Loading only the active skin would cost a reload or a sheet swap on every switch; revisit it when there are more than a handful of skins or a document loads slowly in the client.
