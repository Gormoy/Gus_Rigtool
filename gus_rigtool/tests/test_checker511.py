# 5.0.11: from the Hare - (1) belt pieces inside one constrained group follow the rig (no 'don't follow' warning);
# (2) 'Fix all safe' no longer renames: the side check isn't in it, and a tongue / tail hanging a little off the
# centre isn't 'on L / R' (it was renamed R_Tongue..., R_Tail...)
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.tools import checker
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def mesh(name, parent):
    t = cmds.createNode("transform", name=name, parent=parent)
    cmds.createNode("mesh", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
geo = cmds.ls(cmds.createNode("transform", name="geo_grp"), long=True)[0]
belt_grp = cmds.createNode("transform", name="Belt_grp", parent=geo)
hips = cmds.createNode("joint", name="Hips_jnt")
cmds.parentConstraint(hips, belt_grp, maintainOffset=True)
pieces = [mesh(n, belt_grp) for n in ("Belt", "Belt_Ring", "Belt_piece")]
loose = mesh("Hat", geo)
with mock.patch.object(checker, "_group", lambda k: geo), mock.patch.object(checker, "_deformed", lambda s: False):
    got = [n.split("|")[-1] for n in checker.find_geo_no_skin(None)]
check("belt pieces in a constrained group follow the rig", not any(p.split("|")[-1] in got for p in pieces))
check("a loose mesh is still listed", got == ["Hat"])

def bbox(nodes):                                     # the shape sits on its transform
    n = nodes[0] if isinstance(nodes, list) else nodes
    p = cmds.xform(cmds.listRelatives(n, parent=True, fullPath=True)[0], query=True, worldSpace=True, translation=True)
    return [p[0], p[1], p[2], p[0], p[1], p[2]]
cmds.exactWorldBoundingBox = bbox
def ctrl(name, x, y):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    cmds.xform(t, worldSpace=True, translation=[x, y, 0])
    return cmds.ls(t, long=True)[0]
things = [ctrl("Root_ctrl", 0, 0), ctrl("Head_ctrl", 0, 100), ctrl("Tongue_end_IK_ctrl", 0.6, 80),
          ctrl("Tail_01_ctrl", -1.2, 45), ctrl("arm_ctrl", 15, 70)]
with mock.patch.object(checker, "_named_things", lambda scope: things):
    side = [n.split("|")[-1] for n in checker.find_naming_side(None)]
check("tongue (0.6) and tail (1.2) on a 100 tall rig: centre, not listed", "Tongue_end_IK_ctrl" not in side and
      "Tail_01_ctrl" not in side)
check("a control clearly on one side is still listed", side == ["arm_ctrl"])
check("'Fix all safe' leaves the side renaming out", "naming_side" in checker.NOT_IN_FIX_ALL)
ran = []
fake_checks = [("naming_side", "Naming", "x", "INFO", None, lambda nodes: ran.append("naming") or 1, True),
               ("other", "Scene", "y", "INFO", None, lambda nodes: ran.append("other") or 1, True)]
with mock.patch.object(checker, "CHECKS", fake_checks), mock.patch.object(checker, "_current", lambda cid: ["n"]), \
        mock.patch.object(cmds, "evalDeferred", lambda *a, **k: None, create=True):
    checker.fix_all()
check("fix_all runs the others, not the renaming", ran == ["other"])
# 5.1.1: a centred settings control drawn off to one side stays centre; the Fix asks first
sett = ctrl("Tongue_settings_ctrl", 0, 80)
cmds.exactWorldBoundingBox = lambda nodes: [7, 79, 0, 9, 81, 0]          # its shape sits at x 8
with mock.patch.object(checker, "_named_things", lambda scope: things + [sett]):
    side = [n.split("|")[-1] for n in checker.find_naming_side(None)]
check("a centred control drawn to the side: not listed", "Tongue_settings_ctrl" not in side)
arm = [t for t in things if t.endswith("arm_ctrl")]
with mock.patch.object(cmds, "confirmDialog", lambda **k: "Cancel", create=True):
    n0 = checker.fix_naming_side(arm)
check("Fix: cancelled in the list, nothing renamed", n0 == 0 and cmds.objExists("arm_ctrl"))
with mock.patch.object(cmds, "confirmDialog", lambda **k: "Rename", create=True):
    n1 = checker.fix_naming_side(arm)
check("Fix: accepted, renamed", n1 == 1 and not cmds.objExists("arm_ctrl"))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
