# 5.0.5: Check this scene only flags real things (from the Hare's report): ribbon (NURBS) skins don't crash the
# influence count, Post-normalised skins aren't 'weights don't add up to 1' (and Repair doesn't offer to
# normalise them), ribbon driver joints aren't checked for labels, unlabelled joints aren't also 'wrong side',
# a twin name used by two joints says so, and duplicates inside a referenced file are a WARN, not a FAIL
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool import scene_check
from gus_rigtool.core import repair, joint_labels
from gus_rigtool.tools import checker
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

class Rep(object):
    def __init__(self):
        self.rows = []
    def start(self, title):
        pass
    def add(self, level, what, detail=""):
        self.rows.append((level, what, detail))
    def text(self):
        return "\n".join("%s | %s | %s" % r for r in self.rows)

def mesh(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("mesh", name=name + "Shape", parent=t)
    return name + "Shape"
def surface(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsSurface", name=name + "Shape", parent=t)
    return name + "Shape"
def joint(name, x, side=0, typ=0, other=""):
    j = cmds.createNode("joint", name=name)
    cmds.setAttr(j + ".translateX", x)
    cmds.setAttr(j + ".side", side)
    cmds.setAttr(j + ".type", typ)
    cmds.addAttr(j, longName="otherType", dataType="string") if not cmds.attributeQuery(
        "otherType", node=j, exists=True) else None
    cmds.setAttr(j + ".otherType", other, type="string")
    return cmds.ls(j, long=True)[0]

body = mesh("body_geo")
rib = surface("brow_ribbon")
lb = joint("L_Brow_02_jnt", 2.0, 1, 18, "Brow_02")
rb = joint("R_Brow_02_jnt", -2.0, 2, 18, "Brow_02")
grp = cmds.createNode("transform", name="extra_grp")
rb2 = cmds.createNode("joint", name="R_Brow_02_jnt", parent=grp)        # the same twin name, twice
_n(rb2).name = "R_Brow_02_jnt"                                           # (the fake makes names unique)
cmds.setAttr("|extra_grp|R_Brow_02_jnt.translateX", -2.0)
loose = joint("cheek_jnt", 3.0)                                          # no label at all, off centre
drv = joint("Facial_ribbon_drv_jnt", 5.0)                                # only drives the ribbon surface
SKINS = {"skinBody": ([body], [lb, rb, loose]), "skinRibbon": ([rib], [drv])}
for s in SKINS:
    cmds.createNode("skinCluster", name=s)
    cmds.addAttr(s, longName="maxInfluences", attributeType="long")
    cmds.addAttr(s, longName="maintainMaxInfluences", attributeType="bool")
    cmds.addAttr(s, longName="normalizeWeights", attributeType="long")
    cmds.setAttr(s + ".maxInfluences", 4)
cmds.setAttr("skinBody.normalizeWeights", 2)                            # Post
def skinCluster(skin, query=False, geometry=False, influence=False, **k):
    g, i = SKINS[skin.split("|")[-1]]
    return list(g) if geometry else list(i)
cmds.skinCluster = skinCluster
WEIGHTS = lambda skin: (3, [1.0, 0.7, 1.0], [1.0, 0.7, 1.0])            # vertex 1 adds up to 0.7

# 1. ribbon skins: the influence count skips them (it used to crash on polyEvaluate of a surface)
asked = []
cmds.polyEvaluate = lambda shape, **k: asked.append(shape) or 0
try:
    checker.find_skin_influences(None)
except Exception:
    pass                                          # the fake has no skin weights API: only what's asked matters
check("vertices over the influence limit: the ribbon surface is skipped", not any("ribbon" in a for a in asked))

# 2. Post skins: no 'don't add up to 1' warning, and Repair leaves them alone
with mock.patch.object(scene_check, "_skin_weights", side_effect=WEIGHTS):
    r = Rep(); scene_check.check_skin(r)
    fix = repair._skin_sums()
check("Post skin: no 'don't add up to 1' warning", not any("add up to 1" in w for lv, w, d in r.rows
                                                           if lv == scene_check.WARN))
check("Post skin: noted as fine in its facts", "Post normalises" in r.text())
check("Repair: no 'normalise' offered for a Post skin", fix is None)
cmds.setAttr("skinBody.normalizeWeights", 1)
with mock.patch.object(scene_check, "_skin_weights", side_effect=WEIGHTS):
    r = Rep(); scene_check.check_skin(r)
    fix = repair._skin_sums()
check("Interactive skin: still warned, and Repair offers it", "1 vertices whose weights" in r.text() and fix)

# 3. labels: only joints skinning a mesh; unlabelled ones are not 'wrong side' too; a twin name used twice
scene_check._height = lambda: 100.0
r = Rep(); scene_check.check_labels(r)
t = r.text()
print(t)
check("ribbon driver joints aren't label-checked", "Facial_ribbon_drv_jnt" not in t)
check("an unlabelled joint is listed once (no label), not as 'wrong side'",
      "cheek_jnt" in t and "wrong side" not in t)
check("a twin name used twice says so", "2 joints named R_Brow_02_jnt" in t and "no right twin" not in t)
check("joint_labels.twin_count", joint_labels.twin_count(lb) == 2 and joint_labels.twin_count(loose) == 0)

# 4. duplicate names: inside a referenced file = WARN check, the scene's own = FAIL check
a = cmds.createNode("transform", name="dup_a", parent=grp)
b = cmds.createNode("transform", name="dup_a")
ref1 = cmds.createNode("transform", name="hare_eye", parent=grp)
ref2 = cmds.createNode("transform", name="hare_eye")
_n(b).name = "dup_a"; _n(ref2).name = "hare_eye"; a, b = "|extra_grp|dup_a", "|dup_a"
ref1, ref2 = "|extra_grp|hare_eye", "|hare_eye"
REF = set(cmds.ls([ref1, ref2], long=True))
with mock.patch.object(cmds, "referenceQuery", side_effect=lambda n, **k: cmds.ls(n, long=True)[0] in REF):
    own = [n.split("|")[-1] for n in checker.find_dup_names(None)]
    inref = [n.split("|")[-1] for n in checker.find_dup_names_ref(None)]
check("duplicates of the scene's own: FAIL check", "dup_a" in own and "hare_eye" not in own)
check("duplicates inside a referenced file: their own WARN check", inref and set(inref) == {"hare_eye"})
check("the new check is listed as WARN", [c[3] for c in checker.CHECKS if c[0] == "dup_names_ref"] == ["WARN"])

print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
