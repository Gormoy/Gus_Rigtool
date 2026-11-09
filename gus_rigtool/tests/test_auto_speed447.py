# 4.4.7: finding the controls asks Maya for the scene's curves a handful of times, not once per curve; one pair
# of sides (Lf_arm / Rt_arm) is enough to find the left / right tokens
import os, sys
exec(open("fakemaya.py").read())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
A.profile = lambda ns=None: {}
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def curve(name, parent=None):
    t = cmds.createNode("transform", name=name, parent=parent)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    return cmds.ls(t, long=True)[0]
rig = cmds.createNode("transform", name="rig")
for i in range(120):
    curve("ctl%03d" % i, rig)
curve("Lf_arm", rig); curve("Rt_arm", rig)
calls = [0]
_ls = cmds.ls
def counting_ls(*a, **k):
    if k.get("type") == "nurbsCurve":
        calls[0] += 1
    return _ls(*a, **k)
cmds.ls = counting_ls
ctrls = A.character_controls("")
check("all 122 found", len(ctrls) == 122)
check("find all controls: the scene listed at most twice", calls[0] <= 2)
calls[0] = 0
flags = [A.is_control(c) for c in ctrls]                 # what hide / isolate / reset do, control by control
check("asking 'is this a control?' 122 times right after: at most 1 more listing", all(flags) and calls[0] <= 1)
cmds.ls = _ls
A._pairs_cache.clear()
check("one pair Lf_arm / Rt_arm finds Lf_ / Rt_", ("Lf_", "Rt_") in A.auto_pairs(""))
print("ALL OK" if all(ok) else "SOME FAILED")
