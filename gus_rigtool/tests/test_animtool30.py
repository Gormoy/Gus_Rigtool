# Gus Animtool 3.0: every action runs (or says what to do), an icon per action, the Gus_Animtool shelf, the toolbar
# under the Time Slider (and its button picker), tangents, copy / paste animation, reverse, time scale, smooth,
# noise, arcs, viewport toggles, playblast
import os, sys, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.undoInfo = mock.MagicMock()
cmds.promptDialog = mock.MagicMock(return_value="Cancel")   # the Slower / faster button asks for a length
import gus_animtool
from gus_animtool import anim as A, actions as AC, toolbar as TB, tools as TL
_opts = {"library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
said = []
A.message = lambda text, level="ok": said.append((level, text))

print("icons:", all(os.path.isfile(AC.icon(k)) for k, _l, _t, _g in AC.ACTIONS), len(AC.ACTIONS),
      "| extra icons:", all(os.path.isfile(AC.icon(k)) for k in ("update", "reload", "sets", "edit")))
print("menus point at real actions:", all(AC._call.__code__ and sub for subs in AC.MENUS.values() for _l, sub in subs))

# every action with nothing selected: a message, never a crash
cmds.select(clear=True)
cmds.getPanel = mock.MagicMock(side_effect=lambda **k: "modelPanel4" if k.get("withFocus") else ("modelPanel" if k.get("typeOf") else ["modelPanel4"]))
cmds.modelEditor = mock.MagicMock(return_value=True); cmds.isolateSelect = mock.MagicMock(return_value=0)
cmds.playblast = mock.MagicMock(return_value="movies/untitled_blast"); cmds.setFocus = mock.MagicMock()
cmds.headsUpDisplay = mock.MagicMock(return_value=[]); cmds.modelPanel = mock.MagicMock(return_value="persp"); cmds.workspace = mock.MagicMock(return_value=tempfile.gettempdir())
cmds.playbackOptions = lambda **k: 1 if k.get("minTime") else 24
cmds.workspace = lambda **k: tempfile.mkdtemp(); cmds.file = lambda **k: ""
cmds.currentTime = lambda *a, **k: 10.0
cmds.keyframe = lambda *a, **k: []                         # nothing keyed, nothing selected in the Graph Editor
skip = {"main", "picker", "poses", "clips"}
crashes = []
for k, _l, _t, _g in AC.ACTIONS:
    if k in skip:
        continue
    said[:] = []
    AC.run(k)
    if any(t.startswith("error") for _lv, t in said):
        crashes.append((k, list(said)))
for subs in AC.MENUS.values():
    for _l, sub in subs:
        said[:] = []
        AC.run(sub)
        if any(t.startswith("error") for _lv, t in said):
            crashes.append((sub, list(said)))
print("actions that crashed:", crashes)
said[:] = []; AC.run("nope"); print("unknown action:", said)

# shelf
import maya.mel as mel
mel.eval = mock.MagicMock()
made = []
cmds.shelfButton = lambda **k: made.append(k)
n = TB.make_shelf()
print("shelf buttons:", n, "| first:", made[0]["label"], "| icons:", all(b["image"].endswith(".png") for b in made),
      "| right-click menus:", sorted(b["label"] for b in made if b.get("menuItem")))
print("shelf command:", made[0]["command"])
# toolbar
cmds.workspaceControl = mock.MagicMock(side_effect=lambda *a, **k: True if k.get("exists") and a and a[0] == "TimeSlider" else (False if k.get("exists") else a[0]))
_itb = cmds.iconTextButton                              # like Maya: buttons come back as full paths
cmds.iconTextButton = lambda *a, **k: ("gusAnimtoolToolbar|" + _itb(*a, **k)) if not (k.get("exists") or k.get("query") or k.get("edit")) else _itb(*a, **k)
TB.show()
cmds.iconTextButton = _itb
args = [c for c in cmds.workspaceControl.call_args_list if c.kwargs.get("label")][-1]
print("toolbar docked under the Time Slider:", args.kwargs.get("dockToControl"), "| buttons:",
      sum(1 for v in UI.values() if v.get("kind") == "iconTextButton" and v.get("parent") == TB.BP + "Row"),
      "| right-click menus:", sum(1 for v in UI.values() if v.get("kind") == "popupMenu" and str(v.get("parent", "")).startswith("gusAnimtoolToolbar|")),
      "| tween slider:", TB.BP + "Tween" in UI)
_opts["toolbar_keys"] = "key,mirror,bogus,playblast"
print("chosen buttons:", TB.keys_shown())
from gus_animtool import ui
cmds.window = mock.MagicMock(return_value=False); cmds.showWindow = mock.MagicMock()
ui._toolbar_pick()
print("button picker lists every action:", sum(1 for v in UI.values() if v.get("kind") == "checkBox" and v.get("parent", "").startswith("rowLayout")) >= len(AC.ACTIONS))

# --- tools with a tiny key store
c = cmds.createNode("transform", name="L_hand_ctrl"); cmds.createNode("nurbsCurve", name="L_hand_ctrlShape", parent=c)
d = cmds.createNode("transform", name="R_hand_ctrl"); cmds.createNode("nurbsCurve", name="R_hand_ctrlShape", parent=d)
KEYS = {"L_hand_ctrl_translateX": {"node": "L_hand_ctrl", "attr": "translateX", "keys": [[0, 1.0, "auto", "auto"], [10, 5.0, "linear", "step"]]}}
SET = []
def keyframe(*a, **k):
    target = a[0] if a else None
    if k.get("name"):
        if k.get("selected"):
            return []
        names = target if isinstance(target, list) else [target]
        return [cn for cn, cv in KEYS.items() if any(A.short(x).endswith(cv["node"]) for x in names)]
    cv = KEYS.get(target)
    if cv is None:
        if k.get("keyframeCount"):
            return 1
        return []
    if k.get("timeChange"):
        return [x[0] for x in cv["keys"]]
    if k.get("valueChange"):
        return [x[1] for x in cv["keys"]]
    return []
cmds.keyframe = keyframe
cmds.keyTangent = mock.MagicMock(side_effect=lambda c=None, **k: ([x[2] for x in KEYS[c]["keys"]] if k.get("inTangentType") is True else [x[3] for x in KEYS[c]["keys"]]) if k.get("query") else None)
cmds.listConnections = (lambda real: lambda n, **k: [KEYS[n.split(".")[0]]["node"] + "." + KEYS[n.split(".")[0]]["attr"]] if n.split(".")[0] in KEYS else real(n, **k))(cmds.listConnections)
cmds.setKeyframe = lambda n, attribute=None, time=None, value=None, **k: SET.append((A.short(n), attribute, time, value))
cmds.cutKey = mock.MagicMock()
cmds.select(c)
print("copied curves:", TL.copy_animation())
cmds.select(d)
print("pasted on the other hand (one copied -> any):", TL.paste_animation(), SET)
SET[:] = []; TL.paste_animation(at_current=True); print("at the current frame (10):", [s[2] for s in SET])
cmds.scaleKey = mock.MagicMock(); cmds.snapKey = mock.MagicMock()
TL.reverse([c]); print("reverse:", cmds.scaleKey.call_args.kwargs)
TL.time_scale(2.0, [c]); print("time scale:", cmds.scaleKey.call_args.kwargs, "| snapped:", cmds.snapKey.called)
cmds.keyTangent = mock.MagicMock()
cmds.keyframe = lambda *a, **k: (1 if k.get("keyframeCount") else [])
cmds.select(c)
print("tangents at this frame:", TL.tangents("step"), cmds.keyTangent.call_args.kwargs)
# smooth / noise on selected keys
CUR = {"cv1": [[0, 0.0, True], [1, 10.0, True], [2, 0.0, True]]}
def kf(*a, **k):
    if k.get("query"):
        if k.get("name"):
            return list(CUR)
        cv = CUR[a[0]]
        if k.get("indexValue"):
            return [i for i, x in enumerate(cv) if x[2]]
        if k.get("valueChange"):
            return [x[1] for x in cv]
        return []
    i = k["index"][0]
    if k.get("absolute"):
        CUR[a[0]][i][1] = k["valueChange"]
    else:
        CUR[a[0]][i][1] += k["valueChange"]
cmds.keyframe = kf
print("smooth:", TL.smooth(), [x[1] for x in CUR["cv1"]])
print("noise:", TL.noise(0.1, seed=1), [round(x[1], 3) for x in CUR["cv1"]])
# arcs / view / playblast
cmds.snapshot = mock.MagicMock(return_value=["L_hand_ctrl_arcHandle", "L_hand_ctrl_arc"])
cmds.nodeType = (lambda real: lambda n, **k: "transform" if "arc" in str(n) else real(n, **k))(cmds.nodeType)
cmds.createNode("transform", name="L_hand_ctrl_arcHandle"); cmds.createNode("transform", name="L_hand_ctrl_arc")
print("arcs:", len(TL.arcs([c])), cmds.snapshot.call_args.kwargs.get("motionTrail"), "| cleared:", TL.clear_arcs(), cmds.objExists(TL.ARCS))
print("hide controls:", TL.toggle_controls(), cmds.modelEditor.call_args.kwargs)
mel.eval = mock.MagicMock(); cmds.select(c)
print("isolate:", TL.toggle_isolate(), mel.eval.call_args[0][0])
print("playblast:", TL.playblast(50), cmds.playblast.call_args.kwargs.get("percent"), cmds.playblast.call_args.kwargs.get("startTime"))
print("version:", gus_animtool.__version__)
