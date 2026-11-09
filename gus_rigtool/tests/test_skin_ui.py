# Skin tab: panel builds, light, and the actions fail politely without a selection
exec(open("fakemaya.py").read())
exec(open("fakeui.py").read())
from gus_rigtool.tools import skin_tool
from gus_rigtool import registry
print("category:", [c for c in registry.CATEGORIES if "skin" in c[2]][0][:2])
skin_tool.build()
print("light:", skin_tool._light())
print("ui:", sorted(skin_tool._ui().items()))
for fn in (skin_tool.bind, skin_tool.copy, skin_tool.prune, skin_tool.limit, skin_tool.remove_unused):
    try:
        fn()
    except RuntimeError as e:
        print(fn.__name__, "->", e)
# limit influences: only the biggest weights stay, shared out to 1
from gus_rigtool.core import skin_tools
calls = []
skin_tools._need_skin = lambda g: "skin1"
skin_tools._weights = lambda s, g: (["j1", "j2", "j3"], "vtx", {0: [0.5, 0.3, 0.2], 1: [0.6, 0.4, 0.0]})
cmds.skinPercent = lambda *a, **k: calls.append((a[1], [(j, round(v, 3)) for j, v in k["transformValue"]]))
cmds.skinCluster = lambda *a, **k: None
print("fixed:", skin_tools.limit_influences(["m"], 2), calls)
