exec(open("fakemaya.py").read())
import numpy as np
def deleteAttr(node, attribute=None):
    _n(node).user.pop(attribute, None)
cmds.deleteAttr=deleteAttr
from gus_rigtool.core import follow, mirror_engine as me
A=lambda m: np.array(m).reshape(4,4)
def ctrl(name, pos, parent=None):
    off=S.create("transform", name+"_offset", _n(parent) if parent else None); off.attrs["translate"]=list(pos)
    c=S.create("transform", name, off); S.create("nurbsCurve", name+"Shape", c); return c.name
jaw=ctrl("Jaw_ctrl",[0,150,2])
lip=ctrl("L_lipCorner_ctrl",[3,148,8]); low=ctrl("lowLip_ctrl",[0,147,9])
# ribbon 'pivot on shape' style: a joint copying the control's channels
boff=S.create("transform","lowLip_bind_offset"); boff.attrs["translate"]=[0,147,7]
bj=S.create("joint","lowLip_bind",boff)
for ch in ("translate","rotate"): connectAttr(low+"."+ch, "lowLip_bind."+ch)
done, skipped = follow.add(jaw, [lip, low], ("rotate",), "control", 0.5)
print("done:", done, skipped)
p0={n: A(world(_n(n)))[3,:3].copy() for n in (lip, low, "lowLip_bind")}
# emulate the network: follow.rotate = jaw.rotate * weight
_n(jaw).attrs["rotate"]=[20,0,0]
for c in ("L_lipCorner_ctrl","lowLip_ctrl","lowLip_ctrl_jnt0"):
    f=S.get(c+"_follow"); w=getAttr(("lowLip_ctrl" if "lowLip" in c else c)+".follow"); f.attrs["rotate"]=[20*w,0,0]
pivot=np.array([0,150,2.0])
for n in (lip, low, "lowLip_bind"):
    exp=(p0[n]-pivot)@A(me.euler_matrix([10,0,0],0))[:3,:3]+pivot
    print(n, "follows the jaw by half around its pivot:", np.allclose(A(world(_n(n)))[3,:3], exp, atol=1e-6))
print("list:", follow.all_follows())
follow.set_weight([lip], 0.25); print("weight now:", getAttr("L_lipCorner_ctrl.follow"))
_n(jaw).attrs["rotate"]=[0,0,0]
for c in ("L_lipCorner_ctrl","lowLip_ctrl","lowLip_ctrl_jnt0"): S.get(c+"_follow").attrs["rotate"]=[0,0,0]
print("removed:", follow.remove([lip, low]), "| lip back home:", np.allclose(A(world(_n(lip)))[3,:3], p0[lip]),
      "| bind back home:", np.allclose(A(world(S.get("lowLip_bind")))[3,:3], p0["lowLip_bind"]),
      "| groups left:", [n.name for n in S.nodes if "follow" in n.name.lower()], "| attr left:", "follow" in _n(lip).user)
