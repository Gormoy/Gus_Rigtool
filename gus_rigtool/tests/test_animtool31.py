# Gus Animtool 3.1: copy / paste keys (this frame = the pose, or the Time Slider's highlighted range; replace or
# merge; by name), add / remove inbetweens (selection / character / everything), offset (same / cascade) and back to
# original (saved in the scene), the Time Slider's right-click menu, the new hotkeys
import os, sys, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.undoInfo = mock.MagicMock()
NOW = [10.0]
CUR = {}                                             # curve -> {"node", "attr", "keys": {t: [v, itt, ott]}}
def _node_curves(n):
    s = A.short(n)
    return [c for c, d in CUR.items() if d["node"] == s]
def _targets(a):
    if not a:
        return list(CUR)
    items = a[0] if isinstance(a[0], (list, tuple)) else [a[0]]
    out = []
    for x in items:
        out += [x] if x in CUR else _node_curves(x)
    return out
def keyframe(*a, **k):
    curves = _targets(a)
    if k.get("attribute"):
        curves = [c for c in curves if CUR[c]["attr"] == k["attribute"]]
    t = k.get("time")
    inside = lambda x: (t is None) or (t[0] <= x <= t[1])
    if k.get("query"):
        if k.get("name"):
            return [c for c in curves if CUR[c]["keys"]]
        if k.get("keyframeCount"):
            return sum(1 for c in curves for x in CUR[c]["keys"] if inside(x))
        if k.get("timeChange"):
            return [x for c in curves for x in sorted(CUR[c]["keys"]) if inside(x)]
        if k.get("valueChange"):
            return [CUR[c]["keys"][x][0] for c in curves for x in sorted(CUR[c]["keys"]) if inside(x)]
        return []
    if k.get("edit") and k.get("relative"):
        for c in curves:
            CUR[c]["keys"] = {(x + k["timeChange"] if inside(x) else x): v for x, v in CUR[c]["keys"].items()}
cmds.keyframe = keyframe
def keyTangent(*a, **k):
    curves = _targets(a)
    t = k.get("time")
    if k.get("query"):
        idx = 1 if k.get("inTangentType") else 2
        return [CUR[c]["keys"][x][idx] for c in curves for x in sorted(CUR[c]["keys"]) if t is None or t[0] <= x <= t[1]]
    for c in curves:
        if k.get("attribute") and CUR[c]["attr"] != k["attribute"]:
            continue
        for x in CUR[c]["keys"]:
            if t is None or t[0] <= x <= t[1]:
                CUR[c]["keys"][x][1:] = [k.get("inTangentType", "auto"), k.get("outTangentType", "auto")]
cmds.keyTangent = keyTangent
def setKeyframe(n, attribute=None, time=None, value=None, **k):
    s = A.short(n)
    name = "%s_%s" % (s, attribute)
    CUR.setdefault(name, {"node": s, "attr": attribute, "keys": {}})["keys"][time] = [value, "auto", "auto"]
cmds.setKeyframe = setKeyframe
def cutKey(*a, **k):
    for c in _targets(a):
        if k.get("attribute") and CUR[c]["attr"] != k["attribute"]:
            continue
        t = k.get("time") or (-1e9, 1e9)
        CUR[c]["keys"] = {x: v for x, v in CUR[c]["keys"].items() if not (t[0] <= x <= t[1])}
cmds.cutKey = cutKey
_lc = cmds.listConnections
cmds.listConnections = lambda n, **k: ["%s.%s" % (CUR[n.split(".")[0]]["node"], CUR[n.split(".")[0]]["attr"])] \
    if n.split(".")[0] in CUR else _lc(n, **k)
cmds.currentTime = lambda *a, **k: NOW[0] if k.get("query") else NOW.__setitem__(0, float(a[0]))
cmds.referenceQuery = lambda *a, **k: False
_oe = cmds.objExists
cmds.objExists = lambda n: n in CUR or _oe(n)
_ls = cmds.ls
cmds.ls = lambda *a, **k: list(CUR) if k.get("type") and "animCurveTL" in k["type"] else _ls(*a, **k)
from gus_animtool import anim as A, keys as K, actions as AC
_opts = {"library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
def ctrl(name):
    t = cmds.createNode("transform", name=name); cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
a, b, c = ctrl("L_arm_ctrl"), ctrl("R_arm_ctrl"), ctrl("tail_ctrl")
A.character_controls = lambda ns=None: [a, b, c]
def keys_of(n, attr):
    d = CUR.get("%s_%s" % (A.short(n), attr))
    return sorted((x, round(v[0], 2)) for x, v in d["keys"].items()) if d else []
for t, v in ((0, 0.0), (10, 5.0), (20, 2.0)):
    setKeyframe(a, "translateX", t, v)
setKeyframe(c, "rotateZ", 0, 0.0); setKeyframe(c, "rotateZ", 20, 30.0)
# copy this frame (a key there + the pose of the other channels), paste on the twin at 30
cmds.timeControl = lambda *x, **k: False
import maya.mel as mel; mel.eval = lambda s: "timeSlider"
cmds.setAttr(a + ".ty", 3.0)
cmds.select(a); NOW[0] = 10.0
print("copied at 10:", K.copy_keys())
cmds.select(b); NOW[0] = 30.0
print("pasted on the twin at 30:", K.paste_keys(), "| tx:", keys_of(b, "translateX"), "| ty (the pose):", keys_of(b, "translateY"))
# a highlighted range: 0..20 -> pasted at 40, spacing kept; replace clears what was there
cmds.timeControl = lambda *x, **k: True if k.get("rangeVisible") else [0.0, 21.0]
cmds.select(a); NOW[0] = 15.0
print("slider range:", K.slider_range(), "| copied:", K.copy_keys())
setKeyframe(b, "translateX", 45, 99.0)
cmds.select(b); NOW[0] = 40.0
K.paste_keys(merge=False)
print("range pasted at 40 (the key at 45 replaced):", keys_of(b, "translateX"))
setKeyframe(b, "translateX", 45, 99.0); K.paste_keys(merge=True)
print("merge keeps it:", (45.0, 99.0) in keys_of(b, "translateX") or (45, 99.0) in keys_of(b, "translateX"))
cmds.select(clear=True)
try:
    K.paste_keys()
except RuntimeError as e:
    print("nothing selected:", e)
# inbetweens
cmds.timeControl = lambda *x, **k: False
cmds.select(a); NOW[0] = 5.0
K.inbetween(2, "selection"); print("add 2 after 5 (selection):", keys_of(a, "translateX"), "| tail untouched:", keys_of(c, "rotateZ"))
K.inbetween(-2, "selection"); print("remove 2:", keys_of(a, "translateX"))
K.inbetween(1, "character"); print("character: arm", keys_of(a, "translateX")[1:], "| tail", keys_of(c, "rotateZ"))
K.inbetween(-1, "scene"); print("everything:", keys_of(a, "translateX")[1:], keys_of(c, "rotateZ"))
# offset: cascade base to tip, back to original (saved in the scene)
cmds.select(a, c)
print("offset cascade:", K.offset(3, "cascade"), "| arm (first stays):", keys_of(a, "translateX")[0], "| tail +3:", keys_of(c, "rotateZ"))
print("same:", K.offset(2, "same"), "| arm", keys_of(a, "translateX")[0], "| tail", keys_of(c, "rotateZ")[0])
print("remembered in the scene:", cmds.objExists(K.OFFSET_NODE), K._offsets())
print("back to original:", K.back_to_original(), "| arm", keys_of(a, "translateX")[0], "| tail", keys_of(c, "rotateZ"))
K.offset(4, "same", [c]); K.keep_as_original()
try:
    K.back_to_original()
except RuntimeError as e:
    print("kept as original:", e, keys_of(c, "rotateZ"))
# actions / Time Slider menu / hotkeys
said = []
A.message = lambda text, level="ok": said.append((level, text))
for key in ("copy_keys", "paste_keys", "paste_merge", "inbetween_add", "inbetween_remove", "scope_2", "offset_plus",
            "offset_minus", "omode_2", "offset_back", "offset_keep", "copy_anim", "paste_anim"):
    said[:] = []; cmds.select(a); AC.run(key)
    print("  %-17s %s" % (key, said[-1] if said else ""))
from gus_animtool import timeslider as TS
cmds.popupMenu = mock.MagicMock(side_effect=lambda *x, **k: (x and x[0] == "TimeSliderMenu") if k.get("exists") else ("updateTimeSliderMenu TimeSliderMenu" if k.get("query") else None))
made = []
cmds.menuItem = lambda *x, **k: (made.append(x[0]) if x else made.append(k.get("label"))) if not k.get("exists") else (x[0] in made)
cmds.setParent = lambda *x, **k: None
print("time slider menu hooked:", TS.install(), "| nothing of ours before Maya builds its own:", TS.SUB not in made)
pm = [c_ for c_ in cmds.popupMenu.call_args_list if c_.kwargs.get("edit")][-1].kwargs["postMenuCommand"]
made[:] = []; mel.eval = mock.MagicMock()
pm(); print("menu opens: Maya's own command first:", mel.eval.call_args[0][0], "| then ours at the end:", TS.SUB in made,
           [m for m in made if m and m not in (TS.SUB, TS.DIV)][:3])
TS._state["menu"] = None; made[:] = [TS.DIV, TS.SUB]
cmds.popupMenu = mock.MagicMock(side_effect=lambda *x, **k: (x and x[0] == "TimeSliderMenu") if k.get("exists") else (["TimeSliderMenu|" + TS.DIV, "TimeSliderMenu|" + TS.SUB] if k.get("itemArray") else None))
_del = []; cmds.deleteUI = lambda n, **k: _del.append(n)
TS.install(); print("a menu left with only ours (3.1.0) is emptied for Maya:", sorted(_del))
_opts["timeslider_menu"] = 0; TS._state["menu"] = None; print("turned off:", TS.install())
from gus_animtool import hotkeys
print("new hotkeys:", [(k[3], k[4]) for k in hotkeys.KEYS if "Inbetween" in k[0]])
print("toolbar keeps old choices:", __import__("gus_animtool.toolbar", fromlist=["x"]).keys_shown() if not _opts.update({"toolbar_keys": "copy_anim,paste_anim,offset,key"}) else None)
