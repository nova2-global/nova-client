# assets/_loose

Files placed here are published as **loose files**: the updater writes them to the
client root at the same relative path (e.g. `_loose/bgm/x.mp3` -> `<client>/bgm/x.mp3`,
`_loose/Metin2.exe` -> `<client>/Metin2.exe`) instead of storing them in bundles.
Use it for `bgm/`, `mark/` and the game executable.

Never put user-state files here (`config/metin2.cfg`, `config/channel.inf`,
`config/mouse.cfg`): the client writes those back and the updater would overwrite them.
