# 5.6.39: real-Maya test f reads what the mirror wrote and keys the right control; a new check on your scene scales
# each left control that drives a joint (the pupils) and its right twin, and says when the two sides differ
import os, sys
exec(open("fakemaya.py").read())
HERE = os.path.join(os.getcwd(), "..", "realmaya")
sys.path.insert(0, HERE)
import maya_cases as MC
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# the comparison, with the Hare's numbers
check("both pupils moving the same: nothing to say", MC.scale_pair((53, 0.06), (52, 0.06)) is None)
check("the Hare before the fix (62 stray vertices barely moving, the right pupil 0.06): said",
      "don't match" in (MC.scale_pair((62, 0.004), (52, 0.06)) or ""))
check("one side moving nothing: said", "moves nothing" in (MC.scale_pair((0, 0.0), (52, 0.06)) or ""))
check("neither side moves (nothing skinned to them): nothing to compare", MC.scale_pair((0, 0.0), (0, 0.0)) is None)
check("a small difference (under a quarter) is fine", MC.scale_pair((53, 0.055), (52, 0.06)) is None)

src = open(os.path.join(HERE, "maya_cases.py")).read()
f = src[src.index("def ikfk_mirror"):src.index("def rig_selftest")]
check("test f: the values are read right after the mirror, then the right control is keyed, then measured",
      f.index('"mirror pose L>R"') < f.index("values right after the mirror") < f.index("setKeyframe(twin[0]")
      < f.index("gap1 = mirror_gap()"))
h = src[src.index("def hare"):]
check("your scene: the left / right scale check runs after the eye dry run, before closing without saving",
      h.index("eye_dry_run, rep") < h.index("scale_twins, rep") < h.index("closed without saving"))
check("the scaled controls are put back", "cmds.setAttr(ctrl + \".scaleX\", was)" in src)
print("%d/%d passed" % (sum(ok), len(ok)))
