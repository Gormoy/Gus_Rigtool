exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from gus_rigtool.tools import build_tab as bt, build_form as bf
from gus_rigtool.builder import guides, build as bld
from gus_rigtool.core import ui
ui.report_error=lambda e,w="": __import__("traceback").print_exc()
dialogs=[]
cmds.confirmDialog=lambda **k: (dialogs.append(k.get("message","")[:100].replace("\n"," ")), k["button"][0])[1]
bt.build("B_"); bt.biped()
ids=lambda: [guides.read(g)["id"] for g in bt._rows["B_"]]
def pick(*m): UI["B_List"]["selectIndexedItem"]=[ids().index(x)+1 for x in m]
J=lambda: len([n for n in S.nodes if n.type=="joint"])
# nothing built: Build picked on L:fingers -> asks about unbuilt parents (L:arm, spine, root)
pick("L:fingers"); bt.build_picked()
print("dialog:", dialogs[-1]); print("built:", [i for i in ids() if bld.is_module_built(guides.read(bt._rows['B_'][ids().index(i)]))])
print("light:", bt._light()[1])
bt.build_rig(); j_all=J(); print("Build rest -> joints", j_all, "| waiting:", bld._waiting())
# apply on a built module never builds
pick("C:neck"); bt._fill_form(); cmds.checkBox(bf._form["B_"]["options.head_end"].control, edit=True, value=True)
n_d=len(dialogs); bt.apply_form()
print("apply: dialogs asked:", len(dialogs)-n_d, "| head_end joint:", bool(S.find("head_end_jnt")), "| neck still built:", bool(S.find("neck_jnt")))
pick("C:neck"); bt.build_picked(); print("build picked -> head_end:", bool(S.find("head_end_jnt")))
# apply on a module at its guides never builds
pick("L:arm"); bt.back_picked(); pick("L:arm"); bt._fill_form()
cmds.checkBox(bf._form["B_"]["options.stretch"].control, edit=True, value=True); bt.apply_form()
print("arm at guides after apply:", not S.find("L_humerus_jnt"))
bt.build_rig(); print("Build -> arm back:", bool(S.find("L_humerus_jnt")), "| stretch attr:", "stretch" in S.get("L_wrist_settings_ctrl").user)
try: bt.build_rig()
except Exception as e: print("Build again:", e)
from collections import Counter
print("dupes:", [n for n,c in Counter(x.name for x in S.nodes if x.type in ("joint","transform")).items() if c>1][:5])
