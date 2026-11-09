# 4.5.0: the speed report times the common tools on the open character, slowest first, and undoes what it changed
import os, sys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.setKeyframe = mock.MagicMock(); cmds.currentTime = mock.MagicMock(return_value=1.0)
cmds.internalVar = mock.MagicMock(return_value="/tmp/")
undos = []
cmds.undo = lambda *a, **k: undos.append(1)
def bbox(nodes):
    n = nodes[0] if isinstance(nodes, list) else nodes
    t = cmds.listRelatives(n, parent=True, fullPath=True)
    p = world(_n(t[0] if t else n))[12:15]
    return [p[0] - 1, p[1] - 1, p[2] - 1, p[0] + 1, p[1] + 1, p[2] + 1]
cmds.exactWorldBoundingBox = bbox
from gus_animtool import anim as A
A.profile = lambda ns=None: {}
from gus_rigtool.builder import build as bld
bld.biped(180); bld.build_all(180)
from gus_rigtool.core import speed
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    text = speed.run(ask=False, show=False)
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
check("a report", text and "speed report" in text and "97 controls" in text)
for label in ("find the controls (first time)", "picker: automatic layout", "key every control", "read a pose",
              "apply a pose", "Check this scene", "Repair: look through the scene", "switch between"):
    check("times: " + label, label in text.split("NOT TIMED")[0])
body = text.split("EVERYTHING")[1].split("NOT TIMED")[0].split("\n\n")[0]       # the timings, up to the next gap
lines = [ln for ln in body.splitlines()[1:] if ln.strip()]
secs = [float(ln.split("s", 1)[0]) for ln in lines]
check("slowest first", secs == sorted(secs, reverse=True))
check("what changed the scene was undone (key, apply, isolate...)", len(undos) >= 2)
print("ALL OK" if all(ok) else "SOME FAILED")
