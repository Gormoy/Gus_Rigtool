# Keep the skin through a rebuild, every joint a module makes: twist joints of a bendy arm and the finger joints
# under it keep their skin slots (bound mode) / come back by name (unbind mode); after the Build, a mesh that lost
# joints from its skin is reported (never silent)
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, skin_keep, guides, modules
from gus_rigtool.core import utils
def setopt(mid, key, value, section="options"):
    for g in guides.module_groups():
        i = guides.read(g)
        if i["id"] == mid:
            s = modules.MODULES[i["type"]].complete(i["settings"]); s[section][key] = value; guides.save_settings(g, s)
            guides.update(g, modules.MODULES[i["type"]], s, 180)
bld.biped(180)
setopt("L:arm", "bendy", True); setopt("L:arm", "twist_count", 2)
bld.build_all(180)
info = [i for i in bld._infos() if i["id"] == "L:arm"][0]
st = bld._stored(info)
every = bld._module_joints([st])
print("arm joints: main", len([j for j in st["joints"] if "twist" not in j]), "| with twists and what hangs below:",
      len(every), "| twist joints in it:", sum(1 for j in every if "_twist_" in j))
_SETTINGS["build"] = dict(utils.tool_settings("build", bld.DEFAULTS), keep_skin_bound=True)
mesh = cmds.createNode("transform", name="body_geo"); cmds.createNode("mesh", name="body_geoShape", parent=mesh)
skin = cmds.createNode("skinCluster", name="body_skin")
used = ("L_humerus_jnt", "L_humerus_twist_01_jnt", "L_radius_twist_02_jnt", "L_index_02_jnt", "spine_jnt")
for i, j in enumerate(used):
    cmds.connectAttr(j + ".worldMatrix[0]", "%s.matrix[%d]" % (skin, i))
cmds.connectAttr("body_geoShape.worldMesh[0]", skin + ".outputGeometry[0]") if False else None
_skq = cmds.skinCluster
def skinCluster(*a, **k):
    if k.get("query") and k.get("influence"):
        return [x for x in (cmds.listConnections("%s.matrix[%d]" % (skin, i), source=True, destination=False) or [None] for i in range(len(used))) for x in x if x]
    if k.get("query") and k.get("geometry"):
        return ["body_geoShape"]
    return _skq(*a, **k) if _skq else None
cmds.skinCluster = skinCluster
src = lambda i: (cmds.listConnections("%s.matrix[%d]" % (skin, i), source=True, destination=False) or [None])[0]
bld.back_to_guides_selected(["L:arm"], force=True)
print("at guides, slots held:", [src(i) for i in range(len(used))])
bld.build_picked(["L:arm"], 180)
print("rebuilt, slots back on the new joints:", [src(i) for i in range(len(used))], "| pending:", skin_keep.pending())
# a joint that isn't made again: the Build says which mesh lost it
bld.back_to_guides_selected(["L:arm"], force=True)
setopt("L:arm", "twist_count", 1)
bld.build_picked(["L:arm"], 180)
print("twist_count 2 -> 1:", [src(i) for i in range(len(used))])
