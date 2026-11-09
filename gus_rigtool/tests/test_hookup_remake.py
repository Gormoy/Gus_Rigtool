# A constraint of yours on a rebuilt node (the clavicle's offset group, driven by your chest control) is re-made
# with a fresh offset at the node's new rest: same targets, weights and what drives them, same name
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, guides, hookups
bld.biped(180); bld.build_all(180)
chest = cmds.createNode("transform", name="my_chest_ctrl"); other = cmds.createNode("transform", name="my_world_ctrl")
off = cmds.ls("L_clavicle_FK_offset", long=True)[0]
con = cmds.parentConstraint(chest, other, off, maintainOffset=True)[0]
sw = cmds.createNode("transform", name="my_switch"); cmds.addAttr(sw, longName="follow", attributeType="double")
w = cmds.parentConstraint(con, query=True, weightAliasList=True)
cmds.connectAttr(sw + ".follow", con + "." + w[0])
print("before:", con, w)
bld.back_to_guides_selected(["L:arm"], force=True)
g = [x for x in guides.module_groups() if guides.read(x)["id"] == "L:arm"][0]
cl = guides.read(g)["guides"]["clavicle"]; p = cmds.xform(cl, query=True, worldSpace=True, translation=True)
cmds.xform(cl, worldSpace=True, translation=[p[0], p[1] + 5, p[2]])
bld.build_picked(["L:arm"], 180)
off = cmds.ls("L_clavicle_FK_offset", long=True)[0]
cons = [c for c in _n(off).children if c.type == "parentConstraint"]
print("constraints on the new offset:", [c.name for c in cons], "| targets:", cons[0].attrs.get("targets") if cons else None)
alias = cmds.parentConstraint(cons[0].name, query=True, weightAliasList=True)
print("weight still driven by:", cmds.listConnections(cons[0].name + "." + alias[0], source=True, destination=False, plugs=True))
