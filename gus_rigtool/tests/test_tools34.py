# 3.4 tools: Spaces (make / add target / next / remove), Channels, Rename, Connect, Constraints
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
def _da(plug, **k):
    n, a = _split(plug); n.user.pop(a, None)
    S.conns[:] = [c for c in S.conns if not ((c[2] is n and c[3] == a) or (c[0] is n and c[1] == a))]
cmds.deleteAttr = _da
_add = cmds.addAttr
def addAttr(*a, **k):
    if k.get("edit"):
        n, at = _split(a[0]); n.enums[at] = k.get("enumName", n.enums.get(at)); return
    _add(*a, **k)
cmds.addAttr = addAttr
from gus_rigtool.core import spaces, attrs, renamer, connector, constraints
from gus_rigtool.tools import channels_tool as ch

print("== spaces")
wld = cmds.createNode("transform", name="World_ctrl")
chest = cmds.createNode("transform", name="C_chest_ctrl")
cog = cmds.createNode("transform", name="COG_ctrl")
off = cmds.createNode("transform", name="L_hand_IK_offset")
ctrl = cmds.createNode("transform", name="L_hand_IK_ctrl", parent=off); cmds.createNode("nurbsCurve", name="L_hand_IK_ctrlShape", parent=ctrl)
print("labels:", [spaces.default_label(x) for x in (wld, chest, cog)])
print("piece (offset group):", spaces.piece_of(ctrl))
for bad in ([("world", wld)], [("a", wld), ("a", chest)], [("world", wld), ("me", ctrl)], [("w", wld), ("x", "nope")]):
    try:
        spaces.make(ctrl, bad); print("NOT refused")
    except RuntimeError as e:
        print("refused:", e)
grp = spaces.make(ctrl, [("world", "World_ctrl"), ("chest", "C_chest_ctrl")], "parent", "space", 1)
print("group:", grp, "| ctrl now:", cmds.ls("L_hand_IK_ctrl", long=True)[0])
print("enum:", _n("L_hand_IK_ctrl").enums["space"], "value", cmds.getAttr("L_hand_IK_ctrl.space"))
con = spaces.read("L_hand_IK_ctrl")["constraint"]
print("constraint targets:", _n(con).attrs["targets"], "| weights driven by:",
      sorted(cmds.listConnections(con, source=True, destination=False, type="condition") or []))
try:
    spaces.make("L_hand_IK_ctrl", [("w", wld), ("c", cog)]); print("second switch NOT refused")
except RuntimeError as e:
    print("second switch refused:", str(e)[:50])
print("add cog:", spaces.add_target("L_hand_IK_ctrl", "cog", "COG_ctrl"), _n("L_hand_IK_ctrl").enums["space"],
      "| conds", len(spaces.read("L_hand_IK_ctrl")["conditions"]))
spaces.switch("L_hand_IK_ctrl", 2); print("switched to", cmds.getAttr("L_hand_IK_ctrl.space"))
spaces.remove("L_hand_IK_ctrl")
print("removed: offset parent", cmds.listRelatives("L_hand_IK_offset", parent=True), "| space attr",
      cmds.attributeQuery("space", node="L_hand_IK_ctrl", exists=True), "| group", cmds.objExists(grp),
      "| conds left", cmds.ls(type="condition"))
lone = cmds.createNode("transform", name="prop_ctrl"); cmds.createNode("nurbsCurve", name="prop_ctrlShape", parent=lone)
print("no offset group -> the control itself:", spaces.piece_of(lone))
spaces.make(lone, [("world", wld), ("chest", chest)], "orient", "follow")
print("orient switch:", cmds.listRelatives("prop_ctrl", parent=True), [c.type for c in _n(spaces.read("prop_ctrl")["group"]).children])

print("== channels")
k = cmds.createNode("transform", name="L_arm_FK_ctrl"); controls_ = __import__("gus_rigtool.builder.controls", fromlist=["x"])
controls_.add_float(k, "curl"); controls_.separator(k, "Info"); controls_.add_string(k, "gusNote", "x")
print("own channels:", ch.user_channels(k))
n = ch.set_state([k], ["sx", "sy", "sz", "v"], True, True, "hide")
print("locked+hidden", n, ":", sorted(_n(k).locks), sorted(_n(k).hidden))
ch.set_state([k], ["sx"], False, False, "key")
print("sx back:", "sx" in _n(k).locks, "sx" in _n(k).hidden)
k2 = cmds.createNode("transform", name="R_arm_FK_ctrl"); controls_.add_float(k2, "curl")
ch.copy_state(k, [k2], ["sy", "sz", "v"], True)
print("copied to R:", sorted(_n(k2).locks), sorted(_n(k2).hidden))
print(ch.report([k2]))

print("== rename")
r = [cmds.createNode("joint", name="joint%d" % i) for i in range(1, 4)]
o = {"base": "spine_##_jnt", "start": 1, "pad": 2, "step": 1}
print([x[2] for x in renamer.plan(r, o)])
print([x[2] for x in renamer.plan(r, {"base": "tail", "start": 0, "pad": 3, "step": 2})])
print([x[2] for x in renamer.plan(["L_arm_jnt"], {"search": "arm", "replace": "leg", "prefix": "x_", "suffix": "_b"})])
print([x[2] for x in renamer.plan(["L_arm_jnt", "ns:R_leg_ctrl"], {"swap": True})])
g = cmds.createNode("transform", name="L_ear_ctrl_ctrl"); cmds.createNode("nurbsCurve", name="earShape", parent=g)
e = cmds.createNode("transform", name="R_thing")
print("fix:", [x[2] for x in renamer.plan([g, e, r[0]], {"fix": True})])
print("clash:", renamer.clashes(renamer.plan(r, {"base": "same"})), renamer.clashes(renamer.plan(r[:2], {"suffix": "_x"})))
done = renamer.apply(renamer.plan(r, o), shapes=False)
print("renamed:", done)

print("== connect")
drv = cmds.createNode("transform", name="driver")
dn = [cmds.createNode("transform", name="d%d" % i) for i in range(2)]
print(connector.pairs(["rx"], []), connector.pairs(["rx"], ["ry", "rz"]), connector.pairs(["a", "b"], ["c", "d"]))
try:
    connector.pairs(["a", "b"], ["c"]); print("NOT refused")
except ValueError as e:
    print("refused:", e)
print("direct:", connector.connect(drv, dn, [("rx", "rx")]))
print("multiply:", connector.connect(drv, dn[:1], [("tx", "ty")], 1, 0.5), cmds.listConnections("d0.ty", source=True, destination=False))
cmds.setAttr("d1.tz", lock=True)
print("locked:", connector.connect(drv, dn[1:], [("tz", "tz")]))
print("break:", connector.break_incoming(dn, ["rx", "ty"]), cmds.listConnections("d0.rx", source=True, destination=False))
print(connector.report([drv]))
print("parse:", connector.parse("tx, .ry rz;curl"))

print("== constraints")
t1, t2, t3, dd = [cmds.createNode("transform", name=x) for x in ("tA", "tB", "tC", "dd")]
print(constraints.plan([t1, t2, dd], 0), constraints.plan([t1, t2, dd], 1))
try:
    constraints.plan([t1, t2, dd], 2)
except RuntimeError as e:
    print("pairs refused:", e)
c1 = constraints.make([t1, t2], dd, "parent", True, "y", "")
print("made:", c1, _n(c1).attrs["targets"])
print("targets_of:", constraints.targets_of(c1))
print("swap:", constraints.swap(dd, [t3]), _n(c1).attrs["targets"])
try:
    constraints.make([t1], dd, "poleVector")
except RuntimeError as e:
    print("pv refused:", e)
print(constraints.report([dd, t3]))
print("removed:", constraints.remove([dd]), constraints.constraints_on(dd))

print("== pages")
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool.core import ui
from gus_rigtool.tools import space_tool as sp, rename_tool as rn, connect_tool as cn, constraint_tool as ct
for key, mod in (("spaces", sp), ("channels", ch), ("rename", rn), ("connect", cn), ("constrain", ct)):
    _cur[0] = None; cmds.columnLayout("root_" + key); ui._build_tool(key, "p_%s_" % key); mod._P["p"] = "p_%s_" % key
a1, a2 = cmds.createNode("transform", name="hipsA"), cmds.createNode("transform", name="chestA")
pc = cmds.createNode("transform", name="L_foot_IK_ctrl")
cmds.select([a1, a2, pc]); sp.load_selection()
print("spaces list:", sp._st()["targets"], "| ctrl:", UI["p_spaces_Ctrl"]["text"], "| light:", sp._light()[1])
with mock.patch.object(cmds, "confirmDialog", return_value="Make"):      # 5.6.7: it shows control / targets first
    sp.make()
print("light after:", sp._light()[1])
sp.try_next(); print("space now:", cmds.getAttr("L_foot_IK_ctrl.space"))
cmds.select(["tA", "tB"]); cmds.textField("p_rename_Base", edit=True, text="arm_#_ctrl"); rn.run()
print("renamed:", cmds.objExists("arm_01_ctrl"), cmds.objExists("arm_02_ctrl"))
cmds.select(["driver", "d1"]); cmds.textField("p_connect_Src", edit=True, text="ry"); cn.run()
print("connected:", cmds.listConnections("d1.ry", source=True, destination=False, plugs=True))
cmds.select(["tC", "d1"]); ct.make(); print("constrained:", constraints.constraints_on("d1"))
cmds.select(["L_arm_FK_ctrl"]); ch._tick(["tx", "ty"]); ch._do(True, None, "locked")
print("tx ty locked:", sorted(x for x in _n("L_arm_FK_ctrl").locks if x in ("tx", "ty")))
