# 5.7.1: the new window filled once (Maya fills it itself - 5.7.0 had two), Pop out (each page in its own panel,
# the new look), no button text cut off (also in a wider font, like Maya's), the old window's header buttons,
# the tool's description, Copy error report, Simple view
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["GUS_REAL_QT"] = "1"
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
for name in ("headsUpDisplay", "iconTextCheckBox", "nodeIconButton", "canvas", "image", "palettePort",
             "checkBoxGrp", "textFieldButtonGrp", "radioCollection", "radioButton", "intSlider", "floatSlider",
             "playbackOptions", "workspace", "channelBox", "shelfLayout", "colorIndexSliderGrp",
             "attrColorSliderGrp", "swatchDisplayPort", "iconTextRadioButton", "iconTextRadioCollection"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
cmds.undoInfo = mock.MagicMock(return_value=True)
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.newui.qt import QtCore, QtWidgets
QtCore.qInstallMessageHandler(lambda *a: None)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from gus_rigtool.newui import window as W, theme
from gus_rigtool.newui import qt as QT
from gus_rigtool.core import ui, utils
ROOT = os.path.join(os.getcwd(), "..")

# --- 1. Maya fills a window itself when it makes it (its uiScript): the window is filled once
hosts, made = {}, []
def workspaceControl(name, **k):
    if k.get("exists"):
        return name in hosts
    if k.get("query"):
        return "Gus_Rigtool"
    if k.get("edit"):
        return name
    hosts[name] = QtWidgets.QWidget()
    QtWidgets.QVBoxLayout(hosts[name])
    made.append(name)
    exec(k["uiScript"])                                  # like Maya: the script runs as the window is made
    return name
def deleteUI(name, **k):
    w = hosts.pop(name, None)
    if w is not None:
        w.deleteLater()
cmds.workspaceControl = workspaceControl
real_delete = cmds.deleteUI
cmds.deleteUI = lambda *a, **k: deleteUI(a[0]) if a and a[0] in hosts else real_delete(*a, **k)
with mock.patch.object(QT, "maya_widget", lambda name, kind="layout": hosts.get(name)):
    f = W.show()
    count = len([x for x in hosts[W.WS].findChildren(W.Frame) if W.alive(x)])
    check("the new window opens with ONE page inside (Maya fills it, the tool doesn't fill it again)", count == 1)
    W.show("behaviour")
    check("...asked again (the shelf button twice): still one, on Behaviour", len(
        [x for x in hosts[W.WS].findChildren(W.Frame) if W.alive(x)]) == 1 and made.count(W.WS) == 1 and
        f.areas["controls"].current == ("behaviour", None))
    W.restore()
    check("...Maya fills it again (a docked window at start-up): still one",
          len([x for x in hosts[W.WS].findChildren(W.Frame) if W.alive(x)]) == 1)

    # --- 2. Pop out
    hosts[W.WS].resize(700, 900); hosts[W.WS].show(); app.processEvents()
    pop = f.pop_out()
    check("Pop out: Behaviour in its own panel, in the new look", W.alive(pop) and W.pop_name("behaviour") in hosts and
          isinstance(pop, W.PopFrame))
    pp = pop.body.pages["behaviour"]
    mp = f.areas["controls"].pages["behaviour"]
    pp.fields["q7p_behaviour_LimMin"].widget.setText("-10")
    pp.fields["q7p_behaviour_LimMax"].widget.setText("10")
    mp.fields["q7_behaviour_LimMin"].widget.setText("-45")
    mp.fields["q7_behaviour_LimMax"].widget.setText("90")
    from gus_rigtool.core import limits
    ctl = cmds.ls(createNode("transform", name="L_wrist_IK_ctrl"), long=True)[0]
    cmds.select(ctl)
    got = []
    with mock.patch.object(limits, "set_limit", lambda nodes, ch, lo, hi: got.append((lo, hi)) or 1):
        [b for b in pp.cards[0].findChildren(QtWidgets.QPushButton) if b.text() == "Apply to the selected controls"
         ][0].click()
        [b for b in mp.cards[0].findChildren(QtWidgets.QPushButton) if b.text() == "Apply to the selected controls"
         ][0].click()
    check("...the panel and the main window each use their own fields (-10..10 there, -45..90 here)",
          got == [(-10.0, 10.0), (-45.0, 90.0)])
    f.go(("controls_tab", 2)); app.processEvents()
    pop2 = f.pop_out()
    check("Pop out the Controls tab: Make / Edit shape in it, on the page you were on (several panels open)",
          W.alive(pop2) and pop2.body.current == ("controls_tab", 2) and W.alive(pop) and
          [t.text() for t in pop2.tabs.findChildren(QtWidgets.QPushButton)] == ["Make", "Edit shape"])
    opened = []
    with mock.patch.object(ui, "open_panel", lambda k: opened.append(k)):
        f.go(("skin", None)); app.processEvents()
        f.pop_out()
    check("Pop out a page not redone yet (Skin): its own panel, as before", opened == ["skin"])

# --- 3. no button text cut off - also in a wider font, like Maya's
f = W.Frame(); f.show()
crops = {}
for font in ("13px", "15px"):
    with mock.patch.object(theme, "stylesheet", (lambda real: lambda a: real(a).replace("font-size: 13px",
                                                                                         "font-size: " + font))(
            theme.stylesheet)):
        for width in (300, 420, 700):
            f.resize(width, 900)
            for sub in [("controls_tab", 1), ("controls_tab", 2), ("behaviour", None), ("attrs", None),
                        ("channels", None), ("spaces", None), ("follow", None), ("stick", None)]:
                f.go(sub)
                for _ in range(3):
                    app.processEvents()
                got = W.cut_off(f.areas["controls"])
                if got:
                    crops["%s %s@%d" % (font, sub[0], width)] = got[:3]
check("no button text cut off (Delete, Load...): every Controls page, 300 / 420 / 700 px, normal and wider font",
      not crops)
if crops:
    print("  ", list(crops.items())[:4])

# --- 4. the old window's good parts
f.resize(700, 900); f.go(("behaviour", None)); app.processEvents()
names = [b.text() for b in f.head_buttons.findChildren(QtWidgets.QPushButton)]
check("the header: Favourite, Pop out, Guide, Simple / Full view, What's new, Update... (as in the old window)",
      names[0] in ("☆ Favourite", "★ Favourite") and names[1:3] == ["Pop out", "Guide"] and
      names[3] in ("Full view", "Simple view") and names[4:] == ["What's new", "Update..."])
check("the tool's own description under the sub-pages", "limits" in f.subtitle.text().lower())
import contextlib, io
try:
    raise RuntimeError("boom")
except RuntimeError as e:
    with contextlib.redirect_stdout(io.StringIO()):          # the report it prints has machine paths
        ui.report_error(e, "test")
check("after an error: 'Copy error report' on the status line", f.copy_error.isVisibleTo(f) and
      "Error" in f.status.text())
utils.save_setting("viewMode", "simple")
f2 = W.Frame(); f2.go(("attrs", None))
order = [c for c in f2.areas["controls"].pages["attrs"].cards if c.title.startswith("Order")]
check("Simple view: a tool's advanced sections start closed (Attributes > Order), as in the old window",
      order and order[0].closed)

# --- 5. favourites: the row at the top (the old window's My tools row) and the floating bar
from gus_rigtool.newui import favourites as FV
from gus_rigtool import registry
utils.save_setting("myTools", None)
f3 = W.Frame(); f3.resize(700, 900); f3.show(); f3.go(("behaviour", None)); app.processEvents()
shown = [b.property("fav") for b in f3.favs.findChildren(QtWidgets.QToolButton) if b.property("fav")]
check("the favourites row: your My tools from the old window (the same list)", shown == FV.keys() and
      shown == [registry.resolve(k)[0] for k in registry.MY_TOOLS if registry.resolve(k)[0] != "home"])
extras = [b.text() for b in f3.favs.findChildren(QtWidgets.QToolButton) if not b.property("fav")]
check("...then + (choose), Map (where everything is), Bar (the floating bar)", extras == ["+", "Map", "Bar"])
star = [b for b in f3.head_buttons.findChildren(QtWidgets.QPushButton) if "Favourite" in b.text()][0]
star.click(); app.processEvents()
check("☆ Favourite on Behaviour: added at the end of the row, the star filled", FV.keys()[-1] == "behaviour" and
      star.text() == "★ Favourite" and "behaviour" in [b.property("fav") for b in
                                                     f3.favs.findChildren(QtWidgets.QToolButton)])
FV.move("behaviour", -1)
check("right-click > Move left: one place earlier", FV.keys()[-2] == "behaviour")
went = []
with mock.patch.object(W.Frame, "go_key", lambda self, k, section=None: went.append(k)):
    W._frame["w"] = f3
    [b for b in f3.favs.findChildren(QtWidgets.QToolButton) if b.property("fav") == "select"][0].click()
check("click a favourite: the window goes to that tool", went == ["select"])
star.click(); app.processEvents()
check("☆ again: taken off", "behaviour" not in FV.keys() and star.text() == "☆ Favourite")
d = FV.choose()
for k, c in d.ticks:
    c.setChecked(k in ("controls_tab", "skin", "checker"))
d.save()
check("+ : tick Controls, Skin, Checker - the row shows those (your order kept, the new one after)",
      [b.property("fav") for b in f3.favs.findChildren(QtWidgets.QToolButton) if b.property("fav")] ==
      ["controls_tab", "checker", "skin"])
f3.resize(400, 900); app.processEvents()
check("narrow: only the coloured squares (the name on hover)", all(not b.text() for b in
      f3.favs.findChildren(QtWidgets.QToolButton) if b.property("fav")))
check("a square says which tool (initials) in its area's colour", FV.initials("controls_tab") == "Co" and
      FV.initials("checker") == "Ch" and FV.initials("stick") == "ST" and FV.area_colour("skin") == theme.colour("skin"))
bar = FV.show_bar(); app.processEvents()
check("the floating bar: your favourites as squares, a menu", list(bar.buttons) == ["controls_tab", "checker", "skin"]
      and bar.isVisible())
check("...stays in front of Maya, on the Mac too (a tool window, like the Animtool bar)",
      bool(bar.windowFlags() & QtCore.Qt.Tool))
went = []
with mock.patch.object(W.Frame, "go_key", lambda self, k, section=None: went.append(k)):
    bar.buttons["skin"].click()
check("...click Skin on the bar: the window goes to Skin", went == ["skin"])
bar.flip(); app.processEvents()
check("...a column instead of a row (remembered)", bar.vertical and utils.load_setting(FV.BAR_KEY, {}).get("vertical"))
FV.toggle("select"); app.processEvents()
check("...a favourite added anywhere shows on the bar too", "select" in bar.buttons)
bar.move(120, 80); bar._drag = QtCore.QPoint(0, 0); bar.mouseReleaseEvent(None)
check("...where you drag it is remembered", utils.load_setting(FV.BAR_KEY, {}).get("x") == 120)
FV.close_bar()
check("...Close the bar", FV._bar["w"] is None and utils.load_setting(FV.BAR_KEY, {}).get("open") is False)
print("%d/%d passed" % (sum(ok), len(ok)))
