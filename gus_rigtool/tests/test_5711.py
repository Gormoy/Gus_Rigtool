# 5.7.11: safer updates (Gus: "make sure everything won't crash as soon as we update it"). Safe start: a note on
# disk while a window opens; Maya died while opening last time -> asked, the safe way opens only the window; an
# opening log (the last 5 opens) in "Copy last problem"; windows Maya reopens at start-up guarded; the "done once"
# marks saved at once; every place that deletes Maya UI listed (a new one shows up here); Test this release opens
# both tools from their shelves; a real-Maya case loads every file.
import os, sys, re, tempfile, shutil
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ROOT = os.path.join(os.getcwd(), "..")
sys.path.insert(0, os.path.join(ROOT, "anim"))
sys.path.insert(0, os.path.join(ROOT, ".."))
from gus_animtool import safestart as S, anim as A, ui as AUI
TMP = tempfile.mkdtemp(prefix="gus_safe_")
S.folder = lambda: TMP

# --- 1. safe start: the note, the log
op = S.Opening("t", "Test")
check("a first open: not the safe way, no question", op.begin("1.0") is False and op.last is None)
op.step("the window")
check("while it opens: the note on disk says the step", S.died_last_time("t") == "the window")
op.end()
check("opened: the note is gone, the log says 'open'", S.died_last_time("t") is None and
      S.last_log("t", 1).rstrip().endswith("open"))
op = S.Opening("t", "Test"); op.begin(); op.step("the bar")          # Maya dies here: no end()
asked = []
with mock.patch.object(S, "ask", lambda title, step, log="": asked.append((title, step)) or True):
    op2 = S.Opening("t", "Test")
    safe = op2.begin()
check("Maya died while opening: asked, with the step it died in", asked == [("Test", "the bar")] and safe is True)
op2.end()
check("...the log says so (and the safe way)", "Maya closed while opening last time, at: the bar - the safe way"
      in S.last_log("t", 1))
with mock.patch.object(S, "ask", lambda *a, **k: False):
    op3 = S.Opening("t", "Test"); op3.begin(); op3.step("x"); op3.end()
check("you chose 'As usual' once: the next open is normal, no question",
      S.Opening("t", "Test").begin() is False)
S.forget("t")
o = S.Opening("t", "Test"); o.begin()
check("a step that raises: logged, the open goes on", o.run("broken", lambda: 1 / 0) is None and
      "!! broken" in S.last_log("t", 1) and o.run("fine", lambda: 7) == 7)
o.end()
for _ in range(9):
    o = S.Opening("t", "Test"); o.begin(); o.end()
check("the log keeps the last 5 opens", open(S.log_path("t")).read().count("=== ") == 5)
o = S.Opening("u", "No ask", asks=False); o.begin(); o.step("s")
with mock.patch.object(S, "ask", lambda *a, **k: asked.append("asked") or False):
    n = len(asked)
    check("start-up restores don't ask: after a death they're simply skipped",
          S.Opening("u", "No ask", asks=False).begin() is True and len(asked) == n)
S.forget("u")
with mock.patch.object(S, "ask", lambda *a, **k: True):
    S.Opening("p_restore", "x").begin()                      # died last time
    called = []
    sys.modules["gus_fake_mod"] = type(sys)("gus_fake_mod")
    sys.modules["gus_fake_mod"].go = lambda *a: called.append(a) or "built"
    r1 = S.restore_call("p", "gus_fake_mod", "go", 1)
    r2 = S.restore_call("p", "gus_fake_mod", "go", 2)
check("restore_call: skipped once after a death at start-up, then runs again", r1 is None and r2 == "built" and
      called == [(2,)])

# --- 2. the Animtool window: the safe way = only the window
ran = []
def rec(name):
    return lambda *a, **k: ran.append(name)
opts = {"bar_auto": 1, "toolbar": 1, "bar_replaces_toolbar": 1}
A.opt = lambda k, d: opts.get(k, d)
A.message = lambda *a, **k: ran.append("message")
patches = [mock.patch.object(AUI, n, rec(n)) for n in ("_version_check", "_shelf_up_to_date", "_toolbar_once",
                                                       "_toolbar_show", "_bar_show", "_timeslider_install",
                                                       "_backup_ensure", "build")]
patches += [mock.patch.object(A, "track_selection_order", rec("selection")),
            mock.patch.object(cmds, "workspaceControl", lambda *a, **k: False, create=True),
            mock.patch.object(cmds, "formLayout", lambda *a, **k: False, create=True)]
for p in patches:
    p.start()
AUI.show()
normal = list(ran)
check("opened as usual: the window, then version check, shelf, toolbar, bar, Time Slider menu, backup",
      normal == ["selection", "build", "_version_check", "_shelf_up_to_date", "_toolbar_once", "_toolbar_show",
                 "_bar_show", "_timeslider_install", "_backup_ensure"])
check("...the note cleared", S.died_last_time("animtool") is None)
S.Opening("animtool", "Gus Animtool").begin(); S.Opening("animtool", "x").step("the bar")    # died in the bar
del ran[:]
with mock.patch.object(S, "ask", lambda *a, **k: True):
    AUI.show()
check("Maya died while it opened, 'Safe way': only the window (no bar, no shelf update...), and it says why",
      ran == ["selection", "build", "message"])
del ran[:]
AUI.show()
check("...next time: as usual again", ran == normal)
S.Opening("animtool_restore", "x", asks=False).begin()          # Maya died while reopening it at start-up
del ran[:]
with mock.patch.object(cmds, "text", lambda *a, **k: ran.append("text"), create=True):
    AUI.restore()
check("Maya reopening it at start-up after it died doing that: not filled, a line says open it from the shelf",
      ran == ["text"])
del ran[:]
AUI.restore()
check("...next start: filled as usual", ran == ["build"])
for p in patches:
    p.stop()

# --- 3. the toolbar's once-only mark saved to disk at once
opts.clear(); saved = []
A.set_opt = lambda k, v: opts.__setitem__(k, v)
with mock.patch.object(AUI, "save_prefs", lambda: saved.append(dict(opts))), \
        mock.patch("gus_animtool.toolbar.hide", lambda: None):
    first = AUI._toolbar_once(); again = AUI._toolbar_once()
check("the toolbar switched off once, the mark saved to disk straight away (like the shelf's)",
      first is True and again is False and saved == [{"bar_replaces_toolbar": 1, "toolbar": 0}])

# --- 4. Gus_Rigtool: the same safe start, from its own copy of the Animtool
from gus_rigtool.core import safe_start as RS
check("Gus_Rigtool's safe start is the Animtool's own file (one code, both tools)",
      os.path.samefile(sys.modules["gus_rigtool._safestart"].__file__, S.__file__) and RS.Opening and RS.restore_call)
win = open(os.path.join(ROOT, "newui", "window.py")).read()
check("the Gus_Rigtool window: safe start, the safe way skips the favourites bar and the first selection read",
      'safe_start.Opening("rigtool", "Gus_Rigtool")' in win and 'op.run("the favourites bar", _bar_if_open)' in win
      and "if safe:\n        return frame" in win)
check("...its start-up restore and the Pop out panels' are guarded", 'Opening("rigtool_restore"' in win and
      "def _fill_pop(" in win)

# --- 5. every window Maya reopens at start-up is guarded
scripts = []
for folder, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__")]
    for f in files:
        if f.endswith(".py"):
            src = open(os.path.join(folder, f)).read()
            for m in re.finditer(r'uiScript="([^"]+)"', src):
                scripts.append((f, m.group(1)))
            if "uiScript=script" in src:
                scripts.append((f, src[src.index("script = (\"import"):].split("\n")[0]))
unguarded = [s for s in scripts if not any(g in s[1] for g in ("restore_call(", "_u.restore()", "_w.restore()",
                                                                 "_w.restore_pop("))]
check("every window Maya reopens at start-up goes through a guard (%d windows)" % len(scripts),
      len(scripts) >= 8 and not unguarded)
for s in unguarded:
    print("   unguarded: %s: %s" % s)

# --- 6. every place that deletes Maya UI (a new one shows up here, to be checked: never inside its own click)
calls = {}
for folder, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", "realmaya")]
    for f in sorted(files):
        if not f.endswith(".py"):
            continue
        func = "(module)"
        for line in open(os.path.join(folder, f)):
            m = re.match(r"\s*def (\w+)", line)
            if m and not line.startswith(" " * 8):
                func = m.group(1)
            if "deleteUI(" in line:
                key = "%s: %s" % (os.path.relpath(os.path.join(folder, f), ROOT), func)
                calls[key] = calls.get(key, 0) + 1
print("   places that delete Maya UI (%d):" % len(calls))
for k in sorted(calls):
    print("     " + k)
check("the shelf rebuilds run after the click (5.7.10.1): the Animtool's waits for idle",
      "cmds.evalDeferred(_rebuild_shelf, lowestPriority=True)" in open(os.path.join(ROOT, "anim", "gus_animtool",
                                                                                   "ui.py")).read())

# --- 7. Copy last problem, Test this release, the real-Maya case
bar = open(os.path.join(ROOT, "anim", "gus_animtool", "bar.py")).read()
check("Copy last problem: the opening logs too (even with no other problem)", "_opening_logs()" in bar and
      "safestart.all_logs()" in bar)
S.Opening("anim2", "x").begin(); S.Opening("anim2", "x").end()
check("...all the logs there are, by name", [n for n, _l in S.all_logs()] == sorted(n for n, _l in S.all_logs())
      and "anim2" in [n for n, _l in S.all_logs()])
wc = open(os.path.join(ROOT, "realmaya", "window_checks.py")).read()
check("Test this release: opens both tools from their shelves (the buttons' own commands)",
      "def open_from_shelf" in wc and '("open from the shelves", open_from_shelf)' in wc)
mc = open(os.path.join(ROOT, "realmaya", "maya_cases.py")).read()
check("real-Maya case q: every file of both tools loads; it only reads them (nothing written)",
      "def every_file" in mc and '("q. every file loads", every_file)' in mc and "py_compile" not in mc)
shutil.rmtree(TMP, ignore_errors=True)
print("%d/%d passed" % (sum(ok), len(ok)))
