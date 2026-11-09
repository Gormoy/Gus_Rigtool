# 5.6.22: picker - a turned button is clicked on its turned shape; Mirror makes no twin for a middle control
# (5.6.21 made a second button: Pants_fol_01, Tail_00...); Clean up finds and removes buttons twice on a page and
# buttons for controls that are gone; the 2D slider sets two attributes (across, up) in their ranges and goes back
# to rest; style presets are kept on this computer
import os, sys
exec(open("fakemaya.py").read())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A, pickmodel as PM
_opts = {}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def b(x, y, w=20.0, h=20.0, i=None, **k):
    it = {"id": i or "%s_%s" % (x, y), "kind": "select", "nodes": [k.pop("node", "n")], "x": float(x),
          "y": float(y), "w": w, "h": h, "shape": "rect", "points": [], "rgb": [0.5, 0.5, 0.5], "label": "",
          "twin": None}
    it.update(k)
    return it
bar = b(0, 0, 40, 4, rot=90)                         # a thin bar turned upright
check("turned 90: clicked on its upright shape, not where it lay", PM.contains(bar, 20, 15) and
      not PM.contains(bar, 2, 2))
for n in ("Pants_fol_01_ctrl", "L_arm_ctrl", "R_arm_ctrl"):
    cmds.createNode("nurbsCurve", name=n + "Shape", parent=cmds.createNode("transform", name=n))
page = {"name": "Body", "width": 400.0, "items": [b(50, 50, node="Pants_fol_01_ctrl", i="p"),
                                                  b(100, 50, node="L_arm_ctrl", i="l")]}
with mock.patch.object(PM.A, "mirror_name", side_effect=lambda n: n.replace("L_", "R_") if n.startswith("L_") else None):
    twins = PM.mirror(page, list(page["items"]), "")
check("Mirror: the arm gets its twin, the middle control none (no second button)",
      len(page["items"]) == 3 and sorted(i["nodes"][0] for i in page["items"]) ==
      ["L_arm_ctrl", "Pants_fol_01_ctrl", "R_arm_ctrl"])
page["items"] += [b(200, 50, node="Pants_fol_01_ctrl", i="p2"), b(250, 50, node="Test_shift_frame", i="gone")]
picker = {"pages": [page]}
with mock.patch.object(PM, "resolve", side_effect=lambda it, ns: [] if it["nodes"][0] == "Test_shift_frame" else
                       ["|" + it["nodes"][0]]):
    dup, old = PM.duplicates(picker), PM.stale(picker)
    check("found: Pants_fol_01 twice, Test_shift_frame gone", [i["id"] for _p, i in dup] == ["p2"] and
          [i["id"] for _p, i in old] == ["gone"])
    a, c = PM.cleanup(picker)
check("cleaned: those two go, the first Pants button stays", (a, c) == (1, 1) and
      sorted(i["id"] for i in page["items"]) == sorted(["p", "l"] + [i["id"] for i in page["items"]
                                                                    if i["nodes"][0] == "R_arm_ctrl"]))
eye = cmds.createNode("transform", name="L_Eye_ctrl")
cmds.createNode("nurbsCurve", name="L_Eye_ctrlShape", parent=eye)
cmds.addAttr(eye, longName="lookX", attributeType="double", minValue=-2, maxValue=2)
cmds.addAttr(eye, longName="lookY", attributeType="double", minValue=-1, maxValue=1)
with mock.patch.object(PM.A, "_colour", return_value=[0.5, 0.5, 0.5]), \
        mock.patch.object(cmds, "attributeQuery", side_effect=lambda a, node=None, **k:
                          True if (k.get("minExists") or k.get("maxExists")) else
                          ([-2.0] if a == "lookX" else [-1.0]) if k.get("minimum") else
                          ([2.0] if a == "lookX" else [1.0]) if k.get("maximum") else
                          (a in ("lookX", "lookY")) if k.get("exists") else False):
    pad = PM.add_slider2d(page, "L_Eye_ctrl", "lookX", "lookY")
check("2D slider: across lookX -2..2, up lookY -1..1", pad["kind"] == "slider2d" and
      (pad["min_x"], pad["max_x"], pad["min_y"], pad["max_y"]) == (-2.0, 2.0, -1.0, 1.0))
with mock.patch.object(PM, "resolve", return_value=[cmds.ls("L_Eye_ctrl", long=True)[0]]):
    PM.set_slider2d(pad, "", 0.75, 1.0)
    vals = (cmds.getAttr("L_Eye_ctrl.lookX"), cmds.getAttr("L_Eye_ctrl.lookY"))
    frac = PM.slider2d_value(pad, "")
    PM.reset_slider2d(pad, "")
    back = (cmds.getAttr("L_Eye_ctrl.lookX"), cmds.getAttr("L_Eye_ctrl.lookY"))
check("the handle three quarters across, at the top: lookX 1, lookY 1; read back the same", vals == (1.0, 1.0)
      and frac == (0.75, 1.0))
check("double-click: back to rest (0, 0)", back == (0.0, 0.0))
PM.save_style("FK blue", {"rgb": [0.2, 0.4, 0.9], "shape": "pill", "text_size": 9})
check("style presets kept (on this computer), applied like a paste", PM.styles()["FK blue"]["shape"] == "pill")
dst = b(0, 0)
PM.paste_style([dst], PM.styles()["FK blue"])
check("... applied: colour, shape, text size", dst["shape"] == "pill" and dst["text_size"] == 9)
PM.delete_style("FK blue")
check("... and deleted", "FK blue" not in PM.styles())
print("%d/%d passed" % (sum(ok), len(ok)))
