# 4.5.0: picker editing - snap to other buttons (edges / centres, guide lines), same size, space with a gap
import os, sys
exec(open("fakemaya.py").read())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import pickmodel as PM
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def b(x, y, w=20.0, h=20.0, i=None):
    return {"id": i or "%s_%s" % (x, y), "x": float(x), "y": float(y), "w": w, "h": h}
other = b(100, 50)
mov = b(0, 0)
dx, dy, g = PM.snap([mov], [other], 103.0, 30.0, tol=6.0)          # left edge 3 off other's left edge
check("snaps the left edges together (3 off -> 0)", dx == 100.0 and dy == 30.0 and g and g[0][0] == "v" and g[0][1] == 100.0)
dx, dy, g = PM.snap([mov], [other], 40.0, 52.0, tol=6.0)            # top 2 off other's top, far in x
check("snaps tops, x left alone", dx == 40.0 and dy == 50.0 and [k for k, *_ in g] == ["h"])
dx, dy, g = PM.snap([mov], [other], 140.0, 140.0, tol=6.0)
check("nothing near: no snap, no guides", (dx, dy, g) == (140.0, 140.0, []))
big = b(200, 0, 60, 20)
dx, dy, g = PM.snap([mov], [big], 219.0, 0.0, tol=2.0)              # centres 230 vs 229
check("centres line up too", dx == 220.0)
two = [b(0, 0, i="a"), b(30, 0, i="b")]
dx, dy, g = PM.snap(two, [b(53, 80)], 1.0, 0.0, tol=3.0)          
check("a group snaps by its whole box (right edge 51 -> 53)", dx == 3.0 and g)
row = [b(0, 0, 10, 10, "r1"), b(50, 5, 20, 10, "r2"), b(15, 9, 10, 10, "r3")]
PM.space(row, 4.0, "x")
xs = sorted((i["x"], i["w"]) for i in row)
check("space across: gap 4 from the left-most, y kept", [x for x, _w in xs] == [0.0, 14.0, 28.0]
      and [i["y"] for i in row] == [0.0, 5.0, 9.0])
col = [b(0, 0, 10, 10, "c1"), b(0, 40, 10, 30, "c2")]
PM.space(col, 2.0, "y")
check("space down", col[1]["y"] == 12.0)
items = [b(0, 0, 10, 10, "s1"), b(0, 0, 30, 5, "s2")]
PM.same_size(items, {"w": 25.0, "h": 15.0})
check("same size", all((i["w"], i["h"]) == (25.0, 15.0) for i in items))
print("ALL OK" if all(ok) else "SOME FAILED")
