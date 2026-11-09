# Publish / Unpublish on a built biped: what gets locked, hidden, saved, and that Unpublish puts it back
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, publish, guides
bld.biped(100); bld.build_all(100)
ctrls = publish.rig_controls()
print("controls:", len(ctrls))
snap = {p: (cmds.getAttr(p, lock=True), cmds.getAttr(p, keyable=True)) for c in ctrls[:5] for p in [c + ".translateX", c + ".scaleX"]}
done = publish.publish()
print("\n".join(done))
print("published:", publish.is_published())
c0 = ctrls[0]
print("pose attr on first control:", cmds.getAttr(c0 + ".gusDefaultPose")[:60])
g = cmds.listRelatives(c0, parent=True, fullPath=True)[0]
print("offset tx locked:", cmds.getAttr(g + ".translateX", lock=True), "keyable:", cmds.getAttr(g + ".translateX", keyable=True))
print("skeleton visible:", cmds.getAttr(publish._group("skeleton") + ".visibility"))
print("guides visible:", cmds.getAttr(guides.top_group(False) + ".visibility"))
publish.unpublish()
print("published after unpublish:", publish.is_published())
print("offset tx locked:", cmds.getAttr(g + ".translateX", lock=True), "keyable:", cmds.getAttr(g + ".translateX", keyable=True))
print("skeleton visible:", cmds.getAttr(publish._group("skeleton") + ".visibility"))
print("controls back as they were:", snap == {p: (cmds.getAttr(p, lock=True), cmds.getAttr(p, keyable=True)) for p in snap})
publish.publish(); bld.build_picked(["L:arm"], 100)
print("rebuild unpublishes:", not publish.is_published())
