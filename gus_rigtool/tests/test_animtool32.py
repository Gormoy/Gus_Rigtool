# Gus Animtool 3.2: attach props (follow / release / bake, both directions, stepped weight keys, no-jump offsets),
# mirror half cycle (first half mirrored onto the second, loop frame, cycle infinity), the hider (parts from names,
# hide / only / add / reset in the rig profile), the animation library (save, apply replace / merge / insert /
# mirrored), ghosts, crash backup
import os, sys, json, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.undoInfo = mock.MagicMock()
from gus_animtool import anim as A
_opts = {"library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
said = []
A.message = lambda text, level="ok": said.append(text)
NOW = [10.0]
cmds.currentTime = lambda *a, **k: NOW[0] if k.get("query") else NOW.__setitem__(0, float(a[0]))
def ctrl(name, parent=None, pos=(0, 0, 0)):
    t = cmds.createNode("transform", name=name, parent=parent) if parent else cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    cmds.xform(t, worldSpace=True, translation=pos)
    return cmds.ls(t, long=True)[0]
# --- attach
from gus_animtool import attach as AT
box = ctrl("box_ctrl", pos=(5, 0, 0)); hand = ctrl("L_hand_IK_ctrl", pos=(5, 2, 0)); table = ctrl("table_ctrl", pos=(9, 0, 0))
I = list(AT.IDENTITY)
_get = cmds.getAttr
cmds.getAttr = lambda plug, **k: list(I) if plug.split(".")[-1] in ("offsetParentMatrix", "parentMatrix[0]") else _get(plug, **k)
KEYS = []
cmds.setKeyframe = lambda plug, time=None, value=None, **k: KEYS.append((plug.split(".", 1)[1], time, value))
cmds.keyTangent = mock.MagicMock()
cmds.select(box, hand)
AT.attach()
d = AT.read(box)
print("attached:", said[-1], "| blend on the box:", cmds.listConnections(box + ".offsetParentMatrix", source=True, destination=False))
print("target 0 follows:", cmds.listConnections(d["targets"][0]["node"] + ".matrixIn[1]", source=True, destination=False),
      "| through the box's parent inverse:", bool(cmds.listConnections(d["targets"][0]["node"] + ".matrixIn[2]", source=True, destination=False)))
print("weight keys:", KEYS)
KEYS[:] = []; NOW[0] = 30.0
cmds.select(box, table); AT.attach()
print("then the table at 30:", [k for k in KEYS], "| events:", AT.events(box))
KEYS[:] = []; NOW[0] = 45.0
cmds.select(box); AT.release()
print("released at 45:", sorted(set(k[2] for k in KEYS if k[1] == 45.0)), "| events:", AT.events(box))
# the other way: the hand follows the box
cmds.select(hand, box); AT.attach()
print("the hand follows the box:", AT.read(hand)["targets"][0]["holder"], "| attached:", sorted(A.short(n) for n in AT.attached()))
try:
    cmds.select(box, box); AT.attach(box, box)
except RuntimeError as e:
    print("itself:", e)
AT.remove(hand)
print("removed (no bake): attr gone:", not AT.read(hand), "| blend gone:", not cmds.objExists("L_hand_IK_ctrl_attach_blend"))
# --- mirror half cycle
from gus_animtool import keys as K
lft, rgt, hip = ctrl("L_leg_ctrl", pos=(2, 0, 0)), ctrl("R_leg_ctrl", pos=(-2, 0, 0)), ctrl("hips_ctrl", pos=(0, 5, 0))
CK = []
cmds.setKeyframe = lambda n, attribute=None, time=None, value=None, **k: CK.append((A.short(n), attribute, time))
cmds.cutKey = mock.MagicMock(); cmds.filterCurve = mock.MagicMock(); cmds.refresh = mock.MagicMock()
cmds.setInfinity = mock.MagicMock()
_lc0 = cmds.listConnections
cmds.listConnections = lambda n, **k: [] if isinstance(n, list) else _lc0(n, **k)
cmds.keyframe = lambda *a, **k: ([0.0, 6.0, 12.0, 18.0, 24.0] if k.get("timeChange") else ["c1", "c2"]) if k.get("query") else None
A._frames = lambda nodes, s, e, keys_only: [f for f in (1.0, 7.0, 13.0, 19.0) if s <= f <= e]
A.twin_of = lambda n: cmds.ls({"L_leg_ctrl": "R_leg_ctrl", "R_leg_ctrl": "L_leg_ctrl"}.get(A.short(n), ""), long=True)[0] if A.short(n) in ("L_leg_ctrl", "R_leg_ctrl") else None
A.side_of = lambda n: "L" if A.short(n).startswith("L_") else ("R" if A.short(n).startswith("R_") else "C")
A.pose_target = lambda s, d: ((0, 0, 0), (0, 0, 0), (1, 1, 1))
print("mirror cycle 1-24 (no loop frame given -> 25):", A.mirror_half_cycle([lft, rgt, hip], 1, 24), said[-1])
print("  second half keys at:", sorted(set(t for _n, _a, t in CK)), "| looping:", cmds.setInfinity.call_args.kwargs)
try:
    A.mirror_half_cycle([lft], 1, 2)
except RuntimeError as e:
    print("too short:", e)
# --- hider
from gus_animtool import hider as H
for n in ("head_ctrl", "jaw_ctrl", "L_arm_fk1_ctrl", "R_arm_fk1_ctrl", "L_index1_ctrl", "R_foot_ik_ctrl", "spine1_ctrl", "tail1_ctrl", "L_ear1_ctrl"):
    ctrl(n)
geo = cmds.createNode("transform", name="L_arm_geo"); cmds.createNode("mesh", name="L_arm_geoShape", parent=geo)
A.character_controls = lambda ns=None: [cmds.ls(n, long=True)[0] for n in ("head_ctrl", "jaw_ctrl", "L_arm_fk1_ctrl", "R_arm_fk1_ctrl", "L_index1_ctrl", "R_foot_ik_ctrl", "spine1_ctrl", "tail1_ctrl", "L_ear1_ctrl")]
for sh in cmds.ls(type="nurbsCurve") + cmds.ls(type="mesh"):
    cmds.setAttr(sh + ".lodVisibility", True)                # Maya's default
parts = H.parts("")
print("parts from names:", {p: v["controls"] for p, v in parts.items() if v["controls"]})
print("hide L arm:", H.toggle("L arm", "controls", ""), "| L arm shape:", cmds.getAttr("L_arm_fk1_ctrlShape.lodVisibility"), "| head:", cmds.getAttr("head_ctrlShape.lodVisibility"))
print("only the head:", H.isolate("Head & face", "controls", ""), "| R arm:", cmds.getAttr("R_arm_fk1_ctrlShape.lodVisibility"), "| jaw:", cmds.getAttr("jaw_ctrlShape.lodVisibility"))
print("again -> all back:", H.isolate("Head & face", "controls", ""), cmds.getAttr("R_arm_fk1_ctrlShape.lodVisibility"))
cmds.select(geo); print("add a mesh to L arm:", H.add_selected("L arm", ""), "| saved in the profile:", A.profile("").get("hider", {}).get("L arm", {}).get("geo"))
H.show("L arm", False, "geo", ""); print("mesh hidden:", cmds.getAttr("L_arm_geoShape.lodVisibility"))
H.reset(""); print("reset: back to names:", "hider" not in A.profile(""))
# --- animation library
from gus_animtool import animlib as AL
CUR = {"L_leg_ctrl_translateY": {"node": "L_leg_ctrl", "attr": "translateY", "keys": {1.0: 0.0, 7.0: 2.0, 13.0: 0.0}}}
cmds.keyframe = lambda *a, **k: (list(CUR) if k.get("name") else ([t for c in CUR.values() for t in sorted(c["keys"]) if k["time"][0] <= t <= k["time"][1]] if k.get("timeChange") else [v for c in CUR.values() for t, v in sorted(c["keys"].items()) if k["time"][0] <= t <= k["time"][1]])) if k.get("query") else KE.append(k)
KE = []
cmds.keyTangent = lambda *a, **k: ["auto"] * 3 if k.get("query") else None
_lc = cmds.listConnections
cmds.listConnections = lambda n, **k: ["L_leg_ctrl.translateY"] if n.startswith("L_leg_ctrl_translateY") else _lc(n, **k)
cmds.playblast = mock.MagicMock()
cmds.select(lft)
print("clip saved:", AL.save("hop", start=1, end=13), "| in the list:", AL.names())
clip = AL.load("hop"); print("clip:", clip["length"], clip["controls"])
CK[:] = []; NOW[0] = 40.0
print("applied at 40:", AL.apply("hop", "replace"), "| keys at:", [t for _n, _a, t in CK], "| span cleared:", cmds.cutKey.call_args.kwargs.get("time"))
CK[:] = []; KE[:] = []
AL.apply("hop", "insert"); print("insert pushes later keys by", KE[0]["timeChange"], "from", KE[0]["time"][0])
A.flip_range = mock.MagicMock(return_value=2)
AL.apply("hop", "merge", mirrored=True); print("mirrored: sides swapped inside", A.flip_range.call_args[0][1:])
try:
    AL.apply("hop", only=[hip])
except RuntimeError as e:
    print("only the hips:", e)
AL.delete("hop"); print("deleted:", AL.names())
# --- ghosts
from gus_animtool import tools as TL
body = cmds.createNode("transform", name="body_geo"); cmds.createNode("mesh", name="body_geoShape", parent=body)
cmds.select(body)
SN = []
def snapshot(meshes, **k):
    g = cmds.createNode("transform", name=k["name"] + "Group"); cmds.createNode("transform", name=k["name"] + "1", parent=g)
    SN.append((k["startTime"], k["endTime"], k["increment"], k["update"])); return [k["name"] + "Node", g]
cmds.snapshot = snapshot
_nt = cmds.nodeType
cmds.nodeType = lambda n, **k: "snapshot" if str(n).endswith("Node") else _nt(n, **k)
cmds.shadingNode = lambda *a, **k: cmds.createNode("transform", name=k["name"]); cmds.sets = lambda *a, **k: cmds.createNode("transform", name=k["name"]) if k.get("name") else None
NOW[0] = 20.0
print("ghosts:", TL.ghosts(2, 2, 2), "| frames:", SN, "| grouped:", cmds.objExists(TL.GHOSTS))
TL.clear_ghosts(); print("cleared:", not cmds.objExists(TL.GHOSTS))
# --- crash backup
from gus_animtool import backup as BK
_opts["backup_keep"] = 2
root = tempfile.mkdtemp(); BK.root = lambda: root
files = cmds.file
def file_(*a, **k):
    if k.get("query"):
        return "/proj/hare_walk.ma" if k.get("sceneName") else True
    open(a[0], "w").write("//Maya ASCII"); return a[0]
cmds.file = file_
import time as _t
for i in range(3):
    p = BK.backup_now(); os.utime(p, (_t.time() + i, _t.time() + i)); _t.sleep(1.05)
print("backups kept (2):", len(BK.backups()), "| newest first:", os.path.basename(BK.backups()[0][0]).startswith("hare_walk_"))
cmds.scriptJob = mock.MagicMock(return_value=7)
print("timer:", BK.start(), BK.running(), "| stop:", BK.stop(), BK.running())
print("ensure when off:", BK.ensure())
