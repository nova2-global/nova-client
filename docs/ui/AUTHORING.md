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
4. Write `settings.fixture.json` with every key of every data model the document binds. `nuitool lint` checks its JSON (NUI001) and loads the document with it; pass it to `nuitool snap` with `--fixture`.
5. Write the controller `assets/root/nui_settings.py`: subclass `nui.Window`, set `DOCUMENT` and `MODEL`, return every model key from `initial_model()`, and add one `@nui.on("name")` method for every `data-event-*="name(...)"` in the document.
6. Use `@ui.KEY` (from `locale_interface.txt`) or `@game.KEY` (from `locale_game.txt`) for every visible string. The key must exist in every locale.
7. If you touched `tokens.json`, run `python tools/nui_tokens.py` (it rewrites `tokens.rcss` and the token table below, and prints the contrast ratios). `python tools/nui_tokens.py --check` verifies without writing and exits 1 while an output is stale. Then run `nuitool lint` until it exits 0. Findings are the only thing on standard output; the `N findings in M files` summary and any note about a skipped check always go to standard error. Exit 2 (a missing root, a mistyped path) also leaves standard output empty, so go by the exit code.
8. Run `nuitool snap` in both themes at scale 1.0, 1.5 and 2.0, and once with `--reduced-motion`. `--size` is in pixels: give it the scale times the dp area the window needs, for a full-screen window 1920x1080 at 1.0, 2880x1620 at 1.5 and 3840x2160 at 2.0 (the client's own sizes at those scales). Snap does not scroll, so a scroll container shows only its first screen. Look at the images.
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
| `assets/nui/nui/windows/gallery/` | | every component in `nui/components/` in every state it styles |
| `assets/nui/nui/windows/render-test/` | | every renderer feature on one page |

The client itself loads the fonts, the gallery and the render test by the constants in `nova-client-src/src/NovaUI/Core/NuiPaths.h`.

Paths inside documents and style sheets:

- A relative path resolves against the file that contains it: `href` and `src` in an `.rml` against the document, `image(...)` in an `.rcss` against that style sheet. `..` segments are normalized.
- A path that starts with `/` is a store path from the store root and resolves the same from any file: `/nui/theme/tokens.rcss`, `/icon/item/27001.tga`. `_nui.LoadDocument` takes one too.
- Templates are the exception to the first rule. `href` in a template's `<head>` resolves against the template file, but the template's body is copied into each document that uses it, so a relative `<img src>` or inline-style image path there resolves against that document (RmlUi joins them with the owner document's path). Put images in a template's body through an image decorator in a linked `.rcss`, a sprite, a `/` store path or a `d:/` path; lint reports a relative one as NUI007.
- Name files in lowercase with hyphens. The store and `nuitool` look paths up without regard to case, so a reference in the wrong case still resolves; write the exact case anyway, because git and Linux file systems are case-sensitive. The three font files are the only mixed-case names (fixed by `NuiPaths.h`).
- Legacy assets outside `nui/` are reached from the store root: `/icon/item/27001.tga`, or by climbing to it (three levels from `nui/windows/<name>/`: `../../../icon/item/27001.tga`). Model values from Python are store paths (`item.GetIconImageFileName()` style), so root them in the binding: `data-attr-src="'/' + slot.icon"`; Python may also pass `/icon/...` values itself.
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

All class names start with `nui-`. Modifiers use `--`, parts use `__`, states use `is-*`. The gallery (`nui/windows/gallery/gallery.rml`) shows every component in every state it styles; the body-level layers (`nui-overlay`, `nui-scrim`) and the layout helpers other than `nui-row` are not on it. Copy markup from there.

| Component | Markup | Variants and states |
|---|---|---|
| Window frame | `<body class="nui-window nui-anim">` with `nui-window__titlebar`, `nui-window__handle` (a `<handle move_target="#document">`), `nui-window__title`, `nui-window__close`, `nui-window__body`, `nui-window__footer` | Fades in with a 4dp rise each time the window is shown. For a modal dialog, use `<body class="nui-scrim">` with a `div.nui-window` inside and point the handle at the div's id: `move_target="my-dialog"` (a plain id, no `#`). The scrim centers the div, and the component makes it `position: relative` so the drag can offset it; the dialog's sheet sets only its width and height, never `position`, `left` or `top`. |
| Button | `<button class="nui-button nui-button--primary nui-anim">` | `--primary`, `--secondary` (the default look), `--ghost`, `--danger`; sizes `--small`, `--icon`. `:hover`, `:active`, `:focus-visible`. The `disabled` attribute takes the button out of pointer hit testing, the tab order and Enter/Space (see [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)). |
| Panel | `<div class="nui-panel">` with an optional `nui-panel__title` | `--sunken`, `--flat`. `nui-divider` is a 1dp rule. |
| Tabs | native `<tabset class="nui-tabs nui-tabs--3">` with `<tab>` and `<panel>` pairs and a last `<tab class="nui-tabs__indicator nui-anim">` | `nui-tabs--2` to `--6` must match the number of real tabs. Tabs switch without Python; the selected tab and panel get `:selected`. Tabs are in the tab order: Tab moves between them, Enter or Space selects one, and `:focus-visible` rings the focused tab. |
| List | `<div class="nui-list">` with rows `<div class="nui-list__item nui-anim">`, parts `nui-list__label`, `nui-list__meta` | `is-selected`, `:hover`, `:focus-visible` (a ring on every edge; a selected row keeps its accent stripe). The `disabled` attribute takes a row out of hit testing, the tab order and Enter/Space. Give the list a height in the window sheet to scroll. |
| Slot grid | `<div class="nui-slot-grid">` with `<div class="nui-slot nui-anim">`, `<img class="nui-slot__icon">`, `<span class="nui-slot__count">` | 40dp cells for 32dp icons. `is-selected`, `is-disabled`, `:hover`. |
| Slider | `<input type="range" class="nui-slider" min max step value>` | `:hover` and `:active` on the thumb, `:focus-visible`; `disabled` attribute. RmlUi builds the track, fill and thumb; the component centers them in the 20dp input, so give `.nui-slider` no padding or border. |
| Toggle | `<label class="nui-toggle">` around `<input type="checkbox" class="nui-toggle__input">`, `nui-toggle__track`, `nui-toggle__knob`, `nui-toggle__label` | `checked` and `disabled` attributes. The label forwards clicks to the hidden checkbox. The checkbox stays in the tab order: Tab reaches the toggle, Space flips it, and `:focus-visible` rings the track. |
| Text input | `<input type="text" class="nui-input">` (also `type="password"`), inside `div.nui-field` with `label.nui-field__label` and `span.nui-field__error` | `--invalid`, `disabled` attribute, `:focus`, `:placeholder-shown`. |
| Tooltip | `<span class="nui-has-tooltip">` host with `<span class="nui-tooltip nui-anim">` inside | One line by default; `--wrap` wraps at 240dp. `is-open` shows it without hover. The host is laid out as `inline-block` (one box that does not wrap with the text around it), because RmlUi never places an absolute child against an inline box. Use a span or a component element as the host; a bare `div` or `p` becomes inline-block too. Item tooltips stay on the legacy `uitooltip` windows. |
| Badge | `<span class="nui-badge">` | `--accent`, `--danger`, `--warning`, `--success`. |
| Layout helpers | `nui-row` (flex row, `--wrap`, `--end`, `--between`), `nui-stack` (flex column, `--loose`), `nui-grow`, `nui-muted`, `nui-small` | Use these instead of inline styles. |
| Full-screen layers | `<body class="nui-overlay">` for HUD layers that never take the mouse; `nui-interactive` on children that should | `nui-center-max` caps content at 1600dp; `nui-safe-16x9` limits a HUD anchor area to 16:9 of the screen height on ultrawide screens. |

`is-hover`, `is-active` and `is-focus` force the look of `:hover`, `:active` and `:focus-visible` where a component styles that state: buttons and sliders take all three, inputs, list rows, tabs and toggles take `is-hover` and `is-focus`, and slots take `is-hover`. Use them only where no pointer or keyboard is behind the state: gallery snapshots, or a highlight driven by data (`data-class-is-hover="slot.target"`).

## Tokens

`assets/nui/nui/theme/tokens.json` is the source of truth. `tools/nui_tokens.py` turns it into `nui/theme/tokens.rcss`: the `shared` values go into `body { ... }`, each theme's colors into `body.theme-dark { ... }` and `body.theme-light { ... }`, and the dark colors double as the default for a `<body>` without a theme class. Change a token by editing the JSON and running, from the repository root:

```
python tools/nui_tokens.py           # writes tokens.rcss and the table below, prints contrast ratios
python tools/nui_tokens.py --check   # writes nothing; exit 1 when an output is stale or a ratio fails
```

The script checks WCAG 2.x contrast for every text color a component draws on each background it uses, at 4.5:1 (body text, muted text on panels, hovered and selected rows, labels on accent and status fills, tooltip text, status text), and for the focus ring and the accent fill of the slider and the checked toggle at 3:1. It fails when any pair is below its minimum; the pairs are listed in `CONTRAST_PAIRS` in `tools/nui_tokens.py`. `--border` is deliberately subtle (1.4 to 1.8:1 on the surfaces) and is not checked, both as a border and as the scrollbar thumb; controls are recognizable by their fill.

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
| `{{ expr }}` | `{{ gold }} / {{ slot.count }}` | Text only. The result is translated like other text, so `@ui.KEY` inside a model string also resolves. In an attribute the braces stay literal (`src="{{ icon }}"` loads a file of that name); bind attributes with `data-attr-NAME`. |
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

1. **Lengths in `dp`** (NUI002). `px` is allowed only for hairlines that stay one physical pixel at every scale (`1px`, `-1px`, `0px`), in `@spritesheet` rectangles (texture pixels) and under `nui/theme/`. Unitless `0`, `%`, `em`, `vw` and `vh` are fine.
2. **Colors from tokens** (NUI003, NUI004). No `#hex`, `rgb()`, `rgba()`, `hsl()` or named colors outside `nui/theme/`; `transparent` is allowed. Every `var(--x)` must be a token or a custom property declared in the same file.
3. **No inline styles** (NUI009): no `style="..."`, no `data-style-*` and no `data-attr-style`. Put rules in the window's `.rcss` and switch them with `data-class-*`.
4. **Strings from the locale files** (NUI005): every `@ui.KEY` and `@game.KEY` must exist, and none may sit in a `data-attr-*` or `data-value` binding, which is never translated (see [Localization](#localization)).
5. **Every data event has a handler** (NUI006): `data-event-*="name(...)"` in `nui/windows/<name>/<name>.rml` needs `@nui.on("name")` in `assets/root/nui_<name>.py`.
6. **Every reference resolves** (NUI007): `<link>` targets, templates, `<img>` sources and sprites, and image paths in style sheets.
7. **Documents load cleanly** (NUI001 parse, NUI008 load): no RmlUi warnings or errors with the fixture, and the fixture itself is valid JSON holding one object per model. For template files NUI001 also runs RmlUi's template reader (see [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)).
8. **No per-frame Python.** No polling from `OnUpdate`; drive views with `set()` from game events.
9. **Overlays do not take the mouse.** A full-screen document that is not a modal dialog uses `body.nui-overlay` (`pointer-events: none`). The input arbiter only routes clicks to NovaUI while the pointer is over an element that accepts pointer events, so a full-screen body without it would swallow every world click.
10. **Only features the renderer draws** (NUI010, see the next section).
11. **Motion only in `.component.nui-anim` rules**, with values written out, and on selectors lighter than the reduced-motion rule (NUI011, see [Motion and reduced motion](#motion-and-reduced-motion)).
12. **No fixed widths on text.** Give buttons, tabs and labels room (`min-width`, wrapping rows) instead of `width`; translations are longer than English.

## What the renderer draws

The Direct3D 9 renderer implements geometry, textures, scissor clipping, transforms and the stencil clip mask. It does not implement render layers, filters or shaders, the same as the CPU renderer used by `nuitool snap`. Checked in `Source/Core`, these RCSS features need what is missing and must not be used; `nuitool lint` reports each as NUI010:

| Do not use | Why |
|---|---|
| `decorator: linear-gradient(...)`, `repeating-linear-gradient`, `radial-gradient`, `repeating-radial-gradient`, `conic-gradient`, `repeating-conic-gradient`, `shader(...)` | Compiled shaders (`RenderInterface::CompileShader`). |
| `decorator: gradient(...)`, `horizontal-gradient`, `vertical-gradient` | Drawn with vertex colors, but excluded to keep one rule: no gradients. |
| `box-shadow` | Rendered into a layer and saved as a texture. |
| `filter`, `backdrop-filter` (blur, drop-shadow, brightness, contrast, grayscale, hue-rotate, invert, opacity, saturate, sepia) | Render layers plus compiled filters. |
| `mask-image` | Render layers plus a mask image. |
| `image(...)` with fit `repeat`, `repeat-x` or `repeat-y` | Tiling needs wrap addressing. The CPU renderer behind `nuitool snap` clamps, so its snapshots smear the edge texels, while the Direct3D 9 renderer wraps such geometry; the two would not match. Repeat by laying out several elements, or use a larger image. |

Safe to use: solid backgrounds, borders (all sides solid), `border-radius`, `opacity`, `transform` (translate, rotate, scale, skew, matrix, perspective), `overflow` clipping, `image`, `tiled-horizontal`, `tiled-vertical`, `tiled-box` (their tiles stretch) and `ninepatch` decorators, `<img>`, sprite sheets (`@spritesheet`), `image-color` tints and `font-effect` (outline, shadow, glow, blur; the font engine draws those into glyph textures on the CPU).

Clipping cost: an overflow element with `border-radius` always uses the stencil clip mask. An overflow element that has a transform, or sits inside a transformed element (RmlUi applies ancestor transforms to descendants), uses the mask when its content overflows, and never the scissor, because its box can be projected anywhere. Other rectangular overflow uses the cheaper scissor. The client creates a D24S8 depth-stencil surface, so the mask is available. If the bound depth-stencil surface had no stencil bits, the Direct3D 9 renderer would skip the mask and log a warning once: rounded overflow would then clip to a rectangle, and the overflow of a transformed element would not be clipped by that element at all.

## Motion and reduced motion

Stock motion: button, list, slot, input, toggle and tooltip state changes take 0.1s, the tab indicator slides in 0.2s, and the window fades in with a 4dp rise over 0.2s each time it is shown. All of it uses `cubic-out`.

How to add motion, with reasons from RmlUi 6.3. `nuitool lint` reports a break of the first four points as NUI011:

- Declare `transition` and `animation` only in a rule of the form `.your-class.nui-anim { ... }`, and put `nui-anim` on the element. Motion is then opt-in, and the reduced-motion rule in `base.rcss` can stop it. That rule is `.nui-anim.nui-anim.nui-anim.nui-anim` (four classes, weight 400,000, because RCSS has no `!important`), and every component and window sheet is linked after `base.rcss`, so a motion rule of equal or greater weight wins the tie and keeps moving. A motion rule's whole selector, ancestors and `:not()` included, may therefore hold `nui-anim`, at most two other classes, attributes or pseudo-classes, and tags, but no id: `.shop-row.nui-anim`, `.shop .shop-row.nui-anim` and `li.shop-row.is-open.nui-anim` work; `.shop .shop-row.is-open.nui-anim` and `#buy.nui-anim` do not. Lint measures each motion selector against the rule in `base.rcss` and reports one that ties or outranks it. Declare `transition` on the resting rule, not on `:hover`, `:active` or another state rule: the pseudo-class adds weight, and the transition should run in both directions anyway.
- Write durations and easings out, matching the tokens (`--dur-fast` 0.1s, `--dur-med` 0.2s, `--dur-slow` 0.3s, `--ease-out` cubic-out). RmlUi ignores a `transition` that contains `var()`, without any warning: the property jumps to its end value. An `animation` with `var()` does run, but restarts every time the theme changes.
- Durations are seconds only: `0.12s`. RmlUi does not read `ms`: `120ms` is a syntax error, logged as a warning, and the whole declaration is dropped.
- Easing names are RmlUi tweens, `family-mode`: families `back`, `bounce`, `circular`, `cubic`, `elastic`, `exponential`, `linear`, `quadratic`, `quartic`, `quintic`, `sine`; modes `in`, `out`, `in-out`. CSS names such as `ease` and `ease-in-out` do not exist.
- `transition` lists property names, then the duration, an optional delay and the tween: `transition: background-color border-color 0.1s cubic-out;`. Shorthands such as `border-color` expand to their parts.
- Design keyframes so that the last frame equals the element's normal style. When reduced motion removes an animation, the element shows that style.
- The window-open animation plays each time the window is shown. The runtime puts the class `nui-shown` on the `<body>` in `show()` and takes it off in `hide()`, and `window-frame.rcss` keys the animation on it: `.nui-window.nui-shown.nui-anim`, plus `.nui-shown .nui-window.nui-anim` for the dialog div inside a scrim. A re-load (hot reload, locale change) keeps the class, so a visible window plays the animation again. Key a window's own opening motion on `nui-shown` the same way.

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
- `<input>` gets its type as a class (`input.text`, `input.checkbox`, `input.range`).
- `<handle move_target="#document">` drags the whole document; `#self`, `#parent` and plain ids also work. The handle moves its target by writing `left` and `top`, so a target other than `#document` must be `position: relative` or `absolute`; a static element ignores them. `#document` always works, because the document places itself from `left` and `top`.
- RmlUi does not parse a template file as XML: it searches the text for `<head>`, `</head>`, `<body>`, `</body>` and `<template`. Once that search has passed a `/` in front of the word it looks for, it no longer matches an opening tag, so text such as `/template` before the `<template>` tag, `/head` before `<head>` or `/body` between `</head>` and `<body>` (even inside a comment) makes the template fail to load. Start the file with its `<template name="...">` tag; lint reports this as NUI001.
- A document needs its data model when it loads (see the cheatsheet), which is why every window with a model has a fixture.

## Localization

- `@ui.KEY` resolves from `locale_interface.txt` (the `uiScriptLocale` module) and `@game.KEY` from `locale_game.txt` (`localeInfo`), for the client's current locale.
- What is translated:
  - Text content, `{{ }}` output and the document `<title>` (RmlUi's text path).
  - Attribute values written in markup, such as `placeholder="@ui.KEY"` or `title="@ui.KEY"`: the runtime translates every attribute except `id`, `class`, `style` and `data-*` when the element is created, in documents, templates and `data-for` items alike. The `<body>` attributes are translated once the document has loaded.
  - Not values set later: see the next point.
- Values set after the element exists are not translated: a `data-attr-*` or `data-value` binding, or an attribute set from code, shows `@ui.KEY` as written, and lint reports a key there as NUI005. Bind such an attribute to a model string that the controller fills from `uiScriptLocale` (`data-attr-placeholder="hint"`).
- A missing key stays visible as `@ui.KEY` and is logged once, in text and in attributes alike.
- String tables are plain text. Some shipped strings contain `<` or `&` (key hints such as `<CTRL> + Q`: 31 in `locale_interface.txt`, 4 in `locale_game.txt` across all locales). RmlUi parses translated text again as RML, so the runtime escapes `&`, `<` and `>` in each entry there, and puts entries into attributes as they are: `<CTRL> + Q` shows as written in both. Two places show such an entry with its entities (`&lt;CTRL&gt;`): `<textarea>` content and `{{ }}` output of a model string that holds a key. Keep those keys out of them, or put the translated text into the model from Python.
- Dynamic text (names, numbers, counts) comes from the model.
- After a locale change, `nui.refresh_strings()` pushes the tables again and re-loads open documents; controllers re-apply state in `on_reload()`.
- Noto Sans covers Latin, Greek and Cyrillic, which includes every non-right-to-left locale the client ships. It has no Arabic, Hebrew, CJK or Thai glyphs.
- Right-to-left text is not supported yet: RmlUi's FreeType engine does no shaping or bidirectional layout. For those locales `nui.enabled_for_locale()` is false and callers keep the legacy window.

## Scale and themes

- One `dp` is one pixel at scale 1.0. The runtime sets the ratio from the backbuffer height (1080 lines = 1.0, in steps of 0.125, between 0.75 and 2.0), or from the player's override (75 to 200 percent, `UI_SCALE`). Glyphs are rasterized at the scaled size, so text stays sharp.
- Test at 0.75, 1.0, 1.5 and 2.0. `nuitool snap --scale` takes a factor.
- Every document's `<body>` has exactly one of `theme-dark` and `theme-light`; the runtime sets it and swaps it on `nui.set_theme()`. Components never mention the theme; they read tokens, and the tokens change with the class.

## Tools

The Python tool runs from the asset repository root. `nuitool` is built from `nova-client-src` (target `nuitool`; an MSVC build writes `build/bin/<config>/nuitool.exe`); the commands assume it is on `PATH`.

Tokens: `python tools/nui_tokens.py`, see [Tokens](#tokens).

Lint, from the asset repository root:

```
nuitool lint --root assets/nui --root assets/icon --locale assets/locale/locale/en
```

- `--root` is a folder that contains store paths. The first one holds the documents: `assets/nui` holds `nui/...`. Repeat it for the groups that images come from: `assets/icon` for `icon/...`, and a group with a `ymir work/` folder, such as `assets/ETC`, for `d:/ymir work/...`.
- `--locale` points at one locale folder with `locale_interface.txt` and `locale_game.txt`. Without it, NUI005 is skipped. Run lint once per shipped locale when you add keys.
- `--scripts` points at the controllers. The default tries `<root>/root`, then `<root>/../root`, which finds `assets/root`.
- Lint loads every document through the runtime, with its fixture, for NUI008. When the runtime cannot start (for example a font that fails to load), that is itself an NUI008 finding and the exit code is 1. `--no-load` skips the loads and runs the static checks only; fixture syntax (NUI001) is checked either way.
- Paths after the options limit the run to those files or folders, relative to the first root: `nuitool lint --root assets/nui --root assets/icon nui/windows/settings`.
- Findings go to standard output as `path:line: NUIxxx: message`, one per line. Notes about skipped checks and the summary line go to standard error. The exit code is 0 when clean, 1 with findings and 2 for a usage error.

| Code | Finding |
|---|---|
| NUI001 | A document, template or style sheet does not parse, RmlUi's template reader cannot find the parts of a template file, or a `.fixture.json` is not valid JSON holding one object per model (reported on the fixture, at the JSON line). |
| NUI002 | A `px` length other than a hairline (`1px`, `-1px`, `0px`), outside `nui/theme/` and sprite rectangles. |
| NUI003 | A raw color outside `nui/theme/`. |
| NUI004 | `var(--x)` that is neither a token nor declared in the same file. |
| NUI005 | `@ui.KEY` or `@game.KEY` missing from the locale files, or any such key in a `data-attr-*` or `data-value` binding, which is never translated. |
| NUI006 | A `data-event-*` without a matching `@nui.on` handler. |
| NUI007 | A link, template, image or sprite that does not resolve (a `/` path resolves from the store root), a path that holds `{{ }}`, and a relative image path in a template's body. |
| NUI008 | RmlUi warnings or errors while loading the document with its fixture, one finding per report; or the runtime did not start while loading was on. |
| NUI009 | An inline style: `style="..."`, `data-style-*` or `data-attr-style`. |
| NUI010 | A feature the renderers do not draw (see [What the renderer draws](#what-the-renderer-draws)). |
| NUI011 | Motion that RmlUi drops or that reduced motion cannot stop, including a motion selector that ties or outranks the reduced-motion rule (see [Motion and reduced motion](#motion-and-reduced-motion)). |

Snapshots:

```
nuitool snap --root assets/nui --root assets/icon \
	--doc nui/windows/gallery/gallery.rml --fixture assets/nui/nui/windows/gallery/gallery.fixture.json \
	--theme dark --scale 1.5 --size 2880x1620 --out gallery-dark-150.png
```

- `--doc` is a store path, or a file path under the first root.
- `--fixture` is not picked up automatically; pass the window's `<name>.fixture.json`.
- `--size WxH` is the backbuffer in pixels (default 1280x720). `--scale` is 0.75 to 2, or `auto` for the client's height-based scale (default 1). `--theme` is `dark` (the default) or `light`.
- Snap does not scroll and does not move the window, so the frame has to hold the window: `--size` at least the scale times the window's right and bottom edges in dp. A scroll container shows only its first screen. The gallery is sized for a 1920x1080 dp area: `--size 1920x1080 --scale 1`, `--size 2880x1620 --scale 1.5` and `--size 3840x2160 --scale 2` show all of it. The 1280x720 default is a smaller dp area than the client uses at any automatic scale. Snap notes on standard error when the window reaches past the frame, or when a scroll container (`overflow: auto` or `scroll`) holds more than it shows; neither changes the exit code.
- `--time` is how many seconds of animation run before the frame is taken (default 1, which lets the window-open fade finish). `--reduced-motion` renders the resting state.
- `--compare golden.png [--tolerance N] [--diff diff.png]` compares with a stored image, channel by channel (N is 0 to 255, default 0), and exits 1 on a mismatch. The diff image goes to `--diff`, by default the output name with `.png` replaced by `.diff.png`. A snapshot matches the golden it was saved as at tolerance 0, as long as the golden was written by `nuitool snap` with the same `--size`, `--scale`, `--theme` and `--time`. `--compare` may not name the `--out` or the diff file, since snap writes those.
- RmlUi warnings and errors during a snapshot print as `rmlui: ...` on standard error and do not change the exit code; lint reports them as NUI008.
- DDS and legacy `.sub` images are not decoded in snapshots. The image area stays transparent at the file's own size, so the layout matches the client, which draws them, and snap prints a warning naming each file (`rmlui: SoftRenderInterface: ... is not decoded`). Prefer PNG or TGA for NovaUI art.
- The CPU renderer follows the same RmlUi render interface rules as the D3D9 renderer (premultiplied alpha, the same unsupported features). The two differ at the alpha edges of scaled file images: the CPU renderer filters premultiplied texels, like RmlUi's GL3 backend, while the D3D9 renderer premultiplies after filtering, which darkens the edges of black-matte icons by up to about 50 of 255 (measured on the render test's icon with the CPU renderer set to the D3D9 order). With the Direct3D 9 renderer as it is now (`nui-p1-render` f239f91), scaled legacy icons show that dark fringe in the client at UI scales other than 100%; integration decides whether that changes. Solid colors, borders, text and 1:1 images should agree within a small tolerance, which the integration cross-check verifies.

`nuitool help` prints the current options.

## Hot reload and debugging

In non-distribution builds, while the asset store is in file-load mode (dev runs without an installed release, `--no-patch`), every asset lookup reads the file under the client's working directory, and a `HotReloader` watches the `nui/` folder there. One way to edit in place is to make `<client>/nui` a directory junction to `nova-client/assets/nui/nui`. Note that `nova-client-src/CMakeLists.txt` defines `_DISTRIBUTE` for RelWithDebInfo as well as Release, so today only Debug builds have hot reload and the two hotkeys below.

- Saving an `.rcss` re-applies style sheets to open documents.
- Saving an `.rml` or `.rtpl`, or adding or removing any `.rml`, `.rtpl` or `.rcss` file, re-loads open documents in place. Element handlers from `element_on()` are re-attached, then `on_reload()` runs. Models are kept. A removal counts one poll (0.5 s by default) late, so an editor that saves by replacing the file causes one reload of the kind of file it saved, not two.
- Ctrl+Shift+D toggles the RmlUi debugger (element tree, computed styles, events).
- Ctrl+Shift+U toggles the render test page.

## Status and known gaps

- The runtime (`NuiRuntime`), the Direct3D 9 renderer, the host wiring and the `_nui` module are separate workstreams being integrated. Until then, only the tools and the content can be exercised.
- The gallery's theme button (`#gallery-theme`) and close button (`#gallery-close`) do nothing until a gallery controller binds them with `element_on()`. A draft is in `docs/ui/examples/nui_gallery.py`; integration moves it to `assets/root/nui_gallery.py`.
- Attribute values set after the element exists (`data-attr-*`, `data-value`, code) are not translated (see [Localization](#localization)).
- Right-to-left scripts and IME composition display are not supported yet.
- Hot reload, the debugger and the render test hotkey are compiled out of RelWithDebInfo builds (`_DISTRIBUTE`); a separate dev switch is an integration decision.
