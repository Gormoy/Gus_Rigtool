# 4.0.5: ribbon with the pivot on the shape - bind joints on the ribbon, point + orient constrained to their
# controls; 'Switch to constraints' converts an older build (joints copying the controls) with nothing moving
exec(open("fakemaya.py").read())
import math
import numpy as np
from gus_rigtool.core import ribbon, follow, mirror_engine as me
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
cmds.deleteAttr = lambda node, attribute=None: _n(node).user.pop(attribute, None)
cmds.joint = lambda name=None, **k: cmds.createNode("joint", name=name)
cmds.disconnectAttr = globals().get("disconnectAttr", getattr(cmds, "disconnectAttr", None))
A = lambda m: np.array(m).reshape(4, 4)
W = lambda n: cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True)

# --- the maths: an orient constraint passes the control's own turn to the joint, even on a -1 scale control
def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a)); return np.array([[1,0,0],[0,c,s],[0,-s,c]])
def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a)); return np.array([[c,0,-s],[0,1,0],[s,0,c]])
S_ = np.diag([-1, 1, 1.0])
P = S_ @ ry(200)                         # reflected offset (true mirror) - row-vector convention like Maya
J0 = ry(37) @ rx(12)                     # the joint's own rest axes (anything)
def rot_of(m):                           # Maya decomposes a reflected matrix as (-1 scale) x rotation
    return S_ @ m if np.linalg.det(m) < 0 else m
off = J0 @ np.linalg.inv(rot_of(P))      # maintain offset
for Rl in (rx(25), ry(-40) @ rx(10)):
    ctrl_w = Rl @ P
    joint_w = off @ rot_of(ctrl_w)
    turn_ctrl = np.linalg.inv(P) @ ctrl_w            # world turn of the control from rest
    turn_joint = np.linalg.inv(J0) @ joint_w         # world turn of the joint from rest
    check("orient constraint on a mirrored control: the joint turns like the control",
          np.allclose(turn_ctrl, turn_joint) and np.isclose(np.linalg.det(joint_w), 1))

# --- new builds: the bind joint helper
cmds.createNode("transform", name="b_off"); c = cmds.createNode("transform", name="b_ctrl", parent="b_off")
cmds.xform("b_off", worldSpace=True, matrix=[1,0,0,0, 0,1,0,0, 0,0,1,0, 2,3,5,1])
fm = [1,0,0,0, 0,1,0,0, 0,0,1,0, 2,3,4,1]
b = ribbon._make_bind_on_shape("fol_07", "b_ctrl", fm, 0.3)
cons = sorted(cmds.nodeType(x) for x in cmds.listRelatives(b, type="constraint") or [])
check("new build: joint on the follicle", np.allclose(W(b)[12:15], [2, 3, 4]))
check("new build: point + orient constraints, no direct link", cons == ["orientConstraint", "pointConstraint"]
      and not (cmds.listConnections("b_ctrl.translate", source=False, destination=True) or [])
      or cons == ["orientConstraint", "pointConstraint"] and ribbon._copier("b_ctrl") is None)

# --- an older mouth build: joints copy their controls, some follow the jaw (Follow tool groups above the copies)
top = cmds.createNode("transform", name="Mouth_ribbon_ctrls_grp")
bgrp = cmds.createNode("transform", name="Mouth_ribbon_bind_grp")
for g in (top, bgrp):
    cmds.addAttr(g, longName="rrbSurface", dataType="string"); cmds.setAttr(g + ".rrbSurface", "Mouth_ribbon", type="string")
    cmds.addAttr(g, longName="rrbSkin", dataType="string"); cmds.setAttr(g + ".rrbSkin", "", type="string")
    cmds.addAttr(g, longName="rrbSettings", dataType="string")
    cmds.setAttr(g + ".rrbSettings", '{"prefix": "Mouth_ribbon", "pivot_on_shape": true}', type="string")
cmds.createNode("transform", name="Mouth_ribbon")
def make(i, x, y, yaw, flip=False):
    off = cmds.createNode("transform", name="m%d_offset" % i, parent=top)
    cmds.addAttr(off, longName="rrbIndex", attributeType="long"); cmds.setAttr(off + ".rrbIndex", i)
    co, si = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    m = [co, 0, -si, 0, 0, 1, 0, 0, si, 0, co, 0, x, y, 10, 1]
    if flip:
        m[0:3] = [-v for v in m[0:3]]
    cmds.xform(off, worldSpace=True, matrix=m)
    ctrl = cmds.createNode("transform", name="m%d_ctrl" % i, parent=off)
    cmds.createNode("nurbsCurve", name="m%d_ctrlShape" % i, parent=ctrl)
    boff = cmds.createNode("transform", name="m%d_bind_offset" % i, parent=bgrp)
    cmds.xform(boff, worldSpace=True, matrix=m[:12] + [x, y, 9.0, 1])
    bj = cmds.createNode("joint", name="m%d_bind" % i, parent=boff)
    for ch in ("translate", "rotate"):
        cmds.connectAttr(ctrl + "." + ch, bj + "." + ch)
    return ctrl
ctrls = [make(0, 3, 0, 20), make(1, 0, 1, 0), make(2, -3, 0, 200, flip=True), make(3, 0, -1, 180)]
jaw = cmds.createNode("transform", name="jaw_ctrl")
follow.add(jaw, ["m3_ctrl"], ("rotate",), "control", 0.8)
check("setup: the low lip's joint has its follow copy group",
      bool(cmds.ls("m3_ctrl_jnt0_followSpace")) and ribbon._copier("m3_ctrl"))
before = {i: W("m%d_bind" % i)[12:15] for i in range(4)}
cmds.setAttr("m0_ctrl.translateX", 1)
try:
    ribbon.to_constraints("Mouth_ribbon"); check("refuses posed controls", False)
except RuntimeError as e:
    check("refuses posed controls", "m0_ctrl" in str(e))
cmds.setAttr("m0_ctrl.translateX", 0)
n = ribbon.to_constraints("Mouth_ribbon")
check("4 joints switched", n == 4)
for i in range(4):
    j = cmds.ls("m%d_bind" % i, long=True)[0]
    check("m%d: no direct link, point + orient constraints" % i,
          ribbon._copier("m%d_ctrl" % i) is None and
          sorted(cmds.nodeType(x) for x in cmds.listRelatives(j, type="constraint") or []) == ["orientConstraint", "pointConstraint"])
    check("m%d: in the bind group, didn't move" % i, j.split("|")[-2] == "Mouth_ribbon_bind_grp"
          and np.allclose(W(j)[12:15], before[i]))
    m = A(W(j))[:3, :3]
    check("m%d: clean axes (scale 1, no -1)" % i, np.allclose(np.linalg.norm(m, axis=1), 1) and np.linalg.det(m) > 0)
check("copy groups gone", not cmds.ls("m*_bind_offset"))
check("the joint's follow copy and its multiply gone", not cmds.ls("m3_ctrl_jnt0_followSpace")
      and not cmds.ls("m3_ctrl_jnt0_follow_rotate"))
g = follow.follow_group_of(cmds.ls("m3_ctrl", long=True)[0])
check("the control still follows the jaw, record updated", g and
      not any("jnt0" in x for x in follow._meta(g)["nodes"]) and follow.all_follows())
check("remove follow still works", follow.remove(["m3_ctrl"]) == 1)
try:
    ribbon.to_constraints("Mouth_ribbon"); check("second time: nothing to do", False)
except RuntimeError as e:
    check("second time: nothing to do", "already" in str(e))
# mirror sides on the constrained build: constraints remade, joints stay. In Maya the old constraints drag the
# joints the moment the offset turns (the fake doesn't solve them): do that drag here, as Maya would.
_pm = ribbon._place_mirrored
def _dragging(node, twin, ax):
    moved = {n for n, _c in ribbon._driven_by(ribbon._control_under(node) or node)[1]}
    _pm(node, twin, ax)
    dragged.append(len(moved))
    for j in moved:
        p = cmds.xform(j, query=True, worldSpace=True, translation=True)
        cmds.xform(j, worldSpace=True, translation=[p[0] + 1.0, p[1], p[2]])
dragged = []
ribbon._place_mirrored = _dragging
n = ribbon.mirror_sides("Mouth_ribbon")
ribbon._place_mirrored = _pm
# 4.4.3: point / orient constraints remade with their own 'skip' flag (only a parent constraint has skipRotate)
calls = []
_rm = ribbon._remake_constraint
for kind in ("pointConstraint", "orientConstraint", "parentConstraint"):
    t = cmds.createNode("transform", name="tgt_" + kind); d = cmds.createNode("transform", name="drv_" + kind)
    con = getattr(cmds, kind)(t, d)[0]
    try:
        made = ribbon._remake_constraint(con, d)
        calls.append(bool(made))
    except TypeError as e:
        print("   ", kind, e); calls.append(False)
check("remake point / orient / parent constraints: right flags for each", calls == [True, True, True])
undos = []
_undo = getattr(cmds, 'undo', None)
cmds.undo = lambda *a, **k: undos.append(1)
def _boom(*a, **k):
    raise TypeError("Invalid flag 'test'")
_rms = ribbon._remake_constraints
ribbon._remake_constraints = _boom
_ui = cmds.undoInfo                                 # 5.6.28: only its own step is undone - say which it is
cmds.undoInfo = lambda *a, **k: "gusrigRibbonMirrorSides" if k.get("undoName") else None
try:
    ribbon.mirror_sides("Mouth_ribbon"); raised = False
except TypeError:
    raised = True
cmds.undoInfo = _ui
check("mirror sides fails part way: undone, then the error", raised and undos == [1])
ribbon._remake_constraints = _rms
if _undo: cmds.undo = _undo
else: del cmds.undo
check("mirror sides after: joints stay, still constrained",
      all(np.allclose(W("m%d_bind" % i)[12:15], before[i]) for i in range(4)) and
      len(cmds.listRelatives(cmds.ls("m2_bind", long=True)[0], type="constraint") or []) == 2)

# 4.0.6: a build made with 'Scale controls too' (joints copy translate, rotate, scale) converts as well
top2 = cmds.createNode("transform", name="Lid_ribbon_ctrls_grp")
bgrp2 = cmds.createNode("transform", name="Lid_ribbon_bind_grp")
for g in (top2, bgrp2):
    cmds.addAttr(g, longName="rrbSurface", dataType="string"); cmds.setAttr(g + ".rrbSurface", "Lid_ribbon", type="string")
    cmds.addAttr(g, longName="rrbSkin", dataType="string"); cmds.setAttr(g + ".rrbSkin", "", type="string")
    cmds.addAttr(g, longName="rrbSettings", dataType="string")
    cmds.setAttr(g + ".rrbSettings", '{"prefix": "Lid_ribbon", "pivot_on_shape": true, "pivot_scale": true}', type="string")
cmds.createNode("transform", name="Lid_ribbon")
off = cmds.createNode("transform", name="lid0_offset", parent=top2)
cmds.addAttr(off, longName="rrbIndex", attributeType="long"); cmds.setAttr(off + ".rrbIndex", 0)
cmds.xform(off, worldSpace=True, matrix=[1,0,0,0, 0,1,0,0, 0,0,1,0, 3,160,7,1])
lc = cmds.createNode("transform", name="lid0_ctrl", parent=off); cmds.createNode("nurbsCurve", name="lid0_ctrlShape", parent=lc)
bo = cmds.createNode("transform", name="lid0_bind_offset", parent=bgrp2)
cmds.xform(bo, worldSpace=True, matrix=[1,0,0,0, 0,1,0,0, 0,0,1,0, 3,160,6,1])
lj = cmds.createNode("joint", name="lid0_bind", parent=bo)
for ch in ("translate", "rotate", "scale"):
    cmds.connectAttr(lc + "." + ch, lj + "." + ch)
check("scale build converts", ribbon.to_constraints("Lid_ribbon") == 1)
lj = cmds.ls("lid0_bind", long=True)[0]
check("scale build: no links left (scale too), constraints made",
      not cmds.listConnections(lj + ".scale", source=True, destination=False)
      and sorted(cmds.nodeType(x) for x in cmds.listRelatives(lj, type="constraint") or []) == ["orientConstraint", "pointConstraint"])
check("scale build: its setting is off now",
      ribbon._build_settings(ribbon._find_builds()[ribbon._resolve("Lid_ribbon")]).get("pivot_scale") is False)
print("ALL OK" if all(ok) else "SOME FAILED")
# 4.0.6: an old saved 'Scale controls too' starts off once; after that your choice is kept
from gus_rigtool.core import utils
from gus_rigtool.tools import ribbon_tool as rt
store = {"ribbon": {"pivot_scale": True, "ctrl_radius": 2.0}}
utils.load_setting = lambda k, d: store.get(k, d)
def _sv(k, v): store[k] = v
utils.save_setting = _sv
rt._scale_off_once()
print("scale reset once:", store["ribbon"]["pivot_scale"] is False and store["ribbon"]["ctrl_radius"] == 2.0)
store["ribbon"]["pivot_scale"] = True; rt._scale_off_once()
print("then kept:", store["ribbon"]["pivot_scale"] is True)
