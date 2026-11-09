exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
cmds.radioCollection=lambda *a,**k: a[0] if a else "rc"
cmds.radioButton=_make("radioButton")
cmds.deleteAttr=lambda node, attribute=None: _n(node).user.pop(attribute, None)
from gus_rigtool.tools import follow_tab as ft
from gus_rigtool.core import ui
ui.report_error=lambda e,w="": __import__("traceback").print_exc()
ft.build("F_")
def ctrl(name, pos):
    off=S.create("transform", name+"_offset"); off.attrs["translate"]=list(pos)
    c=S.create("transform", name, off); S.create("nurbsCurve", name+"Shape", c); return c.name
jaw=ctrl("Jaw_ctrl",[0,150,2]); S.create("joint","jaw_jnt"); lip=ctrl("lowLip_ctrl",[0,147,9])
print("weight on default:", UI["F_AttrOn"].get("select"))
cmds.select("jaw_jnt"); ft._load_source(); print("source:", UI["F_Source"].get("text"))
cmds.select(jaw, lip); ft._on_remap(); print(UI["F_Summary"]["label"])
ft.add(); print(UI["F_List"].get("append"))
# pivot / axes options + move follow pivot
S.create("transform","piv_loc").attrs["translate"]=[0,149,1]
cmds.select("piv_loc"); ft._load_pivot(); print("pivot:", UI["F_Pivot"].get("text"), "mode:", UI["F_PivotMode"].get("select"))
UI["F_Axes"]["select"]=2
cmds.select(lip); ft.move_pivot()
import numpy as np
print("moved space:", np.round(np.array(world(S.get("lowLip_ctrl_followSpace"))).reshape(4,4)[3,:3],3).tolist(),
      "| meta axes:", ft.follow._meta(S.get("lowLip_ctrl_follow").name)["axes"])
ft._clear_pivot(); print("cleared mode:", UI["F_PivotMode"].get("select"))
