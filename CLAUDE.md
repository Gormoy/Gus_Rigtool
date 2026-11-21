# Gus_Rigtool - notes for Claude Code

Put this file at the root of the repository. Claude Code reads it automatically at the start of every session.

## What this is

Gus_Rigtool is a personal rigging toolkit for **Maya 2024+** (Python 3.10 inside Maya; code must also lint as
Python 3.7). It ships with **Gus Animtool** (`gus_rigtool/anim/gus_animtool/`), the animators' tools: picker,
pose library, IK/FK switch, mirror, tween, keys tools. Current version: **5.7.8.1**.

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
6b. (5.6.47, Gus asked) Every release message also ends with the **commands to paste**, ready to copy: the
   Terminal line for the real-Maya tests and the one that shows the results file in Finder, and the Script
   Editor line for Test this release:
   ```bash
   "/Applications/Autodesk/maya2024/Maya.app/Contents/bin/mayapy" ~/Library/Preferences/Autodesk/maya/scripts/gus_rigtool/realmaya/run_maya_tests.py --no-scene
   ```
   ```bash
   open -R ~/Library/Preferences/Autodesk/maya/scripts/gus_rigtool/realmaya/maya_test_results.txt
   ```
   ```
   from gus_rigtool.realmaya import window_checks; window_checks.run()
   ```
7. **Never overwrite an existing module.** Check with `ls` / grep before creating a file; there are 60+ modules
   in `core/` and the names are generic (e.g. `core/speed.py` already exists: it's the tool-timing report).
8. Nothing is tested in real Maya here. Say plainly what was only tested against the fake Maya.
9. Don't edit `.ma` / `.mb` scene files; the Hare scenes are on Gus's Mac.
10. Don't push, merge or open a PR until Gus says so.
11. **Maya behaviour first** (5.6.46): before building on how Maya behaves (a node, a command, an evaluation
    rule), check `gus_rigtool/realmaya/MAYA_FACTS.md`; if it isn't there, add the question to `maya_facts.py` and
    get Gus's answer first. When an answer changes, change `tests/fakemaya.py` to match.
12. **Viewport looks proven first** (5.6.46): for anything Gus sees in the viewport (arcs, ghosts, shapes), send a
    tiny try-it script and get his screenshot before building the whole feature (5.6.40's arcs were reverted).
13. **Releases go to `main`** once Gus OKs a push (fast-forward; every release branch builds on the last).
14. **Save the conversation, not only the code** (Gus, 5.7.1): keep `DISCUSSIONS.md` (repo root) up to date in
    every conversation - his decisions, preferences, answers to questions and open plans - and commit it with
    the next commit. Read it at the start of every session, with PROJECT_CONTEXT.md.

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
  newui/                  5.7 window (Qt): window.py (frame, sidebar, areas), record.py (a page's build() written
                          down), render.py (drawn in the new look), proxy.py (the pages' `cmds`: their field names
                          go to the new widgets), widgets.py, theme.py, icons.py, nextstep.py
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
- **Test this release** (since 5.6.46): in Gus's open Maya, Animtool bar > = > Test this release - the checks
  that need Maya's window (`realmaya/window_checks.py`: the bar, the shelf, undo, Time Slider stretches,
  pick-walk). Add a check there for anything only the window shows.
- **Version strings** (since 5.6.46): `run_tests.py` replaces the current version with `<this version>`, so a
  version bump changes no expected output.
- **Real-Maya tests** (since 5.6.35): `gus_rigtool/realmaya/` - Gus double-clicks `run_maya_tests.bat` (Windows)
  or `run_maya_tests.command` (Mac); mayapy runs `maya_cases.py` and writes `maya_test_results.txt`, which he
  sends. They can't run here. Add a case there for anything the fake Maya can't show, and list in the release
  message which cases to run.
- **The new window** (since 5.7.0): `test_570` builds it with real Qt off-screen (`pip install PySide6`; Maya
  2024 itself uses PySide2). It checks nothing is cut off at 300 / 420 / 700 px and that no control of a page is
  lost (a page in the new look is its tool's own build(), recorded). A tool drawn in the new look imports `cmds`
  from `gus_rigtool.newui.proxy`, not maya.cmds.
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

See `PROJECT_CONTEXT.md` for the history, the Hare rig's current state and the open items, and `DISCUSSIONS.md`
for what Gus decided and wants next.
