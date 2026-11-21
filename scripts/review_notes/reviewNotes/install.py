"""
Installer - run by drag_to_maya.mel (drag that file into Maya's viewport). Same way as the onion skin's:
  - removes the REVIEW_NOTES node and unloads the old plugin if they're there (your notes are in the review
    files, nothing is lost); to unload it, it CLEARS THE UNDO HISTORY (Gus OK'd, 0.1.2);
  - copies reviewNotes into the shared Maya scripts folder (every Maya version uses it):
        Windows  Documents/maya/scripts/reviewNotes
        Mac      ~/Library/Preferences/Autodesk/maya/scripts/reviewNotes
  - makes sure that folder is on Python's path at Maya start, and that opening a scene with notes shows them
    (userSetup.py);
  - puts one Review button on the shelf you have open (an older one is replaced, not doubled);
  - loads the plugin and runs the Review button once.
"""

import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel

PACKAGE = "reviewNotes"
PLUGIN = "reviewNotesNode"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".ruff_cache")
MARKER = "# Review Notes (added by its installer)"
BUTTON = "reviewNotesShelfButton"
BUTTON_COMMAND = "import reviewNotes.controller as _rn_c\n_rn_c.show()"


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def _old_copy_off():
    """The running copy off before it's replaced: callbacks, the node, the plugin. False = Maya must restart."""
    for name, fn in (("window", "close"), ("drawtool", "off"), ("controller", "unwatch")):
        mod = sys.modules.get(PACKAGE + "." + name)
        try:
            if mod is not None:
                getattr(mod, fn)()
        except Exception:
            pass
    if not cmds.pluginInfo(PLUGIN, query=True, loaded=True):
        return True
    try:
        for shape in cmds.ls(type="reviewNotes") or []:
            cmds.delete(cmds.listRelatives(shape, parent=True))
        cmds.flushUndo()            # Maya won't unload a plugin whose node is still in the undo queue (Gus OK'd)
        print("Review Notes installer: undo history cleared to update the plugin.")
        cmds.unloadPlugin(PLUGIN)
        sys.modules.pop(PLUGIN, None)   # or Maya loads the OLD code again from Python's memory (0.1.3: still 0.1.1)
        return True
    except RuntimeError as e:
        print("Review Notes installer: the old plugin (%s) stays loaded until Maya restarts: %s"
              % (_loaded_version(), str(e).strip()))
        return False


def _loaded_version():
    try:
        return cmds.pluginInfo(PLUGIN, query=True, version=True)
    except Exception:
        return "?"


def _ensure_user_setup(version_scripts, shared):
    path = os.path.join(version_scripts, "userSetup.py")
    text = ""
    if os.path.isfile(path):
        with open(path, "r") as f:
            text = f.read()
    if MARKER in text:
        return False
    block = ("\n%s\nimport sys as _rn_sys\nif r\"%s\" not in _rn_sys.path:\n    _rn_sys.path.append(r\"%s\")\n"
             "try:\n    import maya.utils as _rn_u\n"
             "    _rn_u.executeDeferred(\"import reviewNotes.controller as _rn_c; _rn_c.watch()\")\n"
             "except Exception as _rn_e:\n    print(\"Review Notes: not started (%%s)\" %% _rn_e)\n"
             % (MARKER, shared, shared))
    if not os.path.isdir(version_scripts):
        os.makedirs(version_scripts)
    with open(path, "a") as f:
        f.write(block)
    return True


def _shelf_button():
    top = mel.eval("$rnShelfTmp = $gShelfTopLevel")
    for shelf in cmds.tabLayout(top, query=True, childArray=True) or []:
        for b in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
            try:
                if cmds.objectTypeUI(b) != "shelfButton":
                    continue
                cmd = cmds.shelfButton(b, query=True, command=True) or ""
                if "reviewNotes" in cmd:
                    cmds.deleteUI(b)
            except RuntimeError:
                pass
    current = cmds.tabLayout(top, query=True, selectTab=True)
    cmds.shelfButton(BUTTON, parent=current, label="Review", annotation="Review Notes: draw and write notes on the camera, see the scene's notes",
                     image="pythonFamily.png", imageOverlayLabel="Rev", sourceType="python", command=BUTTON_COMMAND)
    try:
        mel.eval("saveAllShelves $gShelfTopLevel")
    except RuntimeError:
        pass
    return current


HOTKEYS = (("ReviewNotes_ToggleDraw", "Review Notes: draw on the view on / off", "hk_toggle"),
           ("ReviewNotes_SaveNote", "Review Notes: save the drawing as a note (with the window's text)", "hk_save"),
           ("ReviewNotes_EndCurve", "Review Notes: end the curve you're drawing", "hk_end_curve"))


def _hotkey_commands():
    """Commands to put on keys (Hotkey Editor > Custom Scripts > Review Notes). Made again on every install."""
    made = []
    for name, note, fn in HOTKEYS:
        code = "import reviewNotes.drawtool as _rn_d\n_rn_d.%s()" % fn
        try:
            if cmds.runTimeCommand(name, exists=True):
                cmds.runTimeCommand(name, edit=True, delete=True)
            cmds.runTimeCommand(name, annotation=note, category="Custom Scripts.Review Notes",
                                commandLanguage="python", command=code)
            made.append(name)
        except RuntimeError:
            pass
    return made


def install(source_dir):
    src = os.path.join(source_dir, PACKAGE)
    if not os.path.isfile(os.path.join(src, "__init__.py")):
        cmds.error("Review Notes installer: no '%s' folder next to drag_to_maya.mel (%s)." % (PACKAGE, source_dir))
    shared = os.path.normpath(os.path.join(cmds.internalVar(userAppDir=True), "scripts"))
    version_scripts = os.path.normpath(cmds.internalVar(userScriptDir=True))
    dest = os.path.join(shared, PACKAGE)

    fresh = _old_copy_off()
    if _norm(src) != _norm(dest):
        if not os.path.isdir(shared):
            os.makedirs(shared)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=IGNORE)
    if _norm(shared) not in [_norm(p) for p in sys.path]:
        sys.path.insert(0, shared)
    _ensure_user_setup(version_scripts, shared)
    for name in [m for m in sys.modules if m == PACKAGE or m.startswith(PACKAGE + ".")]:
        del sys.modules[name]

    shelf = _shelf_button()
    keys = _hotkey_commands()
    import reviewNotes
    import reviewNotes.controller as ctl
    ctl.watch()
    ctl.show()
    loaded = _loaded_version()
    stale = loaded != reviewNotes.__version__
    msg = "Review Notes %s installed in %s - Review button on the '%s' shelf; %d hotkey command(s).%s" % (
        reviewNotes.__version__, dest, shelf, len(keys),
        " RESTART MAYA: the plugin running is still %s." % loaded if (stale or not fresh) else "")
    print(msg)
    return dest
