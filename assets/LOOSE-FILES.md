# assets/_loose

Files placed here are published as **loose files**: the updater writes them to the
client root at the same relative path (e.g. `_loose/bgm/x.mp3` -> `<client>/bgm/x.mp3`,
`_loose/Metin2.exe` -> `<client>/Metin2.exe`) instead of storing them in bundles.
Use it for `bgm/`, `mark/`, the game executable and `THIRD_PARTY_NOTICES.txt`, the
license notices of libraries linked into the executable (RmlUi and its bundled code),
which players must be able to read next to it.

Never put user-state files here (`config/metin2.cfg`, `config/channel.inf`,
`config/mouse.cfg`): the client writes those back and the updater would overwrite them.
