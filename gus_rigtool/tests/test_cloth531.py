# 5.3.1: controls in front of the mesh (face skipped); Copy / Skin like the body keep the source's normalization and
# bring every vertex to 1 (the Hare's Bandages_Arms pulled to the world origin); Cloth layer refuses a posed rig;
# Repair weights
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import on_top, skin_tools, cloth
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def ctrl(name):
    t = cmds.createNode("transform", name=name)
    s = cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    cmds.setAttr(s + ".alwaysDrawOnTop", 0)
    return cmds.ls(t, long=True)[0]

# ---- controls on top
names = ["COG_ctrl", "Spine_01_FK_ctrl", "L_clavicle_ctrl", "L_Brow_02_ctrl", "Mouth_fol_14_ctrl", "L_Ear_01_ctrl",
         "Jaw_ctrl", "L_Shear_ctrl"]
for n in names:
    ctrl(n)
on = lambda n: cmds.getAttr(n + "Shape.alwaysDrawOnTop")
changed, face, missing = on_top.apply()
print(changed, face, missing, dict((n, on(n)) for n in names))
check("every body control in front", all(on(n) for n in ("COG_ctrl", "Spine_01_FK_ctrl", "L_clavicle_ctrl",
                                                          "L_Shear_ctrl")))
check("face controls left as they were (brow, mouth, ear, jaw)", not any(on(n) for n in (
    "L_Brow_02_ctrl", "Mouth_fol_14_ctrl", "L_Ear_01_ctrl", "Jaw_ctrl")) and face == 4)
check("count: 4 of 8 on top", on_top.count() == (4, 8))
on_top.apply(skip_face=False)
check("Skip face unticked: all of them", all(on(n) for n in names))
on_top.apply(on=False)
check("Normal: all off again", not any(on(n) for n in names))
on_top.apply([cmds.ls("COG_ctrl", long=True)[0]])
check("only the selected ones", on("COG_ctrl") and not on("Spine_01_FK_ctrl"))

# ---- Copy skin: a new skin takes the source's normalization (Post), then every vertex to 1
src = cmds.createNode("skinCluster", name="bodySkin"); cmds.setAttr(src + ".normalizeWeights", 2)
calls = []
def skinCluster(*a, **k):
    if k.get("query"):
        return ["|a", "|b"] if k.get("influence") else (4 if k.get("maximumInfluences") else 0)
    d = cmds.createNode("skinCluster", name="Bandages_Arms_skinCluster")
    cmds.setAttr(d + ".normalizeWeights", 1)
    return [d]
with mock.patch.object(skin_tools, "skin_of", lambda g: "bodySkin" if g == "Body" else None), \
        mock.patch.object(skin_tools, "_need_skin", lambda g: "bodySkin"), \
        mock.patch.object(skin_tools, "influences", lambda s: ["|a", "|b"]), \
        mock.patch.object(cmds, "skinCluster", side_effect=skinCluster, create=True), \
        mock.patch.object(cmds, "copySkinWeights", side_effect=lambda **k: calls.append("copy"), create=True), \
        mock.patch.object(skin_tools, "bad_sums", lambda s, g: list(range(380))), \
        mock.patch.object(cmds, "skinPercent", side_effect=lambda s, g, **k: calls.append(("normalize", s, k)),
                          create=True):
    skin_tools.copy(source="Body", targets=["Bandages_Arms"])
print(calls)
check("the new skin is Post like the body", cmds.getAttr("Bandages_Arms_skinCluster.normalizeWeights") == 2)
check("after the copy, every vertex brought to 1", calls[0] == "copy" and calls[1][0] == "normalize" and
      calls[1][2].get("normalize") is True)

# ---- off rest: a joint moved since it was bound
I = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
def at(x, y, z):
    return I[:12] + [x, y, z, 1.0]
mats = {"sk.bindPreMatrix[0]": at(-10, -100, 0), "|elbow.worldMatrix[0]": at(10, 100, 0),
        "sk.bindPreMatrix[1]": at(-30, -100, 0), "|wrist.worldMatrix[0]": at(30, 80, 5)}
with mock.patch.object(cloth, "_influences", lambda s: ["|elbow", "|wrist"]), \
        mock.patch.object(cloth, "_logical", lambda s, j: 0 if "elbow" in j else 1), \
        mock.patch.object(cmds, "getAttr", side_effect=lambda p, **k: mats[p]):
    off = cloth.off_rest("sk", 100.0)
print(off)
check("a posed joint is found, the one at rest isn't", [o[0] for o in off] == ["|wrist"] and abs(off[0][1] -
                                                                                              (400 + 25) ** 0.5) < 1e-6)
# cloth layer refuses while posed (and goes back to the frame it was on)
times = []
def currentTime(*a, **k):
    if k.get("query"):
        return 37.0
    times.append(a[0])
with mock.patch.object(cloth, "_skin", lambda m: "sk"), \
        mock.patch.object(cloth, "ribbon_joints", lambda r: ["|L_Cuff_fol_01_jnt"]), \
        mock.patch.object(cloth, "_points", lambda m, s=None: [(0, 0, 0), (0, 100, 0)]), \
        mock.patch.object(cloth, "off_rest", lambda s, size: [("|L_elbow_jnt", 3.0, 40.0)]), \
        mock.patch.object(cmds, "currentTime", side_effect=currentTime, create=True):
    try:
        cloth.cloth_layer("Shirt", ["L_Cuff"])
        refused = ""
    except RuntimeError as e:
        refused = str(e)
print(refused)
check("Cloth layer on a posed rig: refused, with the joint and what to do", "isn't at rest" in refused and
      "L_elbow_jnt" in refused and "Remove the range of motion" in refused)
check("...and the frame put back", times[-1] == 37.0)

# ---- repair
with mock.patch.object(cloth, "_skin", lambda m: "sk"), \
        mock.patch.object(cmds, "skinCluster", side_effect=lambda *a, **k: 4, create=True), \
        mock.patch.object(skin_tools, "limit_influences", lambda geos, limit: 120 if limit == 4 else -1), \
        mock.patch.object(skin_tools, "normalize", lambda s, g: 380):
    check("Repair weights: 4 joints a vertex, every vertex to 1", cloth.repair("Bandages_Arms") == (120, 380))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
