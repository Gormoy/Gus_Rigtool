# 5.0.9: Nodes - name utility nodes from their connections (the Hare's brow: multiplyDivide13 -> ..._md),
# select a whole setup, the Checker's 'Utility nodes with default names' check + Fix
# (setup from test_mirror_setup503) Mirror a setup - the left brow of the Hare rig (from the file Gus sent): brow controls drive the brow
# joints and the face ribbon's _sdk groups through parent constraints whose target inputs are scaled by
# multiplyDivide (and unitConversion for the turns). The right side has the controls and joints, a plain joint
# constraint, no _sdk groups, and not the extra ribbon control fol_10.
exec(open("fakemaya.py").read())
from gus_rigtool.core import mirror_setup as MS
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def T(name, parent=None, x=0.0, y=150.0, kind="transform"):
    n = cmds.createNode(kind, name=name, parent=parent)
    cmds.xform(n, worldSpace=True, matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, 5, 1])
    return cmds.ls(n, long=True)[0]
def C(name, parent, x, y=150.0):
    off = T(name + "_offset", parent, x, y) if not name.startswith(("L_Facial", "R_Facial")) else parent
    t = T(name, off, x, y)                              # at rest: 0 under its offset
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return t
head = T("Head")
for sd, k in (("L", 1), ("R", -1)):
    for i, x in ((1, 2.0), (2, 4.0)):
        C("%s_Brow_0%d_ctrl" % (sd, i), head, k * x, 152)
        T("%s_Brow_0%d_jnt" % (sd, i), head, k * x, 152, "joint")
    grp = T("%s_Facial_ribbon_ctrls_grp" % sd, None, 0, 0)
    off = T("%s_Facial_ribbon_fol_11_ctrl_offset" % sd, grp, k * 3, 151)
    T("%s_Facial_ribbon_fol_10_jnt" % sd, None, k * 2.5, 151, "joint")
    T("%s_Facial_ribbon_fol_11_jnt" % sd, None, k * 3, 151, "joint")
    if sd == "L":
        sdk = T("L_Facial_ribbon_fol_11_ctrl_sdk", off, 3, 151)
        C("L_Facial_ribbon_fol_11_ctrl", sdk, 3, 151)
        off10 = T("L_Facial_ribbon_fol_10_ctrl_offset", grp, 0, 0)       # like the Hare: groups at 0
        sdk10 = T("L_Facial_ribbon_fol_10_ctrl_sdk", off10, 0, 0)
        c10 = T("L_Facial_ribbon_fol_10_ctrl", sdk10, 0, 0)        # like the Hare: at 0, its pivot on the face
        cmds.createNode("nurbsCurve", name="L_Facial_ribbon_fol_10_ctrlShape", parent=c10)
        cmds.xform(c10, worldSpace=True, rotatePivot=[2.5, 151, 5], scalePivot=[2.5, 151, 5])
        cmds.parentConstraint(c10, "L_Facial_ribbon_fol_10_jnt", maintainOffset=True)
    else:
        C("R_Facial_ribbon_fol_11_ctrl", off, -3, 151)
cmds.parentConstraint("R_Brow_01_ctrl", "R_Brow_01_jnt", maintainOffset=True)     # the right's plain one
# the left network
def scaled(ctrl, con, idx, factor):
    md = cmds.createNode("multiplyDivide")
    for a in "XYZ":
        cmds.setAttr(md + ".input2" + a, factor)
    cmds.connectAttr(ctrl + ".translate", md + ".input1")
    cmds.connectAttr(md + ".output", con + ".target[%d].targetTranslate" % idx, force=True)
    uc1 = cmds.createNode("unitConversion"); cmds.setAttr(uc1 + ".conversionFactor", 57.2957795)
    md2 = cmds.createNode("multiplyDivide")
    for a in "XYZ":
        cmds.setAttr(md2 + ".input2" + a, factor)
    uc2 = cmds.createNode("unitConversion"); cmds.setAttr(uc2 + ".conversionFactor", 0.0174533)
    cmds.connectAttr(ctrl + ".rotate", uc1 + ".input")
    cmds.connectAttr(uc1 + ".output", md2 + ".input1")
    cmds.connectAttr(md2 + ".output", uc2 + ".input")
    cmds.connectAttr(uc2 + ".output", con + ".target[%d].targetRotate" % idx, force=True)
con_j = cmds.parentConstraint("L_Brow_01_ctrl", "L_Brow_01_jnt", maintainOffset=True)[0]
scaled("L_Brow_01_ctrl", con_j, 0, 0.5)
con_s = cmds.parentConstraint(["L_Brow_01_ctrl", "L_Brow_02_ctrl"], "L_Facial_ribbon_fol_11_ctrl_sdk", maintainOffset=True)[0]
scaled("L_Brow_01_ctrl", con_s, 0, 0.2)
scaled("L_Brow_02_ctrl", con_s, 1, 0.8)
import sys
from unittest import mock
from gus_rigtool.core import networks as NW
from gus_rigtool.tools import checker
# the posY -> rotX chain on L_Brow_02 (clamp -> multiplyDivide -> unitConversion -> the sdk's rotateX)
cl = cmds.createNode("clamp"); cmds.connectAttr("L_Brow_02_ctrl.translateY", cl + ".inputR")
mdr = cmds.createNode("multiplyDivide"); cmds.connectAttr(cl + ".outputR", mdr + ".input1X")
ucr = cmds.createNode("unitConversion"); cmds.connectAttr(mdr + ".outputX", ucr + ".input")
cmds.connectAttr(ucr + ".output", "L_Facial_ribbon_fol_11_ctrl_sdk.rotateX")
mine = cmds.createNode("multiplyDivide", name="L_Brow_02_ctrl_MD")       # named by you: left alone
cmds.connectAttr("L_Brow_02_ctrl.translate", mine + ".input1")
cmds.connectAttr(mine + ".output", "L_Brow_02_jnt.translate")
lone = cmds.createNode("multiplyDivide")                                 # nothing out: left alone
cmds.connectAttr("L_Brow_01_ctrl.translate", lone + ".input1")
ref = cmds.createNode("multiplyDivide")                                   # in a referenced file: left alone
cmds.connectAttr("L_Brow_01_ctrl.translate", ref + ".input1"); cmds.connectAttr(ref + ".output", "Head.translate")
REF = {ref}
with mock.patch.object(NW, "_referenced", lambda n: n.split("|")[-1] in REF):
    plan = NW.plan()
names = dict((o.split("|")[-1], n) for o, n in plan)
for o, n in sorted(names.items()):
    print("  %-18s -> %s" % (o, n))
check("the brow's 0.8: L_Brow_02_t_to_fol_11_ctrl_sdk_md", "L_Brow_02_t_to_fol_11_ctrl_sdk_md" in names.values())
check("the turn chain: L_Brow_01_r_to_..._uc / _md", any(v.startswith("L_Brow_01_r_to_") and v.endswith("_uc")
                                                          for v in names.values()))
check("the clamp chain: L_Brow_02_ty_to_fol_11_ctrl_sdk_clamp / _md / _uc", {
    "L_Brow_02_ty_to_fol_11_ctrl_sdk_clamp", "L_Brow_02_ty_to_fol_11_ctrl_sdk_md",
    "L_Brow_02_ty_to_fol_11_ctrl_sdk_uc"} <= set(names.values()))
check("names are unique", len(set(names.values())) == len(names))
check("left alone: yours, one with nothing out, one in a reference",
      "L_Brow_02_ctrl_MD" not in names and lone not in names and ref not in names)
with mock.patch.object(NW, "_referenced", lambda n: n.split("|")[-1] in REF):
    found = checker.find_util_names(None)
    n = checker.fix_util_names(found)
check("Checker finds them and Fix renames them all", len(found) == len(plan) and n == len(plan))
check("afterwards none are left", NW.candidates() == [lone, ref] or set(NW.candidates()) == {lone, ref})
check("the renamed network still works (same connections)",
      cmds.listConnections("L_Brow_02_t_to_fol_11_ctrl_sdk_md.output", plugs=True) is not None)
net = NW.read(["L_Brow_02_ctrl"])
short = lambda xs: sorted(x.split("|")[-1] for x in xs)
print("setup:", short(net["utils"]), short(net["cons"]), short(net["driven"]))
check("select the setup: its utility nodes (yours too), constraint and what it moves",
      "L_Brow_02_ctrl_MD" in short(net["utils"]) and len(net["cons"]) == 1 and
      "L_Facial_ribbon_fol_11_ctrl_sdk" in short(net["driven"]) and "L_Brow_02_jnt" in short(net["driven"]))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
