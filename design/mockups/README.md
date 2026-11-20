# Mock-ups (pictures for Gus before anything is built)

HTML drawn with Python, screenshotted with Playwright (Chromium). Not part of the tool or its zip.

- `v2.py` - the 5.7 look, version 2 (a colour per area, X/Y/Z colours, chips, shapes as pictures).
- `v2pages.py` - every Rigtool page in that look (uses v2.py, icons.py).
- `scope.py` - the 5.7 scope (settings under the tile, next step, pin, Skin Tools, one look).
- `anim_mock.py` - the Animtool in the same principles + the customizable bar with profiles.
- `pitch.py` - the Animtool 5.8 pitch (6 slides: today vs proposal, principles and borrowed ideas, pages, style
  variants, bar variants, honest risks and rollout).

Run from this folder: `python3 pitch.py`, then screenshot `pitch.html` (each `.slide` / `.blk`) at device scale 2.
