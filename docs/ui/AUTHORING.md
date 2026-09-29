# NovaUI authoring guide

NovaUI is the RmlUi 6.3 layer that new client windows are written in: RML markup, RCSS style sheets, data bindings, and a Python controller that runs only on events. The legacy `wndMgr` UI keeps running next to it, and windows move over one at a time.

This guide is for people and AI agents writing windows. It is a reference: every rule below is either enforced by `nuitool lint` or explained by an RmlUi 6.3 behavior that was checked in the vendored source (`nova-client-src/vendor/RmlUi-6.3`). Where the RmlUi documentation and this guide disagree, this guide describes what the vendored version does.

Status: the content (tokens, components, gallery, render test) and the contracts are in place. The runtime, the Direct3D 9 renderer and the `_nui` Python module are being integrated, so some behavior described here is the contract rather than something you can run in the client yet. [Status and known gaps](#status-and-known-gaps) lists what is pending.

## Contents

- [New window checklist](#new-window-checklist)
- [File layout and store paths](#file-layout-and-store-paths)
- [A complete window](#a-complete-window)
- [Components](#components)
- [Tokens](#tokens)
- [Data binding cheatsheet](#data-binding-cheatsheet)
- [Python controller API](#python-controller-api)
- [Rules](#rules)
- [What the renderer draws](#what-the-renderer-draws)
- [Motion and reduced motion](#motion-and-reduced-motion)
- [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)
- [Localization](#localization)
- [Scale and themes](#scale-and-themes)
- [Tools](#tools)
- [Hot reload and debugging](#hot-reload-and-debugging)
- [Status and known gaps](#status-and-known-gaps)

## New window checklist

1. Pick a lowercase name, for example `settings`. Create `assets/nui/nui/windows/settings/`.
2. Write `settings.rml` from the skeleton in [A complete window](#a-complete-window): link `../../nui.rtpl`, put `template="nui"` and `class="nui-window nui-anim"` on `<body>`.
3. Write `settings.rcss` for the window's size and position and anything the components do not cover. Use tokens for every color and `dp` for every length.
4. Write `settings.fixture.json` with every key of every data model the document binds. Lint and snapshots load the document with it.
5. Write the controller `assets/root/nui_settings.py`: subclass `nui.Window`, set `DOCUMENT` and `MODEL`, return every model key from `initial_model()`, and add one `@nui.on("name")` method for every `data-event-*="name(...)"` in the document.
6. Use `@ui.KEY` (from `locale_interface.txt`) or `@game.KEY` (from `locale_game.txt`) for every visible string. The key must exist in every locale.
7. Run `python tools/nui_tokens.py --check` if you touched `tokens.json`, then `nuitool lint` until it prints nothing.
8. Run `nuitool snap` in both themes at scale 1.0, 1.5 and 2.0, and once with `--reduced-motion`. Look at the images.
9. Check the window with the German locale (strings run about a third longer than English) and at 75% scale.
10. Open the window from game code only through its controller. Never call RmlUi or `_nui` directly.

## File layout and store paths

NovaPack publishes a file at `assets/<group>/<path>` under the store path `<path>`, lowercased (`src/AssetLib/PathNorm.h`). The `nui` group in `assets/groups.txt` therefore holds a second `nui/` folder, the same pattern as `assets/icon/icon/` and `assets/locale/locale/`:

| In the repository | Store path | What |
|---|---|---|
| `assets/nui/nui/nui.rtpl` | `nui/nui.rtpl` | template that links every shared style sheet |
| `assets/nui/nui/base.rcss` | `nui/base.rcss` | element defaults, typography, focus, scrollbars, reduced motion |
| `assets/nui/nui/theme/tokens.json` | `nui/theme/tokens.json` | design tokens, the source of truth |
| `assets/nui/nui/theme/tokens.rcss` | `nui/theme/tokens.rcss` | generated from `tokens.json`, never edit by hand |
| `assets/nui/nui/components/*.rcss` | `nui/components/*.rcss` | one style sheet per component |
| `assets/nui/nui/fonts/NotoSans-{Regular,Bold,Italic}.ttf` | `nui/fonts/...` | Noto Sans 2.015 (OFL, see `OFL.txt` next to them) |
| `assets/nui/nui/windows/<name>/<name>.rml` | `nui/windows/<name>/<name>.rml` | the window document |
| `assets/nui/nui/windows/<name>/<name>.rcss` | same folder | the window's own rules |
| `assets/nui/nui/windows/<name>/<name>.fixture.json` | same folder | sample model data for lint and snapshots |
| `assets/root/nui_<name>.py` | `nui_<name>.py` | the controller, imported as `nui_<name>` |
| `assets/nui/nui/windows/gallery/` | | every component in every state |
| `assets/nui/nui/windows/render-test/` | | every renderer feature on one page |

The client itself loads the fonts, the gallery and the render test by the constants in `nova-client-src/src/NovaUI/Core/NuiPaths.h`.

Paths inside documents and style sheets:

- A relative path resolves against the file that contains it: `href` and `src` in an `.rml` against the document, `image(...)` in an `.rcss` against that style sheet. `..` segments are normalized.
- Never start a path with `/`. The runtime passes such a path through unchanged and the store has no names starting with `/`, so it never loads.
- Name files in lowercase with hyphens. The store lowercases every lookup; tools on Linux are case-sensitive, so write references with the exact case of the file. The three font files are the only mixed-case names (fixed by `NuiPaths.h`).
- Legacy assets outside `nui/` are reached by climbing to the store root. From `nui/windows/<name>/` that is three levels: `../../../icon/item/27001.tga`. Model values from Python are store paths (`item.GetIconImageFileName()` style), so prefix them in the binding: `data-attr-src="'../../../' + slot.icon"`.
- Legacy `d:/ymir work/...` paths work as written; the runtime treats the drive prefix as absolute.

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
- A range input reports `ev.value` as a float, so the handler rounds it before storing an int.

## Components

All class names start with `nui-`. Modifiers use `--`, parts use `__`, states use `is-*`. The gallery (`nui/windows/gallery/gallery.rml`) shows each one in every state; copy markup from there.

| Component | Markup | Variants and states |
|---|---|---|
| Window frame | `<body class="nui-window nui-anim">` with `nui-window__titlebar`, `nui-window__handle` (a `<handle move_target="#document">`), `nui-window__title`, `nui-window__close`, `nui-window__body`, `nui-window__footer` | Fades in with a 4dp rise when the document loads. For a modal dialog, use `<body class="nui-scrim">` with a `div.nui-window` inside and point the handle at the div's id: `move_target="my-dialog"` (a plain id, no `#`). |
| Button | `<button class="nui-button nui-button--primary nui-anim">` | `--primary`, `--secondary` (the default look), `--ghost`, `--danger`; sizes `--small`, `--icon`. `:hover`, `:active`, `:focus-visible`; `disabled` attribute. |
| Panel | `<div class="nui-panel">` with an optional `nui-panel__title` | `--sunken`, `--flat`. `nui-divider` is a 1dp rule. |
| Tabs | native `<tabset class="nui-tabs nui-tabs--3">` with `<tab>` and `<panel>` pairs and a last `<tab class="nui-tabs__indicator nui-anim">` | `nui-tabs--2` to `--6` must match the number of real tabs. Tabs switch without Python; the selected tab and panel get `:selected`. |
| List | `<div class="nui-list">` with rows `<div class="nui-list__item nui-anim">`, parts `nui-list__label`, `nui-list__meta` | `is-selected`, `disabled` attribute, `:hover`, `:focus-visible`. Give the list a height in the window sheet to scroll. |
| Slot grid | `<div class="nui-slot-grid">` with `<div class="nui-slot nui-anim">`, `<img class="nui-slot__icon">`, `<span class="nui-slot__count">` | 40dp cells for 32dp icons. `is-selected`, `is-disabled`, `:hover`. |
| Slider | `<input type="range" class="nui-slider" min max step value>` | `disabled` attribute. RmlUi builds the track, fill and thumb. |
| Toggle | `<label class="nui-toggle">` around `<input type="checkbox" class="nui-toggle__input">`, `nui-toggle__track`, `nui-toggle__knob`, `nui-toggle__label` | `checked` and `disabled` attributes. The label forwards clicks to the hidden checkbox. |
| Text input | `<input type="text" class="nui-input">` (also `type="password"`), inside `div.nui-field` with `label.nui-field__label` and `span.nui-field__error` | `--invalid`, `disabled` attribute, `:focus`, `:placeholder-shown`. |
| Tooltip | `<span class="nui-has-tooltip">` host with `<span class="nui-tooltip nui-anim">` inside | One line by default; `--wrap` wraps at 240dp. `is-open` shows it without hover. Item tooltips stay on the legacy `uitooltip` windows. |
| Badge | `<span class="nui-badge">` | `--accent`, `--danger`, `--warning`, `--success`. |
| Layout helpers | `nui-row` (flex row, `--wrap`, `--end`, `--between`), `nui-stack` (flex column, `--loose`), `nui-grow`, `nui-muted`, `nui-small` | Use these instead of inline styles. |
| Full-screen layers | `<body class="nui-overlay">` for HUD layers that never take the mouse; `nui-interactive` on children that should | `nui-center-max` caps content at 1600dp; `nui-safe-16x9` limits a HUD anchor area to 16:9 of the screen height on ultrawide screens. |

`is-hover`, `is-active` and `is-focus` force the look of `:hover`, `:active` and `:focus-visible` on buttons, inputs, list rows, slots and tabs. Use them only where no pointer or keyboard is behind the state: gallery snapshots, or a highlight driven by data (`data-class-is-hover="slot.target"`).

## Tokens

`assets/nui/nui/theme/tokens.json` is the source of truth. `tools/nui_tokens.py` turns it into `nui/theme/tokens.rcss`: the `shared` values go into `body { ... }`, each theme's colors into `body.theme-dark { ... }` and `body.theme-light { ... }`, and the dark colors double as the default for a `<body>` without a theme class. Change a token by editing the JSON and running, from the repository root:

```
python tools/nui_tokens.py           # writes tokens.rcss and the table below, prints contrast ratios
python tools/nui_tokens.py --check   # writes nothing; exit 1 when an output is stale or a ratio fails
```

The script checks WCAG 2.x contrast for every pair a component draws: 4.5:1 for text (body text, muted text, labels on accent and status fills, tooltip text, status text) and 3:1 for the focus ring and filled controls. It fails when any pair is below its minimum. Borders are deliberately subtle (about 1.5 to 1.7:1) and are not checked; controls are recognizable by their fill.

What the color roles mean:

- `--surface` is the window background, `--surface-raised` panels and secondary buttons, `--surface-sunken` inputs, slots and tracks, `--surface-hover` hovered rows and buttons, `--selection` selected rows and selected text.
- `--text` is body text, `--text-muted` secondary text and placeholders. `--text-inverse` is text on `--tooltip-bg`, the inverse surface used by tooltips and slot counts (light in the dark theme, dark in the light theme).
- `--accent` fills primary buttons, the checked toggle, the slider fill and the tab indicator, and colors the selected tab label. `--accent-text` is text on `--accent`, `--accent-hover`, `--danger`, `--danger-hover`, `--success` and `--warning` fills.
- `--danger`, `--warning` and `--success` work both as text on surfaces and as fills.
- `--focus-ring` is the keyboard focus border. `--overlay-scrim` is the translucent modal backdrop.

<!-- tokens:begin (generated by tools/nui_tokens.py; do not edit by hand) -->

| Token | Dark | Light |
|---|---|---|
| `--surface` | `#1a1d23` | `#f3f4f6` |
| `--surface-raised` | `#232830` | `#ffffff` |
| `--surface-sunken` | `#121418` | `#e7e9ed` |
| `--surface-hover` | `#2c323c` | `#e3e6eb` |
| `--border` | `#3b424e` | `#c3c8d1` |
| `--text` | `#e7eaf0` | `#1a1d23` |
| `--text-muted` | `#a4acba` | `#525a67` |
| `--text-inverse` | `#16191e` | `#f3f4f6` |
| `--accent` | `#8ab4f8` | `#1a5fc4` |
| `--accent-hover` | `#a8c7fa` | `#154ea3` |
| `--accent-text` | `#0c1a30` | `#ffffff` |
| `--danger` | `#f28b82` | `#b3261e` |
| `--danger-hover` | `#f6aea9` | `#8c1d18` |
| `--warning` | `#f6c75a` | `#8a5300` |
| `--success` | `#7fd29a` | `#1e7a3c` |
| `--focus-ring` | `#f2f5f9` | `#111317` |
| `--selection` | `#2a3a55` | `#d6e4fb` |
| `--overlay-scrim` | `#000000a6` | `#0000007a` |
| `--tooltip-bg` | `#e7eaf0` | `#2a2f37` |

| Token | Value (both themes) |
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

<!-- tokens:end -->

Durations and easings are listed for reference: RCSS cannot read them through `var()` in transitions, so motion values are written out (see [Motion and reduced motion](#motion-and-reduced-motion)).

## Data binding cheatsheet

A document binds one data model by name; the controller owns it. Expressions use model keys, literals and a few operators.

| Attribute | Example | Effect |
|---|---|---|
| `data-model` | `<body data-model="inventory">` | Binds the element and its descendants to the model. The model must exist before the document loads, or RmlUi logs an error and nothing binds. |
| `{{ expr }}` | `{{ gold }} / {{ slot.count }}` | Text. The result is translated like other text, so `@ui.KEY` inside a model string also resolves. |
| `data-for` | `data-for="slot : slots"`, `data-for="slot, i : slots"` | Repeats the element per list entry. Without names the item is `it` and the index `it_index`. |
| `data-if` | `data-if="slot.count > 1"` | Removes the element from layout when false (`display: none`). |
| `data-visible` | `data-visible="loading"` | Hides with `visibility`, keeping the space. |
| `data-class-NAME` | `data-class-is-selected="row.id == selected"` | Adds class NAME while true. |
| `data-attr-NAME` | `data-attr-src="'../../../' + slot.icon"` | Sets attribute NAME to the result. |
| `data-attrif-NAME` | `data-attrif-disabled="!can_buy"` | Sets attribute NAME (empty value) while true, removes it while false. |
| `data-event-TYPE` | `data-event-click="use(slot.index)"` | Calls the controller handler `@nui.on("use")` with the evaluated arguments. `TYPE` is any RmlUi event: `click`, `dblclick`, `mousedown`, `change`, `keydown`, `dragstart`, ... |
| `data-alias-NAME` | `data-alias-item="slots[3]"` | A local name for an address, for templates. |

Expressions:

- Operators: `+ - * /`, `! && ||`, `== != < <= > >=`, `cond ? a : b`, parentheses. `+` joins strings when either side is a string.
- Strings use single quotes inside the double-quoted attribute: `data-if="mode == 'buy'"`.
- Addresses: `slot.icon`, `slots[3].icon`, `slots[i].count` inside a `data-for` with an index name.
- List size: `size(slots)`, as specified by `nova-client-src/src/NovaUI/Core/DynamicModel.h`.
- Formatting: `{{ price | format(2) }}` (two decimals), `format(value, 2, true)` drops trailing zeros, `| round`, `| to_upper`, `| to_lower`.
- Event parameters: `ev.NAME` reads a parameter of the current event, for example `ev.value` and `ev.checked` on `change`, `ev.button` on mouse events, `ev.tab_index` on the tabset's `tabchange`.
- Several actions in one event: `data-event-click="select(slot.index); open_menu()"`.

Keep bindings one-way: write model values from Python with `set()`. Setting `checked` or `value` through a binding also fires `change`, so a handler must accept the value the model already has. RmlUi can also write into a model from the document (`data-value`, `data-checked`, and assignments such as `data-event-click="tab = 2"`), but `DynamicModel.h` does not promise that, so do not rely on it.

## Python controller API

From `assets/root/nui.py` (its docstrings are the specification).

A window is one document plus an optional model and a controller class:

| Member | Meaning |
|---|---|
| `DOCUMENT` | Store path of the `.rml` (required). |
| `MODEL` | Name the document uses in `data-model`, or `None`. |
| `MODAL` | `True` to show the window as a modal document. |
| `initial_model()` | Returns every top-level model key with its first value. Each key's kind (scalar, list, map) is fixed from then on. |
| `@nui.on("name")` | Marks a method as the handler for `data-event-*="name(...)"`. It receives the evaluated arguments as plain Python values (`int`, `float`, `str`, `bool`, `list`, `dict`, `None`). |
| `__init__()` | Creates the model, loads the document hidden and binds the handlers. |
| `show()`, `hide()`, `is_visible()` | Visibility. |
| `set(**values)` | Replaces model keys; only views that use them update. A value of a different kind fails and logs. |
| `get(key)` | A copy of the current value, or `None`. |
| `element_on(element_id, event, fn)` | A plain DOM event on the element with that id; `fn` gets a dict with `type`, `target_id` and, for mouse events, `button`. Re-attached after reloads. |
| `on_reload()` | Hook: the document was re-loaded in place (hot reload, locale change). |
| `destroy()` | Closes the document and drops the model and every handler. |

Module functions: `nui.is_available()` (false without the `_nui` module or a runtime, for example in headless tests; every `Window` method is then a no-op), `nui.enabled_for_locale()` (false for right-to-left locales), `nui.set_theme("dark"|"light")`, `nui.get_theme()`, `nui.set_scale_percent(p)` (0 = automatic, else 75..200), `nui.get_scale_percent()`, `nui.get_scale()`, `nui.get_auto_scale()`, `nui.set_reduced_motion(on)`, `nui.is_reduced_motion()`, `nui.refresh_strings()`. The appearance setters apply at once and persist to `config/metin2.cfg` (`UI_THEME`, `UI_SCALE`, `UI_REDUCED_MOTION`).

Python never runs per frame. It runs when a handler fires or when game code calls a controller method that calls `set()`.

## Rules

`nuitool lint` enforces the ones marked with a code.

1. **Lengths in `dp`** (NUI002). `px` is allowed only as `1px`, for hairlines that stay one physical pixel at every scale. Unitless `0`, `%`, `em`, `vw` and `vh` are fine.
2. **Colors from tokens** (NUI003, NUI004). No `#hex`, `rgb()`, `rgba()`, `hsl()` or named colors outside `nui/theme/`; `transparent` is allowed. Every `var(--x)` must be a token.
3. **No inline styles** (NUI009): no `style="..."` and no `data-style-*`. Put rules in the window's `.rcss`.
4. **Strings from the locale files** (NUI005): every `@ui.KEY` and `@game.KEY` must exist.
5. **Every data event has a handler** (NUI006): `data-event-*="name(...)"` in `nui/windows/<name>/<name>.rml` needs `@nui.on("name")` in `assets/root/nui_<name>.py`.
6. **Every reference resolves** (NUI007): `<link>` targets, templates and image sources.
7. **Documents load cleanly** (NUI001 parse, NUI008 load): no RmlUi warnings or errors with the fixture.
8. **No per-frame Python.** No polling from `OnUpdate`; drive views with `set()` from game events.
9. **Overlays do not take the mouse.** A full-screen document that is not a modal dialog uses `body.nui-overlay` (`pointer-events: none`). The input arbiter only routes clicks to NovaUI while the pointer is over an element that accepts pointer events, so a full-screen body without it would swallow every world click.
10. **Only features the renderer draws** (see the next section).
11. **Motion only in `.component.nui-anim` rules**, with values written out (see [Motion and reduced motion](#motion-and-reduced-motion)).
12. **No fixed widths on text.** Give buttons, tabs and labels room (`min-width`, wrapping rows) instead of `width`; translations are longer than English.

## What the renderer draws

The Direct3D 9 renderer implements geometry, textures, scissor clipping, transforms and the stencil clip mask. It does not implement render layers, filters or shaders, the same as the CPU renderer used by `nuitool snap`. Checked in `Source/Core`, these RCSS features need what is missing and must not be used:

| Do not use | Why |
|---|---|
| `decorator: linear-gradient(...)`, `repeating-linear-gradient`, `radial-gradient`, `repeating-radial-gradient`, `conic-gradient`, `repeating-conic-gradient`, `shader(...)` | Compiled shaders (`RenderInterface::CompileShader`). |
| `decorator: gradient(...)`, `horizontal-gradient`, `vertical-gradient` | Drawn with vertex colors, but excluded to keep one rule: no gradients. |
| `box-shadow` | Rendered into a layer and saved as a texture. |
| `filter`, `backdrop-filter` (blur, drop-shadow, brightness, contrast, grayscale, hue-rotate, invert, opacity, saturate, sepia) | Render layers plus compiled filters. |
| `mask-image` | Render layers plus a mask image. |
| `image(...)` with fit `repeat`, `repeat-x` or `repeat-y` | Tiling needs wrap addressing; both renderers clamp, so the edge texels smear. Repeat by laying out several elements, or use a larger image. |

Safe to use: solid backgrounds, borders (all sides solid), `border-radius`, `opacity`, `transform` (translate, rotate, scale, skew, matrix, perspective), `overflow` clipping, `image`, `tiled-horizontal`, `tiled-vertical`, `tiled-box` (their tiles stretch) and `ninepatch` decorators, `<img>`, sprite sheets (`@spritesheet`), `image-color` tints and `font-effect` (outline, shadow, glow, blur; the font engine draws those into glyph textures on the CPU).

Clipping cost: overflow on an element with `border-radius`, or on a transformed element whose content overflows, uses the stencil clip mask; plain rectangular overflow uses the cheaper scissor. When the device has no stencil buffer, the renderer falls back to the scissor, and rounded corners are then not clipped.

## Motion and reduced motion

Stock motion: button, list, slot, input, toggle and tooltip state changes take 0.1s, the tab indicator slides in 0.2s, and the window fades in with a 4dp rise over 0.2s when its document loads. All of it uses `cubic-out`.

How to add motion, with reasons from RmlUi 6.3:

- Declare `transition` and `animation` only in a rule of the form `.your-class.nui-anim { ... }`, and put `nui-anim` on the element. Motion is then opt-in, and the reduced-motion rule in `base.rcss` (`.nui-anim.nui-anim.nui-anim`, three classes because RCSS has no `!important`) always outranks it.
- Write durations and easings out, matching the tokens (`--dur-fast` 0.1s, `--dur-med` 0.2s, `--dur-slow` 0.3s, `--ease-out` cubic-out). RmlUi ignores a `transition` that contains `var()`, without any warning: the property jumps to its end value. An `animation` with `var()` does run, but restarts every time the theme changes.
- Durations are seconds only: `0.12s`. RmlUi does not read `ms`: `120ms` is a syntax error, logged as a warning, and the whole declaration is dropped.
- Easing names are RmlUi tweens, `family-mode`: families `back`, `bounce`, `circular`, `cubic`, `elastic`, `exponential`, `linear`, `quadratic`, `quartic`, `quintic`, `sine`; modes `in`, `out`, `in-out`. CSS names such as `ease` and `ease-in-out` do not exist.
- `transition` lists property names, then the duration, an optional delay and the tween: `transition: background-color border-color 0.1s cubic-out;`. Shorthands such as `border-color` expand to their parts.
- Design keyframes so that the last frame equals the element's normal style. When reduced motion removes an animation, the element shows that style.
- The window-open animation plays when the document is loaded. Windows that are loaded once and shown later do not replay it on `show()` (see [Status and known gaps](#status-and-known-gaps)).

Reduced motion is the RmlUi media theme `reduced-motion`. `nui.set_reduced_motion(True)` (or `UI_REDUCED_MOTION 1` in `metin2.cfg`) activates it, and `base.rcss` then sets `transition: none; animation: none` on every `nui-anim` element. A window that follows the opt-in rule needs nothing else. To change other properties under reduced motion (for example to hide a decorative element), add a block to the window's sheet:

```css
@media (theme: reduced-motion)
{
	.shop-sparkles { display: none; }
}
```

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
- `font-family` takes one family name. Loaded faces: Noto Sans regular, bold and italic.
- Unitless `0` is accepted for lengths.
- Intrinsic image sizes are in `dp`: an `<img>` without a width, or a decorator image with fit `scale-none`, shows a 32 px icon at 32dp.

Markup:

- A text run made only of whitespace between two tags is dropped: `<b>A</b> <i>B</i>` renders "AB". Keep the space inside a text run: `<b>A</b> and <i>B</i>`, or use `&#160;`.
- Only `&lt; &gt; &amp; &quot;` are decoded as named entities; use numeric ones for anything else, such as `&#215;` for × and `&#160;` for a non-breaking space.
- `<button>` is a plain element: the `disabled` attribute does not stop clicks by itself. The button component adds `pointer-events: none` for `[disabled]`. `:disabled` exists only on `<input>`, `<select>` and `<textarea>`.
- `<input>` gets its type as a class (`input.text`, `input.checkbox`, `input.range`).
- `<handle move_target="#document">` drags the whole document; `#self`, `#parent` and plain ids also work.
- A template file must start with its `<template>` tag. Text before it that contains `/template`, even inside a comment, hides the tag from RmlUi's template reader and the template fails to load.
- A document needs its data model when it loads (see the cheatsheet), which is why every window with a model has a fixture.

## Localization

- `@ui.KEY` resolves from `locale_interface.txt` (the `uiScriptLocale` module) and `@game.KEY` from `locale_game.txt` (`localeInfo`), for the client's current locale.
- Translation applies to text content, to `{{ }}` output and to the document `<title>`. It does not apply to attribute values: `placeholder="@ui.KEY"` shows the raw key. Put translated attribute text in the model instead (`data-attr-placeholder="hint"`, with the controller setting `hint` from `uiScriptLocale`).
- A missing key stays visible as `@ui.KEY` and is logged once.
- Translated text is parsed as RML. Some shipped strings contain `<` or `&` (key hints such as `<CTRL> + Q`: 31 in `locale_interface.txt`, 4 in `locale_game.txt` across all locales), which render correctly only if the string tables are escaped when they are pushed. Check such a key in a snapshot before using it.
- Dynamic text (names, numbers, counts) comes from the model.
- After a locale change, `nui.refresh_strings()` pushes the tables again and re-loads open documents; controllers re-apply state in `on_reload()`.
- Noto Sans covers Latin, Greek and Cyrillic, which includes every non-right-to-left locale the client ships. It has no Arabic, Hebrew, CJK or Thai glyphs.
- Right-to-left text is not supported yet: RmlUi's FreeType engine does no shaping or bidirectional layout. For those locales `nui.enabled_for_locale()` is false and callers keep the legacy window.

## Scale and themes

- One `dp` is one pixel at scale 1.0. The runtime sets the ratio from the backbuffer height (1080 lines = 1.0, in steps of 0.125, between 0.75 and 2.0), or from the player's override (75 to 200 percent, `UI_SCALE`). Glyphs are rasterized at the scaled size, so text stays sharp.
- Test at 0.75, 1.0, 1.5 and 2.0. `nuitool snap --scale` takes a factor.
- Every document's `<body>` has exactly one of `theme-dark` and `theme-light`; the runtime sets it and swaps it on `nui.set_theme()`. Components never mention the theme; they read tokens, and the tokens change with the class.

## Tools

The Python tool runs from the asset repository root. `nuitool` is built from `nova-client-src` (target `nuitool`); the commands assume it is on `PATH`.

Tokens: `python tools/nui_tokens.py`, see [Tokens](#tokens).

Lint, from the asset repository root:

```
nuitool lint --root assets/nui --root assets/icon --locale assets/locale/locale/en
```

- `--root` is a folder that contains store paths; `assets/nui` holds `nui/...`. Repeat it for the groups that images come from (`assets/icon` for `icon/...`; the group that holds a `ymir work/` folder for `d:/ymir work/...`).
- `--locale` points at one locale folder. `--scripts` points at the controllers; the default tries `<root>/root`, then `<root>/../root`, which finds `assets/root`. `--no-load` skips the document loads.
- Findings print as `path:line: NUIxxx: message`, one per line. Exit code 0 means clean.

| Code | Finding |
|---|---|
| NUI001 | A document, template or style sheet does not parse. |
| NUI002 | A `px` length other than `1px`. |
| NUI003 | A raw color outside `nui/theme/`. |
| NUI004 | `var(--x)` that is not a token. |
| NUI005 | `@ui.KEY` or `@game.KEY` missing from the locale files. |
| NUI006 | A `data-event-*` without a matching `@nui.on` handler. |
| NUI007 | A link, template or image source that does not resolve. |
| NUI008 | RmlUi warnings or errors while loading the document with its fixture. |
| NUI009 | An inline style. |

Snapshots:

```
nuitool snap --root assets/nui --root assets/icon \
	--doc nui/windows/gallery/gallery.rml --fixture assets/nui/nui/windows/gallery/gallery.fixture.json \
	--theme dark --scale 1.5 --size 1920x1080 --out gallery-dark-150.png
```

- `--time` is how many seconds of animation run before the frame is taken (default 1, which lets the window-open fade finish). `--reduced-motion` renders the resting state.
- `--compare golden.png --tolerance N --diff diff.png` compares against a stored image and exits 1 on a mismatch.
- DDS and legacy `.sub` images do not decode in snapshots and stay blank; the client draws them. Prefer PNG or TGA for NovaUI art.
- The CPU renderer follows the same RmlUi render interface rules as the D3D9 renderer (premultiplied alpha, the same unsupported features), and integration cross-checks the two within a small tolerance.

`nuitool help` prints the current options.

## Hot reload and debugging

In non-distribution builds, while the asset store is in file-load mode (dev runs without an installed release, `--no-patch`), every asset lookup reads the file under the client's working directory, and a `HotReloader` watches the `nui/` folder there. One way to edit in place is to make `<client>/nui` a directory junction to `nova-client/assets/nui/nui`. Note that `nova-client-src/CMakeLists.txt` defines `_DISTRIBUTE` for RelWithDebInfo as well as Release, so today only Debug builds have hot reload and the two hotkeys below.

- Saving an `.rcss` re-applies style sheets to open documents.
- Saving an `.rml` or `.rtpl`, or adding or removing one of those, re-loads open documents in place. Element handlers from `element_on()` are re-attached, then `on_reload()` runs. Models are kept.
- Ctrl+Shift+D toggles the RmlUi debugger (element tree, computed styles, events).
- Ctrl+Shift+U toggles the render test page.

## Status and known gaps

- The runtime (`NuiRuntime`), the Direct3D 9 renderer, the host wiring and the `_nui` module are separate workstreams being integrated. Until then, only the tools and the content can be exercised.
- The window-open animation plays when a document loads, not on every `show()`. Replaying it needs the runtime to mark shown documents (for example a body class set on show and removed on hide); that is a pending decision.
- The gallery's theme button (`#gallery-theme`) and close button (`#gallery-close`) do nothing until a gallery controller binds them with `element_on()`. A draft is in `docs/ui/examples/nui_gallery.py`; integration moves it to `assets/root/nui_gallery.py`.
- Attribute values are not translated (see [Localization](#localization)).
- Right-to-left scripts and IME composition display are not supported yet.
- Hot reload, the debugger and the render test hotkey are compiled out of RelWithDebInfo builds (`_DISTRIBUTE`); a separate dev switch is an integration decision.
