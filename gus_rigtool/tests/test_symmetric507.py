# 5.0.7: Make symmetric - the Hare's mouth: R controls 26 / 18 / 28 sit 0.011 / 0.008 / 0.001 off the mirror of
# L_02 / L_10 / L_38 (L_ side at -X is the master). Controls (and the joints following them) and follicles move
# onto the exact mirror spot; the skins take the joints' new place as rest (bindPreMatrix), so nothing moves;
# a follicle the surface can't bring exactly there is reported; Check this scene and Repair find it
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import ribbon, repair
from gus_rigtool import scene_check
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
W = lambda n: cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, translation=True)

surf = cmds.createNode("transform", name="Mouth")
cmds.createNode("nurbsSurface", name="MouthShape", parent=surf)
tops = [cmds.createNode("transform", name="Mouth_" + g) for g in ("ctrls_grp", "follicles_grp")]
for g in tops:
    cmds.addAttr(g, longName="rrbSurface", dataType="string"); cmds.setAttr(g + ".rrbSurface", "Mouth", type="string")
    cmds.addAttr(g, longName="rrbSkin", dataType="string"); cmds.setAttr(g + ".rrbSkin", "", type="string")
cmds.createNode("skinCluster", name="Body_skin")
cmds.addAttr("Body_skin", longName="bindPreMatrix", attributeType="double", multi=True)
SLOT = [0]
def bound(j):
    cmds.connectAttr(j + ".worldMatrix[0]", "Body_skin.matrix[%d]" % SLOT[0]); SLOT[0] += 1
# the Hare's mouth controls (v130), the bind joint is under each control here ('child')
CT = [("L_Mouth_fol_02", -3.777, 4.870, 2.469), ("L_Mouth_fol_10", -1.613, 7.403, 3.556),
      ("L_Mouth_fol_38", -3.029, 5.659, 2.217), ("L_Mouth_fol_04", -4.034, 4.807, 2.762),
      ("Mouth_fol_14", 0.0, 7.089, 3.747),
      ("Mouth_fol_26", 3.769, 4.877, 2.466), ("Mouth_fol_18", 1.618, 7.399, 3.552),
      ("Mouth_fol_28", 3.028, 5.659, 2.216), ("Mouth_fol_24", 4.034, 4.807, 2.762)]
for i, (n, x, y, z) in enumerate(CT):
    off = cmds.createNode("transform", name=n + "_ctrl_offset", parent=tops[0])
    cmds.addAttr(off, longName="rrbIndex", attributeType="long"); cmds.setAttr(off + ".rrbIndex", i)
    cmds.xform(off, worldSpace=True, translation=[x, y, z])
    c = cmds.createNode("transform", name=n + "_ctrl", parent=off)
    cmds.createNode("nurbsCurve", name=n + "_ctrlShape", parent=c)
    b = cmds.createNode("joint", name=n + "_bind", parent=c)
    bound(b)
# follicles: 02 / 26 a bit off, 04 / 24 exact; the joint under each skins the mesh
FO = [("Mouth_fol_02", -3.70, 4.90, 2.50), ("Mouth_fol_26", 3.69, 4.91, 2.50),
      ("Mouth_fol_04", -4.00, 4.80, 2.70), ("Mouth_fol_24", 4.00, 4.80, 2.70)]
for n, x, y, z in FO:
    f = cmds.createNode("transform", name=n, parent=tops[1])
    cmds.createNode("follicle", name=n + "Shape", parent=f)
    cmds.xform(f, worldSpace=True, translation=[x, y, z])
    bound(cmds.createNode("joint", name=n + "_jnt", parent=f))

r = ribbon.symmetry_report("Mouth")
got = sorted((m.split("|")[-1], f.split("|")[-1], round(d, 3)) for m, f, d in r["controls"])
check("master: the L_ side (at -X)", r["sign"] == -1.0)
check("controls off (all 3 axes): 26 (0.011), 18 (0.008), 28 (0.001); 24 is exact", got == [
    ("L_Mouth_fol_02_ctrl_offset", "Mouth_fol_26_ctrl_offset", 0.011),
    ("L_Mouth_fol_10_ctrl_offset", "Mouth_fol_18_ctrl_offset", 0.008),
    ("L_Mouth_fol_38_ctrl_offset", "Mouth_fol_28_ctrl_offset", 0.001)])
check("follicles off: 26 only", [f.split("|")[-1] for _m, f, _d in r["follicles"]] == ["Mouth_fol_26"])

def closest(shape, point):           # the fake surface: puts the follicle on the spot (0.002 short in Z)
    CL.append(point)
    return 0.5, 0.5
CL = []
real_set = cmds.setAttr
def setAttr(plug, *a, **k):
    real_set(plug, *a, **k) if not plug.endswith(".parameterV") else None
    if plug.endswith(".parameterV"):
        p = CL[-1]
        cmds.xform(cmds.ls("Mouth_fol_26", long=True)[0], worldSpace=True, translation=[p[0], p[1], p[2] - 0.002])
before = W("Mouth_fol_26_bind")
with mock.patch.object(ribbon, "_closest_uv", side_effect=closest), \
        mock.patch.object(cmds, "setAttr", side_effect=setAttr), \
        mock.patch.object(ribbon, "_say", lambda *a: None):
    lines = ribbon.make_symmetric(report=r)
print("\n".join(lines))
for m, f in (("L_Mouth_fol_02", "Mouth_fol_26"), ("L_Mouth_fol_10", "Mouth_fol_18"), ("L_Mouth_fol_38", "Mouth_fol_28")):
    a, b = W(m + "_ctrl_offset"), W(f + "_ctrl_offset")
    check("%s is now the exact mirror of %s" % (f, m), max(abs(x - y) for x, y in zip((-a[0], a[1], a[2]), b)) < 1e-9)
check("its joint came along", abs(W("Mouth_fol_26_bind")[0] - 3.777) < 1e-9 and before[0] == 3.769)
check("the mesh stays: the moved joints' bind pose is their new place",
      cmds.getAttr("Body_skin.bindPreMatrix[5]")[12] == -3.777 if isinstance(
          cmds.getAttr("Body_skin.bindPreMatrix[5]"), (list, tuple)) else False)
check("the master side didn't move", W("L_Mouth_fol_02_ctrl_offset") == [-3.777, 4.870, 2.469])
check("the follicle went to its twin's mirror spot", CL and [round(v, 3) for v in CL[0]] == [3.7, 4.9, 2.5])
check("a follicle the surface can't place exactly says how far it still is",
      any("Mouth_fol_26: moved" in l and "still 0.0020 off" in l for l in lines))

r2 = ribbon.symmetry_report("Mouth")
check("afterwards: the controls are exact", r2["controls"] == [])
from gus_rigtool import scene_check
with mock.patch.object(ribbon, "is_looped", lambda k: True), mock.patch.object(scene_check, "mirror_tol", lambda: 0.0):
    item = repair._ribbons_not_symmetric()
check("with no tolerance, Repair still offers the follicle the surface can't reach", item and item.count == 1)
with mock.patch.object(ribbon, "is_looped", lambda k: True):
    item = repair._ribbons_not_symmetric()
check("5.3.4: within the skin mirror tolerance (0.002 < 0.01) it isn't offered again", item is None)

print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
