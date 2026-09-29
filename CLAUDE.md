# nova-client notes for agents

## NovaUI windows

New UI windows are RmlUi 6.3 documents in `assets/nui/nui/` (the `nui` group in `assets/groups.txt`; store paths start with `nui/`) with a Python controller in `assets/root/nui_<name>.py`. Read `docs/ui/AUTHORING.md` before writing or changing one. The gallery (`assets/nui/nui/windows/gallery/gallery.rml`) shows every component in every state; copy markup from it.

- Style sheets use `dp` and theme tokens only. `assets/nui/nui/theme/tokens.rcss` is generated: edit `tokens.json`, then run `python tools/nui_tokens.py` (it also checks contrast and updates the token table in the guide). `python -B -m unittest nui_tokens_test` in `tools/` tests the script.
- The Python API is `assets/root/nui.py`; its docstrings are the specification. Python runs only on events.
- Motion goes in `.component.nui-anim` rules with the values written out; RmlUi 6.3 ignores `var()` inside `transition`.

New window checklist:

1. `assets/nui/nui/windows/<name>/<name>.rml`: link `../../nui.rtpl`, `<body template="nui" class="nui-window nui-anim" data-model="<name>">`.
2. `<name>.rcss` for size and position, tokens and `dp` only, no inline styles.
3. `<name>.fixture.json` with every key of every model the document binds.
4. `assets/root/nui_<name>.py`: a `nui.Window` subclass with `DOCUMENT`, `MODEL`, `initial_model()` and one `@nui.on("x")` per `data-event-*="x(...)"`.
5. Strings as `@ui.KEY` / `@game.KEY` that exist in every locale.
6. `nuitool lint --root assets/nui --root assets/icon --locale assets/locale/locale/en` prints nothing.
7. `nuitool snap` in both themes at 1.0, 1.5 and 2.0 and with `--reduced-motion`; look at the images, also with the German locale.
