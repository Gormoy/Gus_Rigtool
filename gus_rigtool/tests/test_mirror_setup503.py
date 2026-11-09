# 5.0.3: Mirror a setup - the left brow of the Hare rig (from the file Gus sent): brow controls drive the brow
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
con_10 = cmds.parentConstraint("L_Brow_02_ctrl", "L_Facial_ribbon_fol_10_ctrl_sdk", maintainOffset=True)[0]
scaled("L_Brow_02_ctrl", con_10, 0, 0.5)

sel = ["L_Brow_01_ctrl", "L_Brow_02_ctrl"]
text = MS.preview(sel)
print(text)
check("preview: the missing right nodes, the constraints, the utility nodes",
      "R_Facial_ribbon_fol_11_ctrl_sdk" in text and "R_Facial_ribbon_fol_10_ctrl" in text and "Constraints (4)" in text
      and "8 multiplyDivide" in text and "8 unitConversion" in text and "replaces" in text)
out = MS.run(sel)
print("   ", out)
L = lambda n: cmds.ls(n, long=True)
sdk = L("R_Facial_ribbon_fol_11_ctrl_sdk")
check("the right _sdk group is made, and the right control moved under it",
      sdk and L("R_Facial_ribbon_fol_11_ctrl")[0].startswith(sdk[0] + "|"))
check("the extra control fol_10 is made on the right (offset > sdk > control, with its curve)",
      L("R_Facial_ribbon_fol_10_ctrl") and "R_Facial_ribbon_fol_10_ctrl_sdk|R_Facial_ribbon_fol_10_ctrl" in L("R_Facial_ribbon_fol_10_ctrl")[0]
      and cmds.listRelatives(L("R_Facial_ribbon_fol_10_ctrl")[0], shapes=True))
p = cmds.xform("R_Facial_ribbon_fol_10_ctrl", query=True, worldSpace=True, rotatePivot=True)
check("... its pivot in the mirrored place", abs(p[0] + 2.5) < 1e-6 and abs(p[1] - 151) < 1e-6)
tl = lambda n, k="parentConstraint": [t.split("|")[-1] for c in cmds.listRelatives(L(n)[0], children=True, type=k) or []
                                      for t in cmds.parentConstraint(c, query=True, targetList=True) or []]
check("the right sdk follows the right brow controls", sorted(tl("R_Facial_ribbon_fol_11_ctrl_sdk")) == ["R_Brow_01_ctrl", "R_Brow_02_ctrl"])
check("the new right control drives its follicle joint (its own setup came too)", tl("R_Facial_ribbon_fol_10_jnt") == ["R_Facial_ribbon_fol_10_ctrl"])
check("the right brow joint's plain constraint is replaced (one, not two)",
      len(cmds.listRelatives(L("R_Brow_01_jnt")[0], children=True, type="parentConstraint") or []) == 1)
def feeding(con_node, idx, what):
    src = cmds.listConnections(con_node + ".target[%d].%s" % (idx, what), source=True, destination=False) or []
    return src[0] if src else None
rcon = cmds.listRelatives(L("R_Facial_ribbon_fol_11_ctrl_sdk")[0], children=True, type="parentConstraint")[0]
targets = cmds.parentConstraint(rcon, query=True, targetList=True)
i2 = targets.index("R_Brow_02_ctrl") if "R_Brow_02_ctrl" in targets else -1
md = feeding(rcon, i2, "targetTranslate")
check("R_Brow_02 -> sdk: its move goes through a copied multiplyDivide x0.8, fed by R_Brow_02_ctrl",
      md and abs(cmds.getAttr(md + ".input2X") - 0.8) < 1e-6 and
      (cmds.listConnections(md + ".input1", source=True, destination=False) or [""])[0] == "R_Brow_02_ctrl")
check("... with a readable name", md and md.startswith("R_Brow_02_t_to_fol_11"))   # 5.0.9: with the channel
uc = feeding(rcon, i2, "targetRotate")
check("its turn: unitConversion -> multiplyDivide -> unitConversion, values kept",
      uc and abs(cmds.getAttr(uc + ".conversionFactor") - 0.0174533) < 1e-6)
n_md = len(cmds.ls(type="multiplyDivide"))
MS.run(sel)
check("running it again replaces its copies (not doubled)", len(cmds.ls(type="multiplyDivide")) == n_md)
cmds.setAttr("L_Brow_01_ctrl.translateY", 1.0)
try:
    MS.run(sel); check("a control not at rest: it says so, changes nothing", False)
except RuntimeError as e:
    check("a control not at rest: it says so, changes nothing", "at rest" in str(e))
print("ALL OK" if all(ok) else "SOME FAILED")
