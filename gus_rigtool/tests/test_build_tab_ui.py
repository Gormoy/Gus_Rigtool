import sys, types, json
from unittest import mock
maya=types.ModuleType("maya"); cmds=mock.MagicMock(); mel=mock.MagicMock(); api=types.ModuleType("maya.api"); om=mock.MagicMock()
maya.cmds=cmds; maya.mel=mel; maya.api=api; api.OpenMaya=om
sys.modules.update({"maya":maya,"maya.cmds":cmds,"maya.mel":mel,"maya.api":api,"maya.api.OpenMaya":om})
import os
sys.path.insert(0, os.environ.get("GUS_RIGTOOL_PARENT") or os.path.abspath(os.path.join(os.getcwd(), "..", "..")))
store={}
cmds.optionVar.side_effect=lambda **k: (k["exists"] in store) if "exists" in k else (store.get(k["query"]) if "query" in k else store.__setitem__(k["stringValue"][0], k["stringValue"][1]))
cmds.objExists.return_value=False
def wc(*a,**k):
    if "childArray" in k: raise TypeError("Invalid flag 'childArray'")
    return False if k.get("exists") else (a[0] if a else "wc")
cmds.workspaceControl.side_effect=wc
built=set()
cmds.formLayout.side_effect=lambda *a,**k: (a[0] in built) if k.get("exists") else (built.add(a[0]) or a[0]) if a else "form"
# UI queries return plausible values
cmds.radioButtonGrp.side_effect=lambda *a,**k: 1 if k.get("query") else "rb"
cmds.optionMenu.side_effect=lambda *a,**k: (1 if k.get("select") is True else "X") if k.get("query") else "om"
cmds.checkBox.side_effect=lambda *a,**k: False if k.get("query") else "cb"
cmds.textField.side_effect=lambda *a,**k: "L_" if k.get("query") else "tf"
cmds.textFieldGrp.side_effect=lambda *a,**k: "_grp" if k.get("query") else "tfg"
cmds.floatField.side_effect=lambda *a,**k: 1.2 if k.get("query") else "ff"
cmds.floatFieldGrp.side_effect=lambda *a,**k: [0.0,0.0,0.0] if k.get("query") else "ffg"
cmds.floatSliderGrp.side_effect=lambda *a,**k: 1.0 if k.get("query") else "fsg"
cmds.colorSliderGrp.side_effect=lambda *a,**k: [1.0,0.0,0.0] if k.get("query") else "csg"
cmds.text.side_effect=lambda *a,**k: True if k.get("exists") else "txt"
cmds.tabLayout.side_effect=lambda *a,**k: 6 if k.get("numberOfChildren") else (1 if k.get("selectTabIndex") is True else "tabs")
cmds.ls.return_value=[]
cmds.intField.side_effect=lambda *a,**k: 5 if k.get("query") else "if"
cmds.undoInfo.side_effect=lambda *a,**k: True if k.get("query") else None
cmds.listRelatives.return_value=[]
from gus_rigtool.tools import build_tab as bt
from gus_rigtool.core import ui
errs=[]; ui.report_error=lambda e,w="": errs.append(repr(e))
bt.build("B_"); print("build tab built; errors:", errs)
