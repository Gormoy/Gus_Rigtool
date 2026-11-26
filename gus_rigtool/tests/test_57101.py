# 5.7.10.1: Maya crashed every time Gus opened the Animtool from its shelf - opening a new version rebuilt the
# Gus_Animtool shelf, deleting the button whose click was still running; the "done" mark was an optionVar (written
# to disk only when Maya quits cleanly), so after the crash it tried again every time. Now: marked and saved first,
# the shelf rebuilt once the click has finished (when Maya is idle).
import os, sys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ROOT = os.path.join(os.getcwd(), "..")
sys.path.insert(0, os.path.join(ROOT, "anim"))
import gus_animtool
from gus_animtool import anim as A, ui as AUI, toolbar as TB

opts, events, later, msgs = {}, [], [], []
A.opt = lambda k, d: opts.get(k, d)
def set_opt(k, v):
    events.append(("opt", k, v)); opts[k] = v
A.set_opt = set_opt
A.message = lambda text, level="ok": msgs.append((level, text))
def save(**k):
    events.append(("save", k))
def make():
    events.append(("make",)); return 57
def defer(fn, **k):
    events.append(("defer", k)); later.append(fn)

# --- 1. a new version, opened from the shelf: nothing deleted during the click
with mock.patch.object(TB, "make_shelf", make), mock.patch.object(cmds, "savePrefs", save, create=True), \
        mock.patch.object(cmds, "evalDeferred", defer, create=True), \
        mock.patch.object(cmds, "shelfLayout", lambda *a, **k: True, create=True):
    r = AUI._shelf_up_to_date()
    during = list(events)
    check("a new version: the shelf isn't touched during the click (the crash: its own button deleted)",
          r is True and ("make",) not in during)
    check("...marked done FIRST and saved to disk at once (a crash can't make it try again)",
          during[:2] == [("opt", "shelf_version", gus_animtool.__version__), ("save", {"general": True})])
    check("...the rebuild waits until Maya is idle (after the click has finished)",
          during[2:] == [("defer", {"lowestPriority": True})] and len(later) == 1)
    n = later[0]()
    check("...then the shelf is made, once, and says so", n == 57 and events.count(("make",)) == 1 and
          any("up to date (57 buttons)" in t for _l, t in msgs))
    check("opened again: nothing to do (the mark was saved)", AUI._shelf_up_to_date() is False and len(later) == 1)

# --- 2. the rebuild failing never stops Maya
def broken():
    raise RuntimeError("no shelf tab")
with mock.patch.object(TB, "make_shelf", broken):
    msgs[:] = []
    r = AUI._rebuild_shelf()
check("the rebuild fails: a warning that says how to fix it, nothing raised",
      r is None and msgs and msgs[0][0] == "warn" and "Make the shelf" in msgs[0][1])

# --- 3. saving the prefs
with mock.patch.object(cmds, "savePrefs", lambda **k: None, create=True):
    check("save_prefs: True when Maya saved", AUI.save_prefs() is True)
def refuse(**k):
    raise RuntimeError("read-only prefs")
with mock.patch.object(cmds, "savePrefs", refuse, create=True):
    check("...False (and no error) when it can't", AUI.save_prefs() is False)

# --- 4. the window still opens if any of it fails; the Test this release check exists
src = open(AUI.__file__).read()
show = src[src.index("def show():"):]
check("show(): the shelf check stays inside try (never stops the window)",    # 5.7.11: op.run = a guarded step
      'op.run("shelf update", _shelf_up_to_date)' in show)
wc = open(os.path.join(ROOT, "realmaya", "window_checks.py")).read()
check("Test this release: a check that the shelf isn't touched during the click and the mark is on disk",
      "def shelf_waits" in wc and "userPrefs.mel" in wc and '("the shelf waits", shelf_waits)' in wc)
mf = open(os.path.join(ROOT, "realmaya", "MAYA_FACTS.md")).read()
check("MAYA_FACTS: a shelf button deleting itself crashes Maya; optionVars reach disk only on a clean quit",
      "deletes its own button" in mf and "clean quit" in mf)

# --- 5. Arcs: an arc already there but hidden (Gus: "when I click arcs nothing shows")
from gus_animtool import arctrail as T
log = []
trails = {"head_CTRL": ["|gusAnimtool_arcs_grp|head_CTRL_arcHandle"]}
def snap(n, **k):
    log.append(("snapshot", n)); return [n + "_arcHandle"]
with mock.patch.object(T, "_trails_of", lambda n: list(trails.get(n.split("|")[-1], []))), \
        mock.patch.object(T, "set_visible", lambda n, v: log.append(("visible", n, v)) or v), \
        mock.patch.object(T, "_group", lambda: "|gusAnimtool_arcs_grp"), \
        mock.patch.object(T, "style", lambda *a, **k: []), mock.patch.object(T, "_watch", lambda: None), \
        mock.patch.object(A, "frame_range", lambda: (1, 58)), \
        mock.patch.object(cmds, "snapshot", snap, create=True), \
        mock.patch.object(cmds, "delete", lambda *a, **k: log.append(("delete",) + a), create=True), \
        mock.patch.object(cmds, "objExists", lambda n: True, create=True), \
        mock.patch.object(cmds, "nodeType", lambda n: "transform", create=True), \
        mock.patch.object(cmds, "parent", lambda a, b: [b + "|" + a], create=True), \
        mock.patch.object(cmds, "ls", lambda *a, **k: ["|head_CTRL"] if a and a[0] == "head_CTRL" else [], create=True), \
        mock.patch.object(cmds, "select", lambda *a, **k: None, create=True):
    T._state["nodes"], T._state["hidden"] = [], []
    T.make(["head_CTRL"])
    check("an arc left in the file from an earlier session (hidden): made again, fresh - it shows",
          ("delete", "|gusAnimtool_arcs_grp|head_CTRL_arcHandle") in log and ("snapshot", "head_CTRL") in log)
    del log[:]
    T.make(["head_CTRL"])
    check("an arc made in this session, hidden: the Arcs button shows it again (not skipped, not made twice)",
          ("visible", "|head_CTRL", True) in log and not any(e[0] == "snapshot" for e in log))
print("%d/%d passed" % (sum(ok), len(ok)))
