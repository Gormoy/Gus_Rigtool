# 4.0 face kit: lids split upper / lower (corners out), Blink set driven keys + Blink_Height nodes, mouth controls
# follow the jaw by height, sticky / roll groups, brows as a plain hierarchy, the page builds
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
for name in ("scriptJob", "image", "radioButtonGrp"):
    if not hasattr(cmds, name):
        setattr(cmds, name, _make(name) if name == "radioButtonGrp" else mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool.core import face_kit as FK
import math

def ctrl_at(name, pos, parent):
    off = cmds.createNode("transform", name=name + "_offset", parent=parent)
    cmds.xform(off, worldSpace=True, translation=pos)
    c = cmds.createNode("transform", name=name, parent=off)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(off, long=True)[0], cmds.ls(c, long=True)[0]

# --- eyelid: 8 controls round an eye at (5, 50, 10)
grp = cmds.createNode("transform", name="L_Eyelid_Ribbon_ctrls_grp")
lid = []
for i in range(8):
    a = 2 * math.pi * i / 8.0
    off, c = ctrl_at("L_Eyelid_Ribbon_fol_%02d_ctrl" % i, (5 + 2 * math.cos(a), 50 + 1.2 * math.sin(a), 10), grp)
    lid.append((i, off, c))
FK.controls_of = lambda srf: lid
up, low, corners = FK._split_lids(FK._live(lid), [5, 50, 10])
from gus_rigtool.core import utils as U
print("lids: upper", [U.path(x[2]).split("|")[-1][-11:-5] for x in up], "| lower", len(low), "| corners", len(corners))
eye = cmds.createNode("transform", name="L_Eye_ctrl")
FK._float(eye, "Blink", 0.0, 0.0, 1.0); FK._float(eye, "Blink_Height", 0.5, 0.0, 1.0)
keys = []
cmds.setDrivenKeyframe = lambda plug, currentDriver=None, driverValue=None, value=None: keys.append(
    (plug.split("|")[-1], currentDriver.split("|")[-1], driverValue, round(value, 3)))
n = FK.blink_setup("srf", eye, [5, 50, 10])
print("blink: lid controls", n, "| driven keys", len(keys))
top = [k for k in keys if "fol_02" in k[0]]                       # the top control (straight up)
print("top control keys:", top)
print("groups above it:", cmds.ls("L_Eyelid_Ribbon_fol_02_ctrl", long=True)[0].split("|")[-4:-1])
md = cmds.ls("L_Eyelid_Ribbon_fol_02_ctrl_heightMove")[0]
print("height: moves", [round(cmds.getAttr(md + ".input2" + a), 3) for a in "XYZ"], "x blink x (height - 0.5)")

# --- mouth: 8 controls round the lips, jaw follow by height
mg = cmds.createNode("transform", name="Mouth_ribbon_ctrls_grp")
mouth = []
for i in range(8):
    a = 2 * math.pi * i / 8.0
    off, c = ctrl_at("Mouth_ribbon_fol_%02d_ctrl" % i, (3 * math.cos(a), 45 + 1.0 * math.sin(a), 12), mg)
    mouth.append((i, off, c))
FK.controls_of = lambda srf: mouth
FK.build_ribbon = lambda *a, **k: "Mouth_ribbon"
jaw = cmds.createNode("transform", name="jaw_ctrl")
from gus_rigtool.core import follow
calls = []
follow.add = lambda driver, followers, channels=(), attr_on="", weight=1.0, **k: calls.append(
    (followers[0].split("|")[-1][-11:-5], weight)) or ([], [])
FK.group = lambda head=None: cmds.ls("face_kit_grp", long=True)[0] if cmds.ls("face_kit_grp") else cmds.ls(cmds.createNode("transform", name="face_kit_grp"), long=True)[0]
FK.mouth(None, "jaw_ctrl", style="cartoony", realistic_extras=True)
print("jaw follow:", calls)
mc = [x for x in cmds.ls(type="transform", long=True) if x.endswith("Mouth_ctrl")][0]
print("realistic extras: Mouth_ctrl attrs", [a for a in ("upper_roll", "lower_roll", "sticky") if cmds.attributeQuery(a, node=mc, exists=True)])
print("groups above a lip control:", cmds.ls("Mouth_ribbon_fol_02_ctrl", long=True)[0].split("|")[-4:-1])

# --- brows: controls end up under L_Brow_main_ctrl under Brows_ctrl
bg = cmds.createNode("transform", name="L_Brow_Ribbon_ctrls_grp")
brow = [(i,) + ctrl_at("L_Brow_Ribbon_fol_%02d_ctrl" % i, (2 + i * 2.0, 55 + i * 0.3, 11), bg) for i in range(3)]
FK.controls_of = lambda srf: brow
FK.build_ribbon = lambda *a, **k: "L_Brow_Ribbon"
FK.brows(None, "L", 3, do_mirror=False)
path = cmds.ls(brow[0][2].split("|")[-1], long=True)[0]
print("brow control path:", [p for p in path.split("|") if p][-5:])
print("no constraint on the brow offsets:", not any(cmds.nodeType(k).endswith("Constraint") for o in (b[1].split("|")[-1] for b in brow)
                                                  for k in (cmds.listRelatives(cmds.ls(o, long=True)[0], children=True, fullPath=True) or [])))

# --- page
from gus_rigtool.core import ui
errors = []
ui.report_error = lambda e, where="": errors.append("%s: %s" % (where, e))
_cur[0] = None; cmds.columnLayout("root")
ui._build_tool("face", "t_face_")
print("page builds:", not errors, errors)
