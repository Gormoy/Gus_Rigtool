# 4.5.1: a rig referenced after Gus Animtool opened: clicking its controls picks it in the character menu
# (no 'Value is out of range: 2'); a space value past its names shows 'space N (no name)'
import os, sys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
A.profile = lambda ns=None: {}
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def curve(name):
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name.split(":")[-1] + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
curve("cam_ctrl")                                           # something in the scene before (no namespace)
cmds.optionMenu(A.P + "Char")
A.fill_characters()
check("the menu lists what's there when the window opens", cmds.optionMenu(A.P + "Char", query=True, numberOfItems=True) == 1)
try:
    cmds.optionMenu(A.P + "Char", edit=True, select=2); check("the fake menu refuses item 2 like Maya", False)
except RuntimeError as e:
    check("the fake menu refuses item 2 like Maya", "Value is out of range: 2" in str(e))
# the rig gets referenced (a namespace) after the window opened, then a control is clicked
c = curve("CHR_Tubero_Rig_V5:R_Scapula_Ctrl")
A.selected = lambda: [c]
A.fill_space_menus = lambda *a: None
A._follow_selection()
check("clicking its control: no error, the menu lists it and picks it",
      cmds.optionMenu(A.P + "Char", query=True, numberOfItems=True) == 2
      and A.current_character() == "CHR_Tubero_Rig_V5:")
check("menu_select never asks for an item that isn't there", A.menu_select(A.P + "Char", 5) is False)
# a space attribute whose value is past its names
cmds.optionMenu(A.P + "SpaceAttr"); cmds.optionMenu(A.P + "SpaceValue")
cmds.menuItem(label="space", parent=A.P + "SpaceAttr")
cmds.addAttr(c, longName="space", attributeType="enum", enumName="world:chest")
cmds.setAttr(c + ".space", 2)
A.space_attrs = lambda n: [("space", ["world", "chest"])]
A.fill_space_values()
check("space value 2 with 2 names: shown as 'space 2 (no name)', no error",
      cmds.optionMenu(A.P + "SpaceValue", query=True, value=True) == "space 2 (no name)" and A._space_index() == 2)
cmds.setAttr(c + ".space", 1)
A.fill_space_values()
check("space value 1: 'chest' picked", cmds.optionMenu(A.P + "SpaceValue", query=True, value=True) == "chest"
      and A._space_index() == 1)
print("ALL OK" if all(ok) else "SOME FAILED")
