# 5.3.5: transform limits on controls - set (min 0 / max -65 swapped to -65..0), from the pose, mirrored to the twin
# (flipped where the twin's channel goes the other way), cleared; Check this scene lists them
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import limits
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def ctrl(name, parent=None):
    t = cmds.createNode("transform", name=name, parent=parent)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    for pre in ("Trans", "Rot", "Scale"):
        for ax in "XYZ":
            for side in ("min", "max"):
                cmds.addAttr(t, longName="%s%s%sLimit" % (side, pre, ax), attributeType="double")
                cmds.addAttr(t, longName="%s%s%sLimitEnable" % (side, pre, ax), attributeType="bool")
    return cmds.ls(t, long=True)[0]

lo = cmds.createNode("transform", name="L_Lid_offset")
ro = cmds.createNode("transform", name="R_Lid_offset")
cmds.setAttr(ro + ".scaleX", -1)                         # a behaviour-mirrored right side
L = ctrl("L_Lid_ctrl", lo)
R = ctrl("R_Lid_ctrl", ro)
limits.set_limit([L], "ty", 0, 32)
limits.set_limit([L], "tz", 0, -65)
check("ty 0..32", limits.get(L, "ty") == (0, 32))
check("'min 0 max -65' becomes -65..0", limits.get(L, "tz") == (-65, 0))
limits.set_limit([L], "tx", None, 5)
check("one side only: no min, max 5", limits.get(L, "tx") == (None, 5))
cmds.setAttr(L + ".rotateZ", 30)
limits.from_pose([L], "rz", "max")
check("max from the pose (rotateZ 30)", limits.get(L, "rz") == (None, 30))
done, alone = limits.mirror([L])
print(done)
c, t, chans, flipped = done[0]
check("mirrored on R_Lid_ctrl: every limited channel", t.endswith("R_Lid_ctrl") and sorted(chans) ==
      ["rz", "tx", "ty", "tz"])
check("behaviour mirror (-1 scale X): every channel keeps its values (the twin moves / turns the mirrored way)",
      limits.get(R, "tx") == (None, 5) and limits.get(R, "ty") == (0, 32) and limits.get(R, "tz") == (-65, 0) and
      limits.get(R, "rz") == (None, 30) and flipped == [])
# a twin turned 180 degrees instead (no negative scale): tz goes the other way -> 0..65 flips to -65..0 and back
lo2 = cmds.createNode("transform", name="L_Brow_offset")
ro2 = cmds.createNode("transform", name="R_Brow_offset")
cmds.setAttr(ro2 + ".rotateY", 180)
L2 = ctrl("L_Brow_ctrl", lo2)
R2 = ctrl("R_Brow_ctrl", ro2)
limits.set_limit([L2], "tz", 0, 65)
limits.set_limit([L2], "ty", 0, 32)
limits.set_limit([L2], "rz", -10, 20)
done3, _a = limits.mirror([L2])
print(done3)
check("turned twin: tz 0..65 -> -65..0 (what you set by hand on the Hare), ty the same",
      limits.get(R2, "tz") == (-65, 0) and limits.get(R2, "ty") == (0, 32))
check("turned twin: rotateZ the same (it turns the mirrored way already)", limits.get(R2, "rz") == (-10, 20))
done2, _a = limits.mirror([L], mode="same")
check("'Same values' copies them as they are", limits.get(R, "tx") == (None, 5))
n = limits.clear([R], "tx")
check("clear one channel", n == 1 and limits.get(R, "tx") == (None, None) and limits.get(R, "ty") == (0, 32))
limits.clear([R])
check("clear all", limits.limited(R) == {})
print(limits.describe(L))
check("describe", "ty 0..32" in limits.describe(L) and "tz -65..0" in limits.describe(L))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
