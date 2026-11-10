# Writing wiki pages

This guide is for writing the in-game wiki's text pages: guides, dungeons, systems and events. You write plain text files. The game turns them into pages in the wiki window, in every theme (dark, light, cyberpunk, classic) and at every interface scale.

You never place anything by pixel. The old wiki's `.txt` pages did, and they broke whenever a font or a scale changed. Here you say *what* something is (a heading, a list, an image on the right), and the window decides where it goes.

## Where the files go

| What | Where |
|---|---|
| An English page | `assets/locale/locale/en/wiki/<path>.txt` |
| The same page in another language | `assets/locale/locale/<lang>/wiki/<path>.txt` (for example `de`, `fr`, `pt`) |
| The list of every page | `assets/locale/locale/en/wiki/index.txt` |
| Images for pages | `assets/locale/locale/common/wiki/<name>.png` (shared by every language), or any image already in the pack |
| Drafts that must not ship | `docs/wiki/drafts/` (outside `assets/`, so the game never sees them) |

A page's **path** is its file name without `.txt`, relative to the `wiki` folder, for example `dungeons/demon_tower`. Paths use only lowercase letters, digits, `_`, `-` and `/`, at most 64 characters.

**English is the fallback.** When a player's language has no file for a page, the English page shows. So write the English page first; translations are optional.

**Every page goes in `index.txt` once**, one path a line. The game cannot list a folder, so a page missing from the index does not exist. The order of the lines is the order of the pages in the wiki's tree. Lines starting with `#` are comments.

```
# index.txt
guides/basic_guide
dungeons/demon_tower
```

Save files as UTF-8, with the extension `.txt`. The game reads no other extension from the pack (a `.md` page never shows), and `check` reports any other file in a `wiki` folder. No page may be called `index`: that name is the list.

## The front matter

Every page starts with its front matter, between two `---` lines:

```
---
title: Demon Tower
category: dungeons
decor: top-right = icon/item/27001.tga
order: 10
---
```

| Key | Needed | What it does |
|---|---|---|
| `title` | yes | The page's name in the tree, the tab, the trail and the search. At most 80 characters. |
| `category` | yes | Where the page sits in the tree: `guides`, `dungeons`, `systems` or `events`. Translations must keep the English page's category. |
| `decor` | no | An image pinned to a corner of the page, behind the text: `top-left`, `top-right`, `bottom-left` or `bottom-right`, then `=` and an image path. It does not move the text. One per corner; repeat the line for another corner. Images larger than 160 x 160 are shrunk. |
| `order` | no | A number. Pages with a lower number come first in their category; pages with the same number keep the index order. |

A new category needs a developer: it is a line in `assets/root/nui_wiki_pages.py` (`CATEGORIES`) and a name in every language's `locale_game.txt`.

## Text

### Headings

```
# A big heading
## A heading
### A small heading
```

The page's title is already shown at the top, so most pages start with `##`.

### Paragraphs

Lines next to each other join into one paragraph. A blank line starts a new one.

```
This is one paragraph,
even on two lines.

This is the next paragraph.
```

### Bold and italic

```
**bold**, *italic*, ***both***
```

A `*` that is never closed stays a `*`: `2 * 3 = 6` shows as written.

### Lists

```
- A bullet
- Another bullet
  that goes on here, indented by two spaces
  - A nested bullet (two spaces before the dash)

1. First
2. Second
3. Third
```

`*` works as a bullet too. A numbered list counts from its first number, whatever numbers follow.

### Tables

```
| Boss | Level | Where |
|---|---|---|
| Blue Death | 75 | Demon Tower |
| Spider Baroness | 80 | Spider Dungeon |
```

The `|---|` line makes the first row a header; leave it out for a table without one. At most 8 columns. A short row gets empty cells.

## Links

```
[[item:19]]                       the item's name, linked to its page
[[mob:101]]                       the monster's name, linked to its page
[[page:dungeons/demon_tower]]     the page's title, linked to it
[[mob:101|this wolf]]             your own text after a |
```

Item and monster links take the number from the game's tables (the vnum). A page link takes a page path from `index.txt`. A link opens like every other link in the wiki: a click opens it, a middle click or Ctrl and a click opens it in a new tab.

A broken link (a wrong kind, a number that is not a number, a page that does not exist) shows in red, and the page says what is wrong.

### Items with their icon

Put a `!` before an item link to show the item as the game does: its icon in a small box, then its name. Pointing at it shows the item's full tooltip, and a click opens its page, like any link.

```
Defeat the [[mob:1093]] to get the ![[item:30304]].
Collect ![[item:30330|Maat Stones]] x5 to break the pillars.
| Grade | Sash |
|---|---|
| Basic | ![[item:85001]] |
```

The first line shows the Zin-Bong-In Key's icon and name in the sentence. Text after a `|` replaces the name, as in a link. An embed works anywhere a link does: in paragraphs, lists, tables, notes and bold text.

Use an embed where a player needs to recognize the item (a key, a stone, a reward), and a plain link elsewhere, so the text stays easy to read. Only items embed: `![[mob:...]]` and `![[page:...]]` are mistakes and show in red; write monsters and pages as links. To show a `!` right before a link, write `\!`.

Why `![[...]]`: in Markdown a `!` before a link makes it an image, so an embed reads as "this link, shown as a picture". `[[item:N|icon]]` would clash with link text (a link whose text is "icon"), and `{{ }}` is the interface's own template syntax, which a page must never use.

OLD's pages placed an item's icon by pixel, `[IMG=icon/item/30304.tga; ITEM_TOOLTIP=30304; X=270; Y=133]`. The converter (`tools/wiki_convert_old.py`) turns each one into `![[item:30304]]` (with ` xN` after it for an `item_count`).

## Images

An image is a line of its own:

```
![A sword](icon/item/00010.tga)
![A sword](icon/item/00010.tga){float=right width=64}
![The map](d:/ymir work/ui/metin2_map_a1_atlas.dds){align=center width=50%}
```

The text in `[ ]` describes the image (the search finds it). Options go in `{ }`:

| Option | Values | What it does |
|---|---|---|
| `float` | `left`, `right` | The image sits at that side and the text flows around it. |
| `align` | `left`, `center`, `right` | The image sits alone on its line. |
| `width` | `8` to `640` | The width in the interface's units (it grows with the scale). |
| `width` | `1%` to `100%` | A share of the page's width. |

Use `float` or `align`, not both. Without `width`, an image keeps its own size (and never grows wider than the page). The height always follows the width.

**Image paths** are pack paths: lowercase letters, digits, `_`, `-`, `.` and `/`, ending in `.png`, `.tga`, `.dds`, `.jpg` or `.sub`. Two kinds work:
- a path from the pack's root, such as `icon/item/27001.tga` or `locale/common/wiki/my_banner.png`;
- a path on the game's art drive, such as `d:/ymir work/ui/metin2_map_a1_atlas.dds`.

Nothing else works: no `..`, no web addresses, no other drives, no capital letters. A new image for a page goes in `assets/locale/locale/common/wiki/` and is written `locale/common/wiki/<name>.png`.

## Separators

```
---                    the theme's line
--- {style=ornate}     a named style
```

`ornate` draws two lines fading out from a small diamond, in the theme's accent color.

### Adding a separator style

A style is one rule in a style sheet, so a developer or a designer adds it (ask one if you want a new look):

1. In `assets/nui/nui/windows/wiki/wiki-pages.rcss`, add rules for `.wp__hr--<name>`. A separator has three parts you can style: two `.wp__hr-line` and the `.wp__hr-gem` between them (hidden by default). Use theme colors (`var(--accent)`, `var(--border)`) and `dp` sizes, so the style follows every theme and scale. Copy the `ornate` rules as a start.
2. To use art from the pack instead, draw it with a decorator, for example `.wp__hr--scroll { decorator: image(/locale/common/wiki/scroll_divider.png); }` with the lines hidden, and list the image in `assets/nui/nui/content-art.json` (with a `why`), or the interface's checks refuse it.
3. Add `<name>` to `SEPARATOR_STYLES` in `assets/root/nui_wiki_page_format.py`. A test checks that every name has a rule and every rule a name.
4. If the classic theme needs a different look, add the rule to `assets/nui/nui/skins/classic/windows/wiki.rcss`, starting with `body.skin-classic.wiki`.

## Notes, warnings and columns

```
:::note
A tip for the player. It can hold **formatting**, lists, tables and images.
:::

:::warning
Something that can go wrong.
:::

:::columns
Left column text
- a list
+++
Right column text
+++
A third column
:::
```

Each block ends with a line `:::`. In `:::columns`, a `+++` line starts the next column; at most 3 columns. A block cannot hold another block (no note inside columns).

## Showing a character as it is

A backslash before any punctuation shows it as written, for example `\*`, `\#`, `\[[`, `\|`, or `1\.` to start a line with a number that is not a list.

You can write anything else as it is, including `<` and `>`: nothing in a page is ever read as code.

## When something is wrong

A mistake never breaks the window. The part that is wrong shows as a red box saying what is wrong, at the place where it happened, and the rest of the page shows. A page with no usable front matter (no `---` at the top, no title, no category) shows only that red box.

## Checking your pages

From the asset repository's root:

```
python3 tools/nui_wiki_pages_tool.py check
```

It reads every page in every language and prints one line a problem: markup the page could not read, a page missing from `index.txt` (or a line of `index.txt` with no page), an unknown category, a link to a page that does not exist, an image that is not in the pack. With the server's tables (`--data <folder with item_names.txt and mob_names.txt>`) it also checks that every item and monster number exists. It ends with `problems: 0` when everything is right.

## Previewing a page without the game

```
python3 tools/nui_wiki_pages_tool.py preview assets/locale/locale/en/wiki/dungeons/demon_tower.txt
```

This draws the wiki window with your page, as the game would, into `preview.png`. It needs `nuitool` (ask a developer for it; `docs/ui/AUTHORING.md` explains how to build it) on your `PATH` or in the `NUITOOL` variable. The file can be anywhere, so you can preview a draft before it ships.

| Option | What it does |
|---|---|
| `--theme modern-dark` | The theme: `modern-dark` (the default), `modern-light`, `cyberpunk` or `classic`. |
| `--scale 1.5` | The interface scale, from `0.75` to `2`. |
| `--locale de` | The language of the window's own words. |
| `--skip 8` | The preview does not scroll: this leaves out the page's first 8 blocks, to see what comes further down. |
| `--out mine.png` | Where to write the picture. |

Check a page in at least `modern-dark` and `classic`, and once at `--scale 2`.

## Linking a page in chat

The wiki's Link button puts a link to the open page in the chat or a whisper. It is written `|Hsyswiki:page:<path>|h[<title>]|h`, and a click on it opens the page.

## A complete example

`docs/wiki/examples/every-feature.txt` uses every feature once. Preview it to see each one in each theme.
