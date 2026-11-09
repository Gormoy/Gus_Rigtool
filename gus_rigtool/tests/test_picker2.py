# Gus Animtool 3.0 picker: automatic layout (pages, outlines, mirrored sides, no overlaps, finger grid), editing
# (move, resize, shape, colour, align, distribute, mirror, duplicate, delete, add buttons / sliders / commands,
# pages, undo), saved in the rig profile; the Qt window (with a stand-in Qt): paint, click / shift / band select,
# zoom, edit mode drag, keys, menus, sliders
import os, sys, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
import fakeqt
fakeqt.install()
import pickrig
from gus_animtool import anim as A, pickmodel as PM
_opts = {"library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
cmds.undoInfo = mock.MagicMock()
RIG = pickrig.rig()
for r in RIG:                                                # the controls exist in the scene
    t = cmds.createNode("transform", name=r["node"])
    cmds.createNode("nurbsCurve", name=r["node"] + "Shape", parent=t)
PM.read_rig = lambda ns=None: pickrig.rig()

# --- labels / geometry
print("labels:", [PM.label_of(n) for n in ("L_arm_fk1_ctrl", "R_leg_ik_ctrl", "cog_ctrl", "spine_L_ctrl")])
print("hull of a square + middle:", PM.hull([(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)]))
diamond = {"x": 0, "y": 0, "w": 10, "h": 10, "shape": "diamond"}
print("diamond hit centre / corner:", PM.contains(diamond, 5, 5), PM.contains(diamond, 0.5, 0.5))

# --- automatic layout
pk = PM.auto("")
print("pages:", [(p["name"], len(p["items"])) for p in pk["pages"]])
for p in pk["pages"]:
    its = p["items"]
    ov = sum(1 for i, a in enumerate(its) for b in its[i + 1:] if PM.overlaps(a, b))
    ids = {i["id"]: i for i in its}
    bad = [i["label"] for i in its if i.get("twin") and abs((i["x"] + i["w"] / 2) + (ids[i["twin"]]["x"] + ids[i["twin"]]["w"] / 2) - p["width"]) > 0.5]
    print("  %s: overlaps %d, twins not mirrored %s, inside the page %s" % (p["name"], ov, bad,
          all(i["x"] >= 0 and i["y"] >= 0 and i["x"] + i["w"] <= p["width"] + 0.5 and i["y"] + i["h"] <= p["height"] + 0.5 for i in its)))
body = pk["pages"][0]
by = {i["nodes"][0]: i for i in body["items"]}
print("left on the right (front view):", by["L_leg_ik_ctrl"]["x"] > body["width"] / 2 > by["R_leg_ik_ctrl"]["x"],
      "| head above hips:", by["head_ctrl"]["y"] < by["hips_ctrl"]["y"], "| spine centred:",
      abs(by["chest_ctrl"]["x"] + by["chest_ctrl"]["w"] / 2 - body["width"] / 2) < 0.5,
      "| eye outline kept:", [i["shape"] for i in pk["pages"][1]["items"] if i["nodes"][0] == "L_eye_ctrl"])
hands = [p for p in pk["pages"] if p["name"] == "Hands"][0]
hb = {i["nodes"][0]: i for i in hands["items"]}
print("hands grid: index1 above index3:", hb["L_index1_ctrl"]["y"] < hb["L_index3_ctrl"]["y"], "| same column:",
      hb["L_index1_ctrl"]["x"] == hb["L_index3_ctrl"]["x"], "| thumb inside (left hand: towards the middle):",
      hb["L_thumb1_ctrl"]["x"] < hb["L_pinky1_ctrl"]["x"], "| thumb a row lower:", hb["L_thumb1_ctrl"]["y"] > hb["L_index1_ctrl"]["y"])

# --- editing
page = body
a, b, c = by["head_ctrl"], by["neck_ctrl"], by["chest_ctrl"]
print("hit head centre:", PM.hit(page, a["x"] + a["w"] / 2, a["y"] + a["h"] / 2)["label"], "| in a box:",
      sorted(i["label"] for i in PM.in_rect(page, a["x"] - 1, a["y"] - 1, a["x"] + a["w"] + 1, a["y"] + a["h"] + 1)))
PM.move([a], 10, 5, grid=5)
print("moved on the grid:", a["x"] % 5 == 0 and a["y"] % 5 == 0)
w0 = a["w"]; PM.resize([a], 2.0); print("resized x2:", round(a["w"] / w0, 2))
PM.align([a, b, c], "left"); print("aligned left:", a["x"] == b["x"] == c["x"])
PM.distribute([a, b, c], "y")
ys = sorted(i["y"] + i["h"] / 2 for i in (a, b, c)); print("distributed:", round(ys[1] - ys[0], 3) == round(ys[2] - ys[1], 3))
PM.set_value([a], "shape", "ellipse"); print("shape:", a["shape"], a["points"])
lw = by["L_arm_ik_ctrl"]; rw = by["R_arm_ik_ctrl"]
PM.move([lw], 7, 0)
PM.mirror(page, [lw], "")
print("mirror keeps the twin mirrored:", abs((lw["x"] + lw["w"] / 2) + (rw["x"] + rw["w"] / 2) - page["width"]) < 1e-6,
      "| its controls:", rw["nodes"])
solo = PM.add_items(page, ["L_toe_ctrl"], 5, 5)[0]
tw = PM.mirror(page, [solo], "")[0]
print("new twin:", tw["nodes"], "| linked:", solo["twin"] == tw["id"] and tw["twin"] == solo["id"])
d = PM.duplicate(page, [solo])[0]; print("duplicate:", d["id"] != solo["id"], d["nodes"], d["twin"])
PM.delete(page, [solo]); print("delete unlinks the twin:", tw["twin"], "| gone:", PM.by_id(page, [solo["id"]]))
grp = PM.add_group_button(page, ["L_arm_fk1_ctrl", "L_arm_fk2_ctrl"], "L arm FK"); print("group button:", grp["nodes"], grp["label"])
cmds.addAttr("L_arm_settings_ctrl", longName="ikfk", attributeType="double", minValue=0, maxValue=1)
sl = PM.add_widget(page, "slider", cmds.ls("L_arm_settings_ctrl", long=True)[0], "ikfk")
print("slider:", sl["kind"], sl["attr"], sl["min"], sl["max"], "| set 0.25:", PM.set_slider(sl, "", 0.25),
      cmds.getAttr("L_arm_settings_ctrl.ikfk"))
ck = PM.add_widget(page, "check", cmds.ls("L_arm_settings_ctrl", long=True)[0], "ikfk")
print("check toggles:", PM.toggle(ck, ""), PM.toggle(ck, ""))
cm = PM.add_command(page, "Hide arms", "print('hi')"); print("command:", cm["kind"], cm["label"])
newp = PM.add_page(pk, " Props "); print("page added:", newp["name"], len(pk["pages"]))
h = PM.History(); h.push(pk); before = len(pk["pages"]); pk["pages"].pop()
back = h.undo(pk); print("undo:", len(back["pages"]) == before, "| redo:", len(h.redo(back)["pages"]) == before - 1)

# --- saved in the rig profile
PM.save(pk, "")
again = PM.load("", make=False)
print("saved / loaded:", len(again["pages"]) == len(pk["pages"]), "| same buttons:",
      [len(p["items"]) for p in again["pages"]] == [len(p["items"]) for p in pk["pages"]], "| no namespace:",
      all(":" not in n for p in again["pages"] for i in p["items"] for n in i["nodes"]))
fresh = PM.new_id(); print("ids keep going after load:", int(fresh[1:]) > max(int(i["id"][1:]) for p in again["pages"] for i in p["items"]))
print("in the rig's own file Save keeps it IN the rig:", PM.where_from("") == "rig", "|",
      cmds.attributeQuery(PM.RIG_ATTR, node=PM.rig_node(""), exists=True))
_ed = PM.rig_editable
PM.rig_editable = lambda ns=None: False                     # a referenced rig: Save is yours, on this computer
mine = PM.load("", make=False); mine["pages"][0]["items"][0]["x"] += 50
print("referenced: Save is yours:", PM.save(mine, "") == "yours", "| yours wins:", PM.where_from("") == "yours")
PM.forget(""); print("back to the rig's picker:", PM.where_from("") == "rig")
PM.rig_editable = _ed
cmds.deleteAttr(PM.rig_node("") + "." + PM.RIG_ATTR) if hasattr(cmds, "deleteAttr") else \
    _n(PM.rig_node("")).user.pop(PM.RIG_ATTR, None)
print("nothing saved -> automatic:", PM.load("", make=False))

# --- the Qt window (stand-in Qt)
cmds.workspaceControl = mock.MagicMock(return_value="gusAnimtoolPicker")
cmds.scriptJob = mock.MagicMock()
from gus_animtool import pickerqt as Q
from fakeqt import Event, Qt, DRAWN, BUTTONS, MENUS, QMessageBox
w = Q.build()
cv = w.canvas
print("window: pages", w.tabs.tabs, "| buttons on the page:", len(w.page()["items"]))
cv.frame(); cv.paintEvent(None)
print("painted:", sum(1 for k, _t in DRAWN if k == "fill") >= len(w.page()["items"]), "| labels drawn:",
      any(t == "head" for k, t in DRAWN if k == "text"))
def at(it):
    p = cv.to_screen(it["x"] + it["w"] / 2, it["y"] + it["h"] / 2)
    return p.x(), p.y()
items = {i["nodes"][0]: i for i in w.page()["items"]}
x, y = at(items["head_ctrl"])
cv.mousePressEvent(Event(x, y, Qt.LeftButton)); cv.mouseReleaseEvent(Event(x, y, Qt.LeftButton))
print("click:", [A.short(n) for n in cmds.ls(selection=True)])
x2, y2 = at(items["neck_ctrl"])
cv.mousePressEvent(Event(x2, y2, Qt.LeftButton, Qt.ShiftModifier)); cv.mouseReleaseEvent(Event(x2, y2, Qt.LeftButton))
w.selection_changed()
print("shift-click adds:", sorted(A.short(n) for n in cmds.ls(selection=True)))
legs = [items[n] for n in ("L_leg_fk2_ctrl", "L_leg_fk3_ctrl")]
x0 = min(i["x"] for i in legs) - 1; y0 = min(i["y"] for i in legs) - 1
x1 = max(i["x"] + i["w"] for i in legs) + 1; y1 = max(i["y"] + i["h"] for i in legs) + 1
s0, s1 = cv.to_screen(x0, y0), cv.to_screen(x1, y1)
blank = PM.hit(w.page(), x0, y0)
cv.mousePressEvent(Event(s0.x(), s0.y(), Qt.LeftButton)); cv.mouseMoveEvent(Event(s1.x(), s1.y()))
cv.mouseReleaseEvent(Event(s1.x(), s1.y(), Qt.LeftButton))
print("drag a box selects:", sorted(A.short(n) for n in cmds.ls(selection=True)), "(started on blank:", blank is None, ")")
sc = cv.scale; cv.wheelEvent(Event(100, 100, delta=120)); print("wheel zooms in:", cv.scale > sc)
cv.mousePressEvent(Event(10, 10, Qt.MiddleButton)); cv.mouseMoveEvent(Event(40, 25)); cv.mouseReleaseEvent(Event(40, 25, Qt.MiddleButton))
print("middle drag pans:", True)
cv.frame()
# edit mode
w.edit_btn.setChecked(True)
print("edit mode:", w.editing, "| edit bar shown:", w.edit_bar.isVisible(), "| use bar hidden:", not w.use_bar.isVisible())
head = items["head_ctrl"]; hx = head["x"]
x, y = at(head)
cv.mousePressEvent(Event(x, y, Qt.LeftButton)); cv.mouseMoveEvent(Event(x + 30 * cv.scale, y)); cv.mouseReleaseEvent(Event(x + 30 * cv.scale, y, Qt.LeftButton))
print("drag moves the button:", round(head["x"] - hx, 3), "| unsaved:", w.dirty, "| Save button:", w.save_btn.label)
cv.keyPressEvent(Event(key=Qt.Key_Right, mods=Qt.ShiftModifier)); print("Shift+Right nudges 10:", round(head["x"] - hx, 3))
cv.keyPressEvent(Event(key=Qt.Key_Z, mods=Qt.ControlModifier)); head = {i["id"]: i for i in w.page()["items"]}[head["id"]]
print("Ctrl+Z:", round(head["x"] - hx, 3))
n0 = len(w.page()["items"]); w.picked = {head["id"]}; cv.keyPressEvent(Event(key=Qt.Key_Delete))
print("Delete:", n0 - len(w.page()["items"]))
cv.keyPressEvent(Event(key=Qt.Key_Z, mods=Qt.ControlModifier)); print("undo the delete:", len(w.page()["items"]) == n0)
w.picked = {head["id"]}
w.recolour(); print("colour:", [round(c, 2) for c in PM.by_id(w.page(), [head["id"]])[0]["rgb"]])
w.relabel(); print("label:", PM.by_id(w.page(), [head["id"]])[0]["label"])
MENUS[:] = []
w.context_menu(None, head["x"] + 1, head["y"] + 1)
m = MENUS[0]
print("edit menu:", [lab for lab, _f in m.actions])
m.find("ellipse")(); print("shape from the menu:", PM.by_id(w.page(), [head["id"]])[0]["shape"])
cmds.select("L_toe_ctrl")
n0 = len(w.page()["items"]); m.find("A button per selected control")(); print("add here:", len(w.page()["items"]) - n0)
w.background(); print("background:", w.page()["bg"])
w.new_page(); print("new page:", w.tabs.tabs[-1], "| on it:", w.index == len(w.picker["pages"]) - 1)
cmds.select("L_arm_settings_ctrl"); cmds.channelBox = mock.MagicMock(return_value=["ikfk"])
w.add_widget("slider", 20, 20); sl = w.page()["items"][-1]
print("slider added:", sl["kind"], sl["attr"])
w.edit_btn.setChecked(False)
r = cv._path(sl)[1]
cv.mousePressEvent(Event(r.left() + r.width() * 0.75, r.top() + 2, Qt.LeftButton)); cv.mouseReleaseEvent(Event(0, 0, Qt.LeftButton))
print("slider drag sets the attribute:", round(cmds.getAttr("L_arm_settings_ctrl.ikfk"), 2))
w.save(); print("saved:", not w.dirty, "| in the rig:", len((PM.rig_picker("") or {}).get("pages", [])))
MENUS[:] = []
w.context_menu(None, -50, -50)
print("use menu:", [lab for lab, _f in MENUS[0].actions])
QMessageBox.answer[0] = QMessageBox.Yes
w.edit_btn.setChecked(True); w.auto(); print("auto layout again:", [p["name"] for p in w.picker["pages"]], "| unsaved:", w.dirty)
cv.keyPressEvent(Event(key=Qt.Key_Z, mods=Qt.ControlModifier)); print("undo it:", [p["name"] for p in w.picker["pages"]])
print("use buttons:", [b.label for b in BUTTONS if b.label in ("All", "Left", "Right", "Page", "Twin", "IK / FK", "Reset", "Key")])

# --- 5.6.21: every new shape, a frame and a text drawn; the frame's title selects its buttons' controls
pg = w.page()
sel5621 = [i for i in pg["items"] if i.get("kind") == "select"][:len(PM.SHAPES)]
for it, shape in zip(sel5621, PM.SHAPES):
    it["shape"] = shape
fr5621 = PM.group_frame(pg, sel5621[:2], "Left Arm")
PM.add_text(pg, "BODY", 5, 5)
del DRAWN[:]
w.set_editing(True); cv.paintEvent(None); w.set_editing(False); cv.paintEvent(None)
print("5.6.21 drawn: the frame's title and the text:", any(t.startswith("Left Arm") for k, t in DRAWN if k == "text"),
      any(t == "BODY" for k, t in DRAWN if k == "text"))
cmds.select(clear=True)
tx, ty = cv.to_screen(fr5621["x"] + 4, fr5621["y"] + 3).x(), cv.to_screen(fr5621["x"] + 4, fr5621["y"] + 3).y()
cv.mousePressEvent(Event(tx, ty, Qt.LeftButton)); cv.mouseReleaseEvent(Event(tx, ty, Qt.LeftButton))
want = sorted(A.short(n) for m in PM.frame_members(pg, fr5621) for n in w.nodes_of(m))
print("5.6.21 click the frame's title: its controls", sorted(A.short(n) for n in cmds.ls(selection=True)) == want, want)
from fakeqt import TOOLS
print("5.6.21 quick buttons:", [b.label for b in TOOLS][:22])

# --- 5.6.22: the Item panel, text size, pins, side by side
w.set_editing(True)
first = [i for i in w.page()["items"] if i.get("kind") == "select"][0]
w.picked = {first["id"]}
cv.paintEvent(None)
print("5.6.22 Item panel shown in Edit:", w.panel.isVisible(), "| shows the picked one's text:",
      w.fields["label"][1].text() == (first.get("label") or ""))
w.panel_set("text_size", 14.0); w.panel_set("label_pos", "below"); w.panel_set("rot", 30.0)
print("5.6.22 panel sets text size / place / turn:", first.get("text_size"), first.get("label_pos"), first.get("rot"))
w.toggle_pin()
print("5.6.22 pinned: it keeps a window place:", first.get("pin"), "px" in first and "pw" in first)
cv.offset = fakeqt.QPointF(cv.offset.x() + 50, cv.offset.y()); cv.sync_pins(w.page())
sp = cv.to_screen(first["x"], first["y"])
print("5.6.22 ... the view pans, it stays put in the window:", abs(sp.x() - first["px"]) < 1e-6)
w.toggle_pin()
w.set_editing(False)
if len(w.picker["pages"]) > 1:
    w.set_side(1 if w.index == 0 else 0)
    del DRAWN[:]
    cv.paintEvent(None)
    print("5.6.22 side by side: the other page's name drawn:", any(t == w.side_page()["name"] for k, t in DRAWN
                                                                  if k == "text"))
    w.set_side(None)
