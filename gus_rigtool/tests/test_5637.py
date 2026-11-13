# 5.6.37: real-Maya test f puts both arms in IK before moving the wrist's IK control (the biped's arms start in
# FK: 5.6.36 moved an IK control nothing followed, and 'to FK' rightly snapped the arm to it - read as a jump)
import os
src = open(os.path.join(os.getcwd(), "..", "realmaya", "maya_cases.py")).read()
f = src[src.index("def ikfk_mirror"):src.index("def rig_selftest")]
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
check("both arms (the left IK control and its right twin) go to IK first", 'A.switch, "ik")' in f and
      '"r_" + c.split("|")[-1][2:].lower()' in f)
check("going to IK at rest is checked too: nothing may move", "to IK at rest: nothing moved" in f)
check("in that order: to IK, then the move, then to FK and back, then the mirror",
      f.index("both arms to IK") < f.index("cmds.move(") < f.index('"switch to FK"') < f.index('"switch to IK"')
      < f.index('"mirror pose L>R"'))
print("%d/%d passed" % (sum(ok), len(ok)))
