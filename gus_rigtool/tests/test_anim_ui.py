# Gus Anim's window builds (fake UI) and its menus fill
import os, sys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.playbackOptions = mock.MagicMock(return_value=1.0); cmds.scriptJob = mock.MagicMock()
cmds.optionVar = mock.MagicMock(return_value=False)
cmds.intField = _make("intField")
cmds.workspace = mock.MagicMock(return_value="/proj"); cmds.floatSliderGrp = _make("floatSliderGrp"); cmds.textFieldGrp = _make("textFieldGrp"); cmds.textFieldButtonGrp = _make("textFieldButtonGrp")
import gus_anim as ga
cmds.workspaceControl = mock.MagicMock(return_value=False)
cmds.columnLayout = _make("columnLayout")
ga.show()
print("built:", "gusAnim_Root" in UI, "| char items:", UI["gusAnim_Char"].get("items"))
print("buttons:", sorted(v["label"] for v in UI.values() if v.get("kind") == "button"))
