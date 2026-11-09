"""
Install a Gus_Rigtool update from its zip, inside Maya: no unzipping, no drag and drop, no code to paste.

    from gus_rigtool.core import updater; updater.install_dialog()

The zip's gus_rigtool folder is copied over the installed one (the old one is kept as
gus_rigtool_backup next to it), then Gus_Rigtool restarts fresh and says which version is running.
"""

import os
import re
import shutil
import sys
import tempfile
import zipfile

import gus_rigtool

TOOL = "Update"
SKIP = ("tests/", "__pycache__/")


def _prefix_and_version(zf):
    """(folder inside the zip that holds gus_rigtool/, version written in its __init__.py)."""
    for name in zf.namelist():
        norm = name.replace("\\", "/")
        if norm.endswith("gus_rigtool/__init__.py"):
            prefix = norm[:-len("__init__.py")]
            text = zf.read(name).decode("utf-8", "replace")
            m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
            return prefix, (m.group(1) if m else "?")
    raise RuntimeError("this zip has no gus_rigtool folder - is it a Gus_Rigtool install zip?")


def zip_version(path):
    with zipfile.ZipFile(path) as zf:
        return _prefix_and_version(zf)[1]


def _key(v):
    return [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v)]


def install(path):
    """Copy the zip's gus_rigtool over the installed one. Returns (old version, new version, backup folder)."""
    if not os.path.isfile(path):
        raise RuntimeError("file not found: %s" % path)
    target = gus_rigtool.ROOT
    parent = os.path.dirname(target)
    backup = os.path.join(parent, "gus_rigtool_backup")
    with zipfile.ZipFile(path) as zf:
        prefix, new = _prefix_and_version(zf)
        stage = tempfile.mkdtemp(prefix="gus_rigtool_update_")
        try:
            for name in zf.namelist():
                norm = name.replace("\\", "/")
                if not norm.startswith(prefix) or norm.endswith("/"):
                    continue
                rel = norm[len(prefix):]
                if not rel or any(rel.startswith(s) or ("/" + s) in rel for s in SKIP) or ".." in rel.split("/"):
                    continue
                dst = os.path.join(stage, *rel.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(name) as src, open(dst, "wb") as out:
                    shutil.copyfileobj(src, out)
            if os.path.isdir(backup):
                shutil.rmtree(backup, ignore_errors=True)
            shutil.copytree(target, backup, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(stage, target, dirs_exist_ok=True)
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    for root, dirs, _files in os.walk(target):                    # old compiled files must not win
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
    update_animtool(target)
    return gus_rigtool.__version__, new, backup


def update_animtool(rigtool_root):
    """Gus Animtool installed in maya/scripts (Build > 5) gets the copy that came with this Gus_Rigtool
    (your naming in its defaults.json stays). Returns the folder updated, or None."""
    import importlib.util
    src = os.path.join(rigtool_root, "anim", "gus_animtool")
    try:
        spec = importlib.util.find_spec("gus_animtool")
    except (ImportError, ValueError):
        spec = None
    if not spec or not spec.origin or not os.path.isdir(src):
        return None
    dst = os.path.dirname(spec.origin)
    if os.path.abspath(dst).startswith(os.path.abspath(rigtool_root)):
        return None
    keep = os.path.join(dst, "defaults.json")
    saved = open(keep).read() if os.path.isfile(keep) else None
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    if saved is not None:
        with open(keep, "w") as f:
            f.write(saved)
    shim = os.path.join(rigtool_root, "anim", "gus_anim.py")
    if os.path.isfile(shim):
        shutil.copy2(shim, os.path.join(os.path.dirname(dst), "gus_anim.py"))
    for m in [m for m in sys.modules if m.startswith("gus_animtool") or m == "gus_anim"]:
        sys.modules.pop(m, None)
    return dst


def restart():
    """Close the windows, forget every loaded Gus_Rigtool module and open the main window again."""
    import maya.cmds as cmds
    try:
        from gus_rigtool.core import ui
        ui.close_all()
    except Exception:
        pass
    for m in [m for m in sys.modules if m == "gus_rigtool" or m.startswith("gus_rigtool.")]:
        sys.modules.pop(m, None)
    cmds.evalDeferred("import gus_rigtool, gus_rigtool.main as _gr; _gr.show(); "
                      "print('Gus_Rigtool %s is running.' % gus_rigtool.__version__)")


def install_dialog(*_):
    import maya.cmds as cmds
    got = cmds.fileDialog2(fileFilter="Gus_Rigtool zip (*.zip)", dialogStyle=2, fileMode=1,
                           caption="Pick the newest Gus_Rigtool zip (sort Downloads by date)")
    if not got:
        return None
    path = got[0]
    new = zip_version(path)
    old = gus_rigtool.__version__
    msg = "Installed now: %s\nIn this zip: %s" % (old, new)
    if _key(new) < _key(old):
        msg += "\n\nThis zip is OLDER than what you have."
    elif new == old:
        msg += "\n\nSame version (reinstall)."
    if cmds.confirmDialog(title="Gus_Rigtool update", message=msg + "\n\nInstall it? (Gus_Rigtool restarts.)",
                          button=["Install", "Cancel"], defaultButton="Install", cancelButton="Cancel",
                          dismissString="Cancel") != "Install":
        return None
    old, new, backup = install(path)
    cmds.confirmDialog(title="Gus_Rigtool update",
                       message="Gus_Rigtool %s installed (was %s).\nThe old files are in:\n%s\n\nIt restarts now."
                               % (new, old, backup), button=["OK"])
    restart()
    return new
