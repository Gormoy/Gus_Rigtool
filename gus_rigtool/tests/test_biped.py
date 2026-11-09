import traceback, json, os, tempfile
exec(open("fakemaya.py").read())
import numpy as np
from gus_rigtool.builder import build as bld, guides, modules, limb, names
bld.biped(180)
print("preview names:", len(bld.preview()))
def setopt(mid, key, value, section="options"):
    for g in guides.module_groups():
        i=guides.read(g)
        if i["id"]==mid:
            s=modules.MODULES[i["type"]].complete(i["settings"]); s[section][key]=value; guides.save_settings(g,s)
            guides.update(g, modules.MODULES[i["type"]], s, 180)
for spine in ("ik_spline","ribbon"):
    setopt("C:spine","type",spine)
    for side in "LR":
        for m in ("arm","leg"):
            setopt("%s:%s"%(side,m),"stretch",True); setopt("%s:%s"%(side,m),"bendy",True); setopt("%s:%s"%(side,m),"ik_orient","joint")
        setopt("%s:fingers"%side,"curl_attrs",True); setopt("%s:fingers"%side,"metacarpal",True)
    setopt("C:root","root_joint",True)
    try:
        bld.build_all(180)
    except Exception:
        traceback.print_exc(); raise SystemExit
    print(spine, "twist joints:", len([n for n in S.nodes if "_twist_" in n.name and n.type=="joint"]),
          "| bend ctrls:", len([n for n in S.nodes if n.name.endswith("_bend_ctrl")]),
          "| L settings attrs:", [a for a in S.get("L_wrist_settings_ctrl").user if not a.startswith("gus")])
    # matching
    cmds.select("L_wrist_IK_ctrl"); limb.match_selected("fk"); print("  match fk ok, ikfk =", getAttr("L_wrist_settings_ctrl.ikfk"))
    cmds.select("L_humerus_FK_ctrl"); limb.match_selected("ik"); print("  match ik ok, ikfk =", getAttr("L_wrist_settings_ctrl.ikfk"))
    cmds.select("R_ankle_IK_ctrl"); limb.match_selected("toggle"); print("  toggle ok, R leg ikfk =", getAttr("R_ankle_settings_ctrl.ikfk"))
    ok = bld.back_to_guides(force=True)
    print("  back:", ok, "| joints left:", len([n for n in S.nodes if n.type=="joint"]), "| guides visible:", S.get("guides_grp").attrs["visibility"])
# names change & guides update
g=[g for g in guides.module_groups() if guides.read(g)["id"]=="C:neck"][0]
i=guides.read(g); s=modules.MODULES["neck"].complete(i["settings"]); s["names"]["chain"]=["neck_01","neck_02"]; s["options"]["joint_count"]=2
new=guides.update(g, modules.MODULES["neck"], s, 180); print("neck guides now:", sorted(guides.read(new)["guides"]))
# naming pattern
_SETTINGS[names.SETTINGS_KEY]={"pattern":"{side}{part}{type}","centre":"C_","suffixes":{"jnt":"_JNT"},"variants":{}}
print("custom names:", names.make("C","spine","jnt"), names.make("L","humerus","ctrl","fk"))
_SETTINGS.pop(names.SETTINGS_KEY)
# template round trip
p=os.path.join(tempfile.mkdtemp(),"t.json"); n=bld.save_template(p,180); print("template modules:", n)
for g in guides.module_groups(): guides.delete(g)
print("loaded:", bld.load_template(p), "| neck roles:", sorted(guides.read([g for g in guides.module_groups() if guides.read(g)["id"]=="C:neck"][0])["guides"]))
bld.build_all(180); print("rebuilt from template OK; neck joints:", [n.name for n in S.nodes if n.type=="joint" and n.name.startswith("C_neck")])
