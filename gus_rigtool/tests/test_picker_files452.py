# 4.5.2: export / import a picker file (take it home), a non-picker file refused
import os, sys, tempfile, json
exec(open("fakemaya.py").read())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import pickmodel as PM
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
pk = {"version": PM.VERSION, "pages": [{"name": "Body", "width": 400, "height": 400, "bg": "",
      "items": [{"id": "i7", "kind": "select", "nodes": ["head_ctrl"], "x": 1, "y": 2, "w": 20, "h": 20}]}]}
path = os.path.join(tempfile.mkdtemp(), "hero_picker.json")
PM.export_file(pk, path)
got = PM.import_file(path)
check("exported and imported back the same", got["pages"][0]["items"][0]["nodes"] == ["head_ctrl"] and got["pages"][0]["name"] == "Body")
bad = path.replace("hero", "bad"); json.dump({"poses": 1}, open(bad, "w"))
try:
    PM.import_file(bad); check("a file that isn't a picker is refused", False)
except RuntimeError as e:
    check("a file that isn't a picker is refused", "isn't a Gus Animtool picker" in str(e))
# saving into a rig whose top group is locked (published): unlocked for the save, locked again
top = cmds.createNode("transform", name="rig_grp"); t = cmds.createNode("transform", name="head_ctrl", parent=top)
cmds.createNode("nurbsCurve", name="head_ctrlShape", parent=t)
cmds.lockNode(top, lock=True)
node = PM.save_in_rig(pk, "")
check("saved into a locked (published) rig, still locked after", node.endswith("rig_grp") and cmds.lockNode(top, query=True, lock=True)[0]
      and PM.rig_picker("") is not None)
_n(top).referenced = True
try:
    PM.save_in_rig(pk, ""); check("a referenced rig can't be written into", False)
except RuntimeError as e:
    check("a referenced rig can't be written into", "referenced" in str(e))
print("ALL OK" if all(ok) else "SOME FAILED")
