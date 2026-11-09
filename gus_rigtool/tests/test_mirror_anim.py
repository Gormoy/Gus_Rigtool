# Mirror animation: frames read, where keys land (offset, wrap), old keys replaced, all read before writing
exec(open("fakemaya.py").read())
from gus_rigtool.core import mirror_engine as me
now = {"t": 0.0}; log = []
cmds.keyframe = lambda *a, **k: [1.0, 5.0, 9.0]
cmds.currentTime = lambda *a, **k: now["t"] if k.get("query") else now.update(t=float(a[0]))
cmds.cutKey = lambda d, **k: log.append(("cut", d, k["time"]))
cmds.setKeyframe = lambda d, **k: log.append(("key", d, k["attribute"], k["time"], round(k["value"], 3)))
cmds.filterCurve = lambda *a, **k: None
cmds.listConnections = lambda *a, **k: None
cmds.objExists = lambda x: True
me._settable = lambda plug: not plug.endswith(("scaleX", "scaleY", "scaleZ"))
target = lambda s, d: ((now["t"], 0, 0), (0, 0, 0), (1, 1, 1))
for offset, wrap in ((0, False), (6, False), (6, True)):
    del log[:]
    n = me.bake_mirror([("L_a", "R_a")], target, lambda s: {"bend": now["t"] * 2}, 1, 13, offset, True, wrap)
    print("offset %d wrap %s: %d keys" % (offset, wrap, n), [x for x in log if x[0] == "cut"])
    print("   tx keys:", [(x[3], x[4]) for x in log if x[0] == "key" and x[2] == "translateX"])
    print("   bend keys:", [(x[3], x[4]) for x in log if x[0] == "key" and x[2] == "bend"])
print("time put back:", now["t"])
print("every frame:", me._frames(["L_a"], 1, 4, False))
