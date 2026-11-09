# 5.3.0: the Cloth section (cloth layer weights / mask, range of motion keys and their removal, the body's joints
# added to an already skinned garment) and the world turn picking World_ctrl, not a stray edgeCurve1
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import cloth, world_turn as WT, utils
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def ctrl(name, parent=None):
    t = cmds.createNode("transform", name=name, parent=parent)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]

# ---- the world control: the one with controls under it, not a lonely curve
wc = ctrl("World_ctrl")
body = ctrl("COG_ctrl", wc)
for n in ("L_Shoulder_FK_ctrl", "R_Shoulder_FK_ctrl", "Spine_01_FK_ctrl", "L_Arm_IK_ctrl", "Neck_ctrl",
          "L_Knee_FK_ctrl", "L_Thumb_01_ctrl"):
    ctrl(n, body)
stray = ctrl("edgeCurve1")
pick = WT.world_control([wc, body, stray] + cmds.listRelatives(body, children=True, fullPath=True))
check("world turn: World_ctrl, not the stray edgeCurve1", pick == wc)
check("a lonely world control still counts when it's all there is", WT.world_control([stray]) == stray)

# ---- cloth layer maths: 3 ribbon joints along X, 2 apart
jp = [(0, 0, 0), (2, 0, 0), (4, 0, 0)]
pts = [(0, 0, 0), (1, 0, 0), (2, 1, 0), (2, 4, 0), (2, 9, 0)]
rows, inner, outer = cloth.layer_weights(pts, jp)
check("spacing found: inner 2, outer 6", abs(inner - 2) < 1e-9 and abs(outer - 6) < 1e-9)
check("on a joint: all its own, mask 1", rows[0][0] == 1.0 and rows[0][1] == {0: 1.0})
check("half way: shared 50 / 50", abs(rows[1][1][0] - 0.5) < 1e-9 and abs(rows[1][1][1] - 0.5) < 1e-9)
check("near: mask 1; every row's weights add up to 1", rows[2][0] == 1.0 and
      all(abs(sum(r[1].values()) - 1.0) < 1e-9 for r in rows))
check("fading between inner and outer", 0.0 < rows[3][0] < 1.0)
check("far away: mask 0 (the body's weights stay)", rows[4][0] == 0.0)

# ---- range of motion
parts = cloth.rom_controls()
names = dict((k, sorted(c.split("|")[-1] for c in v)) for k, v in parts.items())
print(names)
check("ROM controls: shoulders both sides, spine, neck, knee", names.get("shoulders") == [
    "L_Shoulder_FK_ctrl", "R_Shoulder_FK_ctrl"] and "spine" in names and names.get("neck & head") == ["Neck_ctrl"]
      and names.get("knees") == ["L_Knee_FK_ctrl"])
check("ROM leaves out IK, thumbs, the world, the stray curve", not any(
    x in str(names) for x in ("IK", "Thumb", "World", "edgeCurve")))
settings = cmds.createNode("transform", name="L_Arm_settings")
cmds.addAttr(settings, longName="ikfk", attributeType="double")
cmds.setAttr(settings + ".ikfk", 1.0)
cmds.setAttr("L_Knee_FK_ctrl.rotateX", 12.0)
keys, cut, pb = [], [], {"min": 1, "max": 24}
def setKeyframe(plug, time=None, value=None, **k):
    keys.append((plug.split("|")[-1], time, value))
def playbackOptions(**k):
    if k.get("query"):
        return pb["min"] if k.get("minTime") else pb["max"]
    pb["max"] = k.get("maxTime", pb["max"])
with mock.patch.object(cmds, "setKeyframe", side_effect=setKeyframe, create=True), \
        mock.patch.object(cmds, "cutKey", side_effect=lambda p, **k: cut.append(p), create=True), \
        mock.patch.object(cmds, "playbackOptions", side_effect=playbackOptions, create=True), \
        mock.patch.object(utils, "nodes_with_attr", lambda a, *x: [cmds.ls(settings, long=True)[0]]), \
        mock.patch.object(cloth, "_keyable", lambda p: True):
    start, end, plan = cloth.make_rom()
    print(start, end, plan)
    check("ROM: from the playback start, the limbs to FK (ikfk 0)", start == 1 and
          ("L_Arm_settings.ikfk", 1, 0) in keys)
    sh = [k for k in keys if k[0] == "L_Shoulder_FK_ctrl.rotateZ"]
    check("shoulder Z: 0, +70, 0, -70, 0 five frames apart", [v for _p, _t, v in sh][-5:] == [0, 70, 0, -70, 0]
          and sh[-1][1] - sh[-5][1] == 20)
    check("the playback range grows to the end of the ROM", pb["max"] == end and end > 24)
    check("remembered on a gusROM node", cmds.objExists("gusROM"))
    try:
        cloth.make_rom()
        twice = False
    except RuntimeError as e:
        twice = "already" in str(e)
    check("a second ROM is refused while one is there", twice)
    n = cloth.remove_rom()
check("Remove: every keyed channel cut, the node gone", n == len(cut) and n > 10 and not cmds.objExists("gusROM"))
check("Remove: values back as they were (ikfk 1, the knee's 12)", cmds.getAttr(settings + ".ikfk") == 1.0 and
      cmds.getAttr("L_Knee_FK_ctrl.rotateX") == 12.0)

# ---- skin like the body: an already skinned garment keeps its weights, gets the body's joints at 0
added = []
infl = {"bodySkin": ["|a", "|b", "|c"], "shirtSkin": ["|a"]}
with mock.patch.object(cloth, "_skin", lambda m: "bodySkin" if "Body" in m else "shirtSkin"), \
        mock.patch.object(cloth, "_influences", lambda s: infl[s]), \
        mock.patch.object(cmds, "skinCluster", side_effect=lambda s, **k: added.append((s, k.get("addInfluence"),
                                                                                      k.get("weight"))), create=True):
    lines = cloth.skin_like("Hare_Body", ["Shirt"], delta_mush=False)
print(lines)
check("an already skinned garment: weights kept, the 2 missing body joints added at 0",
      added == [("shirtSkin", "|b", 0.0), ("shirtSkin", "|c", 0.0)] and "kept" in lines[0] and "2 body" in lines[0])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
