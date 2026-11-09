# Animtool 3.3: cycles - the half from the keys (not the frame range), re-running doesn't double, Time Slider on
# the cycle; Continue cycle repeats as keys, the root keeps going forward; loop curves without keys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
import os, sys; sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from unittest import mock
from gus_animtool import anim as A
from gus_animtool import cycle as C
from gus_animtool import keys as K

# a tiny animation store: curve -> {time: value}; curve -> attr
CURVES = {"root_tz": {1.0: 0.0, 13.0: 50.0, 25.0: 100.0}, "root_ty": {1.0: 0.0, 7.0: 5.0, 13.0: 0.0, 19.0: 5.0, 25.0: 0.0},
          "leg_rx": {1.0: 30.0, 13.0: -30.0, 25.0: 30.0}}
ATTR = {"root_tz": "translateZ", "root_ty": "translateY", "leg_rx": "rotateX"}
OWNER = {"root": ["root_tz", "root_ty"], "leg": ["leg_rx"]}
clip, infinity, info, playback = {}, {}, {}, {}

def _in(t, rng):
    return rng is None or rng[0] - 1e-6 <= t <= rng[1] + 1e-6

def keyframe(nodes=None, query=False, edit=False, name=False, timeChange=False, valueChange=False, eval=False,
             time=None, relative=False, **k):
    nodes = [nodes] if isinstance(nodes, str) else (nodes or [])
    curves = [c for n in nodes for c in (OWNER.get(n) or ([n] if n in CURVES else []))]
    if query and name:
        return curves
    if query and timeChange:
        return [t for c in curves for t in sorted(CURVES[c]) if _in(t, time)]
    if query and eval:
        c = CURVES[curves[0]]; t = time[0]; ts = sorted(c)
        if t in c: return [c[t]]
        lo = max([x for x in ts if x < t] or ts[:1]); hi = min([x for x in ts if x > t] or ts[-1:])
        return [c[lo] + (c[hi] - c[lo]) * ((t - lo) / (hi - lo) if hi != lo else 0)]
    if edit and relative:
        for c in curves:
            for t in list(CURVES[c]):
                if _in(t, time): CURVES[c][t] += valueChange
cmds.keyframe = keyframe
cmds.cutKey = lambda c, time=None, clear=False, **k: [CURVES[c].pop(t) for t in list(CURVES[c]) if _in(t, time)]
cmds.copyKey = lambda c, time=None, **k: clip.__setitem__(c, {t - time[0]: v for t, v in CURVES[c].items() if _in(t, time)})
cmds.pasteKey = lambda c, time=None, option=None, **k: CURVES[c].update({time[0] + dt: v for dt, v in clip[c].items()})
cmds.setInfinity = lambda c, **k: infinity.__setitem__(c, (k.get("preInfinite"), k.get("postInfinite")))
cmds.listConnections = lambda plug, **k: ["x.%s" % ATTR[plug.split(".")[0]]]
cmds.fileInfo = lambda *a, **k: [info[a[0]]] if k.get("query") and a[0] in info else (info.__setitem__(a[0], a[1]) if len(a) > 1 else [])
cmds.playbackOptions = lambda **k: (1.0 if k.get("query") else playback.update(k))
said = []
A.message = lambda t, level="ok": said.append(t)
K.slider_range = lambda: None
A._pose_sel = lambda: ["root", "leg"]
A.character_controls = lambda ns=None: ["root", "leg"]
A.namespace_of = lambda n: ""

# --- the half comes from the keys: 1-13 keyed -> 1-25, whatever the Time Slider says
for c in CURVES:                                   # only the first half keyed
    for t in list(CURVES[c]):
        if t > 13: CURVES[c].pop(t)
got = []
with mock.patch.object(A, "mirror_half_cycle", lambda sel, s, e, loop: got.append((s, e)) or 2):
    C.mirror()
    print("mirror range from keys 1-13:", got[-1], "| time slider:", playback.get("minTime"), "-", playback.get("maxTime"))
    for c in CURVES: CURVES[c][25.0] = CURVES[c][1.0]       # what the mirror made (loop frame)
    C.mirror()
    print("again after mirroring (keys 1-25): same half, not doubled:", got[-1])
    K.slider_range = lambda: (1.0, 9.0)
    C.mirror()
    print("highlighted 1-9 = the half:", got[-1])
    K.slider_range = lambda: None
info.clear()
CURVES.update({"root_tz": {1.0: 0.0, 13.0: 50.0, 25.0: 100.0}, "root_ty": {1.0: 0.0, 7.0: 5.0, 13.0: 0.0, 19.0: 5.0, 25.0: 0.0},
               "leg_rx": {1.0: 30.0, 13.0: -30.0, 25.0: 30.0}})
try:
    A._pose_sel = lambda: ["leg"]; OWNER["leg"] = []
    C.mirror()
except RuntimeError as e:
    print("no keys:", e)
OWNER["leg"] = ["leg_rx"]; A._pose_sel = lambda: ["root", "leg"]

# --- continue: 2 more times
print("travel tz / ty / rx:", C.travel("root_tz", 1, 25), C.travel("root_ty", 1, 25), C.travel("leg_rx", 1, 25))
C.continue_cycle(2)
print("root tz keys:", sorted(CURVES["root_tz"].items()))
print("root ty keys:", sorted(CURVES["root_ty"].items()))
print("leg rx keys:", sorted(CURVES["leg_rx"].items()))
print("infinity:", sorted(infinity.items()), "| slider:", playback.get("minTime"), "-", playback.get("maxTime"))
print(said[-1])
# running it again on the longer animation uses the whole thing as the cycle unless you highlight one
K.slider_range = lambda: (1.0, 25.0)
C.continue_cycle(1)
print("highlighted cycle 1-25, +1: last tz key", max(CURVES["root_tz"].items()), "| keys past 49 cleared:",
      max(CURVES["leg_rx"]) == 49.0 and max(CURVES["root_tz"]) == 49.0)
# not forward: the root jumps back
C.continue_cycle(1, forward=False)
print("not forward: tz at 25 / 49:", CURVES["root_tz"][25.0], CURVES["root_tz"][49.0])
K.slider_range = lambda: None
# no keys option
infinity.clear()
C.continue_with_curves()
print("loop curves:", sorted(infinity.items()))
print(said[-1])
try:
    C.continue_cycle(0)
except RuntimeError as e:
    print("0 times:", e)

# --- Slower / faster (stretch): the whole character over the Time Slider range, later keys follow, snapped
from gus_animtool import tools as TL
scaled = []
cmds.scaleKey = lambda curves, time=None, timeScale=1, timePivot=0, **k: scaled.append((sorted(curves), time, timeScale, timePivot)) or [
    CURVES[c].update({timePivot + (t - timePivot) * timeScale: CURVES[c].pop(t) for t in sorted(CURVES[c], reverse=timeScale > 1) if t >= time[0]}) for c in curves]
cmds.snapKey = lambda curves, timeMultiple=1: [CURVES[c].update({float(round(t)): CURVES[c].pop(t) for t in list(CURVES[c]) if t != round(t)}) for c in curves]
CURVES.update({"root_tz": {1.0: 0.0, 13.0: 50.0, 25.0: 100.0}, "root_ty": {1.0: 0.0, 7.0: 5.0, 13.0: 0.0, 19.0: 5.0, 25.0: 0.0},
               "leg_rx": {1.0: 30.0, 13.0: -30.0, 25.0: 30.0}})
A.selected = lambda: ["leg"]; cmds.objExists = lambda n: True
pb = {"minTime": 1.0, "maxTime": 24.0, "animationEndTime": 24.0}
cmds.playbackOptions = lambda **k: pb[[x for x in k if x != "query"][0]] if k.get("query") else pb.update(k)
TL.stretch(36)
print("stretch 1-24 -> 36 frames: scaled", scaled[-1][0], "x%.2f" % scaled[-1][2])
print("  root ty keys:", sorted(CURVES["root_ty"]), "| slider:", pb["minTime"], "-", pb["maxTime"])
print(" ", said[-1])
TL.stretch(percent=50)
print("then 50%:", sorted(CURVES["root_ty"]), "| slider:", pb["minTime"], "-", pb["maxTime"])
K.slider_range = lambda: (1.0, 6.0)
print("highlighted 1-6 range:", TL.stretch_range())
K.slider_range = lambda: None
for bad in (dict(length=1), dict()):
    try:
        TL.stretch(**bad)
    except RuntimeError as e:
        print("refused:", e)

# --- Blocking / spline: every key stepped (new keys too), back: each key's own tangent again
TAN = {c: {"in": ["auto", "flat", "linear", "auto", "spline"][:len(CURVES[c])], "out": ["auto", "flat", "linear", "auto", "spline"][:len(CURVES[c])]} for c in CURVES}
glob = {"out": "auto"}
def keyTangent(curves=None, query=False, g=False, index=None, inTangentType=None, outTangentType=None, **k):
    if g:
        if query: return [glob["out"]]
        glob["out"] = outTangentType; return None
    cs = [curves] if isinstance(curves, str) else list(curves)
    if query:
        return list(TAN[cs[0]]["in" if inTangentType else "out"])
    for c in cs:
        for i in (range(index[0], index[1] + 1) if index else range(len(TAN[c]["out"]))):
            TAN[c]["out"][i] = outTangentType
cmds.keyTangent = keyTangent
A.opt = lambda key, default: {"block_prev_out": "auto"}.get(key, default)
print("blocking ->", TL.blocking(), "| leg out:", TAN["leg_rx"]["out"], "| new keys:", glob["out"])
print("toggle   ->", TL.blocking(), "| leg out:", TAN["leg_rx"]["out"], "| new keys:", glob["out"])
print(said[-1])
