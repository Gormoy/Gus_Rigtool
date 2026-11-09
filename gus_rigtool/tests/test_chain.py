import traceback
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, guides, modules, limb, chain
ch = modules.MODULES["chain"]
print("parse:", chain.parse_joints("all", 7, "all", 6), chain.parse_joints("auto", 7), chain.parse_joints("1-3, 7", 7), chain.spread(4, 7))
try: chain.parse_joints("9", 7)
except ValueError as e: print("bad:", e)
bld.biped(180)
def setopts(mid, **kw):
    for g in guides.module_groups():
        i=guides.read(g)
        if i["id"]==mid:
            s=modules.MODULES[i["type"]].complete(i["settings"])
            for k,v in kw.items():
                sec, key = k.split("__") if "__" in k else ("options", k)
                s[sec][key]=v
            guides.save_settings(g,s); guides.update(g, modules.MODULES[i["type"]], s, 180)
g=bld.add_module("chain","C","tail",180)
s=guides.read(g)["settings"]; s["attach"]="spine:hips"; guides.save_settings(g,s)
e=bld.add_module("chain","L","ear",180)
s=guides.read(e)["settings"]; s["attach"]="neck:head"; s["names"]["count"]=3; guides.save_settings(e,s)
guides.update(e, ch, s, 180)
guides.mirror([x for x in guides.module_groups() if guides.read(x)["id"]=="L:ear"][0], ch, 180)
print("tail guides:", sorted(guides.read([x for x in guides.module_groups() if guides.read(x)["id"]=="C:tail"][0])["guides"]))
for typ in chain.TYPES:
    setopts("C:tail", type=typ, ik_joints="1, 4, 7", fk_joints="1, 3, 5", curl=True, volume=True, exact_match=True)
    setopts("L:ear", type=typ); setopts("R:ear", type=typ, tweaks=False)
    try:
        bld.build_all(180)
    except Exception:
        traceback.print_exc(); raise SystemExit
    nodes = lambda suf: sorted(n.name for n in S.nodes if n.name.endswith(suf))
    print("\n==", typ)
    print(" bind:", [n for n in nodes("_jnt") if n.startswith("tail")])
    print(" FK ctrls:", [n for n in nodes("_FK_ctrl") if "tail" in n], "| IK:", [n for n in nodes("_IK_ctrl") if "tail" in n])
    print(" tweaks:", len([n for n in nodes("_tweak_ctrl") if "tail" in n]), "| R ear tweaks:", len([n for n in nodes("_tweak_ctrl") if n.startswith("R_ear")]))
    st = S.get("tail_settings_ctrl")
    print(" settings attrs:", [a for a in st.user if not a.startswith("gus")])
    print(" ear bind:", [n for n in nodes("_jnt") if "ear" in n])
    if typ != "fk":
        cmds.select("tail_04_IK_ctrl"); limb.match_selected("fk"); print(" match fk -> ikfk", getAttr("tail_settings_ctrl.ikfk"))
        cmds.select("tail_01_FK_ctrl"); limb.match_selected("ik"); print(" match ik -> ikfk", getAttr("tail_settings_ctrl.ikfk"))
        cmds.select("L_ear_02_tweak_ctrl"); limb.match_selected("toggle"); print(" toggle ear ->", getAttr("L_ear_settings_ctrl.ikfk"))
    print(" preview names count:", len(bld.preview()))
    bld.back_to_guides(force=True)
    print(" back: joints left", len([n for n in S.nodes if n.type=="joint"]))
