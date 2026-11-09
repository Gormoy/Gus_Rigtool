# 4.1.0: Pivots, Groups, Select, Mirror (links) - the logic, offline
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
import math
import numpy as np
from gus_rigtool.core import pivots as PV, mirror_engine as ME, ui
ui.report_error = lambda e, w="": __import__("traceback").print_exc()
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
A = lambda m: np.array(m).reshape(4, 4)
W = lambda n: A(cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True))

# ---------------------------------------------------------------- pivots maths
for rot in ([10, 20, 30], [-45, 80, 5], [0, 0, 0], [170, -30, 60]):
    m = ME.euler_matrix(rot, 0)
    rows = [m[0:3], m[4:7], m[8:11]]
    back = ME.euler_matrix(PV.euler_xyz(rows), 0)
    check("euler from rows round-trips %s" % rot, np.allclose(A(m), A(back), atol=1e-9))
f = PV.frame([1, 1, 0], [0, 1, 0])
check("frame is orthonormal, X along the aim", np.allclose(np.array(f) @ np.array(f).T, np.eye(3))
      and np.allclose(f[0], np.array([1, 1, 0]) / math.sqrt(2)))
check("Newell normal of a square facing +Z", np.allclose(PV.newell([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]), [0, 0, 1]))
bb = [0, 0, 0, 2, 4, 6]
check("box point: bottom centre", PV.box_point(bb, 0.5, 0.0, 0.5) == [1.0, 0.0, 3.0])
check("box labels", PV.box_label(0.5, 0.0, 0.5) == "bottom" and PV.box_label(1.0, 1.0, 1.0) == "+X top front"
      and PV.box_label(0.5, 0.5, 0.5) == "centre")
mr = ME.euler_matrix(PV.mirror_rotation([0, 0, 0]), 0)
check("mirrored handles of world axes: X -> -X, Y stays up", np.allclose(mr[0:3], [-1, 0, 0]) and np.allclose(mr[4:7], [0, 1, 0]))
r = [15, 40, -20]
m0, m1 = ME.euler_matrix(r, 0), ME.euler_matrix(PV.mirror_rotation(r), 0)
check("mirrored handles: X and Y are the reflections", np.allclose([-m0[0], m0[1], m0[2]], m1[0:3]) and
      np.allclose([-m0[4], m0[5], m0[6]], m1[4:7]))
check("mirror point uses the engine", PV.mirror_point([3, 4, 5]) == [-3, 4, 5])

# component frames with made-up vertices
pts = {"m.vtx[0]": [0, 0, 0], "m.vtx[1]": [2, 0, 0], "m.vtx[2]": [0, 0, -2]}
_ls, _xf = cmds.ls, cmds.xform
cmds.ls = lambda *a, **k: list(a[0]) if a and isinstance(a[0], list) and k.get("flatten") else _ls(*a, **k)
def xf(n, **k):
    if isinstance(n, list) and k.get("query"):
        return [v for x in n for v in pts[x]]
    return _xf(n, **k)
cmds.xform = xf
c, rows = PV.component_frame(["m.vtx[0]", "m.vtx[1]", "m.vtx[2]"])
check("3 vertices: X from the 1st to the 2nd, Y the plane's normal", np.allclose(rows[0], [1, 0, 0]) and
      np.allclose(rows[1], [0, 1, 0]) and np.allclose(c, [2 / 3.0, 0, -2 / 3.0]))
c, rows = PV.component_frame(["m.vtx[0]", "m.vtx[1]"])
check("2 vertices: X along them, Y up", np.allclose(rows[0], [1, 0, 0]) and np.allclose(rows[1], [0, 1, 0]))
try:
    PV.component_frame(["m.vtx[0]"]); check("1 vertex refuses", False)
except RuntimeError:
    check("1 vertex refuses", True)
cmds.ls, cmds.xform = _ls, _xf

# ---------------------------------------------------------------- pivots tool
from gus_rigtool.tools import pivot_matcher as pm
pm.build("PV_")
moves = []
_xf2 = cmds.xform
def xf2(n, **k):
    if k.get("pivots") is not None and not k.get("query"):
        moves.append((n.split("|")[-1], [round(v, 3) for v in k["pivots"]]))
        return None
    return _xf2(n, **k)
cmds.xform = xf2
boxes = {"crate": [0, 0, 0, 2, 2, 2], "barrel": [4, 0, 0, 6, 4, 2]}
cmds.exactWorldBoundingBox = lambda nodes, **k: (boxes[nodes[0].split("|")[-1]] if len(nodes) == 1 else
                                                 [0, 0, 0, 6, 4, 2])
cmds.manipPivot = lambda *a, **k: None
for name in boxes:
    cmds.createNode("transform", name=name)
cmds.select(["crate", "barrel"])
pm.to_box([0.5, 0.0, 0.5], each=True)
check("bottom centre of each object's box", moves == [("crate", [1.0, 0.0, 1.0]), ("barrel", [5.0, 0.0, 1.0])])
moves[:] = []
pm.to_box([0.5, 1.0, 0.5], each=False)
check("top centre of the whole selection", moves == [("crate", [3.0, 4.0, 1.0]), ("barrel", [3.0, 4.0, 1.0])])
moves[:] = []
a = cmds.createNode("joint", name="knee_jnt"); cmds.xform(a, worldSpace=True, translation=(0, 10, 0))
b = cmds.createNode("joint", name="ankle_jnt"); cmds.xform(b, worldSpace=True, translation=(0, 0, 2))
_xf3 = cmds.xform
cmds.xform = lambda n, **k: ([0, 10, 0] if "knee" in str(n) else [0, 0, 2]) if k.get("rotatePivot") and k.get("query") else xf2(n, **k)
cmds.select(["crate", "knee_jnt", "ankle_jnt"])
UI["PV_Chain"]["value"] = 25.0
pm.along_chain()
check("along a chain: 25% from knee to ankle", moves == [("crate", [0.0, 7.5, 0.5])])
cmds.xform = xf2
moves[:] = []
cmds.createNode("transform", name="L_hand_ctrl"); cmds.createNode("transform", name="R_hand_ctrl")
cmds.xform = lambda n, **k: [3.0, 5.0, 1.0] if k.get("rotatePivot") and k.get("query") else xf2(n, **k)
got = PV.mirror_pivots([cmds.ls("L_hand_ctrl", long=True)[0]])
check("mirror pivots to the twin", moves == [("R_hand_ctrl", [-3.0, 5.0, 1.0])] and got[0][1])
mem = PV.remember(None, [1, 2, 3], [0, 90, 0])
check("remember / remembered", PV.remembered()["position"] == [1.0, 2.0, 3.0])
cmds.xform = _xf2

# ---------------------------------------------------------------- groups
def _group(*a, **k):
    return cmds.createNode("transform", name=k.get("name"), parent=k.get("parent")) if k.get("parent") else \
        cmds.createNode("transform", name=k.get("name"))
cmds.group = _group
from gus_rigtool.tools import group_maker as gm
gm.build("GR_")
check("ready-made stacks listed", ("Control", "_offset, _sdk, _driven") in gm.stacks())
gm.save_stack("Face", "_offset , sdk")
check("save your own stack", ("Face", "_offset, _sdk") in gm.stacks())
gm.delete_stack("Face")
check("delete it", ("Face", "_offset, _sdk") not in gm.stacks())
try:
    gm.delete_stack("Control"); check("ready-made stack can't be deleted", False)
except RuntimeError:
    check("ready-made stack can't be deleted", True)
top = cmds.createNode("transform", name="arm_grp")
off = cmds.createNode("transform", name="L_arm_ctrl_offset", parent=top)
cmds.xform(off, worldSpace=True, translation=(5, 2, 0), rotation=(0, 30, 0))
ctl = cmds.createNode("transform", name="L_arm_ctrl", parent=off)
cmds.setAttr(ctl + ".translateX", 1.0)
w_ctrl, w_off = W("L_arm_ctrl"), W("L_arm_ctrl_offset")
from gus_rigtool.core import utils
tops = gm.insert_above_parent([utils.uuid(cmds.ls("L_arm_ctrl", long=True)[0])], ["_sdk"], replace=True)
p = cmds.ls("L_arm_ctrl", long=True)[0].split("|")
check("above its parent: arm_grp > L_arm_ctrl_sdk > offset > ctrl",
      p[-4:] == ["arm_grp", "L_arm_ctrl_sdk", "L_arm_ctrl_offset", "L_arm_ctrl"])
check("nothing moved", np.allclose(W("L_arm_ctrl"), w_ctrl) and np.allclose(W("L_arm_ctrl_offset"), w_off))
check("the new group matches the parent", np.allclose(W("L_arm_ctrl_sdk"), w_off))
removed, skipped = gm.remove_groups([cmds.ls("L_arm_ctrl_sdk", long=True)[0]])
p = cmds.ls("L_arm_ctrl", long=True)[0].split("|")
check("remove group: back to arm_grp > offset > ctrl, nothing moved",
      removed == ["L_arm_ctrl_sdk"] and p[-3:] == ["arm_grp", "L_arm_ctrl_offset", "L_arm_ctrl"]
      and np.allclose(W("L_arm_ctrl"), w_ctrl))
shaped = cmds.createNode("transform", name="shaped_grp"); cmds.createNode("nurbsCurve", name="shapedShape", parent=shaped)
removed, skipped = gm.remove_groups([cmds.ls("shaped_grp", long=True)[0]])
check("a node with a shape is skipped", not removed and skipped and "shape" in skipped[0][1])
tgt = cmds.createNode("transform", name="target_loc"); cmds.xform(tgt, worldSpace=True, translation=(0, 9, 9))
obj = cmds.createNode("transform", name="prop"); cmds.xform(obj, worldSpace=True, translation=(1, 1, 1))
w_obj = W("prop")
tops = gm.group_each([utils.uuid(cmds.ls("prop", long=True)[0])], ["_grp"], False, True, False,
                     target=cmds.ls("target_loc", long=True)[0])
check("at last selected: the group on the target, the object stays",
      np.allclose(W("prop_grp")[3, :3], [0, 9, 9]) and np.allclose(W("prop"), w_obj))
o = dict(gm.DEFAULTS, suffix="_offset, _sdk", place=1, where=1, mode=1)
txt = gm.preview_text(o, [cmds.ls("L_arm_ctrl", long=True)[0]])
check("preview names the stack and where it goes", "L_arm_ctrl_offset*" in txt and "> L_arm_ctrl_sdk" in txt
      and "name taken" in txt)
print(txt)

# ---------------------------------------------------------------- select
from gus_rigtool.tools import selector as sl
sl.build("SL_")
rig = cmds.createNode("transform", name="rig")
a1 = cmds.createNode("transform", name="L_a_ctrl", parent=rig); cmds.createNode("nurbsCurve", name="L_a_ctrlShape", parent=a1)
a2 = cmds.createNode("transform", name="L_b_ctrl", parent=a1); cmds.createNode("nurbsCurve", name="L_b_ctrlShape", parent=a2)
cmds.addAttr(a2, longName="follow", attributeType="double")
r1 = cmds.createNode("transform", name="R_a_ctrl", parent=rig); cmds.createNode("nurbsCurve", name="R_a_ctrlShape", parent=r1)
j = cmds.createNode("joint", name="L_a_jnt", parent=rig)
R = [cmds.ls("rig", long=True)[0]]
names = lambda ns: sorted(n.split("|")[-1] for n in ns)
check("controls inside", names(sl.find_inside(R, sl.is_control)) == ["L_a_ctrl", "L_b_ctrl", "R_a_ctrl"])
check("depth 1: direct children only", names(sl.find_inside(R, sl.is_control, depth=1)) == ["L_a_ctrl", "R_a_ctrl"])
check("invert: everything that isn't a control", names(sl.find_inside(R, sl.is_control, invert=True)) == ["L_a_jnt"])
check("with an attribute", names(sl.find_inside(R, sl.has_attr("follow"))) == ["L_b_ctrl"])
tw, lonely = sl.twins([cmds.ls("L_a_ctrl", long=True)[0], cmds.ls("L_b_ctrl", long=True)[0]])
check("twins: R_a_ctrl found, L_b_ctrl has none", names(tw) == ["R_a_ctrl"] and names(lonely) == ["L_b_ctrl"])
nm = sl.save_quick_set("lips!", [cmds.ls("L_a_ctrl", long=True)[0], cmds.ls("R_a_ctrl", long=True)[0]])
cmds.select(clear=True)
sl.load_quick_set(nm)
check("quick set saved (name cleaned) and selected again", nm == "lips_" and
      names(cmds.ls(selection=True, long=True)) == ["L_a_ctrl", "R_a_ctrl"])
sl.remember_selection("Controls", [cmds.ls("L_a_ctrl", long=True)[0]])
cmds.select(clear=True)
sl.restore_recent(0)
check("recent: select again", names(cmds.ls(selection=True, long=True)) == ["L_a_ctrl"])
cmds.select(R)
sl.select_type("Controls", sl.is_control)
check("the type buttons still select", names(cmds.ls(selection=True, long=True)) == ["L_a_ctrl", "L_b_ctrl", "R_a_ctrl"])

# ---------------------------------------------------------------- mirror links
from gus_rigtool.core import mirror_links as ML, follow
cmds.deleteAttr = lambda node, attribute=None: _n(node).user.pop(attribute, None)
for side, x in (("L", 3), ("R", -3)):
    o_ = cmds.createNode("transform", name="%s_lid_ctrl_offset" % side); cmds.xform(o_, worldSpace=True, translation=(x, 160, 6))
    c_ = cmds.createNode("transform", name="%s_lid_ctrl" % side, parent=o_)
    cmds.createNode("nurbsCurve", name="%s_lid_ctrlShape" % side, parent=c_)
    cmds.addAttr(c_, longName="squash", attributeType="double", keyable=True)
    e_ = cmds.createNode("transform", name="%s_eye_ctrl" % side); cmds.xform(e_, worldSpace=True, translation=(x, 160, 5))
jaw = cmds.createNode("transform", name="jaw_ctrl")
cmds.setAttr("L_lid_ctrl.squash", 0.7)
L = cmds.ls("L_lid_ctrl", long=True)[0]
follow.add(cmds.ls("L_eye_ctrl", long=True)[0], [L], ("rotate",), "control", 0.4, pivot=[3, 160, 4], axes="own")
L = cmds.ls("L_lid_ctrl", long=True)[0]
out = ML.run([L], ["attrs", "follows"])
check("attribute values copied", cmds.getAttr("R_lid_ctrl.squash") == 0.7 and out["attrs"][0])
g = follow.follow_group_of(cmds.ls("R_lid_ctrl", long=True)[0])
m = follow._meta(g) if g else {}
check("follow mirrored: twin driver, same weight, pivot mirrored, same axes",
      m.get("driver") == "R_eye_ctrl" and abs(cmds.getAttr("R_lid_ctrl.follow") - 0.4) < 1e-6
      and m.get("pivot", "").startswith("-3,160,4") and m.get("axes") == "own")
L = cmds.ls("L_lid_ctrl", long=True)[0]
out = ML.run([L], ["follows"])
check("again: skipped (twin already follows) unless Replace", not out["follows"][0] and "already" in out["follows"][1][0][1])
out = ML.run([L], ["follows"], replace=True)
check("Replace: made again", out["follows"][0] and not out["follows"][1])
for sd in "LR":
    cmds.createNode("transform", name="%s_mouth_ctrl" % sd, parent=cmds.createNode("transform", name="%s_mouth_off" % sd))
follow.add(jaw, [cmds.ls("L_mouth_ctrl", long=True)[0]], ("rotate",), "control", 0.5)
ML.run([cmds.ls("L_mouth_ctrl", long=True)[0]], ["follows"])
g = follow.follow_group_of(cmds.ls("R_mouth_ctrl", long=True)[0])
check("a centre driver (the jaw) is used as it is", g and follow._meta(g)["driver"] == "jaw_ctrl")
cmds.createNode("transform", name="L_foot_ctrl"); cmds.createNode("transform", name="R_foot_ctrl")
cmds.createNode("transform", name="L_hip_ctrl"); cmds.createNode("transform", name="R_hip_ctrl")
cmds.parentConstraint(cmds.ls("L_hip_ctrl", long=True)[0], cmds.ls("L_foot_ctrl", long=True)[0], maintainOffset=True)
out = ML.run([cmds.ls("L_foot_ctrl", long=True)[0]], ["constraints"])
rc = [c for c in cmds.listRelatives(cmds.ls("R_foot_ctrl", long=True)[0], children=True, fullPath=True) or []
      if cmds.nodeType(c) == "parentConstraint"]
check("constraint mirrored onto the twin, from the twin target",
      rc and cmds.parentConstraint(rc[0], query=True, targetList=True) and
      "R_hip_ctrl" in cmds.parentConstraint(rc[0], query=True, targetList=True)[0])
# ---------------------------------------------------------------- mirror tool page
from gus_rigtool.tools import mirror_tool as mt
mt.build("MI_")
mt.go("links")
fr = mt._frames["MI_"]
check("mode bar: Links opens its part, the others fold",
      UI[fr["links"]].get("collapse") is False and UI[fr["main"]].get("collapse") is True)
mt.go("mode", 3)
check("mode bar: Joints sets the mode and opens Mirror", UI["MI_Mode"].get("select") == 3
      and UI[fr["main"]].get("collapse") is False and UI[fr["pose"]].get("collapse") is True)
cmds.select(cmds.ls("L_lid_ctrl", long=True))
UI["MI_Mode"]["select"] = 2
rows = mt.pairs_report()
check("list pairs: L_lid_ctrl -> R_lid_ctrl (exists)", rows and rows[0][1].split("|")[-1] == "R_lid_ctrl"
      and rows[0][2].startswith("exists"))
print("ALL OK" if all(ok) else "SOME FAILED")
