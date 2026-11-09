"""
'Make animator tools': writes Gus Animtool (anim/gus_animtool) to a folder, with your naming (left / right
tokens, mirror plane, control suffix) as its defaults (defaults.json), plus its installer and a short how-to.
Animators don't need Gus_Rigtool.
"""

import os
import shutil

import gus_rigtool
from gus_rigtool.builder import names

FILES = ("gus_anim.py", "drag_to_maya_animtool.mel")
OLD_FILES = ("drag_to_maya_anim.mel",)                   # the installer's name before Gus Animtool
README = """Gus Animtool - animator tools for this rig (and any other rig)

Install: drag drag_to_maya_animtool.mel into Maya's viewport (Maya 2024 or later).
It copies the gus_animtool folder and gus_anim.py into your maya/scripts folder, makes the "Gus_Animtool"
shelf (every tool, with icons) and opens the window. Later: the shelf, or run
    import gus_animtool; gus_animtool.show()
Update: Update... in its window, pick the newest zip.

Tabs: Pick (picker, pose library, select), Pose (tween slider, mirror / flip / reset, copy / paste pose,
mirror animation), Keys (nudge, retime, clean up, Euler, offset chain), Space (no-jump switch, key cleanup),
Limbs (IK / FK switch and bake, teach a limb of another rig), Settings (options, rig profile, hotkeys, toolbar,
shelf, update). The picker: zoom, pan, drag to select, right-click menus; Edit mode to change it.
Every action is one undo.
"""


def _source(name):
    return os.path.join(gus_rigtool.ROOT, "anim", name)


def defaults():
    """Your naming as Gus Animtool's defaults (left / right tokens, mirror plane, control suffix)."""
    from gus_rigtool.core import mirror_engine, sides
    pairs = [list(p) for p in sides.default_pairs()] or [["L_", "R_"]]
    axis, center = mirror_engine.plane()
    return {"pairs": pairs, "axis": int(axis), "center": [float(c) for c in center],
            "suffix": names.settings()["suffixes"].get("ctrl", "_ctrl")}


def make(folder):
    """Write the animator tools into folder (gus_animtool with your naming, gus_anim.py, the installer and a
    how-to). Returns the files / folders written."""
    import json
    if not os.path.isdir(folder):
        os.makedirs(folder)
    out = []
    pkg = os.path.join(folder, "gus_animtool")
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)
    shutil.copytree(_source("gus_animtool"), pkg, ignore=shutil.ignore_patterns("__pycache__"))
    with open(os.path.join(pkg, "defaults.json"), "w") as f:
        json.dump(defaults(), f, indent=1)
    out.append(pkg)
    for old in OLD_FILES:                                     # old installer names: only one to drag
        if os.path.isfile(os.path.join(folder, old)):
            os.remove(os.path.join(folder, old))
    for name in FILES:
        shutil.copy2(_source(name), os.path.join(folder, name))
        out.append(os.path.join(folder, name))
    path = os.path.join(folder, "README_animators.txt")
    with open(path, "w") as f:
        f.write(README)
    out.append(path)
    return out


def install_here():
    """Install (or update) Gus Animtool in this Maya's scripts folder with your naming, and open it."""
    import json
    import sys
    import maya.cmds as cmds
    scripts = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    if not os.path.isdir(scripts):
        os.makedirs(scripts)
    pkg = os.path.join(scripts, "gus_animtool")
    if os.path.isdir(pkg):
        shutil.rmtree(pkg, ignore_errors=True)
    shutil.copytree(_source("gus_animtool"), pkg, ignore=shutil.ignore_patterns("__pycache__"))
    with open(os.path.join(pkg, "defaults.json"), "w") as f:
        json.dump(defaults(), f, indent=1)
    shutil.copy2(_source("gus_anim.py"), os.path.join(scripts, "gus_anim.py"))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    for m in [m for m in sys.modules if m.startswith("gus_animtool") or m == "gus_anim"]:
        sys.modules.pop(m, None)
    import gus_animtool
    from gus_animtool import toolbar
    toolbar.make_shelf()
    gus_animtool.show()
    return gus_animtool.__version__
