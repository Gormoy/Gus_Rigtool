# 5.6.38: real-Maya test f keys the IK control after moving it (the switch had keyed it, so the move was undone
# and 5.6.37's 'no jump' passes measured an arm that never moved), and checks the arm really moved first
import os
src = open(os.path.join(os.getcwd(), "..", "realmaya", "maya_cases.py")).read()
f = src[src.index("def ikfk_mirror"):src.index("def rig_selftest")]
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
check("the move is keyed right after it", f.index("cmds.move(") < f.index("cmds.setKeyframe(c") <
      f.index("spots = _arm_spots()"))
check("the arm must have moved more than half a unit, or the test stops and says so",
      "went > 0.5" in f and f.index("went > 0.5") < f.index('"switch to FK"'))
print("%d/%d passed" % (sum(ok), len(ok)))
