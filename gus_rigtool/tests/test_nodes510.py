# 5.1.0: Nodes - finding problems, from the Hare's brows: trace a channel (back to the control, with every value),
# compare sides (R_Brow_03's x1.0 vs the left's x1.6, a clamp fed by another control, a piece one side lacks),
# at rest (an offset left in a network), find loops
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import networks as NW
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def T(name, parent=None, x=0.0, kind="transform"):
    n = cmds.createNode(kind, name=name, parent=parent)
    cmds.xform(n, worldSpace=True, translation=[x, 150, 5])
    return cmds.ls(n, long=True)[0]
def C(name, x):
    off = T(name + "_offset", None, x)
    t = T(name, off, x)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return t
def chain(ctrl, sdk, factor, feeder=None):
    """ctrl.ty -> clamp 0..999 -> md x factor -> uc -> sdk.rotateX"""
    cl = cmds.createNode("clamp"); cmds.setAttr(cl + ".maxR", 999)
    cmds.connectAttr((feeder or ctrl) + ".translateY", cl + ".inputR")
    md = cmds.createNode("multiplyDivide"); cmds.setAttr(md + ".input2X", factor)
    cmds.setAttr(md + ".operation", 1)                            # Maya's default
    cmds.connectAttr(cl + ".outputR", md + ".input1X")
    uc = cmds.createNode("unitConversion"); cmds.setAttr(uc + ".conversionFactor", 0.0174533)
    cmds.connectAttr(md + ".outputX", uc + ".input")
    cmds.connectAttr(uc + ".output", sdk + ".rotateX")
    return cl, md, uc
L2, L3 = C("L_Brow_02_ctrl", 4), C("L_Brow_03_ctrl", 6)
R2, R3 = C("R_Brow_02_ctrl", -4), C("R_Brow_03_ctrl", -6)
LS2, LS3 = T("L_Brow_02_sdk", None, 4), T("L_Brow_03_sdk", None, 6)
RS2, RS3 = T("R_Brow_02_sdk", None, -4), T("R_Brow_03_sdk", None, -6)
chain(L2, LS2, -4.0); chain(L3, LS3, 1.6)
chain(R2, RS2, -4.0); chain(R3, RS3, 1.0)                       # the Hare: x1.0 where the left has x1.6
extra = cmds.createNode("multiplyDivide")                         # a piece only the left has
cmds.connectAttr(L2 + ".translate", extra + ".input1"); cmds.connectAttr(extra + ".output", LS2 + ".translate")

# trace
text = NW.trace_text(cmds.ls("L_Brow_03_sdk", long=True)[0] + ".rotateX")
print(text)
check("trace: back to the control through uc, md, clamp, with values",
      "unitConversion" in text and "multiply by" in text and "1.6" in text and "clamp" in text and
      "L_Brow_03_ctrl.translateY" in text)
check("trace: nothing drives it says so", "nothing drives it" in NW.trace_text(L2 + ".rotateZ"))
cons_sdk = T("L_Brow_cons_sdk", None, 5)
con = cmds.parentConstraint([L2, L3], cons_sdk, maintainOffset=True)[0]
t2 = NW.trace_text(cons_sdk + ".rotate")
print(t2)
check("trace: a constraint lists its targets and weights", "target L_Brow_02_ctrl  weight 1" in t2 and
      "target L_Brow_03_ctrl" in t2)

# compare sides
rows = NW.compare_sides([L2, L3])
txt = NW.compare_text([L2, L3])
print(txt)
check("compare: Brow_03's factor differs (1.6 vs 1)", any("multiply by (1.6" in w and "(1" in w.split(" vs ")[1]
                                                           for _c, _t, w in rows))
check("compare: a piece only the left has", any(w.startswith("only on L_Brow_02_ctrl") for _c, _t, w in rows))
check("compare: Brow_02's chain matches (not listed)", not any("clamp Brow_02.ty" in w for _c, _t, w in rows))
# the Hare's R clamp fed by the wrong control (R_Brow_04's chain fed by R_Brow_02)
L4, R4 = C("L_Brow_04_ctrl", 8), C("R_Brow_04_ctrl", -8)
chain(L4, T("L_Brow_04_sdk", None, 8), 1.0); chain(R4, T("R_Brow_04_sdk", None, -8), 1.0, feeder=R2)
rows = NW.compare_sides([L4])
print(NW.compare_text([L4]))
check("compare: a node fed by another control says which",
      any("R_Brow_04_sdk is fed by R_Brow_02_ctrl instead" in w for _c, _t, w in rows))

# at rest
pma = cmds.createNode("plusMinusAverage")
cmds.connectAttr(L3 + ".translateX", pma + ".input1D[0]"); cmds.setAttr(pma + ".input1D[1]", 2.0)
cmds.connectAttr(pma + ".output1D", cmds.ls("L_Brow_03_sdk", long=True)[0] + ".translateX")
cmds.setAttr(cmds.ls("L_Brow_03_sdk", long=True)[0] + ".translateX", 2.0)   # what the pma gives at rest (the fake)
rest = NW.at_rest([L3])
print(rest)
check("at rest: an offset left in a network", any("L_Brow_03_sdk.translateX" in p for p, v, r, w in rest))
cmds.setAttr(L2 + ".translateY", 1.0)
check("at rest: a control not at rest is named", any(r is None and p == L2 for p, v, r, w in NW.at_rest([L2])))
cmds.setAttr(L2 + ".translateY", 0.0)

# loops
check("no loops in the brows (constraints don't count against themselves)", NW.loops() == [])
a, b = T("loopA"), T("loopB")
m1 = cmds.createNode("multiplyDivide"); m2 = cmds.createNode("multiplyDivide")
cmds.connectAttr(a + ".translate", m1 + ".input1"); cmds.connectAttr(m1 + ".output", b + ".translate")
cmds.connectAttr(b + ".translate", m2 + ".input1"); cmds.connectAttr(m2 + ".output", a + ".rotate")
found = NW.loops()
check("a loop is found, with its nodes", len(found) == 1 and len(found[0]) == 4)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
