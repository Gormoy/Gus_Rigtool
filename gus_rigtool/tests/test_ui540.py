# 5.4.0: the reorganised window - every tool in exactly one tab, Behaviour has limits / in front / stop at the body,
# My tools defaults, Home suggestions from the selection, the map lists every page and what moved
exec(open("fakemaya.py").read())
import sys
from unittest import mock
from gus_rigtool import registry
from gus_rigtool.core import ui
from gus_rigtool.tools import home
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

placed = [k for _c, _l, keys in registry.CATEGORIES for k in keys]
tools = [t[0] for t in registry.TOOLS]
check("every tool in exactly one tab", sorted(placed) == sorted(tools) and len(placed) == len(set(placed)))
check("tabs: Home, Build, Skin, Controls, Connect, Check, Toolbox",
      [c[1] for c in registry.CATEGORIES] == ["Home", "Build", "Skin", "Controls", "Connect", "Check", "Toolbox"])
check("Joints in Build, SDK in Connect, Behaviour in Controls", registry.category_of("joints")[0] == "build" and
      registry.category_of("sdk")[0] == "links" and registry.category_of("behaviour")[0] == "controls")
with mock.patch.object(ui.utils if hasattr(ui, "utils") else __import__("gus_rigtool.core.utils", fromlist=["x"]),
                       "load_setting", lambda k, d=None: d):
    check("My tools by default: what you use most", ui.my_tools() == ["select", "groups", "shapes", "ribbon",
                                                                       "checker", "mirror", "constrain"])
m = ui.map_text()
check("the map: every page, and what moved", all(registry.get(k)[1] in m for k in tools) and
      "Controls > Behaviour" in m and "Build > Joints" in m)
print(m.split("MOVED")[1])

# suggestions
c = cmds.createNode("transform", name="L_Brow_ctrl"); cmds.createNode("nurbsCurve", name="L_Brow_ctrlShape", parent=c)
j = cmds.createNode("joint", name="L_arm_jnt")
srf = cmds.createNode("transform", name="L_Sleeve"); cmds.createNode("nurbsSurface", name="L_SleeveShape", parent=srf)
what, items = home.suggest([cmds.ls(c, long=True)[0]])
print(what, [i[1] for i in items])
check("a control: shapes, behaviour, attributes, spaces, mirror", what == "Control" and
      [i[1] for i in items] == ["shapes", "behaviour", "attrs", "spaces", "mirror"])
what, items = home.suggest([cmds.ls(j, long=True)[0]])
check("a joint: make controls first", what == "Joint" and items[0][1] == "makectrl")
what, items = home.suggest([cmds.ls(srf, long=True)[0]])
check("a surface: ribbon", items and items[0][1] == "ribbon")
what, items = home.suggest(["Hood.e[12]", "Hood.e[13]"])
check("edges: face strip, cloth ribbon, joints", what == "Edges" and [i[1] for i in items] == ["face", "skin",
                                                                                              "joints"])
what, items = home.suggest([])
check("nothing selected: select, build, check", [i[1] for i in items] == ["select", "build", "checker"])
check("at most 6 suggestions", len(home.suggest([cmds.ls(c, long=True)[0], cmds.ls(j, long=True)[0]])[1]) <= 6)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
