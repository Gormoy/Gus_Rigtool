# 5.7.3: the Build area in the new look - Build, Face, Ribbon, Joints as they are today (nothing lost, nothing twice,
# nothing cut off - drop-downs too), two rows of tabs (Build and Skin), colour pickers, sections inside a card as
# lighter panels, number fields that read what you typed, Build's "Settings of the picked module" refilled when you
# pick a module, and the big buttons reaching the tools' own code
exec(open("test_570.py").read().split("# --- 1.")[0])
from gus_rigtool.newui import window as W, widgets
from gus_rigtool.core import utils
BUILD = ["build", "face", "ribbon", "joints"]

# --- 1. nothing lost, nothing twice: every named control of today's 4 Build pages is on the new ones, once
def old_page(key):
    UI.clear(); _cur[0] = None
    cmds.columnLayout("root_" + key)
    ui._build_tool(key, "t_%s_" % key)
    kinds = ("button", "checkBox", "frameLayout", "optionMenu", "radioButtonGrp", "floatField", "intField",
             "textField", "textScrollList", "iconTextButton", "text", "radioButton", "colorSliderGrp",
             "floatFieldGrp", "intFieldGrp", "textFieldGrp", "floatSliderGrp", "intSliderGrp", "checkBoxGrp")
    return [n.replace("t_%s_" % key, "") for n, v in UI.items() if v.get("kind") in kinds and "__" not in n
            and not n.startswith(tuple(kinds))]
lost, twice, not_drawn, total = [], [], [], 0
for key in BUILD:
    rec = record.record(registry.module(key).build, "q3_%s_" % key)
    page = render.Page(key, rec, theme.colour("build"))
    page.build()
    names = [n.replace("q3_%s_" % key, "") for _k, n, _l, how in page.inventory]
    total += len(page.inventory)
    not_drawn += ["%s: %s %s" % (key, k, n) for k, n, _l, how in page.inventory if how.startswith("not drawn")]
    twice += ["%s: %s" % (key, n) for n in set(names) if names.count(n) > 1]
    have = names + [x.replace("q3_%s_" % key, "") for x in page.fields]
    lost += ["%s: %s" % (key, n) for n in old_page(key) if n not in have]
check("nothing lost: every named control of today's Build, Face, Ribbon and Joints is on the new pages (%s)" %
      ("over 500 controls" if total > 500 else "%d controls" % total), not lost and total > 500)
if lost:
    print("   lost:", lost[:10])
check("nothing twice", not twice)
check("every kind of control is drawn - the colour pickers too (Ribbon's control and mirror colours)", not not_drawn)
if not_drawn:
    print("  ", not_drawn[:10])

# --- 2. two rows of tabs
f = W.Frame(); f.resize(700, 1100); f.show()
f.go(("build", None)); app.processEvents()
row1 = [b.text() for b in f.tabs.findChildren(QtWidgets.QPushButton)]
row2 = [b.text() for b in f.tabs2.findChildren(QtWidgets.QPushButton)]
check("Build: the tools on top (Build, Face, Ribbon, Joints), Build's own pages under them",
      row1 == ["Build", "Face", "Ribbon", "Joints"] and row2 == ["Rig builder", "Animation", "Existing rig", "Advanced"])
bp = f.areas["build"].pages["build"]
recorded = [l.split(" ", 1)[1] for l, _w in bp.tabs[bp.key and "q7_build_Tabs"]]
check("...the same pages as the old window's tabs (1 Rig builder ... 4 Advanced)", recorded == row2)
f.go(("build", 2)); app.processEvents()
from gus_rigtool.tools import build_tab as B
check("...click Animation: its page, the choice remembered as in the old window",
      f.areas["build"].current == ("build", 2) and utils.load_setting(B.SETTINGS_KEY, {}).get("sub_page2") == 2)
f.go(("joints", None)); app.processEvents()
check("...Joints on the top row: no second row (it has one page)", not f.tabs2.isVisibleTo(f))
f.go(("skin", "Bind")); app.processEvents()
check("Skin: Skin and Fixes on top, Skin's 6 pages under them",
      [b.text() for b in f.tabs.findChildren(QtWidgets.QPushButton)] == ["Skin", "Fixes"] and
      len(f.tabs2.findChildren(QtWidgets.QPushButton)) == 6)
f.go(("fixes", None)); app.processEvents()
[b for b in f.tabs.findChildren(QtWidgets.QPushButton) if b.text() == "Skin"][0].click(); app.processEvents()
check("...Fixes, then Skin on the top row: back on the Skin page you were on", f.areas["skin"].current == ("skin", "Bind"))

# --- 3. nothing cut off - drop-downs too - at 300 / 420 / 700 px, normal and wider font
crops = {}
subs = [tuple(x[:2]) for x in f.areas["build"].subs]           # 5.7.4: Face and Ribbon have their own pages
for font in ("13px", "15px"):
    with mock.patch.object(theme, "stylesheet", (lambda real: lambda a: real(a).replace("font-size: 13px",
                                                                                         "font-size: " + font))(
            theme.stylesheet)):
        for width in (300, 420, 700):
            f.resize(width, 1100)
            for sub in subs:
                f.go(sub)
                for _ in range(3):
                    app.processEvents()
                got = W.cut_off(f.areas["build"])
                if got:
                    crops["%s %s@%d" % (font, sub, width)] = got[:3]
check("nothing cut off: every Build page, 300 / 420 / 700 px, normal and wider font (buttons, boxes, drop-downs)",
      not crops)
if crops:
    print("  ", list(crops.items())[:4])
f.resize(700, 1100)
widest = []
for sub in subs:
    f.go(sub); app.processEvents()
    bd = f.areas["build"]
    key = tuple(bd.current) if tuple(bd.current) in bd.widgets else (bd.current[0], None)
    widest.append((bd.widgets[key].minimumSizeHint().width(), sub))
check("every Build page fits a narrow window (Gus's Maya at 326 px cut Rig builder and Ribbon: a closed card's "
      "hint never gave way) - no page needs more room than Controls > Behaviour, which fits", max(widest)[0] <= 230)
if max(widest)[0] > 230:
    print("  ", sorted(widest, reverse=True)[:3])
c = QtWidgets.QComboBox(); c.addItems(["One per span, both directions"]); c.setFixedWidth(60)
c.show(); app.processEvents()
check("...the check sees a drop-down that cuts its text", not W._combo_fits(c))
c.hide()

# --- 4. colour pickers, inner sections, number fields
from gus_rigtool.tools import ribbon_tool as RT
f.go(("ribbon", None)); app.processEvents()
rp = f.areas["build"].pages["ribbon"]
col = rp.fields[RT.N("Color")]
check("Ribbon: the control colour is a colour square (click it to choose)", isinstance(
    getattr(col.widget, "swatch", None), QtWidgets.QPushButton) and len(RT._q("colorSliderGrp", "Color", rgbValue=True)) == 3)
col.edit("rgbValue", [0.1, 0.2, 0.9])
check("...the colour you choose is the one Ribbon builds with", RT._ui()["color"][:3] == [0.1, 0.2, 0.9])
rp.fields[RT.N("PlLen")].widget.boxes[0].setText("33")
check("a number you type (Make a plane > Length) is the one the tool reads (was the starting value)",
      RT._q("floatFieldGrp", "PlLen", value1=True) == 33.0)
inner = [c for c in f.areas["build"].findChildren(widgets.Card) if c.property("inner") == "true"]
check("sections inside a card: lighter panels, no number, not pinnable (Ribbon > Surface > Make a plane)",
      inner and all(not c.num.text() and c.pin.isHidden() and c not in rp.cards for c in inner) and
      "Make a plane" in [c.title for c in inner])

# --- 5. Build's "Settings of the picked module": refilled when you pick a module
from gus_rigtool.tools import build_tab as B, build_form
from gus_rigtool.builder import guides
f.go(("build", 1)); app.processEvents()
a = f.areas["build"]
[b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Add" and b.isVisibleTo(a)][0].click()
app.processEvents()
lw = [w for w in a.findChildren(QtWidgets.QListWidget) if w.isVisibleTo(a)][0]
lw.item(0).setSelected(True); app.processEvents()
form = bp.fields[B.N("Form")]
shown = lambda: [w.text() for w in form.widget.findChildren(QtWidgets.QLabel) if w.isVisibleTo(form.widget)]
check("pick a module (Root): its settings appear in the card, in the new look", any(
    t.startswith("Root  -  C root") for t in shown()))
cb = [w for w in form.widget.findChildren(QtWidgets.QCheckBox) if "Root bind joint" in w.text() and
      w.isVisibleTo(form.widget)][0]
cb.click(); app.processEvents()
check("...change one: the tool sees it isn't applied yet", build_form.pending())
with mock.patch.object(build_form.guides, "save_settings", wraps=build_form.guides.save_settings) as ap:
    [b for b in form.widget.findChildren(QtWidgets.QPushButton) if b.text().startswith("Apply") and
     b.isVisibleTo(form.widget)][0].click()
check("...Apply: the tool's own Apply, and nothing left to apply", ap.called and not build_form.pending())
first = set(proxy.REGISTRY)
cmds.select(clear=True)
lw.clearSelection(); app.processEvents()
check("...pick nothing: the card says to pick a module, the old fields gone (not left behind)",
      any("Pick a module" in t for t in shown()) and cb.objectName() not in proxy.REGISTRY and
      len(set(proxy.REGISTRY) - first) <= 2)

# --- 6. the big buttons reach the tools' own code
from gus_rigtool.tools import joint_chain as JC
with mock.patch.object(B.bld, "build_all") as br:
    f.go(("build", 1)); app.processEvents()
    big = [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Build" and b.isVisibleTo(a)]
    big and big[0].click()
check("Build > Rig builder > Build: the builder's Build", br.called if big else False)
with mock.patch.object(RT.ribbon, "build_rig") as rb:
    f.go(("ribbon", None)); app.processEvents()
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Create" and b.isVisibleTo(a)][0].click()
check("Ribbon > Create: builds the ribbon with the page's settings (the colour you chose)",
      rb.called and list(rb.call_args[0][0].get("color", [])[:3]) == [0.1, 0.2, 0.9])
with mock.patch.object(JC, "create", return_value=[]) as jc:
    f.go(("joints", None)); app.processEvents()
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Create joints" and b.isVisibleTo(a)][0].click()
check("Joints > Create joints: makes the joints with the page's settings", jc.called)
print("%d/%d passed" % (sum(ok), len(ok)))
