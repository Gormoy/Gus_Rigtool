# 5.6.25: the picker - one way to place text (anywhere round / in an item, moved by Ctrl+drag, wrapped, a plate),
# sticky notes, connectors (Nuke / Miro style: from an item's dot to another, straight / elbow / curved, bends,
# heads, a label, picked / reconnected / deleted; made from the rig's hierarchy), layers (show / hide / lock),
# your toolbar (sections, order, hidden tools), a silhouette picture from the meshes' triangles, mirror pairs
# leaving middle controls a little off the line alone
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

# --- text places
check("old settings still mean the same place: a button's 'right' -> outside-right, a frame's 'inside' -> top-left, "
      "a text 'left' -> left", [PX.text_place(x) for x in (b(0, 0, label_pos="right"),
                                                            {"kind": "frame", "title_pos": "inside"},
                                                            {"kind": "text", "align": "left"})] ==
      ["outside-right", "top-left", "left"])
check("its own place wins", PX.text_place(b(0, 0, label_pos="right", tpos="bottom-left")) == "bottom-left")
got = dict((pl, PX.text_box(pl, 0, 0, 100, 50, 20, 10, 3.0)) for pl in PX.TEXT_PLACES if pl != "hidden")
check("text boxes: top-left in the corner, bottom-right in the other, above over it, outside-left before it",
      got["top-left"][:2] == (3.0, 3.0) and got["bottom-right"][:2] == (77.0, 37.0) and got["above"][1] < 0 and
      got["outside-left"][0] < 0 and got["center"][:2] == (40.0, 20.0) and got["right"][2] == "right")
page = {"name": "P", "width": 400.0, "height": 300.0, "items": []}
note = PX.add_note(page, "line one\nline two", 10, 10)
check("a sticky note: a text, yellow, text from the top-left, wrapped", note["kind"] == "text" and note["note"] and
      PX.text_place(note) == "top-left" and note["rgb"][0] > 0.9)

# --- connectors
a_, b_, c_ = b(0, 0, 20, 20, i="a"), b(200, 0, 20, 20, i="b"), b(100, 100, 20, 20, i="c")
page["items"] += [a_, b_, c_]
ln = PX.add_link(page, "a", "b")
check("a connector a -> b (curved, an arrow at the end); not twice between the same two",
      ln["style"] == "curved" and ln["head_b"] == "arrow" and PX.add_link(page, "b", "a") is ln and
      len(page["links"]) == 1)
pts = PX.link_points(page, ln)
check("curved: leaves a's right side, arrives at b's left side", pts[0] == (20.0, 10.0) and pts[-1] == (200.0, 10.0)
      and len(pts) > 5)
ln["style"] = "straight"
check("straight: two points", PX.link_points(page, ln) == [(20.0, 10.0), (200.0, 10.0)])
ln2 = PX.add_link(page, "a", "c", style="elbow")
e = PX.link_points(page, ln2)
check("elbow: right angles only", all(p[0] == q[0] or p[1] == q[1] for p, q in zip(e, e[1:])) and len(e) == 4)
check("hit: the straight one, near it", PX.hit_link(page, 110, 11, 3.0) is ln and PX.hit_link(page, 110, 60, 3.0)
      is not ln)
PX.add_bend(page, ln, 110, 60)
PX.add_bend(page, ln, 60, 40)
check("bends (Nuke dots) go in order along it", ln["bends"] == [[60, 40], [110, 60]])
ln["style"] = "curved"
cp = PX.link_points(page, ln)
check("curved through bends passes them", any(abs(p[0] - 110) < 1e-6 and abs(p[1] - 60) < 1e-6 for p in cp))
pt, d = PX.point_at([(0, 0), (10, 0), (10, 10)], 0.75)
check("a point 3/4 along (the label)", pt == (10.0, 5.0))
check("heads: an arrow (filled), open lines, a dot, none", PX.head_shape((10, 0), (0, 0), "arrow", 4)[0] == "poly"
      and PX.head_shape((10, 0), (0, 0), "open", 4)[0] == "lines" and
      PX.head_shape((10, 0), (0, 0), "dot", 4)[0] == "dot" and PX.head_shape((10, 0), (0, 0), "none", 4) is None)
pk = {"version": PM.VERSION, "pages": [page]}
i2 = PM.duplicate_page(pk, 0)
cp_ = pk["pages"][i2]
ids = set(i["id"] for i in cp_["items"])
check("a page copy: its connectors join the copies", len(cp_["links"]) == 2 and
      all(x["a"] in ids and x["b"] in ids for x in cp_["links"]) and cp_["links"][0]["id"] != ln["id"])
PM.delete(page, [c_])
check("an item deleted: its connectors go", [x["id"] for x in page["links"]] == [ln["id"]])
items = [b(0, 0, node="hips", i="h"), b(0, 30, node="spine", i="s"), b(0, 60, node="chest", i="ch")]
hp = {"items": items}
longs = {"h": "|rig|hips", "s": "|rig|hips|g|spine", "ch": "|rig|hips|g|spine|o|chest"}
PX.add_link(hp, "h", "ch", label="mine")
n = PX.links_from_hierarchy(hp, lambda it: longs[it["id"]])
n2 = PX.links_from_hierarchy(hp, lambda it: longs[it["id"]])
check("connectors from the rig's hierarchy: hips -> spine -> chest; made again: not doubled; yours stay",
      n == 2 and n2 == 2 and len(hp["links"]) == 3 and any(x.get("label") == "mine" for x in hp["links"]))

# --- layers
lp = {"name": "L", "items": [b(0, 0, i="x1"), b(0, 0, i="x2")]}
PX.add_layer(lp, "Notes")
PX.set_layer([lp["items"][1]], "Notes")
check("a layer shown: the top one hit", PM.hit_any(lp, 5, 5)["id"] == "x2")
PX.layer(lp, "Notes")["shown"] = False
check("hidden: not hit, not in a box", PM.hit_any(lp, 5, 5)["id"] == "x1" and
      [i["id"] for i in PM.in_rect(lp, -1, -1, 30, 30)] == ["x1"])
PX.layer(lp, "Notes").update({"shown": True, "locked": True})
check("locked: picked through in Edit, still selects while animating",
      PM.hit_any(lp, 5, 5, True)["id"] == "x1" and PM.hit_any(lp, 5, 5)["id"] == "x2")
PX.remove_layer(lp, "Notes")
check("a layer deleted: its items stay, on no layer", "layer" not in lp["items"][1] and not lp["layers"])

# --- your toolbar
spec = [("Create", ["a", "b", "c"]), ("Style", ["d", "e"]), ("File", ["f"])]
check("no changes: the usual", PX.toolbar_layout(spec, {}) == [("Create", ["a", "b", "c"]), ("Style", ["d", "e"]),
                                                               ("File", ["f"])])
saved = {"sections": [["Favourites", ["e", "a"]], ["File", ["f"]], ["Create", ["c", "b", "zz"]]], "hidden": ["d"]}
check("yours: Favourites first, the order kept, hidden left out, a gone tool dropped, a section you took away "
      "comes back with what's left in it",
      PX.toolbar_layout(spec, saved) == [("Favourites", ["e", "a"]), ("File", ["f"]), ("Create", ["c", "b"])])
st, hid = PX.toolbar_state(spec, saved)
PX.toolbar_move(st, "b", step=-1)
PX.toolbar_move(st, "f", to_section="Favourites")
PX.section_move(st, "Create", -2)
check("move a tool up, to another section; a section up (a hidden one kept in its section)",
      [x[0] for x in st] == ["Create", "Favourites", "File", "Style"] and st[0][1] == ["b", "c"] and
      st[1][1] == ["e", "a", "f"] and st[3][1] == ["d"] and hid == ["d"])

# --- mirror pairs: middle controls a little off the line
rest = {"|Collar_fol_01_ctrl": (0.6, 15.0, 0.0), "|L_Lone_ctrl": (0.6, 2.0, 0.0), "|Mid_ctrl": (0.0, 0.0, 0.0),
        "|Top_ctrl": (0.0, 20.0, 0.0)}
for x in rest:
    cmds.createNode("transform", name=x.strip("|"))
with mock.patch.object(A, "character_controls", return_value=list(rest)), \
        mock.patch.object(A, "_rest_pos", side_effect=lambda n: rest[A.long_name(n) or n]), \
        mock.patch.object(A, "position_twins", return_value={}):
    rep = [PM.strip(r["node"]) for r in PX.pair_report("")]
check("pairs: Collar_fol_01 (no side, 3% of the height off the line) left alone; L_Lone (a side) listed",
      rep == ["L_Lone_ctrl"])
check("triangles' box", PX.tri_box([((0, 1), (2, 3), (-1, 5))]) == (-1, 1, 2, 5))

# --- the window
RIG = pickrig.rig()
for r in RIG:
    t = cmds.createNode("transform", name=r["node"])
    cmds.createNode("nurbsCurve", name=r["node"] + "Shape", parent=t)
PM.read_rig = lambda ns=None: pickrig.rig()
cmds.workspaceControl = mock.MagicMock(return_value="gusAnimtoolPicker")
cmds.scriptJob = mock.MagicMock()
from gus_animtool import pickerqt as Q
from fakeqt import Event, Qt, DRAWN, MENUS
w = Q.build()
cv = w.canvas
w.edit_btn.setChecked(True)
pg = w.page()
pg["items"] = [b(40, 40, 30, 20, i="p1", node="cog_ctrl", label="COG"), b(160, 40, 30, 20, i="p2", node="head_ctrl",
                                                                         label="HEAD")]
pg.pop("links", None)
cv.frame(); cv.paintEvent(None)
p1, p2 = pg["items"]
check("the text's place drawn and recorded (Ctrl+drag finds it)", "p1" in cv.text_rects)
box = cv.text_rects["p1"]
c0 = box.center()
cv.mousePressEvent(Event(c0.x(), c0.y(), Qt.LeftButton, Qt.ControlModifier))
cv.mouseMoveEvent(Event(c0.x() + 30 * cv.scale, c0.y() - 20 * cv.scale, Qt.LeftButton, Qt.ControlModifier))
cv.mouseReleaseEvent(Event(c0.x() + 30 * cv.scale, c0.y() - 20 * cv.scale, Qt.LeftButton))
check("Ctrl+drag the text: the words moved (30, -20), the button didn't", abs(p1.get("tdx", 0) - 30) < 1e-6 and
      abs(p1.get("tdy", 0) + 20) < 1e-6 and p1["x"] == 40.0)
w.picked = {"p1"}
cv.paintEvent(None)
w.panel_set("tpos", "below")
check("Item panel: text place 'below'", p1["tpos"] == "below")
mid = cv.to_screen(55, 50)
cv.mouseMoveEvent(Event(mid.x(), mid.y()))
port = cv._ports(p1)["right"]
cv.mousePressEvent(Event(port.x(), port.y(), Qt.LeftButton))
end = cv.to_screen(175, 50)
cv.mouseMoveEvent(Event(end.x(), end.y(), Qt.LeftButton))
cv.mouseReleaseEvent(Event(end.x(), end.y(), Qt.LeftButton))
check("drag from a blue dot to another button: a connector (leaves from the right), picked",
      len(pg.get("links") or []) == 1 and pg["links"][0]["a"] == "p1" and pg["links"][0]["b"] == "p2" and
      pg["links"][0]["a_side"] == "right" and w.picked_links == {pg["links"][0]["id"]})
L = pg["links"][0]
L["style"] = "straight"
cv.paintEvent(None)
w.panel_set("ln_width", 4.0)
w.panel_set("ln_style", "elbow")
w.panel_set("ln_head_a", "dot")
w.panel_set("ln_dash", "dash")
check("Item panel on the connector: width 4, elbow, a dot at the start, dashed", L["width"] == 4.0 and
      L["style"] == "elbow" and L["head_a"] == "dot" and L["dash"] == "dash")
L["style"] = "straight"
w.picked_links = set()
on = cv.to_screen(110, 50)
cv.mousePressEvent(Event(on.x(), on.y(), Qt.LeftButton)); cv.mouseReleaseEvent(Event(on.x(), on.y(), Qt.LeftButton))
check("click the line: picked", w.picked_links == {L["id"]} and not w.picked)
cv.mousePressEvent(Event(on.x(), on.y(), Qt.LeftButton, Qt.ControlModifier))
cv.mouseReleaseEvent(Event(on.x(), on.y(), Qt.LeftButton))
check("Ctrl+click it: a bend there", len(L["bends"]) == 1 and abs(L["bends"][0][0] - 110) < 1)
bd = cv.to_screen(*L["bends"][0])
cv.mousePressEvent(Event(bd.x(), bd.y(), Qt.LeftButton))
to = cv.to_screen(110, 90)
cv.mouseMoveEvent(Event(to.x(), to.y(), Qt.LeftButton)); cv.mouseReleaseEvent(Event(to.x(), to.y(), Qt.LeftButton))
check("drag the bend", abs(L["bends"][0][1] - 90) < 1)
MENUS[:] = []
w.context_menu(None, 110, 90)
labels = [lab for lab, _f in MENUS[0].actions] if MENUS else []
check("right-click the connector: its menu", any("Colour" in x for x in labels) and any("Delete" in x for x in labels))
w.delete()
check("Delete: the connector goes, the buttons stay", not pg["links"] and len(pg["items"]) == 2)
w.picked = {"p2"}
w.new_layer.__func__  # (exists)
with mock.patch.object(Q.QtWidgets.QInputDialog, "getText", return_value=("Notes", True), create=True):
    w.new_layer()
check("a new layer with the picked on it", PX.layer(pg, "Notes") and p2.get("layer") == "Notes")
w.layer_toggle("Notes")
del DRAWN[:]
cv.paintEvent(None)
check("layer hidden: its button not drawn, not hit", not any(t == "HEAD" for k, t in DRAWN if k == "text") and
      PM.hit_any(pg, 170, 45, True) is None)
w.layer_toggle("Notes")
with mock.patch.object(Q.QtWidgets.QInputDialog, "getMultiLineText", return_value=("Remember:\nkey the heels",
                                                                                  True), create=True):
    w.add_note(10, 120)
nt = [i for i in pg["items"] if i.get("note")]
check("a sticky note with two lines", nt and nt[0]["label"] == "Remember:\nkey the heels")
st, hid = PX.toolbar_state(w._spec_ids())
PX.section_move(st, "File", -20)
w.save_toolbar(st, set(hid) | {"undo"})
check("your toolbar: File first, Undo hidden", w.tools[0][0] == "File" and not w.tool_by_id["undo"].isVisible()
      and "Undo" not in [b_.word for _s, b_ in w.tools])
PX.set_toolbar({})
w._layout_tools()
check("back to the usual: Create first, the Connect section there", w.tools[0][0] == "Create" and
      any(s_ == "Connect" for s_, _b in w.tools))
tris = [((-1.0, 0.0), (1.0, 0.0), (0.0, 2.0))] * 3
with mock.patch.object(PX, "mesh_triangles", return_value=tris), \
        mock.patch.object(PM, "fit_view", return_value=(10.0, 100.0, 200.0)):
    w.silhouette_picture(pg)
pic = pg.get("picture") or {}
check("silhouette picture from the meshes' triangles: kept in the picker, where they land on the page",
      pic.get("kind") == "silhouette" and pic["x"] == 90.0 and pic["w"] == 20.0 and pic["h"] == 20.0)
print("%d/%d passed" % (sum(ok), len(ok)))
