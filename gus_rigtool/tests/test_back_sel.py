exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from gus_rigtool.tools import build_tab as bt
from gus_rigtool.builder import guides, build as bld, skin_keep
from gus_rigtool.core import ui
ui.report_error=lambda e,w="": __import__("traceback").print_exc()
cmds.confirmDialog=lambda **k: (print("  [dialog]", k.get("message","")[:120].replace("\n"," ")), k["button"][0])[1]
bt.build("B_"); bt.biped(); bt.build_rig()
rows=bt._rows["B_"]; ids=[guides.read(g)["id"] for g in rows]
def pick(*mids):
    UI["B_List"]["selectIndexedItem"]=[ids.index(m)+1 for m in mids]
joints=lambda: len([n for n in S.nodes if n.type=="joint"])
j0=joints(); print("built joints:", j0)
# A: show guides
pick("L:arm"); bt.show_guides_picked()
vis={guides.read(g)["id"]: S.get(g.split("|")[-1]).attrs["visibility"] for g in guides.module_groups()}
print("A shown:", [k for k,v in vis.items() if v], "| top:", S.get("guides_grp").attrs["visibility"])
bt.show_guides_picked(); print("A again -> top:", S.get("guides_grp").attrs["visibility"])
# B: back L arm (fingers hang from it)
pick("L:arm"); bt.back_picked()
print("joints after back:", joints(), "| L_humerus exists:", bool(S.find("L_humerus_jnt")), "| R_humerus:", bool(S.find("R_humerus_jnt")))
print("list:", [UI["B_List"]["append"][i] for i in range(len(ids)) if UI["B_List"]["append"][i].rstrip().endswith("guides")])
vis={guides.read(g)["id"]: S.get(g.split("|")[-1]).attrs["visibility"] for g in guides.module_groups()}
print("guides shown:", [k for k,v in vis.items() if v])
print("light:", bt._light())
# Build button builds only the waiting ones
bt.build_rig()
print("joints after Build:", joints(), "== before:", joints()==j0, "| top guides vis:", S.get("guides_grp").attrs["visibility"])
# back two separately, rebuild one -> other still at guides
pick("C:neck"); bt.back_picked(); pick("R:leg"); bt.back_picked()
pick("C:neck"); bt.rebuild_selected()
vis={guides.read(g)["id"]: S.get(g.split("|")[-1]).attrs["visibility"] for g in guides.module_groups()}
print("after rebuilding neck, guides shown:", [k for k,v in vis.items() if v], "| light:", bt._light()[1])
pick("R:leg"); bt.rebuild_selected(); print("all back:", joints()==j0, bt._light()[1])
from collections import Counter
print("dupes:", [n for n,c in Counter(x.name for x in S.nodes if x.type in ("joint","transform")).items() if c>1][:5])
