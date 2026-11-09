# 4.4.0: the weight list (average per joint, set a value, average, lock), Blink split, rebuild preview
exec(open("fakemaya.py").read())
from gus_rigtool.core import skin_tools, face_kit
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
W = {0: {"j1": 0.6, "j2": 0.4}, 1: {"j1": 0.2, "j2": 0.3, "j3": 0.5}}
INF = ["j1", "j2", "j3"]
calls = []
def skinPercent(skin, comps, **k):
    if k.get("query"):
        i = int(comps.split("[")[1].rstrip("]"))
        return list(W[i].keys()) if "transform" in k else list(W[i].values())
    calls.append((comps, dict(k)))
cmds.skinPercent = skinPercent
cmds.skinCluster = lambda *a, **k: list(INF) if k.get("query") else None
skin_tools.skin_of = lambda g: "skinCluster1"
skin_tools._transform = lambda p: "|body"
for j in INF:
    cmds.createNode("joint", name=j)
cmds.setAttr("j3.liw", True) if False else None
cmds.addAttr("j3", longName="liw", attributeType="bool"); cmds.setAttr("j3.liw", True)
rows = skin_tools.weight_table(["body.vtx[0]", "body.vtx[1]"])
check("weight list: average per joint, biggest first, locks shown",
      [(j, round(w, 3), lk) for j, w, lk in rows] == [("j1", 0.4, False), ("j2", 0.35, False), ("j3", 0.25, True)])
n = skin_tools.set_joint_weight("j2", 0.7, ["body.vtx[0]", "body.vtx[1]"])
check("set: the joint gets the value, Maya normalises the rest", n == 2 and calls[-1][1]["transformValue"] == [("j2", 0.7)]
      and calls[-1][1]["normalize"] is True)
try:
    skin_tools.set_joint_weight("jX", 0.5, ["body.vtx[0]"]); check("a joint not in the skin is refused", False)
except RuntimeError:
    check("a joint not in the skin is refused", True)
calls[:] = []
_ls = cmds.ls
cmds.ls = lambda *a, **k: (list(a[0]) if a and isinstance(a[0], list) and k.get("flatten") else _ls(*a, **k))
n = skin_tools.average_points(["body.vtx[0]", "body.vtx[1]"])
tv = dict(calls[-1][1]["transformValue"])
check("average: each vertex gets the selection's average", n == 2 and abs(tv["j1"] - 0.4) < 1e-6 and abs(tv["j3"] - 0.25) < 1e-6)
cmds.ls = _ls
cmds.addAttr("j1", longName="liw", attributeType="bool")
check("lock / unlock", skin_tools.lock_joints(["j1"], True) == 1 and cmds.getAttr("j1.liw") is True)

# Blink: lids split by their own middle height, even when the loop sits below the eye centre
ctrls = [(i, "o%d" % i, "c%d" % i, p) for i, p in enumerate([(4.9, 160.2, 8), (4.2, 161.0, 8), (3.5, 161.3, 8),
                                                             (2.8, 161.0, 8), (2.1, 160.2, 8), (2.8, 159.6, 8),
                                                             (4.2, 159.6, 8)])]
up, low, corners = face_kit._split_lids(ctrls, [3.5, 162.0, 8.5])
check("lids split by their own middle (eye centre above them all)", len(up) == 3 and len(low) == 2 and len(corners) == 2)
print("ALL OK" if all(ok) else "SOME FAILED")
