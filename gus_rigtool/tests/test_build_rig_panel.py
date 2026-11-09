# The Build pop-out: its own module list (Refresh) and the Build part; Build picked works from its list.
# The main Build page: list, settings, then the Build part on the same page (tabs: Rig builder / Animation).
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
cmds.confirmDialog = lambda **k: k["button"][0]
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool.builder import build as bld, guides
from gus_rigtool.tools import build_tab
from gus_rigtool.core import ui
bld.biped(100)
_cur[0] = None; cmds.columnLayout("main_root"); build_tab.build("m_build_")
print("main tabs:", [l for _c, l in UI["m_build_Tabs"]["tabLabel"]])
labels = [v.get("label") for v in UI.values() if v.get("kind") == "button" and v.get("label")]
print("main page has Build, Build picked, Publish, Pop out, Refresh:",
      all(x in labels for x in ("Build", "Build picked", "Publish", "Pop out", "Refresh")))
_cur[0] = None; cmds.columnLayout("pop_root"); ui._build_tool("build_rig", "p_build_rig_")
items = UI["p_build_rig_List"].get("append")
print("pop-out list rows:", len(items), "| first:", items[0].strip())
root = [i for i, x in enumerate(items) if " root " in x or x.split()[1:2] == ["root"]]
cmds.textScrollList("p_build_rig_List", edit=True, selectIndexedItem=1)
with mock.patch.object(bld, "build_picked", return_value=None) as bp:
    build_tab._P["p"] = "p_build_rig_"; build_tab.build_picked()
    print("Build picked from the pop-out list builds:", bp.call_args[0][0] if bp.called else None)
# refresh: delete a module by hand, the list follows
g = guides.module_groups()[-1]; name = guides.read(g)["id"]; cmds.delete(g)
build_tab._P["p"] = "m_build_"; print("stale after a hand delete:", build_tab._stale())
build_tab.refresh_now(); print("after Refresh:", build_tab._stale(), "| %s still listed:" % name,
                               any(name.split(":")[1] in r and r.strip().startswith(name[0]) for r in UI["m_build_List"]["append"]))
