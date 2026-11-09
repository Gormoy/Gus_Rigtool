"""
Install a Gus Animtool update from its zip, inside Maya (Update... in the window): the zip's gus_animtool
folder is copied over the installed one (the old one is kept as gus_animtool_backup next to it), then the
window opens again with the new version. Works with a Gus_Animtool zip or a Gus_Rigtool zip (which carries
Gus Animtool too).
"""

import os
import re
import shutil
import sys
import tempfile
import zipfile

import gus_animtool

PACKAGE = "gus_animtool/"


def _prefix_and_version(zf):
    for name in zf.namelist():
        norm = name.replace("\\", "/")
        if norm.endswith(PACKAGE + "__init__.py"):
            prefix = norm[:-len("__init__.py")]
            text = zf.read(name).decode("utf-8", "replace")
            m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
            return prefix, (m.group(1) if m else "?")
    raise RuntimeError("this zip has no gus_animtool folder - is it a Gus Animtool (or Gus_Rigtool) zip?")


def zip_version(path):
    with zipfile.ZipFile(path) as zf:
        return _prefix_and_version(zf)[1]


def _key(v):
    return [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v)]


def install(path):
    """Copy the zip's gus_animtool over the installed one. Returns (old version, new version, backup folder)."""
    if not os.path.isfile(path):
        raise RuntimeError("file not found: %s" % path)
    target = gus_animtool.ROOT
    parent = os.path.dirname(target)
    backup = os.path.join(parent, "gus_animtool_backup")
    with zipfile.ZipFile(path) as zf:
        prefix, new = _prefix_and_version(zf)
        shim = prefix[:-len(PACKAGE)] + "gus_anim.py"
        stage = tempfile.mkdtemp(prefix="gus_animtool_update_")
        try:
            for name in zf.namelist():
                norm = name.replace("\\", "/")
                if not norm.startswith(prefix) or norm.endswith("/") or "__pycache__/" in norm:
                    continue
                rel = norm[len(prefix):]
                if not rel or ".." in rel.split("/"):
                    continue
                dst = os.path.join(stage, *rel.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(name) as src, open(dst, "wb") as out:
                    shutil.copyfileobj(src, out)
            keep = os.path.join(target, "defaults.json")             # your rig's naming stays
            if os.path.isfile(keep) and not os.path.isfile(os.path.join(stage, "defaults.json")):
                shutil.copy2(keep, os.path.join(stage, "defaults.json"))
            if os.path.isdir(backup):
                shutil.rmtree(backup, ignore_errors=True)
            shutil.copytree(target, backup, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(stage, target, dirs_exist_ok=True)
            if shim in zf.namelist():
                with zf.open(shim) as src, open(os.path.join(parent, "gus_anim.py"), "wb") as out:
                    shutil.copyfileobj(src, out)
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    for root, dirs, _files in os.walk(target):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
    return gus_animtool.__version__, new, backup


def restart():
    import maya.cmds as cmds
    for w in ("gusAnimWorkspace", "gusAnimPickerWorkspace", "gusAnimLibraryWorkspace"):
        try:
            if cmds.workspaceControl(w, exists=True):
                cmds.deleteUI(w)
        except RuntimeError:
            pass
    for m in [m for m in sys.modules if m in ("gus_animtool", "gus_anim") or m.startswith("gus_animtool.")]:
        sys.modules.pop(m, None)
    cmds.evalDeferred("import gus_animtool; gus_animtool.show(); "
                      "print('Gus Animtool %s is running.' % gus_animtool.__version__)")


def install_dialog(*_):
    import maya.cmds as cmds
    got = cmds.fileDialog2(fileFilter="Gus Animtool / Gus_Rigtool zip (*.zip)", dialogStyle=2, fileMode=1,
                           caption="Pick the newest Gus Animtool zip (sort Downloads by date)")
    if not got:
        return None
    path = got[0]
    new = zip_version(path)
    old = gus_animtool.__version__
    msg = "Installed now: %s\nIn this zip: %s" % (old, new)
    if _key(new) < _key(old):
        msg += "\n\nThis zip is OLDER than what you have."
    elif new == old:
        msg += "\n\nSame version (reinstall)."
    if cmds.confirmDialog(title="Gus Animtool update", message=msg + "\n\nInstall it? (Gus Animtool restarts.)",
                          button=["Install", "Cancel"], defaultButton="Install", cancelButton="Cancel",
                          dismissString="Cancel") != "Install":
        return None
    old, new, backup = install(path)
    cmds.confirmDialog(title="Gus Animtool update", message="Gus Animtool %s installed (was %s).\nThe old files "
                       "are in:\n%s\n\nIt restarts now." % (new, old, backup), button=["OK"])
    restart()
    return new
