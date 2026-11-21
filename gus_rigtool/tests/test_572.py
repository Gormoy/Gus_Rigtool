# 5.7.2: Settings its own button; the Skin area in the new look (7 sub-pages, nothing lost, nothing cut off);
# favourites profiles (All tools, one per area, your own) with editing on the row and the bar
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
from gus_rigtool.newui import window as W, favourites as FV, record, render, theme
from gus_rigtool.core import ui, utils
from gus_rigtool import registry

# --- 1. Settings: its own button at the bottom of the sidebar, in one place only
f = W.Frame(); f.resize(720, 900); f.show(); app.processEvents()
names = list(f.nav)
check("the sidebar ends with Settings (its own button, under the rest)", names[-1] == "settings" and
      f.nav["settings"].text() == "Settings")
f.go(("settings", None)); app.processEvents()
check("Settings: today's Settings page, in its own place", f.area == "settings" and
      f.areas["settings"].current == ("settings", None))
f.go(("toolbox", None)); app.processEvents()
check("...and no longer in the Toolbox (one place only)", "settings" not in [s[0] for s in f.areas["toolbox"].subs])
f._search_go("Settings  —  Settings"); app.processEvents()
check("search 'Settings' goes there", f.area == "settings")

# --- 2. Skin in the new look: 7 sub-pages, every control, every card on one sub-page
f.go(("skin", None)); app.processEvents()
a = f.areas["skin"]
check("Skin's sub-pages: Bind, Copy & mirror, Save / load, Clean, Weights, Cloth & jiggle, Fixes",
      [s[2] for s in a.subs] == ["Bind", "Copy & mirror", "Save / load", "Clean", "Weights", "Cloth & jiggle",
                                 "Fixes"])
def old_page(key):
    UI.clear(); _cur[0] = None
    cmds.columnLayout("root_" + key)
    ui._build_tool(key, "t_%s_" % key)
    kinds = ("button", "checkBox", "frameLayout", "optionMenu", "radioButtonGrp", "floatField", "intField",
             "textField", "textScrollList", "iconTextButton", "text", "radioButton")
    return [n.replace("t_%s_" % key, "") for n, v in UI.items() if v.get("kind") in kinds and not
            n.startswith(("text", "button", "frameLayout", "checkBox", "optionMenu", "iconTextButton", "floatField",
                          "radioButtonGrp", "textField", "intField"))]
lost, total, twice, not_drawn = [], 0, [], []
for key in ("skin", "fixes"):
    rec = record.record(registry.module(key).build, "zz_%s_" % key)
    pg = render.Page(key, rec, theme.colour("skin")); pg.build()
    got = [n.replace("zz_%s_" % key, "") for _k, n, _l, _h in pg.inventory]
    total += len(pg.inventory)
    not_drawn += [i for i in pg.inventory if i[3].startswith("not drawn")]
    twice += [n for n in set(got) if got.count(n) > 1]
    lost += ["%s: %s" % (key, n) for n in old_page(key) if n not in got]
check("nothing lost: every named control of today's Skin and Fixes pages is there (%d controls)" % total,
      not lost and total > 90)
check("nothing twice, nothing left undrawn", not twice and not not_drawn)
f.go(("skin", "Bind")); app.processEvents()
pg = a.pages["skin"]
seen = {}
for label, _titles in W.SPLITS["skin"]:
    f.go(("skin", label)); app.processEvents()
    seen[label] = [c.title for c in pg.cards if c.isVisibleTo(a.scroll.widget())]
every = [t for v in seen.values() for t in v]
check("every Skin card is on exactly one sub-page (13 cards: Bind, Save / load and Clean are split)",
      sorted(every) == sorted(c.title for c in pg.cards) and len(every) == 13)
check("Copy & mirror: Copy skin and Mirror weights, numbered 1 and 2 on their sub-page",
      seen["Copy & mirror"] == ["Copy skin", "Mirror weights"] and
      [c.num.text() for c in pg.cards if c.title in seen["Copy & mirror"]] == ["1", "2"])
f.go(("fixes", None)); app.processEvents()
check("Fixes: the Fixes page, as a Skin sub-page", a.current == ("fixes", None) and
      [c.title for c in a.pages["fixes"].cards] == ["Sculpt a fix", "Fixes on the mesh"])
crops = {}
for width in (300, 420, 700):
    f.resize(width, 900)
    for s in a.subs:
        f.go(s[:2])
        for _ in range(3):
            app.processEvents()
        got = W.cut_off(a)
        if got:
            crops["%s@%d" % (s[2], width)] = got[:3]
check("nothing cut off: every Skin sub-page at 300, 420 and 700 px (button text too)", not crops)
if crops:
    print("  ", list(crops.items())[:4])
from gus_rigtool.core import skin_tools
f.resize(720, 900); f.go(("skin", "Bind")); app.processEvents()
pg.fields["q7_skin_MaxInf"].widget.setCurrentIndex(pg.fields["q7_skin_MaxInf"].widget.findText("8")) \
    if hasattr(pg.fields["q7_skin_MaxInf"].widget, "findText") else \
    pg.fields["q7_skin_MaxInf"].widget.set_index(pg.fields["q7_skin_MaxInf"].query("itemListShort").index("8"))
got = []
with mock.patch.object(skin_tools, "bind", lambda **k: got.append(k) or []):
    [b for b in pg.cards[0].findChildren(QtWidgets.QPushButton) if b.text() == "Bind skin"][0].click()
check("Skin > Bind in the new window: 8 influences reaches the tool's own Bind (the same code as before)",
      got and got[0]["max_influences"] == 8)
f.go(("skin", None)); app.processEvents()
check("Skin opens on the sub-page you used last", a.current == ("skin", "Bind"))
pop = None
with mock.patch.object(W, "show_pop", lambda tool, page=None: W.PopFrame(tool, page)):
    f.go(("skin", "Weights")); app.processEvents()
    pop = f.pop_out()
check("Pop out Skin > Weights: its own panel, on Weights, with Skin's sub-pages", pop is not None and
      pop.body.current == ("skin", "Weights") and len(pop.tabs.findChildren(QtWidgets.QPushButton)) == 6)

# --- 3. favourites profiles
utils.save_setting("myTools", ["select", "groups", "controls_tab"])
utils.save_setting(FV.PROFILES_KEY, None)
b, mine = FV.profiles()
check("profiles: My tools (your list), All tools, and one per area", mine == ["My tools"] and b[0] == "All tools"
      and b[1:] == ["Build", "Skin", "Controls", "Connect", "Check & publish", "Toolbox", "Settings"])
check("My tools is your old list (the old window's My tools)", FV.current() == "My tools" and
      FV.keys() == ["select", "groups", "controls_tab"])
FV.set_current("Skin")
check("pick 'Skin': the row shows Skin and Fixes", FV.keys() == ["skin", "fixes"] and not FV.editable())
f3 = W.Frame(); f3.resize(720, 900); f3.show(); app.processEvents()
row = [x.property("fav") for x in f3.favs.findChildren(QtWidgets.QToolButton) if x.property("fav")]
check("...the window's row follows the profile", row == ["skin", "fixes"])
FV.toggle("ribbon")
check("☆ on a built-in profile: the tool goes to My tools (built-in ones can't change)",
      FV.current() == "My tools" and FV.keys()[-1] == "ribbon")
FV.new_profile("Face")
FV.set_keys(["face", "controls_tab", "follow", "stick"])
check("New profile 'Face' (a copy), then its own tools - My tools unchanged",
      FV.keys() == ["face", "controls_tab", "follow", "stick"] and FV.keys_of("My tools")[-1] == "ribbon" and
      utils.load_setting("myTools", None)[-1] == "ribbon")
f3.favs.set_editing(True); app.processEvents()
xs = [x for x in f3.favs.findChildren(QtWidgets.QToolButton) if x.property("remove")]
check("✎ Edit: an × on each favourite, + Add and Done", [x.property("remove") for x in xs] ==
      ["face", "controls_tab", "follow", "stick"] and
      [x.text() for x in f3.favs.findChildren(QtWidgets.QToolButton)
       if x.text() in ("+ Add", "Done")] == ["+ Add", "Done"])
[x for x in xs if x.property("remove") == "follow"][0].click(); app.processEvents()
check("...× takes Follow off", FV.keys() == ["face", "controls_tab", "stick"])
f3.favs.drop("stick", "face")
check("...drag Stick onto Face: Stick takes its place", FV.keys() == ["stick", "face", "controls_tab"])
d = FV.choose()
heads = [w.text() for w in d.findChildren(QtWidgets.QLabel) if w.text().isupper()]
check("+ Add: the tools grouped by area, in the sidebar's order", heads[:3] == ["BUILD", "SKIN", "CONTROLS"])
FV.rename_profile("Face", "Face rig")
check("Rename the profile", FV.current() == "Face rig" and "Face rig" in FV.profiles()[1])
bar = FV.FavBar(); bar.show(); app.processEvents()
check("the floating bar shows the same profile", list(bar.buttons) == FV.keys() and
      bar.profile.text().startswith("Face rig"))
bar.flip(); app.processEvents()
FV.set_current("My tools"); app.processEvents()
check("each profile keeps its own bar shape (Face rig: a column; My tools: a row)", not bar.vertical)
FV.set_current("Face rig"); app.processEvents()
check("...back to Face rig: a column again", bar.vertical)
bar.set_editing(True); app.processEvents()
check("the bar's Edit: an × on each square", len([x for x in bar.findChildren(QtWidgets.QToolButton)
                                                  if x.property("remove")]) == 3)
FV.close_bar()
FV.delete_profile("Face rig")
check("Delete a profile: back to My tools", FV.current() == "My tools" and "Face rig" not in FV.profiles()[1])
try:
    FV.delete_profile("My tools"); msg = ""
except RuntimeError as e:
    msg = str(e)
check("My tools can't be deleted (the old window uses it)", "can't be deleted" in msg)
print("%d/%d passed" % (sum(ok), len(ok)))
