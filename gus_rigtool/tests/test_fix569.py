# 5.6.9: dead twins - ribbon bind joints that follow nothing, on a working bind's spot (a loop folding onto itself:
# the Hare's closed lips), found; taken out of skins where they have no weight, kept where they have some; a
# working joint and a lone follicle joint left alone. No number field with a step as big as its range (Maya's
# 'Step must be less than range' warnings when the tool opened)
import sys, re, glob, os
exec(open("fakemaya.py").read())
from gus_rigtool.core import ribbon
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

ctrl = cmds.createNode("transform", name="L_Mouth_fol_06_ctrl")
def bind(name, pos):
    j = cmds.createNode("joint", name=name)
    cmds.xform(j, worldSpace=True, translation=pos)
    return cmds.ls(j, long=True)[0]
live = bind("L_Mouth_fol_06_bind", (4.06, 77.81, 10.86))
cmds.parentConstraint(ctrl, live)
dead = bind("L_Mouth_fol_22_bind", (4.06, 77.81, 10.86))
alone = bind("L_Mouth_fol_12_bind", (2.0, 79.0, 11.0))            # follows nothing, but nobody on its spot
far = bind("Cape_fol_01_bind", (0, 120, -20))
got = ribbon.dead_twins()
print(got)
check("the dead twin found, with its working twin", [(a.split("|")[-1], b.split("|")[-1]) for a, b in got] ==
      [("L_Mouth_fol_22_bind", "L_Mouth_fol_06_bind")])

removed = []
skins = {"Mouth_skinCluster": 0.0, "skinCluster10": 0.3}           # no weight in the ribbon's skin, some in the body's
with mock.patch.object(cmds, "listConnections", side_effect=lambda *a, **k: list(skins) if k.get("type") ==
                       "skinCluster" else None), \
        mock.patch.object(ribbon, "_weight_in", side_effect=lambda sk, j: skins[sk]), \
        mock.patch.object(cmds, "skinCluster", side_effect=lambda sk, **k: removed.append((sk, k.get("removeInfluence")))
                          if k.get("edit") else [], create=True):
    items = ribbon.dead_twin_skins(got)
    check("safe to take out: only where it has no weight", [(j.split("|")[-1], s) for j, s in items] ==
          [("L_Mouth_fol_22_bind", "Mouth_skinCluster")])
    n = ribbon.fix_dead_twins(items)
check("taken out of the ribbon's skin, kept in the body's (weight 0.3)", n == 1 and
      [(s, j.split("|")[-1]) for s, j in removed] == [("Mouth_skinCluster", "L_Mouth_fol_22_bind")])

# every number field: a step smaller than its range
root = os.path.dirname(os.path.dirname(os.path.abspath("fakemaya.py")))
bad = []
for f in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
    if os.sep + "tests" + os.sep in f:
        continue
    src = open(f).read()
    for m in re.finditer(r"cmds\.(floatField|floatSliderGrp|floatSlider|intField|intSliderGrp|intSlider)\(", src):
        i, depth = m.end(), 1
        while depth and i < len(src):
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        call = src[m.start():i]
        if "edit=True" in call or "query=True" in call or "step=" in call:
            continue
        mn, mx = re.search(r"minValue=([-\w.]+)", call), re.search(r"maxValue=([-\w.]+)", call)
        if mn and not mx:                        # 5.6.15: a minimum alone - Maya's default maximum can be below it
            bad.append("%s:%d (no maximum)" % (os.path.basename(f), src[:m.start()].count("\n") + 1))
            continue
        if mn and mx:
            try:
                small = float(mx.group(1)) - float(mn.group(1)) <= 1.0
            except ValueError:
                small = True                                     # a range from variables: give it a step
            if small:
                bad.append("%s:%d" % (os.path.basename(f), src[:m.start()].count("\n") + 1))
check("every small-range number field has a step (%s)" % (bad or "none missing"), not bad)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
