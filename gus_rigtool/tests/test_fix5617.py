# 5.6.17: the pass-through mesh copies (Make before 5.6.17 left one per mesh each time) are found and cleaned -
# the skin's own output, the original and the shape you see stay; the head squash box takes in the ears' bases
# (one per side, the lowest); the riders' follicles grow with the head (no drift at x2); the poses list drops
# poses whose sliders are gone; the board: each knob in an offset group (rests at 0), beside the face, the shift
# slider under the amount slider; its frames and labels aren't controls for the checker
import sys, json
exec(open("fakemaya.py").read())
from gus_rigtool.core import head_squash as HS, face_poses as FP
from gus_rigtool.tools import checker
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- the copies: skinCluster -> Deformed (int) -> DeformedDeformed (int, pass-through) -> ffd -> visible
body = cmds.createNode("transform", name="Hare_Body")
orig = cmds.createNode("mesh", name="Hare_BodyShapeOrig", parent=body)
d1 = cmds.createNode("mesh", name="Hare_BodyShapeDeformed", parent=body)
d2 = cmds.createNode("mesh", name="Hare_BodyShapeDeformedDeformed", parent=body)
d3 = cmds.createNode("mesh", name="Hare_BodyShapeDeformedDeformedDeformed", parent=body)
vis = cmds.createNode("mesh", name="Hare_BodyShape", parent=body)
for m in (orig, d1, d2, d3):
    cmds.setAttr(m + ".intermediateObject", 1)
skin = cmds.createNode("skinCluster", name="skinCluster10")
ffd = cmds.createNode("ffd", name="Head_squashFfd")
cmds.connectAttr(orig + ".worldMesh[0]", skin + ".input[0].inputGeometry")
cmds.connectAttr(skin + ".outputGeometry[0]", d1 + ".inMesh")
cmds.connectAttr(d1 + ".worldMesh[0]", d2 + ".inMesh")
cmds.connectAttr(d2 + ".worldMesh[0]", d3 + ".inMesh")
cmds.connectAttr(d3 + ".worldMesh[0]", ffd + ".input[0].inputGeometry")
cmds.connectAttr(ffd + ".outputGeometry[0]", vis + ".inMesh")
got = sorted(c.split("|")[-1] for c, _s, _d in HS.mesh_copies("Hare_Body"))
print(got)
check("the copies: the two fed by another mesh (not the skin's output, not the original, not the visible shape)",
      got == ["Hare_BodyShapeDeformedDeformed", "Hare_BodyShapeDeformedDeformedDeformed"])
n = HS.clean_copies(["Hare_Body"])
left = sorted(s.split("|")[-1] for s in cmds.listRelatives(body, shapes=True) or [])
check("cleaned: 2 gone, the chain joined (skin -> its shape -> the lattice -> the shape you see)",
      n == 2 and left == ["Hare_BodyShape", "Hare_BodyShapeDeformed", "Hare_BodyShapeOrig"] and
      (cmds.listConnections(ffd + ".input[0].inputGeometry", source=True, destination=False) or [""])[0]
      .split("|")[-1] == "Hare_BodyShapeDeformed")
check("again: nothing to clean", HS.clean_copies(["Hare_Body"]) == 0 and not HS.mesh_copies("Hare_Body"))
check("the lattice is placed without 'after' (that's what made Maya copy the mesh)",
      "after=True" not in open("../core/head_squash.py").read())

# --- the box takes in the ears' bases
def mk(name, parent=None, pos=(0, 0, 0)):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=pos)
    t = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
head = mk("Head_01_CTRL", None, (0, 70, 0))
lg = cmds.ls(cmds.parent(cmds.createNode("transform", name="L_Ear_ctrls_grp"), head)[0], long=True)[0]
e1 = mk("L_Ear_01_FK_ctrl", lg, (5, 130, -2)); mk("L_Ear_02_FK_ctrl", e1, (6, 160, -3))
centre, size = (0, 90, 0), (20, 30, 20)                          # the face: 75 .. 105
c2, s2 = HS._with_ears(centre, size)
top = c2[1] + s2[1] / 2.0
print(c2, s2)
check("the box reaches past the ear's base (130 + a tenth: 133), not up to the tip (160)",
      abs(top - 133) < 1e-6 and c2[1] - s2[1] / 2.0 == 75)
src = open("../core/head_squash.py").read()
check("the follow point grows with the head: decomposeMatrix of the head -> the follicle's scale",
      'dm + ".outputScale", ft + ".scale"' in src and 'head + ".worldMatrix[0]", dm + ".inputMatrix"' in src)
check("the squash keeps full mesh paths (two meshes of the same short name)", '"meshes": list(meshes)' in src)

# --- poses whose sliders are gone
holder = mk("Mouth_main_ctrl", None, (0, 80, 10))
cmds.addAttr(holder, longName="Smile_L", attributeType="double")
cmds.addAttr(holder, longName="Smile_R", attributeType="double")
cmds.addAttr(holder, longName="Wide", attributeType="double")
nd = cmds.createNode("multDoubleLinear", name="Frown_md")
FP._write(holder, {"Smile": {"split": True, "attrs": ["Smile_L", "Smile_R"], "ctrls": {}},
                   "Frown": {"split": False, "attrs": ["Frown"], "ctrls": {"a": {"nodes": ["Frown_md"]}}},
                   "Wide": {"split": False, "attrs": ["Wide"], "ctrls": {}}})
with mock.patch("gus_rigtool.core.group_ctrls._drop_empty_layers"):
    gone = FP.clean(holder)
check("Refresh: Frown dropped (its slider is gone), its node with it; Smile and Wide stay",
      gone == ["Frown"] and FP.poses(holder) == ["Smile", "Wide"] and not cmds.objExists("Frown_md"))
from gus_rigtool.tools import face_kit_tool as FK
check("a Refresh button in Expressions", "clean_poses" in open("../tools/face_kit_tool.py").read() and
      hasattr(FK, "clean_poses") and hasattr(FK, "clean_copies"))

# --- the board
from gus_rigtool.core import face_sliders as FS
fr = FS._frame("Smile_slider_frame", -1, -5, 2, 10, head)
kn = FS._knob("Smile_amount_ctrl", 1, head, (0, -5))
off = cmds.listRelatives(kn, parent=True, fullPath=True)[0]
check("the knob in its own offset group at the slider's bottom; the knob itself at 0",
      off.endswith("Smile_amount_ctrl_offset") and cmds.getAttr(off + ".translate")[0] == (0, -5, 0) and
      tuple(cmds.getAttr(kn + ".translate")[0]) == (0, 0, 0))
check("frames are not controls for the checker; the knob is", not checker.is_control(fr) and checker.is_control(kn))
fs = open("../core/face_sliders.py").read()
check("beside the face at its middle, the shift slider just under the amount one, no 0.06 offset",
      "centre[1],\n" in fs and "shift_y = bottom - size * 0.2" in fs and "size * 0.06)" not in fs)

print("%d/%d passed" % (sum(ok), len(ok)))
