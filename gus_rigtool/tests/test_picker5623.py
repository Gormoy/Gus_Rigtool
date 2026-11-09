# 5.6.23: the visibility switches leave the head squash's hidden curve copies alone (and hide the ones already
# shown); the picker: controls in / out (Add selected where they sit seen from the front, on the page's scale, or
# at the mouse; missing onto their own page; take out / put back), the front view for the picked or a page, a page
# copy, label rules, colour by side, selection sets, toggles, pins (unpin all), your look (text size, theme...),
# the window: mode band, status, button list + search, the Item panel not writing onto newly picked buttons,
# Alt+click the twin
import os, sys, tempfile, json
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
import fakeqt
fakeqt.install()
import pickrig
from gus_animtool import anim as A, pickmodel as PM
from gus_rigtool.core import vis_switch as VS
_opts = {"library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
cmds.undoInfo = mock.MagicMock()
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- visibility: the squash's hidden copies
c = cmds.createNode("transform", name="L_Brow_ctrl")
own = cmds.createNode("nurbsCurve", name="L_Brow_ctrlShape", parent=c)
rider = cmds.createNode("nurbsCurve", name="L_Brow_ctrlShape_squashRider", parent=c)
cmds.setAttr(rider + ".visibility", 0)
check("a control's curves: its own, not the squash's hidden copy",
      [s.split("|")[-1] for s in VS._shapes(c)] == ["L_Brow_ctrlShape"])
sw = cmds.createNode("transform", name="Face_settings_ctrl")
cmds.addAttr(sw, longName="Brows", attributeType="bool", defaultValue=True)
cmds.connectAttr(sw + ".Brows", rider + ".visibility")      # what 5.6.22 did: the copy shown with the switch
cmds.setAttr(rider + ".visibility", 1)
n = VS.fix_riders()
check("repaired: the copy's switch disconnected, hidden again (1 fixed); its own curve untouched", n == 1 and
      not cmds.listConnections(rider + ".visibility", source=True, destination=False) and
      not cmds.getAttr(rider + ".visibility") and cmds.getAttr(own + ".visibility"))
check("run again: nothing to fix", VS.fix_riders() == 0)
src = open("../core/vis_switch.py").read()
check("Make / face switches / clothes / own switch / Remove all repair them too",
      src.count("fix_riders()") >= 5)

# --- label rules
check("label rules: words out, 01 -> 1, Capitals",
      PM.apply_rules("Eyelids fol 01", {"words": "fol, ribbon", "zeros": True, "caps": True}) == "Eyelids 1")
check("no rules: as before", PM.apply_rules("arm fk1") == "arm fk1")
PM.set_label_rules({"words": "fk", "zeros": False, "caps": True})
check("saved rules used by new buttons' text", PM.label_of("L_arm_fk1_ctrl") == "Arm 1" or
      PM.label_of("L_arm_fk_01_ctrl") == "Arm 01")
PM.set_label_rules({"words": "", "zeros": False, "caps": False})

# --- the rig in the scene
RIG = pickrig.rig()
POS = dict((r["node"], r["pos"]) for r in RIG)
for r in RIG:
    t = cmds.createNode("transform", name=r["node"])
    cmds.createNode("nurbsCurve", name=r["node"] + "Shape", parent=t)
PM.read_rig = lambda ns=None: pickrig.rig()
pos_of = lambda n: POS.get(n)
entry = lambda n: dict([(r["node"], r) for r in RIG])[PM.strip(n)]

# --- fit / place / settle
page = {"name": "Body", "width": 400.0, "height": 600.0, "items": []}
for nm in ("head_ctrl", "cog_ctrl", "L_arm_ik_ctrl"):
    x, y = 10 * POS[nm][0] + 200, -10 * POS[nm][1] + 350             # the page: 10 units a metre, centred
    page["items"].append({"id": PM.new_id(), "kind": "select", "nodes": [nm], "x": x - 10, "y": y - 10,
                          "w": 20.0, "h": 20.0, "shape": "round", "points": [], "rgb": [1, 1, 1], "label": nm,
                          "twin": None})
a, b, cc = PM.fit_view(page["items"], pos_of)
check("fit: page = a.X + b, -a.Y + c found back (10, 200, 350)", abs(a - 10) < 1e-6 and abs(b - 200) < 1e-6 and
      abs(cc - 350) < 1e-6)
check("fit: needs two buttons", PM.fit_view(page["items"][:1], pos_of) is None)
picker = {"version": PM.VERSION, "pages": [page]}
made = PM.add_controls(picker, page, ["neck_ctrl", "L_arm_fk1_ctrl", "head_ctrl"], "", pos_of=pos_of,
                       get_entry=entry)
nk = [i for i in made if i["nodes"] == ["neck_ctrl"]][0]
ny = nk["y"] + nk["h"] / 2
check("Add selected (front view): neck between the head and the hips, the arm on the left (right of the page "
      "middle); the head (already there) skipped", len(made) == 2 and -10 * POS['head_ctrl'][1] + 350 < ny < -10 * POS['cog_ctrl'][1] + 350 and
      [i for i in made if i["nodes"] == ["L_arm_fk1_ctrl"]][0]["x"] > 200)
ov = sum(1 for i, x in enumerate(page["items"]) for y in page["items"][i + 1:] if PM.overlaps(x, y))
check("nothing overlaps after", ov == 0)
row = PM.add_controls(picker, page, ["L_toe_ctrl"], "", at=(5.0, 7.0))
check("at the mouse: there", row and row[0]["x"] == 5.0 and row[0]["y"] == 7.0)
empty = {"name": "New", "width": 400.0, "height": 400.0, "items": []}
got = PM.add_controls(picker, empty, ["L_eye_ctrl", "R_eye_ctrl"], "", pos_of=pos_of, get_entry=entry)
check("an empty page: laid out on its own (left eye on the right)", len(got) == 2 and
      got[0]["x"] > got[1]["x"])

# --- take out / put back / missing
picker["exclude"] = []
gone = PM.exclude(picker, ["L_toe_ctrl", "neck_ctrl"])
check("take out: their buttons go, they're on the excluded list", gone == 2 and
      PM.excluded(picker) == ["L_toe_ctrl", "neck_ctrl"] and "neck_ctrl" not in PM.on_picker(picker))
with mock.patch.object(A, "character_controls", return_value=["|neck_ctrl", "|jaw_ctrl", "|head_ctrl"]):
    check("missing: not the taken-out ones", [PM.strip(n) for n in PM.missing(picker, "")] == ["jaw_ctrl"])
PM.include(picker, ["neck_ctrl"])
check("put back: missing again", PM.excluded(picker) == ["L_toe_ctrl"])
PM.add_controls(picker, page, ["L_toe_ctrl"], "", at=(5.0, 7.0))
check("adding a taken-out control puts it back on the list", "exclude" not in picker)
grp = {"name": "two", "items": [{"id": "g", "kind": "select", "nodes": ["a_ctrl", "b_ctrl"], "x": 0, "y": 0,
                                 "w": 10, "h": 10}]}
PM.exclude({"pages": [grp]}, ["a_ctrl"])
check("a button for several: keeps the others", grp["items"][0]["nodes"] == ["b_ctrl"])
pk2 = PM.auto("", rig=pickrig.rig(), points=[], exclude=["head_ctrl"])
check("Auto layout leaves the taken-out ones out (and keeps the list)", "head_ctrl" not in PM.on_picker(pk2) and
      pk2.get("exclude") == ["head_ctrl"])

# --- missing onto their own pages
pk3 = {"version": PM.VERSION, "pages": [{"name": "Body", "width": 400.0, "height": 400.0, "items": []}]}
with mock.patch.object(PM, "guess_pages", return_value={"jaw_ctrl": "Face", "L_eye_ctrl": "Face",
                                                         "L_thumb1_ctrl": "Hands", "cog_ctrl": "Body"}):
    got = PM.add_to_pages(pk3, ["jaw_ctrl", "L_eye_ctrl", "L_thumb1_ctrl", "cog_ctrl"], "", rig=RIG, pos_of=pos_of)
check("missing -> their own page: Face made, fingers on Body (no Hands page)", got == {"Body": 2, "Face": 2} and
      [p["name"] for p in pk3["pages"]] == ["Body", "Face"])

# --- the front view for buttons already there
fv = {"name": "Body", "width": 400.0, "height": 600.0, "items": []}
for k, nm in enumerate(("head_ctrl", "cog_ctrl", "L_arm_ik_ctrl", "R_arm_ik_ctrl", "L_leg_ik_ctrl")):
    fv["items"].append({"id": "f%d" % k, "kind": "select", "nodes": [nm], "x": 20.0 + 30 * k, "y": 20.0 + 60 * k,
                        "w": 20.0, "h": 20.0, "shape": "round", "label": nm, "twin": None})
fv["items"][4]["locked"] = True
moved = PM.arrange_front(fv, fv["items"], pos_of)
it = dict((i["nodes"][0], i) for i in fv["items"])
check("front view: 4 moved (the locked one stays), head above the hips, left hand right of the right hand",
      moved == 4 and it["head_ctrl"]["y"] < it["cog_ctrl"]["y"] and it["L_arm_ik_ctrl"]["x"] > it["R_arm_ik_ctrl"]
      ["x"] and it["L_leg_ik_ctrl"]["x"] == 140.0)
try:
    PM.arrange_front({"items": []}, [], pos_of)
    check("front view with nothing to go by: says why", False)
except RuntimeError as e:
    check("front view with nothing to go by: says why", "two buttons" in str(e))
pts = [(x * 0.5, y * 0.5, 0) for x in range(-20, 21) for y in range(0, 60)]
check("silhouette from the front on the page's scale", PM.page_silhouette(fv, pts, pos_of) and fv.get("outline"))

# --- pages, sides, sets, toggles, pins
pg = {"name": "Face", "width": 300.0, "items": [{"id": "a1", "kind": "select", "nodes": ["L_eye_ctrl"], "x": 0,
                                                  "y": 0, "w": 10, "h": 10, "twin": "a2"},
                                                 {"id": "a2", "kind": "select", "nodes": ["R_eye_ctrl"], "x": 20,
                                                  "y": 0, "w": 10, "h": 10, "twin": "a1"}]}
pk4 = {"pages": [pg]}
i2 = PM.duplicate_page(pk4, 0)
cp = pk4["pages"][1]
check("duplicate page: 'Face (copy)' after it, new ids, twins inside the copy, the original untouched",
      i2 == 1 and cp["name"] == "Face (copy)" and cp["items"][0]["id"] not in ("a1", "a2") and
      cp["items"][0]["twin"] == cp["items"][1]["id"] and pg["items"][0]["twin"] == "a2")
PM.duplicate_page(pk4, 0)
check("a second copy gets its own name", sorted(p["name"] for p in pk4["pages"]) == ["Face", "Face (copy)",
                                                                                      "Face (copy) 2"])
n = PM.colour_by_side(pg["items"], {"L": [0, 0, 1], "C": [1, 1, 0], "R": [1, 0, 0]})
check("colour by side", n == 2 and pg["items"][0]["rgb"] == [0, 0, 1] and pg["items"][1]["rgb"] == [1, 0, 0])
st = PM.add_set_button(pg, pg["items"][:2], "Eyes")
check("selection set: one pill above that selects both", st["nodes"] == ["L_eye_ctrl", "R_eye_ctrl"] and
      st["shape"] == "pill" and st["y"] < 0)
cmds.addAttr("L_arm_settings_ctrl" if cmds.objExists("L_arm_settings_ctrl") else "cog_ctrl", longName="ikfk",
             attributeType="double", minValue=0, maxValue=1)
tnode = "L_arm_settings_ctrl" if cmds.objExists("L_arm_settings_ctrl") else "cog_ctrl"
tg = PM.add_widget(pg, "toggle", tnode, "ikfk")
PM.toggle(tg, "")
v1 = cmds.getAttr(tnode + ".ikfk")
PM.toggle(tg, "")
check("toggle: a pill, one click on (1), again off (0)", tg["kind"] == "toggle" and tg["shape"] == "pill" and
      v1 == 1 and cmds.getAttr(tnode + ".ikfk") == 0)
pg["items"][0].update({"pin": True, "px": 1, "py": 2, "pw": 3, "ph": 4})
check("pinned found", len(PM.pinned(pk4)) == 1)
check("unpin all: pins and their window places gone", PM.unpin_all(pk4) == 1 and "px" not in pg["items"][0])
rep = PM.report(pk4, "")
check("report: pages, missing, pinned, duplicates, gone", set(rep) >= {"pages", "missing", "unsure", "excluded",
                                                                        "pinned", "duplicates", "gone"})

# --- your look
PM.set_pref("text_scale", 1.8)
check("prefs: yours, on this computer (text 1.8; others default)", PM.pref("text_scale") == 1.8 and
      PM.pref("theme") == "dark" and json.loads(_opts["picker_prefs"])["text_scale"] == 1.8)
check("themes: dark, light, contrast", sorted(PM.THEMES) == ["contrast", "dark", "light"])
PM.set_pref("text_scale", 1.0)

# --- the window
cmds.workspaceControl = mock.MagicMock(return_value="gusAnimtoolPicker")
cmds.scriptJob = mock.MagicMock()
from gus_animtool import pickerqt as Q
from fakeqt import Event, Qt, DRAWN, MENUS, QDialog
w = Q.build()
cv = w.canvas
cv.frame(); cv.paintEvent(None)
check("mode band: ANIMATE", w._band.startswith("ANIMATE"))
check("status: page, buttons, zoom", w._status.startswith("Page: Body") and "buttons" in w._status and
      "zoom" in w._status)
w.text_slider.setValue(200)
check("text size slider: 200% kept for you", PM.pref("text_scale") == 2.0 and w.look["text_scale"] == 2.0)
w.text_slider.setValue(100)
w.edit_btn.setChecked(True)
check("mode band: EDIT", w._band.startswith("EDIT"))
items = [i for i in w.page()["items"] if i.get("kind") == "select"]
w.picked = {items[0]["id"]}
cv.paintEvent(None)
x0 = items[0]["x"]
w.picked = {items[1]["id"]}                       # picked another; the X field still had the first's value
w.panel_set("x", x0 + 50)
check("Item panel: a field left after picking another doesn't move the new one", items[1]["x"] != x0 + 50)
cv.paintEvent(None)
x1 = items[1]["x"]
w.panel_set("x", x1 + 5)
check("... after it shows the new one, it does", abs(items[1]["x"] - (x1 + 5)) < 1e-6)
w.list_btn.setChecked(True)
rows = w.list_rows()
check("button list: every item on the page", len(rows) == len(w.page()["items"]))
w.search.setText("head") if hasattr(w.search, "setText") else None
w.filter_list("head")
check("search: finds the head's button(s), drawn highlighted", w.search_ids and all(
    "head" in (i.get("label", "") + " ".join(i.get("nodes") or [])).lower() for i in w.page()["items"]
    if i["id"] in w.search_ids))
w.filter_list("")
w.picked = {items[2]["id"]}
w.toggle_pin()
w.show_missing()
check("a pinned button: the bar says it doesn't zoom", w.pin_btn.isVisible() and "pinned" in w.pin_btn.label)
w.unpin_all()
w.show_missing()
check("Unpin all: gone, the bar too", not PM.pinned(w.picker) and not w.pin_btn.isVisible())
n0 = len(w.picker["pages"])
w.duplicate_page()
check("Page > Duplicate: a copy right after, shown", len(w.picker["pages"]) == n0 + 1 and
      w.page()["name"].endswith("(copy)"))
w.index = 0; w.set_page(0)
victim = [i for i in w.page()["items"] if i.get("kind") == "select"][3]
w.picked = {victim["id"]}
w.exclude_picked()
check("Take out: the button goes, the control on the list", victim["nodes"][0] in PM.excluded(w.picker) and
      victim["id"] not in [i["id"] for i in w.page()["items"]])
QDialog.answer[0] = 0
w.missing_dialog()
ui = w._missing_ui
check("Missing dialog: the taken-out control listed to put back", any(
    ui["out"].item(i).data(Qt.UserRole) == victim["nodes"][0] for i in range(ui["out"].count())))
cmds.select("L_toe_ctrl")
with mock.patch.object(PM, "pos_finder", return_value=pos_of), mock.patch.object(PM, "entry_of", side_effect=entry):
    page = w.page()
    page["items"] = [i for i in page["items"] if i.get("nodes") != ["L_toe_ctrl"]]
    w.add_selected()
added = [i for i in w.page()["items"] if i.get("nodes") == ["L_toe_ctrl"]]
check("Add selected (front view, the default): added, picked", len(added) == 1 and w.picked == {added[0]["id"]})
with mock.patch.object(PM, "pos_finder", return_value=pos_of):
    picked = [i for i in w.page()["items"] if i.get("kind") == "select"][:4]
    w.picked = set(i["id"] for i in picked)
    moved = w.arrange_front(picked_only=True)
check("front view from the window: the picked placed", moved == 4 and w.dirty)
cmds.select(clear=True)
w.edit_btn.setChecked(False)
L = [i for i in w.page()["items"] if i.get("nodes") == ["L_arm_ik_ctrl"]]
if L:
    p0 = cv.to_screen(L[0]["x"] + L[0]["w"] / 2, L[0]["y"] + L[0]["h"] / 2)
    with mock.patch.object(A, "mirror_name", side_effect=lambda n: n.replace("L_", "R_")):
        cv.mousePressEvent(Event(p0.x(), p0.y(), Qt.LeftButton, Qt.AltModifier))
        cv.mouseReleaseEvent(Event(p0.x(), p0.y(), Qt.LeftButton))
    check("Alt+click: the twin selected", [A.short(n) for n in cmds.ls(selection=True)] == ["R_arm_ik_ctrl"])
w.apply_look({"compact": True, "theme": "light", "hover": "outline"})
del DRAWN[:]
cv.paintEvent(None)
check("look applied (compact toolbar, light theme, hover outline) and drawn", w.look["compact"] and
      PM.pref("theme") == "light" and any(k == "fill" for k, _t in DRAWN))
print("%d/%d passed" % (sum(ok), len(ok)))
