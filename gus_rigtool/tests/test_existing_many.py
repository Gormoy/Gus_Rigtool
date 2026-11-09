# Existing rig, several at once: L arm in a list, its twin found by name, place every row (one check first),
# then replace both modules together
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool.builder import existing, build as bld, guides
def jnt(name, parent, pos):
    j = cmds.createNode("joint", name=name, parent=parent); cmds.xform(j, worldSpace=True, translation=pos)
    return cmds.ls(j, long=True)[0]
skel = cmds.createNode("transform", name="old_skeleton")
arms = {}
for sd, sx in (("L", 1), ("R", -1)):
    c = jnt("%s_old_clavicle" % sd, skel, (2 * sx, 140, 0)); h = jnt("%s_old_humerus" % sd, c, (15 * sx, 140, -1))
    r = jnt("%s_old_radius" % sd, h, (40 * sx, 140, -3)); w = jnt("%s_old_wrist" % sd, r, (65 * sx, 140, 0))
    arms[sd] = [c, h, r, w]
print("twins:", [j.split("|")[-1] for j in existing.twin_joints(arms["L"])])
try:
    existing.twin_joints([skel])
except RuntimeError as e:
    print("refused:", e)
try:
    existing.place_many([{"type": "arm", "side": "L", "name": "arm", "joints": arms["L"]},
                         {"type": "arm", "side": "R", "name": "arm", "joints": arms["R"][:2]}], 180)
except RuntimeError as e:
    print("bad row refused:", e, "| nothing made:", guides.module_groups())
# the page: add row, add twin, place every row
from gus_rigtool.core import ui
from gus_rigtool.tools import build_tab as bt
_cur[0] = None; cmds.columnLayout("root"); ui._build_tool("build", "p_build_"); bt._P["p"] = "p_build_"
types = existing.placeable()
cmds.optionMenu("p_build_ExType", edit=True, select=types.index("arm") + 1)
cmds.optionMenu("p_build_ExPlaceSide", edit=True, select=2)
cmds.textField("p_build_ExPlaceName", edit=True, text="arm")
cmds.textField("p_build_ExPlaceJoints", edit=True, text=" ".join(j.split("|")[-1] for j in arms["L"]))
bt.ex_queue_add(); bt.ex_queue_twin()
print("rows:", [(r["side"], r["name"], [j.split("|")[-1] for j in r["joints"]][:2]) for r in bt._q_rows()])
bt.ex_queue_place()
gs = guides.module_groups()
print("placed:", [(guides.read(g)["side"], guides.read(g)["name"]) for g in gs], "| list emptied:", bt._q_rows())
bld.build_all(180)
p = existing.plan_replace(gs, [])
print("one plan for both:", len(p["map"]), "old joints ->", sorted(set(b.split("|")[-1][:2] for b in p["map"].values())))
_p, notes = existing.replace(gs, [])
print("legacy holds:", sorted(x.split("|")[-1] for x in cmds.listRelatives(existing.LEGACY, children=True) or []))
