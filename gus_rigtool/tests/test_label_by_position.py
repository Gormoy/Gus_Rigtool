# Joint labels on a hand-made rig (Tubero's joints): sided names pair by name, 'Mouth_ribbon' joints (no side in the
# name) pair by mirrored position, centre ones are Center; joints with no twin are reported
exec(open("fakemaya.py").read())
import re
from gus_rigtool.core import joint_labels as JL
rows = [re.match(r"(\S+)\s+side=.*pos=\[(.*)\]", l) for l in open("tubero_joints.txt") if "side=" in l and "pos=" in l and not l.startswith(" ")]
joints = []
for m in rows:
    if m:
        j = cmds.createNode("joint", name=m.group(1))
        cmds.xform(j, worldSpace=True, translation=[float(v) for v in m.group(2).split(",")])
        joints.append(j)
print("joints:", len(joints))
lonely = []
print("labelled:", JL.label(joints, lonely))
def lab(n):
    return (cmds.getAttr(n + ".side"), cmds.getAttr(n + ".otherType"))
for n in ("L_Eye", "R_Eye", "Mouth_ribbon_fol_07_jnt", "Mouth_ribbon_fol_15_jnt", "Mouth_ribbon_fol_01_jnt",
          "Mouth_ribbon_fol_21_jnt", "Mouth_ribbon_fol_11_jnt", "Mouth_ribbon_fol_25_jnt", "Head",
          "L_Bk_Digit_02", "R_Bk_Digit_02"):
    print("  %-26s side %d  %s" % (n, lab(n)[0], lab(n)[1]))
pairs = {}
for j in joints:
    s, t = lab(j)
    pairs.setdefault(t, []).append(s)
print("labels with exactly one Left + one Right:", sum(1 for v in pairs.values() if sorted(v) == [1, 2]),
      "| centre:", sum(1 for v in pairs.values() if v == [0]), "| other:", sorted(t for t, v in pairs.items() if sorted(v) not in ([1, 2], [0])))
print("no twin:", [(j.split("|")[-1], why) for j, why in lonely])
