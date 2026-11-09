# Gus Anim 1.2: picker layout (front / side / face from where the controls are), clicks, pose library
# (save / load, blend, one side, mirrored, selection only), and the two windows build
import os, sys, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.setKeyframe = mock.MagicMock(); cmds.currentTime = mock.MagicMock(return_value=1.0)
cmds.scriptJob = mock.MagicMock(return_value=1); cmds.playblast = mock.MagicMock()
cmds.getModifiers = mock.MagicMock(return_value=0); cmds.internalVar = mock.MagicMock(return_value="/tmp")
cmds.colorIndex = mock.MagicMock(return_value=[1, 1, 0])
cmds.iconTextButton = mock.MagicMock(side_effect=lambda *a, **k: UI.setdefault("itb%d" % len(UI), dict(k, kind="iconTextButton",
                                     parent=k.get("parent"))) and "itb%d" % (len(UI) - 1))
def bbox(nodes):
    n = nodes[0] if isinstance(nodes, list) else nodes
    t = cmds.listRelatives(n, parent=True, fullPath=True)
    p = world(_n(t[0] if t else n))[12:15]
    return [p[0] - 1, p[1] - 1, p[2] - 1, p[0] + 1, p[1] + 1, p[2] + 1]
cmds.exactWorldBoundingBox = bbox
import gus_anim as ga
LIB = tempfile.mkdtemp()
_opts = {"key_switch": 0, "library": LIB}
ga.opt = lambda key, default: _opts.get(key, default)
ga.set_opt = lambda key, value: _opts.__setitem__(key, value)
from gus_rigtool.builder import build as bld
bld.biped(180); bld.build_all(180)
lay = ga.picker_layout("")
print("tabs:", {k: len(v) for k, v in lay.items()})
body = {ga.short(b["node"]): b for b in lay["Body"]}
l, r = body["L_wrist_IK_ctrl"], body["R_wrist_IK_ctrl"]
print("front: L hand on the right:", l["x"] > r["x"], "| head above the hips:", body["head_ctrl"]["y"] < body["hips_ctrl"]["y"])
print("inside the canvas:", all(0 <= b["x"] <= ga.PICK_W - b["w"] and 0 <= b["y"] <= ga.PICK_H - b["h"] for v in lay.values() for b in v))
over = [(a["node"], b["node"]) for v in lay.values() for i, a in enumerate(v) for b in v[i + 1:]
        if a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]]
print("overlapping buttons:", len(over))
print("face tab has lips / eyes:", sorted(ga.short(b["node"]) for b in lay["Face"])[:4])
ga.picker_click(cmds.ls("L_wrist_IK_ctrl", long=True)[0]); print("click:", [ga.short(x) for x in cmds.ls(sl=True)])
cmds.getModifiers.return_value = 1
_sel = cmds.select
cmds.select = lambda *a, **k: (S.sel.append(_n(a[0])) if k.get("toggle") else _sel(*a, **k))
ga.picker_click(cmds.ls("R_wrist_IK_ctrl", long=True)[0]); print("shift-click adds:", [ga.short(x) for x in cmds.ls(sl=True)])
cmds.select = _sel
# windows build (fake UI)
cmds.workspaceControl = mock.MagicMock(return_value=False)
_cur[0] = None; cmds.columnLayout(ga.PICKER); ga._build_picker()
print("picker buttons:", len(ga._pick["buttons"]))
_cur[0] = None; cmds.columnLayout(ga.LIBRARY); ga._build_library()
# pose library
c = cmds.ls("L_wrist_IK_ctrl", long=True)[0]; rc = cmds.ls("R_wrist_IK_ctrl", long=True)[0]
cmds.setAttr(c + ".tx", 4.0); cmds.setAttr(c + ".ty", 2.0)
name, n = ga.save_pose("wave hand!", [c], "")
print("saved:", name, n, "| files:", sorted(os.listdir(os.path.join(LIB, "rig"))), "| list:", ga.pose_files(""))
pose = ga.load_pose(name, "")
cmds.setAttr(c + ".tx", 0.0); cmds.setAttr(c + ".ty", 0.0)
ga.apply_pose(pose, "", amount=0.5); print("half:", cmds.getAttr(c + ".tx"), cmds.getAttr(c + ".ty"))
ga.apply_pose(pose, "", amount=1.0, side="R"); print("right only leaves the left:", cmds.getAttr(c + ".tx"))
cmds.setAttr(c + ".tx", 0.0); cmds.setAttr(c + ".ty", 0.0)
print("mirrored:", ga.apply_pose(pose, "", mirrored=True), "| R:", round(cmds.getAttr(rc + ".tx"), 3), round(cmds.getAttr(rc + ".ty"), 3),
      "| L untouched:", cmds.getAttr(c + ".tx"))
print("selection only:", ga.apply_pose(pose, "", only=set()))
ga._lib["picked"] = name; ga.library_fill()
print("grid items:", len([v for v in UI.values() if v.get("kind") == "iconTextButton" and v.get("parent") == ga.PL + "Grid"]))
ga.delete_pose(name, ""); print("deleted:", ga.pose_files(""))
