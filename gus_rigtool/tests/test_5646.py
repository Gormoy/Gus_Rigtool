# 5.6.46: one Animtool (an installed copy runs Gus_Rigtool's newer one, your naming kept), Maya facts, Test this
# release (in Maya's window), Copy the last problem, Bake all attaches, version strings out of the test output,
# working rules in CLAUDE.md
import os, sys, shutil, subprocess, tempfile, textwrap
exec(open("fakemaya.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ROOT = os.path.join(os.getcwd(), "..")
ANIM = os.path.join(ROOT, "anim", "gus_animtool")

# --- 1. one Animtool: the installed copy runs Gus_Rigtool's when that one is newer
src = open(os.path.join(ANIM, "__init__.py")).read()
tmp = tempfile.mkdtemp()
try:
    s = os.path.join(tmp, "scripts")
    os.makedirs(os.path.join(s, "gus_animtool"))
    os.makedirs(os.path.join(s, "gus_rigtool", "anim", "gus_animtool"))
    open(os.path.join(s, "gus_rigtool", "__init__.py"), "w").write("")
    import re
    mine = re.sub(r'__version__ = "[^"]+"', '__version__ = "5.6.45"', src)
    newer = re.sub(r'__version__ = "[^"]+"', '__version__ = "5.6.46"', src)
    open(os.path.join(s, "gus_animtool", "__init__.py"), "w").write(mine)
    open(os.path.join(s, "gus_animtool", "thing.py"), "w").write('WHO = "your copy"\n')
    open(os.path.join(s, "gus_animtool", "defaults.json"), "w").write('{"suffix": "_CTRL"}')
    open(os.path.join(s, "gus_rigtool", "anim", "gus_animtool", "__init__.py"), "w").write(newer)
    open(os.path.join(s, "gus_rigtool", "anim", "gus_animtool", "thing.py"), "w").write('WHO = "Gus_Rigtool\'s"\n')
    code = textwrap.dedent("""
        import sys; sys.path.insert(0, %r)
        import gus_animtool, gus_animtool.thing as t
        print(t.WHO, gus_animtool.__version__, gus_animtool.LOCAL_ROOT == %r, bool(gus_animtool.REDIRECTED))
    """) % (s, os.path.join(s, "gus_animtool"))
    run = lambda: subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True).stdout.strip()
    check("Gus_Rigtool's Animtool is newer: your installed copy runs it (your naming still from your folder)",
          run() == "Gus_Rigtool's 5.6.46 True True")
    open(os.path.join(s, "gus_rigtool", "anim", "gus_animtool", "__init__.py"), "w").write(
        re.sub(r'__version__ = "[^"]+"', '__version__ = "5.6.44"', src))
    check("yours is newer (its own Update): yours runs", run() == "your copy 5.6.45 True False")
    shutil.rmtree(os.path.join(s, "gus_rigtool"))
    check("an animator's copy (no Gus_Rigtool): runs as it is", run() == "your copy 5.6.45 True False")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

sys.path.insert(0, os.path.join(ROOT, "anim"))
import gus_animtool
from gus_animtool import anim as A, actions as AC
tmp = tempfile.mkdtemp()
try:
    open(os.path.join(tmp, "defaults.json"), "w").write('{"suffix": "_CTRL"}')
    with mock.patch.object(gus_animtool, "LOCAL_ROOT", tmp):
        A._load_defaults()
    check("your naming (defaults.json) read from your installed copy's folder", A.DEFAULT_SUFFIX == "_CTRL")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
upd = open(os.path.join(ANIM, "updater.py")).read()
check("the Animtool's own Update writes your installed copy when it runs Gus_Rigtool's (never the one inside "
      "Gus_Rigtool) - and its own folder otherwise", "if getattr(gus_animtool, \"REDIRECTED\", None):" in upd and
      "target = gus_animtool.LOCAL_ROOT" in upd)

# --- 2. Copy the last problem
said = []
real_message = A.message
cmds.warning = lambda t: said.append(t)
cmds.text = lambda *a, **k: False
A.LAST_PROBLEM.clear()
check("nothing yet: nothing to copy", A.problem_report() == "")
A.message("3 curve(s) didn't move", "warn")
rep = A.problem_report()
check("a warning: it's the last problem, with the versions", "3 curve(s) didn't move" in rep and
      "Gus Animtool" in rep and "Maya" in rep)
AC._call = lambda key: 1 / 0
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):          # the traceback it prints (machine paths)
    AC.run("attach")
rep = A.problem_report()
check("a crash: the error, which tool, and the details (the traceback)", "error: division by zero" in rep and
      "Tool: attach" in rep and "ZeroDivisionError" in rep)
bar = open(os.path.join(ANIM, "bar.py")).read()
check("the bar's menu: Copy the last problem / Test this release",
      '"Copy the last problem"' in bar and '"Test this release (in this Maya)..."' in bar)

# --- 3. Bake all attaches
from gus_animtool import attach as AT
cmds.undoInfo = mock.MagicMock()
baked = []
with mock.patch.object(AT, "attached", lambda: ["|box", "|cup"]), mock.patch.object(AT, "read", lambda n: {"v": 2}), \
        mock.patch.object(AT, "bake", lambda n, a, b: baked.append((n, a, b)) or 40):
    got = AT.bake_all(1, 40)
check("Bake all attaches: every attach baked over the range", baked == [("|box", 1, 40), ("|cup", 1, 40)] and
      len(got) == 2)
with mock.patch.object(AT, "attached", lambda: []):
    try:
        AT.bake_all(1, 40); msg = ""
    except RuntimeError as e:
        msg = str(e)
check("nothing attached: says so", "nothing is attached" in msg)
check("in Release's right-click menu and the Attach window",
      ("Bake ALL attaches in this shot (finish the shot)", "attach_bake_all") in AC.MENUS["release"] and
      '"Bake all..."' in open(os.path.join(ANIM, "attachwin.py")).read())

# --- 4. Test this release / Maya facts
sys.path.insert(0, os.path.join(ROOT, ".."))
from gus_rigtool.realmaya import window_checks as WC, maya_facts as MF
check("Test this release: the bar, the shelf, undo, Time Slider, pick-walk, inbetween, versions, Maya facts",
      [n for n, _f in WC.CHECKS if n not in ("new window", "new look", "arrange", "the Rigtool shelf")] == ["versions", "the bar", "the shelf", "undo",
                                                          "time slider stretches", "pick-walk", "inbetween",
                                                          "controls tab", "maya facts"])
cmds.file = mock.MagicMock(side_effect=lambda *a, **k: True if k.get("modified") else ("/x/shot.ma" if
                                                                                      k.get("sceneName") else None))
cmds.confirmDialog = lambda **k: "Cancel"
check("your scene has changes and you press Cancel: nothing happens", WC.leave_scene() is False and
      not any(c.kwargs.get("new") for c in cmds.file.call_args_list))
cmds.confirmDialog = lambda **k: "Save, then test"
WC.leave_scene()
check("Save, then test: your scene saved, then a new empty one",
      any(c.kwargs.get("save") for c in cmds.file.call_args_list) and
      any(c.kwargs.get("new") for c in cmds.file.call_args_list))
check("Maya facts: zero, ls([]), undo, moving keys, controllers, bookmarks, node types",
      [f.__name__ for f in MF.FACTS][:8] == ["zero_threshold", "empty_ls", "undo_state", "key_moves", "mesh_points",
                                         "controllers", "bookmarks", "node_types"])
cases = open(os.path.join(ROOT, "realmaya", "maya_cases.py")).read()
check("...in the Terminal run too (case m)", '("m. Maya facts", maya_facts_case)' in cases)
facts_md = open(os.path.join(ROOT, "realmaya", "MAYA_FACTS.md")).read()
check("MAYA_FACTS.md: what we learned (divide by zero, ls([]), the cycle, bookmarks, Mac windows)",
      all(w in facts_md for w in ("divide by zero", "ls([])", "parentInverseMatrix", "timeSliderBookmark",
                                  "Qt.Tool")))

# --- 5. version strings / working rules
import run_tests as RT
check("the test runner: the current version becomes <this version> (no diffs on a version bump)",
      RT.normalize("version: %s" % RT.VERSION) == "version: <this version>" and
      RT.normalize("5.6.4%s1" % RT.VERSION[-1]) == "5.6.4%s1" % RT.VERSION[-1])
check("the test runner reports any test that changes the tool's own files", "A TEST CHANGED THE TOOL'S OWN FILES" in
      open("run_tests.py").read())
claude = open(os.path.join(ROOT, "..", "CLAUDE.md")).read()
check("CLAUDE.md: Maya behaviour first, viewport looks first, releases go to main",
      "Maya behaviour first" in claude and "Viewport looks proven first" in claude and "Releases go to `main`" in claude)
print("%d/%d passed" % (sum(ok), len(ok)))
