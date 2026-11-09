# 5.6.2: a joint chain whose joints have Segment Scale Compensate (Maya's default) - a parent joint's own scale
# doesn't reach the joint below, so each joint of the chain gets the global scale (the Hare's skeleton_grp: 62 joints
# didn't scale); without Segment Scale Compensate the joint below inherits it (left alone, not twice); Make the rig
# scale does it all in one go and is undone if anything moved at rest
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import scale_check as SC, repair
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

g = cmds.ls(cmds.createNode("transform", name="Global_ctrl"), long=True)[0]
cmds.addAttr(g, longName="globalScale", attributeType="double", defaultValue=1.0)
ctrl = cmds.ls(cmds.createNode("transform", name="Hips_ctrl", parent=g), long=True)[0]
skel = cmds.createNode("transform", name="skeleton_grp")
def joint(name, parent, ssc=True):
    j = cmds.ls(cmds.createNode("joint", name=name, parent=parent), long=True)[0]
    cmds.setAttr(j + ".segmentScaleCompensate", ssc)
    for a in "XYZ":
        cmds.setAttr("%s.scale%s" % (j, a), 1)
    return j
hip = joint("L_femur", skel)
knee = joint("L_tibia", hip)
ankle = joint("L_ankle", knee, ssc=False)
cmds.connectAttr(hip + ".scale", knee + ".inverseScale")            # Maya connects these in a chain
cmds.connectAttr(knee + ".scale", ankle + ".inverseScale")
for j in (hip, knee, ankle):
    cmds.setAttr(j + ".translateX", 1)
SKIN = {hip, knee, ankle}
with mock.patch.object(SC, "_skin_joints", return_value=SKIN), \
        mock.patch.object(SC, "_driver", return_value=ctrl), \
        mock.patch.object(SC, "scale_control", return_value=(g, g + ".globalScale")), \
        mock.patch.object(repair, "rest_points", return_value={}), \
        mock.patch.object(SC, "measure_joints", return_value=([], [])):
    check("before: the whole chain is found (only the top one was before 5.6.2)",
          sorted(j.split("|")[-1] for j, _d in SC.joints(g)) == ["L_ankle", "L_femur", "L_tibia"])
    check("Segment Scale Compensate: the parent joint's own scale doesn't count for the joint below",
          not SC.scaled_by_rig(knee, g))
    got = SC.make_scalable()
    print(got)
    conn = lambda j: [x for x in cmds.listConnections(j + ".scaleX", source=True, destination=False) or []
                      if x.endswith("_globalScale_md")]
    check("each joint with Segment Scale Compensate gets the global scale (x its own)", conn(hip) and conn(knee))
    check("the one without it inherits from its parent: left alone (not scaled twice)", conn(ankle) == [])
    check("nothing left to fix", not SC.joints(g) and got["joints"] == 2 and not got["undone"])

# undone when something moved at rest
for j in (hip, knee):
    for a in "XYZ":
        for s_ in cmds.listConnections(j + ".scale" + a, source=True, destination=False, plugs=True) or []:
            cmds.disconnectAttr(s_, j + ".scale" + a)
shots = [{"Body": [0, 0, 0]}, {"Body": [0, 0, 1]}]
undone = []
with mock.patch.object(SC, "_skin_joints", return_value=SKIN), \
        mock.patch.object(SC, "_driver", return_value=ctrl), \
        mock.patch.object(SC, "scale_control", return_value=(g, g + ".globalScale")), \
        mock.patch.object(repair, "rest_points", side_effect=lambda: shots.pop(0)), \
        mock.patch.object(SC, "measure_joints", return_value=([], [])), \
        mock.patch.object(cmds, "undo", side_effect=lambda *a, **k: undone.append(1), create=True), \
        mock.patch.object(cmds, "undoInfo", side_effect=lambda *a, **k: "gusrigMakeScalable"
                          if k.get("undoName") else True):
    got = SC.make_scalable()
check("anything moved at rest: all of it undone, and it says where", undone == [1] and got["undone"].startswith("Body"))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
