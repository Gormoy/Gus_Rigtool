# 5.6.1: Repair can't change the rig at rest (a fix that moves the skinned meshes is undone); skins with ngSkinTools
# layers are left alone (no cut to the influence limit, no normalising, not reported over the limit); joints get the
# global scale directly (a mirrored -1 scaled one is left alone, a joint under one that now scales too); Global > World
# > Local refuses when a Global_ctrl (or Global_ctrl1) exists, and undoes itself if it fails half way; the scale
# check lists by part of the rig
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import repair, scale_check as SC, world_levels
from gus_rigtool import scene_check
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# ---- the safety net
shots = [{"BodyShape": [0, 0, 0, 1, 1, 1]}, {"BodyShape": [0, 0, 0, 1, 1.5, 1]},     # a fix that moves a vertex
         {"BodyShape": [0, 0, 0, 1, 1, 1]}, {"BodyShape": [0, 0, 0, 1, 1, 1]}]       # one that doesn't
undone = []
grp = cmds.createNode("transform", name="tmp_grp")
def bad_fix():
    cmds.setAttr(grp + ".translateX", 5)
    return 1
items = [repair.Item("scale_joints", "moves the mesh", "", 1, bad_fix),
         repair.Item("util_names", "harmless", "", 1, lambda: 2)]
with mock.patch.object(repair, "rest_points", side_effect=lambda: shots.pop(0)), \
        mock.patch.object(cmds, "undo", side_effect=lambda *a, **k: undone.append(1), create=True), \
        mock.patch.object(cmds, "undoInfo", side_effect=lambda *a, **k: "gusrigRepair_scale_joints"
                          if k.get("undoName") else True):
    out = repair.apply(["scale_joints", "util_names"], items)
print(out)
check("a fix that moves the mesh at rest: undone, and it says which vertices", undone == [1] and
      out[0][1].startswith("undone - safe mode: it moved rest BodyShape: 1 point(s) up to 0.5"))   # 5.6.27 wording
check("a fix that doesn't: kept", out[1][1] == 2)
check("fixes meant to change the mesh (normalise, symmetric ribbons...) aren't checked",
      "skin_limits" in repair.MOVES and "scale_joints" not in repair.MOVES)
check("moved(): nothing moved -> []", repair.moved({"a": [0, 0, 0]}, {"a": [0, 0, 0.0005]}) == [])

# ---- ngSkinTools skins left alone
sk = cmds.createNode("skinCluster", name="skinCluster10")
data = cmds.createNode("ngst2SkinLayerData", name="ngSkinToolsData_skinCluster10")
cmds.addAttr(data, longName="sc", attributeType="message")
cmds.connectAttr(sk + ".message", data + ".sc")
plain = cmds.createNode("skinCluster", name="skinCluster7")
check("skins with ngSkinTools layers found (not the others)", repair.ng_skins() == {"skinCluster10"})
from gus_rigtool.tools import checker
with mock.patch.object(checker, "find_skin_influences",
                       return_value=["Hare_Body.vtx[1]", "Eyes.vtx[2]"]), \
        mock.patch.object(repair, "_skin_of_mesh", side_effect=lambda m: {"Hare_Body": "skinCluster10",
                                                                          "Eyes": "skinCluster7"}[m]):
    item = repair._skin_limits()
check("influence limit: only the mesh without layers is offered (the body's weights are ngSkinTools')",
      item and item.detail.startswith("Eyes"))
src = open("../tools/checker.py").read()
check("the checker doesn't count vertices over the limit on ngSkinTools skins",
      "ng = repair.ng_skins()" in src and "if skin in ng:" in src)

# ---- joints get the global scale directly
g = cmds.createNode("transform", name="Global_ctrl")
cmds.addAttr(g, longName="globalScale", attributeType="double", defaultValue=1.0)
skel = cmds.createNode("transform", name="ribbon_bind_grp")
cmds.setAttr(skel + ".inheritsTransform", 0)
j1 = cmds.ls(cmds.createNode("joint", name="L_Sleeve_fol_01_jnt", parent=skel), long=True)[0]
j2 = cmds.ls(cmds.createNode("joint", name="L_Sleeve_fol_02_jnt", parent=j1), long=True)[0]
jm = cmds.ls(cmds.createNode("joint", name="R_Sleeve_fol_01_jnt", parent=skel), long=True)[0]
for j in (j1, j2):
    for a in "XYZ":
        cmds.setAttr("%s.scale%s" % (j, a), 1)
cmds.setAttr(jm + ".scaleX", -1); cmds.setAttr(jm + ".scaleY", 1); cmds.setAttr(jm + ".scaleZ", 1)
cmds.connectAttr(j1 + ".scale", j2 + ".inverseScale")             # Maya connects it in a chain
n = SC.fix_joints([(j2, "c2"), (j1, "c1"), (jm, "c3")], g + ".globalScale")
md = lambda j: (cmds.listConnections(j + ".scaleX", source=True, destination=False) or [""])[0]
check("the top joint and the -1 scaled one: own scale x global (-1 kept); the one under the top one: left alone"
      " (Segment Scale Compensate off: it inherits)",
      n == 2 and md(j1).endswith("_globalScale_md") and md(jm).endswith("_globalScale_md") and
      cmds.getAttr(md(jm) + ".input1X") == -1 and not md(j2))
check("no scale constraint made", not cmds.ls(type="scaleConstraint"))

# ---- world controls: refused when a Global_ctrl1 is lying around; a failure leaves nothing
from gus_rigtool.builder import publish
cmds.rename(g, "Global_ctrl1")
w = cmds.createNode("transform", name="World_ctrl")
cmds.createNode("nurbsCurve", name="World_ctrlShape", parent=w)
with mock.patch.object(publish, "is_published", return_value=False):
    try:
        world_levels.plan(w)
        check("a Global_ctrl1 left from before: refused", False)
        print("no error")
    except RuntimeError as e:
        print("error:", e)
        check("a Global_ctrl1 left from before: refused, names it", "Global_ctrl1" in str(e))
cmds.delete("Global_ctrl1")
undone = []
with mock.patch.object(publish, "is_published", return_value=False), \
        mock.patch.object(world_levels, "_make", side_effect=RuntimeError("boom")), \
        mock.patch.object(cmds, "undo", side_effect=lambda *a, **k: undone.append(1), create=True), \
        mock.patch.object(cmds, "undoInfo", side_effect=lambda *a, **k: "gusrigWorldLevels"
                          if k.get("undoName") else True):
    try:
        world_levels.make(w)
    except RuntimeError:
        pass
check("failing half way: its own step undone (no half-made Global_ctrl1)", undone == [1])

# ---- the scale check by part
txt = scene_check._by_part(["|a|L_Sleeve_fol_01_ctrl", "|a|L_Sleeve_fol_02_ctrl", "|b|Mouth_fol_33_ctrl"])
check("the scale check lists by part ('L_Sleeve 2, Mouth 1')", txt == "L_Sleeve 2, Mouth 1")
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
