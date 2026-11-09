# 4.3.0: editing what's built - follow update / copy, keep weights maths, switch to copying, face parts remember,
# Repair
exec(open("fakemaya.py").read())
import math
import numpy as np
from gus_rigtool.core import follow, ribbon, ribbon_keep as RK, face_kit, repair
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
cmds.deleteAttr = lambda node, attribute=None: _n(node).user.pop(attribute, None)
cmds.joint = lambda name=None, **k: cmds.createNode("joint", name=name)
W = lambda n: np.array(cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True)).reshape(4, 4)

# ---------------------------------------------------------------- follow: update, copy
def ctrl(name, pos):
    off = cmds.createNode("transform", name=name + "_offset"); cmds.xform(off, worldSpace=True, translation=pos)
    c = cmds.createNode("transform", name=name, parent=off); return cmds.ls(c, long=True)[0]
jaw = ctrl("jaw_ctrl", (0, 150, 2))
lip = ctrl("lowLip_ctrl", (0, 147, 9)); up = ctrl("upLip_ctrl", (0, 149, 9))
follow.add(jaw, [lip], ("rotate",), "control", 0.5)
w0 = W("lowLip_ctrl")
n = follow.update([cmds.ls("lowLip_ctrl", long=True)[0]], weight=0.8, pivot=[0, 149, 0], axes="world")
spec = follow.settings_of("lowLip_ctrl")
check("update: weight / pivot / axes changed, same driver, no jump", n == 1 and abs(spec["weight"] - 0.8) < 1e-6
      and spec["axes"] == "world" and np.allclose(spec["pivot"], [0, 149, 0]) and spec["driver"] == "jaw_ctrl"
      and np.allclose(W("lowLip_ctrl"), w0))
done, sk = follow.copy(cmds.ls("lowLip_ctrl", long=True)[0], [cmds.ls("upLip_ctrl", long=True)[0]])
s2 = follow.settings_of("upLip_ctrl")
check("copy: the other control follows the same way", done and s2["driver"] == "jaw_ctrl" and abs(s2["weight"] - 0.8) < 1e-6
      and s2["axes"] == "world")
cmds.setAttr(jaw + ".rotateX", 10)
try:
    follow.update([cmds.ls("upLip_ctrl", long=True)[0]], weight=0.2); check("update refuses a posed driver", False)
except RuntimeError:
    check("update refuses a posed driver", True)
cmds.setAttr(jaw + ".rotateX", 0)

# ---------------------------------------------------------------- keeping weights: the maths
mp = RK.mapping({"fol_01_bind": [0, 0, 0], "fol_02_bind": [1, 0, 0], "fol_03_bind": [2, 0, 0]},
                {"fol_01_bind": [0, 0, 0], "fol_03_bind": [2.1, 0, 0]})
check("mapping: same name kept, a removed joint goes to the nearest", mp == {"fol_01_bind": "fol_01_bind",
                                                                         "fol_02_bind": "fol_01_bind",
                                                                         "fol_03_bind": "fol_03_bind"})
merged = RK.merge({"fol_01_bind": [0.5, 0.1], "fol_02_bind": [0.25, 0.0], "fol_03_bind": [0.0, 0.6]}, mp)
check("merge: weights add up into the kept joints", merged == {"fol_01_bind": [0.75, 0.1], "fol_03_bind": [0.0, 0.6]})

# ---------------------------------------------------------------- switch to copying (and back)
top = cmds.createNode("transform", name="Lip_ribbon_ctrls_grp")
bgrp = cmds.createNode("transform", name="Lip_ribbon_bind_grp")
for g in (top, bgrp):
    for a, v in (("rrbSurface", "Lip_ribbon"), ("rrbSkin", ""), ("rrbSettings", '{"prefix": "Lip_ribbon", "pivot_on_shape": true}')):
        cmds.addAttr(g, longName=a, dataType="string"); cmds.setAttr(g + "." + a, v, type="string")
cmds.createNode("transform", name="Lip_ribbon")
for i, x in enumerate((3, -3)):
    off = cmds.createNode("transform", name="p%d_offset" % i, parent=top)
    cmds.addAttr(off, longName="rrbIndex", attributeType="long"); cmds.setAttr(off + ".rrbIndex", i)
    cmds.xform(off, worldSpace=True, matrix=[math.cos(0.3), 0, -math.sin(0.3), 0, 0, 1, 0, 0, math.sin(0.3), 0, math.cos(0.3), 0, x, 0, 10, 1])
    c = cmds.createNode("transform", name="p%d_ctrl" % i, parent=off)
    cmds.createNode("nurbsCurve", name="p%d_ctrlShape" % i, parent=c)
    j = cmds.createNode("joint", name="p%d_bind" % i, parent=bgrp)
    cmds.xform(j, worldSpace=True, translation=(x, 0, 9))
    ribbon._constrain_bind(cmds.ls(c, long=True)[0], cmds.ls(j, long=True)[0])
before = {i: W("p%d_bind" % i)[3, :3] for i in range(2)}
n = ribbon.to_copying("Lip_ribbon")
modes = sorted({ribbon.bind_of(cmds.ls("p%d_ctrl" % i, long=True)[0])[1] for i in range(2)})
check("switch to copying: joints copy their controls, nothing moved", n == 2 and modes == ["copy"]
      and all(np.allclose(W("p%d_bind" % i)[3, :3], before[i]) for i in range(2)))
check("each joint in its own group, axes of its control", cmds.ls("p0_bind", long=True)[0].split("|")[-2] == "p0_bind_offset"
      and np.allclose(W("p0_bind_offset")[:3, :3], W("p0_offset")[:3, :3]))
n = ribbon.to_constraints("Lip_ribbon")
check("and back to constraints", n == 2 and sorted({ribbon.bind_of(cmds.ls("p%d_ctrl" % i, long=True)[0])[1]
                                                    for i in range(2)}) == ["constraints"])

# ---------------------------------------------------------------- face parts remember how they were made
cmds.createNode("transform", name="L_Eyelid_Ribbon")
face_kit._remember("L_Eyelid_Ribbon", "eyelids", edges=["head.e[1:9]"], eye_ctrl="L_Eye_ctrl", side="L",
                   style="cartoony", do_mirror=True)
p = face_kit.part_of("L_Eyelid_Ribbon")
check("a face part remembers its edges and settings", p["part"] == "eyelids" and p["edges"] == ["head.e[1:9]"]
      and p["eye_ctrl"] == "L_Eye_ctrl")
try:
    face_kit.redo("Lip_ribbon"); check("redo refuses a ribbon the Face tab didn't make", False)
except RuntimeError:
    check("redo refuses a ribbon the Face tab didn't make", True)

# ---------------------------------------------------------------- repair
for i in range(2):
    c = cmds.ls("p%d_ctrl" % i, long=True)[0]
    ribbon.to_copying("Lip_ribbon") if i == 0 else None
lonely = cmds.createNode("transform", name="lonely_holder")
pc = cmds.createNode("parentConstraint", name="lonely_holder_parentConstraint1", parent=lonely)
items = {it.id: it for it in repair.find()}
check("repair finds: ribbon copying, constraint with no target", "ribbon_constraints" in items and "empty_constraints" in items)
out = repair.apply(["ribbon_constraints", "empty_constraints"])
check("repair applies them", not cmds.ls("lonely_holder_parentConstraint1") and
      ribbon.bind_of(cmds.ls("p0_ctrl", long=True)[0])[1] == "constraints")
check("after repair: nothing left of those", not any(it.id in ("ribbon_constraints", "empty_constraints")
                                                    for it in repair.find()))
print("ALL OK" if all(ok) else "SOME FAILED")
