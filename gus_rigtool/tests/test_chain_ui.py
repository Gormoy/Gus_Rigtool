exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from gus_rigtool.tools import build_tab as bt, build_form as bf
from gus_rigtool.builder import guides, build as bld, modules
from gus_rigtool.core import ui, curves
ui.report_error=lambda e,w="": __import__("traceback").print_exc()
answers=["Selection"]
cmds.confirmDialog=lambda **k: answers.pop(0) if answers else "Later"
cmds.promptDialog=lambda *a, **k: "4" if k.get("query") else "OK"
bt.build("B_")
UI["B_AddType"]["select"]=modules.ORDER.index("chain")+1
UI["B_AddSide"]["select"]=1
UI["B_AddName"]["text"]="tail"
locs=[]
for i in range(5):
    l=S.create("transform","loc%d"%i); l.attrs["translate"]=[0,90,-10-8*i]; locs.append(l.name)
cmds.select(locs)
bt.add()
g=[g for g in guides.module_groups() if guides.read(g)["name"]=="tail"][0]
info=guides.read(g)
print("count:", info["settings"]["names"]["count"], "guides:", sorted(info["guides"]), "| j3 at", cmds.xform(info["guides"]["j3"], query=True, worldSpace=True, translation=True))
UI["B_List"]["selectIndexedItem"]=[bt._rows["B_"].index(g)+1]; bt._fill_form()
f=bf._form["B_"]
print("form keys:", [k for k in f if k.startswith("options.")])
# set type ik spline, use From guides for IK
m=f["options.type"].control; cmds.optionMenu(m, edit=True, select=2)
cmds.select([info["guides"]["j0"], info["guides"]["j2"], info["guides"]["j4"]])
btns=[n for n,v in UI.items() if v.get("kind")=="button" and v.get("label")=="From guides"]
UI[btns[-1]]["command"]()
print("ik field:", UI[f["options.ik_joints"].control].get("text"))
sp=[n for n,v in UI.items() if v.get("kind")=="button" and v.get("label")=="Spread"]
UI[sp[-2]]["command"](); print("fk field after Spread 4:", UI[f["options.fk_joints"].control].get("text"))
bt.apply_form()
g=[g for g in guides.module_groups() if guides.read(g)["name"]=="tail"][0]
print("saved:", {k: guides.read(g)["settings"]["options"][k] for k in ("type","fk_joints","ik_joints")})
# bad joint numbers
UI["B_List"]["selectIndexedItem"]=[bt._rows["B_"].index(g)+1]; bt._fill_form()
cmds.textField(bf._form["B_"]["options.ik_joints"].control, edit=True, text="1, 9")
try: bt._read_form()
except ValueError as e: print("bad numbers ->", e)

# ---- keep shapes
setcalls=[]
curves.read_shape=lambda n: _n(n).attrs.get("shape", [{"points":[[1,0,0]]}])
curves.set_shape=lambda n, data, style=None: (setcalls.append(n.split("|")[-1]), _n(n).attrs.__setitem__("shape", data))
curves.read_style=lambda n: {}
curves.curve_shapes=lambda n: [c for c in (cmds.listRelatives(n, shapes=True, fullPath=True) or []) if cmds.nodeType(c)=="nurbsCurve"]
bld.build_all(180)
print("built tail ctrls:", sorted(n.name for n in S.nodes if n.name.startswith("tail") and n.name.endswith("_ctrl")))
S.get("tail_02_FK_ctrl").attrs["shape"]=[{"points":[[5,5,5]]}]          # user changed this one
bld.rebuild_selected(["C:tail"], 180)
print("restored on rebuild:", setcalls, "| shape now:", S.get("tail_02_FK_ctrl").attrs.get("shape"))
setcalls.clear(); bld.back_to_guides(force=True); bld.build_all(180)
print("restored after back+build:", setcalls)
bld.forget_shapes([g for g in guides.module_groups() if guides.read(g)["name"]=="tail"])
setcalls.clear(); bld.rebuild_selected(["C:tail"], 180); print("after forget:", setcalls)
