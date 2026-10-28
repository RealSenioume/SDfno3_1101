# Slice icons (local only — never committed)

The `lol` theme looks best with the real ping icons, but those are Riot Games'
artwork. This project therefore **does not ship them**: this folder is where
*you* put PNG files on your own machine, and everything here is ignored by Git
(see `.gitignore`).

## How to add your own icons

1. Save one PNG per slice into this folder, named after the icon id:

   | File | Slice (default) |
   | --- | --- |
   | `danger.png` | 6 — Danger (12 o'clock) |
   | `push.png` | 7 — Push (1:30) |
   | `on_my_way.png` | 0 — On My Way (3 o'clock) |
   | `all_in.png` | 1 — All In (4:30) |
   | `assist.png` | 2 — Assist Me (6 o'clock) |
   | `vision.png` | 3 — Need Vision (7:30) |
   | `missing.png` | 4 — Enemy Missing (9 o'clock) |
   | `enemy_vision.png` | 5 — Enemy Vision (10:30) |
   | `ping.png` | centre / basic ping (optional) |

2. Recommended size: 128×128 or 256×256 PNG with transparency. They are scaled
   down at draw time, so larger sources look better on high-DPI screens.
   A square image with the glyph roughly filling the frame works best.

3. Start lolping. Icons are picked up automatically; a missing or unreadable
   file falls back to the built-in vector icon, so a wrong filename never
   produces an empty slice.

4. `python tools/prepare_icons.py` checks the folder and reports what is
   missing, badly named, or not square.

## Where to get them

Use artwork you are allowed to use. For personal/local experimentation the
[League of Legends Wiki ping images](https://wiki.leagueoflegends.com/en-us/Category:Ping_images)
is the usual source; the assets remain © Riot Games and must not be committed to
this repository or redistributed with it.

If you prefer a clean licence, leave this folder empty: the `lol` theme then
draws its own gold vector icons, and the repository stays free of third-party
art.
