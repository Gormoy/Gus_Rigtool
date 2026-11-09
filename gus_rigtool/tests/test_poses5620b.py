# 5.6.20 (b): the controls a pose takes - the face's by name AND any inside the box round them (not the head / neck /
# body level, not the board's knobs); measured as the face shows it (a lid control under a driven-key group the
# lids' master moves: its closing kept - 5.6.19 measured it against that group and lost it), against the parent
# only under another posed control (the ear chain); a number attribute (curl) to its default while the rest is
# measured, switches (ikfk...) left; the name field empties after a save, Save as new is the default
import sys, math
exec(open("fakemaya.py").read())
from gus_rigtool.core import face_poses as FP, group_ctrls as GC
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def mk(name, parent=None, pos=(0, 0, 0)):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=pos)
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]
head = mk("Head_01_CTRL", None, (0, 150, 0))
brow = mk("L_Brow_ctrl", head, (4, 160, 9)); mouth = mk("Mouth_fol_33_ctrl", head, (0, 145, 11))
snout = mk("Snout_wiggle", head, (0, 150, 12))            # inside the face, no face word
arm = mk("L_wrist_FK_ctrl", None, (30, 100, 0))           # far away
neck = mk("Neck_01_CTRL", head, (0, 148, 0))              # inside, but body level
holder = mk("Mouth_main_ctrl", head, (0, 147, 14))
with mock.patch("gus_rigtool.core.group_ctrls.all_groups", return_value=[]):
    got = sorted(c.split("|")[-1] for c in FP.pose_controls(holder))
print(got)
check("pose controls: by name + inside the face box (Snout_wiggle) - not the head, neck, arm, slider control",
      got == ["L_Brow_ctrl", "Mouth_fol_33_ctrl", "Snout_wiggle"])

# a lid control under a driven-key group (the master's driven keys move the group, not the control)
lidm = mk("L_Upper_Eyelids_ctrl", head, (5, 156, 10))
sdk = cmds.createNode("transform", name="L_Eyelids_fol_01_ctrl_Upper_Lid", parent=head)
cmds.xform(sdk, worldSpace=True, translation=(5, 155, 11))
lid = cmds.ls(cmds.createNode("transform", name="L_Eyelids_fol_01_ctrl", parent=sdk), long=True)[0]
cmds.createNode("nurbsCurve", name="L_Eyelids_fol_01_ctrlShape", parent=lid)
# the ear chain
e1 = mk("L_Ear_01_FK_ctrl", head, (6, 170, 0)); e2 = mk("L_Ear_02_FK_ctrl", e1, (6, 180, 0))
# the tongue's curl on Face_settings_ctrl, moving a group above the tongue control
fs = mk("Face_settings_ctrl", head, (12, 150, 0))
cmds.addAttr(fs, longName="curl", attributeType="double", keyable=True)
cmds.addAttr(fs, longName="ikfk", attributeType="double", keyable=True)
curl = cmds.createNode("transform", name="Tongue_01_curl_grp", parent=head)
cmds.xform(curl, worldSpace=True, translation=(0, 146, 6))
tg = cmds.ls(cmds.createNode("transform", name="Tongue_01_FK_ctrl", parent=curl), long=True)[0]
cmds.createNode("nurbsCurve", name="Tongue_01_FK_ctrlShape", parent=tg)
check("custom number attributes: curl - not ikfk", [p.split(".")[-1] for p in FP._custom(fs)] == ["curl"])

# pose: master tz 2 -> (driven keys) the lid group down 1.5; ear chain turned; curl 30 -> curl group turned
CT = [GC._long(n) for n in ("L_Brow_ctrl", "L_Upper_Eyelids_ctrl", "L_Eyelids_fol_01_ctrl", "L_Ear_01_FK_ctrl",
                            "L_Ear_02_FK_ctrl", "Face_settings_ctrl", "Tongue_01_FK_ctrl")]
def drive():                     # what Maya's driven keys / the curl attribute would do (the fake doesn't evaluate)
    cmds.setAttr(sdk + ".translateY", -1.5 * cmds.getAttr(GC._long("L_Upper_Eyelids_ctrl") + ".translateZ") / 2.0)
    cmds.setAttr(curl + ".rotateZ", cmds.getAttr(GC._long("Face_settings_ctrl") + ".curl"))
real_settle = FP.WT._settle
cmds.setAttr(GC._long("L_Upper_Eyelids_ctrl") + ".translateZ", 2)
cmds.setAttr(GC._long("L_Ear_01_FK_ctrl") + ".rotateZ", 20); cmds.setAttr(GC._long("L_Ear_02_FK_ctrl") + ".rotateZ", 10)
cmds.setAttr(GC._long("Face_settings_ctrl") + ".curl", 30); cmds.setAttr(GC._long("Face_settings_ctrl") + ".ikfk", 1)
drive()
with mock.patch.object(FP, "pose_controls", side_effect=lambda h=None: [GC._long(c.split("|")[-1]) for c in CT]), \
        mock.patch.object(FP.WT, "_settle", side_effect=lambda *a: drive()):
    got = FP.save_pose("Mouth_main_ctrl", "Blink", False, include_on=False)
rec = FP.read(GC._long("Mouth_main_ctrl"))["Blink"]["ctrls"]
r = dict((k, [round(v, 3) for v in rec[k]["t"]] + [round(v, 3) for v in rec[k]["r"]]) for k in rec)
print(r)
check("the lid's closing kept (down 1.5 - it comes from the driven-key group above it)",
      r.get("L_Eyelids_fol_01_ctrl", [0])[:3] == [0, -1.5, 0])
check("the ear chain: each link its own turn (20, 10)", r["L_Ear_01_FK_ctrl"][3:] == [0, 0, 20] and
      r["L_Ear_02_FK_ctrl"] == [0, 0, 0, 0, 0, 10])
check("the curl kept: the tongue control turned 30 (curl to its default while the rest was measured)",
      r.get("Tongue_01_FK_ctrl", [0] * 6)[3:] == [0, 0, 30])
check("after: curl at its default, ikfk left as it was (a switch)",
      cmds.getAttr(GC._long("Face_settings_ctrl") + ".curl") == 0 and
      cmds.getAttr(GC._long("Face_settings_ctrl") + ".ikfk") == 1)
src = open("../tools/face_kit_tool.py").read()
check("the name field empties after a save; Save as new the default, Replace after Edit picked pose",
      'cmds.textField(N("pose_name"), edit=True, text="")' in src and '_EDITING.get("pose") == name' in src)
print("%d/%d passed" % (sum(ok), len(ok)))
