# 5.4.2: a section opening / closing makes Maya measure the page again (sections inside sections were cut off:
# Ribbon > Make a surface, Follow > Follows in the scene); viewports hiding curves are found and fixed by Repair
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
import sys
from unittest import mock
from gus_rigtool.core import ui, repair
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

calls = []
cmds.evalDeferred = lambda fn, *a, **k: fn()                  # run at once here
cmds.objectTypeUI = lambda c: (UI.get(str(c).split("|")[-1]) or {}).get("kind", "")
def control(c, **k):
    if k.get("exists"):
        return str(c).split("|")[-1] in UI
    if k.get("fullPathName"):
        name, chain = str(c).split("|")[-1], []
        while name:
            chain.insert(0, name)
            name = (UI.get(name) or {}).get("parent")
        return "|".join(chain)
cmds.control = control
_fl = cmds.frameLayout
def frameLayout(*a, **k):
    if a and k.get("edit") and "collapse" in k:
        calls.append(("collapse", a[0].split("|")[-1], k["collapse"]))
    if a and k.get("query") and k.get("collapse"):
        return False
    return _fl(*a, **k)
cmds.frameLayout = frameLayout
_lay = getattr(cmds, "layout", None)
def layout(*a, **k):
    if k.get("edit") and "manage" in k:
        calls.append(("manage", a[0].split("|")[-1], k["manage"]))
        return
    if k.get("query") and k.get("fullPathName"):
        return control(a[0], fullPathName=True)
    return _lay(*a, **k) if _lay else None
cmds.layout = layout

panel = cmds.columnLayout("gusrig_ribbon_panel_col", adjustableColumn=True)
scroll = cmds.scrollLayout("gusrig_ribbon_scroll")
page = cmds.columnLayout("gusrig_ribbon_page", adjustableColumn=True)
with ui._Fit():
    outer = cmds.frameLayout("Make_a_surface", label="1. Make a surface", collapsable=True)
    cmds.columnLayout("outer_col", adjustableColumn=True)
    inner = cmds.frameLayout("Check_fix_curves", label="Check / fix curves, loft", collapsable=True, collapse=True)
check("a section made in a page gets open / close commands", callable(UI["Check_fix_curves"].get("expandCommand"))
      and callable(UI["Check_fix_curves"].get("collapseCommand")))
fitted = []
with mock.patch.object(ui, "fit_page", side_effect=lambda pg: fitted.append(pg.split("|")[-1]) or 1):
    UI["Check_fix_curves"]["expandCommand"]()                # you open the inner section
check("5.6.2: opening it sizes the whole page by the tool itself (Maya's own measure went stale)",
      fitted == ["gusrig_ribbon_page"])

# fit_page: the heights added up from the contents (Make controls: page 213 px with ~260 px in it)
TREE = {"pg": ("columnLayout", ["hdr", "light", "pres", "frm", "note"], 4, 213),
        "hdr": ("columnLayout", ["t1"], 0, 119), "t1": ("staticText", [], 0, 119),
        "light": ("staticText", [], 0, 34), "pres": ("rowLayout", [], 0, 25),
        "frm": ("frameLayout", ["fcol"], 0, 20), "fcol": ("columnLayout", ["b1", "b2"], 4, 10),
        "b1": ("button", [], 0, 26), "b2": ("button", [], 0, 34), "note": ("staticText", [], 0, 34)}
COLLAPSED = {"frm": False}
SET = {}
def q(fn, c, **k):
    kind, kids, spacing, h = TREE[c]
    if k.get("manage"):
        return True
    if k.get("collapse"):
        return COLLAPSED.get(c, False)
    if k.get("rowSpacing"):
        return spacing
    if k.get("marginHeight"):
        return 4
    if k.get("height"):
        return SET.get(c, h) if kind != "frameLayout" else 20
def column_edit(c, edit=False, height=None, **k):
    SET[c] = height
with mock.patch.object(ui, "_kind", side_effect=lambda c: TREE[c][0]), \
        mock.patch.object(ui, "_children", side_effect=lambda c: TREE[c][1]), \
        mock.patch.object(ui, "_q", side_effect=q), \
        mock.patch.object(cmds, "layout", side_effect=lambda c, **k: TREE.get(c, ("",))[0].endswith("Layout")), \
        mock.patch.object(cmds, "columnLayout", side_effect=column_edit):
    ui.fit_page("pg")
    print(SET)
    inner = 26 + 34 + 4
    check("an open section: its inside sized to its buttons", SET.get("fcol") == inner)
    check("the page: everything on it added up (+ a little room) - nothing below the edge",
          SET.get("pg") == 119 + 34 + 25 + (20 + 8 + inner + 4) + 34 + 4 * 4 + ui.PAGE_PAD)
    COLLAPSED["frm"] = True; SET.clear()
    ui.fit_page("pg")
    check("folded: the page shrinks to the title bar's height", SET.get("pg") == 119 + 34 + 25 + 20 + 34 + 16 + ui.PAGE_PAD)
check("cmds.frameLayout is back to Maya's own after the page", not getattr(cmds.frameLayout, "_gus_fit", False))

# viewports hiding curves
with mock.patch.object(cmds, "getPanel", lambda **k: ["modelPanel1", "modelPanel4"], create=True), \
        mock.patch.object(cmds, "modelEditor", side_effect=lambda p, **k: (p != "modelPanel4") if k.get("query")
                          else calls.append(("show curves", p)), create=True):
    check("modelPanel4 hides curves", repair.curveless_views() == ["modelPanel4"])
    it = repair._curveless_views()
    it.fix()
check("Repair shows curves there again", ("show curves", "modelPanel4") in calls)

# a page text whose label changes later (Mirror's preview, the Ribbon summary...): broken into the lines it has room for
_txt = cmds.text
def text(*a, **k):
    if a and k.get("query") and k.get("wordWrap"):
        return False
    if a and k.get("query") and k.get("height"):
        return 34
    return _txt(*a, **k)
cmds.text = text
t = cmds.text("Preview", label="", height=34, parent=page)
long_label = "Mirror: L_Sleeve_fol_01_ctrl ... L_Sleeve_fol_13_ctrl -> R_Sleeve_fol_01_ctrl ... (13 controls, shapes and colours)"
with ui._Fit():
    cmds.text("Preview", edit=True, label=long_label)
lab = UI["Preview"]["label"]
print(repr(lab))
check("a long new label: two lines (its height), no wider than a narrow page, the whole text in the tooltip",
      lab.count("\n") == 1 and max(len(x) for x in lab.split("\n")) <= 52 and UI["Preview"].get("annotation") ==
      long_label)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
