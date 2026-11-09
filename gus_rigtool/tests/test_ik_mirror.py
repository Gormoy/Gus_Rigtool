# Right IK controls / pole vectors move as the mirror of the left ones (scale -1 offset, 'hold' group below)
exec(open("fakemaya.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.builder import build as bld, limb, mathx
bld.biped(180.0)
bld.build_all(180.0)
for part in ("ankle", "wrist"):
    l, r = cmds.ls("L_%s_IK_ctrl" % part, long=True)[0], cmds.ls("R_%s_IK_ctrl" % part, long=True)[0]
    print(part, "| R offset scaleX:", cmds.getAttr(cmds.listRelatives(r, parent=True, fullPath=True)[0] + ".scaleX"),
          "| L offset scaleX:", cmds.getAttr(cmds.listRelatives(l, parent=True, fullPath=True)[0] + ".scaleX"),
          "| hold:", [c.split("|")[-1] for c in cmds.listRelatives(r, children=True, type="transform") or []])
    for c in (l, r):
        cmds.setAttr(c + ".tx", 3.0); cmds.setAttr(c + ".ty", 2.0); cmds.setAttr(c + ".ry", 20.0)
    pl, pr = limb.world(l), limb.world(r)
    print("   same values -> mirror: pos L", [round(v, 3) for v in pl[12:15]], "R", [round(v, 3) for v in pr[12:15]],
          "| x mirrored:", abs(pl[12] + pr[12]) < 1e-6, "| X axis mirrored:",
          [round(v, 3) for v in pl[0:3]], [round(v, 3) for v in pr[0:3]])
    before = [cmds.getAttr(r + "." + a) for a in ("tx", "ty", "tz", "rx", "ry", "rz")]
    limb.set_world(r, limb.world(r))
    after = [cmds.getAttr(r + "." + a) for a in ("tx", "ty", "tz", "rx", "ry", "rz")]
    print("   set_world on itself keeps the values:", all(abs(a - b) < 1e-6 for a, b in zip(before, after)))
pv = cmds.ls("R_tibia_PV_ctrl", long=True)[0]
print("pv offset:", cmds.getAttr(cmds.listRelatives(pv, parent=True, fullPath=True)[0] + ".scaleX"))
sp = [n for n in cmds.ls(type="transform", long=True) if n.split("|")[-1].startswith("R_") and "space" in n.split("|")[-1]]
print("space groups unscaled:", [(n.split("|")[-1], cmds.getAttr(n + ".scaleX")) for n in sp][:4])
heel = cmds.ls("R_ankle_heelPivot_grp", long=True)
print("heel pivot under hold:", heel and "_hold" in heel[0].split("|")[-2], "| world X axis", [round(v, 3) for v in limb.world(heel[0])[0:3]])
