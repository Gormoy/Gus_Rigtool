# 5.6.0: Global_ctrl (scale) > World_ctrl > Local_ctrl made from the World_ctrl (the scale and whatever read it
# move to Global, what was under World goes under Local, nothing moves); the scale check (x2: what stays, what keeps
# its size, what ends up elsewhere); the usual causes found without scaling and fixed (follicles, joints held by
# constraints, meshes scaling twice, stretch rest lengths); the world turn check skips legacy_grp
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import world_levels, scale_check as SC, organize
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

def curve_ctrl(name, parent=None, pos=(0, 0, 0)):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=list(pos))
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]

rig = cmds.createNode("transform", name="HARE_RIG")
ctrls = cmds.createNode("transform", name="controls_grp", parent=rig)
wctrl = curve_ctrl("World_ctrl", ctrls)
cmds.addAttr(wctrl, longName="globalScale", attributeType="double", defaultValue=1.0)
for a in "XYZ":
    cmds.connectAttr(wctrl + ".globalScale", wctrl + ".scale" + a)
root = curve_ctrl("Root_ctrl", wctrl)
hips = curve_ctrl("Hips_ctrl", root, (0, 10, 0))
rest = cmds.createNode("multDoubleLinear", name="L_arm_Rest")
cmds.setAttr(rest + ".input1", 12.0)
cmds.connectAttr(wctrl + ".globalScale", rest + ".input2")
chain = cmds.createNode("transform", name="Cape_settings")
cmds.addAttr(chain, longName="gusScalePlug", dataType="string")
cmds.setAttr(chain + ".gusScalePlug", "World_ctrl.globalScale", type="string")
hips_before = cmds.xform(hips, query=True, worldSpace=True, matrix=True)

fake_curves = mock.patch.multiple("gus_rigtool.core.curves", read_shape=lambda n: [{"degree": 1, "form": 0,
                                  "points": [[0, 0, 0], [1, 0, 0]], "knots": [0, 1]}],
                                  read_style=lambda n: {},
                                  create_curve_control=lambda name, c, s=None: _mk(name))
def _mk(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
from gus_rigtool.builder import publish
with fake_curves, mock.patch.object(publish, "is_published", return_value=False), \
        mock.patch.object(world_levels, "find_world", return_value=wctrl):
    lines = world_levels.plan()
    print("\n".join(lines))
    check("the plan says what moves: 1 reader of the scale, 1 thing under World", "1 thing(s) read it" in lines[1]
          and "1 thing(s) under World_ctrl" in lines[2])
    got = world_levels.make()
lv = world_levels.levels()
g, w, l = lv["global"], lv["world"], lv["local"]
print(g, w, l, sep="\n")
check("Global > World's group > World > Local > Root", g.endswith("|Global_ctrl") and
      "|Global_ctrl|World_ctrl_offset|World_ctrl|Local_ctrl_offset|Local_ctrl" in l and
      cmds.ls("Root_ctrl", long=True)[0].startswith(l + "|"))
check("the scale is Global's now and scales it", cmds.attributeQuery("globalScale", node=g, exists=True) and
      not cmds.attributeQuery("globalScale", node=w, exists=True) and
      cmds.listConnections(g + ".scaleX", source=True, destination=False, plugs=True) == ["Global_ctrl.globalScale"])
check("what read World's scale reads Global's (the arm's rest length)",
      cmds.listConnections(rest + ".input2", source=True, destination=False, plugs=True) == ["Global_ctrl.globalScale"])
check("a chain that remembered World_ctrl.globalScale remembers Global's",
      cmds.getAttr(chain + ".gusScalePlug") == "Global_ctrl.globalScale")
check("nothing moved", max(abs(a - b) for a, b in zip(hips_before, cmds.xform(cmds.ls("Hips_ctrl")[0], query=True,
                                                                               worldSpace=True, matrix=True))) < 1e-9)
check("World / Local don't scale (channels hidden)", cmds.getAttr(w + ".scaleX", lock=True) and
      cmds.getAttr(l + ".scaleX", lock=True))
with mock.patch.object(publish, "is_published", return_value=False):
    try:
        world_levels.make(w)
        check("a second time: refused", False)
    except RuntimeError as e:
        check("a second time: refused", "made already" in str(e))

# ---- the usual causes
check("the scale control: Global", SC.scale_control() == (g, g + ".globalScale"))
check("scaled by the rig: under Global; not: outside it", SC.scaled_by_rig(cmds.ls("Hips_ctrl", long=True)[0], g) and
      not SC.scaled_by_rig(rig, g))
rib = cmds.createNode("transform", name="Cape_ribbon_grp", parent=rig)
cmds.setAttr(rib + ".inheritsTransform", 0)
fol = cmds.createNode("transform", name="Cape_fol_01", parent=rib)
cmds.createNode("follicle", name="Cape_fol_01Shape", parent=fol)
fctrl = curve_ctrl("Cape_fol_01_ctrl", fol)
empty = cmds.createNode("transform", name="Cape_fol_02", parent=rib)
cmds.createNode("follicle", name="Cape_fol_02Shape", parent=empty)
fols = SC.follicles(g)
check("follicles with controls under them, in a group that doesn't pass the scale on: found (the empty one not)",
      [f.split("|")[-1] for f in fols] == ["Cape_fol_01"])
SC.fix_follicles(fols, g + ".globalScale")
check("fixed: the follicle takes the global scale -> its control grows", SC.scaled_by_rig(fctrl, g) and
      not SC.follicles(g))

skel = cmds.createNode("transform", name="skeleton_grp", parent=rig)
cmds.setAttr(skel + ".inheritsTransform", 0)
jnt = cmds.createNode("joint", name="Cape_fol_01_jnt", parent=skel)
jnt = cmds.ls(jnt, long=True)[0]
with mock.patch.object(SC, "_skin_joints", return_value={jnt}), \
        mock.patch.object(SC, "_driver", side_effect=lambda j: fctrl if j == jnt else None):
    pairs = SC.joints(g)
    check("a skin joint held by a parent constraint from a control that scales: found", pairs == [(jnt, fctrl)])
    cmds.setAttr(jnt + ".scaleX", 1); cmds.setAttr(jnt + ".scaleY", 1); cmds.setAttr(jnt + ".scaleZ", 1)
    SC.fix_joints(pairs, g + ".globalScale")
    md = (cmds.listConnections(jnt + ".scaleX", source=True, destination=False) or [""])[0]
    check("fixed (5.6.3): the joint's own scale x the global scale - no scale constraint",
          md.endswith("_globalScale_md") and
          cmds.listConnections(md + ".input2X", source=True, destination=False, plugs=True) ==
          ["Global_ctrl.globalScale"] and not SC.joints(g))

geo = cmds.createNode("transform", name="Body", parent=cmds.ls("Root_ctrl")[0])
cmds.createNode("mesh", name="BodyShape", parent=geo)
geo2 = cmds.createNode("transform", name="Hood", parent=rig)
cmds.createNode("mesh", name="HoodShape", parent=geo2)
with mock.patch.object(organize, "_skinned", return_value=True):
    tw = SC.meshes_twice(g)
    check("a skinned mesh under the scaled controls: scales twice (one outside: fine)",
          [t.split("|")[-1] for t in tw] == ["Body"])
    SC.fix_meshes(tw)
    check("fixed: it doesn't inherit", not SC.meshes_twice(g))

lone = cmds.createNode("multDoubleLinear", name="R_leg_Rest")
cmds.setAttr(lone + ".input1", 10.0); cmds.setAttr(lone + ".input2", 1.0)   # Maya's default
check("a stretch rest length left at 1: found (the connected one not)", SC.rest_lengths(g + ".globalScale") ==
      ["R_leg_Rest"])
SC.fix_rest_lengths(["R_leg_Rest"], g + ".globalScale")
check("fixed: multiplied by the scale", not SC.rest_lengths(g + ".globalScale"))
check("nothing left to fix", SC.causes() == [])

# ---- the scale test itself (the fake evaluates the scale channels, not connections: scale World's scaleX)
w2 = curve_ctrl("Test_world", None)
inside = curve_ctrl("Inside_ctrl", w2, (0, 10, 0))
outside = curve_ctrl("Outside_ctrl", None, (0, 10, 0))
with mock.patch.object(SC, "scale_control", return_value=(w2, w2 + ".scaleX")), \
        mock.patch.object(organize, "_skinned", return_value=False):
    r = SC.run(nodes=[inside, outside])
print(r["off"])
check("x2: a control under it is fine; one outside 'doesn't scale'", [(n.split("|")[-1], k) for n, k, _t in r["off"]]
      == [("Outside_ctrl", "stays")])
check("put back", cmds.getAttr(w2 + ".scaleX") == 1 and cmds.getAttr(w2 + ".scaleY") == 1)

# ---- the world turn check skips legacy_grp
from gus_rigtool.core import world_turn
leg = cmds.createNode("transform", name="legacy_grp", parent=rig)
old = cmds.createNode("joint", name="R_Clavicule", parent=leg)
with mock.patch.object(world_turn, "world_control", return_value=w2):
    res = world_turn.run(world=w2)
check("world turn: the old joints in legacy_grp aren't checked",
      not [x for x in res["off"] if "R_Clavicule" in x[0]])
from gus_rigtool.builder import chain
txt = chain.jiggle_text("Cape", "Cape_settings", ["Cape_01_jiggle"], "Cape_root_dm", "Z", "Y", "t")
check("jiggle: its movement measured in the rig's own size (divided by the scale) - a bigger rig jiggles the same",
      "outputScaleX" in txt and "$p[$i] / $sc" in txt and chain.JIGGLE_VERSION == "jiggle 5.6.0")
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
