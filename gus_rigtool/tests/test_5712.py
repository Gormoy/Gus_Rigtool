# 5.7.12: updates you can undo (Gus: keep the last two versions). The zip / folder checked before installing; the
# version you had kept in maya/scripts/gus_versions (the last 2 of each tool); the new one copied next to the old
# then switched over (never half installed; your data / naming carried over); Go back to a kept version; the first
# open of a new version loads every file, else offers Go back. Done on real folders here.
import os, sys, shutil, tempfile
exec(open("fakemaya.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ROOT = os.path.join(os.getcwd(), "..")
sys.path.insert(0, os.path.join(ROOT, "anim"))
sys.path.insert(0, os.path.join(ROOT, ".."))
from gus_animtool import versions as V

TMP = tempfile.mkdtemp(prefix="gus_versions_test_")
SCRIPTS = os.path.join(TMP, "scripts")
os.makedirs(SCRIPTS)


def package(where, version, extra=None):
    os.makedirs(where)
    with open(os.path.join(where, "__init__.py"), "w") as f:
        f.write('__version__ = "%s"\n' % version)
    with open(os.path.join(where, "main.py"), "w") as f:
        f.write("X = %r\n" % version)
    for rel, text in (extra or {}).items():
        p = os.path.join(where, rel)
        if not os.path.isdir(os.path.dirname(p)):
            os.makedirs(os.path.dirname(p))
        with open(p, "w") as f:
            f.write(text)
    return where


def main_of(folder):
    return open(os.path.join(folder, "main.py")).read().strip()


# --- 1. the check before installing
good = package(os.path.join(TMP, "new_good", "gusx"), "3.0")
check("a good folder: no problems", V.check_folder(good, ("main.py",)) == [])
bad = package(os.path.join(TMP, "new_bad", "gusx"), "3.0", {"core/broken.py": "def x(:\n"})
got = V.check_folder(bad, ("main.py", "registry.py"))
check("a broken file and a missing one: both named", any("broken.py" in p for p in got) and
      "missing: registry.py" in got)
nover = package(os.path.join(TMP, "new_nover", "gusx"), "")
check("no version: said", any("no version" in p for p in V.check_folder(nover)))
check("...it only reads: nothing written next to the files (no __pycache__)",
      not any("__pycache__" in d for _r, ds, _f in os.walk(bad) for d in ds))

# --- 2. keep the version you had (the last 2)
dest = package(os.path.join(SCRIPTS, "gusx"), "1.0", {"defaults.json": "MY NAMING", "data/shapes/a.json": "A"})
k1 = V.keep(dest, "gusx")
check("the version you had is kept in maya/scripts/gus_versions", k1 == os.path.join(SCRIPTS, "gus_versions",
                                                                                     "gusx_1.0") and
      main_of(k1) == "X = '1.0'")
check("...with a copy of the version keeper itself (the paste line works even if a version can't load)",
      os.path.isfile(os.path.join(SCRIPTS, "gus_versions", "versions.py")))
for v in ("1.5", "2.0"):
    shutil.rmtree(dest); package(dest, v, {"defaults.json": "MY NAMING", "data/shapes/a.json": "A"})
    V.keep(dest, "gusx")
check("only the last 2 are kept (the oldest goes)", [v for v, _f in V.kept(dest, "gusx")] == ["2.0", "1.5"])

# --- 3. switched over: never half installed, yours carried over
V.swap_in(good, dest, keep_files=("defaults.json", "data"))
check("the new one in place", main_of(dest) == "X = '3.0'" and V.version_of(dest) == "3.0")
check("...your naming (defaults.json) and your data folder carried over",
      open(os.path.join(dest, "defaults.json")).read() == "MY NAMING" and
      os.path.isfile(os.path.join(dest, "data", "shapes", "a.json")))
check("...nothing left beside it (no _incoming / _outgoing)", sorted(os.listdir(SCRIPTS)) == ["gus_versions", "gusx"])
real_rename = os.rename
def failing(a, b):
    if a.endswith("_incoming"):
        raise OSError("disk full")
    return real_rename(a, b)
with mock.patch.object(os, "rename", failing):
    try:
        V.swap_in(package(os.path.join(TMP, "new4", "gusx"), "4.0"), dest); err = ""
    except OSError as e:
        err = str(e)
check("the switch fails half way: the old one is put back, untouched", err == "disk full" and
      main_of(dest) == "X = '3.0'")

# --- 4. Go back
was, now = V.go_back(dest, "gusx", "1.5", keep_files=("defaults.json", "data"))
check("Go back to 1.5: it's in place, your naming still yours", (was, now) == ("3.0", "1.5") and
      main_of(dest) == "X = '1.5'" and open(os.path.join(dest, "defaults.json")).read() == "MY NAMING")
check("...the one you left (3.0) is kept, so you can return to it; still 2 kept",
      [v for v, _f in V.kept(dest, "gusx")][:1] == ["3.0"] and len(V.kept(dest, "gusx")) == 2)
try:
    V.go_back(dest, "gusx", "0.1"); msg = ""
except RuntimeError as e:
    msg = str(e)
check("a version that isn't kept: says which are", "isn't kept" in msg and "3.0" in msg)

# --- 5. the first open of a new version
pkgdir = package(os.path.join(TMP, "site", "gusy"), "5.0", {"good.py": "A = 1\n", "bad.py": "import no_such_mod\n",
                                                             "anim/skip.py": "import no_such_mod\n"})
sys.path.insert(0, os.path.join(TMP, "site"))
V.keep(pkgdir, "gusy")                                        # (a 5.0 kept - pretend an older one)
os.rename(os.path.join(TMP, "site", "gus_versions", "gusy_5.0"), os.path.join(TMP, "site", "gus_versions", "gusy_4.0"))
open(os.path.join(TMP, "site", "gus_versions", "gusy_4.0", "__init__.py"), "w").write('__version__ = "4.0"\n')
os.remove(os.path.join(TMP, "site", "gus_versions", "gusy_4.0", "bad.py"))     # 4.0: every file loads
bad_mods = V.self_check(pkgdir, "gusy")
check("self-check: the file that doesn't load is named (Gus_Rigtool's Animtool copy skipped: it checks itself)",
      len(bad_mods) == 1 and bad_mods[0].startswith("gusy.bad (ModuleNotFoundError"))
asked = []
def answer(*a, **k):
    asked.append(k.get("button")); return k.get("button")[0]
with mock.patch.object(cmds, "confirmDialog", answer, create=True):
    go = V.first_open("gusy", pkgdir, "gusy", "gusy", "Gus Y")
check("a file doesn't load: you're offered Go back to the version before; you take it -> back, don't open",
      asked and asked[0] == ["Go back to 4.0", "Open anyway"] and go is False and V.version_of(pkgdir) == "4.0")
del asked[:]
with mock.patch.object(cmds, "confirmDialog", answer, create=True):
    again = V.first_open("gusy", pkgdir, "gusy", "gusy", "Gus Y")
check("...the version you went back to is checked once too (every file loads: no question)",
      again is True)
with mock.patch.object(V, "self_check", lambda *a: ["should not run"]):
    check("...and once checked, a version isn't checked again (no delay on every open)",
          V.first_open("gusy", pkgdir, "gusy", "gusy", "Gus Y") is True)

# --- 6. wired in: the three ways to update, the buttons, the windows
inst = open(os.path.join(ROOT, "install.py")).read()
check("drag_to_maya: checks first (asks before installing a broken one), keeps yours, switches over (no delete "
      "first)", "V.check_folder(src" in inst and "V.keep(dest, PACKAGE)" in inst and "V.swap_in(src, dest)" in inst
      and "shutil.rmtree(dest)" not in inst)
up = open(os.path.join(ROOT, "core", "updater.py")).read()
check("Gus_Rigtool's Update button: checked, kept, switched over (your data folder carried)",
      "V.check_folder(stage" in up and 'V.keep(target, "gus_rigtool")' in up and
      'V.swap_in(stage, target, keep_files=("data",))' in up)
check("...your own Gus Animtool copy, updated with it: kept, switched over (your naming carried)",
      'V.keep(dst, "gus_animtool")' in up and 'V.swap_in(src, dst, keep_files=("defaults.json",))' in up)
aup = open(os.path.join(ROOT, "anim", "gus_animtool", "updater.py")).read()
check("the Animtool's Update button: checked, kept, switched over", "V.check_folder(stage)" in aup and
      'V.keep(target, "gus_animtool")' in aup and 'keep_files=("defaults.json",)' in aup)
aui = open(os.path.join(ROOT, "anim", "gus_animtool", "ui.py")).read()
st = open(os.path.join(ROOT, "tools", "settings_tab.py")).read()
check("Go back... in both Settings (Update)", '("Go back...", _go_back' in aui and
      '"Go back to an earlier version..."' in st and "V.go_back_dialog" in st)
win = open(os.path.join(ROOT, "newui", "window.py")).read()
check("both windows run the first-open check (not the safe way: that opens only the window)",
      'op.run("first open of this version", _first_open) is False' in aui and
      'op.run("first open of this version", _first_open) is False' in win and
      "installed_dir=gus_animtool.LOCAL_ROOT" in aui)
from gus_rigtool.core import safe_start
check("Gus_Rigtool uses the Animtool's own file (one code)",
      os.path.samefile(safe_start.versions.__file__, V.__file__))
wc = open(os.path.join(ROOT, "realmaya", "window_checks.py")).read()
check("Test this release finds the shelf's open button by what it runs (Gus's older shelf had no 'Main')",
      "cmd.strip().endswith(runs)" in wc and '"gr.show()"' in wc)
mc = open(os.path.join(ROOT, "realmaya", "maya_cases.py")).read()
check("real-Maya case r: keep, switch over, go back on your Mac's disk", "def updates_case" in mc and
      '("r. updates", updates_case)' in mc)
shutil.rmtree(TMP, ignore_errors=True)
print("%d/%d passed" % (sum(ok), len(ok)))
