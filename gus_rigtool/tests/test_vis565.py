# 5.6.5: visibility switches - a control above the head; controls sorted Body / Face / Secondary by name, each
# control's curve shapes (not its group) on its switch; shapes driven by something else left alone; Joints /
# Geometry on skeleton_grp / geo_grp drawing overrides; Geo_Display; a control moved to another switch; the Checker
# finds controls on no switch and fixes them. Eye aim: two existing eye joints aimed at L / R_Eye_ctrl under the
# rig's own Eyes_ctrl, the joints themselves unchanged
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import vis_switch as VS, face_kit
from gus_rigtool.tools import checker
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
src = lambda p: cmds.listConnections(p, source=True, destination=False, plugs=True) or []

def _mk(name, parent=None):
    t = cmds.createNode("transform", name=name, parent=parent) if parent else cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]

rig = cmds.createNode("transform", name="HARE_RIG")
cg = cmds.createNode("transform", name="controls_grp", parent=rig)
names_ = ["Global_ctrl", "COG_ctrl", "Head_ctrl", "L_Brow_ctrl", "Mouth_fol_14_ctrl", "Cape_Ribbon_fol_04_ctrl",
          "L_Sleeve_fol_05_ctrl", "L_wrist_IK_ctrl", "Tail_00_ctrl"]
c = dict((n, _mk(n, cg)) for n in names_)
cmds.connectAttr(c["COG_ctrl"] + ".translateX", c["L_wrist_IK_ctrl"].split("|")[-1] + "Shape.visibility")  # driven
skel = cmds.createNode("transform", name="skeleton_grp", parent=rig)
geo = cmds.createNode("transform", name="geo_grp", parent=rig)
for a, v in (("overrideEnabled", 0), ("overrideVisibility", 1), ("overrideDisplayType", 0)):
    for g in (skel, geo):
        if not cmds.attributeQuery(a, node=g, exists=True):
            cmds.addAttr(g, longName=a, attributeType="long", defaultValue=v)

check("sorted by name", [VS.kind(c[n]) for n in ("COG_ctrl", "L_Brow_ctrl", "Mouth_fol_14_ctrl",
                                                  "Cape_Ribbon_fol_04_ctrl", "L_Sleeve_fol_05_ctrl", "Tail_00_ctrl")]
      == ["Body_Ctrls", "Face_Ctrls", "Face_Ctrls", "Secondary_Ctrls", "Secondary_Ctrls", "Body_Ctrls"])
lines = VS.plan(c["Head_ctrl"])
print("\n".join(lines))
check("the plan: a new control above Head_ctrl, the counts", "above Head_ctrl" in lines[0] and
      lines[1].startswith("Body_Ctrls: 4"))
with mock.patch("gus_rigtool.core.curves.create_curve_control", side_effect=lambda name, *a, **k: _mk(name)), \
        mock.patch("gus_rigtool.core.curves.read_shape", return_value=[]), \
        mock.patch("gus_rigtool.core.curves.read_style", return_value={}), \
        mock.patch.object(cmds, "exactWorldBoundingBox", return_value=[-10, 150, -10, 10, 180, 10], create=True):
    got = VS.make(c["Head_ctrl"])
print(got)
sw = got["control"]
check("Visibility_ctrl made, under the head (follows it)", sw.split("|")[-1] == "Visibility_ctrl" and
      "|Head_ctrl|" in sw and VS.find() == sw)
check("its switches", all(cmds.attributeQuery(a, node=sw, exists=True) for a in VS.SWITCHES + (VS.DISPLAY,)))
check("Global_ctrl left out; the counts (Body: COG, Head, Tail; Face 2; Secondary 2)",
      got["controls"] == {"Body_Ctrls": 3, "Face_Ctrls": 2, "Secondary_Ctrls": 2})
check("the shape is switched, not the control or its group",
      src("L_Brow_ctrlShape.visibility") == ["Visibility_ctrl.Face_Ctrls"] and not src(c["L_Brow_ctrl"] +
                                                                                      ".visibility"))
check("a shape driven already (IK / FK) left alone, and said",
      src("L_wrist_IK_ctrlShape.visibility") == ["COG_ctrl.translateX"] and
      [x.split("|")[-1] for x in got["skipped"]] == ["L_wrist_IK_ctrl"])
check("Joints / Geometry / Geo_Display on the groups' drawing overrides",
      src(skel + ".overrideVisibility") == ["Visibility_ctrl.Joints"] and
      src(geo + ".overrideVisibility") == ["Visibility_ctrl.Geometry"] and
      src(geo + ".overrideDisplayType") == ["Visibility_ctrl.Geo_Display"] and cmds.getAttr(geo + ".overrideEnabled"))
moved, _sk = VS.assign([c["Tail_00_ctrl"]], "Secondary_Ctrls")
check("moved to another switch", moved == 1 and VS.switch_of(c["Tail_00_ctrl"]) == "Secondary_Ctrls")
check("the switch control itself is on no switch", VS.switch_of(sw) is None)
new = _mk("R_Brow_ctrl", cg)
check("Checker: a control made after the switches is on none", [x.split("|")[-1] for x in
                                                                 checker.find_ctrl_no_switch([])] == ["R_Brow_ctrl"])
checker.fix_ctrl_no_switch(checker.find_ctrl_no_switch([]))
check("...fixed: on Face", VS.switch_of(new) == "Face_Ctrls" and not checker.find_ctrl_no_switch([]))
check("made again: nothing doubled, nothing re-sorted", VS.make()["controls"] == {"Body_Ctrls": 0, "Face_Ctrls": 0,
                                                                                    "Secondary_Ctrls": 0}
      and VS.switch_of(c["Tail_00_ctrl"]) == "Secondary_Ctrls")

# ---- eye aim on existing joints
head_j = cmds.createNode("joint", name="Head_jnt")
eyes = cmds.createNode("transform", name="Eyes_ctrl", parent=cg)
ej = {}
for side, x in (("L", 3.0), ("R", -3.0)):
    j = cmds.createNode("joint", name="Eye_%s" % ("Left" if side == "L" else "Right"), parent=head_j)
    cmds.setAttr(j + ".translate", x, 170, 5, type="double3")
    ej[side] = cmds.ls(j, long=True)[0]
aims = []
real_aim = getattr(cmds, "aimConstraint", None)
def aim(target, j, **k):
    aims.append((target.split("|")[-1], j.split("|")[-1], k.get("maintainOffset")))
    return ["a"]
with mock.patch("gus_rigtool.core.curves.create_curve_control", side_effect=lambda name, *a, **k: _mk(name)), \
        mock.patch("gus_rigtool.core.curves.read_shape", return_value=[]), \
        mock.patch("gus_rigtool.core.curves.read_style", return_value={}), \
        mock.patch.object(face_kit, "_pos", side_effect=lambda n: [3.0, 170, 5] if "Left" in n else [-3.0, 170, 5]), \
        mock.patch.object(cmds, "aimConstraint", side_effect=aim, create=True):
    made = face_kit.aim_eyes([ej["R"], ej["L"]])
print(aims, made)
check("left = +X: Eye_Left aimed at L_Eye_ctrl, Eye_Right at R_Eye_ctrl, keeping their rest",
      sorted(aims) == [("L_Eye_ctrl", "Eye_Left", True), ("R_Eye_ctrl", "Eye_Right", True)])
check("the eye controls under the rig's own Eyes_ctrl", all("|Eyes_ctrl|" in made[s] for s in "LR"))
check("the joints stay where they are, under the head", all(cmds.listRelatives(ej[s], parent=True)[0] == "Head_jnt"
                                                             for s in "LR"))
try:
    face_kit.aim_eyes([ej["L"]])
    check("one joint: refused", False)
except RuntimeError as e:
    check("one joint: refused (%s)" % e, True)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
