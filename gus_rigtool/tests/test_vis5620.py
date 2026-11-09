# 5.6.20: visibility switches - only the ticked ones made; on a control of yours instead of the gear; the gear open
# while rigging (Publish locks it); one of the tool's switches removed when picked in the Channel Box (what it hid
# shown, Geo_Display back to Normal); Remove all: everything shown, the gear deleted (your control kept), the face's
# switches gone, the head squash's switch left on
exec(open("fakemaya.py").read())
from gus_rigtool.core import vis_switch as VS
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def mk(name, parent=None):
    c = cmds.createNode("transform", name=name, parent=parent) if parent else cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]
head = mk("Head_ctrl"); brow = mk("L_Brow_ctrl", head); arm = mk("L_arm_ctrl"); mine = mk("My_gear_ctrl")
geo = cmds.createNode("transform", name="geo_grp")
ctrls = [head, brow, arm, mine]
with mock.patch("gus_rigtool.core.on_top.controls", return_value=ctrls), \
        mock.patch("gus_rigtool.core.on_top.is_face", side_effect=lambda c: "Brow" in c):
    got = VS.make(None, which=["Body_Ctrls", "Face_Ctrls"], on="My_gear_ctrl")
sw = VS.find()
check("on your control; only Body_Ctrls and Face_Ctrls (no Joints / Geometry / Geo_Display)",
      sw.endswith("My_gear_ctrl") and cmds.attributeQuery("Body_Ctrls", node=sw, exists=True) and
      not cmds.attributeQuery("Geometry", node=sw, exists=True) and not cmds.attributeQuery("Geo_Display", node=sw,
                                                                                            exists=True))
check("your control isn't the tool's gear (Remove all keeps it)", not VS.made_by_tool(sw))
src = lambda x: (cmds.listConnections(x + "|" + x.split("|")[-1] + "Shape.visibility", source=True,
                                      destination=False) or [""])[0].split("|")[-1]
check("brow on Face_Ctrls, arm on Body_Ctrls", src(brow) == "My_gear_ctrl" and src(arm) == "My_gear_ctrl")
cmds.setAttr(sw + ".Face_Ctrls", 0)
done = VS.remove_hand_switches([sw], only=["Face_Ctrls"])
print(done)
check("one of the tool's switches removed when picked (Face_Ctrls): the brow shown again, Body_Ctrls stays",
      done and not cmds.attributeQuery("Face_Ctrls", node=sw, exists=True) and src(brow) == "" and
      cmds.attributeQuery("Body_Ctrls", node=sw, exists=True))
check("not picked: the tool's switches are never offered", not VS.hand_switches(sw))
out = VS.remove_all()
check("Remove all: your control kept, its switches gone, the arm shown",
      not out["gear_deleted"] and cmds.objExists("My_gear_ctrl") and
      not cmds.attributeQuery("Body_Ctrls", node=sw, exists=True) and src(arm) == "" and not VS.find())
src2 = open("../core/vis_switch.py").read()
pub = open("../builder/publish.py").read()
check("the gear: open while you rig (lock=()), marked as the tool's; Publish locks it",
      'lock=())' in src2 and "MADE" in src2 and "vis_switch.made_by_tool(sw)" in pub)
print("%d/%d passed" % (sum(ok), len(ok)))
