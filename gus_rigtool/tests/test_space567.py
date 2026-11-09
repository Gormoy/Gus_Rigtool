# 5.6.7: space switches on the builder's locked offset groups - unlocked to move, locked again (the Hare's arm
# jumped 9.33: Maya kept the locked values, measured from the old parent); a switch that moves the control is taken
# off again; a target inside the control's own hierarchy is refused (the Hare turned 90); standard spaces from the
# limbs' settings controls; Check this scene: every space at rest and x2, the head turn test, Auto Key, the default
# material; visibility switches let go of display layers
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import spaces, space_check, vis_switch as VS
from gus_rigtool.tools import checker
from gus_rigtool import scene_check
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
CH = ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz")
def ctrl(name, parent=None, pos=(0, 0, 0), lock_offset=False):
    off = cmds.createNode("transform", name=name.replace("_ctrl", "_offset"), parent=parent) if parent else \
        cmds.createNode("transform", name=name.replace("_ctrl", "_offset"))
    cmds.xform(off, worldSpace=True, translation=pos)
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    if lock_offset:
        for a in CH:
            cmds.setAttr(off + "." + a, lock=True)
    return cmds.ls(c, long=True)[0]

w = ctrl("World_ctrl"); cog = ctrl("COG_ctrl", w, (0, 100, 0)); waist = ctrl("Waist_ctrl", cog, (0, 95, 0))
chest = ctrl("Chest_ctrl", cog, (0, 140, 0)); clav = ctrl("L_clavicle_FK_ctrl", chest, (5, 150, 0))
hum = ctrl("L_humerus_FK_ctrl", clav, (14.5, 150, 0), lock_offset=True)
ankle_grp = cmds.createNode("transform", name="L_ankle_ik_grp", parent=w)
ank = ctrl("L_ankle_IK_ctrl", ankle_grp, (7.5, 5, -6.8), lock_offset=True)
pv = ctrl("L_tibia_PV_ctrl", ankle_grp, (7.5, 50, 18.5), lock_offset=True)
wrist = ctrl("L_wrist_IK_ctrl", w, (60, 150, 0)); rpv = ctrl("L_radius_PV_ctrl", w, (35, 150, -20), lock_offset=True)

before = cmds.xform(hum, query=True, worldSpace=True, matrix=True)
grp = spaces.make(hum, [("Chest", "Chest_ctrl"), ("COG", "COG_ctrl"), ("World", "World_ctrl")], "orient")
off = cmds.ls("L_humerus_FK_offset", long=True)[0]
check("made on a locked offset: the offset under the space group", off.startswith(grp + "|"))
check("its channels locked again", all(cmds.getAttr(off + "." + a, lock=True) for a in CH))
check("nothing moved", max(abs(a - b) for a, b in zip(before, cmds.xform("L_humerus_FK_ctrl", query=True,
                                                                           worldSpace=True, matrix=True))) < 1e-6)
spaces.remove("L_humerus_FK_ctrl")
off = cmds.ls("L_humerus_FK_offset", long=True)[0]
check("removed: back under the clavicle, still locked", "|L_clavicle_FK_ctrl|L_humerus_FK_offset" in off and
      all(cmds.getAttr(off + "." + a, lock=True) for a in CH))

# a switch that moves the control: taken off again
real_xf = cmds.xform
calls = {"n": 0}
def xf(*a, **k):
    got = real_xf(*a, **k)
    if k.get("query") and k.get("matrix") and a and str(a[0]).endswith("L_tibia_PV_ctrl"):
        calls["n"] += 1
        if calls["n"] == 2:
            got = list(got); got[12] += 9.33
    return got
with mock.patch.object(cmds, "xform", side_effect=xf):
    try:
        spaces.make("L_tibia_PV_ctrl", [("Foot", "L_ankle_IK_ctrl"), ("World", "World_ctrl")])
        check("moved: refused", False)
    except RuntimeError as e:
        print(e)
        check("moved by the switch: taken off again, said so", "moved" in str(e) and not spaces.read("L_tibia_PV_ctrl")
              and not cmds.ls("L_tibia_PV_space_grp"))

# a loop: the 'control' has the targets under it
try:
    spaces.make("World_ctrl", [("ankle", "L_ankle_IK_ctrl"), ("COG", "COG_ctrl")])
    check("loop: refused", False)
except RuntimeError as e:
    print(e)
    check("a target inside the control's own hierarchy: refused, says why", "inside" in str(e) and
          not spaces.read("World_ctrl"))

# standard spaces from the limbs' settings controls
for side_settings, ik, pvc, fk in (("L_leg_settings_ctrl", "L_ankle_IK_ctrl", "L_tibia_PV_ctrl", ""),
                                   ("L_arm_settings_ctrl", "L_wrist_IK_ctrl", "L_radius_PV_ctrl",
                                    "L_clavicle_FK_ctrl L_humerus_FK_ctrl L_radius_FK_ctrl")):
    st = ctrl(side_settings, w)
    for k, v in (("gusIkCtrl", ik), ("gusPvCtrl", pvc), ("gusFkCtrls", fk)):
        cmds.addAttr(st, longName=k, dataType="string"); cmds.setAttr(st + "." + k, v, type="string")
cmds.addAttr(wrist, longName="space", attributeType="enum", enumName="COG:Chest:root")
with mock.patch("gus_rigtool.core.utils.nodes_with_attr", return_value=sorted(
        cmds.ls("L_leg_settings_ctrl", "L_arm_settings_ctrl", long=True))):
    plan = spaces.standard_plan()
    shown = [(c.split("|")[-1], [lb for lb, _n in t], k) for c, t, k in plan]
    print(shown)
    check("the plan: IK foot World/COG/Waist, knee PV Foot/World/COG, arm PV Chest/World/Hand, FK arm orient "
          "Chest/COG/World; the IK hand (has a space already) and the clavicle left out", sorted(shown) == sorted([
              ("L_ankle_IK_ctrl", ["World", "COG", "Waist"], "parent"),
              ("L_tibia_PV_ctrl", ["Foot", "World", "COG"], "parent"),
              ("L_radius_PV_ctrl", ["Chest", "World", "Hand"], "parent"),
              ("L_humerus_FK_ctrl", ["Chest", "COG", "World"], "orient")]))
    made, failed = spaces.standard(plan)
    print(made, failed)
    check("all four made", len(made) == 4 and not failed)
    check("made again: nothing left to make", spaces.standard_plan() == [])

# Check this scene: spaces at rest / x2, head turn
sw = space_check.switches()
check("the space menus found (the four made + the IK hand's own)", len(sw) == 5)
with mock.patch("gus_rigtool.core.scale_check.scale_control", return_value=(None, None)):
    r = space_check.run()
check("each space at rest: no jumps", r["switches"] == 5 and not r["jumps"])
head = ctrl("Head_ctrl", chest, (0, 170, 0))
eye = cmds.createNode("joint", name="L_Eyeball_jnt", parent=head)
cmds.connectAttr(head + ".rotateY", eye + ".rotateY")          # the head's turn given twice
from gus_rigtool.core import world_turn as WT
def settle():                                                  # the fake doesn't evaluate: pass it on by hand
    cmds.setAttr(eye + ".rotateY", cmds.getAttr(head + ".rotateY"))
with mock.patch.object(WT, "_settle", side_effect=settle):
    r = space_check.turn_test()
print(r)
check("the head turned 30: the eyeball turning 60 found", [(n.split("|")[-1], round(d)) for n, d in r["twice"]] ==
      [("L_Eyeball_jnt", 60)] and cmds.getAttr(head + ".rotateY") == 0)

# Auto Key note, default material
rep = scene_check.Report("t")
with mock.patch.object(cmds, "autoKeyframe", return_value=True, create=True):
    scene_check._auto_key(rep)
check("Auto Key on: noted", "Auto Key is on" in str(rep.__dict__))
cmds.createNode("shadingEngine", name="initialShadingGroup")
m = cmds.createNode("transform", name="Bandage_L")
cmds.createNode("mesh", name="Bandage_LShape", parent=m)
with mock.patch.object(cmds, "sets", side_effect=lambda *a, **k: ["Bandage_LShape"] if k.get("query") else None,
                       create=True):
    got = checker.find_default_material([])
check("Checker: the bandage on Maya's default material", [x.split("|")[-1] for x in got] == ["Bandage_L"])

# visibility switches let go of display layers
sw_c = ctrl("Visibility_ctrl", head)
cmds.addAttr(sw_c, longName=VS.MARK, attributeType="bool")
for a in VS.SWITCHES:
    cmds.addAttr(sw_c, longName=a, attributeType="bool")
cmds.addAttr(sw_c, longName=VS.DISPLAY, attributeType="enum", enumName=VS.DISPLAY_TYPES)
lay = cmds.createNode("displayLayer", name="Clothes_geo")
cmds.connectAttr(sw_c + "." + VS.DISPLAY, lay + ".displayType")
with mock.patch.object(VS, "find", return_value=sw_c):
    let = VS.release_layers()
check("Clothes_geo let go (5.6.5 had taken it over)", let == ["Clothes_geo"] and
      not cmds.listConnections(lay + ".displayType", source=True, destination=False))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
