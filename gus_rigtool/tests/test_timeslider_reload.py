# Time Slider menu after Reset / Update (the module reloaded): Maya gives back our old Python hook as text, so
# Maya's own command must come from what we kept (or Maya's default) - else only our items show
import os, sys
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
import maya.mel as mel
from gus_animtool import timeslider as TS
from gus_animtool import anim as A
A.opt = lambda k, d: d
OV = {}
cmds.optionVar = lambda *a, **k: (k["exists"] in OV) if "exists" in k else (OV.get(k["query"]) if "query" in k else OV.__setitem__(*k["stringValue"]))
items = []                                      # what's in the menu
ran = []
def maya_fill(cmd):
    ran.append(cmd)
    if cmd.startswith("exists"):
        return 1
    if cmd.startswith("updateTimeSliderMenu") and not items:        # Maya only fills an empty menu
        items.extend(["Playblast", "Keys", "Sound"])
mel.eval = maya_fill
hook = {"pmc": "updateTimeSliderMenu TimeSliderMenu"}
def popupMenu(*a, **k):
    if k.get("exists"): return a[0] == "TimeSliderMenu"
    if k.get("query") and k.get("postMenuCommand"): return hook["pmc"]
    if k.get("query") and k.get("itemArray"): return ["TimeSliderMenu|" + i for i in items]
    if k.get("edit"): hook["pmc"] = k["postMenuCommand"]
cmds.popupMenu = popupMenu
def menuItem(*a, **k):
    if k.get("exists"): return a[0] in items
    if a: items.append(a[0])
cmds.menuItem = menuItem
cmds.deleteUI = lambda n, **k: items.remove(n)
cmds.setParent = lambda *a, **k: None

print("first install:", TS.install(), "| kept:", OV)
hook["pmc"](); print("menu opens:", items)
# Reset / Update: a fresh module; Maya hands back our old hook as text
TS._state.update(menu=None, original=None); hook["pmc"] = "<function _post at 0x0000021>"
items[:] = [TS.DIV, TS.SUB]                    # the worst case: only ours left in the menu
TS.install(); print("after a reload, original:", TS._state["original"])
hook["pmc"](); print("menu opens:", items)
# nothing kept and nothing usable: Maya's default build
OV.clear(); TS._state.update(menu=None, original=None); hook["pmc"] = "<function _post at 0x1>"; items[:] = []
TS.install(); hook["pmc"](); print("no record either -> Maya's default:", TS._state["original"], "|", items)
# Maya's command didn't fill it (menu already had ours): ours are taken out first, so it does
items[:] = [TS.DIV, TS.SUB]; hook["pmc"](); print("ours taken out before Maya runs:", items)
