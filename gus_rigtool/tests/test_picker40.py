# 4.0 picker: a four-legged rig gets the three-quarter side view (legs apart, head forward), no giant buttons,
# face controls by name on the Face page, the body silhouette from the meshes; a biped stays front view
import os, sys, math
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
import pickrig
from gus_animtool import pickmodel as PM

def ring(c, r, n=10):
    return [(c[0] + r * math.cos(2 * math.pi * i / n), c[1], c[2] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def quad():
    out = []
    def add(name, c, r, side="C", rgb=(1, .85, .2)):
        pts = ring(c, r)
        out.append({"node": name, "pos": list(c), "pts": [(p[0], p[1]) for p in pts], "pts3": pts, "size": 2 * r,
                    "rgb": list(rgb), "side": side, "twin": None, "depth": 3})
    add("cog_ctrl", (0, 10, 0), 3)
    for i, z in enumerate((-6, -3, 0, 3, 6)):
        add("spine_%02d_ctrl" % i, (0, 10, z), 2)
    add("head_ctrl", (0, 12, 10), 2)
    add("Tongue_01_IK_ctrl", (0, 11, 11), 6)                  # a huge curve, like on the screenshot
    for side, x, rgb in (("L", 3, (.2, .4, 1)), ("R", -3, (1, .25, .25))):
        for leg, z in (("front", 6), ("back", -6)):
            for j, y in enumerate((8, 5, 2)):
                add("%s_%s_leg_%02d_ctrl" % (side, leg, j), (x, y, z), 0.8, side, rgb)
            add("%s_%s_paw_IK_ctrl" % (side, leg), (x, 0.3, z + 1), 1.2, side, rgb)
        add("%s_eye_ctrl" % side, (x * 0.4, 13, 11), 0.3, side, rgb)
    return out

rig = quad()
print("view:", PM.pick_view(rig), "| biped:", PM.pick_view([dict(r, pos=list(r["pos"]) + [0.0] * (3 - len(r["pos"]))) for r in pickrig.rig()]))
body_pts = [(x, y, z) for z in range(-8, 12) for y in range(0, 13) for x in (-3, 0, 3) if (y > 7 or abs(z) > 4)]
pk = PM.auto("", rig=rig, points=body_pts)
names = {p["name"]: p for p in pk["pages"]}
print("pages:", [(p["name"], len(p["items"])) for p in pk["pages"]], "| view saved:", pk.get("view"))
body = names["Body"]
by = {i["nodes"][0]: i for i in body["items"]}
cx = lambda n: by[n]["x"] + by[n]["w"] / 2
cy = lambda n: by[n]["y"] + by[n]["h"] / 2
print("head forward (right of the tail end):", cx("head_ctrl") > cx("spine_00_ctrl"),
      "| front legs right of back legs:", cx("L_front_paw_IK_ctrl") > cx("L_back_paw_IK_ctrl"),
      "| left legs apart from right:", abs(cx("L_front_paw_IK_ctrl") - cx("R_front_paw_IK_ctrl")) > 10,
      "| paws below the spine:", cy("L_back_paw_IK_ctrl") > cy("spine_00_ctrl"))
its = body["items"]
print("overlaps:", sum(1 for i, a in enumerate(its) for b in its[i + 1:] if PM.overlaps(a, b)),
      "| biggest button vs usual:", round(max(i["w"] for i in its) / sorted(i["w"] for i in its)[len(its) // 2], 1))
face = names.get("Face")
print("tongue on the Face page:", bool(face) and any("Tongue" in i["nodes"][0] for i in face["items"]))
sil = body.get("outline")
print("silhouette:", bool(sil), "| rows:", len(set(r[0] for r in sil["runs"])) if sil else 0,
      "| inside the page:", all(r[1] >= 0 and (r[2] + 1) * sil["cell"] <= body["width"] + 1 for r in sil["runs"]) if sil else None)
bp = PM.auto("", rig=[dict(r, pos=list(r["pos"]) + [0.0] * (3 - len(r["pos"]))) for r in pickrig.rig()], points=[])
print("biped: view", bp.get("view"), "| body outline (no meshes):", "outline" in bp["pages"][0])
