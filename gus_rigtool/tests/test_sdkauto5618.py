# 5.6.18: SDK tool Auto - the flips per driven node from how its parent is turned against its twin's:
# a ribbon mirrored with Z flipped (the Hare's eyelids) -> tz, rx, ry; an orientation mirror (X flipped) ->
# tx, ry, rz; a behaviour mirror (all flipped) -> translations only; not a clean mirror -> None (ticks used)
exec(open("fakemaya.py").read())
from gus_rigtool.tools import sdk_tool as T
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
CH = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX"]
def flipped(flips):
    return [c for c in CH if T.channel_sign(flips, c) == -1]
check("Z flipped (the eyelids): tz, rx, ry", flipped([1, 1, -1]) == ["translateZ", "rotateX", "rotateY"])
check("X flipped (orientation mirror): tx, ry, rz", flipped([-1, 1, 1]) == ["translateX", "rotateY", "rotateZ"])
check("behaviour (all flipped): the translations only", flipped([-1, -1, -1]) == ["translateX", "translateY",
                                                                                   "translateZ"])
check("can't tell: None (the ticks are used)", T.channel_sign([1, None, -1], "rotateX") is None and
      T.channel_sign([1, None, -1], "translateX") == 1)
# frames read from the parents
def grp(name, m):
    g = cmds.createNode("transform", name=name + "_par")
    cmds.xform(g, worldSpace=True, matrix=m)
    c = cmds.createNode("transform", name=name, parent=g)
    return cmds.ls(c, long=True)[0]
L = grp("L_lid_sdk", [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 3, 5, 1, 1])
R = grp("R_lid_sdk", [-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, -3, 5, 1, 1])     # x mirrored, z flipped
print(T.mirror_flips(L, R))
check("read from the parents: a ribbon mirrored with Z flipped -> [1, 1, -1]", T.mirror_flips(L, R) == [1, 1, -1])
src = open("../tools/sdk_tool.py").read()
check("Auto on by default; the twin driver's keys flipped when it moves the other way",
      '"auto": True' in src and 'floatScale=-1.0' in src)
print("%d/%d passed" % (sum(ok), len(ok)))
