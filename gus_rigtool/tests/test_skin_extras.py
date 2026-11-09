# Skin tab 6: copy / paste vertex weights (average, missing joints skipped), smooth, move weights A > B
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import skin_tools
geo = cmds.createNode("transform", name="body"); cmds.createNode("mesh", name="bodyShape", parent=geo)
W = {0: {"j1": 1.0}, 1: {"j1": 0.5, "j2": 0.5}, 2: {"j2": 1.0}, 3: {"j3": 1.0}}
INF = ["j1", "j2", "j3"]
calls = []
def skinPercent(skin, comps, **k):
    if k.get("query"):
        i = int(comps.split("[")[1].rstrip("]"))
        return list(W[i].keys()) if "transform" in k else list(W[i].values())
    calls.append((comps, {x: y for x, y in k.items()}))
cmds.skinPercent = skinPercent
cmds.skinCluster = lambda *a, **k: list(INF) if k.get("query") else calls.append(("addInfluence", k.get("addInfluence")))
skin_tools.skin_of = lambda g: "skinCluster1"
skin_tools._transform = lambda p: "|body"
cmds.polyListComponentConversion = lambda x, **k: x if k.get("toEdge") else ["body.vtx[0]", "body.vtx[1]", "body.vtx[2]"]
_ls = cmds.ls
cmds.ls = lambda *a, **k: (list(a[0]) if a and isinstance(a[0], list) and k.get("flatten") else _ls(*a, **k))
w = skin_tools.copy_point_weights(["body.vtx[0]", "body.vtx[1]"])
print("copied average:", {k: round(v, 3) for k, v in w.items()})
skin_tools._clip["weights"] = {"j1": 0.5, "jX": 0.5}
print("pasted:", skin_tools.paste_point_weights(["body.vtx[3]"]), calls[-1])
calls[:] = []
print("smoothed:", skin_tools.smooth(["body.vtx[3]"], 0.5))
print("  ->", [(c, sorted((j, round(v, 3)) for j, v in k["transformValue"])) for c, k in calls])
calls[:] = []
print("moved meshes:", skin_tools.move_weights("j1", "j4", points=["body.vtx[0]"]), calls)
try:
    skin_tools.move_weights("jZ", "j1", points=["body.vtx[0]"])
except RuntimeError as e:
    print("refused:", e)
