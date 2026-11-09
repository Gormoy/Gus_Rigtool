# 5.0.10: the chain jiggle no longer writes its memory with setAttr (every evaluation put setAttrs on the undo list:
# the Hare's cape could not be undone, and ngSkinTools hung). Its memory is a MEL global; the root comes in through
# a decomposeMatrix; an old jiggle expression is found (Check this scene / Repair) and rewritten in place
import re
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.builder import chain
from gus_rigtool import scene_check
from gus_rigtool.core import repair
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
EXPR = {}
def expression(*a, **k):
    if k.get("query"):
        return EXPR.get(a[0].split("|")[-1], "")
    name = k.get("name", "expression1")
    cmds.createNode("expression", name=name)
    EXPR[name] = k.get("string", "")
    for m in re.finditer(r"\b([A-Za-z_][\w:]*)\.(output\w+)", EXPR[name]):     # inputs: like Maya, connected
        if cmds.objExists(m.group(1)):
            try:
                cmds.addAttr(name, longName="in_" + m.group(2), attributeType="double")
            except Exception:
                pass
            try:
                cmds.connectAttr(m.group(1) + "." + m.group(2), name + ".in_" + m.group(2), force=True)
            except Exception:
                pass
    return name
cmds.expression = expression

root = cmds.createNode("transform", name="Cape_ctrls_grp")
settings = cmds.createNode("transform", name="Cape_settings_ctrl")
for a in ("jiggle", "jiggle_stiffness", "jiggle_damping", "jiggle_bounce"):
    cmds.addAttr(settings, longName=a, attributeType="double")
groups = [cmds.createNode("transform", name="Cape_%02d_jiggle_grp" % i, parent=root) for i in (1, 2, 3)]

# an old (5.0.9 and before) jiggle, as the Hare has it
old_lines = ["// Gus_Rigtool jiggle: Cape (state on Cape_jiggle_state, read / written with getAttr / setAttr: no cycle)",
             "float $f = frame;", "int $i;",
             "float $p[] = `xform -q -ws -t Cape_ctrls_grp`;", "float $r[] = `xform -q -ws -ro Cape_ctrls_grp`;",
             "float $last = `getAttr Cape_jiggle_state.last`;",
             "int $rest = (Cape_settings_ctrl.jiggle == 0 || abs($f - $last - 1) > 0.01);",
             "setAttr Cape_jiggle_state.last $f;"]
for i in (1, 2, 3):
    old_lines += ["    Cape_%02d_jiggle_grp.rotateY = $os;" % i, "    Cape_%02d_jiggle_grp.rotateZ = $ou;" % i]
cmds.createNode("network", name="Cape_jiggle_state")
expression(string="\n".join(old_lines), name="Cape_jiggle_expr")

check("an old jiggle is found", chain.old_jiggles() == ["Cape_jiggle_expr"])
class Rep(object):
    def __init__(self):
        self.rows = []
    def start(self, t):
        pass
    def add(self, lv, what, detail=""):
        self.rows.append((lv, what, detail))
r = Rep(); scene_check.check_connections(r)
check("Check this scene warns about it", any(lv == scene_check.WARN and "break undo" in w for lv, w, d in r.rows))
item = [i for i in repair.find() if i.id == "old_jiggle"]
check("Repair offers to rewrite it", len(item) == 1 and item[0].count == 1)
item[0].fix()
text = EXPR.get("Cape_jiggle_expr", "")
print(re.sub(r"gusJiggle_Cape_[0-9a-f]{6}", "gusJiggle_Cape_<id>", text))   # the id is random
check("rewritten under the same name", cmds.objExists("Cape_jiggle_expr") and chain.JIGGLE_TAG in text)
check("no setAttr, no getAttr, no xform by name (namespace-proof)", not re.search(r"setAttr|getAttr|xform", text))
check("its memory is one MEL global array", len(set(re.findall(r"\$gusJiggle_Cape_[0-9a-f]{6}", text))) == 1
      and "global float $gusJiggle_Cape_" in text)
check("same groups and axes: side Y, up Z, all three",
      all("Cape_%02d_jiggle_grp.rotateY = $gusJiggle" % i in text and
          "Cape_%02d_jiggle_grp.rotateZ = $gusJiggle" % i in text for i in (1, 2, 3)))
check("same settings attributes", all("Cape_settings_ctrl." + a in text for a in
                                      ("jiggle", "jiggle_stiffness", "jiggle_damping", "jiggle_bounce")))
dm = cmds.ls(type="decomposeMatrix") or []
check("the root comes in through a decomposeMatrix",
      len(dm) == 1 and (cmds.listConnections(dm[0] + ".inputMatrix", source=True) or [""])[0].endswith("Cape_ctrls_grp"))
check("between frames it only puts the offsets back (springs step once per new frame)",
      re.search(r"if \(\$f != \$gusJiggle_\w+\[0\]\) \{", text) is not None)
check("the old state node is gone", not cmds.objExists("Cape_jiggle_state"))
check("nothing old left", chain.old_jiggles() == [])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
