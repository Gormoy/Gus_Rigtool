"""
Gus_Rigtool installer, run by dragging drag_to_maya.mel into Maya's viewport.

  - copies gus_rigtool into the shared Maya scripts folder (used by every Maya version):
        Mac      ~/Library/Preferences/Autodesk/maya/scripts/gus_rigtool
        Windows  Documents/maya/scripts/gus_rigtool
  - keeps your data folder (saved shapes, presets) from earlier installs, including the
    old "rigtools" ones, and carries over the old rigtools settings
  - removes old copies (rigtools / gus_rigtool) from the version scripts folder, the old
    "rigtools" shelf and its panels
  - makes sure Maya finds the shared folder now and in later sessions
  - loads the new code, opens Gus_Rigtool and fills the shelf

Only Python's standard library and Maya are used, so it runs before the package is importable.
"""

import os
import shutil
import sys

import maya.cmds as cmds

PACKAGE = "gus_rigtool"
OLD_PACKAGE = "rigtools"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "tests")      # tests run outside Maya
MARKER = "# Gus_Rigtool path (added by the Gus_Rigtool installer)"
OLD_MARKER = "# rigtools path (added by the rigtools installer)"
OLD_SHELF = "rigtools"
SETTING_PREFIX, OLD_SETTING_PREFIX = "gusrig_", "rigtools_"


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def _collect_data(folders):
    """User files from earlier installs' data folders: {file name: bytes} (newest install wins)."""
    keep = {}
    for folder in folders:
        data = os.path.join(folder, "data")
        if not os.path.isdir(data):
            continue
        for name in os.listdir(data):
            path = os.path.join(data, name)
            if name == "README.txt" or not os.path.isfile(path) or name in keep:
                continue
            with open(path, "rb") as f:
                keep[name] = f.read()
    return keep


def _ensure_user_setup(version_scripts, shared):
    """Add the shared folder to Python's path in this Maya version's userSetup.py."""
    path = os.path.join(version_scripts, "userSetup.py")
    text = ""
    if os.path.isfile(path):
        with open(path, "r") as f:
            text = f.read()
    if MARKER in text or OLD_MARKER in text:          # the old block adds the same folder
        return False
    block = ("\n%s\nimport sys as _gr_sys\nif r\"%s\" not in _gr_sys.path:\n"
             "    _gr_sys.path.append(r\"%s\")\n" % (MARKER, shared, shared))
    if not os.path.isdir(version_scripts):
        os.makedirs(version_scripts)
    with open(path, "a") as f:
        f.write(block)
    return True


def _close_panels():
    for name in cmds.lsUI(type="workspaceControl") or []:
        if name.startswith("rigtools_") or name.startswith("gusrig_"):
            try:
                cmds.deleteUI(name)
            except RuntimeError:
                pass


def _forget_panel_states(keys):
    for key in keys:
        for name in ("rigtools_%s_panel" % key, "gusrig_%s_panel" % key):
            try:
                if cmds.workspaceControlState(name, exists=True):
                    cmds.workspaceControlState(name, remove=True)
            except (RuntimeError, TypeError, AttributeError):
                pass


def _migrate_settings():
    """Copy old rigtools_* settings to gusrig_* (only where nothing is set yet)."""
    moved = 0
    for var in cmds.optionVar(list=True) or []:
        if not var.startswith(OLD_SETTING_PREFIX):
            continue
        new = SETTING_PREFIX + var[len(OLD_SETTING_PREFIX):]
        if cmds.optionVar(exists=new):
            continue
        value = cmds.optionVar(query=var)
        if isinstance(value, str):
            cmds.optionVar(stringValue=(new, value))
            moved += 1
    return moved


def _remove_old_shelf():
    if cmds.shelfLayout(OLD_SHELF, exists=True):
        try:
            cmds.deleteUI(OLD_SHELF)
        except RuntimeError:
            pass
    try:
        shelf_file = os.path.join(cmds.internalVar(userShelfDir=True), "shelf_%s.mel" % OLD_SHELF)
        if os.path.isfile(shelf_file):
            os.remove(shelf_file)
    except (OSError, RuntimeError):
        pass


def install(source_dir):
    src = os.path.join(source_dir, PACKAGE)
    if not os.path.isfile(os.path.join(src, "__init__.py")):
        cmds.error("Gus_Rigtool installer: no '%s' folder next to drag_to_maya.mel (%s)." % (PACKAGE, source_dir))

    app_dir = cmds.internalVar(userAppDir=True)                                   # .../maya/
    shared = os.path.normpath(os.path.join(app_dir, "scripts"))
    version_scripts = os.path.normpath(cmds.internalVar(userScriptDir=True))     # .../maya/2024/scripts
    dest = os.path.join(shared, PACKAGE)
    old_folders = [os.path.join(version_scripts, PACKAGE), os.path.join(shared, OLD_PACKAGE),
                   os.path.join(version_scripts, OLD_PACKAGE)]

    _close_panels()

    keep = {}
    if _norm(src) != _norm(dest):
        keep = _collect_data([dest] + old_folders)
        if not os.path.isdir(shared):
            os.makedirs(shared)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=IGNORE)
        data_dir = os.path.join(dest, "data")
        if not os.path.isdir(data_dir):
            os.makedirs(data_dir)
        for name, content in keep.items():
            with open(os.path.join(data_dir, name), "wb") as f:
                f.write(content)
    for old in old_folders:
        if os.path.isfile(os.path.join(old, "__init__.py")) and _norm(old) != _norm(dest):
            shutil.rmtree(old)

    if _norm(shared) not in [_norm(p) for p in sys.path]:
        sys.path.insert(0, shared)
    _ensure_user_setup(version_scripts, shared)
    moved = _migrate_settings()
    _remove_old_shelf()

    # load the new code from scratch
    for name in [m for m in sys.modules if m in (PACKAGE, OLD_PACKAGE)
                 or m.startswith(PACKAGE + ".") or m.startswith(OLD_PACKAGE + ".")]:
        del sys.modules[name]
    import gus_rigtool
    from gus_rigtool import registry
    import gus_rigtool.main as gr
    from gus_rigtool.core import utils

    _forget_panel_states(["main"] + [t[0] for t in registry.TOOLS])
    gr.show()
    gr.make_shelf()

    msg = "Gus_Rigtool %s installed in %s" % (gus_rigtool.__version__, dest)
    extras = []
    if keep:
        extras.append("kept %d data file(s)" % len(keep))
    if moved:
        extras.append("carried over %d old setting(s)" % moved)
    if extras:
        msg += " (" + ", ".join(extras) + ")"
    utils.info("Gus_Rigtool", msg + ".")
    return dest
