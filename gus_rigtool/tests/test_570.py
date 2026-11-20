# 5.7.0: the new window (Qt, off-screen here): the frame, the Controls area drawn in the new look from the tools'
# own pages (nothing lost, nothing twice), nothing cut off at any width, the fields answer the tools' functions,
# the next step, pinning, search, the old window a click away
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["GUS_REAL_QT"] = "1"                  # this test uses the real Qt (PySide6), off-screen
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
for name in ("scriptJob", "headsUpDisplay", "iconTextCheckBox", "nodeIconButton", "canvas", "image", "palettePort",
             "checkBoxGrp", "textFieldButtonGrp", "radioCollection", "radioButton", "intSlider", "floatSlider",
             "playbackOptions", "workspace", "channelBox", "shelfLayout", "colorIndexSliderGrp",
             "attrColorSliderGrp", "swatchDisplayPort", "iconTextRadioButton", "iconTextRadioCollection"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
cmds.undoInfo = mock.MagicMock(return_value=True)
ROOT = os.path.join(os.getcwd(), "..")
import logging
from gus_rigtool.newui.qt import QtCore, QtWidgets
QtCore.qInstallMessageHandler(lambda *a: None)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from gus_rigtool import registry
from gus_rigtool.core import ui
from gus_rigtool.newui import proxy, record, render, window, nextstep, theme
CONTROLS = ["controls_tab", "behaviour", "attrs", "channels", "spaces", "follow", "stick"]

# --- 1. nothing lost, nothing twice: every control today's page makes is in the new one, once
def old_page(key):
    UI.clear(); _cur[0] = None
    cmds.columnLayout("root_" + key)
    ui._build_tool(key, "t_%s_" % key)
    kinds = ("button", "checkBox", "frameLayout", "optionMenu", "radioButtonGrp", "floatField", "intField",
             "textField", "textScrollList", "iconTextButton", "text", "radioButton")
    return sorted((v.get("kind"), n.replace("t_%s_" % key, "")) for n, v in UI.items()
                  if v.get("kind") in kinds and not n.startswith(("text", "button", "frameLayout", "checkBox",
                                                                   "optionMenu", "iconTextButton", "floatField",
                                                                   "radioButtonGrp", "textField", "intField")))
lost, twice, not_drawn, total = [], [], [], 0
for key in CONTROLS:
    rec = record.record(registry.module(key).build, "q7_%s_" % key)
    page = render.Page(key, rec, theme.colour("controls"))
    page.build()
    names = [n.replace("q7_%s_" % key, "") for _k, n, _l, how in page.inventory]
    total += len(page.inventory)
    not_drawn += ["%s: %s %s" % (key, k, n) for k, n, _l, how in page.inventory if how.startswith("not drawn")]
    twice += ["%s: %s" % (key, n) for n in set(names) if names.count(n) > 1]
    named_old = [n for _k, n in old_page(key)]
    lost += ["%s: %s" % (key, n) for n in named_old if n not in names and n not in
             [x.replace("q7_%s_" % key, "") for x in page.fields]]
check("nothing lost: every named control of today's 7 Controls pages is on the new pages (%d controls)" % total,
      not lost and total > 300)
if lost:
    print("   lost:", lost[:10])
check("nothing twice: no control appears twice", not twice)
check("every kind of control is drawn (none left as 'not known')", not not_drawn)
if not_drawn:
    print("  ", not_drawn[:10])

# --- 2. the window: every Controls sub-page, nothing cut off at 300 / 420 / 700 px
f = window.Frame()
f.show()
def cut_off(area):
    vp = area.scroll.viewport()
    bad = []
    for w in area.scroll.widget().findChildren(QtWidgets.QWidget):
        if not w.isVisibleTo(area.scroll.widget()) or w.width() <= 0:
            continue
        p = w.mapTo(vp, QtCore.QPoint(w.width(), 0))
        if p.x() > vp.width() + 1:
            bad.append((type(w).__name__, (w.text() if hasattr(w, "text") else w.objectName())[:30], p.x(),
                        vp.width()))
    return bad
crops = {}
subs = [("controls_tab", 1), ("controls_tab", 2)] + [(k, None) for k in CONTROLS[1:]]
for width in (300, 420, 700):
    f.resize(width, 900)
    for sub in subs:
        f.go(sub)
        for _ in range(3):
            app.processEvents()
        got = cut_off(f.areas["controls"])
        if got:
            crops["%s@%d" % (sub[0], width)] = got[:3]
check("nothing cut off: every Controls page at 300, 420 and 700 px wide", not crops)
if crops:
    print("  ", list(crops.items())[:4])
f.resize(700, 900); app.processEvents()
check("the sidebar: Home, the rig's 5 steps, Toolbox (names); narrow: icons only",
      [b.text() for k, b in f.nav.items()] == ["Home", "Build", "Skin", "Controls", "Connect", "Check && publish",
                                               "Toolbox"])
f.resize(400, 900); app.processEvents()
check("...narrow: icons only, the section names hidden", f.slim and not any(b.text() for b in f.nav.values())
      and not f.sec_labels[0].isVisibleTo(f))
f.resize(700, 900); app.processEvents()

# --- 3. the fields answer the tools' own functions (they don't know which window they're in)
from gus_rigtool.core import limits
f.go(("behaviour", None)); app.processEvents()
page = f.areas["controls"].pages["behaviour"]
page.fields["q7_behaviour_LimMin"].widget.setText("-45")
page.fields["q7_behaviour_LimMax"].widget.setText("90")
page.fields["q7_behaviour_LimCh"].widget.setCurrentIndex(5)
ctl = cmds.ls(createNode("transform", name="L_wrist_IK_ctrl"), long=True)[0]
cmds.select(ctl)
got = []
with mock.patch.object(limits, "set_limit", lambda nodes, ch, lo, hi: got.append((ch, lo, hi)) or 1):
    [b for b in page.cards[0].findChildren(QtWidgets.QPushButton) if b.text() == "Apply to the selected controls"
     ][0].click()
check("Behaviour > Limits: rz, -45, 90 typed in the new window - Apply limits rz -45 .. 90 (the tool's own code)",
      got == [("rz", -45.0, 90.0)])
check("...the old window's name for that field still goes to Maya (the proxy only takes the new window's)",
      proxy.REGISTRY.get("p_behaviour_LimMin") is None and "q7_behaviour_LimMin" in proxy.REGISTRY)
from gus_rigtool.tools import controls_tab as CT
made = []
with mock.patch.object(CT, "make", lambda *a: made.append(CT.page()) or ["|x"]):
    f.go(("controls_tab", 1)); app.processEvents()
    f.areas["controls"].grids[0].tiles["square"].click()
check("Make: one click on a shape makes the controls (the tool sees it's on its Make page)", made == [1])
f.go(("controls_tab", 2)); app.processEvents()
check("Edit shape: the tool knows it's on Edit shape (hover previews only there)", CT.page() == 2)
check("...the shape you clicked is marked on both pages", all(g.tiles["square"].isChecked()
                                                               for g in f.areas["controls"].grids))
f.go(("spaces", None)); app.processEvents()
sp = f.areas["controls"].pages["spaces"]
proxy.cmds.textScrollList("q7_spaces_Targets", edit=True, append="COG = COG_ctrl")
check("Spaces: a target the tool adds shows in its list", sp.fields["q7_spaces_Targets"].widget.count() >= 1 and
      proxy.cmds.textScrollList("q7_spaces_Targets", query=True, allItems=True)[-1] == "COG = COG_ctrl")
f.go(("follow", None)); app.processEvents()
proxy.cmds.radioButton("q7_follow_Mode2", edit=True, select=True)
check("Follow: the curve choice (radio buttons) read by the tool",
      proxy.cmds.radioButton("q7_follow_Mode2", query=True, select=True) is True and
      proxy.cmds.radioButton("q7_follow_Mode1", query=True, select=True) is False)
ui.status("Behaviour: 3 control(s) limited.", "ok")
check("the status line shows the tools' messages", "3 control(s) limited" in f.status.text())

# --- 4. the next step (it only suggests)
check("next step: a chain of joints -> Make (an FK chain)", nextstep.suggest(["joint"] * 3, ("behaviour", None))[3]
      == ("controls_tab", 1))
check("...a mesh and joints -> Skin > Bind", nextstep.suggest(["mesh", "joint", "joint"], ("controls_tab", 1))[3]
      == ("skin", None))
check("...controls, then a mesh -> Edit shape (On the body)",
      nextstep.suggest(["control", "control", "mesh"], ("controls_tab", 1))[3] == ("controls_tab", 2))
check("...an edge loop -> Shape from edges", nextstep.suggest([], ("controls_tab", 1), edges=12)[3] ==
      ("controls_tab", 2))
check("...nothing selected: no suggestion", nextstep.suggest([], ("controls_tab", 1)) is None)
jn = [cmds.ls(createNode("joint", name=n), long=True)[0] for n in ("L_arm_jnt", "L_elbow_jnt")]
cmds.select(jn)
f.go(("behaviour", None)); f.on_selection(); app.processEvents()
a = f.areas["controls"]
check("in the window: 2 joints selected - the lamp suggests Make, the Selected box shows them",
      a.next.isVisibleTo(a) and "FK chain" in a.next.text.text() and a._target == ("controls_tab", 1))
a._go_next(); app.processEvents()
check("...its button takes you there (nothing is made)", a.current == ("controls_tab", 1) and not made[1:])

# --- 5. pin a card; search; the old window; the other areas
f.go(("behaviour", None)); app.processEvents()
card = f.areas["controls"].pages["behaviour"].cards[1]
f.areas["controls"].toggle_pin(card, "behaviour")
f.go(("attrs", None)); app.processEvents()
check("pin 'In front of the mesh': it stays on top of the other Controls pages (Attributes)",
      card.isVisibleTo(f.areas["controls"].scroll.widget()) and card.property("pinned") == "true" and
      window._state()["pinned"]["controls"] == ["behaviour", "In front of the mesh"])
f.areas["controls"].toggle_pin(card, "behaviour")
check("...unpinned: back in its page", card.property("pinned") == "false" and "controls" not in
      window._state()["pinned"])
f._search_go("Edit shape  —  Controls"); app.processEvents()
check("search 'Edit shape': the Controls area on Edit shape", f.area == "controls" and
      f.areas["controls"].current == ("controls_tab", 2))
f._search_go("ribbon"); app.processEvents()
check("search 'ribbon': the Build area on Ribbon (today's page inside the new window until Build is redone)",
      f.area == "build" and f.areas["build"].current == ("ribbon", None) and
      isinstance(f.areas["build"].widgets[("ribbon", None)], window.OldPage))
f.go(("controls", None)); app.processEvents()
check("an area opens on the sub-page you used last", f.areas["controls"].current == ("controls_tab", 2))
import gus_rigtool.main as gr
from gus_rigtool.core import utils
check("the new window is the default", gr.new_window())
with mock.patch.object(ui, "open_panel", lambda k: None):
    gr.use_window("old")
check("Toolbox > Settings > Window > the old window: gr.show() opens the old one from now on", not gr.new_window())
utils.save_setting(gr.WINDOW_KEY, "new")
st = open(os.path.join(ROOT, "tools", "settings_tab.py")).read()
check("...the switch is on Settings (both windows show it)", '"Use the old window (5.6)"' in st and
      '"Use the new window"' in st)
check("old keys (the Shapes / Make controls shelf buttons) open the right page",
      window.area_of("shapes") == ("controls", "controls_tab", 2) and
      window.area_of("makectrl") == ("controls", "controls_tab", 1))

# --- 6. Maya 2025+ (PySide6) and 2024 (PySide2); the window in Maya
qt = open(os.path.join(ROOT, "newui", "qt.py")).read()
check("Qt: PySide6 (Maya 2025+) or PySide2 (Maya 2024)", "from PySide6 import" in qt and "from PySide2 import" in qt)
w = open(os.path.join(ROOT, "newui", "window.py")).read()
check("the window is rebuilt when Maya reopens it at start-up, with this version's title",
      'uiScript="import gus_rigtool.newui.window as _w; _w.restore()"' in w and
      'label="Gus_Rigtool %s" % gus_rigtool.__version__' in w)
print("%d/%d passed" % (sum(ok), len(ok)))
