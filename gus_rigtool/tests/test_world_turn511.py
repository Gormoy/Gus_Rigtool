# 5.1.1: World turn test (the mech's knee turning twice the world, its right pole left outside the world): turn the
# world control 90, list what doesn't come along exactly, put it back; Find loops asks Maya's cycleCheck
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import world_turn as WT, networks as NW
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def ctrl(name, parent=None, pos=(0, 0, 0)):
    t = cmds.createNode("transform", name=name, parent=parent)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    cmds.xform(t, worldSpace=True, translation=list(pos))
    return cmds.ls(t, long=True)[0]
wc = ctrl("World_03_Ctrl")
arm = ctrl("arm_ctrl", wc, (5, 10, 0))
pole = ctrl("R_IK_KNEE_02_ctrl", None, (-3, 5, 8))               # outside the world: left behind
dbl = cmds.createNode("transform", name="knee_dbl_grp", parent=wc)
knee = ctrl("L_knee_ctrl", dbl, (3, 5, 2))
real_set = cmds.setAttr
def setAttr(plug, *a, **k):                                     # the knee group also gets the world turn
    real_set(plug, *a, **k)
    if plug.endswith("World_03_Ctrl.rotateY"):
        real_set(dbl + ".rotateY", a[0])
undo_calls = []
with mock.patch.object(cmds, "setAttr", side_effect=setAttr), \
        mock.patch.object(cmds, "undoInfo", side_effect=lambda **k: undo_calls.append(k) or True, create=True):
    r = WT.run(world=wc, nodes=[arm, pole, knee])
off = dict((n.split("|")[-1], (t, m, w)) for n, t, m, w in r["off"])
for k, v in off.items():
    print("  ", k, v)
check("the world control turned on Y by 90", r["axis"] == "Y" and r["angle"] == 90)
check("a control under the world comes along: not listed", "arm_ctrl" not in off)
check("the knee turned twice: 180", "L_knee_ctrl" in off and abs(off["L_knee_ctrl"][0] - 180) < 1 and
      "turns 180" in off["L_knee_ctrl"][2])
check("the pole outside the world: stays behind", "R_IK_KNEE_02_ctrl" in off and "stays behind" in
      off["R_IK_KNEE_02_ctrl"][2])
check("the world is put back", abs(cmds.getAttr(wc + ".rotateY")) < 1e-9)
check("nothing on the undo list (recording off, then back)", any("stateWithoutFlush" in c and
                                                                 c["stateWithoutFlush"] is False for c in undo_calls))
check("the world control is found by itself (highest, its name)",
      WT.world_control([arm, knee, wc, pole]) == wc)

# loops: Maya's cycleCheck is used when it's there
def cycleCheck(**k):
    return ["a.translate", "b.rotate", NW.CYCLE_SEP, "c.tx", "d.ty", "c.ry"]
for n in "abcd":
    cmds.createNode("transform", name=n)
with mock.patch.object(cmds, "cycleCheck", side_effect=cycleCheck, create=True):
    got = [[x.split("|")[-1] for x in g] for g in NW.loops()]
check("loops: Maya's cycles, grouped, each node once", got == [["a", "b"], ["c", "d"]])
with mock.patch.object(cmds, "cycleCheck", side_effect=lambda **k: [], create=True):
    check("loops: none when Maya finds none", NW.loops() == [])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
