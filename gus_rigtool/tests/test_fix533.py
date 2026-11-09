# 5.3.3: duplicate names renamed (the extra copies, old -> new shown first); jiggle / wave expressions without
# 'always evaluate' and a pause switch; leftover ngSkinTools data found; the cape stopped at the body (rotation
# limits measured against the body)
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.tools import checker
from gus_rigtool.core import body_stop, repair
from gus_rigtool.builder import chain
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# ---- duplicate names
a = cmds.createNode("transform", name="Arm_grp")
b = cmds.createNode("transform", name="Tongue_grp")
h1 = cmds.createNode("transform", name="L_Arm_ikHandle", parent=a)
h2 = cmds.createNode("transform", name="tmp", parent=b)
_n(h2).name = "L_Arm_ikHandle"                                  # the fake makes names unique: force the clash
g1 = cmds.createNode("transform", name="Curves")
g2 = cmds.createNode("transform", name="Strips")
e1 = cmds.createNode("transform", name="edgeCurve", parent=g1)
e2 = cmds.createNode("transform", name="tmp2", parent=g2)
_n(e2).name = "edgeCurve"
cmds.createNode("transform", name="Strips_edgeCurve")          # taken: the copy gets a number instead
dups = checker.find_dup_names(None)
plan = [(n.split("|")[-2] if n.count("|") > 1 else "", n.split("|")[-1], new) for n, new in checker.rename_plan(dups)]
print(plan)
check("the copy under another group gets that group's name in front", ("Tongue_grp", "L_Arm_ikHandle",
                                                                        "Tongue_grp_L_Arm_ikHandle") in plan or
      ("Arm_grp", "L_Arm_ikHandle", "Arm_grp_L_Arm_ikHandle") in plan)
check("when that name is taken, a number", ("Strips", "edgeCurve", "edgeCurve_2") in plan)
check("one copy of each keeps its name", len(plan) == 2)
n = checker.fix_dup_names(dups, ask=False)
check("renamed: no duplicates left", n == 2 and not checker.find_dup_names(None))
check("Fix all leaves renaming duplicates to you (it asks)", "dup_names" in checker.NOT_IN_FIX_ALL)

# ---- jiggle / wave expressions: always evaluate off, pause
EXPR = {"Cape_jiggle_expr": {"ae": True, "text": chain.JIGGLE_TAG + ": Cape"},
        "Cape_wave_expr": {"ae": True, "text": ".O[0] = sin(time)"}, "other_expr": {"ae": True, "text": "x"}}
for e in EXPR:
    cmds.createNode("expression", name=e)
def expression(*a, **k):
    if k.get("query"):
        return EXPR[a[0]]["ae"] if k.get("alwaysEvaluate") else EXPR[a[0]]["text"]
    if k.get("edit") and "alwaysEvaluate" in k:
        EXPR[a[0]]["ae"] = k["alwaysEvaluate"]
with mock.patch.object(cmds, "expression", side_effect=expression, create=True):
    check("jiggle and wave expressions found (not other expressions)",
          sorted(chain.motion_exprs()) == ["Cape_jiggle_expr", "Cape_wave_expr"])
    item = [i for i in repair.find() if i.id == "always_evaluate"]
    check("Repair offers to stop them always evaluating", len(item) == 1 and item[0].count == 2)
    item[0].fix()
    check("...done: they evaluate only when time / their inputs change", not EXPR["Cape_jiggle_expr"]["ae"] and
          not EXPR["Cape_wave_expr"]["ae"] and EXPR["other_expr"]["ae"])
    chain.pause_motion(True)
    check("Pause: both off (blocking)", sorted(chain.paused()) == ["Cape_jiggle_expr", "Cape_wave_expr"])
    chain.pause_motion(False)
    check("Back on", chain.paused() == [])
import re as _re
made = _re.findall(r"alwaysEvaluate=(\w+), unitConversion", open(chain.__file__).read())
check("new chains: jiggle and wave made without always evaluate", made == ["False", "False"])

# ---- leftover ngSkinTools data
sk = cmds.createNode("skinCluster", name="skinCluster18")
live = cmds.createNode("ngst2SkinLayerData", name="ngSkinToolsData_skinCluster18")
cmds.addAttr(live, longName="sc", attributeType="message")
cmds.connectAttr(sk + ".message", live + ".sc")
dead = cmds.createNode("ngst2SkinLayerData", name="Hare_Body_skinCluster")
cmds.addAttr(dead, longName="sc", attributeType="message")
check("ngSkinTools data with no skin is found, the live one isn't", repair.ng_orphans() == ["Hare_Body_skinCluster"])
item = [i for i in repair.find() if i.id == "ng_orphans"]
item[0].fix()
check("Repair deletes it", not cmds.objExists("Hare_Body_skinCluster") and cmds.objExists(live))

# ---- stop at the body: a cape hanging down from (0, 10, 0), the body in front of it (z > 1)
c1 = cmds.createNode("transform", name="Cape_01_FK_ctrl"); cmds.xform(c1, worldSpace=True, translation=[0, 10, 0])
c2 = cmds.createNode("transform", name="Cape_02_FK_ctrl", parent=c1); cmds.xform(c2, worldSpace=True, translation=[0, 6, 0])
c3 = cmds.createNode("transform", name="Cape_03_FK_ctrl", parent=c2); cmds.xform(c3, worldSpace=True, translation=[0, 2, 0])
ctrls = [cmds.ls(c, long=True)[0] for c in (c1, c2, c3)]
dist = lambda p: 1.0 - p[2]                                   # outside while z < 1
rows = body_stop.measure(ctrls, dist, margin=0.0)
for r in rows:
    print("  ", r[0].split("|")[-1], r[1:])
c, ax, sign, ang, _n_ = rows[0]
check("the top control: rotateX, the negative way goes towards the body", ax == "X" and sign == -1)
check("it stops just before the tip reaches the body (asin(1/12) = 4.8 degrees -> 4)", ang == 4.0)
check("lower controls get more room (shorter chain below)", rows[1][3] > rows[0][3] and rows[2][3] > rows[1][3])
check("measuring put every control back", all(abs(cmds.getAttr(x + ".rotateX")) < 1e-9 for x in ctrls))
lines = body_stop.apply(rows, ctrls[0])
print("\n".join(lines))
check("a limit on the body side, switchable and adjustable from the first control",
      cmds.attributeQuery("body_stop", node=ctrls[0], exists=True) and
      cmds.attributeQuery("body_stop_extra", node=ctrls[0], exists=True) and
      (cmds.listConnections(ctrls[0] + ".minRotXLimit", source=True, destination=False) or [""])[0]
      .endswith("bodyStop_adl") and cmds.getAttr(ctrls[0] + ".gusBodyStop") == -4.0)
body_stop.remove(ctrls)
check("Remove: limits off, its nodes gone", not cmds.ls("*bodyStop*") if False else
      not [x for x in cmds.ls() if "bodyStop" in x] and
      not cmds.attributeQuery("gusBodyStop", node=ctrls[0], exists=True))

# ---- a joint plugged into a skin twice (the Hare's hood): found, merged, weights kept
from gus_rigtool.core import skin_tools
W = {0: {134: 0.3, 145: 0.2, 1: 0.5}, 1: {145: 1.0}, 2: {1: 1.0}}
CON = {134: "Cape_01_jnt", 145: "Cape_01_jnt", 1: "Chest"}
BPM = {134: [1.0] * 16, 145: [1.0] * 16, 1: [0.0] * 16}
removed = []
def getAttr(plug, **k):
    if plug == "hood_skin.matrix" and k.get("multiIndices"):
        return sorted(CON)
    if plug == "hood_skin.weightList" and k.get("multiIndices"):
        return sorted(W)
    m = re.match(r"hood_skin\.weightList\[(\d+)\]\.weights\[(\d+)\]", plug)
    if m:
        return W[int(m.group(1))].get(int(m.group(2)), 0.0)
    m = re.match(r"hood_skin\.bindPreMatrix\[(\d+)\]", plug)
    if m:
        return BPM[int(m.group(1))]
    raise ValueError(plug)
def setAttr(plug, v, **k):
    m = re.match(r"hood_skin\.weightList\[(\d+)\]\.weights\[(\d+)\]", plug)
    W[int(m.group(1))][int(m.group(2))] = v
def removeMulti(plug, **k):
    removed.append(plug)
    m = re.match(r"hood_skin\.weightList\[(\d+)\]\.weights\[(\d+)\]", plug)
    if m:
        W[int(m.group(1))].pop(int(m.group(2)), None)
def listConnections(plug, **k):
    m = re.match(r"hood_skin\.matrix\[(\d+)\]", plug)
    return [CON[int(m.group(1))]] if m else []
import re
with mock.patch.object(cmds, "getAttr", side_effect=getAttr), \
        mock.patch.object(cmds, "setAttr", side_effect=setAttr), \
        mock.patch.object(cmds, "listConnections", side_effect=listConnections), \
        mock.patch.object(cmds, "ls", side_effect=lambda n, **k: [n] if isinstance(n, str) else n), \
        mock.patch.object(cmds, "removeMultiInstance", side_effect=removeMulti, create=True):
    tw = skin_tools.twice("hood_skin")
    check("found: Cape_01_jnt in slots 134 and 145", tw == {"Cape_01_jnt": [134, 145]})
    n, posed = skin_tools.merge_twice("hood_skin")
print(W, removed[-4:])
check("merged: the extra slot's weights on the first one (vertex 0: 0.5, vertex 1: 1.0), nothing lost",
      n == 1 and abs(W[0][134] - 0.5) < 1e-9 and W[1] == {134: 1.0} and 145 not in W[0] and W[2] == {1: 1.0})
check("the extra slot unplugged", "hood_skin.matrix[145]" in removed and "hood_skin.bindPreMatrix[145]" in removed)
check("both bound in the same pose: no warning", posed == [])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
