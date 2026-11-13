# Gus_Rigtool - notes for Claude Code

Put this file at the root of the repository. Claude Code reads it automatically at the start of every session.

## What this is

Gus_Rigtool is a personal rigging toolkit for **Maya 2024+** (Python 3.10 inside Maya; code must also lint as
Python 3.7). It ships with **Gus Animtool** (`gus_rigtool/anim/gus_animtool/`), the animators' tools: picker,
pose library, IK/FK switch, mirror, tween, keys tools. Current version: **5.6.32**.

Owner: Gus (Gustavo), a rigger on macOS. He is finishing the **Hare** rig for the short "The Tree That Bloomed in
Winter". He writes in English (sometimes Portuguese) and prefers plain words over jargon.

## Standing rules (always)

1. **Show a numbered plan before ANY code change and wait for approval.** Reading, searching and running
   tests need no approval.
2. **Number every question.**
3. Small choices you make go under **"Decisions I made"** in that release's CHANGELOG.txt entry.
4. **Run the full test suite once per release** (see Tests). Accept changed expected output only after showing
   the diff.
5. Every release message ends with these three flush-left code blocks, in this order:

   Reset:
   ```
   import sys
   for m in [m for m in sys.modules if m.startswith("gus_rigtool")]:
       del sys.modules[m]
   ```
   Version:
   ```
   import gus_rigtool; print(gus_rigtool.__version__)   # x.y.z
   ```
   Bring:
   ```
   import gus_rigtool.main as gr; gr.show()
   ```
6. In every release message also tell Gus to **restart Maya, or reset `gus_animtool`**: the picker lives in
   Animtool, and the reset above only clears `gus_rigtool`.
7. **Never overwrite an existing module.** Check with `ls` / grep before creating a file; there are 60+ modules
   in `core/` and the names are generic (e.g. `core/speed.py` already exists: it's the tool-timing report).
8. Nothing is tested in real Maya here. Say plainly what was only tested against the fake Maya.
9. Don't edit `.ma` / `.mb` scene files; the Hare scenes are on Gus's Mac.
10. Don't push, merge or open a PR until Gus says so.

## Layout

```
drag_to_maya.mel          installer (sits next to gus_rigtool/ in the zip)
gus_rigtool/
  __init__.py             __version__
  main.py                 gr.show() - main window; gr.show_tool(key)
  registry.py             the tool tabs
  scene_check.py          "Check this scene": PARTS list of sections (scene ... picker, speed, ready)
  maya_check.py           in-Maya self test (sections per release, e.g. _check_picker5626)
  CHANGELOG.txt           every release, newest first, with "Decisions I made"
  WHATSNEW.txt            line 1 carries the version
  core/                   the rig logic (ribbon.py, repair.py, safe.py, rigspeed.py, speed.py, skin*.py, ...)
  builder/                build / publish / deliver (publish.py, deliver.py, anim_export.py, ...)
  tools/                  the Maya UI tabs (ribbon_tool.py, checker.py, ...)
  anim/gus_animtool/      Gus Animtool (anim.py, ui.py, pickerqt.py, pickmodel.py, pickmore.py, pickshapes.py, ...)
  tests/                  run_tests.py, fakemaya.py, fakeqt.py, test_*.py, expected/*.txt
```

## Tests

- Fake Maya and Qt: `tests/fakemaya.py` and `tests/fakeqt.py`. Tests start with `exec(open("fakemaya.py").read())`.
  Extend the fakes when a test needs a command they lack (keep it minimal).
- Full suite (since 5.6.29 it runs 4 tests at a time: about 10 minutes, 5 in the cloud; run it in the
  background): `cd gus_rigtool/tests && timeout 2600 python3 run_tests.py` (`-j 1` = one at a time).
- One or a few tests: `python3 run_tests.py <name> [<name> ...]` (name = file name without `test_` and `.py`).
  Names are **exact**; end one with `*` for a prefix (`fix56*` runs fix561, fix5617, fix5618...).
- Accept new output: `python3 run_tests.py --update <names>` (refused without names; prints each diff). Show
  Gus the diffs first. After accepting, `grep -l "^FAIL" expected/*.txt` must print nothing.
- After a version bump, `animtool30`, `updater`, `anim_ui` and the picker tests show CHANGED (the version string).
  That's expected.
- Lint only the changed files: `ruff check --select F --target-version py37 <files>`. Linting the whole repo
  reports thousands of false errors, because tests use names from `exec`'d fakes.

## Releasing

1. Bump the version in `gus_rigtool/__init__.py`, `gus_rigtool/anim/gus_animtool/__init__.py` and line 1 of
   `WHATSNEW.txt`.
2. Write the CHANGELOG.txt entry at the top, with "Decisions I made".
3. Add `tests/test_<version>.py`, then run the full suite.
4. Package from the folder that holds `gus_rigtool/` and `drag_to_maya.mel`:
   ```
   rm -rf gus_rigtool/tests/out; find gus_rigtool \( -name __pycache__ -o -name .ruff_cache \) -prune -exec rm -rf {} +
   rm -f Gus_*_install.zip; zip -qr Gus_Rigtool_install.zip drag_to_maya.mel gus_rigtool
   ```
5. Write the release message (rules 5 and 6).

## Writing style for Gus

- Plain words; say what the animator or rigger sees ("the belt loses its form when scaled"), not internals.
- Short numbered lists. Name the button or menu path ("Ribbon tab > Not symmetric").
- Be honest about what is untested or uncertain.

See `PROJECT_CONTEXT.md` for the history, the Hare rig's current state and the open items.
