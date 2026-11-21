# 5.7.9: one look in the new window (the 5.6 window = "Legacy look"), the Gus_Rigtool shelf in the new look (the
# sidebar's order, Build and Publish only, right-click: the tool's settings), the favourites bar in Gus's mock-up
# layout (profiles, Row / 2R / Col / Grid, size, names, right-click: the tool's options), Home redone, the
# selection read once (no flattening), no legacy page left
exec(open("test_570.py").read().split("# --- 1.")[0])
from unittest import mock
from gus_rigtool.newui import window as W, widgets, favourites as FV, tiles, homepage
from gus_rigtool.newui.qt import QtCore, QtGui
from gus_rigtool import main as M
from gus_rigtool.core import utils

def settle():
    for _ in range(3):
        app.processEvents()

# --- 1. one look; the legacy look one click away
st = open(os.path.join(ROOT, "tools", "settings_tab.py")).read()
check("Settings > Window: 'New window' / 'Legacy look' (today's look 5.7 taken out)", '"Legacy look"' in st and
      '"New window"' in st and "use_look" not in st and not hasattr(theme, "new_look"))
check("no legacy page inside the new window any more (Home is redone)", not hasattr(W, "OldPage") and
      "home" in W.NEW_LOOK)

# --- 2. the Gus_Rigtool shelf
groups = M._shelf_buttons()
flat = [b[1] for g in groups for b in g]
check("the shelf: the sidebar's order, a group per area (8 groups)", len(groups) == 8 and flat[:2] == ["home", "build"]
      and flat[-3:] == ["settings", "main", "reload"])
check("...Build and Publish on it, Build rig not (it's Build's)", "build" in flat and "publish" in flat and
      "build_rig" not in flat)
made, seps = [], []
real = (cmds.shelfButton if hasattr(cmds, "shelfButton") else None,
        cmds.separator if hasattr(cmds, "separator") else None)
with mock.patch.object(cmds, "shelfLayout", lambda *a, **k: [] if k.get("query") else True, create=True), \
        mock.patch.object(cmds, "shelfButton", lambda *a, **k: made.append(k), create=True), \
        mock.patch.object(cmds, "separator", lambda *a, **k: seps.append(k), create=True), \
        mock.patch.object(M.mel, "eval", lambda *a, **k: None):
    M.make_shelf()
tools = [k for k in made if k.get("label") in [b[0] for g in groups for b in g]]
grp = [k for k in tools if k["label"] == "Groups"][0]
check("...a gap between the areas", len(seps) >= 7)
check("...right-click on a tool: 'Settings of Groups...', favourites, Pop out", grp.get("menuItem") and
      grp["menuItem"][0][0] == "Settings of Groups..." and len(grp["menuItem"]) == 3)
check("...the new icons (every tool, the shortcuts)", all(os.path.isfile(os.path.join(ROOT, "icons", "gr_%s.png" %
                                                                                       k)) for k in flat))
img = QtGui.QImage(os.path.join(ROOT, "icons", "gr_skin.png"))
bar = QtGui.QColor(img.pixel(16, 28))
check("...the bar along the bottom in the area's colour (Skin: pink)", img.width() == 32 and bar.red() > 150 and
      bar.green() < 140)

# --- 3. the favourites bar
FV.set_keys(["select", "groups", "mirror", "controls_tab"])
utils.save_setting(FV.BAR_KEY, {"size": 34})
b = FV.FavBar(); b.show(); settle()
check("the bar: your favourites as the new tiles", list(b.buttons) == FV.keys() and
      all(bt.focusPolicy() == QtCore.Qt.NoFocus for bt in b.buttons.values()))
check("...a short row stays tight: only the essentials (the rest under =), as wide as its tiles",
      b.width() <= b.tiles.sizeHint().width() + 60 and not b.mode_buttons)
b.toggle_bar_settings(); settle()
check("...= opens the bar's settings under it: Row / 2R / Col / Grid, names, size, Edit",
      b.strip.isVisible() and set(b.mode_buttons) == {"row", "2r", "col", "grid"})
b.mode_buttons["2r"].click(); settle()
check("...2 rows: the tiles in two rows", b.shape() == "2r" and b.grid.rowCount() == 2)
b.set_shape("col"); settle()
check("...a column: narrow and even (one width)", b.vertical and b.width() <= 80)
b.set_size(80); settle()
check("...the size stays 24 - 52 px", b.wanted_size() == 52)
ev = QtGui.QWheelEvent(QtCore.QPointF(5, 5), QtCore.QPointF(5, 5), QtCore.QPoint(0, 0), QtCore.QPoint(0, -120),
                       QtCore.Qt.NoButton, QtCore.Qt.ControlModifier, QtCore.Qt.NoScrollPhase, False)
b.wheelEvent(ev); settle()
check("...Ctrl + mouse wheel: smaller", b.wanted_size() == 50)
tri = QtGui.QImage(tiles.image("groups", 32, True))
check("...a corner triangle where right-click has options (Groups has options)", tiles.has_options("groups") and
      QtGui.QColor(tri.pixel(29, 24)).lightness() > 200 and
      QtGui.QColor(tiles.image("groups", 32, False).pixel(29, 24)).lightness() < 200)
b.set_shape("row"); b.show_strip("groups"); settle()
rows = [w for w in b.strip.findChildren(QtWidgets.QWidget) if w.property("option")]
check("right-click a tile: its options in a strip under the bar (Groups: %d)" % len(rows), b.strip.isVisible() and
      rows and b.strip.y() >= b.y() + b.height())
cb = [w for w in rows if isinstance(w, QtWidgets.QCheckBox)][0]
name = cb.property("option")
was = utils.tool_settings(__import__("gus_rigtool.tools.group_maker", fromlist=["x"]).SETTINGS_KEY, {}).get(name)
cb.setChecked(not cb.isChecked()); settle()
now = utils.tool_settings(__import__("gus_rigtool.tools.group_maker", fromlist=["x"]).SETTINGS_KEY, {}).get(name)
check("...a change is saved at once (as in Settings)", now == cb.isChecked() and now != was)
b.set_shape("col"); b.show_strip("mirror"); settle()
check("...beside a column: names above their boxes, narrow (Gus: B)", b.strip.width() <= 230 and
      b.strip.x() >= b.x() + b.width())
utils.save_setting(FV.BAR_KEY, {"size": 34, "labels": True, "shapes": {FV.current(): "row"}})
FV.set_keys(["select", "stick"])
b.hide_strip(); b.build(); settle()
names = [w for w in b.tiles.findChildren(QtWidgets.QLabel) if w.objectName() == "gusFavName"]
check("names under the tiles: on two lines when one needs it ('Stick to skin')", names and
      names[0].height() > names[0].fontMetrics().lineSpacing() * 1.5)
b.close()

# --- 4. Home redone
f = W.Frame(); f.resize(560, 1200); f.show(); f.go(("home", None)); settle()
a = f.areas["home"]
hp = a.widgets[("home", None)]
titles = [c.title for c in a._visual(("home", None))]
check("Home: Next step, the five steps, For what's selected, Any time", titles[0] == "Next step" and
      titles[1:6] == ["Guides", "Build", "Skin", "Controls", "Check & publish"] and titles[-1] == "Any time")
check("...each step with its state (empty scene: Guides is next)", hp.steps["guides"].chip.text() == "● Next" and
      hp.steps["build"].chip.text() == "To do" and hp.next_button.isVisibleTo(f))
with mock.patch.object(__import__("gus_rigtool.tools.home", fromlist=["x"]), "suggest",
                       lambda *a: ("Joint", [("Constrain", "constrain", None)])):
    f.on_selection(); settle()
check("...For what's selected follows the selection", "Joint" in hp.sel_what.text() and
      [w.text() for w in hp.sel_box.findChildren(QtWidgets.QPushButton)][:1] == ["Constrain  ›"])
check("...no lone 'Home' tab, the description once", not f.tabs.isVisible() and not f.subtitle.isVisible())
crops = {}
for width in (300, 326, 420):
    f.resize(width, 1100); settle()
    if W.cut_off(a):
        crops[width] = W.cut_off(a)[:2]
check("...nothing cut off at 300 / 326 / 420 px", not crops)
f.go(("settings", None)); settle()
check("Settings: no 'Selected' box (it has nothing to do with the selection)",
      not f.areas["settings"].selbox.isVisibleTo(f))

# --- 5. lighter: the selection read once, components counted without listing each one
check("edges counted from Maya's ranges (e[10:25] + e[3] = 17), not one by one",
      W.count_components(["m.e[10:25]", "m.e[3]", "m.vtx[1:4]", "grp"], ".e[") == 17)
calls = []
real_sel = W.selection
with mock.patch.object(W, "selection", lambda: (calls.append(1), real_sel())[1]):
    f.go(("controls_tab", 1), as_tool=True); settle()
    calls[:] = []
    f.on_selection(); settle()
check("one selection change: the selection read once (5.7.8: twice - the page and the status line)",
      len(calls) == 1)
print("%d/%d passed" % (sum(ok), len(ok)))
