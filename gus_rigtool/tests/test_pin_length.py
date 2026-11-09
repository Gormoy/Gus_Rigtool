# Arm / leg: pin and length per bone - sliders on the settings control and the node network (stretch off too)
exec(open("fakemaya.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.builder import build as bld, guides, modules
bld.add_module("root", "C", "root", 180.0) if "root" in modules.MODULES else None
g = bld.add_module("leg", "L", "leg", 180.0)
s = guides.read(g)["settings"]; s["options"]["pin"] = True; s["options"]["bone_length"] = True
guides.save_settings(g, s)
bld.build_all(180.0)
st = cmds.ls("L_ankle_settings_ctrl")[0]
print("settings attrs:", [a for a in cmds.listAttr(st, userDefined=True) if not a.startswith("gus")])
tib = cmds.ls("L_tibia_IK_jnt")[0]
src = cmds.listConnections(tib + ".translateX", source=True, destination=False)
print("tibia length <-", src, "<-", sorted(cmds.listConnections(src[0], source=True, destination=False) or []))
pd = cmds.ls("L_ankle_stretchPinDm00")[0]
print("pin measures from:", cmds.listConnections(pd + ".inputMatrix", source=True, destination=False),
      cmds.listConnections("L_ankle_stretchPinDm01.inputMatrix", source=True, destination=False),
      "| no auto stretch nodes:", not cmds.ls("L_ankle_stretchDist"))
