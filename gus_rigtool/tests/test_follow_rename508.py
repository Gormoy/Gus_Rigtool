# 5.0.8: follows keep working after their controls are renamed (the Hare: Mouth_fol_02_ctrl -> L_Mouth_fol_02_ctrl,
# Tail_00_ctrl -> L_Tail_00_ctrl): the control is found under its follow group, the record is updated (its weight
# plug too when the weight sits on the control), the Follow tab lists every follow even when one control is gone,
# and Check this scene names the control as it is now
import sys
exec(open("fakemaya.py").read())
from unittest import mock
def deleteAttr(node, attribute=None):
    _n(node).user.pop(attribute, None)
cmds.deleteAttr = deleteAttr
from gus_rigtool.core import follow
from gus_rigtool import scene_check
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def ctrl(name, pos):
    off = S.create("transform", name + "_offset"); off.attrs["translate"] = list(pos)
    c = S.create("transform", name, off); S.create("nurbsCurve", name + "Shape", c); return c.name
jaw = ctrl("Jaw_end_ctrl", [0, 150, 2])
a = ctrl("Mouth_fol_02_ctrl", [-3, 148, 8]); b = ctrl("Mouth_fol_14_ctrl", [0, 147, 9])
tail = ctrl("Tail_00_ctrl", [0, 100, -10]); gone = ctrl("Mouth_fol_26_ctrl", [3, 148, 8])
follow.add(jaw, [a, b, gone], ("rotate",), "driver", 0.5)
follow.add(jaw, [tail], ("rotate",), "control", 1.0)          # weight on the control itself
before = sorted(r[0] for r in follow.all_follows())
check("before: 4 follows by their names", before == ["Mouth_fol_02_ctrl", "Mouth_fol_14_ctrl", "Mouth_fol_26_ctrl",
                                                     "Tail_00_ctrl"])
cmds.rename("Mouth_fol_02_ctrl", "L_Mouth_fol_02_ctrl")
cmds.rename("Tail_00_ctrl", "L_Tail_00_ctrl")
cmds.delete("Mouth_fol_26_ctrl")
rows = follow.all_follows()
names = sorted(r[0] for r in rows)
check("renamed controls found under their follow group", "L_Mouth_fol_02_ctrl" in names and "L_Tail_00_ctrl" in names)
check("the untouched one is as it was", "Mouth_fol_14_ctrl" in names)
check("a gone control is still listed, saying so", "(control not found, was Mouth_fol_26_ctrl)" in names)
tail_row = [r for r in rows if r[0] == "L_Tail_00_ctrl"][0]
check("weight on the renamed control: its plug follows the new name", tail_row[2] == "L_Tail_00_ctrl.follow"
      and cmds.getAttr(tail_row[2]) == 1.0)
g = follow.follow_group_of(cmds.ls("L_Mouth_fol_02_ctrl", long=True)[0])
check("the record is updated to the new name", cmds.getAttr(g + "." + follow.META).split("|")[5] == "L_Mouth_fol_02_ctrl")

# the Follow tab: the list is filled (one follow it can't read doesn't empty it)
from gus_rigtool.tools import follow_tab
got = {}
def tsl(name, **k):
    if k.get("exists"):
        return True
    if "append" in k:
        got["rows"] = k["append"]
with mock.patch.object(cmds, "textScrollList", side_effect=tsl, create=True), \
        mock.patch.object(follow_tab.ui, "refresh_light", lambda *a, **k: None):
    follow_tab.refresh()
check("Follow tab lists all 4", len(got.get("rows", [])) == 4 and any(r.startswith("L_Mouth_fol_02_ctrl") for r in
                                                                      got["rows"]))

# Check this scene: the name as it is now
class Rep(object):
    def __init__(self):
        self.rows = []
    def start(self, t):
        pass
    def add(self, lv, what, detail=""):
        self.rows.append((lv, what, detail))
cmds.rename("L_Mouth_fol_02_ctrl", "Lf_Mouth_fol_02_ctrl")       # renamed again, not listed since
r = Rep(); scene_check.check_follows(r)
text = "\n".join("%s | %s | %s" % x for x in r.rows)
print(text)
check("Check this scene: renamed shown with its old name", "Lf_Mouth_fol_02_ctrl (renamed from L_Mouth_fol_02_ctrl)" in text)
check("Check this scene: a gone control is a warning", any(lv == scene_check.WARN and "control is gone" in w
                                                           for lv, w, d in r.rows))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
