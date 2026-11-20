# 5.7.6: Check & publish in the new look - Checker, Organize, and Publish moved there from Build (Gus: "move"):
# nothing lost (Publish's controls on its own page, no longer on Build's), nothing twice, nothing cut off; the rows the
# tools make while you work (the checks' results, the repairs, the Outliner plan) are drawn on the page; the buttons
# reach the tools' own code with the page's values
exec(open("test_570.py").read().split("# --- 1.")[0])
from unittest import mock
from gus_rigtool.newui import window as W, widgets
from gus_rigtool.tools import build_tab as B, checker as CK, organize_tool as OT

# --- 1. nothing lost: Checker and Organize as today; Publish's controls on its own page
def old_page(key):
    UI.clear(); _cur[0] = None
    cmds.columnLayout("root_" + key)
    ui._build_tool(key, "t_%s_" % key)
    kinds = ("button", "checkBox", "frameLayout", "optionMenu", "radioButtonGrp", "floatField", "intField",
             "textField", "textScrollList", "iconTextButton", "text", "radioButton", "floatFieldGrp", "intFieldGrp",
             "textFieldGrp", "floatSliderGrp", "intSliderGrp", "checkBoxGrp", "colorSliderGrp")
    return [n.replace("t_%s_" % key, "") for n, v in UI.items() if v.get("kind") in kinds and "__" not in n
            and not n.startswith(tuple(kinds))]
lost, twice, total = [], [], 0
for key in ("checker", "organize", "publish"):
    rec = record.record(registry.builder(key), "q6_%s_" % key)
    page = render.Page(key, rec, theme.colour("check"))
    keep = page.build()
    names = [n.replace("q6_%s_" % key, "") for _k, n, _l, how in page.inventory]
    total += len(page.inventory)
    twice += ["%s: %s" % (key, n) for n in set(names) if names.count(n) > 1]
    have = names + [x.replace("q6_%s_" % key, "") for x in page.fields]
    want = old_page(key) if key != "publish" else [n for n in old_page("build") if n.startswith("Pub_")]
    lost += ["%s: %s" % (key, n) for n in want if n not in have]
check("nothing lost: Checker, Organize, and Build's Publish options on the Publish page (%s)" %
      ("over 110 controls" if total > 110 else "%d controls" % total), not lost and total > 110)
if lost:
    print("   lost:", lost[:10])
check("nothing twice", not twice)

# --- 2. Publish moved: on Check & publish, not on Build any more (the old window keeps it on Build)
f = W.Frame(); f.resize(700, 1100); f.show()
f.go(("checker", None), as_tool=True); app.processEvents()
check("Check & publish: Checker · Organize · Publish", [b.text() for b in f.tabs.findChildren(QtWidgets.QPushButton)]
      == ["Checker", "Organize", "Publish"])
f.go(("build", 1)); app.processEvents()
bp = f.areas["build"].pages["build"]
check("Build > Rig builder: no Publish section (it's on Check & publish now)",
      not [c for c in bp.cards if c.title.startswith("Publish")] and not [n for n in bp.fields if "Pub_" in n])
UI.clear(); _cur[0] = None
cmds.columnLayout("root_old")
ui._build_tool("build", "t_old_")
check("...the old window's Build still has it, as before", any(n.startswith("t_old_Pub_") for n in UI))
f.go_key("publish"); app.processEvents()
check("a search / favourite for Publish: Check & publish > Publish", f.area == "check" and
      f.areas["check"].current == ("publish", None) and "Publish  —  Check & publish" in f.entries)

# --- 3. Publish reads its own page
a = f.areas["check"]
pp = a.pages["publish"]
pp.fields[B.NP("Pub_hide_joints")].widget.setChecked(False)
from gus_rigtool.builder import publish
with mock.patch.object(publish, "publish", lambda o: (got.append(o), [])[1]), \
        mock.patch.object(ui, "report_window", lambda *x, **k: None):
    got = []
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Publish" and b.isVisibleTo(a)][0].click()
check("Publish: the tool's own Publish, with this page's options (Hide the joints off)",
      got and got[0].get("hide_joints") is False)

# --- 4. the rows the tools make while you work: drawn on the page
f.go(("checker", None), as_tool=True); app.processEvents()
cp = a.pages["checker"]
results = {"ctrl_zero": ("WARN", ["|L_arm_ctrl", "|R_arm_ctrl"]), "ctrl_keys": ("PASS", [])}
with mock.patch.object(CK, "run_checks", lambda o, roots: results):
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Run checks" and b.isVisibleTo(a)][0].click()
app.processEvents()
res = cp.fields[CK.N("Results")].widget
shown = [w.text() for w in res.findChildren(QtWidgets.QLabel) if w.isVisibleTo(res)] + \
        [w.text() for w in res.findChildren(QtWidgets.QPushButton) if w.isVisibleTo(res)]
check("Run checks: each check's row on the page ('Controls not at zero' WARN 2)", any(
    "Controls not at zero" in t for t in shown) and any(t.strip() == "WARN" for t in shown))
if not any(t.strip() == "WARN" for t in shown):
    print("  ", shown[:10])
from gus_rigtool.core import repair
items = [repair.Item("ctrl_zero", "Controls not at zero", "2 controls moved", 2, None)]
with mock.patch.object(repair, "find", lambda: items), mock.patch.object(repair, "ERRORS", []):
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Find repairs" and b.isVisibleTo(a)][0].click()
app.processEvents()
tick = cp.fields.get(CK.N("Rep_ctrl_zero"))
check("Find repairs: each repair a tick box on the page, ticked", tick is not None and tick.widget.isChecked() and
      tick.widget.isVisibleTo(a))
done = []
with mock.patch.object(repair, "apply", lambda ids, its: done.append(ids) or []), \
        mock.patch.object(repair, "find", lambda: []), mock.patch.object(repair, "ERRORS", []), \
        mock.patch.object(ui, "report_window", lambda *x, **k: None):
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Apply the ticked repairs" and
     b.isVisibleTo(a)][0].click()
check("Apply the ticked repairs: the ticked ones (read from the page)", done == [["ctrl_zero"]])
f.go(("organize", None), as_tool=True); app.processEvents()
op = a.pages["organize"]
from gus_rigtool.core import organize
plan = [{"node": "|body_geo", "name": "body_geo", "dest": "geo", "why": "a mesh", "kind": "mesh"},
        {"node": "|L_arm_jnt", "name": "L_arm_jnt", "dest": "skeleton", "why": "a joint", "kind": "joint"}]
with mock.patch.object(organize, "analyze", lambda o=None: [dict(r) for r in plan]):
    [b for b in a.findChildren(QtWidgets.QPushButton) if b.text() == "Analyze the Outliner" and b.isVisibleTo(a)][0].click()
app.processEvents()
dest1 = op.fields.get(OT.N("Dest1"))
check("Analyze: the plan on the page, a row per item with where it goes", dest1 is not None and
      dest1.widget.isVisibleTo(a) and OT._plan[OT._P["p"]][1]["dest"] == "skeleton")
dest1.widget.setCurrentIndex(organize.DESTS.index("leave")); app.processEvents()
check("...change a row's place: the plan changes", OT._plan[OT._P["p"]][1]["dest"] == "leave")

# --- 5. nothing cut off
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
check("nothing cut off: Checker, Organize, Publish (with their rows), 300 / 420 / 700 px, normal and wider font",
      not crops)
if crops:
    print("  ", list(crops.items())[:4])
print("%d/%d passed" % (sum(ok), len(ok)))
