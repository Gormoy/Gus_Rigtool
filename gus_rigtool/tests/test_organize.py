# Organize: analyze a messy Outliner, the plan (with why), change a row, apply, restore
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import organize
def tr(name, parent=None):
    return cmds.ls(cmds.createNode("transform", name=name, parent=parent), long=True)[0]
body = tr("body_geo"); cmds.createNode("mesh", name="body_geoShape", parent=body)
prop = tr("rock_geo"); cmds.createNode("mesh", name="rock_geoShape", parent=prop)
proxy = tr("body_proxy"); cmds.createNode("mesh", name="body_proxyShape", parent=proxy)
ctrls = tr("arm_ctrls"); c = tr("L_arm_ctrl", ctrls); cmds.createNode("nurbsCurve", name="L_arm_ctrlShape", parent=c)
root = cmds.ls(cmds.createNode("joint", name="root_jnt"), long=True)[0]; cmds.createNode("joint", name="spine_jnt", parent=root)
ik = tr("L_leg_ik_grp"); cmds.createNode("locator", name="L_leg_locShape", parent=ik)
empty = tr("null1")
rib = tr("L_lid_ribbon_grp"); cmds.addAttr(rib, longName="rrbGroup", dataType="string")
keep = tr("cam_rig_grp"); cmds.createNode("mesh", name="cam_rigShape", parent=keep)
skinned = lambda node, **k: ["skinCluster1"] if "body_geo" in str(node) else []
cmds.listHistory = skinned
cmds.ls = (lambda real: (lambda *a, **k: (["skinCluster1"] if a and a[0] == ["skinCluster1"] and k.get("type") == "skinCluster" else real(*a, **k))))(cmds.ls)
o = dict(organize.DEFAULTS, rules="*_proxy = geo", never="cam_*")
rows = organize.analyze(o)
print(organize.plan_text(rows, o))
for r in rows:
    if r["name"] == "rock_geo":
        r["dest"] = "leave"                          # the user changes a row
notes = organize.apply(rows, o)
print("\n".join(notes))
for n in ("body_geo", "L_arm_ctrl", "root_jnt", "L_leg_ik_grp", "L_lid_ribbon_grp", "rock_geo", "cam_rig_grp"):
    print("%-18s" % n, cmds.ls(n, long=True)[0])
print("rig_nodes hidden:", cmds.getAttr("rig_nodes_grp.visibility"), "| skinned body inherits:", cmds.getAttr("body_geo.inheritsTransform"))
print("restored:", sorted(organize.restore()))
print("after restore:", cmds.ls("body_geo", long=True)[0], cmds.ls("root_jnt", long=True)[0], "| inherits:", cmds.getAttr("body_geo.inheritsTransform"),
      "| left marked:", organize.organized_nodes())
