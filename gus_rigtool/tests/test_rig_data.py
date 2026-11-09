# Rig data: your attributes and Spaces-tool switches on builder controls survive a rebuild; export / import a file
import tempfile, os
exec(open("fakemaya.py").read())
from unittest import mock
cmds.keyframe = mock.MagicMock(return_value=[]); cmds.keyTangent = mock.MagicMock(return_value=[])
sdk = []
cmds.setDrivenKeyframe = lambda *a, **k: sdk.append((a[0].split("|")[-1], k["currentDriver"].split("|")[-1], k["driverValue"], k["value"]))
_add = cmds.addAttr
def addAttr(*a, **k):
    if k.get("edit"):
        n, at = _split(a[0]); n.enums[at] = k.get("enumName", n.enums.get(at)); return
    _add(*a, **k)
cmds.addAttr = addAttr
_da = cmds.deleteAttr
def deleteAttr(plug, **k):
    n, a = _split(plug); n.user.pop(a, None)
    S.conns[:] = [c for c in S.conns if not ((c[2] is n and c[3] == a) or (c[0] is n and c[1] == a))]
cmds.deleteAttr = deleteAttr
from gus_rigtool.builder import build as bld, rig_data
from gus_rigtool.core import spaces
bld.biped(180); bld.build_all(180)
c = "L_humerus_FK_ctrl"
cmds.addAttr(cmds.ls(c, long=True)[0], longName="wiggle", attributeType="double", keyable=True); cmds.setAttr(c + ".wiggle", 0.4)
a1, a2 = cmds.createNode("transform", name="propA"), cmds.createNode("transform", name="propB")
spaces.make(cmds.ls(c, long=True)[0], [("a", a1), ("b", a2)], "orient", "follow", 1)
print("before:", "wiggle" in _n(c).user, spaces.read(c)["attr"], cmds.getAttr(c + ".follow"))
bld.build_picked(["L:arm"], 180)
c2 = cmds.ls(c, long=True)[0]
print("after Build picked: wiggle", cmds.getAttr(c2 + ".wiggle") if "wiggle" in _n(c2).user else None,
      "| switch:", (spaces.read(c2) or {}).get("targets"), "value", cmds.getAttr(c2 + ".follow") if spaces.read(c2) else None,
      "| under its space group:", c2.split("|")[-3])
bld.back_to_guides_selected(["L:arm"], force=True); bld.build_picked(["L:arm"], 180)
c3 = cmds.ls(c, long=True)[0]
print("after Back to guides + Build picked: wiggle", "wiggle" in _n(c3).user, "| switch:", bool(spaces.read(c3)))
# file
path = os.path.join(tempfile.mkdtemp(), "rig.json")
cmds.addAttr(cmds.ls("L_radius_FK_ctrl", long=True)[0], longName="curl", attributeType="double", keyable=True)
crv = cmds.createNode("animCurveUA", name="my_sdk"); cmds.connectAttr("L_wrist_settings_ctrl.ikfk", crv + ".input")
cmds.connectAttr(crv + ".output", "L_radius_FK_ctrl.curl")
cmds.keyframe.side_effect = lambda *a, **k: [0.0, 1.0] if k.get("floatChange") else [0.0, 45.0]
n, k = rig_data.export(path, [cmds.ls("L_radius_FK_ctrl", long=True)[0]])
print("exported:", n, "control(s),", k, "driven key curve(s)")
cmds.deleteAttr("L_radius_FK_ctrl.curl")
got, notes = rig_data.import_(path, shapes=False)
print("imported:", got, notes[:2], "| curl back:", "curl" in _n("L_radius_FK_ctrl").user, "| keys:", sdk)
