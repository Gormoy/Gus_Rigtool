# 5.6.26: the picker - a text never blocks a button (the limbs "not working"), frame titles clicked where drawn,
# close connectors straight, rename many (prefix / suffix / find / numbers / case), shapes (the rig tool's library,
# the control's own curve, the most alike), the controls' colours / Maya's palette, frames per limb, IK / FK fade,
# badges, folded frames, a layer following a rig switch, copy / paste, Alt+drag copies, 8 handles (Shift: its
# proportions), turning, Shift: one direction, distances / equal gaps, the minimap, preview, find on every page,
# page templates, saved versions, another character's pages, the undo history, Z / Shift+Z, the Item panel in
# sections, attributes without the Channel Box
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

# --- the limbs: a text over buttons
pg = {"name": "Body", "items": [b(10, 10, node="L_ankle_IK_ctrl", i="ank"),
                                {"id": "t", "kind": "text", "label": "L Leg", "x": 0.0, "y": 0.0, "w": 100.0,
                                 "h": 60.0, "size": 14.0}]}
check("the Hare's L_ankle_IK button under the 'L Leg' text: a click hits the button (animating and in Edit)",
      PM.hit_any(pg, 20, 20)["id"] == "ank" and PM.hit_any(pg, 20, 20, True)["id"] == "ank")
check("the text: picked in Edit off the button, nothing while animating", PM.hit_any(pg, 80, 50, True)["id"] == "t"
      and PM.hit_any(pg, 80, 50) is None)
fr = {"id": "f", "kind": "frame", "label": "ARM", "x": 0.0, "y": 0.0, "w": 200.0, "h": 100.0, "tpos": "center"}
r = PM.title_rect(fr)
check("a frame title placed in the middle: clicked there, not on the old bar",
      PM.on_title(fr, 100, 50) and not PM.on_title(fr, 5, 5) and r[0] > 50)

# --- close connectors
cp = {"items": [b(0, 0, 20, 20, i="a"), b(30, 0, 20, 20, i="c")]}
ln = PX.add_link(cp, "a", "c")
pts = PX.link_points(cp, ln)
check("two buttons close in a row: a straight line (5.6.25 looped)", pts == [(20.0, 10.0), (30.0, 10.0)])
cp["items"][1]["y"] = 30.0
pts = PX.link_points(cp, ln)
check("... not in line: a gentle curve that stays between them", all(-1 <= p[0] <= 51 and -1 <= p[1] <= 51 for p in pts))

# --- rename
labs = ["Ear FK 01", "Ear FK 02", "Ear FK 03"]
check("rename: find / replace, cut, case, prefix / suffix, numbers",
      PX.rename_labels(labs, find="FK", replace="IK") == ["Ear IK 01", "Ear IK 02", "Ear IK 03"] and
      PX.rename_labels(labs, cut_end=3, prefix="L ", case="upper") == ["L EAR FK", "L EAR FK", "L EAR FK"] and
      PX.rename_labels(["a", "b"], suffix="_x", number=(5, 5, 2, "start")) == ["05 a_x", "10 b_x"])

# --- shapes
lib = dict((c, [n for n, _p, _a in its]) for c, its in PX.library())
check("the shape library: the picker's own + the rig tool's (gear, foot, arrows...)",
      "round" in lib["Picker"] and {"gear", "foot", "hand"} <= set(lib["Rig"]) and "four_way_arrow" in lib["Arrows"])
it = b(0, 0, 30, 30)
PX.apply_shape([it], "gear")
check("a rig tool shape on a button: an outline (poly) with its points, named", it["shape"] == "poly" and
      len(it["points"]) > 10 and it["shape_name"] == "gear")
PX.apply_shape([it], "star")
check("a picker shape: by name", it["shape"] == "star")
import math
circle3 = [(math.cos(a / 24.0 * 2 * math.pi), 5 + math.sin(a / 24.0 * 2 * math.pi), 0.0) for a in range(24)]
got, aspect = PX.view_points(circle3, "front")
check("a control's curve from the front: 0..1, round", got and abs(aspect - 1.0) < 0.05 and
      PX.best_view(circle3) == "front")
near = [n for n, _s in PX.similar(got, 4)]
check("the most alike to a circle: round shapes first (%s)" % near[:3],
      near[0] in ("round", "ellipse", "ring", "circle", "octagon", "sphere"))
sq = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
near_sq = [n for n, _s in PX.similar(PX.view_points(sq, "front")[0], 4)]
check("... to a square: square ones (%s)" % near_sq[:3], any(n in ("rect", "square", "rectangle", "cube")
                                                             for n in near_sq[:3]))

# --- colours, limbs, badges, folding
its = [b(0, 0, node="L_arm_ctrl"), b(30, 0, node="cog_ctrl")]
check("buttons take their control's colour", PX.match_colours(its, lambda n: [0, 0, 1] if n.startswith("L_") else
                                                              None) == 1 and its[0]["rgb"] == [0, 0, 1])
check("31 Maya colours", len(PX.MAYA_PALETTE) == 31)
check("limb titles", PX.limb_title("|rig|L_arm_settings_ctrl") == "L ARM" and PX.limb_title("R_leg_switch") ==
      "R LEG")
lp = {"name": "B", "items": [b(0, 0, node="L_shoulder_FK_ctrl"), b(0, 30, node="L_elbow_FK_ctrl"),
                             b(0, 60, node="L_wrist_IK_ctrl"), b(100, 0, node="cog_ctrl")]}
made = PX.group_by_limb(lp, [("L ARM", ["L_shoulder_FK_ctrl", "L_elbow_FK_ctrl", "L_wrist_IK_ctrl"])])
check("a frame per limb round its buttons (not the cog)", len(made) == 1 and made[0]["label"] == "L ARM" and
      len(PM.frame_members(lp, made[0])) == 3)
check("badges from the name: IK, FK, PV, S; yours wins; '-' none",
      [PX.badge_of(b(0, 0, node=n)) for n in ("L_wrist_IK_ctrl", "L_elbow_FK_ctrl", "L_arm_pv_ctrl",
                                               "L_arm_settings_ctrl", "cog_ctrl")] == ["IK", "FK", "PV", "S", ""]
      and PX.badge_of(b(0, 0, node="x_ik_ctrl", badge="R")) == "R")
made[0]["folded"] = True
check("a folded frame: its buttons hidden, not clicked", len(PX.folded_ids(lp)) == 3 and
      PM.hit_any(lp, 10, 40) is None)
made[0]["folded"] = False

# --- clipboard, find, templates, backups, guides, history
cpage = {"name": "C", "items": [b(0, 0, i="p"), b(50, 0, i="q")]}
PX.add_link(cpage, "p", "q")
clip = PX.copy_items(cpage, cpage["items"])
other = {"name": "D", "items": []}
new = PX.paste_items(other, clip)
check("copy / paste onto another page: new ids, moved, their connector too", len(new) == 2 and
      new[0]["id"] != "p" and new[0]["x"] == 12.0 and len(other["links"]) == 1 and
      other["links"][0]["a"] == new[0]["id"])
pk = {"pages": [{"name": "A", "items": [b(0, 0, node="L_eye_ctrl")]}, {"name": "B", "items": [b(0, 0, node="R_eye_ctrl"),
                                                                                             b(0, 30, node="jaw")]}]}
check("find on every page", dict((k, len(v)) for k, v in PX.find_all(pk, "eye").items()) == {0: 1, 1: 1})
PX.save_template(pk["pages"][1], "Face")
i = PX.page_from_template(pk, "Face")
check("page templates: a new page from yours (new ids)", pk["pages"][i]["name"] == "Face" and
      pk["pages"][i]["items"][0]["id"] != pk["pages"][1]["items"][0]["id"] and len(pk["pages"]) == 3)
base = tempfile.mkdtemp()
p1 = PX.save_backup("hare", {"pages": [{"name": "A", "items": []}]}, base, stamp="20261108-170000")
p2 = PX.save_backup("hare", {"pages": [{"name": "A", "items": [b(0, 0)]}]}, base, stamp="20261108-171500")
rows = PX.backups("hare", base)
check("saved versions: newest first, when, pages, buttons", [(r[1], r[3]) for r in rows] ==
      [("2026-11-08 17:15:00", 1), ("2026-11-08 17:00:00", 0)] and PX.load_backup(p1)["pages"][0]["name"] == "A")
for k in range(5):
    PX.save_backup("hare", {"pages": []}, base, keep=4, stamp="20261109-00000%d" % k)
check("... only the last ones kept", len(PX.backups("hare", base)) == 4)
nb = [b(0, 0, 20, 20), b(100, 0, 20, 20)]
g = dict((s_, d) for s_, d, _l in PX.gaps((48, 0, 68, 20), nb))
check("gaps to the neighbours", g == {"left": 28.0, "right": 32.0})
check("nearly half way: nudged to equal gaps", PX.equal_nudge((48, 0, 68, 20), nb) == (2.0, 0.0))
check("the page's middle lines to snap to", PX.centre_targets({"items": [], "width": 200.0, "height": 100.0})[0]["x"] * 2
      == PM.page_size({"items": [], "width": 200.0, "height": 100.0})[0])
h = PM.History()
pkh = {"pages": [{"name": "A", "items": []}]}
for n in range(3):
    h.push(pkh, "step %d" % n)
    pkh = json.loads(json.dumps(pkh))
    pkh["pages"][0]["items"].append(b(n * 30, 0, i="h%d" % n))
check("undo history: the steps listed", [w_ for _t, w_ in h.steps()] == ["step 0", "step 1", "step 2"])
back = h.back_to(pkh, 1)
check("... back to before step 1 at once (redo can bring them back)", len(back["pages"][0]["items"]) == 1 and
      len(h.redos) == 2)
L_ = {"name": "Brows", "shown": True, "switch": "Face_settings_ctrl.Brows"}
lpage = {"layers": [L_], "items": [b(0, 0, i="br", layer="Brows")]}
PX.SWITCH_READER[0] = lambda plug: 0.0
check("a layer following a rig switch: hidden when the switch is off", PX.layer_off(lpage) == {"br"})
PX.SWITCH_READER[0] = lambda plug: 1.0
check("... shown when on", PX.layer_off(lpage) == set())
PX.SWITCH_READER[0] = None

# --- the window
RIG = pickrig.rig()
for r_ in RIG:
    t = cmds.createNode("transform", name=r_["node"])
    cmds.createNode("nurbsCurve", name=r_["node"] + "Shape", parent=t)
PM.read_rig = lambda ns=None: pickrig.rig()
cmds.workspaceControl = mock.MagicMock(return_value="gusAnimtoolPicker")
cmds.scriptJob = mock.MagicMock()
from gus_animtool import pickerqt as Q
from fakeqt import Event, Qt, DRAWN, MENUS
w = Q.build()
cv = w.canvas
w.edit_btn.setChecked(True)
page = w.page()
page["items"] = [b(40, 40, 40, 20, i="w1", node="cog_ctrl", label="COG"),
                 b(140, 40, 40, 20, i="w2", node="head_ctrl", label="HEAD")]
cv.frame(); cv.paintEvent(None)
check("Edit: Undo / Redo / History / Preview on the band", all(b_.isVisible() for b_ in w.band_tools))
w.picked = {"w1"}
w.copy_picked()
w.paste()
check("Ctrl+C / Ctrl+V: a copy, picked", len(page["items"]) == 3 and w.picked and "w1" not in w.picked)
cv.keyPressEvent(Event(key=Qt.Key_Z))
check("Z (like Maya): undoes the paste", len(w.page()["items"]) == 2)
cv.keyPressEvent(Event(key=Qt.Key_Z, mods=Qt.ShiftModifier))
check("Shift+Z: redoes it", len(w.page()["items"]) == 3)
w.undo()
page = w.page()
w1, w2 = page["items"]
s1 = cv.to_screen(60, 50)
cv.mousePressEvent(Event(s1.x(), s1.y(), Qt.LeftButton, Qt.AltModifier))
s2 = cv.to_screen(60, 120)
cv.mouseMoveEvent(Event(s2.x(), s2.y(), Qt.LeftButton))
cv.mouseReleaseEvent(Event(s2.x(), s2.y(), Qt.LeftButton))
copies = [i for i in page["items"] if i["id"] not in ("w1", "w2")]
check("Alt+drag in Edit: a copy dragged off, the original stays", len(copies) == 1 and w1["x"] == 40.0 and
      abs(copies[0]["y"] - 110) < 1 and w.canvas.drag is None)
w.undo()
page = w.page()
w1, w2 = page["items"]
w.picked = {"w1", "w2"}
cv.paintEvent(None)
hs = cv._handles()
check("two picked: 8 handles round both (no turn handle)", set(hs) == {"nw", "n", "ne", "e", "se", "s", "sw", "w"})
se = hs["se"]
cv.mousePressEvent(Event(se.x(), se.y(), Qt.LeftButton))
to = cv.to_screen(320, 80)
cv.mouseMoveEvent(Event(to.x(), to.y(), Qt.LeftButton))
cv.mouseReleaseEvent(Event(to.x(), to.y(), Qt.LeftButton))
check("drag the corner: both scale as one box (twice as wide, twice as tall)",
      abs(w2["x"] - 240) < 1 and abs(w1["w"] - 80) < 1 and abs(w1["h"] - 40) < 1 and w1["x"] == 40.0)
w.undo()
page = w.page()
w1, w2 = page["items"]
w.picked = {"w1"}
cv.paintEvent(None)
e_ = cv._handles()["e"]
cv.mousePressEvent(Event(e_.x(), e_.y(), Qt.LeftButton))
to = cv.to_screen(120, 50)
cv.mouseMoveEvent(Event(to.x(), to.y(), Qt.LeftButton, Qt.ShiftModifier))
cv.mouseReleaseEvent(Event(to.x(), to.y(), Qt.LeftButton))
check("Shift on a side handle: its proportions kept (80 x 40)", abs(w1["w"] - 80) < 1 and abs(w1["h"] - 40) < 1)
w.undo()
page = w.page()
w1, w2 = page["items"]
w.picked = {"w1"}
cv.paintEvent(None)
rot = cv._handles()["rot"]
cv.mousePressEvent(Event(rot.x(), rot.y(), Qt.LeftButton))
to = cv.to_screen(100, 50)
cv.mouseMoveEvent(Event(to.x(), to.y(), Qt.LeftButton, Qt.ShiftModifier))
cv.mouseReleaseEvent(Event(to.x(), to.y(), Qt.LeftButton))
check("the turn handle: a quarter turn (Shift: 15 degree steps)", w1.get("rot") == 90.0)
w1["rot"] = 0
s1 = cv.to_screen(60, 50)
cv.mousePressEvent(Event(s1.x(), s1.y(), Qt.LeftButton))
s2 = cv.to_screen(90, 54)
cv.mouseMoveEvent(Event(s2.x(), s2.y(), Qt.LeftButton, Qt.ShiftModifier))
check("Shift while dragging: only across", w1["y"] == 40.0 and w1["x"] > 60)
check("... the distances to the neighbours shown", any(sd == "right" for sd, _g, _l in cv.gap_lines))
cv.mouseReleaseEvent(Event(s2.x(), s2.y(), Qt.LeftButton))
w.toggle_preview()
with mock.patch.object(cv, "_paint_handles") as ph, mock.patch.object(cv, "_paint_ports") as pp:
    cv.paintEvent(None)
check("Preview: drawn as the animators see it (no handles, no dots)", w.preview and not ph.called and
      not pp.called)
cv.mousePressEvent(Event(5, 5, Qt.LeftButton))
check("... a click ends it", not w.preview)
new = w.rename_items(PX.reading_order(page["items"]), prefix="L ", suffix=" ctrl")
check("rename the picked at once", new == ["L COG ctrl", "L HEAD ctrl"] and w1["label"] == "L COG ctrl")
with mock.patch.object(A, "with_attr", return_value=["|L_arm_settings_ctrl"]), \
        mock.patch.object(A, "limb_controls", return_value=["|cog_ctrl", "|head_ctrl"]):
    w.group_by_limb()
check("Limbs: a frame round the limb's buttons", any(PM.is_frame(i) and i["label"] == "L ARM"
                                                    for i in w.page()["items"]))
page = w.page()
frm = [i for i in page["items"] if PM.is_frame(i)][0]
tr = PM.title_rect(frm)
fp = cv.to_screen(tr[0] + tr[2] - 4.0 / cv.scale, tr[1] + tr[3] / 2)
cv.mousePressEvent(Event(fp.x(), fp.y(), Qt.LeftButton)); cv.mouseReleaseEvent(Event(fp.x(), fp.y(), Qt.LeftButton))
check("the fold arrow (right of the title): folded", frm.get("folded") is True)
rows = w.list_rows()
check("the button list as an outline: the group, its buttons indented under it",
      rows[0][1].startswith("[folded] L ARM") and rows[1][1].startswith("      "))
frm["folded"] = False
w.picked_links = set()
w.picked = {page["items"][-1]["id"]}
cv.paintEvent(None)
check("Item panel: sections for a button (no Connector, no Toggle)", w.panel_sections["Text"][0].isVisible() and
      not w.panel_sections["Connector"][0].isVisible() and not w.panel_sections["Toggle"][0].isVisible())
with mock.patch.object(Q.QtWidgets.QInputDialog, "getItem", return_value=("ikfk", True), create=True):
    cmds.select("L_arm_settings_ctrl" if cmds.objExists("L_arm_settings_ctrl") else "cog_ctrl")
    node = A.selected()[0]
    cmds.addAttr(node, longName="ikfk", attributeType="double", minValue=0, maxValue=1, keyable=True)
    got = w.choose_attr(("double",))
check("no Channel Box pick: the control's attributes to choose from", got == (node, "ikfk"))
with mock.patch.object(A, "settings_of", return_value="|L_arm_settings_ctrl"), \
        mock.patch.object(A, "limb_controls", side_effect=lambda s, which="all": ["|cog_ctrl"] if which == "ik" else
                          ["|head_ctrl"]), mock.patch.object(A, "_in_fk", return_value=True):
    w._ikfk = {}
    cog = [i for i in page["items"] if i.get("nodes") == ["cog_ctrl"]][0]
    hd = [i for i in page["items"] if i.get("nodes") == ["head_ctrl"]][0]
    check("IK / FK fade: in FK the IK button fades, the FK one doesn't", w.ikfk_faded(cog) and not w.ikfk_faded(hd))
pk0 = json.loads(json.dumps(w.picker))
n = w.add_pages_from({"pages": [{"name": "Face", "items": [b(0, 0, node="zz_only_here_ctrl")]}]})
check("pages from another character", n == 1 and w.page() is not None and
      any(p_["name"] == "Face" for p_ in w.picker["pages"]))
fpage = len(w.picker["pages"]) - 1
w.index = 0
w.set_page(0)
w.find_everywhere("zz_only_here")
w.find_go()
check("find: none here - Enter goes to the page that has it", w.index == fpage)
PX.backup_dir = lambda rig, base=None: os.path.join(base or tempfile.gettempdir(), "gus_t", rig)
path = PX.save_backup("x", pk0, tempfile.mkdtemp())
w.restore_backup(path)
check("a saved version back (Undo can take it away)", len(w.picker["pages"]) == len(pk0["pages"]))
steps = w.history.steps()
w.undo_to(len(steps) - 1)
check("undo history: back one step from the list", len(w.picker["pages"]) == len(pk0["pages"]) + 1)
big = w.page()
big["width"], big["height"] = 6000.0, 4000.0
cv.scale = 1.0
cv.paintEvent(None)
check("a page bigger than the window: the minimap", cv._mini is not None)
box, k = cv._mini
off0 = cv.offset.x()
cv.mousePressEvent(Event(box.left() + box.width() * 0.9, box.top() + box.height() * 0.5, Qt.LeftButton))
check("... click it: the view goes there", cv.offset.x() != off0)
print("%d/%d passed" % (sum(ok), len(ok)))
