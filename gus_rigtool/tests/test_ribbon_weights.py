# Ribbon / spline weights: the mid driver fades to zero at the ends; the end rows follow their end driver only
exec(open("fakemaya.py").read())
from gus_rigtool.builder import ribbons
pts = [[0, 0, z * 10.0] for z in range(5)]                       # 5 joints along +Z
drivers = []
for name, p in (("start", pts[0]), ("mid", pts[2]), ("end", pts[4])):
    d = S.create("joint", name); d.attrs["translate"] = list(p); drivers.append(d.name)
cvs = {"c%d" % i: [0, 0, z] for i, z in enumerate([0, 2.5, 7, 13, 20, 27, 33, 37.5, 40])}   # 9 rows
ribbons._cvs = lambda geo: [(k, i, len(cvs)) for i, k in enumerate(cvs)]
orig_xform = cmds.xform
cmds.xform = lambda n, **k: cvs[n] if n in cvs else orig_xform(n, **k)
got = {}
cmds.skinPercent = lambda sk, cv, transformValue=None: got.__setitem__(cv, dict(transformValue))
ribbons.even_weights("skin1", "srf", drivers)
for cv in cvs:
    w = got[cv]
    print(cv, "z=%-5s" % cvs[cv][2], " ".join("%s %.2f" % (k, v) for k, v in w.items()))
