# 4.0.7: the report (problems first, summary, expected notes) and Check this scene on a small scene
exec(open("fakemaya.py").read())
import math
from gus_rigtool.core import report as R
rep = R.Report("Maya check")
rep.start("Windows")
rep.add(R.OK, "main window")
rep.step("page that breaks", lambda: 1 / 0)
rep.start("Animtool")
rep.step("action pull", lambda: (_ for _ in ()).throw(RuntimeError("select keys in the Graph Editor first.")))
rep.step("action odd", lambda: (_ for _ in ()).throw(RuntimeError("something new went wrong")))
rep.add(R.OK, "action key")
rep.start("Facts")
rep.add(R.INFO, "Mouth_ribbon", "26 follicles")
rep.start("Never used")
cmds.about = lambda **k: "2024"
t = rep.text()
print("\n".join(l for l in t.splitlines()[2:] if "File" not in l and "line" not in l))
print("problems first:", t.index("PROBLEMS") < t.index("SUMMARY") < t.index("DETAILS"))
print("expected note is fine, not a problem:", "action pull" not in t.split("SUMMARY")[0])
print("empty section not listed:", "Never used" not in t)
ok = R.Report("x"); ok.start("A"); ok.add(R.OK, "a")
print("clean:", ok.text().splitlines()[3])

# --- Check this scene on a small fake scene: an old-style mouth ribbon, a follow, a joint with no label
from gus_rigtool.core import ribbon, follow
cmds.joint = lambda name=None, **k: cmds.createNode("joint", name=name)
cmds.deleteAttr = lambda node, attribute=None: _n(node).user.pop(attribute, None)
top = cmds.createNode("transform", name="Mouth_ribbon_ctrls_grp")
bgrp = cmds.createNode("transform", name="Mouth_ribbon_bind_grp")
for g in (top, bgrp):
    cmds.addAttr(g, longName="rrbSurface", dataType="string"); cmds.setAttr(g + ".rrbSurface", "Mouth_ribbon", type="string")
    cmds.addAttr(g, longName="rrbSkin", dataType="string"); cmds.setAttr(g + ".rrbSkin", "", type="string")
    cmds.addAttr(g, longName="rrbSettings", dataType="string")
    cmds.setAttr(g + ".rrbSettings", '{"prefix": "Mouth_ribbon", "pivot_on_shape": true}', type="string")
cmds.createNode("transform", name="Mouth_ribbon")
def make(i, x, y, yaw):
    off = cmds.createNode("transform", name="m%d_offset" % i, parent=top)
    cmds.addAttr(off, longName="rrbIndex", attributeType="long"); cmds.setAttr(off + ".rrbIndex", i)
    co, si = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cmds.xform(off, worldSpace=True, matrix=[co, 0, -si, 0, 0, 1, 0, 0, si, 0, co, 0, x, y, 10, 1])
    ctrl = cmds.createNode("transform", name="m%d_ctrl" % i, parent=off)
    cmds.createNode("nurbsCurve", name="m%d_ctrlShape" % i, parent=ctrl)
    boff = cmds.createNode("transform", name="m%d_bind_offset" % i, parent=bgrp)
    bj = cmds.createNode("joint", name="m%d_bind" % i, parent=boff)
    for ch in ("translate", "rotate"):
        cmds.connectAttr(ctrl + "." + ch, bj + "." + ch)
    return ctrl
for i, (x, y, yaw) in enumerate(((3, 0, 20), (0, 1, 0), (-3, 0, 200), (0, -1, 180))):
    make(i, x, y, yaw)
jaw = cmds.createNode("transform", name="jaw_ctrl")
follow.add(jaw, ["m3_ctrl"], ("rotate",), "control", 0.8)
import gus_rigtool.scene_check as SC
for n, v in (("currentUnit", lambda **k: "cm" if k.get("linear") else "film"), ("upAxis", lambda **k: "y"),
             ("unknownPlugin", lambda *a, **k: []), ("internalVar", lambda **k: "/tmp/")):
    setattr(cmds, n, v)
_file = cmds.file
cmds.file = lambda *a, **k: (None if not k.get("query") else ("" if k.get("sceneName") else [] if k.get("reference") else False))
r = SC.report()
t = r.text()
crashed = [x for x in t.splitlines() if "crashed" in x and x.strip().startswith("FAIL")]
print("checker parts the fake Maya cannot run:", len(crashed))
for key in ("joints copy their controls", "m3_ctrl   <- jaw_ctrl x 0.80", "Mouth_ribbon:"):
    print("found %-30s" % key, any(key in line for line in t.splitlines()))
print("scene not changed: m0_bind still copies:", ribbon._copier(cmds.ls("m0_ctrl", long=True)[0]) is not None)
