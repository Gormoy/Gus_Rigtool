# 5.6.3: the Hare's scale cases - follicles reading World_ctrl.scaleX (which stays 1 under Global_ctrl) count as not
# scaling and get the global scale; Make Global > World > Local moves World_ctrl's scale-channel readers to Global;
# ribbon control groups cut off by a no-inherit group get it (own scale kept: -1 stays -1); a chain whose joints
# have Segment Scale Compensate but no inverseScale connection (the tongue) gets it once, not on every joint;
# IK stretch / pin / soft IK distances measured in world units are divided by it
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import scale_check as SC, world_levels, repair
from gus_rigtool.builder import publish
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
src = lambda p: cmds.listConnections(p, source=True, destination=False, plugs=True) or []

def ctrl(name, parent=None):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]

rig = cmds.createNode("transform", name="HARE_RIG")
ctrls_root = cmds.createNode("transform", name="Ctrls", parent=rig)
w = ctrl("World_ctrl", ctrls_root)
dnt = cmds.createNode("transform", name="DO_NOT_TOUCH", parent=rig)
rgrp = cmds.createNode("transform", name="Cape_Ribbon_ribbon_grp", parent=dnt)
cmds.setAttr(rgrp + ".inheritsTransform", 0)
fgrp = cmds.createNode("transform", name="Cape_Ribbon_follicles_grp", parent=rgrp)
fol = cmds.ls(cmds.createNode("transform", name="Cape_Ribbon_fol_01", parent=fgrp), long=True)[0]
cmds.createNode("follicle", name="Cape_Ribbon_fol_01Shape", parent=fol)
fj = cmds.createNode("joint", name="Cape_Ribbon_fol_01_jnt", parent=fol)
for a in "XYZ":
    cmds.connectAttr(w + ".scale" + a, fol + ".scale" + a)          # what the Ribbon tool made
cgrp = cmds.createNode("transform", name="Cape_Ribbon_ctrls_grp", parent=rgrp)
cmds.setAttr(cgrp + ".scaleX", -1)                                   # a mirrored one
rc = ctrl("Cape_Ribbon_fol_02_ctrl", cgrp)

# ---- Global > World > Local moves World_ctrl's scale-channel readers
fake_curves = mock.patch.multiple("gus_rigtool.core.curves", read_shape=lambda n: [], read_style=lambda n: {},
                                  create_curve_control=lambda name, c, s=None: _mk(name))
def _mk(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
with fake_curves, mock.patch.object(publish, "is_published", return_value=False), \
        mock.patch("gus_rigtool.core.shape_data.scale", side_effect=lambda d, f: d), \
        mock.patch("gus_rigtool.core.shape_data.circle_curve", side_effect=lambda r: []):
    lines = world_levels.plan(w)
    print(lines)
    check("the plan counts World_ctrl's scale-channel readers (the follicle: 3)", "3 thing(s) read it" in lines[1])
    got = world_levels.make(w)
check("made: the follicle now reads Global_ctrl.globalScale, not World_ctrl.scaleX",
      src(fol + ".scaleX") == ["Global_ctrl.globalScale"] and got["readers"] == 3)
g = world_levels.levels()["global"]

# ---- a scale input that doesn't scale doesn't count
for a in "XYZ":
    cmds.connectAttr(w.replace("World_ctrl", "World_ctrl") if False else world_levels.levels()["world"] + ".scale" + a,
                     fol + ".scale" + a, force=True)                 # back to the old wiring, to test the check
check("a follicle reading World_ctrl.scaleX (stays 1): counted as NOT scaling", not SC.scaled_by_rig(fol, g) and
      SC.follicles(g) == [fol])
SC.fix_follicles(SC.follicles(g), g + ".globalScale")
check("fixed: it reads the global scale", src(fol + ".scaleX") == ["Global_ctrl.globalScale"] and not SC.follicles(g))

# ---- control groups cut off by a no-inherit group
with mock.patch("gus_rigtool.core.on_top.controls", return_value=[rc]):
    groups = SC.control_groups(g)
check("the ribbon control group cut off by the no-inherit ribbon group: found (the top one)",
      [x.split("|")[-1] for x in groups] == ["Cape_Ribbon_ctrls_grp"])
md = SC.give_scale(groups[0], g + ".globalScale")
check("given the scale with its own kept (-1 stays -1): own x global", cmds.getAttr(md + ".input1X") == -1 and
      src(groups[0] + ".scaleX") == [md + ".outputX"] and src(md + ".input2X") == ["Global_ctrl.globalScale"])
check("...and now it counts as scaling", SC.scaled_by_rig(rc, g))

# ---- the tongue: Segment Scale Compensate on, inverseScale NOT connected
skel = cmds.createNode("transform", name="skeleton_grp", parent=dnt)
t1 = cmds.ls(cmds.createNode("joint", name="Tongue_01_jnt", parent=skel), long=True)[0]
t2 = cmds.ls(cmds.createNode("joint", name="Tongue_02_jnt", parent=t1), long=True)[0]
t3 = cmds.ls(cmds.createNode("joint", name="Tongue_03_jnt", parent=t2), long=True)[0]
for j in (t1, t2, t3):
    cmds.setAttr(j + ".segmentScaleCompensate", True)
    for a in "XYZ":
        cmds.setAttr("%s.scale%s" % (j, a), 1)
        cmds.connectAttr(g + ".globalScale", "%s.scale%s" % (j, a))
twice = SC.scaled_twice(g)
check("no inverseScale connection: Segment Scale Compensate does nothing - joints 02 and 03 get it twice",
      sorted(x.split("|")[-1] for x in twice) == ["Tongue_02_jnt", "Tongue_03_jnt"])
SC.fix_twice(twice)
check("fixed: only the first one gets the scale, the others inherit it (scale 1)",
      src(t1 + ".scaleX") and not src(t2 + ".scaleX") and not src(t3 + ".scaleX") and cmds.getAttr(t3 + ".scaleX") == 1
      and not SC.scaled_twice(g))
cmds.connectAttr(t1 + ".scale", t2 + ".inverseScale")
cmds.connectAttr(g + ".globalScale", t2 + ".scaleX", force=True)
check("with inverseScale connected the parent's scale IS cancelled - not 'twice'", t2 not in SC.scaled_twice(g))

# ---- IK limbs: distances in world units
rest = cmds.createNode("multDoubleLinear", name="L_ankle_stretchRest")
cmds.setAttr(rest + ".input1", 40.0); cmds.setAttr(rest + ".input2", 1.0)
pin = cmds.createNode("multiplyDivide", name="L_ankle_stretchPinLocal0")
cmds.setAttr(pin + ".operation", 2); cmds.setAttr(pin + ".input2X", 1.0)
dist = cmds.createNode("distanceBetween", name="L_ankle_softDist")
over = cmds.createNode("plusMinusAverage", name="L_ankle_softOver")
near = cmds.createNode("condition", name="L_ankle_softNear")
cmds.connectAttr(dist + ".distance", over + ".input1D[0]")
cmds.connectAttr(dist + ".distance", near + ".firstTerm")
found = SC.world_measures(g + ".globalScale")
print(found)
check("found: the stretch rest length, the pin length, the soft IK distance",
      sorted(k for k, _n in found) == ["pin", "rest", "soft"])
SC.fix_world_measures(found, g + ".globalScale")
scaled = [n for n in cmds.ls(type="multiplyDivide") if "Scaled_globalScale" in n]
check("fixed: rest and pin x the scale; the soft IK distance divided by it before everything that read it",
      src(rest + ".input2") == ["Global_ctrl.globalScale"] and src(pin + ".input2X") == ["Global_ctrl.globalScale"]
      and scaled and src(over + ".input1D[0]") == [scaled[0] + ".outputX"] and
      src(near + ".firstTerm") == [scaled[0] + ".outputX"] and not SC.world_measures(g + ".globalScale"))

# ---- Make the rig scale: all of it in one go (measured pass mocked - the test Maya doesn't evaluate)
for a in "XYZ":
    cmds.connectAttr(world_levels.levels()["world"] + ".scale" + a, fol + ".scale" + a, force=True)
with mock.patch.object(SC, "measure_joints", return_value=([], [])), mock.patch.object(repair, "rest_points", return_value={}), \
        mock.patch("gus_rigtool.core.on_top.controls", return_value=[rc]):
    got = SC.make_scalable()
print(got)
check("Make the rig scale: the follicle re-wired; nothing left", got["follicles"] == 1 and not SC.follicles(g) and
      not SC.scaled_twice(g) and not got["undone"])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
