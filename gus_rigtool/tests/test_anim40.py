# Animtool 4.0: overlap (spring maths and the bake), cycle in place <-> forward, bake / reduce keys, playblast
# with HUD (versions, Maya's HUDs back after)
import os, sys, math, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
from gus_animtool import motion as M
said = []
A.message = lambda t, level="ok": said.append(t)
cmds.undoInfo = mock.MagicMock(); cmds.refresh = mock.MagicMock()

# --- overlap maths
ax, ang = M.arc([1, 0, 0], [0, 1, 0])
print("arc x->y:", [round(v, 3) for v in ax], round(math.degrees(ang), 1))
print("rotate x by it:", [round(v, 3) for v in M.rotate([1, 0, 0], ax, ang)])
goals = [[[float(f), 0.0, 0.0]] for f in range(30)] + [[[30.0, 0.0, 0.0]] for _ in range(30)]   # moves, then stops
sim = M.springs(goals, [0.3], 0.35)
lag = [round(goals[i][0][0] - sim[i][0][0], 2) for i in (5, 20, 29)]
print("spring lags while moving:", lag, "| overshoots after stopping:", max(s[0][0] for s in sim[30:]) > 30.0,
      "| settles:", abs(sim[-1][0][0] - 30.0) < 0.05)
loop = [[[math.sin(2 * math.pi * f / 24.0) * 10, 0.0, 0.0]] for f in range(25)]
once = M.springs(loop, [0.3], 0.35)
twice = M.springs(loop, [0.3], 0.35, cycle=True)
print("cycle: the loop frame matches the first:", twice[-1] == twice[0], "| without: off by",
      round(abs(once[0][0][0] - once[-1][0][0]), 2))

# --- overlap bake on a 3-control chain moving sideways (fake world matrices)
T = [0.0]
chain_ = ["tail_01_ctrl", "tail_02_ctrl", "tail_03_ctrl"]
def world(n):
    i = chain_.index(n)
    x = 5.0 * math.sin(T[0] / 4.0)                      # the whole chain swings sideways
    return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, 0, -10.0 * i, 1]
A.world = world
turned = []
A.set_world = lambda n, m, translate=True, rotate=True: turned.append((n, T[0]))
keyed = []
cmds.currentTime = lambda *a, **k: T[0] if k.get("query") else T.__setitem__(0, float(a[0]))
cmds.setKeyframe = lambda n, attribute=None, time=None, **k: keyed.append((n, time))
A._settable = lambda p: True
A.time_curves = lambda nodes: []
n = M.overlap(chain_, 1, 24)
print("overlap: controls", n, "| keyed frames per control:", len([k for k in keyed if k[0] == chain_[0]]),
      "| turned (some frames):", len(turned) > 0, "| current frame back to where it was:", T[0] == 0.0)
print(said[-1])
try:
    M.overlap(chain_, 1, 2)
except RuntimeError as e:
    print("refused:", e)

# --- curves store for cycles / reduce
CURVES = {}
ATTR = {}
OWNER = {}
def keyframe(nodes=None, query=False, edit=False, name=False, timeChange=False, valueChange=False, eval=False,
             time=None, relative=False, **k):
    nodes = [nodes] if isinstance(nodes, str) else (nodes or [])
    curves = [c for n in nodes for c in (OWNER.get(n) or ([n] if n in CURVES else []))]
    rng = lambda t: time is None or time[0] - 1e-6 <= t <= time[1] + 1e-6
    if query and name: return curves
    if query and timeChange: return [t for c in curves for t in sorted(CURVES[c]) if rng(t)]
    if query and eval:
        c = CURVES[curves[0]]; t = time[0]; ts = sorted(c)
        if t in c: return [c[t]]
        lo = max([x for x in ts if x < t] or ts[:1]); hi = min([x for x in ts if x > t] or ts[-1:])
        return [c[lo] + (c[hi] - c[lo]) * ((t - lo) / (hi - lo) if hi != lo else 0)]
    if query and valueChange: return [CURVES[c][t] for c in curves for t in sorted(CURVES[c]) if rng(t)]
    if edit and relative:
        for c in curves:
            for t in list(CURVES[c]):
                if rng(t): CURVES[c][t] += valueChange
cmds.keyframe = keyframe
cmds.listConnections = lambda plug, **k: ["root_ctrl.%s" % ATTR[plug.split(".")[0]]]
inf = {}
cmds.setInfinity = lambda c, **k: inf.__setitem__(c, k.get("postInfinite"))
cmds.nodeType = lambda n: "animCurveTL" if n in CURVES else "transform"
from gus_animtool import cycle as C
from gus_animtool import keys as K
del A.time_curves
import importlib; importlib.reload(A); A.message = lambda t, level="ok": said.append(t)
K.slider_range = lambda: None
CURVES.update({"root_tz": {1.0: 0.0, 13.0: 50.0, 25.0: 100.0}, "root_ty": {1.0: 0.0, 7.0: 5.0, 13.0: 0.0, 19.0: 5.0, 25.0: 0.0}})
ATTR.update({"root_tz": "translateZ", "root_ty": "translateY"}); OWNER["root_ctrl"] = ["root_tz", "root_ty"]
C._scope = lambda nodes: ["root_ctrl"]
print("in place:", C.in_place(), "| tz:", sorted(CURVES["root_tz"].items()), "| ty untouched:",
      CURVES["root_ty"][7.0] == 5.0, "| infinity:", inf.get("root_tz"))
try:
    C.in_place()
except RuntimeError as e:
    print("twice:", e)
A.selected = lambda: []
cmds.objExists = lambda n: n in CURVES or n == C.TRAVEL_NODE
print("forward:", C.forward(), "| tz:", sorted(CURVES["root_tz"].items()), "| infinity:", inf.get("root_tz"))
try:
    C.forward()
except RuntimeError as e:
    print("forward again:", e)

# --- reduce: a dense straight-then-bump curve
dense = {float(f): (f * 2.0 if f <= 10 else 20.0 + 10 * math.sin((f - 10) / 10.0 * math.pi)) for f in range(0, 21)}
CURVES["c_dense"] = dict(dense); ATTR["c_dense"] = "translateX"; OWNER["ctl"] = ["c_dense"]
def cutKey(c, time=None, clear=True, **k):
    for t in list(CURVES[c]):
        if time[0] - 1e-6 <= t <= time[1] + 1e-6: CURVES[c].pop(t)
cmds.cutKey = cutKey
cmds.setKeyframe = lambda c, time=None, value=None, **k: CURVES[c].__setitem__(float(time), value)
cmds.keyTangent = lambda *a, **k: ["auto"] if k.get("query") else None
K.scope_curves = lambda scope=None: ["c_dense"]
gone, before = K.reduce_keys(0.01)
print("reduce 1%%: %d of %d gone | kept:" % (gone, before), sorted(CURVES["c_dense"]), "| peak kept:", 15.0 in CURVES["c_dense"])
worst = max(abs(keyframe("c_dense", query=True, eval=True, time=(f, f))[0] - v) for f, v in dense.items())
print("worst change: %.3f (limit %.3f)" % (worst, 0.01 * (max(dense.values()) - min(dense.values()))))

# --- bake
baked = []
cmds.bakeResults = lambda plugs, **k: baked.append((plugs, k.get("time"), k.get("sampleBy"), k.get("preserveOutsideKeys")))
A.frame_range = lambda: (1, 24)
K.bake(2)
print("bake:", baked[-1])

# --- playblast with HUD
from gus_animtool import tools as TL
folder = tempfile.mkdtemp()
open(os.path.join(folder, "shot010_v001.mov"), "w").close()
print("next version:", os.path.basename(TL.next_version(folder, "shot010")))
huds = {"HUDFrameRate": True, "HUDCameraNames": True, "HUDObjectDetails": False}
def headsUpDisplay(*a, **k):
    if k.get("listHeadsUpDisplays"): return list(huds)
    if k.get("nextFreeBlock") is not None: return 1
    name = a[0] if a else None
    if k.get("exists"): return name in huds
    if k.get("remove"): huds.pop(name, None); return None
    if k.get("query") and k.get("visible"): return huds[name]
    if k.get("edit"): huds[name] = k["visible"]; return None
    huds[name] = True                                       # made
cmds.headsUpDisplay = headsUpDisplay
cmds.getPanel = lambda **k: "modelPanel4" if k.get("withFocus") or k.get("typeOf") is None else "modelPanel"
cmds.getPanel = lambda **k: ("modelPanel4" if k.get("withFocus") else ("modelPanel" if k.get("typeOf") else ["modelPanel4"]))
cmds.modelPanel = lambda *a, **k: "persp"
cmds.listRelatives = lambda *a, **k: ["perspShape"]
cmds.getAttr = lambda p: 35.0
cmds.setFocus = lambda *a: None
during = {}
def playblast(**k):
    during.update(ours=sorted(h for h in huds if h.startswith(TL.HUD)), mayas=[h for h, v in huds.items() if v and not h.startswith(TL.HUD)],
                  file=os.path.basename(k["filename"]), ornaments=k["showOrnaments"])
    return k["filename"]
cmds.playblast = playblast
TL.blast_settings = lambda: {"shot": "shot010", "artist": "gus", "folder": folder, "hud": True, "scale": 50}
TL.playblast()
print("during the blast:", during)
print("after: ours gone:", not any(h.startswith(TL.HUD) for h in huds), "| Maya's back:", huds)
