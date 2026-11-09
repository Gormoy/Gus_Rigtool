# 4.1.1: joint at the centre of the selection; Make controls (constrain / parent / direct, FK chains, both sides)
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
import numpy as np
from gus_rigtool.core import centre_point as CP, make_controls as MC, ui, utils
ui.report_error = lambda e, w="": __import__("traceback").print_exc()
cmds.joint = lambda *a, **k: cmds.createNode("joint", name=k.get("name")) if not k.get("edit") else None
_joint = cmds.joint
def joint(*a, **k):
    if k.get("edit"):
        return None
    j = cmds.createNode("joint", name=k.get("name"))
    if k.get("position"):
        cmds.xform(j, worldSpace=True, translation=k["position"])
    return j
cmds.joint = joint
cmds.spaceLocator = lambda name=None, **k: [cmds.createNode("transform", name=name)]
cmds.makeIdentity = lambda *a, **k: None
cmds.selectMode = lambda **k: None
cmds.controller = lambda *a, **k: None
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
W = lambda n: np.array(cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True)).reshape(4, 4)
P = lambda n: W(n)[3, :3]

# ---------------------------------------------------------------- centre maths
check("average centre", CP.centre([[0, 0, 0], [2, 0, 0], [2, 4, 0]]) == [4 / 3.0, 4 / 3.0, 0.0])
check("box centre", CP.centre([[0, 0, 0], [2, 0, 0], [2, 4, 0]], "box") == [1.0, 2.0, 0.0])
links = {1: [2], 2: [1, 3], 3: [2], 7: [8], 8: [7]}
check("pieces: two islands, in selection order", CP.islands([7, 1, 2, 3, 8], lambda v: links.get(v, [])) == [[7, 8], [1, 2, 3]])

# components faked: two eyes' vertices
pts = {"head.vtx[1]": [3, 160, 8], "head.vtx[2]": [4, 160, 8], "head.vtx[3]": [3.5, 161, 8],
       "head.vtx[11]": [-3, 160, 8], "head.vtx[12]": [-4, 160, 8], "head.vtx[13]": [-3.5, 161, 8]}
nbr = {"head.vtx[1]": ["head.vtx[2]"], "head.vtx[2]": ["head.vtx[1]", "head.vtx[3]"], "head.vtx[3]": ["head.vtx[2]"],
       "head.vtx[11]": ["head.vtx[12]"], "head.vtx[12]": ["head.vtx[11]", "head.vtx[13]"], "head.vtx[13]": ["head.vtx[12]"]}
cmds.createNode("transform", name="head"); cmds.createNode("mesh", name="headShape", parent=cmds.ls("head", long=True)[0])
_ls, _xf = cmds.ls, cmds.xform
def ls(*a, **k):
    if a and isinstance(a[0], (list, str)) and k.get("flatten"):
        items = a[0] if isinstance(a[0], list) else [a[0]]
        if all(".vtx[" in x for x in items):
            return list(items)
    if a and isinstance(a[0], str) and ".vtx[" in a[0]:
        return [a[0]]
    return _ls(*a, **k)
def xf(n, **k):
    if isinstance(n, str) and ".vtx[" in n:
        return pts[n]
    return _xf(n, **k)
cmds.ls, cmds.xform = ls, xf
CP._vertex_neighbours = lambda v: nbr[v]
sel = sorted(pts)
groups = CP.groups_from_selection(sel, "piece")
check("each piece: two eyes", len(groups) == 2)
names = CP.names_for(groups, "joint")
check("names from the object, side from the position", sorted(names) == ["L_head_01_jnt", "R_head_02_jnt"]
      or sorted(names) == ["L_head_02_jnt", "R_head_01_jnt"])
check("your name, numbered, side added", sorted(CP.names_for(groups, "joint", "eye")) in
      (["L_eye_01_jnt", "R_eye_02_jnt"], ["L_eye_02_jnt", "R_eye_01_jnt"]))
made = CP.make(kind="joint", per="piece", sel=sel)
cmds.ls, cmds.xform = _ls, _xf
centres = sorted(tuple(np.round(P(m.split("|")[-1]), 3)) for m in made)
check("two joints at the eyes' centres", centres == [(-3.5, 160.333, 8.0), (3.5, 160.333, 8.0)])
cmds.ls, cmds.xform = ls, xf
made = CP.make(kind="locator", per="all", sel=sel, name="mid")
cmds.ls, cmds.xform = _ls, _xf
check("one locator for everything, centre (no side)", len(made) == 1 and made[0].endswith("mid_loc")
      and np.allclose(P("mid_loc"), [0, 160.333, 8], atol=1e-3))

# ---------------------------------------------------------------- make controls
def chain(names, pts, parent=None):
    out = []
    for n, p in zip(names, pts):
        j = cmds.createNode("joint", name=n, parent=out[-1] if out else parent)
        cmds.xform(j, worldSpace=True, translation=p)
        out.append(cmds.ls(j, long=True)[0])
    return out
arm = chain(["L_arm_jnt", "L_elbow_jnt", "L_wrist_jnt"], [(5, 150, 0), (25, 150, -2), (45, 150, 0)])
chain(["R_arm_jnt", "R_elbow_jnt", "R_wrist_jnt"], [(-5, 150, 0), (-25, 150, -2), (-45, 150, 0)])
rows = MC.plan(arm, ["_offset", "_sdk"], hierarchy=True)
check("plan: names and FK parents", [(r[1], r[2], r[3]) for r in rows] == [
    ("L_arm_ctrl", ["L_arm_ctrl_offset", "L_arm_ctrl_sdk"], None),
    ("L_elbow_ctrl", ["L_elbow_ctrl_offset", "L_elbow_ctrl_sdk"], "L_arm_ctrl"),
    ("L_wrist_ctrl", ["L_wrist_ctrl_offset", "L_wrist_ctrl_sdk"], "L_elbow_ctrl")])
check("auto size: half the bone", abs(MC.auto_size(arm[0]) - 0.5 * np.linalg.norm([20, 0, -2])) < 1e-6)
w0 = {n: W(n) for n in ("L_arm_jnt", "L_elbow_jnt", "L_wrist_jnt")}
out = MC.make(arm, stack=["_offset", "_sdk"], both_sides=True)
check("both sides: 6 controls", len(out) == 6)
p = cmds.ls("L_wrist_ctrl", long=True)[0].split("|")
check("FK chain: arm > elbow > wrist controls", p[-7:] == ["L_arm_ctrl", "L_elbow_ctrl_offset", "L_elbow_ctrl_sdk",
                                                          "L_elbow_ctrl", "L_wrist_ctrl_offset", "L_wrist_ctrl_sdk",
                                                          "L_wrist_ctrl"])
check("controls sit on their joints", all(np.allclose(P(c.split("|")[-1]), W(n.split("|")[-1])[3, :3]) for n, c in out))
cons = lambda n: sorted(cmds.nodeType(x) for x in cmds.listRelatives(cmds.ls(n, long=True)[0], type="constraint") or [])
check("constrain: parent + scale on the joint, skeleton untouched",
      cons("L_elbow_jnt") == ["parentConstraint", "scaleConstraint"] and
      cmds.ls("L_elbow_jnt", long=True)[0].split("|")[-2] == "L_arm_jnt")
check("joints didn't move", all(np.allclose(W(n), m) for n, m in w0.items()))
check("visibility locked, scale free", "v" in _n("L_arm_ctrl").locks and "sx" not in _n("L_arm_ctrl").locks)
again = MC.plan(arm, ["_offset"])
check("already has a control: skipped next time", all("already" in r[4] for r in again))
prop = cmds.createNode("transform", name="crate_geo"); cmds.xform(prop, worldSpace=True, translation=(0, 0, 30))
cmds.exactWorldBoundingBox = lambda n, **k: [-1, 0, 29, 1, 2, 31]
out = MC.make([cmds.ls("crate_geo", long=True)[0]], drive="parent", stack=["_offset"])
pp = cmds.ls("crate_geo", long=True)[0].split("|")
check("parent: crate_geo under crate_ctrl (geo suffix swapped), values 0, same place",
      pp[-3:] == ["crate_ctrl_offset", "crate_ctrl", "crate_geo"] and np.allclose(P("crate_geo"), [0, 0, 30])
      and np.allclose(cmds.getAttr(pp and cmds.ls("crate_geo", long=True)[0] + ".translate")[0], 0))
lamp = cmds.createNode("transform", name="lamp_geo"); cmds.setAttr(lamp + ".translateY", 3.0)
out = MC.make([cmds.ls("lamp_geo", long=True)[0]], drive="direct", stack=["_offset"])
pma = cmds.listConnections(cmds.ls("lamp_geo", long=True)[0] + ".translate", source=True, destination=False) or []
check("direct: rest values kept through an add node", pma and cmds.nodeType(pma[0]) == "plusMinusAverage")

# ---------------------------------------------------------------- the tool page
from gus_rigtool.tools import make_controls_tool as mt
mt.build("MK_")
j = chain(["tail_01_jnt", "tail_02_jnt"], [(0, 100, -10), (0, 100, -20)])
cmds.select(j)
mt.what()
print(UI["MK_What"]["label"])
mt.run()
check("the page makes them", cmds.objExists("tail_02_ctrl") and cmds.objExists("tail_01_ctrl_offset"))
from gus_rigtool.tools import joint_chain as jc
jc.build("JC_")
check("Joints tab: the centre section is there", "JC_CpKind" in UI and "JC_CpWhat" in UI)
print("ALL OK" if all(ok) else "SOME FAILED")
