# Organize tab: Analyze fills one row per item with a destination menu; changing a row changes the plan
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool.tools import organize_tool as ot
from gus_rigtool.core import ui
a = cmds.ls(cmds.createNode("transform", name="arm_ctrls"), long=True)[0]
c = cmds.createNode("transform", name="L_arm_ctrl", parent=a); cmds.createNode("nurbsCurve", name="L_arm_ctrlShape", parent=c)
m = cmds.ls(cmds.createNode("transform", name="body_geo"), long=True)[0]; cmds.createNode("mesh", name="body_geoShape", parent=m)
_cur[0] = None; cmds.columnLayout("root"); ui._build_tool("organize", "p_organize_")
ot._P["p"] = "p_organize_"; ot.analyze()
rows = ot._plan["p_organize_"]
print("rows:", [(r["name"], r["dest"]) for r in rows])
print("menus:", [UI["p_organize_Dest%d" % i]["select"] for i in range(len(rows))])
cmds.optionMenu("p_organize_Dest1", edit=True, select=5); ot._row_changed(1)
print("after changing row 2 to leave:", [(r["name"], r["dest"]) for r in rows])
print("light:", ot._light()[1])
