# Quadruped template: build with hock and spring legs, toes, pelvis, auto scapula, stretch, bendy
import traceback
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, guides, modules, limb
bld.quadruped(100)
print("modules:", sorted(guides.read(g)["id"] for g in guides.module_groups()))
def setopts(mid, **kw):
    for g in guides.module_groups():
        i = guides.read(g)
        if i["id"] == mid:
            s = modules.MODULES[i["type"]].complete(i["settings"]); s["options"].update(kw)
            guides.save_settings(g, s); guides.update(g, modules.MODULES[i["type"]], s, 100)
nodes = lambda suf: sorted(n.name for n in S.nodes if n.name.endswith(suf))
for variant in ("hock", "spring"):
    for side in "LR":
        setopts("%s:back_leg" % side, ik_type=variant, pelvis=(variant == "hock"), toe_count=4, stretch=True,
                bendy=(variant == "spring"))
        setopts("%s:front_leg" % side, ik_type=variant, auto_scapula=True, toe_count=(3 if variant == "hock" else 0))
    try:
        bld.build_all(100)
    except Exception:
        traceback.print_exc(); raise SystemExit
    print("\n==", variant)
    print(" L back bind:", [n for n in nodes("_jnt") if n.startswith("L_") and n[2:].split("_")[0] in
                            ("pelvis", "femur", "tibia", "metatarsus", "ball")])
    print(" L front bind:", [n for n in nodes("_jnt") if n.startswith("L_") and n[2:].split("_")[0] in
                             ("scapula", "humerus", "radius", "metacarpus")])
    print(" controls L:", [n for n in nodes("_ctrl") if n.startswith("L_") and "toe" not in n])
    def chain_of(j):
        out = []
        node = S.get(j)
        while node:
            out.append(node.name)
            kids = [k for k in node.children if k.type == "joint" and not k.name.split("_")[1].startswith(("toeA", "toeB", "toeC", "toeD"))
                    and "toe" + "A" not in k.name]
            node = kids[0] if kids else None
        return out
    print(" back leg chain:", chain_of("L_pelvis_jnt" if S.find("L_pelvis_jnt") else "L_femur_jnt"))
    print(" front leg chain:", chain_of("L_scapula_jnt"))
    print(" FK ctrls:", [n for n in nodes("_FK_ctrl") if n.startswith("L_")])
    print(" joints under the back ball:", sorted(k.name for k in S.get("L_ball_jnt").children if k.type == "joint"))
    print(" toe chains under the back toe joint:", sorted(k.name for k in S.get("L_toe_jnt").children if k.type == "joint"))
    print(" toes L:", len([n for n in nodes("_jnt") if n.startswith("L_toe")]), "joints")
    st = S.get("L_ball_settings_ctrl") if S.find("L_ball_settings_ctrl") else None
    print(" settings ctrls:", nodes("_settings_ctrl"))
    for c in nodes("_settings_ctrl"):
        print("  ", c, [a for a in S.get(c).user if not a.startswith("gus")])
    print(" paw attrs:", [a for a in S.get("L_ball_IK_ctrl").user if not a.startswith("gus")] if S.find("L_ball_IK_ctrl") else "-")
    handles = sorted((n.name, n.attrs.get("solver", "")) for n in S.nodes if n.type == "ikHandle")
    print(" ik handles:", len(handles), [h for h, _ in handles if h.startswith("L_")])
    print(" spine joints:", nodes("_jnt")[:0] or [n for n in nodes("_jnt") if n.startswith("spine")], "| tail:", len([n for n in nodes("_jnt") if n.startswith("tail_") and "FK" not in n and "IK" not in n and "result" not in n and "drv" not in n]))
    for c in ("L_ball_IK_ctrl", "R_metatarsus_hock_ctrl" if variant == "hock" else "R_tibia_FK_ctrl"):
        cmds.select(c); limb.match_selected("toggle")
    print(" match toggles ok:", getAttr("L_ball_settings_ctrl.ikfk"))
    print(" preview names:", len(bld.preview()), "| clashes:", [n for _m, n, e in bld.preview() if False])
    bld.back_to_guides(force=True)
    print(" back: joints left", len([n for n in S.nodes if n.type == "joint"]))
from collections import Counter
print("dupes:", [n for n, c in Counter(x.name for x in S.nodes if x.type in ("joint", "transform")).items() if c > 1][:5])
