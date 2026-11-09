# Face module: biped and quadruped templates, every part on
import traceback
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, guides, modules
nodes = lambda suf: sorted(n.name for n in S.nodes if n.name.endswith(suf))
for template in ("biped", "quadruped"):
    for g in guides.module_groups():
        guides.delete(g)
    getattr(bld, template)(100)
    for g in guides.module_groups():
        i = guides.read(g)
        if i["type"] == "face":
            s = modules.MODULES["face"].complete(i["settings"])
            s["options"].update(lip_detail=True, upper_jaw=True, tongue=True, ears=True)
            guides.save_settings(g, s); guides.update(g, modules.MODULES["face"], s, 100)
            print(template, "face guides:", len(guides.read([x for x in guides.module_groups() if guides.read(x)["type"] == "face"][0])["guides"]))
    try:
        bld.build_all(100)
    except Exception:
        traceback.print_exc(); raise SystemExit
    face_j = [n for n in nodes("_jnt") if any(k in n for k in ("jaw", "chin", "snout", "lip", "eye", "lid", "brow", "cheek",
                                                                "nose", "nostril", "ear", "tongue", "teeth"))]
    print(template, "face joints (%d):" % len(face_j), face_j)
    ctrls = [n for n in nodes("_ctrl") if any(k in n for k in ("jaw", "mouth", "lip", "eye", "lid", "brow", "cheek", "nose",
                                                                "nostril", "ear", "tongue", "teeth"))]
    print(template, "face controls (%d):" % len(ctrls), ctrls)
    print(" jaw attrs:", [a for a in S.get("jaw_ctrl").user if not a.startswith("gus")])
    print(" lip follow:", {c: S.get(c).user.get("jaw_follow") for c in ctrls if "lip" in c})
    print(" eye target attrs:", [a for a in S.get("L_eye_target_ctrl").user])
    print(" eyes target space:", "space" in S.get("eyes_target_ctrl").user, "| ear curl:", "curl" in S.get("L_ear_01_FK_ctrl").user)
    print(" aim constraints:", len([n for n in S.nodes if n.type == "aimConstraint"]))
    bld.back_to_guides(force=True)
    print(" back: joints left", len([n for n in S.nodes if n.type == "joint"]))
from collections import Counter
print("dupes:", [n for n, c in Counter(x.name for x in S.nodes if x.type in ("joint", "transform")).items() if c > 1][:5])
