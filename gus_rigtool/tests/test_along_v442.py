# 4.4.2: a ribbon that runs along V is swapped before building; Check / Repair find built ones
exec(open("fakemaya.py").read())
from gus_rigtool.core import ribbon, repair
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
swaps = []
state = {"v": True}
ribbon.runs_along_v = lambda s: state["v"]
cmds.reverseSurface = lambda *a, **k: (swaps.append((a, k)), state.update(v=False))
cmds.createNode("transform", name="strip")
check("runs along V: swapped (reverseSurface direction 3)", ribbon._turn_along_u("strip") == "swapped"
      and swaps and swaps[-1][1].get("direction") == 3)
check("runs along U: left alone", ribbon._turn_along_u("strip") is None and len(swaps) == 1)
state["v"] = True
_ls = cmds.ls
cmds.listHistory = lambda *a, **k: ["skinCluster9"]
cmds.ls = lambda *a, **k: ["skinCluster9"] if k.get("type") == "geometryFilter" else _ls(*a, **k)
check("deformed: not swapped, reported", ribbon._turn_along_u("strip") == "deformed" and len(swaps) == 1)
cmds.ls = _ls
ribbon._find_builds = lambda: {"|strip": {"nodes": [], "skins": []}}
cmds.objExists = lambda n: True
item = repair._along_v()
check("Repair offers 'Rebuild along the length'", item is not None and item.id == "ribbon_along_v" and item.count == 1)
state["v"] = False
check("nothing to repair when it runs along U", repair._along_v() is None)
print("ALL OK" if all(ok) else "SOME FAILED")
