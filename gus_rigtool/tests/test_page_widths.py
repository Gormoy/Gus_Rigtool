# 5.3.3: every page fits a narrow window (no horizontal scroll bar, no buttons cut off on the right): built with
# the fake UI, the width each page asks for is estimated - long labels no longer widen it (they take the column's
# width, long texts wrap)
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read()); exec(open("widths.py").read())
import sys
from unittest import mock
for name in ("scriptJob", "headsUpDisplay", "playbackOptions", "workspace", "channelBox", "iconTextCheckBox",
             "shelfLayout", "nodeIconButton", "colorIndexSliderGrp", "canvas", "image", "palettePort",
             "attrColorSliderGrp", "swatchDisplayPort", "checkBoxGrp", "textFieldButtonGrp", "radioCollection",
             "radioButton", "iconTextRadioButton", "iconTextRadioCollection", "intSlider", "floatSlider"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(str(c).split("|")[-1]) or {}).get("kind", "")
from gus_rigtool import registry
from gus_rigtool.core import ui
ui.report_error = lambda e, where="": print("ERROR", where, e)
LIMIT = 440
wide = []
for key, label, _m, _s in registry.TOOLS + [p[:4] for p in registry.PANELS]:
    _cur[0] = None
    root = cmds.columnLayout("root_" + key, adjustableColumn=True)
    _k, label, _m, sub = registry.get(key)
    ui.header(label, sub, pop_key=key)                    # 5.4.0: the title, the subtitle and the step line too
    ui.where_line(key)
    ui._build_tool(key, "t_%s_" % key)
    out = []
    w = need(root, out)
    if w > LIMIT:
        wide.append("%s %d: %s" % (key, w, "; ".join("%d %s" % (o[0], o[3]) for o in sorted(out, reverse=True)[:3])))
print("\n".join(wide) or "every page fits %d px" % LIMIT)
# a callback that adds to its page later (the Build page's module form) fits too
_cur[0] = None
col = cmds.columnLayout("gusrig_main_panel_col", adjustableColumn=True)
state = {"p": "x_"}
ui.bind(state, lambda: cmds.button(label="A very long button label that would make the page wider than the window"))()
btn = [v for v in UI.values() if v.get("kind") == "button" and "very long" in str(v.get("label"))][0]
print("5.4.1: a button added by a callback keeps its own width (no 1-pixel buttons), long label shortened:",
      "width" not in btn and len(btn["label"]) <= 55 and "very long" in btn.get("annotation", ""))
outside = cmds.columnLayout("someDialog_col", adjustableColumn=True)
ui.bind(state, lambda: cmds.button(label="dialog button"))()
dlg = [v for v in UI.values() if v.get("kind") == "button" and v.get("label") == "dialog button"][0]
print("a dialog window's button is left alone:", "width" not in dlg)
print("cmds.button is back to Maya's own after:", not getattr(cmds.button, "_gus_fit", False))
sys.exit(1 if wide else 0)
