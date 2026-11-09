# 5.0.1: Publish / Unpublish / Deliver a rig made by hand (no Gus_Rigtool build): its top group and controls are
# found, only the groups above the controls are locked, joints hidden (not a chain holding a control), sets
# made, and Unpublish puts every channel / visibility / set back exactly
import os, sys, tempfile
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
A.profile = lambda ns=None: {}
from gus_rigtool.builder import publish
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def curve(name, parent):
    t = cmds.createNode("transform", name=name, parent=parent)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
top = cmds.createNode("transform", name="Mech_Rig")
ctrls_grp = cmds.createNode("transform", name="Mech_controls", parent=top)
off = cmds.createNode("transform", name="arm_offset", parent=ctrls_grp)
arm = curve("arm_CON", off)
chest = curve("chest", ctrls_grp)                         # hand-made: no suffix
skel = cmds.createNode("joint", name="root_jnt", parent=top)
j2 = cmds.createNode("joint", name="arm_jnt", parent=skel)
held = cmds.createNode("joint", name="prop_jnt", parent=top)     # a chain with a control under it
prop = curve("prop_ctrl", held)
extras = cmds.createNode("transform", name="noTouch", parent=top); cmds.setAttr(extras + ".visibility", 0)
curve("spline_crv", extras)                               # hidden for good: not a control
other = cmds.createNode("transform", name="rig_nodes_by_hand", parent=top)   # not above a control: untouched
cmds.setAttr(chest + ".rotateX", 15.0)
ctrls = publish.rig_controls()
names_ = sorted(c.split("|")[-1] for c in ctrls)
check("found: the rig's top group and its controls", publish.rig_group().endswith("Mech_Rig") and
      names_ == ["arm_CON", "chest", "prop_ctrl"] and publish.is_hand_made())
def state():
    out = {}
    for n in cmds.ls(top, dag=True, long=True) or []:
        if cmds.nodeType(n) in ("transform", "joint"):
            for a in ("translateX", "rotateY", "scaleZ", "visibility"):
                p = n + "." + a
                out[p] = (cmds.getAttr(p, lock=True), cmds.getAttr(p, keyable=True), cmds.getAttr(p))
    return out
before = state()
done = publish.publish()
print("   ", done)
L = lambda n, a: cmds.getAttr(cmds.ls(n, long=True)[0] + "." + a, lock=True)
check("the groups above the controls are locked (offset, controls group, top)",
      L("arm_offset", "translateX") and L("Mech_controls", "rotateY") and L("Mech_Rig", "scaleZ"))
check("other nodes untouched, controls still free", not L("rig_nodes_by_hand", "translateX") and
      not L("arm_CON", "translateX"))
check("the skeleton is hidden, not a chain holding a control",
      cmds.getAttr(skel + ".visibility") == 0 and cmds.getAttr(held + ".visibility") != 0)
check("default pose remembered on every control", all(cmds.attributeQuery("gusDefaultPose", node=c, exists=True)
                                                       for c in ctrls))
check("sets: every control", sorted(x.split("|")[-1] for x in cmds.sets("rig_ctrls_set", query=True)) == names_)
check("published (state kept on the top group)", publish.is_published())
publish.unpublish()
after = state()
diff = [p for p in before if before[p] != after.get(p)]
check("Unpublish: every channel and visibility exactly as before", not diff)
for p in diff[:5]:
    print("   ", p, before[p], after.get(p))
check("Unpublish: the sets are gone", not cmds.objExists("rig_ctrls_set"))
print("ALL OK" if all(ok) else "SOME FAILED")
