# 5.6.20: Save takes the face as you see it (an expression that's on goes in too) - or, unticked, only what the
# controls add; a save that stops is taken back by hand (controls as posed, no new sliders, no new layers, the old
# pose of that name whole); replacing builds the new one first then swaps; a layer that lost its sums is healed;
# controls moved without a face name are found
import sys, math
exec(open("fakemaya.py").read())
from gus_rigtool.core import face_poses as FP, group_ctrls as GC
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def mk(name, parent=None, pos=(0, 0, 0)):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent) if parent else \
        cmds.createNode("transform", name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=pos)
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]
head = mk("Head_ctrl", None, (0, 150, 0))
L = mk("L_Mouth_fol_06_ctrl", head, (4, 150, 10)); M = mk("Mouth_fol_33_ctrl", head, (0, 149, 11))
holder = mk("Mouth_main_ctrl", head, (0, 150, 14))
other = mk("Snout_wiggle", head, (0, 152, 12))               # no face word in its name
CT = [L, M]
P = mock.patch.object(FP, "pose_controls", side_effect=lambda h=None: [GC._long(c.split("|")[-1]) for c in CT])

# Angry: L up 1
with P:
    cmds.setAttr(L + ".translateY", 1)
    FP.save_pose("Mouth_main_ctrl", "Angry", False)
check("Angry saved", "Angry" in FP.read(GC._long("Mouth_main_ctrl")))

# the fake doesn't evaluate connections: 'Angry on' = what Maya would show - the layer carrying it
lay = GC.layer_of(GC._long("L_Mouth_fol_06_ctrl"))
cmds.disconnectAttr(GC._sum_of(lay, "translate") + ".output3D", lay + ".translate")
cmds.setAttr(lay + ".translateY", 1)                         # Angry at 1, as Maya would draw it
cmds.setAttr(GC._long("Mouth_fol_33_ctrl") + ".translateY", 0.5)
with P, mock.patch.object(FP, "sliders_on", return_value={"Angry": 1.0}):
    seen = FP._measure([GC._long("L_Mouth_fol_06_ctrl"), GC._long("Mouth_fol_33_ctrl")])
print(round(seen[0][GC._long("L_Mouth_fol_06_ctrl")][13], 3))
check("as you see it: L up 1 (Angry) measured before anything goes off", abs(seen[0][GC._long("L_Mouth_fol_06_ctrl")][13] - 151) < 1e-6)
cmds.setAttr(lay + ".translateY", 0)
cmds.connectAttr(GC._sum_of(lay, "translate") if GC._sum_of(lay, "translate") else "x", lay + ".translate") \
    if False else None

# a stopped save: taken back by hand
cmds.setAttr(GC._long("Mouth_fol_33_ctrl") + ".translateY", 0.5)
real = GC._add_layer
calls = []
def boom(node, carries):
    calls.append(node)
    raise RuntimeError("stopped on purpose")
before_attrs = set(cmds.listAttr(GC._long("Mouth_main_ctrl"), userDefined=True))
with P, mock.patch.object(GC, "_add_layer", side_effect=boom):
    try:
        FP.save_pose("Mouth_main_ctrl", "Angry", False, include_on=False)
        msg = ""
    except RuntimeError as e:
        msg = str(e)
print(msg)
d = FP.read(GC._long("Mouth_main_ctrl"))
check("stopped: nothing changed - the face as posed, no new slider, the old Angry whole",
      "nothing changed" in msg and cmds.getAttr(GC._long("Mouth_fol_33_ctrl") + ".translateY") == 0.5 and
      set(cmds.listAttr(GC._long("Mouth_main_ctrl"), userDefined=True)) == before_attrs and
      list(d) == ["Angry"] and d["Angry"]["attrs"] == ["Angry"] and
      "L_Mouth_fol_06_ctrl" in d["Angry"]["ctrls"])

# replacing: built first, then swapped
with P:
    got = FP.save_pose("Mouth_main_ctrl", "Angry", False, include_on=False)
d = FP.read(GC._long("Mouth_main_ctrl"))
check("replaced: Angry is now the middle up 0.5, its slider called Angry, no Angry_new left",
      got["attrs"] == ["Angry"] and list(d) == ["Angry"] and list(d["Angry"]["ctrls"]) == ["Mouth_fol_33_ctrl"] and
      not cmds.attributeQuery("Angry_new", node=GC._long("Mouth_main_ctrl"), exists=True))

# moved without a face name
cmds.setAttr(GC._long("Snout_wiggle") + ".rotateX", 12)
with mock.patch("gus_rigtool.core.on_top.controls", return_value=[GC._long(n) for n in
                ("L_Mouth_fol_06_ctrl", "Mouth_fol_33_ctrl", "Snout_wiggle", "Mouth_main_ctrl")]), P:
    out = [c.split("|")[-1] for c in FP.moved_outside("Mouth_main_ctrl")]
check("moved, no face name: found (Snout_wiggle)", out == ["Snout_wiggle"])

# a layer that lost its sums
lay = GC.layer_of(GC._long("Mouth_fol_33_ctrl"))
cmds.delete(GC._sum_of(lay, "translate"))
fixed = GC.repair_layers()
check("a layer without its sum: healed (then gone - nothing fed it any more), no broken layer left",
      fixed["healed"] == ["Mouth_fol_33_ctrl_groups"] and
      all(GC._sum_of(x, "translate") and GC._sum_of(x, "rotate") for x in
          cmds.ls("*." + GC.LAYER, objectsOnly=True, long=True) or []))
lay2 = GC._add_layer(GC._long("L_Mouth_fol_06_ctrl"), GC._long("L_Mouth_fol_06_ctrl"))[0]
if True:
    cmds.delete(GC._sum_of(lay2, "rotate"))
    got = GC._add_layer(GC._long("L_Mouth_fol_06_ctrl"), GC._long("L_Mouth_fol_06_ctrl"))
    check("saving onto a broken layer: it's healed, not refused", got[0] == lay2 and got[1] and got[2])
print("%d/%d passed" % (sum(ok), len(ok)))
