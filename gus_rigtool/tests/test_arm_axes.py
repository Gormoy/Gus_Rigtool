# Arm: the wrist (and hand) keep the forearm's axes; the clavicle pin points to the front (+Z) on both sides
exec(open("fakemaya.py").read())
import numpy as np
from gus_rigtool.builder import build as bld, controls, guides
from gus_rigtool.core import curves as cv
shapes = {}
real = controls.curves.create_curve_control
def spy(name, data, style):
    shapes[name] = data
    return real(name, data, style)
controls.curves.create_curve_control = spy
bld.biped(180)
for g in guides.module_groups():                 # put the hand guide off the forearm line (like the hare)
    i = guides.read(g)
    if i["type"] == "arm":
        h = i["guides"]["hand"]; p = cmds.xform(h, query=True, worldSpace=True, translation=True)
        cmds.xform(h, worldSpace=True, translation=[p[0], p[1] - 8, p[2] + 6])
bld.build_all(180)
A = lambda n: np.array(world(S.get(n))).reshape(4, 4)
for side in "LR":
    r, w, hd = A(side + "_radius_jnt"), A(side + "_wrist_jnt"), A(side + "_hand_jnt")
    print(side, "wrist axes == forearm axes:", np.allclose(r[:3, :3], w[:3, :3], atol=1e-5),
          "| hand too:", np.allclose(r[:3, :3], hd[:3, :3], atol=1e-5))
    stick = shapes[side + "_clavicle_FK_ctrl"][0]["points"]       # the pin's stick: base -> tip
    tip = np.array(stick[1]) - np.array(stick[0])
    m = A(side + "_clavicle_FK_ctrl")
    d = np.array(tip) @ m[:3, :3]
    print(side, "clavicle pin points (world):", np.round(d / np.linalg.norm(d), 3))
# the Checker's new twist check: our arm passes; a wrist turned 60 degrees around its bone is found
from gus_rigtool.tools import checker
print("twisted joints in the built rig:", [j.split("|")[-1] for j in checker.find_jnt_twist([], 30)])
j = S.get("L_wrist_jnt"); j.attrs["jointOrient"] = [60.0, 0.0, 0.0]
print("after turning L_wrist 60 deg:", [x.split("|")[-1] for x in checker.find_jnt_twist([], 30)])
