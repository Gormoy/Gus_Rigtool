# Existing rig: a hand-made arm (joints + FK controls + IK + switch). Scan it, adopt it (taught IK/FK),
# then rebuild it with the builder on its joints, check hook-ups, replace (old part into legacy_grp).
exec(open("fakemaya.py").read())
from unittest import mock
_real_ik = cmds.ikHandle
cmds.ikHandle = mock.MagicMock(side_effect=lambda *a, **k: (["L_old_arm_ikHandle", "eff1"] if not k.get("query") else
                               ({"startJoint": "L_old_humerus", "endEffector": "eff1"}.get([x for x in k if x != "query"][0]))))
from gus_rigtool.builder import existing, build as bld, guides, limb
def jnt(name, parent, pos):
    j = cmds.createNode("joint", name=name, parent=parent); cmds.xform(j, worldSpace=True, translation=pos)
    return cmds.ls(j, long=True)[0]
def ctrl(name, parent, pos):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent); cmds.xform(off, worldSpace=True, translation=pos)
    c = cmds.createNode("transform", name=name, parent=off); cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]
skel = cmds.createNode("transform", name="old_skeleton")
clav = jnt("L_old_clavicle", skel, (2, 140, 0)); hum = jnt("L_old_humerus", clav, (15, 140, -1))
rad = jnt("L_old_radius", hum, (40, 140, -3)); wri = jnt("L_old_wrist", rad, (65, 140, 0))
grp = cmds.ls(cmds.createNode("transform", name="L_old_arm_ctrls"), long=True)[0]
fk = [ctrl("L_old_%s_fk" % n, grp, p) for n, p in (("humerus", (15, 140, -1)), ("radius", (40, 140, -3)), ("wrist", (65, 140, 0)))]
for c, j in zip(fk, (hum, rad, wri)):
    cmds.parentConstraint(c, j)
ik = ctrl("L_old_arm_ik", grp, (65, 140, 0)); pv = ctrl("L_old_arm_pv", grp, (40, 140, -30))
clav_c = ctrl("L_old_clavicle_ctrl", grp, (2, 140, 0)); cmds.parentConstraint(clav_c, clav)
cmds.addAttr(clav_c, longName="ikFkBlend", attributeType="double", keyable=True)
prop = cmds.createNode("transform", name="sword_grp", parent=wri)                     # something hanging from the arm
watch = cmds.createNode("transform", name="watch_grp"); cmds.parentConstraint(fk[1], watch)
cmds.select(grp)
info = existing.scan()
print("scan controls:", sorted(c.split("|")[-1] for c in info["controls"]))
print("scan joints:", sorted(j.split("|")[-1] for j in info["joints"]))
print("switches:", [(c.split("|")[-1], a) for c, a in info["switches"]])
print("hook-ups:", existing.hookup_lines(info["hookups"]))
# adopt with a taught limb
g = existing.adopt("old_arm", "L", info["controls"], [dict(name="L_old_arm", fk=fk, joints=[hum, rad, wri], ik=ik, pv=pv,
                   switch=clav_c + ".ikFkBlend", fk_value=0, ik_value=1)])
print("adopted:", existing.read_adopted(g)["id"], "| taught:", sorted(existing.taught_data()))
cmds.select(fk[0]); limb.match_selected("ik"); print("IK/FK match on the adopted arm -> switch:", getAttr(clav_c + ".ikFkBlend"))
print("publish sees adopted controls:", len([c for c in __import__("gus_rigtool.builder.publish", fromlist=["x"]).rig_controls() if "old" in c]))
existing.forget_adopted(g); print("forgot:", existing.adopted_groups(), sorted(existing.taught_data()))
# place a builder arm on the old joints (no hand joint: it is made up), build, check, replace
cmds.ikHandle = _real_ik
mg = existing.place_on_joints("arm", "L", "arm", [clav, hum, rad, wri], 180)
gi = guides.read(mg)
print("placed_on:", gi["settings"]["placed_on"])
print("guides on the joints:", all(abs(a - b) < 1e-6 for r, j in (("humerus", hum), ("wrist", wri))
      for a, b in zip(cmds.xform(gi["guides"][r], query=True, worldSpace=True, translation=True), cmds.xform(j, query=True, worldSpace=True, translation=True))))
print("hand guide made up past the wrist:", [round(v, 2) for v in cmds.xform(gi["guides"]["hand"], query=True, worldSpace=True, translation=True)])
bld.build_picked([gi["id"]], 180)
p = existing.plan_replace(mg, [grp])
print("\n".join(existing.plan_lines(p)))
_p, notes = existing.replace(mg, [grp])
print("\n".join(notes))
print("sword now under:", cmds.listRelatives("sword_grp", parent=True)[0], "| old arm controls in:", cmds.ls(grp.split("|")[-1], long=True)[0])
print("old joints in backup:", [x.split("|")[-1] for x in cmds.listRelatives(existing.LEGACY, children=True)])
existing.remove_backup(); print("backup removed:", not cmds.objExists(existing.LEGACY))
# skin swap (stubbed skinCluster): the new joint takes the old joint's matrix slot, bind pre-matrix = its inverse
old_j = jnt("old_spine", None, (0, 100, 0)); new_j = jnt("new_spine", None, (0, 100, 0))
cmds.setAttr(new_j + ".jointOrient", 0, 0, 90)
calls = []
skin_q = lambda *a, **k: [old_j] if k.get("influence") else None
with mock.patch.object(cmds, "skinCluster", side_effect=skin_q, create=True), \
     mock.patch.object(cmds, "listConnections", side_effect=lambda *a, **k: ["skinCluster1.matrix[2]"]), \
     mock.patch.object(cmds, "connectAttr", side_effect=lambda a, b, **k: calls.append(("connect", a.split("|")[-1], b))), \
     mock.patch.object(cmds, "setAttr", side_effect=lambda p, *v, **k: calls.append(("set", p, [round(x, 3) for x in v[:16]]))):
    done, skipped = existing.swap_influences({old_j: new_j}, ["skinCluster1"])
print("swapped:", [(s, o.split("|")[-1], n.split("|")[-1]) for s, o, n in done], skipped)
for c in calls:
    print("  ", c)
