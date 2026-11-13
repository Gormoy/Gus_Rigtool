# 5.6.33: the bandages' history (Maya 2024's real classification text), the pupils' locked channels zeroed by Keep
# the pose without moving them, the Checker's zero fix honest about what it can't change, the Joints / Face fields
# that made "Step must be less than range"
import os, re, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import zero_pose
from gus_rigtool.tools import checker
ok = []
def reset():
    S.__init__()
    _LOCKED.clear()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- 1. the history check with what Maya 2024 really answers
MAYA = {"condition": ["drawdb/shader/operation/condition:utility/general"],
        "plusMinusAverage": ["drawdb/shader/operation/plusMinusAverage:math/operation"],
        "polySmoothFace": [""]}
reset()
for t, n in (("condition", "Clothes_Bandages_hidden"), ("plusMinusAverage", "Clothes_Bandages_pma"),
             ("polySmoothFace", "polySmoothFace1")):
    createNode(t, name=n)
with mock.patch.object(cmds, "getClassification", lambda t, **k: MAYA.get(t, [""])):
    check("Maya 2024's 'drawdb/...:utility/general' and 'math/operation': both seen as settings",
          checker._drives_a_setting("Clothes_Bandages_hidden") and checker._drives_a_setting("Clothes_Bandages_pma"))
with mock.patch.object(cmds, "getClassification", lambda t, **k: [""]):
    check("and by name, whatever Maya answers", checker._drives_a_setting("Clothes_Bandages_pma"))
with mock.patch.object(cmds, "listHistory", lambda *a, **k: ["Clothes_Bandages_hidden", "Clothes_Bandages_pma",
                                                               "polySmoothFace1"]), \
        mock.patch.object(cmds, "getClassification", lambda t, **k: MAYA.get(t, [""])):
    check("the bandages: only real model history is listed", checker._non_deformer_history("x") == ["polySmoothFace1"])

# --- 2. the pupils: locked channels off rest (Gus's numbers)
def pupil():
    reset()
    createNode("transform", name="L_Pupil_ctrl_grp")
    createNode("transform", name="L_Pupil_ctrl", parent="L_Pupil_ctrl_grp")
    createNode("nurbsCurve", name="L_Pupil_ctrlShape", parent="L_Pupil_ctrl")
    c = ls("L_Pupil_ctrl", long=True)[0]
    for a, v in (("translateZ", 9.7461), ("rotateX", -720.0), ("rotateY", -37.6547), ("rotateZ", 720.0)):
        setAttr(c + "." + a, v)
    for a in ("translate", "rotate"):
        for x in "XYZ":
            setAttr("%s.%s%s" % (c, a, x), lock=True)
    setAttr(c + ".scaleZ", lock=True)
    return c
warned = []
c = pupil()
with mock.patch.object(checker.utils, "warn", lambda tool, msg: warned.append(msg)):
    fixed = checker.fix_ctrl_zero([c])
check("Checker > Controls not at zero > Fix: 0 fixed, not '2' (all locked), and it says which and where to go",
      fixed == 0 and warned and "L_Pupil_ctrl.translateZ 9.746 (locked)" in warned[0] and "Keep the pose" in warned[0])
before = cmds.xform(c, query=True, worldSpace=True, matrix=True)
done, skipped = zero_pose.apply([c])
c = ls("L_Pupil_ctrl", long=True)[0]
vals = [getAttr("%s.%s%s" % (c, a, x)) for a in ("translate", "rotate") for x in "XYZ"]
check("Keep the pose: the locked channels read 0 now (5.6.32 left 9.75, -720, -37.65, 720)",
      done and not skipped and all(abs(v) < 1e-6 for v in vals))
check("they're locked again, as you left them", all(getAttr("%s.%s%s" % (c, a, x), lock=True)
                                                    for a in ("translate", "rotate") for x in "XYZ") and
      getAttr(c + ".scaleZ", lock=True) and not getAttr(c + ".scaleX", lock=True))
check("the pupil stays where it was (its group took the pose)",
      all(abs(a - b) < 1e-4 for a, b in zip(cmds.xform(c, query=True, worldSpace=True, matrix=True), before)))
with mock.patch.object(checker, "transforms", lambda scope: [c]):
    check("the Checker has nothing left to say", checker.find_ctrl_zero(None) == [])

# --- 3. a channel something drives stays, and Keep the pose says so
reset()
createNode("transform", name="Jaw_grp")
createNode("transform", name="Jaw_ctrl", parent="Jaw_grp")
createNode("nurbsCurve", name="Jaw_ctrlShape", parent="Jaw_ctrl")
createNode("multiplyDivide", name="Jaw_md")
jc = ls("Jaw_ctrl", long=True)[0]
setAttr(jc + ".translateX", 2.0)
setAttr(jc + ".rotateY", 5.0)
connectAttr("Jaw_md.outputX", jc + ".rotateY")
setAttr(jc + ".rotateY", 5.0)
with mock.patch.object(zero_pose, "constraints_on", lambda c: ([], None)):
    done, skipped = zero_pose.apply([jc])
check("a driven channel: left as it is and listed", zero_pose.LEFT and zero_pose.LEFT[0][1].startswith("rotateY "
                                                                                                   "driven"))

# --- 4. the fields behind "Step must be less than range"
for f, names in (("../tools/joint_chain.py", ("Pad", "IKCount")), ("../tools/face_kit_tool.py", ("BrowCount",))):
    src = open(f).read()
    for n in names:
        made = [m.group(0) for m in re.finditer(r'Field\(N\("%s"\)[^\n]*(\n[^\n]*)?' % n, src)
                if "query=True" not in m.group(0) and "edit=True" not in m.group(0)]
        check("%s: a step of 1 inside its small range (Maya's default step 10 is bigger)" % n,
              made and all("step=1" in x for x in made))

print("%d/%d passed" % (sum(ok), len(ok)))
