# 5.6.34: the pupils - Keep the pose leaves a control whose own values drive something (their rotate feeds the
# eyeballs' orient constraints), runs through safe mode, no longer unlocks; the Checker leaves out locked channels
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import zero_pose, safe
from gus_rigtool.tools import checker, behaviour_tool
ok = []
def reset():
    S.__init__()
    _LOCKED.clear()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

def hare_pupil():
    reset()
    createNode("transform", name="L_Pupil_ctrl_rest")
    createNode("transform", name="L_Pupil_ctrl", parent="L_Pupil_ctrl_rest")
    createNode("nurbsCurve", name="L_Pupil_ctrlShape", parent="L_Pupil_ctrl")
    createNode("orientConstraint", name="L_Eyeball_jnt_orientConstraint1")
    createNode("joint", name="L_Pupil_jnt")
    c = ls("L_Pupil_ctrl", long=True)[0]
    setAttr(c + ".translateZ", 9.7461)
    setAttr(c + ".rotateY", -37.6547)
    setAttr(c + ".rotateX", -720.0)
    connectAttr(c + ".rotate", "L_Eyeball_jnt_orientConstraint1.target[0].targetRotate")
    connectAttr(c + ".scale", "L_Pupil_jnt.scale")
    for a in ("translate", "rotate"):
        for x in "XYZ":
            setAttr("%s.%s%s" % (c, a, x), lock=True)
    return c

# --- 1. the pupils as they are in the Hare
c = hare_pupil()
check("what the pupil's own values feed is found: rotate into the eyeball's orient constraint",
      ("L_Pupil_ctrl.rotate", "L_Eyeball_jnt_orientConstraint1.target[0].targetRotate") in zero_pose.feeds(c))
done, skipped = zero_pose.apply([c])
check("Keep the pose leaves it and says why (5.6.33 zeroed it and the eyes turned)",
      not done and skipped and "drive something" in skipped[0][1] and "orientConstraint" in skipped[0][1])
check("nothing changed on it", getAttr(c + ".rotateY") == -37.6547 and getAttr(c + ".translateZ") == 9.7461 and
      getAttr(c + ".rotateX", lock=True))
with mock.patch.object(checker, "transforms", lambda scope: [c]):
    check("Checker: locked channels aren't the animator's - the pupils aren't 'not at zero'",
          checker.find_ctrl_zero(None) == [])
setAttr(c + ".scaleX", 1.5)
with mock.patch.object(checker, "transforms", lambda scope: [c]):
    check("a free channel off rest still counts (scale X 1.5)", checker.find_ctrl_zero(None) == [c])

# --- 2. a plain control still zeroes as before
reset()
createNode("transform", name="Arm_grp")
createNode("transform", name="Arm_ctrl", parent="Arm_grp")
createNode("nurbsCurve", name="Arm_ctrlShape", parent="Arm_ctrl")
ac = ls("Arm_ctrl", long=True)[0]
setAttr(ac + ".translateX", 3.0)
done, skipped = zero_pose.apply([ac])
check("a control that feeds nothing: zeroed, its group took the pose", done and not skipped and
      getAttr(ls("Arm_ctrl", long=True)[0] + ".translateX") == 0 and getAttr("Arm_grp.translateX") == 3.0)

# --- 3. the button runs through safe mode
reset()
createNode("transform", name="Arm_grp")
createNode("transform", name="Arm_ctrl", parent="Arm_grp")
createNode("nurbsCurve", name="Arm_ctrlShape", parent="Arm_ctrl")
cmds.select("Arm_ctrl")
warned, seen = [], []
def fake_run(fn, label="", states=()):
    seen.append((label, states))
    return False, "undone - it moved: L_Eye_geo"
with mock.patch.object(safe, "run", fake_run), \
        mock.patch.object(behaviour_tool.utils, "warn", lambda tool, msg: warned.append(msg)):
    behaviour_tool.zero_here()
check("Behaviour > Keep the pose goes through safe mode: something moved, so it's put back and named",
      seen and seen[0][1] == ("rest",) and warned and "put back" in warned[0] and "L_Eye_geo" in warned[0])

print("%d/%d passed" % (sum(ok), len(ok)))
