# 5.0.2: Bendy limbs get a bend control ON the knee / elbow: it follows the joint, the two bendy pieces' shared
# end follows it, and its 'roundness' turns those ends towards each other (nothing moves at rest)
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, guides, modules
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
bld.biped(180)
for g in guides.module_groups():
    i = guides.read(g)
    if i["id"] in ("L:leg", "R:leg", "L:arm", "R:arm"):
        s = modules.MODULES[i["type"]].complete(i["settings"]); s["options"]["bendy"] = True
        guides.save_settings(g, s); guides.update(g, modules.MODULES[i["type"]], s, 180)
bld.build_all(180)
names_ = sorted(n.name for n in S.nodes if n.name.endswith("_bend_ctrl"))
print("   ", names_)
for c in ("L_knee_bend_ctrl", "R_knee_bend_ctrl", "L_elbow_bend_ctrl", "R_elbow_bend_ctrl"):
    check("%s made, with 'roundness' 0-1 (0 at rest)" % c, c in names_ and cmds.getAttr(c + ".roundness") == 0.0)
knee = cmds.ls("L_knee_bend_ctrl", long=True)[0]
off = cmds.listRelatives(knee, parent=True, fullPath=True)[0]
cons = cmds.listRelatives(off, type="parentConstraint") or []
check("it follows the knee joint", cons and any("tibia" in t for t in cmds.parentConstraint(cons[0], query=True, targetList=True)))
def targets(drv, kind):
    out = []
    for c in cmds.listRelatives(cmds.ls(drv, long=True)[0], type=kind) or []:
        out += [t.split("|")[-1] for t in getattr(cmds, kind)(c, query=True, targetList=True) or []]
    return out
check("the thigh piece's end follows the knee control", "L_knee_bend_ctrl" in targets("L_femur_bendy_end_drv_jnt", "pointConstraint"))
check("the shin piece's start follows the knee control", "L_knee_bend_ctrl" in targets("L_tibia_bendy_start_drv_jnt", "pointConstraint"))
check("roundness turns both ends (thigh end towards the shin, shin start towards the thigh)",
      sorted(targets("L_femur_bendy_end_drv_jnt", "parentConstraint")) == ["L_femur_jnt", "L_tibia_jnt"] and
      sorted(targets("L_tibia_bendy_start_drv_jnt", "parentConstraint")) == ["L_femur_jnt", "L_tibia_jnt"])
half = cmds.ls("L_femur_bendy_end_round_half")
check("roundness drives the turn (x 0.5: half way at 1)", half and cmds.listConnections(half[0] + ".input1", source=True))
from gus_rigtool.builder import limb
st = cmds.ls("L_ankle_settings_ctrl", long=True)[0]
check("the limb knows its bend controls (select the limb, IK/FK keys them)",
      sorted(limb._meta(st, "gusTweaks")) == ["L_femur_bend_ctrl", "L_knee_bend_ctrl", "L_tibia_bend_ctrl"])
print("ALL OK" if all(ok) else "SOME FAILED")
