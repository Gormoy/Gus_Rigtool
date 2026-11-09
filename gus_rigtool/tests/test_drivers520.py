# 5.2.0: Make a driver (the Hare's brow: translateY up -> rotateX x -4 on the _sdk group, on both sides) and Connect
# by name pattern (L_Brow_0*_ctrl.translateY -> L_Brow_0*_sdk.rotateX)
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import drivers as D, connector
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def ctrl(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
for sd in "LR":
    for i in (1, 2, 3):
        ctrl("%s_Brow_0%d_ctrl" % (sd, i))
        cmds.createNode("transform", name="%s_Brow_0%d_sdk" % (sd, i))
src = cmds.ls("L_Brow_02_ctrl", long=True)[0] + ".translateY"
text = D.preview(src, [("L_Brow_02_sdk", "rotateX", -4.0)], side="positive")
print(text)
check("preview: this side and the other", "L_Brow_02_ctrl.translateY" in text and "R_Brow_02_ctrl.translateY" in text
      and "x -4 -> L_Brow_02_sdk.rotateX" in text and "x -4 -> R_Brow_02_sdk.rotateX" in text)
made, skipped = D.make(src, [("L_Brow_02_sdk", "rotateX", -4.0)], side="positive")
names = [m.split("|")[-1] for m in made]
print(names)
check("made: a clamp and a multiplyDivide on each side, named", set(names) >= {
    "L_Brow_02_ty_to_Brow_02_sdk_clamp", "L_Brow_02_ty_to_Brow_02_sdk_md",
    "R_Brow_02_ty_to_Brow_02_sdk_clamp", "R_Brow_02_ty_to_Brow_02_sdk_md"} and not skipped)
cl, md = "L_Brow_02_ty_to_Brow_02_sdk_clamp", "L_Brow_02_ty_to_Brow_02_sdk_md"
check("positive side only: clamp 0 .. big", cmds.getAttr(cl + ".minR") == 0.0 and cmds.getAttr(cl + ".maxR") >= 1e5)
check("x -4 into the sdk's rotateX", cmds.getAttr(md + ".input2X") == -4.0 and
      (cmds.listConnections(md + ".outputX", plugs=True) or [""])[0].endswith("L_Brow_02_sdk.rotateX"))
check("fed by the control's translateY", (cmds.listConnections(cl + ".inputR", plugs=True, source=True,
                                                                destination=False) or [""])[0].endswith(
    "L_Brow_02_ctrl.translateY"))
check("the other side: the same amount (not flipped)", cmds.getAttr("R_Brow_02_ty_to_Brow_02_sdk_md.input2X") == -4.0)
# again on the same channel: already driven -> skipped, says so
made2, skipped2 = D.make(src, [("L_Brow_02_sdk", "rotateX", -4.0)], side="positive")
check("a channel already driven is skipped, with the reason", not made2 and skipped2 and "already driven" in skipped2[0])
# negative with a limit, flipped on the other side
s3 = cmds.ls("L_Brow_03_ctrl", long=True)[0] + ".translateY"
made3, _s = D.make(s3, [("L_Brow_03_sdk", "rotateZ", 10.0)], side="negative", limit=2.0, flip_other=True)
check("negative side up to 2: clamp -2 .. 0", cmds.getAttr("L_Brow_03_ty_to_Brow_03_sdk_clamp.minR") == -2.0 and
      cmds.getAttr("L_Brow_03_ty_to_Brow_03_sdk_clamp.maxR") == 0.0)
check("flipped on the other side: -10", cmds.getAttr("R_Brow_03_ty_to_Brow_03_sdk_md.input2X") == -10.0)
# both ways, no limit: no clamp
s1 = cmds.ls("L_Brow_01_ctrl", long=True)[0] + ".translateX"
made4, _s = D.make(s1, [("L_Brow_01_sdk", "translateX", 0.5)], side="both", mirror=False)
check("both ways, no limit: just the multiply, this side only", [m.split("|")[-1] for m in made4] ==
      ["L_Brow_01_tx_to_Brow_01_sdk_md"])

# Connect by pattern (Maya's ls understands *; the fake gets it here)
import fnmatch
_ls = cmds.ls
def ls(*a, **k):
    if a and isinstance(a[0], str) and "*" in a[0]:
        names = [n for n in _ls(long=True) if fnmatch.fnmatchcase(n.split("|")[-1], a[0])]
        return sorted(names)
    return _ls(*a, **k)
cmds.ls = ls
pairs = connector.pattern_pairs("L_Brow_0*_ctrl.translateZ", "L_Brow_0*_sdk.scaleY")
short = [(a.split("|")[-1], b.split("|")[-1]) for a, b in pairs]
print(short)
check("pattern: pairs by what * stands for", short == [("L_Brow_01_ctrl.translateZ", "L_Brow_01_sdk.scaleY"),
                                                       ("L_Brow_02_ctrl.translateZ", "L_Brow_02_sdk.scaleY"),
                                                       ("L_Brow_03_ctrl.translateZ", "L_Brow_03_sdk.scaleY")])
made5, prob = connector.connect_pairs(pairs, middle=1, factor=0.5)
check("connected with a multiply in between", made5 == 3 and not prob)
one = connector.pattern_pairs("L_Brow_01_ctrl.visibility", "R_Brow_0*_sdk.visibility")
check("one driver, many driven", len(one) == 3)
try:
    connector.pattern_pairs("L_Brow_0*_ctrl.tx", "nothing_*.tx")
    bad = False
except ValueError as e:
    bad = "nothing matches" in str(e)
check("nothing matching says so", bad)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
