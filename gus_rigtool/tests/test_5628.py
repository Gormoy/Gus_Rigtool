# 5.6.28: the 5.6.27 review fixes - component tags reported only (wildcards understood, the head squash made
# without tags), the mirror table (joints keep their place, custom attributes at default, an honest count), held
# groups through a pairBlend and the offset itself, safe mode (by UUID, gone nodes, unsteady frames, only its own
# undo step), the speed timing always put back with Auto Key off, the pairBlend message, Unpublish clears the
# mirror table
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import safe, repair, ribbon, head_squash as HS, report as R
from gus_rigtool.core import rigspeed as speed
from gus_rigtool import scene_check
from gus_rigtool.builder import publish
ok = []
def reset():
    S.__init__()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- 1. component tags: reported only, wildcards understood
check("a wildcard stays in the name (5.6.27 cut it off: head_* became head_)",
      speed._expr_names("head_* + Head_squash") == ["head_*", "Head_squash"])
check("a tag name with a wildcard is found when a tag matches it",
      speed._tag_found("head_*", {"head_top"}) and speed._tag_found("Head_squash", {"Head_squash"}) and
      not speed._tag_found("head_*", {"neck"}) and not speed._tag_found("Head_squash", {"Head_squash_3"}))
reset()
createNode("skinCluster", name="Head_squash")              # any deformer (the fake knows skinCluster as one)
with mock.patch.object(speed, "_indices", lambda d: [0, 1]), mock.patch.object(speed, "_tags_on", lambda p: {"head_top"}):
    setAttr("Head_squash.input[0].componentTagExpression", "head_*")
    setAttr("Head_squash.input[1].componentTagExpression", "Head_squash")
    tp = speed.tag_problems()
    check("only the input asking for a tag nobody has is listed (head_* matches head_top)",
          tp == [("Head_squash", 1, "Head_squash", ["Head_squash"])])
    check("the fix changes nothing any more (no deformer gets the whole mesh)",
          speed.fix_tags(tp) == 0 and getAttr("Head_squash.input[1].componentTagExpression") == "Head_squash")
check("Check this scene says how to fix it: make the squash again",
      "Remove, then Make" in speed.tag_advice("Head_squash") and "make the deformer again" in speed.tag_advice("x"))
check("not a Repair any more", repair._speed_tags not in repair.FINDERS and repair._speed_tags() is None)

# --- 1b. the head squash without component tags: whole meshes in the lattice, the outside held at 0
got = HS.lattice_targets(["|Hare_Body", "|Eyes"], ["|Hare_Body.vtx[2:3]", "|Eyes"],
                         {"|Hare_Body": ["|Hare_Body.vtx[0:1]"]})
check("the lattice takes the whole body (its outside known) and a mesh it can't read as before",
      got == ["|Hare_Body", "|Eyes"])
check("with nothing outside known: the member vertices, as in 5.6.27",
      HS.lattice_targets(["|Hare_Body"], ["|Hare_Body.vtx[2:3]"], {}) == ["|Hare_Body.vtx[2:3]"])
calls = []
with mock.patch.object(cmds, "percent", lambda *a, **k: calls.append((a, k)), create=True):
    n = HS.hold_outside("Head_squash", {"|Hare_Body": ["|Hare_Body.vtx[0:1]"], "|Eyes": []})
check("the outside vertices get weight 0 on the deformer (kept in the rig file, not a tag on the mesh)",
      n == 1 and calls == [(("Head_squash", ["|Hare_Body.vtx[0:1]"]), {"value": 0.0})])

# --- 2. the mirror table
from gus_animtool import anim as A
A.opt = lambda key, default: default
reset()
createNode("transform", name="L_arm_grp")
setAttr("L_arm_grp.translateX", 5.0)
createNode("joint", name="L_tail_01_ctrl", parent="L_arm_grp")
createNode("nurbsCurve", name="L_tail_01_ctrlShape", parent="L_tail_01_ctrl")
jc = ls("L_tail_01_ctrl", long=True)[0]
setAttr(jc + ".translateX", 3.0)
setAttr(jc + ".rotateZ", 20.0)
createNode("transform", name="L_wrist_settings_ctrl", parent="L_arm_grp")
createNode("nurbsCurve", name="L_wrist_settings_ctrlShape", parent="L_wrist_settings_ctrl")
wc = ls("L_wrist_settings_ctrl", long=True)[0]
addAttr(wc, longName="curl", attributeType="double", defaultValue=0.0, keyable=True)
addAttr(wc, longName="ikfk", attributeType="double", defaultValue=1.0, keyable=True)
setAttr(wc + ".curl", 7.0)
setAttr(wc + ".ikfk", 0.0)
seen = {}
real_world = A.world
def spy(n):
    if n == wc:
        seen["curl"], seen["ikfk"] = getAttr(wc + ".curl"), getAttr(wc + ".ikfk")
    return real_world(n)
with mock.patch.object(A, "Undo", mock.MagicMock()), mock.patch.object(A, "message", lambda *x, **k: None), \
        mock.patch.object(A, "world", spy):
    n = A.learn_rest(nodes=[jc, wc])
st = A.stored_rest(jc)
check("a joint control keeps its place on its parent (translate isn't zeroed): rest x = 5 + 3",
      n == 2 and st is not None and abs(st[12] - 8.0) < 1e-6)
check("while it's read, the custom attributes are at their default (curl 0, ikfk 1)",
      seen == {"curl": 0.0, "ikfk": 1.0})
check("then every value is back (joint tx 3, rz 20, curl 7, ikfk 0)",
      getAttr(jc + ".translateX") == 3.0 and getAttr(jc + ".rotateZ") == 20.0 and
      getAttr(wc + ".curl") == 7.0 and getAttr(wc + ".ikfk") == 0.0)
real_set = cmds.setAttr
def locked(plug, *a, **k):
    if plug.endswith(A.REST_ATTR):
        raise RuntimeError("locked reference")
    return real_set(plug, *a, **k)
with mock.patch.object(A, "Undo", mock.MagicMock()), mock.patch.object(A, "message", lambda *x, **k: None), \
        mock.patch.object(A.cmds, "setAttr", locked):
    n = A.learn_rest(nodes=[jc, wc])
check("a table that can't be written (a locked reference) isn't counted as learned", n == 0)

# --- 3. held groups: through a pairBlend, and the offset itself
reset()
createNode("transform", name="Cape_04_ctrl_offset")
createNode("transform", name="Cape_04_ctrl_sdk", parent="Cape_04_ctrl_offset")
createNode("transform", name="Cape_04_ctrl", parent="Cape_04_ctrl_sdk")
createNode("parentConstraint", name="sdk_pc")
createNode("pairBlend", name="pairBlend1")
connectAttr("sdk_pc.constraintRotateX", "pairBlend1.inRotateX2")
connectAttr("pairBlend1.outRotateX", "Cape_04_ctrl_sdk.rotateX")
got = ribbon.constrained_between("Cape_04_ctrl_offset", ls("Cape_04_ctrl", long=True)[0])
check("a group held by a constraint through a pairBlend (a keyed channel / space blend) is found",
      [g.split("|")[-1] for g in got] == ["Cape_04_ctrl_sdk"])
reset()
createNode("transform", name="o")
createNode("transform", name="c", parent="o")
createNode("parentConstraint", name="o_pc")
connectAttr("o_pc.constraintTranslateX", "o.translateX")
got = ribbon.constrained_between("o", ls("c", long=True)[0])
check("the offset itself held by a constraint is found too (it's the group that gets flipped)",
      [g.split("|")[-1] for g in got] == ["o"])
createNode("transform", name="free_o")
createNode("transform", name="free_c", parent="free_o")
check("nothing held: nothing found", ribbon.constrained_between("free_o", ls("free_c", long=True)[0]) == [])

# --- 4. safe mode
reset()
createNode("transform", name="Hare_Body")
createNode("transform", name="grp")
uid = ls("Hare_Body", uuid=True)[0]
a = {"rest": {"mesh": safe._by_uuid({"|Hare_Body": [0, 0, 0, 1, 1, 1]}), "ctrl": {}}}
check("looks are kept by UUID, with the name for the report", list(a["rest"]["mesh"]) == [uid] and
      a["rest"]["mesh"][uid][0] == "|Hare_Body")
parent("Hare_Body", "grp")
b = {"rest": {"mesh": safe._by_uuid({"|grp|Hare_Body": [0, 0, 0, 1, 1, 1.5]}), "ctrl": {}}}
bad = safe.compare(a, b)
check("a mesh the fix moved under another group is still compared (5.6.27 skipped it)",
      bad == [("rest", "|Hare_Body", 1, 0.5)])
gone = safe.compare(a, {"rest": {"mesh": {}, "ctrl": {}}})
check("a mesh the fix deleted is listed as gone", gone == [("rest", "|Hare_Body", 0, None)] and
      "gone, or its points changed" in safe.describe(gone))
fewer = safe.compare(a, {"rest": {"mesh": {uid: ("|Hare_Body", [0, 0, 0])}, "ctrl": {}}})
check("a mesh whose points changed in number is listed too", fewer == [("rest", "|Hare_Body", 0, None)])
f1 = {"frame 10": {"mesh": {"j": ("Belt", [0, 0, 0])}, "ctrl": {}}}
f2 = {"frame 10": {"mesh": {"j": ("Belt", [0, 0, 0.3])}, "ctrl": {}}}
shaky = safe.unsteady(f1, f2)
check("a mesh that isn't the same twice with nothing done (jiggle) is unsteady",
      shaky == {("frame 10", "j")})
check("an unsteady mesh isn't held against the fix", safe.compare(f1, f2, skip=shaky) == [] and
      safe.compare(f1, f2) != [])
undo = mock.MagicMock()
with mock.patch.object(cmds, "undo", undo, create=True), mock.patch.object(
        cmds, "undoInfo", mock.MagicMock(side_effect=lambda *x, **k: "somethingElse" if k.get("undoName") else True),
        create=True):
    done = safe.undo_own("gusrigRepair_x")
check("undo only takes back our own step (the last step is someone else's: left alone)",
      not done and not undo.called)
with mock.patch.object(cmds, "undo", undo, create=True), mock.patch.object(
        cmds, "undoInfo", mock.MagicMock(side_effect=lambda *x, **k: "gusrigRepair_x" if k.get("undoName") else True),
        create=True):
    done = safe.undo_own("gusrigRepair_x")
check("our own step is undone", done and undo.called)
# Repair: the look after the fix is taken once its undo step is closed
order = []
it = repair.Item("t", "test", "", 1, lambda: order.append("fix"))
def snap(*x, **k):
    order.append("look")
    return {"rest": {"mesh": {}, "ctrl": {}}}
def info(*x, **k):
    if k.get("closeChunk"):
        order.append("close")
    if k.get("openChunk"):
        order.append("open")
    return True
with mock.patch.object(safe, "snapshot", snap), mock.patch.object(safe, "anim_frames", lambda *x: []), \
        mock.patch.object(cmds, "undoInfo", mock.MagicMock(side_effect=info), create=True):
    res = repair.apply(["t"], [it])
check("Repair: before-look, fix in its own step, the step closed, then the after-look",
      order == ["look", "open", "fix", "close", "look"] and res[0][1] is None)
boom = repair.Item("b", "boom", "", 1, lambda: (_ for _ in ()).throw(ValueError("no")))
undo = mock.MagicMock()
with mock.patch.object(safe, "snapshot", snap), mock.patch.object(safe, "anim_frames", lambda *x: []), \
        mock.patch.object(cmds, "undo", undo, create=True), mock.patch.object(
            cmds, "undoInfo", mock.MagicMock(side_effect=lambda *x, **k: "" if k.get("undoName") else True),
            create=True):
    res = repair.apply(["b"], [boom])
check("a fix that failed before changing anything: nothing undone (the step before it is left alone)",
      res[0][1].startswith("failed") and not undo.called)

# --- 5. speed timing: always back, Auto Key off for the test
reset()
createNode("transform", name="COG_ctrl")
setAttr("COG_ctrl.translateX", 1.5)
calls = {"n": 0, "key": []}
def bad_refresh(**k):
    calls["n"] += 1
    if calls["n"] == 3:
        raise RuntimeError("the viewport went away")
with mock.patch.object(cmds, "refresh", bad_refresh, create=True):
    try:
        speed._step_time("COG_ctrl.translateX", 5)
        raised = False
    except RuntimeError:
        raised = True
check("the drag breaks half way: the control is back where it was (1.5)",
      raised and getAttr("COG_ctrl.translateX") == 1.5)
state = {"on": True}
def autokey(query=False, state_=None, **k):
    if query:
        return state["on"]
    state["on"] = k.get("state")
    calls["key"].append(state["on"])
with mock.patch.object(cmds, "refresh", lambda **k: None, create=True), \
        mock.patch.object(cmds, "autoKeyframe", lambda **k: autokey(query=k.pop("query", False), **k), create=True), \
        mock.patch.object(cmds, "undoInfo", mock.MagicMock(return_value=True), create=True):
    t = speed.time_drag(["|COG_ctrl"], steps=3)
check("Auto Key is off while it drags, then on again", calls["key"] == [False, True] and state["on"] and
      "|COG_ctrl" in t and getAttr("COG_ctrl.translateX") == 1.5)

# --- 6. the pairBlend message: a space blend is normal
reset()
createNode("transform", name="L_humerus_FK_space_grp")
createNode("parentConstraint", name="space_pc")
createNode("pairBlend", name="pairBlend1")
connectAttr("space_pc.constraintRotateX", "pairBlend1.inRotateX1")
connectAttr("pairBlend1.outRotateX", "L_humerus_FK_space_grp.rotateX")
createNode("transform", name="L_Pupil_ctrl")
createNode("pairBlend", name="pairBlend2")
createNode("animCurveTL", name="L_Pupil_ctrl_translateX")
connectAttr("L_Pupil_ctrl_translateX.output", "pairBlend2.inTranslateX1")
connectAttr("pairBlend2.outTranslateX", "L_Pupil_ctrl.translateX")
rep = R.Report("x")
scene_check.check_connections(rep)
text = rep.text()
check("a real key + constraint is still said", "keys + constraints on the same channels (pairBlend) (1)" in text
      and "pairBlend2" in text)
check("the space blend (pairBlend1 on the humerus space group) is said to be normal",
      "constraints blended by a pairBlend (1) - normal (a space switch)" in text)

# --- 7. Unpublish clears the mirror table
reset()
createNode("transform", name="L_hand_ctrl")
addAttr("L_hand_ctrl", longName="gusRestWorld", dataType="string")
createNode("transform", name="R_hand_ctrl")
n = publish.clear_mirror_table(["L_hand_ctrl", "R_hand_ctrl"])
check("the learned rest is taken off (Animtool works it out live until the next Publish)",
      n == 1 and not attributeQuery("gusRestWorld", node="L_hand_ctrl", exists=True))

print("%d/%d passed" % (sum(ok), len(ok)))
