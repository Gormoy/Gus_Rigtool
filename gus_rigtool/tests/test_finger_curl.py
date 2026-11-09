# Fingers: the curl drives every joint of every finger (not a metacarpal); spread is centred on the fingers
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, guides, modules
def run(meta, fingers, joints):
    S.__init__()
    bld.biped(180)
    for g in guides.module_groups():
        i = guides.read(g)
        if i["type"] == "fingers":
            s = modules.MODULES["fingers"].complete(i["settings"])
            s["options"].update(curl_attrs=True, metacarpal=meta, finger_count=len(fingers))
            s["names"]["fingers"] = fingers; s["names"]["joints"] = joints
            guides.save_settings(g, s); guides.update(g, modules.MODULES["fingers"], s, 180)
    bld.build_all(180)
    curl = {}
    spread = {}
    for s_, sa, d, da in S.conns:
        if sa.endswith("_curl") and d.name.startswith("L_"):
            curl.setdefault(sa, []).append(d.name)
        if s_.type == "multDoubleLinear" and s_.name.startswith("L_") and "_spread" in s_.name:
            spread[s_.name] = round(s_.attrs.get("input2", 0), 3)
    print("meta=%s fingers=%s joints=%d" % (meta, fingers, joints))
    for k in sorted(curl):
        print("  ", k, "->", sorted(curl[k]))
    print("   spread weights:", sorted(spread.items()))
run(False, ["thumb", "index", "middle", "ring", "pinky"], 3)
run(False, ["index", "middle", "ring", "pinky"], 2)
run(True, ["thumb", "index", "middle"], 2)
