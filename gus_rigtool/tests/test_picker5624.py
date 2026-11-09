# 5.6.24: the picker - normalize (a page far too big: sane units, fitted), text that grows past the edge / on
# everything (texts, frame titles), frame titles placed / sized / aligned, the meshes' outline from any namespace
# (cells sized to the page), a picture kept in the picker, Switches / Face sliders pages made from the rig, space
# switches (no jump), keyed state, hierarchy lines, my sets, templates / style rules, chain numbers, line / arc,
# mirror the layout, one page to a file, your keys, the unsure curves' ignore list, mirror pairs (a link wins
# when it's the one at the mirrored place); the window: a toggle flips on click, seen from behind, find, help,
# per-page view, animator lock, the page as a picture
import os, sys, tempfile, json
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
import fakeqt
fakeqt.install()
import pickrig
from gus_animtool import anim as A, pickmodel as PM, pickmore as PX
_opts = {"library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
cmds.undoInfo = mock.MagicMock()
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def b(x, y, w=20.0, h=20.0, i=None, **k):
    it = {"id": i or "b%s_%s" % (x, y), "kind": "select", "nodes": [k.pop("node", "n%s_%s" % (x, y))],
          "x": float(x), "y": float(y), "w": w, "h": h, "shape": "round", "points": [], "rgb": [0.5, 0.5, 0.5],
          "label": k.pop("label", "btn"), "twin": None}
    it.update(k)
    return it

# --- normalize: the Hare's Body page (buttons ~190 units, the page 4000 wide)
big = {"name": "Body", "width": 4200.0, "height": 5200.0,
       "items": [b(1000 + 300 * k, 900 + 250 * k, 190, 140, i="g%d" % k) for k in range(6)] +
       [{"id": "t1", "kind": "text", "label": "BODY", "x": 900.0, "y": 600.0, "w": 400.0, "h": 120.0,
         "size": 140.0}],
       "outline": {"cell": 40.0, "runs": [[30, 25, 40]]},
       "picture": {"x": 800.0, "y": 500.0, "w": 2000.0, "h": 3000.0, "data": "", "alpha": 0.5}}
check("needs normalizing: buttons ~190 units / the page far bigger than them", PX.needs_normalize(big))
k = PX.normalize(big)
g0 = PM.by_id(big, {"g0"})[0]
check("normalized: the usual button 24 units, everything from the margin, the page fitted (k %.3f)" % k,
      abs(PM.typical_size([i for i in big["items"] if i["kind"] == "select"]) - 24.0) < 0.5 and
      PM.bounds(big["items"])[0] == PM.MARGIN and big["width"] < 400 and not PX.needs_normalize(big))
check("... text, outline and picture came along",
      abs(PM.by_id(big, {"t1"})[0]["size"] - 140 * k) < 0.1 and abs(big["outline"]["cell"] - 40 * k) < 1e-3 and
      "ox" in big["outline"] and abs(big["picture"]["w"] - 2000 * k) < 0.1)
check("a sane page doesn't need it", not PX.needs_normalize(big) and
      not PX.needs_normalize({"items": [b(16, 16), b(50, 16)], "width": 100, "height": 60}))

# --- text: fit to text, bigger on everything
row = [b(0, 0, 20, 14, label="Shoulder FK"), b(50, 0, 80, 14, label="ok")]
check("fit to text: the narrow one grows, the wide one stays", PX.fit_to_text(row) == 1 and row[0]["w"] > 40 and
      row[1]["w"] == 80)
txt = {"id": "t", "kind": "text", "label": "T", "x": 0, "y": 0, "w": 20, "h": 20, "size": 14.0}
fr = {"id": "f", "kind": "frame", "label": "Arm", "x": 0, "y": 0, "w": 100, "h": 80}
btn = b(0, 0, 20, 20)
PX.text_bigger([txt, fr, btn], 1.5)
check("Text + on a text (its size), a frame title, a button", txt["size"] == 21.0 and
      fr["text_size"] == round(PM.TITLE_SIZE * 1.5, 2) and abs(btn["text_size"] - 20 * 0.56 * 1.5) < 0.01)

# --- frame titles
fr2 = dict(fr, text_size=24.0)
check("a bigger title: a taller bar", PM.title_h(fr2) == 36.0 and PM.title_h(dict(fr, text_size=0)) == PM.TITLE_H)
fr2["title_pos"] = "above"
check("title above the frame: clicked there, not inside", PM.on_title(fr2, 50, -10) and not PM.on_title(fr2, 50, 5))
fr2["title_pos"] = "hidden"
check("hidden title: no title to click", PM.title_rect(fr2) is None and not PM.on_title(fr2, 50, 5))
pg = {"items": [dict(fr, title_pos="below"), b(30, 30)]}
check("hit: a title below the frame selects the frame", PM.hit_any(pg, 50, 85) is pg["items"][0])

# --- outline from the meshes, any namespace
with mock.patch.object(cmds, "ls", side_effect=lambda *a, **k: ["skin1"] if k.get("type") == "skinCluster" else []), \
        mock.patch.object(cmds, "skinCluster", create=True, side_effect=lambda s, **k: ["|rig|Hips_jnt"] if
                          k.get("influence") else ["|Geo_Hare_07:body|Geo_Hare_07:bodyShape"]), \
        mock.patch.object(cmds, "listRelatives", side_effect=lambda n, **k: ["|Geo_Hare_07:body"]):
    got = PX.rig_meshes("")
check("meshes: a model referenced as Geo_Hare_07: skinned to the rig's joints counts", got == ["|Geo_Hare_07:body"])
RIG = pickrig.rig()
POS = dict((r["node"], r["pos"]) for r in RIG)
pos_of = lambda n: POS.get(n)
page = {"name": "Body", "width": 400.0, "height": 600.0, "items": []}
for nm in ("head_ctrl", "cog_ctrl", "L_arm_ik_ctrl", "R_arm_ik_ctrl"):
    page["items"].append(b(10 * POS[nm][0] + 200 - 10, -10 * POS[nm][1] + 350 - 10, node=nm, i=nm))
pts = [(x * 0.25, y * 0.25, 0.0) for x in range(-30, 31) for y in range(0, 85)]
check("outline: made, cells sized to the page (~1/160 of it, never under 2)", PX.page_outline(page, pts, pos_of)
      and abs(page["outline"]["cell"] - max(2.0, max(PM.page_size(page)) / 160.0)) < 1e-6)
cols, rows, x0, y0 = PX.outline_grid(page["outline"])
check("... drawn as one small picture (%d x %d)" % (cols, rows), cols > 5 and rows > 5)
fit = PM.fit_view(page["items"], pos_of)
rect = PX.picture_rect_from_camera(fit, (0.0, 10.0), 8.0, 20.0)
check("front picture: where the camera's frame lands on the page", abs(rect["x"] - (10 * -4 + 200)) < 1e-6 and
      abs(rect["y"] - (-10 * 20 + 350)) < 1e-6 and rect["w"] == 80.0 and rect["h"] == 200.0)
PX.set_picture(page, b"\x89PNGfake", rect, kind="capture", alpha=0.4)
check("the picture is kept in the picker (the animators get it)", PX.picture_bytes(page) == b"\x89PNGfake" and
      json.loads(json.dumps(page))["picture"]["alpha"] == 0.4)

# --- the rig in the scene
for r in RIG:
    t = cmds.createNode("transform", name=r["node"])
    cmds.createNode("nurbsCurve", name=r["node"] + "Shape", parent=t)
PM.read_rig = lambda ns=None: pickrig.rig()
gear = "L_arm_settings_ctrl"
cmds.addAttr(gear, longName="ikfk", attributeType="double", minValue=0, maxValue=1, keyable=True)
cmds.addAttr(gear, longName="Fingers_Vis", attributeType="bool", keyable=True)
cmds.addAttr(gear, longName="follow", attributeType="enum", enumName="World:Chest:Head", keyable=True)
cmds.addAttr(gear, longName="stretch", attributeType="double", minValue=0, maxValue=1, keyable=True)
found = PX.switch_attrs([gear])
check("switches found: ikfk, Fingers_Vis (toggles), follow (a space menu) - not stretch",
      sorted((a, k) for _c, a, k in found) == [("Fingers_Vis", "toggle"), ("follow", "enum"), ("ikfk", "toggle")])
pk = {"version": PM.VERSION, "pages": [{"name": "Body", "width": 400.0, "height": 400.0, "items": []}]}
sw = PX.switches_page(pk, "", controls=[gear])
kinds = sorted(i["kind"] for i in sw["items"])
check("Switches page: a frame for the gear, 2 toggles and a space menu", kinds == ["enum", "frame", "toggle",
                                                                                   "toggle"])
mine = b(300, 300, label="mine")
sw["items"].append(mine)
PX.switches_page(pk, "", controls=[gear])
check("made again: the same (not doubled), your own button stays", sum(1 for p in pk["pages"]
                                                                        if p["name"] == "Switches") == 1 and
      mine in sw["items"] and len([i for i in sw["items"] if i.get("kind") == "toggle"]) == 2)
face = "jaw_ctrl"
cmds.addAttr(face, longName="Smile_L", attributeType="double", minValue=0, maxValue=1, keyable=True)
cmds.addAttr(face, longName="Angry", attributeType="double", minValue=-1, maxValue=1, keyable=True)
fs = PX.face_sliders_page(pk, "", controls=[face])
check("Face sliders page: Smile_L and Angry as sliders in their ranges",
      sorted((i["attr"], i["min"], i["max"]) for i in fs["items"] if i.get("kind") == "slider") ==
      [("Angry", -1, 1), ("Smile_L", 0, 1)])
en = [i for i in sw["items"] if i.get("kind") == "enum"][0]
check("space menu: its choices", en["choices"] == ["World", "Chest", "Head"])
with mock.patch.object(cmds, "xform", side_effect=lambda *a, **k: [1.0] * 16 if k.get("query") else None) as xf:
    PX.set_enum(en, "", 2)
check("pick 'Head': set, the control put back where it was (no jump)", cmds.getAttr(gear + ".follow") == 2 and
      any(c.kwargs.get("matrix") and not c.kwargs.get("query") for c in xf.call_args_list))
with mock.patch.object(cmds, "keyframe", side_effect=lambda n, **k: 1 if "time" in k else 3):
    check("keyed state: keyed here and animated", PX.keyed_state("cog_ctrl", 5.0) == (True, True))
with mock.patch.object(cmds, "keyframe", side_effect=lambda n, **k: 0):
    check("... not animated", PX.keyed_state("cog_ctrl", 5.0) == (False, False))
items = [b(0, 0, node="hips", i="h"), b(0, 30, node="spine", i="s"), b(0, 60, node="chest", i="c")]
longs = {"h": "|rig|hips", "s": "|rig|hips|grp|spine", "c": "|rig|hips|grp|spine|off|chest"}
links = PX.hierarchy_links(items, lambda it: longs[it["id"]])
check("hierarchy lines: hips -> spine -> chest (through their groups)",
      sorted((a["id"], c["id"]) for a, c in links) == [("h", "s"), ("s", "c")])

# --- my sets, templates, rules, numbers, line / arc, mirror layout
PX.save_my_set("hare", "Brows", ["|rig|L_brow1_ctrl", "R_brow1_ctrl"])
check("my sets: kept per rig, names without paths", PX.my_sets("hare") == {"Brows": ["L_brow1_ctrl",
                                                                                     "R_brow1_ctrl"]} and
      PX.my_sets("other") == {})
PX.save_my_set("hare", "Brows", None)
check("... deleted", PX.my_sets("hare") == {})
check("ready-made templates", {"FK dot", "IK box", "Tweak dot"} <= set(PX.all_styles()))
its = [b(0, 0, node="L_arm_fk1_ctrl"), b(30, 0, node="L_tail_fol_02_ctrl"), b(60, 0, node="cog_ctrl")]
n = PX.apply_style_rules(its, [("*_fk*", "FK dot"), ("*_fol_*", "Tweak dot")])
check("style rules: FK -> FK dot, fol -> Tweak dot, cog untouched", n == 2 and its[0]["w"] == 18.0 and
      its[1]["shape"] == "ellipse" and its[2]["shape"] == "round")
ch = [b(0, 0, node="L_Ear_01_FK_ctrl"), b(0, 30, node="L_Ear_02_FK_ctrl"), b(0, 60, node="L_Ear_03_FK_ctrl"),
      b(0, 90, node="cog_ctrl", label="cog")]
check("chain numbers: Ear FK 1, 2, 3", PX.chain_numbers(ch) == 3 and [i["label"] for i in ch[:3]] ==
      ["Ear FK 1", "Ear FK 2", "Ear FK 3"] and ch[3]["label"] == "cog")
ln = [b(0, 0), b(13, 40), b(100, 10)]
PX.on_line(ln)
check("on a line: the middle one half way", abs(ln[1]["x"] - 50) < 1e-6 and abs(ln[1]["y"] - 5) < 1e-6)
arc = [b(0, 100), b(50, 100), b(100, 100)]
PX.on_arc(arc, 0.3)
check("on an arc: the middle one bows up", arc[1]["y"] < 100 - 20)
lay = {"name": "Body", "width": 200.0, "items": [b(90, 0, node="cog_ctrl"), b(130, 40, 30, 20, node="L_x_ctrl"),
                                                 b(10, 90, node="R_x_ctrl")]}
with mock.patch.object(A, "side_of", side_effect=lambda n: "L" if n.startswith("L_") else ("R" if
                                                                                         n.startswith("R_") else "C")):
    moved = PX.mirror_layout(lay, "L", mirror_name=lambda n: n.replace("L_", "R_"))
r_ = lay["items"][2]
check("mirror the layout: the right one mirrors the left across the middle buttons", moved == 1 and
      r_["w"] == 30 and abs((r_["x"] + 15) - (2 * 100 - 145)) < 1e-6 and r_["y"] == 40)

# --- one page to a file, keys, unsure
path = os.path.join(tempfile.mkdtemp(), "face_page.json")
PX.export_page({"name": "Face", "items": [b(0, 0, i="a", twin="b"), b(30, 0, i="b", twin="a")]}, path)
pk2 = {"version": PM.VERSION, "pages": [{"name": "Face", "items": []}]}
i = PX.import_page(pk2, path)
newp = pk2["pages"][i]
check("import a page: added as 'Face 2' (the name was taken), new ids, twins kept",
      [p["name"] for p in pk2["pages"]] == ["Face", "Face (copy)"] or newp["name"] in ("Face 2", "Face (copy)"))
check("... its twins point to each other", newp["items"][0]["twin"] == newp["items"][1]["id"] and
      newp["items"][0]["id"] != "a")
check("keys: 'ctrl + shift + g' -> Ctrl+Shift+G -> ungroup", PX.norm_key("ctrl + shift + g") == "Ctrl+Shift+G" and
      PX.action_for("Ctrl+Shift+G") == "ungroup" and PX.action_for("?") == "help")
PX.set_shortcuts({"group": "Ctrl+K"})
check("your keys: group on Ctrl+K", PX.action_for("Ctrl+K") == "group" and PX.action_for("Ctrl+G") is None)
PX.set_shortcuts({})
check("unsure curves: the ear lines and guides not listed",
      [PM.strip(x) for x in PX.drop_ignored(["|L_Ear_02_line_crv", "|L_brow_guide", "|Hat_ctrl2"])] ==
      ["Hat_ctrl2"])

# --- mirror pairs
rest = {"|L_Cape01_ctrl": (5.0, 10.0, 0.0), "|R_Cape01_ctrl": (-7.0, 10.0, 0.0), "|R_Cape02_ctrl": (-5.0, 10.0, 0.0),
        "|L_Cape02_ctrl": (7.0, 10.0, 0.0), "|L_Lone_ctrl": (3.0, 2.0, 0.0), "|Mid_ctrl": (0.0, 0.0, 0.0),
        "|Top_ctrl": (0.0, 20.0, 0.0)}
for n in rest:
    cmds.createNode("transform", name=n.strip("|"))
with mock.patch.object(A, "character_controls", return_value=list(rest)), \
        mock.patch.object(A, "_rest_pos", side_effect=lambda n: rest[A.long_name(n) or n]), \
        mock.patch.object(A, "position_twins", return_value={}):
    rep = dict((PM.strip(r["node"]), r) for r in PX.pair_report(""))
    check("pairs: L_Cape01's named twin isn't at the mirrored place - R_Cape02 is (suggested)",
          rep["L_Cape01_ctrl"]["problem"] == "off" and PM.strip(rep["L_Cape01_ctrl"]["suggest"]) == "R_Cape02_ctrl")
    check("... L_Lone has no twin; the middle ones aren't listed", rep["L_Lone_ctrl"]["problem"] == "none" and
          "Mid_ctrl" not in rep and "Top_ctrl" not in rep)
    A.link_twins("L_Cape01_ctrl", "R_Cape02_ctrl")
    check("linked: the link wins over the name (it's the one at the mirrored place)",
          PM.strip(A._name_twin(A.long_name("L_Cape01_ctrl"))) == "R_Cape02_ctrl")
    rep2 = dict((PM.strip(r["node"]), r) for r in PX.pair_report(""))
    check("... and it isn't listed any more", "L_Cape01_ctrl" not in rep2)

# --- the window
cmds.workspaceControl = mock.MagicMock(return_value="gusAnimtoolPicker")
cmds.scriptJob = mock.MagicMock()
from gus_animtool import pickerqt as Q
from fakeqt import Event, Qt, DRAWN, MENUS
w = Q.build()
cv = w.canvas
cv.frame(); cv.paintEvent(None)
check("the list folded by default", not w.list_btn.isChecked())
pg = w.page()
tg = PM.add_widget(pg, "toggle", gear, "ikfk", 5, 5)
cmds.setAttr(gear + ".ikfk", 0)
s = cv.to_screen(tg["x"] + tg["w"] / 2, tg["y"] + tg["h"] / 2)
cv.mousePressEvent(Event(s.x(), s.y(), Qt.LeftButton)); cv.mouseReleaseEvent(Event(s.x(), s.y(), Qt.LeftButton))
check("a toggle flips on click (5.6.23 selected its control instead)", cmds.getAttr(gear + ".ikfk") == 1)
L = [i for i in pg["items"] if i.get("nodes") == ["L_arm_ik_ctrl"]][0]
p0 = cv.to_screen(L["x"] + L["w"] / 2, L["y"] + L["h"] / 2)
w.toggle_behind(True)
p1 = cv.to_screen(L["x"] + L["w"] / 2, L["y"] + L["h"] / 2)
back = cv.to_page(p1)
check("seen from behind: the left arm's button on the other side of the window; clicks still find it",
      (p0.x() - cv.width() / 2) * (p1.x() - cv.width() / 2) < 0 and
      abs(back[0] - (L["x"] + L["w"] / 2)) < 1e-6 and PM.hit_any(pg, *back) is L)
cv.mousePressEvent(Event(p1.x(), p1.y(), Qt.LeftButton)); cv.mouseReleaseEvent(Event(p1.x(), p1.y(), Qt.LeftButton))
check("... clicked: the left arm selected", [A.short(n) for n in cmds.ls(selection=True)] == ["L_arm_ik_ctrl"])
del DRAWN[:]
cv.paintEvent(None)
check("... drawn", any(k == "fill" for k, _t in DRAWN))
w.toggle_behind(False)
found = w.find("arm_ik")
w.find_go()
check("find: the arm IK buttons lit, Enter selects them", len(found) >= 2 and
      sorted(A.short(n) for n in cmds.ls(selection=True)) == ["L_arm_ik_ctrl", "R_arm_ik_ctrl"])
w.hide_find()
w.toggle_help()
del DRAWN[:]
cv.paintEvent(None)
check("? : the keys drawn over the page", any(t and t.startswith("Picker - keys") for k, t in DRAWN if k == "text"))
w.toggle_help()
w.keep_view()
cv.scale, s0 = 3.0, cv.scale
w.set_page(1); w.set_page(0)
check("each page keeps its zoom", abs(cv.scale - 3.0) < 1e-6)
with mock.patch.object(PM, "rig_editable", return_value=False), mock.patch.object(PM, "where_from",
                                                                                   return_value="rig"):
    check("animator lock: a referenced rig's picker - no Edit", not w.can_edit())
    w.look["allow_edit"] = True
    check("... Look > let me edit: Edit", w.can_edit())
    w.look["allow_edit"] = False
w.edit_btn.setChecked(True)
page = w.page()
for it in page["items"]:
    for kk in ("x", "y", "w", "h"):
        it[kk] *= 9.0
page["width"], page["height"] = page["width"] * 9, page["height"] * 9
w.show_missing()
check("Edit: a page far too big - the Normalize bar", w.norm_btn.isVisible())
w.normalize_page()
w.show_missing()
check("... normalized: the bar goes", not w.norm_btn.isVisible())
picked = [i for i in page["items"] if i.get("kind") == "select"][:2]
w.picked = set(i["id"] for i in picked)
cv.keyPressEvent(Event(key=Qt.Key_G, mods=Qt.ControlModifier))
check("Ctrl+G (your keys): a group", any(PM.is_frame(i) for i in page["items"]))
it = w.set_script(None, "Key all", "cmds.setKeyframe(A.character_controls(ns))", 5, 5)
check("script button: made with its text and script", it["kind"] == "command" and it["label"] == "Key all")
w.make_switches_page()
check("Make the Switches page from the window: shown", w.page()["name"] == "Switches")
out = os.path.join(tempfile.mkdtemp(), "sheet.png")
check("the page as a picture", w.canvas.render_page(out) == out)
w.set_background(w.page(), 0.3, 0.2)
w.index = 0; w.set_page(0)
page = w.page()
page["picture"] = {"x": 0, "y": 0, "w": 50, "h": 50, "data": "", "alpha": 0.5}
w.set_background(page, 0.3, None, {"x": 1.0, "y": 2.0, "w": 60.0, "h": 70.0})
check("background: the picture's opacity and place", page["picture"]["alpha"] == 0.3 and page["picture"]["w"] == 60.0)
fr = [i for i in page["items"] if PM.is_frame(i)][0]
w.picked = {fr["id"]}
cv.paintEvent(None)
w.panel_set("title_pos", "above"); w.panel_set("align", "center")
w.panel_set("text_size", 20.0)
check("Item panel on a frame: title above, centred, size 20", fr.get("title_pos") == "above" and
      fr.get("align") == "center" and fr.get("text_size") == 20.0)
tx = PM.add_text(page, "BODY", 5, 5)
w.picked = {tx["id"]}
cv.paintEvent(None)
w.panel_set("text_size", 30.0)
check("... on a text: its own size", tx["size"] == 30.0)
w.edit_btn.setChecked(False)
fr["x"] += 3000.0                                    # away from the buttons
MENUS[:] = []
w.context_menu(None, fr["x"] + fr["w"] / 2, fr["y"] - 4)
check("right-click a frame's title (animating): select all in it, key, reset at the top",
      [lab for lab, _f in MENUS[0].actions][:3] == ["Select all in '%s'" % fr["label"], "Key  (S)", "Reset"])
with mock.patch.object(PX, "pair_report", return_value=[{"node": "|L_x", "twin": None, "how": None,
                                                         "problem": "none", "suggest": "|R_y", "dist": 0.1}]):
    from fakeqt import QDialog
    QDialog.answer[0] = 0
    w.pairs_dialog()
    check("Pairs window: the problem listed with its suggestion", w._pairs_ui["list"].count() == 1 and
          "suggested: R_y" in w._pairs_ui["list"].item(0).text())
txt = Q.diagnose(shot=False)
check("diagnose: pages, controls, pairs", "== mirror pairs" in txt and "-- Body" in txt)
print("%d/%d passed" % (sum(ok), len(ok)))
