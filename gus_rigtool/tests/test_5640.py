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

# --- 2. the look
class Shape(object):
    attrs = ["showFrameMarkers", "frameMarkerSize", "keyframeSize", "trailThickness", "showFrames", "preFrame",
             "postFrame", "fadeInoutFrames", "trailDrawMode", "trailColor", "preFrameColor", "postFrameColor",
             "extraTrailColor", "showInTangent", "showOutTangent", "increment"]
sets_ = {}
with mock.patch.object(cmds, "listRelatives", lambda n, **k: ["|trailShape"] if k.get("shapes") else []), \
        mock.patch.object(cmds, "listAttr", lambda n, **k: list(Shape.attrs)), \
        mock.patch.object(cmds, "attributeQuery", lambda a, **k: ["Line:Alternating Frames:Past/Future:Velocity"]), \
        mock.patch.object(cmds, "setAttr", lambda plug, *v, **k: sets_.__setitem__(plug.split(".")[-1], v)):
    done = T.style("|trail")
check("24 frames before and after your frame, fading over the last 8",
      sets_["preFrame"] == (24,) and sets_["postFrame"] == (24,) and sets_["fadeInoutFrames"] == (8,))
check("Past/Future found by its name (the 3rd choice), past blue, future orange",
      sets_["trailDrawMode"] == (2,) and sets_["preFrameColor"] == T.PAST and sets_["postFrameColor"] == T.FUTURE)
check("a dot on every frame, bigger keys, a thin line, no frame numbers",
      sets_["showFrameMarkers"] == (True,) and sets_["keyframeSize"] == (9.0,) and sets_["trailThickness"] == (1.5,)
      and sets_["showFrames"] == (False,))
check("the bezier handles: on (Maya shows them on the key you select)",
      sets_["showInTangent"] == (True,) and sets_["showOutTangent"] == (True,))
check("'extraTrailColor' isn't mistaken for past / future", "extraTrailColor" not in sets_)
Shape.attrs = ["preFrame", "postFrame"]
sets_.clear()
_opts["arcs_range"] = 0
with mock.patch.object(cmds, "listRelatives", lambda n, **k: ["|trailShape"] if k.get("shapes") else []), \
        mock.patch.object(cmds, "listAttr", lambda n, **k: list(Shape.attrs)), \
        mock.patch.object(cmds, "setAttr", lambda plug, *v, **k: sets_.__setitem__(plug.split(".")[-1], v)):
    done = T.style("|trail")
check("the whole range: the window covers frames 1-100; settings Maya doesn't have are skipped, no error",
      sets_ == {"preFrame": (100,), "postFrame": (100,)} and done == ["preFrame", "postFrame"])
_opts["arcs_range"] = 24

# --- 3. show: editable trails + the onion skin for rotation-only controls
made = []
T.make = lambda nodes: made.extend(nodes) or list(nodes)
onion_pts = []
class Arcs(object):
    def __init__(s): s.points = []
    def setPoints(s, p): s.points = list(p); onion_pts.append(list(p))
    def removePoint(s, p): s.points.remove(p)
sess = types.SimpleNamespace(o=types.SimpleNamespace(arcs=Arcs()), prefs={"arcsShow": False}, _arcKeys=lambda: None,
                             changed=lambda: None, scheduleAutoFill=lambda: None, isOn=lambda: True)
sess.setArcs = lambda k, v: sess.prefs.__setitem__(k, v)
T._onion = lambda: sess
edit, view, unseen = T.show([hand, wrist])
check("the hand gets an editable trail, the wrist goes to the onion skin's arcs (and its arcs are turned on)",
      edit == [hand] and view == [wrist] and unseen == [] and made == [hand] and sess.o.arcs.points == [(wrist, None)]
      and sess.prefs["arcsShow"] is True)
check("the message says which can be dragged and which can't",
      "1 editable" in T.describe(edit, view, unseen) and "shown, not editable" in T.describe(edit, view, unseen))
T._onion = lambda: None
check("no onion skin installed: the wrist is said to have no arc to drag", T.show([wrist])[2] == [wrist] and
      "install the onion skin" in T.describe([], [wrist], [wrist]))
T._onion = lambda: sess

# --- 4. follow selection and pin
deleted = []
_g = createNode("transform", name="grp")
for _t in ("L_hand_ik_ctrl_arc", "R_hand_ik_ctrl_arc"):
    createNode("transform", name=_t, parent=_g)
trails_of = {hand: ["|grp|L_hand_ik_ctrl_arc"], wrist: []}
T._trails_of = lambda n: list(trails_of.get(n, []))
T._watch = lambda: None
other = createNode("transform", name="R_hand_ik_ctrl")
cv = createNode("animCurveTL", name="R_hand_tx"); connectAttr(cv + ".output", other + ".translateX")
other = cmds.ls(other, long=True)[0]
with mock.patch.object(cmds, "delete", lambda *a, **k: deleted.extend(a)):
    cmds.select(hand)
    T.follow(True)
    check("Arcs on: they follow the selection (the hand)", T._state["follow"] and T._state["followed"] == [hand])
    cmds.select(other)
    made[:] = []
    T._selection_changed()
    check("select the other hand: the first hand's arc goes, the new one shows",
          deleted == ["|grp|L_hand_ik_ctrl_arc"] and made == [other] and T._state["followed"] == [other])
    deleted[:] = []
    cmds.select(clear=True)
    T._selection_changed()
    check("nothing selected: the arc stays", deleted == [] and T._state["followed"] == [other])
    T.pin([hand])
    check("pinned: the hand's arc stays", hand in T._state["pinned"])
    cmds.select(wrist)
    deleted[:] = []
    trails_of[other] = ["|grp|R_hand_ik_ctrl_arc"]
    T._selection_changed()
    check("select the wrist: the pinned hand stays, the followed other hand goes, the wrist to the onion skin",
          deleted == ["|grp|R_hand_ik_ctrl_arc"] and hand in T._state["pinned"] and (wrist, None) in sess.o.arcs.points)
    cmds.select(hand)
    T._selection_changed()
    check("from the wrist to something else: its onion arc is taken away again", (wrist, None) not in sess.o.arcs.points)
    T.follow(False)
    check("Arcs off: the followed ones go, the pinned stay", T._state["followed"] == [] and T._state["pinned"] == [hand])

# --- 5. saving: no arc nodes in the file
T._state["followed"] = [other]
with mock.patch.object(cmds, "delete", lambda *a, **k: deleted.extend(a)), \
        mock.patch.object(cmds, "ls", lambda *a, **k: ["|gusAnimtool_arcs_grp"] if a and a[0] == T.GROUP else []):
    deleted[:] = []
    T._before_save()
check("before a save: the arcs' group is deleted, the controls remembered",
      deleted == [["|gusAnimtool_arcs_grp"]] and T._state["saved"] == [other, hand])
later = []
with mock.patch.object(cmds, "evalDeferred", lambda fn, **k: later.append(fn), create=True):
    T._after_save()
made[:] = []
trails_of.clear()                      # the trails went with the save
later[0]()
check("after the save: they come back (once Maya is idle)", made == [other, hand] and T._state["saved"] is None)

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

# --- 7. the button and its menu
labels = [lab for lab, _c in AC.MENUS["arcs"]]
check("right-click on Arcs: pin, 12 / 24 / 48 / whole range, timing beads, clear",
      [c for _l, c in AC.MENUS["arcs"]] == ["arcs_pin", "arcs_r12", "arcs_r24", "arcs_r48", "arcs_r0", "arcs_weighted",
                                           "arcs_clear"] and "asks first" in labels[5])
restyled = []
T.restyle = lambda: restyled.append(1)
check("Range 48: kept, and the arcs restyled", "48 frames" in AC._call("arcs_r48") and _opts["arcs_range"] == 48 and
      restyled == [1])
check("Range whole", "whole frame range" in AC._call("arcs_r0"))
T._state["follow"] = False
cmds.select(hand)
said = AC._call("arcs")
check("the Arcs button: follow on, and what it shows", T._state["follow"] and "follow your selection" in said)
check("again: follow off", "stop following" in AC._call("arcs"))

# --- 8. clear and another scene
gone = []
with mock.patch.object(cmds, "delete", lambda *a, **k: gone.extend(a)), \
        mock.patch.object(cmds, "ls", lambda *a, **k: ["|gusAnimtool_arcs_grp"] if a and a[0] == T.GROUP else []):
    T._unwatch = lambda: gone.append("jobs")
    sess.o.arcs.points = [(wrist, None), ("|other:point", 5)]
    T._state["onion"] = [(wrist, None)]
    T.clear()
check("Clear: the trails, the selection job and only the onion arcs the Animtool added go",
      ["|gusAnimtool_arcs_grp"] in gone and "jobs" in gone and sess.o.arcs.points == [("|other:point", 5)]
      and not T._state["follow"] and T._state["pinned"] == [])
T._state.update(followed=[hand], pinned=[other], follow=True)
T._scene_gone()
check("another scene opened: nothing left to follow or pin", T._state["followed"] == [] and T._state["pinned"] == []
      and not T._state["follow"])

print("%d/%d passed" % (sum(ok), len(ok)))
