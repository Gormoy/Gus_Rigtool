# 5.2.1: (a) Switch to constraints also takes ribbon bind joints that hang under their (mirrored, -1 scale)
# controls, and one left outside under Maya's 'transform1' (the Hare's R_Sleeve_fol_01_bind); (b) nodes <-> set
# driven key: the brow's clamp + x-4 chain becomes keys (0, 0) (1, -4), and back
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import ribbon, sdk_convert as SC
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# ---- (a) the right sleeve: binds under the controls, one under transform1
rib = cmds.createNode("transform", name="R_Sleeve_ribbon_grp")
srf = cmds.createNode("transform", name="R_Sleeve", parent=rib)
cmds.createNode("nurbsSurface", name="R_SleeveShape1", parent=srf)
cg = cmds.createNode("transform", name="R_Sleeve_ctrls_grp", parent=rib)
for a in ("rrbSurface", "rrbSkin"):
    cmds.addAttr(cg, longName=a, dataType="string")
cmds.setAttr(cg + ".rrbSurface", "R_Sleeve", type="string"); cmds.setAttr(cg + ".rrbSkin", "", type="string")
ctrls = []
for i in (1, 3, 5):
    off = cmds.createNode("transform", name="R_Sleeve_fol_%02d_ctrl_offset" % i, parent=cg)
    cmds.addAttr(off, longName="rrbIndex", attributeType="long"); cmds.setAttr(off + ".rrbIndex", i - 1)
    cmds.xform(off, worldSpace=True, translation=[-20 - i, 60, 0])
    c = cmds.createNode("transform", name="R_Sleeve_fol_%02d_ctrl" % i, parent=off)
    cmds.createNode("nurbsCurve", name="R_Sleeve_fol_%02d_ctrlShape" % i, parent=c)
    ctrls.append(cmds.ls(c, long=True)[0])
    if i == 1:
        t1 = cmds.createNode("transform", name="transform1", parent=cg)                 # Maya's extra group
        cmds.createNode("joint", name="R_Sleeve_fol_01_bind", parent=t1)
    else:
        cmds.createNode("joint", name="R_Sleeve_fol_%02d_bind" % i, parent=c)
loose = [(a.split("|")[-1], b.split("|")[-1]) for a, b in ribbon._loose_binds(ctrls)]
check("found: two under their controls, one outside under transform1", sorted(loose) == [
    ("R_Sleeve_fol_01_ctrl", "R_Sleeve_fol_01_bind"), ("R_Sleeve_fol_03_ctrl", "R_Sleeve_fol_03_bind"),
    ("R_Sleeve_fol_05_ctrl", "R_Sleeve_fol_05_bind")])
with mock.patch.object(ribbon, "_say", lambda *a: None):
    n = ribbon.to_constraints("R_Sleeve")
check("Switch to constraints: all three", n == 3)
for i in (1, 3, 5):
    j = cmds.ls("R_Sleeve_fol_%02d_bind" % i, long=True)[0]
    kids = [k.split("|")[-1] for k in cmds.listRelatives(j, children=True) or []]
    check("fol_%02d: in R_Sleeve_bind_grp, point + orient constraints" % i,
          "|R_Sleeve_bind_grp|" in j and any("pointConstraint" in k for k in kids) and
          any("orientConstraint" in k for k in kids))
check("Maya's transform1 is gone", not cmds.objExists("transform1"))
check("the new bind group is part of the build", any(n.endswith("R_Sleeve_bind_grp") for n in
                                                     ribbon._find_builds()["R_Sleeve"]["nodes"]))

# ---- (b) nodes -> set driven key -> nodes
c = cmds.createNode("transform", name="L_Brow_02_ctrl")
sdk = cmds.createNode("transform", name="L_Brow_02_sdk")
cl = cmds.createNode("clamp"); cmds.setAttr(cl + ".minR", 0.0); cmds.setAttr(cl + ".maxR", 1.0e6)
md = cmds.createNode("multiplyDivide"); cmds.setAttr(md + ".input2X", -4.0)
cmds.connectAttr(c + ".translateY", cl + ".inputR"); cmds.connectAttr(cl + ".outputR", md + ".input1X")
cmds.connectAttr(md + ".outputX", sdk + ".rotateX")
f = lambda x: -4.0 * min(max(x, 0.0), 1.0e6)
with mock.patch.object(SC, "_sample", lambda d, t, xs: [(x, f(x)) for x in xs]):
    driver, nodes, keys, pre, post = SC.plan_sdk("L_Brow_02_sdk.rotateX")
check("nodes -> key: the driver is the control's translateY", driver.endswith("L_Brow_02_ctrl.translateY"))
check("keys at the corner: (0, 0) and the end; flat before, straight on after",
      keys[0] == (0.0, 0.0) and abs(keys[-1][1] - f(keys[-1][0])) < 1e-9 and pre == "constant" and post == "linear"
      and len(keys) == 2)
made = []
with mock.patch.object(SC, "_sample", lambda d, t, xs: [(x, f(x)) for x in xs]), \
        mock.patch.object(cmds, "setDrivenKeyframe", side_effect=lambda *a, **k: made.append((a, k)), create=True), \
        mock.patch.object(cmds, "setInfinity", lambda *a, **k: None, create=True):
    line = SC.to_sdk("L_Brow_02_sdk.rotateX")
print(line)
check("to_sdk: keyed with the control as driver, the chain deleted",
      len(made) == 2 and made[0][1]["currentDriver"].endswith("translateY") and not cmds.objExists(cl) and
      not cmds.objExists(md))
# a key curve -> nodes
cur = cmds.createNode("animCurveUA", name="L_Brow_02_sdk_rotateX")
cmds.connectAttr(c + ".translateY", cur + ".input"); cmds.connectAttr(cur + ".output", sdk + ".rotateX")
KEYS = {"x": [0.0, 1.0], "y": [0.0, -4.0], "t": ["linear", "linear"], "pre": "constant", "post": "linear"}
def keyframe(*a, **k):
    return KEYS["x"] if k.get("floatChange") else KEYS["y"]
def keyTangent(*a, **k):
    return KEYS["t"]
def setInfinity(*a, **k):
    return [KEYS["pre"]] if k.get("preInfinite") else [KEYS["post"]]
with mock.patch.object(cmds, "keyframe", side_effect=keyframe, create=True), \
        mock.patch.object(cmds, "keyTangent", side_effect=keyTangent, create=True), \
        mock.patch.object(cmds, "setInfinity", side_effect=setInfinity, create=True):
    plan = SC.plan_nodes("L_Brow_02_sdk.rotateX")
    check("key -> nodes: clamp from 0 (no top), x -4, no offset", plan[2] == 0.0 and plan[3] is None and
          plan[4] == -4.0 and abs(plan[5]) < 1e-12)
    line = SC.to_nodes("L_Brow_02_sdk.rotateX")
    print(line)
    md2 = cmds.ls("L_Brow_02_ty_to_Brow_02_sdk_md", long=True)
    check("built: clamp + multiply into rotateX, the curve gone", md2 and not cmds.objExists(cur) and
          cmds.getAttr(md2[0] + ".input2X") == -4.0 and
          cmds.getAttr("L_Brow_02_ty_to_Brow_02_sdk_clamp.minR") == 0.0)
    # a curved one is refused
    cur2 = cmds.createNode("animCurveUA", name="bent")
    cmds.connectAttr(c + ".translateX", cur2 + ".input")
    t2 = cmds.createNode("transform", name="bent_sdk")
    cmds.connectAttr(cur2 + ".output", t2 + ".rotateY")
    KEYS.update(x=[0.0, 1.0, 2.0], y=[0.0, -4.0, -6.0], t=["linear"] * 3)
    try:
        SC.plan_nodes("bent_sdk.rotateY")
        refused = False
    except RuntimeError as e:
        refused = "bends" in str(e)
    check("a bent key curve is left, with the reason", refused)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
