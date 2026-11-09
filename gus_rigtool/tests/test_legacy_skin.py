# Skin repair: old joints (duplicate names) placed by uuid; Replace moves weights even when the new joint is in the
# skin; legacy joints still in a skin are matched to the new joint at the same spot and their weights moved
exec(open("fakemaya.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.builder import existing, build as bld, guides
from gus_rigtool.core import skin_tools
def jnt(name, parent, pos):
    j = cmds.createNode("joint", name=name, parent=parent); cmds.xform(j, worldSpace=True, translation=pos)
    return cmds.ls(j, long=True)[0]
skel = cmds.createNode("transform", name="old_skeleton")
other = cmds.createNode("transform", name="old_fk")
c = jnt("L_Clavicule", skel, (2, 140, 0)); h = jnt("L_Shoulder", c, (15, 140, -1))
r = jnt("L_Elbow", h, (40, 140, -3)); w = jnt("L_Wrist", r, (65, 140, 0))
dup = jnt("L_Wrist", other, (65, 140, 0))                       # a second 'L_Wrist' (FK chain)
g = existing.place_on_joints("arm", "L", "arm", [c, h, r, w], 180)
st = guides.read(g)["settings"]
print("stored uuids:", sorted(st["placed_uuid"]), "| positions:", sorted(st["placed_pos"]))
bld.build_all(180)
print("map finds the right L_Wrist despite the duplicate:", {k.split("|")[-1]: v.split("|")[-1] for k, v in existing.joint_map(g).items()}.get("L_Wrist"),
      "| lost:", existing.lost_joints([g]))
# a fake skin: influences + moves recorded
INF = {"skinCluster1": [cmds.ls(x, uuid=True)[0] for x in (c, w, cmds.ls("L_clavicle_jnt", long=True)[0])]}
cur = lambda: [cmds.ls(u, long=True)[0] for u in INF["skinCluster1"]]
calls = []
def skinCluster(*a, **k):
    if k.get("query"):
        if k.get("influence") or k.get("weightedInfluence"):
            return cur()
        if k.get("geometry"):
            return ["body"]
        return None
    if k.get("addInfluence"):
        INF[a[0]].append(cmds.ls(k["addInfluence"], uuid=True)[0]); calls.append(("add", k["addInfluence"].split("|")[-1]))
    if k.get("removeInfluence"):
        INF[a[0]] = [x for x in INF[a[0]] if x != cmds.ls(k["removeInfluence"], uuid=True)[0]]
        calls.append(("remove", k["removeInfluence"].split("|")[-1]))
cmds.skinCluster = skinCluster
cmds.skinPercent = lambda *a, **k: calls.append(("move", [x.split("|")[-1] for x in k["transformMoveWeights"]]))
body = cmds.createNode("transform", name="body"); cmds.createNode("mesh", name="bodyShape", parent=body)
_ls = cmds.ls
cmds.ls = lambda *a, **k: (["skinCluster1"] if k.get("type") == "skinCluster" and not a else _ls(*a, **k))
legacy = cmds.createNode("transform", name=existing.LEGACY)
cmds.parent(skel, legacy)
plan = existing.legacy_skin_plan()
print("\n".join(existing.legacy_plan_lines(plan)))
print("moved:", existing.repair_legacy_skin(plan))
print("calls:", calls)
print("skin now:", [x.split("|")[-1] for x in cur()])
from gus_rigtool.tools import checker
print("checker after:", checker.find_skin_legacy(None))
