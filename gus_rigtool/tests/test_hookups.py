# Rebuilds keep your own work: a prop under the wrist, a constraint on an FK control, a driven key from the
# settings control - through Build picked, and through Back to guides (picked) + Build picked
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld
bld.biped(180); bld.build_all(180)
prop = cmds.createNode("transform", name="sword_grp", parent="L_wrist_jnt")
watch = cmds.createNode("transform", name="watch_grp"); cmds.parentConstraint("L_radius_FK_ctrl", watch)
crv = cmds.createNode("animCurveUA", name="my_sdk_curve"); drv = cmds.createNode("transform", name="my_driven_grp")
cmds.connectAttr("L_wrist_settings_ctrl.ikfk", crv + ".input"); cmds.connectAttr(crv + ".output", drv + ".rotateX")
def check(when):
    print(when)
    print("   sword under:", cmds.listRelatives("sword_grp", parent=True))
    print("   watch constraint target from:", sorted(set(s.name for s, sa, d, da in S.conns if d.name.startswith("watch_grp_parentConstraint") and da.startswith("target"))))
    print("   sdk input from:", [s.name + "." + sa for s, sa, d, da in S.conns if d.name == "my_sdk_curve" and da == "input"])
check("before")
bld.build_picked(["L:arm"], 180); check("after Build picked")
bld.back_to_guides_selected(["L:arm"], force=True); print("   sword waiting in the world:", cmds.listRelatives("sword_grp", parent=True))
bld.build_picked(["L:arm"], 180); check("after Back to guides + Build picked")
