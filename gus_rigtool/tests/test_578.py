# 5.7.8: text never cut (choice buttons sized for bold, '&' shown, names above when narrow, tick boxes plain
# text), Arrange on every page (Up / Down / To top, Reset order, Done), your order on every tab (Build's pages,
# Edit shape's swap keeps its items), one-section pages split, Settings in the new look, the sidebar hides to a
# strip, a gap in the area titles
exec(open("test_570.py").read().split("# --- 1.")[0])
from unittest import mock
from gus_rigtool.newui import window as W, widgets
from gus_rigtool.core import utils
from gus_rigtool.newui.qt import QtCore, QtGui
Qt = QtCore.Qt

def set_look(name):
    utils.save_setting(theme.LOOK_KEY, name)
    theme.load_look()

def settle():
    for _ in range(3):
        app.processEvents()

set_look("today")
utils.save_setting(W.STATE_KEY, {})

# --- 1. text never cut
seg = widgets.Segmented(["Match & zero", "Keep values", "Above the object"], 0)
seg.show(); settle()
check("'&' shows as '&' ('Match & zero', not 'Match _zero')", seg.labels()[0] == "Match & zero" and
      seg.buttons[0].text() == "Match && zero")
f = QtGui.QFont(seg.buttons[2].font()); f.setBold(True)
need = QtGui.QFontMetrics(f).horizontalAdvance("Above the object")
seg.buttons[2].setChecked(True); settle()
check("a picked choice (bold) is as wide as its words ('Above the objec' was cut)",
      seg.buttons[2].sizeHint().width() >= need + 20 and seg.buttons[2].minimumSizeHint().width() >= need + 20)
cb = widgets.WrapCheckBox("Shapes follow (<name>Shape)")
check("a tick box's words are plain text ('<name>' is not read as a tag)", cb._lb.textFormat() == Qt.PlainText)
fm = cb._lb.fontMetrics()
check("...never narrower than its longest word", cb.minimumSizeHint().width() >= fm.horizontalAdvance(
    "(<name>Shape)") + 30)
box = QtWidgets.QWidget()
form = widgets.FormLayout(box)
lab, combo = QtWidgets.QLabel("Starts in"), render._Combo()
combo.addItems(["parent (move + turn)"])
form.addRow(lab, combo)
box.resize(600, 40); box.show(); settle()
side = lab.geometry().top() == combo.geometry().top() or abs(lab.geometry().center().y() -
                                                             combo.geometry().center().y()) < 6
box.resize(combo.minimumSizeHint().width() + 20, 80); settle()
check("a name beside its control when there's room, above it when narrow (the control keeps its width)",
      side and lab.geometry().bottom() <= combo.geometry().top() and
      combo.width() >= combo.minimumSizeHint().width())

crops = {}
for look in ("today", "new"):
    set_look(look)
    for font in ("13px", "15px"):
        with mock.patch.object(theme, "stylesheet", (lambda real: lambda c: real(c).replace(
                "font-size: 13px", "font-size: " + font))(theme.stylesheet)):
            fr = W.Frame(); fr.show()
            for key in W.NEW_LOOK:
                a = fr._area(key)
                for x in a.subs:
                    for width in (300, 326, 700):
                        fr.resize(width, 1100)
                        fr.go(tuple(x[:2]), as_tool=True)
                        settle()
                        got = W.cut_off(a)
                        if got:
                            crops["%s %s %s > %s @%d" % (look, font, key, x[2], width)] = got[:2]
            fr.close()
check("nothing cut off on any page: both looks, 300 / 326 / 700 px, normal and wider font (your Mac's)",
      not crops)
if crops:
    print("  ", list(crops.items())[:4])
set_look("today")

# --- 2. Arrange (Edit shape, your example)
utils.save_setting(W.STATE_KEY, {})
fr = W.Frame(); fr.resize(560, 1300); fr.show()
sub = ("controls_tab", 2)
fr.go(sub, as_tool=True); settle()
a = fr.areas["controls"]
btn = [b for b in fr.head_buttons.findChildren(QtWidgets.QPushButton) if b.text() == "Arrange"]
check("an Arrange button in every page's header", len(btn) == 1)
was = dict((c.title, c.closed) for c in a._cards_of(sub))
btn[0].click(); settle()
cards = a._cards_of(sub)
check("Arrange: every section closed to its title, with Up / Down / To top; the bar with Reset order and Done",
      a.arranging and all(c.closed and c.arr.isVisibleTo(fr) for c in cards) and a.arrange_bar.isVisibleTo(fr)
      and btn[0].text() == "Done arranging")
first = [c.title for c in a._visual(sub)]
mv = [c for c in cards if c.title.startswith("Move the shape")][0]
mv.arr_buttons[2].click(); settle()
now = [c.title for c in a._visual(sub)]
check("To top: 'Move the shape' above 'Swap the shape' (Gus's example)", now[0].startswith("Move the shape") and
      now[1] == first[0])
sz = [c for c in a._cards_of(sub) if c.title == "Size and turn"][0]
sz.arr_buttons[0].click(); settle()
check("Up: one place up", [c.title for c in a._visual(sub)].index("Size and turn") == now.index("Size and turn")
      - 1)
sz.arr_buttons[1].click(); settle()
check("Down: back", [c.title for c in a._visual(sub)] == now)
check("...clicking a title while arranging doesn't open it", (sz.head.mouseReleaseEvent(QtGui.QMouseEvent(
    QtCore.QEvent.MouseButtonRelease, QtCore.QPointF(5, 5), QtCore.QPointF(5, 5), Qt.LeftButton, Qt.LeftButton,
    Qt.NoModifier)) or True) and sz.closed)
btn[0].click(); settle()
check("Done: the sections open / closed as they were, the order kept", not a.arranging and
      all(c.closed == was.get(c.title, c.closed) for c in a._cards_of(sub)) and
      [c.title for c in a._visual(sub)] == now and not a.arrange_bar.isVisibleTo(fr))
fr2 = W.Frame(); fr2.resize(560, 1300); fr2.show(); fr2.go(sub, as_tool=True); settle()
check("remembered after a restart", [c.title for c in fr2.areas["controls"]._visual(sub)] == now)
fr2.areas["controls"].arrange(True)
fr2.areas["controls"].move_card(sub, "", "@Reset order"); settle()
a2 = fr2.areas["controls"]
check("Reset order (in Arrange): the tool's order, still arranging", [c.title for c in a2._visual(sub)] == first
      and a2.arranging and all(c.arr.isVisibleTo(fr2) for c in a2._cards_of(sub)))
a2.arrange(False)
check("Edit shape: 'Select the controls to change' and 'Keep their size and place' inside 'Swap the shape' (they "
      "move with it)", [c for c in a2._cards_of(sub) if c.title.startswith("Swap")][0].findChildren(
          widgets.WrapCheckBox)[0].text() == "Keep their size and place")
fr2.close()

# --- 3. your order on every page (both looks): To top works everywhere, Build's pages too
bad = []
for look in ("today", "new"):
    set_look(look)
    utils.save_setting(W.STATE_KEY, {})
    fr = W.Frame(); fr.resize(700, 1200); fr.show()
    for key in W.NEW_LOOK:
        a = fr._area(key)
        for x in a.subs:
            s = tuple(x[:2])
            fr.go(s, as_tool=True); settle()
            vis = a._visual(s)
            if len(vis) < 2:
                continue
            last = vis[-1]
            last.moved.emit(last.title, "@Move to top"); settle()
            if a._visual(s)[0] is not last:
                bad.append("%s %s" % (look, x[2]))
            last.moved.emit(last.title, "@Reset order"); settle()
    fr.close()
check("To top works on every page with two sections or more, both looks (5.7.7: not on Build > Animation, "
      "Existing rig, Advanced)", not bad)
if bad:
    print("  ", bad[:6])
set_look("today")

# --- 4. one-section pages split (Gus: "ok"), nothing lost
utils.save_setting(W.STATE_KEY, {})
fr = W.Frame(); fr.resize(600, 1200); fr.show()
want = {("skin", "Bind"): ["Bind", "Add joints"], ("skin", "Save / load"): ["Save weights", "Load weights"],
        ("skin", "Clean"): ["Prune", "Limit influences", "Remove unused joints"],
        ("check", "Publish"): ["Publish (clean rig for animators)", "Deliver to animators"],
        ("controls", "Stick to skin"): ["Stick", "Find what's stuck"]}
got = {}
for (area, label), titles in want.items():
    a = fr._area(area)
    x = [x for x in a.subs if x[2] == label][0]
    fr.go(tuple(x[:2]), as_tool=True); settle()
    got[label] = [c.title for c in a._visual(tuple(x[:2]))]
check("split into sections: Bind · Add joints / Save · Load weights / Prune · Limit · Remove unused / Publish · "
      "Deliver / Stick · Find what's stuck", all(got[l] == t for (_a, l), t in want.items()))
if [l for (_a, l), t in want.items() if got[l] != t]:
    print("  ", got)
a = fr._area("skin")
x = [x for x in a.subs if x[2] == "Clean"][0]
fr.go(tuple(x[:2]), as_tool=True); settle()
page = a.pages["skin"]
lim = [c for c in a._cards_of(tuple(x[:2])) if c.title == "Limit influences"][0]
names = [n for n, fl in page.fields.items() if "Influences" in n or "Inf" in n.split("_")[-1]]
check("...the moved controls are the tool's own (the tool reads and fills them as before)",
      any(fl.widget is not None and lim.isAncestorOf(fl.widget) for fl in page.fields.values()))
fr.close()

# --- 5. Settings in the new look (Gus: "yes"): its sections arrange, its options on show, its search works
set_look("new")
fr = W.Frame(); fr.resize(700, 1400); fr.show(); fr.go(("settings", None)); settle()
a = fr.areas["settings"]
cards = a._cards_of(("settings", None))
check("Settings drawn in the new look: its sections (%s) can be arranged" % ("over 20" if len(cards) > 20 else
                                                                            len(cards)),
      not isinstance(a.widgets.get(("settings", None)), W.OldPage) and len(cards) > 20)
check("...its options are on show (a page of options doesn't fold them)", not [fo for fo in
                                                                                 a.findChildren(widgets.Fold)
                                                                                 if fo.title == "Options"])
ed = [w for w in a.findChildren(QtWidgets.QLineEdit) if w.isVisibleTo(a)][0]
ed.setText("mirror")
for sig in ("textChanged", "editingFinished", "returnPressed"):
    try:
        getattr(ed, sig).emit(*(["mirror"] if sig == "textChanged" else []))
    except Exception:
        pass
settle()
shown = [w.text() for w in a.findChildren(QtWidgets.QCheckBox) if w.isVisibleTo(a)]
check("...Search options: 'mirror' shows only the options about mirroring", shown and
      all("mirror" in t.lower() for t in shown))
ed.setText("")
for sig in ("textChanged", "editingFinished", "returnPressed"):
    try:
        getattr(ed, sig).emit(*([""] if sig == "textChanged" else []))
    except Exception:
        pass
check("...the Look buttons are still on it (you can always go back)", [b for b in a.findChildren(
    QtWidgets.QAbstractButton) if "Today's look" in b.text()])
fr.close()
set_look("today")

# --- 6. the sidebar hides to a thin strip of icons, remembered; a gap in the titles
utils.save_setting(W.STATE_KEY, {})
fr = W.Frame(); fr.resize(800, 900); fr.show(); settle()
check("the sidebar: '‹' at its top", fr.side_toggle.text() == "‹" and fr.side.width() == 196)
fr.side_toggle.click(); settle()
check("...click: a thin strip of icons ('›' to open it)", fr.side.width() == 54 and fr.side_toggle.text() == "›"
      and fr.nav["build"].isVisible() and fr.nav["build"].text() == "")
fr3 = W.Frame(); fr3.resize(800, 900); fr3.show(); settle()
check("...remembered after a restart", fr3.side.width() == 54)
fr3.side_toggle.click(); settle()
check("...'›': back", fr3.side.width() == 196)
check("a gap between the area's icon and its name (the Toolbox title)", fr3.head_icon.parentWidget() is not None
      and fr3.head_title.geometry().left() - fr3.head_icon.geometry().right() >= 10)
print("%d/%d passed" % (sum(ok), len(ok)))
