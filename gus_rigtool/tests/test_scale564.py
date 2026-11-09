# 5.6.4: Make Global > World > Local leaves constraint target scales alone (pointed at the global scale, the Hare's IK
# hands in 'root' space went off at x2); a constraint target scale read from another node is found and put back;
# groups that follow a scaling control with a parent constraint but not its scale (the Hare's femur limb groups) get
# a scale constraint; Make the rig scale is undone when the scale check gets worse; joints measured growing twice
# lose their scale input; pages fit again after a button press
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import scale_check as SC, world_levels, repair, ui
from gus_rigtool.builder import publish
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
src = lambda p: cmds.listConnections(p, source=True, destination=False, plugs=True) or []

def ctrl(name, parent=None):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]

rig = cmds.createNode("transform", name="HARE_RIG")
ctrls_root = cmds.createNode("transform", name="Ctrls", parent=rig)
w = ctrl("World_ctrl", ctrls_root)
waist = ctrl("Waist_ctrl", w)
space = cmds.createNode("transform", name="L_wrist_ik_space_grp", parent=w)
con = cmds.parentConstraint(w, space)[0]
cmds.connectAttr(w + ".scale", con + ".target[0].targetScale")       # what Maya makes
fol = cmds.createNode("transform", name="Cape_fol_01")
for a in "XYZ":
    cmds.connectAttr(w + ".scale" + a, fol + ".scale" + a)

fake_curves = mock.patch.multiple("gus_rigtool.core.curves", read_shape=lambda n: [], read_style=lambda n: {},
                                  create_curve_control=lambda name, c, s=None: _mk(name))
def _mk(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
with fake_curves, mock.patch.object(publish, "is_published", return_value=False), \
        mock.patch("gus_rigtool.core.shape_data.scale", side_effect=lambda d, f: d), \
        mock.patch("gus_rigtool.core.shape_data.circle_curve", side_effect=lambda r: []):
    lines = world_levels.plan(w)
    print(lines)
    check("the plan counts the follicle (3), not the constraint", "3 thing(s) read it" in lines[1])
    got = world_levels.make(w)
g = world_levels.levels()["global"]
wl = world_levels.levels()["world"]
print(src(con + ".target[0].targetScale"), src(fol + ".scaleX"))
check("the follicle reads the global scale; the constraint's target scale still reads World_ctrl.scale",
      src(fol + ".scaleX") == ["Global_ctrl.globalScale"] and src(con + ".target[0].targetScale") == ["World_ctrl.scale"]
      and got["readers"] == 3)

# ---- a target scale read from the wrong node (what 5.6.3 left in the Hare)
cmds.connectAttr(g + ".scale", con + ".target[0].targetScale", force=True)
real_aq, real_ga = cmds.attributeQuery, cmds.getAttr
def aq(name, node=None, **k):
    if name == "targetScale" and k.get("exists"):
        return True
    return real_aq(name, node=node, **k)
def ga(plug, **k):
    if k.get("multiIndices") and plug.endswith(".target"):
        return [0]
    return real_ga(plug, **k)
with mock.patch.object(cmds, "attributeQuery", side_effect=aq), mock.patch.object(cmds, "getAttr", side_effect=ga):
    found = SC.target_scales()
    print(found)
    check("found: the constraint's target scale reads Global_ctrl - should read World_ctrl",
          len(found) == 1 and found[0][1].split("|")[-1] == "World_ctrl.scale")
    SC.fix_target_scales(found)
    check("fixed: it reads its own target's scale again", src(con + ".target[0].targetScale") == ["World_ctrl.scale"]
          and not SC.target_scales())

# ---- limb groups: follow Waist_ctrl with a parent constraint, no scale
dnt = cmds.createNode("transform", name="DO_NOT_TOUCH", parent=rig)
nodes = cmds.createNode("transform", name="L_leg_nodes_grp", parent=dnt)
limb = cmds.ls(cmds.createNode("transform", name="L_femur_limb_grp", parent=nodes), long=True)[0]
cmds.parentConstraint("Waist_ctrl", limb)
with mock.patch.object(SC, "scaled_by_rig", side_effect=lambda n, c: n.split("|")[-1] in ("Waist_ctrl", "World_ctrl")
                       or "|Ctrls|" in n):
    lg = SC.limb_groups(g)
    print(lg)
    check("found: the femur limb group, from Waist_ctrl", [(a.split("|")[-1], b.split("|")[-1]) for a, b in lg] ==
          [("L_femur_limb_grp", "Waist_ctrl")])
    check("the IK space group under the controls (already scaled) isn't", all("space" not in a for a, _b in lg))
    SC.fix_limb_groups(lg)
    check("fixed: a scale constraint from Waist_ctrl", [c for c in cmds.listRelatives(limb, children=True) or []
                                                        if "scaleConstraint" in c])
    check("then it has a scale input: not found again", not SC.limb_groups(g))

# ---- Make the rig scale: undone when the scale check gets worse; kept when it's better
undone = []
scores = [5, 9]
with mock.patch.object(SC, "_score", side_effect=lambda *a: scores.pop(0)), \
        mock.patch.object(SC, "measure_joints", return_value=([], [])), \
        mock.patch.object(repair, "rest_points", return_value={}), \
        mock.patch.object(cmds, "undo", side_effect=lambda *a, **k: undone.append(1), create=True), \
        mock.patch.object(cmds, "undoInfo", side_effect=lambda *a, **k: "gusrigMakeScalable"
                          if k.get("undoName") else True), \
        mock.patch("gus_rigtool.core.on_top.controls", return_value=[]):
    got = SC.make_scalable()
print(got)
check("worse after (5 -> 9): all of it undone, and it says why", undone == [1] and got["why"] and "5" in got["undone"]
      and "9" in got["undone"])
scores = [5, 0]
with mock.patch.object(SC, "_score", side_effect=lambda *a: scores.pop(0)), \
        mock.patch.object(SC, "measure_joints", return_value=([], [])), \
        mock.patch.object(repair, "rest_points", return_value={}), \
        mock.patch("gus_rigtool.core.on_top.controls", return_value=[]):
    got = SC.make_scalable()
check("better (5 -> 0): kept", not got["undone"] and got["before"] == 5 and got["after"] == 0)

# ---- measured twice: the scale input goes, own scale back
j1 = cmds.ls(cmds.createNode("joint", name="Tongue_01"), long=True)[0]
md = SC.give_scale(j1, g + ".globalScale")
cmds.setAttr(md + ".input1X", 1.0)
calls = [([], [j1]), ([], [])]
with mock.patch.object(SC, "_score", return_value=0), \
        mock.patch.object(SC, "measure_joints", side_effect=lambda *a: calls.pop(0)), \
        mock.patch.object(repair, "rest_points", return_value={}), \
        mock.patch("gus_rigtool.core.on_top.controls", return_value=[]):
    got = SC.make_scalable()
check("a joint measured growing twice loses its scale input", got["twice"] == 1 and not src(j1 + ".scaleX"))

# ---- Repair: the static 'scaled twice' item is gone, the new ones are offered
with mock.patch.object(SC, "scale_control", return_value=(g, g + ".globalScale")), \
        mock.patch.object(SC, "target_scales", return_value=[("c.target[0].targetScale", "World_ctrl.scale")]), \
        mock.patch.object(SC, "limb_groups", return_value=[("|L_femur_limb_grp", "|Waist_ctrl")]), \
        mock.patch("gus_rigtool.core.on_top.controls", return_value=[]):
    ids = [i.id if hasattr(i, "id") else i[0] for i in repair._scale_causes()]
print(ids)
check("Repair offers the target scales and the limb groups, not 'scale_twice'",
      "scale_targets" in ids and "scale_limbs" in ids and "scale_twice" not in ids)

# ---- pages: a fit queued after every callback
queued = []
with mock.patch.object(cmds, "evalDeferred", side_effect=lambda fn, *a, **k: queued.append(fn), create=True):
    ui._refit_queued[0] = False
    state = {"p": "x_"}
    ui.bind(state, lambda *_: None)()
    ui.bind(state, lambda *_: None)()
check("after a button press the shown page is fitted again (once, however many callbacks)", len(queued) == 1)
fits = []
with mock.patch.object(ui, "visible_tool", return_value="checker"), \
        mock.patch.dict(ui._page_cols, {"checker": ("scroll", "page")}), \
        mock.patch.object(cmds, "layout", return_value=True, create=True), \
        mock.patch.object(ui, "fit_page", side_effect=lambda p: fits.append(p)):
    queued[0]()
check("...the page of the tab shown (the Checker)", fits == ["page"] and not ui._refit_queued[0])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
