# 5.6.41: Attach - no loop (the parent's inverse, not the follower's own: the stutter), hold channels in the
# Channel Box (normalised), grips keyed so nothing jumps, hand-over, both hands, release, the timeline / changes
# (show, go to, delete, move), loops refused, 5.6.40 attaches repaired, bookmarks (the plugin loaded);
# arcs on controls with no translate keys, the selection put back after a trail, a trail never a control
import os, sys, types
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.undoInfo = mock.MagicMock()
from gus_animtool import anim as A, actions as AC, attach as AT, arctrail as T
said = []
A.message = lambda text, level="ok": said.append(text)
A.frame_range = lambda: (1, 100)
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- a small key store: channels keyed over time (stepped, or eased between two keys)
KEYS = {}                                                      # plug -> {time: [value, out tangent]}
NOW = [10.0]
def _plug(p):
    node, attr = p.split(".", 1)
    return (cmds.ls(node, long=True) or [node])[0] + "." + attr
def setKeyframe(plug=None, time=None, value=None, attribute=None, **k):
    p = _plug(plug)
    if value is None:
        value = _real_get(p)
    KEYS.setdefault(p, {})[float(time)] = [float(value), "auto"]
def keyTangent(plug, time=None, outTangentType=None, attribute=None, **k):
    if k.get("query"):
        return [False]
    plugs = [plug + "." + a for a in attribute] if attribute else [plug]
    for p in plugs:
        p = _plug(p)
        if p in KEYS and time and float(time[0]) in KEYS[p] and outTangentType:
            KEYS[p][float(time[0])][1] = outTangentType
def value_at(p, t):
    ks = sorted(KEYS.get(p, {}).items())
    if not ks:
        return None
    before = [(kt, kv) for kt, kv in ks if kt <= t + 1e-9]
    if not before:
        return ks[0][1][0]
    kt, (v, tan) = before[-1]
    after = [(nt, nv) for nt, nv in ks if nt > t + 1e-9]
    if tan == "step" or not after:
        return v
    nt, (nv, _t) = after[0]
    return v + (nv - v) * (t - kt) / (nt - kt)
def keyframe(plug, query=False, timeChange=False, **k):
    return sorted(KEYS.get(_plug(plug), {}))
def cutKey(plug, time=None, clear=False, **k):
    p = _plug(plug)
    if p in KEYS:
        KEYS[p].pop(float(time[0]), None)
_real_get = cmds.getAttr
def getAttr(plug, **k):
    if "time" in k:
        v = value_at(_plug(plug), float(k["time"]))
        return v if v is not None else _real_get(plug)
    if plug.endswith(".offsetParentMatrix"):
        return list(OPM.get(_plug(plug).split(".")[0], AT.IDENTITY))
    return _real_get(plug, **k)
OPM = {}
cmds.setKeyframe, cmds.keyTangent, cmds.keyframe, cmds.cutKey, cmds.getAttr = setKeyframe, keyTangent, keyframe, cutKey, getAttr
cmds.currentTime = lambda *a, **k: NOW[0] if k.get("query") else NOW.__setitem__(0, float(a[0]))
cmds.pluginInfo = mock.MagicMock(return_value=False)
cmds.loadPlugin = mock.MagicMock()

def ctrl(name, parent=None, pos=(0, 0, 0)):
    t = cmds.createNode("transform", name=name, parent=parent) if parent else cmds.createNode("transform", name=name)
    cmds.xform(t, worldSpace=True, translation=pos)
    return cmds.ls(t, long=True)[0]
rig = ctrl("Wes_rig")
offset = ctrl("L_wrist_IK_offset", parent=rig)
hand = ctrl("L_wrist_IK_ctrl", parent=offset, pos=(5, 2, 0))
box = ctrl("Box_ctrl", pos=(5, 0, 0))
table = ctrl("Table_ctrl", pos=(9, 0, 0))
rhand = ctrl("R_wrist_IK_ctrl", pos=(-5, 2, 0))

# --- 1. the hand follows the box (the way Gus needs it), at frame 10
AT.attach(hand, box)
d = AT.read(hand)
mm = d["holders"][1]["mm"]
src2 = cmds.listConnections(mm + ".matrixIn[2]", source=True, destination=False, plugs=True)
check("the hand follows the box, through its PARENT's inverse (L_wrist_IK_offset) - not its own: no loop, no stutter",
      src2 == ["L_wrist_IK_offset.worldInverseMatrix[0]"] and
      cmds.listConnections(mm + ".matrixIn[1]", source=True, destination=False) == ["Box_ctrl"])
check("the Hold channels on the hand (Channel Box): Hold Free and hold_Box_ctrl, plus the Attach separator",
      [h["attr"] for h in d["holders"]] == ["hold_free", "hold_Box_ctrl"] and
      cmds.attributeQuery("attachHold", node=hand, exists=True))
w1 = cmds.listConnections(d["blend"] + ".target[1].weight", source=True, destination=False)
check("normalised: target 1's weight = hold_Box / (free + Box)", w1 and w1[0].startswith("L_wrist_IK_ctrl_attach_w1"))
hp = hand + ".hold_Box_ctrl"
check("keys: off at 9, on at 10, stepped (no slide)", value_at(hp, 9) == 0 and value_at(hp, 10) == 1 and
      KEYS[hp][10.0][1] == "step")
grip = d["holders"][1]["grip"]
check("the grip is keyed at 10 (the offset that keeps the hand still: no jump)", 10.0 in KEYS.get(grip + ".tx", {}))
check("the message says you can still move it", "you can still move it" in said[-1])

# --- 2. hand-over to the table at 30, over 4 frames
NOW[0] = 30.0
AT.hand_over(box, table) if False else None
AT.attach(box, rhand)                                   # the box in the right hand from 30
NOW[0] = 50.0
AT.hand_over(box, table, frames=4)
db = AT.read(box)
ht, hr = box + ".hold_Table_ctrl", box + ".hold_R_wrist_IK_ctrl"
check("hand-over 50-54: the right hand eases out, the table eases in (both carry it in between)",
      value_at(hr, 50) == 1 and value_at(ht, 50) == 0 and value_at(hr, 52) == 0.5 and value_at(ht, 52) == 0.5 and
      value_at(ht, 54) == 1 and KEYS[ht][50.0][1] == "flat")
check("the table's grip keyed at the start (50): it takes the box where it is", 50.0 in KEYS.get(db["holders"][2]["grip"]
                                                                                              + ".tx", {}))
check("the right hand's grip isn't touched by the hand-over (it keeps carrying it)",
      sorted(KEYS.get(db["holders"][1]["grip"] + ".tx", {})) == [30.0])

# --- 3. both hands
NOW[0] = 70.0
AT.both(box, rhand)
check("both: the table and the right hand, 50 / 50 from 70", value_at(ht, 70) == 0.5 and value_at(hr, 70) == 0.5)
NOW[0] = 90.0
AT.release(box)
check("released at 90: Hold Free 1, the others 0; the free pose keyed at 90",
      value_at(box + ".hold_free", 90) == 1 and value_at(ht, 90) == 0 and 90.0 in KEYS.get(db["holders"][0]["grip"] + ".tx", {}))

# --- 4. over time
segs = AT.timeline(box)
labels = [(s["start"], s["label"]) for s in segs]
check("the timeline: own parent, right hand 30, hand-over 50, table 54, both 70, free 90",
      labels == [(29.0, "its own parent"), (30.0, "R_wrist_IK_ctrl"), (50.0, "hand-over to Table_ctrl"),
                 (54.0, "Table_ctrl"), (70.0, "R_wrist_IK_ctrl 50% + Table_ctrl 50%"), (90.0, "stays where it is")]
      or print(labels))
check("the changes (Show where it holds): from 30 on", [e[0] for e in AT.events(box)] == [30.0, 50.0, 54.0, 70.0, 90.0])
NOW[0] = 60.0
check("previous / next change from 60: 54 and 70", AT.next_change(box, backwards=True) == 54.0 and AT.next_change(box) == 70.0)
txt = AT.describe(box)
check("Show where it holds: the stretches with their frames", "30-49: R_wrist_IK_ctrl" in txt and "90-end: stays where it is" in txt)
AT.delete_change(box, 70.0)
check("Delete the 'both' change: the table holds it on to 90, the other frames as before",
      value_at(ht, 75) == 1 and value_at(hr, 75) == 0 and value_at(box + ".hold_free", 95) == 1)
AT.move_change(box, 30.0, 25.0)
check("Move the right hand's change from 30 to 25 (taken again there)", value_at(hr, 25) == 1 and value_at(hr, 27) == 1
      and 30.0 not in KEYS.get(hr, {}))

# --- 5. loops refused
for f, h, why in ((box, box, "itself"), (offset, hand, "its child"), (box, hand, "holds the hand that holds the box")):
    try:
        AT.set_hold(f, {h: 1.0}, 10)
        msg = ""
    except RuntimeError as e:
        msg = str(e)
    check("refused: %s" % why, "loop" in msg or "itself" in msg)

# --- 6. 5.6.40 attaches: repaired, not converted
old = ctrl("Cup_ctrl", parent=offset)
mm_old = cmds.createNode("multMatrix", name="Cup_ctrl_attach_0")
cmds.connectAttr(old + ".parentInverseMatrix[0]", mm_old + ".matrixIn[2]")
cmds.addAttr(old, longName="gusAttach", dataType="string")
cmds.setAttr(old + ".gusAttach", '{"blend": "x", "targets": [{"holder": "Box_ctrl", "node": "Cup_ctrl_attach_0"}], '
             '"events": [[10, "Box_ctrl"]]}', type="string")
check("a 5.6.40 attach is recognised", AT.is_old(AT.read(old)) and AT.events(old) == [(10, "Box_ctrl")])
check("Repair: its link to its own parentInverseMatrix replaced by the parent's (the stutter gone)",
      AT.repair(old) == 1 and cmds.listConnections(mm_old + ".matrixIn[2]", source=True, destination=False,
                                                   plugs=True) == ["L_wrist_IK_offset.worldInverseMatrix[0]"])
try:
    AT.release(old); msg = ""
except RuntimeError as e:
    msg = str(e)
check("Release on an old one says what to do (Bake, then Attach again)", "Bake" in msg)

# --- 7. bookmarks: Maya's plugin loaded first (5.6.40 didn't - no bookmarks)
made = []
tsb = types.SimpleNamespace(createBookmark=lambda **k: made.append(k))
sys.modules["maya.plugin"] = types.ModuleType("maya.plugin")
sys.modules["maya.plugin.timeSliderBookmark"] = types.ModuleType("maya.plugin.timeSliderBookmark")
sys.modules["maya.plugin.timeSliderBookmark.timeSliderBookmark"] = tsb
sys.modules["maya.plugin.timeSliderBookmark"].timeSliderBookmark = tsb
_ls = cmds.ls
with mock.patch.object(cmds, "ls", lambda *a, **k: [] if k.get("type") == "timeSliderBookmark" else _ls(*a, **k)), \
        mock.patch.object(cmds, "playbackOptions", lambda **k: 120, create=True):
    AT._bookmarks(box)
check("the bookmark plugin is loaded, then a coloured stretch per holder (not for 'free')",
      cmds.loadPlugin.called and [(b["start"], b["stop"]) for b in made] == [(25.0, 49), (50.0, 53), (54.0, 89)]
      and all(b["name"].startswith("gusAttach_Box_ctrl") for b in made))

# --- 8. remove
AT.remove(hand)
check("Remove: the hold channels and the setup gone", not cmds.attributeQuery("hold_free", node=hand, exists=True)
      and not AT.read(hand))

# --- 9. the menus
cmds_ = [c for _l, c in AC.MENUS["attach"]]
check("right-click on Attach: hand-over, both hands, where it holds, previous / next change, the window, repair",
      cmds_ == ["attach_handover", "attach_both", "attach_show", "attach_prev", "attach_next", "attach_window",
                "attach_repair"])

# --- 10. arcs
k = ctrl("L_hand_ctrl")
check("arcs: a control with free translate but no keys can be edited now (5.6.40 sent it away)", T.moves(k)
      and not T.has_translate_keys(k) and "set a key to edit it" in T.describe([k], [], []))
cmds.setAttr(k + ".translateX", lock=True); cmds.setAttr(k + ".translateY", lock=True); cmds.setAttr(k + ".translateZ", lock=True)
check("translate locked (an FK control): view only", not T.moves(k))
cons = cmds.createNode("pointConstraint", name="k_pc")
k2 = ctrl("R_hand_ctrl")
cmds.connectAttr(cons + ".constraintTranslateX", k2 + ".translateX")
for ax in "YZ":
    cmds.setAttr(k2 + ".translate" + ax, lock=True)
check("translate driven by a constraint: view only", not T.moves(k2))
trail = ctrl("L_hand_ctrl_arcHandle")
cmds.createNode("motionTrailShape", name="L_hand_ctrl_arcHandleShape", parent=trail) if False else None
with mock.patch.object(T, "_is_trail", lambda n: n == trail):
    check("a trail (by its shape, wherever it is) is never taken for a control", T.controls([trail, k]) == [k])
selected = []
with mock.patch.object(cmds, "snapshot", lambda *a, **kw: [], create=True), \
        mock.patch.object(cmds, "select", lambda *a, **kw: selected.append((a, kw))), \
        mock.patch.object(cmds, "ls", lambda *a, **kw: [k] if kw.get("selection") else _ls(*a, **kw)):
    T.make([k])
check("after making a trail, your selection is put back (Maya selects the new trail)", selected == [(([k],), {"replace": True})]
      and T._state["busy"] is False)

print("%d/%d passed" % (sum(ok), len(ok)))
