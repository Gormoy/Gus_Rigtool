# Ribbon builds in one <prefix>_ribbon_grp: organize existing builds, tags still find the ribbon, under a parent
exec(open("fakemaya.py").read())
from gus_rigtool.core import ribbon
surf = cmds.createNode("nurbsSurface", name="L_lid_ribbonShape"); surf_t = cmds.ls("L_lid_ribbon", long=True)[0]
fols = cmds.ls(cmds.createNode("transform", name="L_lid_follicles_grp"), long=True)[0]
ctrls = cmds.ls(cmds.createNode("transform", name="L_lid_ctrls_grp"), long=True)[0]
ribbon._tag([fols, ctrls], surf_t, "", {"rrbSettings": '{"prefix": "L_lid"}'})
print("builds before:", list(ribbon._find_builds()))
made = ribbon.organize_builds("")
print("made:", made)
print("children:", sorted(x.split("|")[-1] for x in cmds.listRelatives(made[0], children=True)))
print("inherits transform:", cmds.getAttr(made[0] + ".inheritsTransform"))
print("builds after (ribbon found in the group):", list(ribbon._find_builds()))
print("again: nothing to do:", ribbon.organize_builds(""))
ctl = cmds.ls(cmds.createNode("transform", name="controls_grp"), long=True)[0]
g = ribbon.group_build(ribbon._resolve(surf_t), [ribbon._resolve(fols)], "L_lid", "controls_grp")
print("same group reused, now under:", g)
