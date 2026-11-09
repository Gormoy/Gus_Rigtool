exec(open("fakemaya.py").read())
import gus_rigtool, tempfile
gus_rigtool.ROOT=tempfile.mkdtemp()
from gus_rigtool.builder import build as bld, guides, skin_keep
# --- tiny skin support for the fake
SK={}
def skinCluster(*args, **k):
    if k.get("query"):
        s=SK[args[0]]
        if k.get("geometry"): return [s["mesh"]]
        if k.get("influence"): return list(s["inf"])
        if k.get("maximumInfluences"): return 4
        if k.get("skinMethod"): return 0
        return None
    if k.get("edit"):
        if k.get("unbind"):
            s=SK.pop(args[0]); delete(args[0])
            S.conns=[c for c in S.conns if not (c[2].name==args[0])]
        return None
    flat=[]
    for a in args: flat += a if isinstance(a,(list,tuple)) else [a]
    joints, mesh = flat[:-1], flat[-1]
    n=S.create("skinCluster", k.get("name","skinCluster1"))
    SK[n.name]={"mesh":mesh,"inf":[_n(j).name for j in joints]}
    for j in joints: connectAttr(_n(j).name+".worldMatrix", n.name+".matrix[0]", force=True) if False else S.conns.append((_n(j),"worldMatrix[0]",n,"matrix"))
    return [n.name]
cmds.skinCluster=skinCluster
cmds.deformerWeights=lambda *a,**k: print("    deformerWeights", "export" if k.get("export") else "import", a[0])
cmds.file=lambda **k: ""
cmds.listHistory=lambda n,**k: [x for x,s in SK.items() if s["mesh"]==n or _n(s["mesh"]) is _n(n)]
bld.biped(180); bld.build_all(180)
geo=S.create("transform","body_geo"); S.create("mesh","body_geoShape",geo)
skinCluster("L_humerus_jnt","L_radius_jnt","spine_jnt","body_geo", name="body_skin")
print("skinned to:", SK["body_skin"]["inf"])
# rebuild only the left arm (fingers follow)
print("dependents of L:arm:", bld.dependents(["L:arm"]))
before=len(S.nodes)
bld.rebuild_selected(["L:arm"],180)
print("nodes before/after:", before, len(S.nodes), "| L arm joint exists:", bool(S.find("L_humerus_jnt")), "| R arm untouched:", bool(S.find("R_humerus_jnt")))
print("skin after rebuild:", {k:v["inf"] for k,v in SK.items()})
# a duplicate-name check: nothing named twice
from collections import Counter
dups=[n for n,c in Counter(x.name for x in S.nodes if x.type in ("joint","transform")).items() if c>1]
print("duplicate names:", dups[:5])
# back to guides keeps skin, build brings it back
bld.back_to_guides(); print("after back: skins", list(SK), "| pending:", skin_keep.pending())
bld.build_all(180); print("after build: skins", {k:v["inf"] for k,v in SK.items()}, "| pending:", skin_keep.pending())
# guide modes
guides.set_mode(True, 180); g=[g for g in guides.module_groups() if guides.read(g)["id"]=="L:arm"][0]
print("free: radius guide parent =", S.get("L_radius_gde").parent.name)
guides.set_mode(False, 180); print("linked: radius guide parent =", S.get("L_radius_gde").parent.name)
