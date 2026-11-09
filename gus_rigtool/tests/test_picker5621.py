# 5.6.21: picker - more shapes (their outline used for clicks), frames (a group with a title: behind the buttons,
# its title selects its buttons, hidden with them), text, order (front / back / up / down, frames stay behind),
# lock (can't move), copy / paste style, centre on the page, move to another page, clothes on their own page,
# small finger buttons beside each hand on Body
import os, sys
exec(open("fakemaya.py").read())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import pickmodel as PM
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def b(x, y, w=20.0, h=20.0, i=None, **k):
    it = {"id": i or "%s_%s" % (x, y), "kind": "select", "nodes": [k.pop("node", "n")], "x": float(x),
          "y": float(y), "w": w, "h": h, "shape": "round", "points": [], "rgb": [0.5, 0.5, 0.5], "label": "",
          "twin": None}
    it.update(k)
    return it
check("shapes: pill, ring, triangle, hexagon, star, plus, four arrows",
      all(s in PM.SHAPES for s in ("pill", "ring", "triangle", "hexagon", "star", "plus", "arrow up", "arrow down",
                                   "arrow left", "arrow right")))
tri = b(0, 0, 20, 20, shape="triangle")
check("a triangle: its tip's corner isn't it, its middle is", not PM.contains(tri, 1, 1) and PM.contains(tri, 10, 15))
star = b(0, 0, 20, 20, shape="star")
check("a star: between the points isn't it", PM.contains(star, 10, 10) and not PM.contains(star, 2, 3))
arrow = b(0, 0, 20, 20, shape="arrow right")
check("an arrow right: the tip is, above the shaft isn't", PM.contains(arrow, 18, 10) and not PM.contains(arrow, 3, 2))

page = {"name": "Body", "width": 400.0, "height": 400.0, "items": [b(100, 100, i="a"), b(140, 100, i="c"),
                                                                   b(300, 300, i="far")]}
fr = PM.group_frame(page, page["items"][:2], "Left Arm")
check("Group: a frame round them with room for its title, at the back", page["items"][0] is fr and
      fr["x"] < 100 and fr["y"] + PM.TITLE_H < 100 and fr["label"] == "Left Arm")
check("its buttons: a and c, not far", sorted(i["id"] for i in PM.frame_members(page, fr)) == ["a", "c"])
check("click on its title: the frame; on its body (in use): the button there, else nothing",
      PM.hit_any(page, fr["x"] + 5, fr["y"] + 3) is fr and PM.hit_any(page, 105, 105)["id"] == "a" and
      PM.hit_any(page, fr["x"] + 3, fr["y"] + fr["h"] - 2) is None and
      PM.hit_any(page, fr["x"] + 3, fr["y"] + fr["h"] - 2, editing=True) is fr)
fr["hidden"] = True
check("hidden: the frame and its buttons can't be clicked (in use), the others can",
      PM.hit_any(page, 105, 105) is None and PM.hit_any(page, 305, 305)["id"] == "far" and
      PM.hit_any(page, 105, 105, editing=True)["id"] == "a")
fr["hidden"] = False
PM.order(page, [page["items"][-1]], "back")
check("Send to back: behind the buttons - but frames stay behind everything",
      [i["id"] for i in page["items"]] == [fr["id"], "far", "a", "c"])
PM.order(page, [i for i in page["items"] if i["id"] == "far"], "up")
check("Up one", [i["id"] for i in page["items"]] == [fr["id"], "a", "far", "c"])
PM.order(page, [i for i in page["items"] if i["id"] == "a"], "front")
check("Bring to front", [i["id"] for i in page["items"]][-1] == "a")
a = [i for i in page["items"] if i["id"] == "a"][0]
a["locked"] = True
PM.move([a], 50, 0)
PM.resize([a], 2.0)
check("locked: it doesn't move or resize", a["x"] == 100.0 and a["w"] == 20.0)
a["locked"] = False
t = PM.add_text(page, "LEFT ARM", 10, 10)
PM.resize([t], 1.5)
check("text: a text item; Bigger grows its letters", t["kind"] == "text" and abs(t["size"] - 21.0) < 1e-6)
src = b(0, 0, 30, 18, shape="star", rgb=[1, 0, 0], i="src")
dst = b(200, 200, 10, 10, i="dst")
PM.paste_style([dst], PM.copy_style(src))
check("paste style: shape, colour and size, the middle where it was", dst["shape"] == "star" and dst["rgb"] == [1, 0, 0]
      and dst["w"] == 30 and dst["x"] + 15 == 205)
c = [i for i in page["items"] if i["id"] == "c"][0]
PM.centre_on_page(page, [c])
check("centre on the page (across)", c["x"] + c["w"] * 0.5 == 200)
picker = {"pages": [page]}
PM.move_to_page(picker, page, [c], "Clothes")
check("move to a page (made): same place, gone from this one", picker["pages"][1]["name"] == "Clothes" and
      picker["pages"][1]["items"][0] is c and c not in page["items"])

# auto: clothes / fingers
rig = []
def r(node, pos, side):
    rig.append({"node": node, "pos": pos, "pts": [(pos[0] - 1, pos[1] - 1), (pos[0] + 1, pos[1] + 1)], "pts3": [],
                "size": 2.0, "rgb": [0.5, 0.5, 0.5], "side": side, "twin": None, "depth": 3})
r("Collar_fol_01_ctrl", (0, 140, 5), "C"); r("Head_ctrl", (0, 160, 0), "C"); r("L_Brow_ctrl", (3, 165, 5), "L")
r("L_hand_ctrl", (40, 100, 0), "L"); r("R_hand_ctrl", (-40, 100, 0), "R"); r("Hips_ctrl", (0, 90, 0), "C")
r("L_index_01_FK_ctrl", (45, 95, 0), "L"); r("L_index_02_FK_ctrl", (47, 93, 0), "L")
r("R_index_01_FK_ctrl", (-45, 95, 0), "R")
with mock.patch.object(PM, "_tweaks", return_value=set()), \
        mock.patch.object(PM.A, "face_controls", return_value=set(["Collar_fol_01_ctrl", "L_Brow_ctrl"])):
    pages = PM.classify(rig)
    check("the collar on Clothes, not Face (even near the head)", [x["node"] for x in pages["Clothes"]] ==
          ["Collar_fol_01_ctrl"] and "Collar_fol_01_ctrl" not in [x["node"] for x in pages["Face"]])
    got = PM.auto("", rig=rig, points=[])
names = [p["name"] for p in got["pages"]]
body = [p for p in got["pages"] if p["name"] == "Body"][0]
fing = [i for i in body["items"] if "index" in i["nodes"][0]]
hand = [i for i in body["items"] if i["nodes"][0] == "L_hand_ctrl"][0]
print(names, len(fing))
check("pages: Body, Face, Hands, Clothes", names[:4] == ["Body", "Face", "Hands", "Clothes"])
check("fingers also on Body: small, under their hand", len(fing) == 3 and
      all(f["w"] < 20 for f in fing) and min(f["y"] for f in fing if f["nodes"][0].startswith("L_")) > hand["y"])
print("%d/%d passed" % (sum(ok), len(ok)))
