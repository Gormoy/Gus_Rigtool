# Gus Animtool 2.1: push / pull / negate / delete redundant on the selected Graph Editor keys (pivot left / right /
# last), their hotkeys, selection sets in the rig profile, temporary spaces (world / camera / pivot, bake back),
# rotate order convert
import os, sys, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
# a tiny Graph Editor: curve -> [[time, value, selected]]
CURVES = {}
def keyframe(*a, **k):
    names = [a[0]] if a and isinstance(a[0], str) else (a[0] if a else list(CURVES))
    if k.get("lastSelected"):
        last = [x for c in CURVES.values() for x in c if x[2]]
        return [last[-1][1]] if last else []
    out = []
    for c in names:
        keys = CURVES.get(c, [])
        if k.get("name"):
            if any(x[2] for x in keys):
                out.append(c)
            continue
        if k.get("time"):
            keys = [x for x in keys if k["time"][0] <= x[0] <= k["time"][1]]
        if k.get("selected"):
            idx = [i for i, x in enumerate(keys) if x[2]]
        else:
            idx = list(range(len(keys)))
        if k.get("indexValue"):
            out += idx
        elif k.get("timeChange"):
            out += [keys[i][0] for i in idx]
        elif k.get("valueChange"):
            out += [keys[i][1] for i in idx]
    return out
def scaleKey(c, index=None, valuePivot=0.0, valueScale=1.0):
    x = CURVES[c][index[0]]
    x[1] = valuePivot + (x[1] - valuePivot) * valueScale
def cutKey(c, time=None, clear=False):
    CURVES[c][:] = [x for x in CURVES[c] if not (time[0] <= x[0] <= time[1])]
cmds.keyframe, cmds.scaleKey, cmds.cutKey = keyframe, scaleKey, cutKey
cmds.undoInfo = mock.MagicMock()
import gus_animtool
from gus_animtool import anim as A, keys as K
_opts = {"library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
def setup():
    CURVES.clear()
    CURVES["c_tx"] = [[0, 0.0, False], [5, 10.0, True], [10, 4.0, True], [15, 2.0, False]]
    CURVES["c_ry"] = [[0, 30.0, False], [5, 50.0, True], [10, 30.0, False]]
def vals(c):
    return [round(x[1], 3) for x in CURVES[c]]
setup(); K.push_pull("pull", 0.5, "left")
print("pull 0.5 around the key on the left:", vals("c_tx"), vals("c_ry"))
setup(); K.push_pull("push", 0.5, "right")
print("push 0.5 around the key on the right:", vals("c_tx"), vals("c_ry"))
setup(); K.negate("left")
print("negate around the left key:", vals("c_tx"), vals("c_ry"))
setup(); K.negate("last")
print("negate around the last selected key (50):", vals("c_tx"), vals("c_ry"))
_opts.update({"pushpull_factor": 0.9, "pushpull_pivot": 1})
setup(); K.push_pull("pull")
print("pull with the Settings (0.9, left):", vals("c_tx"))
CURVES.clear()
CURVES["c_tz"] = [[0, 1.0, True], [5, 1.0, True], [10, 1.0, True], [15, 1.0, False], [20, 3.0, True], [25, 3.0, True]]
print("delete redundant:", K.delete_redundant(), "| keys left at:", [x[0] for x in CURVES["c_tz"]])
CURVES.clear()
try:
    K.negate()
except RuntimeError as e:
    print("nothing selected:", e)
# hotkeys
cmds.hotkeySet = mock.MagicMock(side_effect=lambda *a, **k: "Maya_Default" if k.get("current") and k.get("query") else (False if k.get("exists") else None))
cmds.runTimeCommand = mock.MagicMock(return_value=False); cmds.nameCommand = mock.MagicMock(); cmds.hotkey = mock.MagicMock()
from gus_animtool import hotkeys
hotkeys.install()
print("hotkeys:", sorted((c.kwargs["keyShortcut"], c.kwargs["shiftModifier"]) for c in cmds.hotkey.call_args_list))
# selection sets
from gus_animtool import selsets as SS
a = cmds.createNode("transform", name="L_lip_ctrl"); cmds.createNode("nurbsCurve", name="L_lip_ctrlShape", parent=a)
b = cmds.createNode("transform", name="R_lip_ctrl"); cmds.createNode("nurbsCurve", name="R_lip_ctrlShape", parent=b)
print("saved set:", SS.save("mouth", [a, b], ""), "| sets:", SS.names(""), "| in the profile file:", A.profile("").get("sets"))
cmds.select(clear=True); SS.select("mouth", ns="")
print("selected by the set:", sorted(A.short(n) for n in cmds.ls(selection=True)))
SS.remove("mouth", ""); print("after remove:", SS.names(""))
try:
    SS.save("  ", [a], "")
except RuntimeError as e:
    print("no name:", e)
# temporary spaces
from gus_animtool import tempspace as TS
BAKED = []
cmds.bakeResults = lambda nodes, **k: BAKED.append(sorted(A.short(n) for n in nodes))
cmds.playbackOptions = lambda **k: 1 if k.get("minTime") else 24
cmds.getPanel = mock.MagicMock(side_effect=lambda **k: "modelPanel4" if k.get("withFocus") else "modelPanel")
cmds.modelPanel = mock.MagicMock(return_value="shotCam")
cmds.createNode("transform", name="shotCam")
cmds.select(a, b)
locs = TS.world()
print("world locators:", [A.short(l) for l in locs], "| baked:", BAKED[-1],
      "| lip follows its locator:", cmds.parentConstraint(cmds.listRelatives(a, type="parentConstraint")[0], query=True, targetList=True))
print("temp nodes:", sorted((A.short(l), [A.short(n) for n in ns]) for l, ns in TS.temp_nodes()))
print("bake back:", TS.bake_back(), "| baked:", BAKED[-1], "| constraints left on the lip:",
      cmds.listRelatives(a, type="parentConstraint"), "| helpers left:", cmds.objExists(TS.TOP))
cmds.select(a)
TS.camera()
cam_grp = cmds.ls("camera_space_grp", long=True)[0]
print("camera space: group under", A.short(cmds.listRelatives(cam_grp, parent=True)[0]), "follows",
      cmds.parentConstraint(cmds.listRelatives(cam_grp, type="parentConstraint")[0], query=True, targetList=True))
TS.bake_back()
cmds.select(a, b)
loc = TS.pivot()
print("pivot:", A.short(loc), "drives", [cmds.parentConstraint(cmds.listRelatives(n, type="parentConstraint")[0], query=True, targetList=True) for n in (a, b)])
TS.bake_back(); print("all gone:", cmds.objExists(TS.TOP), cmds.listRelatives(a, type="parentConstraint"))
try:
    TS.bake_back()
except RuntimeError as e:
    print("nothing to bake:", e)
# rotate order
cmds.filterCurve = mock.MagicMock()
cmds.setKeyframe = mock.MagicMock()
cmds.currentTime = mock.MagicMock(return_value=1.0)
CURVES.clear()
cmds.setAttr(a + ".rotate", 30, 40, 50)
before = A.world(a)
print("converted:", K.convert_rotate_order([a], "zxy"), "| order:", cmds.getAttr(a + ".rotateOrder"),
      "| same world pose:", all(abs(x - y) < 1e-4 for x, y in zip(before, A.world(a))),
      "| rotate now:", [round(v, 2) for v in cmds.getAttr(a + ".rotate")[0]])
print("already that order:", K.convert_rotate_order([a], "zxy"))
