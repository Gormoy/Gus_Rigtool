# 5.6.30: the clothes - bandages too, a Full / Hidden per piece; Publish's default pose and mirror table on every
# control, Unpublish clears the same; Keep the pose, zero for a control driven by a constraint (the pupils); Not a
# control; Go there in Check this scene; each clothes piece timed
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import clothes_switch as CS, zero_pose, control_role, report as R
from gus_rigtool.core import rigspeed as speed
from gus_rigtool import scene_check
from gus_rigtool.builder import publish
from gus_rigtool.tools import checker
ok = []
def reset():
    S.__init__()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

DEFORMERS = ("skinCluster", "deltaMush")
real_type = cmds.objectType
def otype(name, isAType=None):
    if isAType == "geometryFilter":
        return real_type(name) in DEFORMERS
    return real_type(name, isAType=isAType)

# --- 1. the clothes: bandages, a switch per piece
check("pieces from the names: Hood, Pants, Bandages (Bandage_L, Bandages_Arms); the belt isn't clothes",
      [CS.part_of(m) for m in ("Geo:Hood", "Pants", "Bandage_L", "Bandages_Arms")] == ["Hood", "Pants", "Bandages",
                                                                                        "Bandages"]
      and not __import__("re").search(CS.PATTERN, "Belt_Ring", __import__("re").IGNORECASE))
reset()
createNode("transform", name="Visibility_ctrl")
names = ("Hood", "Bandage_L", "Bandages_Arms", "Belt")
hist, deforms = {}, {}
for i, t in enumerate(names):
    createNode("transform", name=t)
    createNode("mesh", name=t + "Shape", parent=t)
    sk = "skin%d" % i
    createNode("skinCluster", name=sk)
    addAttr(sk, longName="nodeState", attributeType="long")
    hist["|%s|%sShape" % (t, t)] = [sk]
    deforms[sk] = ["|%s|%sShape" % (t, t)]
def history(node, **k):
    return list(hist.get(ls(node, long=True)[0], []))
with mock.patch.object(cmds, "listHistory", history), \
        mock.patch.object(cmds, "deformer", lambda d, **k: list(deforms[d]), create=True), \
        mock.patch.object(cmds, "objectType", otype), \
        mock.patch.object(CS, "_switch_control", lambda: ls("Visibility_ctrl", long=True)[0]):
    found = CS.suggest()
    check("found by name: the hood and both bandages (5.6.29 missed the bandages), not the belt",
          found == ["|Hood", "|Bandage_L", "|Bandages_Arms"])
    lines = CS.describe(found)
    check("the plan lists each piece and its meshes", "  Bandages_Geo: Bandage_L, Bandages_Arms" in lines and
          "  Hood_Geo: Hood" in lines)
    data = CS.make(found)
    vc = "Visibility_ctrl"
    check("a Full / Hidden per piece next to Clothes (Hood_Geo, Bandages_Geo)",
          getAttr(vc + ".Hood_Geo") == 0 and getAttr(vc + ".Bandages_Geo") == 0 and getAttr(vc + ".Clothes") == 0 and
          sorted(data["parts"]) == ["Bandages", "Hood"])
    check("a piece is hidden when Clothes or its own switch is on Hidden (Clothes + piece > 0)",
          listConnections("Clothes_Bandages_pma.input1D[0]", source=True, destination=False, plugs=True) ==
          ["Visibility_ctrl.Clothes"] and
          listConnections("Clothes_Bandages_pma.input1D[1]", source=True, destination=False, plugs=True) ==
          ["Visibility_ctrl.Bandages_Geo"] and getAttr("Clothes_Bandages_hidden.operation") == 2)
    check("both bandages hide with Bandages_Geo, their skins switch off with it",
          listConnections("Bandage_L.visibility", source=True, destination=False) == ["Clothes_Bandages_rev"] and
          listConnections("Bandages_Arms.visibility", source=True, destination=False) == ["Clothes_Bandages_rev"]
          and listConnections("skin2.nodeState", source=True, destination=False, plugs=True) ==
          ["Clothes_Bandages_hidden.outColorR"])
    check("removed: the piece switches and their nodes go too", CS.remove() and
          not attributeQuery("Bandages_Geo", node=vc, exists=True) and not objExists("Clothes_Bandages_pma"))

# --- 2. Publish: default pose and mirror table on every control; Unpublish clears the same
src = open(publish.__file__).read()
check("Publish saves the default pose on every control Animtool sees (the ribbons too), not only controls_grp's",
      "for c in every:" in src and "every = mirror_table_controls(A, ctrls) if A else list(ctrls)" in src)
reset()
createNode("transform", name="HARE_RIG")
publish.controls.add_string("|HARE_RIG", publish.STATE_ATTR, '{"plugs": {}, "attrs": {}, "sets": []}')
cleared = []
A = mock.MagicMock()
A.namespace_of.return_value = ""
A.character_controls.return_value = ["|c1", "|ribbon_ctrl"]
with mock.patch.object(publish, "_gus_rig", lambda: "|HARE_RIG"), \
        mock.patch.object(publish, "is_published", lambda: True), \
        mock.patch.object(publish, "rig_controls", lambda: ["|c1"]), \
        mock.patch.object(publish, "_animtool_module", lambda: A), \
        mock.patch.object(publish, "clear_mirror_table", lambda ctrls=None: cleared.append(ctrls) or 2), \
        mock.patch("gus_rigtool.core.network_tools.unprotect", lambda *a, **k: None):
    publish.unpublish(quiet=True)
check("Unpublish clears the table on the same controls Publish learned it on (366, not 182)",
      cleared == [["|c1", "|ribbon_ctrl"]])

# --- 3. Keep the pose, zero: a control driven by a constraint (the pupils)
reset()
createNode("transform", name="Head_ctrl")
setAttr("Head_ctrl.translateY", 10.0)
createNode("transform", name="L_Pupil_ctrl_offset")
createNode("transform", name="L_Pupil_ctrl", parent="L_Pupil_ctrl_offset")
createNode("nurbsCurve", name="L_Pupil_ctrlShape", parent="L_Pupil_ctrl")
pc = ls("L_Pupil_ctrl", long=True)[0]
setAttr(pc + ".translateX", 2.0)
setAttr(pc + ".translateY", 11.0)
cmds.parentConstraint("Head_ctrl", pc, maintainOffset=True)        # the fake names it <driven>_parentConstraint1
before = cmds.xform(pc, query=True, worldSpace=True, matrix=True)
cons, why = zero_pose.constraints_on(pc)
check("the pupil: a parent constraint on the control itself is found", [cmds.nodeType(c) for c in cons] ==
      ["parentConstraint"] and why is None)
done, skipped = zero_pose.apply([pc])
pc = ls("L_Pupil_ctrl", long=True)[0]
grp = cmds.listRelatives(pc, parent=True, fullPath=True)[0]
check("zeroed: the control reads 0, the constraint is on its group now, the control stays where it was",
      done and not skipped and getAttr(pc + ".translateX") == 0 and getAttr(pc + ".translateY") == 0 and
      not zero_pose.constraints_on(pc)[0] and
      [cmds.nodeType(x) for x in cmds.listRelatives(grp, children=True) or [] if "onstraint" in cmds.nodeType(x)]
      == ["parentConstraint"] and
      cmds.parentConstraint(zero_pose.constraints_on(grp)[0][0], query=True, targetList=True) == ["Head_ctrl"] and
      all(abs(a - b) < 1e-6 for a, b in zip(cmds.xform(pc, query=True, worldSpace=True, matrix=True), before)))
reset()
createNode("transform", name="Tongue_ctrl")
createNode("nurbsCurve", name="Tongue_ctrlShape", parent="Tongue_ctrl")
createNode("aimConstraint", name="Tongue_aim")
connectAttr("Tongue_aim.constraintRotateX", "Tongue_ctrl.rotateX")
_c, why = zero_pose.constraints_on(ls("Tongue_ctrl", long=True)[0])
check("an aim constraint isn't moved for you - it says to do that one by hand", "aimConstraint" in (why or ""))

# --- 4. Not a control
reset()
createNode("transform", name="Neck_ctrl")
createNode("nurbsCurve", name="Neck_ctrlShape", parent="Neck_ctrl")
nk = ls("Neck_ctrl", long=True)[0]
from gus_animtool import anim as AN
check("a control to begin with", checker.is_control(nk) and publish._is_ctrl(nk))
got = control_role.set_role([nk], control=False)
check("marked 'not a control': the checker, Publish and Animtool leave it out", got == [nk] and
      not checker.is_control(nk) and not publish._is_ctrl(nk) and not AN.is_control(nk))
check("marking it again changes nothing", control_role.set_role([nk], control=False) == [])
control_role.set_role([nk], control=True)
check("a control again", checker.is_control(nk) and not control_role.is_marked(nk))

# --- 5. Go there
rep = R.Report("x")
rep.start("Ribbons")
rep.add(R.WARN, "Collar: 4 right-side control(s) don't mirror their left twin", "")
rep.start("Checker")
rep.add(R.WARN, "Controls: Controls driven by a constraint (3)", "L_Pupil_ctrl")
rep.add(R.WARN, "Controls: Controls hidden by a group above them (5)", "Neck_ctrl_GRP")
rep.add(R.WARN, "plugins the file asks for that aren't loaded", "stereoCamera")
rep.add(R.INFO, "Limits: something", "")
got = scene_check.go_targets(rep)
check("each problem with a place to fix it gets a Go button: the collar, the pupils, the old controls",
      [(t, sc) for _n, _l, t, sc in got] == [("ribbon", "Build and mirror"), ("behaviour", "Rest here"),
                                            ("behaviour", "Not a control")])
check("the ones fixed outside the tool (a plugin) and plain info get none",
      not any("plugins" in n or "Limits" in n for n, _l, _t, _s in got))

# --- 6. each clothes piece timed
def fake_drag(controls, steps=8, attrs=None, hide=None, off=None, **k):
    speed.SKIPPED.clear()
    if attrs:
        return {controls[0]: 100.0 - (30.0 if any("Hood_Geo" in p for p in attrs) else 8.0)}
    return {controls[0]: 100.0}
with mock.patch.object(speed, "time_drag", fake_drag), mock.patch.object(speed, "gpu_on", lambda: False), \
        mock.patch.object(CS, "read", lambda sw=None: {"parts": {"Hood": {"attr": "Hood_Geo"},
                                                                 "Bandages": {"attr": "Bandages_Geo"}}}), \
        mock.patch.object(CS, "_switch_control", lambda: "|Visibility_ctrl"), \
        mock.patch.object(CS, "hidden", mock.MagicMock()), \
        mock.patch.object(cmds, "ls", lambda *a, **k: []):
    x = speed.extra_timings("|COG_ctrl")
check("each piece hidden on its own, through its own switch: Hood saves 30 ms, Bandages 8 ms",
      sorted(x["pieces"]) == [("Bandages", 8.0), ("Hood", 30.0)])
rep = R.Report("x")
rep.start("Speed")
with mock.patch.object(speed, "extra_timings", lambda c: dict(x, clothes=None, gpu_off=None, skins=[])), \
        mock.patch.object(CS, "suggest", lambda: []):
    scene_check._speed_more(rep, speed, {"|COG_ctrl": 100.0})
check("Check this scene lists them, the biggest saving first", "Hood saves 30 ms; Bandages saves 8 ms" in rep.text())

print("%d/%d passed" % (sum(ok), len(ok)))
