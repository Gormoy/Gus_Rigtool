# Stick to skin (3.12.1): each control follows the joints of the skin under it with the skin's own weights (bind
# matrix x joint now, summed by weight) - minus the joints it moves itself (their share to the joint above) - in a
# world-driven stick group blended with its anchor; translation only by default; added later; unstick; kept through
# a rebuild; a control stuck with 3.12.0 still unsticks
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.builder import build as bld
from gus_rigtool.core import sticky, skin_io
bld.biped(180)
bld.build_all(180)
body = cmds.createNode("transform", name="body_geo"); cmds.createNode("mesh", name="body_geoShape", parent=body)
skin = cmds.createNode("skinCluster", name="body_skin")
JOINTS = ["head_jnt", "jaw_jnt", "L_lip_corner_jnt", "R_lip_corner_jnt"]
for i, j in enumerate(JOINTS):
    cmds.connectAttr(j + ".worldMatrix[0]", "body_skin.matrix[%d]" % i)
import gus_rigtool.core.skin_mirror as sm
sm.skin_of = lambda m: "body_skin" if "body_geo" in m else None
cmds.skinCluster = lambda *a, **k: list(JOINTS) if k.get("query") else None
lc = cmds.xform("L_lip_corner_ctrl", query=True, worldSpace=True, translation=True)
rc = cmds.xform("R_lip_corner_ctrl", query=True, worldSpace=True, translation=True)
far = [lc[0] + 50, lc[1] + 50, lc[2]]
PTS = [lc, [lc[0] + 0.1, lc[1], lc[2]], [lc[0], lc[1] + 0.1, lc[2]], far, rc]
W = {0: {"L_lip_corner_jnt": 0.5, "jaw_jnt": 0.3, "head_jnt": 0.2}, 1: {"L_lip_corner_jnt": 0.5, "jaw_jnt": 0.5},
     2: {"jaw_jnt": 0.4, "head_jnt": 0.6}, 3: {"head_jnt": 1.0}, 4: {"R_lip_corner_jnt": 0.6, "jaw_jnt": 0.4}}
skin_io.positions = lambda m: PTS
def skinPercent(skin_, point, **k):
    i = int(point.split("[")[-1][:-1])
    names = sorted(W[i])
    return names if "transform" in k else [W[i][n] for n in names]
cmds.skinPercent = skinPercent
_get = cmds.getAttr
cmds.getAttr = lambda plug, **k: [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0] if ".bindPreMatrix[" in plug \
    else _get(plug, **k)
ctrl = cmds.ls("L_lip_corner_ctrl", long=True)[0]
print("the skin under the control (3 nearest vertices):",
      {k.split("|")[-1]: round(v, 3) for k, v in sticky.skin_weights_at("body_geo", lc).items()})
skip = sticky.downstream_joints([ctrl])
print("joints the control moves:", sorted(j.split("|")[-1] for j in skip))
print("what it follows (its own joint's share to the joint above):",
      {k.split("|")[-1]: round(v, 3) for k, v in sticky.follow_weights(sticky.skin_weights_at("body_geo", lc), skip, cmds.ls(JOINTS, long=True)).items()})
try:
    sticky.follow_weights({cmds.ls("L_lip_corner_jnt", long=True)[0]: 1.0}, skip, [])
except RuntimeError as e:
    print("only its own joint there:", e)
sticky.stick([ctrl], "body_geo")
c = cmds.ls("L_lip_corner_ctrl", long=True)[0]
d = sticky.read(c)
grp = cmds.ls(d["group"], long=True)[0]
wt = d["nodes"][0]
ins = [cmds.listConnections("%s.matrixIn[1]" % m, source=True, destination=False)[0] for m in d["nodes"][1:-3]]
print("stuck: under", c.split("|")[-3], "| follows", d["joints"], "| through", ins)
print("no hidden mesh, no pin:", not cmds.objExists("body_geo_stickyBase"), "| skin weights on the add node:",
      [round(cmds.getAttr("%s.wtMatrix[%d].weightIn" % (wt, k)), 3) for k in range(len(d["joints"]))])
print("world-driven group:", cmds.getAttr(grp + ".inheritsTransform") in (0, False), "| anchor:", d["anchor"],
      "| blend on stick:", cmds.listConnections(d["nodes"][-1] + ".envelope", source=True, destination=False, plugs=True),
      "| translation only:", cmds.getAttr(d["nodes"][-1] + ".target[0].useRotate") in (0, False))
try:
    sticky.stick([c], "body_geo")
except RuntimeError as e:
    print("twice refused:", e)
r = cmds.ls("R_lip_corner_ctrl", long=True)[0]
sticky.stick([r], "body_geo", rotate=True)
r = cmds.ls("R_lip_corner_ctrl", long=True)[0]
print("added later:", bool(sticky.read(cmds.ls("L_lip_corner_ctrl", long=True)[0])), sticky.read(r)["joints"],
      "| turning with the skin:", sticky.read(r)["rotate"])
nodes = d["nodes"]
sticky.unstick(c)
c = cmds.ls("L_lip_corner_ctrl", long=True)[0]
print("unstuck: parent", c.split("|")[-3], "| stick attr:", cmds.attributeQuery("stick", node=c, exists=True),
      "| its nodes gone:", not any(cmds.objExists(n) for n in nodes), "| the other still stuck:", bool(sticky.read(r)))
# kept through a rebuild of the face
sticky.stick([c], "body_geo", ignore=["head_jnt"])
print("don't follow head:", sticky.read(cmds.ls("L_lip_corner_ctrl", long=True)[0])["joints"])
from gus_rigtool.core import utils
_SETTINGS["build"] = dict(utils.tool_settings("build", bld.DEFAULTS), keep_skin=False)   # the skin isn't the point here
bld.build_picked(["C:face"], 180)
c = cmds.ls("L_lip_corner_ctrl", long=True)[0]
print("after Build picked: stuck again:", bool(sticky.read(c)), "| under:", c.split("|")[-3], "| still not head:",
      "head_jnt" not in sticky.read(c)["joints"])
# a control stuck with 3.12.0 (pin + hidden copy) still unsticks cleanly
sticky.unstick(c)
c = cmds.ls("L_lip_corner_ctrl", long=True)[0]
pin = cmds.createNode("transform", name="body_geo_stickyBase_pin"); base = cmds.createNode("transform", name="body_geo_stickyBase")
cmds.removeMultiInstance = mock.MagicMock()
sticky._write(c, {"mesh": "body_geo", "group": "none_grp", "piece": "none", "local": [], "nodes": [], "pin": "body_geo_stickyBase_pin",
                  "base": "body_geo_stickyBase", "index": 0})
sticky.unstick(c)
print("old-style unstick: pin and copy gone:", not cmds.objExists("body_geo_stickyBase_pin"), not cmds.objExists("body_geo_stickyBase"))
# the diagnostic for real scenes
text = sticky.diagnose("L_lip_corner_ctrl", "body_geo")
print("diagnose: lines", len(text.splitlines()), "| has groups / skin / moves / follow:",
      all(k in text for k in ("groups above", "skin at the control", "joints this control moves", "it would follow")))
