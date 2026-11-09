exec(open("fakemaya.py").read())
from gus_rigtool.builder import chain
c=S.create("transform","crv"); S.create("nurbsCurve","crvShape",c)
# curve param p -> point on a quarter circle with uneven parameterisation (p^2)
import math
def poc(shape, parameter=0, turnOnPercentage=True, position=True):
    a=(parameter**2)*math.pi/2; return [10*math.cos(a), 10*math.sin(a), 0]
cmds.pointOnCurve=poc
pts=chain.positions_from_curve("crv", 5)
d=[round(math.dist(a,b),3) for a,b in zip(pts[:-1],pts[1:])]
print("even spacing:", d, "| ends:", [round(v,3) for v in pts[0]], [round(v,3) for v in pts[-1]])
