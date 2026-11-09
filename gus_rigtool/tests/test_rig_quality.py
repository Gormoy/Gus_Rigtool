# 3.7: head spaces use a parent constraint (rotation only), no-flip knee, spine volume / stretch, lip falloff,
# quadruped pin / length / no-flip
exec(open("fakemaya.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.builder import build as bld, guides, modules
def opts(mtype, side, **o):
    for g in guides.module_groups():
        i = guides.read(g)
        if i["type"] == mtype and i["side"] == side:
            s = i["settings"]; s["options"].update(o); guides.save_settings(g, s)
            guides.update(g, modules.MODULES[mtype], s, 180.0)
bld.biped(180.0)
opts("spine", "C", type="ribbon", volume=True)
opts("leg", "L", no_flip=True)
opts("face", "C", lip_detail=True, lip_falloff=True)
bld.build_all(180.0)
hs = cmds.ls("head_space_grp", long=True)[0]
print("head space constraint:", [c.type for c in _n(hs).children])
st = cmds.ls("L_ankle_settings_ctrl")[0]
print("leg settings:", [a for a in cmds.listAttr(st, userDefined=True) if a.startswith("knee")])
pvc = [c for c in _n(cmds.ls("L_ankle_ikHandle", long=True)[0] if cmds.objExists("L_ankle_ikHandle") else
       [h for h in cmds.ls(type="ikHandle")][0]).children if c.type == "poleVectorConstraint"]
print("pole targets:", pvc[0].attrs["targets"] if pvc else None)
print("chest attrs:", [a for a in cmds.listAttr("chest_ctrl", userDefined=True)])
print("volume on middle joint:", cmds.listConnections("abdomen_jnt.scaleY", source=True, destination=False),
      "| ends left alone:", cmds.listConnections("spine_jnt.scaleY", source=True, destination=False))
print("side lip falloff:", [a for a in cmds.listAttr("L_lip_upper_side_ctrl", userDefined=True)],
      cmds.listConnections("L_lip_upper_side_falloff_grp.translate", source=True, destination=False))
# ik spline stretch + volume, quadruped extras
for g in guides.module_groups():
    cmds.delete(g)
for t in ("C_rig_grp", "rig_grp"):
    if cmds.objExists(t): cmds.delete(t)
bld.add_module("root", "C", height=180.0)
mod = modules.MODULES["spine"]; s = mod.complete(mod.default_settings("C"))
s["options"].update(type="ik_spline", stretch=True, volume=True)
bld.add_module("spine", "C", height=180.0, settings_=s)
mod = modules.MODULES["back_leg"]; s = mod.complete(mod.default_settings("L"))
s["options"].update(pin=True, bone_length=True, no_flip=True)
bld.add_module("back_leg", "L", height=180.0, settings_=s)
bld.build_all(180.0)
print("ik spline chest:", [a for a in cmds.listAttr("chest_ctrl", userDefined=True)],
      "| joint translate driven:", cmds.listConnections("abdomen_jnt.translateX", source=True, destination=False))
print("back leg settings:", [a for a in cmds.listAttr("L_ball_settings_ctrl", userDefined=True)
                             if a in ("pin", "upper_length", "lower_length", "knee_mode", "knee_twist")])
tw = cmds.ls("L_tibia_kneeTwist_grp", long=True) or cmds.ls("L_ball_kneeTwist_grp", long=True)
print("knee twist group starts at 0 (no pop):", [round(v, 6) for v in cmds.getAttr(tw[0] + ".rotate")[0]] if tw else tw,
      "| under its offset:", tw[0].split("|")[-2] if tw else None)
