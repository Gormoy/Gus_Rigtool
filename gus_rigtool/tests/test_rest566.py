# 5.6.6: keep the pose on a control whose group is driven by a constraint (the Hare's Eyes_ctrl): the constraint
# node under the group doesn't count as 'other things'; a new <control>_rest group above the control takes the
# pose - nothing moves; ROM Remove finds controls whose full path changed (groups went in above them) and keeps
# its record when it finds none
import sys, json
exec(open("fakemaya.py").read())
from gus_rigtool.core import zero_pose, cloth
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

top = cmds.createNode("transform", name="controls_grp")
head = cmds.createNode("transform", name="Head_ctrl")
cmds.xform(head, worldSpace=True, translation=[0, 150, 0])
off = cmds.createNode("transform", name="Eyes_ctrl_offset", parent=top)
cmds.xform(off, worldSpace=True, translation=[0, 160, 20])
e = cmds.createNode("transform", name="Eyes_ctrl", parent=off)
cmds.createNode("nurbsCurve", name="Eyes_ctrlShape", parent=e)
cmds.parentConstraint(head, off, maintainOffset=True)
e = cmds.ls(e, long=True)[0]
check("the constraint node is not 'other things'; the driven group is the reason",
      zero_pose.blocker(e).endswith("is driven"))
cmds.setAttr(e + ".translateY", -7.1); cmds.setAttr(e + ".rotateZ", 22.7)
for a in "XYZ":
    cmds.setAttr(e + ".scale" + a, 9.9)
before = cmds.xform(e, query=True, worldSpace=True, matrix=True)
done, skipped = zero_pose.apply([e])
print(done, skipped)
after = cmds.xform(done[0], query=True, worldSpace=True, matrix=True) if done else None
check("done, nothing skipped: under a new Eyes_ctrl_rest, under the offset",
      not skipped and done and done[0].endswith("|Eyes_ctrl_offset|Eyes_ctrl_rest|Eyes_ctrl"))
check("the control reads 0 / 1", done and cmds.getAttr(done[0] + ".translateY") == 0 and
      cmds.getAttr(done[0] + ".rotateZ") == 0 and abs(cmds.getAttr(done[0] + ".scaleX") - 1) < 1e-9)
check("nothing moved", after and max(abs(a - b) for a, b in zip(before, after)) < 1e-6)
check("the offset is still the constraint's (untouched)", cmds.listConnections(off + ".translate", source=True,
                                                                                destination=False))

# ---- ROM Remove: the saved full path is gone (Global > World > Local went in above)
c = cmds.createNode("transform", name="L_Shoulder_FK_ctrl", parent=top)
cmds.setAttr(c + ".rotateZ", 5)
node = cmds.createNode("network", name="gusROM")
cmds.addAttr(node, longName="gusRomData", dataType="string")
cmds.setAttr(node + ".gusRomData", json.dumps({"start": 1, "end": 40, "plugs": ["|Ctrls|old|L_Shoulder_FK_ctrl.rotateZ"],
                                               "was": {"|Ctrls|old|L_Shoulder_FK_ctrl.rotateZ": 0.0}}), type="string")
cut = []
with mock.patch.object(cmds, "cutKey", side_effect=lambda p, **k: cut.append(p), create=True):
    n = cloth.remove_rom()
check("found by name: its keys cut, its value back, the record gone", n == 1 and cut and
      cut[0].endswith("L_Shoulder_FK_ctrl.rotateZ") and cmds.getAttr(c + ".rotateZ") == 0 and
      not cmds.objExists("gusROM"))
node = cmds.createNode("network", name="gusROM")
cmds.addAttr(node, longName="gusRomData", dataType="string")
cmds.setAttr(node + ".gusRomData", json.dumps({"start": 1, "end": 40, "plugs": ["|x|Gone_ctrl.rotateX"], "was": {}}),
             type="string")
try:
    cloth.remove_rom()
    check("none found: refused", False)
except RuntimeError as err:
    check("none found: refused, says so, the record kept (%s)" % str(err)[:40], cmds.objExists("gusROM"))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
