# 5.5.1: keep the pose, zero the control - its values go into the group above it (nothing moves); skipped when the
# group has other things under it or is driven; the heaviest list puts Maya's default names apart; a page built in
# a hidden tab is measured again the first time it's shown
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import zero_pose, network_tools as NT, ui
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

def ctrl(name, parent):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent)
    cmds.xform(off, worldSpace=True, translation=[5, 10, 0])
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0], cmds.ls(off, long=True)[0]

top = cmds.createNode("transform", name="rig")
c, off = ctrl("Cape_Ribbon_fol_02_ctrl", top)
cmds.setAttr(c + ".translateY", 2.5); cmds.setAttr(c + ".rotateX", 30); cmds.setAttr(c + ".scaleZ", 1.5)
before = cmds.xform(c, query=True, worldSpace=True, matrix=True)
done, skipped = zero_pose.apply([c])
after = cmds.xform(c, query=True, worldSpace=True, matrix=True)
check("zeroed: translate / rotate 0, scale 1", done == [c] and cmds.getAttr(c + ".translateY") == 0 and
      cmds.getAttr(c + ".rotateX") == 0 and cmds.getAttr(c + ".scaleZ") == 1)
check("nothing moved", max(abs(a - b) for a, b in zip(before, after)) < 1e-6)
check("its group took the pose", abs(cmds.xform(off, query=True, worldSpace=True, translation=True)[1] - 12.5) < 1e-6)

e, eoff = ctrl("Eyes_ctrl", top)
cmds.createNode("transform", name="Eyes_extra", parent=eoff)
cmds.setAttr(e + ".translateX", 1)
done, skipped = zero_pose.apply([e])
check("a group with other things under it: (5.6.6) a new Eyes_ctrl_rest takes the pose", not skipped and
      done and done[0].endswith("|Eyes_ctrl_rest|Eyes_ctrl") and cmds.getAttr(done[0] + ".translateX") == 0)
d, doff = ctrl("Driven_ctrl", top)
cmds.setAttr(d + ".translateX", 1)
cmds.connectAttr(top + ".translateX", doff + ".translateX")
check("a driven group: (5.6.6) a rest group too", zero_pose.apply([d])[0][0].endswith("_rest|Driven_ctrl"))
z, _zoff = ctrl("Zero_ctrl", top)
check("already at rest: left alone", zero_pose.apply([z]) == ([], []))

check("Maya's default names grouped apart in the heaviest list", NT._part("unitConversion253") == "(default names)"
      and NT._part("multiplyDivide12") == "(default names)" and NT._part("L_Brow_md") == "L_Brow")

calls = []
ui._built_hidden.clear()
ui._built_hidden["constrain"] = ("col", "m_constrain_", 2)
with mock.patch.object(ui, "visible_tool", return_value="constrain"), \
        mock.patch.object(ui, "build_page", return_value=False), \
        mock.patch.object(ui, "rebuild_page", side_effect=lambda k: calls.append(k) or ui._built_hidden.pop(k)):
    ui.build_visible_page(); ui.build_visible_page()
check("5.6.1: a page built while hidden is built again the first time it's shown (once)", calls == ["constrain"])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
