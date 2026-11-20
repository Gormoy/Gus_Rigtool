# 5.7.2.1: Test this release's 'new window' check runs here (a stand-in for Maya's window): no part crashes, and
# a part that does crash is reported while the others still run (5.7.2's check stopped at Settings)
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["GUS_REAL_QT"] = "1"
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
for name in ("headsUpDisplay", "iconTextCheckBox", "nodeIconButton", "canvas", "image", "palettePort",
             "checkBoxGrp", "textFieldButtonGrp", "radioCollection", "radioButton", "intSlider", "floatSlider",
             "playbackOptions", "workspace", "channelBox", "shelfLayout", "colorIndexSliderGrp",
             "attrColorSliderGrp", "swatchDisplayPort", "iconTextRadioButton", "iconTextRadioCollection"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
cmds.undoInfo = mock.MagicMock(return_value=True)
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.newui.qt import QtCore, QtWidgets
QtCore.qInstallMessageHandler(lambda *a: None)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from gus_rigtool.newui import window as W, qt as QT
from gus_rigtool.core.report import Report, FAIL
hosts = {}
def workspaceControl(name, **k):
    if k.get("exists"):
        return name in hosts
    if k.get("query"):
        return "Gus_Rigtool <this version>"
    if k.get("edit"):
        if k.get("resizeWidth") and name in hosts:
            hosts[name].resize(k["resizeWidth"], 900)
        return name
    hosts[name] = QtWidgets.QWidget()
    QtWidgets.QVBoxLayout(hosts[name])
    hosts[name].resize(700, 900)
    hosts[name].show()
    exec(k["uiScript"])
    return name
cmds.workspaceControl = workspaceControl
real_delete = cmds.deleteUI
cmds.deleteUI = lambda *a, **k: hosts.pop(a[0]).deleteLater() if a and a[0] in hosts else real_delete(*a, **k)
limits = {}
cmds.transformLimits = lambda n, **k: (limits.get(n, [0.0, 0.0]) if k.get("rotationZ") else [False, False]) \
    if k.get("query") else None
cmds.undo = lambda: None
cmds.circle = lambda **k: [cmds.ls(createNode("transform", name=k.get("name", "nurbsCircle1")), long=True)[0]]
from gus_rigtool.core import limits as L
L.set_limit = lambda nodes, ch, lo, hi: [limits.__setitem__(n, [lo, hi]) for n in nodes] and len(nodes)
sys.path.insert(0, os.path.join(os.getcwd(), "..", ".."))
from gus_rigtool.realmaya import window_checks as WC
WC.__dict__["cmds"] = cmds
with mock.patch.object(QT, "maya_widget", lambda name, kind="layout": hosts.get(name)):
    rep = Report("x")
    WC.new_window(rep)
crashed = [r for r in rep.rows if r[1] == FAIL and "crashed" in r[2]]
check("the 'new window' check runs through every part, none crashes (5.7.2's stopped at Settings)", not crashed)
if crashed:
    print("  ", [r[2] for r in crashed])
names = [r[2] for r in rep.rows]
check("...Settings is looked for in its own place now", any(n.startswith("Settings: its own button") for n in names))
check("...and the parts after it ran: Pop out, the favourites, Skin, profiles",
      all(any(n.startswith(x) for n in names) for x in ("Pop out", "the favourites bar", "Skin: its 7 sub-pages",
                                                         "favourites profile 'Skin'")))
with mock.patch.object(W.Frame, "pop_out", lambda self: 1 / 0), \
        mock.patch.object(QT, "maya_widget", lambda name, kind="layout": hosts.get(name)):
    rep = Report("x")
    WC.new_window(rep)
names = [r[2] for r in rep.rows]
check("a part that crashes (Pop out here) is reported, and the rest still run",
      any("new window: Pop out (the check itself crashed)" in n for n in names) and
      any(n.startswith("Skin: its 7 sub-pages") for n in names))
print("%d/%d passed" % (sum(ok), len(ok)))
