# 5.5.0: a control's network found (utility nodes / driven-key curves between the drivers and what they move) and
# shown alone in the Node Editor; the networks protected on Publish (unlocked on Unpublish); unit conversions back
# to back folded; the heaviest parts listed; a setup (with its set driven keys) saved and made again on another
# character; the rig map
import os
import shutil
import sys
import tempfile
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.core import network_tools as NT, setups, rig_map, repair
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

KEYS = {}
def keyframe(curve, query=False, floatChange=False, valueChange=False, **k):
    rows = KEYS.get(cmds.ls(curve)[0], [])
    return [r[0] for r in rows] if floatChange else [r[1] for r in rows]
def setKeyframe(curve, float=None, value=None, **k):
    KEYS.setdefault(cmds.ls(curve)[0], []).append([float, value, "spline", "spline", 0.0, 0.0, 1.0, 1.0])
TAN = {}
def keyTangent(curve, query=False, edit=False, index=None, **k):
    name = cmds.ls(curve)[0]
    if query:
        row = KEYS[name][index[0]]
        for i, f in enumerate(("inTangentType", "outTangentType", "inAngle", "outAngle", "inWeight", "outWeight")):
            if k.get(f):
                return [row[2 + i]]
    if edit:
        TAN[(name, index[0])] = k
        row = KEYS[name][index[0]]
        for i, f in enumerate(("inTangentType", "outTangentType", "inAngle", "outAngle", "inWeight", "outWeight")):
            if f in k:
                row[2 + i] = k[f]
cmds.keyframe = keyframe; cmds.setKeyframe = setKeyframe; cmds.keyTangent = keyTangent
_orig_listAttr = cmds.listAttr
def listAttr(node, **k):
    if k.get("settable") and k.get("scalar"):
        n = _n(node)
        return [a for a in n.attrs if a not in ("translate", "rotate", "scale", "visibility")] + list(n.user)
    return _orig_listAttr(node, **k)
cmds.listAttr = listAttr

def character(name):
    top = cmds.createNode("transform", name=name + "_rig")
    c = cmds.createNode("transform", name=name + "_Brow_ctrl", parent=top)
    cmds.createNode("nurbsCurve", name=name + "_Brow_ctrlShape", parent=c)
    sdk = cmds.createNode("transform", name=name + "_Brow_sdk", parent=top)
    t = cmds.createNode("transform", name=name + "_BrowTweak_ctrl", parent=sdk)
    cmds.createNode("nurbsCurve", name=name + "_BrowTweak_ctrlShape", parent=t)
    return c, sdk

# ---- a brow: ty -> driven key curve -> rotateX of the _sdk group; ty x 2 -> md -> uc -> tz
c, sdk = character("Hare")
crv = cmds.createNode("animCurveUA", name="Hare_Brow_ty_to_rx")
cmds.connectAttr(c + ".translateY", crv + ".input")
cmds.connectAttr(crv + ".output", sdk + ".rotateX")
setKeyframe(crv, float=0.0, value=0.0); setKeyframe(crv, float=1.0, value=-30.0)
KEYS["Hare_Brow_ty_to_rx"][1][2:6] = ["linear", "flat", 12.5, 0.0]
cmds.setAttr(crv + ".postInfinity", 1)
md = cmds.createNode("multiplyDivide", name="Hare_Brow_md")
cmds.setAttr(md + ".input2X", 2.0)
cmds.connectAttr(c + ".translateY", md + ".input1X")
cmds.connectAttr(md + ".outputX", sdk + ".translateZ")
other = cmds.createNode("multiplyDivide", name="Other_md")        # not part of it

net = NT.network([c])
names = sorted(n.split("|")[-1] for n in net["nodes"])
check("the brow's network: its driven-key curve and multiplyDivide (not another network)",
      names == ["Hare_Brow_md", "Hare_Brow_ty_to_rx"])
check("...driven by the control, moving the _sdk group", [x.split("|")[-1] for x in net["drivers"]] ==
      ["Hare_Brow_ctrl"] and [x.split("|")[-1] for x in net["driven"]] == ["Hare_Brow_sdk"])
check("from a node in the middle: its own piece (networks meet at the control, not through it)",
      [n.split("|")[-1] for n in NT.network([md])["nodes"]] == ["Hare_Brow_md"])

# ---- Node Editor
calls = []
with mock.patch.object(cmds, "getPanel", side_effect=lambda **k: ["nodeEditorPanel1"], create=True), \
        mock.patch.object(cmds, "scriptedPanel", side_effect=lambda *a, **k: None, create=True), \
        mock.patch.object(cmds, "NodeEditorWindow", side_effect=lambda *a, **k: None, create=True), \
        mock.patch.object(cmds, "nodeEditor", side_effect=lambda ed, **k: calls.append((ed, k)), create=True):
    NT.tidy([c])
added = [k["addNode"].split("|")[-1] for _e, k in calls if "addNode" in k]
check("Node Editor: cleared, then drivers, network, driven added, laid out and framed",
      calls[0][1].get("rootNode") == "" and added[0] == "Hare_Brow_ctrl" and added[-1] == "Hare_Brow_sdk" and
      sorted(added[1:3]) == ["Hare_Brow_md", "Hare_Brow_ty_to_rx"] and
      any(k.get("layout") is True for _e, k in calls) and calls[-1][1].get("frameAll"))
lone = cmds.createNode("transform", name="Lonely_grp")
try:
    NT.tidy([lone])
    check("nothing around: says so", False)
except RuntimeError as e:
    check("a node with no network around it: says so", "no utility nodes" in str(e))

# ---- setups: save the brow, make it on the Fox
tmp = tempfile.mkdtemp()
path, n, outside = setups.save([c], "brow_raise", where=tmp)
check("saved: 2 nodes, connected to the control and the _sdk group", n == 2 and outside == ["Hare_Brow_ctrl",
                                                                                         "Hare_Brow_sdk"])
check("listed in the library", setups.names(tmp) == ["brow_raise"])
fc, fsdk = character("Fox")
pre = setups.preview("brow_raise", "Hare", "Fox", where=tmp)
check("preview: the Fox's control and group found", all(found for _o, _t, found in pre) and
      [t for _o, t, _f in pre] == ["Fox_Brow_ctrl", "Fox_Brow_sdk"])
got = setups.load("brow_raise", "Hare", "Fox", where=tmp)
print(got)
check("made on the Fox: renamed nodes, 4 connections, nothing missing",
      sorted(got["made"]) == ["Fox_Brow_md", "Fox_Brow_ty_to_rx"] and got["connected"] == 4 and not got["missing"])
check("its connections: the Fox's ty drives the curve, the curve the Fox's rotateX",
      cmds.listConnections("Fox_Brow_ty_to_rx.input", source=True, destination=False, plugs=True) ==
      ["Fox_Brow_ctrl.translateY"] and
      cmds.listConnections("Fox_Brow_sdk.rotateX", source=True, destination=False) == ["Fox_Brow_ty_to_rx"])
check("values kept (input2X 2, the curve's post infinity)", cmds.getAttr("Fox_Brow_md.input2X") == 2.0 and
      cmds.getAttr("Fox_Brow_ty_to_rx.postInfinity") == 1)
check("keys and tangents kept", [r[:2] for r in KEYS["Fox_Brow_ty_to_rx"]] == [[0.0, 0.0], [1.0, -30.0]] and
      KEYS["Fox_Brow_ty_to_rx"][1][2:6] == ["linear", "flat", 12.5, 0.0])
check("the Hare is untouched", cmds.listConnections("Hare_Brow_sdk.rotateX", source=True, destination=False) ==
      ["Hare_Brow_ty_to_rx"])
lost = setups.load("brow_raise", "Hare", "Wolf", where=tmp)
check("on a character without those names: made, the missing ones listed", lost["connected"] == 0 and
      lost["missing"] == ["Wolf_Brow_ctrl", "Wolf_Brow_sdk"])
setups.delete("brow_raise", where=tmp)
check("deleted from the library", setups.names(tmp) == [])
shutil.rmtree(tmp)

# ---- unit conversions back to back
a = cmds.createNode("unitConversion", name="unitConversion1")
b = cmds.createNode("unitConversion", name="unitConversion2")
cmds.setAttr(a + ".conversionFactor", 0.017453)
cmds.setAttr(b + ".conversionFactor", 1 / 0.017453)
cmds.connectAttr(c + ".rotateZ", a + ".input")
cmds.connectAttr(a + ".output", b + ".input")
cmds.connectAttr(b + ".output", sdk + ".rotateZ")
half = cmds.createNode("unitConversion", name="unitConversion3")      # alone: needed
cmds.setAttr(half + ".conversionFactor", 0.5)
cmds.connectAttr(c + ".rotateY", half + ".input")
cmds.connectAttr(half + ".output", sdk + ".rotateY")
pairs = NT.double_conversions()
check("found: the pair that cancels out, not the single one", [(p[0], p[1]) for p in pairs] ==
      [("unitConversion1", "unitConversion2")])
check("Repair offers it", [i for i in repair.find() if i.id == "double_conversions"])
check("folded: the source connected straight, the two gone, the single one kept",
      NT.fold_conversions() == 1 and not cmds.objExists(a) and not cmds.objExists(b) and cmds.objExists(half) and
      cmds.listConnections(sdk + ".rotateZ", source=True, destination=False, plugs=True) == [c + ".rotateZ"])

# ---- heaviest parts
for i in range(5):
    cmds.createNode("multiplyDivide", name="L_Cheek_%02d_md" % i)
rows = NT.heaviest()
print(NT.heaviest_text())
check("heaviest: L_Cheek first with its 5 multiplyDivides", rows[0][0] == "L_Cheek" and rows[0][1] == 5 and
      rows[0][2] == {"multiplyDivide": 5})
check("part names: side + first word", NT._part("R_Lip_03_md") == "R_Lip" and NT._part("Cape_jiggle_expr") == "Cape")

# ---- protect / unprotect (Publish option)
from gus_rigtool.builder import publish
check("Publish: 'protect networks' is off unless ticked", publish.DEFAULTS["protect_networks"] is False)
n = NT.protect()
check("protected: every utility node and driven-key curve locked", n >= 6 and
      cmds.lockNode("Hare_Brow_md", query=True, lock=True)[0] and
      cmds.lockNode("Fox_Brow_ty_to_rx", query=True, lock=True)[0])
check("a second time: nothing new", NT.protect() == 0)
back = NT.unprotect()
check("unprotected: unlocked again, the record gone", back == n and
      not cmds.lockNode("Hare_Brow_md", query=True, lock=True)[0] and not cmds.objExists(NT.PROTECT_NODE))

# ---- rig map
rows = rig_map.entries()
labels = [r[2] for r in rows]
txt = rig_map.text()
print(txt)
check("rig map: controls by part, drivers, jiggles", labels[0].startswith("Controls") and
      any(l.startswith("Drivers") for l in labels) and any(l.startswith("Jiggles") for l in labels))
check("a control under a driven group lists that driver", any(r[2] == "driven by Hare_Brow_ctrl" for r in rows))
check("the driver lists what it moves", any(r[2].startswith("Hare_Brow_ctrl -> ") for r in rows))
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
