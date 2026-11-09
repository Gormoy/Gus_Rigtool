# 4.4.6: the controls of any rig are found without a suffix: names (any case), controls sets, controller tags,
# hand-made curves you can key; not hidden-for-good / templated / locked / driven curves. Left / right tokens too.
import os, sys
exec(open("fakemaya.py").read())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A, pickmodel as PM
A.profile = lambda ns=None: {}
OV = {}
def optionVar(**k):
    if "exists" in k: return k["exists"] in OV
    if "query" in k: return OV[k["query"]]
    if "stringValue" in k: OV[k["stringValue"][0]] = k["stringValue"][1]
    if "remove" in k: OV.pop(k["remove"], None)
cmds.optionVar = optionVar
def bbox(nodes):
    n = nodes[0] if isinstance(nodes, list) else nodes
    t = cmds.listRelatives(n, parent=True, fullPath=True)
    p = world(_n(t[0] if t else n))[12:15]
    return [p[0] - 1, p[1] - 1, p[2] - 1, p[0] + 1, p[1] + 1, p[2] + 1]
cmds.exactWorldBoundingBox = bbox
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def curve(name, parent=None):
    t = cmds.createNode("transform", name=name, parent=parent)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
rig = cmds.createNode("transform", name="handmade_rig")
made = {}
# hand-made: no suffix at all
for nm in ("hips", "chest", "head", "Lf_arm", "Rt_arm", "Lf_leg", "Rt_leg"):
    made[nm] = curve(nm, rig)
# other naming styles
made["jaw_CTL"] = curve("jaw_CTL", rig)                  # upper case
made["tail_con"] = curve("tail_con", rig)
made["gus_ctrl"] = curve("spine_ctrl", rig)              # a script-made one, in the same rig
# hidden for good: an IK spline curve under a hidden 'no touch' group
dnt = cmds.createNode("transform", name="noTouch", parent=rig); cmds.setAttr(dnt + ".visibility", 0)
made["spline"] = curve("spine_ikCurve", dnt)
# hidden by an IK/FK switch (visibility driven): still a control
sw = cmds.createNode("transform", name="fk_vis_grp", parent=rig)
rev = cmds.createNode("reverse", name="ikfk_rev")
cmds.connectAttr(rev + ".outputX", sw + ".visibility")
cmds.setAttr(sw + ".visibility", 0)
made["Lf_hand_fk"] = curve("Lf_hand_fk", sw)
made["Rt_hand_fk"] = curve("Rt_hand_fk", sw)
# templated, all locked, all driven by a constraint: not controls
made["tmpl"] = curve("guideLine", rig); cmds.setAttr(made["tmpl"] + ".template", 1)
made["locked"] = curve("label_curve", rig)
for a in [x + y for x in ("translate", "rotate", "scale") for y in "XYZ"]:
    cmds.setAttr(made["locked"] + "." + a, lock=True)
made["driven"] = curve("follow_curve", rig)
pb = cmds.createNode("multiplyDivide", name="drv")
for a in [x + y for x in ("translate", "rotate", "scale") for y in "XYZ"]:
    cmds.connectAttr(pb + ".outputX", made["driven"] + "." + a)
# a locked curve with a keyable attribute of its own (a settings control): counts
made["settings"] = curve("settings", rig)
for a in [x + y for x in ("translate", "rotate", "scale") for y in "XYZ"]:
    cmds.setAttr(made["settings"] + "." + a, lock=True)
cmds.addAttr(made["settings"], longName="ikFk", attributeType="double", keyable=True)
# in a controls set, all locked (an Advanced Skeleton style set): counts
made["inset"] = curve("FKShoulder_R", rig)
for a in [x + y for x in ("translate", "rotate", "scale") for y in "XYZ"]:
    cmds.setAttr(made["inset"] + "." + a, lock=True)
cmds.sets(made["inset"], name="ControlSet")

found = A.auto_controls("")
short = lambda xs: sorted(x.split("|")[-1] for x in xs)
want = ["Lf_arm", "Lf_hand_fk", "Lf_leg", "Rt_arm", "Rt_hand_fk", "Rt_leg", "chest", "head", "hips", "jaw_CTL",
        "spine_ctrl", "tail_con", "settings", "FKShoulder_R"]
check("every animatable curve found, any naming", short(found) == sorted(want))
check("not: hidden-for-good spline, templated, locked, driven",
      not {"spine_ikCurve", "guideLine", "label_curve", "follow_curve"} & set(short(found)))
check("controls hidden by an IK/FK switch still count", "Lf_hand_fk" in short(found))
check("is_control agrees (the rest of Gus Animtool sees the same)",
      sorted(short([c for c in A.character_controls("")])) == sorted(want))
print("   ", A.found_text(""))
check("how they were found is said", "found automatically" in A.found_text("") and "channels" in A.found_text(""))
# left / right tokens found from the names (Lf_ / Rt_ here)
A._pairs_cache.clear()
check("left / right tokens found: Lf_ / Rt_", ("Lf_", "Rt_") in A.auto_pairs(""))
check("twins by name", A.mirror_name("Lf_arm") == "Rt_arm")
# your own suffix wins: only those names
cmds.optionVar(stringValue=(A.P + "suffix", "_CTL"))
check("your own suffix: only those names", short(A.character_controls("")) == ["jaw_CTL"])
cmds.optionVar(remove=A.P + "suffix")
# a picker made earlier misses controls made later: they go on their own page
A._auto_cache.clear()
picker = {"version": PM.VERSION, "pages": [{"name": "Body", "width": 400, "height": 400, "bg": "", "items": []}]}
PM.add_items(picker["pages"][0], [made[n] for n in ("hips", "chest", "head")])
miss = PM.missing(picker, "")
check("missing controls listed", len(miss) == len(want) - 3)
before = [dict(i) for i in picker["pages"][0]["items"]]
n = PM.add_missing(picker, "")
check("added on a page 'New controls', your page untouched", n == len(want) - 3 and picker["pages"][-1]["name"] ==
      PM.NEW_PAGE and picker["pages"][0]["items"] == before)
check("nothing missing after", PM.missing(picker, "") == [])
print("ALL OK" if all(ok) else "SOME FAILED")
