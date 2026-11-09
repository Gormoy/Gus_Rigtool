"""
Crash backup: every few minutes, if the scene changed, a copy is saved to a backup folder (the scene you work on
is untouched - same name, same 'not saved' state). The last few copies of each scene are kept. Recover lists them
by time; open one to get your work back after a crash.

Off until you turn it on (Settings). Folder: <maya>/gus_anim_backups/<scene name>/
"""

import os
import time

import maya.cmds as cmds

from gus_animtool import anim as A

_state = {"timer": None, "job": None, "last": 0.0}


def root():
    try:
        base = cmds.internalVar(userAppDir=True)
    except (RuntimeError, AttributeError):
        base = os.path.expanduser("~")
    return os.path.join(base, "gus_anim_backups")


def _scene():
    path = cmds.file(query=True, sceneName=True) or ""
    return os.path.splitext(os.path.basename(path))[0] or "untitled"


def folder(scene=None):
    p = os.path.join(root(), scene or _scene())
    if not os.path.isdir(p):
        os.makedirs(p)
    return p


def backup_now(force=False):
    """Save a copy now (only when the scene changed, unless force). Returns the file, or None."""
    try:
        changed = cmds.file(query=True, modified=True)
    except RuntimeError:
        changed = True
    if not changed and not force:
        return None
    path = os.path.join(folder(), "%s_%s.ma" % (_scene(), time.strftime("%Y%m%d_%H%M%S")))
    cmds.file(path, exportAll=True, type="mayaAscii", force=True, preserveReferences=True)
    _prune()
    _state["last"] = time.time()
    return path


def _prune(scene=None):
    keep = max(1, int(A.opt("backup_keep", 5)))
    files = backups(scene)
    for p, _t in files[keep:]:
        try:
            os.remove(p)
        except OSError:
            pass


def backups(scene=None):
    """[(file, saved time)] newest first, of this scene (or every scene: scene='*')."""
    out = []
    if scene == "*":
        folders = [os.path.join(root(), d) for d in os.listdir(root())] if os.path.isdir(root()) else []
    else:
        folders = [folder(scene)]
    for d in folders:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith((".ma", ".mb")):
                p = os.path.join(d, f)
                out.append((p, os.path.getmtime(p)))
    return sorted(out, key=lambda x: -x[1])


def _tick(*_):
    minutes = max(1, int(A.opt("backup_minutes", 5)))
    if time.time() - _state["last"] < minutes * 60:
        return
    _state["last"] = time.time()
    try:
        got = backup_now()
        if got:
            print("Gus Animtool: backup saved - %s" % got)
    except Exception as e:                                  # a backup must never get in the way
        print("Gus Animtool: backup skipped (%s)" % e)


def start():
    """Start the timer (a Qt timer when there's Qt, else an idle check). Returns True."""
    stop()
    _state["last"] = time.time()
    try:
        try:
            from PySide6 import QtCore
        except ImportError:
            from PySide2 import QtCore
        t = QtCore.QTimer()
        t.setInterval(30 * 1000)                            # checks every 30 s, saves every N minutes
        t.timeout.connect(_tick)
        t.start()
        _state["timer"] = t
    except Exception:
        _state["job"] = cmds.scriptJob(idleEvent=_tick)
    return True


def stop():
    if _state.get("timer") is not None:
        try:
            _state["timer"].stop()
        except Exception:
            pass
        _state["timer"] = None
    if _state.get("job"):
        try:
            cmds.scriptJob(kill=_state["job"], force=True)
        except RuntimeError:
            pass
        _state["job"] = None
    return True


def running():
    return _state.get("timer") is not None or bool(_state.get("job"))


def ensure():
    """On when the setting says so (called when Gus Animtool opens)."""
    if A.opt("backup_on", 0) and not running():
        start()
    return running()


# ---------------------------------------------------------------------------
# recover window
# ---------------------------------------------------------------------------

WIN = "gusAnimtoolRecoverWin"


def show_recover(*_):
    files = backups("*")
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)
    cmds.window(WIN, title="Gus Animtool - Recover a backup", widthHeight=(520, 360))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4, columnAttach=("both", 6))
    cmds.text(label="Backups, newest first (folder: %s)" % root(), align="left")
    lst = cmds.textScrollList(height=240, allowMultiSelection=False)
    for p, t in files:
        cmds.textScrollList(lst, edit=True, append="%s   %s" % (time.strftime("%Y-%m-%d %H:%M", time.localtime(t)),
                                                             os.path.basename(p)))

    def open_it(*_):
        i = (cmds.textScrollList(lst, query=True, selectIndexedItem=True) or [0])[0]
        if not i:
            raise RuntimeError("pick a backup.")
        path = files[i - 1][0]
        if cmds.confirmDialog(title="Open backup", message="Open %s?\n(Maya asks to save the current scene "
                              "first.)" % os.path.basename(path), button=["Open", "Cancel"], defaultButton="Open",
                              cancelButton="Cancel", dismissString="Cancel") != "Open":
            return
        import maya.mel as mel
        if mel.eval('saveChanges("")'):
            cmds.file(path, open=True, force=True)
            cmds.deleteUI(WIN)
    A._buttons([("Open the picked backup", open_it, "Open it (you can Save As where you want)."),
                ("Save a backup now", lambda *_: A.message("backup: %s" % backup_now(force=True)), "Right now.")])
    cmds.showWindow(WIN)
    return WIN
