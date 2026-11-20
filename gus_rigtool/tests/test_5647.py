# 5.6.47: the Controls tab (Make controls + Shapes: one shape list, Make / Edit shape pages, in front on an axis,
# pivot on the shape, hover preview, shape handles with Done / Cancel / click away, stretch), Ctrl+Z after timing
# beads, Arcs: break / join the handles, the shelf rebuilt once per version, the pick-walk crash (a shape is a list
# of curves - the fake now refuses one curve on its own), Maya facts from Gus's Mac (ls([]) lists nothing)
import os, sys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ROOT = os.path.join(os.getcwd(), "..")
cmds.undoInfo = mock.MagicMock(return_value=True)
from gus_rigtool.core import shape_edit as SE, curves, shape_data

# --- 1. moving the points: in front (axes only), stretch, size, turn
moved = {}
def map_cvs(n, func):
    moved[n] = func((1.0, 2.0, 3.0))
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), mock.patch.object(curves, "map_cvs_object", map_cvs):
    SE.in_front(["|c"], 2.0, "+Y")
    a = moved["|c"]
    SE.in_front(["|c"], 2.0, "-X")
    b = moved["|c"]
    SE.stretch(["|c"], "Z", 2.0)
    st = moved["|c"]
    SE.resize(["|c"], 0.5)
    sz = moved["|c"]
    SE.turn90(["|c"], "Y")
    tn = moved["|c"]
check("in front +Y 2: every point 2 along the control's Y (the pivot stays)", a == (1.0, 4.0, 3.0))
check("in front -X 2", b == (-1.0, 2.0, 3.0))
check("stretch on Z only", st == (1.0, 2.0, 6.0))
check("size: all three", sz == (0.5, 1.0, 1.5))
check("turn 90 on Y", tn == (3.0, 2.0, -1.0))
check("the six directions, nothing else (Gus: just the axes)", sorted(SE.AXES) == ["+X", "+Y", "+Z", "-X", "-Y", "-Z"])
try:
    SE.in_front(["|c"], 1.0, "toward the camera"); msg = ""
except ValueError as e:
    msg = str(e)
check("anything else is refused", "axis" in msg)

# --- 2. hover preview: shown, not an undo step, the controls' own shapes back
SQUARE = [{"degree": 1, "form": 0, "points": [[0, 0, 0], [1, 0, 0]], "knots": [0.0, 1.0]}]
CIRCLE = [shape_data.circle_curve(1.0)]
shapes, sets = {"|L_hand_ctrl": CIRCLE}, []
undo_states = []
def undoInfo(**k):
    if "stateWithoutFlush" in k and not k.get("query"):
        undo_states.append(k["stateWithoutFlush"])
    return True
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), \
        mock.patch.object(curves, "read_shape", lambda n: shapes[n]), \
        mock.patch.object(curves, "read_style", lambda n: {"lineWidth": 2.0}), \
        mock.patch.object(curves, "set_shape", lambda n, d, st=None: sets.append((n, d, st))), \
        mock.patch.object(cmds, "undoInfo", undoInfo), mock.patch.object(cmds, "objExists", lambda n: True):
    SE.preview(["|L_hand_ctrl"], SQUARE)
    shown = sets[-1]
    SE.end_preview()
    back = sets[-1]
check("hover: the shape shows on the control, its size kept, its line width kept",
      shown[0] == "|L_hand_ctrl" and shown[1] != SQUARE and shown[2] == {"lineWidth": 2.0})
check("...not an undo step (undo off while it shows)", undo_states[:2] == [False, True])
check("the mouse leaves: the control's own shape back", back == ("|L_hand_ctrl", CIRCLE, {"lineWidth": 2.0}))
check("...and nothing left to put back", SE._preview == {})

# --- 3. shape handles: Done (or clicking away) puts the move into the curve; Cancel throws it away
c = cmds.ls(createNode("transform", name="L_arm_ctrl"), long=True)[0]
createNode("nurbsCurve", name="L_arm_ctrlShape", parent=c)
deferred, got = [], {}
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), \
        mock.patch.object(curves, "read_shape", lambda n: CIRCLE), \
        mock.patch.object(cmds, "scriptJob", lambda **k: 7, create=True), \
        mock.patch.object(cmds, "evalDeferred", lambda fn, **k: deferred.append(fn), create=True):
    hs = SE.handles_start([c])
    check("a handle on the control's shape, selected for you", len(hs) == 1 and hs[0].startswith(c + "|") and
          cmds.ls(selection=True, long=True) == hs)
    cmds.select(clear=True)
    SE._on_selection()
    check("you click something else: it's kept (as with Done)", deferred and deferred[0] == SE.handles_done)
    with mock.patch.object(SE, "_matrix_of", lambda h: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 3, 0, 1]), \
            mock.patch.object(curves, "map_cvs_object", lambda n, f: got.__setitem__(n, f((1.0, 0.0, 0.0)))):
        n = SE.handles_done()
check("Done: the handle's move into the curve points (the control's channels untouched), the handle gone",
      n == 1 and got.get(c) == (1.0, 3.0, 0.0) and not cmds.objExists(hs[0]) and not SE.handles_active())
with mock.patch.object(SE, "controls", lambda nodes: list(nodes)), \
        mock.patch.object(curves, "read_shape", lambda n: CIRCLE), \
        mock.patch.object(cmds, "scriptJob", lambda **k: 7, create=True):
    hs = SE.handles_start([c])
    got.clear()
    with mock.patch.object(curves, "map_cvs_object", lambda n, f: got.__setitem__(n, 1)):
        SE.handles_cancel()
check("Cancel: the handle gone, the shape as it was", not cmds.objExists(hs[0]) and got == {})

# --- 4. Make: in front, the pivot on the joint or on the shape
from gus_rigtool.core import make_controls as MC
cmds.controller = lambda *a, **k: None
j = cmds.ls(createNode("joint", name="L_arm_jnt"), long=True)[0]
calls = []
with mock.patch.object(SE, "in_front", lambda nodes, d, ax: calls.append((nodes, d, ax))):
    out = MC.make([j], shape="circle", size=1.0, front=2.0, front_axis="+Y", pivot_on_shape=False)
ctrl = out[0][1]
check("in front, the pivot stays on the joint: only the shape moves (the control at the joint)",
      calls and calls[0][1:] == (2.0, "+Y") and
      [round(v, 4) for v in cmds.xform(ctrl, query=True, worldSpace=True, translation=True)] == [0, 0, 0])
cmds.delete(cmds.listRelatives(ctrl, parent=True, fullPath=True)[0])
cmds.deleteAttr = getattr(cmds, "deleteAttr", lambda *a, **k: None)
j2 = cmds.ls(createNode("joint", name="L_leg_jnt"), long=True)[0]
out = MC.make([j2], shape="circle", size=1.0, front=2.0, front_axis="+Y", pivot_on_shape=True)
leg_ctrl = out[0][1]
pos = [round(v, 4) for v in cmds.xform(leg_ctrl, query=True, worldSpace=True, translation=True)]
check("pivot on the shape: the whole control 2 along +Y (Ribbon's 'pivot on the shape')", pos == [0, 2.0, 0])

# --- 5. the Controls tab
from gus_rigtool.tools import controls_tab as CT
from gus_rigtool import registry
CT.build()
check("one shape list: the built-in shapes, My shapes last", [cat for cat, _n in CT.shape_names()] ==
      ["Basic", "3D", "Arrows", "Rig", "My shapes"] and len(CT._rows["p_controls_"]) >= 33)
check("two pages: Make, Edit shape", cmds.tabLayout("p_controls_Pages", query=True, selectTabIndex=True) in (1, 2))
check("Custom starts open (not in the folded 'advanced' list)", "Custom" not in registry.ADVANCED.get("controls_tab", []))
jn = cmds.ls(createNode("joint", name="R_arm_jnt"), long=True)[0]
with mock.patch.object(CT, "picked", lambda: "four_way_arrow"):
    d_joints = CT.describe([jn])
    d_ctrls = CT.describe([leg_ctrl])
    d_none = CT.describe([])
check("joints selected: 'Make 1 control(s) (Four Way Arrow)', Edit greyed out with the reason",
      d_joints[1] == "Make 1 control(s) (Four Way Arrow)" and d_joints[2] and not d_joints[5] and
      d_joints[4] == "Select controls to change")
check("controls selected: Make greyed out and says why; Edit: 'Use Four Way Arrow on 1 control(s)'",
      not d_ctrls[2] and "Edit shape changes them" in d_ctrls[0] and d_ctrls[4] == "Use Four Way Arrow on 1 control(s)")
check("nothing selected: one control at the centre", d_none[1] == "Make 1 control at the centre (Four Way Arrow)")
check("the old keys open the Controls tab, on their page (Shapes: Edit shape; Make controls: Make)",
      registry.resolve("shapes") == ("controls_tab", 2) and registry.resolve("makectrl") == ("controls_tab", 1) and
      "controls_tab" in dict((c, k) for c, _l, k in registry.CATEGORIES)["controls"] and
      "shapes" not in dict((c, k) for c, _l, k in registry.CATEGORIES)["controls"])
from gus_rigtool.core import ui
check("...the page is chosen for you", ui._follow_alias("shapes") == "controls_tab" and CT.WANT_PAGE["page"] == 2)
CT.WANT_PAGE["page"] = None

# --- 6. the fixes
src = open(os.path.join(ROOT, "anim", "gus_animtool", "arctrail.py")).read()
check("Ctrl+Z after timing beads: arc styling isn't an undo step", "with A.NoUndo():\n        return _style(" in src)
sys.path.insert(0, os.path.join(ROOT, "anim"))
from gus_animtool import arctrail as T, actions as AC, anim as A, ui as AUI, toolbar as TB
kt = []
with mock.patch.object(cmds, "keyframe", lambda *a, **k: (["crv_tx"] if k.get("name") else [5.0]) if k.get("selected")
                       else None, create=True), \
        mock.patch.object(cmds, "keyTangent", lambda c, **k: kt.append((c, k.get("time"), k.get("lock"))), create=True):
    n = T.break_handles([])
check("Break the handles: the selected key's handles move on their own", n == 1 and kt == [("crv_tx", (5.0, 5.0), False)])
check("...Join them again, both in the right-click menu", ("Break the handles (move one at a time)", "arcs_break") in
      AC.MENUS["arcs"] and ("Join the handles again", "arcs_join") in AC.MENUS["arcs"])
opts = {}
A.opt = lambda k, d: opts.get(k, d)
A.set_opt = lambda k, v: opts.__setitem__(k, v)
A.message = lambda *a, **k: None
built = []
import gus_animtool
with mock.patch.object(TB, "make_shelf", lambda: built.append(1) or 57), \
        mock.patch.object(cmds, "shelfLayout", lambda *a, **k: True, create=True):
    first = AUI._shelf_up_to_date()
    opts["shelf_version"] = gus_animtool.__version__
    again = AUI._shelf_up_to_date()
check("the shelf: rebuilt once for a new version (Attach and the 21 others come back), not again",
      first is True and again is False and built == [1])
with mock.patch.object(cmds, "shelfLayout", lambda *a, **k: False, create=True):
    opts.pop("shelf_version")
    check("...no Gus_Animtool shelf: none is made", AUI._shelf_up_to_date() is False)
try:
    curves.create_curve_control("bad_ctrl", shape_data.circle_curve(1.0)); bad = ""
except TypeError as e:
    bad = str(e)
check("one curve on its own (not a list): refused, as in Maya (the pick-walk crash)", "list of curves" in bad)
wc = open(os.path.join(ROOT, "realmaya", "window_checks.py")).read()
wl = open(os.path.join(ROOT, "core", "world_levels.py")).read()
check("...Test this release and World levels give a list", "[shape_data.circle_curve(1.0)]" in wc and
      "[shape_data.circle_curve(1.0)]" in wl)
check("the fake Maya: ls([]) lists nothing (Gus's Mac)", cmds.ls([]) == [])
facts = open(os.path.join(ROOT, "realmaya", "MAYA_FACTS.md")).read()
check("MAYA_FACTS.md: ls([]) corrected, divide by zero measured, handles joined by default",
      "lists NOTHING" in facts and "quiet from 0.00002" in facts and "unified" in facts)
from gus_rigtool.realmaya import maya_facts as MF
check("new Maya facts: ls([]) with flags, what refuses to move keys, the nearest point on a mesh",
      "mesh_points" in [f.__name__ for f in MF.FACTS] and "animation layer" in open(MF.__file__).read() and
      "type='mesh'" in open(MF.__file__).read())
claude = open(os.path.join(ROOT, "..", "CLAUDE.md")).read()
check("CLAUDE.md: every release ends with the commands to paste", "commands to paste" in claude and
      "window_checks.run()" in claude)
print("%d/%d passed" % (sum(ok), len(ok)))
