# 5.6.19: a pose with a chain of controls (the ear's FK: L_Ear_02 under L_Ear_01) saves - the deepest first, so a
# layer above a parent doesn't break its children's paths (5.6.18 stopped half way) - and each link keeps only its
# own move (measured against its parent as posed: L_Ear_02 didn't take L_Ear_01's swing too); a save that stops
# is taken back; replacing a name asks first
import sys, math
exec(open("fakemaya.py").read())
from gus_rigtool.core import face_poses as FP, group_ctrls as GC
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def mk(name, parent=None, pos=(0, 0, 0)):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=pos)
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]
head = mk("Head_ctrl", None, (0, 150, 0))
e1 = mk("L_Ear_01_FK_ctrl", head, (5, 170, 0))
e2 = mk("L_Ear_02_FK_ctrl", e1, (5, 180, 0))
e3 = mk("L_Ear_03_FK_ctrl", e2, (5, 190, 0))
m = mk("L_Mouth_fol_06_ctrl", head, (4, 150, 10))
holder = mk("Mouth_main_ctrl", head, (0, 150, 14))
cmds.setAttr(e1 + ".rotateZ", 20); cmds.setAttr(e2 + ".rotateZ", 10); cmds.setAttr(e3 + ".translateX", 0.5)
cmds.setAttr(m + ".translateY", 1)
with mock.patch.object(FP, "pose_controls", return_value=[e1, e2, e3, m]):
    try:
        got = FP.save_pose("Mouth_main_ctrl", "Surprised", False)
        err = None
    except Exception as x:
        got, err = None, x
print(got, err)
check("saved: a chain of three posed links and the mouth (5.6.18 stopped half way)", got and got["controls"] == 4)
rec = FP.read(GC._long("Mouth_main_ctrl"))["Surprised"]["ctrls"]
r = dict((k, [round(v, 3) for v in rec[k]["r"]] + [round(v, 3) for v in rec[k]["t"]]) for k in rec)
print(r)
check("each link only its own move: 01 turned 20, 02 turned 10 (not 30, not swung), 03 moved 0.5 (not swung)",
      r["L_Ear_01_FK_ctrl"][:3] == [0, 0, 20] and r["L_Ear_02_FK_ctrl"] == [0, 0, 10, 0, 0, 0] and
      r["L_Ear_03_FK_ctrl"] == [0, 0, 0, 0.5, 0, 0])
check("the chain at rest after (each link's layer under its parent)",
      all(abs(cmds.getAttr(GC._long(n) + "." + a)) < 1e-9 for n in ("L_Ear_01_FK_ctrl", "L_Ear_02_FK_ctrl")
          for a in ("rotateZ", "translateX")) and
      cmds.listRelatives(GC._long("L_Ear_02_FK_ctrl"), parent=True)[0] == "L_Ear_02_FK_ctrl_groups")
src = open("../core/face_poses.py").read()
check("a save that stops is taken back (the face as posed, the poses as they were) - 5.6.20 by hand",
      "_take_back(holder, made, values, sliders)" in src and "nothing changed" in src)
check("a name already there: Save as new beside it (default), or Replace", "Save as new: " in open("../tools/face_kit_tool.py").read())
print("%d/%d passed" % (sum(ok), len(ok)))
