# 4.0 corrective shapes (Fixes): the inverse of the skinning lands the sculpt exactly, the pose reader nodes,
# mirror map / mirrored aim, the tool page builds
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
import math
from unittest import mock
for name in ("scriptJob", "image", "intSlider"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool.core import shape_fixes as F

# matrices
def rot_z(deg, t=(0, 0, 0)):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, t[0], t[1], t[2], 1]
m = rot_z(30, (1, 2, 3))
print("inverse ok:", all(abs(a - b) < 1e-9 for a, b in zip(F.mmul(m, F.inverse(m)), [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])))

# unskin: two joints, a point weighted 50/50; skin it forward, then back
mats = [rot_z(0), rot_z(60, (0, 0, 0))]
weights = [[0.5, 0.5], [1.0, 0.0], [0.2, 0.8]]
rest = [[2.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 3.0, 1.0]]
def skin_fwd(p, w):
    acc = [sum(wi * mi[k] for wi, mi in zip(w, mats)) for k in range(16)]
    return F.pmul(p, acc)
posed = [skin_fwd(p, w) for p, w in zip(rest, weights)]
from gus_rigtool.core import skin_io
skin_io.get_weights = lambda skin, mesh: (["a", "b"], weights)
F.influence_matrices = lambda skin: mats
real_get = cmds.getAttr
cmds.getAttr = lambda plug, **k: [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1] if plug.endswith("geomMatrix") or plug.endswith("worldMatrix[0]") else real_get(plug, **k)
back = F.unskin("body", "skin", posed)
print("unskin gives the rest points back:", all(abs(a - b) < 1e-9 for p, q in zip(back, rest) for a, b in zip(p, q)))
sculpted = [[p[0], p[1] + 0.5, p[2]] for p in posed]                 # sculpt: up 0.5 in the pose
fixed = F.unskin("body", "skin", sculpted)
print("the fix, skinned again, is the sculpt:", all(abs(a - b) < 1e-9 for p, q, w in zip(fixed, sculpted, weights)
                                                   for a, b in zip(skin_fwd(p, w), q)))
cmds.getAttr = real_get

# reader nodes
elbow = cmds.createNode("joint", name="L_elbow_jnt"); hand = cmds.createNode("joint", name="L_hand_jnt", parent=elbow)
cmds.setAttr(hand + ".translate", 10, 0, 0)
print("aim axis:", F.aim_axis(elbow))
plug, nodes = F.make_reader("L_elbow_90", elbow, [0, 1, 0], 90)
rm = nodes[-1]
print("reader:", [cmds.nodeType(n) for n in nodes], "| out:", plug.split("|")[-1], "| cone:", cmds.getAttr(rm + ".inputMax"),
      "| 1 at the pose -> 0 at rest:", cmds.getAttr(rm + ".outputMin"), cmds.getAttr(rm + ".outputMax"))

# mirror map
pts = [[1, 0, 0], [-1, 0, 0], [0, 2, 0], [3, 1, 1], [-3, 1, 1]]
print("mirror map:", F.mirror_map(pts))
# mirrored aim through the rest world: a twin under a mirrored parent
lp = cmds.createNode("joint", name="L_arm_jnt"); rp = cmds.createNode("joint", name="R_arm_jnt")
cmds.setAttr(lp + ".translate", 5, 0, 0); cmds.setAttr(rp + ".translate", -5, 0, 0)
cmds.setAttr(rp + ".jointOrient", 0, 180, 0)
lj = cmds.createNode("joint", name="L_fore_jnt", parent=lp); rj = cmds.createNode("joint", name="R_fore_jnt", parent=rp)
aim = F.mirror_aim(lj, rj, [0.6, 0.8, 0.0])
print("mirrored aim (parent turned 180 in Y):", [round(v, 3) for v in aim])

# the tool page
from gus_rigtool.core import ui
errors = []
ui.report_error = lambda e, where="": errors.append("%s: %s" % (where, e))
_cur[0] = None; cmds.columnLayout("root")
ui._build_tool("fixes", "t_fixes_")
print("page builds:", not errors, errors)
