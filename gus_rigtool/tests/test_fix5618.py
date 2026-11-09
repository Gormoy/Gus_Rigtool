# 5.6.18: the ear's FK held by a constraint to the head (the Hare's L_Ear_01_FK_zero <- Head_ctrl) gets a delta group
# under it (only the squash's movement) - pieces held by ear pieces don't; the face's switches move to a control of
# yours (Face_Ctrls + one per part, through Face_<part>_vis_mdl); hand-made show / hide attributes come off (what
# they hid shown again, an empty heading too); Edit picked pose puts a pose back on its controls
import sys, json
exec(open("fakemaya.py").read())
from gus_rigtool.core import head_squash as HS, vis_switch as VS, face_poses as FP
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def mk(name, parent=None, pos=(0, 0, 0)):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=pos)
    t = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
def held(node, target):
    con = cmds.createNode("parentConstraint", name=node.split("|")[-1] + "_parentConstraint1", parent=node)
    cmds.connectAttr(target + ".worldMatrix[0]", con + ".target[0].targetParentMatrix")
    cmds.connectAttr(con + ".constraintTranslateX", node + ".translateX")
    return con

# --- the ear: what's held from outside
head = mk("Head_ctrl", None, (0, 70, 0))
grp = cmds.ls(cmds.createNode("transform", name="L_Ear_ctrls_grp"), long=True)[0]
follow = cmds.ls(cmds.createNode("transform", name="L_Ear_ctrls_grp_squash_follow", parent=grp), long=True)[0]
zero = cmds.ls(cmds.createNode("transform", name="L_Ear_01_FK_zero", parent=follow), long=True)[0]
fk1 = mk("L_Ear_01_FK_ctrl", zero, (5, 95, 0)); fk2 = mk("L_Ear_02_FK_ctrl", fk1, (6, 105, 0))
held(zero, head)
held(cmds.listRelatives(fk2, parent=True, fullPath=True)[0], head)        # under a held one: not again
rj = cmds.ls(cmds.createNode("joint", name="L_Ear_01_result_jnt"), long=True)[0]
tw = mk("L_Ear_01_tweak_ctrl", follow, (5, 96, 0))
held(cmds.listRelatives(tw, parent=True, fullPath=True)[0], rj)            # held by an ear piece: rides with it
ik = mk("L_Ear_01_IK_ctrl", follow, (5, 95, 0))
got = [n.split("|")[-1] for n in HS._held_from_outside(follow)]
print(got)
check("held from outside: the FK zero (by Head_ctrl) - not what's under it, not the tweak (held by the ear's result "
      "joint), not the IK", got == ["L_Ear_01_FK_zero"])
fol = cmds.ls(cmds.createNode("transform", name="L_Ear_squash_fol"), long=True)[0]
cmds.xform(fol, worldSpace=True, translation=(5, 95, 0))
made = []
ears = [{"kind": "group", "group": "L_Ear_ctrls_grp_squash_follow", "follicle": "L_Ear_squash_fol"}]
HS._ear_deltas(ears, head, made)
d = ears[0]["deltas"]
g = d[0][1] if d else ""
mm = [n for n in made if cmds.nodeType(n) == "multMatrix"]
check("a delta group under the zero holding what it held (the FK chain), driven by zero . head^-1 . C . point . "
      "zero^-1", len(d) == 1 and g.endswith("L_Ear_01_FK_zero|L_Ear_01_FK_zero_squash_delta") and
      cmds.listRelatives("L_Ear_01_FK_ctrl", parent=True, fullPath=True)[0].startswith(g + "|") and mm and
      [(cmds.listConnections("%s.matrixIn[%d]" % (mm[0], i), source=True, destination=False) or ["C"])[0]
       .split("|")[-1] for i in range(5)] == ["L_Ear_01_FK_zero", "Head_ctrl", "C", "L_Ear_squash_fol",
                                              "L_Ear_01_FK_zero"])
c = HS._mul4(HS._m4(cmds.xform(head, query=True, worldSpace=True, matrix=True)),
             HS._inv4(HS._m4(cmds.xform(fol, query=True, worldSpace=True, matrix=True))))
check("C = head . point^-1 (at rest the delta is nothing)", abs(c[3][1] - (70 - 95)) < 1e-6 and abs(c[3][0] + 5) < 1e-6)
inv = HS._inv4([[2, 0, 0, 0], [0, 1, 0, 0], [0, 0, 4, 0], [1, 2, 3, 1]])
check("the 4x4 inverse", max(abs(a - b) for r1, r2 in zip(HS._mul4([[2, 0, 0, 0], [0, 1, 0, 0], [0, 0, 4, 0],
                                                                   [1, 2, 3, 1]], inv),
                                                         [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                               for a, b in zip(r1, r2)) < 1e-9)
src = open("../core/head_squash.py").read()
check("Remove puts what the delta groups held back under the node (relative: as it was)",
      'for n, g in e.get("deltas", [])' in src and "cmds.parent(k, n, relative=True)" in src)

# --- the face's switches on Face_settings_ctrl
vis = cmds.ls(cmds.createNode("transform", name="Visibility_ctrl"), long=True)[0]
for a in VS.SWITCHES:
    cmds.addAttr(vis, longName=a, attributeType="bool", defaultValue=True)
cmds.addAttr(vis, longName=VS.MARK, attributeType="bool", defaultValue=True)
brow = mk("L_Brow_ctrl", head, (3, 90, 8)); lid = mk("L_Eyelids_fol_01_ctrl", head, (3, 86, 8))
mouth = mk("L_Mouth_fol_06_ctrl", head, (3, 78, 9)); tongue = mk("Tongue_01_FK_ctrl", head, (0, 77, 5))
fs = mk("Face_settings_ctrl", head, (10, 80, 0))
for c_ in (brow, lid, mouth, tongue, fs):
    cmds.connectAttr(vis + ".Face_Ctrls", c_ + "|" + c_.split("|")[-1] + "Shape.visibility")
check("parts by name (5.6.22: the lid / mouth ribbons apart)", [VS.face_part(x) for x in (
    brow, lid, mouth, tongue, "L_Eye_ctrl", "Head_squash_ctrl")] ==
      ["Brows", "Eyelid_Ribbons", "Mouth_Ribbon", "Tongue", "Eyes", "Other"])
with mock.patch("gus_rigtool.core.on_top.controls", return_value=[brow, lid, mouth, tongue, fs, vis]), \
        mock.patch("gus_rigtool.core.on_top.is_face", return_value=True):
    lines, _f = VS.face_plan(fs)
    print("\n".join(lines))
    got = VS.move_face(fs)
    sw_of = VS.switch_of(brow)
src_of = lambda c_: (cmds.listConnections(c_ + "|" + c_.split("|")[-1] + "Shape.visibility", source=True,
                                          destination=False) or [""])[0].split("|")[-1]
print(got["parts"])
check("on Face_settings_ctrl: Face_Ctrls + Brows, Eyelid_Ribbons, Mouth_Ribbon, Tongue; each control on its part",
      all(cmds.attributeQuery(a, node=fs, exists=True) for a in ("Face_Ctrls", "Brows", "Eyelid_Ribbons",
                                                                 "Mouth_Ribbon", "Tongue", VS.FACE_HEADER)) and
      [src_of(x) for x in (brow, lid, mouth, tongue)] == ["Face_Brows_vis_mdl", "Face_Eyelid_Ribbons_vis_mdl",
                                                          "Face_Mouth_Ribbon_vis_mdl", "Face_Tongue_vis_mdl"])
check("a part = Face_Ctrls x its own switch", [x.split("|")[-1] for x in (
    cmds.listConnections("Face_Brows_vis_mdl.input1", source=True, destination=False) or []) +
    (cmds.listConnections("Face_Brows_vis_mdl.input2", source=True, destination=False) or [])] ==
    ["Face_settings_ctrl", "Face_settings_ctrl"])
check("Visibility_ctrl.Face_Ctrls gone; the holder itself always shown; the control still counts as on Face_Ctrls",
      not cmds.attributeQuery("Face_Ctrls", node=vis, exists=True) and src_of(fs) == "" and sw_of == "Face_Ctrls")
with mock.patch("gus_rigtool.core.on_top.is_face", return_value=True):
    nb = mk("R_Brow_ctrl", head, (-3, 90, 8))
    VS.assign([nb], "Face_Ctrls")
check("a new face control later (group controls, the board...): onto its part", src_of(nb) == "Face_Brows_vis_mdl")

# --- hand-made switches off
wrist = mk("L_wrist_settings_ctrl", None, (20, 50, 0))
for a, t in (("ikfk", "double"), ("_Ctrl_Vis", "enum"), ("Sleeves", "double"), ("Bend", "double")):
    cmds.addAttr(wrist, longName=a, attributeType=t, **({"enumName": "----"} if t == "enum" else {}))
ikc = cmds.createNode("parentConstraint", name="L_wrist_jnt_parentConstraint1")
cmds.connectAttr(wrist + ".ikfk", ikc + ".w1")
sl = cmds.createNode("transform", name="L_Sleeve_ctrls_grp"); bd = cmds.createNode("transform", name="L_bend_sdk")
cmds.connectAttr(wrist + ".Sleeves", sl + ".visibility"); cmds.connectAttr(wrist + ".Bend", bd + ".visibility")
cmds.setAttr(wrist + ".Sleeves", 0)
found = [a for a, _d in VS.hand_switches(wrist)]
check("found: Sleeves, Bend (only show / hide) - not ikfk, not the heading", found == ["Sleeves", "Bend"])
done = VS.remove_hand_switches([wrist])
print(done)
check("removed: the two, their heading (nothing left under it); ikfk stays; what they hid shown again",
      cmds.listAttr(wrist, userDefined=True) == ["ikfk"] and cmds.getAttr(sl + ".visibility") and
      not cmds.listConnections(sl + ".visibility", source=True, destination=False))

# --- Edit picked pose
holder = mk("Mouth_main_ctrl", head, (0, 75, 12))
cmds.addAttr(holder, longName="Smile_L", attributeType="double"); cmds.addAttr(holder, longName="Smile_R", attributeType="double")
cmds.setAttr(holder + ".Smile_L", 0.5)
FP._write(holder, {"Smile": {"split": True, "attrs": ["Smile_L", "Smile_R"], "ctrls": {
    "L_Mouth_fol_06_ctrl": {"t": [0, 1.5, 0], "r": [0, 0, 10], "left": 1, "nodes": []}}}})
cmds.setAttr(mouth + ".translateX", 0.7)
with mock.patch.object(FP, "_drivers", return_value=[mouth]):
    got = FP.edit_pose(holder, "Smile")
check("Edit: sliders to 0, the face zeroed, the pose on its control (ty 1.5, rz 10), split kept",
      cmds.getAttr(holder + ".Smile_L") == 0 and cmds.getAttr(mouth + ".translate")[0] == (0, 1.5, 0) and
      cmds.getAttr(mouth + ".rotateZ") == 10 and got["split"] and got["set"] == 1)
print("%d/%d passed" % (sum(ok), len(ok)))
