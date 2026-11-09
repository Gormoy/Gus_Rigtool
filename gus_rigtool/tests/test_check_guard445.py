# 4.4.5: a crash in any part of the Maya check (e.g. Qt "already deleted") costs one FAIL line, never the report
exec(open("fakemaya.py").read())
import gus_rigtool.maya_check as mc
from gus_rigtool.core.report import Report
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
DEAD = RuntimeError("Internal C++ object (PySide2.QtWidgets.QWidget) already deleted.")
def dead(*a, **k):
    raise DEAD
# every part stubbed; the windows part and the rig part crash the way Qt did
names = ["check_rig", "check_animtool", "check_picker", "check_daily_tools", "check_make_controls", "check_ribbons",
         "check_editing", "check_follow", "check_face_kit", "check_correctives", "check_selftest"]
ran = []
for n in names:
    setattr(mc, n, (lambda nm: lambda rep, *a, **k: ran.append(nm))(n))
mc.check_windows = dead
mc.check_rig = dead
cmds.internalVar = lambda **k: "/tmp/"
for _d in ("confirmDialog", "promptDialog", "fileDialog2"):
    if not hasattr(cmds, _d):
        setattr(cmds, _d, lambda *a, **k: None)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):     # the report prints its tracebacks
    text = mc.run(ask=False)
check("the report still comes out", isinstance(text, str) and "RESULT" in text)
check("windows crash: one FAIL line naming it", "windows (the check itself crashed)" in text and "already deleted" in text)
check("biped and quadruped rig crash: their own lines", "biped rig (the check itself crashed)" in text
      and "quadruped rig (the check itself crashed)" in text)
check("every later part still ran", all(n in ran for n in names if n != "check_rig"))
# a button Maya deleted while it's being read counts as fine
mc._cut_now = dead
check("deleted button: skipped, no crash", mc._cut("someButton") is None)
# the button check crashing inside the windows part: one FAIL line, the windows part carries on
rep = Report("t")
mc._check_cut_buttons = dead
rep.guard("button check", mc._check_cut_buttons, rep)
check("button check crash: its own FAIL line", any("button check (the check itself crashed)" in r[2] for r in rep.rows))
print("ALL OK" if all(ok) else "SOME FAILED")
