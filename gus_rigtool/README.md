# Gus_Rigtool 5.0

Personal rigging toolkit for Maya 2024+, with Gus Animtool for the animators.
What's new since 4.0: `WHATSNEW.txt` (also the **What's new** button). Every change: `CHANGELOG.txt`.

## Install / update

1. Unzip `Gus_Rigtool_install.zip`.
2. Drag **`drag_to_maya.mel`** into Maya's viewport.

That's it, for the first install and for every update. The installer copies `gus_rigtool`
into the shared Maya scripts folder (every Maya version uses it), keeps your `data` folder
(saved shapes, presets), moves over anything from the old `rigtools`, reloads the code,
opens Gus_Rigtool and fills the shelf.

If a new Maya version ever does not find Gus_Rigtool, drag the installer once in that version.

## Opening (Python, no spaces before the code)

```python
import gus_rigtool.main as gr; gr.show()                 # main window, every tool in a tab
import gus_rigtool.main as gr; gr.show_tool("mirror")    # one tool in its own panel
```
Tool keys: home, shapes, mirror, joints, ribbon, skin, fixes, makectrl, stick, follow, build, face, select, groups,
pivots, sdk, attrs, channels, spaces, connect, constrain, rename, organize, checker, settings.

The main window follows the way you rig: **Home** (the five steps, which ones this scene has done, and the
next one), then the workflow - Build, Skin, Controls, Connect, Finish - then the **Toolbox** (helpers for any
step). Under every tool's title a line says which step it is, with buttons to the steps around it. The
**Guide** button opens step-by-step pages with "Take me there" buttons (and saves them as a web page to share).
**Simple view** folds the advanced sections away; **Full view** shows everything. Search box at the top.

Every window is a dockable panel. Each tab of the main window has a **Pop out** button,
so several tools can be open side by side. **What's new** (top of the main window) lists
the changes of the installed version.

## Tools

- **Shapes**: create / replace / edit control shapes (pictures + search), colours, line width,
  your own shapes.
- **Mirror**: Shapes / Full control / Joints / Geometry, live preview, names without L_ / R_,
  mirror whole scene, Mirror / Flip / Reset pose, Select twin, twin list, live follow,
  mirror skin weights.
- **Joints**: joint chains on curves, edges, objects or ribbons; optional IK spline.
- **Ribbon**: ribbon rigs on NURBS surfaces in 4 steps (surface, follicles, controls, build),
  even-by-length follicles, Shape Library controls, rebuild, mirror build.
- **Follow**: controls follow part of a driver (lips follow the jaw, lids the eyes), weight per control.
- **Build**: a full body rig from guides (Biped template or modules, plus Chain for tails, ears...), your names, IK/FK, stretch,
  reverse foot, bendy limbs, spaces, IK/FK matching, templates.
- **Face**: the face on the mesh from its edges - eyes (Blink, Blink_Height), eyelid ribbons, a mouth ribbon
  following the jaw (realistic: lip roll, sticky lips), brows as a control hierarchy, any facial strip; mirrored.
- **Skin**: bind (labels the joints first), copy, clean, mirror by labels, add missing twins, save / load weights.
- **Fixes**: corrective shapes - sculpt in a bent pose, it turns on by itself with the bend; mirror, re-sculpt.
- **Corrective joints**: an option on arm / leg / quadruped leg modules (volume at the bends).
- **Deliver to animators** (Build > Publish): the published rig, the animator tools and a README in one folder.
- **Maya check** (Settings > Self-test): every tool page, a build / skin / rebuild / publish, every Gus Animtool
  action and the self-test, as a report.
- **Select**: select types inside groups, side / name filters, live counts.
- **Groups**: offset / zero groups, stacked groups, shared group or set.
- **Pivots**: many pivots to one spot, reset.
- **SDK**: mirror or copy set driven keys.
- **Checker**: finds rig problems, safe fixes, report.
- **Settings**: every option, your defaults, side colours, export / import, shelf.

**Shelf shortcuts** (after the tool buttons): Freeze, Center pivot, Delete history (safe),
Reset, Snap, Loc at sel, Lock/Hide, Joint axes, Joint size, Mirror pose, Select twin, Offset grp. Left-click = the usual
version, right-click = variants. Choose which ones show in Settings > Shelf shortcuts.

Every tool: status light, numbered steps, ? help, presets, "Copy error report" on errors.

## Layout

```
gus_rigtool/
  main.py         main window, shelf
  registry.py     the list of tools
  install.py      the installer (run by drag_to_maya.mel)
  core/           shared helpers
  tools/          one module per tool (build() = content, show() = own panel)
  builder/        the modular rig builder (names, guides, modules, chain, build)
  icons/          shelf icons, shape pictures
  data/           your saved shapes and presets
  anim/           Gus Anim: the standalone animator tools (Build tab > Make animator tools)
  tests/          tests that run outside Maya (not installed into Maya)
```

## Tests

Outside Maya, with Python 3 and numpy: `cd gus_rigtool/tests` then `python run_tests.py`.
Each test's output is compared with `tests/expected/`; `--update` accepts a new output.
