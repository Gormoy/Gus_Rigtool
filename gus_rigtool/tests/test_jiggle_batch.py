# 3.13: chain jiggle (follow-through spring groups under each FK control, an expression that rests when you jump in
# time) and batch Checker / Publish. 5.0.10: its memory is a MEL global (no setAttr: undo stays clean), the root
# comes in through a decomposeMatrix
import os, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
from gus_rigtool.builder import build as bld, guides, modules, chain
EXPR = []
cmds.expression = lambda **k: EXPR.append(k) or k.get("name")
bld.biped(180)
e = bld.add_module("chain", "L", "ear", 180)
s = guides.read(e)["settings"]; s["attach"] = "neck:head"; s["names"]["count"] = 3; s["options"]["jiggle"] = True
guides.save_settings(e, s); guides.update(e, modules.MODULES["chain"], s, 180)
bld.build_all(180)
jg = cmds.ls([n for n in cmds.ls() if n.endswith("_jiggle_grp")], long=True)
print("jiggle groups:", [g.split("|")[-1] for g in jg], "| control under each:", all(cmds.listRelatives(g, children=True) for g in jg))
st = [n for n in cmds.ls() if n.endswith("_jiggle_state")]          # 5.0.10: no state node any more
sc = [n for n in cmds.ls() if n.startswith("L_ear") and n.endswith("settings_ctrl")]
print("state node:", st, "| on", sc, ":", [a for a in ("jiggle", "jiggle_stiffness", "jiggle_damping", "jiggle_bounce") if sc and cmds.objExists(sc[0] + "." + a)])
code = [x for x in EXPR if "jiggle" in x.get("name", "")][0]["string"]
import re
print("expression: memory in a MEL global, no setAttr:", "global float $gusJiggle_" in code and "setAttr" not in code,
      "| rests on a jump:", re.search(r"abs\(\$f - \$gusJiggle_\w+\[0\] - 1\) > 0\.01", code) is not None,
      "| drives each group:", sum(code.count("%s.rotate" % g.split("|")[-1]) for g in jg),
      "| reads the head through a decomposeMatrix:", "outputRotateX" in code and bool(cmds.ls(type="decomposeMatrix")))
# batch
from gus_rigtool.tools import batch, checker
d = tempfile.mkdtemp()
files = [os.path.join(d, n) for n in ("hare_rig.ma", "fox_rig.ma")]
OPENED, SAVED = [], []
def file_(*a, **k):
    if k.get("open"):
        OPENED.append(os.path.basename(a[0]))
    if k.get("rename"):
        SAVED.append(os.path.basename(k["rename"]))
cmds.file = file_
checker.run_checks = lambda o, scope: {"dup_names": ("FAIL", ["x"])} if OPENED[-1].startswith("fox") else {"ctrl_zero": ("WARN", ["a"])}
import gus_rigtool.builder.publish as pub
pub.publish = mock.MagicMock(return_value=["ok"])
text = batch.run(files, publish=True)
print("opened:", OPENED, "| published:", SAVED)
print(text.splitlines()[0]); print("\n".join(text.splitlines()[2:4]))
print("publish name:", batch.publish_path("/x/hare_rig.mb"), batch.publish_path("/x/hare"))
