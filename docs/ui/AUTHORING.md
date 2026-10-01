# NovaUI authoring guide

NovaUI is the RmlUi 6.3 layer that new client windows are written in: RML markup, RCSS style sheets, data bindings, and a Python controller that runs only on events. The legacy `wndMgr` UI keeps running next to it, and windows move over one at a time.

This guide is for people and AI agents writing windows. It is a reference: every rule below is either enforced by `nuitool lint` or explained by an RmlUi 6.3 behavior that was checked in the vendored source (`nova-client-src/vendor/RmlUi-6.3`). Where the RmlUi documentation and this guide disagree, this guide describes what the vendored version does.

Status: the runtime, the Direct3D 9 renderer, the CPU renderer behind `nuitool snap`, the client host, the `_nui` Python module and this content are integrated and covered by unit and integration tests. They have not been checked in the running client yet. [Status and known gaps](#status-and-known-gaps) lists what is missing.

## Contents

- [New window checklist](#new-window-checklist)
- [File layout and store paths](#file-layout-and-store-paths)
- [A complete window](#a-complete-window)
- [Components](#components)
- [Tokens](#tokens)
- [Data binding cheatsheet](#data-binding-cheatsheet)
- [Python controller API](#python-controller-api)
- [Keyboard and modals](#keyboard-and-modals)
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

1. Pick a name of lowercase letters, digits and hyphens that starts with a letter, for example `settings` or `item-shop`. Create `assets/nui/nui/windows/settings/`.
2. Write `settings.rml` from the skeleton in [A complete window](#a-complete-window): link `../../nui.rtpl`, put `template="nui"` and `class="nui-window nui-anim"` on `<body>`. A dialog that must take the keyboard is a modal instead: `<body class="nui-scrim">` with a `div.nui-window` inside, and `MODAL = True` in step 5 (see [Keyboard and modals](#keyboard-and-modals)).
3. Write `settings.rcss` for the window's size and position and anything the components do not cover. Use tokens for every color and `dp` for every length.
4. Write `settings.fixture.json` with every key of every data model the document binds. `nuitool lint` checks its JSON (NUI001) and loads the document with it; pass it to `nuitool snap` with `--fixture`.
5. Write the controller `assets/root/nui_settings.py`: subclass `nui.Window`, set `DOCUMENT` and `MODEL` (and `MODAL = True` for a dialog), return every model key from `initial_model()`, and add one `@nui.on("name")` method for every `data-event-*="name(...)"` in the document. The controller's name writes each hyphen of the window name as an underscore: window `item-shop` has `assets/root/nui_item_shop.py`, imported as `nui_item_shop`. Model keys and event names follow RmlUi's name rule (see [Data binding cheatsheet](#data-binding-cheatsheet)).
6. Use `@ui.KEY` (from `locale_interface.txt`) or `@game.KEY` (from `locale_game.txt`) for every visible string. The key must exist in every locale, and a `@game.KEY` must be a plain string, not one of the typed entries localeInfo makes functions of (see [Localization](#localization), which also says how to add a key).
7. If you touched `tokens.json`, run `python tools/nui_tokens.py` (it rewrites `tokens.rcss` and the token table below, and prints the contrast ratios). `python tools/nui_tokens.py --check` verifies without writing and exits 1 while an output is stale. Then run `nuitool lint` until it exits 0. Findings are the only thing on standard output; the `N findings in M files` summary and any note about a skipped check always go to standard error. Exit 2 (a missing root, a mistyped path) also leaves standard output empty, so go by the exit code.
8. Run `nuitool snap` with `--locale assets/locale/locale/en` in both themes at scale 1.0, 1.5 and 2.0, and once with `--reduced-motion`. `--size` is in pixels: give it the scale times the dp area the window needs, for a full-screen window 1920x1080 at 1.0, 2880x1620 at 1.5 and 3840x2160 at 2.0 (the client's own sizes at those scales). Snap does not scroll, so a scroll container shows only its first screen. Look at the images.
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
| `assets/nui/nui/components/*.rcss` | `nui/components/*.rcss` | one style sheet per component |
| `assets/nui/nui/fonts/NotoSans-{Regular,Bold,Italic}.ttf` | `nui/fonts/...` | Noto Sans 2.015 (OFL, see `OFL.txt` next to them) |
| `assets/nui/nui/windows/<name>/<name>.rml` | `nui/windows/<name>/<name>.rml` | the window document |
| `assets/nui/nui/windows/<name>/<name>.rcss` | same folder | the window's own rules |
| `assets/nui/nui/windows/<name>/<name>.fixture.json` | same folder | sample model data for lint and snapshots |
| `assets/root/nui_<module>.py` | `nui_<module>.py` | the controller, imported as `nui_<module>`: the window name with each hyphen as an underscore (`item-shop`: `nui_item_shop`) |
| `assets/nui/nui/windows/gallery/` | | every component in `nui/components/` in every state it styles |
| `assets/nui/nui/windows/render-test/` | | every renderer feature on one page |

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
| Button | `<button class="nui-button nui-button--primary nui-anim">` | `--primary`, `--secondary` (the default look), `--ghost`, `--danger`; sizes `--small`, `--icon`. `:hover`, `:active`, `:focus-visible`. Enter and Space press a focused button where NovaUI has the keyboard ([Keyboard and modals](#keyboard-and-modals)). The `disabled` attribute takes the button out of pointer hit testing, the tab order and Enter/Space (see [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)). |
| Panel | `<div class="nui-panel">` with an optional `nui-panel__title` | `--sunken`, `--flat`. `nui-divider` is a 1dp rule. |
| Tabs | native `<tabset class="nui-tabs nui-tabs--3">` with `<tab>` and `<panel>` pairs and a last `<tab class="nui-tabs__indicator nui-anim">` | `nui-tabs--2` to `--6` must match the number of real tabs. Tabs switch without Python; the selected tab and panel get `:selected`. Tabs are in the tab order: where NovaUI has the keyboard, Tab moves between them, Enter or Space selects one, and `:focus-visible` rings the focused tab. |
| List | `<div class="nui-list">` around a `<div class="nui-list__viewport">` that holds the rows `<div class="nui-list__item nui-anim">`, parts `nui-list__label`, `nui-list__meta` | `is-selected`, `:hover`, `:focus-visible` (a ring on every edge; a selected row keeps its accent stripe). Enter or Space selects the focused row where NovaUI has the keyboard. The `disabled` attribute takes a row out of hit testing, the tab order and Enter/Space. Give the viewport a height in the window sheet to scroll (`.my-list .nui-list__viewport { height: 200dp; }`): the rounded frame does not clip, the square viewport does, so the list clips with the scissor alone (see [What the renderer draws](#what-the-renderer-draws)). |
| Slot grid | `<div class="nui-slot-grid">` with `<div class="nui-slot nui-anim">`, `<img class="nui-slot__icon">`, `<span class="nui-slot__count">` | 40dp cells for 32dp icons. `is-selected`, `is-disabled`, `:hover`. |
| Slider | `<input type="range" class="nui-slider" min max step value>` | `:hover` and `:active` on the thumb, `:focus-visible`; `disabled` attribute. The arrow keys move a focused slider where NovaUI has the keyboard. RmlUi builds the track, fill and thumb; the component centers them in the 20dp input, so give `.nui-slider` no padding or border. |
| Toggle | `<label class="nui-toggle">` around `<input type="checkbox" class="nui-toggle__input">`, `nui-toggle__track`, `nui-toggle__knob`, `nui-toggle__label` | `checked` and `disabled` attributes. The label forwards clicks to the hidden checkbox. The checkbox stays in the tab order: where NovaUI has the keyboard, Tab reaches the toggle, Space flips it, and `:focus-visible` rings the track. |
| Text input | `<input type="text" class="nui-input">` (also `type="password"`), inside `div.nui-field` with `label.nui-field__label` and `span.nui-field__error` | `--invalid`, `disabled` attribute, `:focus`, `:placeholder-shown`. The corners are square on purpose: RmlUi makes every text input clip, and square clipping needs no stencil mask. `nui-escape-keeps-focus` on `<body>`: Escape in a field of this document does not leave the field (the login board). |
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

Names: a top-level model key and a data-event name are letters, digits and `_`, start with a letter, and are none of `it`, `it_index`, `ev`, `true`, `false`, `size` and `literal`, in any case (RmlUi's rule; `nova-client-src/src/NovaUI/Core/DataNames.h`). Members of nested lists and maps may have any name. RmlUi refuses a whole model for one other key: the window stays unavailable, every method does nothing, and `syserr.txt` names the key; lint reports it on the fixture (NUI001). `@nui.on()` raises `ValueError` for another event name.

| Attribute | Example | Effect |
|---|---|---|
| `data-model` | `<body data-model="inventory">` | Binds the element and its descendants to the model. The model must exist before the document loads, or RmlUi logs an error and nothing binds. |
| `{{ expr }}` | `{{ gold }} / {{ slot.count }}` | Text only. The result is translated like other text, so `@ui.KEY` inside a model string also resolves. So never bind text another player wrote (chat, whispers, names, shop signs, guild notices, mail) through `{{ }}` as it is: `x@game.SOME_KEY` would show that locale string. In an attribute the braces stay literal (`src="{{ icon }}"` loads a file of that name); bind attributes with `data-attr-NAME`. |
| `data-for` | `data-for="slot : slots"`, `data-for="slot, i : slots"` | Repeats the element per list entry. Without names the item is `it` and the index `it_index`. |
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

## Python controller API

From `assets/root/nui.py` (its docstrings are the specification).

A window is one document plus an optional model and a controller class:

| Member | Meaning |
|---|---|
| `DOCUMENT` | Store path of the `.rml` (required). |
| `MODEL` | Name the document uses in `data-model`, or `None`. |
| `MODAL` | `True` to show the window as a modal document: it takes every key and every click that the legacy lock window and the legacy top layer leave, also beside the window. Pair it with `body.nui-scrim` (see [Keyboard and modals](#keyboard-and-modals)). |
| `initial_model()` | Returns every top-level model key with its first value. Each key's kind (scalar, list, map) is fixed from then on. Keys follow the name rule in the [Data binding cheatsheet](#data-binding-cheatsheet); one other key leaves the window unavailable. |
| `@nui.on("name")` | Marks a method as the handler for `data-event-*="name(...)"`. It receives the evaluated arguments as Python scalars: `int`, `float`, `str`, `bool` or `None`. A whole number arrives as an `int`, literals and arithmetic included (`use(3)` and `use(slot.index + 1)` pass an `int`); other numbers arrive as `float`. A list or map argument arrives as its length or member count, with no warning, so pass its members: `use(slot.index)`, not `use(slot)`. Event parameters that are not scalars (`ev.drag_element`) arrive as `None`. The name follows the name rule in the [Data binding cheatsheet](#data-binding-cheatsheet); another one raises `ValueError`. A data-event handler cannot stop an event. |
| `__init__()` | Creates the model, binds the handlers, then loads the document hidden. Events the document raises while it loads (`data-event-load` on `<body>`, `change` from bindings such as `data-attrif-checked`) reach the handlers before `__init__` returns; until then `show()`, `hide()`, `is_visible()` and `element_on()` do nothing, while `set()` and `get()` work. |
| `show()`, `hide()`, `is_visible()` | Visibility. |
| `focus(element_id)` | Gives the element with that id the keyboard focus (a text field gets the caret); `False` while the window or the element is hidden. `hide()` takes the focus off the window's fields and a later `show()` does not put it back, so focus the field again after `show()`. Works inside handlers. |
| `set(**values)` | Replaces model keys; only views that use them update. An unknown key or a value of a different kind is refused and logged; a value that is not an `int`, `float`, `str`, `bool`, `None`, `list`, `tuple` or `dict` with `str` keys raises `TypeError`. Inside a handler the values wait until the event is over (`get()` sees them at once), so a list the clicked element lives in is not rebuilt under it. |
| `get(key)` | A copy of the current value, or `None`. |
| `element_on(element_id, event, fn)` | A plain DOM event on the element with that id; `fn` gets a dict with `type`, `target_id` and, for mouse events, `button`, plus the event's other parameters (`key_identifier` for key events). Re-attached after reloads. For `"keydown"`, `fn` returning exactly `True` keeps the key (see [Keyboard and modals](#keyboard-and-modals)); any other value lets it go on, and nothing else stops an event. |
| `on_reload()` | Hook: the document was re-loaded in place (hot reload, locale change). By then the `element_on()` handlers are attached again and the new document's own events (its load, `change` from bindings) have reached the `@nui.on` handlers. The replaced document's events (its unload, a `mouseout` as it leaves) reach no handler. |
| `destroy()` | Closes the document and drops the model and every handler. Inside one of the window's own handlers (a close button) the document hides at once, and it goes with the model by the end of the frame. From `destroy()` on, the document's own events (a `mouseout` as it hides, its unload) reach none of the window's handlers, so a window made again in its own handler (a reset button, a wizard step) keeps the model; a close by C++ or RmlUi still delivers the unload. |

Module functions: `nui.is_available()` (false without the `_nui` module or an active runtime, for example when NovaUI failed to start or a test started no runtime; every `Window` method is then a no-op. A headless runtime, under `NOVA_UI_HEADLESS` or a test's null renderer, is available), `nui.enabled_for_locale()` (false for right-to-left locales), `nui.set_theme("dark"|"light")`, `nui.get_theme()`, `nui.set_scale_percent(p)` (0 = automatic, else 75..200), `nui.get_scale_percent()`, `nui.get_scale()`, `nui.get_auto_scale()`, `nui.set_reduced_motion(on)`, `nui.is_reduced_motion()`, `nui.refresh_strings()`. The appearance setters apply at once and persist to `config/metin2.cfg` (`UI_THEME`, `UI_SCALE`, `UI_REDUCED_MOTION`). The constants `nui.KEY_ESCAPE`, `nui.KEY_RETURN`, `nui.KEY_NUMPADENTER`, `nui.KEY_TAB` and `nui.KEY_SPACE` are the `key_identifier` values of those keys (RmlUi's own numbers).

A window lives until `destroy()`: the runtime holds its handlers, so dropping the last reference does not close it. Only one window per `MODEL` name can exist at a time.

Python never runs per frame. It runs when a handler fires or when game code calls a controller method that calls `set()`.

## Keyboard and modals

The legacy UI and the game keep the keyboard unless NovaUI has a reason to take it (`nova-client-src/src/NovaUI/Core/InputArbiter.h`, `src/UserInterface/NuiHost.h`):

- NovaUI has the keyboard while one of its text fields has the focus (any input but checkbox, radio, range, submit and button; textarea; select), while a NovaUI modal (`MODAL = True`) is shown, and while the focus sits on a control the player moved it to with Tab or an arrow key that reached NovaUI (Tab out of a field, or inside a modal). Every other key goes to the legacy UI and the game hotkeys: Space attacks, Enter opens the chat.
- So in a window that is not modal, the keyboard works its buttons, tabs, toggles, sliders and list rows only after a Tab out of one of its text fields: then Enter and Space press the focused control and Tab moves on. A click, a press that goes to the legacy UI, Escape, or another non-modal window shown meanwhile (it takes the focus from the control) ends it, and the next keys are the game's again. A window without text fields cannot be worked with the keyboard unless it is modal.
- Keep a control out of the tab order when it should not be reached that way: `tab-index: none` on buttons, tabs, list rows and `.nui-focusable`; `focus: none` on form controls (the toggle's checkbox, the slider, input buttons), whose inline `tab-index: auto` outranks a style sheet. The login board takes its buttons out, so Tab moves only between its two fields.
- While a legacy modal (a lock window: the connect-failure popup, a quest dialog) is open, NovaUI gets neither the pointer (except the release of its own press) nor keys, also from a field that keeps its focus behind it, or from a NovaUI modal. Do not open a NovaUI modal from a locked legacy dialog.
- The middle button turns the game camera: it starts no autoscroll in NovaUI.

Escape:

- Escape reaches the focused NovaUI window first, also when NovaUI does not have the keyboard, and it reaches only the focused document (the last one shown or clicked; it keeps the focus after a world click). A hidden window gets none.
- A Python `element_on("", "keydown", fn)` handler that returns exactly `True` keeps it: the legacy Escape chain does not run (it would close the topmost legacy window or open the system menu). Return `True` only when the handler acted, and only while the window is shown. A data-event handler (`@nui.on`) cannot keep a key.
- Nobody keeps it: the legacy UI gets it as well. In a text field it also leaves the field (not in a modal, and not in a document whose `<body>` has `nui-escape-keeps-focus`), so the next Escape is the legacy UI's alone.
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

## Rules

`nuitool lint` enforces the ones marked with a code.

1. **Lengths in `dp`** (NUI002). `px` is allowed only for hairlines that stay one physical pixel at every scale (`1px`, `-1px`, `0px`), in `@spritesheet` rectangles (texture pixels) and under `nui/theme/`. Unitless `0`, `%`, `em`, `vw` and `vh` are fine.
2. **Colors from tokens** (NUI003, NUI004). No `#hex`, `rgb()`, `rgba()`, `hsl()` or named colors outside `nui/theme/`; `transparent` is allowed. Every `var(--x)` must be a token or a custom property declared in the same file.
3. **No inline styles** (NUI009): no `style="..."`, no `data-style-*` and no `data-attr-style`. Put rules in the window's `.rcss` and switch them with `data-class-*`.
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

Safe to use: solid backgrounds, borders (all sides solid), `border-radius`, `opacity` (but do not animate it on a container, see [Motion and reduced motion](#motion-and-reduced-motion)), `transform` (translate, rotate, scale, skew, matrix, perspective), `overflow` clipping, `image`, `tiled-horizontal`, `tiled-vertical`, `tiled-box` (their tiles stretch) and `ninepatch` decorators, `<img>`, sprite sheets (`@spritesheet`, with a gutter, see below), `image-color` tints, `font-effect` (outline, shadow, glow, blur; the font engine draws those into glyph textures on the CPU), and:

- Two-color gradients: `decorator: horizontal-gradient(var(--accent) var(--danger))` and `vertical-gradient(...)`. RmlUi colors the background mesh's vertices, so no shader is involved, and the gradient follows `border-radius`. The older form `gradient(horizontal ...)` draws the same but RmlUi 6.3 logs it as deprecated, which lint reports as NUI008.
- Image fits `repeat`, `repeat-x` and `repeat-y`. Both renderers wrap along an axis whose texture coordinates leave the image (by more than 1/4096) and clamp along the other, so `repeat-x` tiles across without bleeding the top and bottom rows into each other. RmlUi refuses these fits for `@spritesheet` sprites.

Sprite sheets need a gutter. RmlUi addresses a sprite on its whole sheet and passes only texture coordinates, so neither renderer knows the sprite's rectangle: drawn larger than the sheet's resolution, at any UI scale above it (the automatic scale on 1440 and 2160 lines), the sprite's edge pixels filter in up to half a texel of the neighboring sprite. A `.sub` region does not have this problem. Keep at least 1 px of transparent gutter between sprites; for art whose edges must stay opaque (button-state strips, frames), repeat each sprite's edge texels into a 1 px ring around it, which means 2 px between two such sprites. The sheet's outer border needs nothing. One image per icon, or a sheet drawn at twice the size and declared `resolution: 2x`, avoids the question.

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
  echo "== $l"; nuitool lint --root assets/nui --root assets/icon --locale assets/locale/locale/$l
done
```
- Noto Sans covers Latin, Greek and Cyrillic, which includes every non-right-to-left locale the client ships. It has no Arabic, Hebrew, CJK or Thai glyphs.
- Right-to-left text is not supported yet: RmlUi's FreeType engine does no shaping or bidirectional layout. For those locales `nui.enabled_for_locale()` is false and callers keep the legacy window.

## Scale and themes

- One `dp` is one pixel at scale 1.0. The runtime sets the ratio from the backbuffer height (1080 lines = 1.0, in steps of 0.125, between 0.75 and 2.0), or from the player's override (75 to 200 percent, `UI_SCALE`). Glyphs are rasterized at the scaled size, so text stays sharp.
- Test at 0.75, 1.0, 1.5 and 2.0. `nuitool snap --scale` takes a factor in whole percents (`1.25`, not `1.125`, which is a usage error); `--scale auto` with a `--size` gives the client's automatic scale for that height, including its 1/8 steps (0.875 at 900 lines).
- Every document's `<body>` has exactly one of `theme-dark` and `theme-light`; the runtime sets it and swaps it on `nui.set_theme()`. Components never mention the theme; they read tokens, and the tokens change with the class.

## Tools

The Python tool runs from the asset repository root. `nuitool` is built from `nova-client-src`; the commands assume it is on `PATH` and run from the asset repository root, with the relative paths shown. Two ways to get it:

- On Linux or WSL, with the portable harness in `nova-client-src` (no `protocol/` submodule, no GPU), the platform the snapshot goldens were written on:

```bash
cmake -S nova-client-src/tools/linux-nui -B build-nui -G "Unix Makefiles"
cmake --build build-nui -j 6 --target nuitool
ln -sf "$PWD/build-nui/bin/nuitool" ~/.local/bin/nuitool
```

- On Windows, the MSVC build of `nova-client-src` (target `nuitool`, which needs the `protocol/` submodule) writes `build/bin/<config>/nuitool.exe`. From WSL, build it with the recipe in `nova-client-src/tests/README.md` ("Driving the Windows toolchain from WSL") and link it under a name without `.exe`, since WSL does not add the extension (no `PATHEXT`): `ln -s <build>/bin/RelWithDebInfo/nuitool.exe ~/.local/bin/nuitool`. Run it from the asset repository root with relative paths: a Windows executable started from a `/mnt/<drive>` directory does not translate an absolute Linux path such as a `mktemp` directory under `/tmp` (keep `--out` relative, or pass it through `wslpath -w`). A Windows build can differ from the goldens by 1 in a few pixels (see the snapshot README).

Tokens: `python tools/nui_tokens.py`, see [Tokens](#tokens).

Lint, from the asset repository root:

```
nuitool lint --root assets/nui --root assets/icon --locale assets/locale/locale/en
```

- `--root` is a folder that contains store paths. The first one holds the documents: `assets/nui` holds `nui/...`. Repeat it for the groups that images come from: `assets/icon` for `icon/...`, and a group with a `ymir work/` folder, such as `assets/ETC`, for `d:/ymir work/...`.
- `--locale` points at one locale folder with `locale_interface.txt` and `locale_game.txt`. Without it, NUI005 is skipped. Run lint once per shipped locale when you add keys.
- `--scripts` points at the controllers. The default tries `<root>/root`, then `<root>/../root`, which finds `assets/root`.
- Lint loads every document through the runtime, with its fixture, for NUI008. When the runtime cannot start (for example a font that fails to load), that is itself an NUI008 finding and the exit code is 1. `--no-load` skips the loads and runs the static checks only; fixture syntax and model key names (NUI001) are checked either way.
- Lint and snap run no controller, so they give every data-event name a document calls a handler that does nothing, before the document raises its first event: the events a load raises (`data-event-load`, `change` from a binding that moves a toggle or a slider) are not findings. NUI006 is the handler check, and it checks only `nui/windows/<w>/<w>.rml` against `nui_<w>.py` (hyphens as underscores); other documents get no handler check.
- Paths after the options limit the run to those files or folders, relative to the first root: `nuitool lint --root assets/nui --root assets/icon nui/windows/settings`.
- Findings go to standard output as `path:line: NUIxxx: message`, one per line. Notes about skipped checks and the summary line go to standard error. The exit code is 0 when clean, 1 with findings and 2 for a usage error.

| Code | Finding |
|---|---|
| NUI001 | A document, template or style sheet does not parse, RmlUi's template reader cannot find the parts of a template file, or a `.fixture.json` is not valid JSON holding one object per model, or has a top-level model key RmlUi refuses (reported on the fixture, at the JSON line; a key name at line 1). |
| NUI002 | A `px` length other than a hairline (`1px`, `-1px`, `0px`), outside `nui/theme/` and sprite rectangles. |
| NUI003 | A raw color outside `nui/theme/`. |
| NUI004 | `var(--x)` that is neither a token nor declared in the same file. |
| NUI005 | `@ui.KEY` or `@game.KEY` missing from the locale files; a `@game.KEY` typed `SA`, `SNA`, `SAA` or `SAN` in `locale_game.txt`, which `localeInfo` makes a function; any such key in a `data-attr-*` or `data-value` binding, which is never translated; or a locale file whose last line has no newline (reported at that line). |
| NUI006 | A `data-event-*` without a matching `@nui.on` handler in the controller (`nui_<window>.py`, each hyphen as an underscore), or a window name outside lowercase letters, digits and hyphens. |
| NUI007 | A link, template, image or sprite that does not resolve (a `/` path resolves from the store root), an image of a type the client has no loader for (only `.png`, `.tga`, `.jpg`, `.bmp`, `.dds` and `.sub` load), a path that holds `{{ }}`, and a relative image path in a template's body. |
| NUI008 | RmlUi warnings or errors while loading the document with its fixture, one finding per report; or the runtime did not start while loading was on. RmlUi's binding reports carry no line, so lint reports them at the line of the binding whose expression or name they quote, and a report that only follows another one (a view that could not be added) at that one's line; line 1 when nothing matches, as for a binding from a linked template. A key NUI005 already reported is not reported again. |
| NUI009 | An inline style: `style="..."`, `data-style-*` or `data-attr-style`. |
| NUI010 | A feature the renderers do not draw, or an image with opaque `#FF00FF` texels, which the client's color key draws transparent (see [What the renderer draws](#what-the-renderer-draws)). |
| NUI011 | Motion that RmlUi drops or that reduced motion cannot stop, including a motion selector that ties or outranks the reduced-motion rule (see [Motion and reduced motion](#motion-and-reduced-motion)). |
| NUI012 | `data-rml` or `data-rml-*` in markup: model strings are text, never markup (the runtime removes the attribute). |

Snapshots:

```
nuitool snap --root assets/nui --root assets/icon --locale assets/locale/locale/en \
	--doc nui/windows/gallery/gallery.rml --fixture assets/nui/nui/windows/gallery/gallery.fixture.json \
	--theme dark --scale 1.5 --size 2880x1620 --out gallery-dark-150.png
```

- `--doc` is a store path, or a file path under the first root.
- `--fixture` is not picked up automatically; pass the window's `<name>.fixture.json`.
- `--locale` points at one locale folder, as for lint, and fills the string tables before the document loads. Without it every `@ui.KEY` and `@game.KEY` shows as written, and RmlUi warns once for each.
- `--size WxH` is the backbuffer in pixels (default 1280x720). `--scale` is 0.75 to 2 in whole percents (`1.125` is a usage error, since the runtime takes a whole percent), or `auto` for the client's height-based scale, which includes the 1/8 steps (default 1). `--theme` is `dark` (the default) or `light`.
- Snap does not scroll and does not move the window, so the frame has to hold the window: `--size` at least the scale times the window's right and bottom edges in dp. A scroll container shows only its first screen. The gallery is sized for a 1920x1080 dp area: `--size 1920x1080 --scale 1`, `--size 2880x1620 --scale 1.5` and `--size 3840x2160 --scale 2` show all of it. The 1280x720 default is a smaller dp area than the client uses at any automatic scale. Snap notes on standard error when the window reaches past the frame, or when a scroll container (`overflow: auto` or `scroll`) holds more than it shows; neither changes the exit code.
- `--time` is how many seconds of animation run before the frame is taken (default 1, which lets the window-open motion and every stock transition finish). RmlUi moves an animation at most 0.1 s per update, so snap advances the clock in steps of at most 0.1 s; long times cost one update per 0.1 s. An endless animation is caught at the phase `--time` gives it. `--reduced-motion` renders the resting state.
- `--compare golden.png [--tolerance N] [--diff diff.png]` compares with a stored image, channel by channel (N is 0 to 255, default 0), and exits 1 on a mismatch. The diff image goes to `--diff`, by default the output name with `.png` replaced by `.diff.png`. A snapshot matches the golden it was saved as at tolerance 0, as long as the golden was written by `nuitool snap` with the same `--size`, `--scale`, `--theme` and `--time`, by a build for the same platform. Windows and Linux builds can differ by 1 in a few pixels of rotated content, so compare across platforms with `--tolerance 1`. `--compare` may not name the `--out` or the diff file, since snap writes those.
- RmlUi warnings and errors during a snapshot print as `rmlui: ...` on standard error and do not change the exit code; lint reports them as NUI008. Like lint, snap gives every data event a handler that does nothing, so the guide's own windows snap without warnings.
- DDS files are not decoded in snapshots, and neither are `.sub` images whose atlas is a DDS file (most legacy `.sub` files). The image area stays transparent at the image's own size, so the layout matches the client, which draws them, and snap prints a warning naming each file (`rmlui: SoftRenderInterface: ... is not decoded`). A `.sub` image of a PNG, TGA, JPEG or BMP atlas is drawn. Prefer PNG or TGA for NovaUI art.
- The CPU renderer follows the Direct3D 9 renderer's rules: premultiplied texels filtered, clamp addressing that wraps per axis for repeat fits, `.sub` regions clamped at their own edges, the color key and the same unsupported features. Colors, borders, text and images should therefore agree within a small tolerance, but a snapshot is not a screenshot of the client.
- `docs/ui/snapshots/` holds goldens of the gallery, the render test and the login board in both themes at scales 1.0, 1.5 and 2.0. `python3 tools/check_nui_snapshots.py` checks all of them and `--write` regenerates them (see the README there). Regenerate them in the same change as anything they show.

`nuitool help` prints the current options.

## Hot reload and debugging

Hot reload and the two hotkeys below are dev tools. They are compiled into every client build except a distribution one (the CMake option `NOVA_DISTRIBUTION` sets the define `NOVA_UI_DEV_TOOLS` to 0), in every configuration. They switch on only in a build that does not enforce the safe gate (`NOVA_SAFEGATE=OFF`, the dev and test builds), started with the environment variable `NOVA_UI_DEV` set to anything but `0`; a build that enforces the gate, as every player build does, never reads the variable (`nova-client-src/src/UserInterface/NuiHost.h`).

Hot reload also needs the asset store in file-load mode (dev runs without an installed release, `--no-patch`): every asset lookup then reads the file under the client's working directory, and a `HotReloader` watches the `nui/` folder there. One way to edit in place is to make `<client>/nui` a directory junction to `nova-client/assets/nui/nui`.

- Saving an `.rcss` re-applies style sheets to open documents.
- Saving an `.rml` or `.rtpl`, or adding or removing any `.rml`, `.rtpl` or `.rcss` file, re-loads open documents in place. Element handlers from `element_on()` are re-attached, the new document's own events (its load, `change` from bindings) reach the `@nui.on` handlers, then `on_reload()` runs; the replaced document's events reach no handler. Models are kept. A removal counts one poll (0.5 s by default) late, so an editor that saves by replacing the file causes one reload of the kind of file it saved, not two.
- A reload does not retry an image that was missing: add the file, then restart the client (see [What the renderer draws](#what-the-renderer-draws)).
- Ctrl+Shift+D toggles the RmlUi debugger (element tree, computed styles, events).
- Ctrl+Shift+U toggles the render test page. It is loaded afresh on each toggle with RmlUi's style sheet and template caches cleared, so edits to the page, its sheets and `nui.rtpl` show without hot reload.
- The gallery has no hotkey: open it from the client's Python console or a debug script with `import nui_gallery; nui_gallery.open_gallery()`.

## Status and known gaps

- Nothing here has been checked in the running client yet; the unit and integration tests and the snapshots are the evidence so far. That includes the gallery controller, `assets/root/nui_gallery.py`, which binds the theme and close buttons with `element_on()`, and the keyboard rules of [Keyboard and modals](#keyboard-and-modals).
- A data-event handler (`@nui.on`) cannot stop an event; only an `element_on` keydown handler can keep a key (by returning `True`).
- There is no helper yet that marks text another player wrote so `{{ }}` leaves its `@ui.`/`@game.` words alone; until there is, do not bind such text through `{{ }}`.
- Attribute values set after the element exists (`data-attr-*`, `data-value`, code) are not translated (see [Localization](#localization)).
- Right-to-left scripts are not supported. NovaUI text fields show the IME composition, underlined, inside the field; like the legacy edit line, they show no candidate list.
- RmlUi has no drag cancel event (see [RCSS and RML differences that matter](#rcss-and-rml-differences-that-matter)).
- Snapshots do not decode DDS files or `.sub` images of a DDS atlas; they stay transparent.
- A missing image is not retried until the client restarts, hot reload included (see [What the renderer draws](#what-the-renderer-draws)).
