"""
Safer updates (5.7.12, Gus: "make sure everything won't crash as soon as we update it"):

  check_folder   before installing: every file there and readable by Python, the version known
  keep           the version you had is kept (the last KEEP of each tool) in maya/scripts/gus_versions
  swap_in        the new version copied next to the old one first, then switched over (never half installed)
  go_back        back to a kept version (Settings > Update > Go back..., or the line to paste below)
  self_check     the first time a new version opens: every file of it loads, else you're offered Go back

It uses only Python's own library (and Maya's cmds for the questions), so it works for Gus_Rigtool, Gus Animtool
and an animator's copy alike, and a copy of it is kept in gus_versions - the paste line works even if a new
version can't load at all:

    g = {}; exec(open(__import__("os").path.expanduser(
        "~/Library/Preferences/Autodesk/maya/scripts/gus_versions/versions.py")).read(), g); g["go_back_dialog"]()
"""

import os
import re
import shutil
import sys

KEEP = 2                                     # Gus: keep the last two versions
STORE = "gus_versions"
SKIP = ("__pycache__", ".DS_Store", "tests", ".ruff_cache")


def _key(v):
    return [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v or "")]


def version_of(folder):
    """The __version__ written in a package folder's __init__.py, or None."""
    try:
        with open(os.path.join(folder, "__init__.py")) as f:
            m = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
        return m.group(1) if m else None
    except (IOError, OSError):
        return None


def check_folder(folder, need=()):
    """Problems with a package folder about to be installed: no version, a file Python can't read, a file
    missing (need: paths relative to the folder). [] = fine. Only reads (nothing written)."""
    problems = []
    if not os.path.isfile(os.path.join(folder, "__init__.py")):
        return ["no __init__.py in %s" % folder]
    if not version_of(folder):
        problems.append("no version in %s" % os.path.join(folder, "__init__.py"))
    for rel in need:
        if not os.path.exists(os.path.join(folder, rel)):
            problems.append("missing: %s" % rel)
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    with open(path, "rb") as fh:
                        compile(fh.read(), path, "exec")
                except Exception as e:
                    problems.append("%s: %s" % (os.path.relpath(path, folder), str(e).splitlines()[-1]))
    return problems


def store_of(dest):
    """maya/scripts/gus_versions, next to the installed package."""
    return os.path.join(os.path.dirname(os.path.abspath(dest)), STORE)


def kept(dest, package):
    """[(version, folder)] kept for this package, newest first."""
    store = store_of(dest)
    out = []
    try:
        names = os.listdir(store)
    except OSError:
        return out
    for n in names:
        if n.startswith(package + "_") and os.path.isdir(os.path.join(store, n)):
            v = n[len(package) + 1:]
            out.append((v, os.path.join(store, n)))
    return sorted(out, key=lambda x: _key(x[0]), reverse=True)


def keep(dest, package, keep_n=KEEP):
    """The installed version copied into gus_versions (the oldest beyond keep_n removed). Returns its folder,
    or None (nothing installed there yet). A copy of this file goes there too (for the paste line)."""
    version = version_of(dest)
    if not version:
        return None
    store = store_of(dest)
    if not os.path.isdir(store):
        os.makedirs(store)
    to = os.path.join(store, "%s_%s" % (package, version))
    if os.path.isdir(to):
        shutil.rmtree(to, ignore_errors=True)
    shutil.copytree(dest, to, ignore=shutil.ignore_patterns(*SKIP))
    for _v, folder in kept(dest, package)[keep_n:]:
        shutil.rmtree(folder, ignore_errors=True)
    save_self(store)
    return to


def save_self(store):
    try:
        here = os.path.abspath(__file__)
        if here.endswith(".pyc"):
            here = here[:-1]
        if os.path.isfile(here) and os.path.abspath(os.path.dirname(here)) != os.path.abspath(store):
            shutil.copy2(here, os.path.join(store, "versions.py"))
    except (IOError, OSError, NameError):
        pass


def swap_in(src, dest, keep_files=()):
    """src copied next to dest first (dest + '_incoming'), the files in keep_files (relative, e.g. your
    defaults.json, the data folder) carried over from the old one, then switched over: the old one renamed away,
    the new one in its place, the old one removed. A failure before the switch leaves the old one untouched."""
    dest = os.path.abspath(dest)
    incoming, outgoing = dest + "_incoming", dest + "_outgoing"
    for d in (incoming, outgoing):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(src, incoming, ignore=shutil.ignore_patterns(*SKIP))
    for rel in keep_files:
        old = os.path.join(dest, rel)
        new = os.path.join(incoming, rel)
        if os.path.isdir(old) and not os.path.exists(new):
            shutil.copytree(old, new)
        elif os.path.isdir(old):
            for root, _dirs, files in os.walk(old):
                for f in files:
                    o = os.path.join(root, f)
                    n = os.path.join(new, os.path.relpath(o, old))
                    if not os.path.exists(n):
                        if not os.path.isdir(os.path.dirname(n)):
                            os.makedirs(os.path.dirname(n))
                        shutil.copy2(o, n)
        elif os.path.isfile(old):
            if not os.path.isdir(os.path.dirname(new)):
                os.makedirs(os.path.dirname(new))
            shutil.copy2(old, new)
    if os.path.isdir(dest):
        os.rename(dest, outgoing)
    try:
        os.rename(incoming, dest)
    except OSError:
        if os.path.isdir(outgoing) and not os.path.isdir(dest):
            os.rename(outgoing, dest)                    # put the old one back
        raise
    shutil.rmtree(outgoing, ignore_errors=True)
    return dest


def go_back(dest, package, version, keep_files=()):
    """dest back to a kept version (the one installed now is kept first). Returns (from, to)."""
    folders = dict(kept(dest, package))
    if version not in folders:
        raise RuntimeError("%s %s isn't kept (kept: %s)" % (package, version, ", ".join(folders) or "none"))
    now = version_of(dest)
    src = folders[version]
    if now and now != version:
        keep(dest, package, KEEP + 1)                   # now kept too (one more for a moment: the one we go to)
        folders = dict(kept(dest, package))
        src = folders.get(version, src)
    swap_in(src, dest, keep_files)
    shutil.rmtree(src, ignore_errors=True)               # it's the installed one now (kept again at the next update)
    for _v, folder in kept(dest, package)[KEEP:]:
        shutil.rmtree(folder, ignore_errors=True)
    return now, version


def installed(package):
    """Where a package is installed, found the way Maya would (sys.path), without loading it."""
    for p in sys.path:
        d = os.path.join(p, package)
        if os.path.isfile(os.path.join(d, "__init__.py")):
            return d
    return None


KEEP_FILES = {"gus_rigtool": ("data",), "gus_animtool": ("defaults.json",)}


def go_back_dialog(*_):
    """Settings > Update > Go back... (or the paste line): pick a kept version of either tool, then restart Maya."""
    import maya.cmds as cmds
    choices = []
    for package in ("gus_rigtool", "gus_animtool"):
        dest = installed(package)
        if not dest:
            continue
        for v, _f in kept(dest, package):
            choices.append((package, dest, v, "%s %s (now %s)" % (package, v, version_of(dest) or "?")))
    if not choices:
        cmds.confirmDialog(title="Go back", message="No earlier version is kept yet (they're kept from 5.7.12 on, "
                           "each time you update).", button=["OK"])
        return None
    labels = [c[3] for c in choices[:6]]
    got = cmds.confirmDialog(title="Go back to an earlier version", message="Which one? (Your settings, saved "
                             "shapes and naming stay. Restart Maya after.)", button=labels + ["Cancel"],
                             defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel")
    for package, dest, v, label in choices:
        if label == got:
            was, now = go_back(dest, package, v, KEEP_FILES.get(package, ()))
            cmds.confirmDialog(title="Go back", message="%s is back to %s (was %s).\n\nRestart Maya now." % (
                package, now, was), button=["OK"])
            return package, now
    return None


# --------------------------------------------------------------------------- the first open of a new version
def _mark(dest, name):
    """The 'this version was checked' note: in Maya's prefs folder (gus_safe_start, with safe start's notes) -
    never inside the tools' folders."""
    base = None
    try:
        import maya.cmds as cmds
        base = cmds.internalVar(userPrefDir=True)
    except Exception:
        base = None
    import tempfile
    return os.path.join(base or tempfile.gettempdir(), "gus_safe_start", "%s_checked.txt" % name)


def self_check(package_dir, import_name):
    """Every module of the package loads. [] = fine, else ['module (error)']."""
    import importlib
    bad = []
    for root, dirs, files in os.walk(package_dir):
        dirs[:] = [d for d in dirs if d not in SKIP + ("realmaya",)]
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(root, f), package_dir)[:-3].replace(os.sep, ".")
            if rel.startswith("anim.") or rel == "install":   # (Gus_Rigtool's copy of the Animtool: checked by it)
                continue
            mod = import_name if rel == "__init__" else "%s.%s" % (import_name, rel)
            mod = mod[:-len(".__init__")] if mod.endswith(".__init__") else mod
            try:
                importlib.import_module(mod)
            except Exception as e:
                bad.append("%s (%s: %s)" % (mod, type(e).__name__, e))
    return bad


def first_open(name, package_dir, import_name, package, title, installed_dir=None):
    """Run once per new version, before its window opens: every module loads? If not, you're offered Go back.
    installed_dir: your installed copy (where the kept versions are), when another copy runs (the Animtool running
    Gus_Rigtool's newer one). Returns True to go on opening, False when you went back (restart Maya)."""
    home = installed_dir or package_dir
    version = version_of(package_dir)
    mark = _mark(home, name)
    try:
        with open(mark) as f:
            if f.read().strip() == version:
                return True
    except (IOError, OSError):
        pass
    bad = self_check(package_dir, import_name)
    try:
        if not os.path.isdir(os.path.dirname(mark)):
            os.makedirs(os.path.dirname(mark))
        with open(mark, "w") as f:
            f.write(version or "")
            f.flush()
            os.fsync(f.fileno())
    except (IOError, OSError):
        pass
    if not bad:
        return True
    older = [v for v, _f in kept(home, package) if v != version]
    try:
        import maya.cmds as cmds
        buttons = (["Go back to %s" % older[0]] if older else []) + ["Open anyway"]
        got = cmds.confirmDialog(title=title, message="%s %s: %d file(s) don't load:\n\n%s%s" % (
            title, version, len(bad), "\n".join(bad[:6]), "\n..." if len(bad) > 6 else ""), button=buttons,
            defaultButton=buttons[0], cancelButton="Open anyway", dismissString="Open anyway")
    except Exception:
        return True
    if older and got == buttons[0]:
        go_back(home, package, older[0], KEEP_FILES.get(package, ()))
        cmds.confirmDialog(title=title, message="Back to %s. Restart Maya now." % older[0], button=["OK"])
        return False
    return True
