# 5.7.5: the Connect area in the new look - Constraints, Connections, Nodes (3 pages), Driven keys: nothing lost,
# nothing twice, nothing cut off; two rows of tabs with plain names; the Connections tab opens Connections (its key
# is the area's); Driven keys' Copy section only in Copy mode; lists as tall as their rows; the buttons reach the
# tools' own code with the page's values
exec(open("test_570.py").read().split("# --- 1.")[0])
from unittest import mock
from gus_rigtool.newui import window as W, widgets
TOOLS = ["constrain", "connect", "nodes", "sdk"]

# --- 1. nothing lost, nothing twice
def old_page(key):
    UI.clear(); _cur[0] = None
    cmds.columnLayout("root_" + key)
    ui._build_tool(key, "t_%s_" % key)
    kinds = ("button", "checkBox", "frameLayout", "optionMenu", "radioButtonGrp", "floatField", "intField",
             "textField", "textScrollList", "iconTextButton", "text", "radioButton", "floatFieldGrp", "intFieldGrp",
             "textFieldGrp", "floatSliderGrp", "intSliderGrp", "checkBoxGrp", "colorSliderGrp")
    return [n.replace("t_%s_" % key, "") for n, v in UI.items() if v.get("kind") in kinds and "__" not in n
            and not n.startswith(tuple(kinds))]
lost, twice, not_drawn, total = [], [], [], 0
for key in TOOLS:
    rec = record.record(registry.module(key).build, "q5_%s_" % key)
    page = render.Page(key, rec, theme.colour("connect"))
    keep = page.build()
    names = [n.replace("q5_%s_" % key, "") for _k, n, _l, how in page.inventory]
    total += len(page.inventory)
    not_drawn += ["%s: %s %s" % (key, k, n) for k, n, _l, how in page.inventory if how.startswith("not drawn")]
    twice += ["%s: %s" % (key, n) for n in set(names) if names.count(n) > 1]
    have = names + [x.replace("q5_%s_" % key, "") for x in page.fields]
    lost += ["%s: %s" % (key, n) for n in old_page(key) if n not in have]
check("nothing lost: every named control of today's Constraints, Connect, Nodes and SDK is on the new pages (%s)" %
      ("over 170 controls" if total > 170 else "%d controls" % total), not lost and total > 170)
if lost:
    print("   lost:", lost[:10])
check("nothing twice, every kind of control drawn", not twice and not not_drawn)

# --- 2. two rows of tabs, plain names; the Connections tab opens Connections
f = W.Frame(); f.resize(700, 1100); f.show()
f.go(("nodes", "Make a driver")); app.processEvents()
row1 = [b.text() for b in f.tabs.findChildren(QtWidgets.QPushButton)]
row2 = [b.text() for b in f.tabs2.findChildren(QtWidgets.QPushButton)]
check("Connect: Constraints, Connections, Nodes, Driven keys on top; Nodes' pages under them",
      row1 == ["Constraints", "Connections", "Nodes", "Driven keys"] and
      row2 == ["See && trace", "Make a driver", "Find && clean"])
a = f.areas["connect"]
np_ = a.pages["nodes"]
check("Nodes > Make a driver: Make a driver, Setups library", [c.title for c in np_.cards if c.isVisibleTo(a)] ==
      ["Make a driver", "Setups library"])
[b for b in f.tabs.findChildren(QtWidgets.QPushButton) if b.text() == "Connections"][0].click(); app.processEvents()
check("click Connections: the Connections page (5.7.4 went to the Connect area's last page - its name is the "
      "area's)", a.current == ("connect", None) and f.area == "connect")
f.go_key("connect"); app.processEvents()
check("...a favourite / search for Connect: Connections too", a.current == ("connect", None))
f.go(("connect", None)); app.processEvents()
check("...the sidebar's Connect button: the area (its last page)", f.area == "connect")

# --- 3. nothing cut off
crops = {}
subs = [tuple(x[:2]) for x in a.subs]
for font in ("13px", "15px"):
    with mock.patch.object(theme, "stylesheet", (lambda real: lambda c: real(c).replace("font-size: 13px",
                                                                                         "font-size: " + font))(
            theme.stylesheet)):
        for width in (300, 420, 700):
            f.resize(width, 1100)
            for sub in subs:
                f.go(sub, as_tool=True)
                for _ in range(3):
                    app.processEvents()
                got = W.cut_off(a)
                if got:
                    crops["%s %s@%d" % (font, sub, width)] = got[:3]
check("nothing cut off: every Connect page (%d), 300 / 420 / 700 px, normal and wider font" % len(subs), not crops)
if crops:
    print("  ", list(crops.items())[:4])
f.resize(700, 1100)
widest = []
for sub in subs:
    f.go(sub, as_tool=True); app.processEvents()
    key = tuple(a.current) if tuple(a.current) in a.widgets else (a.current[0], None)
    widest.append((a.widgets[key].minimumSizeHint().width(), sub))
check("every Connect page fits a narrow window (no more room than Controls > Behaviour)", max(widest)[0] <= 230)

# --- 4. Driven keys: Copy only in Copy mode; the list as tall as its rows
from gus_rigtool.tools import sdk_tool as SK
f.go(("sdk", None), as_tool=True); app.processEvents()
sp = a.pages["sdk"]
copy = [c for c in sp.cards if c.title.startswith("Copy")][0]
mode = sp.fields[SK.N("Mode")]
SK.preview(); app.processEvents()
nums = lambda: [(c.title.split(" ")[0], c.num.text()) for c in sp.cards if not c.isHidden()]
check("Driven keys in Mirror mode: the Copy section hidden, the others numbered 1 2 3 4 (no gap)",
      not copy.isVisibleTo(a) and SK._ui()["mode"] == 1 and [n for _t, n in nums()] == ["1", "2", "3", "4"])
mode.widget.findChildren(QtWidgets.QPushButton)[1].click(); app.processEvents()
SK.preview(); app.processEvents()
check("...Copy mode: the Copy section shows (numbered 2, as before)", copy.isVisibleTo(a) and SK._ui()["mode"] == 2
      and copy.num.text() == "2" and [n for _t, n in nums()] == ["1", "2", "3", "4", "5"])
rows = sp.fields[SK.N("Rows")].widget
short = rows.height()
SK.cmds.textScrollList(SK.N("Rows"), edit=True, append=["row %d" % i for i in range(12)]); app.processEvents()
check("the driven keys list: short with one line, taller with more (up to its old height)",
      short < 90 and rows.minimumHeight() > short and rows.minimumHeight() <= 150)

# --- 5. the buttons reach the tools' own code, with the page's values
from gus_rigtool.core import constraints, connector
from gus_rigtool.tools import constraint_tool as CN, connect_tool as CC
f.go(("constrain", None), as_tool=True); app.processEvents()
s1 = cmds.createNode("transform", name="tgt"); s2 = cmds.createNode("transform", name="drv")
cmds.select(s1, s2)
got = []
with mock.patch.object(constraints, "plan", lambda sel, order: got.append(("plan", order)) or []):
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Constrain" and b.isVisibleTo(a)][0].click()
check("Constraints > Constrain: the tool's own Constrain (with the Order on the page)", got and got[0][0] == "plan")
f.go(("connect", None), as_tool=True); app.processEvents()
with mock.patch.object(connector, "pairs", lambda s, d: got.append(("pairs", s, d)) or []), \
        mock.patch.object(connector, "connect", lambda *x: got.append(("connect",)) or (0, [])):
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Connect" and b.isVisibleTo(a)][0].click()
check("Connections > Connect: the tool's own Connect", any(g[0] == "pairs" for g in got))
from gus_rigtool.core import drivers
from gus_rigtool.tools import nodes_tool as NT
f.go(("nodes", "Make a driver")); app.processEvents()
npg = a.pages["nodes"]
npg.fields[NT.N("DrvAttr")].widget.setText("translateY")
npg.fields[NT.N("TgtAttr")].widget.setText("rotateX")
npg.fields[NT.N("Amount")].widget.setText("-4")
cmds.select(s1, s2)
with mock.patch.object(drivers, "preview", lambda *x: got.append(("preview",) + x) or "plan"), \
        mock.patch.object(cmds, "confirmDialog", lambda **k: "Cancel"):
    try:
        [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Make the driver" and b.isVisibleTo(a)][0].click()
    except Exception:
        pass
drv = [g for g in got if g[0] == "preview"]
check("Nodes > Make the driver: the tool's own, with the page's channels and amount (its plan shown first)",
      drv and drv[0][1].endswith("tgt.translateY") and drv[0][2][0][1:] == ("rotateX", -4.0))
print("%d/%d passed" % (sum(ok), len(ok)))
