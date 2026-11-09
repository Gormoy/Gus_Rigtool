# Build tab list: Refresh button and the automatic refresh (deleted by hand, new scene, undo)
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
jobs = []
cmds.scriptJob = lambda **k: jobs.append((k["event"][0], k["event"][1], k.get("parent"))) or len(jobs)
from gus_rigtool.tools import build_tab as bt
from gus_rigtool.builder import guides
from gus_rigtool.core import ui
ui.report_error = lambda e, w="": __import__("traceback").print_exc()
bt.build("B_"); bt.biped()
print("events on the list:", sorted(set(e for e, f, p in jobs if p == "B_List")))
fire = lambda ev: [f() for e, f, p in jobs if e == ev and p == "B_List"]
ids = lambda: [guides.read(g)["id"] for g in bt._rows["B_"]]
print("modules:", len(ids()))
UI["B_List"]["selectIndexedItem"] = [ids().index("L:arm") + 1]
gone = [g for g in guides.module_groups() if guides.read(g)["id"] == "L:fingers"][0]
cmds.delete(gone)                                             # deleted by hand in the outliner
print("stale after a hand delete:", bt._stale())
fire("SelectionChanged")
print("after selection changed:", len(ids()), "| fingers listed:", "L:fingers" in ids(),
      "| still picked:", [guides.read(g)["id"] for g in bt._picked()])
S.__init__()                                                  # a new scene
fire("NewSceneOpened")
print("after new scene:", UI["B_List"].get("append"), "| rows:", len(bt._rows["B_"]))
bt.biped(); bt.refresh_now()
print("Refresh button:", len(ids()), "modules")
