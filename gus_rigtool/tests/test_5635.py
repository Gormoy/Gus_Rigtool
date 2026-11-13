# 5.6.35: the real-Maya tests - the runner (mayapy, no window), the launchers for Windows and the Mac, your scene
# asked once and remembered, the results file; the tests' order (a-c alone, e builds the biped d and f use)
import os, sys, json, tempfile, types
exec(open("fakemaya.py").read())
from unittest import mock
HERE = os.path.join(os.getcwd(), "..", "realmaya")
sys.path.insert(0, HERE)
import run_maya_tests as RT
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- 1. paths dragged into a terminal
check("a path dragged in: quotes and Mac's '\\ ' taken off",
      RT.clean_path(' "C:\\Users\\Gus\\Hare v201.ma" ') == "C:\\Users\\Gus\\Hare v201.ma" and
      RT.clean_path("/Users/gus/The\\ Tree/Hare.ma ") == "/Users/gus/The Tree/Hare.ma")

# --- 2. your scene: asked once, remembered, changed with --scene, skipped with --no-scene
tmp = tempfile.mkdtemp()
cfg = os.path.join(tmp, "gus_maya_tests.json")
with mock.patch.object(RT, "CONFIG", cfg):
    asked = []
    got = RT.scene_to_use([], ask=lambda q: asked.append(q) or '"H:/Hare/Hare_v201.ma"')
    check("the first run asks for the scene and keeps it", got == "H:/Hare/Hare_v201.ma" and len(asked) == 1 and
          json.load(open(cfg))["scene"] == "H:/Hare/Hare_v201.ma")
    got = RT.scene_to_use([], ask=lambda q: asked.append(q) or "x")
    check("the next run doesn't ask again", got == "H:/Hare/Hare_v201.ma" and len(asked) == 1)
    check("--no-scene skips it this time", RT.scene_to_use(["--no-scene"]) is None)
    check("--scene PATH changes it", RT.scene_to_use(["--scene", "/Users/gus/Hare.mb"]) == "/Users/gus/Hare.mb")
    os.remove(cfg)
    check("Enter alone: skipped, and not asked again",
          RT.scene_to_use([], ask=lambda q: "") is None and RT.scene_to_use([], ask=lambda q: 1 / 0) is None)
    os.remove(cfg)
    check("not a scene file: skipped", RT.scene_to_use([], ask=lambda q: "C:/notes.txt") is None)

# --- 3. a run: each test on its own new scene, d and f on the biped e built; the results file written
calls, news = [], []
fake_cases = types.ModuleType("maya_cases")
def case(name):
    return lambda rep: (calls.append(name), rep.add("ok", name, ""))
fake_cases.CASES = [(n, case(n)) for n in ("a. pupils", "e. biped", "d. Check this scene", "f. IK/FK and mirror")]
fake_cases.WHOLE_RIG = ("d. Check this scene", "f. IK/FK and mirror")
fake_cases.APPENDIX = {}
fake_cases.hare = lambda rep, path: calls.append("scene " + path)
standalone = types.ModuleType("maya.standalone")
standalone.initialize = lambda **k: calls.append("maya started")
standalone.uninitialize = lambda: calls.append("maya closed")
out = os.path.join(tmp, "maya_test_results.txt")
with mock.patch.dict(sys.modules, {"maya.standalone": standalone, "maya_cases": fake_cases}), \
        mock.patch.object(RT, "OUT", out), mock.patch.object(RT, "CONFIG", cfg), \
        mock.patch.object(cmds, "file", lambda *a, **k: news.append(k.get("new")) if k.get("new") else None), \
        mock.patch("builtins.print", lambda *a, **k: None):
    sys.modules["maya"].standalone = standalone
    text = RT.main(["--scene", "H:/Hare.ma"])
check("Maya started, every test run in order, then your scene, then Maya closed",
      calls == ["maya started", "a. pupils", "e. biped", "d. Check this scene", "f. IK/FK and mirror",
                "scene H:/Hare.ma", "maya closed"])
check("a new empty scene before a and e only (d and f use the biped)", news == [True, True])
check("the results file is written next to the runner, with the version and your scene",
      os.path.isfile(out) and "Real Maya tests" in open(out).read() and "Your scene: H:/Hare.ma" in text)

# --- 4. the launchers
bat = open(os.path.join(HERE, "run_maya_tests.bat"), "rb").read().decode()
check("Windows: Maya 2024's mayapy.exe, Windows line endings, asks once if it isn't there",
      "C:\\Program Files\\Autodesk\\Maya2024\\bin\\mayapy.exe" in bat and "\r\n" in bat and
      bat.count("\n") == bat.count("\r\n") and "gus_maya_tests_mayapy.txt" in bat and "pause" in bat)
cmd = os.path.join(HERE, "run_maya_tests.command")
src = open(cmd).read()
check("Mac: Maya 2024's mayapy in /Applications, runnable by double-click",
      "/Applications/Autodesk/maya2024/Maya.app/Contents/bin/mayapy" in src and os.access(cmd, os.X_OK) and
      src.startswith("#!/bin/bash") and "\r" not in src)

# --- 5. the tests themselves: all there, in the agreed order
src = open(os.path.join(HERE, "maya_cases.py")).read()
block = src[src.index("CASES = ["):]
order = [block.index('("%s' % n) for n in ("a. pupils", "b. history", "c. head squash", "e. biped", "d. Check",
                                          "f. IK/FK")]
check("a pupils, b history, c head squash, then e builds the biped, d and f run on it",
      order == sorted(order) and "WHOLE_RIG" in src)
check("your scene is never saved: no save anywhere in the tests or the runner",
      "save=True" not in src and "saveAs" not in src and
      "save=True" not in open(os.path.join(HERE, "run_maya_tests.py")).read())

print("%d/%d passed" % (sum(ok), len(ok)))
