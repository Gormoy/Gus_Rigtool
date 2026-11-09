# Number of toes through the Build tab: dropdown, unapplied warning, Build asks to apply first
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from gus_rigtool.tools import build_tab as bt, build_form as bf
from gus_rigtool.builder import guides, build as bld
from gus_rigtool.core import ui
ui.report_error = lambda e, w="": __import__("traceback").print_exc()
cmds.confirmDialog = lambda **k: (print("  [dialog]", k.get("message", "")[:160].replace("\n", " | ")), k["button"][0])[1]
bt.build("B_"); bt.quadruped()
for g in guides.module_groups():
    i = guides.read(g)
    if i["type"] in ("front_leg", "back_leg"):
        print(i["id"], "toes from the template:", i["settings"]["options"]["toe_count"],
              "| toe guides:", len([r for r in i["guides"] if r.startswith("t") and "_" in r]))
bt.build_rig()
print("back toes built:", len([n for n in S.nodes if n.type == "joint" and n.name.startswith("L_toeA")]))
ids = lambda: [guides.read(g)["id"] for g in bt._rows["B_"]]
UI["B_List"]["selectIndexedItem"] = [ids().index("R:back_leg") + 1]; bt._fill_form()
field = bf._form["B_"]["options.toe_count"].control
print("field kind:", UI[field]["kind"], "| items:", UI[field].get("items"))
cmds.optionMenu(field, edit=True, select=3)                     # 2 toes
print("pending:", bf.pending()); print("light:", bt._light())
UI["B_List"]["selectIndexedItem"] = [ids().index("R:back_leg") + 1]
bt.build_picked()                                                 # asks; 'Apply and build'
g = [g for g in guides.module_groups() if guides.read(g)["id"] == "R:back_leg"][0]
print("saved:", guides.read(g)["settings"]["options"]["toe_count"],
      "| R toes built:", sorted(n.name for n in S.nodes if n.type == "joint" and n.name.startswith("R_toe") and n.name.endswith("_01_jnt")))
print("light after:", bt._light()[1])
