# 5.6.12: face expressions - pose the face, Save as Smile: the pose goes into Smile_L / Smile_R on the slider
# control (each control's share by where it is: left 1 / right 0 / the middle half each), measured in the control's
# own layer space (a turned lip: its move turned into its axes; a turn kept as a turn), the face back to 0; the other
# sliders at 0 while measuring; saving again replaces; a face at rest is refused; remove cleans up (no layers left);
# selection sets made in the rig under gus_anim_sets, and Gus Animtool lists them
import sys, math
exec(open("fakemaya.py").read())
from gus_rigtool.core import face_poses as FP, group_ctrls as GC
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
src = lambda p: cmds.listConnections(p, source=True, destination=False, plugs=True) or []
def mk(name, parent=None, pos=(0, 0, 0), roty=0):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=pos)
    cmds.setAttr(off + ".rotateY", roty)
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]

head = mk("Head_ctrl", None, (0, 150, 0))
L = mk("L_Mouth_fol_06_ctrl", head, (4, 150, 10))
R = mk("R_Mouth_fol_22_ctrl", head, (-4, 150, 10))
M = mk("Mouth_fol_33_ctrl", head, (0, 149, 11))
T = mk("L_Mouth_fol_02_ctrl", head, (2, 151, 10.5), roty=90)        # a lip control turned 90 on Y
holder = mk("Mouth_main_ctrl", head, (0, 150, 14))
check("the pose controls: the face ones (not the slider control)", sorted(c.split("|")[-1] for c in FP.pose_controls("Mouth_main_ctrl"))
      == sorted(["L_Mouth_fol_06_ctrl", "R_Mouth_fol_22_ctrl", "Mouth_fol_33_ctrl", "L_Mouth_fol_02_ctrl"]))

# a smile: corners up, the middle a little, the turned one sideways in the world (+X) and turned 10
cmds.setAttr(L + ".translateY", 1); cmds.setAttr(R + ".translateY", 1); cmds.setAttr(M + ".translateY", 0.4)
cmds.setAttr(T + ".translateZ", -1)                       # its local -Z = world +X (its group turned 90 on Y)
cmds.setAttr(T + ".rotateX", 10)
got = FP.save_pose("Mouth_main_ctrl", "smile")
print(got)
check("Smile_L / Smile_R on the slider control, 4 controls", got["attrs"] == ["Smile_L", "Smile_R"] and
      got["controls"] == 4 and cmds.attributeQuery("Smile_L", node="Mouth_main_ctrl", exists=True))
check("the face back at rest", all(cmds.getAttr(GC._long(c.split("|")[-1]) + ".translateY") == 0
                                   for c in (L, R, M)) and
      abs(cmds.getAttr(GC._long("L_Mouth_fol_02_ctrl") + ".translateZ")) < 1e-9)
d = FP.read(GC._long("Mouth_main_ctrl"))["Smile"]["ctrls"]
check("left corner: all left; right corner: all right; the middle: half each",
      d["L_Mouth_fol_06_ctrl"]["left"] == 1.0 and d["R_Mouth_fol_22_ctrl"]["left"] == 0.0 and
      abs(d["Mouth_fol_33_ctrl"]["left"] - 0.5) < 1e-6)
check("the corner's move: 1 up in its layer's space", [round(v, 6) for v in d["L_Mouth_fol_06_ctrl"]["t"]] ==
      [0, 1, 0])
tt = d["L_Mouth_fol_02_ctrl"]["t"]
check("the turned lip's move measured in its own group's axes (-Z there: %s)" % [round(v, 3) for v in tt],
      abs(tt[2] + 1) < 1e-6 and abs(tt[0]) < 1e-6)
check("its turn kept as a turn (10 on X: %s)" % [round(v, 3) for v in d["L_Mouth_fol_02_ctrl"]["r"]],
      abs(d["L_Mouth_fol_02_ctrl"]["r"][0] - 10) < 1e-3)
lay = GC.layer_of(GC._long("Mouth_fol_33_ctrl"))
pt = src(lay + ".translate")[0].split(".")[0]
ins = cmds.listConnections(pt + ".input3D", source=True, destination=False) or []
check("the middle one: both sliders feed its layer (%d)" % len(ins), len(ins) == 2)
md = [n for n in d["Mouth_fol_33_ctrl"]["nodes"] if n.startswith("Smile_L")][0]
check("...each with half the move", abs(cmds.getAttr(md + ".input1")[0][1] - 0.2) < 1e-6
      if isinstance(cmds.getAttr(md + ".input1")[0], tuple) else abs(cmds.getAttr(md + ".input1")[1] - 0.2) < 1e-6)

# at rest: refused
try:
    FP.save_pose("Mouth_main_ctrl", "Frown")
    check("a face at rest: refused", False)
except RuntimeError:
    check("a face at rest: refused", True)
# saving again replaces; other sliders zeroed while measuring
cmds.setAttr("Mouth_main_ctrl.Smile_L", 0.7)
cmds.setAttr(GC._long("L_Mouth_fol_06_ctrl") + ".translateY", -1)
got = FP.save_pose("Mouth_main_ctrl", "Frown", split=False)
check("Frown (not split): one slider; Smile set to 0 while it was measured", got["attrs"] == ["Frown"] and
      cmds.getAttr("Mouth_main_ctrl.Smile_L") == 0)
cmds.setAttr(GC._long("L_Mouth_fol_06_ctrl") + ".translateY", -2)
FP.save_pose("Mouth_main_ctrl", "Frown", split=False)
check("saved again: replaced (-2 now)", FP.read(GC._long("Mouth_main_ctrl"))["Frown"]["ctrls"]["L_Mouth_fol_06_ctrl"]
      ["t"][1] == -2 and FP.poses(GC._long("Mouth_main_ctrl")) == ["Frown", "Smile"])
FP.remove_pose("Mouth_main_ctrl", "Frown"); FP.remove_pose("Mouth_main_ctrl", "Smile")
check("removed: sliders gone, no layers left", not cmds.attributeQuery("Smile_L", node="Mouth_main_ctrl", exists=True)
      and not GC.layer_of(GC._long("Mouth_fol_33_ctrl")))

# euler: a known turn
r = [[math.cos(math.radians(30)), 0, -math.sin(math.radians(30))], [0, 1, 0],
     [math.sin(math.radians(30)), 0, math.cos(math.radians(30))]]
check("a 30 degree turn on Y reads back as 30 on Y", [round(v, 6) for v in FP._euler_xyz(r)] == [0, 30, 0])

# selection sets
got = FP.make_sets([GC._long(n) for n in ("L_Mouth_fol_06_ctrl", "R_Mouth_fol_22_ctrl", "Mouth_fol_33_ctrl",
                                          "L_Mouth_fol_02_ctrl")])
print(got)
check("sets: all, corners (the two widest), upper / lower", got.get("mouth_all") == 4 and got.get("mouth_corners") == 2
      and got.get("face_all") == 4)
members = [m.split("|")[-1] for m in cmds.sets("gus_anim_sets", query=True)]
check("all of them inside gus_anim_sets", sorted(members) == sorted(got))
import os
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import selsets as SS, anim as A
with mock.patch.object(A, "profile", return_value={}), mock.patch.object(A, "current_character", return_value=""):
    names = SS.names("")
    corners = [m.split("|")[-1] for m in SS.members("mouth_corners", "")]
check("Gus Animtool lists the rig's sets (%s)" % names, "mouth_corners" in names and sorted(corners) ==
      ["L_Mouth_fol_06_ctrl", "R_Mouth_fol_22_ctrl"])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
