# Joint labels and left / right symmetry (3.12.1): side + name labels for skin mirroring (ngSkinTools / Maya by
# label), twin joints that aren't mirror images (why a mirror by distance picks the wrong joint), the Checker item,
# labels set by every Build
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from gus_rigtool.core import joint_labels as JL
print("split:", [JL.split_side(n) for n in ("L_eye", "R_Nostril", "Head", "eye_L", "hare:Lf_ear_jnt")])
print("twins:", [JL.twin_name(n) for n in ("L_eye", "R_Nostril", "Head", "eye_l", "hare:L_ear_jnt")])
J = {}
for name, pos in (("Head", (0, 10, 0)), ("L_eye", (2, 10, 1)), ("R_eye", (-2, 10, 1)), ("L_Nostril", (1, 8, 1)),
                  ("R_Nostril", (-1.4, 8.2, 1)), ("L_ear", (1, 12, 0))):
    j = cmds.createNode("joint", name=name); cmds.xform(j, worldSpace=True, translation=pos); J[name] = j
print("labelled:", JL.label(list(J.values())), "| L_eye:", cmds.getAttr("L_eye.side"), cmds.getAttr("L_eye.type"),
      cmds.getAttr("L_eye.otherType"), "| R_eye:", cmds.getAttr("R_eye.side"), cmds.getAttr("R_eye.otherType"),
      "| Head:", cmds.getAttr("Head.side"), cmds.getAttr("Head.otherType"))
bad = JL.not_mirrored(list(J.values()))
print("not mirror images:", [(a.split("|")[-1], b.split("|")[-1] if b else None, round(o, 2) if o else o) for a, b, o in bad])
from gus_rigtool.tools import checker
JL.rig_joints = lambda: list(J.values())
print("checker:", [n.split("|")[-1] for n in checker.find_jnt_not_mirrored(None)])
# every Build labels the skeleton
from gus_rigtool.builder import build as bld
bld.biped(180); bld.build_all(180)
print("after Build:", [(n, cmds.getAttr(n + ".side"), cmds.getAttr(n + ".otherType")) for n in ("L_humerus_jnt", "R_humerus_jnt", "spine_jnt")])
