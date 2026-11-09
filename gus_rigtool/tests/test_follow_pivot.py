exec(open("fakemaya.py").read())
import numpy as np
def deleteAttr(node, attribute=None):
    _n(node).user.pop(attribute, None)
cmds.deleteAttr=deleteAttr
from gus_rigtool.core import follow, mirror_engine as me
A=lambda m: np.array(m).reshape(4,4)
ok=[]
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ")+label)
def ctrl(name, pos, rot=(0,0,0), parent=None):
    off=S.create("transform", name+"_offset", _n(parent) if parent else None)
    off.attrs["translate"]=list(pos); off.attrs["rotate"]=list(rot)
    c=S.create("transform", name, off); S.create("nurbsCurve", name+"Shape", c); return c.name
def pos(n): return A(world(_n(n)))[3,:3].copy()
def axes(n):
    m=A(world(_n(n)))[:3,:3]; return m/np.linalg.norm(m,axis=1)[:,None]

eye=ctrl("L_eye_ctrl",[3,160,5],(0,30,0))                 # driver turned 30 on Y
lid=ctrl("L_upLid_ctrl",[3.2,161,6.5],(20,0,10))          # lid with its own axes
loc=S.create("transform","lidPivot_loc"); loc.attrs["translate"]=[3,160,4]
# ribbon-style copier joint
boff=S.create("transform","L_upLid_bind_offset"); boff.attrs["translate"]=[3.2,161,6.4]; boff.attrs["rotate"]=[20,0,10]
S.create("joint","L_upLid_bind",boff)
for ch in ("translate","rotate"): connectAttr(lid+"."+ch, "L_upLid_bind."+ch)

piv=follow.point_of(["lidPivot_loc"])
check("point_of an object = its position", np.allclose(piv,[3,160,4]))
loc2=S.create("transform","lidPivot2_loc"); loc2.attrs["translate"]=[5,162,6]
check("point_of several = their centre", np.allclose(follow.point_of(["lidPivot_loc","lidPivot2_loc"]),[4,161,5]))
try: follow.point_of([]); check("point_of nothing raises", False)
except RuntimeError: check("point_of nothing raises", True)

p0={n: pos(n) for n in (lid,"L_upLid_bind")}
done, sk = follow.add(eye, [lid], ("rotate",), "control", 0.5, pivot=piv, axes="own")
check("added", done and not sk)
sp=S.get("L_upLid_ctrl_followSpace")
check("space at the picked pivot", np.allclose(pos(sp.name),[3,160,4]))
check("space keeps the lid's own axes", np.allclose(axes(sp.name), axes("L_upLid_ctrl_offset"), atol=1e-6))
check("no jump on add", all(np.allclose(pos(n),p0[n]) for n in p0))
check("meta remembers pivot and axes", follow._meta(S.get("L_upLid_ctrl_follow").name)["axes"]=="own"
      and follow._meta(S.get("L_upLid_ctrl_follow").name)["pivot"].startswith("3,160,4"))
# rotate: follow.rotate = eye.rotate * 0.5, around the picked pivot, in the lid's axes
for f in ("L_upLid_ctrl_follow","L_upLid_ctrl_jnt0_follow"):
    S.get(f).attrs["rotate"]=[10,0,0]
R=A(me.euler_matrix([10,0,0],0))[:3,:3]
for n in (lid,"L_upLid_bind"):
    spn = "L_upLid_ctrl_followSpace" if n==lid else "L_upLid_ctrl_jnt0_followSpace"
    ax=axes(spn); exp=(p0[n]-[3,160,4])@ax.T@R@ax+[3,160,4]
    check("%s turns around the picked pivot on its own axes" % n, np.allclose(pos(n),exp,atol=1e-6))
for f in ("L_upLid_ctrl_follow","L_upLid_ctrl_jnt0_follow"): S.get(f).attrs["rotate"]=[0,0,0]

# pivot on each control, world axes
lo=ctrl("L_loLid_ctrl",[3.2,159,6.5],(-20,0,0))
follow.add(eye, [lo], ("rotate",), "control", 1.0, pivot="control", axes="world")
sp2="L_loLid_ctrl_followSpace"
check("pivot 'control' = on the control", np.allclose(pos(sp2),[3.2,159,6.5]))
check("axes 'world'", np.allclose(axes(sp2), np.eye(3), atol=1e-6))

# default unchanged: at the driver with its axes
br=ctrl("L_brow_ctrl",[3,165,6])
follow.add(eye, [br])
check("default still at the driver", np.allclose(pos("L_brow_ctrl_followSpace"),[3,160,5])
      and np.allclose(axes("L_brow_ctrl_followSpace"), axes(eye), atol=1e-6))

# move the pivot of an existing follow: no jump, then turns around the new pivot
pb=pos(br)
n=follow.move_pivot([br], [3,160,4], "own")
check("move_pivot count", n==1)
check("move_pivot: no jump", np.allclose(pos(br),pb))
check("move_pivot: space moved", np.allclose(pos("L_brow_ctrl_followSpace"),[3,160,4])
      and np.allclose(axes("L_brow_ctrl_followSpace"), axes("L_brow_ctrl_offset"), atol=1e-6))
check("move_pivot: meta updated", follow._meta(S.get("L_brow_ctrl_follow").name)["axes"]=="own")
# the copier follow moves too, joint stays
pj=pos("L_upLid_bind"); pl=pos(lid)
follow.move_pivot([lid], "driver", "driver")
check("move_pivot: lid + its joint stay", np.allclose(pos("L_upLid_bind"),pj) and np.allclose(pos(lid),pl))
check("move_pivot: joint's space at the driver", np.allclose(pos("L_upLid_ctrl_jnt0_followSpace"),[3,160,5]))
# not at rest -> refuse
S.get("L_brow_ctrl_follow").attrs["rotate"]=[5,0,0]
try: follow.move_pivot([br], "control", "world"); check("move_pivot refuses when not at rest", False)
except RuntimeError: check("move_pivot refuses when not at rest", True)
S.get("L_brow_ctrl_follow").attrs["rotate"]=[0,0,0]
# remove still works
check("remove", follow.remove([br, lid, lo])==3 and np.allclose(pos(lid),p0[lid]))
print("ALL OK" if all(ok) else "SOME FAILED")
