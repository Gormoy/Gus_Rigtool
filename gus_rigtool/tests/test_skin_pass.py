# 4.0 skin pass: corrective (volume) joints on arms / legs / quadruped legs, labels made on bind and kept after a
# mirror, 'Add missing twins' (the mirror image made, in the skins, labelled)
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.builder import build as bld, guides, modules
from gus_rigtool.core import joint_labels as JL, skin_tools, skin_mirror

def setopt(mid, key, value):
    for g in guides.module_groups():
        i = guides.read(g)
        if i["id"] == mid:
            s = modules.MODULES[i["type"]].complete(i["settings"]); s["options"][key] = value; guides.save_settings(g, s)
            guides.update(g, modules.MODULES[i["type"]], s, 180)

def cor_report():
    out = []
    for j in sorted(x for x in (cmds.ls(type="joint", long=True) or []) if x.endswith("_cor_jnt")):
        parent = cmds.listRelatives(j, parent=True)[0]
        oc = [c for c in (cmds.listRelatives(j, children=True, fullPath=True) or []) if cmds.nodeType(c) == "orientConstraint"]
        targets = cmds.orientConstraint(oc[0], query=True, targetList=True) if oc else []
        out.append("%s under %s, half way between %s" % (j.split("|")[-1], parent, targets))
    return out

bld.biped(180)
for side in "LR":
    for m in ("arm", "leg"):
        setopt("%s:%s" % (side, m), "correctives", True)
print("preview has them:", sorted(n for n in bld.preview() if n.endswith("_cor_jnt")) if isinstance(bld.preview()[0], str) else
      sorted(x for p in bld.preview() for x in (p if isinstance(p, (list, tuple)) else [p]) if str(x).endswith("_cor_jnt")))
bld.build_all(180)
for line in cor_report():
    print(" ", line)
print("bind joints include them:", sum(1 for j in skin_tools.rig_joints() if j.endswith("_cor_jnt")))

# rebuild keeps them
bld.back_to_guides(True); bld.build_all(180)
print("after a rebuild:", len([x for x in cmds.ls(type="joint") if x.endswith("_cor_jnt")]))

# labels on bind
geo = cmds.polyCube(name="body_geo")[0] if hasattr(cmds, "polyCube") else None
if not geo:
    t = cmds.createNode("transform", name="body_geo"); cmds.createNode("mesh", name="body_geoShape", parent=t); geo = "body_geo"
for j in skin_tools.rig_joints():
    cmds.setAttr(j + ".side", 0); cmds.setAttr(j + ".type", 0)
skin_tools.bind([geo])
lab = lambda n: (cmds.getAttr(cmds.ls(n, long=True)[0] + ".side"), cmds.getAttr(cmds.ls(n, long=True)[0] + ".otherType"))
print("labelled on bind:", lab("L_radius_cor_jnt"), lab("R_radius_cor_jnt"))

# quadruped legs
cmds.file(new=True, force=True) if hasattr(cmds, "file") and callable(getattr(cmds, "file", None)) else None
S.__init__() if hasattr(S, "__init__") else None
bld.quadruped(100)
for side in "LR":
    for m in ("back_leg", "front_leg"):
        setopt("%s:%s" % (side, m), "correctives", True)
bld.build_all(100)
quad = cor_report()
print("quadruped:", len(quad), "corrective joints")
for line in quad[:4]:
    print(" ", line)

# add missing twins
lone = cmds.createNode("joint", name="L_humerus_extra_jnt", parent=cmds.ls("L_humerus_jnt", long=True)[0])
cmds.xform(lone, worldSpace=True, translation=(30, 140, 0))
made_mirror = []
def mirrorJoint(j, mirrorYZ=True, mirrorBehavior=True, **k):
    p = cmds.listRelatives(j, parent=True, fullPath=True)
    n = cmds.createNode("joint", name="mirrored1", parent=p[0] if p else None)
    pos = cmds.xform(j, query=True, worldSpace=True, translation=True)
    cmds.xform(n, worldSpace=True, translation=(-pos[0], pos[1], pos[2]))
    made_mirror.append(n)
    return [n]
cmds.mirrorJoint = mirrorJoint
def duplicate(j, parentOnly=True, name=None):
    n = cmds.createNode("joint", name=name, parent=cmds.listRelatives(j, parent=True, fullPath=True)[0])
    cmds.xform(n, worldSpace=True, translation=cmds.xform(j, query=True, worldSpace=True, translation=True))
    return [n]
cmds.duplicate = duplicate
added = []
cmds.listConnections = (lambda real: lambda plug, **k: ["body_skinCluster"] if plug.endswith(".worldMatrix") and "extra" in plug else real(plug, **k))(cmds.listConnections)
cmds.skinCluster = (lambda real: lambda *a, **k: added.append((a, k.get("addInfluence"))) if k.get("addInfluence") else real(*a, **k))(cmds.skinCluster)
made = JL.add_twins([lone])
print("missing twin made:", [m.split("|")[-1] for m in made], "| under:", cmds.listRelatives(made[0], parent=True)[0],
      "| at:", [round(v, 1) for v in cmds.xform(made[0], query=True, worldSpace=True, translation=True)],
      "| into the skin:", [x[1].split("|")[-1] for x in added], "| labels:", lab("L_humerus_extra_jnt"), lab("R_humerus_extra_jnt"))
print("again: nothing to do:", JL.add_twins([lone]))
