# 5.3.4: 'always evaluate' off through the expression's attribute (editing it broke the Hare's Ear_wave_expr on a
# locked channel); a repair that fails is undone at once; constraints that drive nothing / plugins / playback in
# Repair; warnings accepted as intended pass, until something new shows up on the line
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.builder import chain
from gus_rigtool.core import repair, accept
from gus_rigtool.core.report import Report, WARN, NOTE, OK
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# the wave drives a locked channel (through a unitConversion): unlocked for the edit, locked again after
e = cmds.createNode("expression", name="Ear_wave_expr")
grp = cmds.createNode("transform", name="Tongue_01_wave_grp")
uc = cmds.createNode("unitConversion", name="Ear_wave_expr_out_to_Tongue_01_wave_grp_uc")
cmds.addAttr(e, longName="out0", attributeType="double")
cmds.addAttr(uc, longName="input", attributeType="double"); cmds.addAttr(uc, longName="output", attributeType="double")
cmds.connectAttr(e + ".out0", uc + ".input"); cmds.connectAttr(uc + ".output", grp + ".rotateY")
cmds.setAttr(grp + ".rotateY", lock=True)
state = {"ae": True}
seen_locked = []
def expression(*a, **k):
    if k.get("query"):
        return state["ae"] if k.get("alwaysEvaluate") else "// x"
    if k.get("edit"):
        seen_locked.append(cmds.getAttr(grp + ".rotateY", lock=True))
        state["ae"] = k.get("alwaysEvaluate", state["ae"])
with mock.patch.object(cmds, "expression", side_effect=expression, create=True):
    check("found", chain.always_evaluating() == ["Ear_wave_expr"])
    chain.stop_always_evaluating()
check("turned off; the locked channel it drives was unlocked during the edit and is locked again",
      state["ae"] is False and seen_locked == [False] and cmds.getAttr(grp + ".rotateY", lock=True))

# a failed repair is undone at once, the others stay
calls = []
def undoInfo(**k):
    calls.append(k)
    if k.get("query") and k.get("undoName"):
        return "gusrigRepair_bad"
    return True
undone = []
items = [repair.Item("good", "good", "", 1, lambda: 3),
         repair.Item("bad", "bad", "", 1, lambda: (_ for _ in ()).throw(RuntimeError("Destination is locked.")))]
with mock.patch.object(cmds, "undoInfo", side_effect=undoInfo, create=True), \
        mock.patch.object(cmds, "undo", side_effect=lambda: undone.append(1), create=True):
    out = repair.apply(["good", "bad"], items)
print(out)
check("the good one done, the failed one says so and was undone at once",
      out[0][1] == 3 and "failed (nothing of it left changed)" in out[1][1] and undone == [1])
check("each repair its own undo step", sum(1 for c in calls if c.get("openChunk")) == 2)

# constraints that drive nothing
t = cmds.createNode("transform", name="Tail_00_jnt")
con = cmds.createNode("parentConstraint", name="Tail_00_jnt_parentConstraint2", parent=t)
with mock.patch.object(cmds, "parentConstraint", side_effect=lambda *a, **k: ["Waist_ctrl"] if k.get("query")
                       else None, create=True):
    idle = repair.idle_constraints()
    check("a constraint with a target that drives nothing is found", [i.split("|")[-1] for i in idle] ==
          ["Tail_00_jnt_parentConstraint2"])
    it = repair._idle_constraints()
    it.fix()
check("Repair deletes it", not cmds.objExists("Tail_00_jnt_parentConstraint2"))

# accept
rep = Report("Check this scene")
rep.start("Checker")
rep.add(WARN, "Scene: Duplicate names inside a referenced file (8)", "Belt; Belt; Gums_UP")
rep.add(NOTE, "Joints: Joint twisted against its parent (7)", "L_Humerus, Nose")
rep.add(WARN, "Controls: Controls not at zero (1)", "Eyes_ctrl")
accept.accept([("Checker", "Scene: Duplicate names inside a referenced file (8)", "Belt; Belt; Gums_UP"),
               ("Checker", "Joints: Joint twisted against its parent (7)", "L_Humerus, Nose")])
check("kept in the scene", cmds.objExists("gusAccepted") and len(accept.load()) == 2)
n = accept.apply(rep)
st = [(r[1], r[2]) for r in rep.rows]
print(st)
check("accepted rows pass, marked '(accepted)'; the others still warn", n == 2 and st[0][0] == OK and
      "(accepted)" in st[0][1] and st[1][0] == OK and st[2][0] == WARN)
rep2 = Report("again")
rep2.start("Checker")
rep2.add(NOTE, "Joints: Joint twisted against its parent (8)", "L_Humerus, Nose, R_Knee")
accept.apply(rep2)
check("something new on an accepted line: it warns again, and says it changed",
      rep2.rows[0][1] == NOTE and "changed since you accepted it" in rep2.rows[0][3])
accept.forget()
check("Forget: nothing accepted, the node gone", accept.load() == {} and not cmds.objExists("gusAccepted"))

# loose joints that skin and drive nothing (the Hare's joint1-5): offered for deleting; a used one isn't
j1 = cmds.createNode("joint", name="joint1")
j2 = cmds.createNode("joint", name="joint2", parent=j1)
k1 = cmds.createNode("joint", name="L_Head_old")
sk = cmds.createNode("skinCluster", name="someSkin")
cmds.addAttr(sk, longName="ma", attributeType="matrix")
cmds.connectAttr(k1 + ".worldMatrix", sk + ".ma")
roots = [r.split("|")[-1] for r in repair.unused_joint_roots()]
print(roots)
check("joint1 (with joint2 under it) offered, the skinned one not", "joint1" in roots and "L_Head_old" not in roots
      and "joint2" not in roots)

# add joints to a skin: each exactly once (Maya's Add Influence put every cape joint in twice)
from gus_rigtool.core import skin_tools
r1 = cmds.createNode("joint", name="L_Cape01_01_jnt")
r2 = cmds.createNode("joint", name="L_Cape01_02_jnt", parent=r1)
r3 = cmds.createNode("joint", name="L_Cape01_end_jnt", parent=r2)
have = [cmds.ls(r1, long=True)[0]]
added_calls = []
def skinCluster(*a, **k):
    if k.get("edit") and k.get("addInfluence"):
        added_calls.append(k["addInfluence"]); have.append(k["addInfluence"])
with mock.patch.object(skin_tools, "skin_of", lambda m: "hood_skin"), \
        mock.patch.object(skin_tools, "influences", lambda sk: list(have)), \
        mock.patch.object(cmds, "skinCluster", side_effect=skinCluster, create=True):
    added, had = skin_tools.add_joints("Hood", [r1, cmds.ls(r3, long=True)[0], r1])
print([a.split("|")[-1] for a in added_calls], had)
check("the chain's joints added once each (the root already in, picked twice: skipped)",
      [a.split("|")[-1] for a in added_calls] == ["L_Cape01_02_jnt", "L_Cape01_end_jnt"] and had == 1)

# a control group hidden by hand (the Hare's Neck_ctrl_GRP): found, shown again; a driven one left alone
from gus_rigtool.tools import checker
ng = cmds.createNode("transform", name="Neck_ctrl_GRP")
nc = cmds.createNode("transform", name="Neck_ctrl", parent=ng)
cmds.createNode("nurbsCurve", name="Neck_ctrlShape", parent=nc)
cmds.setAttr(ng + ".visibility", 0)
fk = cmds.createNode("transform", name="L_Arm_fk_grp")
fc = cmds.createNode("transform", name="L_Arm_FK_ctrl", parent=fk)
cmds.createNode("nurbsCurve", name="L_Arm_FK_ctrlShape", parent=fc)
sw = cmds.createNode("transform", name="L_Arm_settings")
cmds.addAttr(sw, longName="fkVis", attributeType="bool")
cmds.connectAttr(sw + ".fkVis", fk + ".visibility")
hid = [h.split("|")[-1] for h in checker.find_ctrl_hidden(None)]
check("the hand-hidden group is found, the switched one isn't", hid == ["Neck_ctrl_GRP"])
checker.fix_ctrl_hidden(checker.find_ctrl_hidden(None))
check("Fix shows it again", cmds.getAttr(ng + ".visibility") and not checker.find_ctrl_hidden(None))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
