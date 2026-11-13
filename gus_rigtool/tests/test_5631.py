# 5.6.31: Keep the pose moves aim constraints too (the Hare's pupils), the Checker's history fix puts back a mesh
# that moved (the left eye), Check this scene says what the history is and where to clean it, Remove head squash
# leaves no switch node behind
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import zero_pose, head_squash as HS, safe, report as R
from gus_rigtool import scene_check
from gus_rigtool.tools import checker
ok = []
def reset():
    S.__init__()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- 1. the pupils: an aim constraint on the control
reset()
createNode("transform", name="Eye_target")
createNode("transform", name="Head_ctrl")
createNode("transform", name="L_Pupil_ctrl_offset")
createNode("transform", name="L_Pupil_ctrl", parent="L_Pupil_ctrl_offset")
createNode("nurbsCurve", name="L_Pupil_ctrlShape", parent="L_Pupil_ctrl")
pc = ls("L_Pupil_ctrl", long=True)[0]
setAttr(pc + ".translateX", 2.0)
cmds.aimConstraint("Eye_target", pc, maintainOffset=True)
before = cmds.xform(pc, query=True, worldSpace=True, matrix=True)
cons, why = zero_pose.constraints_on(pc)
check("an aim constraint on the control can be moved now (5.6.30 said 'move it by hand')",
      [cmds.nodeType(c) for c in cons] == ["aimConstraint"] and why is None)
real_aim = cmds.aimConstraint
made = []
def aim(*a, **k):
    if k.get("query"):
        got = {"aimVector": [0.0, 0.0, 1.0], "upVector": [0.0, 1.0, 0.0], "worldUpType": "object",
               "worldUpObject": "Head_ctrl"}
        for f in zero_pose.AIM_FLAGS:
            if k.get(f):
                return got.get(f)
        return real_aim(*a, **k)
    made.append(dict(k))
    return real_aim(*a, **{x: v for x, v in k.items() if x in ("maintainOffset", "name")})
with mock.patch.object(cmds, "aimConstraint", aim):
    done, skipped = zero_pose.apply([pc])
pc = ls("L_Pupil_ctrl", long=True)[0]
grp = cmds.listRelatives(pc, parent=True, fullPath=True)[0]
check("zeroed: the control reads 0, the aim is on its group, the control stays where it was",
      done and not skipped and getAttr(pc + ".translateX") == 0 and not zero_pose.constraints_on(pc)[0] and
      [cmds.nodeType(c) for c in zero_pose.constraints_on(grp)[0]] == ["aimConstraint"] and
      all(abs(a - b) < 1e-6 for a, b in zip(cmds.xform(pc, query=True, worldSpace=True, matrix=True), before)))
check("the new aim keeps the old one's settings: aim Z, up Y, world up the head (object)",
      made and made[-1].get("aimVector") == [0.0, 0.0, 1.0] and made[-1].get("upVector") == [0.0, 1.0, 0.0] and
      made[-1].get("worldUpType") == "object" and made[-1].get("worldUpObject") == "Head_ctrl" and
      made[-1].get("maintainOffset"))
with mock.patch.object(cmds, "aimConstraint", lambda *a, **k: {"worldUpType": "vector", "worldUpObject": "x"}.get(
        next((f for f in zero_pose.AIM_FLAGS if k.get(f)), ""))):
    flags = zero_pose._aim_flags("c")
check("its own settings read one by one", flags == {"worldUpType": "vector", "worldUpObject": "x"})

# --- 2. the Checker's history fix: a mesh that moves is put back
reset()
createNode("transform", name="L_Eye_geo")
createNode("mesh", name="L_Eye_geoShape", parent="L_Eye_geo")
warned = []
with mock.patch.object(safe, "run", lambda fn, label="", states=(): (False, "undone - it moved")), \
        mock.patch.object(cmds, "referenceQuery", lambda *a, **k: False, create=True), \
        mock.patch.object(checker.utils, "warn", lambda tool, msg: warned.append(msg)):
    n = checker.fix_mesh_history([ls("L_Eye_geo", long=True)[0]])
check("the left eye moved when its history went: put back, and said (keep that history)",
      n == 0 and warned and "moved when their history went, so it was put back: L_Eye_geo" in warned[0])
with mock.patch.object(safe, "run", lambda fn, label="", states=(): (True, fn())), \
        mock.patch.object(cmds, "referenceQuery", lambda *a, **k: False, create=True), \
        mock.patch.object(cmds, "bakePartialHistory", lambda *a, **k: None, create=True):
    n = checker.fix_mesh_history([ls("L_Eye_geo", long=True)[0]])
check("a mesh that doesn't move loses its history as before", n == 1)

# --- 3. Check this scene: what the history is and where to clean it
with mock.patch.object(checker, "_shapes", lambda n: ["shape"]), \
        mock.patch.object(checker, "_non_deformer_history", lambda s: ["transformGeometry1"]), \
        mock.patch.object(cmds, "nodeType", lambda n: "transformGeometry"), \
        mock.patch.object(cmds, "referenceQuery", lambda *a, **k: True, create=True):
    hist, ref = checker.history_detail("|Geo:Bandage_L")
check("the history named with its type, and referenced = the model file", hist == ["transformGeometry1 "
                                                                              "(transformGeometry)"] and ref)
rep = R.Report("x")
detail = {"|L_Eye_geo": (["transformGeometry1 (transformGeometry)"], False),
          "|Geo:Bandage_L": (["polySmoothFace1 (polySmoothFace)"], True)}
with mock.patch.object(checker, "run_checks", lambda o, s: {"mesh_history": ("WARN", list(detail))}), \
        mock.patch.object(checker, "history_detail", lambda m: detail[m]):
    scene_check.check_checker(rep)
text = rep.text()
check("the report: each mesh's history and where to clean it (this file / the model file), and a warning",
      "L_Eye_geo: transformGeometry1 (transformGeometry) - in this file" in text and
      "Bandage_L: polySmoothFace1 (polySmoothFace) - in the model file" in text and "moves it when it's deleted"
      in text)

# --- 4. Remove head squash leaves no switch node
reset()
createNode("transform", name="Head_squash_ctrl")
createNode("reverse", name="Head_squash_off")
createNode("reverse", name="Head_squash_off1")
createNode("transform", name="something")
connectAttr("Head_squash_off1.outputX", "something.visibility")
with mock.patch.object(HS, "find", lambda: "|Head_squash_ctrl"), mock.patch.object(HS, "read", lambda: {}), \
        mock.patch.object(HS, "_unride", lambda *a: None), mock.patch.object(HS, "_deformed_curves", lambda f: []), \
        mock.patch.object(HS, "repair_curves", lambda c: 0), mock.patch.object(HS, "clean_copies", lambda m: 0):
    HS.remove()
check("Remove: a Head_squash_off with nothing connected goes; one still in use stays",
      not objExists("Head_squash_off") and objExists("Head_squash_off1"))

print("%d/%d passed" % (sum(ok), len(ok)))
