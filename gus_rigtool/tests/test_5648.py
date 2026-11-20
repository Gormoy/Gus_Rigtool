# 5.6.48: shapes on the body (fit to the body, lie on the skin, shape from edges), one click makes the controls,
# Make on a selected control adds a new control there (any rig), referenced / locked controls' shapes rebuilt in
# place, the Animtool's title after Maya reopens it, the click-away check waits for Maya, ls([], type=...) -> []
import os, sys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ROOT = os.path.join(os.getcwd(), "..")
cmds.undoInfo = mock.MagicMock(return_value=True)
from gus_rigtool.core import shape_edit as SE, curves, shape_data

# a ball of radius 2 at the centre, worked out exactly (the real mesh is case o in real Maya)
def ball_tools(mesh):
    def closest(p):
        d = sum(x * x for x in p) ** 0.5
        n = [x / d for x in p]
        return [2.0 * x for x in n], n
    def ray(src, d):
        return [src[i] + d[i] * 2.0 for i in range(3)] if src == [0, 0, 0] else None
    return closest, ray
r = lambda p: round(sum(x * x for x in p) ** 0.5, 4)
written = {}

# --- 1. fit to the body: a small circle at the ball's centre wraps it, 20% off the skin
ring = [[0.5, 0, 0], [0, 0, 0.5], [-0.5, 0, 0], [0, 0, -0.5]]
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), mock.patch.object(SE, "_mesh_tools", ball_tools), \
        mock.patch.object(SE, "_mesh_of", lambda m: m), \
        mock.patch.object(curves, "world_positions", lambda n: [list(ring)]), \
        mock.patch.object(curves, "set_world_positions", lambda n, pts: written.__setitem__(n, pts)), \
        mock.patch.object(cmds, "xform", lambda *a, **k: [0, 0, 0]):
    got, missed = SE.fit_to_body(["|wrist_ctrl"], "ball", 0.2)
check("fit to the body: every point out to the skin (2) and 20% more (2.4); the pivot stays",
      got == ["|wrist_ctrl"] and not missed and [r(p) for p in written["|wrist_ctrl"][0]] == [2.4] * 4)
far = [[5.0, 0, 0], [0, 0, 5.0]]
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), mock.patch.object(SE, "_mesh_tools", ball_tools), \
        mock.patch.object(SE, "_mesh_of", lambda m: m), \
        mock.patch.object(curves, "world_positions", lambda n: [list(far)]), \
        mock.patch.object(curves, "set_world_positions", lambda n, pts: written.__setitem__(n, pts)), \
        mock.patch.object(cmds, "xform", lambda *a, **k: [0, 0, 0]):
    SE.fit_to_body(["|big_ctrl"], "ball", 0.2)
check("...a circle bigger than the body comes in to it (Gus: 'the circle going to the point works')",
      [r(p) for p in written["|big_ctrl"][0]] == [2.4, 2.4])
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), mock.patch.object(SE, "_mesh_tools", ball_tools), \
        mock.patch.object(SE, "_mesh_of", lambda m: m), \
        mock.patch.object(curves, "world_positions", lambda n: [list(ring)]), \
        mock.patch.object(curves, "set_world_positions", lambda n, pts: written.__setitem__(n, pts)), \
        mock.patch.object(cmds, "xform", lambda *a, **k: [9, 9, 9]):
    _g, missed = SE.fit_to_body(["|lost_ctrl"], "ball", 0.2)
check("points whose line meets no skin stay where they were, and it says how many",
      missed == 4 and written["|lost_ctrl"][0] == ring)

# --- 2. lie on the skin: a cheek control outside the ball pressed onto it, lifted by 20% of its size
cheek = [[3.0, 0.5, 0], [3.0, -0.5, 0], [3.0, 0, 0.5]]
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), mock.patch.object(SE, "_mesh_tools", ball_tools), \
        mock.patch.object(SE, "_mesh_of", lambda m: m), \
        mock.patch.object(curves, "world_positions", lambda n: [list(cheek)]), \
        mock.patch.object(curves, "set_world_positions", lambda n, pts: written.__setitem__(n, pts)):
    SE.lie_on_skin(["|cheek_ctrl"], "ball", 0.2)
check("lie on the skin: every point on the skin, lifted 0.1 (20% of the shape's half size 0.5)",
      [r(p) for p in written["|cheek_ctrl"][0]] == [2.1, 2.1, 2.1])
try:
    SE._mesh_of("nothing_here"); msg = ""
except RuntimeError as e:
    msg = str(e)
check("no mesh picked: says to select the controls, then the mesh", "then the mesh" in msg)

# --- 3. shape from edges: a ring of edges at height 1, radius 1
LOOP = [{"degree": 3, "form": 2, "points": [[1, 1, 0], [0, 1, 1], [-1, 1, 0], [0, 1, -1]], "knots": [0, 1, 2, 3]}]
def ring_normals(mesh):
    def closest(p):
        d = (p[0] ** 2 + p[2] ** 2) ** 0.5
        return p, [p[0] / d, 0.0, p[2] / d]
    return closest, None
made = []
with mock.patch.object(SE, "_mesh_tools", ring_normals), mock.patch.object(SE, "_loop_curve", lambda e: [dict(c) for c in LOOP]), \
        mock.patch("gus_rigtool.core.control_maker.new", lambda name, data, style, groups=(), matrix=None, **k:
                   made.append((name, data, groups, matrix)) or ("|" + groups[0], "|" + groups[0] + "|" + name)):
    got = SE.from_edges(["Hare_Body.e[10]", "Hare_Body.e[11]"], [], 0.2)
name, data, groups, matrix = made[0]
check("only edges: a new control on the loop, named after the mesh, at the loop's centre",
      name == "Hare_Body_loop_ctrl" and groups == ["Hare_Body_loop_ctrl_offset"] and list(matrix[12:15]) == [0, 1, 0])
check("...its shape is the loop 20% off the skin (radius 1.2), around its own centre",
      [round(((p[0] ** 2 + p[2] ** 2) ** 0.5), 4) for p in data[0]["points"]] == [1.2] * 4 and
      all(abs(p[1]) < 1e-9 for p in data[0]["points"]))
sets = []
with mock.patch.object(SE, "_mesh_tools", ring_normals), mock.patch.object(SE, "_loop_curve", lambda e: [dict(c) for c in LOOP]), \
        mock.patch.object(SE, "controls", lambda nodes: list(nodes or [])), \
        mock.patch.object(cmds, "getAttr", lambda a: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -1, 0, 1]), \
        mock.patch.object(curves, "set_shape", lambda n, d, st=None: sets.append((n, d))):
    SE.from_edges(["Hare_Body.e[10]"], ["|mouth_ctrl"], 0.2)
check("edges + a control: the control takes the loop's shape, in its own space (its pivot stays)",
      sets and sets[0][0] == "|mouth_ctrl" and all(abs(p[1]) < 1e-9 for p in sets[0][1][0]["points"]))
try:
    SE.from_edges(["Hare_Body"], [], 0.2); msg = ""
except RuntimeError as e:
    msg = str(e)
check("no edges: says to select an edge loop", "edge loop" in msg)

# --- 4. other rigs' controls: a locator next to the curve is fine; a mesh is not a control
t = cmds.createNode("transform", name="other_rig_ctrl")
cmds.createNode("nurbsCurve", name="other_rig_ctrlShape", parent=t)
cmds.createNode("locator", name="other_rig_pickShape", parent=t)
g = cmds.createNode("transform", name="body_geo")
cmds.createNode("nurbsCurve", name="body_geoCrv", parent=g)
cmds.createNode("mesh", name="body_geoShape", parent=g)
check("a control with a helper shape (a locator) counts; a mesh with a curve doesn't",
      SE.controls(["other_rig_ctrl", "body_geo"]) == ["other_rig_ctrl"])

# --- 5. a referenced / locked control: its curve rebuilt in place (it can't be deleted)
ctrl = curves.create_curve_control("locked_ctrl", [shape_data.circle_curve(1.0)])
shp = curves.curve_shapes(ctrl)[0]
cmds.lockNode(shp, lock=True)
free = curves.create_curve_control("free_ctrl", [shape_data.circle_curve(1.0)])
import importlib
fake_set_shape = curves.set_shape
importlib.reload(curves)                     # the real set_shape (the fake Maya stands one in)
replaced, deleted = [], []
real_curve, real_delete = cmds.curve, cmds.delete
with mock.patch.object(cmds, "curve", lambda *a, **k: (replaced.append(a) if k.get("replace") else None) or
                       real_curve(*a, **k)), \
        mock.patch.object(cmds, "delete", lambda *a, **k: deleted.append(a) or real_delete(*a, **k)):
    curves.set_shape(ctrl, [shape_data.circle_curve(2.0)])
    locked_rep, locked_del = list(replaced), list(deleted)
    cmds.lockNode(shp, lock=False)
    del replaced[:], deleted[:]
    curves.set_shape(free, [shape_data.circle_curve(2.0)])
curves.set_shape, curves.create_curve_control = fake_set_shape, _ccc
check("a locked control: the same curve rebuilt in place (curve -replace), nothing deleted",
      locked_rep == [(shp,)] and not locked_del and curves.curve_shapes(ctrl) == [shp])
check("an ordinary control: as before (a new curve, the old one deleted)", not replaced and deleted)

# --- 6. the Controls tab: one click; Make on a selected control adds a new control there
from gus_rigtool.tools import controls_tab as CT
CT.build()
calls = []
with mock.patch.object(CT, "page", lambda: 1), mock.patch.object(CT, "make", lambda *a: calls.append("make") or ["|x"]):
    CT.pick("square")
check("Make page: clicking a shape makes the controls at once (like the old Shapes tab)", calls == ["make"])
with mock.patch.object(CT, "page", lambda: 2), mock.patch.object(CT, "make", lambda *a: calls.append("make2")), \
        mock.patch("gus_rigtool.core.utils.selected_transforms", lambda *a, **k: []):
    CT.pick("square")
check("Edit shape page with nothing selected: a click only picks (nothing made)", "make2" not in calls)
with mock.patch.object(CT, "picked", lambda: "square"):
    d = CT.describe(["|other_rig_ctrl"])
check("a control selected: Make says a new control goes at its place (it isn't changed), the button on",
      "a new control at each one's place" in d[0] and d[1] == "Make 1 control(s) (Square)" and d[2])
newc = []
s = dict(CT.DEFAULTS)
with mock.patch.object(curves, "read_shape", lambda n: [shape_data.circle_curve(1.0)]), \
        mock.patch.object(curves, "match_matrix", lambda n: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 3, 4, 5, 1]), \
        mock.patch.object(cmds, "select", lambda *a, **k: None), \
        mock.patch("gus_rigtool.core.control_maker.new", lambda name, data, style, groups=(), matrix=None, **k:
                   newc.append((name, groups, matrix, k.get("parent"))) or ("|" + groups[0], "|" + groups[0] + "|" + name)):
    out = CT.on_controls(["|rigA:L_hand_ctrl"], s)
check("...a new control named after it (no namespace), at its pivot, not under it and not driving it",
      newc and newc[0][0] == "L_hand_ctrl" and list(newc[0][2][12:15]) == [3, 4, 5] and newc[0][3] is None)
src = open(os.path.join(ROOT, "tools", "controls_tab.py")).read()
check("Edit shape page: On the body - Gap %, Fit to the body, Lie on the skin, Shape from edges",
      all(w in src for w in ('"Gap %"', '"Fit to the body"', '"Lie on the skin"', '"Shape from edges"')))

# --- 7. the Animtool's title, the click-away check, Maya facts, the fake
ui_src = open(os.path.join(ROOT, "anim", "gus_animtool", "ui.py")).read()
check("the Animtool window's title is set to this version when Maya reopens it (build)",
      'cmds.workspaceControl(WINDOW, edit=True, label="Gus Animtool %s" % gus_animtool.__version__)' in ui_src)
wc = open(os.path.join(ROOT, "realmaya", "window_checks.py")).read()
check("Test this release: click away waits for Maya's idle queue; if Maya still hasn't, 'try it by hand' (not FAIL)",
      "cmds.flushIdleQueue()" in wc and "try it by hand" in wc and "the Animtool window's title" in wc)
sys.path.insert(0, os.path.join(ROOT, ".."))
from gus_rigtool.realmaya import maya_facts as MF
check("Maya facts: curve -replace on plain / history / locked / referenced controls",
      "curve_replace" in [x.__name__ for x in MF.FACTS])
cases = open(os.path.join(ROOT, "realmaya", "maya_cases.py")).read()
check("real-Maya case o: shapes on the body", '("o. shapes on the body", body_shapes)' in cases)
check("the fake Maya: ls([], type=...) lists nothing, like Maya (5.6.47 facts)",
      cmds.ls([], type="transform") == [] and cmds.ls([], long=True) == [])
print("%d/%d passed" % (sum(ok), len(ok)))
