# 5.6.40: the Animtool's arcs - Maya's editable trail dressed like the onion skin's arcs (a window around your
# frame, past / future colours, a dot per frame, handles on the selected key), follow selection and pin,
# rotation-only controls shown by the onion skin, no arc nodes in a saved file, weighted tangents only when asked
import os, sys, types
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.undoInfo = mock.MagicMock()
from gus_animtool import anim as A, actions as AC, arctrail as T
_opts = {}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
A.frame_range = lambda: (1, 100)
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- the scene: an IK hand (translate keyed), an FK wrist (rotate keyed), a locked one
hand = createNode("transform", name="L_hand_ik_ctrl")
wrist = createNode("transform", name="L_wrist_fk_ctrl")
still = createNode("transform", name="COG_ctrl")
for n, attr in ((hand, "translateX"), (wrist, "rotateZ"), (still, "translateY")):
    cv = createNode("animCurveTL", name=n.split("|")[-1] + "_" + attr)
    connectAttr(cv + ".output", n + "." + attr)
for _fk in (wrist, still):                 # FK-like: translate locked (5.6.41: a free translate can be edited)
    for _ax in "XYZ":
        cmds.setAttr(_fk + ".translate" + _ax, lock=True)
hand, wrist, still = [cmds.ls(n, long=True)[0] for n in (hand, wrist, still)]
real_lc = cmds.listConnections
cmds.listConnections = lambda plug, **k: (
    [c for c in real_lc(plug, **dict(k, type=None)) or [] if "animCurve" in cmds.nodeType(c)]
    if k.get("type") == "animCurve" else real_lc(plug, **k))

# --- 1. which arcs can be edited
check("the IK hand's arc can be edited (translate animated)", T.moves(hand))
check("the FK wrist only rotates: view only", not T.moves(wrist))
check("a locked translate: view only", not T.moves(still))
check("the arcs' own nodes and key components never count as a selection (dragging a key keeps the arcs)",
      T.controls([hand, "|gusAnimtool_arcs_grp|L_hand_ik_ctrl_arcHandle", hand + ".keyframe[3]", "nope"]) == [hand])

# (5.6.42: the look, follow selection, pin and the onion skin hand-off went back to the plain arc - test_5642.
# What 5.6.40 brought and 5.6.42 keeps is checked here.)

# --- 5. saving: no arc nodes in the file
made = []
T.make = lambda nodes: made.extend(nodes) or list(nodes)
T._state["nodes"] = [hand, wrist]
deleted = []
with mock.patch.object(cmds, "delete", lambda *a, **k: deleted.extend(a)), \
        mock.patch.object(cmds, "ls", lambda *a, **k: ["|gusAnimtool_arcs_grp"] if a and a[0] == T.GROUP else []):
    T._before_save()
check("before a save: the arcs' group is deleted, the controls remembered",
      deleted == [["|gusAnimtool_arcs_grp"]] and T._state["saved"] == [hand, wrist])
later = []
with mock.patch.object(cmds, "evalDeferred", lambda fn, **k: later.append(fn), create=True):
    T._after_save()
later[0]()
check("after the save: they come back (once Maya is idle)", made == [hand, wrist] and T._state["saved"] is None)

# --- 6. timing beads: weighted only when you say so
kt = []
def keyTangent(c, **k):
    if k.get("query"):
        return [False]
    kt.append((c, k))
cmds.keyTangent = keyTangent
cmds.confirmDialog = mock.MagicMock(return_value="Cancel")
check("timing beads, you press Cancel: nothing changes", T.make_weighted([hand]) == 0 and kt == [])
cmds.confirmDialog = mock.MagicMock(return_value="Make weighted")
T.restyle = lambda: None
check("you press Make weighted: the hand's curve weighted, in one undo",
      T.make_weighted([hand]) == 1 and kt[0][1] == {"edit": True, "weightedTangents": True})
msg = cmds.confirmDialog.call_args.kwargs["message"]
check("the question says what changes and that Ctrl+Z undoes it", "keep their shape" in msg and "Ctrl+Z" in msg)
cmds.keyTangent = lambda c, **k: [True] if k.get("query") else None
try:
    T.make_weighted([hand]); said = ""
except RuntimeError as e:
    said = str(e)
check("already weighted: it says so (the beads already show)", "already weighted" in said)

# --- 8. clear and another scene
gone = []
with mock.patch.object(cmds, "delete", lambda *a, **k: gone.extend(a)), \
        mock.patch.object(cmds, "ls", lambda *a, **k: ["|gusAnimtool_arcs_grp"] if a and a[0] == T.GROUP else []):
    T._unwatch = lambda: gone.append("jobs")
    T.clear()
check("Clear: the arcs and the scene jobs go", ["|gusAnimtool_arcs_grp"] in gone and "jobs" in gone and
      T._state["nodes"] == [])
T._state.update(nodes=[hand])
T._scene_gone()
check("another scene opened: the arcs are forgotten", T._state["nodes"] == [])

print("%d/%d passed" % (sum(ok), len(ok)))
