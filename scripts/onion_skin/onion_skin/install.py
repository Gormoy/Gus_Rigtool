"""
Onion Skin installer - run by drag_to_maya.mel (drag that file into Maya's viewport). It:
  - closes the Onion Skin window if it's open (its ghosts are cleared);
  - copies onion_skin into the shared Maya scripts folder (every Maya version uses it):
        Windows  Documents/maya/scripts/onion_skin
        Mac      ~/Library/Preferences/Autodesk/maya/scripts/onion_skin
  - makes sure that folder is on Python's path at Maya start (this version's userSetup.py);
  - puts one Onion button on the shelf you have open (an older one is replaced, not doubled);
  - loads the new code and opens the window.
Dragging a newer zip's drag_to_maya.mel updates it the same way. Your settings are kept.
"""

import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel

PACKAGE = "onion_skin"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".ruff_cache")
MARKER = "# Onion Skin path (added by the Onion Skin installer)"
BUTTON = "onionSkinShelfButton"


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def _close_window():
    try:
        mod = sys.modules.get(PACKAGE + ".ui")
        w = mod.WINDOW.get("w") if mod else None
        if w is not None:
            w.close()
    except Exception:
        pass


def _ensure_user_setup(version_scripts, shared):
    path = os.path.join(version_scripts, "userSetup.py")
    text = ""
    if os.path.isfile(path):
        with open(path, "r") as f:
            text = f.read()
    if MARKER in text or ('"%s"' % shared) in text:
        return False
    block = ("\n%s\nimport sys as _os_sys\nif r\"%s\" not in _os_sys.path:\n"
             "    _os_sys.path.append(r\"%s\")\n" % (MARKER, shared, shared))
    if not os.path.isdir(version_scripts):
        os.makedirs(version_scripts)
    with open(path, "a") as f:
        f.write(block)
    return True


def _shelf_button():
    """One Onion button on the shelf you have open; old ones (any shelf) go first."""
    top = mel.eval("$onionSkinTmp = $gShelfTopLevel")
    for shelf in cmds.tabLayout(top, query=True, childArray=True) or []:
        for b in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
            try:
                if cmds.objectTypeUI(b) != "shelfButton":
                    continue
                cmd = cmds.shelfButton(b, query=True, command=True) or ""
                if "onion_skin" in cmd or cmds.shelfButton(b, query=True, label=True) == "Onion":
                    cmds.deleteUI(b)
            except RuntimeError:
                pass
    current = cmds.tabLayout(top, query=True, selectTab=True)
    cmds.shelfButton(BUTTON, parent=current, label="Onion",
                     annotation="Onion Skin: 3D ghosts of the past / next keys",
                     image="pythonFamily.png", imageOverlayLabel="Onion", sourceType="python",
                     command="import onion_skin\nonion_skin.show()")
    try:
        mel.eval("saveAllShelves $gShelfTopLevel")
    except RuntimeError:
        pass
    return current


def install(source_dir):
    src = os.path.join(source_dir, PACKAGE)
    if not os.path.isfile(os.path.join(src, "__init__.py")):
        cmds.error("Onion Skin installer: no '%s' folder next to drag_to_maya.mel (%s)." % (PACKAGE, source_dir))
    shared = os.path.normpath(os.path.join(cmds.internalVar(userAppDir=True), "scripts"))
    version_scripts = os.path.normpath(cmds.internalVar(userScriptDir=True))
    dest = os.path.join(shared, PACKAGE)

    _close_window()
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
    import onion_skin
    shelf = _shelf_button()
    onion_skin.show()
    msg = "Onion Skin %s installed in %s - Onion button on the '%s' shelf." % (onion_skin.__version__, dest, shelf)
    print(msg)
    cmds.inViewMessage(amg=msg, pos="topCenter", fade=True)
    return dest
