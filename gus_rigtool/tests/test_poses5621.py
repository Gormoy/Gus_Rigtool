# 5.6.21: a pose measures each control against the first node above it the rig moves again by itself - a ribbon's
# neighbour (its offset held by a follicle constraint) moved only by the ribbon stays out of the pose (5.6.20 kept
# that move too: it moved twice); the control you moved keeps its own move; a lid under a driven-key group keeps the
# closing; a turned group's axes respected
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
head = mk("Head_01_CTRL", None, (0, 150, 0))
rib = cmds.ls(cmds.createNode("transform", name="Mouth_ribbon_grp", parent=head), long=True)[0]
A = mk("L_Mouth_fol_06_ctrl", rib, (4, 145, 10))
B = mk("L_Mouth_fol_08_ctrl", rib, (6, 145, 9))
for n in (A, B):                                         # their offsets held by follicles (a constraint)
    off = cmds.listRelatives(n, parent=True, fullPath=True)[0]
    con = cmds.createNode("parentConstraint", name=n.split("|")[-1] + "_offset_parentConstraint1", parent=off)
    cmds.connectAttr(con + ".constraintTranslateX", off + ".translateX")
holder = mk("Mouth_main_ctrl", head, (0, 147, 14))
offB = cmds.listRelatives(B, parent=True, fullPath=True)[0]
def ribbon():          # what the skinned ribbon does in Maya: A up -> B's follicle (offset) up half as much
    cmds.setAttr(offB + ".translateY", -0.5 * 0 + 0.5 * cmds.getAttr(GC._long("L_Mouth_fol_06_ctrl") + ".translateY"))
cmds.setAttr(A + ".translateY", 1.0)
ribbon()
CT = [A, B]
with mock.patch.object(FP, "pose_controls", side_effect=lambda h=None: [GC._long(c.split("|")[-1]) for c in CT]), \
        mock.patch.object(FP.WT, "_settle", side_effect=lambda *a: ribbon()):
    got = FP.save_pose("Mouth_main_ctrl", "Up", False, include_on=False)
rec = FP.read(GC._long("Mouth_main_ctrl"))["Up"]["ctrls"]
print(dict((k, [round(v, 3) for v in rec[k]["t"]]) for k in rec))
check("the control you moved keeps its move (up 1)", [round(v, 3) for v in rec["L_Mouth_fol_06_ctrl"]["t"]] == [0, 1, 0])
check("the ribbon's neighbour stays out (the ribbon moves it again when the pose plays - 5.6.20 doubled it)",
      "L_Mouth_fol_08_ctrl" not in rec)
check("the neighbour is measured against its follicle-held offset",
      FP._frame_of(GC._long("L_Mouth_fol_08_ctrl"), set()).endswith("L_Mouth_fol_08_ctrl_offset"))
print("%d/%d passed" % (sum(ok), len(ok)))
