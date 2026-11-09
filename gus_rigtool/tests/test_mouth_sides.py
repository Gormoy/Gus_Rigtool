# 4.0.2: Tubero's mouth - labels pair fol_02 / fol_20 (0.06 off) and keep _jnt with _jnt, _bind with _bind;
# a loop ribbon's right-side controls get mirrored axes with nothing moving
exec(open("fakemaya.py").read())
import re, math
from gus_rigtool.core import joint_labels as JL, ribbon
rows = [re.match(r"(\S+) side .*\[(.*)\]", l) for l in open("tubero_mouth.txt") if l.startswith("Mouth_ribbon")]
js = []
for m in rows:
    j = cmds.createNode("joint", name=m.group(1))
    cmds.xform(j, worldSpace=True, translation=[float(v) for v in m.group(2).split(",")])
    js.append(j)
lonely = []
JL.label(js, lonely)
lab = lambda n: (cmds.getAttr(n + ".side"), cmds.getAttr(n + ".otherType"))
print("joints:", len(js), "| no twin:", lonely)
for n in ("Mouth_ribbon_fol_02_jnt", "Mouth_ribbon_fol_20_jnt", "Mouth_ribbon_fol_11_jnt", "Mouth_ribbon_fol_25_jnt",
          "Mouth_ribbon_fol_01_bind", "Mouth_ribbon_fol_21_bind", "Mouth_ribbon_fol_01_jnt", "Mouth_ribbon_fol_21_jnt"):
    print("  %-26s %s" % (n, lab(n)))
mixed = [j for j in js if any(k != j and lab(k)[1] == lab(j)[1] and lab(k)[0] != lab(j)[0] and
                              k.endswith("_bind") != j.endswith("_bind") for k in js)]
print("a _jnt paired with a _bind:", mixed)

# --- mirror_sides on a small loop: 4 controls round the mouth (pivot on the shape: joints copy the controls),
# the right ones turned the wrong way
top = cmds.createNode("transform", name="Mouth_ribbon_ctrls_grp")
bgrp = cmds.createNode("transform", name="Mouth_ribbon_bind_grp")
for g in (top, bgrp):
    cmds.addAttr(g, longName="rrbSurface", dataType="string"); cmds.setAttr(g + ".rrbSurface", "Mouth_ribbon", type="string")
    cmds.addAttr(g, longName="rrbSkin", dataType="string"); cmds.setAttr(g + ".rrbSkin", "", type="string")
cmds.createNode("transform", name="Mouth_ribbon")
def make(i, x, y, yaw):
    off = cmds.createNode("transform", name="m%d_offset" % i, parent=top)
    cmds.addAttr(off, longName="rrbIndex", attributeType="long"); cmds.setAttr(off + ".rrbIndex", i)
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    m = [c, 0, -s_, 0, 0, 1, 0, 0, s_, 0, c, 0, x, y, 10, 1]
    cmds.xform(off, worldSpace=True, matrix=m)
    ctrl = cmds.createNode("transform", name="m%d_ctrl" % i, parent=off)
    cmds.createNode("nurbsCurve", name="m%d_ctrlShape" % i, parent=ctrl)
    boff = cmds.createNode("transform", name="m%d_bind_offset" % i, parent=bgrp)
    cmds.xform(boff, worldSpace=True, matrix=m[:12] + [x, y, 9.0, 1])
    b = cmds.createNode("joint", name="m%d_bind" % i, parent=boff)
    cmds.connectAttr(ctrl + ".translate", b + ".translate")
    return off, ctrl, b
made = [make(0, 3, 0, 20), make(1, 0, 1, 0), make(2, -3, 0, 200), make(3, 0, -1, 180)]
W = lambda n: cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True)
before = {n: W("m%d_bind" % n)[12:15] for n in range(4)}
done = ribbon.mirror_sides("Mouth_ribbon")
L, R = W("m0_offset"), W("m2_offset")
print("done:", done)
print("right control: X mirrors the left's (outward on both):", [round(v, 3) for v in R[0:3]], "vs left", [round(v, 3) for v in L[0:3]],
      "| Y the same:", [round(v, 3) for v in R[4:7]], "| Z the same:", [round(v, 3) for v in R[8:11]], "vs", [round(v, 3) for v in L[8:11]])
BL, BR = W("m0_bind_offset"), W("m2_bind_offset")
print("its joint's group turned the same way:", [round(v, 3) for v in BR[0:3]] == [round(v, 3) for v in R[0:3]],
      "| joints stay put:", all(max(abs(a - b) for a, b in zip(before[n], W("m%d_bind" % n)[12:15])) < 1e-6 for n in range(4)))
print("centre ones untouched:", [round(v, 3) for v in W("m1_offset")[0:3]])
print("bind group follows the controls' group:", ribbon.link_bind_group("Mouth_ribbon"),
      bool(cmds.listRelatives(cmds.ls("Mouth_ribbon_bind_grp", long=True)[0], type="parentConstraint")))
