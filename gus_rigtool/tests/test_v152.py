exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
import numpy as np
from gus_rigtool.tools import build_tab as bt, build_form as bf
from gus_rigtool.builder import guides, build as bld
from gus_rigtool.core import ui, mirror_engine as me
ui.report_error=lambda e,w="": __import__("traceback").print_exc()
cmds.confirmDialog=lambda **k: (print("  [dialog]", k.get("message","")[:90].replace("\n"," ")), k["button"][0])[1]
A=lambda m: np.array(m).reshape(4,4)
bt.build("B_"); bt.biped(); bt.build_rig()
# head: world axes, no head end
print("head_end joint:", bool(S.find("head_end_jnt")), "| head joint axes:", A(world(S.get("head_jnt")))[:3,:3].round(3).tolist())
# settings ctrls mirrored
L=A(world(S.get("L_wrist_settings_ctrl")))[3,:3]; R=A(world(S.get("R_wrist_settings_ctrl")))[3,:3]
print("settings ctrl L / R:", L.round(1), R.round(1), "mirrored:", np.allclose(L*[-1,1,1], R))
# clavicle ctrl pivot on clavicle
print("clav ctrl pivot == clav joint:", np.allclose(A(world(S.get("L_clavicle_FK_ctrl")))[3,:3], A(world(S.get("L_clavicle_jnt")))[3,:3]))
# multi-select: L arm, R arm, L leg, R leg -> stretch on (rig built) -> rebuild now
groups=bt._rows["B_"]
picks=[groups.index(g)+1 for g in groups if guides.read(g)["type"] in ("arm","leg")]
UI["B_List"]["selectIndexedItem"]=picks
bt._fill_form()
print("common options:", sorted(k for k in bf._form["B_"]))
ctrl = bf._form["B_"]["options.stretch"].control; cmds.checkBox(ctrl, edit=True, value=True)
bt.apply_common(); groups=bt._rows["B_"]; UI["B_List"]["selectIndexedItem"]=[groups.index(g)+1 for g in groups if guides.read(g)["type"] in ("arm","leg")]; bt.build_picked()
for c in ("L_wrist_settings_ctrl","R_wrist_settings_ctrl","L_ankle_settings_ctrl","R_ankle_settings_ctrl"):
    print(c, "stretch" in S.get(c).user)
from collections import Counter
print("duplicate names:", [n for n,c in Counter(x.name for x in S.nodes if x.type in ("joint","transform")).items() if c>1][:5])
# single apply while built (head option) 
groups=bt._rows["B_"]; neck=[g for g in groups if guides.read(g)["type"]=="neck"][0]
UI["B_List"]["selectIndexedItem"]=[groups.index(neck)+1]; bt._fill_form()
ctrl = bf._form["B_"]["options.head_end"].control; cmds.checkBox(ctrl, edit=True, value=True)
bt.apply_form(); bt.build_picked(); print("head_end joint after apply+rebuild:", bool(S.find("head_end_jnt")))
print("duplicate names:", [n for n,c in Counter(x.name for x in S.nodes if x.type in ("joint","transform")).items() if c>1][:5])
