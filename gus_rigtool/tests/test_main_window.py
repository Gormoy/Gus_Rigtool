# Main window: 4 categories with their tools, search finds options, go_to opens the right tabs
import sys, types, os
from unittest import mock
maya = types.ModuleType("maya"); cmds = mock.MagicMock(); api = types.ModuleType("maya.api")
maya.cmds = cmds; maya.mel = mock.MagicMock(); maya.api = api; api.OpenMaya = mock.MagicMock()
sys.modules.update({"maya": maya, "maya.cmds": cmds, "maya.mel": maya.mel, "maya.api": api,
                    "maya.api.OpenMaya": api.OpenMaya})
sys.path.insert(0, os.environ.get("GUS_RIGTOOL_PARENT") or os.path.abspath(os.path.join(os.getcwd(), "..", "..")))
from gus_rigtool import registry
from gus_rigtool.core import ui
print("categories:", [(c[1], c[2]) for c in registry.CATEGORIES])
print("every tool in a category:", sorted(k for c in registry.CATEGORIES for k in c[2]) == sorted(t[0] for t in registry.TOOLS))
ui._index[:] = [("toes number of toes", "Number of toes", "Build > Build", "win|cats|build|tools|build_scroll|col|tabs|settings|Form|frame3|col|row|menu"),
                ("mirror pose l > r", "Mirror pose", "Mirror & Pose > Mirror", "win|cats|mirror|tools|mirror_scroll|col|frame1|col|btn"),
                ("stretch ik stretch", "IK stretch", "Build > Build", "win|cats|build|tools|build_scroll|col|tabs|settings|Form|frame2|col|cb")]
ui._index_state["stale"] = False                    # the index above is current
print("search 'toes':", ui.search("toes"))
print("search 'mirror pose':", ui.search("mirror pose"))
tabs = {"win|cats": ["build", "controls", "mirror", "check"], "win|cats|build|tools": ["build_scroll", "j", "r"],
        "win|cats|build|tools|build_scroll|col|tabs": ["modules", "settings", "buildpage", "anim"]}
kinds = lambda p: "tabLayout" if p in tabs else ("frameLayout" if p.split("|")[-1].startswith("frame") else "columnLayout")
cmds.objectTypeUI.side_effect = kinds
picked = []
cmds.tabLayout.side_effect = lambda p, **k: tabs[p] if k.get("childArray") else picked.append((p, k.get("selectTabIndex")))
opened = []
cmds.frameLayout.side_effect = lambda p, **k: opened.append(p)
ui.go_to(ui._index[0][3])
print("go_to selected tabs:", picked, "| opened frames:", [o.split("|")[-1] for o in opened])
# the whole main window builds (every tool, mocked Maya UI)
cmds.reset_mock(); cmds.objectTypeUI.side_effect = None; cmds.tabLayout.side_effect = None; cmds.frameLayout.side_effect = None
cmds.formLayout.return_value = False
errors = []
ui.report_error = lambda e, w="": errors.append((w, repr(e)))
ui.fill_panel(ui.MAIN_KEY)
waiting = len(ui._lazy)
print("main window opens with only the shown page built:", waiting == len(registry.TOOLS) - 1, "(%d waiting)" % waiting)
print("the rest build on demand:", ui.build_all_pages() == waiting, "| none left:", not ui._lazy)
print("main window built; tool errors (mock values aside):", [e for e in errors if "MagicMock" not in e[1]])
