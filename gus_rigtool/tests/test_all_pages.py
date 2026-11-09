# Every tool page builds with the strict fake UI (a row only takes as many items as it has columns), no errors
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
for name in ("scriptJob", "headsUpDisplay", "playbackOptions", "workspace", "channelBox", "iconTextCheckBox",
             "shelfLayout", "nodeIconButton", "colorIndexSliderGrp", "canvas", "image", "palettePort",
             "attrColorSliderGrp", "swatchDisplayPort", "checkBoxGrp", "textFieldButtonGrp", "radioCollection",
             "radioButton", "iconTextRadioButton", "iconTextRadioCollection", "intSlider", "floatSlider"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool import registry
from gus_rigtool.core import ui
errors = []
ui.report_error = lambda e, where="": errors.append("%s: %s: %s" % (where, type(e).__name__, e))
for key, label, _m, _s in registry.TOOLS + [p[:4] for p in registry.PANELS]:
    _cur[0] = None
    root = cmds.columnLayout("root_" + key)
    before = len(errors)
    ui._build_tool(key, "t_%s_" % key)
    print("%-9s %s" % (key, "ok" if len(errors) == before else "FAILED"))
print("\n".join(errors) or "no errors")
# the old 3.0.0 bug is caught: a third item in a 2-slot row
_cur[0] = None; cmds.columnLayout("probe"); cmds.rowLayout(numberOfColumns=2); cmds.text(label="a"); cmds.text(label="b")
try:
    cmds.text(label="c"); print("strict rows: NOT working")
except RuntimeError:
    print("strict rows: a third item in a 2-slot row is refused, like Maya")
# safety net: a tool that breaks inside a full row still leaves the window going
from gus_rigtool.tools import skin_tool
real = skin_tool.build
def broken(prefix):
    cmds.rowLayout(numberOfColumns=1); cmds.text(label="a"); cmds.text(label="b")
skin_tool.build = broken
_cur[0] = None; cmds.columnLayout("page"); start = len(errors)
ui._build_tool("skin", "x_skin_")
print("broken tool reported:", len(errors) - start, "| message on its own page:",
      any(v.get("parent") == "page" and "could not open" in str(v.get("label")) for v in UI.values()))
skin_tool.build = real
