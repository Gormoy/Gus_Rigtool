# Spaces from a hand-made rig: scan suggests root / cog / hips / chest, adopt offers them,
# a builder arm's IK hand follows them (default root), plus an extra space written in its settings
exec(open("fakemaya.py").read())
from unittest import mock
captured = {}
from gus_rigtool.builder import existing, build as bld, guides, modules, controls
real_add = controls.add_spaces
def spy(side, part, ctrl, offset, targets, kind="parent", default=0):
    captured[part] = ([(l, n.split("|")[-1]) for l, n in targets], default)
    return real_add(side, part, ctrl, offset, targets, kind, default)
controls.add_spaces = spy
def ctrl(name, parent=None, pos=(0, 0, 0)):
    c = cmds.createNode("transform", name=name, parent=parent); cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    cmds.xform(c, worldSpace=True, translation=pos); return cmds.ls(c, long=True)[0]
def jnt(name, parent, pos):
    j = cmds.createNode("joint", name=name, parent=parent); cmds.xform(j, worldSpace=True, translation=pos)
    return cmds.ls(j, long=True)[0]
wc = ctrl("World_ctrl"); cog = ctrl("COG_ctrl", wc, (0, 100, 0))
hips_c = ctrl("Hips_ctrl", cog, (0, 100, 0)); chest_c = ctrl("Chest_ctrl", cog, (0, 140, 0))
head_c = ctrl("Head_ctrl", wc, (0, 170, 0))
hj = jnt("hips_jnt", None, (0, 100, 0)); sj = jnt("spine_jnt", hj, (0, 120, 0)); cj = jnt("chest_jnt", sj, (0, 140, 0))
cmds.parentConstraint(hips_c, hj); cmds.parentConstraint(chest_c, cj)
cmds.select(cog)
info = existing.scan()
sp = existing.suggest_spaces(info)
print("suggested:", existing.spaces_text(sp))
existing.adopt("spine", "C", info["controls"], spaces=existing.parse_spaces(existing.spaces_text(sp)))
g = bld.add_module("arm", "L", "arm", 180)
s = guides.read(g)["settings"]; s["options"]["extra_spaces"] = "head = Head_ctrl, nothing = Missing_ctrl"
guides.save_settings(g, s)
bld.build_all(180)
for k in sorted(captured):
    print(k, "->", captured[k][0], "default:", captured[k][1])
print("IK hand space attr:", cmds.attributeQuery("space", node="L_wrist_IK_ctrl", exists=True))
