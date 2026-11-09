# 5.0.6: twins found by position (the Hare's mouth loop: L_Mouth_fol_02_ctrl's twin is Mouth_fol_26_ctrl, not a
# '_02' on the right) in Gus Animtool - mirror pose goes to the right control and the unnamed one is the other
# side - and in the Checker (Fix links them for every Gus_Rigtool mirror). Plus the 5.0.6 check fixes from the
# Hare's report: joints the rig turns, a reference's namespace / names / Orig shapes
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
A.profile = lambda ns=None: {}
from gus_rigtool.tools import checker
from gus_rigtool.core import sides
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def ctrl(name, x, y, z, parent):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent)
    cmds.setAttr(off + ".translate", x, y, z, type="double3")
    t = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
rig = cmds.createNode("transform", name="Hare_rig")
# the Hare's mouth controls (v130 positions): the -X side renamed L_, the +X side never renamed
HARE = [("L_Mouth_fol_02_ctrl", -3.777, 4.870, 2.469), ("L_Mouth_fol_04_ctrl", -4.034, 4.807, 2.762),
        ("L_Mouth_fol_10_ctrl", -1.613, 7.403, 3.556), ("L_Mouth_fol_38_ctrl", -3.029, 5.659, 2.217),
        ("Mouth_fol_14_ctrl", 0.0, 7.089, 3.747),
        ("Mouth_fol_18_ctrl", 1.618, 7.399, 3.552), ("Mouth_fol_24_ctrl", 4.034, 4.807, 2.762),
        ("Mouth_fol_26_ctrl", 3.769, 4.877, 2.466), ("Mouth_fol_28_ctrl", 3.028, 5.659, 2.216),
        ("L_arm_ctrl", 10.0, 50.0, 0.0), ("R_arm_ctrl", -10.0, 50.0, 0.0)]
C = dict((n, ctrl(n, x, y, z, rig)) for n, x, y, z in HARE)
A.character_controls = lambda ns=None: list(C.values())
A._position_cache.clear()
got = dict((k.split("|")[-1], v.split("|")[-1]) for k, v in A.position_twins("").items())
check("mouth twins by position: 02-26, 04-24, 10-18, 38-28",
      got.get("L_Mouth_fol_02_ctrl") == "Mouth_fol_26_ctrl" and got.get("L_Mouth_fol_04_ctrl") == "Mouth_fol_24_ctrl"
      and got.get("L_Mouth_fol_10_ctrl") == "Mouth_fol_18_ctrl" and got.get("Mouth_fol_28_ctrl") == "L_Mouth_fol_38_ctrl")
check("the centre one and named pairs aren't paired by position",
      "Mouth_fol_14_ctrl" not in got and "L_arm_ctrl" not in got)
check("twin_of: the name first, then the position",
      A.twin_of(C["L_arm_ctrl"]).endswith("R_arm_ctrl") and A.twin_of(C["Mouth_fol_26_ctrl"]).endswith("L_Mouth_fol_02_ctrl"))
check("the unnamed one is the other side of its named twin (R), wherever it sits",
      A.side_of(C["Mouth_fol_26_ctrl"]) == "R" and A.side_of(C["L_Mouth_fol_02_ctrl"]) == "L"
      and A.side_of(C["Mouth_fol_14_ctrl"]) == "C")
cmds.setAttr(C["L_Mouth_fol_02_ctrl"] + ".translateY", 0.5)
cmds.select([C["L_Mouth_fol_02_ctrl"], C["Mouth_fol_26_ctrl"]])
with mock.patch.object(A, "message", lambda *a, **k: None, create=True):
    A.mirror_pose("L>R")
check("mirror pose L > R: 02's move lands on 26 (and 02 keeps it)",
      abs(cmds.getAttr(C["Mouth_fol_26_ctrl"] + ".translateY") - 0.5) < 1e-6
      and abs(cmds.getAttr(C["L_Mouth_fol_02_ctrl"] + ".translateY") - 0.5) < 1e-6)
cmds.setAttr(C["L_Mouth_fol_02_ctrl"] + ".translateY", 0.0); cmds.setAttr(C["Mouth_fol_26_ctrl"] + ".translateY", 0.0)

# Checker: side controls without a twin -> Fix links them by position (every Gus_Rigtool mirror reads links)
checker.is_control = lambda n: n in C.values()
missing = [n.split("|")[-1] for n in checker.find_twins_missing(None)]
check("Checker lists the L_ mouth controls with no twin", sorted(missing) == [
    "L_Mouth_fol_02_ctrl", "L_Mouth_fol_04_ctrl", "L_Mouth_fol_10_ctrl", "L_Mouth_fol_38_ctrl"])
n = checker.fix_twins_missing(checker.find_twins_missing(None))
check("Fix links all 4 to their mirrored twin", n == 4 and sides.get_twin(C["L_Mouth_fol_02_ctrl"]).endswith(
    "Mouth_fol_26_ctrl") and sides.get_twin(C["Mouth_fol_18_ctrl"]).endswith("L_Mouth_fol_10_ctrl"))
check("... and then none are missing", checker.find_twins_missing(None) == [])

# joints the rig turns aren't 'joints with rotate values'
loose = cmds.createNode("joint", name="loose_jnt"); cmds.setAttr(loose + ".rotateX", 20)
driven = cmds.createNode("joint", name="Mouth_fol_02_bind"); cmds.setAttr(driven + ".rotateX", 20)
pc = cmds.createNode("parentConstraint", name="Mouth_fol_02_bind_parentConstraint1", parent=driven)
cmds.addAttr(pc, longName="crx", attributeType="double")
cmds.connectAttr(pc + ".crx", driven + ".rotateX")
iks = cmds.createNode("joint", name="Ear_ik1_drv_jnt"); cmds.setAttr(iks + ".rotateZ", 15)
cmds.ikHandle = lambda h, **k: [iks] if k.get("jointList") else None
cmds.createNode("ikHandle", name="Ear_ikHandle")
rot = [x.split("|")[-1] for x in checker.find_jnt_rotate(None)]
check("rotate values: the loose joint only (not the constrained one, not the IK one)", rot == ["loose_jnt"])

# a reference's own: not leftover namespaces, not 'no suffix', Orig shapes in their own check
geo = cmds.createNode("transform", name="Geo_Hare_07:Belt")
cmds.createNode("mesh", name="Geo_Hare_07:BeltShape", parent=geo)
orig = cmds.createNode("mesh", name="Geo_Hare_07:BeltShapeOrig", parent=geo)
mine = cmds.createNode("transform", name="myBox_geo")
cmds.createNode("mesh", name="myBox_geoShape", parent=mine)
morig = cmds.createNode("mesh", name="myBox_geoShapeOrig", parent=mine)
for o in (orig, morig):
    cmds.setAttr(o + ".intermediateObject", 1)
REF = set(cmds.ls(["Geo_Hare_07:Belt", "Geo_Hare_07:BeltShape", "Geo_Hare_07:BeltShapeOrig"], long=True))
cmds.namespaceInfo = lambda ns, **k: (["Geo_Hare_07"] if k.get("listOnlyNamespaces") else
                                      ["Geo_Hare_07:Belt", "Geo_Hare_07:BeltShape"])
with mock.patch.object(cmds, "referenceQuery", side_effect=lambda x, **k: (cmds.ls(x, long=True) or [""])[0] in REF):
    check("a reference's namespace isn't 'leftover'", checker.find_namespaces(None) == [])
    suffix = [x.split("|")[-1] for x in checker.find_naming_suffix(None)]
    check("no suffix: not the reference's nodes, not constraints",
          "Geo_Hare_07:Belt" not in suffix and "Mouth_fol_02_bind_parentConstraint1" not in suffix)
    own = [x.split("|")[-1] for x in checker.find_orig_shapes(None)]
    ref = [x.split("|")[-1] for x in checker.find_orig_shapes_ref(None)]
    check("Orig shapes: yours can be deleted, the reference's are listed apart",
          own == ["myBox_geoShapeOrig"] and ref == ["Geo_Hare_07:BeltShapeOrig"])

print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
