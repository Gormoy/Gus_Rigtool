"""
(noPyMEL copy) Installer - run by drag_to_maya.mel (drag that file into Maya's viewport). It:
  - closes the onion skin window if it's open;
  - copies onionSkinRenderer into the shared Maya scripts folder (every Maya version uses it):
        Windows  Documents/maya/scripts/onionSkinRenderer
        Mac      ~/Library/Preferences/Autodesk/maya/scripts/onionSkinRenderer
  - keeps your saved settings (settings made before this version get the new defaults once: in front of the
    character, past / next keys, blue / orange);
  - makes sure that folder is on Python's path at Maya start (userSetup.py);
  - puts one Onion button on the shelf you have open (an older one is replaced, not doubled);
  - opens the window. Dragging a newer zip's drag_to_maya.mel updates it the same way.
"""

import json
import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel

PACKAGE = "onionSkinRenderer"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".ruff_cache")
MARKER = "# Onion skin renderer path (added by its installer)"
BUTTON = "onionSkinRendererShelfButton"
SETTINGS_VERSION = 2
OLD_PATHS = ("onionSkinRenderer-master", "onionSkinRenderer-noPyMEL")

BUTTON_COMMAND = "\n".join([
    "import sys",
    "for _p in [p for p in sys.path if %r in p or %r in p]:" % OLD_PATHS,
    "    sys.path.remove(_p)",
    "import onionSkinRenderer.controller as _osr_ctl",
    "_osr_ctl.show()",
])


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def _close_window():
    try:
        mod = sys.modules.get(PACKAGE + ".controller")
        if mod and getattr(mod, "OSR_WINDOW", None) is not None:
            mod.OSR_WINDOW.close()
    except Exception:
        pass


def _old_settings(dest):
    path = os.path.join(dest, "settings.txt")
    try:
        with open(path) as f:
            data = json.load(f)
        return data if data.get("settingsVersion", 0) >= SETTINGS_VERSION else None
    except (IOError, OSError, ValueError):
        return None


def _ensure_user_setup(version_scripts, shared):
    path = os.path.join(version_scripts, "userSetup.py")
    text = ""
    if os.path.isfile(path):
        with open(path, "r") as f:
            text = f.read()
    if MARKER in text or ('"%s"' % shared) in text:
        return False
    block = ("\n%s\nimport sys as _osr_sys\nif r\"%s\" not in _osr_sys.path:\n"
             "    _osr_sys.path.append(r\"%s\")\n" % (MARKER, shared, shared))
    if not os.path.isdir(version_scripts):
        os.makedirs(version_scripts)
    with open(path, "a") as f:
        f.write(block)
    return True


def _shelf_button():
    top = mel.eval("$osrShelfTmp = $gShelfTopLevel")
    for shelf in cmds.tabLayout(top, query=True, childArray=True) or []:
        for b in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
            try:
                if cmds.objectTypeUI(b) != "shelfButton":
                    continue
                cmd = cmds.shelfButton(b, query=True, command=True) or ""
                if "onionSkinRenderer" in cmd or "onion_skin" in cmd or \
                        cmds.shelfButton(b, query=True, label=True) == "Onion":
                    cmds.deleteUI(b)
            except RuntimeError:
                pass
    current = cmds.tabLayout(top, query=True, selectTab=True)
    cmds.shelfButton(BUTTON, parent=current, label="Onion", annotation="Onion skin (in front, past / next keys)",
                     image="pythonFamily.png", imageOverlayLabel="Onion", sourceType="python",
                     command=BUTTON_COMMAND)
    try:
        mel.eval("saveAllShelves $gShelfTopLevel")
    except RuntimeError:
        pass
    return current


HOTKEYS = (("OnionSkin_Toggle", "Onion skin on / off in the viewport you clicked", "hk_toggle"),
           ("OnionSkin_Fill", "Onion skin: fill the ghosts now", "hk_fill"),
           ("OnionSkin_NextKey", "Onion skin: go to the next key of the onion characters", "hk_next_key"),
           ("OnionSkin_PreviousKey", "Onion skin: go to the previous key of the onion characters", "hk_previous_key"),
           ("OnionSkin_ToggleArcs", "Onion skin: show / hide the arcs", "hk_toggle_arcs"))


def _hotkey_commands():
    """Runtime commands to put on keys (Hotkey Editor > Custom Scripts). Made again on every install."""
    made = []
    for name, note, fn in HOTKEYS:
        code = "import onionSkinRenderer.controller as _osr_c\n_osr_c.%s()" % fn
        try:
            if cmds.runTimeCommand(name, exists=True):
                cmds.runTimeCommand(name, edit=True, delete=True)
            cmds.runTimeCommand(name, annotation=note, category="Custom Scripts", commandLanguage="python",
                                command=code)
            made.append(name)
        except RuntimeError:
            pass
    return made


def install(source_dir):
    src = os.path.join(source_dir, PACKAGE)
    if not os.path.isfile(os.path.join(src, "__init__.py")):
        cmds.error("Onion skin installer: no '%s' folder next to drag_to_maya.mel (%s)." % (PACKAGE, source_dir))
    shared = os.path.normpath(os.path.join(cmds.internalVar(userAppDir=True), "scripts"))
    version_scripts = os.path.normpath(cmds.internalVar(userScriptDir=True))
    dest = os.path.join(shared, PACKAGE)

    _close_window()
    kept = None
    if _norm(src) != _norm(dest):
        kept = _old_settings(dest)
        if not os.path.isdir(shared):
            os.makedirs(shared)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=IGNORE)
        if kept:
            with open(os.path.join(dest, "settings.txt"), "w") as f:
                json.dump(kept, f)
    for p in [p for p in sys.path if any(o in p for o in OLD_PATHS)]:
        sys.path.remove(p)
    if _norm(shared) not in [_norm(p) for p in sys.path]:
        sys.path.insert(0, shared)
    _ensure_user_setup(version_scripts, shared)

    for name in [m for m in sys.modules if m == PACKAGE or m.startswith(PACKAGE + ".")]:
        del sys.modules[name]
    shelf = _shelf_button()
    keys = _hotkey_commands()
    import onionSkinRenderer.controller as ctl
    ctl.show()
    msg = "Onion skin installed in %s - Onion button on the '%s' shelf%s; %d hotkey command(s) ready." % (
        dest, shelf, " (your settings kept)" if kept else "", len(keys))
    print(msg)
    try:
        cmds.inViewMessage(amg=msg, pos="topCenter", fade=True)
    except RuntimeError:
        pass
    return dest
