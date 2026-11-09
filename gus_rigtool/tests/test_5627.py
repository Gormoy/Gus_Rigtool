# 5.6.27: safe fixes - safe mode (rest, x2, real animation), the mirror table, ribbons marked not symmetric,
# Make the right side mirror the left refusing held groups, Delta Mush scale, hidden meshes in deformer chains,
# missing component tags, stray keys, the picker saved in the rig, Speed / Ready for animators
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import safe, repair, ribbon
from gus_rigtool.core import rigspeed as speed
from gus_rigtool import scene_check
ok = []
def reset():
    S.__init__()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- safe mode: comparing looks
a = {"rest": {"mesh": {"m": [0, 0, 0, 1, 1, 1]}, "ctrl": {"c": [0, 0, 0]}}}
b = {"rest": {"mesh": {"m": [0, 0, 0, 1, 1, 1.5]}, "ctrl": {"c": [0, 0, 0]}}}
bad = safe.compare(a, b)
check("safe mode: a vertex off by 0.5 is found (state, mesh, how many, most)", bad == [("rest", "m", 1, 0.5)])
check("safe mode: the same look twice: nothing moved", safe.compare(a, a) == [] and safe.describe([]) == "nothing moved")
check("safe mode: a state seen only once isn't compared", safe.compare(a, {"scale": a["rest"]}) == [])
check("safe mode: under a hair (0.0005) counts as still",
      safe.compare(a, {"rest": {"mesh": {"m": [0, 0, 0, 1, 1, 1.0005]}}}) == [])
check("safe mode: what moved, said in words", "rest m: 1 point(s) up to 0.5" in safe.describe(bad))
looks = iter([a, b])
undo = mock.MagicMock()
with mock.patch.object(safe, "snapshot", lambda *x, **k: next(looks)), \
        mock.patch.object(safe, "anim_frames", lambda *x: []), mock.patch.object(cmds, "undo", undo, create=True), \
        mock.patch.object(cmds, "undoInfo", mock.MagicMock(), create=True):
    kept, why = safe.run(lambda: "done")
check("safe mode: a fix that moved something is undone and says what moved",
      not kept and undo.called and why.startswith("undone - it moved"))
looks = iter([a, a])
undo = mock.MagicMock()
with mock.patch.object(safe, "snapshot", lambda *x, **k: next(looks)), \
        mock.patch.object(safe, "anim_frames", lambda *x: []), mock.patch.object(cmds, "undo", undo, create=True), \
        mock.patch.object(cmds, "undoInfo", mock.MagicMock(), create=True):
    kept, why = safe.run(lambda: "done")
check("safe mode: a fix that moved nothing is kept", kept and why == "done" and not undo.called)
check("Repair: fixes meant to move the mesh skip safe mode", repair.safe_states("skin_normalize") == ())
check("Repair: scale fixes compare rest + animation, not the x2 look",
      repair.safe_states("deltamush_scale") == ("rest", "anim") and repair.safe_states("scale_joints") == ("rest", "anim"))
check("Repair: every other fix: rest, x2 and real animation", repair.safe_states("speed_chain") == ("rest", "scale", "anim"))

# --- component tags
check("tag expression names", speed._expr_names("Head_squash") == ["Head_squash"] and
      speed._expr_names("a + b*") == ["a", "b"])
reset()
createNode("skinCluster", name="Head_squash")
with mock.patch.object(speed, "_indices", lambda d: [10, 3]), \
        mock.patch.object(speed, "_tags_on", lambda p: {"Head_squash_3"}):
    setAttr("Head_squash.input[10].componentTagExpression", "Head_squash")
    setAttr("Head_squash.input[3].componentTagExpression", "Head_squash_3")
    tp = speed.tag_problems()
    check("the Hare's Head_squash: input 10 asks for 'Head_squash' that isn't there, input 3 is fine",
          tp == [("Head_squash", 10, "Head_squash", ["Head_squash"])])
    speed.fix_tags(tp)
    check("fix: that input takes the whole mesh (empty expression), the good one is left",
          getAttr("Head_squash.input[10].componentTagExpression") == "" and
          getAttr("Head_squash.input[3].componentTagExpression") == "Head_squash_3")
with mock.patch.object(speed, "_indices", lambda d: [0]), mock.patch.object(speed, "_tags_on", lambda p: None):
    setAttr("Head_squash.input[0].componentTagExpression", "x")
    check("when Maya can't say which tags a mesh has: nothing is reported", speed.tag_problems() == [])

# --- a hidden mesh in the middle of a chain (skin -> Hare_BodyShapeDeformed -> Head_squash)
reset()
createNode("skinCluster", name="skinCluster10")
createNode("skinCluster", name="squash")
createNode("mesh", name="Hare_BodyShapeDeformed")
setAttr("Hare_BodyShapeDeformed.intermediateObject", True)
connectAttr("skinCluster10.outputGeometry[0]", "Hare_BodyShapeDeformed.inMesh")
connectAttr("Hare_BodyShapeDeformed.worldMesh[0]", "squash.input[3].inputGeometry")
with mock.patch.object(speed, "_indices", lambda d: [3] if d == "squash" else []):
    br = speed.chain_breaks()
    check("found: skinCluster10 -> a hidden mesh -> the squash", br == [("skinCluster10.outputGeometry[0]",
                                                                      "squash.input[3].inputGeometry",
                                                                      "Hare_BodyShapeDeformed")])
    speed.fix_chain_breaks(br)
    check("fixed: the skin feeds the squash straight, the hidden mesh is gone",
          listConnections("squash.input[3].inputGeometry", source=True, destination=False, plugs=True) ==
          ["skinCluster10.outputGeometry[0]"] and not objExists("Hare_BodyShapeDeformed"))
reset()
createNode("skinCluster", name="s1")
createNode("skinCluster", name="s2")
createNode("mesh", name="mid")
createNode("mesh", name="other")
setAttr("mid.intermediateObject", True)
connectAttr("s1.outputGeometry[0]", "mid.inMesh")
connectAttr("mid.worldMesh[0]", "s2.input[0].inputGeometry")
connectAttr("mid.outMesh", "other.inMesh")
with mock.patch.object(speed, "_indices", lambda d: [0] if d == "s2" else []):
    check("a hidden mesh that also feeds something else is left alone", speed.chain_breaks() == [])
reset()
createNode("skinCluster", name="s1")
createNode("mesh", name="vis")
connectAttr("vis.worldMesh[0]", "s1.input[0].inputGeometry")
with mock.patch.object(speed, "_indices", lambda d: [0]):
    check("a visible mesh feeding a deformer isn't a break", speed.chain_breaks() == [])

# --- Delta Mush and the scale
reset()
createNode("transform", name="Global_ctrl")
addAttr("Global_ctrl", longName="globalScale", attributeType="double", defaultValue=1.0)
for n, v in (("Belt_Ring_deltaMush", 1.0), ("Pants_deltaMush", 0.5)):
    createNode("deltaMush", name=n)
    setAttr(n + ".displacement", v)
with mock.patch.object(safe, "scale_plug", lambda: "Global_ctrl.globalScale"):
    plug, dms = speed.unscaled_delta_mush()
    check("Delta Mush with displacement not tied to the scale", plug == "Global_ctrl.globalScale" and
          sorted(dms) == ["Belt_Ring_deltaMush", "Pants_deltaMush"])
    speed.fix_delta_mush(plug, dms)
    src = listConnections("Pants_deltaMush.displacement", source=True, destination=False)
    check("the belt: displacement = the global scale; Pants (0.5): through a multiply that keeps its 0.5",
          listConnections("Belt_Ring_deltaMush.displacement", source=True, destination=False, plugs=True) ==
          ["Global_ctrl.globalScale"] and src and nodeType(src[0]) == "multDoubleLinear" and
          getAttr(src[0] + ".input2") == 0.5)
    check("after the fix nothing is reported", speed.unscaled_delta_mush()[1] == [])

# --- stray keys (pairBlend)
reset()
createNode("transform", name="L_Pupil_ctrl")
createNode("pairBlend", name="pairBlend1")
createNode("animCurveTL", name="L_Pupil_ctrl_translateX")
connectAttr("L_Pupil_ctrl_translateX.output", "pairBlend1.inTranslateX1")
connectAttr("pairBlend1.outTranslateX", "L_Pupil_ctrl.translateX")
addAttr("L_Pupil_ctrl", longName="blendParent1", attributeType="double", defaultValue=0.5)
setAttr("L_Pupil_ctrl.blendParent1", 0.5)
connectAttr("L_Pupil_ctrl.blendParent1", "pairBlend1.weight")
sk = repair.stray_keys()
check("keys left on a constrained channel: the pairBlend, its control and the key",
      sk == [("pairBlend1", ["L_Pupil_ctrl"], ["L_Pupil_ctrl_translateX"])])
repair.fix_stray_keys(sk)
check("fix: the key is gone and the constraint has the whole say",
      not objExists("L_Pupil_ctrl_translateX") and getAttr("L_Pupil_ctrl.blendParent1") == 1)
check("nothing left to report", repair.stray_keys() == [])

# --- ribbons marked not symmetric; held groups between offset and control
reset()
createNode("transform", name="Collar_ribbon_grp")
createNode("transform", name="Collar_ctrls_grp", parent="Collar_ribbon_grp")
with mock.patch.object(ribbon, "_find_builds", lambda: {"Collar": {"nodes": ["Collar_ctrls_grp"]}}), \
        mock.patch.object(ribbon, "_resolve", lambda k: k), mock.patch.object(ribbon, "_say", lambda m: None):
    check("a ribbon starts symmetric", not ribbon.is_asymmetric("Collar"))
    ribbon.set_asymmetric("Collar", True)
    check("marked not symmetric (an attribute on its controls group, nothing moves)",
          ribbon.is_asymmetric("Collar") and getAttr("Collar_ctrls_grp.rrbNotSymmetric"))
    try:
        ribbon.mirror_sides("Collar")
        refused = False
    except RuntimeError as e:
        refused = "not symmetric" in str(e)
    check("Make the right side mirror the left refuses a ribbon marked not symmetric", refused)
    ribbon.set_asymmetric("Collar", False)
    check("the mark comes off", not ribbon.is_asymmetric("Collar"))
check("an unknown ribbon isn't marked", not ribbon.is_asymmetric("nothing"))
reset()
createNode("transform", name="Cape_fol_04_ctrl_offset")
createNode("transform", name="Cape_fol_04_ctrl_sdk", parent="Cape_fol_04_ctrl_offset")
createNode("transform", name="Cape_fol_04_ctrl", parent="Cape_fol_04_ctrl_sdk")
createNode("parentConstraint", name="sdk_pc", parent="Cape_fol_04_ctrl_sdk")
connectAttr("sdk_pc.constraintTranslateX", "Cape_fol_04_ctrl_sdk.translateX")
got = ribbon.constrained_between("Cape_fol_04_ctrl_offset", ls("Cape_fol_04_ctrl", long=True)[0])
check("the cape's _sdk group held by a constraint between offset and control is found",
      [g.split("|")[-1] for g in got] == ["Cape_fol_04_ctrl_sdk"])
reset()
createNode("transform", name="o")
createNode("transform", name="c", parent="o")
check("nothing between offset and control: nothing held", ribbon.constrained_between("o", ls("c", long=True)[0]) == [])

# --- Animtool: the mirror table, controls on a ribbon marked not symmetric pair with nobody
from gus_animtool import anim as A
A.opt = lambda key, default: default
reset()
createNode("transform", name="Collar_ctrls_grp")
addAttr("Collar_ctrls_grp", longName="rrbNotSymmetric", attributeType="bool")
setAttr("Collar_ctrls_grp.rrbNotSymmetric", True)
createNode("transform", name="Collar_fol_09_ctrl_offset", parent="Collar_ctrls_grp")
createNode("transform", name="Collar_fol_09_ctrl", parent="Collar_fol_09_ctrl_offset")
createNode("nurbsCurve", name="Collar_fol_09_ctrlShape", parent="Collar_fol_09_ctrl")
c9 = ls("Collar_fol_09_ctrl", long=True)[0]
check("a control on a ribbon marked not symmetric: no twin (mirror leaves it alone)",
      A.no_mirror(c9) and A.twin_of(c9) is None)
createNode("transform", name="L_arm_grp")
setAttr("L_arm_grp.translateX", 5.0)
createNode("transform", name="L_Cape_ctrl", parent="L_arm_grp")
createNode("nurbsCurve", name="L_Cape_ctrlShape", parent="L_Cape_ctrl")
cc = ls("L_Cape_ctrl", long=True)[0]
setAttr(cc + ".translateX", 2.0)
setAttr(cc + ".rotateY", 30.0)
check("not learned yet: no stored rest", A.stored_rest(cc) is None)
with mock.patch.object(A, "Undo", mock.MagicMock()), mock.patch.object(A, "message", lambda *x, **k: None):
    n = A.learn_rest(nodes=[cc])
st = A.stored_rest(cc)
check("learned: the control's rest place is kept (at its parent's spot, tx 5), its pose is back (tx 2, ry 30)",
      n == 1 and st is not None and abs(st[12] - 5.0) < 1e-6 and getAttr(cc + ".translateX") == 2.0 and
      getAttr(cc + ".rotateY") == 30.0)
setAttr("L_arm_grp.translateX", 9.0)
check("the arm posed later: mirror still uses the learned rest (not where the arm is now)",
      abs(A.world_rest(cc)[12] - 5.0) < 1e-6)
check("a control not learned is worked out as before", A.stored_rest(c9) is None and len(A.world_rest(c9)) == 16)

# --- the picker check reads the picker saved in the rig
from gus_animtool import pickmodel as PM
with mock.patch.object(PM, "rig_picker", lambda ns=None: {"pages": []}), \
        mock.patch.object(PM, "own_picker", lambda ns=None: None):
    pk, where = scene_check.picker_saved("")
check("the picker saved in the rig is found (the old check said 'no saved picker')",
      pk == {"pages": []} and where.startswith("in the rig"))
with mock.patch.object(PM, "rig_picker", lambda ns=None: None), \
        mock.patch.object(PM, "own_picker", lambda ns=None: {"pages": [1]}):
    pk, where = scene_check.picker_saved("")
check("only on this computer: said so (animators wouldn't get it)", "this computer only" in where)
with mock.patch.object(PM, "rig_picker", lambda ns=None: None), mock.patch.object(PM, "own_picker", lambda ns=None: None):
    check("none anywhere", scene_check.picker_saved("") == (None, ""))
check("Speed and Ready for animators are parts of Check this scene",
      [p for p, _f in scene_check.PARTS][-2:] == ["speed", "ready"])
check("Repair knows the new fixes", all(f in repair.FINDERS for f in (repair._speed_chain, repair._speed_tags,
                                                                       repair._delta_mush_scale, repair._stray_keys)))

print("%d/%d passed" % (sum(ok), len(ok)))
