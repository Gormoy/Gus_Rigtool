# 5.6.15: the ears ride the head squash (each ear root's top group follows a follicle on a small plane in the
# lattice, the head's scale; the ears' vertices get the lattice less by how much the skin ties them to the ears);
# Remove puts each ear back under its own parent; the sliders board: per pose an amount knob (0 -> 1 up) and a
# shift knob for split poses driving Smile_L / Smile_R, limited, on the Face switch; saving a new pose rebuilds
# it; remove lets the sliders go; no number field with a minimum and no maximum
import sys, json
exec(open("fakemaya.py").read())
from gus_rigtool.core import head_squash as HS, face_sliders as FS, face_poses as FP
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
src = lambda p: cmds.listConnections(p, source=True, destination=False, plugs=True) or []
def mk(name, parent=None, pos=(0, 0, 0)):
    on = name.replace("_ctrl", "_offset") if "_ctrl" in name else name + "_offset"
    off = cmds.createNode("transform", name=on, parent=parent) if parent else cmds.createNode("transform", name=on)
    cmds.xform(off, worldSpace=True, translation=pos)
    t = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
head = mk("Head_01_CTRL", None, (0, 70, 0))
e1 = mk("L_Ear_01_FK_ctrl", head, (5, 95, -2)); e2 = mk("L_Ear_02_FK_ctrl", e1, (6, 110, -3))
r1 = mk("R_Ear_01_FK_ctrl", head, (-5, 95, -2))
rib = mk("L_Ear_ribbon_fol_03_ctrl", head, (6, 105, -3))
check("ear roots: L_Ear_01 and R_Ear_01 (not the chain below, not the ear ribbon's controls)",
      sorted(c.split("|")[-1] for c in HS.ear_roots()) == ["L_Ear_01_FK_ctrl", "R_Ear_01_FK_ctrl"])

def nurbsPlane(name=None, **k):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsSurface", name=name + "Shape", parent=t)
    return [t]
cons = []
def pcon(t, g, **k):
    cons.append(("parent", t.split("|")[-1], g.split("|")[-1])); return ["pc"]
def scon(t, g, **k):
    cons.append(("scale", t.split("|")[-1], g.split("|")[-1])); return ["sc"]
grp = cmds.ls(cmds.parent(cmds.createNode("transform", name="Head_squash_grp"), head)[0], long=True)[0]
before = cmds.xform("L_Ear_01_FK_ctrl", query=True, worldSpace=True, matrix=True)
made = []
with mock.patch.object(cmds, "nurbsPlane", side_effect=nurbsPlane, create=True), \
        mock.patch.object(cmds, "parentConstraint", side_effect=pcon), \
        mock.patch.object(cmds, "scaleConstraint", side_effect=scon):
    ears, planes = HS._ear_riders(grp, head, made)
print(ears)
check("one rider per ear root, its plane in the lattice", len(ears) == 2 and len(planes) == 2)
L = [e for e in ears if e["ctrl"] == "L_Ear_01_FK_ctrl"][0]
check("the ear's top group under a new follow group (where it was, nothing moved)",
      "|L_Ear_01_FK_squash_follow|L_Ear_01_FK_offset|L_Ear_01_FK_ctrl" in cmds.ls("L_Ear_01_FK_ctrl", long=True)[0]
      and max(abs(a - b) for a, b in zip(before, cmds.xform("L_Ear_01_FK_ctrl", query=True, worldSpace=True,
                                                             matrix=True))) < 1e-6)
# after the lattice: Maya keeps a copy of the plane as it was (intermediate) - the follicle must read the other one
for e in ears:
    pl = cmds.ls(e["plane"], long=True)[0]
    old = cmds.listRelatives(pl, shapes=True, fullPath=True)[0]
    cmds.addAttr(old, longName="intermediateObject", attributeType="bool") if not \
        cmds.attributeQuery("intermediateObject", node=old, exists=True) else None
    cmds.setAttr(old + ".intermediateObject", 1)                  # the copy as it was
    new = cmds.createNode("nurbsSurface", name=e["plane"] + "ShapeDeformed", parent=pl)
    cmds.addAttr(new, longName="intermediateObject", attributeType="bool")
with mock.patch.object(cmds, "parentConstraint", side_effect=pcon), \
        mock.patch.object(cmds, "scaleConstraint", side_effect=scon):
    HS._connect_riders(ears, cmds.ls(head, long=True)[0])
check("follows the follicle (and the head's scale)", ("parent", "L_Ear_01_FK_squash_fol", "L_Ear_01_FK_squash_follow")
      in cons and ("scale", "Head_01_CTRL", "L_Ear_01_FK_squash_follow") in cons)
fol = cmds.ls(L["follicle"], long=True)[0]
fs = cmds.listRelatives(fol, shapes=True)[0]
check("the follicle reads the squashed plane, not Maya's copy of it as it was (5.6.15: the points never moved)",
      src(fs + ".inputSurface") == [L["plane"] + "ShapeDeformed.local"] and
      cmds.getAttr(fol + ".inheritsTransform") == 0)

# the ears' vertices: less lattice by their ear weight
with mock.patch.object(cmds, "listHistory", return_value=["skinCluster10"]), \
        mock.patch.object(cmds, "skinCluster", return_value=["Head_jnt", "L_Ear_01_jnt", "L_Ear_02_jnt"], create=True), \
        mock.patch.object(cmds, "ls", side_effect=lambda *a, **k: ["skinCluster10"] if k.get("type") == "skinCluster"
                          else (["|Body.vtx[0]", "|Body.vtx[1]", "|Body.vtx[2]"] if k.get("flatten") else [])), \
        mock.patch.object(cmds, "skinPercent", side_effect=lambda sk, v, transform=None, **k:
                          {"L_Ear_01_jnt": [0.0, 0.5, 1.0], "L_Ear_02_jnt": [0.0, 0.25, 0.0]}[transform], create=True):
    flat, w = HS._ear_weights("|Body", ["|Body.vtx[0:2]"])
check("ear weight per vertex: the ear joints only (0, 0.75, 1)", w == [0.0, 0.75, 1.0])

# Remove: the ears back
c = cmds.createNode("transform", name="Head_squash_ctrl", parent=grp)
cmds.addAttr(c, longName=HS.META, dataType="string")
cmds.setAttr(c + "." + HS.META, json.dumps({"group": "Head_squash_grp", "ears": ears, "nodes": [], "deformers": [],
                                            "switch": ""}), type="string")
HS.remove()
check("removed: each ear back under its own parent, the follow groups gone, nothing moved",
      cmds.ls("L_Ear_01_FK_ctrl", long=True)[0] == "|Head_01_CTRL_offset|Head_01_CTRL|L_Ear_01_FK_offset|L_Ear_01_FK_ctrl"
      and not cmds.objExists("L_Ear_01_FK_squash_follow") and max(abs(a - b) for a, b in zip(
          before, cmds.xform("L_Ear_01_FK_ctrl", query=True, worldSpace=True, matrix=True))) < 1e-6)

# ---- an ear built like the Hare's: FK, IK, tweak, settings in their own branches inside L_Ear_ctrls_grp
for n in ("L_Ear_01_FK_offset", "R_Ear_01_FK_offset", "L_Ear_ribbon_fol_03_offset", "Head_squash_grp"):
    if cmds.objExists(n):
        cmds.delete(n)                                    # (the first ears: one ear rig per side, like the Hare)
for side, x in (("L", 5), ("R", -5)):
    eg = cmds.createNode("transform", name="%s_Ear_ctrls_grp" % side, parent=head)
    for n, y in (("%s_Ear_01_FK_ctrl", 95), ("%s_Ear_01_IK_ctrl", 95), ("%s_Ear_03_tweak_ctrl", 105),
                 ("%s_Ear_settings_ctrl", 100)):
        mk(n % side + "X", eg, (x, y, 0))
units = HS.ear_units()
print(units)
check("one unit per side: the ear group (the whole ear rig rides as one - 5.6.15 found 26 tops)",
      sorted((u.split("|")[-1], k) for u, k in units) == [("L_Ear_ctrls_grp", "group"),
                                                          ("R_Ear_ctrls_grp", "group")])
kids0 = sorted(cmds.listRelatives("L_Ear_ctrls_grp", children=True))
made = []
grp2 = cmds.ls(cmds.parent(cmds.createNode("transform", name="Head_squash_grp"), head)[0], long=True)[0]
with mock.patch.object(cmds, "nurbsPlane", side_effect=nurbsPlane, create=True):
    ears2, _pl = HS._ear_riders(grp2, head, made)
Lg = [e for e in ears2 if e["ctrl"] == "L_Ear_ctrls_grp"]
check("a follow group INSIDE the ear group, holding all it held (works when the ear group is constrained)",
      Lg and cmds.listRelatives("L_Ear_ctrls_grp", children=True) == ["L_Ear_ctrls_grp_squash_follow"] and
      sorted(cmds.listRelatives("L_Ear_ctrls_grp_squash_follow", children=True)) == kids0)

# ---- the sliders board
holder = mk("Mouth_main_ctrl", head, (0, 70, 14))
for a in ("Smile_L", "Smile_R", "Frown"):
    cmds.addAttr(holder, longName=a, attributeType="double", minValue=0, maxValue=1)
FP._write(holder, {"Smile": {"split": True, "attrs": ["Smile_L", "Smile_R"], "ctrls": {}},
                   "Frown": {"split": False, "attrs": ["Frown"], "ctrls": {}}})
limits = []
with mock.patch.object(cmds, "transformLimits", side_effect=lambda c, **k: limits.append((c.split("|")[-1], k)),
                       create=True), \
        mock.patch.object(cmds, "textCurves", side_effect=lambda **k: [cmds.createNode("transform",
                                                                                        name=k["name"])], create=True), \
        mock.patch.object(cmds, "exactWorldBoundingBox", return_value=[-10, 60, -10, 10, 90, 10], create=True):
    got = FS.make("Mouth_main_ctrl", "Head_01_CTRL")
print(got)
check("a column per pose: Smile (amount + shift), Frown (amount)", got == {"Smile": ["Smile_amount_ctrl",
                                                                                  "Smile_shift_ctrl"],
                                                                        "Frown": ["Frown_amount_ctrl"]})
check("the board follows the head", "|Head_01_CTRL|Face_sliders_grp" in FS.find())
def upstream(plug, want, depth=6):
    seen, todo = set(), [plug]
    for _i in range(depth):
        nxt = []
        for p in todo:
            for s_ in src(p):
                node = s_.split(".")[0]
                if node == want:
                    return True
                if node not in seen:
                    seen.add(node)
                    nxt += [node + "." + a for a in ("input1", "input1X", "input1Y", "input2X", "input2Y", "inputR",
                                                     "inputG", "input1D[0]", "input3D[1].input3Dx",
                                                     "input3D[1].input3Dy", "output3Dx", "output3Dy")]
        todo = nxt
    return False
check("Smile_L and Smile_R come from the amount knob and the shift knob",
      all(upstream("Mouth_main_ctrl." + a, k) for a in ("Smile_L", "Smile_R") for k in ("Smile_amount_ctrl",
                                                                                       "Smile_shift_ctrl")))
check("Frown from its amount knob only", upstream("Mouth_main_ctrl.Frown", "Frown_amount_ctrl") and
      not upstream("Mouth_main_ctrl.Frown", "Smile_amount_ctrl"))
check("the knobs are limited (up 0..size; shift sideways)", ("Smile_amount_ctrl", ) and
      any(n == "Smile_amount_ctrl" and "translationY" in k for n, k in limits) and
      any(n == "Smile_shift_ctrl" and "translationX" in k for n, k in limits))
check("the knobs move only the way they should", cmds.getAttr(FS._long("Smile_amount_ctrl") + ".tx", lock=True) and
      not cmds.getAttr(FS._long("Smile_amount_ctrl") + ".ty", lock=True))
check("the knobs aren't part of a pose", not any("Face_sliders_grp" in c for c in FP.pose_controls()))
FS.remove()
check("removed: the sliders free (no input) and at 0", not FS.find() and not src("Mouth_main_ctrl.Smile_L") and
      cmds.getAttr("Mouth_main_ctrl.Smile_L") == 0)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
