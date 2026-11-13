# 5.6.32: the history check leaves out the Clothes switch (the bandages' false warning); Remove head squash unlocks
# what Publish locked and cleans a squash removed half-way (Head_squash_off, Head_squash_factor_md, the ears'
# _squash_follow groups) with the ear controls staying put; Keep the pose says when no control is selected
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import head_squash as HS
from gus_rigtool.tools import checker, behaviour_tool
ok = []
def reset():
    S.__init__()
    _LOCKED.clear()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

real_delete = cmds.delete
def maya_delete(*a, **k):
    """Like Maya: a locked node, or a group with a locked node under it, can't be deleted."""
    for x in a:
        for n in (x if isinstance(x, (list, tuple)) else [x]):
            for y in [n] + (cmds.listRelatives(n, allDescendents=True, fullPath=True) or []):
                if cmds.lockNode(y, query=True, lock=True)[0]:
                    raise RuntimeError("Cannot delete locked node '%s'." % y)
    return real_delete(*a, **k)

# --- 1. the history check: the Clothes switch isn't model history
reset()
createNode("transform", name="Bandage_L")
createNode("mesh", name="Bandage_LShape", parent="Bandage_L")
createNode("skinCluster", name="skin1")
for t, n in (("plusMinusAverage", "Clothes_Bandages_pma"), ("condition", "Clothes_Bandages_hidden"),
             ("animCurveTU", "Clothes_key"), ("polySmoothFace", "polySmoothFace1")):
    createNode(t, name=n)
hist = ["skin1", "Clothes_Bandages_hidden", "Clothes_Bandages_pma", "Clothes_key"]
with mock.patch.object(cmds, "listHistory", lambda *a, **k: list(hist)):
    got = checker._non_deformer_history("|Bandage_L|Bandage_LShape")
    check("the bandages: the switch's nodes (condition, plusMinusAverage) and a key on it aren't history - "
          "5.6.31 said 'in the model file'", got == [])
    hist.append("polySmoothFace1")
    got = checker._non_deformer_history("|Bandage_L|Bandage_LShape")
check("real model history is still found", got == ["polySmoothFace1"])

# --- 2. a squash removed half-way: the leftovers
def half_removed():
    reset()
    createNode("transform", name="Head_ctrl")
    createNode("transform", name="L_Ear_ctrls_grp", parent="Head_ctrl")
    setAttr("L_Ear_ctrls_grp.translateX", 3.0)
    createNode("transform", name="L_Ear_ctrls_grp_squash_follow", parent="L_Ear_ctrls_grp")
    setAttr("L_Ear_ctrls_grp_squash_follow.translateY", 0.5)
    createNode("transform", name="L_Ear_01_ctrl", parent="L_Ear_ctrls_grp_squash_follow")
    setAttr("L_Ear_01_ctrl.translateY", 2.0)
    createNode("parentConstraint", name="L_Ear_01_pc", parent="L_Ear_01_ctrl")
    createNode("reverse", name="Head_squash_off")
    createNode("multiplyDivide", name="Head_squash_factor_md")
    createNode("multiplyDivide", name="Other_md")
    for n in ("Head_squash_factor_md", "L_Ear_01_pc", "Other_md"):     # Publish's protect
        cmds.lockNode(ls(n, long=True)[0], lock=True)
half_removed()
before = cmds.xform("L_Ear_01_ctrl", query=True, worldSpace=True, translation=True)
check("found: the switch node, the factor node, the ear's follow group - not the head or other nodes",
      sorted(HS._short(n) for n in HS.leftovers()) ==
      ["Head_squash_factor_md", "Head_squash_off", "L_Ear_ctrls_grp_squash_follow"])
with mock.patch.object(cmds, "delete", maya_delete):
    HS.remove()                                      # no squash any more: its leftovers go
ear = ls("L_Ear_01_ctrl", long=True)
check("Remove head squash (5.6.31 stopped at 'Cannot delete locked node'): the leftovers are gone",
      not objExists("Head_squash_off") and not objExists("Head_squash_factor_md") and
      not objExists("L_Ear_ctrls_grp_squash_follow") and not HS.leftovers())
check("the ear control moved up to L_Ear_ctrls_grp and stayed where it was",
      ear and cmds.listRelatives(ear[0], parent=True) == ["L_Ear_ctrls_grp"] and
      all(abs(a - b) < 1e-6 for a, b in zip(cmds.xform(ear[0], query=True, worldSpace=True, translation=True),
                                            before)))
check("what stays is locked again, as Publish left it (the ear's constraint, other nodes)",
      cmds.lockNode(ls("L_Ear_01_pc", long=True)[0], query=True, lock=True)[0] and
      cmds.lockNode(ls("Other_md", long=True)[0], query=True, lock=True)[0])
reset()
try:
    HS.remove()
    said = ""
except RuntimeError as e:
    said = str(e)
check("nothing there: it still says there's no head squash", "no head squash" in said)

# --- 3. a whole squash on a published rig: unlocked first
reset()
createNode("transform", name="Head_squash_grp")
createNode("transform", name="Head_squash_ctrl", parent="Head_squash_grp")
createNode("multiplyDivide", name="Head_squash_factor_md")
for n in ("Head_squash_factor_md", "Head_squash_ctrl"):
    cmds.lockNode(ls(n, long=True)[0], lock=True)
data = {"group": "Head_squash_grp", "nodes": ["Head_squash_factor_md"]}
with mock.patch.object(HS, "find", lambda: ls("Head_squash_ctrl", long=True)[0] if objExists("Head_squash_ctrl")
                       else None), \
        mock.patch.object(HS, "read", lambda: data), mock.patch.object(HS, "_unride", lambda *a: None), \
        mock.patch.object(HS, "_deformed_curves", lambda f: []), mock.patch.object(HS, "repair_curves", lambda c: 0), \
        mock.patch.object(HS, "clean_copies", lambda m: 0), mock.patch.object(cmds, "delete", maya_delete):
    HS.remove()
check("a published rig's squash goes in one go (its nodes were locked)",
      not objExists("Head_squash_grp") and not objExists("Head_squash_factor_md"))

# --- 4. Keep the pose: the meshes selected, not the controls
reset()
createNode("transform", name="R_Eye_geo")
createNode("mesh", name="R_Eye_geoShape", parent="R_Eye_geo")
cmds.select("R_Eye_geo")
try:
    behaviour_tool.zero_here()
    said = ""
except RuntimeError as e:
    said = str(e)
check("only the eye mesh selected: it says to select the control curves (5.6.31 said '0 zeroed')",
      "no controls in the selection (R_Eye_geo)" in said and "L_Pupil_ctrl" in said)

print("%d/%d passed" % (sum(ok), len(ok)))
