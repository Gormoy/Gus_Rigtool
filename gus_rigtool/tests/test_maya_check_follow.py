# 4.0.7: the Maya check's Follow part runs end to end (fake Maya + a small numpy OpenMaya): the maths of the
# expected results agrees with what follow.py builds
exec(open("fakemaya.py").read())
import fake_om
import gus_rigtool.maya_check as mc
mc._om = lambda: fake_om
cmds.deleteAttr = lambda node, attribute=None: _n(node).user.pop(attribute, None)
cmds.circle = lambda name=None, **k: [cmds.createNode("transform", name=name)]
cmds.group = lambda *a, **k: cmds.createNode("transform", name=k.get("name"))
cmds.spaceLocator = lambda name=None, **k: [cmds.createNode("transform", name=name)]
mc._new_scene = lambda: None
# fake Maya doesn't solve the follow network: copy driver x weight onto the follow group when the driver turns
_set = cmds.setAttr
def setAttr(plug, *v, **k):
    _set(plug, *v, **k)
    if plug.endswith("chkEye_ctrl.rotateX"):
        f = cmds.ls("chkLid_ctrl_follow", long=True)
        if f:
            w = cmds.getAttr(cmds.ls("chkLid_ctrl", long=True)[0] + ".follow")
            _set(f[0] + ".rotateX", v[0] * w)
cmds.setAttr = setAttr
from gus_rigtool.core.report import Report
r = Report("x")
mc.check_follow(r)
for sec, st, name, det in r.rows:
    print(st, name)
