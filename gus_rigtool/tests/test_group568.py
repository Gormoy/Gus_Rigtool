# 5.6.8: group controls - a control moving a set of controls by weights, through a layer group above each one
# (shared, summed); the mouth plan (main / upper / lower / corners, cheeks following the corners a little); set /
# change / take off weights; remove leaves the controls where they were; the scale check measures a skinned mesh
# by its vertices (not its box, which took in the Hare belts' unused shapes: x31 instead of x2)
import sys, math
exec(open("fakemaya.py").read())
from gus_rigtool.core import group_ctrls as GC, scale_check as SC
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
src = lambda p: cmds.listConnections(p, source=True, destination=False, plugs=True) or []

head = cmds.createNode("transform", name="Head_ctrl"); cmds.createNode("nurbsCurve", name="Head_ctrlShape", parent=head)
cmds.xform(head, worldSpace=True, translation=[0, 150, 0])
jaw = cmds.createNode("transform", name="Jaw_end_ctrl", parent=head)
cmds.createNode("nurbsCurve", name="Jaw_end_ctrlShape", parent=jaw)
grp = cmds.createNode("transform", name="Mouth_ctrls_grp", parent=head)
mouth = []
pts = [(-4, 150, 10), (-2, 151, 10.5), (0, 151.5, 11), (2, 151, 10.5), (4, 150, 10), (2, 149, 10.5), (0, 148.5, 11),
       (-2, 149, 10.5)]
for i, p in enumerate(pts):
    off = cmds.createNode("transform", name="Mouth_fol_%02d_ctrl_offset" % i, parent=grp)
    cmds.xform(off, worldSpace=True, translation=p)
    cmds.setAttr(off + ".rotateY", 20 * (i - 4))                 # each lip control turned its own way
    c = cmds.createNode("transform", name="Mouth_fol_%02d_ctrl" % i, parent=off)
    cmds.createNode("nurbsCurve", name="Mouth_fol_%02d_ctrlShape" % i, parent=c)
    mouth.append(cmds.ls(c, long=True)[0])
cheek = cmds.createNode("transform", name="L_Facial_fol_03_ctrl", parent=grp)
cmds.createNode("nurbsCurve", name="L_Facial_fol_03_ctrlShape", parent=cheek)
cmds.xform(cheek, worldSpace=True, translation=[6, 153, 9])
far = cmds.createNode("transform", name="L_Brow_ctrl", parent=grp)
cmds.createNode("nurbsCurve", name="L_Brow_ctrlShape", parent=far)
cmds.xform(far, worldSpace=True, translation=[5, 170, 9])
face = [cmds.ls(cheek, long=True)[0], cmds.ls(far, long=True)[0]]

plan = GC.mouth_plan(mouth, face)
print("\n".join(GC.plan_text(plan)))
check("five group controls planned", sorted(plan) == sorted(["Mouth_main_ctrl", "Upper_Lip_ctrl", "Lower_Lip_ctrl",
                                                             "L_Mouth_Corner_ctrl", "R_Mouth_Corner_ctrl"]))
lw = dict((k.split("|")[-1], v) for k, v in plan["L_Mouth_Corner_ctrl"]["weights"].items())
check("left corner: its own corner 1, the lip next to it less, the far corner nothing", lw.get("Mouth_fol_04_ctrl") == 1.0
      and 0 < lw.get("Mouth_fol_03_ctrl", 0) < 1 and "Mouth_fol_00_ctrl" not in lw)
check("the cheek follows the left corner a little, the brow (far) not at all", 0 < lw.get("L_Facial_fol_03_ctrl", 0)
      <= 0.5 and "L_Brow_ctrl" not in lw)
uw = dict((k.split("|")[-1], v) for k, v in plan["Upper_Lip_ctrl"]["weights"].items())
check("upper lip: the middle 1, the upper side less, the lower lip not", uw.get("Mouth_fol_02_ctrl") == 1.0 and
      uw["Mouth_fol_01_ctrl"] < 1 and "Mouth_fol_06_ctrl" not in uw)
check("the lower lip goes under the jaw; the right corner mirrored", plan["Lower_Lip_ctrl"]["jaw"] and
      plan["R_Mouth_Corner_ctrl"]["mirrored"])

mk = lambda name, *a, **k: _mk(name)
def _mk(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
before = dict((c, cmds.xform(c, query=True, worldSpace=True, translation=True)) for c in mouth)
real_connect = cmds.connectAttr
def maya_connect(src, dst, **k):                    # like Maya: a sum into a rotate goes through a unit conversion
    if dst.endswith(".rotate") and cmds.nodeType(src.split(".")[0]) == "plusMinusAverage":
        uc = cmds.createNode("unitConversion")
        real_connect(src, uc + ".input")
        return real_connect(uc + ".output", dst, **k)
    return real_connect(src, dst, **k)
cmds.connectAttr = maya_connect
with mock.patch("gus_rigtool.core.curves.create_curve_control", side_effect=mk), \
        mock.patch("gus_rigtool.core.curves.read_shape", return_value=[]), \
        mock.patch("gus_rigtool.core.curves.read_style", return_value={}):
    made = GC.make_mouth(plan, cmds.ls(head, long=True)[0], cmds.ls(jaw, long=True)[0])
print([m.split("|")[-1] for m in made])
check("all five made - through Maya's unit conversions (5.6.8 crashed on the second one)", len(made) == 5)
rot_src = cmds.listConnections(GC.layer_of(GC._long("Mouth_fol_04_ctrl")) + ".rotate", source=True,
                               destination=False) or []
check("(the rotate sum really is behind a unit conversion here)", rot_src and
      cmds.nodeType(rot_src[0]) == "unitConversion")
check("the lower lip under the jaw, the rest under the head", "|Jaw_end_ctrl|" in GC._long("Lower_Lip_ctrl") and
      "|Jaw_end_ctrl|" not in GC._long("Upper_Lip_ctrl"))
c4 = GC._long("Mouth_fol_04_ctrl")
lay = GC.layer_of(c4)
check("the corner control has ONE layer above it, shared", lay and lay.endswith("|Mouth_fol_04_ctrl_groups") and
      cmds.listRelatives(lay, children=True)[0] == "Mouth_fol_04_ctrl")
pt = src(lay + ".translate")[0].split(".")[0]
n_in = len(cmds.listConnections(pt + ".input3D", source=True, destination=False) or [])
check("its layer sums the main, the lower lip... and the left corner (%d)" % n_in, n_in >= 2)
check("nothing moved", all(max(abs(a - b) for a, b in zip(before[c.split("|")[-1] and c],
                                                        cmds.xform(GC._long(c.split("|")[-1]), query=True,
                                                                   worldSpace=True, translation=True))) < 1e-6
                           for c in mouth))
r = GC._long("R_Mouth_Corner_ctrl")
rw = cmds.xform(cmds.listRelatives(r, parent=True, fullPath=True)[0], query=True, worldSpace=True, matrix=True)
check("right corner's group: a clean mirror in the world (X -1, Y 1, Z 1)", [round(rw[0], 6), round(rw[5], 6),
                                                                             round(rw[10], 6)] == [-1, 1, 1])
d = GC.read(GC._long("L_Mouth_Corner_ctrl"))
m, _sg = GC._space_matrix(cmds.listRelatives(GC._long("L_Mouth_Corner_ctrl"), parent=True, fullPath=True)[0],
                          cmds.listRelatives(GC.layer_of(GC._long("Mouth_fol_04_ctrl")), parent=True,
                                             fullPath=True)[0])
check("the corner's move in the corner control's axes (not turned: the same axes)",
      abs(m[0] - 1.0) < 1e-6 and abs(m[2]) < 1e-6 and abs(m[5] - 1.0) < 1e-6)
up_off = cmds.listRelatives(GC._long("Upper_Lip_ctrl"), parent=True, fullPath=True)[0]
lip_par = cmds.listRelatives(GC.layer_of(GC._long("Mouth_fol_01_ctrl")), parent=True, fullPath=True)[0]
m1, _sg = GC._space_matrix(up_off, lip_par)              # (the fake Maya doesn't keep a node's matrix)
check("a lip control turned 60 degrees: the upper lip's sideways move turned into its axes (cos 60 = %.2f)" % m1[0],
      abs(m1[0] - 0.5) < 1e-3 and abs(abs(m1[2]) - math.sqrt(3) / 2) < 1e-3)

# 5.6.10: under a scaled, turned head (the Hare's Head_01_CTRL, 25.8): the groups still come out clean
big = cmds.createNode("transform", name="Head_01_CTRL")
cmds.setAttr(big + ".scaleX", 25.826); cmds.setAttr(big + ".rotateY", 90)
with mock.patch("gus_rigtool.core.curves.create_curve_control", side_effect=mk), \
        mock.patch("gus_rigtool.core.curves.read_shape", return_value=[]), \
        mock.patch("gus_rigtool.core.curves.read_style", return_value={}):
    rc = GC.make("R_Test_ctrl", {"Mouth_fol_00_ctrl": 1.0}, [-5, 150, 12], big, 1.0, "circle", "R", True)
    lc = GC.make("L_Test_ctrl", {"Mouth_fol_04_ctrl": 1.0}, [5, 150, 12], big, 1.0)
for c, want in ((rc, [-1, 1, 1]), (lc, [1, 1, 1])):
    w = cmds.xform(cmds.listRelatives(c, parent=True, fullPath=True)[0], query=True, worldSpace=True, matrix=True)
    sizes = [math.sqrt(sum(v * v for v in w[r * 4:r * 4 + 3])) for r in range(3)]
    check("%s under the scaled head: its group's world size 1, 1, 1 (%s), axes %s" % (
        c.split("|")[-1], [round(x, 3) for x in sizes], want), max(abs(x - 1) for x in sizes) < 1e-6 and
        [round(w[0], 6), round(w[5], 6), round(w[10], 6)] == want)
m_t, _sg = GC._space_matrix(cmds.listRelatives(rc, parent=True, fullPath=True)[0],
                            cmds.listRelatives(GC.layer_of(GC._long("Mouth_fol_00_ctrl")), parent=True, fullPath=True)[0])
check("...so its move isn't blown up (5.6.8: 9.275 for 1): length %.3f" % math.sqrt(sum(v * v for v in m_t[0:3])),
      abs(math.sqrt(sum(v * v for v in m_t[0:3])) - 1.0) < 1e-6)
GC.remove(rc); GC.remove(lc)

# weights: change, add, take off
GC.set_weights(GC._long("L_Mouth_Corner_ctrl"), {"Mouth_fol_03_ctrl": 0.8, "L_Brow_ctrl": 0.2, "Mouth_fol_04_ctrl": 0})
d = GC.read(GC._long("L_Mouth_Corner_ctrl"))
check("set weight: changed (0.8), added (the brow 0.2), taken off (the corner)", d["Mouth_fol_03_ctrl"][0] == 0.8 and
      d["L_Brow_ctrl"][0] == 0.2 and "Mouth_fol_04_ctrl" not in d)
md = [n for n in d["Mouth_fol_03_ctrl"][1] if n.endswith("_t_w")][0]
w2 = cmds.getAttr(md + ".input2")
check("...the weight is on its node", list(w2[0] if isinstance(w2[0], tuple) else w2) == [0.8, 0.8, 0.8])

# remove everything: layers gone, controls back under their offsets
for name in ("Mouth_main_ctrl", "Upper_Lip_ctrl", "Lower_Lip_ctrl", "L_Mouth_Corner_ctrl", "R_Mouth_Corner_ctrl"):
    GC.remove(GC._long(name))
check("removed: no group controls left", not any(cmds.objExists(n) for n in ("Mouth_main_ctrl", "Upper_Lip_ctrl",
                                                                              "L_Mouth_Corner_ctrl")))
c4 = GC._long("Mouth_fol_04_ctrl")
check("...and no layers: the lip control back under its own group", not GC.layer_of(c4) and
      cmds.listRelatives(c4, parent=True)[0] == "Mouth_fol_04_ctrl_offset")
cmds.connectAttr = real_connect

# the scale check: vertices, not the box
p0 = [(0, 0, 0), (1, 0, 0), (0, 2, 0)]
dmat = [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1]
err, ratio = SC._mesh_error(p0, [(0, 0, 0), (2, 0, 0), (0, 4, 0)], dmat, 2)
check("vertices where the scale takes them: no error, x2", err < 1e-9 and abs(ratio - 2) < 1e-9)
err, ratio = SC._mesh_error(p0, [(0, 0, 0), (2, 0, 0), (0, 3, 0)], dmat, 2)
check("one vertex short: found (%.0f%% of the size)" % (err * 100), err > 0.02)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
