---
title: Notes on OLD's Page Format
category: guides
---
![](d:/ymir work/ui/wiki/banners/patchnotes.png){align=center width=100%}

Every line is a single textline for the parser.
If you start the line with [ you can
format the current line (for example CENTER_ALIGN):

--- {style=ornate}

- You can add paragraphs by starting the textline with \*.
- You can set the X_PADDING for every textline so it will start a little bit right
- You can color whole lines using COLOR=0xRRGGBB (optional: you can set the alpha if you use 0xRRGGBBAA)

## Its possible to write HUUUUGE TEXT LINES

## with FONT_SIZE

- You can also set the Y_PADDING so the text will start farther from the previous line.

---

Right align exists too ;)
For images you have to set the path in the IMG token, then you can set its (local) position with X and Y tokens. If you
write CENTER_ALIGN or RIGHT_ALIGN then it will overwrite the X token.

Oh btw tokens are separated with ;

![](d:/ymir work/ui/wiki/detail_item.png)

If you write the image before the text you can even write on the image
Otherwise you cant ;)

![](d:/ymir work/ui/wiki/detail_item.png)

If you dont want to restart the client every time you modify this text coppy the wiki folder from locale/en to the client's
folder, then rename it in locale to something else (like wiki_ or whatever) then pack locale and in test_server it will read
the files from the client's folder.

Once its done you only have to change the category to see the edited texts.

## Yeah and dont forget to put it back to locale once you finished (:

If you are wondering why that scrollbar is so long:

- because of the empty lines at the end of the file
