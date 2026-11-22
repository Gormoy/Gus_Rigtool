# 5.7.9.1: the bar's options strip shows one tool at a time (5.7.9 stacked them: the old title and size rows stayed),
# right-click the same tile again closes it, another tile takes its place; a row always shows its settings on top
# (Gus); the shelf's new icons under new file names (Maya kept the old pictures by name until a restart)
exec(open("test_570.py").read().split("# --- 1.")[0])
from gus_rigtool.newui import favourites as FV
from gus_rigtool import main as M
from gus_rigtool.core import utils

def settle():
    for _ in range(3):
        app.processEvents()

def shown_titles(b):
    return [w.text() for w in b.strip.findChildren(QtWidgets.QLabel) if w.isVisibleTo(b.strip) and
            ("options" in w.text() or "The bar" in w.text())]

FV.set_keys(["select", "groups", "controls_tab", "ribbon"])
utils.save_setting(FV.BAR_KEY, {"size": 34})
b = FV.FavBar(); b.show(); settle()
b.right_click("groups"); settle()
b.right_click("select"); settle()
check("right-click Groups, then Select: only Select's options (5.7.9: both, on top of each other)",
      shown_titles(b) == ["<b>Select</b>  options"])
check("...one size slider at most, one close button", len([w for w in b.strip.findChildren(QtWidgets.QToolButton)
                                                           if w.isVisibleTo(b.strip) and w.text() == "×"]) == 1)
b.right_click("select"); settle()
check("right-click Select again: the strip closes", not b.strip.isVisible())
b.right_click("groups"); settle()
b.show_bar_settings(); settle()
check("the bar's settings after a tool's options: only the bar's", shown_titles(b) == ["<b>The bar</b>"])
b.toggle_bar_settings(); settle()
check("...= again: closed", not b.strip.isVisible())
check("a row: its settings always on top (Gus) - Row / 2R / Col / Grid, names, size",
      set(b.mode_buttons) == {"row", "2r", "col", "grid"} and b.slider.isVisibleTo(b))
icons = [M._icon(k[1]) for g in M._shelf_buttons() for k in g]
check("the shelf's icons: the new ones under new names (gr2_...) - no restart needed to see them",
      all("/gr2_" in p for p in icons))
check("...the legacy look's letter icons kept under their own names", os.path.isfile(os.path.join(ROOT, "icons",
                                                                                                 "gr_home.png")))
print("%d/%d passed" % (sum(ok), len(ok)))
