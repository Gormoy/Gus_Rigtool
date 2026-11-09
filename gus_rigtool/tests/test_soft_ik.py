# Soft IK: the node network gives d_soft = a + s(1 - e^-((d-a)/s)) past a = L - s; plain IK before; soft 0 = off
exec(open("fakemaya.py").read())
import math
from gus_rigtool.builder import build as bld, guides, modules
bld.biped(180)
for g in guides.module_groups():
    i = guides.read(g)
    if i["id"] == "L:arm":
        s = modules.MODULES["arm"].complete(i["settings"]); s["options"]["soft_ik"] = True
        guides.save_settings(g, s); guides.update(g, modules.MODULES["arm"], s, 180)
bld.build_all(180)
print("soft_ik slider:", cmds.attributeQuery("soft_ik", node="L_wrist_settings_ctrl", exists=True),
      "| handle point-constrained:", any(n.type == "pointConstraint" for n in S.get("L_wrist_ikHandle").children))
# evaluate the network: feed a distance, read the ratio
inputs = {}
def val(node, attr):
    if (node.name, attr) in inputs:
        return inputs[(node.name, attr)]
    for s_, sa, d, da in S.conns:
        if d is node and da == attr:
            return out(s_, sa)
    v = node.attrs.get(attr, node.user.get(attr, 0.0))
    return v[0] if isinstance(v, list) else v
def out(node, attr):
    if (node.name, attr) in inputs:
        return inputs[(node.name, attr)]
    t = node.type
    if t == "multiplyDivide":
        a, b, op = val(node, "input1X"), val(node, "input2X"), node.attrs.get("operation", 1)
        return a * b if op == 1 else (a / b if op == 2 else a ** b)
    if t == "plusMinusAverage":
        a, b, op = val(node, "input1D[0]"), val(node, "input1D[1]"), node.attrs.get("operation", 1)
        return a + b if op == 1 else a - b
    if t == "condition":
        f, s2 = val(node, "firstTerm"), val(node, "secondTerm")
        return val(node, "colorIfTrueR") if f > s2 else val(node, "colorIfFalseR")
    if t == "blendTwoAttr":
        bl = val(node, "attributesBlender"); return val(node, "input[0]") * (1 - bl) + val(node, "input[1]") * bl
    if t == "distanceBetween":
        return val(node, "distance")
    return val(node, attr)
dist = [n for n in S.nodes if n.type == "distanceBetween" and "soft" in n.name][0]
ratio = [n for n in S.nodes if n.name.endswith("_softRatio")][0]
L = sum(abs(S.get(j).attrs["translate"][0]) for j in ("L_radius_IK_jnt", "L_wrist_IK_jnt"))
for soft in (0.0, 0.4):
    inputs[("L_wrist_settings_ctrl", "soft_ik")] = soft
    row = []
    for frac in (0.8, 0.95, 1.0, 1.1, 1.5):
        d = L * frac
        inputs[(dist.name, "distance")] = d
        r = out(ratio, "outputX")
        s = soft * L * 0.25; a = L - s
        want = d if (s < 1e-4 or d <= a) else a + s * (1 - math.exp(-(d - a) / s))
        row.append("%.2fL -> %.3fL (%s)" % (frac, r * d / L, "ok" if abs(r * d - want) < 1e-6 else "WRONG"))
    print("soft %.1f:" % soft, " | ".join(row))
