# Guide symmetry lock: right guides follow the left ones through a node network; off keeps them where they are;
# re-made modules (Mirror picked / new settings) get linked again by themselves while it is on
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.builder import build as bld, guides
bld.add_module("arm", "L", "arm", 180.0)
bld.add_module("spine", "C", "spine", 180.0)
print("pairs before mirror:", len(guides.symmetry_pairs()))
print("on with no twin:", guides.set_symmetry(True), guides.symmetry_on())
bld.mirror_all(180.0)
print("linked by itself after mirror:", guides.symmetry_on(), "| pairs:", len(guides.symmetry_pairs()))
pairs = guides.symmetry_pairs()
left, right = pairs[0]
src = cmds.listConnections(right + ".translate", source=True, destination=False)
mm = cmds.listConnections(src[0] + ".inputMatrix", source=True, destination=False)
print("right", right.split("|")[-1], "<-", src, "<-", mm, "<-", cmds.listConnections(mm[0] + ".matrixIn[0]", source=True,
      destination=False), "| mirror matrix", _n(mm[0]).attrs.get("matrixIn[1]")[:3])
print("every right guide driven:", all(guides._drives_translate(r) for _l, r in pairs), len(pairs))
g = [x for x in guides.module_groups() if guides.read(x)["side"] == "L"][0]
from gus_rigtool.builder import modules
guides.update(g, modules.MODULES["arm"], guides.read(g)["settings"], 180.0)
print("after the left module is re-made: networks", len(guides.symmetry_nodes()), "| all driven:",
      all(guides._drives_translate(r) for _l, r in guides.symmetry_pairs()))
print("off:", guides.set_symmetry(False), guides.symmetry_on(), "| right free:",
      not any(guides._drives_translate(r) for _l, r in guides.symmetry_pairs()))
# the page button
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool.core import ui
from gus_rigtool.tools import build_tab as bt
_cur[0] = None; cmds.columnLayout("root"); ui._build_tool("build", "p_build_"); bt._P["p"] = "p_build_"
print("button:", UI["p_build_SymToggle"]["label"]); bt.toggle_symmetry(); print("button:", UI["p_build_SymToggle"]["label"])
