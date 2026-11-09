# Keep the skin bound: the arm's joint slots in the skin are held by hidden locators while the arm is rebuilt,
# then the new joints (same names) take them back with a new bind matrix - no unbind
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, skin_keep
from gus_rigtool.core import utils
bld.biped(180); bld.build_all(180)
_SETTINGS["build"] = dict(utils.tool_settings("build", bld.DEFAULTS), keep_skin_bound=True)
skin = cmds.createNode("skinCluster", name="body_skin")
for i, j in enumerate(("L_humerus_jnt", "L_radius_jnt", "spine_jnt")):
    cmds.connectAttr(j + ".worldMatrix[0]", "%s.matrix[%d]" % (skin, i))
bld.build_picked(["L:arm"], 180)
src = lambda i: cmds.listConnections("%s.matrix[%d]" % (skin, i), source=True, destination=False)
print("after Build picked:", [src(i) for i in range(3)], "| holders left:", cmds.objExists(skin_keep.HOLDERS))
print("new bind matrix set:", "bindPreMatrix[0]" in _n(skin).attrs, "| waiting:", skin_keep.pending())
# a joint that isn't made again keeps its weights on the holder, and the log says so
bld.back_to_guides_selected(["L:arm"], force=True)
print("while at guides:", [src(i) for i in range(3)])
cmds.rename("L_radius_jnt", "keep_me") if cmds.objExists("L_radius_jnt") else None
bld.build_picked(["L:arm"], 180)
print("back:", [src(i) for i in range(3)], "| pending:", skin_keep.pending())
