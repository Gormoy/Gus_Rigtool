# Skin tab 5 (3.12): weights to one readable .json and back - names without namespaces, by vertex number or closest
# position, a missing joint's weights to the nearest joint, meshes without skin bound first, the import window
import os, sys, json, random, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
from gus_rigtool.core import skin_io
J = {}
for name, pos in (("spine_jnt", (0, 10, 0)), ("L_arm_jnt", (5, 15, 0)), ("L_hand_jnt", (9, 15, 0))):
    j = cmds.createNode("joint", name=name); cmds.xform(j, worldSpace=True, translation=pos); J[name] = j
MESH = {}
def mesh(name, pts, skin=None, infl=None, weights=None):
    t = cmds.createNode("transform", name=name); cmds.createNode("mesh", name=name.split(":")[-1] + "Shape", parent=t)
    MESH[cmds.ls(t, long=True)[0]] = {"pts": pts, "skin": skin, "infl": infl or [], "w": weights}
    return cmds.ls(t, long=True)[0]
def info(geo):
    return MESH[cmds.ls(geo, long=True)[0]]
skin_io.point_count = lambda g: len(info(g)["pts"])
skin_io.positions = lambda g: info(g)["pts"]
skin_io.skin_of = lambda g: info(g)["skin"]
SKIN_OF = {}
skin_io.influences = lambda s: SKIN_OF[s]["infl"]
skin_io.get_weights = lambda s, g: (SKIN_OF[s]["infl"], SKIN_OF[s]["w"])
def set_weights(s, g, rows):
    SKIN_OF[s]["w"] = rows
skin_io.set_weights = set_weights
import gus_rigtool.core.skin_tools as _st; _st.rig_joints = lambda: [J["spine_jnt"], J["L_arm_jnt"], cmds.ls("L_wrist_jnt", long=True)[0] if cmds.objExists("L_wrist_jnt") else J["L_hand_jnt"]]
def skinCluster(*a, **k):
    if k.get("query"):
        return 4 if k.get("maximumInfluences") else 0
    if k.get("edit") and k.get("addInfluence"):
        SKIN_OF[a[0]]["infl"].append(cmds.ls(k["addInfluence"], long=True)[0]); return None
    joints, geo = a[0], a[1]
    name = k.get("name", "skinCluster1"); SKIN_OF[name] = {"infl": cmds.ls(joints, long=True), "w": None}
    info(geo)["skin"] = name
    return [name]
cmds.skinCluster = skinCluster
# a skinned body: 3 points
body = mesh("body_geo", [[0, 10, 0], [5, 15, 0], [9, 15, 0]], skin="body_skin")
SKIN_OF["body_skin"] = {"infl": [J["spine_jnt"], J["L_arm_jnt"], J["L_hand_jnt"]],
                        "w": [[1.0, 0.0, 0.0], [0.25, 0.75, 0.0], [0.0, 0.4, 0.6]]}
info(body)["skin"] = "body_skin"
path = os.path.join(tempfile.mkdtemp(), "hare_skin")
saved, path = skin_io.export_file(path, [body])
text = open(path).read()
print("exported:", saved, os.path.basename(path), "| readable, a line per vertex:", '      [[1, 0.25], [2, 0.75]]' not in text and '[[0, 0.25], [1, 0.75]]' in text)
print(text.splitlines()[0]); print([l.strip() for l in text.splitlines() if l.strip().startswith('"joints"')][0])
data = skin_io.read_file(path)
try:
    open(path + "x", "w").write('{"a": 1}'); skin_io.read_file(path + "x")
except RuntimeError as e:
    print("other json:", e)
# the same mesh in a referenced file (namespace), one joint renamed away -> nearest joint takes its weights
cmds.rename(J["L_hand_jnt"], "L_wrist_jnt")
other = mesh("hare:body_geo", [[0, 10, 0], [5, 15, 0], [9, 15, 0]], skin="hare_skin")
SKIN_OF["hare_skin"] = {"infl": [J["spine_jnt"]], "w": None}
print("guess by name (namespaces ignored):", skin_io.guess_mesh("body_geo", [other]).split("|")[-1])
lines, done = skin_io.import_file(path, {"body_geo": other})
print(lines[0])
print("weights (joints added to the skin, renamed joint's weights on the nearest):",
      [s.split("|")[-1] for s in SKIN_OF["hare_skin"]["infl"]], [[round(w, 2) for w in r] for r in SKIN_OF["hare_skin"]["w"]])
# a changed mesh (5 points): closest position; no skin yet -> bound first
remesh = mesh("body_geo_v2", [[0, 9.8, 0], [5.1, 15, 0], [9, 15.2, 0], [2, 11, 0], [8.8, 14.9, 0]])
lines, done = skin_io.import_file(path, {"body_geo": remesh})
print(lines[0])
print("bound to:", [s.split("|")[-1] for s in SKIN_OF[info(remesh)["skin"]]["infl"]], "| rows:", len(SKIN_OF[info(remesh)["skin"]]["w"]),
      "| point 4 takes vertex 2's weights:", [round(w, 2) for w in SKIN_OF[info(remesh)["skin"]]["w"][4]])
try:
    skin_io.import_entry(data["meshes"]["body_geo"], remesh, "index")
except RuntimeError as e:
    print("by vertex number on another mesh:", e)
lines, done = skin_io.import_file(path, {"body_geo": mesh("bare_geo", [[0, 0, 0]] * 3)}, bind=False)
print(lines[0])
print("skipped:", skin_io.import_file(path, {"body_geo": None})[0])
# closest point search = brute force
random.seed(3)
pts = [[random.uniform(-50, 50), random.uniform(0, 180), random.uniform(-20, 20)] for _ in range(3000)]
near = skin_io.Nearest(pts)
qs = [[random.uniform(-60, 60), random.uniform(-10, 190), random.uniform(-30, 30)] for _ in range(200)]
brute = [min(range(len(pts)), key=lambda i: skin_io._dist(pts[i], q)) for q in qs]
print("grid search = brute force:", [near.find(q) for q in qs] == brute)
# the import window
from gus_rigtool.tools import skin_tool
cmds.window = mock.MagicMock(return_value=False); cmds.showWindow = mock.MagicMock()
cmds.select(other)
win = skin_tool.import_window(path)
menus = [n for n, v in UI.items() if v.get("kind") == "optionMenu" and v.get("items") and v["items"][0] == "(skip)"]
print("window: a row per mesh in the file:", len(menus), "| picked:", UI[menus[0]]["items"][UI[menus[0]]["select"] - 1])
